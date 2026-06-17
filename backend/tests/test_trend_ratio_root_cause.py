"""Sprint 27 治根专项: TrendData member_ratios ×100 双 Bug

背景:
- 用户报告: 人群看板 → 日趋势 → "全店GSV与会员占比" 折线图 tooltip 显示 5346.0%, 期望 53.46%
- 根因: backend/services/metrics/overview.py:453,461 service 层 ×100 返 0-100 percentage,
        违反 CLAUDE.md Ratio Convention (*_ratio 字段必须 0-1 decimal).
- 前端 AudienceView.vue:1409 tooltip formatter 注释说 "API ratio 返 0-1 decimal", 但实际拿到 53.46,
  formatter ×100 后变 5346.0.

治根路线 (跟 Sprint 14.5 OverviewMetrics.member_ratio 一致):
- service: 返 0-1 decimal (round(_, 4))
- contract: RatioField / List[Annotated[float, Field(ge=0, le=1)]]
- 前端 tooltip / Y 轴 formatter: 自 ×100 显示

本测试覆盖治根后的契约不变量, 防回归 (e.g. 有人改回 ×100 立即 422 报警).
"""
import pytest
from pydantic import ValidationError

from backend.contracts.metrics import TrendData
from backend.contracts.metrics import OverviewMetrics  # Sprint 27 借机补 RatioField


class TestTrendMemberRatiosSprint27:
    """TrendData.member_ratios / ly_member_ratios Sprint 27 治根契约"""

    def test_member_ratios_accept_0_1_decimal(self):
        """mark 1: 0.5346 (53.46%) 应被 accept (caller 传 0-1 decimal 正确路径)"""
        td = TrendData(
            metric_type="GSV", dates=["2026-01-01"], amounts=[1000.0],
            member_ratios=[0.5346],
        )
        assert td.member_ratios == [0.5346]

    def test_member_ratios_reject_old_percentage(self):
        """mark 2: 53.46 (老 percentage 值) 应被 422 拦截 (防回归).

        之前 service ×100 返 53.46, Sprint 27 治根后 0-1 contract 不接受 53.46.
        如果未来有人错把 service 改回 ×100, 此测试 422 失败 → 立即报警.
        """
        with pytest.raises(ValidationError) as exc_info:
            TrendData(
                metric_type="GSV", dates=["2026-01-01"], amounts=[1000.0],
                member_ratios=[53.46],  # 治根前老 percentage 值
            )
        errors = exc_info.value.errors()
        assert any("member_ratios" in str(e.get("loc", "")) for e in errors)

    def test_ly_member_ratios_accept_0_1_decimal(self):
        """mark 3: 0.4838 (48.38%) 应被 accept"""
        td = TrendData(
            metric_type="GSV", dates=["2026-01-01"], amounts=[1000.0],
            ly_member_ratios=[0.4838],
        )
        assert td.ly_member_ratios == [0.4838]

    def test_member_ratios_boundary_zero_accept(self):
        """mark 4: 边界 0.0 (0%) 应 accept"""
        td = TrendData(
            metric_type="GSV", dates=["2026-01-01"], amounts=[1000.0],
            member_ratios=[0.0],
        )
        assert td.member_ratios == [0.0]

    def test_member_ratios_boundary_one_accept(self):
        """mark 5: 边界 1.0 (100%) 应 accept"""
        td = TrendData(
            metric_type="GSV", dates=["2026-01-01"], amounts=[1000.0],
            member_ratios=[1.0],
        )
        assert td.member_ratios == [1.0]

    def test_member_ratios_negative_rejected(self):
        """mark 6: 负值应被 422 拦截 (ratio 不可能为负)"""
        with pytest.raises(ValidationError) as exc_info:
            TrendData(
                metric_type="GSV", dates=["2026-01-01"], amounts=[1000.0],
                member_ratios=[-0.1],
            )
        errors = exc_info.value.errors()
        assert any("member_ratios" in str(e.get("loc", "")) for e in errors)


class TestOverallMemberRatioSprint27:
    """TrendData.overall_member_ratio / overall_member_ratio_ly Sprint 27 借机补 RatioField"""

    def test_overall_member_ratio_accept_0_1_decimal(self):
        """mark 1: 0.5346 accept"""
        td = TrendData(
            metric_type="GSV", dates=["2026-01-01"], amounts=[1000.0],
            overall_member_ratio=0.5346, overall_member_ratio_ly=0.4838,
        )
        assert td.overall_member_ratio == 0.5346
        assert td.overall_member_ratio_ly == 0.4838

    def test_overall_member_ratio_reject_old_percentage(self):
        """mark 2: 53.46 (老 percentage 值) 应被 422 拦截"""
        with pytest.raises(ValidationError) as exc_info:
            TrendData(
                metric_type="GSV", dates=["2026-01-01"], amounts=[1000.0],
                overall_member_ratio=53.46,
            )
        errors = exc_info.value.errors()
        assert any("overall_member_ratio" in str(e.get("loc", "")) for e in errors)

    def test_overall_member_ratio_default_zero(self):
        """mark 3: 默认值 0.0 accept (TrendData 兼容老 caller 不传)"""
        td = TrendData(
            metric_type="GSV", dates=["2026-01-01"], amounts=[1000.0],
        )
        assert td.overall_member_ratio == 0.0
        assert td.overall_member_ratio_ly == 0.0


class TestOverviewMetricsMemberRatioConsistency:
    """OverviewMetrics.member_ratio 跟 TrendData.member_ratios 一致性 (都 0-1 decimal)

    用 model_construct 绕过 date_range / old_user_ratio / new_user_ratio / mom_change /
    yoy_change 等必填字段 (这些不是本测试关注点). 仅验证 member_ratio 接受 0-1 decimal,
    防 Sprint 27 治根后有人误把 member_ratio 改成 PercentageField.
    """

    def test_overview_member_ratio_accept_0_1_decimal(self):
        """OverviewMetrics.member_ratio 是 RatioField (Sprint 14.5), 0.5346 accept"""
        om = OverviewMetrics.model_construct(
            metric_type="GSV",
            member_ratio=0.5346,  # 0-1 ratio (Sprint 14.5 治根)
        )
        assert om.member_ratio == 0.5346

    def test_overview_member_ratio_reject_old_percentage(self):
        """OverviewMetrics.member_ratio 拒绝 53.46 (老 percentage 值, 防回归)"""
        with pytest.raises(ValidationError) as exc_info:
            OverviewMetrics.model_construct(member_ratio=53.46)
            # model_construct 跳过 validation, 改用 full validate
            OverviewMetrics.model_validate({
                "metric_type": "GSV", "member_ratio": 53.46,
                # 提供其他必填字段最小集
                "date_range": {"start_date": "2026-01-01", "end_date": "2026-01-31"},
                "amount": 0, "order_count": 0, "avg_order_value": 0,
                "new_users": 0, "old_users": 0,
                "new_user_amount": 0, "old_user_amount": 0,
                "member_amount": 0, "member_count": 0, "member_order_count": 0,
                "old_user_ratio": 0, "new_user_ratio": 0,
                "mom_change": {}, "yoy_change": {},
            })
        errors = exc_info.value.errors()
        assert any("member_ratio" in str(e.get("loc", "")) for e in errors)
