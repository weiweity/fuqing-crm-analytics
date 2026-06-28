"""Sprint 144: Sampling 回购周期分布 4 桶回归测试."""

import pytest

from backend.services.sampling_service import get_sampling_repurchase_buckets
from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE


pytestmark = pytest.mark.skipif(
    not _PROD_DUCKDB_AVAILABLE,
    reason="production DuckDB 不可用",
)


def _reset_orders(conn, rows):
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
    if rows:
        conn.executemany(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?::TIMESTAMP, ?::TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )


@pytest.fixture
def distribution_orders(monkeypatch_connection):
    rows = [
        ("s1", None, "u1", "U先派样", "2026-06-01", None, "面膜", "核心", "面膜", "涂抹", "修护", "小样", 0.01, False, "交易成功"),
        ("r1", None, "u1", "货架", "2026-06-04", None, "面膜", "核心", "面膜", "涂抹", "修护", "正装", 10.0, False, "交易成功"),
        ("s2", None, "u2", "U先派样", "2026-06-01", None, "面膜", "核心", "面膜", "涂抹", "修护", "小样", 0.01, False, "交易成功"),
        ("r2", None, "u2", "货架", "2026-06-20", None, "面膜", "核心", "面膜", "涂抹", "修护", "正装", 20.0, False, "交易成功"),
        ("s3", None, "u3", "百补派样", "2026-06-01", None, "精华", "潜力", "精华", "安瓶", "抗老", "小样", 0.01, False, "交易成功"),
        ("r3", None, "u3", "货架", "2026-07-15", None, "精华", "潜力", "精华", "安瓶", "抗老", "正装", 30.0, False, "交易成功"),
        ("s4", None, "u4", "百补派样", "2026-06-01", None, "精华", "潜力", "精华", "安瓶", "抗老", "小样", 0.01, False, "交易成功"),
        ("r4", None, "u4", "货架", "2026-08-20", None, "精华", "潜力", "精华", "安瓶", "抗老", "正装", 40.0, False, "交易成功"),
    ]
    _reset_orders(monkeypatch_connection, rows)
    try:
        yield monkeypatch_connection
    finally:
        monkeypatch_connection.execute("DROP TABLE IF EXISTS orders")


def test_distribution_4_buckets(distribution_orders):
    result = get_sampling_repurchase_buckets("2026-06-01", "2026-06-30", window_days=90)

    assert [b["bucket"] for b in result["buckets"]] == ["0-7d", "8-30d", "31-60d", "61-90d"]
    assert [b["users"] for b in result["buckets"]] == [1, 1, 1, 1]


def test_distribution_window_days(distribution_orders):
    result = get_sampling_repurchase_buckets("2026-06-01", "2026-06-30", window_days=30)

    assert result["window_days"] == 30
    assert [b["users"] for b in result["buckets"]] == [1, 1, 0, 0]


def test_distribution_empty(monkeypatch_connection):
    _reset_orders(monkeypatch_connection, [])

    result = get_sampling_repurchase_buckets("2026-06-01", "2026-06-30", window_days=90)

    assert len(result["buckets"]) == 4
    assert all(bucket["users"] == 0 for bucket in result["buckets"])
    assert all(bucket["gsv"] == 0.0 for bucket in result["buckets"])


def test_distribution_ttl_vs_single_channel(distribution_orders):
    ttl = get_sampling_repurchase_buckets("2026-06-01", "2026-06-30", window_days=90)
    u_channel = get_sampling_repurchase_buckets(
        "2026-06-01",
        "2026-06-30",
        window_days=90,
        channel="U先派样",
    )

    assert sum(b["users"] for b in ttl["buckets"]) == 4
    assert sum(b["users"] for b in u_channel["buckets"]) == 2
