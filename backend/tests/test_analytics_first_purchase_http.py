"""First-purchase HTTP on the shared physical worker, no native product claim."""
import json
import os
from pathlib import Path
from fastapi.testclient import TestClient
from backend.analytics_first_purchase_app import PREFIX, create_first_purchase_app
from backend.services.analytics.access import AnalyticsPrincipal, B0IdentityRegistry
from backend.services.analytics.first_purchase.runtime import FirstPurchaseRuntime
from backend.services.analytics.jobs import RunStore
from backend.analytics_first_purchase_fixture import create_first_purchase_fixture
from backend.tests.analytics_run_support import profile

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
SNAPSHOT_PATH = FIXTURE_DIR / "analytics_first_purchase_v1.json"
EXPECTED_PATH = FIXTURE_DIR / "analytics_first_purchase_v1_expected.json"
MISSING_SNAPSHOT_PATH = FIXTURE_DIR / "analytics_first_purchase_v1_missing_role.json"
MISSING_EXPECTED_PATH = FIXTURE_DIR / "analytics_first_purchase_v1_missing_role_expected.json"
MUTATED_SNAPSHOT_PATH = FIXTURE_DIR / "analytics_first_purchase_v1_mutated.json"
MUTATED_EXPECTED_PATH = FIXTURE_DIR / "analytics_first_purchase_v1_mutated_expected.json"
FAMILY_ROOT = Path(__file__).resolve().parents[1]
TOKEN = "a" * 40
OTHER = "b" * 40
READER = "c" * 40


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def private_dir(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.mkdir(mode=0o700)
    os.chmod(path, 0o700)
    return path


def fp_actor(name="synthetic-demo", *, capabilities=None, scopes=None):
    return AnalyticsPrincipal(
        name,
        frozenset({"run:create", "run:read", "run:cancel"} if capabilities is None else capabilities),
        frozenset({"first-purchase-fixture"} if scopes is None else scopes),
    )


def headers(token=TOKEN, key=None, etag=None):
    values = {"authorization": f"Bearer {token}"}
    if key is not None:
        values["idempotency-key"] = key
    if etag is not None:
        values["if-match"] = str(etag)
    return values



def make_client(tmp_path, snapshot=None):
    fixture = create_first_purchase_fixture(snapshot or load_json(SNAPSHOT_PATH))
    store = RunStore(private_dir(tmp_path, "state"), profile(), family="first_purchase")
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, fp_actor())
    registry.grant(OTHER, fp_actor("other-demo"))
    registry.grant(READER, fp_actor("reader-demo", capabilities={"run:read"}))
    actors = {"synthetic-demo": fp_actor(), "other-demo": fp_actor("other-demo")}
    runtime = FirstPurchaseRuntime(store, fixture, actors.get)
    return TestClient(create_first_purchase_app(runtime, registry)), runtime


def test_http_physical_worker_and_replay(tmp_path):
    client, runtime = make_client(tmp_path)
    expected = load_json(EXPECTED_PATH)
    response = client.post(PREFIX + "/runs", json=expected["request"], headers=headers(key="one"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "SUCCEEDED"
    assert body["result"]["facts"] == expected["result"]["facts"]
    replay = client.post(PREFIX + "/runs", json=expected["request"], headers=headers(key="one"))
    assert replay.json()["run_id"] == body["run_id"]
    assert len(runtime.store.worker_records(active_only=False)) == 1
    fresh = RunStore(runtime.store.directory, profile(), family="first_purchase")
    assert fresh.get(fp_actor(), body["run_id"]).result.facts.model_dump(mode="json") == expected["result"]["facts"]
    changed = {**expected["request"], "observation_days": 60}
    assert client.post(PREFIX + "/runs", json=changed, headers=headers(key="one")).status_code == 409
    assert client.get(PREFIX + "/runs/" + body["run_id"], headers=headers(OTHER)).status_code == 404
    cancel = client.post(PREFIX + "/runs/" + body["run_id"] + "/cancel", json={"reason":"USER_REQUEST"},
                         headers=headers(key="cancel", etag=body["version"]))
    assert cancel.status_code == 200 and cancel.json()["status"] == "SUCCEEDED"
    assert not (runtime.store.directory / "first_purchase_runs.sqlite3").exists()


def test_http_missing_role_is_rejected_without_facts(tmp_path):
    client, _ = make_client(tmp_path, load_json(MISSING_SNAPSHOT_PATH))
    response = client.post(PREFIX + "/runs", json=load_json(MISSING_EXPECTED_PATH)["request"], headers=headers(key="missing"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "SUCCEEDED"
    assert body["result"]["status"] == "REJECTED" and body["result"]["facts"] is None


def test_http_rejects_invalid_or_unauthorized(tmp_path):
    client, runtime = make_client(tmp_path)
    req = load_json(EXPECTED_PATH)["request"]
    assert client.post(PREFIX + "/runs", json=req).status_code == 401
    assert client.post(PREFIX + "/runs", json=req, headers=headers(READER, "read-only")).status_code == 403
    assert client.post(PREFIX + "/runs", json=req, headers=headers()).status_code == 428
    assert client.post(PREFIX + "/runs", json={**req, "observation_days":7}, headers=headers(key="bad")).status_code == 422
    assert not runtime.store.runtime_work()


def test_offline_openapi_has_shared_snapshot():
    schema = create_first_purchase_app().openapi()
    assert schema["x-shared-run-kernel"] is True
    assert "202" in schema["paths"][PREFIX + "/runs"]["post"]["responses"]
    assert "FirstPurchaseKernelSnapshot" in schema["components"]["schemas"]


def test_concurrent_http_same_key_only_one_worker(tmp_path):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    client, runtime = make_client(tmp_path)
    entered, release = threading.Event(), threading.Event()
    def hook(point, payload):
        if point == "worker:spawned":
            entered.set()
            assert release.wait(5)
    runtime.manager.fault_hook = hook
    request = load_json(EXPECTED_PATH)["request"]
    with ThreadPoolExecutor(1) as pool:
        running = pool.submit(client.post, PREFIX + "/runs", json=request, headers=headers(key="parallel"))
        try:
            assert entered.wait(5)
            retry = client.post(PREFIX + "/runs", json=request, headers=headers(key="parallel"))
            assert retry.status_code == 202, retry.text
            assert retry.json()["status"] == "RUNNING"
        finally:
            release.set()
        done = running.result(timeout=10)
    assert done.status_code == 200
    assert done.json()["run_id"] == retry.json()["run_id"]
    assert len(runtime.store.worker_records(active_only=False)) == 1


def test_shared_queued_cancel_never_spawns(tmp_path):
    import fcntl
    client, runtime = make_client(tmp_path)
    path = runtime.store.directory / ".first-purchase-dispatch.lock"
    with path.open("w") as lock:
        path.chmod(0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        accepted = client.post(PREFIX + "/runs", json=load_json(EXPECTED_PATH)["request"], headers=headers(key="queued"))
        assert accepted.status_code == 202
        body = accepted.json()
        cancelled = client.post(PREFIX + "/runs/" + body["run_id"] + "/cancel",
                                json={"reason":"USER_REQUEST"}, headers=headers(key="cancel", etag=body["version"]))
        assert cancelled.json()["status"] == "CANCELLED"
    runtime.tick()
    assert not runtime.store.worker_records(active_only=False)


def test_restart_recovers_orphan_without_resending(tmp_path):
    import subprocess
    import sys
    import time
    client, runtime = make_client(tmp_path)
    code = '''
import json, os, sys
from pathlib import Path
from backend.tests.test_analytics_first_purchase_http import fp_actor, load_json, SNAPSHOT_PATH, EXPECTED_PATH
from backend.tests.analytics_run_support import profile
from backend.analytics_first_purchase_fixture import create_first_purchase_fixture
from backend.services.analytics.jobs import RunStore
from backend.services.analytics.first_purchase.runtime import FirstPurchaseRuntime
store = RunStore(Path(sys.argv[1]), profile(), family="first_purchase")
runtime = FirstPurchaseRuntime(store, create_first_purchase_fixture(load_json(SNAPSHOT_PATH)), lambda _: fp_actor())
def crash(point, payload):
    if point == "worker:spawned": os._exit(73)
runtime.manager.fault_hook = crash
runtime.submit_and_execute(fp_actor(), "orphan", load_json(EXPECTED_PATH)["request"])
'''
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run([sys.executable, "-c", code, str(runtime.store.directory)], cwd=root,
                          env={**os.environ, "PYTHONPATH":str(root)}, timeout=10)
    assert proc.returncode == 73
    request = load_json(EXPECTED_PATH)["request"]
    for _ in range(30):
        replay = client.post(PREFIX + "/runs", json=request, headers=headers(key="orphan"))
        if replay.status_code == 200:
            break
        time.sleep(0.05)
    assert replay.status_code == 200, replay.text
    assert replay.json()["status"] == "FAILED"
    assert replay.json()["result"] is None
    records = runtime.store.worker_records(active_only=False)
    assert len(records) == 1 and records[0]["active_slot"] is None
    assert records[0]["run_id"] == replay.json()["run_id"]


def test_permission_revoked_while_worker_active_cannot_commit_success(tmp_path):
    client, runtime = make_client(tmp_path)
    def revoke(point, payload):
        if point == "worker:spawned":
            runtime.resolve_actor = lambda _: None
            runtime.manager.resolve_actor = lambda _: None
    runtime.manager.fault_hook = revoke
    response = client.post(PREFIX + "/runs", json=load_json(EXPECTED_PATH)["request"], headers=headers(key="revoke"))
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "FAILED"
    assert response.json()["result"] is None
    assert response.json()["diagnostics"]["error_code"] == "PERMISSION_REVOKED"
    assert all(r["active_slot"] is None for r in runtime.store.worker_records(active_only=False))
