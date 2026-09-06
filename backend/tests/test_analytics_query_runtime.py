"""Query-family ASGI/native helper. Browser/Gateway/cards are NOT RUN."""

from __future__ import annotations

import os
from copy import deepcopy

from fastapi.testclient import TestClient

from backend.analytics_query_fixture import create_channel_followup_fixture
from backend.analytics_runtime import runtime_app
from backend.contracts.analytics_query import ChannelFollowupResult
from backend.contracts.analytics_query_run import QUERY_RECEIPT_SCHEMA, QUERY_RUN_SCHEMA
from backend.services.analytics.access import AnalyticsPrincipal
from backend.services.analytics.jobs import ExecutionObservation
from backend.services.analytics.resource_profile import content_hash
from backend.tests.analytics_run_support import actor, make_store, synthetic_fixture
from backend.tests.test_analytics_native_runtime import Receiver
from backend.tests.test_analytics_query_jobs import (
    DIGEST, VALID_REQUEST, golden_snapshot, query_native, query_request,
)
from backend.tests.test_analytics_query_worker import assert_facts_match_hand_golden, private_dir

SESSIONS = ("session-query-a", "session-query-b")
GATEWAY = "g" * 40
RUNTIME = "r" * 40


def runtime_actor():
    return AnalyticsPrincipal(
        "b0-synthetic-owner",
        frozenset({"run:create", "run:read", "run:cancel"}),
        frozenset({"channel-followup-fixture"}),
    )


def query_config(tmp_path):
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    os.chmod(state, 0o700)
    fixture = create_channel_followup_fixture(private_dir(tmp_path / "fixture"), golden_snapshot())
    return {
        "family": "channel_followup",
        "state_dir": str(state),
        "session_ids": list(SESSIONS),
        "gateway_token": GATEWAY,
        "runtime_token": RUNTIME,
        "method_package_digest": DIGEST,
        "fixture": {"directory": fixture.directory, "manifest_sha256": fixture.manifest_sha256},
    }


def gateway(session):
    return {"authorization": f"Bearer {GATEWAY}", "x-runtime-session-id": session}


def runtime():
    return {"authorization": f"Bearer {RUNTIME}"}


def followup_body(session, request_id, call_id, days=30):
    return {
        "session_id": session, "request_id": request_id, "call_id": call_id,
        "request": query_request(days).model_dump(mode="json"),
    }


def setup_query_app(tmp_path):
    app = runtime_app(query_config(tmp_path), bridge=Receiver())
    app.state.dispatcher.ready = True
    return app


def accept_and_claim(client, app, session, key, text="查看合成渠道后续购买"):
    accepted = client.post("/internal/native/prompt", json=query_native(session, key, text),
                           headers={"authorization": f"Bearer {GATEWAY}"})
    assert accepted.status_code == 202, accepted.text
    intent = app.state.store.claim_next(lambda owner: runtime_actor() if owner == "b0-synthetic-owner" else None)
    assert intent is not None and intent.session_id == session and intent.request_id == key
    return accepted.json(), intent


def test_two_registered_sessions_and_negative_auth_bounds(tmp_path):
    app = setup_query_app(tmp_path)
    client = TestClient(app)
    try:
        paths = app.openapi()["paths"]
        assert "/api/v1/analytics/runs/{run_id}" not in paths
        assert not any(path.startswith("/internal") for path in paths)
        first = client.post("/internal/native/prompt", json=query_native(SESSIONS[0], "a-1"),
                            headers={"authorization": f"Bearer {GATEWAY}"})
        second = client.post("/internal/native/prompt", json=query_native(SESSIONS[1], "b-1"),
                             headers={"authorization": f"Bearer {GATEWAY}"})
        assert first.status_code == 202 and second.status_code == 202
        assert first.json()["run_id"] != second.json()["run_id"]
        a_ctx = client.get("/internal/native/context", headers=gateway(SESSIONS[0])).json()
        b_ctx = client.get("/internal/native/context", headers=gateway(SESSIONS[1])).json()
        assert a_ctx["session_id"] == SESSIONS[0] and b_ctx["session_id"] == SESSIONS[1]
        assert first.json()["run_id"] in a_ctx["conversation"]["run_ids"]
        assert first.json()["run_id"] not in b_ctx["conversation"]["run_ids"]
        run_a = client.get(f"/api/v1/analytics-query/runs/{first.json()['run_id']}", headers=gateway(SESSIONS[0]))
        assert run_a.status_code == 200 and run_a.json()["schema_version"] == QUERY_RUN_SCHEMA
        assert run_a.headers["cache-control"] == "no-store"
        assert client.get(f"/api/v1/analytics-query/runs/{first.json()['run_id']}", headers=gateway(SESSIONS[1])).status_code == 404
        assert client.get(f"/api/v1/analytics-query/runs/{first.json()['run_id']}",
                          headers=gateway("session-query-c")).status_code == 404
        assert client.post("/internal/native/prompt", json=query_native("session-query-c", "c-1"),
                           headers={"authorization": f"Bearer {GATEWAY}"}).status_code == 404
        assert client.get(f"/api/v1/analytics-query/runs/{first.json()['run_id']}",
                          headers={"x-runtime-session-id": SESSIONS[0]}).status_code == 401
        assert client.get(
            f"/api/v1/analytics-query/runs/{first.json()['run_id']}",
            headers=[("authorization", f"Bearer {GATEWAY}"), ("authorization", f"Bearer {GATEWAY}"),
                     ("x-runtime-session-id", SESSIONS[0])],
        ).status_code == 400
        huge = {"reason": "USER_REQUEST", "pad": "x" * 70000}
        assert client.post(f"/api/v1/analytics-query/runs/{first.json()['run_id']}/cancel", json=huge,
                           headers={**gateway(SESSIONS[0]), "idempotency-key": "cancel", "if-match": "1"}).status_code == 413
        app.state.registry.grant("n" * 40, AnalyticsPrincipal(
            "b0-synthetic-owner", frozenset({"run:create", "run:read", "run:cancel"}), frozenset({"b0-fixture"}),
        ))
        noscope = {"authorization": f"Bearer {'n' * 40}", "x-runtime-session-id": SESSIONS[0]}
        assert client.get(f"/api/v1/analytics-query/runs/{first.json()['run_id']}", headers=noscope).status_code == 403
        assert client.get("/api/v1/analytics/runs/" + first.json()["run_id"], headers=gateway(SESSIONS[0])).status_code == 404
        assert client.post("/internal/native/fixture", json={"session_id": SESSIONS[0], "request_id": "a-1",
                                                            "call_id": "tool", "query": "channel_repeat_rate"},
                           headers=runtime()).status_code == 404
    finally:
        client.close()


def test_native_replay_and_context_modes_and_revoke(tmp_path):
    app = setup_query_app(tmp_path)
    client = TestClient(app)
    try:
        first = client.post("/internal/native/prompt", json=query_native(SESSIONS[0], "native-1"),
                            headers={"authorization": f"Bearer {GATEWAY}"})
        replay = client.post("/internal/native/prompt", json=query_native(SESSIONS[0], "native-1"),
                             headers={"authorization": f"Bearer {GATEWAY}"})
        assert first.status_code == replay.status_code == 202
        assert first.json() == replay.json()
        drifted = client.post("/internal/native/prompt",
                              json=query_native(SESSIONS[0], "native-1", timezone="UTC"),
                              headers={"authorization": f"Bearer {GATEWAY}"})
        assert drifted.status_code == 409
        intent = app.state.store.claim_next(lambda owner: runtime_actor() if owner == "b0-synthetic-owner" else None)
        awaiting = client.post("/internal/native/run-context", json={
            "session_id": SESSIONS[0], "request_id": "native-1", "unit_id": "model:1:1",
            "package_digest": DIGEST,
        }, headers=runtime()).json()
        assert awaiting["conditions"]["mode"] == "AWAITING_REGISTERED_QUERY"
        assert awaiting["schema_version"] == "analytics-channel-followup-runtime-context/v1"
        app.state.store.reserve_step(runtime_actor(), intent.run_id, intent.attempt_id, "tool-1", request=query_request(30))
        registered = client.post("/internal/native/run-context", json={
            "session_id": SESSIONS[0], "request_id": "native-1", "unit_id": "model:1:2",
            "package_digest": DIGEST,
        }, headers=runtime()).json()
        assert registered["conditions"]["mode"] == "REGISTERED_QUERY"
        assert registered["conditions"]["request"]["observation_days"] == 30
        replay_budget = client.post("/internal/native/run-context", json={
            "session_id": SESSIONS[0], "request_id": "native-1", "unit_id": "model:1:1",
            "package_digest": DIGEST,
        }, headers=runtime()).json()
        assert replay_budget["remaining_budget"]["model_steps"] == registered["remaining_budget"]["model_steps"]
        app.state.registry.revoke(GATEWAY)
        assert client.post("/internal/native/prompt", json=query_native(SESSIONS[0], "native-2"),
                           headers={"authorization": f"Bearer {GATEWAY}"}).status_code == 401
        assert client.post("/internal/native/run-context", json={
            "session_id": SESSIONS[0], "request_id": "native-1", "unit_id": "model:1:3",
            "package_digest": DIGEST, "resource": "SKILL.md",
        }, headers=runtime()).status_code == 403
        assert client.post("/internal/native/channel-followup",
                           json=followup_body(SESSIONS[0], "native-1", "tool-2"),
                           headers=runtime()).status_code == 403
    finally:
        client.close()


def test_native_helper_real_worker_n30_n60_pending_and_reuse(tmp_path):
    app = setup_query_app(tmp_path)
    client = TestClient(app)
    store = app.state.store
    try:
        _, intent_a = accept_and_claim(client, app, SESSIONS[0], "n30")
        executed = client.post("/internal/native/channel-followup",
                               json=followup_body(SESSIONS[0], "n30", "call-n30", 30), headers=runtime())
        assert executed.status_code == 200, executed.text
        receipt_a = executed.json()
        assert receipt_a["schema_version"] == QUERY_RECEIPT_SCHEMA
        assert receipt_a["disposition"] == "EXECUTE"
        assert receipt_a["run_id"] == intent_a.run_id
        result_a = ChannelFollowupResult.model_validate(receipt_a["result"])
        assert_facts_match_hand_golden(result_a, 30)
        assert result_a.resolved_filters.permission_scope == content_hash(
            {"actor_id": "b0-synthetic-owner", "data_scope": "channel-followup-fixture"},
        )
        reused = client.post("/internal/native/channel-followup",
                             json=followup_body(SESSIONS[0], "n30", "call-n30", 30), headers=runtime())
        assert reused.status_code == 200
        assert reused.json()["disposition"] == "REUSE_RESULT"
        assert reused.json()["step_id"] == receipt_a["step_id"]
        assert reused.json()["result"] == receipt_a["result"]
        store.observe(runtime_actor(), ExecutionObservation(
            intent_a.run_id, intent_a.attempt_id, intent_a.session_id, intent_a.request_id,
            True, "SUCCEEDED", receipt_a["step_id"],
        ))
        _, intent_b = accept_and_claim(client, app, SESSIONS[1], "n60")
        executed_b = client.post("/internal/native/channel-followup",
                                 json=followup_body(SESSIONS[1], "n60", "call-n60", 60), headers=runtime())
        assert executed_b.status_code == 200, executed_b.text
        receipt_b = executed_b.json()
        assert receipt_b["run_id"] != receipt_a["run_id"]
        assert receipt_b["step_id"] != receipt_a["step_id"]
        result_b = ChannelFollowupResult.model_validate(receipt_b["result"])
        assert_facts_match_hand_golden(result_b, 60)
        assert content_hash(receipt_a["result"]) != content_hash(receipt_b["result"])
        reserved = store.reserve_step(
            runtime_actor(), intent_b.run_id, intent_b.attempt_id, "call-pending", request=query_request(60),
        )
        assert reserved.disposition == "EXECUTE"
        pending = client.post("/internal/native/channel-followup",
                              json=followup_body(SESSIONS[1], "n60", "call-pending", 60), headers=runtime())
        assert pending.status_code == 409
        assert pending.json()["error"]["code"] == "STEP_PENDING"
        workers = store.worker_records(active_only=False)
        assert sum(1 for row in workers if row["step_id"] == reserved.step_id) == 0
        invalid = deepcopy(VALID_REQUEST)
        invalid["sql"] = "SELECT private_information"
        assert client.post("/internal/native/channel-followup", json={
            "session_id": SESSIONS[1], "request_id": "n60", "call_id": "bad", "request": invalid,
        }, headers=runtime()).status_code == 422
        unknown = deepcopy(VALID_REQUEST)
        unknown["query_version"] = "channel-followup-query/v0"
        assert client.post("/internal/native/channel-followup", json={
            "session_id": SESSIONS[1], "request_id": "n60", "call_id": "bad2", "request": unknown,
        }, headers=runtime()).status_code == 422
    finally:
        client.close()


def test_b0_runtime_does_not_mount_query_helper(tmp_path):
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    config = {"state_dir": str(state), "session_id": "native-session", "gateway_token": GATEWAY,
              "runtime_token": RUNTIME, "fixture": __import__("dataclasses").asdict(synthetic_fixture(tmp_path / "fixture"))}
    app = runtime_app(config, bridge=Receiver())
    client = TestClient(app)
    try:
        assert client.post("/internal/native/channel-followup", json=followup_body("native-session", "x", "y"),
                           headers=runtime()).status_code == 404
        assert make_store(tmp_path / "b0").family == "b0"
        assert actor().data_scopes == frozenset({"b0-fixture"})
    finally:
        client.close()
