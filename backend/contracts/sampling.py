"""芙清 CRM - Pydantic 契约模型"""
from __future__ import annotations
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from .types import RatioField, PercentageField, PpField  # Sprint 17 B2 全量 audit

class SamplingChannelSummary(BaseModel):
    """派样渠道汇总"""
    channel: str
    sample_users: int
    repurchase_users_7d: int
    repurchase_users_30d: int
    repurchase_users_60d: int
    # Sprint 17 B2 全量 audit: 0-1 decimal ratio 字段补 RatioField 标注
    repurchase_rate_7d: "RatioField"
    repurchase_rate_30d: "RatioField"
    repurchase_rate_60d: "RatioField"
    repurchase_gsv_7d: float
    repurchase_gsv_30d: float
    repurchase_gsv_60d: float
    repurchase_aus_7d: float
    repurchase_aus_30d: float
    repurchase_aus_60d: float


class SamplingCategoryRow(BaseModel):
    """派样品类明细"""
    channel: str
    category: str
    sample_users: int
    repurchase_users: int
    # Sprint 17 B2 全量 audit: 0-1 decimal ratio 字段补 RatioField 标注
    repurchase_rate: "RatioField"
    repurchase_gsv: float
    repurchase_aus: float
    same_category_repurchase: int
    same_category_rate: "RatioField"


class SamplingROITimeRange(BaseModel):
    """派样ROI时间范围"""
    start: str
    end: str
    window_days: int


class SamplingROIResponse(BaseModel):
    """派样ROI分析响应"""
    summary: Dict[str, List[SamplingChannelSummary]]
    category_breakdown: List[SamplingCategoryRow]
    time_range: SamplingROITimeRange


class SamplingLockCampaignInfo(BaseModel):
    """锁权活动信息"""
    year: int
    campaign_name: str
    conversion_start: Optional[str] = None
    conversion_end: Optional[str] = None
    lock_start: Optional[str] = None
    lock_end: Optional[str] = None
    error: Optional[str] = None


class SamplingLockYearData(BaseModel):
    """锁权分析单年数据"""
    total_uv: int
    locked_users: int
    # Sprint 17 B2 全量 audit: 0-1 decimal ratio 字段补 RatioField 标注
    lock_rate: "RatioField"
    converted_users: int
    conversion_rate: "RatioField"
    lock_gsv: float
    lock_aus: float
    new_locked_users: int
    new_locked_ratio: "RatioField"
    new_converted_users: int
    new_conversion_rate: "RatioField"
    new_lock_gsv: float
    new_lock_aus: float


class SamplingLockYOY(BaseModel):
    """锁权分析同比数据 - yoy_ratio() 返 pp 差"""
    total_uv: Optional["PercentageField"] = None
    locked_users: Optional["PercentageField"] = None
    lock_rate: Optional["PpField"] = None
    converted_users: Optional["PercentageField"] = None
    conversion_rate: Optional["PpField"] = None
    lock_gsv: Optional["PercentageField"] = None
    lock_aus: Optional["PercentageField"] = None
    new_locked_users: Optional["PercentageField"] = None
    # Sprint 18 #141 之前误标 RatioField; 实际是 yoy_ratio() 返 pp 差, 但 service 返
    # (cur_ratio - ly_ratio) 后服务又 *100 放 pp, 实际值可超 1 (e.g. cur=0.55, ly=0.1 → 0.45 → 45)
    # 改 float 兼容, 不约束范围
    new_locked_ratio: Optional[float] = None
    new_converted_users: Optional["PercentageField"] = None
    new_conversion_rate: Optional["PpField"] = None
    new_lock_gsv: Optional["PercentageField"] = None
    new_lock_aus: Optional["PercentageField"] = None


class SamplingLockAnalysisResponse(BaseModel):
    """0.01锁权分析响应"""
    campaign_info: SamplingLockCampaignInfo
    current_year: SamplingLockYearData
    last_year: SamplingLockYearData
    yoy: SamplingLockYOY


# ============================================================
# 0.01派样滚动同期对比 (Rolling Comparison)
# ============================================================

class RollingYearMetrics(BaseModel):
    """单年的滚动指标"""
    phase: str = Field(..., description="当前阶段：sample(派样期) 或 conversion(转化期)")
    total_uv: int
    locked_users: int
    # Sprint 17 B2 全量 audit: 0-1 decimal ratio 字段补 RatioField 标注
    lock_rate: "RatioField"
    new_locked_users: int
    new_locked_ratio: "RatioField"
    old_locked_users: int
    old_locked_ratio: "RatioField"
    converted_users: int
    conversion_rate: "RatioField"
    conv_gsv: float
    conv_aus: float
    new_converted_users: int
    new_conversion_rate: "RatioField"
    new_conv_gsv: float
    new_conv_aus: float
    old_converted_users: int
    old_conversion_rate: "RatioField"


class RollingYOY(BaseModel):
    """滚动对比 YoY - yoy_ratio() 返 pp 差, yoy_absolute() 返 percentage"""
    total_uv: Optional["PercentageField"] = None
    locked_users: Optional["PercentageField"] = None
    lock_rate: Optional["PpField"] = None
    new_locked_users: Optional["PercentageField"] = None
    # Sprint 18 #141: new_locked_ratio 实际是 0-1 decimal ratio (safe_ratio(new_locked, locked_users))
    # 改 RatioField (0-1), 之前误标 PpField
    new_locked_ratio: Optional["RatioField"] = None
    converted_users: Optional["PercentageField"] = None
    conversion_rate: Optional["PpField"] = None
    conv_gsv: Optional["PercentageField"] = None
    conv_aus: Optional["PercentageField"] = None
    new_converted_users: Optional["PercentageField"] = None
    new_conversion_rate: Optional["PpField"] = None
    new_conv_gsv: Optional["PercentageField"] = None
    new_conv_aus: Optional["PercentageField"] = None


class RollingTimeline(BaseModel):
    """滚动时间线参数"""
    year_a_sample_start: str
    year_a_sample_end: str
    year_a_conv_start: str
    year_b_sample_start: str
    year_b_sample_end: str
    year_b_conv_start: str
    rolling_end: str
    year_b_equiv_end: str = Field(..., description="year_b 自动对齐后的等价截止日")
    T: int = Field(..., description="从 year_a 派样起始到滚动截止日的总天数")
    T_sample_a: int = Field(..., description="year_a 派样期总天数")
    T_sample_b: int = Field(..., description="year_b 派样期总天数")
    T_conv: int = Field(..., description="从 year_a 转化起始到滚动截止日的天数")


class RollingComparisonResponse(BaseModel):
    """0.01派样滚动同期对比响应"""
    year_a: RollingYearMetrics
    year_b: RollingYearMetrics
    yoy: RollingYOY
    timeline: RollingTimeline

