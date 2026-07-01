"""
test_ad_hoc_query_api.py — Sprint 188 即席查询 HTTP API 集成测试.

Scope: backend/routers/ad_hoc_query.py 9 endpoint 各 1 case ≥ 200 + dq-report 校验错误返回 422.

合规:
- L4.3 真连 DuckDB 测试用 monkeypatch_connection fixture (Sprint 53 治本)
- L4.4 真连 DuckDB 测试必须 _PROD_DUCKDB_AVAILABLE skipif (Sprint 39 治本)
- L4.41 subprocess PYTHONPATH 绝对路径 (本测试不启动子进程, 走 uvicorn 主进程 TestClient)
- L4.36 禁停 uvicorn: TestClient 不依赖 uvicorn 守护进程, 也不杀 uvicorn

配套 fixtures:
- monkeypatch_connection (Sprint 53): 每个 xdist worker 用 temp DuckDB + ATTACH production read_only
- HEALTH_API_KEY + FQ_CRM_PASSWORDS env 已 os.environ.setdefault 设值 (test file 顶部强制)
"""
from __future__ import annotations

import os
import secrets

import pytest
from fastapi.testclient import TestClient

# --- 强制 test credentials (跟 test_api_integration.py 同模式, 避免 .env 抢值) ---
os.environ.setdefault("HEALTH_API_KEY", secrets.token_urlsafe(32))
os.environ.setdefault("FQ_CRM_PASSWORDS", "testuser:testpass123")

# --- L4.4 Sprint 39: 真连 DuckDB 测试必须 _PROD_DUCKDB_AVAILABLE skipif ---
from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE  # noqa: E402

pytestmark = pytest.mark.skipif(
    not _PROD_DUCKDB_AVAILABLE,
    reason="production DuckDB 不可用 (CI runner 无 100GB data 文件)",
)


# --- Sprint 53 跨 worker 隔离 fixture ---
@pytest.fixture
def client(monkeypatch_connection):
    """FastAPI TestClient — 复用 monkeypatch_connection fixture (per-worker temp DB)."""
    from backend.main import app  # 延迟 import, 让 conftest fixtures 先注入

    return TestClient(app)


@pytest.fixture
def auth_token(client):
    """调 /api/v1/auth/login 拿 Bearer token (跟 main.py auth_middleware 配套)."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "testpass123"},
    )
    assert response.status_code == 200, f"login failed: {response.text}"
    return response.json()["token"]


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


# ─────────────────────────────────────────────────────────────
# 9 endpoint × 1 case ≥ 200
# Sprint 188 任务要求: 9 endpoint 各 1 case + dq-report 校验错误返回
# ─────────────────────────────────────────────────────────────


def test_daily_gsv_ok(client, auth_headers) -> None:
    """POST /api/v1/ad-hoc/daily-gsv — 起始+结束日期有效时返 ≥200."""
    response = client.post(
        "/api/v1/ad-hoc/daily-gsv",
        headers=auth_headers,
        json={"start_date": "2026-06-01", "end_date": "2026-06-21"},
    )
    assert response.status_code == 200, f"expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert body["command"] == "daily-gsv"
    assert body["headers"] == ["date", "gsv", "customers", "yoy_pct"]
    assert isinstance(body["rows"], list)
    assert body["row_count"] == len(body["rows"])


def test_yoy_battle_ok(client, auth_headers) -> None:
    """POST /api/v1/ad-hoc/yoy-battle — baseline + current 双窗口."""
    response = client.post(
        "/api/v1/ad-hoc/yoy-battle",
        headers=auth_headers,
        json={
            "baseline_start": "2025-06-01",
            "baseline_end": "2025-06-21",
            "current_start": "2026-06-01",
            "current_end": "2026-06-21",
            "metric": "all",
        },
    )
    assert response.status_code == 200, f"expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert body["command"] == "yoy-battle"
    assert body["headers"] == ["metric", "baseline_value", "current_value", "abs_diff", "yoy_pct"]
    assert isinstance(body["rows"], list)


def test_channel_slice_ok(client, auth_headers) -> None:
    """POST /api/v1/ad-hoc/channel-slice — 单日 channel 切片."""
    response = client.post(
        "/api/v1/ad-hoc/channel-slice",
        headers=auth_headers,
        json={"date": "2026-06-21", "channel": "all", "compare": "yoy"},
    )
    assert response.status_code == 200, f"expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert body["command"] == "channel-slice"
    assert body["headers"] == ["channel", "gsv", "orders", "customers", "aov", "yoy_pct"]
    assert isinstance(body["rows"], list)


def test_two_year_overview_ok(client, auth_headers) -> None:
    """POST /api/v1/ad-hoc/two-year-overview — 两年新老客 30 指标对比."""
    response = client.post(
        "/api/v1/ad-hoc/two-year-overview",
        headers=auth_headers,
        json={"year": 2026, "start": "2026-06-01", "end": "2026-06-21"},
    )
    assert response.status_code == 200, f"expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert body["command"] == "two-year-overview"
    assert isinstance(body["rows"], list)
    assert "metric_key" in body["headers"]


def test_new_old_customer_ok(client, auth_headers) -> None:
    """POST /api/v1/ad-hoc/new-old-customer — 新老客拆分, 字段前缀隔离."""
    response = client.post(
        "/api/v1/ad-hoc/new-old-customer",
        headers=auth_headers,
        json={
            "start_date": "2026-06-01",
            "end_date": "2026-06-21",
            "dimension": "channel",
        },
    )
    assert response.status_code == 200, f"expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert body["command"] == "new-old-customer"
    # L4.25 防串台字段: headers 必须含明确前缀, 不允许裸 gsv/users/aus
    headers_str = ",".join(body["headers"])
    assert any(p in headers_str for p in ("new_", "old_", "all_", "member_")), \
        f"new_old 必须有字段前缀隔离, got headers={body['headers']}"


def test_rfm_repurchase_ok(client, auth_headers) -> None:
    """POST /api/v1/ad-hoc/rfm-repurchase — R 区间复购周期分布."""
    response = client.post(
        "/api/v1/ad-hoc/rfm-repurchase",
        headers=auth_headers,
        json={
            "start_date": "2026-06-01",
            "end_date": "2026-06-21",
            "year": 2026,
        },
    )
    assert response.status_code == 200, f"expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert body["command"] == "rfm-repurchase"
    assert isinstance(body["rows"], list)
    # R 6 桶 SSOT (Sprint 170) 头列含 r_seg_
    headers_str = ",".join(body["headers"])
    assert "r_seg_" in headers_str, f"rfm 必须有 r_seg_ 前缀, got headers={body['headers']}"


def test_top_n_ok(client, auth_headers) -> None:
    """POST /api/v1/ad-hoc/top-n — TOP N 品类/产品层级."""
    response = client.post(
        "/api/v1/ad-hoc/top-n",
        headers=auth_headers,
        json={
            "start_date": "2026-06-01",
            "end_date": "2026-06-21",
            "dimension": "spu_category",
            "limit": 20,
        },
    )
    assert response.status_code == 200, f"expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert body["command"] == "top-n"
    assert isinstance(body["rows"], list)


def test_export_excel_ok(client, auth_headers) -> None:
    """POST /api/v1/ad-hoc/export-excel — 返 StreamingResponse 二进制流."""
    response = client.post(
        "/api/v1/ad-hoc/export-excel",
        headers=auth_headers,
        json={"start_date": "2026-06-01", "end_date": "2026-06-21", "year": 2026},
    )
    # StreamingResponse 200 + content-type: vnd.openxmlformats
    assert response.status_code == 200, f"expected 200, got {response.status_code}: {response.text[:200]}"
    assert "openxmlformats" in response.headers.get("content-type", ""), \
        f"expected xlsx content-type, got {response.headers.get('content-type')}"
    binary = response.content
    # xlsx 是 zip 容器, magic bytes 是 PK\x03\x04
    assert binary[:4] == b"PK\x03\x04", f"expected xlsx zip magic, got {binary[:8]!r}"


# ─────────────────────────────────────────────────────────────
# dq-report 校验错误返回 (Sprint 188 任务明确要求)
# ─────────────────────────────────────────────────────────────


def test_dq_report_ok(client, auth_headers) -> None:
    """POST /api/v1/ad-hoc/dq-report — 5 项规则报告 ≥200."""
    response = client.post(
        "/api/v1/ad-hoc/dq-report",
        headers=auth_headers,
        json={"start_date": "2026-06-01", "end_date": "2026-06-21", "full": False},
    )
    assert response.status_code == 200, f"expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert body["command"] == "dq-report"
    assert isinstance(body["rows"], list)


def test_dq_report_invalid_date_returns_422(client, auth_headers) -> None:
    """start_date > end_date → 422 校验错返 (跟 _validate_date_range 配套)."""
    response = client.post(
        "/api/v1/ad-hoc/dq-report",
        headers=auth_headers,
        json={"start_date": "2026-06-30", "end_date": "2026-06-01"},  # start > end
    )
    assert response.status_code == 422, f"expected 422 invalid date, got {response.status_code}"
    # FastAPI 422 标准格式: detail 是 list
    assert "detail" in response.json()


def test_dq_report_bad_date_format_returns_422(client, auth_headers) -> None:
    """日期格式错 → 422 (跟 date.fromisoformat 配套)."""
    response = client.post(
        "/api/v1/ad-hoc/dq-report",
        headers=auth_headers,
        json={"start_date": "not-a-date", "end_date": "2026-06-21"},
    )
    assert response.status_code == 422


# ─────────────────────────────────────────────────────────────
# Auth 覆盖: 没 token → 401 (跟 main.py auth_middleware 配套)
# ─────────────────────────────────────────────────────────────


def test_daily_gsv_requires_auth(client) -> None:
    """未带 Bearer token → 401 (跟 main.py auth_middleware 配套)."""
    response = client.post(
        "/api/v1/ad-hoc/daily-gsv",
        json={"start_date": "2026-06-01", "end_date": "2026-06-21"},
    )
    assert response.status_code == 401
