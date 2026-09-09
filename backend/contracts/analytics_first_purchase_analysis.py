"""HTTP contract for saved first-purchase SNAPSHOT analyses.

Store documents keep http_api=NOT_CONNECTED. This surface is CONNECTED only.
Channel follow-up saved-analysis/v1 is a different family and is not accepted.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, field_validator

from backend.contracts.analytics import AnalyticsModel, OpaqueId
from backend.contracts.analytics_first_purchase import (
    DATA_VERSION,
    METRIC_ID,
    METRIC_VERSION,
    QUERY_ID,
    QUERY_VERSION,
    SNAPSHOT_ID,
    FirstPurchaseFacts,
    FirstPurchaseFixedWindow,
    FirstPurchaseQueryRequest,
    FirstPurchaseResolvedFilters,
    Sha256Hex,
)

ANALYSIS_SCHEMA = "analytics-first-purchase-saved-analysis/v1"
VISUAL_SCHEMA = "analytics-visual-table/v1"
HTTP_API_CONNECTED = "CONNECTED"


class FirstPurchaseVisualSpec(AnalyticsModel):
    schema_version: Literal["analytics-visual-table/v1"] = VISUAL_SCHEMA
    kind: Literal["TABLE"] = "TABLE"


class FirstPurchaseAnalysisCreateRequest(AnalyticsModel):
    created_from_run_id: OpaqueId
    title: Annotated[str, Field(min_length=1, max_length=120)]
    visual_spec: FirstPurchaseVisualSpec | None = None

    @field_validator("title")
    @classmethod
    def title_text(cls, value: str) -> str:
        title = value.strip()
        if not title or any(ord(ch) < 32 or ord(ch) == 127 for ch in title):
            raise ValueError("title must be 1-120 characters without controls")
        return title


class FirstPurchaseAnalysisTitleRequest(AnalyticsModel):
    title: Annotated[str, Field(min_length=1, max_length=120)]

    @field_validator("title")
    @classmethod
    def title_text(cls, value: str) -> str:
        return FirstPurchaseAnalysisCreateRequest.title_text(value)


class FirstPurchaseQueryRef(AnalyticsModel):
    query_id: Literal["first_purchase_product_path"] = QUERY_ID
    query_version: Literal["first-purchase-path-query/v1"] = QUERY_VERSION


class FirstPurchaseMetricRef(AnalyticsModel):
    metric_id: Literal["first_purchase_product_n_day_finished"] = METRIC_ID
    metric_version: Literal["first-purchase-path-metric/v1"] = METRIC_VERSION


class FirstPurchaseSavedSnapshot(AnalyticsModel):
    run_id: OpaqueId
    evidence_digest: Sha256Hex
    resolved_filters: FirstPurchaseResolvedFilters
    data_snapshot_ref: Literal["synthetic-first-purchase-v1"] = SNAPSHOT_ID
    as_of: str


class FirstPurchaseSavedAnalysis(AnalyticsModel):
    schema_version: Literal["analytics-first-purchase-saved-analysis/v1"] = ANALYSIS_SCHEMA
    analysis_id: OpaqueId
    version: Annotated[int, Field(strict=True, ge=1)]
    title: str
    query_ref: FirstPurchaseQueryRef
    metric_refs: list[FirstPurchaseMetricRef]
    filters: FirstPurchaseQueryRequest
    visual_spec: FirstPurchaseVisualSpec
    created_from_run_id: OpaqueId
    owner_id: OpaqueId
    visibility: Literal["PRIVATE"]
    endorsement: Literal["PERSONAL"]
    data_mode: Literal["SNAPSHOT"]
    snapshot: FirstPurchaseSavedSnapshot
    facts: FirstPurchaseFacts
    data_version: Literal["synthetic-first-purchase-data/v1"] = DATA_VERSION
    filter_hash: Sha256Hex
    limitations: list[str]
    created_at: str
    finite_mock: Literal[True]
    http_api: Literal["CONNECTED"] = HTTP_API_CONNECTED


class FirstPurchaseSavedAnalysisListItem(AnalyticsModel):
    schema_version: Literal["analytics-first-purchase-saved-analysis/v1"] = ANALYSIS_SCHEMA
    analysis_id: OpaqueId
    version: Annotated[int, Field(strict=True, ge=1)]
    title: str
    query_id: Literal["first_purchase_product_path"] = QUERY_ID
    observation_days: Literal[30, 60, 90]
    cohort_window: FirstPurchaseFixedWindow
    as_of: str
    data_mode: Literal["SNAPSHOT"]
    visibility: Literal["PRIVATE"]
    finite_mock: Literal[True]
    http_api: Literal["CONNECTED"] = HTTP_API_CONNECTED


class FirstPurchaseSavedAnalysisList(AnalyticsModel):
    schema_version: Literal["analytics-first-purchase-saved-analysis/v1"] = ANALYSIS_SCHEMA
    items: list[FirstPurchaseSavedAnalysisListItem]
