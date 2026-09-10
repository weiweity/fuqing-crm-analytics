"""Real socket cancellation must fence publication, not only stop awaiting HTTP."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from threading import Event, Thread
from time import monotonic, sleep

import pytest
import uvicorn
from fastapi.testclient import TestClient

from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal
from backend.services.analytics.competition_diagnosis.computed import compute_result
from backend.services.analytics.competition_diagnosis.store import ComputedResultStore
from backend.tests.test_competition_diagnosis_store import (
    ALICE, BASE, BOB, CAPS, SCOPES, TOKEN, B0IdentityRegistry, app_at, condition, private, source as computed_source,
)

ROOT = Path(__file__).resolve().parents[2]
source = computed_source


@pytest.fixture
def held_computation(tmp_path, source, monkeypatch):
    import backend.analytics_competition_app as wiring
    entered, release, attempted = Event(), Event(), Event()
    original_compute, original_save = wiring.compute_result, ComputedResultStore.save

    def compute(*args, **kwargs):
        result = original_compute(*args, **kwargs)
        entered.set()
        assert release.wait(20), "test did not release its computation"
        return result

    def save(*args, **kwargs):
        try:
            return original_save(*args, **kwargs)
        finally:
            attempted.set()

    monkeypatch.setattr(wiring, "compute_result", compute)
    monkeypatch.setattr(ComputedResultStore, "save", save)
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, ALICE)
    app = app_at(tmp_path, source, registry)
    # Bind an OS-assigned loopback port; no fixed user/demo port is touched.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="off"))
        thread = Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = monotonic() + 10
            while not server.started and thread.is_alive() and monotonic() < deadline:
                sleep(0.01)
            assert server.started
            yield f"http://127.0.0.1:{sock.getsockname()[1]}", entered, release, attempted
        finally:
            release.set()
            server.should_exit = True
            thread.join(10)
            assert not thread.is_alive(), "owned test server failed to stop"


@pytest.mark.skipif(shutil.which("node") is None, reason="native HTTP transport requires Node")
@pytest.mark.parametrize("reason", ["native", "deadline"])
def test_native_abort_during_compute_never_publishes(held_computation, tmp_path, reason):
    base, entered, release, attempted = held_computation
    payload = {"capability_id": "diag.gsv", "condition_mode": "EXPLICIT",
               "condition": condition().model_dump(mode="json"), "session_id": "native-cancel", "request_id": "r1"}
    script = """
import { liveDiagnosisCall } from './dsh-plugins/analytics-workbench/src/competition-agent/tools.mjs';
const abort = new AbortController();
const outcome = liveDiagnosisCall('competition_growth_step', JSON.parse(process.env.CANCEL_TEST_PAYLOAD), abort.signal)
  .then(value => ({value}), error => ({name: error.name, cancellation: error.cancellation}));
process.stdin.once('data', () => abort.abort());
console.log(JSON.stringify(await outcome));
process.stdin.destroy();
"""
    process = subprocess.Popen([shutil.which("node"), "--input-type=module", "-e", script], cwd=ROOT,
        env={**os.environ, "COMPETITION_HTTP_BASE": base, "COMPETITION_HTTP_TOKEN": TOKEN,
             "CANCEL_TEST_PAYLOAD": json.dumps(payload)}, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True)
    try:
        assert entered.wait(15), "native transport never reached the computation"
        stdout, stderr = process.communicate("stop\n" if reason == "native" else "", timeout=10)
        assert process.returncode == 0, stderr
        outcome = json.loads(stdout)
        assert outcome["name"] == ("AbortError" if reason == "native" else "TimeoutError"), outcome
        release.set()
        assert attempted.wait(10), "backend did not reach its publication boundary"
        assert ComputedResultStore(tmp_path / "diagnosis").list_results(ALICE) == []
        assert outcome["cancellation"]["status"] == "CANCELLED"
    finally:
        release.set()
        if process.poll() is None:
            process.terminate()
            process.communicate(timeout=10)


def test_cancel_is_durable_scoped_and_cannot_undo_publication(tmp_path, source):
    directory = private(tmp_path / "state")
    store = ComputedResultStore(directory)
    result = compute_result(source, ALICE, condition(), "diag.gsv", session_id="s1", request_id="r1")
    assert store.cancel(ALICE, "s1", "r1")["status"] == "CANCELLED"
    # A new process must respect the fence; no dependence on session RAM.
    process = subprocess.run([sys.executable, "-c", """
import sys
from pathlib import Path
from backend.services.analytics.access import AnalyticsPrincipal, AnalyticsError
from backend.services.analytics.competition_diagnosis.store import ComputedResultStore
actor=AnalyticsPrincipal('alice', frozenset({'analysis:read'}), frozenset({'competition-diagnosis-fixture'}))
try:
    ComputedResultStore(Path(sys.argv[1])).prior(actor, 's1', 'r1', 'unused')
except AnalyticsError as error:
    print(error.code)
""", str(directory)], cwd=tmp_path, env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHON_DOTENV_DISABLED": "1"},
        capture_output=True, text=True, check=True, timeout=20)
    assert process.stdout.strip() == "CANCELLED"
    for action in (lambda: store.prior(ALICE, "s1", "r1", "digest"),
                   lambda: store.save(ALICE, "s1", "r1", "digest", result)):
        with pytest.raises(AnalyticsError) as error:
            action()
        assert error.value.code == "CANCELLED"
    assert store.cancel(ALICE, "s1", "r1")["status"] == "CANCELLED"
    assert store.prior(BOB, "s1", "r1", "digest") is None
    assert store.prior(ALICE, "s2", "r1", "digest") is None
    next_result = compute_result(source, ALICE, condition(), "diag.gsv", session_id="s1", request_id="r2")
    saved = store.save(ALICE, "s1", "r2", "digest", next_result)
    with pytest.raises(AnalyticsError) as error:
        store.cancel(ALICE, "s1", "r2")
    assert error.value.code == "ALREADY_PUBLISHED"
    assert store.prior(ALICE, "s1", "r2", "digest") == saved


def test_http_cancel_before_dispatch_rejects_replay_but_allows_next_request(tmp_path, source, monkeypatch):
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, ALICE)
    app = app_at(tmp_path, source, registry)
    payload = {"session_id": "native-s1", "request_id": "r1"}
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        assert client.post(BASE + "/diagnosis/cancel", json=payload, headers={"Authorization": ""}).status_code == 401
        for actor in (AnalyticsPrincipal("alice", CAPS - {"analysis:read"}, SCOPES),
                      AnalyticsPrincipal("alice", CAPS, frozenset())):
            registry.grant(TOKEN, actor)
            assert client.post(BASE + "/diagnosis/cancel", json=payload).status_code == 403
        registry.grant(TOKEN, ALICE)
        for bad in ({"request_id": "r1"}, {"session_id": "native-s1"}, {**payload, "session_id": "../oops"}):
            assert client.post(BASE + "/diagnosis/cancel", json=bad).status_code == 400
        # Forged owner is ignored; authentication remains the only authority.
        assert client.post(BASE + "/diagnosis/cancel", json={**payload, "actor_id": "bob"}).json()["status"] == "CANCELLED"
        step = {**payload, "capability_id": "diag.gsv", "condition_mode": "EXPLICIT", "condition": condition().model_dump(mode="json")}
        import backend.analytics_competition_app as wiring
        original = wiring.compute_result
        def forbidden(*args, **kwargs):
            pytest.fail("cancelled request must not enter computation")
        monkeypatch.setattr(wiring, "compute_result", forbidden)
        cancelled = client.post(BASE + "/diagnosis/step", json=step)
        assert cancelled.status_code == 409 and cancelled.json()["error"]["code"] == "CANCELLED"
        monkeypatch.setattr(wiring, "compute_result", original)
        completed = client.post(BASE + "/diagnosis/step", json={**step, "request_id": "r2"})
        assert completed.status_code == 200 and completed.json()["analysis_persisted"]
        late = client.post(BASE + "/diagnosis/cancel", json={**payload, "request_id": "r2"})
        assert late.status_code == 409 and late.json()["error"]["code"] == "ALREADY_PUBLISHED"
        assert len(client.get(BASE + "/results").json()["items"]) == 1


def test_busy_cancel_is_unconfirmed_and_must_not_claim_to_fence(tmp_path, source):
    import sqlite3
    store = ComputedResultStore(private(tmp_path / "state"))
    with sqlite3.connect(store.path) as lock:
        lock.execute("BEGIN IMMEDIATE")
        with pytest.raises(AnalyticsError) as error:
            store.cancel(ALICE, "s1", "r1")
        assert error.value.status == 503 and error.value.retryable
        lock.rollback()
    assert store.prior(ALICE, "s1", "r1", "digest") is None
    assert store.cancel(ALICE, "s1", "r1")["status"] == "CANCELLED"
