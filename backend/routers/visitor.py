"""
访客入会率路由

前缀: /api/v1/visitor/*
"""

from fastapi import APIRouter, Query, Response
from typing import Optional

from backend.contracts.schemas import VisitorSummaryResponse, VisitorDailyTrendResponse
from backend.services.visitor_service import get_visitor_summary, get_visitor_daily_trend
from backend.services import check_future_date

router = APIRouter(prefix="/api/v1/visitor", tags=["访客入会率"])


@router.get("/summary", response_model=VisitorSummaryResponse)
def get_visitor_summary_api(
    response: Response,
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    compare_start_date: Optional[str] = Query(default=None, description="对比期开始日期（可选，覆盖自动Y-1推算）"),
    compare_end_date: Optional[str] = Query(default=None, description="对比期结束日期（可选，覆盖自动Y-1推算）"),
):
    """
    访客入会率汇总

    返回指定周期内的：
    - 访客数、新增会员数、入会率
    - 去年同期对比（访客数YoY、新增会员数YoY、入会率百分点差）
    - 环比（访客数MoM、新增会员数MoM、入会率百分点差）
    """
    if warning := check_future_date(start_date) or check_future_date(end_date):
        response.headers["X-Data-Warning"] = warning
    return get_visitor_summary(start_date, end_date, compare_start_date, compare_end_date)


@router.get("/daily-trend", response_model=VisitorDailyTrendResponse)
def get_visitor_daily_trend_api(
    response: Response,
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    compare_start_date: Optional[str] = Query(default=None, description="对比期开始日期（可选，覆盖自动Y-1推算）"),
    compare_end_date: Optional[str] = Query(default=None, description="对比期结束日期（可选，覆盖自动Y-1推算）"),
):
    """
    访客入会率每日趋势

    返回每日访客数、新增会员数、入会率，含对比期同天数据。
    """
    if warning := check_future_date(start_date) or check_future_date(end_date):
        response.headers["X-Data-Warning"] = warning
    data = get_visitor_daily_trend(start_date, end_date, compare_start_date, compare_end_date)
    return {
        "start_date": start_date,
        "end_date": end_date,
        "data": data,
    }
