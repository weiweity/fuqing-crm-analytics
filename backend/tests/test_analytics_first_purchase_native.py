"""Native first-purchase adapter over shared RunStore/worker. No ledger."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.analytics_first_purchase_fixture import create_first_purchase_fixture
from backend.analytics_first_purchase_native import create_first_purchase_native_app
from backend.contracts.analytics_first_purchase import FirstPurchaseQueryRequest
from backend.contracts.analytics_first_purchase_kernel import (
    FIRST_PURCHASE_CONTEXT_SCHEMA,
    FirstPurchaseConversationRequest,
    FirstPurchaseKernelRequest,
)
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal
from backend.services.analytics.jobs import RunStore
from backend.services.analytics.runtime import execute_native_first_purchase
from backend.services.analytics.worker import WorkerManager
from backend.tests.analytics_run_support import observation, profile, sqlite_connection
from backend.tests.test_analytics_native_runtime import Receiver

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
SNAPSHOT = json.loads((FIXTURE_DIR / "analytics_first_purchase_v1.json").read_text(encoding="utf-8"))
EXPECTED = json.loads((FIXTURE_DIR / "analytics_first_purchase_v1_expected.json").read_text(encoding="utf-8"))
MISSING = json.loads((FIXTURE_DIR / "analytics_first_purchase_v1_missing_role.json").read_text(encoding="utf-8"))
MISSING_EXPECTED = json.loads((FIXTURE_DIR / "analytics_first_purchase_v1_missing_role_expected.json").read_text(encoding="utf-8"))
RUNTIME = "r" * 32
GATEWAY = "g" * 32
SESSION = "session-first-purchase"
DIGEST = "a" * 64
PREFIX = "/api/v1/analytics-first-purchase"


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


def native_prompt(key="req-1", text="查看合成首购路径", session=SESSION):
    return {
        "sessionId": session, "requestId": key, "mode": "queue",
        "content": [{"type": "text", "text": text}], "clientTimeZone": "Asia/Shanghai",
    }


def make_store(path: Path, **kwargs):
    path.mkdir(mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    return RunStore(path, kwargs.pop("resource_profile", profile()), family="first_purchase", **kwargs)


def bind_native(store, principal=None, *, key="req-1", digest=DIGEST):
    principal = principal or fp_actor()
    fixture = create_first_purchase_fixture(SNAPSHOT)
    conv = store.create_conversation(
        principal, "native-first-purchase", FirstPurchaseConversationRequest(),
        runtime_session_id=SESSION,
    )
    accepted = store.accept(
        principal, conv.conversation_id, key,
        FirstPurchaseKernelRequest(question="查看合成首购路径"),
        method_package_digest=digest, fixture_descriptor=fixture.binding_descriptor(),
        native_request=native_prompt(key),
    )
    return conv, accepted, fixture


def native_app(tmp_path: Path, snapshot=None, *, assets=False, bridge=None):
    config = {
        "state_dir": str(private_dir(tmp_path, "state")),
        "runtime_token": RUNTIME,
        "gateway_token": GATEWAY,
        "session_id": SESSION,
        "snapshot": snapshot or SNAPSHOT,
        "method_package_digest": DIGEST,
    }
    if assets:
        analysis = private_dir(tmp_path, "analyses")
        cockpit = private_dir(tmp_path, "cockpit")
        config.update({
            "analysis_dir": str(analysis),
            "cockpit_dir": str(cockpit),
            "asset_capabilities": ["analysis:save", "analysis:read", "dashboard:read", "dashboard:update"],
        })
    return create_first_purchase_native_app(config, bridge=bridge or Receiver())


def auth(token=GATEWAY):
    return {"authorization": f"Bearer {token}"}


def runtime_headers():
    return {"authorization": f"Bearer {RUNTIME}"}


def test_prompt_binds_real_run_before_execute_and_survives_reopen(tmp_path):
    store = make_store(tmp_path / "state")
    conv, accepted, _fixture = bind_native(store)
    assert accepted.run_id.startswith("run_")
    assert accepted.location == f"{PREFIX}/runs/{accepted.run_id}"
    assert "analytics-query" not in accepted.location
    snapshot = store.get(fp_actor(), accepted.run_id)
    assert snapshot.status == "QUEUED"
    work = store.runtime_work(session_id=SESSION, request_id="req-1")
    assert len(work) == 1
    assert work[0]["intent"].run_id == accepted.run_id
    assert work[0]["status"] == "QUEUED"
    listed = store.get_conversation(fp_actor(), conv.conversation_id)
    assert accepted.run_id in listed.run_ids
    with sqlite_connection(store.path) as con:
        row = con.execute(
            "SELECT request_hash FROM idempotency WHERE operation='runtime.binding' AND target=? AND key='method'",
            (accepted.run_id,),
        ).fetchone()
        assert row[0] == DIGEST
        native = con.execute(
            "SELECT 1 FROM idempotency WHERE operation='runtime.native-binding' AND target=?",
            (accepted.run_id,),
        ).fetchone()
        assert native is not None
    restored = RunStore(store.directory, profile(), family="first_purchase")
    found = restored.runtime_work(session_id=SESSION, request_id="req-1")
    assert len(found) == 1 and found[0]["intent"].run_id == accepted.run_id
    replay = restored.accept(
        fp_actor(), conv.conversation_id, "req-1",
        FirstPurchaseKernelRequest(question="查看合成首购路径"),
        allow_new=False, method_package_digest=DIGEST,
        fixture_descriptor=create_first_purchase_fixture(SNAPSHOT).binding_descriptor(),
        native_request=native_prompt(),
    )
    assert replay.run_id == accepted.run_id
    assert replay.location == accepted.location


def test_unregistered_cross_session_and_revoked_native_are_rejected(tmp_path):
    store = make_store(tmp_path / "state")
    _conv, accepted, fixture = bind_native(store)
    workers = WorkerManager(store, lambda _: fp_actor(), fixture)
    with pytest.raises(AnalyticsError) as unbound:
        execute_native_first_purchase(
            store, lambda _: fp_actor(), SESSION, "never-registered", "call-1",
            FirstPurchaseQueryRequest.model_validate(EXPECTED["request"]), workers=workers,
        )
    assert unbound.value.code == "UNBOUND_NATIVE_REQUEST"
    with pytest.raises(AnalyticsError) as foreign:
        execute_native_first_purchase(
            store, lambda _: fp_actor(), "other-session", "req-1", "call-1",
            FirstPurchaseQueryRequest.model_validate(EXPECTED["request"]), workers=workers,
        )
    assert foreign.value.code == "UNBOUND_NATIVE_REQUEST"
    with pytest.raises(AnalyticsError) as revoked:
        execute_native_first_purchase(
            store, lambda _: None, SESSION, "req-1", "call-1",
            FirstPurchaseQueryRequest.model_validate(EXPECTED["request"]), workers=workers,
        )
    assert revoked.value.status == 403
    reader = fp_actor(capabilities={"run:read"})
    with pytest.raises(AnalyticsError) as forbidden:
        store.accept(
            reader, accepted.run_id, "req-2",
            FirstPurchaseKernelRequest(question="查看合成首购路径"),
            method_package_digest=DIGEST, fixture_descriptor=fixture.binding_descriptor(),
            native_request=native_prompt("req-2"),
        )
    assert forbidden.value.status == 403


def test_context_uses_shared_budget_and_actual_status(tmp_path):
    store = make_store(tmp_path / "state")
    _conv, accepted, _fixture = bind_native(store)
    intent = store.claim_next(lambda _: fp_actor())
    assert intent.run_id == accepted.run_id
    state = store.rebuild_context(
        fp_actor(), intent.run_id, intent.attempt_id, package_digest=DIGEST, unit_id="model:1:1",
    )
    assert state["schema_version"] == FIRST_PURCHASE_CONTEXT_SCHEMA
    assert state["run_status"] == "RUNNING"
    assert state["run_id"] == accepted.run_id
    assert state["versions"]["method_package_digest"] == DIGEST
    assert state["remaining_budget"]["model_steps"] == 7
    with pytest.raises(AnalyticsError) as mismatch:
        store.rebuild_context(
            fp_actor(), intent.run_id, intent.attempt_id, package_digest="b" * 64, unit_id="model:1:2",
        )
    assert mismatch.value.code in {"METHOD_NOT_BOUND", "CONFLICT"}
    for index in range(7):
        store.rebuild_context(
            fp_actor(), intent.run_id, intent.attempt_id, package_digest=DIGEST, unit_id=f"model:2:{index}",
        )
    with pytest.raises(AnalyticsError) as exhausted:
        store.rebuild_context(
            fp_actor(), intent.run_id, intent.attempt_id, package_digest=DIGEST, unit_id="model:2:7",
        )
    assert exhausted.value.code == "RESOURCE_EXCEEDED"
    store.observe(fp_actor(), observation(intent, "FAILED"))
    done = store.get(fp_actor(), accepted.run_id)
    assert done.status == "FAILED"
    with pytest.raises(AnalyticsError):
        store.rebuild_context(
            fp_actor(), intent.run_id, intent.attempt_id, package_digest=DIGEST, unit_id="model:late",
        )


def test_in_flight_retry_keeps_run_and_does_not_report_tool_failed(tmp_path):
    store = make_store(tmp_path / "state")
    _conv, accepted, fixture = bind_native(store)
    workers = WorkerManager(store, lambda _: fp_actor(), fixture)
    status, receipt = execute_native_first_purchase(
        store, lambda _: fp_actor(), SESSION, "req-1", "call-1",
        FirstPurchaseQueryRequest.model_validate(EXPECTED["request"]), workers=workers,
    )
    assert status == 202
    assert receipt["disposition"] == "IN_FLIGHT"
    assert receipt["run_id"] == accepted.run_id
    assert receipt["result"] is None
    assert receipt["run_status"] == "QUEUED"
    again_status, again = execute_native_first_purchase(
        store, lambda _: fp_actor(), SESSION, "req-1", "call-2",
        FirstPurchaseQueryRequest.model_validate(EXPECTED["request"]), workers=workers,
    )
    assert again_status == 202
    assert again["run_id"] == accepted.run_id
    assert store.get(fp_actor(), accepted.run_id).status == "QUEUED"
    assert len(store.runtime_work(session_id=SESSION, request_id="req-1")) == 1


def test_http_prompt_context_execute_cancel_and_get_readonly(tmp_path):
    app = native_app(tmp_path)
    with TestClient(app) as client:
        app.state.dispatcher.tick()
        prompt = client.post("/internal/native/prompt", json=native_prompt(), headers=auth())
        assert prompt.status_code == 202, prompt.text
        run_id = prompt.json()["run_id"]
        assert run_id.startswith("run_")
        assert prompt.json()["location"] == f"{PREFIX}/runs/{run_id}"
        assert "analytics-query" not in prompt.json()["location"]
        listed = client.get("/internal/native/context", headers=auth())
        assert listed.status_code == 200
        assert run_id in listed.json()["conversation"]["run_ids"]
        assert listed.json()["conversation"]["schema_version"] == "analytics-run-first-purchase-path/v1"
        got = client.get(prompt.json()["location"], headers=auth())
        assert got.status_code == 200
        assert got.json()["status"] in {"QUEUED", "RUNNING"}
        assert got.json()["run_id"] == run_id
        workers_before = len(app.state.store.worker_records(active_only=False))
        again = client.get(f"{PREFIX}/runs/{run_id}", headers=auth())
        assert again.status_code == 200
        assert len(app.state.store.worker_records(active_only=False)) == workers_before
        unbound = client.post("/internal/native/first-purchase", json={
            "session_id": SESSION, "request_id": "ghost", "call_id": "c1",
            "request": EXPECTED["request"],
        }, headers=runtime_headers())
        assert unbound.status_code == 409
        assert unbound.json()["error"]["code"] == "UNBOUND_NATIVE_REQUEST"
        foreign = client.post("/internal/native/first-purchase", json={
            "session_id": "other", "request_id": "req-1", "call_id": "c1",
            "request": EXPECTED["request"],
        }, headers=runtime_headers())
        assert foreign.status_code == 404
        mismatch = client.post("/internal/native/run-context", json={
            "session_id": SESSION, "request_id": "req-1", "unit_id": "model:1:1",
            "package_digest": "b" * 64,
        }, headers=runtime_headers())
        assert mismatch.status_code == 409
        assert mismatch.json()["error"]["code"] == "METHOD_VERSION_MISMATCH"
        idle = client.post("/internal/native/first-purchase/cancel", json={}, headers={**auth(), "idempotency-key": "no-run"})
        assert idle.status_code == 409
        assert idle.json()["error"]["code"] == "NO_ACTIVE_RUN"
        app.state.dispatcher.tick()
        current = client.get(f"{PREFIX}/runs/{run_id}", headers=auth()).json()
        if current["status"] == "QUEUED":
            intent = app.state.store.claim_next(lambda owner: fp_actor() if owner == "synthetic-demo" else None)
            assert intent is not None
        executed = client.post("/internal/native/first-purchase", json={
            "session_id": SESSION, "request_id": "req-1", "call_id": "call-ok",
            "request": EXPECTED["request"],
        }, headers=runtime_headers())
        assert executed.status_code == 200, executed.text
        receipt = executed.json()
        assert receipt["run_id"] == run_id
        assert receipt["disposition"] in {"EXECUTE", "REUSE_RESULT"}
        assert receipt["result"]["facts"] == EXPECTED["result"]["facts"]
        replay = client.post("/internal/native/first-purchase", json={
            "session_id": SESSION, "request_id": "req-1", "call_id": "call-ok",
            "request": EXPECTED["request"],
        }, headers=runtime_headers())
        assert replay.status_code == 200
        assert replay.json()["run_id"] == run_id
        assert replay.json()["disposition"] == "REUSE_RESULT"
        ctx = client.post("/internal/native/run-context", json={
            "session_id": SESSION, "request_id": "req-1", "unit_id": "model:done",
            "package_digest": DIGEST,
        }, headers=runtime_headers())
        assert ctx.status_code == 200
        assert ctx.json()["run_status"] == "SUCCEEDED"
        assert ctx.json()["completed_steps"]
        denied = client.post("/internal/native/run-context", json={
            "session_id": SESSION, "request_id": "req-1", "unit_id": "late-resource",
            "package_digest": DIGEST, "resource": "SKILL.md",
        }, headers=runtime_headers())
        assert denied.status_code == 409
        remaining = ctx.json()["remaining_budget"]["model_steps"]
        for index in range(remaining):
            summary = client.post("/internal/native/run-context", json={
                "session_id": SESSION, "request_id": "req-1", "unit_id": f"summary:{index}",
                "package_digest": DIGEST,
            }, headers=runtime_headers())
            assert summary.status_code == 200
        exhausted = client.post("/internal/native/run-context", json={
            "session_id": SESSION, "request_id": "req-1", "unit_id": "summary:exhausted",
            "package_digest": DIGEST,
        }, headers=runtime_headers())
        assert exhausted.status_code == 409
        assert exhausted.json()["error"]["code"] == "RESOURCE_EXCEEDED"
        snap = client.get(f"{PREFIX}/runs/{run_id}", headers=auth()).json()
        cancel = client.post(
            f"{PREFIX}/runs/{run_id}/cancel", json={"reason": "USER_REQUEST"},
            headers={**auth(), "idempotency-key": "c1", "if-match": str(snap["version"])},
        )
        assert cancel.status_code == 200
        assert cancel.json()["status"] == "SUCCEEDED"
        assert cancel.json()["result"]["facts"] == EXPECTED["result"]["facts"]


def test_http_in_flight_worker_cancel_requires_exit(tmp_path):
    app = native_app(tmp_path)
    entered, release = threading.Event(), threading.Event()

    def hook(point, payload):
        if point == "worker:spawned":
            entered.set()
            assert release.wait(5)

    with TestClient(app) as client:
        app.state.dispatcher.tick()
        app.state.workers.fault_hook = hook
        prompt = client.post("/internal/native/prompt", json=native_prompt("hold"), headers=auth())
        assert prompt.status_code == 202, prompt.text
        run_id = prompt.json()["run_id"]
        app.state.dispatcher.tick()
        if app.state.store.get(fp_actor(), run_id).status == "QUEUED":
            app.state.store.claim_next(lambda owner: fp_actor() if owner == "synthetic-demo" else None)
        with ThreadPoolExecutor(1) as pool:
            running = pool.submit(
                client.post, "/internal/native/first-purchase",
                json={
                    "session_id": SESSION, "request_id": "hold", "call_id": "call-hold",
                    "request": EXPECTED["request"],
                },
                headers=runtime_headers(),
            )
            try:
                assert entered.wait(5)
                retry = client.post("/internal/native/first-purchase", json={
                    "session_id": SESSION, "request_id": "hold", "call_id": "call-hold",
                    "request": EXPECTED["request"],
                }, headers=runtime_headers())
                assert retry.status_code == 202, retry.text
                assert retry.json()["disposition"] == "IN_FLIGHT"
                assert retry.json()["run_id"] == run_id
                snap = client.get(f"{PREFIX}/runs/{run_id}", headers=auth()).json()
                cancelled = client.post(
                    f"{PREFIX}/runs/{run_id}/cancel", json={"reason": "USER_REQUEST"},
                    headers={**auth(), "idempotency-key": "cancel-hold", "if-match": str(snap["version"])},
                )
                assert cancelled.status_code == 200
                assert cancelled.json()["status"] in {"CANCELLING", "CANCELLED"}
                assert cancelled.json()["status"] != "SUCCEEDED" or cancelled.json()["diagnostics"]["execution_active"]
            finally:
                release.set()
            result = running.result(timeout=10)
        assert result.status_code in {200, 409}
        final = client.get(f"{PREFIX}/runs/{run_id}", headers=auth()).json()
        if result.status_code == 409:
            assert result.json()["error"]["code"] in {"RUN_CANCELLED", "TOOL_FAILED", "WORKER_ACTIVE", "CONFLICT"}
            assert final["status"] in {"CANCELLED", "CANCELLING", "FAILED"}
        records = app.state.store.worker_records(active_only=False)
        if records:
            assert records[0]["run_id"] == run_id


def test_native_missing_role_rejected_without_facts(tmp_path):
    app = native_app(tmp_path, MISSING)
    with TestClient(app) as client:
        app.state.dispatcher.tick()
        prompt = client.post("/internal/native/prompt", json=native_prompt("miss"), headers=auth())
        assert prompt.status_code == 202, prompt.text
        app.state.dispatcher.tick()
        run_id = prompt.json()["run_id"]
        if app.state.store.get(fp_actor(), run_id).status == "QUEUED":
            app.state.store.claim_next(lambda owner: fp_actor() if owner == "synthetic-demo" else None)
        response = client.post("/internal/native/first-purchase", json={
            "session_id": SESSION, "request_id": "miss", "call_id": "c",
            "request": MISSING_EXPECTED["request"],
        }, headers=runtime_headers())
        assert response.status_code == 200, response.text
        result = response.json()["result"]
        assert result["status"] == "REJECTED"
        assert result["facts"] is None
        dumped = json.dumps(result)
        assert "finished_conversion_ratio" not in dumped
        assert "finished_conversion_count" not in dumped


def test_new_process_reopens_native_binding(tmp_path):
    store = make_store(tmp_path / "state")
    _conv, accepted, _fixture = bind_native(store)
    root = Path(__file__).resolve().parents[2]
    code = """
import sys
from pathlib import Path
from backend.tests.analytics_run_support import profile
from backend.services.analytics.jobs import RunStore
from backend.tests.test_analytics_first_purchase_native import fp_actor, SESSION
store = RunStore(Path(sys.argv[1]), profile(), family="first_purchase")
work = store.runtime_work(session_id=SESSION, request_id="req-1")
assert len(work) == 1
print(work[0]["intent"].run_id)
"""
    proc = subprocess.run(
        [sys.executable, "-c", code, str(store.directory)],
        cwd=root, env={**os.environ, "PYTHONPATH": str(root)},
        capture_output=True, text=True, timeout=10,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == accepted.run_id


def test_succeeded_source_mismatch_copy_uses_first_purchase_ids(tmp_path):
    from backend.tests.test_analytics_first_purchase_analysis import asset_actor, succeed_first_purchase

    store, _runtime, run = succeed_first_purchase(tmp_path)
    codec = dict(store.codec.__dict__)
    codec["query_id"] = "other_query"
    store.codec = SimpleNamespace(**codec)
    with pytest.raises(AnalyticsError) as mismatch:
        store.succeeded_operating_source(asset_actor(), run.run_id)
    assert mismatch.value.status == 422
    assert mismatch.value.code == "UNPROCESSABLE"
    assert "other_query" in mismatch.value.message
    assert "first-purchase-path-query/v1" in mismatch.value.message
    assert "channel_first_observed_followup" not in mismatch.value.message


def test_native_success_save_cockpit_roundtrip_and_negatives(tmp_path):
    app = native_app(tmp_path, assets=True)
    with TestClient(app) as client:
        app.state.dispatcher.tick()
        prompt = client.post("/internal/native/prompt", json=native_prompt("save"), headers=auth())
        assert prompt.status_code == 202, prompt.text
        run_id = prompt.json()["run_id"]
        app.state.dispatcher.tick()
        if app.state.store.get(fp_actor(), run_id).status == "QUEUED":
            app.state.store.claim_next(lambda owner: fp_actor() if owner == "synthetic-demo" else None)
        executed = client.post("/internal/native/first-purchase", json={
            "session_id": SESSION, "request_id": "save", "call_id": "call-save",
            "request": EXPECTED["request"],
        }, headers=runtime_headers())
        assert executed.status_code == 200, executed.text
        assert executed.json()["result"]["query_id"] == "first_purchase_product_path"
        saved = client.post(
            PREFIX + "/analyses",
            json={"created_from_run_id": run_id, "title": "首购 N=30"},
            headers={**auth(), "idempotency-key": "save-run"},
        )
        assert saved.status_code == 201, saved.text
        analysis = saved.json()
        assert analysis["created_from_run_id"] == run_id
        assert analysis["query_ref"]["query_id"] == "first_purchase_product_path"
        assert "channel_first_observed_followup" not in json.dumps(analysis)
        analysis_id = analysis["analysis_id"]
        fetched = client.get(f"{PREFIX}/analyses/{analysis_id}", headers=auth())
        assert fetched.status_code == 200
        assert fetched.json()["snapshot"]["run_id"] == run_id
        replay = client.post(
            PREFIX + "/analyses",
            json={"created_from_run_id": run_id, "title": "首购 N=30"},
            headers={**auth(), "idempotency-key": "save-run"},
        )
        assert replay.status_code in {200, 201}
        assert replay.json()["analysis_id"] == analysis_id
        board = client.post(
            PREFIX + "/dashboards", json={"title": "我的首购驾驶舱"},
            headers={**auth(), "idempotency-key": "board-1"},
        )
        assert board.status_code in {200, 201}, board.text
        dashboard_id = board.json()["dashboard_id"]
        added = client.post(
            f"{PREFIX}/dashboards/{dashboard_id}/versions",
            json={"op": "add", "analysis_ref": {"analysis_id": analysis_id, "version": analysis["version"]}},
            headers={**auth(), "idempotency-key": "add-1", "if-match": str(board.json()["version"])},
        )
        assert added.status_code in {200, 201}, added.text
        reread = client.get(f"{PREFIX}/dashboards/{dashboard_id}", headers=auth())
        assert reread.status_code == 200
        payload = reread.json()
        assert payload["schema_version"] == "analytics-first-purchase-cockpit/v1"
        assert payload["cards"][0]["snapshot"]["run_id"] == run_id
        facts = payload["cards"][0]["facts"]
        assert facts["display_name"] == "首购商品路径 / N日正装转化"
        assert "channel_repeat_count" not in json.dumps(payload)
        rejected_root = tmp_path / "rejected"
        rejected_root.mkdir(mode=0o700)
        rejected_app = native_app(rejected_root, MISSING, assets=True)
        with TestClient(rejected_app) as rejected_client:
            rejected_app.state.dispatcher.tick()
            miss = rejected_client.post("/internal/native/prompt", json=native_prompt("rej"), headers=auth())
            miss_id = miss.json()["run_id"]
            if rejected_app.state.store.get(fp_actor(), miss_id).status == "QUEUED":
                rejected_app.state.store.claim_next(lambda owner: fp_actor() if owner == "synthetic-demo" else None)
            rejected_client.post("/internal/native/first-purchase", json={
                "session_id": SESSION, "request_id": "rej", "call_id": "c",
                "request": MISSING_EXPECTED["request"],
            }, headers=runtime_headers())
            denied = rejected_client.post(
                PREFIX + "/analyses",
                json={"created_from_run_id": miss_id, "title": "拒绝结果"},
                headers={**auth(), "idempotency-key": "save-rej"},
            )
            assert denied.status_code == 422
        queued = client.post("/internal/native/prompt", json=native_prompt("open"), headers=auth())
        open_id = queued.json()["run_id"]
        incomplete = client.post(
            PREFIX + "/analyses",
            json={"created_from_run_id": open_id, "title": "未完成"},
            headers={**auth(), "idempotency-key": "save-open"},
        )
        assert incomplete.status_code == 422
        facts_body = client.post(
            PREFIX + "/analyses",
            json={"created_from_run_id": run_id, "title": "伪造", "facts": EXPECTED["result"]["facts"]},
            headers={**auth(), "idempotency-key": "save-facts"},
        )
        assert facts_body.status_code == 422
