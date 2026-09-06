from pathlib import Path

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.local_demo_access import allows_local_demo
from backend.tests.test_missions_api import synthetic_db  # generated fixture, never private data


@pytest.fixture
def local_client(monkeypatch, tmp_path: Path, synthetic_db: Path):
    for name, value in {
        "FQ_LOCAL_DEMO_NO_LOGIN": "1",
        "FQ_MISSION_DEMO_ENABLED": "1",
        "FQ_MISSION_DEMO_RESET_ENABLED": "1",
        "FQ_SYNTHETIC_DB_PATH": str(synthetic_db),
        "FQ_MISSION_CONTROL_DB": str(tmp_path / "control.sqlite3"),
        "FQ_MISSION_EXPORT_DIR": str(tmp_path / "exports"),
    }.items():
        monkeypatch.setenv(name, value)
    # No lifespan: do not start legacy CRM database/worker services.
    return TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 12345))


def test_anonymous_synthetic_chain_and_real_api_isolation(local_client):
    client = local_client
    access = client.get("/api/v1/missions/access")
    assert access.status_code == 200
    assert access.json()["local_demo_no_login"] is True
    assert access.headers["cache-control"] == "no-store"
    for endpoint in ["/api/v1/core/summary", "/api/v1/auth/me", "/api/v1/missions-evil/today"]:
        assert client.get(endpoint).status_code == 401
    today = client.get("/api/v1/missions/today")
    assert today.status_code == 200
    mission = today.json()
    assert mission["data_provenance"]["contains_real_data"] is False
    assert client.post("/api/v1/missions/diagnose", json={"question": "哪个渠道粘性最强？"}).status_code == 200
    path = f"/api/v1/missions/{mission['mission_id']}"
    headers = {"If-Match": "1", "Idempotency-Key": "demo-approve"}
    assert client.post(path + "/audience-export", headers=headers).status_code == 409
    assert client.post(path + "/approve", json={"decision": "APPROVE"}).status_code == 428
    approved = client.post(path + "/approve", headers=headers, json={"decision": "APPROVE"})
    assert approved.status_code == 200
    assert approved.json()["approval"]["approved_by"] == "LOCAL_SYNTHETIC_DEMO"
    exported = client.post(path + "/audience-export", headers={"If-Match": "2", "Idempotency-Key": "demo-export"})
    assert exported.status_code == 200
    assert client.get(exported.json()["download_url"]).status_code == 200
    assert client.post(path + "/demo-reset", headers={"If-Match": "3", "Idempotency-Key": "demo-reset"}).status_code == 200


@pytest.mark.parametrize("flag", ["FQ_LOCAL_DEMO_NO_LOGIN", "FQ_MISSION_DEMO_ENABLED"])
def test_demo_requires_both_explicit_flags(local_client, monkeypatch, flag):
    monkeypatch.delenv(flag)
    assert local_client.get("/api/v1/missions/access").json()["local_demo_no_login"] is False
    assert local_client.get("/api/v1/missions/today").status_code == 401


@pytest.mark.parametrize("headers", [
    {"Host": "public.example"},
    {"Origin": "https://evil.example"},
    {"Origin": "null"},
    {"Sec-Fetch-Site": "cross-site"},
    {"X-Forwarded-For": "203.0.113.1"},
    {"X-Forwarded-For": "127.0.0.1, 203.0.113.1"},
    {"X-Forwarded-Host": "public.example"},
    {"Forwarded": "for=203.0.113.1"},
])
def test_untrusted_browser_and_proxy_requests_cannot_bypass_auth(local_client, headers):
    assert local_client.get("/api/v1/missions/today", headers=headers).status_code == 401


def test_local_vite_proxy_is_allowed(local_client):
    headers = {"Origin": "http://localhost:5173", "X-Forwarded-For": "::1", "X-Forwarded-Host": "localhost:5173"}
    assert local_client.get("/api/v1/missions/today", headers=headers).status_code == 200


def test_remote_peer_denied_even_with_local_host(local_client):
    request = Request({"type": "http", "path": "/api/v1/missions/today", "client": ("192.168.1.50", 12345), "headers": [(b"host", b"localhost:8000")]})
    assert not allows_local_demo(request)


def test_invalid_synthetic_source_never_grants_demo_access(local_client, monkeypatch, tmp_path):
    monkeypatch.setenv("FQ_SYNTHETIC_DB_PATH", str(tmp_path / "missing.duckdb"))
    assert local_client.get("/api/v1/missions/access").status_code == 503
    assert local_client.get("/api/v1/missions/today").status_code == 503


def test_demo_lifespan_never_opens_legacy_database(local_client, monkeypatch):
    def forbidden():
        pytest.fail("local synthetic demo must not validate the private CRM database")
    monkeypatch.setattr("backend.main.validate_startup_db", forbidden)
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 12345)) as client:
        assert client.get("/api/v1/missions/today").status_code == 200
