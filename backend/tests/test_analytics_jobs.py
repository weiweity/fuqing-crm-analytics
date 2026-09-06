"""B0 durable-state integration tests. No CRM fixtures or real data required."""

import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from threading import Barrier
from types import SimpleNamespace

import pytest

from backend.contracts.analytics import AnalyticsCancelRequest, AnalyticsRunRequest
from backend.services.analytics.access import AnalyticsError
from backend.services.analytics.jobs import RunStore
from backend.tests.analytics_run_support import (
    accept, actor, conversation, fixture_result, make_store, observation, profile,
    receive, send, sqlite_connection, start_probe, stop_owned, successful_step,
)


def test_receiver_frames_adjacent_events_without_waiting_on_empty_fd():
    read_fd, write_fd = os.pipe()
    with os.fdopen(read_fd, "r") as output, os.fdopen(write_fd, "w") as producer:
        producer.write('{"first":true}\n{"second":true}\n')
        producer.flush()
        proc = SimpleNamespace(stdout=output)
        assert receive(proc, timeout=0.1) == {"first": True}
        assert receive(proc, timeout=0.1) == {"second": True}


def test_atomic_idempotency_across_independent_connections(tmp_path):
    first = make_store(tmp_path / "state")
    second = RunStore(first.directory, profile())
    conv = conversation(first)
    barrier = Barrier(2)

    def submit(store):
        barrier.wait(timeout=5)
        return accept(store, conversation_id=conv.conversation_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        left, right = pool.submit(submit, first), pool.submit(submit, second)
        assert left.result(timeout=5) == right.result(timeout=5)
    with sqlite_connection(first.path) as con:
        assert con.execute("SELECT count(*) FROM runs").fetchone()[0] == 1
        assert con.execute("SELECT count(*) FROM dispatch_intents").fetchone()[0] == 1
        assert con.execute("SELECT count(*) FROM idempotency WHERE operation='run:create'").fetchone()[0] == 1
        assert con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert first.get(actor(), left.result().run_id).status == "QUEUED"


def test_semantic_hash_defaults_and_original_response_after_completion(tmp_path):
    store = make_store(tmp_path / "state")
    conv = conversation(store)
    accepted = store.accept(actor(), conv.conversation_id, "key", AnalyticsRunRequest(question="  查看合成渠道  "))
    intent = store.claim_next(lambda _owner: actor())
    step = successful_step(store, intent)
    result = store.observe(actor(), observation(intent, "SUCCEEDED", primary=step.step_id))
    replay = store.accept(actor(), conv.conversation_id, "key", AnalyticsRunRequest(
        question="查看合成渠道", parent_run_id=None, condition_patch=None))
    assert replay == accepted and replay.version == 1
    assert result.status == "SUCCEEDED" and result.version > replay.version
    assert result.result == fixture_result()
    assert result.primary_result_ref == step.step_id
    with pytest.raises(AnalyticsError) as error:
        store.accept(actor(), conv.conversation_id, "key", AnalyticsRunRequest(question="换一个问题"))
    assert error.value.status == 409


@pytest.mark.parametrize("point,expected_count", [("accept:before_commit", 0), ("accept:after_commit", 1)])
def test_real_process_crash_at_acceptance_barriers(tmp_path, point, expected_count):
    store = make_store(tmp_path / "state")
    conv = conversation(store)
    child = start_probe({"action": "accept", "state_dir": str(store.directory), "conversation_id": conv.conversation_id,
                         "key": "crash-key", "fault": point})
    try:
        assert receive(child) == {"ready": point}
        child.kill()  # Only the child handle this test created.
        assert child.wait(timeout=5) < 0
        assert child.stdout.read() == ""  # Receiver saw no dispatch after the barrier.
        with sqlite_connection(store.path) as con:
            assert con.execute("SELECT count(*) FROM runs").fetchone()[0] == expected_count
            assert con.execute("SELECT count(*) FROM dispatch_intents").fetchone()[0] == expected_count
            assert con.execute("SELECT count(*) FROM idempotency WHERE operation='run:create'").fetchone()[0] == expected_count
            committed = con.execute("SELECT original_202 FROM runs").fetchone()
        fresh = RunStore(store.directory, profile())
        replay = accept(fresh, key="crash-key", conversation_id=conv.conversation_id)
        if committed:
            assert replay.model_dump(mode="json") == json.loads(committed[0])
    finally:
        stop_owned(child)


@pytest.mark.parametrize("point,committed", [("claim:before_commit", False), ("claim:after_commit", True)])
def test_real_process_crash_at_claim_preserves_original_intent_without_resend(tmp_path, point, committed):
    store = make_store(tmp_path / "state")
    accepted = accept(store)
    original_snapshot = store.get(actor(), accepted.run_id)
    with sqlite_connection(store.path) as con:
        original = con.execute("SELECT session_id, request_id, payload_hash FROM dispatch_intents").fetchone()
    child = start_probe({"action": "claim", "state_dir": str(store.directory), "fault": point})
    try:
        assert receive(child) == {"ready": point}
        child.kill()
        assert child.wait(timeout=5) < 0
        assert child.stdout.read() == ""  # Independent receiver got no request.
        fresh = RunStore(store.directory, profile())
        with sqlite_connection(store.path) as con:
            assert con.execute("SELECT session_id, request_id, payload_hash FROM dispatch_intents").fetchone() == original
            assert con.execute("SELECT attempts FROM dispatch_intents").fetchone()[0] == int(committed)
            assert con.execute("SELECT count(*) FROM runs").fetchone()[0] == 1
        recovered = fresh.recover()
        current = fresh.get(actor(), accepted.run_id)
        assert current.diagnostics.attempt_id == original_snapshot.diagnostics.attempt_id
        assert current.deadline == original_snapshot.deadline
        if committed:
            assert current.status == "UNKNOWN" and len(recovered) == 1
            assert fresh.claim_next(actor) is None  # No inference from the dead API PID.
            assert (recovered[0].session_id, recovered[0].request_id, recovered[0].payload_hash) == original
        else:
            assert current.status == "QUEUED" and recovered == []
            intent = fresh.claim_next(actor)
            assert (intent.session_id, intent.request_id, intent.payload_hash) == original
    finally:
        stop_owned(child)


@pytest.mark.parametrize("point,committed", [("observe:before_commit", False), ("observe:after_commit", True)])
def test_terminal_process_crash_and_lost_notification_recover_from_durable_snapshot(tmp_path, point, committed):
    store = make_store(tmp_path / "state")
    accept(store)
    intent = store.claim_next(actor)
    step = successful_step(store, intent)
    observed = observation(intent, "SUCCEEDED", primary=step.step_id)
    child = start_probe({"action": "observe", "state_dir": str(store.directory),
                         "observation": asdict(observed), "fault": point})
    try:
        assert receive(child) == {"ready": point}
        child.kill()
        assert child.wait(timeout=5) < 0
        assert child.stdout.read() == ""  # No terminal response/notification delivered.
        fresh = RunStore(store.directory, profile())
        current = fresh.get(actor(), intent.run_id)
        events = [event for event in fresh.events(actor(), intent.run_id) if event.type == "run.completed"]
        assert current.status == ("SUCCEEDED" if committed else "RUNNING")
        assert len(events) == int(committed)
        assert (current.result is not None) == committed
        if committed:
            assert fresh.recover() == []
            assert fresh.observe(actor(), observed) == current
        else:
            assert fresh.recover()[0] == intent
            assert fresh.get(actor(), intent.run_id).status == "UNKNOWN"
            # The independent receiver re-supplies the same terminal proof,
            # never a new dispatch or tool execution.
            assert fresh.observe(actor(), observed).status == "SUCCEEDED"
        final_events = [event for event in fresh.events(actor(), intent.run_id) if event.type == "run.completed"]
        assert len(final_events) == 1
        assert fresh.get(actor(), intent.run_id).diagnostics.dispatch_attempts == 1
    finally:
        stop_owned(child)


@pytest.mark.parametrize("receipt", [True, False, None])
def test_independent_protocol_receiver_and_lost_dispatch_receipt(tmp_path, receipt):
    store = make_store(tmp_path / "state")
    conv = conversation(store)
    child = start_probe({"action": "accept", "state_dir": str(store.directory), "conversation_id": conv.conversation_id,
                         "key": "wire-key"})
    received = []
    try:
        accepted = receive(child)["accepted"]
        received.append(receive(child)["dispatch"])
        if receipt is None:
            child.kill()
            child.wait(timeout=5)
        else:
            send(child, {"accepted": receipt})
            assert receive(child)["observed"] == ("RUNNING" if receipt else "FAILED")
            assert child.wait(timeout=5) == 0
        fresh = RunStore(store.directory, profile())
        recovered = fresh.recover()
        current = fresh.get(actor(), accepted["run_id"])
        if receipt is False:
            assert recovered == [] and current.status == "FAILED"
            assert not current.diagnostics.execution_active
        else:
            assert len(recovered) == 1 and current.status == "UNKNOWN"
            assert recovered[0].request_id == received[0]["request_id"]
            assert recovered[0].attempt_id == received[0]["attempt_id"]
            assert recovered[0].payload_hash == received[0]["payload_hash"]
            assert current.diagnostics.execution_active
        assert fresh.accept(actor(), conv.conversation_id, "wire-key", AnalyticsRunRequest(question="查看合成渠道")).model_dump(mode="json") == accepted
        assert len(received) == 1
    finally:
        stop_owned(child)


def test_queued_cancel_never_dispatches_and_replay_returns_original_cancel(tmp_path):
    store = make_store(tmp_path / "state")
    accepted = accept(store)
    cancelled = store.cancel(actor(), accepted.run_id, "cancel", 1, AnalyticsCancelRequest())
    assert cancelled.status == "CANCELLED" and not cancelled.diagnostics.execution_active
    assert store.claim_next(lambda _owner: actor()) is None
    assert store.cancel(actor(), accepted.run_id, "cancel", 1, AnalyticsCancelRequest()) == cancelled
    assert cancelled.diagnostics.dispatch_attempts == 0


@pytest.mark.parametrize("stage", ["model_wait", "tool_gap", "query", "finalizing"])
def test_cancel_holds_slot_until_owned_child_really_exits(tmp_path, stage):
    store = make_store(tmp_path / "state")
    accepted = accept(store)
    intent = store.claim_next(lambda _owner: actor())
    own_child = start_probe({"action": "worker", "attempt_id": intent.attempt_id})
    other_child = start_probe({"action": "worker", "attempt_id": "unrelated-test-child"})
    try:
        assert receive(own_child)["attempt_id"] == intent.attempt_id
        assert receive(other_child)["attempt_id"] == "unrelated-test-child"
        step = None
        if stage == "query":
            step = store.reserve_step(actor(), intent.run_id, intent.attempt_id, "query")
        elif stage in {"tool_gap", "finalizing"}:
            step = successful_step(store, intent)
        current = store.get(actor(), accepted.run_id)
        store.cancel(actor(), accepted.run_id, "cancel", current.version, AnalyticsCancelRequest())
        waiting = store.get(actor(), accepted.run_id)
        assert waiting.status == "CANCELLING" and waiting.diagnostics.execution_active
        accept(store, key="second", conversation_id=waiting.conversation_id)
        assert store.claim_next(lambda _owner: actor()) is None
        assert own_child.poll() is None
        with pytest.raises(ValueError, match="confirmed execution exit"):
            store.observe(actor(), observation(intent, "CANCELLED", exited=False))
        with pytest.raises(AnalyticsError):
            store.reserve_step(actor(), intent.run_id, intent.attempt_id, "after-cancel")
        own_child.terminate()
        assert own_child.wait(timeout=5) < 0
        assert other_child.poll() is None
        terminal = store.observe(actor(), observation(intent, "SUCCEEDED" if stage == "finalizing" else "CANCELLED",
                                                      primary=step.step_id if step else None))
        assert terminal.status == "CANCELLED" and not terminal.diagnostics.execution_active
        assert terminal.result is None
        next_intent = store.claim_next(lambda _owner: actor())
        assert next_intent is not None and next_intent.run_id != intent.run_id
    finally:
        stop_owned(own_child)
        stop_owned(other_child)


def test_cancel_intent_survives_actual_process_crash(tmp_path):
    store = make_store(tmp_path / "state")
    accepted = accept(store)
    intent = store.claim_next(lambda _owner: actor())
    current = store.get(actor(), accepted.run_id)
    child = start_probe({"action": "cancel", "state_dir": str(store.directory), "run_id": accepted.run_id,
                         "version": current.version, "fault": "cancel:after_commit"})
    try:
        assert receive(child) == {"ready": "cancel:after_commit"}
        child.kill()
        child.wait(timeout=5)
        fresh = RunStore(store.directory, profile())
        recovered = fresh.recover()
        assert recovered[0].attempt_id == intent.attempt_id
        assert fresh.get(actor(), intent.run_id).status == "CANCELLING"
        assert fresh.claim_next(lambda _owner: actor()) is None
        assert fresh.observe(actor(), observation(intent, "CANCELLED")).status == "CANCELLED"
    finally:
        stop_owned(child)


@pytest.mark.parametrize("first", ["cancel", "success"])
def test_two_connection_terminal_compare_and_set_both_orderings(tmp_path, first):
    left = make_store(tmp_path / "state")
    right = RunStore(left.directory, profile())
    accepted = accept(left)
    intent = left.claim_next(lambda _owner: actor())
    step = successful_step(left, intent)
    version = left.get(actor(), accepted.run_id).version
    if first == "cancel":
        right.cancel(actor(), accepted.run_id, "cancel", version, AnalyticsCancelRequest())
        result = left.observe(actor(), observation(intent, "SUCCEEDED", primary=step.step_id))
        assert result.status == "CANCELLED" and result.result is None
    else:
        result = left.observe(actor(), observation(intent, "SUCCEEDED", primary=step.step_id))
        with pytest.raises(AnalyticsError) as error:
            right.cancel(actor(), accepted.run_id, "cancel-stale", version, AnalyticsCancelRequest())
        assert error.value.status == 409
        unchanged = right.cancel(actor(), accepted.run_id, "cancel-current", result.version, AnalyticsCancelRequest())
        assert unchanged == result and unchanged.status == "SUCCEEDED"
    terminal = [event for event in right.events(actor(), accepted.run_id) if event.type in {"run.completed", "run.cancelled"}]
    assert len(terminal) == 1


def test_claim_race_only_one_global_execution_across_owners(tmp_path):
    left = make_store(tmp_path / "state")
    right = RunStore(left.directory, profile())
    first = accept(left, actor("alice"), key="a")
    accept(left, actor("bob"), key="b")
    barrier = Barrier(2)

    def claim(store):
        barrier.wait(timeout=5)
        return store.claim_next(actor)

    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(claim, left), pool.submit(claim, right)
        values = [a.result(timeout=5), b.result(timeout=5)]
    dispatched = [value for value in values if value is not None]
    assert len(dispatched) == 1 and dispatched[0].run_id == first.run_id


def test_actual_terminal_race_has_one_winner_and_one_terminal_event(tmp_path):
    left = make_store(tmp_path / "state")
    right = RunStore(left.directory, profile())
    accepted = accept(left)
    intent = left.claim_next(actor)
    step = successful_step(left, intent)
    version = left.get(actor(), accepted.run_id).version
    barrier = Barrier(2)

    def cancel():
        barrier.wait(timeout=5)
        try:
            return right.cancel(actor(), accepted.run_id, "cancel-race", version, AnalyticsCancelRequest()).status
        except AnalyticsError as error:
            assert error.status == 409
            return "STALE_VERSION"

    def finish():
        barrier.wait(timeout=5)
        return left.observe(actor(), observation(intent, "SUCCEEDED", primary=step.step_id))

    with ThreadPoolExecutor(max_workers=2) as pool:
        cancellation, completion = pool.submit(cancel), pool.submit(finish)
        cancel_status, terminal = cancellation.result(timeout=5), completion.result(timeout=5)
    assert terminal.status == ("SUCCEEDED" if cancel_status == "STALE_VERSION" else "CANCELLED")
    assert not terminal.diagnostics.execution_active
    assert (terminal.result is None) == (terminal.status == "CANCELLED")
    final_events = [e for e in right.events(actor(), accepted.run_id) if e.type in {"run.completed", "run.cancelled"}]
    assert len(final_events) == 1


@pytest.mark.parametrize("changed", [{"attempt_id": "wrong"}, {"session_id": "wrong"}, {"request_id": "wrong"}, {"run_id": "wrong"}])
def test_stale_or_foreign_execution_cannot_write(tmp_path, changed):
    store = make_store(tmp_path / "state")
    accepted = accept(store)
    intent = store.claim_next(lambda _owner: actor())
    before = store.get(actor(), accepted.run_id)
    with pytest.raises(AnalyticsError) as error:
        store.observe(actor(), observation(intent, "FAILED", **changed))
    assert error.value.status == 409
    assert store.get(actor(), accepted.run_id) == before


def test_missing_or_pending_primary_result_never_succeeds(tmp_path):
    store = make_store(tmp_path / "state")
    accept(store)
    intent = store.claim_next(lambda _owner: actor())
    with pytest.raises(AnalyticsError, match="INCOMPLETE_EVIDENCE"):
        store.observe(actor(), observation(intent, "SUCCEEDED"))
    step = successful_step(store, intent)
    store.reserve_step(actor(), intent.run_id, intent.attempt_id, "unfinished")
    with pytest.raises(AnalyticsError, match="INCOMPLETE_EVIDENCE"):
        store.observe(actor(), observation(intent, "SUCCEEDED", primary=step.step_id))
    assert store.get(actor(), intent.run_id).status == "RUNNING"


@pytest.mark.parametrize("outcome", ["FAILED", "NEEDS_INPUT"])
def test_model_failure_or_clarification_before_first_tool_is_durable(tmp_path, outcome):
    store = make_store(tmp_path / "state")
    first = accept(store)
    intent = store.claim_next(lambda _owner: actor())
    terminal = store.observe(actor(), observation(intent, outcome, error_code="MODEL_FAILED" if outcome == "FAILED" else None))
    assert terminal.result is None and terminal.status == outcome
    fresh = RunStore(store.directory, profile())
    second = accept(fresh, key="followup", conversation_id=terminal.conversation_id, parent=first.run_id)
    assert fresh.get(actor(), second.run_id).parent_run_id == first.run_id
    assert fresh.claim_next(lambda _owner: actor()).run_id == second.run_id


@pytest.mark.parametrize("outcome", ["FAILED", "NEEDS_INPUT"])
def test_partial_tool_evidence_is_retained_but_never_presented_as_complete_success(tmp_path, outcome):
    store = make_store(tmp_path / "state")
    accepted = accept(store)
    intent = store.claim_next(actor)
    step = successful_step(store, intent)
    pending = store.reserve_step(actor(), intent.run_id, intent.attempt_id, "second-tool")
    terminal = store.observe(actor(), observation(intent, outcome, error_code="MODEL_FAILED" if outcome == "FAILED" else None))
    assert terminal.status == outcome and terminal.result is None and terminal.primary_result_ref is None
    fresh = RunStore(store.directory, profile())
    assert fresh.step_result(actor(), intent.run_id, intent.attempt_id, step.step_id) == fixture_result()
    with sqlite_connection(store.path) as con:
        assert con.execute("SELECT state FROM steps WHERE step_id=?", (pending.step_id,)).fetchone()[0] == "STARTED"
    with pytest.raises(AnalyticsError):
        fresh.complete_step(actor(), intent.run_id, intent.attempt_id, pending.step_id, fixture_result())
    followup = accept(fresh, key="clarification", conversation_id=terminal.conversation_id, parent=accepted.run_id)
    assert fresh.get(actor(), followup.run_id).parent_run_id == accepted.run_id
    assert fresh.claim_next(actor).run_id == followup.run_id


@pytest.mark.parametrize("operation", ["cancel", "complete_step", "observe"])
def test_busy_cancel_or_result_transaction_never_claims_persistent_success(tmp_path, operation):
    store = make_store(tmp_path / "state")
    accept(store)
    intent = store.claim_next(actor)
    step = store.reserve_step(actor(), intent.run_id, intent.attempt_id, "tool")
    if operation == "observe":
        store.complete_step(actor(), intent.run_id, intent.attempt_id, step.step_id, fixture_result())
    before = store.get(actor(), intent.run_id)

    def write():
        if operation == "cancel":
            return store.cancel(actor(), intent.run_id, "cancel-busy", before.version, AnalyticsCancelRequest())
        if operation == "complete_step":
            return store.complete_step(actor(), intent.run_id, intent.attempt_id, step.step_id, fixture_result())
        return store.observe(actor(), observation(intent, "SUCCEEDED", primary=step.step_id))

    with sqlite_connection(store.path) as lock:
        lock.execute("BEGIN IMMEDIATE")
        with pytest.raises(AnalyticsError, match="STATE_UNAVAILABLE"):
            write()
        assert store.get(actor(), intent.run_id) == before  # WAL reader still works.
    write()
    after = RunStore(store.directory, profile()).get(actor(), intent.run_id)
    assert after.status == {"cancel": "CANCELLING", "complete_step": "RUNNING", "observe": "SUCCEEDED"}[operation]
    assert after.diagnostics.dispatch_attempts == 1


def test_state_busy_never_creates_a_partial_acceptance(tmp_path):
    store = make_store(tmp_path / "state")
    conv = conversation(store)
    with sqlite_connection(store.path) as lock:
        lock.execute("BEGIN IMMEDIATE")
        with pytest.raises(AnalyticsError) as error:
            accept(store, conversation_id=conv.conversation_id)
        assert error.value.code == "STATE_UNAVAILABLE"
        assert lock.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
        assert lock.execute("SELECT count(*) FROM dispatch_intents").fetchone()[0] == 0
    assert accept(store, conversation_id=conv.conversation_id).status == "QUEUED"


def test_failed_result_commit_leaves_no_false_terminal(tmp_path):
    store = make_store(tmp_path / "state")
    accept(store)
    intent = store.claim_next(lambda _owner: actor())
    step = successful_step(store, intent)

    def fail(point):
        if point == "observe:before_commit":
            raise sqlite3.OperationalError("controlled disk failure")

    store.fault_hook = fail
    with pytest.raises(AnalyticsError, match="STATE_UNAVAILABLE"):
        store.observe(actor(), observation(intent, "SUCCEEDED", primary=step.step_id))
    fresh = RunStore(store.directory, profile())
    current = fresh.get(actor(), intent.run_id)
    assert current.status == "RUNNING" and current.result is None and current.diagnostics.execution_active
    assert not any(event.type == "run.completed" for event in fresh.events(actor(), intent.run_id))
