"""HTTP contract for private first-purchase SNAPSHOT cockpits.

Store documents keep http_api=NOT_CONNECTED. This surface is CONNECTED only.
HTTP add binds a saved first-purchase analysis version; it does not accept caller facts.
Channel cockpit/v1 cards cannot be posted here.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field, field_validator, model_validator

from backend.contracts.analytics import AnalyticsModel, OpaqueId
from backend.contracts.analytics_first_purchase import FirstPurchaseFacts, Sha256Hex
from backend.contracts.analytics_first_purchase_analysis import FirstPurchaseSavedSnapshot

DASHBOARD_SCHEMA = "analytics-first-purchase-cockpit/v1"
FILTER_SCHEMA = "analytics-first-purchase-cockpit-filters/v1"
VISUAL_TABLE = "analytics-visual-table/v1"
HTTP_API_CONNECTED = "CONNECTED"
GRID_COLUMNS = 12
GRID_MAX_ROW = 240
AnalysisId = Annotated[str, Field(min_length=11, max_length=128, pattern=r"^analysis_[A-Za-z0-9_.:-]{1,118}$")]


class FirstPurchaseCockpitCreateRequest(AnalyticsModel):
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


class FirstPurchaseCockpitAnalysisRef(AnalyticsModel):
    analysis_id: AnalysisId
    version: Annotated[int, Field(strict=True, ge=1)]


class FirstPurchaseCockpitLayout(AnalyticsModel):
    x: Annotated[int, Field(strict=True, ge=0, le=10)]
    y: Annotated[int, Field(strict=True, ge=0, le=GRID_MAX_ROW)]
    w: Annotated[int, Field(strict=True, ge=2, le=12)]
    h: Annotated[int, Field(strict=True, ge=2, le=12)]

    @model_validator(mode="after")
    def grid_bounds(self):
        if self.x + self.w > GRID_COLUMNS:
            raise ValueError("layout exceeds the 12-column grid")
        return self


class FirstPurchaseCockpitTablePlugin(AnalyticsModel):
    type: Literal["TABLE"] = "TABLE"
    version: Literal["analytics-visual-table/v1"] = VISUAL_TABLE


class FirstPurchaseCockpitDisplayOverrides(AnalyticsModel):
    title: Annotated[str, Field(min_length=1, max_length=120)]

    @field_validator("title")
    @classmethod
    def title_text(cls, value: str) -> str:
        title = value.strip()
        if not title or any(ord(ch) < 32 or ord(ch) == 127 for ch in title):
            raise ValueError("title must be 1-120 characters without controls")
        return title


class FirstPurchaseCockpitAddOp(AnalyticsModel):
    op: Literal["add"]
    analysis_ref: FirstPurchaseCockpitAnalysisRef
    plugin_ref: FirstPurchaseCockpitTablePlugin | None = None
    layout: FirstPurchaseCockpitLayout | None = None
    display_overrides: FirstPurchaseCockpitDisplayOverrides | None = None


class FirstPurchaseCockpitCopyOp(AnalyticsModel):
    op: Literal["copy"]
    card_id: OpaqueId


class FirstPurchaseCockpitRemoveOp(AnalyticsModel):
    op: Literal["remove"]
    card_id: OpaqueId


class FirstPurchaseCockpitLayoutOp(AnalyticsModel):
    op: Literal["layout"]
    card_id: OpaqueId
    layout: FirstPurchaseCockpitLayout


class FirstPurchaseCockpitUndoOp(AnalyticsModel):
    op: Literal["undo"]
    scope: Literal["board"]
    restore_from_version: Annotated[int, Field(strict=True, ge=1)]


FirstPurchaseCockpitOp = Annotated[
    Union[
        FirstPurchaseCockpitAddOp,
        FirstPurchaseCockpitCopyOp,
        FirstPurchaseCockpitRemoveOp,
        FirstPurchaseCockpitLayoutOp,
        FirstPurchaseCockpitUndoOp,
    ],
    Field(discriminator="op"),
]


class FirstPurchaseCockpitCardError(AnalyticsModel):
    code: Annotated[str, Field(min_length=1, max_length=64)]
    message: Annotated[str, Field(min_length=1, max_length=200)]


class FirstPurchaseCockpitCardOk(AnalyticsModel):
    card_id: OpaqueId
    plugin_ref: FirstPurchaseCockpitTablePlugin
    analysis_ref: FirstPurchaseCockpitAnalysisRef
    data_mode: Literal["SNAPSHOT"]
    layout: FirstPurchaseCockpitLayout
    display_overrides: dict[str, str]
    filter_mapping: dict[str, str]
    local_filters: dict[str, list[str]]
    snapshot: FirstPurchaseSavedSnapshot
    facts: FirstPurchaseFacts
    filter_hash: Sha256Hex
    limitations: list[str]
    effective_spec_hash: Sha256Hex
    freshness: Literal["PINNED"]
    source_status: Literal["OK"] = "OK"


class FirstPurchaseCockpitCardUnavailable(AnalyticsModel):
    card_id: OpaqueId
    analysis_ref: FirstPurchaseCockpitAnalysisRef | None = None
    data_mode: Literal["SNAPSHOT"] = "SNAPSHOT"
    layout: FirstPurchaseCockpitLayout
    plugin_ref: FirstPurchaseCockpitTablePlugin | None = None
    freshness: Literal["PINNED"] = "PINNED"
    source_status: Literal["UNAVAILABLE"] = "UNAVAILABLE"
    error: FirstPurchaseCockpitCardError


FirstPurchaseCockpitCard = Annotated[
    Union[FirstPurchaseCockpitCardOk, FirstPurchaseCockpitCardUnavailable],
    Field(discriminator="source_status"),
]


class FirstPurchaseCockpitFilters(AnalyticsModel):
    schema_version: Literal["analytics-first-purchase-cockpit-filters/v1"] = FILTER_SCHEMA
    channel_ids: list[str]


class FirstPurchaseDashboard(AnalyticsModel):
    schema_version: Literal["analytics-first-purchase-cockpit/v1"] = DASHBOARD_SCHEMA
    dashboard_id: OpaqueId
    version: Annotated[int, Field(strict=True, ge=1)]
    base_version: Annotated[int, Field(strict=True, ge=1)]
    title: str
    owner_id: OpaqueId
    visibility: Literal["PRIVATE"]
    cards: list[FirstPurchaseCockpitCard]
    global_filters: FirstPurchaseCockpitFilters
    created_at: str
    preview: bool
    persisted: bool
    affected_card_ids: list[OpaqueId]
    finite_mock: Literal[True]
    http_api: Literal["CONNECTED"] = HTTP_API_CONNECTED


class FirstPurchaseDashboardListItem(AnalyticsModel):
    schema_version: Literal["analytics-first-purchase-cockpit/v1"] = DASHBOARD_SCHEMA
    dashboard_id: OpaqueId
    version: Annotated[int, Field(strict=True, ge=1)]
    title: str
    visibility: Literal["PRIVATE"]
    card_count: Annotated[int, Field(strict=True, ge=0)]
    finite_mock: Literal[True]
    http_api: Literal["CONNECTED"] = HTTP_API_CONNECTED


class FirstPurchaseDashboardList(AnalyticsModel):
    schema_version: Literal["analytics-first-purchase-cockpit/v1"] = DASHBOARD_SCHEMA
    items: list[FirstPurchaseDashboardListItem]
