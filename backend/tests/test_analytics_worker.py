"""D4 real small read-only DuckDB + owned physical processes, no CRM fixture."""

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

import pytest

from backend.analytics_fixture import SyntheticFixture
from backend.contracts.analytics import AnalyticsCancelRequest
from backend.services.analytics.access import AnalyticsError
from backend.services.analytics.execution_lease import create_lease
from backend.services.analytics.jobs import RunStore
from backend.services.analytics.worker import WorkerManager
from backend.tests.analytics_run_support import (
    REPO_ROOT, accept, actor, child_environment, fixture_result, make_store, observation, profile,
    receive, start_probe, stop_owned, synthetic_fixture,
)
from backend.tests.analytics_worker_probe import ProbeLauncher


def setup_worker(tmp_path, **limits):
    store = make_store(tmp_path / "state", resource_profile=profile(**limits))
    accepted = accept(store)
    intent = store.claim_next(lambda _: actor())
    step = store.reserve_step(actor(), intent.run_id, intent.attempt_id, "query")
    fixture = synthetic_fixture(tmp_path / "fixture")
    return store, accepted, intent, step, fixture


def test_readonly_worker_computes_fixture_and_records_independent_exit(tmp_path):
    store, _, intent, step, fixture = setup_worker(tmp_path)
    before = fixture.validate().read_bytes()
    manager = WorkerManager(store, lambda _: actor(), fixture)
    assert manager.execute(actor(), intent, step) == fixture_result()
    assert fixture.validate().read_bytes() == before
    records = store.worker_records(active_only=False)
    assert len(records) == 1 and records[0]["state"] == "EXITED" and records[0]["active_slot"] is None
    assert records[0]["exit_code"] == 0 and records[0]["error_code"] is None
    metrics = json.loads(records[0]["metrics_json"])
    assert metrics["rss_peak_bytes"] > 0 and metrics["temp_peak_bytes"] == 0
    assert metrics["settings"]["access_mode"].lower() == "read_only"
    assert metrics["settings"]["threads"] == "2"
    assert metrics["settings"]["enable_external_access"] == "false"
    assert metrics["settings"]["lock_configuration"] == "true"
    assert metrics["engine"]["version"] == "1.5.3"
    fresh = RunStore(store.directory, profile())
    assert fresh.step_result(actor(), intent.run_id, intent.attempt_id, step.step_id) == fixture_result()
    done = fresh.observe(actor(), observation(intent, "SUCCEEDED", primary=step.step_id))
    assert done.status == "SUCCEEDED" and not done.diagnostics.execution_active


@pytest.mark.parametrize("pollution", ["manifest", "database", "real-flag", "symlink", "foreign-path"])
def test_fixture_pollution_is_rejected_without_default_path_or_execution(tmp_path, pollution, monkeypatch):
    store, _, intent, step, fixture = setup_worker(tmp_path)
    monkeypatch.setenv("DUCKDB_PATH", str(tmp_path / "never-open.duckdb"))
    directory = Path(fixture.directory)
    if pollution == "manifest":
        with (directory / "manifest.json").open("a") as stream:
            stream.write(" ")
    elif pollution == "database":
        with (directory / "fixture.duckdb").open("ab") as stream:
            stream.write(b"tampered")
    elif pollution == "real-flag":
        manifest = json.loads((directory / "manifest.json").read_text())
        manifest["contains_real_data"] = True
        (directory / "manifest.json").write_text(json.dumps(manifest))
    elif pollution == "symlink":
        linked = tmp_path / "linked"
        linked.symlink_to(directory, target_is_directory=True)
        fixture = SyntheticFixture(str(linked), fixture.manifest_sha256)
    else:
        fixture = SyntheticFixture(str(tmp_path / "missing"), fixture.manifest_sha256)
    with pytest.raises((ValueError, OSError)):
        WorkerManager(store, lambda _: actor(), fixture)
    assert store.worker_records(active_only=False) == []
    assert not (tmp_path / "never-open.duckdb").exists()


def test_live_execution_lease_fences_native_terminal_and_step_commit(tmp_path):
    store, _, intent, step, fixture = setup_worker(tmp_path)
    execution_id = "exec_" + "a" * 32
    fd, dev, ino, _temporary = create_lease(store.directory, execution_id)
    try:
        store.begin_worker(actor(), intent.run_id, intent.attempt_id, step.step_id, execution_id, dev, ino)
        with pytest.raises(BlockingIOError):
            store.worker_exited(execution_id, exit_code=0, error_code=None, metrics={})
        with pytest.raises(AnalyticsError, match="WORKER_ACTIVE"):
            store.complete_step(actor(), intent.run_id, intent.attempt_id, step.step_id, fixture_result())
        with pytest.raises(AnalyticsError, match="WORKER_ACTIVE"):
            store.observe(actor(), observation(intent, "FAILED", error_code="MODEL_FAILED"))
        WorkerManager(store, lambda _: actor(), fixture).recover()
        assert store.get(actor(), intent.run_id).diagnostics.execution_active
        assert store.worker_records()[0]["state"] == "RESERVED"
    finally:
        os.close(fd)
    manager = WorkerManager(store, lambda _: actor(), fixture)
    manager.recover()
    assert store.worker_records() == []
    assert store.get(actor(), intent.run_id).status == "CANCELLING"
    current = store.get(actor(), intent.run_id)
    manager.recover()
    assert store.get(actor(), intent.run_id).version == current.version


def test_stricter_fault_profile_never_raises_approved_default_ceilings(tmp_path):
    store, _, intent, step, fixture = setup_worker(tmp_path, duckdb_memory_mib=16, worker_temp_mib=1,
                                                  worker_rss_observation_mib=256)
    try:
        result = WorkerManager(store, lambda _: actor(), fixture).execute(actor(), intent, step)
    except AnalyticsError as error:
        pytest.fail(f"{error.code}; worker evidence: {store.worker_records(active_only=False)}")
    assert result == fixture_result()
    record = store.worker_records(active_only=False)[0]
    assert json.loads(record["metrics_json"])["settings"]["memory_limit"] == "16.0 MiB"
    assert asdict(fixture)["manifest_sha256"]


def test_worker_peak_excludes_parent_image_and_retains_own_freed_peak():
    # Force the same fork/exec path as an inherited worker lease, with a large
    # but bounded parent image. No DB or persistent file is involved.
    padding = bytearray(256 * 1024 * 1024)
    read_fd, write_fd = os.pipe()
    try:
        command = '''
import json, resource, sys
from backend.analytics_worker import worker_peak_rss_bytes
before = worker_peak_rss_bytes()
memory = bytearray(32 * 1024 * 1024)
allocated = worker_peak_rss_bytes()
del memory
print(json.dumps(dict(before=before, allocated=allocated, freed=worker_peak_rss_bytes(),
    legacy=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024))))
'''
        child = subprocess.run([sys.executable, '-c', command], cwd=REPO_ROOT,
                               env=child_environment(), pass_fds=(read_fd,),
                               capture_output=True, text=True, timeout=15)
        assert child.returncode == 0, child.stderr
        observed = json.loads(child.stdout)
        assert observed['allocated'] >= observed['before'] + 24 * 1024 * 1024, observed
        assert observed['freed'] >= observed['allocated'], observed
        assert observed['freed'] < len(padding), observed
        if sys.platform == 'linux':
            assert observed['legacy'] >= len(padding), observed
    finally:
        os.close(read_fd)
        os.close(write_fd)
        del padding


@pytest.mark.parametrize("reason", ["cancel", "permission", "query_deadline", "run_deadline"])
def test_real_sql_stop_waits_for_physical_exit_and_keeps_original_budget(tmp_path, reason):
    store, _, intent, step, fixture = setup_worker(tmp_path)
    allowed = [actor()]
    def manager_actor(_name):
        return allowed[0]
    initial = store.get(actor(), intent.run_id)
    next_run = accept(store, key="second")
    with ThreadPoolExecutor(max_workers=1) as pool, ProbeLauncher("sql_hold", ignore_term=True) as launch:
        manager = WorkerManager(store, manager_actor, fixture, launch=launch)
        future = pool.submit(manager.execute, actor(), intent, step)
        proof = launch.receive()
        assert proof["event"] == "SQL_ACTIVE" and launch.child.poll() is None
        assert proof["attempt_id"] == intent.attempt_id and proof["step_id"] == step.step_id
        if reason == "cancel":
            store.cancel(actor(), intent.run_id, "cancel", store.get(actor(), intent.run_id).version,
                         AnalyticsCancelRequest())
        elif reason == "permission":
            allowed[0] = actor(capabilities={"run:read"})
        else:
            store.clock = lambda: (step.deadline_ms if reason == "query_deadline" else intent.deadline_ms) + 1
        with pytest.raises(AnalyticsError) as failed:
            future.result(timeout=8)
        assert failed.value.code == {"cancel": "TOOL_FAILED", "permission": "PERMISSION_REVOKED",
                                     "query_deadline": "TIMEOUT", "run_deadline": "TIMEOUT"}[reason]
        assert launch.child.returncode == -9  # SIGTERM ignored; the owned handle was killed and reaped.
    record = store.worker_records(active_only=False)[0]
    metrics = json.loads(record["metrics_json"])
    assert metrics["forced_kill"] is True and record["active_slot"] is None
    # Worker exit alone is not the DSH loop's exit and cannot free the run slot.
    stopped = store.get(actor(), intent.run_id)
    assert stopped.status == "CANCELLING" and stopped.diagnostics.execution_active
    assert stopped.diagnostics.tool_steps_used == initial.diagnostics.tool_steps_used
    assert stopped.diagnostics.dispatch_attempts == initial.diagnostics.dispatch_attempts
    assert store.runtime_work()[0]["intent"] == intent
    assert store.get(actor(), next_run.run_id).status == "QUEUED"
    assert store.claim_next(lambda _: actor()) is None
    with pytest.raises(AnalyticsError):
        store.step_result(actor(), intent.run_id, intent.attempt_id, step.step_id)
    done = store.observe(allowed[0], observation(intent, "CANCELLED" if reason == "cancel" else "FAILED"))
    assert done.status == ("CANCELLED" if reason == "cancel" else "FAILED")
    assert not done.diagnostics.execution_active


def test_readonly_close_and_result_frames_cannot_replace_actual_process_exit(tmp_path):
    store, _, intent, step, fixture = setup_worker(tmp_path)
    with ThreadPoolExecutor(max_workers=1) as pool, ProbeLauncher("closed_hold", ignore_term=True) as launch:
        manager = WorkerManager(store, lambda _: actor(), fixture, launch=launch)
        future = pool.submit(manager.execute, actor(), intent, step)
        assert launch.receive()["event"] == "CLOSED_FRAME_NOT_EXIT"
        assert launch.child.poll() is None and not future.done()
        with pytest.raises(AnalyticsError, match="WORKER_ACTIVE"):
            store.complete_step(actor(), intent.run_id, intent.attempt_id, step.step_id, fixture_result())
        store.cancel(actor(), intent.run_id, "cancel", store.get(actor(), intent.run_id).version,
                     AnalyticsCancelRequest())
        with pytest.raises(AnalyticsError):
            future.result(timeout=8)
    assert store.worker_records(active_only=False)[0]["exit_code"] == -9


@pytest.mark.parametrize("mode,limits", [("rss", {"worker_rss_observation_mib": 32}),
                                       ("temp_exceed", {"worker_temp_mib": 1})])
def test_sampled_physical_resource_limit_stops_only_owned_worker(tmp_path, mode, limits):
    store, _, intent, step, fixture = setup_worker(tmp_path, **limits)
    with ProbeLauncher("sql_hold" if mode == "rss" else mode) as launch:
        manager = WorkerManager(store, lambda _: actor(), fixture, launch=launch)
        with pytest.raises(AnalyticsError, match="RESOURCE_EXCEEDED"):
            manager.execute(actor(), intent, step)
        assert launch.child.poll() is not None
    metrics = json.loads(store.worker_records(active_only=False)[0]["metrics_json"])
    observed = metrics["rss_peak_bytes" if mode == "rss" else "temp_peak_bytes"]
    assert observed > (32 if mode == "rss" else 1) * 1024 * 1024
    assert store.get(actor(), intent.run_id).diagnostics.execution_active
    assert list((store.directory / "workers").glob("*/tmp/*")) == []
    if mode == "temp_exceed":
        assert metrics["temp_removed_files"] == 1 and metrics["temp_removed_bytes"] == 2 * 1024 * 1024


@pytest.mark.parametrize("object_kind", ["unknown-name", "symlink", "hardlink"])
def test_recovery_refuses_foreign_temp_objects_and_keeps_reservation(tmp_path, object_kind):
    store, _, intent, step, _fixture = setup_worker(tmp_path)
    execution_id = "exec_" + "b" * 32
    fd, dev, ino, temporary = create_lease(store.directory, execution_id)
    store.begin_worker(actor(), intent.run_id, intent.attempt_id, step.step_id, execution_id, dev, ino)
    foreign = tmp_path / "preserve.txt"
    foreign.write_text("unrelated retained evidence")
    target = temporary / "duckdb_temp_storage_DEFAULT-0.tmp"
    if object_kind == "unknown-name":
        target = temporary / "unknown.txt"
        target.write_text("not an owned spill")
    elif object_kind == "symlink":
        target.symlink_to(foreign)
    else:
        os.link(foreign, target)
    try:
        with pytest.raises(BlockingIOError):
            store.worker_exited(execution_id, exit_code=0, error_code=None, metrics={})
    finally:
        os.close(fd)
    with pytest.raises(ValueError):
        store.worker_exited(execution_id, exit_code=0, error_code=None, metrics={})
    assert target.exists() and foreign.read_text() == "unrelated retained evidence"
    assert store.worker_records()[0]["active_slot"] == 1


def test_multiple_managers_share_one_physical_slot_before_spawn(tmp_path):
    store, _, intent, step, fixture = setup_worker(tmp_path)
    second_step = store.reserve_step(actor(), intent.run_id, intent.attempt_id, "second-tool")
    with ThreadPoolExecutor(max_workers=1) as pool, ProbeLauncher("sql_hold") as launch:
        future = pool.submit(WorkerManager(store, lambda _: actor(), fixture, launch=launch).execute,
                             actor(), intent, step)
        assert launch.receive()["event"] == "SQL_ACTIVE"
        calls = []

        def no_spawn(config, lease_fd):
            calls.append(config)
            raise AssertionError("shared slot must reject before spawn")

        with pytest.raises(AnalyticsError, match="WORKER_BUSY"):
            WorkerManager(RunStore(store.directory, store.profile), lambda _: actor(), fixture,
                          launch=no_spawn).execute(actor(), intent, second_step)
        assert calls == [] and launch.child.poll() is None
        launch.release()
        assert future.result(timeout=5) == fixture_result()
    assert len(store.worker_records(active_only=False)) == 1


@pytest.mark.parametrize("temp_mib", [1, 64])
def test_real_duckdb_external_sort_spill_and_quota(tmp_path, temp_mib):
    store, _, intent, step, fixture = setup_worker(tmp_path, duckdb_memory_mib=32, worker_temp_mib=temp_mib,
                                                  worker_rss_observation_mib=256)
    original = fixture.validate().read_bytes()
    with ProbeLauncher("spill") as launch:
        manager = WorkerManager(store, lambda _: actor(), fixture, launch=launch)
        if temp_mib == 1:
            with pytest.raises(AnalyticsError, match="RESOURCE_EXCEEDED"):
                manager.execute(actor(), intent, step)
        else:
            assert manager.execute(actor(), intent, step) == fixture_result()
            proof = launch.receive()
            assert proof["event"] == "SPILL_COMPLETE"
        assert launch.child.returncode is not None
    metrics = json.loads(store.worker_records(active_only=False)[0]["metrics_json"])
    if temp_mib == 64:
        assert metrics["temp_peak_bytes"] > 0
    assert fixture.validate().read_bytes() == original
    assert list((store.directory / "workers").glob("*/tmp/*")) == []


def test_engine_temp_quota_separately_with_bounded_owned_child(tmp_path):
    # Distinct engine proof: the physical file observer is tested above. A
    # preallocated spill file can exceed its populated bytes before DuckDB's
    # own quota check, so do not call a parent-initiated stop an engine error.
    store, _, intent, step, fixture = setup_worker(tmp_path, duckdb_memory_mib=32, worker_temp_mib=1)
    execution_id = "exec_" + "c" * 32
    fd, dev, ino, temporary = create_lease(store.directory, execution_id)
    binding = {"execution_id": execution_id, "run_id": intent.run_id,
               "attempt_id": intent.attempt_id, "step_id": step.step_id}
    try:
        store.begin_worker(actor(), intent.run_id, intent.attempt_id, step.step_id, execution_id, dev, ino)
        with ProbeLauncher("spill") as launch:
            child = launch({"binding": binding, "profile": store.profile.model_dump(),
                            "profile_hash": store.profile.digest, "fixture": asdict(fixture),
                            "lease_fd": fd, "temp_dir": str(temporary)}, fd)
            os.close(fd)
            fd = None
            # Input is generated range(2 million), not a larger on-disk DB;
            # owned-child timeout is a five-second backstop, not the run SLA.
            child.wait(timeout=5)
            proof = launch.receive()
            assert proof == {"event": "ENGINE_LIMIT", "pid": child.pid, **binding, "temp_quota": True}
            frames = [json.loads(line) for line in child.stdout.read(65536).splitlines()]
            assert [frame["type"] for frame in frames] == ["ready", "error", "closed"]
            assert frames[1]["code"] == "RESOURCE_EXCEEDED"
            assert child.returncode == 0
            store.worker_exited(execution_id, exit_code=child.returncode, error_code="RESOURCE_EXCEEDED",
                                metrics={"engine_quota_observed": True})
    finally:
        if fd is not None:
            os.close(fd)


@pytest.mark.parametrize("fault", ["SQL_ACTIVE", "worker:before_commit", "worker:after_commit", "worker:spawned"])
def test_owner_crash_never_adopts_pid_replays_sql_or_resets_original_budget(tmp_path, fault):
    store, _, intent, step, fixture = setup_worker(tmp_path)
    payload = {"action": "owner", "state_dir": str(store.directory), "profile": store.profile.model_dump(),
               "fixture": asdict(fixture), "step": asdict(step), "fault": fault}
    owner = subprocess.Popen([sys.executable, "-m", "backend.tests.analytics_worker_probe"], cwd=REPO_ROOT,
                             env=child_environment(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
    unrelated = start_probe({"action": "worker", "attempt_id": "unrelated-owned-child"})
    try:
        owner.stdin.write(json.dumps(payload) + "\n")
        owner.stdin.flush()
        assert receive(unrelated)["ready"] == "worker"
        proof = receive(owner, timeout=8)
        assert proof["event"] == fault
        before = store.get(actor(), intent.run_id)
        records = store.worker_records(active_only=False)
        assert len(records) == (0 if fault == "worker:before_commit" else 1)
        if records:
            WorkerManager(store, lambda _: actor(), fixture).recover()
            assert store.worker_records()[0]["active_slot"] == 1  # Live inherited inode still held.
        owner.kill()  # Exact owned parent handle; never signal the recorded worker PID.
        owner.wait(timeout=5)
        fresh = RunStore(store.directory, store.profile)
        manager = WorkerManager(fresh, lambda _: actor(), fixture)
        deadline = time.monotonic() + 5
        while fresh.worker_records() and time.monotonic() < deadline:
            manager.recover()
            time.sleep(0.02)
        assert fresh.worker_records() == []
        assert unrelated.poll() is None
        after = fresh.get(actor(), intent.run_id)
        assert after.diagnostics.execution_active  # DSH exit remains separately unproven.
        assert after.diagnostics.dispatch_attempts == before.diagnostics.dispatch_attempts
        assert after.diagnostics.tool_steps_used == before.diagnostics.tool_steps_used
        assert fresh.runtime_work()[0]["intent"] == intent
        if after.status == "RUNNING":
            assert fresh.reserve_step(actor(), intent.run_id, intent.attempt_id, "query").disposition == "PENDING"
        else:
            with pytest.raises(AnalyticsError):
                fresh.reserve_step(actor(), intent.run_id, intent.attempt_id, "query")
        assert len(fresh.worker_records(active_only=False)) == len(records)
    finally:
        stop_owned(owner)
        stop_owned(unrelated)


def test_foreign_worker_result_binding_never_commits(tmp_path):
    store, _, intent, step, fixture = setup_worker(tmp_path)
    with ProbeLauncher("foreign_frame") as launch:
        with pytest.raises(AnalyticsError, match="TOOL_FAILED"):
            WorkerManager(store, lambda _: actor(), fixture, launch=launch).execute(actor(), intent, step)
    with pytest.raises(AnalyticsError):
        store.step_result(actor(), intent.run_id, intent.attempt_id, step.step_id)
