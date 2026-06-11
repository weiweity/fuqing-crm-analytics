"""芙清 CRM - Pydantic 契约模型"""
from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field
from .common import DateRangeResponse
from .types import RatioField, PercentageField, PpField  # Sprint 17 B2 全量 audit

class BreakdownRequest(BaseModel):
    """一键拆解请求 v2"""
    target_gmv: float = Field(..., description="全店GSV目标（元）")
    activity_start: str = Field(..., description="活动开始日期 YYYY-MM-DD")
    activity_end: str = Field(..., description="活动结束日期 YYYY-MM-DD")
    last_year_start: Optional[str] = Field(default=None, description="去年同期开始 YYYY-MM-DD（不传则自动推算）")
    last_year_end: Optional[str] = Field(default=None, description="去年同期结束 YYYY-MM-DD（不传则自动推算）")
    # Sprint 17 B2 全量 audit: 0-1 decimal ratio 字段补 RatioField 标注
    old_customer_ratio_target: Optional["RatioField"] = Field(default=0.6, description="老客占比目标（默认60%）")
    breakdown_mode: str = Field(default="forward", description="拆解模式：forward(顺拆) 或 reverse(倒拆)")


# ── 老客 R区间明细 ──

class BreakdownRIntervalRow(BaseModel):
    """老客R区间×F段拆解明细（顺拆）"""
    r_interval: str = Field(..., description="R区间标签")
    f_segment: str = Field(..., description="F段：F>1 或 F=1")
    user_count: int = Field(..., description="当前该区间用户数")
    # Sprint 17 B2 全量 audit: ratio 字段补 RatioField 标注
    ly_repurchase_rate: "RatioField" = Field(..., description="去年同期该区间回购率 0-1 decimal")
    est_repurchase_rate: "RatioField" = Field(..., description="预估回购率（经活动系数调整）0-1 decimal")
    est_aus: float = Field(..., description="预估客单价")
    est_gmv: float = Field(..., description="预估GMV")
    ly_total_users: int = Field(default=0, description="去年同期该区间总人数")
    ly_repurchased_users: int = Field(default=0, description="去年同期该区间回购人数")


class BreakdownRIntervalReverseRow(BaseModel):
    """老客R区间×F段拆解明细（倒拆）"""
    r_interval: str = Field(..., description="R区间标签")
    f_segment: str = Field(..., description="F段：F>1 或 F=1")
    current_users: int = Field(..., description="当前该区间用户数")
    # Sprint 17 B2 全量 audit: ratio 字段补 RatioField 标注
    est_repurchase_rate: "RatioField" = Field(..., description="预估回购率 0-1 decimal")
    est_aus: float = Field(..., description="预估客单价")
    interval_target_gmv: float = Field(..., description="该区间目标GMV")
    needed_users: int = Field(..., description="所需用户数")
    user_gap: int = Field(..., description="用户数缺口")
    ly_repurchase_rate: "RatioField" = Field(default=0, description="去年回购率参考 0-1 decimal")
    ly_total_users: int = Field(default=0, description="去年该区间总人数")


class BreakdownOldCustomer(BaseModel):
    """老客拆解结果 v2"""
    old_users_total: int = Field(..., description="老客总人数")
    old_gmv_target: float = Field(..., description="老客目标GSV")
    old_gmv_estimate: Optional[float] = Field(default=None, description="老客预估GSV（顺拆有值，倒拆为None）")
    old_gmv_gap: Optional[float] = Field(default=None, description="老客gap（顺拆有值，倒拆为None）")
    r_interval_breakdown: List = Field(default_factory=list, description="R区间×F段拆解明细")


# ── 新客渠道明细 ──

class BreakdownChannelNewRow(BaseModel):
    """新客渠道拆解明细（顺拆）"""
    channel: str = Field(..., description="渠道名")
    ly_new_users: int = Field(..., description="去年同期新客人数")
    est_new_users: int = Field(..., description="预估新客人数")
    ly_new_aus: float = Field(..., description="去年同期新客客单价")
    est_new_aus: float = Field(..., description="预估新客客单价")
    est_new_gmv: float = Field(..., description="预估新客GSV")


class BreakdownChannelNewReverseRow(BaseModel):
    """新客渠道拆解明细（倒拆）"""
    channel: str = Field(..., description="渠道名")
    ly_new_users: int = Field(..., description="去年同期新客人数")
    ly_new_aus: float = Field(..., description="去年同期新客客单价")
    channel_target_gmv: float = Field(..., description="该渠道目标GSV")
    needed_users: int = Field(..., description="所需新客人数")
    user_gap: int = Field(..., description="新客人数缺口")


class BreakdownNewCustomer(BaseModel):
    """新客拆解结果 v2"""
    new_users_total: Optional[int] = Field(default=None, description="新客总人数（顺拆有值）")
    new_gmv_target: float = Field(..., description="新客目标GSV")
    new_gmv_estimate: Optional[float] = Field(default=None, description="新客预估GSV（顺拆有值）")
    new_gmv_gap: Optional[float] = Field(default=None, description="新客gap（顺拆有值）")
    channel_breakdown: List = Field(default_factory=list, description="新客渠道拆解明细")
    uv_reference: int = Field(default=0, description="参考UV")
    # Sprint 17 B2 全量 audit: 0-1 decimal ratio 字段补 RatioField 标注
    member_join_rate: "RatioField" = Field(default=0.0, description="参考入会率 0-1 decimal")
    needed_uv: Optional[int] = Field(default=None, description="所需UV（倒拆）")
    uv_gap: Optional[int] = Field(default=None, description="UV缺口（倒拆）")


# ── 通用 ──

class BreakdownGapSuggestion(BaseModel):
    """补gap建议"""
    dimension: str = Field(..., description="维度：老客/新客/总店")
    gap_amount: Optional[float] = Field(default=None, description="gap金额（顺拆）")
    gap_users: Optional[int] = Field(default=None, description="gap人数（倒拆）")
    uv_gap: Optional[int] = Field(default=None, description="UV缺口（倒拆新客）")
    suggestions: List[str] = Field(default_factory=list, description="建议列表")
    priority: str = Field(default="P1", description="优先级 P0/P1/P2")


class BreakdownMeta(BaseModel):
    """拆解元数据"""
    activity_type: str = Field(..., description="活动类型")
    repurchase_adjustment: float = Field(..., description="回购率调整系数")
    metric_type: str = Field(default="GSV", description="指标类型（固定GSV）")


class BreakdownLogic(BaseModel):
    """拆解逻辑说明（前端展示公式和知识引用）"""
    old_customer_formula: str = Field(..., description="老客拆解公式")
    old_customer_source: str = Field(..., description="老客拆解知识来源")
    new_customer_formula: str = Field(..., description="新客拆解公式")
    new_customer_source: str = Field(..., description="新客拆解知识来源")


class BreakdownResponse(BaseModel):
    """一键拆解响应 v2"""
    mode: str = Field(..., description="拆解模式：forward 或 reverse")
    mode_label: str = Field(..., description="拆解模式中文标签")
    target_gmv: float = Field(..., description="目标GSV")
    total_estimate: Optional[float] = Field(default=None, description="总预估GSV（顺拆有值，倒拆为None）")
    total_gap: Optional[float] = Field(default=None, description="总gap（顺拆有值，倒拆为None）")
    # Sprint 18 #141: gap_ratio 真实 0-1 decimal ratio, 用 RatioField
    gap_ratio: Optional["RatioField"] = Field(default=None, description="gap占比（顺拆有值）0-1 decimal")
    old_customer: BreakdownOldCustomer
    new_customer: BreakdownNewCustomer
    suggestions: List[BreakdownGapSuggestion]
    activity_period: DateRangeResponse
    reference_period: DateRangeResponse
    meta: BreakdownMeta = Field(..., description="拆解元数据")
    breakdown_logic: BreakdownLogic = Field(..., description="拆解逻辑说明")

