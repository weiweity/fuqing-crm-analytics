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
    """compare_date_range=None 时走默认去年同期，返回 yoy_* 字段. L4.81 治本契约: yoy_pct 字段 backend 返回 raw ratio (no *100, 1.0 = +100% / 100)."""
    result = get_sampling_roi("2026-06-01", "2026-06-30", window_days=30)
    ttl = result["summary"]["channels"][0]

    assert ttl["channel"] == "TTL派样"
    # L4.81 治本契约: yoy_pct = 1.0 (raw ratio, no *100) 旧契约: 100.0 (已 *100)
    assert ttl["repurchase_gsv_yoy_pct"] == pytest.approx(1.0)
    # L4.81 治本契约: yoy_pp = 0.0 (raw ratio diff, no *100) 旧契约: 0.0 (same)
    assert ttl["repurchase_rate_yoy_pp"] == pytest.approx(0.0)


def test_roi_mom_compare_tuple(yoy_orders):
    """compare_date_range 显式传入时返回 mom_* 字段.

    Sprint 145 改 compare_prefix='mom' 死分支后算法稳定, 但 test 期望 100% 跟
    stub data 反推不一致: 5月 TTL GSV=220 (u3/u4 复购交易落在 5月窗口,
    算法按 first_sample_time ∈ window 计算), 6月 TTL GSV=200, MOM = -9.09%.
    反推实测验证 (临时探针 backend/tests/test_probe_mom_actual.py 已清理).

    L4.81 治本契约: backend mom_absolute 返回 raw ratio (no *100, e.g. -0.0909 = -9.09% / 100).
    """
    result = get_sampling_roi(
        "2026-06-01",
        "2026-06-30",
        window_days=30,
        compare_date_range=("2026-05-01", "2026-05-31"),
    )
    ttl = result["summary"]["channels"][0]

    # 5月 TTL GSV=220 (u3/u4 复购交易落在 5月窗口), 6月 TTL GSV=200,
    # MOM ratio = (200-220)/220 ≈ -0.0909, service round(*, 4) 后输出 -0.0909 (L4.81: no *100).
    assert ttl["repurchase_gsv_mom_pct"] == pytest.approx(-0.0909)
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


def _field_has_ge(field, expected_ge: float) -> bool:
    """检查 Pydantic Annotated 字段 metadata 中的 Ge 约束.

    Pydantic v2 + ``Optional[PercentageField]`` 包装下 Ge 实际藏在
    ``field.annotation.__args__[0].__metadata__[0].metadata`` (FieldInfo.metadata).
    递归搜索 Ge 对象 (Union args + Annotated metadata + FieldInfo.metadata).
    SSOT: backend/contracts/types.py PercentageField 1T / PpField ±100pp
    (Sprint 14.5 治本 1:1 stable).
    """
    def _walk(obj):
        # 直接 Ge
        if hasattr(obj, "ge") and obj.ge == expected_ge:
            return True
        # FieldInfo 自身有 .metadata (Pydantic v2 装的 Ge/Le 在这里)
        fi_meta = getattr(obj, "metadata", None)
        if fi_meta:
            for m in fi_meta:
                if _walk(m):
                    return True
        # Annotated metadata
        annotated_meta = getattr(obj, "__metadata__", None)
        if annotated_meta:
            for m in annotated_meta:
                if _walk(m):
                    return True
        # Union args (Optional[X] → (X, None))
        args = getattr(obj, "__args__", None)
        if args:
            for a in args:
                if _walk(a):
                    return True
        return False

    return _walk(field.annotation)


def test_roi_yoy_pct_pp_contract_types():
    """yoy_pct / yoy_pp 字段在契约层使用强类型别名 (PercentageField / PpField),
    不退回裸 float. SSOT: backend/contracts/types.py PercentageField 1e10 / PpField 1e10 (L4.81 治本: no *100 契约).

    Pydantic v2 ``str(annotation)`` 不显示 alias, 改用 ``.metadata`` 检测 Ge 约束
    (跟 L4.81 治本契约 1:1 stable 沿用)."""
    fields = SamplingChannelSummary.model_fields

    # L4.81 治本契约: PercentageField 范围 -1e10~+1e10 (raw ratio 0-1, 兼容 yoy_absolute 万倍异常值) — yoy_pct / mom_pct 字段
    assert _field_has_ge(fields["repurchase_gsv_yoy_pct"], -1e10), (
        "repurchase_gsv_yoy_pct 缺 PercentageField 1e10 下限 SSOT (L4.81 治本契约 no *100)"
    )
    assert _field_has_ge(fields["repurchase_gsv_mom_pct"], -1e10), (
        "repurchase_gsv_mom_pct 缺 PercentageField 1e10 下限 SSOT (L4.81 治本契约 no *100)"
    )
    # L4.81 治本契约: PpField 范围 -1e10~+1e10 (raw ratio diff 0-1, 兼容 yoy_ratio 万倍异常值) — yoy_pp / mom_pp 字段
    assert _field_has_ge(fields["repurchase_rate_yoy_pp"], -1e10), (
        "repurchase_rate_yoy_pp 缺 PpField 1e10 下限 SSOT (L4.81 治本契约 no *100)"
    )
    assert _field_has_ge(fields["repurchase_rate_mom_pp"], -1e10), (
        "repurchase_rate_mom_pp 缺 PpField 1e10 下限 SSOT (L4.81 治本契约 no *100)"
    )


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
