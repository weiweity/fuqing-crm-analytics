"""
地域分析路由

前缀: /api/v1/geo/*
"""

from fastapi import APIRouter, Query, Response
from typing import Optional, List

from backend.config import _default_end_date
from backend.contracts.schemas import (
    GeoDistributionResponse,
    GeoSegmentMatrixResponse,
    GeoTrendResponse,
)
from backend.services.geo_service import (
    get_geo_distribution,
    get_geo_segment_matrix,
    get_geo_trend,
)
from backend.services import check_future_date

router = APIRouter(prefix="/api/v1/geo", tags=["地域分析"])


@router.get("/distribution", response_model=GeoDistributionResponse)
def get_geo_distribution_api(
    response: Response,
    date: str = Query(default=_default_end_date(), description="分析日期 YYYY-MM-DD"),
    lookback_days: int = Query(default=90, description="回溯天数"),
    level: str = Query(default="省份", description="省份/城市"),
    top_n: int = Query(default=50, description="返回前 N 条"),
    segment_id: Optional[int] = Query(default=None, description="象限ID筛选"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
):
    """地域分布：返回各省/市的用户数、GMV 及占比"""
    if warning := check_future_date(date):
        response.headers["X-Data-Warning"] = warning
    return get_geo_distribution(date, lookback_days, level, top_n, segment_id, exclude_channels)


@router.get("/segment", response_model=GeoSegmentMatrixResponse)
def get_geo_segment_api(
    response: Response,
    date: str = Query(default=_default_end_date(), description="分析日期 YYYY-MM-DD"),
    lookback_days: int = Query(default=90, description="回溯天数"),
    top_n: int = Query(default=10, description="每个象限返回前 N 个省份"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
):
    """地域-象限交叉矩阵：返回各象限Top省份分布"""
    if warning := check_future_date(date):
        response.headers["X-Data-Warning"] = warning
    return get_geo_segment_matrix(date, lookback_days, top_n, exclude_channels)


@router.get("/trend", response_model=GeoTrendResponse)
def get_geo_trend_api(
    response: Response,
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    lookback_days: int = Query(default=90, description="回溯天数"),
    top_n: int = Query(default=5, description="追踪前 N 个省份"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
):
    """地域趋势（多时间点）：返回各省份随时间的变化趋势"""
    if warning := check_future_date(start_date) or check_future_date(end_date):
        response.headers["X-Data-Warning"] = warning
    return get_geo_trend(start_date, end_date, lookback_days, top_n, exclude_channels)
