"""芙清 CRM - Pydantic 契约模型"""
from __future__ import annotations
from typing import List, Dict
from pydantic import BaseModel, Field
from typing import Annotated
from .types import RatioField, PercentageField, PpField  # Sprint 17 B2 全量 audit

class ChurnSegmentItem(BaseModel):
    name: str
    high: int
    medium: int
    low: int


class ChurnDistributionResponse(BaseModel):
    date: str
    churn_mode: str
    total_users: int
    high_risk: int
    medium_risk: int
    low_risk: int
    # Sprint 17 B2 全量 audit: 0-1 decimal ratio 字段补 RatioField 标注
    high_risk_rate: "RatioField"
    by_segment: Dict[str, ChurnSegmentItem]


class ChurnUserItem(BaseModel):
    user_id: str
    segment_id: int
    segment_name: str
    risk_score: float
    risk_level: str
    last_order_days: int
    frequency: int
    monetary: float


class ChurnUsersResponse(BaseModel):
    date: str
    mode: str
    total_matched: int
    users: List[ChurnUserItem]

class ChurnScatterPoint(BaseModel):
    """流失预警-散点数据"""
    category_name: str
    current_users: int
    # Sprint 17 B2 全量 audit: 0-1 decimal ratio 字段补 RatioField 标注
    mom_change_rate: "RatioField"
    churn_users: int
    inter_churn: int     # 品类间流失
    silent_churn: int    # 沉默流失


class ChurnBarData(BaseModel):
    """流失预警-条形数据"""
    category_name: str
    current_users: int
    previous_users: int
    # Sprint 17 B2 全量 audit: 0-1 decimal ratio 字段补 RatioField 标注
    mom_change_rate: "RatioField"


class ChurnTableRow(BaseModel):
    """流失预警-表格行"""
    category_name: str
    current_users: int
    previous_users: int
    # Sprint 17 B2 全量 audit: 0-1 decimal ratio 字段补 RatioField 标注
    mom_change_rate: "RatioField"
    inter_churn: int
    silent_churn: int
    top_churn_dest1: str
    top_churn_dest1_ratio: "RatioField"
    top_churn_dest2: str
    top_churn_dest2_ratio: "RatioField"
    挽回建议: str


class CategoryChurnResponse(BaseModel):
    """流失预警 Tab 响应"""
    scatter_data: List[ChurnScatterPoint]
    bar_data: List[ChurnBarData]
    table: List[ChurnTableRow]
    operation_suggestions: List[str]
    data_quality_note: str


# ─────────────────────────────────────────────────────────────
# 品类看板 v2 - 详情页 API
# ─────────────────────────────────────────────────────────────

class CategoryDailyTrendResponse(BaseModel):
    """品类每日趋势响应"""
    category_id: str
    category_name: str
    granularity: str = "daily"
    dates: List[str]
    gmv: List[float]
    user_count: List[int]
    aus: List[float]
    # Sprint 17 B2 全量 audit: List[RatioField] 必须用 Annotated 才能触发 element-wise 约束
    new_customer_ratio: List[Annotated[float, Field(ge=0.0, le=1.0, description="0-1 decimal 新客占比")]]


class UserDetail(BaseModel):
    """用户详情"""
    user_id: str
    nickname: str
    order_count: int
    total_gmv: float
    first_order_date: str
    last_order_date: str
    segment_id: int
    segment_name: str
    is_member: bool
    is_wool_party: bool


class CategoryUserListResponse(BaseModel):
    """品类用户列表响应"""
    category_id: str
    category_name: str
    total_users: int
    users: List[UserDetail]

