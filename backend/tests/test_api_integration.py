"""
Tests for backend API endpoints - FastAPI integration tests.

Covers:
- GET /api/v1/metrics/overview: core metrics API
- GET /api/v1/metrics/trend: trend data
- GET /api/v1/audience/table: audience table
- GET /api/v1/geo/distribution: geographic distribution
- GET /api/v1/category/distribution: category distribution
- GET /api/v1/flow/matrix: RFM flow matrix
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

# Force test credentials — must override .env's FQ_CRM_PASSWORDS (load_dotenv in auth.py
# reads .env before this module runs; setdefault would NOT override the .env value).
os.environ["HEALTH_API_KEY"] = os.environ.get("HEALTH_API_KEY") or secrets.token_urlsafe(32)
os.environ["FQ_CRM_PASSWORDS"] = "testuser:testpass123"

# Check if database exists before running integration tests
# Sprint 22 #31: 默认名 sample.duckdb 改 fuqing_crm.duckdb (跟 backend/config.py 一致 + 真实生产文件)
DB_PATH = os.environ.get(
    "FUQING_DB_PATH",
    str(Path(__file__).parent.parent.parent / "data" / "processed" / "fuqing_crm.duckdb"),
)
DB_EXISTS = Path(DB_PATH).exists()


# Sprint 53: 每个 xdist worker 使用 temp DuckDB + ATTACH production read_only，
# 不再因生产库文件锁跳过并行测试。CI 无生产数据时仍保持 skip。
from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE  # noqa: E402
pytestmark = [
    pytest.mark.skipif(
        not _PROD_DUCKDB_AVAILABLE,
        reason="生产 DuckDB 不可用 (CI / fresh checkout / data/processed/ 缺文件)",
    ),
]


@pytest.fixture(autouse=True)
def _use_isolated_db(monkeypatch_connection):
    """所有 API 测试使用当前 worker 的隔离 DuckDB。"""


def get_test_client():
    """Create a FastAPI TestClient (lazy import to avoid module-level errors)."""
    from fastapi.testclient import TestClient
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def client(monkeypatch_connection):
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
