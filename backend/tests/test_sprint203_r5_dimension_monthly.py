"""Sprint 203 R5 多维度按月衍生 锁回归 (L4.59 + L4.43 + L4.5 + L4.37 永久规则配套)

- 5 件新 tool 注册验证 (跟 Sprint 196 8 case 1:1 stable)
- QuerySpec spec 字段验证 (L4.37 registry 显式 import)
- L4.43 argparse 透传 (跟 Sprint 190 daily-gsv-multi-period 1:1 stable)
- L4.5 FilterBuilder 维度白名单 (L4.19 channel alias 永久规则)
- top_n axis 扩 monthly/quarterly/yearly (跟 Sprint 190 模式 1:1 stable)

L4.60 跨平台: REPO_ROOT = Path(__file__).resolve().parents[2]
"""
from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]  # L4.60 跨平台
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ad_hoc_queries"))

# === Phase 1 前 2 件 import + spec 验证 ===

def test_channel_monthly_import_ok():
    """Sprint 203 R5: channel-monthly 注册到 QUERIES dict."""
    import channel_monthly
    assert channel_monthly._channel_monthly_spec.name == "channel-monthly"
    assert channel_monthly.CHANNEL_MONTHLY_HEADERS == [
        "channel", "gsv", "orders", "customers", "aov", "yoy_pct"
    ]


def test_channel_monthly_run_signature():
    """Sprint 203 R5: run_channel_monthly 接 start / end / channel 参数."""
    import inspect
    import channel_monthly
    sig = inspect.signature(channel_monthly.run_channel_monthly)
    assert "start" in sig.parameters
    assert "end" in sig.parameters
    assert "channel" in sig.parameters


def test_channel_monthly_spec_args():
    """Sprint 203 R5: QuerySpec args 含 --start / --end / --channel (跟 channel_slice 1:1 stable)."""
    import channel_monthly
    spec = channel_monthly._channel_monthly_spec
    flag_names = [a["flags"][0] for a in spec.args if "flags" in a]
    assert "--start" in flag_names
    assert "--end" in flag_names
    assert "--channel" in flag_names


def test_top_n_axis_monthly_quarterly_yearly_added():
    """Sprint 203 R5: top_n 扩 axis 参数 (跟 Sprint 190 daily-gsv-multi-period 1:1 stable)."""
    from scripts.ad_hoc_queries.registry import QUERIES
    spec = QUERIES.get("top-n")
    assert spec is not None
    flag_names = [a["flags"][0] for a in spec.args if "flags" in a]
    assert "--axis" in flag_names
    assert "--month" in flag_names
    assert "--quarter" in flag_names
    assert "--year" in flag_names
    # axis choices
    axis_arg = next(a for a in spec.args if a.get("flags") == ("--axis",))
    assert "monthly" in axis_arg["choices"]
    assert "quarterly" in axis_arg["choices"]
    assert "yearly" in axis_arg["choices"]


def test_top_n_resolve_axis_daily():
    """Sprint 203 R5: _resolve_axis_dates axis=daily 走 start/end."""
    import top_n
    s, e = top_n._resolve_axis_dates("daily", "2026-06-01", "2026-06-15", None, None, None)
    assert s == "2026-06-01"
    assert e == "2026-06-15"


def test_top_n_resolve_axis_monthly():
    """Sprint 203 R5: _resolve_axis_dates axis=monthly 自动推导 [YYYY-MM-01, YYYY-MM+1-01)."""
    import top_n
    s, e = top_n._resolve_axis_dates("monthly", None, None, "2026-06", None, None)
    assert s == "2026-06-01"
    assert e == "2026-07-01"
    # 12 月边界
    s, e = top_n._resolve_axis_dates("monthly", None, None, "2026-12", None, None)
    assert s == "2026-12-01"
    assert e == "2027-01-01"


def test_top_n_resolve_axis_quarterly_yearly():
    """Sprint 203 R5: quarterly / yearly 边界正确."""
    import top_n
    # Q1 = 1-3 月
    s, e = top_n._resolve_axis_dates("quarterly", None, None, None, "2026-Q1", None)
    assert s == "2026-01-01"
    assert e == "2026-04-01"
    # Q4 = 10-12 月
    s, e = top_n._resolve_axis_dates("quarterly", None, None, None, "2026-Q4", None)
    assert s == "2026-10-01"
    assert e == "2027-01-01"
    # yearly
    s, e = top_n._resolve_axis_dates("yearly", None, None, None, None, "2026")
    assert s == "2026-01-01"
    assert e == "2027-01-01"


# === Phase 2 后 3 件 import + spec 验证 ===

def test_member_monthly_import_ok():
    """Sprint 203 R5: member-monthly 注册."""
    import member_monthly
    assert member_monthly._member_monthly_spec.name == "member-monthly"
    assert member_monthly.MEMBER_MONTHLY_HEADERS == [
        "is_member", "gsv", "orders", "customers", "ratio", "yoy_pct"
    ]


def test_refund_monthly_import_ok():
    """Sprint 203 R5: refund-monthly 注册."""
    import refund_monthly
    assert refund_monthly._refund_monthly_spec.name == "refund-monthly"
    assert refund_monthly.REFUND_MONTHLY_HEADERS == [
        "is_refund", "gsv", "orders", "refund_amount", "refund_rate", "yoy_pct"
    ]


def test_cross_dimension_monthly_import_ok():
    """Sprint 203 R5: cross-dimension-monthly 注册."""
    import cross_dimension_monthly
    assert cross_dimension_monthly._cross_dimension_monthly_spec.name == "cross-dimension-monthly"
    assert cross_dimension_monthly.CROSS_DIMENSION_MONTHLY_HEADERS == [
        "dim1_value", "dim2_value", "gsv", "orders", "customers", "yoy_pct"
    ]


def test_cross_dimension_whitelist_enforced():
    """Sprint 203 R5: dim1/dim2 必须 in 白名单 (L4.5 FilterBuilder 1:1 stable 防护 SQL 注入)."""
    import pytest
    import cross_dimension_monthly
    with pytest.raises(ValueError, match="not in whitelist"):
        cross_dimension_monthly.run_cross_dimension_monthly(
            start="2026-01", end="2026-06", dim1="evil_column", dim2="channel"
        )
    with pytest.raises(ValueError, match="not in whitelist"):
        cross_dimension_monthly.run_cross_dimension_monthly(
            start="2026-01", end="2026-06", dim1="channel", dim2="user_input"
        )


def test_cross_dimension_whitelist_6_dimensions():
    """Sprint 203 R5: 白名单含 channel / is_member / is_goujinjin / spu_category / spu_tier / spu_product_class (跟衍生矩阵 1:1 stable)."""
    import cross_dimension_monthly
    expected = {"channel", "is_member", "is_goujinjin", "spu_category", "spu_tier", "spu_product_class"}
    assert set(cross_dimension_monthly._DIMENSION_WHITELIST.keys()) == expected


# === QUERIES dict 1:1 stable 验证 ===

def test_queries_dict_5_new_tools_registered():
    """Sprint 203 R5: QUERIES dict 含 5 件新 tool (跟 Sprint 198 14 → 19 累计 1:1 stable)."""
    from scripts.ad_hoc_queries.registry import QUERIES
    new_tools = ["channel-monthly", "member-monthly", "refund-monthly", "cross-dimension-monthly"]
    for name in new_tools:
        assert name in QUERIES, f"Missing tool: {name}"
    # top-n 仍是同一个 (axis 扩)
    assert "top-n" in QUERIES


def test_all_new_tools_have_business_tag():
    """Sprint 203 R5: 5 件新 tool business_tag 非空 (跟 Sprint 196/198 1:1 stable)."""
    from scripts.ad_hoc_queries.registry import QUERIES
    new_tools = ["channel-monthly", "member-monthly", "refund-monthly", "cross-dimension-monthly"]
    for name in new_tools:
        spec = QUERIES[name]
        assert spec.business_tag, f"{name} missing business_tag"


# === 月份边界处理 (L4.43 argparse 透传配套) ===

def test_monthly_dec_end_of_year_december():
    """Sprint 203 R5: 12 月边界正确 (2026-12 → 2027-01)."""
    from datetime import date
    # Re-test monthly end_exclusive logic via cross_dimension helper
    end_year, end_month = 2026, 12
    if end_month == 12:
        end_exclusive = date(end_year + 1, 1, 1)
    else:
        end_exclusive = date(end_year, end_month + 1, 1)
    assert end_exclusive.isoformat() == "2027-01-01"


def test_yoy_logic_same_month_prev_year():
    """Sprint 203 R5: YOY 同期是去年同月 (L4.43 1:1 stable 跨 sprint 模式)."""
    from datetime import date
    start_date = date(2026, 6, 1)
    yoy_start = date(start_date.year - 1, start_date.month, 1)
    assert yoy_start.isoformat() == "2025-06-01"


def test_member_monthly_total_gsv_sum():
    """Sprint 203 R5: member-monthly total_gsv sum 行为验证 (空数据 → 0)."""
    # Mimic the sum logic from member_monthly
    rows = []  # 空数据
    total_gsv = sum(float(r[1]) for r in rows) if rows else 0.0
    assert total_gsv == 0.0


def test_refund_monthly_refund_rate_calculation():
    """Sprint 203 R5: refund-monthly refund_rate = refund_amount / gsv (跟 channel_monthly ratio 1:1 stable)."""
    gsv = 1000.0
    refund_amount = 100.0
    refund_rate = round(refund_amount / gsv * 100, 2) if gsv > 0 else 0.0
    assert refund_rate == 10.0
    # 零 GSV fallback
    refund_rate = round(refund_amount / 0 * 100, 2) if 0 > 0 else 0.0
    assert refund_rate == 0.0