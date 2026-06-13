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
def api_key():
    """API key for authentication."""
    return os.environ.get("HEALTH_API_KEY", "test-key")


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
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200

    def test_overview_has_required_keys(self, client, api_key):
        response = client.get(
            "/api/v1/metrics/overview",
            headers={"X-API-Key": api_key},
        )
        data = response.json()
        # Should contain at least some metric keys
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_trend_returns_200(self, client, api_key):
        response = client.get(
            "/api/v1/metrics/trend",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200


@pytest.mark.skipif(not DB_EXISTS, reason="Database not found")
class TestAudienceAPI:
    """Test audience endpoints."""

    def test_audience_table(self, client, api_key):
        response = client.get(
            "/api/v1/audience/table",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200


@pytest.mark.skipif(not DB_EXISTS, reason="Database not found")
class TestGeoAPI:
    """Test geographic distribution API."""

    def test_geo_distribution(self, client, api_key):
        response = client.get(
            "/api/v1/geo/distribution",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200


@pytest.mark.skipif(not DB_EXISTS, reason="Database not found")
class TestCategoryAPI:
    """Test category distribution API."""

    def test_category_distribution(self, client, api_key):
        response = client.get(
            "/api/v1/category/distribution",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200


@pytest.mark.skipif(not DB_EXISTS, reason="Database not found")
class TestFlowAPI:
    """Test RFM flow matrix API."""

    def test_flow_matrix(self, client, api_key):
        response = client.get(
            "/api/v1/flow/matrix",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200


@pytest.mark.skipif(not DB_EXISTS, reason="Database not found")
class TestCustomerHealthAPI:
    """Test customer health endpoints."""

    def test_health_overview(self, client, api_key):
        response = client.get(
            "/api/v1/customer-health/overview",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
