"""Owned native-state probe: real SQL barrier and invalid worker frames. No CRM."""

import json
import os
import selectors
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.analytics_runtime import runtime_app
from backend.contracts.analytics import AnalyticsB0Result
from backend.services.analytics.access import AnalyticsError
from backend.services.analytics.execution_lease import create_lease
from backend.services.analytics.jobs import RunStore
from backend.services.analytics.worker import WorkerManager, spawn_worker
from backend.tests.analytics_native_probe import (
    NativeProbeCoordinator, native_probe_app, prepare_probe_dir, probe_dir_for_state,
)
from backend.tests.analytics_run_support import (
    REPO_ROOT, accept, actor, child_environment, fixture_result, make_store, observation, synthetic_fixture,
)
from backend.tests.analytics_worker_probe import ProbeDumpOnly
from backend.tests.test_analytics_native_runtime import Receiver, native


BYPASS_ENV = "B0_G1_BYPASS_RESULT_VALIDATOR"


FORBIDDEN_IMPORTS = ("backend.main", "backend.db", "backend.etl", "fuqing_adhoc")


def wait_proof(probe, event="SQL_ACTIVE", timeout=8):
    path = probe / "proof.jsonl"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            lines = [line for line in path.read_text().splitlines() if line]
            for line in reversed(lines):
                row = json.loads(line)
                if row.get("event") == event:
                    return row
        time.sleep(0.02)
    raise AssertionError(f"{event} proof was not written")


def wait_current(probe, timeout=8):
    path = probe / "current.json"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file() and path.stat().st_size:
            return json.loads(path.read_text())
        time.sleep(0.02)
    raise AssertionError("current hold file was not written")


def write_release(probe, execution_id, nonce):
    target = probe / "release" / execution_id
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.write(fd, nonce.encode())
    finally:
        os.close(fd)


def start_step(store, key):
    accept(store, key=key)
    intent = store.claim_next(lambda _: actor())
    step = store.reserve_step(actor(), intent.run_id, intent.attempt_id, f"query-{key}")
    return intent, step


def finish(store, intent, step, *, failed=False):
    if failed:
        store.observe(actor(), observation(intent, "FAILED", error_code="MODEL_FAILED"))
    else:
        store.observe(actor(), observation(intent, "SUCCEEDED", primary=step.step_id))


def setup_probe_runtime(tmp_path, sequence=("sql_hold", "unknown_schema", "illegal_facts", "passthrough")):
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    state = runtime / "kernel"
    state.mkdir(mode=0o700)
    probe = prepare_probe_dir(runtime / "probe", sequence)
    store = make_store(state)
    fixture = synthetic_fixture(tmp_path / "fixture")
    return store, fixture, probe


def test_probe_sources_do_not_import_crm_or_real_db():
    root = Path(__file__).resolve().parents[2]
    for name in ("analytics_native_probe.py", "analytics_worker_probe.py"):
        text = (root / "backend/tests" / name).read_text()
        for forbidden in FORBIDDEN_IMPORTS:
            assert forbidden not in text
        assert "DUCKDB_PATH" not in text


def test_default_runtime_app_never_installs_probe_launcher(tmp_path):
    fixture = synthetic_fixture(tmp_path / "fixture")
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    app = runtime_app({"state_dir": str(state), "session_id": "native-session", "gateway_token": "g" * 40,
                       "runtime_token": "r" * 40, "fixture": asdict(fixture)}, bridge=Receiver())
    assert app.state.workers.launch is spawn_worker
    assert not hasattr(app.state, "probe")
    assert not any(getattr(route, "path", "").endswith("/probe") for route in app.routes)
    assert not any(path.startswith("/internal") for path in app.openapi()["paths"])


def test_probe_app_requires_owned_probe_dir_and_adds_no_http_routes(tmp_path):
    fixture = synthetic_fixture(tmp_path / "fixture")
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    state = runtime / "kernel"
    state.mkdir(mode=0o700)
    config = {"state_dir": str(state), "session_id": "native-session", "gateway_token": "g" * 40,
              "runtime_token": "r" * 40, "fixture": asdict(fixture)}
    with pytest.raises((FileNotFoundError, ValueError, OSError)):
        native_probe_app(config, bridge=Receiver())
    real_probe = prepare_probe_dir(tmp_path / "real-probe")
    (runtime / "probe").symlink_to(real_probe)
    with pytest.raises(ValueError, match="symlink"):
        native_probe_app(config, bridge=Receiver())
    (runtime / "probe").unlink()
    prepare_probe_dir(runtime / "probe")
    probe_app = native_probe_app(config, bridge=Receiver())
    prod_state = tmp_path / "prod"
    prod_state.mkdir(mode=0o700)
    prod = runtime_app({"state_dir": str(prod_state), "session_id": "native-session",
                        "gateway_token": "g" * 40, "runtime_token": "r" * 40,
                        "fixture": asdict(fixture)}, bridge=Receiver())
    assert probe_app.state.workers.launch is probe_app.state.probe
    assert probe_app.state.workers.launch is not spawn_worker
    prod_paths = sorted((getattr(route, "path", None), tuple(sorted(getattr(route, "methods", []) or [])))
                        for route in prod.routes)
    probe_paths = sorted((getattr(route, "path", None), tuple(sorted(getattr(route, "methods", []) or [])))
                         for route in probe_app.routes)
    assert prod_paths == probe_paths
    assert probe_app.openapi()["paths"].keys() == prod.openapi()["paths"].keys()
    assert "/internal/native/fixture" not in probe_app.openapi()["paths"]
    probe_app.state.probe.close()


def test_probe_app_http_surface_matches_production_auth(tmp_path):
    fixture = synthetic_fixture(tmp_path / "fixture")
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    state = runtime / "kernel"
    state.mkdir(mode=0o700)
    prepare_probe_dir(runtime / "probe", ("passthrough",))
    config = {"state_dir": str(state), "session_id": "native-session", "gateway_token": "g" * 40,
              "runtime_token": "r" * 40, "fixture": asdict(fixture)}
    app = native_probe_app(config, bridge=Receiver())
    with TestClient(app) as client:
        app.state.dispatcher.ready = True
        endpoint = "/internal/native/prompt"
        assert client.post(endpoint, json=native()).status_code == 401
        assert client.post(endpoint, json=native(), headers={"authorization": "Bearer " + "r" * 40}).status_code == 401
        created = client.post(endpoint, json=native(), headers={"authorization": "Bearer " + "g" * 40})
        assert created.status_code == 202
        assert client.post("/internal/native/fixture", json={"session_id": "native-session", "request_id": "native-1",
                                                            "call_id": "tool", "query": "channel_repeat_rate"},
                           headers={"authorization": "Bearer " + "g" * 40}).status_code == 401


def test_sql_hold_proof_is_bound_and_stale_release_is_ignored(tmp_path):
    store, fixture, probe = setup_probe_runtime(tmp_path, ("sql_hold", "passthrough"))
    coordinator = NativeProbeCoordinator(probe)
    manager = WorkerManager(store, lambda _: actor(), fixture, launch=coordinator)
    try:
        intent, step = start_step(store, "hold")
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(manager.execute, actor(), intent, step)
            proof = wait_proof(probe)
            current = wait_current(probe)
            assert proof["event"] == "SQL_ACTIVE"
            assert proof["run_id"] == intent.run_id
            assert proof["attempt_id"] == intent.attempt_id
            assert proof["step_id"] == step.step_id
            assert "release_nonce" not in proof
            assert current["execution_id"] == proof["execution_id"]
            records = store.worker_records()
            assert len(records) == 1
            assert records[0]["state"] == "RUNNING" and records[0]["active_slot"] == 1
            assert records[0]["execution_id"] == proof["execution_id"]
            assert store.get(actor(), intent.run_id).diagnostics.execution_active
            write_release(probe, "exec_" + "ab" * 16, current["release_nonce"])
            time.sleep(0.2)
            assert future.running()
            write_release(probe, current["execution_id"], current["release_nonce"])
            assert future.result(timeout=15) == fixture_result()
        record = store.worker_records(active_only=False)[0]
        assert record["state"] == "EXITED" and record["active_slot"] is None
        assert record["error_code"] is None and record["exit_code"] == 0
        finish(store, intent, step)
    finally:
        coordinator.close()


def _bypass_parent_result_validator_if_requested():
    if os.environ.get(BYPASS_ENV) != "1":
        return
    import backend.services.analytics.worker as worker_mod

    def _accept(_cls, *_args, **_kwargs):
        return fixture_result()

    AnalyticsB0Result.model_validate = classmethod(_accept)
    worker_mod.AnalyticsB0Result.model_validate = classmethod(_accept)


def test_invalid_probe_result_is_dump_only_and_rejected_by_production_validator():
    payload = fixture_result().model_dump(mode="json")
    payload["schema_version"] = "analytics-run-b0/v99"
    dumped = ProbeDumpOnly(payload).model_dump(mode="json")
    assert dumped["schema_version"] == "analytics-run-b0/v99"
    assert dumped["facts"]["repeat_ratio"] == 0.25
    assert not isinstance(ProbeDumpOnly(payload), AnalyticsB0Result)
    with pytest.raises(Exception):
        AnalyticsB0Result.model_validate(dumped)


def test_unknown_schema_and_illegal_facts_are_parent_rejections(tmp_path):
    _bypass_parent_result_validator_if_requested()
    store, fixture, probe = setup_probe_runtime(tmp_path, ("unknown_schema", "illegal_facts", "passthrough"))
    coordinator = NativeProbeCoordinator(probe)
    manager = WorkerManager(store, lambda _: actor(), fixture, launch=coordinator)
    try:
        for key, mode in (("unknown", "unknown_schema"), ("illegal", "illegal_facts")):
            intent, step = start_step(store, key)
            with pytest.raises(AnalyticsError, match="TOOL_FAILED"):
                manager.execute(actor(), intent, step)
            records = store.worker_records(active_only=False)
            latest = records[-1]
            assert latest["run_id"] == intent.run_id
            assert latest["state"] == "EXITED" and latest["active_slot"] is None
            assert latest["error_code"] == "TOOL_FAILED"
            with pytest.raises(AnalyticsError):
                store.step_result(actor(), intent.run_id, intent.attempt_id, step.step_id)
            finish(store, intent, step, failed=True)
            fresh = RunStore(store.directory, store.profile)
            done = fresh.get(actor(), intent.run_id)
            assert done.result is None and not done.diagnostics.execution_active
            assert mode in {"unknown_schema", "illegal_facts"}
        intent, step = start_step(store, "recover")
        assert manager.execute(actor(), intent, step) == fixture_result()
        record = store.worker_records(active_only=False)[-1]
        assert record["state"] == "EXITED" and record["error_code"] is None and record["active_slot"] is None
        finish(store, intent, step)
    finally:
        coordinator.close()


def test_parent_rejection_dies_under_validator_bypass():
    env = child_environment()
    env[BYPASS_ENV] = "1"
    target = "backend/tests/test_analytics_native_probe.py::test_unknown_schema_and_illegal_facts_are_parent_rejections"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--noconftest", "-W", "error::ResourceWarning", "-q", target],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=90)
    assert proc.returncode != 0, proc.stdout + proc.stderr
    combined = proc.stdout + proc.stderr
    assert "failed" in combined.lower() or "Failed" in combined
    assert "1 passed" not in proc.stdout


def test_close_kills_this_instance_sql_hold_child(tmp_path):
    store, fixture, probe = setup_probe_runtime(tmp_path, ("sql_hold",))
    coordinator = NativeProbeCoordinator(probe)
    manager = WorkerManager(store, lambda _: actor(), fixture, launch=coordinator)
    intent, step = start_step(store, "kill")
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(manager.execute, actor(), intent, step)
        proof = wait_proof(probe)
        pid = proof["pid"]
        os.kill(pid, 0)
        coordinator.close()
        with pytest.raises(AnalyticsError):
            future.result(timeout=10)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            break
        time.sleep(0.05)
    else:
        raise AssertionError("owned probe child remained after coordinator close")
    record = store.worker_records(active_only=False)[0]
    assert record["state"] == "EXITED" and record["active_slot"] is None


def test_coordinator_close_preserves_worker_owned_pipes_until_eof(tmp_path):
    # Pause the consuming owner by not reading yet. Closing these registered
    # pipes in the coordinator can strand a Linux epoll map after child exit.
    store, fixture, probe = setup_probe_runtime(tmp_path, ("sql_hold",))
    intent, step = start_step(store, "pipe-owner")
    execution_id = "exec_" + "de" * 16
    fd, _dev, _ino, temporary = create_lease(store.directory, execution_id)
    binding = {"execution_id": execution_id, "run_id": intent.run_id,
               "attempt_id": intent.attempt_id, "step_id": step.step_id}
    coordinator = NativeProbeCoordinator(probe)
    child = None
    try:
        child = coordinator({"binding": binding, "profile": store.profile.model_dump(),
                             "profile_hash": store.profile.digest, "fixture": asdict(fixture),
                             "lease_fd": fd, "temp_dir": str(temporary)}, fd)
        os.close(fd)
        fd = None
        assert wait_proof(probe)["pid"] == child.pid
        with selectors.DefaultSelector() as selector:
            for stream in (child.stdout, child.stderr):
                selector.register(stream, selectors.EVENT_READ)
            coordinator.close()
            assert child.poll() == -9
            assert not child.stdout.closed and not child.stderr.closed
            deadline = time.monotonic() + 3
            while selector.get_map() and time.monotonic() < deadline:
                for key, _events in selector.select(timeout=0.02):
                    if not os.read(key.fd, 65536):
                        selector.unregister(key.fileobj)
            assert not selector.get_map(), "worker owner must be able to drain both pipes to EOF"
    finally:
        coordinator.close()
        if child is not None:
            for stream in (child.stdin, child.stdout, child.stderr):
                stream.close()
        if fd is not None:
            os.close(fd)


def test_probe_dir_helper_is_sibling_of_kernel_state(tmp_path):
    kernel = tmp_path / "cell" / "kernel"
    kernel.mkdir(parents=True, mode=0o700)
    assert probe_dir_for_state(kernel) == (tmp_path / "cell" / "probe").resolve()


def test_world_writable_probe_dir_is_rejected(tmp_path):
    probe = prepare_probe_dir(tmp_path / "probe")
    os.chmod(probe, 0o777)
    with pytest.raises(ValueError):
        NativeProbeCoordinator(probe)
    os.chmod(probe, 0o700)
    os.chmod(probe / "release", 0o777)
    with pytest.raises(ValueError):
        NativeProbeCoordinator(probe)
