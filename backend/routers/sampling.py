"""
派样看板路由

前缀: /api/v1/sampling/*
"""

from fastapi import APIRouter, Query, Response
from typing import Optional

from backend.config import _default_start_date, _default_end_date
from backend.contracts.schemas import (
    SamplingROIResponse,
    SamplingLockAnalysisResponse,
    RollingComparisonResponse,
)
from backend.services.sampling_service import (
    get_sampling_roi,
    get_sampling_lock_analysis,
    get_rolling_comparison,
)
from backend.services import check_future_date

router = APIRouter(prefix="/api/v1/sampling", tags=["派样看板"])


@router.get("/roi", response_model=SamplingROIResponse)
def get_sampling_roi_api(
    response: Response,
    start_date: str = Query(default=_default_start_date(), description="派样起始日期"),
    end_date: str = Query(default=_default_end_date(), description="派样结束日期"),
    window_days: int = Query(default=30, description="回购窗口天数：7/30/60"),
    level: str = Query(default="spu_category", description="品类维度：spu_category/spu_tier/spu_product_class"),
    channel: Optional[str] = Query(default=None, description="筛选特定派样渠道"),
):
    """
    派样 ROI 分析

    返回 U先派样 / 百补派样 在指定时间窗口内的：
    - 渠道汇总：派样人数、7/30/60天回购人数、回购率、贡献GSV、AUS
    - 品类明细：每个渠道×品类的回购情况（含同品类回购）
    """
    if warning := check_future_date(start_date) or check_future_date(end_date):
        response.headers["X-Data-Warning"] = warning
    return get_sampling_roi(start_date, end_date, window_days, level, channel)


@router.get("/lock-analysis", response_model=SamplingLockAnalysisResponse)
def get_sampling_lock_analysis_api(
    campaign_name: str = Query(default="618节日", description="大促名称：618节日/双11/38节日"),
    year: int = Query(default=2026, description="年份"),
):
    """
    0.01派样锁权分析

    返回指定大促周期的：
    - 锁权人数、锁权率（UV→锁权）
    - 转化人数、转化率、贡献GSV、AUS
    - 新客锁权人数、新客占比、新客转化率、新客GSV
    - 同比对比（去年同大促）
    """
    return get_sampling_lock_analysis(campaign_name, year)


@router.get("/rolling-comparison", response_model=RollingComparisonResponse)
def get_rolling_comparison_api(
    response: Response,
    year_a_sample_start: str = Query(..., description="year_a 派样起始"),
    year_a_sample_end: str = Query(..., description="year_a 派样结束"),
    year_a_conv_start: str = Query(..., description="year_a 转化起始"),
    year_b_sample_start: str = Query(..., description="year_b 派样起始"),
    year_b_sample_end: str = Query(..., description="year_b 派样结束"),
    year_b_conv_start: str = Query(..., description="year_b 转化起始"),
    rolling_end: str = Query(..., description="滚动截止日"),
):
    """
    0.01派样滚动同期对比

    以 year_a 的参数为主，year_b 自动 T 对齐。
    派样期内：UV、锁权人数、锁权率
    转化期内：加赠转化人数（货架+累计≥100元）、转化率、转化GSV、转化AUS
    """
    if warning := (
        check_future_date(year_a_sample_start) or check_future_date(year_a_sample_end) or
        check_future_date(year_a_conv_start) or check_future_date(year_b_sample_start) or
        check_future_date(year_b_sample_end) or check_future_date(year_b_conv_start) or
        check_future_date(rolling_end)
    ):
        response.headers["X-Data-Warning"] = warning
    return get_rolling_comparison(
        year_a_sample_start=year_a_sample_start,
        year_a_sample_end=year_a_sample_end,
        year_a_conv_start=year_a_conv_start,
        year_b_sample_start=year_b_sample_start,
        year_b_sample_end=year_b_sample_end,
        year_b_conv_start=year_b_conv_start,
        rolling_end=rolling_end,
    )
