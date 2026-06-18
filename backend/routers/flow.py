"""
人群流转路由

前缀: /api/v1/flow/*

Sprint 36-6 清理: 删 /sankey endpoint + FlowSankeyResponse + get_flow_sankey (前端 0 + 后端 0 业务消费).
留 /matrix endpoint + get_flow_matrix (被 backend export_service.py:360 + report_service.py:9 真业务消费).
"""

from fastapi import APIRouter, Query
from typing import Optional, List

from backend.contracts.schemas import FlowMatrixResponse
from backend.services.flow_service import get_flow_matrix

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
