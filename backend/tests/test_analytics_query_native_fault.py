"""Query-family native cancel / malformed closed loop. Does not rewrite jobs.py.

HTTP cancel, store idempotency, and worker unknown-schema rejection already
exist; this file covers missing two-session isolation, terminal CAS, lease
release, native-helper unknown version, and UNKNOWN historical supervisors.
"""

from __future__ import annotations

import fcntl
import json
import os
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier

import pytest

from backend.contracts.analytics import AnalyticsCancelRequest
from backend.contracts.analytics_query_run import AnalyticsQueryConversationRequest, AnalyticsQueryRunRequest
from backend.services.analytics.access import AnalyticsError
from backend.services.analytics.execution_lease import create_lease
from backend.services.analytics.jobs import RunStore
from backend.services.analytics.worker import WorkerManager
from backend.tests.analytics_query_native_fault_probe import (
    DEFAULT_SEQUENCE, HISTORICAL_SUPERVISOR_EXITS, QUERY_ALLOWED_MODES, prepare_query_probe_dir,
)
from backend.tests.analytics_query_worker_probe import QueryProbeLauncher
from backend.tests.analytics_run_support import observation, sqlite_connection
from backend.tests.test_analytics_query_jobs import (
    DIGEST, AnalyticsQueryRunSnapshot, golden_descriptor, make_query_store, query_actor,
    query_native,
)
from backend.tests.test_analytics_query_runtime import (
    GATEWAY, SESSIONS, accept_and_claim, followup_body, gateway, runtime, runtime_actor,
    setup_query_app,
)
from backend.tests.test_analytics_query_worker import setup_query_worker
from fastapi.testclient import TestClient


def _busy(error):
    return error.status == 503 and error.code == "STATE_UNAVAILABLE" and error.retryable is True


def _call_or_busy(fn):
    try:
        return fn()
    except AnalyticsError as error:
        if not _busy(error):
            raise
        return error


def _is_busy(result):
    return isinstance(result, AnalyticsError) and _busy(result)


def _terminal_events(store, run_id):
    return [event for event in store.events(query_actor(), run_id) if event.type in {"run.completed", "run.cancelled"}]


def _native_accept(store, session, key, conversation_id, descriptor=None):
    return store.accept(
        query_actor(), conversation_id, key,
        AnalyticsQueryRunRequest(question="查看合成渠道后续购买"),
        method_package_digest=DIGEST, fixture_descriptor=descriptor or golden_descriptor(),
        native_request=query_native(session, key),
    )


def two_native_sessions(tmp_path):
    store = make_query_store(tmp_path / "state")
    conv_a = store.create_conversation(
        query_actor(), "native-a", AnalyticsQueryConversationRequest(),
        runtime_session_id="session-query-synthetic-a",
    )
    conv_b = store.create_conversation(
        query_actor(), "native-b", AnalyticsQueryConversationRequest(),
        runtime_session_id="session-query-synthetic-b",
    )
    run_a = _native_accept(store, "session-query-synthetic-a", "a-1", conv_a.conversation_id)
    run_b = _native_accept(store, "session-query-synthetic-b", "b-1", conv_b.conversation_id)
    return store, conv_a, conv_b, run_a, run_b


def assert_lease_released(store, execution_id):
    path = store.directory / "workers" / execution_id / ".lease"
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        os.close(fd)
    fd, _dev, _ino, _tmp = create_lease(store.directory, "exec_" + "e" * 32)
    os.close(fd)


def test_historical_supervisor_exits_remain_unknown():
    assert HISTORICAL_SUPERVISOR_EXITS["count"] == 3
    assert HISTORICAL_SUPERVISOR_EXITS["status"] == "UNKNOWN"
    assert HISTORICAL_SUPERVISOR_EXITS["closed_by_epipe"] is False
    assert "EPIPE" not in HISTORICAL_SUPERVISOR_EXITS["verdict"]


def test_query_native_fault_sequence_allows_only_three_modes(tmp_path):
    assert QUERY_ALLOWED_MODES == ("sql_hold", "unknown_schema", "passthrough")
    assert DEFAULT_SEQUENCE == QUERY_ALLOWED_MODES
    prepare_query_probe_dir(tmp_path / "ok")
    with pytest.raises(ValueError, match="invalid query native-fault probe sequence"):
        prepare_query_probe_dir(tmp_path / "illegal", sequence=("sql_hold", "illegal_facts", "passthrough"))


def test_cancel_session_a_does_not_cancel_queued_session_b(tmp_path):
    store, _conv_a, conv_b, run_a, run_b = two_native_sessions(tmp_path)
    intent_a = store.claim_next(lambda owner: query_actor() if owner == "alice" else None)
    assert intent_a.run_id == run_a.run_id
    assert store.get(query_actor(), run_b.run_id).status == "QUEUED"
    cancelled = store.cancel(query_actor(), run_a.run_id, "cancel-a",
                             store.get(query_actor(), run_a.run_id).version, AnalyticsCancelRequest())
    assert cancelled.status == "CANCELLING"
    peer = store.get(query_actor(), run_b.run_id)
    assert peer.status == "QUEUED"
    assert peer.run_id != run_a.run_id
    assert store.get_conversation(query_actor(), conv_b.conversation_id).run_ids == [run_b.run_id]
    terminal = store.observe(query_actor(), observation(intent_a, "CANCELLED"))
    assert terminal.status == "CANCELLED" and terminal.result is None
    assert store.get(query_actor(), run_b.run_id).status == "QUEUED"
    intent_b = store.claim_next(lambda owner: query_actor() if owner == "alice" else None)
    assert intent_b is not None and intent_b.run_id == run_b.run_id
    assert store.get(query_actor(), run_a.run_id).status == "CANCELLED"


def test_http_cancel_a_cannot_target_b_and_does_not_mark_b_cancelled(tmp_path):
    app = setup_query_app(tmp_path)
    client = TestClient(app)
    store = app.state.store
    try:
        first = client.post("/internal/native/prompt", json=query_native(SESSIONS[0], "a-1"),
                            headers={"authorization": f"Bearer {GATEWAY}"})
        second = client.post("/internal/native/prompt", json=query_native(SESSIONS[1], "b-1"),
                             headers={"authorization": f"Bearer {GATEWAY}"})
        assert first.status_code == second.status_code == 202
        run_a, run_b = first.json()["run_id"], second.json()["run_id"]
        snap_a = client.get(f"/api/v1/analytics-query/runs/{run_a}", headers=gateway(SESSIONS[0]))
        snap_b = client.get(f"/api/v1/analytics-query/runs/{run_b}", headers=gateway(SESSIONS[1]))
        assert snap_a.status_code == snap_b.status_code == 200
        crossed = client.post(
            f"/api/v1/analytics-query/runs/{run_b}/cancel", json={"reason": "USER_REQUEST"},
            headers={**gateway(SESSIONS[0]), "idempotency-key": "cancel-cross", "if-match": str(snap_b.json()["version"])},
        )
        assert crossed.status_code == 404
        cancelled = client.post(
            f"/api/v1/analytics-query/runs/{run_a}/cancel", json={"reason": "USER_REQUEST"},
            headers={**gateway(SESSIONS[0]), "idempotency-key": "cancel-a", "if-match": str(snap_a.json()["version"])},
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] in {"CANCELLED", "CANCELLING"}
        peer = client.get(f"/api/v1/analytics-query/runs/{run_b}", headers=gateway(SESSIONS[1]))
        assert peer.status_code == 200
        assert peer.json()["status"] not in {"CANCELLED", "CANCELLING"}
        assert store.get(runtime_actor(), run_b).status not in {"CANCELLED", "CANCELLING"}
    finally:
        client.close()


def test_succeeded_then_cancel_keeps_query_result(tmp_path):
    store, accepted, intent, step, fixture = setup_query_worker(tmp_path)
    result = WorkerManager(store, lambda _: query_actor(), fixture).execute(query_actor(), intent, step)
    done = store.observe(query_actor(), observation(intent, "SUCCEEDED", primary=step.step_id))
    assert done.status == "SUCCEEDED"
    assert isinstance(done, AnalyticsQueryRunSnapshot)
    assert done.result == result
    stale = store.get(query_actor(), accepted.run_id).version
    with pytest.raises(AnalyticsError) as conflict:
        store.cancel(query_actor(), accepted.run_id, "cancel-stale", 1, AnalyticsCancelRequest())
    assert conflict.value.status == 409
    replayed = store.cancel(query_actor(), accepted.run_id, "cancel-current", stale, AnalyticsCancelRequest())
    assert replayed.status == "SUCCEEDED"
    assert replayed.result == result
    assert replayed.primary_result_ref == step.step_id
    workers = store.worker_records(active_only=False)
    assert len(workers) == 1
    assert workers[0]["state"] == "EXITED" and workers[0]["active_slot"] is None
    assert_lease_released(store, workers[0]["execution_id"])
    restored = RunStore(store.directory, store.profile, family="channel_followup")
    again = restored.get(query_actor(), accepted.run_id)
    assert again.status == "SUCCEEDED" and again.result == result
    assert len(_terminal_events(restored, accepted.run_id)) == 1


def test_cancel_vs_observe_race_leaves_one_terminal(tmp_path):
    store, accepted, intent, step, fixture = setup_query_worker(tmp_path)
    WorkerManager(store, lambda _: query_actor(), fixture).execute(query_actor(), intent, step)
    version = store.get(query_actor(), accepted.run_id).version
    right = RunStore(store.directory, store.profile, family="channel_followup")
    barrier = Barrier(2)
    evidence = observation(intent, "SUCCEEDED", primary=step.step_id)
    request = AnalyticsCancelRequest()

    def cancel():
        barrier.wait(timeout=5)
        try:
            return right.cancel(query_actor(), accepted.run_id, "cancel-race", version, request)
        except AnalyticsError as error:
            if _busy(error) or error.status == 409:
                return error
            raise

    def finish():
        barrier.wait(timeout=5)
        return _call_or_busy(lambda: store.observe(query_actor(), evidence))

    with ThreadPoolExecutor(max_workers=2) as pool:
        cancellation, completion = pool.submit(cancel), pool.submit(finish)
        cancel_result, observe_result = cancellation.result(timeout=8), completion.result(timeout=8)
    if _is_busy(cancel_result):
        try:
            right.cancel(query_actor(), accepted.run_id, "cancel-race", version, request)
        except AnalyticsError as error:
            assert error.status == 409
    if _is_busy(observe_result):
        store.observe(query_actor(), evidence)
    final = store.get(query_actor(), accepted.run_id)
    assert final.status in {"SUCCEEDED", "CANCELLED"}
    assert not final.diagnostics.execution_active
    assert (final.result is None) == (final.status == "CANCELLED")
    assert len(_terminal_events(right, accepted.run_id)) == 1
    restored = RunStore(store.directory, store.profile, family="channel_followup")
    again = restored.get(query_actor(), accepted.run_id)
    assert again.status == final.status
    if final.status == "SUCCEEDED":
        assert again.result == final.result
    else:
        assert again.result is None


def test_cancel_sql_hold_on_a_releases_worker_and_leaves_b_queued(tmp_path):
    store, _accepted, intent, step, fixture = setup_query_worker(tmp_path)
    conv_b = store.create_conversation(
        query_actor(), "peer-b", AnalyticsQueryConversationRequest(),
        runtime_session_id="session-query-synthetic-b",
    )
    run_b = _native_accept(
        store, "session-query-synthetic-b", "b-1", conv_b.conversation_id,
        descriptor=fixture.binding_descriptor(),
    )
    initial = store.get(query_actor(), intent.run_id)
    with ThreadPoolExecutor(max_workers=1) as pool, QueryProbeLauncher("sql_hold", ignore_term=True) as launch:
        future = pool.submit(
            WorkerManager(store, lambda _: query_actor(), fixture, launch=launch).execute,
            query_actor(), intent, step,
        )
        assert launch.receive()["event"] == "SQL_ACTIVE"
        store.cancel(query_actor(), intent.run_id, "cancel-a",
                     store.get(query_actor(), intent.run_id).version, AnalyticsCancelRequest())
        assert store.get(query_actor(), run_b.run_id).status == "QUEUED"
        with pytest.raises(AnalyticsError) as failed:
            future.result(timeout=8)
        assert failed.value.code == "TOOL_FAILED"
    record = store.worker_records(active_only=False)[0]
    assert record["state"] == "EXITED" and record["active_slot"] is None
    assert store.worker_records() == []
    assert_lease_released(store, record["execution_id"])
    peer = store.get(query_actor(), run_b.run_id)
    assert peer.status == "QUEUED"
    stopped = store.get(query_actor(), intent.run_id)
    assert stopped.status == "CANCELLING"
    assert stopped.result is None
    assert stopped.diagnostics.tool_steps_used == initial.diagnostics.tool_steps_used
    terminal = store.observe(query_actor(), observation(intent, "CANCELLED"))
    assert terminal.status == "CANCELLED" and terminal.result is None
    assert store.get(query_actor(), run_b.run_id).status == "QUEUED"
    claimed = store.claim_next(lambda owner: query_actor() if owner == "alice" else None)
    assert claimed is not None and claimed.run_id == run_b.run_id


def test_native_helper_unknown_schema_is_refused_without_facts_or_new_peer_run(tmp_path):
    app = setup_query_app(tmp_path)
    client = TestClient(app)
    store = app.state.store
    try:
        accepted, intent = accept_and_claim(client, app, SESSIONS[0], "a-unknown")
        peer = client.post("/internal/native/prompt", json=query_native(SESSIONS[1], "b-hold"),
                           headers={"authorization": f"Bearer {GATEWAY}"})
        assert peer.status_code == 202
        assert intent.request_id == "a-unknown"
        before_ids = store.get_conversation(runtime_actor(), store.get(runtime_actor(), peer.json()["run_id"]).conversation_id).run_ids
        with QueryProbeLauncher("unknown_schema") as launch:
            app.state.workers.launch = launch
            refused = client.post("/internal/native/channel-followup",
                                  json=followup_body(SESSIONS[0], "a-unknown", "call-unknown", 30),
                                  headers=runtime())
        assert refused.status_code == 409
        assert refused.json()["error"]["code"] == "TOOL_FAILED"
        body = json.dumps(refused.json())
        assert "channel_repeat_count" not in body
        assert "1100" not in body
        snap = store.get(runtime_actor(), accepted["run_id"])
        assert snap.status != "SUCCEEDED" and snap.result is None
        worker = store.worker_records(active_only=False)[0]
        assert worker["state"] == "EXITED" and worker["active_slot"] is None
        assert_lease_released(store, worker["execution_id"])
        peer_snap = store.get(runtime_actor(), peer.json()["run_id"])
        assert peer_snap.status not in {"CANCELLED", "CANCELLING", "SUCCEEDED"}
        after_ids = store.get_conversation(runtime_actor(), peer_snap.conversation_id).run_ids
        assert after_ids == before_ids
        unknown = deepcopy(followup_body(SESSIONS[0], "a-unknown", "call-v0", 30))
        unknown["request"] = {**unknown["request"], "query_version": "channel-followup-query/v0"}
        assert client.post("/internal/native/channel-followup", json=unknown, headers=runtime()).status_code == 422
    finally:
        client.close()


def test_failed_query_refresh_reread_does_not_add_runs(tmp_path):
    store, accepted, intent, step, fixture = setup_query_worker(tmp_path)
    with QueryProbeLauncher("unknown_schema") as launch:
        with pytest.raises(AnalyticsError) as failed:
            WorkerManager(store, lambda _: query_actor(), fixture, launch=launch).execute(
                query_actor(), intent, step,
            )
        assert failed.value.code == "TOOL_FAILED"
    first = store.get_conversation(query_actor(), store.get(query_actor(), accepted.run_id).conversation_id)
    with sqlite_connection(store.path) as con:
        runs = con.execute("SELECT run_id, status, result_json FROM runs ORDER BY rowid").fetchall()
        steps = con.execute("SELECT count(*) FROM steps").fetchone()[0]
    restored = RunStore(store.directory, store.profile, family="channel_followup")
    again = restored.get_conversation(query_actor(), first.conversation_id)
    assert again.run_ids == first.run_ids == [accepted.run_id]
    snap = restored.get(query_actor(), accepted.run_id)
    assert snap.result is None
    with sqlite_connection(restored.path) as con:
        assert con.execute("SELECT count(*) FROM runs").fetchone()[0] == 1
        assert con.execute("SELECT count(*) FROM steps").fetchone()[0] == steps
        assert con.execute("SELECT result_json FROM steps WHERE step_id=?", (step.step_id,)).fetchone()[0] is None
    assert [row[0] for row in runs] == again.run_ids
