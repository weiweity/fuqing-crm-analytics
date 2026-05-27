"""芙清 CRM - Pydantic 契约模型"""
from typing import List, Dict
from pydantic import BaseModel, Field
from .common import DateRangeResponse

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
    old_user_ratio: float = Field(..., description="老客金额占比 %")
    new_user_ratio: float = Field(..., description="新客金额占比 %")
    member_ratio: float = Field(..., description="会员金额占比 %")
    member_avg_order_value: float = Field(default=0.0, description="会员客单价(AUS)")
    member_premium: float = Field(default=0.0, description="会员溢价 %（会员AUS/全店AUS）")
    mom_change: Dict[str, float]
    yoy_change: Dict[str, float]


class TrendData(BaseModel):
    metric_type: str
    dates: List[str]
    amounts: List[float]
    member_ratios: List[float] = Field(default_factory=list, description="今年会员占比 %")
    ly_amounts: List[float] = Field(default_factory=list, description="去年同周期金额")
    ly_member_ratios: List[float] = Field(default_factory=list, description="去年同周期会员占比 %")

