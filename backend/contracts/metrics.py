"""芙清 CRM - Pydantic 契约模型"""
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
    # Sprint 16.5 B2 试点治根: 3 个 List 字段补标注 (跟 audience.py B1 模式一致)
    # 修法: caller 错传 (e.g. percentage >100) 在 API 入口 ValidationError, 不再 500
    # Pydantic v2: List[Annotated[T, Field(...)]] 支持 element-wise 约束 (TypeAdapter 解析时生效)
    # 注: 直接 List["PercentageField"] 不会触发 element-wise 约束 (前向引用解析为 float, Field 丢失), 必须 Annotated
    member_ratios: List[Annotated[float, Field(ge=0.0, le=100.0)]] = Field(default_factory=list, description="今年会员占比 % (已 *100, 0-100 范围)")
    ly_amounts: List[Annotated[float, Field(ge=0.0)]] = Field(default_factory=list, description="去年同周期金额 (>=0)")
    ly_member_ratios: List[Annotated[float, Field(ge=0.0, le=100.0)]] = Field(default_factory=list, description="去年同周期会员占比 % (已 *100, 0-100 范围)")

