"""Sprint 142 level 联动 summary 二级聚合回归测试."""

import pytest

from backend.services.sampling_service import _group_by_level, get_sampling_roi
from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE


pytestmark = pytest.mark.skipif(
    not _PROD_DUCKDB_AVAILABLE,
    reason="production DuckDB 不可用",
)


def _reset_sampling_orders(conn):
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
    rows = [
        ("s1", None, "u1", "U先派样", "2026-05-01", None, "胶原膜", "核心品", "面膜", "涂抹面膜", "修护", "小样", 0.01, False, "交易成功"),
        ("r1", None, "u1", "货架", "2026-05-10", None, "胶原膜", "核心品", "面膜", "涂抹面膜", "修护", "正装", 200.0, False, "交易成功"),
        ("s2", None, "u2", "百补派样", "2026-05-02", None, "精华", "潜力品", "精华液", "安瓶", "抗老", "小样", 0.01, False, "交易成功"),
        ("r2", None, "u2", "货架", "2026-05-18", None, "精华", "潜力品", "精华液", "安瓶", "抗老", "正装", 300.0, False, "交易成功"),
    ]
    conn.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?::TIMESTAMP, ?::TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


@pytest.fixture
def sampling_orders(monkeypatch_connection):
    _reset_sampling_orders(monkeypatch_connection)
    try:
        yield monkeypatch_connection
    finally:
        monkeypatch_connection.execute("DROP TABLE IF EXISTS orders")


class TestLevelAggregation:
    """Sprint 142: summary_by_level 字段在 5 levels 都正确返回."""

    @pytest.mark.parametrize(
        "level",
        ["spu_category", "spu_tier", "spu_product_class", "spu_product_subclass", "spu_cosmetic"],
    )
    def test_summary_by_level_5_levels(self, sampling_orders, level):
        """5 levels 都返回 summary_by_level 字段."""
        result = get_sampling_roi(
            start_date="2026-05-01",
            end_date="2026-05-31",
            window_days=30,
            level=level,
        )

        assert result["summary_by_level"]
        assert isinstance(result["summary_by_level"], dict)
        assert result["category_breakdown"]
        for level_value, summaries in result["summary_by_level"].items():
            assert level_value
            assert summaries
            for summary in summaries:
                assert summary.level == level
                assert summary.level_value == level_value

    def test_group_by_level_reuses_category_rows(self, monkeypatch_connection):
        """summary_by_level helper 直接复用 category rows, 不需要连接或新增 SQL."""
        rows = [
            {
                "channel": "U先派样",
                "category": "核心品",
                "sample_users": 10,
                "repurchase_users": 4,
                "repurchase_rate": 0.4,
                "repurchase_gsv": 800.0,
                "repurchase_aus": 200.0,
                "full_repurchase_users": 3,
                "full_repurchase_rate": 0.3,
                "full_repurchase_gsv": 600.0,
                "full_repurchase_aus": 200.0,
                "nonfull_repurchase_users": 1,
                "nonfull_repurchase_gsv": 200.0,
                "nonfull_repurchase_aus": 200.0,
            }
        ]

        grouped = _group_by_level(rows, "spu_tier")

        assert list(grouped) == ["核心品"]
        assert grouped["核心品"][0].channel == "U先派样"
        assert grouped["核心品"][0].level == "spu_tier"
