"""
人群流转路由

前缀: /api/v1/flow/*
"""

from fastapi import APIRouter, Query
from typing import Optional, List

from backend.contracts.schemas import FlowMatrixResponse, FlowSankeyResponse
from backend.services.flow_service import get_flow_matrix, get_flow_sankey

router = APIRouter(prefix="/api/v1/flow", tags=["人群流转"])


@router.get("/matrix", response_model=FlowMatrixResponse)
def get_flow_matrix_api(
    from_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    to_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    lookback_days: int = Query(default=90, description="回溯天数"),
    metric_type: str = Query(default="GMV", description="GMV/GSV"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
):
    """人群流转矩阵：返回 9x9 矩阵 + 留存/升级/降级汇总指标"""
    return get_flow_matrix(from_date, to_date, lookback_days, metric_type, exclude_channels)


@router.get("/sankey", response_model=FlowSankeyResponse)
def get_flow_sankey_api(
    from_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    to_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    lookback_days: int = Query(default=90, description="回溯天数"),
    metric_type: str = Query(default="GMV", description="GMV/GSV"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
):
    """桑基图数据：返回 nodes + links，用于可视化"""
    return get_flow_sankey(from_date, to_date, lookback_days, metric_type, exclude_channels)
