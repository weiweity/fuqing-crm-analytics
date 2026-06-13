"""芙清 CRM - Pydantic 契约模型"""
from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel
from .types import RatioField, PercentageField  # Sprint 17 B2 全量 audit

class VisitorSummaryResponse(BaseModel):
    """访客入会率汇总响应.
    注意: member_join_rate / ly_member_join_rate / *_yoy / *_mom 都是 0-1 decimal 形式
    (Sprint 17 B2 全量 audit 治理范围), 不是 percentage. 前端 unit='pp' 时自己 *100."""
    start_date: str
    end_date: str
    visitors: int
    new_members: int
    member_join_rate: "RatioField"
    ly_visitors: int
    ly_new_members: int
    ly_member_join_rate: "RatioField"
    # yoy/mom: 0-1 decimal 形式 pp 差 (cur-ly), 越界 ±1
    visitors_yoy: Optional["PercentageField"] = None
    new_members_yoy: Optional["PercentageField"] = None
    member_join_rate_yoy: Optional["RatioField"] = None  # 0-1 pp 差 (cur-ly)
    # 环比
    visitors_mom: Optional["PercentageField"] = None
    new_members_mom: Optional["PercentageField"] = None
    member_join_rate_mom: Optional["RatioField"] = None  # 0-1 pp 差 (cur-mom)


class VisitorDailyTrendItem(BaseModel):
    """访客入会率每日趋势项.
    注意: daily trend 跟 summary 不同, member_join_rate/ly_member_join_rate 是 0-100 percentage (service *100 后)
    """
    date: str
    visitors: int
    new_members: int
    # 0-100 percentage
    member_join_rate: "PercentageField"
    ly_visitors: int
    ly_new_members: int
    ly_member_join_rate: "PercentageField"


class VisitorDailyTrendResponse(BaseModel):
    """访客入会率每日趋势响应"""
    start_date: str
    end_date: str
    data: List[VisitorDailyTrendItem]

