"""Sprint 196 fixed-product-list-compare regression tests."""
from __future__ import annotations

import os
import secrets
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient


os.environ.setdefault("HEALTH_API_KEY", secrets.token_urlsafe(32))
os.environ["FQ_CRM_PASSWORDS"] = "testuser:testpass123"

COSMETIC_ID = "803474428381"
MEDICAL_ID = "597655781410"
TAOKE_ID = "621639424901"
SYNTHETIC_IDS = [COSMETIC_ID, MEDICAL_ID, TAOKE_ID]
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def synthetic_client(monkeypatch_synthetic_ad_hoc_connection, monkeypatch, tmp_path):
    monkeypatch.setenv("FQ_TAKE_ROOT", str(tmp_path / "take_root"))
    from backend.routers import auth

    auth.VALID_CREDENTIALS = auth._load_credentials()
    auth._LOGIN_ATTEMPTS.clear()
    from backend.main import app

    return TestClient(app)


@pytest.fixture
def synthetic_auth_headers(synthetic_client):
    response = synthetic_client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "testpass123"},
    )
    assert response.status_code == 200, f"login failed: {response.text}"
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _ttl_row(rows: list[list[Any]], label: str) -> list[Any]:
    return next(row for row in rows if row[1] == "TTL" and row[2] == label)


def _service_ttl(result: dict[str, Any]) -> dict[str, Any]:
    return next(row for row in result["channel_all"] if row["channel"] == "TTL")


class TestSprint196FixedProductListCompare:
    def test_rows_match_archived_formula_on_synthetic_data(self, monkeypatch_synthetic_ad_hoc_connection) -> None:
        from scripts.ad_hoc_queries.fixed_product_list_compare import (
            CATEGORY_GROUPS,
            PRODUCT_IDS,
            run_fixed_product_list_compare,
        )

        rows = run_fixed_product_list_compare(
            start_date="2026-06-15",
            end_date="2026-06-15",
            product_ids=SYNTHETIC_IDS,
            mom_start_date="2025-06-15",
            mom_end_date="2025-06-15",
        )

        assert PRODUCT_IDS[:3] == [
            "803474428381",
            "870597889980",
            "683395365107",
        ]
        assert set(CATEGORY_GROUPS) == {"妆品销售TTL", "械品销售TTL", "淘客品销售TTL"}
        assert len(rows) == 6
        cosmetic_ttl = _ttl_row(rows, "妆品销售TTL")
        taoke_ttl = _ttl_row(rows, "淘客品销售TTL")
        assert cosmetic_ttl[3:9] == [1, 100.0, 100.0, 0, 0.0, 0.0]
        assert cosmetic_ttl[10] == 25.0
        assert taoke_ttl[3:9] == [0, 0.0, 0.0, 1, 50.0, 50.0]
        assert taoke_ttl[13] == 25.0

        help_result = subprocess.run(
            [sys.executable, "scripts/ad_hoc_query.py", "fixed-product-list-compare", "--help"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(PROJECT_ROOT),
            env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        )
        assert help_result.returncode == 0, help_result.stderr[:500]
        assert "--start-date" in help_result.stdout


class TestSprint196AskRouterRegression:
    def test_fixed_product_routes_with_100_percent_accuracy(self) -> None:
        from scripts.ad_hoc_queries.ask import route_ask

        scenarios = [
            "按固定清单单品对比 2026 H1",
            "固定产品新老客拆一下",
            "产品清单两年对比",
            "商品清单按单品输出",
            "单品对比要用固定清单",
        ]
        hits = 0
        for text in scenarios:
            command, params = route_ask(text)
            hits += int(command == "fixed-product-list-compare")
            assert params["start_date"] <= params["end_date"]
        assert hits == len(scenarios), f"Sprint 196 routing accuracy {hits}/{len(scenarios)}"


class TestSprint196EdgeCases:
    def test_empty_product_list_and_reversed_dates_fail(self, synthetic_client, synthetic_auth_headers) -> None:
        from scripts.ad_hoc_queries.fixed_product_list_compare import run_fixed_product_list_compare

        with pytest.raises(ValueError, match="产品清单不能为空"):
            run_fixed_product_list_compare(
                start_date="2026-06-15",
                end_date="2026-06-15",
                product_ids=[],
            )

        response = synthetic_client.post(
            "/api/v1/ad-hoc/fixed-product-list-compare",
            headers=synthetic_auth_headers,
            json={"start_date": "2026-06-30", "end_date": "2026-06-01"},
        )
        assert response.status_code == 422


class TestSprint196BackendServiceSSOT:
    def test_audience_summary_product_ids_filter_uses_service_ssot(self, monkeypatch_synthetic_ad_hoc_connection) -> None:
        from backend.services.metrics.audience_summary import calculate_audience_summary

        filtered = calculate_audience_summary(
            year=2026,
            metric_type="GSV",
            start_date="2026-06-15",
            end_date="2026-06-15",
            product_ids=[COSMETIC_ID],
        )
        unfiltered = calculate_audience_summary(
            year=2026,
            metric_type="GSV",
            start_date="2026-06-15",
            end_date="2026-06-15",
        )

        assert _service_ttl(filtered)["old_gsv_2026"] == 100.0
        assert _service_ttl(filtered)["new_gsv_2026"] == 0.0
        assert _service_ttl(unfiltered)["gsv_2026"] == 350.0


class TestSprint196Synthetic:
    def test_http_endpoint_runs_on_synthetic_duckdb(self, synthetic_client, synthetic_auth_headers) -> None:
        response = synthetic_client.post(
            "/api/v1/ad-hoc/fixed-product-list-compare",
            headers=synthetic_auth_headers,
            json={
                "start_date": "2026-06-15",
                "end_date": "2026-06-15",
                "product_ids": SYNTHETIC_IDS,
                "mom_start_date": "2025-06-15",
                "mom_end_date": "2025-06-15",
            },
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["command"] == "fixed-product-list-compare"
        assert body["row_count"] == 6
        assert len(body["headers"]) == 33
        assert body["rows"][0][0] == "妆品销售TTL"
