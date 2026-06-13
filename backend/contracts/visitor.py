"""Sample CRM - Pydantic 契约模型"""
from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel
from .types import PercentageField, PpField  # Sprint 17 B2 全量 audit

class VisitorSummaryResponse(BaseModel):
    """访客入会率汇总响应.
    注意: member_join_rate / ly_member_join_rate 是 0-100 percentage 形式
    (Sprint 17 B2 全量 audit 治理范围), 前端直接显示 value%."""
    start_date: str
    end_date: str
    visitors: int
    new_members: int
    member_join_rate: "PercentageField"
    ly_visitors: int
    ly_new_members: int
    ly_member_join_rate: "PercentageField"
    # yoy/mom: pp 差 (cur-ly), 范围 -100~+100
    visitors_yoy: Optional["PercentageField"] = None
    new_members_yoy: Optional["PercentageField"] = None
    member_join_rate_yoy: Optional["PpField"] = None
    # 环比
    visitors_mom: Optional["PercentageField"] = None
    new_members_mom: Optional["PercentageField"] = None
    member_join_rate_mom: Optional["PpField"] = None


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

