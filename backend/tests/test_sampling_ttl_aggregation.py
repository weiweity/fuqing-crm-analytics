"""Sprint 144: TTL 派样聚合回归测试."""

import pytest

from backend.services.sampling_service import _compute_ttl_metrics, get_sampling_roi
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
def ttl_orders(monkeypatch_connection):
    rows = [
        ("s1", None, "u1", "U先派样", "2026-06-01", None, "面膜", "核心", "面膜", "涂抹", "修护", "小样", 0.01, False, "交易成功"),
        ("s2", None, "u1", "百补派样", "2026-06-02", None, "面膜", "核心", "面膜", "涂抹", "修护", "小样", 0.01, False, "交易成功"),
        ("r1", None, "u1", "货架", "2026-06-08", None, "面膜", "核心", "面膜", "涂抹", "修护", "正装", 100.0, False, "交易成功"),
    ]
    _reset_orders(monkeypatch_connection, rows)
    try:
        yield monkeypatch_connection
    finally:
        monkeypatch_connection.execute("DROP TABLE IF EXISTS orders")


def test_ttl_dedup_user(ttl_orders):
    """同一用户 U先+百补 都派样，TTL sample_users 只算 1."""
    result = get_sampling_roi("2026-06-01", "2026-06-30", window_days=30)
    ttl, u_channel, b_channel = result["summary"]["channels"]

    assert ttl["channel"] == "TTL派样"
    assert [c["channel"] for c in result["summary"]["channels"]] == ["TTL派样", "U先派样", "百补派样"]
    assert ttl["sample_users"] == 1
    assert ttl["sample_users"] < u_channel["sample_users"] + b_channel["sample_users"]


def test_ttl_gsv_sum(monkeypatch_connection):
    """无重叠用户时，TTL GSV 等于两个单渠道 GSV 之和."""
    rows = [
        ("s1", None, "u1", "U先派样", "2026-06-01", None, "面膜", "核心", "面膜", "涂抹", "修护", "小样", 0.01, False, "交易成功"),
        ("r1", None, "u1", "货架", "2026-06-08", None, "面膜", "核心", "面膜", "涂抹", "修护", "正装", 100.0, False, "交易成功"),
        ("s2", None, "u2", "百补派样", "2026-06-02", None, "精华", "潜力", "精华", "安瓶", "抗老", "小样", 0.01, False, "交易成功"),
        ("r2", None, "u2", "货架", "2026-06-10", None, "精华", "潜力", "精华", "安瓶", "抗老", "非正装", 50.0, False, "交易成功"),
    ]
    _reset_orders(monkeypatch_connection, rows)

    result = get_sampling_roi("2026-06-01", "2026-06-30", window_days=30)
    ttl, u_channel, b_channel = result["summary"]["channels"]

    assert ttl["repurchase_gsv"] == pytest.approx(u_channel["repurchase_gsv"] + b_channel["repurchase_gsv"])


def test_ttl_empty_baseline(monkeypatch_connection):
    """DB 没有派样数据时返回空指标."""
    _reset_orders(monkeypatch_connection, [])

    ttl = _compute_ttl_metrics("2026-06-01", "2026-06-30", window_days=30)

    assert ttl["channel"] == "TTL派样"
    assert ttl["sample_users"] == 0
    assert ttl["repurchase_gsv"] == 0.0


def test_ttl_full_gsv_sum(monkeypatch_connection):
    """无重叠用户时，TTL 正装 GSV 等于两个单渠道正装 GSV 之和."""
    rows = [
        ("s1", None, "u1", "U先派样", "2026-06-01", None, "面膜", "核心", "面膜", "涂抹", "修护", "小样", 0.01, False, "交易成功"),
        ("r1", None, "u1", "货架", "2026-06-08", None, "面膜", "核心", "面膜", "涂抹", "修护", "正装", 100.0, False, "交易成功"),
        ("s2", None, "u2", "百补派样", "2026-06-02", None, "精华", "潜力", "精华", "安瓶", "抗老", "小样", 0.01, False, "交易成功"),
        ("r2", None, "u2", "货架", "2026-06-10", None, "精华", "潜力", "精华", "安瓶", "抗老", "正装", 70.0, False, "交易成功"),
    ]
    _reset_orders(monkeypatch_connection, rows)

    result = get_sampling_roi("2026-06-01", "2026-06-30", window_days=30)
    ttl, u_channel, b_channel = result["summary"]["channels"]

    assert ttl["full_repurchase_gsv"] == pytest.approx(
        u_channel["full_repurchase_gsv"] + b_channel["full_repurchase_gsv"]
    )
