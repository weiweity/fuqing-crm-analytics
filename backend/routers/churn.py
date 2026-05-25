"""
流失预警路由

前缀: /api/v1/churn/*
"""

from fastapi import APIRouter, Query
from typing import Optional, List

from backend.contracts.schemas import ChurnDistributionResponse, ChurnUsersResponse
from backend.services.churn_service import get_churn_risk_distribution, get_churn_risk_users

router = APIRouter(prefix="/api/v1/churn", tags=["流失预警"])


@router.get("/distribution", response_model=ChurnDistributionResponse)
def get_churn_distribution_api(
    date: str = Query(..., description="分析日期 YYYY-MM-DD"),
    segment_id: Optional[int] = Query(default=None, description="象限ID筛选"),
    churn_mode: str = Query(default="dynamic", description="dynamic 或 fixed"),
    fixed_threshold: int = Query(default=60, description="固定阈值天数"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
):
    """各象限流失风险分布"""
    return get_churn_risk_distribution(date, segment_id, churn_mode, fixed_threshold, exclude_channels)


@router.get("/risk", response_model=ChurnUsersResponse)
def get_churn_risk_users_api(
    date: str = Query(..., description="分析日期 YYYY-MM-DD"),
    risk_level: Optional[str] = Query(default=None, description="high/medium/low"),
    segment_id: Optional[int] = Query(default=None, description="象限ID筛选"),
    churn_mode: str = Query(default="dynamic", description="dynamic 或 fixed"),
    fixed_threshold: int = Query(default=60, description="固定阈值天数"),
    limit: int = Query(default=100, description="返回条数上限"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除的渠道列表"),
):
    """高流失风险用户列表"""
    return get_churn_risk_users(
        date, risk_level, segment_id, churn_mode, fixed_threshold, limit, exclude_channels
    )
