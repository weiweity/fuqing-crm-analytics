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
    # Sprint 205: 跟 _add_compare_metrics() 输出对齐，避免 response_model 过滤新字段。
    sample_users_yoy_pct: Optional[PercentageField] = None
    repurchase_users_yoy_pct: Optional[PercentageField] = None
    repurchase_gsv_yoy_pct: Optional[PercentageField] = None
    repurchase_rate_yoy_pp: Optional[PpField] = None
    full_repurchase_users_yoy_pct: Optional[PercentageField] = None
    full_repurchase_gsv_yoy_pct: Optional[PercentageField] = None
    full_repurchase_rate_yoy_pp: Optional[PpField] = None
    repurchase_aus_yoy_pct: Optional[PercentageField] = None
    full_repurchase_aus_yoy_pct: Optional[PercentageField] = None
    nonfull_repurchase_gsv_yoy_pct: Optional[PercentageField] = None
    nonfull_repurchase_users_yoy_pct: Optional[PercentageField] = None
    sample_users_mom_pct: Optional[PercentageField] = None
    repurchase_users_mom_pct: Optional[PercentageField] = None
    repurchase_gsv_mom_pct: Optional[PercentageField] = None
    repurchase_rate_mom_pp: Optional[PpField] = None
    full_repurchase_users_mom_pct: Optional[PercentageField] = None
    full_repurchase_gsv_mom_pct: Optional[PercentageField] = None
    full_repurchase_rate_mom_pp: Optional[PpField] = None
    repurchase_aus_mom_pct: Optional[PercentageField] = None
    full_repurchase_aus_mom_pct: Optional[PercentageField] = None
    nonfull_repurchase_gsv_mom_pct: Optional[PercentageField] = None
    nonfull_repurchase_users_mom_pct: Optional[PercentageField] = None


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
    # Sprint 154: 02 板块新增 YOY/MOM 字段 (跟 SamplingChannelSummary Sprint 144 模式 stable)
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
    # Sprint 175 Q5: YOY/MOM 同比字段 (跨 sprint 复用 _add_compare_metrics 模式)
    # Sprint 176 强类型补标: 跟 sibling SamplingChannelSummary (L27-35) 对齐 B1+B2 契约
    # _pct 后缀 → PercentageField (0-1B, 含 YOY 异常值), _pp 后缀 → PpField (-100~+100 pp)
    repurchase_users_yoy_pct: Optional[PercentageField] = None
    repurchase_gsv_yoy_pct: Optional[PercentageField] = None
    repurchase_rate_yoy_pp: Optional[PpField] = None
    full_repurchase_users_yoy_pct: Optional[PercentageField] = None
    full_repurchase_gsv_yoy_pct: Optional[PercentageField] = None
    full_repurchase_rate_yoy_pp: Optional[PpField] = None
    repurchase_aus_yoy_pct: Optional[PercentageField] = None
    full_repurchase_aus_yoy_pct: Optional[PercentageField] = None
    nonfull_repurchase_gsv_yoy_pct: Optional[PercentageField] = None


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


class SamplingRepurchaseTrackingBucket(BaseModel):
    """Sprint 169 回购周期跟踪单桶 (3 年对比).

    - bucket: 桶标签 (0-7d / 8-30d / 31-60d / 61-90d)
    - year_label: 年份标签 (cur/ly/prev2 对应 "2026年"/"2025年"/"2024年")
    - rate: 该桶该年的"回购周期分布率" = 派样后回购正装人数 / 总派样人数 (0-1 decimal)
    - year_range: 该年实际期间 (起, 止), 跟 SamplingROIResponse.time_range 一致
    """
    bucket: str
    year_label: str
    rate: RatioField = 0.0
    year_range_start: str
    year_range_end: str


class SamplingRepurchaseTrackingResponse(BaseModel):
    """Sprint 169 回购周期跟踪响应.

    - buckets: 所有年份所有桶的扁平列表
    - year_labels: 按年份顺序 (cur→ly→prev2), 跟健康页一致
    - time_range: 当前年份的窗口范围 (Sprint 144 同)
    - window_days: 回购窗口天数
    """
    buckets: List[SamplingRepurchaseTrackingBucket] = Field(default_factory=list)
    year_labels: List[str] = Field(default_factory=list)
    time_range: SamplingROITimeRange
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
