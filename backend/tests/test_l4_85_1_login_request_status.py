"""L4.85.1 secure status + claim handoff regression tests."""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.routers import auth as auth_module
from backend.routers import login_request as lr_module


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    auth_module.ACTIVE_TOKENS.clear()
    auth_module._LOGIN_ATTEMPTS.clear()
    lr_module._reset_l4_85_state()
    yield
    auth_module.ACTIVE_TOKENS.clear()
    auth_module._LOGIN_ATTEMPTS.clear()
    lr_module._reset_l4_85_state()


def _create_request() -> tuple[str, str]:
    auth_module.ACTIVE_TOKENS["admin-token-1"] = ("admin", datetime.now())
    response = client.post(
        "/api/v1/auth/login-request",
        json={"username": "admin", "password": "123456"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return body["request_id"], body["claim_token"]


def _claim_headers(claim_token: str) -> dict[str, str]:
    return {"X-Login-Claim": claim_token}


def test_get_request_status_pending_is_idempotent():
    request_id, claim_token = _create_request()

    first = client.get(
        f"/api/v1/auth/login-request/{request_id}/status",
        headers=_claim_headers(claim_token),
    )
    second = client.get(
        f"/api/v1/auth/login-request/{request_id}/status",
        headers=_claim_headers(claim_token),
    )

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["status"] == "pending"


def test_approved_status_then_claim_returns_one_retryable_token():
    request_id, claim_token = _create_request()
    approved = client.post(
        f"/api/v1/auth/login-request/{request_id}/approve",
        headers={"Authorization": "Bearer admin-token-1"},
    )
    assert approved.status_code == 200
    assert "token" not in approved.text
    assert auth_module.ACTIVE_TOKENS == {}

    status = client.get(
        f"/api/v1/auth/login-request/{request_id}/status",
        headers=_claim_headers(claim_token),
    )
    assert status.json() == {
        "request_id": request_id,
        "status": "approved",
        "username": "admin",
    }

    first_claim = client.post(
        f"/api/v1/auth/login-request/{request_id}/claim",
        headers=_claim_headers(claim_token),
    )
    second_claim = client.post(
        f"/api/v1/auth/login-request/{request_id}/claim",
        headers=_claim_headers(claim_token),
    )
    assert first_claim.status_code == second_claim.status_code == 200
    assert first_claim.json() == second_claim.json()
    assert first_claim.headers["cache-control"] == "no-store"
    assert list(auth_module.ACTIVE_TOKENS) == [first_claim.json()["token"]]


def test_rejected_status_requires_claim_secret():
    request_id, claim_token = _create_request()
    rejected = client.post(
        f"/api/v1/auth/login-request/{request_id}/reject",
        headers={"Authorization": "Bearer admin-token-1"},
    )
    assert rejected.status_code == 200

    missing = client.get(f"/api/v1/auth/login-request/{request_id}/status")
    wrong = client.get(
        f"/api/v1/auth/login-request/{request_id}/status",
        headers=_claim_headers("wrong-claim-token"),
    )
    valid = client.get(
        f"/api/v1/auth/login-request/{request_id}/status",
        headers=_claim_headers(claim_token),
    )
    assert missing.status_code == wrong.status_code == 404
    assert valid.status_code == 200
    assert valid.json()["status"] == "rejected"


def test_invalid_request_id_returns_404_without_auth_side_effects():
    response = client.get(
        "/api/v1/auth/login-request/non-existent/status",
        headers=_claim_headers("unused-secret"),
    )
    assert response.status_code == 404
