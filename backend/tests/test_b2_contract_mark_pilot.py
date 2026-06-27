"""Sprint 16.5 B2 试点 3 contract audit 治根测试.

背景:
- Sprint 15 B1 模式: audience.py 28 个 ratio/percentage/pp 字段补 RatioField/PercentageField/PpField 标注
- Sprint 16.5 B2 试点: 扩到 category + metrics + health 3 个 contract, 每个 3 mark 字段治根 = 9 字段
- 治根: service 端返错值 (e.g. ratio=1.5 越界) 原本 API 层 500, 加 Pydantic Field 标注后 422 ValidationError

测试覆盖 3 contract × 3 mark = 9 个治根点:
- category.py: CategoryDistributionItem.pct / penetration_rate / member_ratio
- metrics.py: TrendData.member_ratios / ly_amounts / ly_member_ratios
- health.py: ValueTierDefinition.gsv_ratio / TierFlowRow.repurchase_gsv_ratio_current / CustomerSegmentItem.gsv_ratio
"""
import pytest
from pydantic import ValidationError

from backend.contracts.category import CategoryDistributionItem
from backend.contracts.metrics import TrendData
from backend.contracts.health import ValueTierDefinition, TierFlowRow, CustomerSegmentItem


class TestCategoryContractMark:
    """category.py × 3 mark 字段: CategoryDistributionItem.pct / penetration_rate / member_ratio"""

    def test_category_pct_valid_ratio(self):
        """mark 1: pct 0-100 percentage 合法值接受"""
        item = CategoryDistributionItem(name="面膜", user_count=100, gmv=50000.0, pct=42.0)
        assert item.pct == 42.0

    def test_category_pct_invalid_ratio_rejected(self):
        """mark 1: pct 越界 2e12 触发 422 ValidationError (不再 500).

        Sprint 24 P0: PercentageField 上限从 1B 放宽到 1T (治根 6/14 aus_yoy=3.35e9 不再 500),
        越界值相应提到 2e12. 1e12 仍接受 (兼容 yoy 万倍涨), 2e12 触发 ValidationError.
        """
        with pytest.raises(ValidationError) as exc_info:
            CategoryDistributionItem(name="面膜", user_count=100, gmv=50000.0, pct=2_000_000_000_000.0)
        errors = exc_info.value.errors()
        assert any("pct" in str(e.get("loc", "")) for e in errors)

    def test_category_penetration_rate_invalid_rejected(self):
        """mark 2: penetration_rate 越界 -0.1 触发 422"""
        with pytest.raises(ValidationError) as exc_info:
            CategoryDistributionItem(
                name="面膜", user_count=100, gmv=50000.0, pct=0.5,
                penetration_rate=-0.1,
            )
        errors = exc_info.value.errors()
        assert any("penetration_rate" in str(e.get("loc", "")) for e in errors)

    def test_category_member_ratio_invalid_rejected(self):
        """mark 3: member_ratio 越界 1.2 触发 422"""
        with pytest.raises(ValidationError) as exc_info:
            CategoryDistributionItem(
                name="面膜", user_count=100, gmv=50000.0, pct=0.5,
                member_ratio=1.2,
            )
        errors = exc_info.value.errors()
        assert any("member_ratio" in str(e.get("loc", "")) for e in errors)


class TestMetricsContractMark:
    """metrics.py × 3 mark 字段: TrendData.member_ratios / ly_amounts / ly_member_ratios"""

    def test_metrics_member_ratios_invalid_rejected(self):
        """mark 1: member_ratios 元素 > 1 (ratio 越界, 0-1 decimal) 触发 422.
        Sprint 27 治根: member_ratios 改 RatioField 0-1, 跟 Sprint 13+ 0-1 ratio 严守契约一致.
        之前 150.0 是 percentage 越界 (0-100), 治根后 1.5 是 ratio 越界 (0-1).
        """
        with pytest.raises(ValidationError) as exc_info:
            TrendData(
                metric_type="GSV", dates=["2026-01-01"], amounts=[1000.0],
                member_ratios=[1.5],  # 越界 RatioField 0-1
            )
        errors = exc_info.value.errors()
        assert any("member_ratios" in str(e.get("loc", "")) for e in errors)

    def test_metrics_ly_amounts_negative_rejected(self):
        """mark 2: ly_amounts 元素 < 0 (金额应 >= 0) 触发 422"""
        with pytest.raises(ValidationError) as exc_info:
            TrendData(
                metric_type="GSV", dates=["2026-01-01"], amounts=[1000.0],
                ly_amounts=[-100.0],  # 负金额越界
            )
        errors = exc_info.value.errors()
        assert any("ly_amounts" in str(e.get("loc", "")) for e in errors)

    def test_metrics_ly_member_ratios_invalid_rejected(self):
        """mark 3: ly_member_ratios 元素 > 1 触发 422 (Sprint 27 治根 0-1 decimal)."""
        with pytest.raises(ValidationError) as exc_info:
            TrendData(
                metric_type="GSV", dates=["2026-01-01"], amounts=[1000.0],
                ly_member_ratios=[1.5],  # 越界 RatioField 0-1
            )
        errors = exc_info.value.errors()
        assert any("ly_member_ratios" in str(e.get("loc", "")) for e in errors)


class TestHealthContractMark:
    """health.py × 3 mark 字段: ValueTierDefinition.gsv_ratio / TierFlowRow.repurchase_gsv_ratio_current / CustomerSegmentItem.gsv_ratio"""

    def test_health_value_tier_gsv_ratio_invalid_rejected(self):
        """mark 1: ValueTierDefinition.gsv_ratio 越界 1.5 触发 422"""
        with pytest.raises(ValidationError) as exc_info:
            ValueTierDefinition(
                tier_code="S", tier_name="超级用户", user_count=100,
                gsv=50000.0, gsv_ratio=1.5,
            )
        errors = exc_info.value.errors()
        assert any("gsv_ratio" in str(e.get("loc", "")) for e in errors)

    def test_health_tier_flow_gsv_ratio_invalid_rejected(self):
        """mark 2: TierFlowRow.repurchase_gsv_ratio_current 越界 1.3 触发 422"""
        with pytest.raises(ValidationError) as exc_info:
            TierFlowRow(
                tier_segment="S-高频",
                repurchase_gsv_ratio_current=1.3,
            )
        errors = exc_info.value.errors()
        assert any("repurchase_gsv_ratio_current" in str(e.get("loc", "")) for e in errors)

    def test_health_customer_segment_gsv_ratio_invalid_rejected(self):
        """mark 3: CustomerSegmentItem.gsv_ratio 越界 1.8 触发 422"""
        with pytest.raises(ValidationError) as exc_info:
            CustomerSegmentItem(
                segment_code="S-high", segment_name="超级用户",
                value_tier="S", frequency_tier="high", user_count=100,
                gsv=50000.0, gsv_ratio=1.8, avg_order_value=500.0,
                avg_orders_per_user=2.0, suggested_action="维护", priority=1,
            )
        errors = exc_info.value.errors()
        assert any("gsv_ratio" in str(e.get("loc", "")) for e in errors)


class TestB2BaselineHappyPath:
    """Baseline: 合法值应该接受 (治根不破老 happy path)"""

    def test_category_all_legitimate_values(self):
        """category 3 mark 全部合法值"""
        item = CategoryDistributionItem(
            name="面膜", user_count=100, gmv=50000.0, pct=0.42,
            penetration_rate=0.15, member_ratio=0.38,
        )
        assert item.pct == 0.42
        assert item.penetration_rate == 0.15
        assert item.member_ratio == 0.38

    def test_metrics_all_legitimate_values(self):
        """metrics 3 mark 全部合法值"""
        td = TrendData(
            metric_type="GSV", dates=["2026-01-01"], amounts=[1000.0],
            member_ratios=[0.5346], ly_amounts=[800.0], ly_member_ratios=[0.4838],
        )
        assert td.member_ratios == [0.5346]
        assert td.ly_amounts == [800.0]
        assert td.ly_member_ratios == [0.4838]

    def test_health_all_legitimate_values(self):
        """health 3 mark 全部合法值"""
        vtd = ValueTierDefinition(
            tier_code="S", tier_name="超级用户", user_count=100,
            gsv=50000.0, gsv_ratio=0.42,
        )
        assert vtd.gsv_ratio == 0.42

        tfr = TierFlowRow(
            tier_segment="S-高频",
            repurchase_gsv_ratio_current=0.35,
        )
        assert tfr.repurchase_gsv_ratio_current == 0.35

        csi = CustomerSegmentItem(
            segment_code="S-high", segment_name="超级用户",
            value_tier="S", frequency_tier="high", user_count=100,
            gsv=50000.0, gsv_ratio=0.42, avg_order_value=500.0,
            avg_orders_per_user=2.0, suggested_action="维护", priority=1,
        )
        assert csi.gsv_ratio == 0.42
