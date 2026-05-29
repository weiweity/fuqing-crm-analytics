"""
RFM 路由

前缀: /api/v1/rfm/*
"""

from fastapi import APIRouter, Query, Response
from typing import Optional, List

from backend.contracts.schemas import (
    RFMRFlowResponse,
    RFMFRFlowResponse,
    RFMMFlowResponse,
    SegmentOrdersResponse,
)
from backend.services.rfm import (
    get_rfm_r_flow,
    get_rfm_f_flow,
    get_rfm_m_flow,
    get_segment_orders,
)
from backend.semantic.time import check_future_date

router = APIRouter(prefix="/api/v1/rfm", tags=["RFM"])


@router.get("/r-flow", response_model=RFMRFlowResponse)
def get_rfm_r_flow_api(
    response: Response,
    year: int = Query(default=2026, description="对比基准年（仅影响列标签）"),
    metric_type: str = Query(default="GSV", description="GMV 或 GSV"),
    period: Optional[str] = Query(default=None, description="WTD / MTD / YTD / Q1-Q4"),
    start_date: Optional[str] = Query(default=None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="结束日期 YYYY-MM-DD"),
    channel: Optional[str] = Query(default=None, description="渠道筛选"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
    compare_start_date: Optional[str] = Query(default=None, description="对比期开始日期（可选，覆盖自动Y-1推算）"),
    compare_end_date: Optional[str] = Query(default=None, description="对比期结束日期（可选，覆盖自动Y-1推算）"),
):
    """RFM - R区间流转看板"""
    _warn = (check_future_date(start_date) if start_date else None) \
        or (check_future_date(end_date) if end_date else None)
    if _warn:
        response.headers["X-Data-Warning"] = _warn
    return get_rfm_r_flow(
        year=year,
        metric_type=metric_type,
        period=period,
        start_date=start_date,
        end_date=end_date,
        channel=channel,
        exclude_channels=exclude_channels,
        compare_start_date=compare_start_date,
        compare_end_date=compare_end_date,
    )


@router.get("/f-flow", response_model=RFMFRFlowResponse)
def get_rfm_f_flow_api(
    response: Response,
    year: int = Query(default=2026, description="对比基准年（仅影响列标签）"),
    metric_type: str = Query(default="GSV", description="GMV 或 GSV"),
    period: Optional[str] = Query(default=None, description="WTD / MTD / YTD / Q1-Q4"),
    start_date: Optional[str] = Query(default=None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="结束日期 YYYY-MM-DD"),
    channel: Optional[str] = Query(default=None, description="渠道筛选"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
    compare_start_date: Optional[str] = Query(default=None, description="对比期开始日期（可选，覆盖自动Y-1推算）"),
    compare_end_date: Optional[str] = Query(default=None, description="对比期结束日期（可选，覆盖自动Y-1推算）"),
):
    """RFM - F区间流转看板"""
    _warn = (check_future_date(start_date) if start_date else None) \
        or (check_future_date(end_date) if end_date else None)
    if _warn:
        response.headers["X-Data-Warning"] = _warn
    return get_rfm_f_flow(
        year=year,
        metric_type=metric_type,
        period=period,
        start_date=start_date,
        end_date=end_date,
        channel=channel,
        exclude_channels=exclude_channels,
        compare_start_date=compare_start_date,
        compare_end_date=compare_end_date,
    )


@router.get("/m-flow", response_model=RFMMFlowResponse)
def get_rfm_m_flow_api(
    response: Response,
    year: int = Query(default=2026, description="对比基准年（仅影响列标签）"),
    metric_type: str = Query(default="GSV", description="GMV 或 GSV"),
    period: Optional[str] = Query(default=None, description="WTD / MTD / YTD / Q1-Q4"),
    start_date: Optional[str] = Query(default=None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="结束日期 YYYY-MM-DD"),
    channel: Optional[str] = Query(default=None, description="渠道筛选"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
    compare_start_date: Optional[str] = Query(default=None, description="对比期开始日期（可选，覆盖自动Y-1推算）"),
    compare_end_date: Optional[str] = Query(default=None, description="对比期结束日期（可选，覆盖自动Y-1推算）"),
):
    """RFM - M区间流转看板"""
    _warn = (check_future_date(start_date) if start_date else None) \
        or (check_future_date(end_date) if end_date else None)
    if _warn:
        response.headers["X-Data-Warning"] = _warn
    return get_rfm_m_flow(
        year=year,
        metric_type=metric_type,
        period=period,
        start_date=start_date,
        end_date=end_date,
        channel=channel,
        exclude_channels=exclude_channels,
        compare_start_date=compare_start_date,
        compare_end_date=compare_end_date,
    )


@router.get("/segment-orders", response_model=SegmentOrdersResponse)
def get_segment_orders_api(
    response: Response,
    dimension: str = Query(..., description="维度：r / f / m"),
    segment: str = Query(..., description="区间名称（如 近1个月已购客）"),
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    metric_type: str = Query(default="GSV", description="GMV 或 GSV"),
    mode: str = Query(default="all", description="all / member / same_channel / member_same_channel"),
    channel: Optional[str] = Query(default=None, description="渠道筛选"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
):
    """
    RFM 区间订单明细导出

    根据维度和区间，返回该区间内所有用户的订单号明细，用于二次营销。
    """
    if warning := check_future_date(start_date) or check_future_date(end_date):
        response.headers["X-Data-Warning"] = warning
    return get_segment_orders(
        dimension=dimension,
        segment=segment,
        start_date=start_date,
        end_date=end_date,
        metric_type=metric_type,
        mode=mode,
        channel=channel,
        exclude_channels=exclude_channels,
    )
