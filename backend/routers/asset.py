"""
资产分析路由

前缀: /api/v1/asset/*
"""

from fastapi import APIRouter, Query

from backend.config import _default_start_date, _default_end_date
from backend.contracts.schemas import AssetSummaryResponse, AssetTrendResponse
from backend.services.asset_service import get_asset_summary, get_asset_trend

router = APIRouter(prefix="/api/v1/asset", tags=["资产分析"])


@router.get("/summary", response_model=AssetSummaryResponse)
def get_asset_summary_api(
    date: str = Query(default=_default_end_date(), description="分析日期 YYYY-MM-DD"),
):
    """资产汇总（订单 GMV 模拟）"""
    return get_asset_summary(date)


@router.get("/trend", response_model=AssetTrendResponse)
def get_asset_trend_api(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    granularity: str = Query(default="month", description="month 或 week"),
):
    """资产趋势（多月/周）"""
    return get_asset_trend(start_date, end_date, granularity)
