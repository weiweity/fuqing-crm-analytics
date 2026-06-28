"""
RFM 路由

前缀: /api/v1/rfm/*

W5 v0.4.13: 4 个端点 (r-flow / f-flow / m-flow / segment-orders) 加 DuckDB-KV cache.
manifest 变化由 cache 内部 _ManifestTracker 检测, 自动整表失效.
"""

from fastapi import APIRouter, Query, Response
from typing import Optional, List

from backend.contracts.schemas import (
    RFMRFlowResponse,
    RFMFRFlowResponse,
    RFMMFlowResponse,
    SegmentOrdersResponse,
    RFMExtendedRequest,
    RFMExtendedResponse,
)
from backend.db.connection import get_connection
from backend.services.rfm.loader import get_rfm_manifest_info  # W2 v0.4.8
from backend.services.rfm import (
    get_rfm_r_flow,
    get_rfm_f_flow,
    get_rfm_m_flow,
    get_segment_orders,
    get_user_rfm_extended,
)
from backend.services.rfm.cache import RfmQueryCache  # W5 v0.4.13
from backend.services import check_future_date

router = APIRouter(prefix="/api/v1/rfm", tags=["RFM"])

# W5 v0.4.13: 进程内单例 cache (避免每次请求 new, 共享 manifest tracker 状态)
_rfm_cache = RfmQueryCache()


def _cached_rfm_call(endpoint: str, params: dict, compute_fn, *args, **kwargs):
    """W5 cache hit/miss 包装. 命中返回 cached, miss 时调 compute_fn 并 set.

    设计: 把 params (dict) 作为 key 输入, compute_fn 接受 *args, **kwargs.
    cache.get 走 ThreadSafeCursor (锁内预取), 安全并发.
    """
    cached = _rfm_cache.get(endpoint, params)
    if cached is not None:
        return cached
    result = compute_fn(*args, **kwargs)
    # 只缓存成功结果 (compute_fn 抛异常时不写入)
    _rfm_cache.set(endpoint, params, result)
    return result


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
    # W5 v0.4.13: cache hit/miss
    params = {
        "year": year, "metric_type": metric_type, "period": period,
        "start_date": start_date, "end_date": end_date,
        "channel": channel, "exclude_channels": exclude_channels,
        "compare_start_date": compare_start_date, "compare_end_date": compare_end_date,
    }
    return _cached_rfm_call("r-flow", params, get_rfm_r_flow, **params)


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
    # W5 v0.4.13: cache hit/miss
    params = {
        "year": year, "metric_type": metric_type, "period": period,
        "start_date": start_date, "end_date": end_date,
        "channel": channel, "exclude_channels": exclude_channels,
        "compare_start_date": compare_start_date, "compare_end_date": compare_end_date,
    }
    return _cached_rfm_call("f-flow", params, get_rfm_f_flow, **params)


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
    # W5 v0.4.13: cache hit/miss
    params = {
        "year": year, "metric_type": metric_type, "period": period,
        "start_date": start_date, "end_date": end_date,
        "channel": channel, "exclude_channels": exclude_channels,
        "compare_start_date": compare_start_date, "compare_end_date": compare_end_date,
    }
    return _cached_rfm_call("m-flow", params, get_rfm_m_flow, **params)


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
    # W5 v0.4.13: cache hit/miss
    params = {
        "dimension": dimension, "segment": segment,
        "start_date": start_date, "end_date": end_date,
        "metric_type": metric_type, "mode": mode,
        "channel": channel, "exclude_channels": exclude_channels,
    }
    return _cached_rfm_call("segment-orders", params, get_segment_orders, **params)


@router.post("/extended", response_model=RFMExtendedResponse)
def get_rfm_extended_api(request: RFMExtendedRequest):
    """Sprint 142: RFM 扩展分群（生命周期 / 价值层 / 潜力层）."""
    segments = get_user_rfm_extended(
        get_connection(),
        user_ids=request.user_ids,
        as_of_date=request.as_of_date,
    )
    return RFMExtendedResponse(segments=list(segments.values()))


# W2 v0.4.8: manifest version endpoint (设计 doc v1.1 §6 完成标志第 4 条)
@router.get("/version")
def get_rfm_manifest_version():
    """返回当前 active manifest 信息 (active_view / version / ts / path).

    用途:
    - 调试 ETL 跑批后 manifest 是否更新
    - W5 cache invalidate 配套 (manifest 变化触发整表失效)
    - 监控告警 (active_view 空 = ETL 还没跑过)
    """
    return get_rfm_manifest_info()


# W5 v0.4.13: cache 调试端点 (设计与 §7.5 验收对齐)
@router.get("/cache/stats")
def get_rfm_cache_stats():
    """W5 cache 状态: 总行数 / 有效行数 / 过期行数. 用于监控 + 验证 invalidate."""
    return _rfm_cache.stats()


@router.post("/cache/invalidate")
def post_rfm_cache_invalidate():
    """W5 手动整表失效 (admin/测试用). 生产环境正常由 manifest 变化自动触发."""
    deleted = _rfm_cache.invalidate()
    return {"invalidated": deleted}


@router.get("/cache/keys")
def get_rfm_cache_keys(endpoint: Optional[str] = None, limit: int = 50):
    """W5 调试: 列出 cache 键 (可按 endpoint 过滤). limit 上限 500."""
    return {"keys": _rfm_cache.list_keys(endpoint=endpoint, limit=min(limit, 500))}
