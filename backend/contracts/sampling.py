"""Sample CRM - Pydantic 契约模型"""
from __future__ import annotations
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from .types import RatioField, PercentageField, PpField  # Sprint 17 B2 全量 audit

class SamplingChannelSummary(BaseModel):
    """派样渠道汇总"""
    channel: str
    sample_users: int
    # Sprint 140: 统一窗口字段（任意 window_days 由 service 参数化计算）
    repurchase_users: int = 0
    repurchase_rate: "RatioField" = 0.0
    repurchase_gsv: float = 0.0
    repurchase_aus: float = 0.0
    # Sprint 139 保留: 正装/非正装 split
    full_repurchase_users: int = 0
    full_repurchase_gsv: float = 0.0
    full_repurchase_aus: float = 0.0
    full_repurchase_rate: "RatioField" = 0.0
    nonfull_repurchase_users: int = 0
    nonfull_repurchase_gsv: float = 0.0
    nonfull_repurchase_aus: float = 0.0
    # Sprint 144: ROI 卡片同比/环比，percentage 已 *100，pp 为百分点差。
    # 注: PercentageField/PpField 顶部已直接 import, 不需要 string forward reference
    # (CLAUDE.md §B1+B2 + Sprint 18 #142 保留 RatioField string ref 是 Pydantic v2 兼容性考虑)
    repurchase_users_yoy_pct: Optional[PercentageField] = None
    repurchase_gsv_yoy_pct: Optional[PercentageField] = None
    repurchase_rate_yoy_pp: Optional[PpField] = None
    full_repurchase_users_yoy_pct: Optional[PercentageField] = None
    full_repurchase_gsv_yoy_pct: Optional[PercentageField] = None
    full_repurchase_rate_yoy_pp: Optional[PpField] = None
    repurchase_aus_yoy_pct: Optional[PercentageField] = None
    full_repurchase_aus_yoy_pct: Optional[PercentageField] = None
    nonfull_repurchase_gsv_yoy_pct: Optional[PercentageField] = None
    repurchase_users_mom_pct: Optional[PercentageField] = None
    repurchase_gsv_mom_pct: Optional[PercentageField] = None
    repurchase_rate_mom_pp: Optional[PpField] = None
    full_repurchase_users_mom_pct: Optional[PercentageField] = None
    full_repurchase_gsv_mom_pct: Optional[PercentageField] = None
    full_repurchase_rate_mom_pp: Optional[PpField] = None
    repurchase_aus_mom_pct: Optional[PercentageField] = None
    full_repurchase_aus_mom_pct: Optional[PercentageField] = None
    nonfull_repurchase_gsv_mom_pct: Optional[PercentageField] = None


class SamplingLevelSummary(BaseModel):
    """派样 level 二级聚合（channel × level_value）."""

    channel: str = Field(..., description="渠道")
    level: str = Field(..., description="聚合维度字段")
    level_value: str = Field(..., description="level 聚合维度值")
    sample_users: int = Field(..., description="派样人数")
    repurchase_users: int = Field(default=0, description="回购人数")
    repurchase_rate: "RatioField" = Field(default=0.0, description="回购率")
    repurchase_gsv: float = Field(default=0.0, description="回购 GSV")
    repurchase_aus: float = Field(default=0.0, description="客单价")
    full_repurchase_users: int = 0
    full_repurchase_gsv: float = 0.0
    full_repurchase_aus: float = 0.0
    full_repurchase_rate: "RatioField" = 0.0
    nonfull_repurchase_users: int = 0
    nonfull_repurchase_gsv: float = 0.0
    nonfull_repurchase_aus: float = 0.0


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
    # Sprint 139: 正装/非正装 split
    full_repurchase_users: int = 0
    full_repurchase_rate: "RatioField" = 0.0
    full_repurchase_gsv: float = 0.0
    full_repurchase_aus: float = 0.0
    nonfull_repurchase_users: int = 0
    nonfull_repurchase_gsv: float = 0.0
    nonfull_repurchase_aus: float = 0.0


class SamplingROITimeRange(BaseModel):
    """派样ROI时间范围"""
    start: str
    end: str
    window_days: int


class SamplingRepurchaseBucket(BaseModel):
    """Sprint 144 回购周期分布桶."""
    bucket: str
    users: int = 0
    gsv: float = 0.0
    aus: float = 0.0


class SamplingRepurchaseDistribution(BaseModel):
    """Sprint 144 回购周期分布响应."""
    buckets: List[SamplingRepurchaseBucket] = Field(default_factory=list)
    window_days: int = 90


class QualityFlag(BaseModel):
    """DQM 守卫警告 (Sprint 139 引入, Sprint 141 补字段语义)

    字段语义 (Sprint 140 起 window_days 可变 1-90):
    - code: 警告代码 (e.g. POSIZE_RATIO_LOW)
    - severity: 'warning' | 'error', 当前 Sprint 139 实现仅 warning
    - message: 人读 warning 描述, 已含当前 window_days 上下文
    - posize_ratio: 当前 window_days 内正装 GSV / 任意 GSV (0-1)
    - total_posize_gsv: 当前 window_days 内正装 GSV 总和
    - total_gsv: 当前 window_days 内任意回购 GSV 总和
    """
    code: str = Field(..., description="警告代码 (e.g. POSIZE_RATIO_LOW)")
    severity: str = Field(..., description="'warning' | 'error'")
    message: str = Field(..., description="人读 warning 描述, 已含当前 window_days 上下文")
    posize_ratio: Optional["RatioField"] = Field(default=None, description="当前 window_days 内正装 GSV / 任意 GSV")
    total_posize_gsv: Optional[float] = Field(default=None, description="当前 window_days 内正装 GSV 总和")
    total_gsv: Optional[float] = Field(default=None, description="当前 window_days 内任意回购 GSV 总和")


class SamplingROIResponse(BaseModel):
    """派样ROI分析响应"""
    summary: Dict[str, List[SamplingChannelSummary]]
    category_breakdown: List[SamplingCategoryRow]
    time_range: SamplingROITimeRange
    quality_flags: List[QualityFlag] = Field(default_factory=list)
    summary_by_level: Dict[str, List[SamplingLevelSummary]] = Field(
        default_factory=dict,
        description="level 二级聚合 {level_value: [SamplingLevelSummary]}",
    )


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
    # 跟 SamplingLockYOY 同问题: Sprint 18 #141 误标 RatioField, 实际 YOY 可超 1
    new_locked_ratio: Optional[float] = None
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
