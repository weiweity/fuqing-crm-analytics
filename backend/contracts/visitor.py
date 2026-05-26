"""芙清 CRM - Pydantic 契约模型"""
from typing import Optional, List, Any, Dict
from enum import Enum
from pydantic import BaseModel, Field

class VisitorSummaryResponse(BaseModel):
    """访客入会率汇总响应"""
    start_date: str
    end_date: str
    visitors: int
    new_members: int
    member_join_rate: float
    ly_visitors: int
    ly_new_members: int
    ly_member_join_rate: float
    visitors_yoy: Optional[float] = None
    new_members_yoy: Optional[float] = None
    member_join_rate_yoy: Optional[float] = None
    # 环比
    visitors_mom: Optional[float] = None
    new_members_mom: Optional[float] = None
    member_join_rate_mom: Optional[float] = None


class VisitorDailyTrendItem(BaseModel):
    """访客入会率每日趋势项"""
    date: str
    visitors: int
    new_members: int
    member_join_rate: float
    ly_visitors: int
    ly_new_members: int
    ly_member_join_rate: float


class VisitorDailyTrendResponse(BaseModel):
    """访客入会率每日趋势响应"""
    start_date: str
    end_date: str
    data: List[VisitorDailyTrendItem]

