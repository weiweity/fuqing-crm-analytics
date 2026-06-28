"""Sprint 142 RFM 扩展分群回归测试."""

import pytest

from backend.services.rfm.extended import get_user_rfm_extended
from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE


pytestmark = pytest.mark.skipif(
    not _PROD_DUCKDB_AVAILABLE,
    reason="production DuckDB 不可用",
)


def _reset_orders(conn):
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE orders (
            order_id VARCHAR,
            sub_order_id VARCHAR,
            user_id VARCHAR,
            channel VARCHAR,
            pay_time TIMESTAMP,
            sample_received_at TIMESTAMP,
            spu_category VARCHAR,
            spu_tier VARCHAR,
            spu_product_class VARCHAR,
            spu_product_subclass VARCHAR,
            spu_cosmetic VARCHAR,
            spu_type VARCHAR,
            actual_amount DOUBLE,
            is_refund BOOLEAN,
            order_status VARCHAR
        )
    """)


def _insert_order(conn, order_id, user_id, pay_time, amount):
    conn.execute(
        """
        INSERT INTO orders VALUES (
            ?, NULL, ?, '货架', ?::TIMESTAMP, NULL,
            '胶原膜', '核心品', '面膜', '涂抹面膜', '修护', '正装',
            ?, FALSE, '交易成功'
        )
        """,
        [order_id, user_id, pay_time, amount],
    )


@pytest.fixture
def rfm_orders(monkeypatch_connection):
    _reset_orders(monkeypatch_connection)
    try:
        yield monkeypatch_connection
    finally:
        monkeypatch_connection.execute("DROP TABLE IF EXISTS orders")


class TestRFMExtended:
    """Sprint 142: lifecycle_stage + value_tier + potential_tier."""

    def test_lifecycle_classification_basic(self, rfm_orders):
        """lifecycle_stage 4 桶分类正确."""
        _insert_order(rfm_orders, "n1", "u_new", "2026-06-20", 100)
        _insert_order(rfm_orders, "a1", "u_active", "2026-04-01", 100)
        _insert_order(rfm_orders, "a2", "u_active", "2026-06-10", 100)
        _insert_order(rfm_orders, "d1", "u_dormant", "2026-04-01", 100)
        _insert_order(rfm_orders, "c1", "u_churned", "2025-10-01", 100)

        result = get_user_rfm_extended(
            rfm_orders,
            ["u_new", "u_active", "u_dormant", "u_churned"],
            as_of_date="2026-06-28",
        )

        assert result["u_new"].lifecycle_stage == "新客"
        assert result["u_active"].lifecycle_stage == "活跃客"
        assert result["u_dormant"].lifecycle_stage == "沉睡客"
        assert result["u_churned"].lifecycle_stage == "流失客"
        assert result["u_new"].rfm_quadrant

    def test_value_tier_gsv_and_frequency_thresholds(self, rfm_orders):
        """value_tier 3 桶分类正确."""
        _insert_order(rfm_orders, "h1", "u_high_gsv", "2026-06-01", 6000)
        for idx in range(10):
            _insert_order(rfm_orders, f"hf{idx}", "u_high_freq", "2026-06-01", 50)
        _insert_order(rfm_orders, "m1", "u_medium", "2026-06-01", 1500)
        _insert_order(rfm_orders, "l1", "u_low", "2026-06-01", 100)

        result = get_user_rfm_extended(
            rfm_orders,
            ["u_high_gsv", "u_high_freq", "u_medium", "u_low"],
            as_of_date="2026-06-28",
        )

        assert result["u_high_gsv"].value_tier == "高价值"
        assert result["u_high_freq"].value_tier == "高价值"
        assert result["u_medium"].value_tier == "中价值"
        assert result["u_low"].value_tier == "低价值"

    def test_potential_tier_growth_slope(self, rfm_orders):
        """potential_tier 3 桶分类正确."""
        _insert_order(rfm_orders, "hp1", "u_high", "2026-05-15", 100)
        _insert_order(rfm_orders, "hp2", "u_high", "2026-06-20", 250)
        _insert_order(rfm_orders, "mp1", "u_medium", "2026-05-15", 100)
        _insert_order(rfm_orders, "mp2", "u_medium", "2026-06-20", 100)
        _insert_order(rfm_orders, "lp1", "u_low", "2026-04-01", 300)

        result = get_user_rfm_extended(
            rfm_orders,
            ["u_high", "u_medium", "u_low"],
            as_of_date="2026-06-28",
        )

        assert result["u_high"].potential_tier == "高潜力"
        assert result["u_medium"].potential_tier == "中潜力"
        assert result["u_low"].potential_tier == "低潜力"
