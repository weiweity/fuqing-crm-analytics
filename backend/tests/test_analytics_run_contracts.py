"""In-process HTTP and offline schema checks; never bind a network listener."""

import json
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.analytics_app import PREFIX, create_app
from backend.contracts.analytics import (
    AnalyticsB0Facts, AnalyticsB0Result, AnalyticsCancelRequest,
)
from backend.services.analytics.access import B0IdentityRegistry
from backend.tests.analytics_run_support import (
    REPO_ROOT, actor, child_environment, conversation, make_store, observation, sqlite_connection, successful_step,
)

TOKEN = "b0-tests-only-not-a-live-secret-0001"


@pytest.fixture
def api(tmp_path):
    store = make_store(tmp_path / "state")
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, actor())
    ready = [True]
    app = create_app(store, registry, runtime_ready=lambda: ready[0], stream_window_seconds=0.08)
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        yield client, store, registry, ready


def submit(client):
    conv = client.post(PREFIX + "/conversations", headers={"Idempotency-Key": "conversation"}, json={})
    assert conv.status_code == 201
    url = f"{PREFIX}/conversations/{conv.json()['conversation_id']}/runs"
    response = client.post(url, headers={"Idempotency-Key": "run"}, json={"question": "查看合成渠道"})
    assert response.status_code == 202
    return url, response


def test_http_original_202_survives_runtime_offline_and_terminal_state(api):
    client, store, _, ready = api
    url, accepted = submit(client)
    intent = store.claim_next(actor)
    step = successful_step(store, intent)
    store.observe(actor(), observation(intent, "SUCCEEDED", primary=step.step_id))
    ready[0] = False
    replay = client.post(url, headers={"Idempotency-Key": "run"}, json={"question": " 查看合成渠道 ", "condition_patch": None})
    assert replay.status_code == 202 and replay.content == accepted.content
    assert replay.headers["location"] == accepted.headers["location"]
    snapshot = client.get(replay.headers["location"])
    assert snapshot.json()["status"] == "SUCCEEDED"
    assert int(snapshot.headers["etag"]) > replay.json()["version"]
    blocked = client.post(url, headers={"Idempotency-Key": "new"}, json={"question": "查看合成渠道"})
    assert blocked.status_code == 503 and blocked.json()["error"]["code"] == "RUNTIME_NOT_CONNECTED"
    with sqlite_connection(store.path) as con:
        assert con.execute("SELECT count(*) FROM runs").fetchone()[0] == 1


@pytest.mark.parametrize("phase", ["QUEUED", "RUNNING", "SUCCEEDED"])
def test_lost_http_202_at_actual_asgi_response_boundary_replays_original(tmp_path, phase):
    store = make_store(tmp_path / "state")
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, actor())
    app = create_app(store, registry, runtime_ready=lambda: True)
    dropped = {}

    async def drop_first_accepted_response(scope, receive, send):
        async def send_or_drop(message):
            if message["type"] == "http.response.start" and message["status"] == 202 and not dropped:
                dropped["headers"] = dict(message["headers"])
                dropped["armed"] = True
            if message["type"] == "http.response.body" and dropped.get("armed"):
                dropped["content"] = message["body"]
                dropped["armed"] = False
                raise ConnectionResetError("owned test drops committed 202 before delivery")
            await send(message)

        await app(scope, receive, send_or_drop)

    with TestClient(drop_first_accepted_response, headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        conv = client.post(PREFIX + "/conversations", headers={"Idempotency-Key": "conv"}, json={})
        url = f"{PREFIX}/conversations/{conv.json()['conversation_id']}/runs"
        with pytest.raises(ConnectionResetError):
            client.post(url, headers={"Idempotency-Key": "lost-202"}, json={"question": "查看合成渠道"})
        accepted = json.loads(dropped["content"])
        with sqlite_connection(store.path) as con:
            assert json.loads(con.execute("SELECT original_202 FROM runs").fetchone()[0]) == accepted
        if phase != "QUEUED":
            intent = store.claim_next(actor)
            if phase == "SUCCEEDED":
                step = successful_step(store, intent)
                store.observe(actor(), observation(intent, "SUCCEEDED", primary=step.step_id))
        replay = client.post(url, headers={"Idempotency-Key": "lost-202"}, json={"question": "查看合成渠道"})
        assert replay.status_code == 202 and replay.content == dropped["content"]
        assert replay.headers["location"].encode() == dropped["headers"][b"location"]
        snapshot = client.get(replay.headers["location"])
        assert snapshot.json()["status"] == phase
        assert snapshot.json()["run_id"] == accepted["run_id"]
        with sqlite_connection(store.path) as con:
            assert con.execute("SELECT count(*) FROM runs").fetchone()[0] == 1
            assert con.execute("SELECT count(*) FROM dispatch_intents").fetchone()[0] == 1
            assert con.execute("SELECT attempts FROM dispatch_intents").fetchone()[0] == int(phase != "QUEUED")


def test_factory_defaults_refuse_execution_even_with_valid_identity(tmp_path):
    store = make_store(tmp_path / "state")
    conv = conversation(store)
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, actor())
    with TestClient(create_app(store, registry)) as client:
        response = client.post(f"{PREFIX}/conversations/{conv.conversation_id}/runs", json={"question": "test"},
                               headers={"Authorization": f"Bearer {TOKEN}", "Idempotency-Key": "run"})
    assert response.status_code == 503
    assert store.get_conversation(actor(), conv.conversation_id).run_ids == []


def test_identity_spoof_headers_are_not_authentication(api):
    client, store, _, _ = api
    conv = conversation(store)
    client.headers.pop("authorization")
    response = client.get(f"{PREFIX}/conversations/{conv.conversation_id}",
                          headers={"X-Actor-ID": "alice", "X-Role": "admin"})
    assert response.status_code == 401


def test_cancel_requires_key_and_current_version_and_replay_is_stable(api):
    client, _, _, _ = api
    _, accepted = submit(client)
    url = accepted.headers["location"] + "/cancel"
    assert client.post(url, json={}).status_code == 428
    assert client.post(url, json={}, headers={"Idempotency-Key": "cancel"}).status_code == 428
    cancelled = client.post(url, json={}, headers={"Idempotency-Key": "cancel", "If-Match": "1"})
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "CANCELLED"
    assert client.post(url, json={}, headers={"Idempotency-Key": "cancel", "If-Match": "1"}).content == cancelled.content
    stale = client.post(url, json={}, headers={"Idempotency-Key": "different", "If-Match": "1"})
    assert stale.status_code == 409
    with sqlite_connection(api[1].path) as con:
        assert con.execute("SELECT count(*) FROM dispatch_intents WHERE attempts>0").fetchone()[0] == 0


@pytest.mark.parametrize("patch", [
    {"question": ""}, {"question": "  "}, {"question": "bad\u0000question"},
    {"question": "q", "condition_patch": {}}, {"question": "q", "actor_id": "bob"},
    {"question": "q", "sql": "SELECT private_information"}, {"question": "q", "schema_version": "future/v99"},
])
def test_http_rejects_unsupported_fields_without_reflecting_input(api, patch):
    client, store, _, _ = api
    conv = conversation(store)
    response = client.post(f"{PREFIX}/conversations/{conv.conversation_id}/runs", json=patch,
                           headers={"Idempotency-Key": "invalid"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert "private_information" not in response.text and "future/v99" not in response.text
    assert store.get_conversation(actor(), conv.conversation_id).run_ids == []


def test_body_and_duplicate_control_header_limits(api):
    client, _, _, _ = api
    response = client.post(PREFIX + "/conversations", content=b"x" * 65537)
    assert response.status_code == 413
    response = client.post(PREFIX + "/conversations", json={},
                           headers=[("Idempotency-Key", "a"), ("Idempotency-Key", "b")])
    assert response.status_code == 400


def test_full_queue_returns_retryable_error_but_same_request_can_recover(api):
    client, _, _, _ = api
    url, first = submit(client)
    for key in ("second", "third"):
        assert client.post(url, json={"question": "查看合成渠道"}, headers={"Idempotency-Key": key}).status_code == 202
    full = client.post(url, json={"question": "查看合成渠道"}, headers={"Idempotency-Key": "fourth"})
    assert full.status_code == 429 and full.headers["retry-after"] == "1"
    assert full.json()["error"]["retryable"] is True
    assert client.post(url, json={"question": "查看合成渠道"}, headers={"Idempotency-Key": "run"}).content == first.content


def test_conflicting_event_cursors_are_not_silently_overridden(api):
    client, _, _, _ = api
    _, accepted = submit(client)
    run = accepted.json()["run_id"]
    response = client.get(accepted.headers["location"] + "/events", params={"after": f"{run}:1"},
                          headers={"Last-Event-ID": f"{run}:0"})
    assert response.status_code == 422 and response.json()["error"]["code"] == "EVENT_CURSOR_CONFLICT"


def parse_events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def test_sse_replay_is_monotonic_and_does_not_resubmit(api):
    client, store, _, _ = api
    _, accepted = submit(client)
    run_id = accepted.json()["run_id"]
    store.cancel(actor(), run_id, "cancel", 1, AnalyticsCancelRequest())
    before = store.get(actor(), run_id)
    url = accepted.headers["location"] + "/events"
    response = client.get(url)
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_events(response)
    assert [event["sequence"] for event in events] == [1, 2]
    replay = client.get(url, headers={"Last-Event-ID": events[0]["event_id"]})
    assert parse_events(replay) == events[1:]
    assert parse_events(client.get(url, headers={"Last-Event-ID": events[-1]["event_id"]})) == []
    assert store.get(actor(), run_id) == before
    assert before.diagnostics.dispatch_attempts == 0


@pytest.mark.parametrize("cursor", ["wrong:1", "{run}:999", "{run}:-1", "{run}:01"])
def test_invalid_event_cursor_is_rejected_before_streaming(api, cursor):
    client, _, _, _ = api
    _, accepted = submit(client)
    response = client.get(accepted.headers["location"] + "/events",
                          headers={"Last-Event-ID": cursor.format(run=accepted.json()["run_id"])})
    assert response.status_code == 422 and "application/json" in response.headers["content-type"]


def test_expired_cursor_returns_410_snapshot_recovery(api):
    client, store, _, _ = api
    _, accepted = submit(client)
    run_id = accepted.json()["run_id"]
    store.cancel(actor(), run_id, "cancel", 1, AnalyticsCancelRequest())
    with sqlite_connection(store.path) as con:
        # Test-only expiration injection in a small disposable ledger. The
        # implementation does not prune user events or idempotency records.
        con.execute("DELETE FROM events WHERE run_id=? AND sequence=1", (run_id,))
    response = client.get(accepted.headers["location"] + "/events")
    assert response.status_code == 410
    assert response.json()["error"]["recovery_url"] == accepted.headers["location"]
    assert parse_events(client.get(accepted.headers["location"] + "/events",
                                  headers={"Last-Event-ID": f"{run_id}:1"}))[0]["sequence"] == 2


def test_schema_contains_only_real_routes_controls_and_event_contract():
    schema = create_app().openapi()
    assert len(schema["paths"]) == 6
    assert schema["security"] == [{"B0Bearer": []}]
    assert "AnalyticsRunEvent" in schema["components"]["schemas"]
    assert schema["components"]["schemas"]["AnalyticsB0Facts"]["properties"]["repeat_ratio"]["const"] == 0.25
    cancel = schema["paths"][PREFIX + "/runs/{run_id}/cancel"]["post"]
    headers = {p["name"] for p in cancel["parameters"] if p["in"] == "header" and p["required"]}
    assert headers == {"Idempotency-Key", "If-Match"}
    stream = schema["paths"][PREFIX + "/runs/{run_id}/events"]["get"]["responses"]["200"]
    assert set(stream["content"]) == {"text/event-stream"}
    assert "dashboards" not in json.dumps(schema) and "refresh-runs" not in json.dumps(schema)


@pytest.mark.parametrize("bad", [
    {"customers": 101}, {"customers": 100.0}, {"repeat_customers": "25"},
    {"repeat_ratio": "0.25"}, {"repeat_ratio": 0.5}, {"repeat_ratio": float("nan")},
])
def test_model_cannot_supply_alternative_fixture_facts(bad):
    with pytest.raises(ValidationError):
        AnalyticsB0Facts(**bad)


@pytest.mark.parametrize("flag", [True, 0, "false"])
def test_synthetic_flag_is_strict(flag):
    with pytest.raises(ValidationError):
        AnalyticsB0Result(facts=AnalyticsB0Facts(), contains_real_data=flag)


def test_clean_import_and_openapi_cannot_touch_legacy_config_or_real_database(tmp_path):
    script = """
import importlib.abc, json, sys
class DenyLegacy(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {'backend.config', 'backend.routers', 'backend.main', 'backend.db', 'duckdb', 'dotenv'}:
            raise AssertionError('legacy import forbidden: ' + fullname)
sys.meta_path.insert(0, DenyLegacy())
def no_external_effect(event, args):
    if event in {'sqlite3.connect', 'socket.connect', 'subprocess.Popen'}:
        raise AssertionError('offline contract opened external state')
    if event == 'open' and isinstance(args[0], str) and (args[0].endswith('.env') or args[0].endswith('.duckdb')):
        raise AssertionError('private state access forbidden')
sys.addaudithook(no_external_effect)
from backend.analytics_app import create_app
schema = create_app().openapi()
print(json.dumps({'path_count': len(schema['paths']), 'status': 'OFFLINE_ONLY'}))
"""
    env = {**child_environment(), "DUCKDB_PATH": str(tmp_path / "must-not-open.duckdb"),
           "ANALYTICS_WORKERS": "999", "ANALYTICS_MEMORY_LIMIT": "999TB"}
    result = subprocess.run([sys.executable, "-c", script], cwd=REPO_ROOT, env=env,
                            capture_output=True, text=True, timeout=15, check=True)
    assert json.loads(result.stdout) == {"path_count": 6, "status": "OFFLINE_ONLY"}
    assert list(tmp_path.iterdir()) == []
