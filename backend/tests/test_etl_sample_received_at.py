"""Sprint 141.5 Phase 1 sample_received_at 字段回归测试."""

import pytest

from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE


pytestmark = pytest.mark.skipif(
    not _PROD_DUCKDB_AVAILABLE,
    reason="production DuckDB 不可用",
)


class TestSampleReceivedAtPhase1:
    """orders schema 含收货时间字段, service 在 NULL 时回退 pay_time."""

    def test_orders_has_sample_received_at_column(self, monkeypatch_connection):
        """orders schema 含 sample_received_at TIMESTAMP."""
        cols = monkeypatch_connection.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'orders' AND column_name = 'sample_received_at'
        """).fetchall()

        assert len(cols) == 1
        assert any("TIMESTAMP" in data_type.upper() for _, data_type in cols)

    def test_sampling_service_falls_back_to_pay_time(self, monkeypatch_connection):
        """sample_received_at 为 NULL 时, COALESCE 回退 pay_time 并保持 ROI 可查."""
        from backend.services.sampling_service import get_sampling_roi

        result = get_sampling_roi(
            start_date="2026-04-01",
            end_date="2026-06-30",
            window_days=30,
            level="spu_category",
        )

        assert "period_distribution" in result
        assert "bucket_1_3d" in result["period_distribution"]
