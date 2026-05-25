"""
一键拆解路由

前缀: /api/v1/breakdown/*
"""

from fastapi import APIRouter

from backend.contracts.schemas import BreakdownRequest, BreakdownResponse
from backend.services.breakdown_service import calculate_one_click_breakdown

router = APIRouter(prefix="/api/v1/breakdown", tags=["一键拆解"])


@router.post("/one-click", response_model=BreakdownResponse)
def get_one_click_breakdown_api(request: BreakdownRequest):
    """
    一键拆解 v2 — GSV only

    支持两种模式：
    - forward（顺拆）：从现状数据预估，计算目标gap
    - reverse（倒拆）：从目标反推各R区间/渠道所需人数/UV

    老客拆解：按R区间（6档）× F段（F>1/F=1）逐层预估
    新客拆解：按渠道漏斗逐渠道预估
    """
    return calculate_one_click_breakdown(
        target_gmv=request.target_gmv,
        activity_start=request.activity_start,
        activity_end=request.activity_end,
        last_year_start=request.last_year_start,
        last_year_end=request.last_year_end,
        old_customer_ratio_target=request.old_customer_ratio_target,
        breakdown_mode=request.breakdown_mode,
    )
