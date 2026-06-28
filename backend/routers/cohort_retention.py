"""Sprint 143 cohort retention router."""

from fastapi import APIRouter, Query

from backend.contracts.cohort_retention import (
    SamplingCohortRetentionResponse,
    SamplingCohortRetentionRow,
)
from backend.services.cohort_retention_service import get_cohort_retention_matrix


router = APIRouter(prefix="/api/v1/cohort-retention", tags=["cohort-retention"])


@router.get("/matrix", response_model=SamplingCohortRetentionResponse)
def get_cohort_retention(
    start_month: str = Query(..., description="cohort 起始月份 YYYY-MM"),
    end_month: str = Query(..., description="cohort 结束月份 YYYY-MM"),
    channel: str = Query(default="全店", description="渠道，默认全店"),
):
    """Sprint 143: cohort retention matrix."""
    rows = get_cohort_retention_matrix(start_month, end_month, channel)
    return SamplingCohortRetentionResponse(
        rows=[
            SamplingCohortRetentionRow(
                cohort_month=row.cohort_month,
                cohort_size=row.cohort_size,
                retention=row.retention,
            )
            for row in rows
        ],
        start_month=start_month,
        end_month=end_month,
        channel=channel,
    )
