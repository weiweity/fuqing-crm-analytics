"""Ledger resource enforcement, not DuckDB/RSS/spill capacity certification."""

import os

import pytest
from pydantic import ValidationError

from backend.contracts.analytics import AnalyticsCancelRequest
from backend.services.analytics.access import AnalyticsError
from backend.services.analytics.jobs import RunStore
from backend.services.analytics.resource_profile import B0ResourceProfile, MIB
from backend.tests.analytics_run_support import (
    Clock, accept, actor, conversation, fixture_result, make_store, observation, profile,
    receive, sqlite_connection, start_probe, stop_owned, successful_step,
)


def test_required_profile_never_falls_back_to_old_environment(monkeypatch):
    monkeypatch.setenv("DUCKDB_MEMORY_LIMIT", "32GB")
    monkeypatch.setenv("DUCKDB_PATH", "/not-an-authorized-database.duckdb")
    with pytest.raises(ValidationError):
        B0ResourceProfile()
    value = profile()
    assert value.duckdb_memory_mib == 512 and value.active_workers == 1
    assert value.max_queued == 8 and value.max_tool_steps == 8


@pytest.mark.parametrize("invalid", [
    {"active_workers": 2}, {"active_workers": True}, {"duckdb_threads": 2.0},
    {"max_actor_inflight": 4}, {"max_tool_steps": "8"}, {"max_dispatch_attempts": 4},
    {"max_queued": 9}, {"query_timeout_ms": 30001}, {"run_timeout_ms": 120001},
    {"state_high_water_bytes": 1}, {"unknown_setting": 1},
    {"max_retained_runs": 1, "max_retained_runs_per_actor": 2},
    {"query_timeout_ms": 200, "run_timeout_ms": 100},
])
def test_resource_profile_rejects_invalid_or_unbounded_settings(invalid):
    with pytest.raises(ValidationError):
        profile(**invalid)


def test_state_directory_must_be_explicit_private_and_owned(tmp_path):
    with pytest.raises(ValueError):
        RunStore(tmp_path / "not-created", profile())
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o755)
    shared.chmod(0o755)
    with pytest.raises(ValueError):
        RunStore(shared, profile())
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    link = tmp_path / "linked-state"
    link.symlink_to(private, target_is_directory=True)
    with pytest.raises(ValueError):
        RunStore(link, profile())
    assert not (private / "runs.sqlite3").exists()


@pytest.mark.parametrize("linked_file", ["runs.sqlite3", ".initialize.lock"])
@pytest.mark.parametrize("kind", ["symbolic", "hard"])
def test_linked_state_or_lock_cannot_modify_another_file(tmp_path, linked_file, kind):
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    unrelated = tmp_path / "unrelated.sqlite3"
    with sqlite_connection(unrelated) as con:
        con.execute("CREATE TABLE preserve_me (value INTEGER)")
    before = unrelated.read_bytes()
    if kind == "symbolic":
        (state / linked_file).symlink_to(unrelated)
    else:
        os.link(unrelated, state / linked_file)
    with pytest.raises((ValueError, OSError)):
        RunStore(state, profile())
    assert unrelated.read_bytes() == before


def test_foreign_sqlite_and_profile_changes_are_not_implicitly_adopted(tmp_path):
    state = tmp_path / "foreign"
    state.mkdir(mode=0o700)
    with sqlite_connection(state / "runs.sqlite3") as con:
        con.execute("CREATE TABLE preserve_me (value INTEGER)")
    before = (state / "runs.sqlite3").read_bytes()
    with pytest.raises(ValueError, match="foreign"):
        RunStore(state, profile())
    assert (state / "runs.sqlite3").read_bytes() == before
    store = make_store(tmp_path / "actual")
    with pytest.raises(ValueError, match="profile differs"):
        RunStore(store.directory, profile(max_tool_steps=2))


def test_actor_inflight_includes_unknown_and_cancelling(tmp_path):
    store = make_store(tmp_path / "state")
    first = accept(store)
    intent = store.claim_next(actor)
    second = accept(store, key="second")
    third = accept(store, key="third")
    store.recover()
    with pytest.raises(AnalyticsError, match="RUN_QUOTA"):
        accept(store, key="fourth")
    current = store.get(actor(), first.run_id)
    store.cancel(actor(), first.run_id, "cancel", current.version, AnalyticsCancelRequest())
    with pytest.raises(AnalyticsError, match="RUN_QUOTA"):
        accept(store, key="fourth")
    assert accept(store, key="second") == second  # replay is independent of a full quota
    store.observe(actor(), observation(intent, "CANCELLED"))
    assert accept(store, key="fourth").run_id not in {first.run_id, second.run_id, third.run_id}


def test_global_queue_cap_is_shared_across_callers_and_recovers_after_exit(tmp_path):
    store = make_store(tmp_path / "state")
    accepted = [accept(store, actor(f"actor-{index}")) for index in range(8)]
    with pytest.raises(AnalyticsError, match="RUN_QUOTA"):
        accept(store, actor("actor-8"))
    intent = store.claim_next(actor)
    assert intent.run_id == accepted[0].run_id
    accept(store, actor("actor-8"))  # one active + eight queued is the explicit policy
    with pytest.raises(AnalyticsError, match="RUN_QUOTA"):
        accept(store, actor("actor-9"))
    assert store.claim_next(actor) is None
    store.observe(actor("actor-0"), observation(intent, "FAILED", error_code="MODEL_FAILED"))
    assert store.claim_next(actor).run_id == accepted[1].run_id


def test_retained_caps_refuse_new_work_without_erasing_idempotency(tmp_path):
    limits = profile(max_retained_runs=1, max_retained_runs_per_actor=1,
                     max_retained_conversations=1, max_retained_conversations_per_actor=1)
    store = make_store(tmp_path / "state", resource_profile=limits)
    first = accept(store)
    store.cancel(actor(), first.run_id, "cancel", 1, AnalyticsCancelRequest())
    with pytest.raises(AnalyticsError, match="RETENTION_LIMIT"):
        accept(store, key="second")
    with pytest.raises(AnalyticsError, match="RETENTION_LIMIT"):
        conversation(store, key="another")
    assert accept(store) == first
    assert store.get(actor(), first.run_id).status == "CANCELLED"


def test_state_high_water_admission_preserves_existing_records(tmp_path, monkeypatch):
    store = make_store(tmp_path / "state")
    first = accept(store)
    conv = store.get(actor(), first.run_id).conversation_id
    monkeypatch.setattr(store, "storage_bytes", lambda: store.profile.state_high_water_bytes)
    with pytest.raises(AnalyticsError, match="STATE_HIGH_WATER"):
        accept(store, key="second", conversation_id=conv)
    assert accept(store, conversation_id=conv) == first
    assert store.cancel(actor(), first.run_id, "cancel", 1, AnalyticsCancelRequest()).status == "CANCELLED"
    assert store.get_conversation(actor(), conv).run_ids == [first.run_id]


def test_real_admission_reservation_is_bounded_without_filling_disk(tmp_path):
    store = make_store(tmp_path / "state", resource_profile=profile(state_high_water_bytes=16 * MIB))
    for index in range(3):
        accept(store, actor(f"actor-{index}"))
    with pytest.raises(AnalyticsError, match="STATE_HIGH_WATER"):
        accept(store, actor("actor-3"))
    assert store.storage_bytes() < MIB  # testing reservation, not writing a giant fixture


def test_duplicate_steps_keep_deadlines_and_never_reset_eight_step_budget(tmp_path):
    clock = Clock()
    store = make_store(tmp_path / "state", clock=clock)
    accept(store)
    intent = store.claim_next(actor)
    first = store.reserve_step(actor(), intent.run_id, intent.attempt_id, "call-0")
    clock.now += 1000
    retry = store.reserve_step(actor(), intent.run_id, intent.attempt_id, "call-0")
    assert retry.disposition == "PENDING" and retry.deadline_ms == first.deadline_ms
    store.complete_step(actor(), intent.run_id, intent.attempt_id, first.step_id, fixture_result())
    assert store.reserve_step(actor(), intent.run_id, intent.attempt_id, "call-0").disposition == "REUSE_RESULT"
    for index in range(1, 8):
        successful_step(store, intent, call_id=f"call-{index}")
    with pytest.raises(AnalyticsError, match="TOOL_STEP_LIMIT"):
        store.reserve_step(actor(), intent.run_id, intent.attempt_id, "call-8")
    assert store.get(actor(), intent.run_id).diagnostics.tool_steps_used == 8
    fresh = RunStore(store.directory, profile(), clock=clock)
    recovered = fresh.recover()[0]
    current = fresh.get(actor(), intent.run_id)
    assert recovered == intent and current.diagnostics.tool_steps_used == 8
    assert current.diagnostics.dispatch_attempts == 1 and current.diagnostics.profile_hash == profile().digest
    assert fresh.claim_next(actor) is None


def test_step_budget_and_absolute_deadline_survive_real_process_kill(tmp_path):
    store = make_store(tmp_path / "state")
    accept(store)
    intent = store.claim_next(actor)
    child = start_probe({"action": "reserve-step", "state_dir": str(store.directory),
                         "run_id": intent.run_id, "attempt_id": intent.attempt_id})
    try:
        reserved = receive(child)
        child.kill()
        assert child.wait(timeout=5) < 0
        fresh = RunStore(store.directory, profile())
        recovered = fresh.recover()[0]
        current = fresh.get(actor(), intent.run_id)
        assert recovered == intent
        assert current.diagnostics.tool_steps_used == 1 and current.diagnostics.dispatch_attempts == 1
        with sqlite_connection(store.path) as con:
            assert con.execute("SELECT step_id, deadline_ms FROM steps").fetchone() == (
                reserved["step_id"], reserved["deadline_ms"])
    finally:
        stop_owned(child)


def test_query_deadline_rejects_late_results(tmp_path):
    clock = Clock()
    store = make_store(tmp_path / "state", clock=clock)
    accept(store)
    intent = store.claim_next(actor)
    step = store.reserve_step(actor(), intent.run_id, intent.attempt_id, "late")
    clock.now = step.deadline_ms
    with pytest.raises(AnalyticsError, match="QUERY_TIMEOUT"):
        store.complete_step(actor(), intent.run_id, intent.attempt_id, step.step_id, fixture_result())
    assert store.get(actor(), intent.run_id).diagnostics.execution_active


def test_run_deadlines_fail_queued_but_hold_active_slot_until_exit(tmp_path):
    clock = Clock()
    store = make_store(tmp_path / "state", clock=clock)
    first = accept(store)
    intent = store.claim_next(actor)
    second = accept(store, key="second")
    clock.now = intent.deadline_ms
    assert store.enforce_deadlines() == [first.run_id]
    assert store.get(actor(), first.run_id).status == "CANCELLING"
    assert store.get(actor(), second.run_id).status == "FAILED"
    assert store.get(actor(), second.run_id).diagnostics.dispatch_attempts == 0
    assert store.claim_next(actor) is None
    terminal = store.observe(actor(), observation(intent, "FAILED", error_code="MODEL_FAILED"))
    assert terminal.diagnostics.error_code == "TIMEOUT" and not terminal.diagnostics.execution_active


def test_event_capacity_is_transactional_and_reserves_final_state_space(tmp_path):
    store = make_store(tmp_path / "state")
    accepted = accept(store)
    intent = store.claim_next(actor)
    before = store.get(actor(), accepted.run_id)
    with sqlite_connection(store.path) as con:
        con.execute("UPDATE runs SET event_bytes=? WHERE run_id=?", (store.profile.max_run_event_bytes - 32768, accepted.run_id))
    with pytest.raises(AnalyticsError, match="EVENT_CAPACITY"):
        store.reserve_step(actor(), intent.run_id, intent.attempt_id, "cannot-fit")
    assert store.get(actor(), accepted.run_id) == before
    terminal = store.observe(actor(), observation(intent, "FAILED", error_code="RESOURCE_EXCEEDED"))
    assert terminal.status == "FAILED" and not terminal.diagnostics.execution_active


def test_truthy_exit_is_not_process_exit_evidence(tmp_path):
    store = make_store(tmp_path / "state")
    accept(store)
    intent = store.claim_next(actor)
    for incorrect in (1, "true", None):
        with pytest.raises(ValueError, match="unsupported runtime evidence"):
            store.observe(actor(), observation(intent, "FAILED", exited=incorrect))
    assert store.get(actor(), intent.run_id).diagnostics.execution_active
