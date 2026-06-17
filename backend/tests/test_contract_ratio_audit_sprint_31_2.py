"""Sprint 31.2 合同 ratio/rate 范围约束补标测试 (Sprint 30.3 ratio audit 收口).

背景:
- Sprint 30.3 (v0.4.14.107) 闭环了 CohortRetentionResponse 4 个 List 嵌套字段
- Sprint 31.2 (v0.4.14.115) 收口 Sprint 30.3 留的'TierFlowRow ratio /
  NewCustomerConversionFunnel rate / MarketBasketItem support-confidence 走
  Sprint 31+ 单独 sprint 风险 review'
- 补 Pydantic v2 strict 0-1 / pp 范围约束, 防 service 层某路径返回越界值时
  API 入口 422 freeze (跟 Sprint 30.3 模式一致)

覆盖 (12 字段 + 1 保留 = 13 case):
  - TierFlowRow: 5 ratio (repurchase_rate_* + repurchase_gsv_ratio_*) 越界 freeze
  - TierFlowRow: yoy_repurchase_rate PpField 范围 -100~+100, 150 应 raise
  - TierFlowRow: yoy_repurchase_rate None 透传
  - NewCustomerConversionFunnel: 4 rate (day7/30/90 + year) 越界 freeze
  - MarketBasketItem: support / confidence 越界 freeze
  - MarketBasketItem: lift / gsv_lift 保持 float (倍数可超 1, Sprint 30.3 决定)
"""
import pytest
from pydantic import ValidationError

from backend.contracts.health import TierFlowRow, NewCustomerConversionFunnel
from backend.contracts.category import MarketBasketItem


# ============================================================
# TierFlowRow 越界 freeze (6 case)
# ============================================================

class TestTierFlowRowRatioBounds:
    def test_repurchase_rate_current_oob_raises(self):
        """repurchase_rate_current > 1.0 必须 raise, loc 含字段名"""
        with pytest.raises(ValidationError) as exc:
            TierFlowRow(tier_segment="S", repurchase_rate_current=1.5)
        assert any("repurchase_rate_current" in str(e.get("loc", ""))
                   for e in exc.value.errors())

    def test_repurchase_rate_comp_oob_raises(self):
        """repurchase_rate_comp < 0 必须 raise (下限 0)"""
        with pytest.raises(ValidationError) as exc:
            TierFlowRow(tier_segment="S", repurchase_rate_comp=-0.1)
        assert any("repurchase_rate_comp" in str(e.get("loc", ""))
                   for e in exc.value.errors())

    def test_repurchase_rate_prev2_oob_raises(self):
        """repurchase_rate_prev2 > 1.0 必须 raise (上限 1)"""
        with pytest.raises(ValidationError) as exc:
            TierFlowRow(tier_segment="S", repurchase_rate_prev2=1.001)
        assert any("repurchase_rate_prev2" in str(e.get("loc", ""))
                   for e in exc.value.errors())

    def test_repurchase_gsv_ratio_comp_oob_raises(self):
        """注释写'0-1'但注解是 float, 补 RatioField 后越界应 raise"""
        with pytest.raises(ValidationError) as exc:
            TierFlowRow(tier_segment="S", repurchase_gsv_ratio_comp=2.0)
        assert any("repurchase_gsv_ratio_comp" in str(e.get("loc", ""))
                   for e in exc.value.errors())

    def test_repurchase_gsv_ratio_prev2_oob_raises(self):
        """repurchase_gsv_ratio_prev2 < 0 应 raise (跟 Sprint 16.5 current 模式对齐)"""
        with pytest.raises(ValidationError) as exc:
            TierFlowRow(tier_segment="S", repurchase_gsv_ratio_prev2=-0.5)
        assert any("repurchase_gsv_ratio_prev2" in str(e.get("loc", ""))
                   for e in exc.value.errors())

    def test_yoy_repurchase_rate_pp_field_range(self):
        """yoy_repurchase_rate 用 PpField, 范围 -100~+100, 150 应 raise, 50 应 pass"""
        with pytest.raises(ValidationError):
            TierFlowRow(tier_segment="S", yoy_repurchase_rate=150.0)
        # 合法 pp 差应 pass (Sprint 30.3 例子 5.28pp)
        row = TierFlowRow(tier_segment="S", yoy_repurchase_rate=5.28)
        assert row.yoy_repurchase_rate == 5.28

    def test_yoy_repurchase_rate_none_passes(self):
        """yoy_repurchase_rate Optional, None 应 pass (透传)"""
        row = TierFlowRow(tier_segment="S", yoy_repurchase_rate=None)
        assert row.yoy_repurchase_rate is None


# ============================================================
# NewCustomerConversionFunnel 越界 freeze (4 case)
# ============================================================

class TestNewCustomerConversionFunnelRatioBounds:
    def test_day7_rate_oob_raises(self):
        """day7_rate > 1.0 必须 raise"""
        with pytest.raises(ValidationError) as exc:
            NewCustomerConversionFunnel(
                cohort_date="2026-06", total_first_purchase=100,
                day7_repurchase=50, day7_rate=1.2,
            )
        assert any("day7_rate" in str(e.get("loc", ""))
                   for e in exc.value.errors())

    def test_day30_rate_oob_raises(self):
        """day30_rate < 0 必须 raise"""
        with pytest.raises(ValidationError) as exc:
            NewCustomerConversionFunnel(
                cohort_date="2026-06", total_first_purchase=100,
                day30_repurchase=50, day30_rate=-0.1,
            )
        assert any("day30_rate" in str(e.get("loc", ""))
                   for e in exc.value.errors())

    def test_day90_rate_oob_raises(self):
        """day90_rate > 1.0 必须 raise (临界 1.0001)"""
        with pytest.raises(ValidationError) as exc:
            NewCustomerConversionFunnel(
                cohort_date="2026-06", total_first_purchase=100,
                day90_repurchase=50, day90_rate=1.0001,
            )
        assert any("day90_rate" in str(e.get("loc", ""))
                   for e in exc.value.errors())

    def test_year_rate_oob_raises(self):
        """year_rate > 1.0 必须 raise"""
        with pytest.raises(ValidationError) as exc:
            NewCustomerConversionFunnel(
                cohort_date="2026-06", total_first_purchase=100,
                year_repurchase=50, year_rate=2.0,
            )
        assert any("year_rate" in str(e.get("loc", ""))
                   for e in exc.value.errors())


# ============================================================
# MarketBasketItem 越界 freeze + float 保留 (2 case)
# ============================================================

class TestMarketBasketItemRatioBounds:
    def test_support_oob_raises(self):
        """support 用 RatioField, 越界应 raise"""
        with pytest.raises(ValidationError) as exc:
            MarketBasketItem(
                category_name="A", co_order_count=10,
                support=1.5, confidence=0.5, lift=1.0,
                target_order_count=20, co_gsv=100.0, co_own_gsv=80.0,
                co_aus=10.0, target_aus=5.0, gsv_lift=2.0,
            )
        assert any("support" in str(e.get("loc", ""))
                   for e in exc.value.errors())

    def test_confidence_oob_raises(self):
        """confidence 用 RatioField, 越界应 raise"""
        with pytest.raises(ValidationError) as exc:
            MarketBasketItem(
                category_name="A", co_order_count=10,
                support=0.5, confidence=-0.1, lift=1.0,
                target_order_count=20, co_gsv=100.0, co_own_gsv=80.0,
                co_aus=10.0, target_aus=5.0, gsv_lift=2.0,
            )
        assert any("confidence" in str(e.get("loc", ""))
                   for e in exc.value.errors())

    def test_lift_gsv_lift_remains_float(self):
        """lift / gsv_lift 保持 float (倍数可超 1, Sprint 30.3 决定)"""
        item = MarketBasketItem(
            category_name="A", co_order_count=10,
            support=0.5, confidence=0.5, lift=1.5,  # 1.5 倍应 pass
            target_order_count=20, co_gsv=100.0, co_own_gsv=80.0,
            co_aus=15.0, target_aus=5.0, gsv_lift=3.0,  # 3.0 倍应 pass
        )
        assert item.lift == 1.5
        assert item.gsv_lift == 3.0
