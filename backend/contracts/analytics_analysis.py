"""HTTP contract for saved channel-follow-up SNAPSHOT analyses.

Store documents keep http_api=NOT_CONNECTED. This surface is CONNECTED only.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, field_validator

from backend.contracts.analytics import AnalyticsModel, OpaqueId
from backend.contracts.analytics_query import (
    ChannelFollowupFacts,
    ChannelFollowupFixedWindow,
    ChannelFollowupQueryRequest,
    ChannelFollowupResolvedFilters,
    Sha256Hex,
)

ANALYSIS_SCHEMA = "analytics-saved-analysis/v1"
VISUAL_SCHEMA = "analytics-visual-table/v1"
HTTP_API_CONNECTED = "CONNECTED"


class AnalyticsVisualSpec(AnalyticsModel):
    schema_version: Literal["analytics-visual-table/v1"] = VISUAL_SCHEMA
    kind: Literal["TABLE"] = "TABLE"


class AnalyticsAnalysisCreateRequest(AnalyticsModel):
    created_from_run_id: OpaqueId
    title: Annotated[str, Field(min_length=1, max_length=120)]
    visual_spec: AnalyticsVisualSpec | None = None

    @field_validator("title")
    @classmethod
    def title_text(cls, value: str) -> str:
        title = value.strip()
        if not title or any(ord(ch) < 32 or ord(ch) == 127 for ch in title):
            raise ValueError("title must be 1-120 characters without controls")
        return title


class AnalyticsAnalysisTitleRequest(AnalyticsModel):
    title: Annotated[str, Field(min_length=1, max_length=120)]

    @field_validator("title")
    @classmethod
    def title_text(cls, value: str) -> str:
        return AnalyticsAnalysisCreateRequest.title_text(value)


class AnalyticsQueryRef(AnalyticsModel):
    query_id: Literal["channel_first_observed_followup"]
    query_version: Literal["channel-followup-query/v1"]


class AnalyticsMetricRef(AnalyticsModel):
    metric_id: Literal["channel_first_observed_n_day_repeat"]
    metric_version: Literal["channel-followup-metric/v1"]


class AnalyticsSavedSnapshot(AnalyticsModel):
    run_id: OpaqueId
    evidence_digest: Sha256Hex
    resolved_filters: ChannelFollowupResolvedFilters
    data_snapshot_ref: Literal["synthetic-channel-followup-v1"]
    as_of: str


class AnalyticsRefreshCandidate(AnalyticsModel):
    run_id: OpaqueId
    evidence_digest: Sha256Hex


class AnalyticsSavedAnalysis(AnalyticsModel):
    schema_version: Literal["analytics-saved-analysis/v1"] = ANALYSIS_SCHEMA
    analysis_id: OpaqueId
    version: Annotated[int, Field(strict=True, ge=1)]
    title: str
    query_ref: AnalyticsQueryRef
    metric_refs: list[AnalyticsMetricRef]
    filters: ChannelFollowupQueryRequest
    visual_spec: AnalyticsVisualSpec
    created_from_run_id: OpaqueId
    owner_id: OpaqueId
    visibility: Literal["PRIVATE"]
    endorsement: Literal["PERSONAL"]
    data_mode: Literal["SNAPSHOT"]
    snapshot: AnalyticsSavedSnapshot
    facts: ChannelFollowupFacts
    data_version: Literal["synthetic-channel-followup-data/v1"]
    filter_hash: Sha256Hex
    limitations: list[str]
    refresh_candidate: AnalyticsRefreshCandidate | None
    created_at: str
    finite_mock: Literal[True]
    http_api: Literal["CONNECTED"] = HTTP_API_CONNECTED


class AnalyticsSavedAnalysisListItem(AnalyticsModel):
    schema_version: Literal["analytics-saved-analysis/v1"] = ANALYSIS_SCHEMA
    analysis_id: OpaqueId
    version: Annotated[int, Field(strict=True, ge=1)]
    title: str
    query_id: Literal["channel_first_observed_followup"]
    observation_days: Literal[30, 60, 90]
    cohort_window: ChannelFollowupFixedWindow
    as_of: str
    data_mode: Literal["SNAPSHOT"]
    visibility: Literal["PRIVATE"]
    refreshable: bool
    finite_mock: Literal[True]
    http_api: Literal["CONNECTED"] = HTTP_API_CONNECTED


class AnalyticsSavedAnalysisList(AnalyticsModel):
    schema_version: Literal["analytics-saved-analysis/v1"] = ANALYSIS_SCHEMA
    items: list[AnalyticsSavedAnalysisListItem]
