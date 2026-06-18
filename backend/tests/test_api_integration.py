"""
Tests for backend API endpoints - FastAPI integration tests.

Covers:
- GET /api/v1/metrics/overview: core metrics API
- GET /api/v1/metrics/trend: trend data
- GET /api/v1/audience/table: audience table
- GET /api/v1/geo/distribution: geographic distribution
- GET /api/v1/category/distribution: category distribution
- GET /api/v1/churn/distribution: churn distribution
- GET /api/v1/flow/matrix: RFM flow matrix
- GET /api/v1/customer-health/*: customer health endpoints

NOTE: These tests require:
  1. HEALTH_API_KEY environment variable (required by the app at import time)
  2. FQ_CRM_PASSWORDS environment variable (required by the app at import time)
  3. A running DuckDB database with data (for data-dependent tests)
"""
import pytest
import os
import secrets
from pathlib import Path

# Ensure HEALTH_API_KEY & FQ_CRM_PASSWORDS are set before importing backend.main
if "HEALTH_API_KEY" not in os.environ:
    os.environ["HEALTH_API_KEY"] = secrets.token_urlsafe(32)
if "FQ_CRM_PASSWORDS" not in os.environ:
    os.environ["FQ_CRM_PASSWORDS"] = "testuser:testpass123"

# Check if database exists before running integration tests
# Sprint 22 #31: 默认名 sample.duckdb 改 fuqing_crm.duckdb (跟 backend/config.py 一致 + 真实生产文件)
DB_PATH = os.environ.get(
    "FUQING_DB_PATH",
    str(Path(__file__).parent.parent.parent / "data" / "processed" / "fuqing_crm.duckdb"),
)
DB_EXISTS = Path(DB_PATH).exists()


# Sprint 22.5 #S22.5-1: TestClient 跟生产 uvicorn 共享 DuckDB 锁冲突 (跟 #25 同根因).
# dev 跑测试前先停 uvicorn (锁 release), 或公开后用户 clone 跑 (无 uvicorn = 0 锁).
# 简化: module-level skipif — uvicorn 在就整文件 skip, 跟 conftest.py skip_if_duckdb_locked 配套.
import os as _os
import subprocess as _sp
_PROD_DUCKDB = Path(__file__).parent.parent.parent / "data" / "processed" / "fuqing_crm.duckdb"
_UVICORN_LOCK_PID = (
    int(_sp.run(["lsof", "-t", str(_PROD_DUCKDB)], capture_output=True, text=True, timeout=5).stdout.strip().split()[0])
    if _PROD_DUCKDB.exists() and _sp.run(["lsof", "-t", str(_PROD_DUCKDB)], capture_output=True, text=True, timeout=5).stdout.strip()
    else None
)
# Sprint 36-5 race flake 治标: pytest-xdist 多 worker 跨进程也撞 DuckDB file lock.
# 旧 skipif 只拦 uvicorn PID, 不拦 pytest-xdist worker 之间互锁. 加 worker count 探测
# → 多 worker 时整 module skip, 提示用 `pytest -n0` serial mode 跑.
# Sprint 39 CI 爆红修复: CI 跑 serial mode + production DuckDB 不存在 → 真连空 DuckDB
# → CatalogException fail. 加 _PROD_DUCKDB_AVAILABLE check (CI 没数据时整 module skip).
from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE  # noqa: E402
_XDIST_WORKER_COUNT = _os.environ.get("PYTEST_XDIST_WORKER_COUNT")
_IN_XDIST_PARALLEL = _XDIST_WORKER_COUNT is not None and int(_XDIST_WORKER_COUNT) > 1
pytestmark = pytest.mark.skipif(
    not _PROD_DUCKDB_AVAILABLE
    or (_UVICORN_LOCK_PID is not None and _UVICORN_LOCK_PID != _os.getpid())
    or _IN_XDIST_PARALLEL,
    reason=(
        (
            "生产 DuckDB 不可用 (CI / fresh checkout / data/processed/ 缺文件). "
            "本地真跑: 先 ETL 跑批生成 data/processed/fuqing_crm.duckdb. "
        )
        if not _PROD_DUCKDB_AVAILABLE
        else ""
    )
    + (
        "生产 DuckDB lock 冲突: "
        + (
            f"PID {_UVICORN_LOCK_PID} 占 fd (uvicorn 或 xdist worker), TestClient 跨进程锁冲突. "
            if _UVICORN_LOCK_PID is not None and _UVICORN_LOCK_PID != _os.getpid()
            else ""
        )
        + (
            f"pytest-xdist 多 worker ({_XDIST_WORKER_COUNT}) 跑 race flake. "
            f"用 `pytest backend/tests/test_api_integration.py -n0` serial mode 跑 = 0 冲突. "
            f"真治本留 Sprint 36.x (per-test tmp DuckDB ATTACH 模式)."
            if _IN_XDIST_PARALLEL
            else ""
        )
    ),
)


def get_test_client():
    """Create a FastAPI TestClient (lazy import to avoid module-level errors)."""
    from fastapi.testclient import TestClient
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def client():
    """FastAPI test client fixture."""
    return get_test_client()


@pytest.fixture
def api_key(client):
    """Bearer token for auth_middleware (Sprint 17+ 全局).

    Sprint 22.5 #S22.5-1 修: 原 fixture 返 X-API-Key (给 health router 内部用),
    但 main.py:124 auth_middleware 强制 Authorization: Bearer {token}, 7 个 integration
    test 一律 401. 改走 /api/v1/auth/login 拿真实 token (FQ_CRM_PASSWORDS=testuser:testpass123,
    见 module-level os.environ 设值).
    """
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "testpass123"},
    )
    assert resp.status_code == 200, f"login 失败: {resp.status_code} {resp.text}"
    return resp.json()["token"]


def _auth_headers(token: str) -> dict:
    """Bearer token header, 跟 auth_middleware (main.py:137) 协议一致."""
    return {"Authorization": f"Bearer {token}"}


# ── Smoke tests (always run) ──────────────────────────────────


class TestAppStartup:
    """Test that the app can be imported and configured."""

    def test_app_has_routes(self):
        """App should have registered routes."""
        from backend.main import app
        routes = [r.path for r in app.routes]
        assert len(routes) > 0

    def test_openapi_schema_exists(self):
        """App should generate OpenAPI schema."""
        from backend.main import app
        schema = app.openapi()
        assert "paths" in schema
        assert len(schema["paths"]) > 0


# ── Integration tests (require database) ──────────────────────


@pytest.mark.skipif(not DB_EXISTS, reason="Database not found")
class TestMetricsAPI:
    """Test metrics overview API with real data."""

    def test_overview_returns_200(self, client, api_key):
        response = client.get(
            "/api/v1/metrics/overview",
            headers=_auth_headers(api_key),
        )
        assert response.status_code == 200

    def test_overview_has_required_keys(self, client, api_key):
        response = client.get(
            "/api/v1/metrics/overview",
            headers=_auth_headers(api_key),
        )
        data = response.json()
        # Should contain at least some metric keys
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_trend_returns_200(self, client, api_key):
        response = client.get(
            "/api/v1/metrics/trend",
            headers=_auth_headers(api_key),
        )
        assert response.status_code == 200


@pytest.mark.skipif(not DB_EXISTS, reason="Database not found")
class TestAudienceAPI:
    """Test audience endpoints."""

    def test_audience_table(self, client, api_key):
        response = client.get(
            "/api/v1/audience/table",
            headers=_auth_headers(api_key),
        )
        assert response.status_code == 200


@pytest.mark.skipif(not DB_EXISTS, reason="Database not found")
class TestGeoAPI:
    """Test geographic distribution API."""

    def test_geo_distribution(self, client, api_key):
        response = client.get(
            "/api/v1/geo/distribution",
            headers=_auth_headers(api_key),
        )
        assert response.status_code == 200


@pytest.mark.skipif(not DB_EXISTS, reason="Database not found")
class TestCategoryAPI:
    """Test category distribution API."""

    def test_category_distribution(self, client, api_key):
        response = client.get(
            "/api/v1/category/distribution",
            headers=_auth_headers(api_key),
        )
        assert response.status_code == 200


@pytest.mark.skipif(not DB_EXISTS, reason="Database not found")
class TestFlowAPI:
    """Test RFM flow matrix API."""

    def test_flow_matrix(self, client, api_key):
        # Sprint 22.5 #S22.5-1: /api/v1/flow/matrix 必填 from_date + to_date (Query)
        response = client.get(
            "/api/v1/flow/matrix",
            params={"from_date": "2026-05-13", "to_date": "2026-06-12"},
            headers=_auth_headers(api_key),
        )
        assert response.status_code == 200


@pytest.mark.skipif(not DB_EXISTS, reason="Database not found")
class TestCustomerHealthAPI:
    """Test customer health endpoints."""

    def test_health_overview(self, client, api_key):
        # Sprint 22.5 #S22.5-1: /api/v1/customer-health/overview 必填 analysis_date (Query)
        response = client.get(
            "/api/v1/customer-health/overview",
            params={"analysis_date": "2026-06-12"},
            headers=_auth_headers(api_key),
        )
        assert response.status_code == 200
