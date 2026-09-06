"""Query-family RunStore checks on private SQLite. Worker/HTTP/native are NOT RUN."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from backend.contracts.analytics import AnalyticsCancelRequest, AnalyticsConversationRequest, AnalyticsRunRequest
from backend.contracts.analytics_query import (
    ChannelFollowupQueryRequest,
    ChannelFollowupSnapshot,
    canonical_rfc3339,
    snapshot_digest,
)
from backend.contracts.analytics_query_run import (
    QUERY_CONTEXT_SCHEMA,
    QUERY_RUN_SCHEMA,
    AnalyticsQueryConversationRequest,
    AnalyticsQueryRunRequest,
    AnalyticsQueryRunSnapshot,
)
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal
from backend.services.analytics.catalog import bind_resolved_filters, bind_resolved_filters_from_metadata
from backend.services.analytics import jobs as jobs_mod
from backend.services.analytics.jobs import RunStore
from backend.services.analytics.resource_profile import canonical_json
from backend.tests.analytics_run_support import (
    accept, actor, make_store, observation, profile, sqlite_connection,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
SNAPSHOT_PATH = FIXTURE_DIR / "analytics_channel_followup_v1.json"
DIGEST = "a" * 64
PERMISSION = "synthetic-demo"
VALID_REQUEST = {
    "schema_version": "analytics-channel-followup/v1",
    "query_id": "channel_first_observed_followup",
    "query_version": "channel-followup-query/v1",
    "metric_id": "channel_first_observed_n_day_repeat",
    "metric_version": "channel-followup-metric/v1",
    "cohort_window": {"kind": "FIXED", "start_date": "2026-06-01", "end_date": "2026-09-01"},
    "observation_days": 30,
    "data_snapshot_ref": "synthetic-channel-followup-v1",
    "timezone": "Asia/Shanghai",
    "channel_ids": [],
    "cohort_ref": None,
    "product_ids": [],
    "exclude_low_price": False,
    "comparison": None,
}


def _sha(name: str) -> str:
    return hashlib.sha256(name.encode()).hexdigest()


def query_actor(name="alice", *, capabilities=None, scopes=None):
    return AnalyticsPrincipal(
        name,
        frozenset({"run:create", "run:read", "run:cancel"} if capabilities is None else capabilities),
        frozenset({"channel-followup-fixture"} if scopes is None else scopes),
    )


def golden_snapshot() -> ChannelFollowupSnapshot:
    return ChannelFollowupSnapshot.model_validate(json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8")))


def golden_descriptor(**changes):
    snap = golden_snapshot()
    payload = {
        "snapshot_id": snap.snapshot_id,
        "data_version": snap.data_version,
        "data_digest": snapshot_digest(snap),
        "as_of": canonical_rfc3339(snap.as_of),
        "timezone": snap.timezone,
        "physical_sha256": _sha("physical"),
    }
    payload.update(changes)
    return payload


def query_request(days=30, channel_ids=None) -> ChannelFollowupQueryRequest:
    payload = deepcopy(VALID_REQUEST)
    payload["observation_days"] = days
    if channel_ids is not None:
        payload["channel_ids"] = channel_ids
    return ChannelFollowupQueryRequest.model_validate(payload)


def make_query_store(path, **kwargs):
    path.mkdir(mode=0o700, exist_ok=True)
    return RunStore(path, kwargs.pop("resource_profile", profile()), family="channel_followup", **kwargs)


def query_conversation(store, principal=None, key="conversation"):
    return store.create_conversation(principal or query_actor(), key, AnalyticsQueryConversationRequest())


def query_accept(store, principal=None, *, key="run", conversation_id=None, parent=None, descriptor=None):
    principal = principal or query_actor()
    conv = conversation_id or query_conversation(store, principal).conversation_id
    return store.accept(
        principal, conv, key,
        AnalyticsQueryRunRequest(question="查看合成渠道后续购买", parent_run_id=parent),
        method_package_digest=DIGEST,
        fixture_descriptor=descriptor or golden_descriptor(),
    )


def test_fresh_query_create_reopen_and_old_b0_stays_b0(tmp_path):
    query_store = make_query_store(tmp_path / "query")
    accepted = query_accept(query_store)
    snapshot = query_store.get(query_actor(), accepted.run_id)
    assert isinstance(snapshot, AnalyticsQueryRunSnapshot)
    assert snapshot.schema_version == QUERY_RUN_SCHEMA
    assert snapshot.answer_mode == "DETERMINISTIC_TOOL"
    assert snapshot.result is None
    restored = RunStore(query_store.directory, profile(), family="channel_followup")
    assert restored.get(query_actor(), accepted.run_id).schema_version == QUERY_RUN_SCHEMA
    with sqlite_connection(query_store.path) as con:
        assert con.execute("SELECT value FROM metadata WHERE key='run_family'").fetchone()[0] == "channel_followup"
        assert con.execute("PRAGMA user_version").fetchone()[0] == 2
    with pytest.raises(ValueError):
        RunStore(query_store.directory, profile())

    b0 = make_store(tmp_path / "b0")
    b0_run = accept(b0)
    assert b0.get(actor(), b0_run.run_id).schema_version == "analytics-run-b0/v1"
    RunStore(b0.directory, profile())
    with pytest.raises(ValueError):
        RunStore(b0.directory, profile(), family="channel_followup")
    with sqlite_connection(b0.path) as con:
        assert con.execute("SELECT value FROM metadata WHERE key='run_family'").fetchone() is None


def test_missing_family_with_query_evidence_refuses_b0_downgrade(tmp_path):
    store = make_query_store(tmp_path / "query")
    accepted = query_accept(store)
    with sqlite_connection(store.path) as con:
        con.execute("DELETE FROM metadata WHERE key='run_family'")
        assert con.execute("SELECT request_json FROM runs WHERE run_id=?", (accepted.run_id,)).fetchone() is not None
    with pytest.raises(ValueError, match="query evidence"):
        RunStore(store.directory, profile())
    with pytest.raises(ValueError):
        RunStore(store.directory, profile(), family="channel_followup")


def test_unknown_family_metadata_is_not_overwritten(tmp_path):
    store = make_query_store(tmp_path / "query")
    query_accept(store)
    with sqlite_connection(store.path) as con:
        con.execute("UPDATE metadata SET value=? WHERE key='run_family'", ("mixed",))
    with pytest.raises(ValueError, match="unknown"):
        RunStore(store.directory, profile(), family="channel_followup")
    with sqlite_connection(store.path) as con:
        assert con.execute("SELECT value FROM metadata WHERE key='run_family'").fetchone()[0] == "mixed"


def test_accept_and_reserve_are_atomic_on_fault(tmp_path):
    store = make_query_store(tmp_path / "query")
    conv = query_conversation(store)

    def boom(point):
        if point == "accept:before_commit":
            raise RuntimeError("owned accept crash")

    store.fault_hook = boom
    with pytest.raises(RuntimeError, match="owned accept crash"):
        query_accept(store, conversation_id=conv.conversation_id, key="crash")
    with sqlite_connection(store.path) as con:
        assert con.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
        assert con.execute("SELECT count(*) FROM idempotency").fetchone()[0] == 1  # conversation only
    store.fault_hook = None
    accepted = query_accept(store, conversation_id=conv.conversation_id, key="crash")
    intent = store.claim_next(lambda owner: query_actor() if owner == "alice" else None)

    def boom_reserve(point):
        if point == "reserve:before_commit":
            raise RuntimeError("owned reserve crash")

    store.fault_hook = boom_reserve
    with pytest.raises(RuntimeError, match="owned reserve crash"):
        store.reserve_step(query_actor(), intent.run_id, intent.attempt_id, "tool-1", request=query_request())
    with sqlite_connection(store.path) as con:
        assert con.execute("SELECT count(*) FROM steps").fetchone()[0] == 0
        assert con.execute("SELECT count(*) FROM idempotency WHERE operation='runtime.step-binding'").fetchone()[0] == 0
        assert con.execute("SELECT tool_steps_used FROM runs WHERE run_id=?", (accepted.run_id,)).fetchone()[0] == 0


def test_replay_same_key_and_condition_conflict(tmp_path):
    store = make_query_store(tmp_path / "query")
    conv = query_conversation(store)
    first = query_accept(store, conversation_id=conv.conversation_id)
    replay = query_accept(store, conversation_id=conv.conversation_id)
    assert replay == first
    with pytest.raises(AnalyticsError) as error:
        store.accept(
            query_actor(), conv.conversation_id, "run",
            AnalyticsQueryRunRequest(question="换一个问题"),
            method_package_digest=DIGEST,
            fixture_descriptor=golden_descriptor(),
        )
    assert error.value.status == 409
    with pytest.raises(AnalyticsError) as changed:
        store.accept(
            query_actor(), conv.conversation_id, "run",
            AnalyticsQueryRunRequest(question="查看合成渠道后续购买"),
            method_package_digest=DIGEST,
            fixture_descriptor=golden_descriptor(physical_sha256=_sha("other-physical")),
        )
    assert changed.value.status == 409


def test_actor_scope_and_capability_revocation(tmp_path):
    store = make_query_store(tmp_path / "query")
    accepted = query_accept(store)
    conv = store.get(query_actor(), accepted.run_id).conversation_id
    b0_only = query_actor(scopes={"b0-fixture"})
    reader = query_actor(capabilities={"run:read"})
    revoked = query_actor(capabilities=set())
    intent = store.claim_next(lambda owner: query_actor() if owner == "alice" else None)
    for op in (
        lambda: query_accept(store, b0_only, conversation_id=conv, key="run"),
        lambda: query_accept(store, b0_only, conversation_id=conv, key="other"),
        lambda: store.get(b0_only, accepted.run_id),
        lambda: store.events(b0_only, accepted.run_id),
        lambda: store.cancel(b0_only, accepted.run_id, "cancel", 1, AnalyticsCancelRequest()),
        lambda: store.cancel(reader, accepted.run_id, "cancel", 1, AnalyticsCancelRequest()),
        lambda: store.get(revoked, accepted.run_id),
        lambda: store.rebuild_context(b0_only, intent.run_id, intent.attempt_id, package_digest=DIGEST, unit_id="model:deny"),
        lambda: store.rebuild_context(revoked, intent.run_id, intent.attempt_id, package_digest=DIGEST, unit_id="model:deny"),
    ):
        with pytest.raises(AnalyticsError) as error:
            op()
        assert error.value.status == 403
    assert store.get(query_actor(), accepted.run_id).status == "RUNNING"


def test_pending_step_does_not_resend_or_reset_budget(tmp_path):
    store = make_query_store(tmp_path / "query")
    query_accept(store)
    intent = store.claim_next(lambda owner: query_actor() if owner == "alice" else None)
    first = store.reserve_step(query_actor(), intent.run_id, intent.attempt_id, "tool-1", request=query_request(30))
    assert first.disposition == "EXECUTE"
    replay = store.reserve_step(query_actor(), intent.run_id, intent.attempt_id, "tool-1", request=query_request(30))
    assert replay.disposition == "PENDING" and replay.step_id == first.step_id
    with pytest.raises(AnalyticsError) as error:
        store.reserve_step(query_actor(), intent.run_id, intent.attempt_id, "tool-1", request=query_request(60))
    assert error.value.status == 409
    snapshot = store.get(query_actor(), intent.run_id)
    assert snapshot.diagnostics.tool_steps_used == 1
    context = store.rebuild_context(query_actor(), intent.run_id, intent.attempt_id, package_digest=DIGEST, unit_id="model:1:1")
    assert context["remaining_budget"]["tool_steps"] == 7
    with sqlite_connection(store.path) as con:
        assert con.execute("SELECT count(*) FROM steps").fetchone()[0] == 1


def test_parent_outside_conversation_or_fixture_is_rejected(tmp_path):
    store = make_query_store(tmp_path / "query")
    parent = query_accept(store)
    other = query_conversation(store, key="second")
    with pytest.raises(AnalyticsError) as missing:
        query_accept(store, conversation_id=other.conversation_id, parent=parent.run_id, key="child")
    assert missing.value.status == 404
    with pytest.raises(AnalyticsError) as foreign:
        query_accept(store, query_actor("bob"), parent=parent.run_id, key="child")
    assert foreign.value.status == 404
    conv = store.get(query_actor(), parent.run_id).conversation_id
    with pytest.raises(AnalyticsError) as unsupported:
        query_accept(
            store, conversation_id=conv, parent=parent.run_id, key="child",
            descriptor=golden_descriptor(physical_sha256=_sha("other")),
        )
    assert unsupported.value.status in {409, 422}


def test_b0_request_and_missing_schema_binding_are_rejected(tmp_path):
    store = make_query_store(tmp_path / "query")
    conv = query_conversation(store)
    with pytest.raises(AnalyticsError) as error:
        store.accept(query_actor(), conv.conversation_id, "run", AnalyticsRunRequest(question="查看合成渠道"))
    assert error.value.status == 422
    with pytest.raises(AnalyticsError):
        store.create_conversation(query_actor(), "b0-conv", AnalyticsConversationRequest())
    accepted = query_accept(store, conversation_id=conv.conversation_id)
    with sqlite_connection(store.path) as con:
        con.execute("DELETE FROM idempotency WHERE key='descriptor'")
    with pytest.raises(AnalyticsError) as missing:
        store.get(query_actor(), accepted.run_id)
    assert missing.value.status == 409
    with pytest.raises(ValueError):
        RunStore(store.directory, profile(), family="channel_followup")


def test_complete_requires_exited_worker_and_has_no_success_bypass(tmp_path):
    store = make_query_store(tmp_path / "query")
    query_accept(store)
    intent = store.claim_next(lambda owner: query_actor() if owner == "alice" else None)
    step = store.reserve_step(query_actor(), intent.run_id, intent.attempt_id, "tool-1", request=query_request())
    with pytest.raises(AnalyticsError) as missing:
        store.complete_step(query_actor(), intent.run_id, intent.attempt_id, step.step_id, {"ignored": True})
    assert missing.value.code == "WORKER_NOT_EXITED"
    with sqlite_connection(store.path) as con:
        con.execute(
            "INSERT INTO worker_executions "
            "(execution_id, run_id, attempt_id, step_id, lease_dev, lease_ino, state, active_slot, deadline_ms) "
            "VALUES (?, ?, ?, ?, 1, 1, 'RUNNING', 1, ?)",
            ("exec_1", intent.run_id, intent.attempt_id, step.step_id, step.deadline_ms),
        )
    with pytest.raises(AnalyticsError) as active:
        store.complete_step(query_actor(), intent.run_id, intent.attempt_id, step.step_id, {"ignored": True})
    assert active.value.code == "WORKER_ACTIVE"
    with sqlite_connection(store.path) as con:
        con.execute(
            "UPDATE worker_executions SET state='EXITED', active_slot=NULL, exit_code=NULL, error_code=NULL "
            "WHERE execution_id='exec_1'",
        )
    with pytest.raises(AnalyticsError) as unknown:
        store.complete_step(query_actor(), intent.run_id, intent.attempt_id, step.step_id, {"ignored": True})
    assert unknown.value.code == "WORKER_NOT_EXITED"
    with sqlite_connection(store.path) as con:
        con.execute("UPDATE worker_executions SET exit_code=1 WHERE execution_id='exec_1'")
    with pytest.raises(AnalyticsError) as nonzero:
        store.complete_step(query_actor(), intent.run_id, intent.attempt_id, step.step_id, {"ignored": True})
    assert nonzero.value.code == "WORKER_NOT_EXITED"
    with sqlite_connection(store.path) as con:
        con.execute("UPDATE worker_executions SET exit_code=0, error_code=NULL WHERE execution_id='exec_1'")
    with pytest.raises(AnalyticsError) as invalid:
        store.complete_step(query_actor(), intent.run_id, intent.attempt_id, step.step_id, {"ignored": True})
    assert invalid.value.code == "INVALID_RESULT"
    with sqlite_connection(store.path) as con:
        assert con.execute("SELECT state FROM steps WHERE step_id=?", (step.step_id,)).fetchone()[0] == "STARTED"
        assert con.execute("SELECT result_json FROM steps WHERE step_id=?", (step.step_id,)).fetchone()[0] is None


def test_context_uses_query_version_and_frozen_step_not_b0_fixture(tmp_path):
    store = make_query_store(tmp_path / "query")
    query_accept(store)
    intent = store.claim_next(lambda owner: query_actor() if owner == "alice" else None)
    first = store.rebuild_context(query_actor(), intent.run_id, intent.attempt_id, package_digest=DIGEST, unit_id="model:1:1")
    assert first["schema_version"] == QUERY_CONTEXT_SCHEMA
    assert first["conditions"]["mode"] == "AWAITING_REGISTERED_QUERY"
    assert first["versions"]["contract"] == QUERY_RUN_SCHEMA
    assert "FIXED_FIXTURE_NOT_PARSED_FROM_QUESTION" not in json.dumps(first)
    store.reserve_step(query_actor(), intent.run_id, intent.attempt_id, "tool-1", request=query_request(30))
    second = store.rebuild_context(query_actor(), intent.run_id, intent.attempt_id, package_digest=DIGEST, unit_id="model:1:2")
    assert second["conditions"]["mode"] == "REGISTERED_QUERY"
    assert second["conditions"]["request"]["observation_days"] == 30
    assert second["completed_steps"] == []
    assert second["remaining_budget"]["model_steps"] == 6


def test_metadata_binder_matches_g2_n30_n60_n90_hashes():
    snap = golden_snapshot()
    metadata = {
        "snapshot_id": snap.snapshot_id,
        "data_version": snap.data_version,
        "data_digest": snapshot_digest(snap),
        "as_of": snap.as_of,
        "timezone": snap.timezone,
    }
    for days in (30, 60, 90):
        request = query_request(days)
        left = bind_resolved_filters(request, snap, PERMISSION)
        right = bind_resolved_filters_from_metadata(request, metadata, PERMISSION)
        assert left == right
        assert left.filter_hash == right.filter_hash
        assert left.observation_days == days
        assert left.product_ids == []


def _tamper_json(store, *, table_sql, update_sql, mutate):
    with sqlite_connection(store.path) as con:
        row = con.execute(table_sql).fetchone()
        payload = json.loads(row[0])
        mutate(payload)
        con.execute(update_sql, (canonical_json(payload),))


def test_descriptor_and_method_drift_without_hash_change_is_rejected(tmp_path):
    store = make_query_store(tmp_path / "query")
    conv = query_conversation(store)
    accepted = query_accept(store, conversation_id=conv.conversation_id)
    _tamper_json(
        store,
        table_sql="SELECT response_json FROM idempotency WHERE key='descriptor'",
        update_sql="UPDATE idempotency SET response_json=? WHERE key='descriptor'",
        mutate=lambda payload: payload["fixture"].__setitem__("as_of", "2026-09-01T16:00:00.000000+00:00"),
    )
    with sqlite_connection(store.path) as con:
        con.execute("UPDATE idempotency SET request_hash=? WHERE key='method'", ("c" * 64,))
    with pytest.raises(ValueError):
        RunStore(store.directory, profile(), family="channel_followup")
    with pytest.raises(AnalyticsError) as missing:
        store.get(query_actor(), accepted.run_id)
    assert missing.value.status == 409
    with pytest.raises(AnalyticsError) as replay:
        query_accept(store, conversation_id=conv.conversation_id)
    assert replay.value.status == 409
    with pytest.raises(AnalyticsError) as claimed:
        store.claim_next(lambda owner: query_actor() if owner == "alice" else None)
    assert claimed.value.status == 409


def test_step_payload_drift_without_hash_change_is_rejected(tmp_path):
    store = make_query_store(tmp_path / "query")
    query_accept(store)
    intent = store.claim_next(lambda owner: query_actor() if owner == "alice" else None)
    store.reserve_step(query_actor(), intent.run_id, intent.attempt_id, "tool-1", request=query_request(30))
    _tamper_json(
        store,
        table_sql="SELECT response_json FROM idempotency WHERE operation='runtime.step-binding'",
        update_sql="UPDATE idempotency SET response_json=? WHERE operation='runtime.step-binding'",
        mutate=lambda payload: (
            payload["request"].__setitem__("observation_days", 90),
            payload["resolved_filters"].__setitem__("permission_scope", "foreign-scope"),
        ),
    )
    with pytest.raises(AnalyticsError) as context_error:
        store.rebuild_context(query_actor(), intent.run_id, intent.attempt_id, package_digest=DIGEST, unit_id="model:drift")
    assert context_error.value.status == 409
    with pytest.raises(AnalyticsError) as pending:
        store.reserve_step(query_actor(), intent.run_id, intent.attempt_id, "tool-1", request=query_request(30))
    assert pending.value.status == 409
    with pytest.raises(ValueError):
        RunStore(store.directory, profile(), family="channel_followup")


def test_create_replay_without_descriptor_is_rejected(tmp_path):
    store = make_query_store(tmp_path / "query")
    conv = query_conversation(store)
    accepted = query_accept(store, conversation_id=conv.conversation_id)
    with sqlite_connection(store.path) as con:
        con.execute("DELETE FROM idempotency WHERE key='descriptor'")
        assert con.execute("SELECT count(*) FROM runs").fetchone()[0] == 1
    with pytest.raises(AnalyticsError) as error:
        query_accept(store, conversation_id=conv.conversation_id)
    assert error.value.status == 409
    assert error.value.code == "BINDING_MISSING"
    with sqlite_connection(store.path) as con:
        assert con.execute("SELECT count(*) FROM runs").fetchone()[0] == 1
        assert json.loads(con.execute("SELECT original_202 FROM runs WHERE run_id=?", (accepted.run_id,)).fetchone()[0])["run_id"] == accepted.run_id


@pytest.mark.parametrize("first,second", [("0", "f"), ("f", "0")])
def test_context_latest_conditions_follow_rowid_not_step_uuid(tmp_path, monkeypatch, first, second):
    original = jobs_mod._id
    step_ids = iter([f"step_{first * 32}", f"step_{second * 32}"])

    def fake(prefix):
        if prefix == "step":
            return next(step_ids)
        return original(prefix)

    monkeypatch.setattr(jobs_mod, "_id", fake)
    store = make_query_store(tmp_path / "query")
    query_accept(store)
    intent = store.claim_next(lambda owner: query_actor() if owner == "alice" else None)
    store.reserve_step(query_actor(), intent.run_id, intent.attempt_id, "tool-1", request=query_request(30))
    store.reserve_step(query_actor(), intent.run_id, intent.attempt_id, "tool-2", request=query_request(60))
    context = store.rebuild_context(query_actor(), intent.run_id, intent.attempt_id, package_digest=DIGEST, unit_id="model:order")
    assert context["conditions"]["mode"] == "REGISTERED_QUERY"
    assert context["conditions"]["request"]["observation_days"] == 60
    assert context["conditions"]["step_id"] == f"step_{second * 32}"
    assert [item["request"]["observation_days"] for item in context["registered_queries"]] == [30, 60]
    assert context["remaining_budget"]["tool_steps"] == 6
    assert context["versions"]["method_package_digest"] == DIGEST


def test_unrelated_extra_scope_does_not_change_frozen_hash(tmp_path):
    wide = query_actor(scopes={"channel-followup-fixture", "unrelated-scope"})
    store = make_query_store(tmp_path / "query")
    accepted = query_accept(store, wide)
    assert store.get(query_actor(), accepted.run_id).run_id == accepted.run_id
    assert store.get(wide, accepted.run_id).schema_version == QUERY_RUN_SCHEMA


def test_begin_worker_requires_intact_step_binding(tmp_path):
    store = make_query_store(tmp_path / "query")
    query_accept(store)
    intent = store.claim_next(lambda owner: query_actor() if owner == "alice" else None)
    step = store.reserve_step(query_actor(), intent.run_id, intent.attempt_id, "tool-1", request=query_request())
    with sqlite_connection(store.path) as con:
        con.execute("DELETE FROM idempotency WHERE operation='runtime.step-binding'")
    with pytest.raises(AnalyticsError) as error:
        store.begin_worker(query_actor(), intent.run_id, intent.attempt_id, step.step_id, "exec_1", 1, 1)
    assert error.value.status == 409
    with sqlite_connection(store.path) as con:
        assert con.execute("SELECT count(*) FROM worker_executions").fetchone()[0] == 0


def test_constructed_invalid_query_request_is_rejected_before_insert(tmp_path):
    store = make_query_store(tmp_path / "query")
    conv = query_conversation(store)
    bad = AnalyticsQueryRunRequest.model_construct(schema_version="analytics-run-b0/v1", question="")
    with pytest.raises(AnalyticsError) as error:
        store.accept(
            query_actor(), conv.conversation_id, "run", bad,
            method_package_digest=DIGEST, fixture_descriptor=golden_descriptor(),
        )
    assert error.value.status == 422
    with sqlite_connection(store.path) as con:
        assert con.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
        assert con.execute("SELECT count(*) FROM idempotency WHERE operation='run:create'").fetchone()[0] == 0


def test_cancel_replay_rejects_tampered_run_id_and_replays_original(tmp_path):
    store = make_query_store(tmp_path / "query")
    accepted = query_accept(store)
    cancelled = store.cancel(query_actor(), accepted.run_id, "cancel", 1, AnalyticsCancelRequest())
    original = cancelled.model_dump(mode="json")
    _tamper_json(
        store,
        table_sql="SELECT response_json FROM idempotency WHERE operation='run:cancel'",
        update_sql="UPDATE idempotency SET response_json=? WHERE operation='run:cancel'",
        mutate=lambda payload: payload.__setitem__("run_id", "run_" + "f" * 32),
    )
    with pytest.raises(AnalyticsError) as error:
        store.cancel(query_actor(), accepted.run_id, "cancel", 1, AnalyticsCancelRequest())
    assert error.value.status == 409
    with sqlite_connection(store.path) as con:
        con.execute(
            "UPDATE idempotency SET response_json=? WHERE operation='run:cancel'",
            (canonical_json(original),),
        )
    replayed = store.cancel(query_actor(), accepted.run_id, "cancel", 1, AnalyticsCancelRequest())
    assert replayed.model_dump(mode="json") == original
    assert replayed.run_id == accepted.run_id
    assert store.get(query_actor(), accepted.run_id).diagnostics.tool_steps_used == 0


def test_accept_cached_202_cannot_point_at_another_owned_run(tmp_path):
    store = make_query_store(tmp_path / "query")
    conv = query_conversation(store)
    first = query_accept(store, conversation_id=conv.conversation_id, key="run")
    second = query_accept(store, conversation_id=conv.conversation_id, key="other")
    _tamper_json(
        store,
        table_sql="SELECT response_json FROM idempotency WHERE operation='run:create' AND key='run'",
        update_sql="UPDATE idempotency SET response_json=? WHERE operation='run:create' AND key='run'",
        mutate=lambda payload: payload.__setitem__("run_id", second.run_id),
    )
    with pytest.raises(AnalyticsError) as error:
        query_accept(store, conversation_id=conv.conversation_id, key="run")
    assert error.value.status == 409
    with sqlite_connection(store.path) as con:
        original = json.loads(con.execute("SELECT original_202 FROM runs WHERE run_id=?", (first.run_id,)).fetchone()[0])
        con.execute(
            "UPDATE idempotency SET response_json=? WHERE operation='run:create' AND key='run'",
            (canonical_json(original),),
        )
        assert con.execute("SELECT count(*) FROM runs").fetchone()[0] == 2
    replayed = query_accept(store, conversation_id=conv.conversation_id, key="run")
    assert replayed == first
    assert replayed.run_id != second.run_id


def test_corrupt_step_binding_rejects_cancel_get_and_observe(tmp_path):
    store = make_query_store(tmp_path / "query")
    accepted = query_accept(store)
    intent = store.claim_next(lambda owner: query_actor() if owner == "alice" else None)
    store.reserve_step(query_actor(), intent.run_id, intent.attempt_id, "tool-1", request=query_request(30))
    used = store.get(query_actor(), accepted.run_id).diagnostics.tool_steps_used
    with sqlite_connection(store.path) as con:
        version = con.execute("SELECT version FROM runs WHERE run_id=?", (accepted.run_id,)).fetchone()[0]
    _tamper_json(
        store,
        table_sql="SELECT response_json FROM idempotency WHERE operation='runtime.step-binding'",
        update_sql="UPDATE idempotency SET response_json=? WHERE operation='runtime.step-binding'",
        mutate=lambda payload: payload["request"].__setitem__("observation_days", 90),
    )
    with pytest.raises(AnalyticsError) as get_error:
        store.get(query_actor(), accepted.run_id)
    assert get_error.value.status == 409
    with pytest.raises(AnalyticsError) as observe_error:
        store.observe(query_actor(), observation(intent, "RUNNING", exited=False))
    assert observe_error.value.status == 409
    with pytest.raises(AnalyticsError) as cancel_error:
        store.cancel(query_actor(), accepted.run_id, "cancel", version, AnalyticsCancelRequest())
    assert cancel_error.value.status == 409
    with sqlite_connection(store.path) as con:
        assert con.execute("SELECT tool_steps_used FROM runs WHERE run_id=?", (accepted.run_id,)).fetchone()[0] == used
        assert con.execute("SELECT version FROM runs WHERE run_id=?", (accepted.run_id,)).fetchone()[0] == version
        assert con.execute("SELECT count(*) FROM worker_executions").fetchone()[0] == 0


def test_query_conversation_cache_rejects_unknown_id(tmp_path):
    store = make_query_store(tmp_path / "query")
    created = query_conversation(store)
    original = created.model_dump(mode="json")
    _tamper_json(
        store,
        table_sql="SELECT response_json FROM idempotency WHERE operation='conversation:create'",
        update_sql="UPDATE idempotency SET response_json=? WHERE operation='conversation:create'",
        mutate=lambda payload: payload.__setitem__("conversation_id", "conv_" + "f" * 32),
    )
    with pytest.raises(AnalyticsError) as error:
        query_conversation(store)
    assert error.value.status in {404, 409}
    with sqlite_connection(store.path) as con:
        con.execute(
            "UPDATE idempotency SET response_json=? WHERE operation='conversation:create'",
            (canonical_json(original),),
        )
    replayed = query_conversation(store)
    assert replayed.conversation_id == created.conversation_id
    assert replayed.title == created.title
