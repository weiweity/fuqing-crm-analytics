"""Sprint 17 B2 全量 audit 13 contract 字段补标测试.

背景:
- Sprint 16.5 B2 试点: 3 contract (category/metrics/health) × 3 mark 字段 = 9 mark 治根
- Sprint 17 B2 全量: 扩到 13 contract, 标完所有 ratio/percentage/pp 字段
- 模式: 跟 Sprint 16.5 B2 试点 + Sprint 15 B1 (audience.py 28 字段) 一致
  - ratio 字段 (0-1 decimal) → RatioField
  - percentage 字段 (0-100) → PercentageField
  - pp 差字段 (-100~+100) → PpField
  - List[inner] 必须 List[Annotated[inner, Field(...)]] 触发 element-wise 约束

测试覆盖 13 contract (除已 B2-done 的 category/metrics/health) × ≥ 2 mark:
- asset.py: ProductClassRepurchase.repurchase_rate / ly_repurchase_rate / repurchase_rate_yoy / gsv_yoy
- audience.py: AudiencePeriodMetrics.old_gsv_ratio / AudienceRow.old_gsv_ratio / AudienceRow.yoy_old_gsv_ratio_ppt
- breakdown.py: BreakdownRIntervalRow.est_repurchase_rate / BreakdownRequest.old_customer_ratio_target
- churn.py: ChurnDistributionResponse.high_risk_rate / ChurnTableRow.mom_change_rate / ChurnTableRow.top_churn_dest1_ratio
- common.py: WoolPartyBreakdown.type1_ratio / DualAxisLineData.wool_party_ratios
- flow.py: FlowMatrixCell.ratio / AssociationItem.ratio
- geo.py: GeoDistributionItem.user_ratio / gmv_ratio
- rfm.py: RFMCategoryDrilldownRow.repurchase_rate_current / RFMCategoryDrilldownSummary.overall_repurchase_rate / DecliningCategoryItem.yoy_repurchase_rate
- sampling.py: SamplingChannelSummary.repurchase_rate_7d / SamplingLockYearData.lock_rate / RollingYearMetrics.lock_rate
- visitor.py: VisitorSummaryResponse.member_join_rate / VisitorDailyTrendItem.member_join_rate
"""
import pytest
from pydantic import ValidationError

from backend.contracts.asset import ProductClassRepurchase
from backend.contracts.audience import AudiencePeriodMetrics, AudienceRow
from backend.contracts.breakdown import (
    BreakdownRequest,
    BreakdownRIntervalRow,
    BreakdownNewCustomer,
)
from backend.contracts.churn import (
    ChurnDistributionResponse,
    ChurnTableRow,
    CategoryDailyTrendResponse,
)
from backend.contracts.common import (
    WoolPartyBreakdown,
    DualAxisLineData,
)
from backend.contracts.flow import FlowMatrixCell, AssociationItem
from backend.contracts.geo import GeoDistributionItem
from backend.contracts.rfm import (
    DecliningCategoryItem,
    RFMCategoryDrilldownRow,
    RFMCategoryDrilldownSummary,
    TopDriverItem,
)
from backend.contracts.sampling import (
    SamplingChannelSummary,
    SamplingLockYearData,
    SamplingLockYOY,
    RollingYearMetrics,
)
from backend.contracts.visitor import VisitorSummaryResponse, VisitorDailyTrendItem


# ============================================================
# 1. asset.py × 4 mark 字段
# ============================================================

class TestAssetContractMark:
    """asset.py × 4 mark 字段: ProductClassRepurchase.repurchase_rate / ly_repurchase_rate / repurchase_rate_yoy / gsv_yoy"""

    def test_asset_repurchase_rate_valid_ratio(self):
        """mark 1: repurchase_rate 0-1 decimal 合法值接受"""
        item = ProductClassRepurchase(
            product_class="面膜", total_buyers=100, repurchase_users=30,
            repurchase_rate=0.3, median_days=30, p25_days=15, p75_days=60,
            avg_order_value=200.0, gsv=10000.0,
            repurchase_order_value=250.0, repurchase_gsv=7500.0,
        )
        assert item.repurchase_rate == 0.3

    def test_asset_repurchase_rate_invalid_rejected(self):
        """mark 1: repurchase_rate 越界 1.5 触发 422"""
        with pytest.raises(ValidationError) as exc_info:
            ProductClassRepurchase(
                product_class="面膜", total_buyers=100, repurchase_users=30,
                repurchase_rate=1.5, median_days=30, p25_days=15, p75_days=60,
                avg_order_value=200.0, gsv=10000.0,
                repurchase_order_value=250.0, repurchase_gsv=7500.0,
            )
        assert any("repurchase_rate" in str(e.get("loc", "")) for e in exc_info.value.errors())

    def test_asset_ly_repurchase_rate_valid(self):
        """mark 2: ly_repurchase_rate Optional[RatioField] 合法值"""
        item = ProductClassRepurchase(
            product_class="面膜", total_buyers=100, repurchase_users=30,
            repurchase_rate=0.3, ly_repurchase_rate=0.25, median_days=30,
            p25_days=15, p75_days=60, avg_order_value=200.0, gsv=10000.0,
            repurchase_order_value=250.0, repurchase_gsv=7500.0,
        )
        assert item.ly_repurchase_rate == 0.25

    def test_asset_ly_repurchase_rate_invalid_rejected(self):
        """mark 2: ly_repurchase_rate 越界 -0.1 触发 422"""
        with pytest.raises(ValidationError):
            ProductClassRepurchase(
                product_class="面膜", total_buyers=100, repurchase_users=30,
                repurchase_rate=0.3, ly_repurchase_rate=-0.1, median_days=30,
                p25_days=15, p75_days=60, avg_order_value=200.0, gsv=10000.0,
                repurchase_order_value=250.0, repurchase_gsv=7500.0,
            )

    def test_asset_repurchase_rate_yoy_invalid_pp_rejected(self):
        """mark 3: repurchase_rate_yoy (PpField) 越界 +150 触发 422"""
        with pytest.raises(ValidationError):
            ProductClassRepurchase(
                product_class="面膜", total_buyers=100, repurchase_users=30,
                repurchase_rate=0.3, repurchase_rate_yoy=150.0,
                median_days=30, p25_days=15, p75_days=60,
                avg_order_value=200.0, gsv=10000.0,
                repurchase_order_value=250.0, repurchase_gsv=7500.0,
            )

    def test_asset_gsv_yoy_accepts_any_value(self):
        """mark 4: gsv_yoy (float) 接受任何值 (含 > 1, < 0)
        2026-06-13 改: 实际值是 (cur-ly)/ly 变化率, 可负可超 1, 改 float 兼容.
        0-1 强约束 (原 RatioField) 跟实际语义不符."""
        # 正值 (正常增长)
        item = ProductClassRepurchase(
            product_class="面膜", total_buyers=100, repurchase_users=30,
            repurchase_rate=0.3, gsv_yoy=1.5, median_days=30,
            p25_days=15, p75_days=60, avg_order_value=200.0, gsv=10000.0,
            repurchase_order_value=250.0, repurchase_gsv=7500.0,
        )
        assert item.gsv_yoy == 1.5
        # 负值 (衰退)
        item2 = ProductClassRepurchase(
            product_class="面膜", total_buyers=100, repurchase_users=30,
            repurchase_rate=0.3, gsv_yoy=-0.5, median_days=30,
            p25_days=15, p75_days=60, avg_order_value=200.0, gsv=10000.0,
            repurchase_order_value=250.0, repurchase_gsv=7500.0,
        )
        assert item2.gsv_yoy == -0.5
        # 超大正值 (新品类从 0 涨起)
        item3 = ProductClassRepurchase(
            product_class="面膜", total_buyers=100, repurchase_users=30,
            repurchase_rate=0.3, gsv_yoy=42.94, median_days=30,
            p25_days=15, p75_days=60, avg_order_value=200.0, gsv=10000.0,
            repurchase_order_value=250.0, repurchase_gsv=7500.0,
        )
        assert item3.gsv_yoy == 42.94

    def test_asset_all_legitimate_values(self):
        """all 4 mark 字段合法值全接受"""
        item = ProductClassRepurchase(
            product_class="面膜", total_buyers=100, repurchase_users=30,
            repurchase_rate=0.3, ly_repurchase_rate=0.25,
            repurchase_rate_yoy=5.0,  # +5pp
            median_days=30, p25_days=15, p75_days=60,
            avg_order_value=200.0, gsv=10000.0,
            repurchase_order_value=250.0, repurchase_gsv=7500.0,
            gsv_yoy=0.15,  # +15%
        )
        assert item.repurchase_rate == 0.3
        assert item.ly_repurchase_rate == 0.25
        assert item.repurchase_rate_yoy == 5.0
        assert item.gsv_yoy == 0.15


# ============================================================
# 2. audience.py × 4 mark 字段
# ============================================================

class TestAudienceContractMark:
    """audience.py × 4 mark 字段: AudiencePeriodMetrics.old_gsv_ratio / AudienceRow.old_gsv_ratio / yoy_*_ratio (PpField) / ChannelGSVRow (already done)"""

    def test_audience_period_old_gsv_ratio_valid(self):
        """mark 1: AudiencePeriodMetrics.old_gsv_ratio 合法值接受"""
        m = AudiencePeriodMetrics(old_gsv_ratio=0.6)
        assert m.old_gsv_ratio == 0.6

    def test_audience_period_old_gsv_ratio_invalid_rejected(self):
        """mark 1: AudiencePeriodMetrics.old_gsv_ratio 越界 1.2 触发 422"""
        with pytest.raises(ValidationError):
            AudiencePeriodMetrics(old_gsv_ratio=1.2)

    def test_audience_row_old_gsv_ratio_invalid_rejected(self):
        """mark 2: AudienceRow.old_gsv_ratio 越界 -0.1 触发 422"""
        with pytest.raises(ValidationError):
            AudienceRow(
                dimension="channel", gsv_users=100, gsv=10000.0, aus=100.0,
                old_users=60, old_gsv=6000.0, old_aus=100.0,
                old_gsv_ratio=-0.1,  # 越界
                old_users_ratio=0.6,
                new_users=40, new_gsv=4000.0, new_aus=100.0,
                new_gsv_ratio=0.4, new_users_ratio=0.4,
                member_users=50, member_gsv=5000.0, member_aus=100.0,
                member_gsv_ratio=0.5, member_users_ratio=0.5,
                member_old_users=30, member_old_gsv=3000.0, member_old_aus=100.0,
                member_old_gsv_ratio=0.3, member_old_users_ratio=0.3,
                member_new_users=20, member_new_gsv=2000.0, member_new_aus=100.0,
                member_new_gsv_ratio=0.2, member_new_users_ratio=0.2,
                # comp/prev2/yoy 留 None
            )

    def test_audience_row_yoy_old_gsv_ratio_ppt_invalid_rejected(self):
        """mark 3: AudienceRow.yoy_old_gsv_ratio_ppt (PpField) 越界 +150 触发 422"""
        with pytest.raises(ValidationError):
            AudienceRow(
                dimension="channel", gsv_users=100, gsv=10000.0, aus=100.0,
                old_users=60, old_gsv=6000.0, old_aus=100.0,
                old_gsv_ratio=0.6, old_users_ratio=0.6,
                new_users=40, new_gsv=4000.0, new_aus=100.0,
                new_gsv_ratio=0.4, new_users_ratio=0.4,
                member_users=50, member_gsv=5000.0, member_aus=100.0,
                member_gsv_ratio=0.5, member_users_ratio=0.5,
                member_old_users=30, member_old_gsv=3000.0, member_old_aus=100.0,
                member_old_gsv_ratio=0.3, member_old_users_ratio=0.3,
                member_new_users=20, member_new_gsv=2000.0, member_new_aus=100.0,
                member_new_gsv_ratio=0.2, member_new_users_ratio=0.2,
                yoy_old_gsv_ratio_ppt=150.0,  # 越界
            )

    def test_audience_row_yoy_gsv_invalid_rejected(self):
        """mark 4: AudienceRow.yoy_gsv (PercentageField) 越界 -2e9 触发 422"""
        with pytest.raises(ValidationError):
            AudienceRow(
                dimension="channel", gsv_users=100, gsv=10000.0, aus=100.0,
                old_users=60, old_gsv=6000.0, old_aus=100.0,
                old_gsv_ratio=0.6, old_users_ratio=0.6,
                new_users=40, new_gsv=4000.0, new_aus=100.0,
                new_gsv_ratio=0.4, new_users_ratio=0.4,
                member_users=50, member_gsv=5000.0, member_aus=100.0,
                member_gsv_ratio=0.5, member_users_ratio=0.5,
                member_old_users=30, member_old_gsv=3000.0, member_old_aus=100.0,
                member_old_gsv_ratio=0.3, member_old_users_ratio=0.3,
                member_new_users=20, member_new_gsv=2000.0, member_new_aus=100.0,
                member_new_gsv_ratio=0.2, member_new_users_ratio=0.2,
                yoy_gsv=-2_000_000_000.0,  # 越界 (PercentageField ge=-1B)
            )

    def test_audience_all_legitimate_values(self):
        """all mark 字段合法值全接受"""
        row = AudienceRow(
            dimension="channel", gsv_users=100, gsv=10000.0, aus=100.0,
            old_users=60, old_gsv=6000.0, old_aus=100.0,
            old_gsv_ratio=0.6, old_users_ratio=0.6,
            new_users=40, new_gsv=4000.0, new_aus=100.0,
            new_gsv_ratio=0.4, new_users_ratio=0.4,
            member_users=50, member_gsv=5000.0, member_aus=100.0,
            member_gsv_ratio=0.5, member_users_ratio=0.5,
            member_old_users=30, member_old_gsv=3000.0, member_old_aus=100.0,
            member_old_gsv_ratio=0.3, member_old_users_ratio=0.3,
            member_new_users=20, member_new_gsv=2000.0, member_new_aus=100.0,
            member_new_gsv_ratio=0.2, member_new_users_ratio=0.2,
            # comp
            comp_gsv_users=80, comp_gsv=8000.0, comp_aus=100.0,
            comp_old_users=50, comp_old_gsv=5000.0, comp_old_aus=100.0,
            comp_old_gsv_ratio=0.625, comp_old_users_ratio=0.625,
            comp_new_users=30, comp_new_gsv=3000.0, comp_new_aus=100.0,
            comp_new_gsv_ratio=0.375, comp_new_users_ratio=0.375,
            comp_member_users=40, comp_member_gsv=4000.0, comp_member_aus=100.0,
            comp_member_gsv_ratio=0.5, comp_member_users_ratio=0.5,
            comp_member_old_users=25, comp_member_old_gsv=2500.0, comp_member_old_aus=100.0,
            comp_member_old_gsv_ratio=0.5, comp_member_old_users_ratio=0.5,
            comp_member_new_users=15, comp_member_new_gsv=1500.0, comp_member_new_aus=100.0,
            comp_member_new_gsv_ratio=0.5, comp_member_new_users_ratio=0.5,
            # prev2
            prev2_gsv_users=70, prev2_gsv=7000.0, prev2_aus=100.0,
            prev2_old_users=45, prev2_old_gsv=4500.0, prev2_old_aus=100.0,
            prev2_old_gsv_ratio=0.643, prev2_old_users_ratio=0.643,
            prev2_new_users=25, prev2_new_gsv=2500.0, prev2_new_aus=100.0,
            prev2_new_gsv_ratio=0.357, prev2_new_users_ratio=0.357,
            prev2_member_users=35, prev2_member_gsv=3500.0, prev2_member_aus=100.0,
            prev2_member_gsv_ratio=0.5, prev2_member_users_ratio=0.5,
            prev2_member_old_users=22, prev2_member_old_gsv=2200.0, prev2_member_old_aus=100.0,
            prev2_member_old_gsv_ratio=0.5, prev2_member_old_users_ratio=0.5,
            prev2_member_new_users=13, prev2_member_new_gsv=1300.0, prev2_member_new_aus=100.0,
            prev2_member_new_gsv_ratio=0.5, prev2_member_new_users_ratio=0.5,
            # yoy
            yoy_gsv=25.0, yoy_old_gsv_ratio_ppt=5.0,
        )
        assert row.yoy_gsv == 25.0
        assert row.yoy_old_gsv_ratio_ppt == 5.0


# ============================================================
# 3. breakdown.py × 3 mark 字段
# ============================================================

class TestBreakdownContractMark:
    """breakdown.py × 3 mark 字段: BreakdownRequest.old_customer_ratio_target / BreakdownRIntervalRow.est_repurchase_rate / BreakdownNewCustomer.member_join_rate"""

    def test_breakdown_old_customer_ratio_target_valid(self):
        """mark 1: old_customer_ratio_target 0-1 decimal 合法值"""
        req = BreakdownRequest(
            target_gmv=100000.0, activity_start="2026-01-01", activity_end="2026-01-31",
            old_customer_ratio_target=0.6,
        )
        assert req.old_customer_ratio_target == 0.6

    def test_breakdown_old_customer_ratio_target_invalid_rejected(self):
        """mark 1: old_customer_ratio_target 越界 1.5 触发 422"""
        with pytest.raises(ValidationError):
            BreakdownRequest(
                target_gmv=100000.0, activity_start="2026-01-01", activity_end="2026-01-31",
                old_customer_ratio_target=1.5,
            )

    def test_breakdown_est_repurchase_rate_valid(self):
        """mark 2: BreakdownRIntervalRow.est_repurchase_rate 合法值"""
        row = BreakdownRIntervalRow(
            r_interval="R1", f_segment="F>1", user_count=100,
            ly_repurchase_rate=0.3, est_repurchase_rate=0.35,
            est_aus=100.0, est_gmv=3500.0,
        )
        assert row.est_repurchase_rate == 0.35

    def test_breakdown_est_repurchase_rate_invalid_rejected(self):
        """mark 2: est_repurchase_rate 越界 -0.1 触发 422"""
        with pytest.raises(ValidationError):
            BreakdownRIntervalRow(
                r_interval="R1", f_segment="F>1", user_count=100,
                ly_repurchase_rate=0.3, est_repurchase_rate=-0.1,
                est_aus=100.0, est_gmv=3500.0,
            )

    def test_breakdown_member_join_rate_invalid_rejected(self):
        """mark 3: BreakdownNewCustomer.member_join_rate (RatioField) 越界 1.5 触发 422"""
        with pytest.raises(ValidationError):
            BreakdownNewCustomer(new_gmv_target=10000.0, member_join_rate=1.5)

    def test_breakdown_all_legitimate_values(self):
        """all mark 字段合法值全接受"""
        nc = BreakdownNewCustomer(
            new_gmv_target=10000.0, member_join_rate=0.3,
        )
        assert nc.member_join_rate == 0.3


# ============================================================
# 4. churn.py × 4 mark 字段
# ============================================================

class TestChurnContractMark:
    """churn.py × 4 mark 字段: ChurnDistributionResponse.high_risk_rate / ChurnTableRow.mom_change_rate + top_churn_dest1_ratio / CategoryDailyTrendResponse.new_customer_ratio (List element-wise)"""

    def test_churn_high_risk_rate_valid(self):
        """mark 1: high_risk_rate 0-1 decimal 合法值"""
        from backend.contracts.churn import ChurnSegmentItem
        resp = ChurnDistributionResponse(
            date="2026-01-01", churn_mode="m12",
            total_users=1000, high_risk=100, medium_risk=300, low_risk=600,
            high_risk_rate=0.1,
            by_segment={"S1": ChurnSegmentItem(name="S1", high=10, medium=30, low=60)},
        )
        assert resp.high_risk_rate == 0.1

    def test_churn_high_risk_rate_invalid_rejected(self):
        """mark 1: high_risk_rate 越界 1.5 触发 422"""
        with pytest.raises(ValidationError):
            ChurnDistributionResponse(
                date="2026-01-01", churn_mode="m12",
                total_users=1000, high_risk=100, medium_risk=300, low_risk=600,
                high_risk_rate=1.5,
            )

    def test_churn_mom_change_rate_accepts_negative(self):
        """mark 2: ChurnTableRow.mom_change_rate (float) 接受负值和超 1 值
        2026-06-13 改: 实际值是 (cur-prev)/prev 变化率, 可负, 改 float 兼容."""
        item = ChurnTableRow(
            category_name="面膜", current_users=100, previous_users=200,
            mom_change_rate=-1.0,  # 减半, 合法
            inter_churn=10, silent_churn=5,
            top_churn_dest1="其他", top_churn_dest1_ratio=0.5,
            top_churn_dest2="精华", top_churn_dest2_ratio=0.3,
            挽回建议="加大投放",
        )
        assert item.mom_change_rate == -1.0

    def test_churn_top_churn_dest1_ratio_invalid_rejected(self):
        """mark 3: ChurnTableRow.top_churn_dest1_ratio 越界 1.5 触发 422"""
        with pytest.raises(ValidationError):
            ChurnTableRow(
                category_name="面膜", current_users=100, previous_users=200,
                mom_change_rate=-0.2, inter_churn=10, silent_churn=5,
                top_churn_dest1="其他", top_churn_dest1_ratio=1.5,
                top_churn_dest2="精华", top_churn_dest2_ratio=0.3,
                挽回建议="加大投放",
            )

    def test_churn_new_customer_ratio_list_invalid_rejected(self):
        """mark 4: CategoryDailyTrendResponse.new_customer_ratio List element-wise 越界"""
        with pytest.raises(ValidationError):
            CategoryDailyTrendResponse(
                category_id="面膜", category_name="面膜",
                dates=["2026-01-01", "2026-01-02"],
                gmv=[1000.0, 2000.0], user_count=[100, 200], aus=[10.0, 10.0],
                new_customer_ratio=[1.5, 0.4],  # 1.5 越界
            )

    def test_churn_all_legitimate_values(self):
        """all mark 字段合法值全接受"""
        trend = CategoryDailyTrendResponse(
            category_id="面膜", category_name="面膜",
            dates=["2026-01-01", "2026-01-02"],
            gmv=[1000.0, 2000.0], user_count=[100, 200], aus=[10.0, 10.0],
            new_customer_ratio=[0.3, 0.4],
        )
        assert trend.new_customer_ratio == [0.3, 0.4]


# ============================================================
# 5. common.py × 2 mark 字段
# ============================================================

class TestCommonContractMark:
    """common.py × 2 mark 字段: WoolPartyBreakdown.type1_ratio / DualAxisLineData.wool_party_ratios (List element-wise)"""

    def test_common_type1_ratio_valid(self):
        """mark 1: type1_ratio 0-1 decimal 合法值"""
        wp = WoolPartyBreakdown(
            type1_count=10, type2_count=20, total_count=30,
            type1_ratio=10/30, type2_ratio=20/30,
        )
        assert wp.type1_ratio == pytest.approx(10/30)

    def test_common_type1_ratio_accepts_above_one(self):
        """mark 1: type1_ratio (float) 接受 > 1 值
        2026-06-13 改: 实际值是 count/total_users, 可超 1 (单用户跨多品类), 改 float 兼容."""
        wp = WoolPartyBreakdown(
            type1_count=10, type2_count=20, total_count=30,
            type1_ratio=1.5,  # > 1 合法 (跨品类用户重复计)
            type2_ratio=0.5,
        )
        assert wp.type1_ratio == 1.5
        # 同时接受 0 边界
        wp2 = WoolPartyBreakdown(
            type1_count=0, type2_count=0, total_count=0,
            type1_ratio=0.0, type2_ratio=0.0,
        )
        assert wp2.type1_ratio == 0.0

    def test_common_wool_party_ratios_list_invalid_rejected(self):
        """mark 2: DualAxisLineData.wool_party_ratios List element-wise 越界"""
        with pytest.raises(ValidationError):
            DualAxisLineData(
                categories=["A", "B"],
                wool_party_ratios=[1.5, 0.2],  # 1.5 越界
                high_value_ratios=[0.1, 0.2],
            )

    def test_common_all_legitimate_values(self):
        """all mark 字段合法值全接受"""
        line = DualAxisLineData(
            categories=["A", "B"],
            wool_party_ratios=[0.1, 0.2],
            high_value_ratios=[0.3, 0.4],
        )
        assert line.wool_party_ratios == [0.1, 0.2]
        assert line.high_value_ratios == [0.3, 0.4]


# ============================================================
# 6. flow.py × 2 mark 字段
# ============================================================

class TestFlowContractMark:
    """flow.py × 2 mark 字段: FlowMatrixCell.ratio / AssociationItem.ratio"""

    def test_flow_matrix_cell_ratio_valid(self):
        """mark 1: FlowMatrixCell.ratio 0-1 decimal 合法值"""
        cell = FlowMatrixCell(
            source_category="A", target_category="B", user_count=100, ratio=0.5,
            concentration_risk=False,
        )
        assert cell.ratio == 0.5

    def test_flow_matrix_cell_ratio_invalid_rejected(self):
        """mark 1: FlowMatrixCell.ratio 越界 1.5 触发 422"""
        with pytest.raises(ValidationError):
            FlowMatrixCell(
                source_category="A", target_category="B", user_count=100, ratio=1.5,
                concentration_risk=False,
            )

    def test_flow_association_ratio_invalid_rejected(self):
        """mark 2: AssociationItem.ratio 越界 1.5 触发 422"""
        with pytest.raises(ValidationError):
            AssociationItem(
                category_name="A", user_count=100, order_count=200, gsv=10000.0,
                ratio=1.5, avg_days_gap=10.0,
            )

    def test_flow_all_legitimate_values(self):
        """all mark 字段合法值全接受"""
        cell = FlowMatrixCell(
            source_category="A", target_category="B", user_count=100, ratio=0.5,
            concentration_risk=False,
        )
        assert cell.ratio == 0.5


# ============================================================
# 7. geo.py × 2 mark 字段
# ============================================================

class TestGeoContractMark:
    """geo.py × 2 mark 字段: GeoDistributionItem.user_ratio / gmv_ratio"""

    def test_geo_user_ratio_valid(self):
        """mark 1: user_ratio 0-1 decimal 合法值"""
        item = GeoDistributionItem(
            name="浙江", user_count=1000, gmv=10000.0, user_ratio=0.3, gmv_ratio=0.25,
        )
        assert item.user_ratio == 0.3

    def test_geo_user_ratio_invalid_rejected(self):
        """mark 1: user_ratio 越界 1.5 触发 422"""
        with pytest.raises(ValidationError):
            GeoDistributionItem(
                name="浙江", user_count=1000, gmv=10000.0, user_ratio=1.5, gmv_ratio=0.25,
            )

    def test_geo_gmv_ratio_invalid_rejected(self):
        """mark 2: gmv_ratio 越界 1.5 触发 422"""
        with pytest.raises(ValidationError):
            GeoDistributionItem(
                name="浙江", user_count=1000, gmv=10000.0, user_ratio=0.3, gmv_ratio=1.5,
            )

    def test_geo_all_legitimate_values(self):
        """all mark 字段合法值全接受"""
        item = GeoDistributionItem(
            name="浙江", user_count=1000, gmv=10000.0, user_ratio=0.3, gmv_ratio=0.25,
        )
        assert item.user_ratio == 0.3
        assert item.gmv_ratio == 0.25


# ============================================================
# 8. rfm.py × 4 mark 字段
# ============================================================

class TestRFMContractMark:
    """rfm.py × 4 mark 字段: RFMCategoryDrilldownRow.repurchase_rate_current / DecliningCategoryItem.yoy_repurchase_rate (PpField) / RFMCategoryDrilldownSummary.overall_repurchase_rate / TopDriverItem.repurchase_rate_current"""

    def test_rfm_drilldown_repurchase_rate_invalid_rejected(self):
        """mark 1: RFMCategoryDrilldownRow.repurchase_rate_current 越界 1.5 触发 422"""
        with pytest.raises(ValidationError):
            RFMCategoryDrilldownRow(category_name="面膜", repurchase_rate_current=1.5)

    def test_rfm_declining_yoy_repurchase_rate_invalid_rejected(self):
        """mark 2: DecliningCategoryItem.yoy_repurchase_rate (PpField) 越界 +150 触发 422"""
        with pytest.raises(ValidationError):
            DecliningCategoryItem(name="面膜", yoy_repurchase_rate=150.0)

    def test_rfm_summary_overall_repurchase_rate_invalid_rejected(self):
        """mark 3: RFMCategoryDrilldownSummary.overall_repurchase_rate (RatioField) 越界 1.5 触发 422"""
        with pytest.raises(ValidationError):
            RFMCategoryDrilldownSummary(overall_repurchase_rate=1.5)

    def test_rfm_top_driver_repurchase_rate_invalid_rejected(self):
        """mark 4: TopDriverItem.repurchase_rate_current 越界 1.5 触发 422"""
        with pytest.raises(ValidationError):
            TopDriverItem(category_name="面膜", repurchase_rate_current=1.5)

    def test_rfm_all_legitimate_values(self):
        """all mark 字段合法值全接受"""
        s = RFMCategoryDrilldownSummary(
            overall_repurchase_rate=0.35,
            overall_repurchase_rate_comp=0.30,
            overall_repurchase_rate_yoy=5.0,  # +5pp
        )
        assert s.overall_repurchase_rate == 0.35
        assert s.overall_repurchase_rate_yoy == 5.0


# ============================================================
# 9. sampling.py × 4 mark 字段
# ============================================================

class TestSamplingContractMark:
    """sampling.py × 4 mark 字段: SamplingChannelSummary.repurchase_rate_7d / SamplingLockYearData.lock_rate / SamplingLockYOY.lock_rate (PpField) / RollingYearMetrics.lock_rate"""

    def test_sampling_repurchase_rate_7d_valid(self):
        """mark 1: SamplingChannelSummary.repurchase_rate_7d 0-1 decimal 合法值"""
        s = SamplingChannelSummary(
            channel="A", sample_users=100,
            repurchase_users_7d=20, repurchase_users_30d=30, repurchase_users_60d=40,
            repurchase_rate_7d=0.2, repurchase_rate_30d=0.3, repurchase_rate_60d=0.4,
            repurchase_gsv_7d=2000.0, repurchase_gsv_30d=3000.0, repurchase_gsv_60d=4000.0,
            repurchase_aus_7d=100.0, repurchase_aus_30d=100.0, repurchase_aus_60d=100.0,
        )
        assert s.repurchase_rate_7d == 0.2

    def test_sampling_repurchase_rate_invalid_rejected(self):
        """mark 1: repurchase_rate_7d 越界 1.5 触发 422"""
        with pytest.raises(ValidationError):
            SamplingChannelSummary(
                channel="A", sample_users=100,
                repurchase_users_7d=20, repurchase_users_30d=30, repurchase_users_60d=40,
                repurchase_rate_7d=1.5, repurchase_rate_30d=0.3, repurchase_rate_60d=0.4,
                repurchase_gsv_7d=2000.0, repurchase_gsv_30d=3000.0, repurchase_gsv_60d=4000.0,
                repurchase_aus_7d=100.0, repurchase_aus_30d=100.0, repurchase_aus_60d=100.0,
            )

    def test_sampling_lock_rate_invalid_rejected(self):
        """mark 2: SamplingLockYearData.lock_rate 越界 1.5 触发 422"""
        with pytest.raises(ValidationError):
            SamplingLockYearData(
                total_uv=1000, locked_users=100,
                lock_rate=1.5,  # 越界
                converted_users=50, conversion_rate=0.5,
                lock_gsv=10000.0, lock_aus=100.0,
                new_locked_users=60, new_locked_ratio=0.6,
                new_converted_users=30, new_conversion_rate=0.5,
                new_lock_gsv=6000.0, new_lock_aus=100.0,
            )

    def test_sampling_lock_yoy_lock_rate_invalid_rejected(self):
        """mark 3: SamplingLockYOY.lock_rate (PpField) 越界 +150 触发 422"""
        with pytest.raises(ValidationError):
            SamplingLockYOY(lock_rate=150.0)

    def test_sampling_rolling_lock_rate_invalid_rejected(self):
        """mark 4: RollingYearMetrics.lock_rate 越界 1.5 触发 422"""
        with pytest.raises(ValidationError):
            RollingYearMetrics(
                phase="sample", total_uv=1000, locked_users=100, lock_rate=1.5,
                new_locked_users=60, new_locked_ratio=0.6,
                old_locked_users=40, old_locked_ratio=0.4,
                converted_users=50, conversion_rate=0.5,
                conv_gsv=10000.0, conv_aus=100.0,
                new_converted_users=30, new_conversion_rate=0.5,
                new_conv_gsv=6000.0, new_conv_aus=100.0,
                old_converted_users=20, old_conversion_rate=0.5,
            )

    def test_sampling_all_legitimate_values(self):
        """all mark 字段合法值全接受"""
        s = SamplingLockYearData(
            total_uv=1000, locked_users=100,
            lock_rate=0.1, converted_users=50, conversion_rate=0.5,
            lock_gsv=10000.0, lock_aus=100.0,
            new_locked_users=60, new_locked_ratio=0.6,
            new_converted_users=30, new_conversion_rate=0.5,
            new_lock_gsv=6000.0, new_lock_aus=100.0,
        )
        assert s.lock_rate == 0.1


# ============================================================
# 10. visitor.py × 2 mark 字段
# ============================================================

class TestVisitorContractMark:
    """visitor.py × 2 mark 字段: VisitorSummaryResponse.member_join_rate (PercentageField) / VisitorDailyTrendItem.member_join_rate (PercentageField)"""

    def test_visitor_summary_member_join_rate_valid(self):
        """mark 1: VisitorSummaryResponse.member_join_rate 0-100 percentage 合法值"""
        resp = VisitorSummaryResponse(
            start_date="2026-01-01", end_date="2026-01-31",
            visitors=1000, new_members=300, member_join_rate=30.0,
            ly_visitors=800, ly_new_members=200, ly_member_join_rate=25.0,
        )
        assert resp.member_join_rate == 30.0

    def test_visitor_summary_member_join_rate_invalid_rejected(self):
        """mark 1: VisitorSummaryResponse.member_join_rate 越界 2e9 触发 422"""
        with pytest.raises(ValidationError):
            VisitorSummaryResponse(
                start_date="2026-01-01", end_date="2026-01-31",
                visitors=1000, new_members=300, member_join_rate=2_000_000_000.0,
                ly_visitors=800, ly_new_members=200, ly_member_join_rate=25.0,
            )

    def test_visitor_daily_member_join_rate_valid(self):
        """mark 2: VisitorDailyTrendItem.member_join_rate 0-100 percentage 合法值"""
        item = VisitorDailyTrendItem(
            date="2026-01-01", visitors=1000, new_members=300,
            member_join_rate=30.0,  # 30%
            ly_visitors=800, ly_new_members=200, ly_member_join_rate=25.0,
        )
        assert item.member_join_rate == 30.0

    def test_visitor_daily_member_join_rate_invalid_rejected(self):
        """mark 2: VisitorDailyTrendItem.member_join_rate 越界 2e9 触发 422"""
        with pytest.raises(ValidationError):
            VisitorDailyTrendItem(
                date="2026-01-01", visitors=1000, new_members=300,
                member_join_rate=2_000_000_000.0,  # 越界 PercentageField ge=-1B
                ly_visitors=800, ly_new_members=200, ly_member_join_rate=25.0,
            )

    def test_visitor_all_legitimate_values(self):
        """all mark 字段合法值全接受"""
        resp = VisitorSummaryResponse(
            start_date="2026-01-01", end_date="2026-01-31",
            visitors=1000, new_members=300, member_join_rate=30.0,
            ly_visitors=800, ly_new_members=200, ly_member_join_rate=25.0,
            member_join_rate_yoy=5.0,  # +5.0 pp diff
            member_join_rate_mom=2.0,
        )
        assert resp.member_join_rate == 30.0
        assert resp.member_join_rate_yoy == 5.0
