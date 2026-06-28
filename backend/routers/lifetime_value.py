"""Sprint 143 LTV router."""

from fastapi import APIRouter, Query

from backend.contracts.lifetime_value import LifetimeValueSummary
from backend.services.lifetime_value_service import get_lifetime_value_summary


router = APIRouter(prefix="/api/v1/lifetime-value", tags=["LTV"])


@router.get("/cohort", response_model=LifetimeValueSummary)
def get_lifetime_value_cohort(
    cohort_date: str = Query(..., description="派样 cohort 日期 YYYY-MM-DD"),
    channel: str = Query(default="全店", description="渠道，默认全店"),
):
    """Sprint 143: cohort LTV 90/180/365 天汇总."""
    return get_lifetime_value_summary(cohort_date=cohort_date, channel=channel)
