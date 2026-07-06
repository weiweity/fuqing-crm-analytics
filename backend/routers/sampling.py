"""
派样看板路由

前缀: /api/v1/sampling/*
"""

from fastapi import APIRouter, Query, Response
from typing import Optional, List

from backend.config import _default_start_date, _default_end_date
from backend.contracts.schemas import (
    SamplingROIResponse,
    SamplingRepurchaseDistribution,
    SamplingRepurchaseTrackingResponse,
)
from backend.services.sampling_service import (
    get_sampling_roi,
    get_sampling_repurchase_buckets,
    get_sampling_repurchase_tracking,
)
from backend.services import check_future_date

router = APIRouter(prefix="/api/v1/sampling", tags=["派样看板"])


@router.get("/roi", response_model=SamplingROIResponse)
def get_sampling_roi_api(
    response: Response,
    start_date: str = Query(default=_default_start_date(), description="派样起始日期"),
    end_date: str = Query(default=_default_end_date(), description="派样结束日期"),
    window_days: int = Query(default=30, ge=1, le=90, description="回购窗口天数：1-90"),
    level: str = Query(default="spu_category", description="品类维度：spu_category/spu_tier/spu_product_class"),
    channel: Optional[str] = Query(default=None, description="筛选特定派样渠道"),
    compare_date_range: Optional[List[str]] = Query(default=None, description="对比日期范围 [start, end]"),
    exclude_low_price: bool = Query(default=False, description="是否剔除低价渠道（Sampling 本期接收参数）"),
):
    """
    派样 ROI 分析

    返回 U先派样 / 百补派样 在指定时间窗口内的：
    - 渠道汇总：派样人数、所选窗口回购人数、回购率、贡献GSV、AUS
    - 品类明细：每个渠道×品类的回购情况（含同品类回购）
    """
    if warning := check_future_date(start_date) or check_future_date(end_date):
        response.headers["X-Data-Warning"] = warning
    compare_tuple = None
    if compare_date_range and len(compare_date_range) == 2:
        compare_tuple = (compare_date_range[0], compare_date_range[1])
    return get_sampling_roi(start_date, end_date, window_days, level, channel, compare_tuple)


@router.get("/repurchase-distribution", response_model=SamplingRepurchaseDistribution)
def get_sampling_repurchase_distribution_api(
    response: Response,
    start_date: str = Query(default=_default_start_date(), description="派样起始日期"),
    end_date: str = Query(default=_default_end_date(), description="派样结束日期"),
    window_days: int = Query(default=90, ge=1, le=90, description="回购窗口天数：1-90"),
    channel: Optional[str] = Query(default=None, description="筛选特定派样渠道；空值为 TTL 派样"),
):
    """回购周期分布：TTL 或单渠道的 4 桶聚合。"""
    if warning := check_future_date(start_date) or check_future_date(end_date):
        response.headers["X-Data-Warning"] = warning
    return get_sampling_repurchase_buckets(start_date, end_date, window_days, channel)


@router.get("/repurchase-tracking", response_model=SamplingRepurchaseTrackingResponse)
def get_sampling_repurchase_tracking_api(
    response: Response,
    start_date: str = Query(default=_default_start_date(), description="派样起始日期"),
    end_date: str = Query(default=_default_end_date(), description="派样结束日期"),
    window_days: int = Query(default=90, ge=1, le=90, description="回购窗口天数：1-90"),
    channel: Optional[str] = Query(default=None, description="筛选特定派样渠道；空值为 TTL 派样"),
):
    """Sprint 169 回购周期跟踪 (3 年对比柱状图).

    对当前期间 + 上一年 + 前年 各跑一次 get_sampling_repurchase_buckets, 拼出 3 年 × 4 桶
    扁平列表, 供前端 ECharts grouped bar 渲染.

    注意: 早期年份订单表未覆盖时静默回落 0 (L4.20 SSOT 一致性).
    """
    if warning := check_future_date(start_date) or check_future_date(end_date):
        response.headers["X-Data-Warning"] = warning
    return get_sampling_repurchase_tracking(start_date, end_date, window_days, channel)

