"""Sprint 144: Sampling ROI 同比/环比字段回归测试."""

import pytest

from backend.contracts.sampling import SamplingChannelSummary
from backend.services.sampling_service import get_sampling_roi
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
def yoy_orders(monkeypatch_connection):
    rows = [
        ("s26u", None, "u1", "U先派样", "2026-06-01", None, "面膜", "核心", "面膜", "涂抹", "修护", "小样", 0.01, False, "交易成功"),
        ("r26u", None, "u1", "货架", "2026-06-08", None, "面膜", "核心", "面膜", "涂抹", "修护", "正装", 120.0, False, "交易成功"),
        ("s26b", None, "u2", "百补派样", "2026-06-02", None, "精华", "潜力", "精华", "安瓶", "抗老", "小样", 0.01, False, "交易成功"),
        ("r26b", None, "u2", "货架", "2026-06-10", None, "精华", "潜力", "精华", "安瓶", "抗老", "正装", 80.0, False, "交易成功"),
        ("s25u", None, "u3", "U先派样", "2025-06-01", None, "面膜", "核心", "面膜", "涂抹", "修护", "小样", 0.01, False, "交易成功"),
        ("r25u", None, "u3", "货架", "2025-06-08", None, "面膜", "核心", "面膜", "涂抹", "修护", "正装", 60.0, False, "交易成功"),
        ("s25b", None, "u4", "百补派样", "2025-06-02", None, "精华", "潜力", "精华", "安瓶", "抗老", "小样", 0.01, False, "交易成功"),
        ("r25b", None, "u4", "货架", "2025-06-10", None, "精华", "潜力", "精华", "安瓶", "抗老", "正装", 40.0, False, "交易成功"),
        ("s26m", None, "u5", "U先派样", "2026-05-01", None, "面膜", "核心", "面膜", "涂抹", "修护", "小样", 0.01, False, "交易成功"),
        ("r26m", None, "u5", "货架", "2026-05-08", None, "面膜", "核心", "面膜", "涂抹", "修护", "正装", 100.0, False, "交易成功"),
    ]
    _reset_orders(monkeypatch_connection, rows)
    try:
        yield monkeypatch_connection
    finally:
        monkeypatch_connection.execute("DROP TABLE IF EXISTS orders")


def test_roi_yoy_compare_none_uses_native_year_over_year(yoy_orders):
    """compare_date_range=None 时走默认去年同期，返回 yoy_* 字段."""
    result = get_sampling_roi("2026-06-01", "2026-06-30", window_days=30)
    ttl = result["summary"]["channels"][0]

    assert ttl["channel"] == "TTL派样"
    assert ttl["repurchase_gsv_yoy_pct"] == pytest.approx(100.0)
    assert ttl["repurchase_rate_yoy_pp"] == pytest.approx(0.0)


def test_roi_mom_compare_tuple(yoy_orders):
    """compare_date_range 显式传入时返回 mom_* 字段."""
    result = get_sampling_roi(
        "2026-06-01",
        "2026-06-30",
        window_days=30,
        compare_date_range=("2026-05-01", "2026-05-31"),
    )
    ttl = result["summary"]["channels"][0]

    assert ttl["repurchase_gsv_mom_pct"] == pytest.approx(100.0)
    assert "repurchase_gsv_yoy_pct" not in ttl


def test_roi_yoy_zero_baseline(monkeypatch_connection):
    """对比窗口为 0 时，百分比变化为 None，防止除零."""
    rows = [
        ("s26u", None, "u1", "U先派样", "2026-06-01", None, "面膜", "核心", "面膜", "涂抹", "修护", "小样", 0.01, False, "交易成功"),
        ("r26u", None, "u1", "货架", "2026-06-08", None, "面膜", "核心", "面膜", "涂抹", "修护", "正装", 120.0, False, "交易成功"),
    ]
    _reset_orders(monkeypatch_connection, rows)

    result = get_sampling_roi("2026-06-01", "2026-06-30", window_days=30)
    ttl = result["summary"]["channels"][0]

    assert ttl["repurchase_gsv_yoy_pct"] is None
    assert ttl["repurchase_users_yoy_pct"] is None


def test_roi_yoy_pct_pp_contract_types():
    """yoy_pct / yoy_pp 字段在契约层使用强类型别名，不退回裸 float."""
    fields = SamplingChannelSummary.model_fields

    assert "PercentageField" in str(fields["repurchase_gsv_yoy_pct"].annotation)
    assert "PpField" in str(fields["repurchase_rate_yoy_pp"].annotation)
    assert "PercentageField" in str(fields["repurchase_gsv_mom_pct"].annotation)
    assert "PpField" in str(fields["repurchase_rate_mom_pp"].annotation)


def test_roi_yoy_ttl_included(yoy_orders):
    """TTL 行和单渠道行都带同比字段."""
    result = get_sampling_roi("2026-06-01", "2026-06-30", window_days=30)
    channels = result["summary"]["channels"]

    assert channels[0]["channel"] == "TTL派样"
    assert all("repurchase_gsv_yoy_pct" in channel for channel in channels)


def test_roi_category_breakdown_no_unbound_local_error(yoy_orders):
    """Sprint 176 真因回归: a6447de bugfix 误删主循环+compare_cat_by_key 构造块 70 行
    导致 /api/v1/sampling/roi 报 500 UnboundLocalError. 验证 category_breakdown 构造不抛
    异常, 且每行带 9 个 yoy_* 字段 (Sprint 175 Q5 设计意图).

    配套 contract B2 回归见 test_sampling_roi_sprint176_regression.py (不依赖 DuckDB)."""
    result = get_sampling_roi("2026-06-01", "2026-06-30", window_days=30)

    # 主断言: category_breakdown 必须存在且非空 (u1-u5 在 2026-06-01~30 有派样)
    assert "category_breakdown" in result
    assert isinstance(result["category_breakdown"], list)
    assert len(result["category_breakdown"]) > 0, (
        "Sprint 176: category_breakdown 为空 → category_result 未构造, 回归 UnboundLocalError"
    )

    # 第二断言: summary_by_level 走的是 _group_by_level (line 460), 必须正常返回
    assert "summary_by_level" in result
    assert isinstance(result["summary_by_level"], dict)

    # 第三断言: 每行带 9 个 yoy 字段 (Sprint 175 Q5 设计)
    required_yoy_fields = {
        "repurchase_users_yoy_pct",
        "repurchase_gsv_yoy_pct",
        "repurchase_rate_yoy_pp",
        "full_repurchase_users_yoy_pct",
        "full_repurchase_gsv_yoy_pct",
        "full_repurchase_rate_yoy_pp",
        "repurchase_aus_yoy_pct",
        "full_repurchase_aus_yoy_pct",
        "nonfull_repurchase_gsv_yoy_pct",
    }
    for row in result["category_breakdown"]:
        missing = required_yoy_fields - set(row.keys())
        assert not missing, f"Sprint 176: 行 {row.get('category')} 缺少 yoy 字段: {missing}"
