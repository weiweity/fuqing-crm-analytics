"""HTTP contract for private SNAPSHOT cockpits.

Store documents keep http_api=NOT_CONNECTED. This surface is CONNECTED only.
HTTP add binds a saved analysis version; it does not accept caller facts.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field, field_validator

from backend.contracts.analytics import AnalyticsModel, OpaqueId
from backend.contracts.analytics_analysis import AnalyticsSavedSnapshot
from backend.contracts.analytics_query import ChannelFollowupFacts, Sha256Hex

DASHBOARD_SCHEMA = "analytics-cockpit/v1"
FILTER_SCHEMA = "analytics-cockpit-filters/v1"
VISUAL_TABLE = "analytics-visual-table/v1"
HTTP_API_CONNECTED = "CONNECTED"
AnalysisId = Annotated[str, Field(min_length=11, max_length=128, pattern=r"^analysis_[A-Za-z0-9_.:-]{1,118}$")]


class AnalyticsCockpitCreateRequest(AnalyticsModel):
    title: Annotated[str, Field(min_length=1, max_length=120)] | None = None

    @field_validator("title")
    @classmethod
    def title_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        title = value.strip()
        if not title or any(ord(ch) < 32 or ord(ch) == 127 for ch in title):
            raise ValueError("title must be 1-120 characters without controls")
        return title


class AnalyticsCockpitAnalysisRef(AnalyticsModel):
    analysis_id: AnalysisId
    version: Annotated[int, Field(strict=True, ge=1)]


class AnalyticsCockpitLayout(AnalyticsModel):
    x: Annotated[int, Field(strict=True, ge=0)]
    y: Annotated[int, Field(strict=True, ge=0)]
    w: Annotated[int, Field(strict=True, ge=2, le=12)]
    h: Annotated[int, Field(strict=True, ge=2, le=12)]


class AnalyticsCockpitTablePlugin(AnalyticsModel):
    type: Literal["TABLE"] = "TABLE"
    version: Literal["analytics-visual-table/v1"] = VISUAL_TABLE


class AnalyticsCockpitDisplayOverrides(AnalyticsModel):
    title: Annotated[str, Field(min_length=1, max_length=120)]

    @field_validator("title")
    @classmethod
    def title_text(cls, value: str) -> str:
        title = value.strip()
        if not title or any(ord(ch) < 32 or ord(ch) == 127 for ch in title):
            raise ValueError("title must be 1-120 characters without controls")
        return title


class AnalyticsCockpitAddOp(AnalyticsModel):
    op: Literal["add"]
    analysis_ref: AnalyticsCockpitAnalysisRef
    plugin_ref: AnalyticsCockpitTablePlugin | None = None
    layout: AnalyticsCockpitLayout | None = None
    display_overrides: AnalyticsCockpitDisplayOverrides | None = None


class AnalyticsCockpitCopyOp(AnalyticsModel):
    op: Literal["copy"]
    card_id: OpaqueId


class AnalyticsCockpitRemoveOp(AnalyticsModel):
    op: Literal["remove"]
    card_id: OpaqueId


class AnalyticsCockpitLayoutOp(AnalyticsModel):
    op: Literal["layout"]
    card_id: OpaqueId
    layout: AnalyticsCockpitLayout


class AnalyticsCockpitUndoOp(AnalyticsModel):
    op: Literal["undo"]
    scope: Literal["board"]
    restore_from_version: Annotated[int, Field(strict=True, ge=1)]


AnalyticsCockpitOp = Annotated[
    Union[
        AnalyticsCockpitAddOp,
        AnalyticsCockpitCopyOp,
        AnalyticsCockpitRemoveOp,
        AnalyticsCockpitLayoutOp,
        AnalyticsCockpitUndoOp,
    ],
    Field(discriminator="op"),
]


class AnalyticsCockpitCardError(AnalyticsModel):
    code: Annotated[str, Field(min_length=1, max_length=64)]
    message: Annotated[str, Field(min_length=1, max_length=200)]


class AnalyticsCockpitCardOk(AnalyticsModel):
    card_id: OpaqueId
    plugin_ref: AnalyticsCockpitTablePlugin
    analysis_ref: AnalyticsCockpitAnalysisRef
    data_mode: Literal["SNAPSHOT"]
    layout: AnalyticsCockpitLayout
    display_overrides: dict[str, str]
    filter_mapping: dict[str, str]
    local_filters: dict[str, list[str]]
    snapshot: AnalyticsSavedSnapshot
    facts: ChannelFollowupFacts
    filter_hash: Sha256Hex
    limitations: list[str]
    effective_spec_hash: Sha256Hex
    freshness: Literal["PINNED"]
    source_status: Literal["OK"] = "OK"


class AnalyticsCockpitCardUnavailable(AnalyticsModel):
    card_id: OpaqueId
    analysis_ref: AnalyticsCockpitAnalysisRef | None = None
    data_mode: Literal["SNAPSHOT"] = "SNAPSHOT"
    layout: AnalyticsCockpitLayout
    plugin_ref: AnalyticsCockpitTablePlugin | None = None
    freshness: Literal["PINNED"] = "PINNED"
    source_status: Literal["UNAVAILABLE"] = "UNAVAILABLE"
    error: AnalyticsCockpitCardError


AnalyticsCockpitCard = Annotated[
    Union[AnalyticsCockpitCardOk, AnalyticsCockpitCardUnavailable],
    Field(discriminator="source_status"),
]


class AnalyticsCockpitFilters(AnalyticsModel):
    schema_version: Literal["analytics-cockpit-filters/v1"] = FILTER_SCHEMA
    channel_ids: list[str]


class AnalyticsDashboard(AnalyticsModel):
    schema_version: Literal["analytics-cockpit/v1"] = DASHBOARD_SCHEMA
    dashboard_id: OpaqueId
    version: Annotated[int, Field(strict=True, ge=1)]
    base_version: Annotated[int, Field(strict=True, ge=1)]
    title: str
    owner_id: OpaqueId
    visibility: Literal["PRIVATE"]
    cards: list[AnalyticsCockpitCard]
    global_filters: AnalyticsCockpitFilters
    created_at: str
    preview: bool
    persisted: bool
    affected_card_ids: list[OpaqueId]
    finite_mock: Literal[True]
    http_api: Literal["CONNECTED"] = HTTP_API_CONNECTED


class AnalyticsDashboardListItem(AnalyticsModel):
    schema_version: Literal["analytics-cockpit/v1"] = DASHBOARD_SCHEMA
    dashboard_id: OpaqueId
    version: Annotated[int, Field(strict=True, ge=1)]
    title: str
    visibility: Literal["PRIVATE"]
    card_count: Annotated[int, Field(strict=True, ge=0)]
    finite_mock: Literal[True]
    http_api: Literal["CONNECTED"] = HTTP_API_CONNECTED


class AnalyticsDashboardList(AnalyticsModel):
    schema_version: Literal["analytics-cockpit/v1"] = DASHBOARD_SCHEMA
    items: list[AnalyticsDashboardListItem]
