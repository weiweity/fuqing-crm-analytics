"""L4.85.4 account handoff security and lifecycle regression tests."""
from __future__ import annotations

from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import threading
import time

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.routers import auth as auth_module
from backend.routers import login_request as login_request_module


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_auth_state():
    auth_module.ACTIVE_TOKENS.clear()
    auth_module._LOGIN_ATTEMPTS.clear()
    login_request_module._reset_l4_85_state()
    yield
    auth_module.ACTIVE_TOKENS.clear()
    auth_module._LOGIN_ATTEMPTS.clear()
    login_request_module._reset_l4_85_state()


def _apply() -> tuple[str, str]:
    response = client.post(
        "/api/v1/auth/login-request",
        json={"username": "admin", "password": "123456"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return body["request_id"], body["claim_token"]


def _claim_headers(claim_token: str) -> dict[str, str]:
    return {"X-Login-Claim": claim_token}


def test_login_request_reuses_shared_five_minute_activity_rule():
    auth_module.ACTIVE_TOKENS["stale-admin-token"] = (
        "admin",
        datetime.now() - timedelta(minutes=10),
    )
    response = client.post(
        "/api/v1/auth/login-request",
        json={"username": "admin", "password": "123456"},
    )
    assert response.status_code == 409
    assert login_request_module._PENDING_REQUESTS == {}


def test_request_id_visible_to_a_cannot_claim_b_session():
    auth_module.ACTIVE_TOKENS["admin-token-a"] = ("admin", datetime.now())
    request_id, claim_token = _apply()
    approved = client.post(
        f"/api/v1/auth/login-request/{request_id}/approve",
        headers={"Authorization": "Bearer admin-token-a"},
    )
    assert approved.status_code == 200
    assert auth_module.ACTIVE_TOKENS == {}

    assert client.post(f"/api/v1/auth/login-request/{request_id}/claim").status_code == 404
    assert client.post(
        f"/api/v1/auth/login-request/{request_id}/claim",
        headers=_claim_headers(request_id),
    ).status_code == 404

    claimed = client.post(
        f"/api/v1/auth/login-request/{request_id}/claim",
        headers=_claim_headers(claim_token),
    )
    assert claimed.status_code == 200
    assert list(auth_module.ACTIVE_TOKENS) == [claimed.json()["token"]]


def test_approved_but_never_claimed_creates_no_ghost_and_is_evicted():
    auth_module.ACTIVE_TOKENS["admin-token-a"] = ("admin", datetime.now())
    request_id, _ = _apply()
    approved = client.post(
        f"/api/v1/auth/login-request/{request_id}/approve",
        headers={"Authorization": "Bearer admin-token-a"},
    )
    assert approved.status_code == 200
    assert auth_module.ACTIVE_TOKENS == {}

    target = login_request_module._PENDING_REQUESTS["admin"][0]
    target.resolved_at = time.monotonic() - login_request_module.LOGIN_REQUEST_TIMEOUT_SECONDS - 1
    with login_request_module._STATE_LOCK:
        login_request_module._evict_expired_requests_locked(time.monotonic())
    assert login_request_module._PENDING_REQUESTS == {}
    assert request_id not in login_request_module._PENDING_REQUEST_OWNERS
    assert auth_module.ACTIVE_TOKENS == {}


def test_login_and_login_request_share_account_lockout():
    auth_module.ACTIVE_TOKENS["admin-token-a"] = ("admin", datetime.now())
    for _ in range(auth_module.MAX_FAIL_ATTEMPTS - 1):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrong"},
        )
        assert response.status_code == 401

    fifth = client.post(
        "/api/v1/auth/login-request",
        json={"username": "admin", "password": "wrong"},
    )
    locked = client.post(
        "/api/v1/auth/login-request",
        json={"username": "admin", "password": "123456"},
    )
    assert fifth.status_code == 401
    assert locked.status_code == 429


def test_same_ip_retry_rotates_claim_and_refreshes_authoritative_ttl():
    auth_module.ACTIVE_TOKENS["admin-token-a"] = ("admin", datetime.now())
    request_id, first_claim = _apply()
    target = login_request_module._PENDING_REQUESTS["admin"][0]
    target.created_at = (
        time.monotonic() - login_request_module.LOGIN_REQUEST_TIMEOUT_SECONDS + 1
    )

    retried = client.post(
        "/api/v1/auth/login-request",
        json={"username": "admin", "password": "123456"},
    )
    assert retried.status_code == 200
    body = retried.json()
    assert body["request_id"] == request_id
    assert body["claim_token"] != first_claim
    assert time.monotonic() - target.created_at < 1
    assert client.get(
        f"/api/v1/auth/login-request/{request_id}/status",
        headers=_claim_headers(first_claim),
    ).status_code == 404
    assert client.get(
        f"/api/v1/auth/login-request/{request_id}/status",
        headers=_claim_headers(body["claim_token"]),
    ).status_code == 200


def test_concurrent_direct_logins_mint_only_one_active_session(monkeypatch):
    """The single-session decision must stay atomic across FastAPI workers."""
    rendezvous = threading.Barrier(2)

    def synchronized_credentials(*_args):
        rendezvous.wait(timeout=2)

    monkeypatch.setattr(auth_module, "_authenticate_credentials", synchronized_credentials)

    def attempt_login() -> int:
        with TestClient(app) as isolated_client:
            return isolated_client.post(
                "/api/v1/auth/login",
                json={"username": "admin", "password": "unused"},
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = sorted(executor.map(lambda _: attempt_login(), range(2)))

    assert statuses == [200, 409]
    assert len(auth_module.ACTIVE_TOKENS) == 1


def test_claimed_session_logout_leaves_no_ghost_account():
    auth_module.ACTIVE_TOKENS["admin-token-a"] = ("admin", datetime.now())
    request_id, claim_token = _apply()
    client.post(
        f"/api/v1/auth/login-request/{request_id}/approve",
        headers={"Authorization": "Bearer admin-token-a"},
    )
    claimed = client.post(
        f"/api/v1/auth/login-request/{request_id}/claim",
        headers=_claim_headers(claim_token),
    )
    transferred_token = claimed.json()["token"]

    logout = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {transferred_token}"},
    )
    assert logout.status_code == 200
    assert auth_module.ACTIVE_TOKENS == {}
    assert client.post(
        f"/api/v1/auth/login-request/{request_id}/claim",
        headers=_claim_headers(claim_token),
    ).status_code == 410


def test_claim_header_is_allowed_by_cors_preflight():
    response = client.options(
        "/api/v1/auth/login-request/request-1/status",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-login-claim",
        },
    )
    assert response.status_code == 200
    assert "x-login-claim" in response.headers["access-control-allow-headers"].lower()
