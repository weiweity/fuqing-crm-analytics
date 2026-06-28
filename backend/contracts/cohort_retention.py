"""Sprint 143 cohort retention matrix contract."""

from typing import Dict, List

from pydantic import BaseModel, Field

from .types import RatioField


class SamplingCohortRetentionRow(BaseModel):
    """cohort retention 矩阵单行."""

    cohort_month: str = Field(..., description="cohort 月份 YYYY-MM")
    cohort_size: int = Field(..., ge=0, description="cohort 用户数")
    retention: Dict[int, RatioField] = Field(
        default_factory=dict,
        description="{月偏移: 留存率 0-1 decimal}，0 = cohort 月，12 = cohort + 12 月",
    )


class SamplingCohortRetentionResponse(BaseModel):
    """cohort retention matrix response."""

    rows: List[SamplingCohortRetentionRow] = Field(default_factory=list)
    start_month: str = Field(..., description="起始 cohort 月份 YYYY-MM")
    end_month: str = Field(..., description="结束 cohort 月份 YYYY-MM")
    channel: str = Field(..., description="渠道")


# Backward-compatible aliases for the Sprint 143 handoff names. The router uses
# the Sampling* classes above so OpenAPI does not collide with health.CohortRetentionResponse.
CohortRetentionRow = SamplingCohortRetentionRow
CohortRetentionResponse = SamplingCohortRetentionResponse
