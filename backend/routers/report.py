"""
报告汇总路由

前缀: /api/v1/report/*
"""

from fastapi import APIRouter, Query

from backend.services.report_service import get_report_summary

router = APIRouter(prefix="/api/v1/report", tags=["报告汇总"])


@router.get("/summary")
def get_report_summary_api(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    lookback_days: int = Query(default=90, description="回溯天数"),
):
    """
    获取报告汇总

    整合所有数据：核心指标、象限分布、地域分布、品类分布
    """
    return get_report_summary(start_date, end_date, lookback_days)
