"""芙清 CRM - Pydantic 契约模型"""
from typing import Optional, List, Dict
from pydantic import BaseModel, Field

class SamplingChannelSummary(BaseModel):
    """派样渠道汇总"""
    channel: str
    sample_users: int
    repurchase_users_7d: int
    repurchase_users_30d: int
    repurchase_users_60d: int
    repurchase_rate_7d: float
    repurchase_rate_30d: float
    repurchase_rate_60d: float
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
    repurchase_rate: float
    repurchase_gsv: float
    repurchase_aus: float
    same_category_repurchase: int
    same_category_rate: float


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
    lock_rate: float
    converted_users: int
    conversion_rate: float
    lock_gsv: float
    lock_aus: float
    new_locked_users: int
    new_locked_ratio: float
    new_converted_users: int
    new_conversion_rate: float
    new_lock_gsv: float
    new_lock_aus: float


class SamplingLockYOY(BaseModel):
    """锁权分析同比数据"""
    total_uv: Optional[float] = None
    locked_users: Optional[float] = None
    lock_rate: Optional[float] = None
    converted_users: Optional[float] = None
    conversion_rate: Optional[float] = None
    lock_gsv: Optional[float] = None
    lock_aus: Optional[float] = None
    new_locked_users: Optional[float] = None
    new_locked_ratio: Optional[float] = None
    new_converted_users: Optional[float] = None
    new_conversion_rate: Optional[float] = None
    new_lock_gsv: Optional[float] = None
    new_lock_aus: Optional[float] = None


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
    lock_rate: float
    new_locked_users: int
    new_locked_ratio: float
    old_locked_users: int
    old_locked_ratio: float
    converted_users: int
    conversion_rate: float
    conv_gsv: float
    conv_aus: float
    new_converted_users: int
    new_conversion_rate: float
    new_conv_gsv: float
    new_conv_aus: float
    old_converted_users: int
    old_conversion_rate: float


class RollingYOY(BaseModel):
    """滚动对比 YoY"""
    total_uv: Optional[float] = None
    locked_users: Optional[float] = None
    lock_rate: Optional[float] = None
    new_locked_users: Optional[float] = None
    new_locked_ratio: Optional[float] = None
    converted_users: Optional[float] = None
    conversion_rate: Optional[float] = None
    conv_gsv: Optional[float] = None
    conv_aus: Optional[float] = None
    new_converted_users: Optional[float] = None
    new_conversion_rate: Optional[float] = None
    new_conv_gsv: Optional[float] = None
    new_conv_aus: Optional[float] = None


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

