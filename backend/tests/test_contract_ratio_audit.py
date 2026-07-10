"""Sprint 30.3 #120 B2 全量 9 contract audit 剩余字段补标测试.

背景:
- Sprint 16.5 B2 试点 (3 contract × 3 mark) + Sprint 17 B2 全量 (13 contract × ≥ 2 mark)
  治根 category/metrics/health 部分 ratio 字段
- Sprint 30.3 #120 收口: 补 linter R1-R5 真正支持的剩余字段 — 主要是 List 嵌套 List 元素约束
  (CohortRetentionResponse 4 个 List[List[Optional[Annotated[float, Field(ge, le)]]]])

模式 (跟 Sprint 16.5/17 一致):
  - 0-1 decimal 字段 -> RatioField (CLAUDE.md §强制规则 表 `*_ratio`/`*_rate`)
  - 0-1B 字段 -> PercentageField (yoy_absolute 返 percentage)
  - -100~+100 pp 差 -> PpField (字段名 _yoy / _ppt)
  - 倍数 / 变化率 (lift / 提升度) -> 保留 float, 不约束 0-1
  - List[Optional[T]] 元素约束 -> 必须 List[Optional[Annotated[T, Field(...)]]]
    (Linter R5 覆盖, 不允许 List[RatioField] 没 Annotated 包装)

测试范围 (Sprint 30.3 实际落地):
  - health.py: CohortRetentionResponse 4 个 List[List[Optional[Annotated[float, Field(ge, le)]]]]
    (B1+B2 List 模式, 真正触发 Pydantic element-wise 422 拦截)
"""
import pytest
from pydantic import ValidationError

from backend.contracts.health import CohortRetentionResponse


# ============================================================
# health.py CohortRetentionResponse (4 List[List[Optional[Annotated]]] element-wise)
# ============================================================

class TestCohortRetentionElementWise:
    """health.py × CohortRetentionResponse: 4 个 List[Optional[Annotated[float, Field(ge=0, le=1)]]]
    元素 0-1 越界触发 422, None 透传 (cohort 周期不齐)
    """

    def test_matrix_valid(self):
        """matrix 0-1 decimal 合法值"""
        resp = CohortRetentionResponse(
            cohort_months=["2026-01", "2026-02"],
            periods=["M0", "M1"],
            matrix=[[0.5, 0.3], [0.6, None]],  # None 透传 (M1 周期未到)
            avg_by_period=[0.55, 0.3],
        )
        assert resp.matrix[0][0] == 0.5
        assert resp.matrix[1][1] is None  # None 透传

    def test_matrix_element_invalid_rejected(self):
        """matrix 元素越界 1.5 触发 422"""
        with pytest.raises(ValidationError):
            CohortRetentionResponse(
                cohort_months=["2026-01"],
                periods=["M0"],
                matrix=[[1.5]],  # 越界
            )

    def test_avg_by_period_element_invalid_rejected(self):
        """avg_by_period 元素越界 1.5 触发 422"""
        with pytest.raises(ValidationError):
            CohortRetentionResponse(
                cohort_months=["2026-01"],
                periods=["M0"],
                matrix=[[0.5]],
                avg_by_period=[1.5],  # 越界
            )

    def test_ly_matrix_element_invalid_rejected(self):
        """ly_matrix 元素越界 1.5 触发 422"""
        with pytest.raises(ValidationError):
            CohortRetentionResponse(
                cohort_months=["2026-01"],
                periods=["M0"],
                matrix=[[0.5]],
                avg_by_period=[0.5],
                ly_matrix=[[1.5]],  # 越界
            )

    def test_ly_avg_by_period_element_invalid_rejected(self):
        """ly_avg_by_period 元素越界 1.5 触发 422"""
        with pytest.raises(ValidationError):
            CohortRetentionResponse(
                cohort_months=["2026-01"],
                periods=["M0"],
                matrix=[[0.5]],
                avg_by_period=[0.5],
                ly_matrix=[[0.5]],
                ly_avg_by_period=[1.5],  # 越界
            )

    def test_negative_element_rejected(self):
        """matrix 元素负值触发 422 (0-1 范围)"""
        with pytest.raises(ValidationError):
            CohortRetentionResponse(
                cohort_months=["2026-01"],
                periods=["M0"],
                matrix=[[-0.1]],
            )

    def test_above_one_element_rejected(self):
        """ly_matrix 元素 > 1 触发 422"""
        with pytest.raises(ValidationError):
            CohortRetentionResponse(
                cohort_months=["2026-01"],
                periods=["M0"],
                matrix=[[0.5]],
                avg_by_period=[0.5],
                ly_matrix=[[1.2]],  # 越界
            )

    def test_empty_matrix_valid(self):
        """空 matrix 合法 (无 cohort)"""
        resp = CohortRetentionResponse(
            cohort_months=[],
            periods=[],
        )
        assert resp.matrix == []
        assert resp.avg_by_period == []
        assert resp.ly_matrix == []
        assert resp.ly_avg_by_period == []


# ============================================================
# 回归测试 - Sprint 16.5/17 B2 试点 (确保没回退)
# ============================================================

class TestRegressionNoRevert:
    """Sprint 16.5 B2 试点 + Sprint 17 B2 全量字段保持合规 (防止本次 Sprint 30.3 改坏)"""

    def test_health_overview_old_customer_gsv_ratio_still_ratio(self):
        """回归: HealthOverviewMetrics.old_customer_gsv_ratio 仍是 RatioField (Sprint 16.5 B2 试点治根)"""
        from backend.contracts.health import HealthOverviewMetrics
        m = HealthOverviewMetrics(
            analysis_date="2026-01-01", period_days=30,
            all_store_repurchase_rate=0.3, same_product_repurchase_rate=0.2,
            period_repurchase_users=100,
            old_gsv=10000.0, old_users=200, old_customer_gsv_ratio=0.6,
            old_customer_aus=100.0,
            member_old_gsv=5000.0, member_old_users=100, member_old_customer_gsv_ratio=0.5,
            member_old_customer_aus=50.0,
            health_score=80.0, health_level="healthy",
        )
        assert m.old_customer_gsv_ratio == 0.6
        # 越界拦截依然有效
        with pytest.raises(ValidationError):
            HealthOverviewMetrics(
                analysis_date="2026-01-01", period_days=30,
                all_store_repurchase_rate=0.3, same_product_repurchase_rate=0.2,
                period_repurchase_users=100,
                old_gsv=10000.0, old_users=200, old_customer_gsv_ratio=1.5,  # 越界
                old_customer_aus=100.0,
                member_old_gsv=5000.0, member_old_users=100, member_old_customer_gsv_ratio=0.5,
                member_old_customer_aus=50.0,
                health_score=80.0, health_level="healthy",
            )


# ============================================================
# Sprint 30.3 #120 B2 audit 4 类型覆盖 (Task #21)
# ============================================================

class TestRatioConventionTypeCoverage:
    """Sprint 30.3 Task #21: 4 个 Ratio Convention 强类型每种至少 1 case 验证 Pydantic 422 拦截.

    覆盖 (跟 CLAUDE.md §强制规则 表格一致):
    - RatioField: 0-1 decimal (e.g. 0.42 = 42%)
    - PercentageField: 0-1B 兼容 YOY 异常值 (e.g. yoy_absolute *100 万倍涨)
    - PpField: -100~+100 pp 差 (e.g. 5.28 = +5.28pp)
    - Annotated[float, Field(ge, le)]: 自定义范围 (e.g. cohort 0-1, day7_rate 0-1)

    用既有 Sprint 16.5/17 B2 试点字段做 import-based test, 不需新增 contract 字段, 零 hook 还原风险.
    """

    def test_ratio_field_coverage(self):
        """Type 1: RatioField (0-1 decimal) 越界 1.5 触发 422"""
        from backend.contracts.health import HealthOverviewMetrics
        with pytest.raises(ValidationError) as exc_info:
            HealthOverviewMetrics(
                analysis_date="2026-01-01", period_days=30,
                all_store_repurchase_rate=0.3, same_product_repurchase_rate=0.2,
                period_repurchase_users=100,
                old_gsv=10000.0, old_users=200, old_customer_gsv_ratio=1.5,  # 越界 0-1
                old_customer_aus=100.0,
                member_old_gsv=5000.0, member_old_users=100, member_old_customer_gsv_ratio=0.5,
                member_old_customer_aus=50.0,
                health_score=80.0, health_level="healthy",
            )
        assert any("old_customer_gsv_ratio" in str(e.get("loc", "")) for e in exc_info.value.errors())

    def test_percentage_field_coverage(self):
        """Type 2: PercentageField (0-1B 兼容 YOY 异常值) 越界 ±1T 触发 422"""
        from backend.contracts.health import HealthOverviewMetrics
        with pytest.raises(ValidationError) as exc_info:
            HealthOverviewMetrics(
                analysis_date="2026-01-01", period_days=30,
                all_store_repurchase_rate=0.3, same_product_repurchase_rate=0.2,
                period_repurchase_users=100,
                old_gsv=10000.0, old_users=200, old_customer_gsv_ratio=0.6,
                old_customer_aus=100.0,
                member_old_gsv=5000.0, member_old_users=100, member_old_customer_gsv_ratio=0.5,
                member_old_customer_aus=50.0,
                health_score=80.0, health_level="healthy",
                yoy_old_gsv=2e12,  # 越界 PercentageField ge=-1T (Sprint 15 治根 1B→1T 兼容 YOY)
            )
        assert any("yoy_old_gsv" in str(e.get("loc", "")) for e in exc_info.value.errors())

    def test_pp_field_coverage(self):
        """Type 3: PpField (L4.81 治本契约: -1e10~+1e10 raw ratio diff) 越界 +1e11 触发 422"""
        from backend.contracts.health import HealthOverviewMetrics
        with pytest.raises(ValidationError) as exc_info:
            HealthOverviewMetrics(
                analysis_date="2026-01-01", period_days=30,
                all_store_repurchase_rate=0.3, same_product_repurchase_rate=0.2,
                period_repurchase_users=100,
                old_gsv=10000.0, old_users=200, old_customer_gsv_ratio=0.6,
                old_customer_aus=100.0,
                member_old_gsv=5000.0, member_old_users=100, member_old_customer_gsv_ratio=0.5,
                member_old_customer_aus=50.0,
                health_score=80.0, health_level="healthy",
                yoy_old_customer_gsv_ratio_ppt=1e11,  # 越界 PpField L4.81 -1e10~+1e10 raw ratio diff
            )
        assert any("yoy_old_customer_gsv_ratio_ppt" in str(e.get("loc", "")) for e in exc_info.value.errors())

    def test_annotated_float_field_coverage(self):
        """Type 4: Annotated[float, Field(ge, le)] (自定义范围) 越界触发 422"""
        # Sprint 30.3 实际增量: CohortRetentionResponse.matrix 元素约束
        # (List[List[Optional[Annotated[float, Field(ge=0.0, le=1.0)]]]])
        with pytest.raises(ValidationError) as exc_info:
            CohortRetentionResponse(
                cohort_months=["2026-01"],
                periods=["M0"],
                matrix=[[2.5]],  # 越界 Annotated[float, Field(ge=0, le=1)]
            )
        assert any("matrix" in str(e.get("loc", "")) for e in exc_info.value.errors())
