from __future__ import annotations

import os
import secrets

import pytest
from fastapi.testclient import TestClient


os.environ.setdefault("HEALTH_API_KEY", secrets.token_urlsafe(32))
os.environ["FQ_CRM_PASSWORDS"] = "testuser:testpass123"


@pytest.fixture
def client(monkeypatch_synthetic_ad_hoc_connection):
    from backend.routers import auth

    auth.VALID_CREDENTIALS = auth._load_credentials()
    auth._LOGIN_ATTEMPTS.clear()
    from backend.main import app

    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "testpass123"},
    )
    assert response.status_code == 200, f"login failed: {response.text}"
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_daily_gsv_via_synthetic_db(client, auth_headers) -> None:
    response = client.post(
        "/api/v1/ad-hoc/daily-gsv",
        headers=auth_headers,
        json={"start_date": "2026-06-15", "end_date": "2026-06-15"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["command"] == "daily-gsv"
    assert body["row_count"] >= 1
    assert body["rows"][0][0] == "2026-06-15"


def test_daily_gsv_multi_period_via_synthetic_db(client, auth_headers) -> None:
    response = client.post(
        "/api/v1/ad-hoc/daily-gsv-multi-period",
        headers=auth_headers,
        json={
            "periods": ["2026-06-15", "2026-06-15", "2025-06-15", "2025-06-15"],
            "metrics": [
                "sample_gmv",
                "sample_gsv",
                "member_gmv",
                "member_gsv",
                "new_users",
                "new_gsv",
                "old_users",
                "old_gsv",
            ],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["command"] == "daily-gsv-multi-period"
    assert body["headers"][2:] == [
        "sample_gmv",
        "sample_gsv",
        "member_gmv",
        "member_gsv",
        "new_users",
        "new_gsv",
        "old_users",
        "old_gsv",
    ]
    assert body["row_count"] >= 2


def test_yoy_battle_via_synthetic_db(client, auth_headers) -> None:
    response = client.post(
        "/api/v1/ad-hoc/yoy-battle",
        headers=auth_headers,
        json={
            "start_date": "2026-06-15",
            "end_date": "2026-06-15",
            "baseline_start": "2025-06-15",
            "baseline_end": "2025-06-15",
            "current_start": "2026-06-15",
            "current_end": "2026-06-15",
            "metric": "all",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["command"] == "yoy-battle"
    assert body["row_count"] == 4


def test_two_year_overview_via_synthetic_db(client, auth_headers) -> None:
    response = client.post(
        "/api/v1/ad-hoc/two-year-overview",
        headers=auth_headers,
        json={"year": 2026, "start": "2026-06-15", "end": "2026-06-15"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["command"] == "two-year-overview"
    assert "metric_key" in body["headers"]
    assert body["row_count"] >= 10


def test_dq_report_via_synthetic_db(client, auth_headers) -> None:
    response = client.post(
        "/api/v1/ad-hoc/dq-report",
        headers=auth_headers,
        json={"start_date": "2026-06-15", "end_date": "2026-06-15", "full": False},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["command"] == "dq-report"
    assert body["row_count"] == 5
