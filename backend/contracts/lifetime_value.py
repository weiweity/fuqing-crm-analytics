"""Sprint 143 LTV contract."""

from pydantic import BaseModel, Field

from .types import PercentageField


class LifetimeValueSummary(BaseModel):
    """用户生命周期价值 (LTV) 90/180/365 天汇总."""

    cohort_date: str = Field(..., description="派样 cohort 日期 YYYY-MM-DD")
    user_count: int = Field(..., ge=0, description="cohort 用户数")
    ltv_90d_avg: float = Field(default=0.0, ge=0.0, description="90 天累计 GSV 平均值")
    ltv_180d_avg: float = Field(default=0.0, ge=0.0, description="180 天累计 GSV 平均值")
    ltv_365d_avg: float = Field(default=0.0, ge=0.0, description="365 天累计 GSV 平均值")
    ltv_90d_median: float = Field(default=0.0, ge=0.0, description="90 天累计 GSV 中位数")
    ltv_180d_median: float = Field(default=0.0, ge=0.0, description="180 天累计 GSV 中位数")
    ltv_365d_median: float = Field(default=0.0, ge=0.0, description="365 天累计 GSV 中位数")
    ltv_90d_yoy_pct: PercentageField = Field(default=0.0, description="90 天 LTV YoY percentage")
    ltv_180d_yoy_pct: PercentageField = Field(default=0.0, description="180 天 LTV YoY percentage")
    ltv_365d_yoy_pct: PercentageField = Field(default=0.0, description="365 天 LTV YoY percentage")
