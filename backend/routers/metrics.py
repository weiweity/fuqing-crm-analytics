"""
指标路由

前缀: /api/v1/metrics/*
"""

from fastapi import APIRouter, Query, Response
from typing import Optional, List

from backend.config import _default_start_date, _default_end_date
from backend.contracts.schemas import OverviewMetrics, TrendData
from backend.services.metrics_service import get_overview_metrics, get_daily_trend
from backend.semantic.time import check_future_date

router = APIRouter(prefix="/api/v1/metrics", tags=["指标"])


@router.get("/overview", response_model=OverviewMetrics)
def get_metrics_overview(
    response: Response,
    start_date: str = Query(default=_default_start_date(), description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(default=_default_end_date(), description="结束日期 YYYY-MM-DD"),
    metric_type: str = Query(default="GMV", description="指标类型：GMV 或 GSV"),
    channel: Optional[str] = Query(default=None, description="渠道筛选（UI渠道名）"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
    compare_start_date: Optional[str] = Query(default=None, description="对比期开始日期（可选，覆盖自动Y-1推算）"),
    compare_end_date: Optional[str] = Query(default=None, description="对比期结束日期（可选，覆盖自动Y-1推算）"),
):
    """获取核心指标概览：GMV、订单数、客单价、新老客数量和GMV、会员指标、环比、同比变化"""
    if warning := check_future_date(start_date) or check_future_date(end_date):
        response.headers["X-Data-Warning"] = warning
    return get_overview_metrics(
        start_date, end_date, metric_type, channel, exclude_channels,
        compare_start_date, compare_end_date
    )


@router.get("/trend", response_model=TrendData)
def get_metrics_trend(
    response: Response,
    start_date: str = Query(default=_default_start_date(), description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(default=_default_end_date(), description="结束日期 YYYY-MM-DD"),
    metric_type: str = Query(default="GMV", description="指标类型：GMV 或 GSV"),
    channel: Optional[str] = Query(default=None, description="渠道筛选（UI渠道名）"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
    compare_start_date: Optional[str] = Query(default=None, description="对比期开始日期（可选，覆盖自动Y-1推算）"),
    compare_end_date: Optional[str] = Query(default=None, description="对比期结束日期（可选，覆盖自动Y-1推算）"),
):
    """获取每日趋势数据（GMV、订单数、用户数），用于绘制折线图"""
    if warning := check_future_date(start_date) or check_future_date(end_date):
        response.headers["X-Data-Warning"] = warning
    return get_daily_trend(
        start_date, end_date, metric_type, channel, exclude_channels,
        compare_start_date, compare_end_date
    )
