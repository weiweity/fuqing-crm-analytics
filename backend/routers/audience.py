"""
人群看板路由

前缀: /api/v1/audience/*
"""

from fastapi import APIRouter, Query, Response
from typing import Optional, List

from backend.contracts.schemas import AudienceTableResponse, AudienceSummaryResponse
from backend.contracts.audience import AudienceSummaryRequest
from backend.services.metrics_service import get_audience_table, calculate_audience_summary
from backend.services import PeriodBuilder, check_future_date
from datetime import date

router = APIRouter(prefix="/api/v1/audience", tags=["人群看板"])


@router.get("/table", response_model=AudienceTableResponse)
def get_audience_table_api(
    response: Response,
    dimension: str = Query(default="channel", description="维度：channel 或 spu_tier"),
    mode: str = Query(default="mtd", description="模式：mtd 或 free"),
    start_date: Optional[str] = Query(default=None, description="开始日期（free模式必填）"),
    end_date: Optional[str] = Query(default=None, description="结束日期（free模式必填）"),
    channels: Optional[str] = Query(default=None, description="逗号分隔的渠道列表"),
    metric_type: str = Query(default="GMV", description="指标类型：GMV 或 GSV"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
):
    """
    人群看板主表

    默认 MTD 同月对比（当年MTD vs 去年MTD），
    支持自由时间段筛选和渠道筛选。
    返回 24 个指标字段。
    """
    if mode == "free" and (not start_date or not end_date):
        raise ValueError("free 模式需要传入 start_date 和 end_date")
    if warning := check_future_date(start_date) or check_future_date(end_date):
        response.headers["X-Data-Warning"] = warning

    channel_list = None
    if channels:
        channel_list = [ch.strip() for ch in channels.split(",") if ch.strip()]

    return get_audience_table(
        dimension=dimension,
        mode=mode,
        start_date=start_date,
        end_date=end_date,
        channels=channel_list,
        metric_type=metric_type,
        exclude_channels=exclude_channels,
    )


@router.get("/summary", response_model=AudienceSummaryResponse)
def get_audience_summary_api(
    response: Response,
    year: int = Query(default=2026, description="对比基准年（仅影响列标签）"),
    metric_type: str = Query(default="GSV", description="GMV 或 GSV"),
    period: Optional[str] = Query(default=None, description="WTD / MTD / YTD / Q1-Q4"),
    start_date: Optional[str] = Query(default=None, description="开始日期 YYYY-MM-DD（period为空时使用）"),
    end_date: Optional[str] = Query(default=None, description="结束日期 YYYY-MM-DD（period为空时使用）"),
    channel: Optional[str] = Query(default=None, description="渠道筛选"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
    compare_start_date: Optional[str] = Query(default=None, description="对比期开始日期（可选，覆盖自动Y-1推算）"),
    compare_end_date: Optional[str] = Query(default=None, description="对比期结束日期（可选，覆盖自动Y-1推算）"),
    order_ids: Optional[List[str]] = Query(default=None, description="订单号列表，仅统计匹配订单"),
):
    """
    人群看板汇总接口

    一次返回三块数据：
    - Panel A：30指标对比（__TOTAL__ 全店，3年同比）
    - Panel B：渠道概览-全店（各渠道 GSV，3年同比 + 占比）
    - Panel C：渠道概览-会员（各渠道会员 GSV，3年同比 + 占比）
    """
    return _calculate_summary(
        response, year, metric_type, period, start_date, end_date,
        channel, exclude_channels, compare_start_date, compare_end_date, order_ids,
    )


def _calculate_summary(
    response: Response,
    year: int,
    metric_type: str,
    period: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    channel: Optional[str],
    exclude_channels: Optional[List[str]],
    compare_start_date: Optional[str],
    compare_end_date: Optional[str],
    order_ids: Optional[List[str]],
):
    if warning := check_future_date(start_date) or check_future_date(end_date):
        response.headers["X-Data-Warning"] = warning

    resolved_start = start_date
    resolved_end = end_date

    if period and not (start_date and end_date):
        try:
            pb = getattr(PeriodBuilder, period.lower())(today=date.today())
            resolved_start = pb["current"].start
            resolved_end = pb["current"].end
        except (AttributeError, KeyError):
            pass

    return calculate_audience_summary(
        year=year,
        metric_type=metric_type,
        start_date=resolved_start,
        end_date=resolved_end,
        channel=channel,
        exclude_channels=exclude_channels,
        compare_start_date=compare_start_date,
        compare_end_date=compare_end_date,
        order_ids=order_ids,
    )


@router.post("/summary", response_model=AudienceSummaryResponse)
def post_audience_summary_api(
    response: Response,
    body: AudienceSummaryRequest,
):
    """人群看板汇总接口（POST 版，支持大量订单号列表）"""
    return _calculate_summary(
        response,
        body.year,
        body.metric_type,
        body.period,
        body.start_date,
        body.end_date,
        body.channel,
        body.exclude_channels,
        body.compare_start_date,
        body.compare_end_date,
        body.order_ids,
    )
