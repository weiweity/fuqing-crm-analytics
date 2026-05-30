"""
资产分析路由

前缀: /api/v1/asset/*
"""

from fastapi import APIRouter, Query, Response

from backend.config import _default_end_date
from backend.contracts.schemas import AssetSummaryResponse, AssetTrendResponse
from backend.services.asset_service import get_asset_summary, get_asset_trend
from backend.services import check_future_date

router = APIRouter(prefix="/api/v1/asset", tags=["资产分析"])


@router.get("/summary", response_model=AssetSummaryResponse)
def get_asset_summary_api(
    response: Response,
    date: str = Query(default=_default_end_date(), description="分析日期 YYYY-MM-DD"),
):
    """资产汇总（订单 GMV 模拟）"""
    if warning := check_future_date(date):
        response.headers["X-Data-Warning"] = warning
    return get_asset_summary(date)


@router.get("/trend", response_model=AssetTrendResponse)
def get_asset_trend_api(
    response: Response,
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    granularity: str = Query(default="month", description="month 或 week"),
):
    """资产趋势（多月/周）"""
    if warning := check_future_date(start_date) or check_future_date(end_date):
        response.headers["X-Data-Warning"] = warning
    return get_asset_trend(start_date, end_date, granularity)
