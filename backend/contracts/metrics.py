"""Sample CRM - Pydantic 契约模型"""
from __future__ import annotations
from typing import List, Dict, Annotated  # Sprint 16.5 B2 试点: Annotated for element-wise
from pydantic import BaseModel, Field
from .common import DateRangeResponse
from .types import RatioField  # Sprint 14 A.1

class OverviewMetrics(BaseModel):
    metric_type: str
    date_range: DateRangeResponse
    amount: float = Field(..., description="GMV 或 GSV 金额")
    order_count: int
    avg_order_value: float
    new_users: int
    old_users: int
    new_user_amount: float
    old_user_amount: float
    member_amount: float
    member_count: int
    member_order_count: int
    old_user_ratio: RatioField = Field(..., description="老客金额占比 0-1 decimal (e.g. 0.42 = 42%)")
    new_user_ratio: RatioField = Field(..., description="新客金额占比 0-1 decimal")
    member_ratio: RatioField = Field(..., description="会员金额占比 0-1 decimal")
    member_avg_order_value: float = Field(default=0.0, description="会员客单价(AUS)")
    member_premium: float = Field(default=0.0, description="会员溢价 %（会员AUS/全店AUS）")
    mom_change: Dict[str, float]
    yoy_change: Dict[str, float]


class TrendData(BaseModel):
    metric_type: str
    dates: List[str]
    amounts: List[float]
    # Sprint 27 治根: member_ratios / ly_member_ratios 从 0-100 percentage (已 ×100) 改为 0-1 decimal,
    # 跟 CLAUDE.md Ratio Convention (*_ratio 必须 RatioField 0-1) + Sprint 14.5 OverviewMetrics.member_ratio
    # 治根路线一致。Sprint 16.5 B2 试点时 0-100 范围是错把 percentage 当 ratio, 治根后 caller 传 0-1 decimal,
    # 前端展示层 (AudienceView.vue tooltip / Y 轴 formatter) 自己 ×100 格式化。
    # Pydantic v2: List[Annotated[T, Field(...)]] 支持 element-wise 约束 (TypeAdapter 解析时生效)
    # 注: 直接 List["RatioField"] 不会触发 element-wise 约束 (前向引用解析为 float, Field 丢失), 必须 Annotated
    member_ratios: List[Annotated[float, Field(ge=0.0, le=1.0)]] = Field(default_factory=list, description="今年会员GSV占比 0-1 decimal (e.g. 0.5346 = 53.46%)")
    ly_amounts: List[Annotated[float, Field(ge=0.0)]] = Field(default_factory=list, description="去年同周期金额 (>=0)")
    ly_member_ratios: List[Annotated[float, Field(ge=0.0, le=1.0)]] = Field(default_factory=list, description="去年同周期会员GSV占比 0-1 decimal (e.g. 0.4838 = 48.38%)")
    # Sprint 27 借机补: overall_member_ratio / overall_member_ratio_ly 之前是 dead data 未标 RatioField,
    # Sprint 16.5 B2 试点 9 字段没覆盖到这 2 个 (跟 OverviewMetrics.member_ratio 同语义), 借本次治根一起补,
    # 避免 Sprint 17 #120 全量 9 contract audit 返工。range 0-1 跟 Sprint 14.5 member_ratio 一致。
    overall_member_ratio: "RatioField" = Field(default=0.0, description="整体会员GSV占比 0-1 decimal (e.g. 0.5346 = 53.46%)")
    overall_member_ratio_ly: "RatioField" = Field(default=0.0, description="去年同周期整体会员GSV占比 0-1 decimal")

