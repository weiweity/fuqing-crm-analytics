"""Sprint 142 _compute_lock_metrics 性能重构回归测试."""

import pytest

from backend.semantic.calculations import safe_ratio
from backend.semantic.channels import GIFT_SAMPLE_DB
from backend.services.sampling_service import (
    _assert_sql_param_count,
    _compute_lock_metrics,
)
from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE


pytestmark = pytest.mark.skipif(
    not _PROD_DUCKDB_AVAILABLE,
    reason="production DuckDB 不可用",
)


def _reset_lock_tables(conn):
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE orders (
            order_id VARCHAR,
            user_id VARCHAR,
            channel VARCHAR,
            pay_time TIMESTAMP,
            actual_amount DOUBLE,
            is_refund BOOLEAN,
            order_status VARCHAR
        )
    """)
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE daily_visitors (
            date DATE,
            visitors INTEGER
        )
    """)
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE user_first_purchase (
            user_id VARCHAR,
            first_pay_date DATE
        )
    """)
    rows = [
        ("l1", "u1", GIFT_SAMPLE_DB, "2026-05-26", 0.01, False, "交易成功"),
        ("l2", "u2", GIFT_SAMPLE_DB, "2026-05-27", 0.01, False, "交易成功"),
        ("l3", "u3", GIFT_SAMPLE_DB, "2026-05-28", 0.01, False, "交易成功"),
        ("c1", "u1", "货架", "2026-06-05", 120.0, False, "交易成功"),
        ("c2", "u2", "货架", "2026-06-10", 80.0, False, "交易成功"),
    ]
    conn.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.executemany(
        "INSERT INTO daily_visitors VALUES (?::DATE, ?)",
        [("2026-06-01", 600), ("2026-06-02", 400)],
    )
    conn.executemany(
        "INSERT INTO user_first_purchase VALUES (?, ?::DATE)",
        [("u1", "2026-05-26"), ("u2", "2026-01-01"), ("u3", "2026-05-28")],
    )


@pytest.fixture
def lock_tables(monkeypatch_connection):
    _reset_lock_tables(monkeypatch_connection)
    try:
        yield monkeypatch_connection
    finally:
        monkeypatch_connection.execute("DROP TABLE IF EXISTS orders")
        monkeypatch_connection.execute("DROP TABLE IF EXISTS daily_visitors")
        monkeypatch_connection.execute("DROP TABLE IF EXISTS user_first_purchase")


class TestLockMetricsRefactor:
    """Sprint 142: _compute_lock_metrics 单 SQL 合并."""

    def test_lock_metrics_consistent_with_known_values(self, lock_tables):
        """重构后输出字段和值保持 Sprint 141 语义."""
        campaign_row = (2026, "618", "2026-06-01", "2026-06-18", "2026-05-25", "2026-05-31")

        result = _compute_lock_metrics(lock_tables, campaign_row)

        assert result["total_uv"] == 1000
        assert result["locked_users"] == 3
        assert result["converted_users"] == 2
        assert result["lock_gsv"] == 200.0
        assert result["new_locked_users"] == 2
        assert result["new_converted_users"] == 1
        assert result["new_lock_gsv"] == 120.0
        assert result["lock_rate"] == round(safe_ratio(3, 1000), 6)
        assert result["conversion_rate"] == round(safe_ratio(2, 3), 4)

    def test_lock_metrics_empty_lock_returns_empty(self, lock_tables):
        """lock_start/lock_end 为空时返回空指标."""
        result = _compute_lock_metrics(
            lock_tables,
            (2026, "noop", "2026-06-01", "2026-06-18", None, None),
        )

        assert result["locked_users"] == 0
        assert result["converted_users"] == 0
        assert result["lock_gsv"] == 0

    def test_lock_metrics_params_count_assertion(self, lock_tables):
        """L4.7 治根: SQL ? 数量必须等于 params 数量."""
        with pytest.raises(AssertionError, match="params mismatch"):
            _assert_sql_param_count("SELECT ? + ?", [1], "_compute_lock_metrics")
