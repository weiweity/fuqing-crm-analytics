"""Channel-follow-up shared worker: real child, lease, EXITED gate. HTTP/native NOT RUN."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

import pytest

from backend.analytics_query_fixture import ChannelFollowupFixture, create_channel_followup_fixture
from backend.contracts.analytics import AnalyticsB0Result, AnalyticsCancelRequest, AnalyticsRunSnapshot
from backend.contracts.analytics_query import ChannelFollowupResult
from backend.contracts.analytics_query_run import QUERY_RUN_SCHEMA, AnalyticsQueryRunSnapshot
from backend.services.analytics.access import AnalyticsError
from backend.services.analytics.execution_lease import create_lease
from backend.services.analytics.jobs import RunStore
from backend.services.analytics.worker import WorkerManager
from backend.tests.analytics_run_support import (
    REPO_ROOT, accept, actor, child_environment, make_store, observation, profile, receive,
    sqlite_connection, start_probe, stop_owned, synthetic_fixture,
)
from backend.tests.analytics_query_worker_probe import QueryProbeLauncher
from backend.tests.test_analytics_query_jobs import (
    golden_descriptor, golden_snapshot, make_query_store, query_accept, query_actor,
    query_request,
)

EXPECTED_PATH = Path(__file__).resolve().parent / "fixtures" / "analytics_channel_followup_v1_expected.json"


def private_dir(path: Path) -> Path:
    path.mkdir(mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def query_fixture(path: Path) -> ChannelFollowupFixture:
    return create_channel_followup_fixture(private_dir(path), golden_snapshot())


def setup_query_worker(tmp_path, days=30, **limits):
    fixture = query_fixture(tmp_path / "fixture")
    store = make_query_store(tmp_path / "state", resource_profile=profile(**limits))
    accepted = query_accept(store, descriptor=fixture.binding_descriptor())
    intent = store.claim_next(lambda owner: query_actor() if owner == "alice" else None)
    step = store.reserve_step(
        query_actor(), intent.run_id, intent.attempt_id, "query", request=query_request(days),
    )
    return store, accepted, intent, step, fixture


def window_expected(days: int) -> dict:
    return json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))["windows"][str(days)]


def assert_facts_match_hand_golden(result: ChannelFollowupResult, days: int) -> None:
    expected = window_expected(days)
    assert EXPECTED_PATH.read_text(encoding="utf-8").find('"computation": "NOT_RUN"') > 0
    assert result.facts.observation_days == days
    for index, channel in enumerate(expected["channels"]):
        actual = result.facts.channels[index].model_dump()
        for key, value in channel.items():
            assert actual[key] == value, (days, channel["channel_id"], key, actual[key], value)
    totals = result.facts.totals.model_dump()
    for key, value in expected["totals"].items():
        assert totals[key] == value, (days, key, totals[key], value)


def test_query_step_binding_is_store_trusted_and_does_not_charge_budget(tmp_path):
    store, _, intent, step, fixture = setup_query_worker(tmp_path)
    before = store.get(query_actor(), intent.run_id).diagnostics.tool_steps_used
    frozen = store.query_step_binding(query_actor(), intent.run_id, intent.attempt_id, step.step_id)
    assert frozen.family == "channel_followup"
    assert frozen.request.observation_days == 30
    assert frozen.fixture.physical_sha256 == fixture.binding_descriptor()["physical_sha256"]
    assert frozen.permission_scope != "synthetic-demo"
    wide = query_actor(scopes={"channel-followup-fixture", "unrelated-scope"})
    again = store.query_step_binding(wide, intent.run_id, intent.attempt_id, step.step_id)
    assert again.permission_scope == frozen.permission_scope
    assert again.resolved_filters == frozen.resolved_filters
    assert store.get(query_actor(), intent.run_id).diagnostics.tool_steps_used == before
    b0 = make_store(tmp_path / "b0")
    with pytest.raises(AnalyticsError) as error:
        b0.query_step_binding(actor(), "run_x", "attempt_x", "step_x")
    assert error.value.code == "FAMILY_MISMATCH"


@pytest.mark.parametrize("days", [30, 60, 90])
def test_real_worker_matches_hand_golden_and_reopen_stays_query_type(tmp_path, days):
    store, _, intent, step, fixture = setup_query_worker(tmp_path, days=days)
    before = fixture.physical_sha256()
    source = (Path(fixture.directory) / "channel-followup.duckdb").read_bytes()
    manager = WorkerManager(store, lambda _: query_actor(), fixture)
    result = manager.execute(query_actor(), intent, step)
    assert isinstance(result, ChannelFollowupResult)
    assert_facts_match_hand_golden(result, days)
    assert fixture.physical_sha256() == before
    assert (Path(fixture.directory) / "channel-followup.duckdb").read_bytes() == source
    records = store.worker_records(active_only=False)
    assert len(records) == 1
    assert records[0]["state"] == "EXITED" and records[0]["active_slot"] is None
    assert records[0]["exit_code"] == 0 and records[0]["error_code"] is None
    metrics = json.loads(records[0]["metrics_json"])
    assert metrics["settings"]["access_mode"].lower() == "read_only"
    assert metrics["settings"]["enable_external_access"] == "false"
    assert metrics["settings"]["lock_configuration"] == "true"
    assert metrics["settings"]["threads"] == "2"
    assert metrics["engine"]["version"] == "1.5.3"
    fresh = RunStore(store.directory, profile(), family="channel_followup")
    stored = fresh.step_result(query_actor(), intent.run_id, intent.attempt_id, step.step_id)
    assert stored == result
    snapshot = fresh.get(query_actor(), intent.run_id)
    assert isinstance(snapshot, AnalyticsQueryRunSnapshot)
    assert snapshot.schema_version == QUERY_RUN_SCHEMA
    done = fresh.observe(query_actor(), observation(intent, "SUCCEEDED", primary=step.step_id))
    assert done.status == "SUCCEEDED" and isinstance(done.result, ChannelFollowupResult)
    with pytest.raises(ValueError):
        RunStore(store.directory, profile())
    b0 = make_store(tmp_path / "b0")
    b0_run = accept(b0)
    b0_snap = b0.get(actor(), b0_run.run_id)
    assert isinstance(b0_snap, AnalyticsRunSnapshot)
    assert b0_snap.schema_version == "analytics-run-b0/v1"
    assert b0_snap.result is None


def test_bound_condition_conflict_and_success_replay_does_not_spawn(tmp_path):
    store, _, intent, step, fixture = setup_query_worker(tmp_path, days=30)
    result = WorkerManager(store, lambda _: query_actor(), fixture).execute(query_actor(), intent, step)
    with pytest.raises(AnalyticsError) as changed:
        store.reserve_step(query_actor(), intent.run_id, intent.attempt_id, "query", request=query_request(60))
    assert changed.value.status == 409
    replay = store.reserve_step(query_actor(), intent.run_id, intent.attempt_id, "query", request=query_request(30))
    assert replay.disposition == "REUSE_RESULT" and replay.step_id == step.step_id
    calls = []

    def no_spawn(config, lease_fd):
        calls.append(config)
        raise AssertionError("successful replay must not spawn")

    with pytest.raises(AnalyticsError) as reused:
        WorkerManager(store, lambda _: query_actor(), fixture, launch=no_spawn).execute(
            query_actor(), intent, replay,
        )
    assert reused.value.status == 409 and calls == []
    assert store.step_result(query_actor(), intent.run_id, intent.attempt_id, step.step_id) == result
    assert len(store.worker_records(active_only=False)) == 1


def test_pending_reserve_does_not_spawn_or_reset_budget(tmp_path):
    store, _, intent, step, fixture = setup_query_worker(tmp_path)
    pending = store.reserve_step(query_actor(), intent.run_id, intent.attempt_id, "query", request=query_request(30))
    assert pending.disposition == "PENDING" and pending.step_id == step.step_id
    used = store.get(query_actor(), intent.run_id).diagnostics.tool_steps_used
    calls = []

    def no_spawn(config, lease_fd):
        calls.append(config)
        raise AssertionError("pending must not spawn")

    with pytest.raises(AnalyticsError):
        WorkerManager(store, lambda _: query_actor(), fixture, launch=no_spawn).execute(
            query_actor(), intent, pending,
        )
    assert calls == []
    assert store.get(query_actor(), intent.run_id).diagnostics.tool_steps_used == used
    assert store.worker_records(active_only=False) == []


def test_two_managers_share_one_slot_before_spawn(tmp_path):
    store, _, intent, step, fixture = setup_query_worker(tmp_path)
    second = store.reserve_step(query_actor(), intent.run_id, intent.attempt_id, "second", request=query_request(60))
    with ThreadPoolExecutor(max_workers=1) as pool, QueryProbeLauncher("sql_hold") as launch:
        future = pool.submit(
            WorkerManager(store, lambda _: query_actor(), fixture, launch=launch).execute,
            query_actor(), intent, step,
        )
        assert launch.receive()["event"] == "SQL_ACTIVE"
        calls = []

        def no_spawn(config, lease_fd):
            calls.append(config)
            raise AssertionError("shared slot must reject before spawn")

        busy_store = RunStore(store.directory, store.profile, family="channel_followup")
        with pytest.raises(AnalyticsError, match="WORKER_BUSY"):
            WorkerManager(busy_store, lambda _: query_actor(), fixture, launch=no_spawn).execute(
                query_actor(), intent, second,
            )
        assert calls == [] and launch.child.poll() is None
        launch.release()
        result = future.result(timeout=8)
        assert isinstance(result, ChannelFollowupResult)
    assert len(store.worker_records(active_only=False)) == 1


@pytest.mark.parametrize("reason", ["cancel", "permission", "query_deadline", "run_deadline"])
def test_sql_active_stop_releases_lease_without_result_or_budget_reset(tmp_path, reason):
    store, _, intent, step, fixture = setup_query_worker(tmp_path)
    allowed = [query_actor()]

    def manager_actor(_name):
        return allowed[0]

    initial = store.get(query_actor(), intent.run_id)
    with ThreadPoolExecutor(max_workers=1) as pool, QueryProbeLauncher("sql_hold", ignore_term=True) as launch:
        manager = WorkerManager(store, manager_actor, fixture, launch=launch)
        future = pool.submit(manager.execute, query_actor(), intent, step)
        proof = launch.receive()
        assert proof["event"] == "SQL_ACTIVE" and launch.child.poll() is None
        pid = launch.child.pid
        if reason == "cancel":
            store.cancel(query_actor(), intent.run_id, "cancel", store.get(query_actor(), intent.run_id).version,
                         AnalyticsCancelRequest())
        elif reason == "permission":
            allowed[0] = query_actor(scopes={"b0-fixture"})
        else:
            store.clock = lambda: (step.deadline_ms if reason == "query_deadline" else intent.deadline_ms) + 1
        with pytest.raises(AnalyticsError) as failed:
            future.result(timeout=8)
        assert failed.value.code == {"cancel": "TOOL_FAILED", "permission": "PERMISSION_REVOKED",
                                     "query_deadline": "TIMEOUT", "run_deadline": "TIMEOUT"}[reason]
        assert launch.child.returncode == -9
        assert not Path(f"/proc/{pid}").exists() if os.path.exists("/proc") else True
    record = store.worker_records(active_only=False)[0]
    assert record["state"] == "EXITED" and record["active_slot"] is None
    assert store.worker_records() == []
    stopped = store.get(query_actor(), intent.run_id)
    assert stopped.result is None
    assert stopped.diagnostics.tool_steps_used == initial.diagnostics.tool_steps_used
    with pytest.raises(AnalyticsError):
        store.step_result(query_actor(), intent.run_id, intent.attempt_id, step.step_id)
    fd, _dev, _ino, _temporary = create_lease(store.directory, "exec_" + "d" * 32)
    os.close(fd)


def test_worker_state_read_failure_stops_owned_child_without_raw_driver_error(tmp_path, monkeypatch):
    store, _, intent, step, fixture = setup_query_worker(tmp_path)
    fail_read = threading.Event()
    worker_records = store.worker_records

    def interrupted_read(**kwargs):
        if kwargs.get("execution_id") and fail_read.is_set():
            fail_read.clear()
            raise sqlite3.OperationalError("database is locked")
        return worker_records(**kwargs)

    monkeypatch.setattr(store, "worker_records", interrupted_read)
    with ThreadPoolExecutor(max_workers=1) as pool, QueryProbeLauncher("closed_hold", ignore_term=True) as launch:
        future = pool.submit(
            WorkerManager(store, lambda _: query_actor(), fixture, launch=launch).execute,
            query_actor(), intent, step,
        )
        assert launch.receive()["event"] == "CLOSED_FRAME_NOT_EXIT"
        assert launch.child.poll() is None and not future.done()
        # Inject the exact failed driver boundary from CI; SQL calculation,
        # child process, lease, stop and exit persistence remain real.
        fail_read.set()
        with pytest.raises(AnalyticsError) as failed:
            future.result(timeout=8)
        assert failed.value.code == "EXECUTION_UNKNOWN"
        assert launch.child.returncode == -9
    record = worker_records(active_only=False)[0]
    assert record["state"] == "EXITED" and record["active_slot"] is None
    assert record["error_code"] == "EXECUTION_UNKNOWN"
    with sqlite_connection(store.path) as con:
        assert con.execute("SELECT result_json FROM steps WHERE step_id=?", (step.step_id,)).fetchone()[0] is None


def test_result_and_closed_without_process_exit_cannot_complete(tmp_path):
    store, _, intent, step, fixture = setup_query_worker(tmp_path)
    with ThreadPoolExecutor(max_workers=1) as pool, QueryProbeLauncher("closed_hold", ignore_term=True) as launch:
        future = pool.submit(
            WorkerManager(store, lambda _: query_actor(), fixture, launch=launch).execute,
            query_actor(), intent, step,
        )
        assert launch.receive()["event"] == "CLOSED_FRAME_NOT_EXIT"
        assert launch.child.poll() is None and not future.done()
        with pytest.raises(AnalyticsError, match="WORKER_ACTIVE"):
            store.complete_step(query_actor(), intent.run_id, intent.attempt_id, step.step_id, {"ignored": True})
        store.cancel(query_actor(), intent.run_id, "cancel", store.get(query_actor(), intent.run_id).version,
                     AnalyticsCancelRequest())
        with pytest.raises(AnalyticsError):
            future.result(timeout=8)
    assert store.worker_records(active_only=False)[0]["exit_code"] == -9
    with sqlite_connection(store.path) as con:
        assert con.execute("SELECT result_json FROM steps WHERE step_id=?", (step.step_id,)).fetchone()[0] is None


@pytest.mark.parametrize("mode,code", [("wrong_n", "BINDING_MISMATCH"), ("wrong_scope", "BINDING_MISMATCH")])
def test_parent_binding_rejects_self_consistent_mutants_without_child_error_frame(tmp_path, mode, code):
    store, _, intent, step, fixture = setup_query_worker(tmp_path)
    with QueryProbeLauncher(mode) as launch:
        with pytest.raises(AnalyticsError) as failed:
            WorkerManager(store, lambda _: query_actor(), fixture, launch=launch).execute(
                query_actor(), intent, step,
            )
        assert failed.value.code == code
        assert launch.child.returncode == 0
    record = store.worker_records(active_only=False)[0]
    assert record["state"] == "EXITED" and record["active_slot"] is None
    assert record["exit_code"] == 0 and record["error_code"] is None
    with sqlite_connection(store.path) as con:
        assert con.execute("SELECT result_json FROM steps WHERE step_id=?", (step.step_id,)).fetchone()[0] is None
        assert con.execute("SELECT state FROM steps WHERE step_id=?", (step.step_id,)).fetchone()[0] == "STARTED"
    with pytest.raises(AnalyticsError):
        store.step_result(query_actor(), intent.run_id, intent.attempt_id, step.step_id)


def test_unknown_schema_is_rejected_by_family_codec_not_child_error_frame(tmp_path):
    store, _, intent, step, fixture = setup_query_worker(tmp_path)
    with QueryProbeLauncher("unknown_schema") as launch:
        with pytest.raises(AnalyticsError) as failed:
            WorkerManager(store, lambda _: query_actor(), fixture, launch=launch).execute(
                query_actor(), intent, step,
            )
        assert failed.value.code == "TOOL_FAILED"
    record = store.worker_records(active_only=False)[0]
    assert record["state"] == "EXITED" and record["active_slot"] is None
    assert record["error_code"] == "TOOL_FAILED"
    with sqlite_connection(store.path) as con:
        assert con.execute("SELECT result_json FROM steps WHERE step_id=?", (step.step_id,)).fetchone()[0] is None


def test_fixture_seal_change_after_init_is_durable_failure(tmp_path):
    store, _, intent, step, fixture = setup_query_worker(tmp_path)
    manager = WorkerManager(store, lambda _: query_actor(), fixture)
    with (Path(fixture.directory) / "channel-followup.duckdb").open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(AnalyticsError, match="TOOL_FAILED"):
        manager.execute(query_actor(), intent, step)
    fresh = RunStore(store.directory, profile(), family="channel_followup")
    records = fresh.worker_records(active_only=False)
    assert len(records) == 1 and records[0]["state"] == "EXITED"
    assert records[0]["active_slot"] is None and records[0]["error_code"] == "TOOL_FAILED"
    with sqlite_connection(fresh.path) as con:
        assert con.execute("SELECT result_json FROM steps WHERE step_id=?", (step.step_id,)).fetchone()[0] is None


def test_init_rejects_fixture_that_does_not_match_store_descriptor(tmp_path):
    fixture = query_fixture(tmp_path / "fixture")
    store = make_query_store(tmp_path / "state")
    query_accept(store, descriptor=golden_descriptor())
    assert fixture.binding_descriptor()["physical_sha256"] != golden_descriptor()["physical_sha256"]
    with pytest.raises(ValueError, match="store binding"):
        WorkerManager(store, lambda _: query_actor(), fixture)


@pytest.mark.parametrize("fault", ["SQL_ACTIVE", "worker:before_commit", "worker:after_commit", "worker:spawned"])
def test_owner_crash_never_adopts_pid_or_resends_query(tmp_path, fault):
    store, _, intent, step, fixture = setup_query_worker(tmp_path)
    payload = {"action": "owner", "state_dir": str(store.directory), "profile": store.profile.model_dump(),
               "fixture": asdict(fixture), "step": asdict(step), "fault": fault}
    owner = subprocess.Popen([sys.executable, "-m", "backend.tests.analytics_query_worker_probe"], cwd=REPO_ROOT,
                             env=child_environment(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
    unrelated = start_probe({"action": "worker", "attempt_id": "unrelated-owned-child"})
    try:
        owner.stdin.write(json.dumps(payload) + "\n")
        owner.stdin.flush()
        assert receive(unrelated)["ready"] == "worker"
        proof = receive(owner, timeout=8)
        assert proof["event"] == fault
        before = store.get(query_actor(), intent.run_id)
        records = store.worker_records(active_only=False)
        assert len(records) == (0 if fault == "worker:before_commit" else 1)
        if records:
            WorkerManager(store, lambda _: query_actor(), fixture).recover()
            assert store.worker_records()[0]["active_slot"] == 1
        owner.kill()
        owner.wait(timeout=5)
        fresh = RunStore(store.directory, store.profile, family="channel_followup")
        manager = WorkerManager(fresh, lambda _: query_actor(), fixture)
        deadline = time.monotonic() + 5
        while fresh.worker_records() and time.monotonic() < deadline:
            manager.recover()
            time.sleep(0.02)
        assert fresh.worker_records() == []
        assert unrelated.poll() is None
        after = fresh.get(query_actor(), intent.run_id)
        assert after.diagnostics.execution_active
        assert after.diagnostics.dispatch_attempts == before.diagnostics.dispatch_attempts
        assert after.diagnostics.tool_steps_used == before.diagnostics.tool_steps_used
        assert fresh.runtime_work()[0]["intent"] == intent
        if after.status == "RUNNING":
            assert fresh.reserve_step(
                query_actor(), intent.run_id, intent.attempt_id, "query", request=query_request(30),
            ).disposition == "PENDING"
        else:
            with pytest.raises(AnalyticsError):
                fresh.reserve_step(
                    query_actor(), intent.run_id, intent.attempt_id, "query", request=query_request(30),
                )
        assert len(fresh.worker_records(active_only=False)) == len(records)
    finally:
        stop_owned(owner)
        stop_owned(unrelated)


def test_b0_worker_still_returns_legacy_result_type(tmp_path):
    b0 = make_store(tmp_path / "b0")
    accept(b0)
    intent = b0.claim_next(lambda _: actor())
    step = b0.reserve_step(actor(), intent.run_id, intent.attempt_id, "query")
    fixture = synthetic_fixture(tmp_path / "b0-fixture")
    result = WorkerManager(b0, lambda _: actor(), fixture).execute(actor(), intent, step)
    assert isinstance(result, AnalyticsB0Result)
    assert not isinstance(result, ChannelFollowupResult)
    assert b0.step_result(actor(), intent.run_id, intent.attempt_id, step.step_id) == result
