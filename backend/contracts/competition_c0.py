"""Competition C0 shared contracts.

Maps conceptual Condition/ResultRef/BoardSpec/Patch/Audience/Action/Error/
Capabilities onto existing analytics and old-CRM types. Does not replace
channel-follow-up, saved-analysis, cockpit, first-purchase, or B0 run-kernel
schemas. Offline only: no HTTP, DuckDB, or workers.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal, Union

from pydantic import Field, field_serializer, field_validator, model_validator
from pydantic.json_schema import models_json_schema

from backend.contracts.analytics import AnalyticsErrorDetail, AnalyticsModel, OpaqueId
from backend.contracts.analytics_cockpit import (
    AnalyticsCockpitAddOp,
    AnalyticsCockpitCopyOp,
    AnalyticsCockpitDisplayOverrides,
    AnalyticsCockpitLayout,
    AnalyticsCockpitLayoutOp,
    AnalyticsCockpitRemoveOp,
    AnalyticsCockpitUndoOp,
    DASHBOARD_SCHEMA,
)
from backend.contracts.analytics_query import (
    JS_MAX_SAFE_INTEGER,
    QUERY_SCHEMA,
    Sha256Hex,
    canonical_json,
    canonical_rfc3339,
    parse_query_date,
    parse_query_datetime,
)

C0_SCHEMA = "competition-c0/v1"
C0_METRICS_CONTRACT_ID = "competition-metrics/v1"
C0_CONDITION_SCHEMA = "competition-condition/v1"
C0_RESULT_SCHEMA = "competition-result/v1"
C0_BOARD_SCHEMA = "competition-board/v1"
C0_PATCH_SCHEMA = "competition-board-patch/v1"
C0_BATCH_SCHEMA = "competition-board-batch/v1"
C0_AUDIENCE_SCHEMA = "competition-audience/v1"
C0_ACTION_SCHEMA = "competition-action/v1"
C0_ERROR_SCHEMA = "competition-error/v1"
C0_CAPABILITY_SCHEMA = "competition-capabilities/v1"
C0_FRONTEND_SCHEMA = "competition-frontend-ports/v1"
C0_HASH_VERSION = "competition-c0-filter-hash/v1"
SHANGHAI = "Asia/Shanghai"
B0_RUN_SCHEMA = "analytics-run-b0/v1"
SAVED_ANALYSIS_SCHEMA = "analytics-saved-analysis/v1"
COCKPIT_SCHEMA = DASHBOARD_SCHEMA
QUERY_RUN_SCHEMA = "analytics-run-channel-followup/v1"
FIRST_PURCHASE_SCHEMA = "analytics-first-purchase-path/v1"
HANDOFF_SCHEMA = "analytics-handoff-audience/v1"
DOCS_CONTRACTS = Path("docs/hackathon/parallel-competition-2026-09-09/contracts")

QueryDate = Annotated[date, Field()]
QueryDateTime = Annotated[datetime, Field()]
StrictCount = Annotated[int, Field(strict=True, ge=0, le=JS_MAX_SAFE_INTEGER)]
PositiveVersion = Annotated[int, Field(strict=True, ge=1)]
IdempotencyKey = Annotated[str, Field(min_length=1, max_length=200)]


def _parse_date(value: object) -> date:
    return parse_query_date(value)


def _parse_datetime(value: object) -> datetime:
    return parse_query_datetime(value)


class CompetitionModel(AnalyticsModel):
    """Same extra=forbid/frozen config as analytics contracts."""


class SupportStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    PARTIAL = "PARTIAL"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"
    NOT_CONNECTED = "NOT_CONNECTED"


class ComparisonMode(StrEnum):
    YOY_SAME_PERIOD = "YOY_SAME_PERIOD"
    LAST_WEEK_SAME_WEEKDAY = "LAST_WEEK_SAME_WEEKDAY"
    CUSTOM_DUAL_WINDOW = "CUSTOM_DUAL_WINDOW"


class SampleMode(StrEnum):
    INCLUDE = "INCLUDE"
    EXCLUDE_CURRENT_SALES_ONLY = "EXCLUDE_CURRENT_SALES_ONLY"
    EXCLUDE_AND_RECOMPUTE_HISTORY = "EXCLUDE_AND_RECOMPUTE_HISTORY"


class ScopeKind(StrEnum):
    ALL = "ALL"
    CHANNEL_IDS = "CHANNEL_IDS"
    PRODUCT_IDS = "PRODUCT_IDS"
    CHANNEL_AND_PRODUCT = "CHANNEL_AND_PRODUCT"


class SourceTense(StrEnum):
    PUBLISHED_SNAPSHOT = "PUBLISHED_SNAPSHOT"
    REBUILT_FROM_LATEST_CORRECTIONS = "REBUILT_FROM_LATEST_CORRECTIONS"


class Completeness(StrEnum):
    COMPLETE = "COMPLETE"
    EMPTY = "EMPTY"
    INSUFFICIENT = "INSUFFICIENT"
    UNSUPPORTED = "UNSUPPORTED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class BoardLayoutMode(StrEnum):
    ONE_BOARD_MULTI_BLOCK = "ONE_BOARD_MULTI_BLOCK"
    BATCH_MULTI_BOARD = "BATCH_MULTI_BOARD"


class PatchIntent(StrEnum):
    STYLE_ONLY = "STYLE_ONLY"
    FILTER_CHANGE = "FILTER_CHANGE"
    STRUCTURE = "STRUCTURE"


class CombineOp(StrEnum):
    AND = "AND"
    OR = "OR"


class NonRepurchaseKind(StrEnum):
    ORIGIN_CHANNEL_ABSENT = "ORIGIN_CHANNEL_ABSENT"
    ORIGIN_PRODUCT_ABSENT = "ORIGIN_PRODUCT_ABSENT"
    STOREWIDE_ABSENT = "STOREWIDE_ABSENT"


class MemberMark(StrEnum):
    MEMBER = "MEMBER"
    NON_MEMBER = "NON_MEMBER"
    UNKNOWN = "UNKNOWN"


class DraftStatus(StrEnum):
    DRAFT = "DRAFT"
    REVIEW_PENDING = "REVIEW_PENDING"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class SnapshotCompat(StrEnum):
    READ_OLD_SNAPSHOT = "READ_OLD_SNAPSHOT"
    ISOLATED_NEW = "ISOLATED_NEW"
    REJECT_UNSUPPORTED_VERSION = "REJECT_UNSUPPORTED_VERSION"


class InclusiveDateRange(CompetitionModel):
    start_date: QueryDate
    end_date: QueryDate
    end_bound: Literal["INCLUSIVE_CALENDAR_DAY"] = "INCLUSIVE_CALENDAR_DAY"

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def calendar_date(cls, value: object) -> date:
        return _parse_date(value)

    @model_validator(mode="after")
    def ordered(self):
        if self.start_date > self.end_date:
            raise ValueError("period start_date must be <= end_date")
        return self

    def exclusive_end_date(self) -> date:
        """Convert C0 inclusive end to channel-follow-up FIXED exclusive end."""
        return self.end_date + timedelta(days=1)


class FilterScope(CompetitionModel):
    kind: ScopeKind
    channel_ids: list[str] = Field(default_factory=list, max_length=64)
    product_ids: list[str] = Field(default_factory=list, max_length=64)

    @field_validator("channel_ids", "product_ids")
    @classmethod
    def unique_tokens(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            if type(item) is not str or not item or len(item) > 64 or "\x00" in item:
                raise ValueError("scope ids must be 1-64 character strings without NUL")
            if item in seen:
                raise ValueError("scope ids must not contain duplicates")
            seen.add(item)
            cleaned.append(item)
        return cleaned

    @model_validator(mode="after")
    def kind_matches_ids(self):
        has_ch = bool(self.channel_ids)
        has_pr = bool(self.product_ids)
        if self.kind == ScopeKind.ALL and (has_ch or has_pr):
            raise ValueError("ALL scope must use empty channel_ids and product_ids")
        if self.kind == ScopeKind.CHANNEL_IDS and (not has_ch or has_pr):
            raise ValueError("CHANNEL_IDS scope requires channel_ids and empty product_ids")
        if self.kind == ScopeKind.PRODUCT_IDS and (has_ch or not has_pr):
            raise ValueError("PRODUCT_IDS scope requires product_ids and empty channel_ids")
        if self.kind == ScopeKind.CHANNEL_AND_PRODUCT and not (has_ch and has_pr):
            raise ValueError("CHANNEL_AND_PRODUCT scope requires both id lists")
        return self


class UnknownFlag(CompetitionModel):
    code: Literal[
        "SAMPLE_CHANNEL_SET",
        "MEMBER_HISTORY",
        "F_ORDER_GRAIN_OLD_CRM",
        "NEW_OLD_CUSTOM_MONTH_CUTOFF",
        "VALID_ORDER_RULE_OLD_CRM",
    ]
    status: Literal["UNKNOWN"] = "UNKNOWN"
    note: str


class PendingDefault(CompetitionModel):
    key: str
    value: str | bool
    pending_confirmation: bool
    note: str


C0_DEFAULTS: tuple[PendingDefault, ...] = (
    PendingDefault(
        key="metric_type", value="GSV", pending_confirmation=False,
        note="工具必须显式传 GSV；旧 /audience/table 默认 GMV 不得继承。",
    ),
    PendingDefault(
        key="timezone", value="Asia/Shanghai", pending_confirmation=False,
        note="与 ChannelFollowupQueryRequest.timezone 及 W4 customer features 一致。",
    ),
    PendingDefault(
        key="end_bound", value="INCLUSIVE_CALENDAR_DAY", pending_confirmation=False,
        note="旧 CRM pay_time 闭区间。channel-follow-up FIXED 仍是开区间结束，绑定层用 exclusive_end_date()。",
    ),
    PendingDefault(
        key="data_cutoff_policy", value="T_PLUS_1_YESTERDAY", pending_confirmation=False,
        note="PeriodBuilder 使用昨天；无本月可用数据返回 EMPTY，不比较未来完整月。",
    ),
    PendingDefault(
        key="leap_day_alignment", value="CLAMP_TO_MONTH_END", pending_confirmation=False,
        note="已有 semantic.time.shift_year_clamped：目标年无该日则收敛到当月最后一天。",
    ),
    PendingDefault(
        key="sample_mode_first_purchase_rfm", value="INCLUDE", pending_confirmation=False,
        note="小样默认计入首次购买和 RFM；剔除必须显式 sample_mode。",
    ),
    PendingDefault(
        key="sample_mode_when_excluding", value="EXCLUDE_CURRENT_SALES_ONLY",
        pending_confirmation=True,
        note="待确认。推荐剔除小样只过滤本期销售；EXCLUDE_AND_RECOMPUTE_HISTORY 必须显式选择。",
    ),
    PendingDefault(
        key="board_layout_mode", value="ONE_BOARD_MULTI_BLOCK", pending_confirmation=True,
        note="待确认。推荐一组认可分析一板多块；BATCH_MULTI_BOARD 为可选显式模式。",
    ),
    PendingDefault(
        key="data_mode", value="SNAPSHOT", pending_confirmation=False,
        note="沿用 analytics-saved-analysis/v1 与 analytics-cockpit/v1。LATEST_SUCCESS 为 NOT_CONNECTED。",
    ),
    PendingDefault(
        key="auto_send", value=False, pending_confirmation=False,
        note="行动草稿不得自动发送；与 Mission DRAFT_EXPORT 不是同一对象。",
    ),
    PendingDefault(
        key="member_history", value="UNKNOWN", pending_confirmation=False,
        note="无核验过的历史会员状态时保持 UNKNOWN，不得伪装非会员。",
    ),
)


class CompetitionCondition(CompetitionModel):
    """C0 Condition. Callers must send every execution-relevant field explicitly."""

    schema_version: Literal["competition-condition/v1"] = C0_CONDITION_SCHEMA
    metrics_contract_id: Literal["competition-metrics/v1"] = C0_METRICS_CONTRACT_ID
    metric_type: Literal["GSV"]
    timezone: Literal["Asia/Shanghai"]
    current_period: InclusiveDateRange
    comparison_mode: ComparisonMode
    comparison_period: InclusiveDateRange
    sales_scope: FilterScope
    history_scope: FilterScope
    sample_mode: SampleMode
    sample_channel_ids: list[str] | None = None
    data_cutoff_policy: Literal["T_PLUS_1_YESTERDAY"]
    leap_day_alignment: Literal["CLAMP_TO_MONTH_END"]
    data_snapshot_ref: OpaqueId | None = None
    as_of: QueryDateTime | None = None
    rule_version: str | None = None

    @field_validator("schema_version", mode="before")
    @classmethod
    def reject_foreign(cls, value: object) -> object:
        if value in {B0_RUN_SCHEMA, QUERY_SCHEMA, FIRST_PURCHASE_SCHEMA, C0_SCHEMA}:
            raise ValueError("foreign analytics schema cannot be used as competition-condition/v1")
        return value

    @field_validator("as_of", mode="before")
    @classmethod
    def optional_as_of(cls, value: object) -> object:
        if value is None:
            return None
        return _parse_datetime(value)

    @field_validator("rule_version")
    @classmethod
    def rule_token(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip() or len(value) > 128 or "\x00" in value:
            raise ValueError("rule_version must be 1-128 characters without NUL")
        return value.strip()

    @field_validator("sample_channel_ids")
    @classmethod
    def sample_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if not value:
            raise ValueError("sample_channel_ids must be null or a non-empty list")
        FilterScope(kind=ScopeKind.CHANNEL_IDS, channel_ids=value, product_ids=[])
        return list(value)

    @model_validator(mode="after")
    def sample_mode_requires_ids(self):
        if self.sample_mode == SampleMode.INCLUDE:
            if self.sample_channel_ids is not None:
                raise ValueError("INCLUDE sample_mode must set sample_channel_ids to null")
        elif self.sample_channel_ids is None:
            raise ValueError("excluding sample_mode requires explicit sample_channel_ids; channel set is UNKNOWN")
        if self.sample_mode == SampleMode.EXCLUDE_AND_RECOMPUTE_HISTORY:
            if self.history_scope == self.sales_scope and self.history_scope.kind == ScopeKind.ALL:
                raise ValueError("history recompute must declare history_scope independently from sales_scope")
        return self

    @field_serializer("as_of")
    def serialize_as_of(self, value: datetime | None) -> str | None:
        return None if value is None else canonical_rfc3339(value)

    def to_channel_followup_window(self) -> dict[str, str]:
        window = self.current_period
        return {
            "kind": "FIXED",
            "start_date": window.start_date.isoformat(),
            "end_date": window.exclusive_end_date().isoformat(),
        }

    def to_audience_summary_kwargs(self) -> dict[str, Any]:
        if self.sample_mode == SampleMode.EXCLUDE_AND_RECOMPUTE_HISTORY:
            raise ValueError("old calculate_audience_summary cannot express history recompute")
        exclude = None if self.sample_mode == SampleMode.INCLUDE else list(self.sample_channel_ids or [])
        return {
            "metric_type": "GSV",
            "start_date": self.current_period.start_date.isoformat(),
            "end_date": self.current_period.end_date.isoformat(),
            "compare_start_date": self.comparison_period.start_date.isoformat(),
            "compare_end_date": self.comparison_period.end_date.isoformat(),
            "exclude_channels": exclude,
        }


def _cutoff_for(start: date) -> date:
    return start - timedelta(days=1)


def condition_hash_payload(resolved: dict[str, Any]) -> dict[str, Any]:
    return {
        "as_of": resolved["as_of"],
        "comparison_mode": resolved["comparison_mode"],
        "comparison_period": resolved["comparison_period"],
        "current_period": resolved["current_period"],
        "cutoff": resolved["cutoff"],
        "data_cutoff_policy": resolved["data_cutoff_policy"],
        "data_snapshot_ref": resolved["data_snapshot_ref"],
        "data_version": resolved["data_version"],
        "hash_version": C0_HASH_VERSION,
        "history_scope": resolved["history_scope"],
        "leap_day_alignment": resolved["leap_day_alignment"],
        "metric_type": resolved["metric_type"],
        "metrics_contract_id": resolved["metrics_contract_id"],
        "permission_scope": resolved["permission_scope"],
        "published_at": resolved["published_at"],
        "rule_version": resolved["rule_version"],
        "sales_scope": resolved["sales_scope"],
        "sample_channel_ids": resolved["sample_channel_ids"],
        "sample_mode": resolved["sample_mode"],
        "source_tense": resolved["source_tense"],
        "timezone": resolved["timezone"],
    }


class CompetitionResolvedCondition(CompetitionModel):
    schema_version: Literal["competition-condition/v1"] = C0_CONDITION_SCHEMA
    metrics_contract_id: Literal["competition-metrics/v1"] = C0_METRICS_CONTRACT_ID
    metric_type: Literal["GSV"]
    timezone: Literal["Asia/Shanghai"]
    current_period: InclusiveDateRange
    comparison_mode: ComparisonMode
    comparison_period: InclusiveDateRange
    cutoff: QueryDate
    as_of: QueryDateTime
    published_at: QueryDateTime
    event_time: QueryDateTime
    source_tense: SourceTense
    sales_scope: FilterScope
    history_scope: FilterScope
    sample_mode: SampleMode
    sample_channel_ids: list[str] | None = None
    sample_history_recomputed: bool
    sample_channel_set_status: Literal["UNKNOWN"]
    data_cutoff_policy: Literal["T_PLUS_1_YESTERDAY"]
    leap_day_alignment: Literal["CLAMP_TO_MONTH_END"]
    data_snapshot_ref: OpaqueId
    data_version: str
    rule_version: str
    warehouse_as_of: QueryDateTime | None = None
    feature_as_of: QueryDateTime | None = None
    permission_scope: OpaqueId
    actor_id: OpaqueId
    filter_hash: Sha256Hex
    ignored_filters: list[str] = Field(default_factory=list, max_length=0)
    unknown_flags: list[UnknownFlag]
    limitations: Annotated[list[str], Field(min_length=1)]

    @field_validator("cutoff", mode="before")
    @classmethod
    def cutoff_date(cls, value: object) -> date:
        return _parse_date(value)

    @field_validator("as_of", "published_at", "event_time", "warehouse_as_of", "feature_as_of", mode="before")
    @classmethod
    def instants(cls, value: object) -> object:
        if value is None:
            return None
        return _parse_datetime(value)

    @field_validator("ignored_filters")
    @classmethod
    def no_silent_drop(cls, value: list[str]) -> list[str]:
        if value:
            raise ValueError("ignored_filters must be empty; dropping filters is a contract failure")
        return []

    @model_validator(mode="after")
    def echo_invariants(self):
        expected_cutoff = _cutoff_for(self.current_period.start_date)
        if self.cutoff != expected_cutoff:
            raise ValueError("C0 cutoff is current_period.start_date minus one calendar day")
        if self.sample_mode == SampleMode.INCLUDE:
            if self.sample_channel_ids is not None or self.sample_history_recomputed:
                raise ValueError("INCLUDE must not recompute history or list sample channels")
        else:
            if not self.sample_channel_ids:
                raise ValueError("excluding sample_mode must echo executed sample_channel_ids")
            if self.sample_mode == SampleMode.EXCLUDE_CURRENT_SALES_ONLY and self.sample_history_recomputed:
                raise ValueError("EXCLUDE_CURRENT_SALES_ONLY must set sample_history_recomputed false")
            if self.sample_mode == SampleMode.EXCLUDE_AND_RECOMPUTE_HISTORY and not self.sample_history_recomputed:
                raise ValueError("history recompute must set sample_history_recomputed true")
        payload = condition_hash_payload({
            "as_of": canonical_rfc3339(self.as_of),
            "comparison_mode": self.comparison_mode.value,
            "comparison_period": self.comparison_period.model_dump(mode="json"),
            "current_period": self.current_period.model_dump(mode="json"),
            "cutoff": self.cutoff.isoformat(),
            "data_cutoff_policy": self.data_cutoff_policy,
            "data_snapshot_ref": self.data_snapshot_ref,
            "data_version": self.data_version,
            "history_scope": self.history_scope.model_dump(mode="json"),
            "leap_day_alignment": self.leap_day_alignment,
            "metric_type": self.metric_type,
            "metrics_contract_id": self.metrics_contract_id,
            "permission_scope": self.permission_scope,
            "published_at": canonical_rfc3339(self.published_at),
            "rule_version": self.rule_version,
            "sales_scope": self.sales_scope.model_dump(mode="json"),
            "sample_channel_ids": self.sample_channel_ids,
            "sample_mode": self.sample_mode.value,
            "source_tense": self.source_tense.value,
            "timezone": self.timezone,
        })
        digest = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
        if digest != self.filter_hash:
            raise ValueError("filter_hash does not match the canonical resolved condition")
        return self

    @field_serializer("as_of", "published_at", "event_time", "warehouse_as_of", "feature_as_of")
    def serialize_times(self, value: datetime | None) -> str | None:
        return None if value is None else canonical_rfc3339(value)


class ResultPage(CompetitionModel):
    offset: StrictCount
    limit: Annotated[int, Field(strict=True, ge=1, le=500)]
    total: StrictCount
    checksum: Sha256Hex
    complete: bool

    @model_validator(mode="after")
    def page_bounds(self):
        if self.offset > self.total:
            raise ValueError("page offset exceeds total")
        if self.complete and self.offset + self.limit < self.total:
            raise ValueError("complete page cannot leave unread rows")
        if not self.complete and self.offset + self.limit >= self.total:
            raise ValueError("incomplete flag requires remaining rows")
        return self


class CompetitionResultRef(CompetitionModel):
    schema_version: Literal["competition-result/v1"] = C0_RESULT_SCHEMA
    result_id: OpaqueId
    run_id: OpaqueId | None = None
    analysis_id: OpaqueId | None = None
    query_id: str
    query_version: str
    metric_id: str | None = None
    metric_version: str | None = None
    facts_schema_ref: Literal[
        "backend.contracts.analytics_query.ChannelFollowupResult",
        "backend.contracts.analytics_first_purchase.FirstPurchaseResult",
        "backend.contracts.audience.AudienceSummaryResponse",
        "backend.semantic.analytics_handoff_audience",
        "competition-result/v1#empty",
        "competition-result/v1#unsupported",
    ]
    existing_result_schema: Literal[
        "analytics-channel-followup/v1",
        "analytics-first-purchase-path/v1",
        "analytics-saved-analysis/v1",
        "analytics-run-b0/v1",
        "analytics-handoff-audience/v1",
        "none",
    ]
    completeness: Completeness
    empty_reason: Literal[
        "NO_CURRENT_MONTH_DATA",
        "EMPTY_MATURE_COHORT",
        "ZERO_COHORT",
        "PERIOD_AFTER_AS_OF",
        None,
    ] = None
    row_count: StrictCount
    page: ResultPage | None = None
    resolved_condition: CompetitionResolvedCondition
    evidence_digest: Sha256Hex | None = None
    primary_result_ref: OpaqueId | None = None
    data_mode: Literal["SNAPSHOT"]
    contains_real_data: Literal[False] = False
    limitations: Annotated[list[str], Field(min_length=1)]

    @model_validator(mode="after")
    def completeness_rules(self):
        if self.completeness == Completeness.EMPTY:
            if self.row_count != 0 or self.empty_reason is None:
                raise ValueError("EMPTY results require row_count=0 and empty_reason")
            if self.facts_schema_ref != "competition-result/v1#empty":
                raise ValueError("EMPTY results must use the empty facts ref")
        else:
            if self.empty_reason is not None:
                raise ValueError("non-EMPTY results cannot set empty_reason")
        if self.completeness == Completeness.COMPLETE and self.row_count == 0:
            raise ValueError("COMPLETE cannot have zero rows; use EMPTY")
        if self.completeness in {Completeness.FAILED, Completeness.UNSUPPORTED}:
            if self.facts_schema_ref != "competition-result/v1#unsupported":
                raise ValueError("FAILED/UNSUPPORTED must not carry another family's facts schema")
        if self.contains_real_data is not False:
            raise ValueError("C0 fixtures and competition results must set contains_real_data false")
        if self.existing_result_schema == B0_RUN_SCHEMA and self.completeness == Completeness.COMPLETE:
            raise ValueError("analytics-run-b0/v1 STUB is not a competition business result")
        return self


class CompetitionDisplayOp(CompetitionModel):
    op: Literal["display"]
    card_id: OpaqueId
    display_overrides: AnalyticsCockpitDisplayOverrides


class CompetitionFilterChangeOp(CompetitionModel):
    op: Literal["filter_change"]
    card_id: OpaqueId
    local_filters: dict[str, list[str]]

    @field_validator("local_filters")
    @classmethod
    def registered_filter_keys(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        if set(value) - {"channel_ids", "product_ids"}:
            raise ValueError("filter_change only accepts channel_ids or product_ids")
        if not value:
            raise ValueError("filter_change requires at least one local filter")
        return value


CockpitStructureOp = Annotated[
    Union[
        AnalyticsCockpitAddOp,
        AnalyticsCockpitCopyOp,
        AnalyticsCockpitRemoveOp,
        AnalyticsCockpitLayoutOp,
        AnalyticsCockpitUndoOp,
    ],
    Field(discriminator="op"),
]


class CompetitionPatchRequest(CompetitionModel):
    schema_version: Literal["competition-board-patch/v1"] = C0_PATCH_SCHEMA
    board_id: OpaqueId
    block_id: OpaqueId | None = None
    base_version: PositiveVersion
    attempt_id: OpaqueId
    idempotency_key: IdempotencyKey
    intent: PatchIntent
    cockpit_op: CockpitStructureOp | None = None
    display_op: CompetitionDisplayOp | None = None
    filter_change: CompetitionFilterChangeOp | None = None

    @model_validator(mode="after")
    def intent_payload(self):
        present = [item is not None for item in (self.cockpit_op, self.display_op, self.filter_change)]
        if sum(present) != 1:
            raise ValueError("patch must send exactly one of cockpit_op, display_op, filter_change")
        if self.intent == PatchIntent.FILTER_CHANGE:
            if self.filter_change is None:
                raise ValueError("FILTER_CHANGE requires filter_change and creates a new run")
            if self.block_id != self.filter_change.card_id:
                raise ValueError("in-flight block_id must equal filter_change.card_id")
        if self.intent == PatchIntent.STYLE_ONLY:
            if self.display_op is None and not isinstance(self.cockpit_op, AnalyticsCockpitLayoutOp):
                raise ValueError("STYLE_ONLY allows display_op or layout only")
            if self.filter_change is not None:
                raise ValueError("STYLE_ONLY cannot change filters")
        if self.intent == PatchIntent.STRUCTURE:
            if self.cockpit_op is None:
                raise ValueError("STRUCTURE requires an existing AnalyticsCockpitOp")
            if isinstance(self.cockpit_op, AnalyticsCockpitLayoutOp) and self.display_op is None:
                pass
        if self.block_id is None and self.intent != PatchIntent.STRUCTURE:
            raise ValueError("STYLE_ONLY and FILTER_CHANGE require a stable block_id")
        return self


class EndorsedResultRef(CompetitionModel):
    result_id: OpaqueId
    run_id: OpaqueId
    analysis_id: OpaqueId | None = None
    evidence_digest: Sha256Hex
    completeness: Literal["COMPLETE"] = "COMPLETE"


class BoardOperation(CompetitionModel):
    operation_id: OpaqueId
    idempotency_key: IdempotencyKey
    request_fingerprint: Sha256Hex
    layout_mode: BoardLayoutMode
    board_id: OpaqueId | None = None
    title: Annotated[str, Field(min_length=1, max_length=120)]
    endorsed_result_refs: Annotated[list[EndorsedResultRef], Field(min_length=1, max_length=20)]

    @field_validator("title")
    @classmethod
    def title_text(cls, value: str) -> str:
        title = value.strip()
        if not title or any(ord(ch) < 32 or ord(ch) == 127 for ch in title):
            raise ValueError("title must be 1-120 characters without controls")
        return title


class CompetitionBoardBatchRequest(CompetitionModel):
    schema_version: Literal["competition-board-batch/v1"] = C0_BATCH_SCHEMA
    batch_id: OpaqueId
    layout_mode: BoardLayoutMode
    operations: Annotated[list[BoardOperation], Field(min_length=1, max_length=20)]

    @model_validator(mode="after")
    def mode_and_keys(self):
        keys = [item.idempotency_key for item in self.operations]
        ops = [item.operation_id for item in self.operations]
        if len(keys) != len(set(keys)) or len(ops) != len(set(ops)):
            raise ValueError("operation_id and idempotency_key must be unique in a batch")
        if self.layout_mode == BoardLayoutMode.ONE_BOARD_MULTI_BLOCK and len(self.operations) != 1:
            raise ValueError("ONE_BOARD_MULTI_BLOCK uses a single operation with multiple endorsed results")
        for item in self.operations:
            if item.layout_mode != self.layout_mode:
                raise ValueError("operation layout_mode must match the batch")
        return self


class BoardOpReceipt(CompetitionModel):
    operation_id: OpaqueId
    board_id: OpaqueId | None
    version: PositiveVersion | None = None
    status: Literal["SUCCEEDED", "FAILED", "CONFLICT"]
    error_code: str | None = None
    retryable: bool = False


class CompetitionBoardBatchReceipt(CompetitionModel):
    schema_version: Literal["competition-board-batch/v1"] = C0_BATCH_SCHEMA
    batch_id: OpaqueId
    status: Literal["SUCCEEDED", "PARTIAL", "FAILED"]
    items: Annotated[list[BoardOpReceipt], Field(min_length=1, max_length=20)]

    @model_validator(mode="after")
    def batch_status(self):
        statuses = {item.status for item in self.items}
        if statuses == {"SUCCEEDED"} and self.status != "SUCCEEDED":
            raise ValueError("all-success receipt must be SUCCEEDED")
        if "SUCCEEDED" in statuses and statuses - {"SUCCEEDED"} and self.status != "PARTIAL":
            raise ValueError("mixed board outcomes must be PARTIAL")
        if "SUCCEEDED" not in statuses and self.status == "SUCCEEDED":
            raise ValueError("SUCCEEDED batch requires at least one succeeded board")
        return self


class CompetitionBoardSpec(CompetitionModel):
    schema_version: Literal["competition-board/v1"] = C0_BOARD_SCHEMA
    board_id: OpaqueId
    block_ids: list[OpaqueId]
    version: PositiveVersion
    base_version: PositiveVersion
    title: str
    owner_id: OpaqueId
    visibility: Literal["PRIVATE"]
    layout_mode: BoardLayoutMode
    existing_dashboard_schema: Literal["analytics-cockpit/v1"]
    data_namespace: Literal["analytics-cockpit/v1", "competition-board/v1"]
    snapshot_compat: SnapshotCompat
    data_mode: Literal["SNAPSHOT"]
    preview: bool
    persisted: bool
    batch_id: OpaqueId | None = None
    operation_id: OpaqueId | None = None
    affected_block_ids: list[OpaqueId]
    limitations: Annotated[list[str], Field(min_length=1)]

    @model_validator(mode="after")
    def namespace_rules(self):
        if self.data_namespace == "analytics-cockpit/v1" and self.snapshot_compat != SnapshotCompat.READ_OLD_SNAPSHOT:
            raise ValueError("existing cockpit SNAPSHOT boards stay READ_OLD_SNAPSHOT")
        if self.data_namespace == "competition-board/v1" and self.snapshot_compat == SnapshotCompat.READ_OLD_SNAPSHOT:
            raise ValueError("competition-board/v1 is an isolated namespace")
        if self.preview == self.persisted:
            raise ValueError("preview and persisted are mutually exclusive")
        return self


class CohortRule(CompetitionModel):
    rule_id: OpaqueId
    kind: Literal["ENROLLMENT_SNAPSHOT", "NON_REPURCHASE", "MEMBER_CROSS"]
    non_repurchase: NonRepurchaseKind | None = None
    member_mark: MemberMark
    f_threshold: Annotated[int, Field(strict=True, ge=1, le=10000)] | None = None
    f_grain_status: Literal["UNKNOWN", "W4_ORDER_GRAIN"]
    channel_ids: list[str] = Field(default_factory=list, max_length=64)
    product_ids: list[str] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def rule_shape(self):
        if self.kind == "NON_REPURCHASE" and self.non_repurchase is None:
            raise ValueError("NON_REPURCHASE rules require non_repurchase kind")
        if self.kind != "NON_REPURCHASE" and self.non_repurchase is not None:
            raise ValueError("non_repurchase is only valid on NON_REPURCHASE rules")
        if self.member_mark != MemberMark.UNKNOWN and self.kind == "MEMBER_CROSS":
            pass
        if self.f_threshold is not None and self.f_grain_status == "UNKNOWN":
            raise ValueError("F threshold cannot be applied while F grain is UNKNOWN")
        return self


class CompetitionCohortSpec(CompetitionModel):
    schema_version: Literal["competition-audience/v1"] = C0_AUDIENCE_SCHEMA
    cohort_id: OpaqueId
    enrollment_window: InclusiveDateRange
    observation_window: InclusiveDateRange
    enrollment_rule_version: str
    as_of: QueryDateTime
    published_at: QueryDateTime
    source_tense: SourceTense
    member_history_status: Literal["UNKNOWN"]
    existing_family: Literal["analytics-handoff-audience/v1", "none"]
    rules: Annotated[list[CohortRule], Field(min_length=1, max_length=8)]
    permission_scope: OpaqueId
    limitations: Annotated[list[str], Field(min_length=1)]

    @field_validator("as_of", "published_at", mode="before")
    @classmethod
    def instants(cls, value: object) -> datetime:
        return _parse_datetime(value)

    @field_serializer("as_of", "published_at")
    def serialize_times(self, value: datetime) -> str:
        return canonical_rfc3339(value)


class CandidateExplanation(CompetitionModel):
    customer_key: OpaqueId
    reasons: Annotated[list[str], Field(min_length=1, max_length=8)]


class CompetitionCandidateSet(CompetitionModel):
    schema_version: Literal["competition-audience/v1"] = C0_AUDIENCE_SCHEMA
    candidate_set_id: OpaqueId
    cohort_id: OpaqueId
    source_result_ref: OpaqueId
    combine: CombineOp
    unique_count: StrictCount
    customer_keys: list[OpaqueId]
    explanations: list[CandidateExplanation]
    auto_send: Literal[False] = False
    permission_scope: OpaqueId
    limitations: Annotated[list[str], Field(min_length=1)]

    @model_validator(mode="after")
    def set_invariants(self):
        keys = list(self.customer_keys)
        if len(keys) != len(set(keys)):
            raise ValueError("candidate customer_keys must be unique")
        if len(keys) != self.unique_count:
            raise ValueError("unique_count must equal the customer_keys set size")
        if self.unique_count == 0 and self.explanations:
            raise ValueError("zero candidates must not include fabricated explanations")
        explained = {item.customer_key for item in self.explanations}
        if explained - set(keys):
            raise ValueError("explanations must reference listed customer_keys")
        return self


class CompetitionActionDraft(CompetitionModel):
    schema_version: Literal["competition-action/v1"] = C0_ACTION_SCHEMA
    draft_id: OpaqueId
    version: PositiveVersion
    candidate_set_id: OpaqueId
    source_result_ref: OpaqueId
    status: DraftStatus
    owner_id: OpaqueId
    reviewer_id: OpaqueId | None = None
    review_by: QueryDate | None = None
    budget_cap_minor: StrictCount | None = None
    currency: Literal["CNY"] = "CNY"
    channel: str | None = None
    product_id: str | None = None
    control_design: str | None = None
    stop_condition: str | None = None
    unknowns: list[str]
    auto_send: Literal[False] = False
    expired_reason: Literal["RULE_CHANGED", "SOURCE_CHANGED"] | None = None
    copy_only_change: bool = False
    existing_mission_export: Literal["not-mission-draft-export"] = "not-mission-draft-export"
    limitations: Annotated[list[str], Field(min_length=1)]

    @field_validator("review_by", mode="before")
    @classmethod
    def optional_date(cls, value: object) -> object:
        if value is None:
            return None
        return _parse_date(value)

    @model_validator(mode="after")
    def expiry_rules(self):
        if self.status == DraftStatus.EXPIRED and self.expired_reason is None:
            raise ValueError("EXPIRED drafts require expired_reason")
        if self.copy_only_change and self.expired_reason is not None:
            raise ValueError("copy-only edits must not expire evidence")
        if self.auto_send is not False:
            raise ValueError("action drafts cannot auto-send")
        return self


class CompetitionErrorDetail(CompetitionModel):
    schema_version: Literal["competition-error/v1"] = C0_ERROR_SCHEMA
    code: Annotated[str, Field(min_length=1, max_length=64)]
    message: Annotated[str, Field(min_length=1, max_length=500)]
    param: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    retryable: bool
    retry_after: Annotated[int, Field(strict=True, ge=0, le=86400)] | None = None
    request_id: Annotated[str, Field(min_length=1, max_length=128)]
    doc_ref: Annotated[str, Field(min_length=1, max_length=256)] | None = None
    recovery_url: Annotated[str, Field(min_length=1, max_length=256)] | None = None
    http_status: Annotated[int, Field(strict=True, ge=400, le=599)]
    maps_to: Literal["backend.contracts.analytics.AnalyticsErrorDetail"]

    @model_validator(mode="after")
    def retry_fields(self):
        if self.retry_after is not None and not self.retryable:
            raise ValueError("retry_after requires retryable true")
        return self

    def as_b0_error_detail(self) -> AnalyticsErrorDetail:
        return AnalyticsErrorDetail(
            code=self.code, message=self.message, retryable=self.retryable,
            request_id=self.request_id, recovery_url=self.recovery_url,
        )


class CompetitionErrorResponse(CompetitionModel):
    error: CompetitionErrorDetail


class CompetitionCapability(CompetitionModel):
    schema_version: Literal["competition-capabilities/v1"] = C0_CAPABILITY_SCHEMA
    capability_id: OpaqueId
    title: str
    concept: Literal["Condition", "ResultRef", "BoardSpec", "Patch", "Audience", "Action", "Error", "Capabilities", "FrontendPort"]
    support_status: SupportStatus
    existing_types: list[str]
    http_mapping: str | None = None
    service_mapping: str | None = None
    w4_mapping: str | None = None
    required_capabilities: list[str]
    actor_filtered: Literal[True] = True
    backend_recheck: Literal[True] = True
    unknown_flags: list[str] = Field(default_factory=list)
    notes: str


class CompetitionFrontendPort(CompetitionModel):
    schema_version: Literal["competition-frontend-ports/v1"] = C0_FRONTEND_SCHEMA
    port_id: OpaqueId
    owner: Literal["A4", "A5", "A6", "A7", "A8"]
    name: str
    signature: str
    support_status: Literal["NOT_CONNECTED"] = "NOT_CONNECTED"
    notes: str


class CompetitionConceptMap(CompetitionModel):
    concept: str
    c0_type: str
    existing_types: list[str]
    notes: str


CONCEPT_MAP: tuple[CompetitionConceptMap, ...] = (
    CompetitionConceptMap(
        concept="Condition", c0_type="CompetitionCondition",
        existing_types=[
            "backend.contracts.analytics_query.ChannelFollowupQueryRequest",
            "backend.contracts.audience.AudienceSummaryRequest",
            "backend.semantic.filters.FilterBuilder",
            "backend.semantic.time.DateRange",
            "backend.contracts.analytics.AnalyticsRunRequest.condition_patch=None",
        ],
        notes="B0/query-run condition_patch remains None. C0 is the shared explicit object; old HTTP is a partial projection.",
    ),
    CompetitionConceptMap(
        concept="ResultRef", c0_type="CompetitionResultRef",
        existing_types=[
            "backend.contracts.analytics.AnalyticsRunSnapshot.primary_result_ref",
            "backend.contracts.analytics_query.ChannelFollowupResult",
            "backend.contracts.analytics_analysis.AnalyticsSavedSnapshot",
            "backend.contracts.analytics_query.ChannelFollowupResolvedFilters",
        ],
        notes="Reuse existing facts schemas by facts_schema_ref. Do not treat B0 STUB as a business result.",
    ),
    CompetitionConceptMap(
        concept="BoardSpec", c0_type="CompetitionBoardSpec",
        existing_types=[
            "backend.contracts.analytics_cockpit.AnalyticsDashboard",
            "dashboard_id→board_id",
            "card_id→block_id",
            "base_version",
        ],
        notes="analytics-cockpit/v1 SNAPSHOT stays readable. competition-board/v1 is an isolated namespace; no silent migration.",
    ),
    CompetitionConceptMap(
        concept="Patch", c0_type="CompetitionPatchRequest",
        existing_types=[
            "backend.contracts.analytics_cockpit.AnalyticsCockpitOp",
            "backend.services.analytics.cockpit.PATCH_FIELDS",
        ],
        notes="STYLE_ONLY must not query. FILTER_CHANGE creates a new run and is NOT_CONNECTED on current cockpit HTTP.",
    ),
    CompetitionConceptMap(
        concept="Audience", c0_type="CompetitionCohortSpec/CompetitionCandidateSet",
        existing_types=[
            "backend.semantic.analytics_handoff_audience",
            "backend.contracts.audience.AudienceRow",
            "backend.services.analytics.family_handoff_audience",
        ],
        notes="handoff-audience is sample-to-full, not last-year F≥4. T05 cohort is a new A8 computation.",
    ),
    CompetitionConceptMap(
        concept="Action", c0_type="CompetitionActionDraft",
        existing_types=["backend.contracts.mission.ExportResponse.DRAFT_EXPORT_READY"],
        notes="Mission DRAFT_EXPORT is experiment-arm export, not recall action drafts. auto_send is always false.",
    ),
    CompetitionConceptMap(
        concept="Error", c0_type="CompetitionErrorDetail",
        existing_types=[
            "backend.contracts.analytics.AnalyticsErrorDetail",
            "backend.services.analytics.access.AnalyticsError",
        ],
        notes="B0 subset lacks param/retry_after/doc_ref. C0 requires them; maps_to AnalyticsErrorDetail.",
    ),
    CompetitionConceptMap(
        concept="Capabilities", c0_type="CompetitionCapability",
        existing_types=[
            "backend.services.analytics.access.AnalyticsPrincipal",
            "backend.services.analytics.catalog.QUERY_FAMILIES",
            "dashboard:read/dashboard:update/analysis:save/analysis:read",
        ],
        notes="Catalog is actor-filtered; backend still re-checks. HTTP catalog is NOT_CONNECTED.",
    ),
)


SUPPORT_MATRIX: tuple[CompetitionCapability, ...] = (
    CompetitionCapability(
        capability_id="diag.gsv", title="GSV 下降", concept="Condition",
        support_status=SupportStatus.PARTIAL,
        existing_types=["AudienceSummaryRequest.metric_type", "FilterBuilder.with_metric_type(MetricType.GSV)"],
        http_mapping="POST /api/v1/audience/summary",
        service_mapping="backend.services.metrics.audience_summary.calculate_audience_summary",
        w4_mapping="amount_unit minor / currency CNY on synthetic warehouse",
        required_capabilities=["analysis:read"],
        notes="C0 tools must send GSV. Old /audience/table defaults to GMV and is not the competition default.",
    ),
    CompetitionCapability(
        capability_id="diag.yoy", title="去年同期", concept="Condition",
        support_status=SupportStatus.PARTIAL,
        existing_types=["PeriodBuilder.free", "shift_year_clamped", "AudienceSummaryRequest.compare_*"],
        http_mapping="POST /api/v1/audience/summary compare_start_date/compare_end_date",
        service_mapping="backend.semantic.time.PeriodBuilder",
        required_capabilities=["analysis:read"],
        notes="Leap days clamp to month end. Custom audience_summary cutoff still uses month-start; C0 cutoff is start-1.",
        unknown_flags=["NEW_OLD_CUSTOM_MONTH_CUTOFF"],
    ),
    CompetitionCapability(
        capability_id="diag.last_week_same_weekday", title="上周同星期", concept="Condition",
        support_status=SupportStatus.PARTIAL,
        existing_types=["PeriodBuilder.wtd"],
        service_mapping="backend.semantic.time.PeriodBuilder.wtd",
        required_capabilities=["analysis:read"],
        notes="Existing WTD is week-to-date vs last week WTD, not an arbitrary window's last-week same weekday. Resolver is new.",
    ),
    CompetitionCapability(
        capability_id="diag.promo_dual_window", title="大促自选两段", concept="Condition",
        support_status=SupportStatus.PARTIAL,
        existing_types=["AudienceSummaryRequest.compare_start_date/compare_end_date"],
        http_mapping="POST /api/v1/audience/summary",
        service_mapping="calculate_audience_summary",
        required_capabilities=["analysis:read"],
        notes="Comparison dates exist on summary POST. Must be echoed as actual execution windows.",
    ),
    CompetitionCapability(
        capability_id="diag.channel", title="渠道下降贡献", concept="ResultRef",
        support_status=SupportStatus.PARTIAL,
        existing_types=["AudienceSummaryResponse.channel_all", "ChannelFollowupResult"],
        http_mapping="POST /api/v1/audience/summary; channel-follow-up query family",
        service_mapping="calculate_audience_summary / analytics_channel_followup",
        required_capabilities=["analysis:read"],
        notes="Channel-follow-up product_ids stay empty-array const. Competition product scope is a different bind.",
    ),
    CompetitionCapability(
        capability_id="diag.sample_exclude_current", title="剔除小样（仅本期销售）", concept="Condition",
        support_status=SupportStatus.PARTIAL,
        existing_types=["FilterBuilder.with_exclude_channels", "AudienceSummaryRequest.exclude_channels"],
        http_mapping="exclude_channels on /audience/summary and /audience/table",
        service_mapping="FilterBuilder.with_exclude_channels",
        required_capabilities=["analysis:read"],
        unknown_flags=["SAMPLE_CHANNEL_SET"],
        notes="Channel set is UNKNOWN: sampling_service uses U先派样/百补派样; category_service adds 赠品&0.01/其他. Do not freeze a guessed set.",
    ),
    CompetitionCapability(
        capability_id="diag.sample_recompute_history", title="剔除小样并重算历史", concept="Condition",
        support_status=SupportStatus.UNSUPPORTED,
        existing_types=["none"],
        service_mapping="none; A2 must add an explicit history-scope path",
        required_capabilities=["analysis:read"],
        unknown_flags=["SAMPLE_CHANNEL_SET"],
        notes="No old-CRM path recomputes new/old or RFM after excluding sample from history. C0 only defines the explicit mode.",
    ),
    CompetitionCapability(
        capability_id="diag.new_old", title="新老客（分析 start 前）", concept="Condition",
        support_status=SupportStatus.PARTIAL,
        existing_types=["DateRange.cutoff=start-1", "calculate_audience_summary custom month-start cutoff"],
        service_mapping="backend.semantic.time.DateRange; audience_summary.py custom branch",
        required_capabilities=["analysis:read"],
        unknown_flags=["NEW_OLD_CUSTOM_MONTH_CUTOFF"],
        notes="C0 cutoff is analysis start minus one day. Old custom summary uses month-start minus one day and is LEGACY_INCOMPATIBLE.",
    ),
    CompetitionCapability(
        capability_id="diag.member", title="会员交叉", concept="Condition",
        support_status=SupportStatus.PARTIAL,
        existing_types=["OrderFilters.is_member", "AudienceRow.member_*"],
        service_mapping="backend.semantic.filters.OrderFilters.is_member",
        required_capabilities=["analysis:read"],
        unknown_flags=["MEMBER_HISTORY"],
        notes="Current-order is_member is not last-year membership. Historical member mark is UNKNOWN.",
    ),
    CompetitionCapability(
        capability_id="diag.product", title="产品下钻", concept="Condition",
        support_status=SupportStatus.PARTIAL,
        existing_types=["AudienceTableRequest.dimension", "ChannelFollowupQueryRequest.product_ids=empty"],
        http_mapping="/api/v1/audience/table dimension=spu_*",
        required_capabilities=["analysis:read"],
        notes="channel-follow-up rejects any product filter. Bind layer must 422 rather than drop product_ids.",
    ),
    CompetitionCapability(
        capability_id="diag.rfm", title="RFM 交叉", concept="ResultRef",
        support_status=SupportStatus.PARTIAL,
        existing_types=["backend.services.rfm", "W4 valid_order_count"],
        w4_mapping="backend.services.analytics.customer_features.contract ORDER_GRAIN=(synthetic_user_id,order_id)",
        required_capabilities=["analysis:read"],
        unknown_flags=["F_ORDER_GRAIN_OLD_CRM", "VALID_ORDER_RULE_OLD_CRM"],
        notes="W4 F is valid order count at header grain. Old CRM RFM F grain is UNKNOWN until A2 verifies it is not line COUNT(*).",
    ),
    CompetitionCapability(
        capability_id="diag.fixed_cohort", title="去年固定 cohort 本期回购", concept="Audience",
        support_status=SupportStatus.UNSUPPORTED,
        existing_types=["analytics-handoff-audience/v1 (different rule)"],
        w4_mapping="valid_order_count / first_paid_at / last_paid_at",
        required_capabilities=["cohort:read"],
        unknown_flags=["F_ORDER_GRAIN_OLD_CRM", "MEMBER_HISTORY"],
        notes="handoff-audience is first-channel sample→full, not last-year F≥4 frozen membership. T05 is A8 new compute.",
    ),
    CompetitionCapability(
        capability_id="diag.non_repurchase", title="三种未回购", concept="Audience",
        support_status=SupportStatus.UNSUPPORTED,
        existing_types=["none"],
        required_capabilities=["cohort:read"],
        notes="ORIGIN_CHANNEL_ABSENT / ORIGIN_PRODUCT_ABSENT / STOREWIDE_ABSENT are C0 enums only until A8 implements them.",
    ),
    CompetitionCapability(
        capability_id="asset.save_snapshot", title="保存 SNAPSHOT 分析", concept="ResultRef",
        support_status=SupportStatus.SUPPORTED,
        existing_types=["AnalyticsSavedAnalysis", "SavedAnalysisStore"],
        http_mapping="POST /api/v1/analytics/analyses",
        required_capabilities=["analysis:save"],
        notes="Existing CONNECTED saved-analysis HTTP. C0 endorsements bind these result refs.",
    ),
    CompetitionCapability(
        capability_id="board.single_cockpit", title="单板驾驶舱", concept="BoardSpec",
        support_status=SupportStatus.PARTIAL,
        existing_types=["AnalyticsDashboard", "AnalyticsCockpitOp"],
        http_mapping="POST/GET /api/v1/analytics/dashboards",
        required_capabilities=["dashboard:read", "dashboard:update"],
        notes="One private SNAPSHOT board with TABLE cards. Batch multi-board and FILTER_CHANGE are not on this HTTP.",
    ),
    CompetitionCapability(
        capability_id="board.batch", title="认可后批量成板", concept="BoardSpec",
        support_status=SupportStatus.NOT_CONNECTED,
        existing_types=["CompetitionBoardBatchRequest"],
        required_capabilities=["dashboard:update", "analysis:read"],
        notes="Schema frozen. A5 implements persistence. Same-idempotency-key different payload is 409.",
    ),
    CompetitionCapability(
        capability_id="board.patch_409", title="版本冲突", concept="Patch",
        support_status=SupportStatus.SUPPORTED,
        existing_types=["CockpitStore.apply If-Match", "AnalyticsError 409"],
        http_mapping="POST /api/v1/analytics/dashboards/{id}/versions",
        required_capabilities=["dashboard:update"],
        notes="Existing cockpit 409 does not overwrite. C0 adds param/retry_after/doc_ref on the error body.",
    ),
    CompetitionCapability(
        capability_id="action.draft", title="行动草稿", concept="Action",
        support_status=SupportStatus.NOT_CONNECTED,
        existing_types=["Mission ExportResponse is a different object"],
        required_capabilities=["draft:write"],
        notes="No auto send. Rule/source changes expire drafts; copy-only edits do not.",
    ),
    CompetitionCapability(
        capability_id="catalog.http", title="能力目录 HTTP", concept="Capabilities",
        support_status=SupportStatus.NOT_CONNECTED,
        existing_types=["QUERY_FAMILIES", "AnalyticsPrincipal"],
        http_mapping="GET /api/v1/analytics/catalog (planned, not wired)",
        required_capabilities=[],
        notes="C0 freezes the catalog document. A3 maps live calls. Actor filter does not replace backend checks.",
    ),
)


FRONTEND_PORTS: tuple[CompetitionFrontendPort, ...] = (
    CompetitionFrontendPort(
        port_id="a4.theme_tokens", owner="A4", name="theme_tokens_export",
        signature="export function competitionThemeTokens(): Readonly<Record<string, string>>",
        notes="A4 owns global styles/brand. A6 consumes tokens; does not rewrite DESIGN.md.",
    ),
    CompetitionFrontendPort(
        port_id="a4.shell_slots", owner="A4", name="shell_slots",
        signature="slots: ask | analysis | cockpit | actions",
        notes="Native DSH slots remain reachable. Competition UI mounts inside these slots.",
    ),
    CompetitionFrontendPort(
        port_id="a6.mount", owner="A6", name="mount_dispose",
        signature="mount(el, props): { dispose(): void }",
        notes="A6 board/actions UI. Dispose must drop listeners; in-flight board_id is not stored only in React state.",
    ),
    CompetitionFrontendPort(
        port_id="a6.selection", owner="A6", name="selection_scope",
        signature="{ board_id: OpaqueId, block_id: OpaqueId, base_version: number }",
        notes="UI selection cannot rewrite FastAPI in-flight patch target.",
    ),
    CompetitionFrontendPort(
        port_id="a7.selected_edit", owner="A7", name="selected_edit_event",
        signature="event: { board_id, block_id, base_version, intent: PatchIntent }",
        notes="A7 emits controlled patch requests. Illegal paths/scripts are contract failures.",
    ),
    CompetitionFrontendPort(
        port_id="a5.transport", owner="A5", name="board_transport",
        signature="preview/apply/batch(principal, payload, If-Match, Idempotency-Key)",
        notes="HTTP registration stays with Grok. Transport must send C0 BoardSpec/Patch types.",
    ),
    CompetitionFrontendPort(
        port_id="a8.transport", owner="A8", name="audience_transport",
        signature="previewCandidates/saveDraft(principal, payload)",
        notes="customer_key stays inside permission_scope. No cross-brand identity join as access.",
    ),
)


OPENAPI_MODELS = (
    InclusiveDateRange,
    FilterScope,
    UnknownFlag,
    PendingDefault,
    CompetitionCondition,
    CompetitionResolvedCondition,
    ResultPage,
    CompetitionResultRef,
    CompetitionDisplayOp,
    CompetitionFilterChangeOp,
    CompetitionPatchRequest,
    EndorsedResultRef,
    BoardOperation,
    CompetitionBoardBatchRequest,
    BoardOpReceipt,
    CompetitionBoardBatchReceipt,
    CompetitionBoardSpec,
    CohortRule,
    CompetitionCohortSpec,
    CandidateExplanation,
    CompetitionCandidateSet,
    CompetitionActionDraft,
    CompetitionErrorDetail,
    CompetitionErrorResponse,
    CompetitionCapability,
    CompetitionFrontendPort,
    CompetitionConceptMap,
    AnalyticsCockpitAddOp,
    AnalyticsCockpitCopyOp,
    AnalyticsCockpitRemoveOp,
    AnalyticsCockpitLayoutOp,
    AnalyticsCockpitUndoOp,
    AnalyticsCockpitLayout,
    AnalyticsCockpitDisplayOverrides,
)


def c0_openapi() -> dict:
    keyed, document = models_json_schema(
        [(model, "validation") for model in OPENAPI_MODELS],
        ref_template="#/components/schemas/{model}",
    )
    definitions = dict(document.get("$defs", {}))
    for (model, _mode), item in keyed.items():
        definitions.setdefault(model.__name__, item)
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "competition-c0/v1 shared contracts",
            "description": (
                "Offline C0 catalog. paths is empty: this unit does not implement HTTP. "
                "Conceptual Condition/ResultRef/BoardSpec/Patch/Audience/Action/Error/Capabilities "
                "map onto existing analytics and old-CRM types. Integer wire fields cap at "
                f"{JS_MAX_SAFE_INTEGER}. Ratios stay 0-1 on reused analytics facts schemas. "
                "Do not use analytics-run-b0/v1 as a business result."
            ),
            "version": C0_SCHEMA,
        },
        "paths": {},
        "components": {"schemas": definitions},
        "x-not-an-http-api": True,
        "x-c0-schema": C0_SCHEMA,
        "x-b0-run-schema-untouched": B0_RUN_SCHEMA,
        "x-existing-query-schema": QUERY_SCHEMA,
        "x-existing-cockpit-schema": COCKPIT_SCHEMA,
        "x-existing-saved-analysis-schema": SAVED_ANALYSIS_SCHEMA,
        "x-js-max-safe-integer": JS_MAX_SAFE_INTEGER,
    }


def _field_catalog(model: type[CompetitionModel]) -> dict[str, Any]:
    schema = model.model_json_schema()
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    rows = []
    for name, spec in properties.items():
        any_of = spec.get("anyOf", []) if isinstance(spec, dict) else []
        rows.append({
            "name": name,
            "required": name in required,
            "nullable": spec.get("type") == "null" or spec.get("type") == ["string", "null"] or any(
                isinstance(item, dict) and item.get("type") == "null" for item in any_of
            ),
            "enum": spec.get("enum") or next(
                (item.get("enum") for item in any_of if isinstance(item, dict) and "enum" in item),
                None,
            ),
            "description": spec.get("description") or spec.get("title") or "",
            "schema": spec,
        })
    version_field = model.model_fields.get("schema_version")
    return {
        "model": model.__name__,
        "schema_version": None if version_field is None else version_field.default,
        "fields": rows,
    }


AS_OF = "2026-08-31T16:00:00.000000+00:00"
PUBLISHED = "2026-08-31T16:00:00.000000+00:00"
ACTOR_A = "analyst.brand-a"
ACTOR_B = "analyst.brand-b"
SCOPE_A = "scope-brand-a"
DIGEST_A = "a" * 64


def _scope_all() -> dict[str, Any]:
    return {"kind": "ALL", "channel_ids": [], "product_ids": []}


def _period(start: str, end: str) -> dict[str, str]:
    return {"start_date": start, "end_date": end, "end_bound": "INCLUSIVE_CALENDAR_DAY"}


def _unknown_flags() -> list[dict[str, str]]:
    return [
        {"code": "SAMPLE_CHANNEL_SET", "status": "UNKNOWN",
         "note": "派样渠道集合未在 C0 冻结；执行必须回显实际 sample_channel_ids。"},
        {"code": "MEMBER_HISTORY", "status": "UNKNOWN",
         "note": "无核验历史会员状态，不得把 UNKNOWN 当非会员。"},
        {"code": "F_ORDER_GRAIN_OLD_CRM", "status": "UNKNOWN",
         "note": "旧 CRM RFM F 粒度未核清；W4 仅声明 (synthetic_user_id, order_id)。"},
        {"code": "NEW_OLD_CUSTOM_MONTH_CUTOFF", "status": "UNKNOWN",
         "note": "audience_summary 自定义日期仍用月初 cutoff；C0 要求 start-1。"},
        {"code": "VALID_ORDER_RULE_OLD_CRM", "status": "UNKNOWN",
         "note": "旧有效订单规则以 FilterBuilder.valid_order 为准，不在 C0 另造阈值。"},
    ]


def make_resolved(*, sample_mode: str, sample_ids: list[str] | None,
                  history_recomputed: bool, data_version: str, rule_version: str,
                  snapshot: str, extra_limit: str) -> CompetitionResolvedCondition:
    current = InclusiveDateRange(start_date=date(2026, 8, 1), end_date=date(2026, 8, 31))
    comparison = InclusiveDateRange(start_date=date(2025, 8, 1), end_date=date(2025, 8, 31))
    cutoff = _cutoff_for(current.start_date)
    as_of = _parse_datetime(AS_OF)
    published = _parse_datetime(PUBLISHED)
    payload = condition_hash_payload({
        "as_of": canonical_rfc3339(as_of),
        "comparison_mode": ComparisonMode.YOY_SAME_PERIOD.value,
        "comparison_period": comparison.model_dump(mode="json"),
        "current_period": current.model_dump(mode="json"),
        "cutoff": cutoff.isoformat(),
        "data_cutoff_policy": "T_PLUS_1_YESTERDAY",
        "data_snapshot_ref": snapshot,
        "data_version": data_version,
        "history_scope": _scope_all(),
        "leap_day_alignment": "CLAMP_TO_MONTH_END",
        "metric_type": "GSV",
        "metrics_contract_id": C0_METRICS_CONTRACT_ID,
        "permission_scope": SCOPE_A,
        "published_at": canonical_rfc3339(published),
        "rule_version": rule_version,
        "sales_scope": _scope_all(),
        "sample_channel_ids": sample_ids,
        "sample_mode": sample_mode,
        "source_tense": SourceTense.PUBLISHED_SNAPSHOT.value,
        "timezone": SHANGHAI,
    })
    return CompetitionResolvedCondition.model_validate({
        "metric_type": "GSV",
        "timezone": SHANGHAI,
        "current_period": current.model_dump(mode="json"),
        "comparison_mode": "YOY_SAME_PERIOD",
        "comparison_period": comparison.model_dump(mode="json"),
        "cutoff": cutoff.isoformat(),
        "as_of": AS_OF,
        "published_at": PUBLISHED,
        "event_time": AS_OF,
        "source_tense": "PUBLISHED_SNAPSHOT",
        "sales_scope": _scope_all(),
        "history_scope": _scope_all(),
        "sample_mode": sample_mode,
        "sample_channel_ids": sample_ids,
        "sample_history_recomputed": history_recomputed,
        "sample_channel_set_status": "UNKNOWN",
        "data_cutoff_policy": "T_PLUS_1_YESTERDAY",
        "leap_day_alignment": "CLAMP_TO_MONTH_END",
        "data_snapshot_ref": snapshot,
        "data_version": data_version,
        "rule_version": rule_version,
        "warehouse_as_of": AS_OF,
        "feature_as_of": AS_OF,
        "permission_scope": SCOPE_A,
        "actor_id": ACTOR_A,
        "filter_hash": hashlib.sha256(canonical_json(payload).encode()).hexdigest(),
        "ignored_filters": [],
        "unknown_flags": _unknown_flags(),
        "limitations": [
            extra_limit,
            "C0 不把 B0 STUB 或未核清口径写成 SUPPORTED。",
        ],
    })


def success_condition() -> CompetitionCondition:
    return CompetitionCondition.model_validate({
        "metric_type": "GSV",
        "timezone": SHANGHAI,
        "current_period": _period("2026-08-01", "2026-08-31"),
        "comparison_mode": "YOY_SAME_PERIOD",
        "comparison_period": _period("2025-08-01", "2025-08-31"),
        "sales_scope": _scope_all(),
        "history_scope": _scope_all(),
        "sample_mode": "EXCLUDE_CURRENT_SALES_ONLY",
        "sample_channel_ids": ["sample-channel-unverified-a", "sample-channel-unverified-b"],
        "data_cutoff_policy": "T_PLUS_1_YESTERDAY",
        "leap_day_alignment": "CLAMP_TO_MONTH_END",
        "data_snapshot_ref": "synthetic-c0-demo-v1",
        "as_of": AS_OF,
        "rule_version": "competition-condition-rule/v1",
    })


def success_result() -> CompetitionResultRef:
    resolved = make_resolved(
        sample_mode="EXCLUDE_CURRENT_SALES_ONLY",
        sample_ids=["sample-channel-unverified-a", "sample-channel-unverified-b"],
        history_recomputed=False,
        data_version="synthetic-c0-demo-data/v1",
        rule_version="competition-condition-rule/v1",
        snapshot="synthetic-c0-demo-v1",
        extra_limit="facts_schema_ref 指向已有 ChannelFollowupResult，不另造渠道二单事实。",
    )
    return CompetitionResultRef.model_validate({
        "result_id": "result_c0_gsv_20260831",
        "run_id": "run_c0_gsv_20260831",
        "analysis_id": "analysis_c0aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "query_id": "channel_first_observed_followup",
        "query_version": "channel-followup-query/v1",
        "metric_id": "channel_first_observed_n_day_repeat",
        "metric_version": "channel-followup-metric/v1",
        "facts_schema_ref": "backend.contracts.analytics_query.ChannelFollowupResult",
        "existing_result_schema": "analytics-channel-followup/v1",
        "completeness": "COMPLETE",
        "row_count": 2,
        "page": {
            "offset": 0, "limit": 50, "total": 2, "checksum": DIGEST_A, "complete": True,
        },
        "resolved_condition": resolved.model_dump(mode="json"),
        "evidence_digest": DIGEST_A,
        "primary_result_ref": "result_c0_gsv_20260831",
        "data_mode": "SNAPSHOT",
        "contains_real_data": False,
        "limitations": resolved.limitations,
    })


def empty_result() -> CompetitionResultRef:
    resolved = make_resolved(
        sample_mode="INCLUDE",
        sample_ids=None,
        history_recomputed=False,
        data_version="synthetic-c0-demo-data/v1",
        rule_version="competition-condition-rule/v1",
        snapshot="synthetic-c0-demo-v1",
        extra_limit="2026-09-01 T+1 时 9 月尚无可用数据：EMPTY，不比较未来完整月。",
    )
    empty_period = InclusiveDateRange(start_date=date(2026, 9, 1), end_date=date(2026, 9, 1))
    dump = resolved.model_dump(mode="json")
    dump["current_period"] = empty_period.model_dump(mode="json")
    dump["cutoff"] = _cutoff_for(empty_period.start_date).isoformat()
    payload = condition_hash_payload({
        "as_of": dump["as_of"],
        "comparison_mode": dump["comparison_mode"],
        "comparison_period": dump["comparison_period"],
        "current_period": dump["current_period"],
        "cutoff": dump["cutoff"],
        "data_cutoff_policy": dump["data_cutoff_policy"],
        "data_snapshot_ref": dump["data_snapshot_ref"],
        "data_version": dump["data_version"],
        "history_scope": dump["history_scope"],
        "leap_day_alignment": dump["leap_day_alignment"],
        "metric_type": dump["metric_type"],
        "metrics_contract_id": dump["metrics_contract_id"],
        "permission_scope": dump["permission_scope"],
        "published_at": dump["published_at"],
        "rule_version": dump["rule_version"],
        "sales_scope": dump["sales_scope"],
        "sample_channel_ids": dump["sample_channel_ids"],
        "sample_mode": dump["sample_mode"],
        "source_tense": dump["source_tense"],
        "timezone": dump["timezone"],
    })
    dump["filter_hash"] = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
    empty_resolved = CompetitionResolvedCondition.model_validate(dump)
    return CompetitionResultRef.model_validate({
        "result_id": "result_c0_empty_20260901",
        "run_id": "run_c0_empty_20260901",
        "query_id": "competition_gsv_mtd",
        "query_version": "competition-metrics/v1",
        "facts_schema_ref": "competition-result/v1#empty",
        "existing_result_schema": "none",
        "completeness": "EMPTY",
        "empty_reason": "NO_CURRENT_MONTH_DATA",
        "row_count": 0,
        "resolved_condition": empty_resolved.model_dump(mode="json"),
        "data_mode": "SNAPSHOT",
        "contains_real_data": False,
        "limitations": empty_resolved.limitations,
    })


def permission_error(*, param: str, message: str, request_id: str) -> CompetitionErrorResponse:
    return CompetitionErrorResponse(error=CompetitionErrorDetail(
        code="FORBIDDEN", message=message, param=param, retryable=False,
        request_id=request_id, doc_ref="docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T06",
        recovery_url=None, http_status=403,
        maps_to="backend.contracts.analytics.AnalyticsErrorDetail",
    ))


def param_error_payloads() -> dict[str, dict[str, Any]]:
    good = success_condition().model_dump(mode="json")
    return {
        "condition": {**good, "metric_type": "GMV"},
        "result": {"schema_version": B0_RUN_SCHEMA, "completeness": "COMPLETE"},
        "board": {**success_board().model_dump(mode="json"), "visibility": "PUBLIC"},
        "audience": {**success_candidates().model_dump(mode="json"), "unique_count": 99},
        "error": {"error": {"code": "X", "message": "x", "retryable": False, "request_id": "r",
                            "http_status": 400, "maps_to": "nope"}},
        "capabilities": {"capability_id": "x", "title": "x", "concept": "Nope",
                         "support_status": "SUPPORTED", "existing_types": [],
                         "required_capabilities": [], "notes": "x"},
    }


def success_board() -> CompetitionBoardSpec:
    return CompetitionBoardSpec.model_validate({
        "board_id": "dash_c0_board_a",
        "block_ids": ["card_c0_block_1", "card_c0_block_2"],
        "version": 4,
        "base_version": 3,
        "title": "8月GSV诊断板",
        "owner_id": ACTOR_A,
        "visibility": "PRIVATE",
        "layout_mode": "ONE_BOARD_MULTI_BLOCK",
        "existing_dashboard_schema": "analytics-cockpit/v1",
        "data_namespace": "analytics-cockpit/v1",
        "snapshot_compat": "READ_OLD_SNAPSHOT",
        "data_mode": "SNAPSHOT",
        "preview": False,
        "persisted": True,
        "batch_id": "batch_c0_1",
        "operation_id": "op_c0_board_a",
        "affected_block_ids": ["card_c0_block_1", "card_c0_block_2"],
        "limitations": [
            "沿用 analytics-cockpit/v1 SNAPSHOT 读兼容；competition-board/v1 新板走隔离命名空间。",
        ],
    })


def success_patch() -> CompetitionPatchRequest:
    return CompetitionPatchRequest.model_validate({
        "board_id": "dash_c0_board_a",
        "block_id": "card_c0_block_1",
        "base_version": 4,
        "attempt_id": "attempt_c0_style_1",
        "idempotency_key": "patch-style-1",
        "intent": "STYLE_ONLY",
        "display_op": {
            "op": "display",
            "card_id": "card_c0_block_1",
            "display_overrides": {"title": "渠道贡献（样式）"},
        },
    })


def success_batch() -> CompetitionBoardBatchRequest:
    endorsed = EndorsedResultRef(
        result_id="result_c0_gsv_20260831",
        run_id="run_c0_gsv_20260831",
        analysis_id="analysis_c0aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        evidence_digest=DIGEST_A,
    )
    return CompetitionBoardBatchRequest.model_validate({
        "batch_id": "batch_c0_1",
        "layout_mode": "ONE_BOARD_MULTI_BLOCK",
        "operations": [{
            "operation_id": "op_c0_board_a",
            "idempotency_key": "board-create-a",
            "request_fingerprint": DIGEST_A,
            "layout_mode": "ONE_BOARD_MULTI_BLOCK",
            "title": "8月GSV诊断板",
            "endorsed_result_refs": [endorsed.model_dump(mode="json")],
        }],
    })


def partial_batch_receipt() -> CompetitionBoardBatchReceipt:
    return CompetitionBoardBatchReceipt.model_validate({
        "batch_id": "batch_c0_multi",
        "status": "PARTIAL",
        "items": [
            {"operation_id": "op_c0_board_a", "board_id": "dash_c0_board_a", "version": 1,
             "status": "SUCCEEDED", "error_code": None, "retryable": False},
            {"operation_id": "op_c0_board_b", "board_id": None, "version": None,
             "status": "FAILED", "error_code": "ANALYSIS_UNAVAILABLE", "retryable": True},
        ],
    })


def conflict_409() -> CompetitionErrorResponse:
    return CompetitionErrorResponse(error=CompetitionErrorDetail(
        code="VERSION_CONFLICT",
        message="base_version 与已保存版本不一致，未覆盖。",
        param="base_version",
        retryable=False,
        request_id="req_c0_409_board",
        doc_ref="docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T11",
        recovery_url=None,
        http_status=409,
        maps_to="backend.contracts.analytics.AnalyticsErrorDetail",
    ))


def success_cohort() -> CompetitionCohortSpec:
    return CompetitionCohortSpec.model_validate({
        "cohort_id": "cohort_c0_ly_f_unknown",
        "enrollment_window": _period("2025-01-01", "2025-12-31"),
        "observation_window": _period("2026-08-01", "2026-08-31"),
        "enrollment_rule_version": "competition-cohort-rule/v1",
        "as_of": AS_OF,
        "published_at": PUBLISHED,
        "source_tense": "PUBLISHED_SNAPSHOT",
        "member_history_status": "UNKNOWN",
        "existing_family": "none",
        "rules": [{
            "rule_id": "rule_origin_channel",
            "kind": "NON_REPURCHASE",
            "non_repurchase": "ORIGIN_CHANNEL_ABSENT",
            "member_mark": "UNKNOWN",
            "f_threshold": None,
            "f_grain_status": "UNKNOWN",
            "channel_ids": ["channel-unverified-origin"],
            "product_ids": [],
        }],
        "permission_scope": SCOPE_A,
        "limitations": [
            "去年 F≥4 固定入组未核清旧 CRM F 粒度，C0 禁止带 f_threshold。",
            "handoff-audience 不得冒充本 cohort。",
        ],
    })


def success_candidates() -> CompetitionCandidateSet:
    return CompetitionCandidateSet.model_validate({
        "candidate_set_id": "cand_c0_10",
        "cohort_id": "cohort_c0_ly_f_unknown",
        "source_result_ref": "result_c0_gsv_20260831",
        "combine": "AND",
        "unique_count": 2,
        "customer_keys": ["cust_c0_1", "cust_c0_2"],
        "explanations": [
            {"customer_key": "cust_c0_1", "reasons": ["ORIGIN_CHANNEL_ABSENT"]},
            {"customer_key": "cust_c0_2", "reasons": ["ORIGIN_CHANNEL_ABSENT"]},
        ],
        "auto_send": False,
        "permission_scope": SCOPE_A,
        "limitations": ["合成 customer_key，不导出真实名单。"],
    })


def empty_candidates() -> CompetitionCandidateSet:
    return CompetitionCandidateSet.model_validate({
        "candidate_set_id": "cand_c0_zero",
        "cohort_id": "cohort_c0_ly_f_unknown",
        "source_result_ref": "result_c0_gsv_20260831",
        "combine": "AND",
        "unique_count": 0,
        "customer_keys": [],
        "explanations": [],
        "auto_send": False,
        "permission_scope": SCOPE_A,
        "limitations": ["零候选不得伪造建议名单。"],
    })


def success_draft() -> CompetitionActionDraft:
    return CompetitionActionDraft.model_validate({
        "draft_id": "draft_c0_1",
        "version": 1,
        "candidate_set_id": "cand_c0_10",
        "source_result_ref": "result_c0_gsv_20260831",
        "status": "DRAFT",
        "owner_id": ACTOR_A,
        "reviewer_id": "reviewer.ops",
        "review_by": "2026-09-15",
        "budget_cap_minor": 100000,
        "currency": "CNY",
        "channel": "channel-unverified-origin",
        "product_id": None,
        "control_design": "holdout 待确认",
        "stop_condition": "观察窗结束或人工停止",
        "unknowns": ["MEMBER_HISTORY", "SAMPLE_CHANNEL_SET", "incremental_roi"],
        "auto_send": False,
        "expired_reason": None,
        "copy_only_change": False,
        "existing_mission_export": "not-mission-draft-export",
        "limitations": ["GSV 下降不等于投放回报低；缺成本时只给试验优先级。"],
    })


def expired_draft() -> CompetitionActionDraft:
    return success_draft().model_copy(update={
        "version": 2,
        "status": DraftStatus.EXPIRED,
        "expired_reason": "RULE_CHANGED",
        "copy_only_change": False,
    })


def success_capability() -> CompetitionCapability:
    return SUPPORT_MATRIX[0]


def empty_capability_list() -> list[CompetitionCapability]:
    return []


def pretty(value: Any) -> str:
    if hasattr(value, "model_dump"):
        payload = value.model_dump(mode="json")
    else:
        payload = value
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"


def fixture_docs() -> dict[str, str]:
    return {
        "fixtures/condition/success.json": pretty(success_condition()),
        "fixtures/condition/empty.json": pretty({
            "note": "Empty is a ResultRef, not a missing Condition. This file is the Sept-1 T+1 empty MTD result.",
            "result": empty_result().model_dump(mode="json"),
        }),
        "fixtures/condition/param_error.json": pretty({
            "expected": {"http_status": 422, "code": "INVALID_REQUEST", "param": "metric_type"},
            "payload": param_error_payloads()["condition"],
        }),
        "fixtures/condition/permission_denied.json": pretty(permission_error(
            param="permission_scope", message="当前身份无权读取该品牌条件。",
            request_id="req_c0_403_condition",
        )),
        "fixtures/result/success.json": pretty(success_result()),
        "fixtures/result/empty.json": pretty(empty_result()),
        "fixtures/result/param_error.json": pretty({
            "expected": {"http_status": 422, "code": "INVALID_REQUEST", "param": "schema_version"},
            "payload": param_error_payloads()["result"],
        }),
        "fixtures/result/permission_denied.json": pretty(permission_error(
            param="result_id", message="当前身份无权读取该结果引用。",
            request_id="req_c0_403_result",
        )),
        "fixtures/board/success.json": pretty({
            "board": success_board().model_dump(mode="json"),
            "patch": success_patch().model_dump(mode="json"),
            "batch": success_batch().model_dump(mode="json"),
        }),
        "fixtures/board/empty.json": pretty(CompetitionBoardSpec.model_validate({
            **success_board().model_dump(mode="json"),
            "block_ids": [],
            "affected_block_ids": [],
            "version": 1,
            "base_version": 1,
            "title": "空板",
            "batch_id": None,
            "operation_id": None,
            "limitations": ["无块的已存板仍是合法 BoardSpec，不等于失败。"],
        })),
        "fixtures/board/param_error.json": pretty({
            "expected": {"http_status": 422, "code": "INVALID_REQUEST", "param": "visibility"},
            "payload": param_error_payloads()["board"],
        }),
        "fixtures/board/permission_denied.json": pretty(permission_error(
            param="board_id", message="当前身份无权读取或编辑该驾驶舱。",
            request_id="req_c0_403_board",
        )),
        "fixtures/board/conflict_409.json": pretty(conflict_409()),
        "fixtures/board/partial_success.json": pretty(partial_batch_receipt()),
        "fixtures/audience/success.json": pretty({
            "cohort": success_cohort().model_dump(mode="json"),
            "candidates": success_candidates().model_dump(mode="json"),
            "draft": success_draft().model_dump(mode="json"),
        }),
        "fixtures/audience/empty.json": pretty(empty_candidates()),
        "fixtures/audience/param_error.json": pretty({
            "expected": {"http_status": 422, "code": "INVALID_REQUEST", "param": "unique_count"},
            "payload": param_error_payloads()["audience"],
        }),
        "fixtures/audience/permission_denied.json": pretty(permission_error(
            param="customer_key", message="当前身份无权预览该候选明细。",
            request_id="req_c0_403_audience",
        )),
        "fixtures/audience/conflict_409.json": pretty(CompetitionErrorResponse(error=CompetitionErrorDetail(
            code="VERSION_CONFLICT", message="草稿 base_version 冲突，未覆盖。",
            param="version", retryable=False, request_id="req_c0_409_draft",
            doc_ref="docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T12",
            http_status=409, maps_to="backend.contracts.analytics.AnalyticsErrorDetail",
        ))),
        "fixtures/audience/partial_success.json": pretty({
            "status": "PARTIAL",
            "combine": "OR",
            "note": "一条规则成功、一条规则因 F 粒度 UNKNOWN 被拒绝，不得把失败规则人数加进成功集合。",
            "accepted": success_candidates().model_dump(mode="json"),
            "rejected": {
                "rule_id": "rule_f_ge_4",
                "error": CompetitionErrorDetail(
                    code="UNSUPPORTED_FILTER", message="F 粒度 UNKNOWN，拒绝应用 f_threshold。",
                    param="f_threshold", retryable=False, request_id="req_c0_partial_audience",
                    doc_ref="docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T05",
                    http_status=422, maps_to="backend.contracts.analytics.AnalyticsErrorDetail",
                ).model_dump(mode="json"),
            },
        }),
        "fixtures/error/success.json": pretty(CompetitionErrorResponse(error=CompetitionErrorDetail(
            code="STATE_UNAVAILABLE", message="状态暂不可用。", param=None, retryable=True,
            retry_after=1, request_id="req_c0_503", doc_ref="docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T08",
            http_status=503, maps_to="backend.contracts.analytics.AnalyticsErrorDetail",
        ))),
        "fixtures/error/empty.json": pretty({
            "note": "Empty is not an error. Use ResultRef completeness=EMPTY.",
            "not_an_error": empty_result().model_dump(mode="json")["completeness"],
        }),
        "fixtures/error/param_error.json": pretty({
            "expected": {"http_status": 422, "code": "INVALID_REQUEST", "param": "maps_to"},
            "payload": param_error_payloads()["error"],
        }),
        "fixtures/error/permission_denied.json": pretty(permission_error(
            param="Authorization", message="需要本次有效身份。", request_id="req_c0_401_error",
        ).model_copy(update={"error": permission_error(
            param="Authorization", message="需要本次有效身份。", request_id="req_c0_401_error",
        ).error.model_copy(update={"code": "UNAUTHENTICATED", "http_status": 401})})),
        "fixtures/capabilities/success.json": pretty({
            "defaults": [item.model_dump(mode="json") for item in C0_DEFAULTS],
            "concept_map": [item.model_dump(mode="json") for item in CONCEPT_MAP],
            "matrix": [item.model_dump(mode="json") for item in SUPPORT_MATRIX],
            "frontend_ports": [item.model_dump(mode="json") for item in FRONTEND_PORTS],
        }),
        "fixtures/capabilities/empty.json": pretty(empty_capability_list()),
        "fixtures/capabilities/param_error.json": pretty({
            "expected": {"http_status": 422, "code": "INVALID_REQUEST", "param": "concept"},
            "payload": param_error_payloads()["capabilities"],
        }),
        "fixtures/capabilities/permission_denied.json": pretty(permission_error(
            param="capability_id", message="该 actor 的能力目录不含此项；后端仍会拒绝调用。",
            request_id="req_c0_403_capability",
        )),
    }


def field_docs() -> dict[str, str]:
    mapping = {
        "condition": CompetitionCondition,
        "resolved_condition": CompetitionResolvedCondition,
        "result": CompetitionResultRef,
        "board": CompetitionBoardSpec,
        "patch": CompetitionPatchRequest,
        "batch": CompetitionBoardBatchRequest,
        "batch_receipt": CompetitionBoardBatchReceipt,
        "cohort": CompetitionCohortSpec,
        "candidates": CompetitionCandidateSet,
        "action": CompetitionActionDraft,
        "error": CompetitionErrorDetail,
        "capability": CompetitionCapability,
        "frontend_port": CompetitionFrontendPort,
    }
    docs = {}
    for name, model in mapping.items():
        catalog = _field_catalog(model)
        if name == "condition":
            catalog["permission_identity"] = {
                "request": "no owner_id; extra=forbid rejects client-supplied owner",
                "resolved": "actor_id + permission_scope from AnalyticsPrincipal",
                "http": "Authorization Bearer as CockpitBearer / B0 identity; old CRM session is not C0 identity",
            }
            catalog["actual_execution"] = [
                "current_period", "comparison_period", "timezone", "cutoff", "as_of",
                "published_at", "event_time", "source_tense", "sales_scope", "history_scope",
                "sample_mode", "sample_channel_ids", "rule_version", "data_version",
            ]
            catalog["units"] = {
                "dates": "ISO YYYY-MM-DD in Asia/Shanghai",
                "timestamps": "canonical UTC YYYY-MM-DDTHH:MM:SS.ffffff+00:00",
                "amounts": "minor integer fen when facts reuse analytics_query",
                "ratios": "0-1 on reused *_ratio fields; do not guess suffix magnitude",
            }
        docs[f"fields/{name}.json"] = pretty(catalog)
    docs["defaults.json"] = pretty([item.model_dump(mode="json") for item in C0_DEFAULTS])
    docs["mapping.json"] = pretty([item.model_dump(mode="json") for item in CONCEPT_MAP])
    docs["support_matrix.json"] = pretty([item.model_dump(mode="json") for item in SUPPORT_MATRIX])
    docs["frontend_ports.json"] = pretty([item.model_dump(mode="json") for item in FRONTEND_PORTS])
    return docs


HASHED_SOURCE_PATHS = (
    "backend/contracts/competition_c0.py",
    "backend/contracts/schemas.py",
    "backend/contracts/analytics-competition-c0.openapi.json",
    "backend/contracts/tests/test_competition_c0.py",
    "dsh-plugins/analytics-workbench/src/competition-c0-contract.generated.d.ts",
    "scripts/dsh-b0/competition-c0-contract.mjs",
)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def stable_contract_hash(root: Path, manifest_without_hash: dict[str, Any]) -> str:
    entries: list[tuple[str, str]] = []
    for rel in HASHED_SOURCE_PATHS:
        path = root / rel
        if path.is_file():
            entries.append((rel.replace("\\", "/"), _sha256_bytes(path.read_bytes())))
    contracts = root / DOCS_CONTRACTS
    if contracts.is_dir():
        for path in sorted(contracts.rglob("*")):
            if not path.is_file() or path.name == "C0-MANIFEST.json":
                continue
            rel = path.relative_to(root).as_posix()
            entries.append((rel, _sha256_bytes(path.read_bytes())))
    manifest_payload = dict(manifest_without_hash)
    manifest_payload["contract_hash"] = ""
    entries.append((
        f"{DOCS_CONTRACTS.as_posix()}/C0-MANIFEST.json",
        _sha256_bytes(canonical_json(manifest_payload).encode("utf-8")),
    ))
    entries.sort()
    blob = "".join(f"{name}:{digest}\n" for name, digest in entries).encode("utf-8")
    return _sha256_bytes(blob)


def emit_bundle_json() -> str:
    validate_fixture_library()
    return json.dumps(c0_bundle(), ensure_ascii=False, sort_keys=True, allow_nan=False)


def c0_bundle(root: Path | None = None) -> dict[str, Any]:
    del root
    schema = c0_openapi()
    docs = {**field_docs(), **fixture_docs()}
    file_list = sorted(
        [f"{DOCS_CONTRACTS.as_posix()}/{name}" for name in docs]
        + [f"{DOCS_CONTRACTS.as_posix()}/C0-MANIFEST.json"]
        + list(HASHED_SOURCE_PATHS)
        + ["docs/hackathon/parallel-competition-2026-09-09/contracts/competition-c0-contract.typecheck.ts"]
    )
    manifest = {
        "schema_version": C0_SCHEMA,
        "metrics_contract_id": C0_METRICS_CONTRACT_ID,
        "version": C0_SCHEMA,
        "base_sha_expected": "71a65f06f87cb3a5cbd888372487b6b36faaf2a6",
        "not_an_http_api": True,
        "existing_schemas_untouched": [
            B0_RUN_SCHEMA, QUERY_SCHEMA, QUERY_RUN_SCHEMA, SAVED_ANALYSIS_SCHEMA,
            COCKPIT_SCHEMA, FIRST_PURCHASE_SCHEMA, HANDOFF_SCHEMA,
        ],
        "defaults_pending_confirmation": [
            item.key for item in C0_DEFAULTS if item.pending_confirmation
        ],
        "explicit_modes": {
            "sample_mode": [item.value for item in SampleMode],
            "board_layout_mode": [item.value for item in BoardLayoutMode],
            "comparison_mode": [item.value for item in ComparisonMode],
        },
        "support_matrix": [item.model_dump(mode="json") for item in SUPPORT_MATRIX],
        "files": file_list,
        "contract_hash": "",
    }
    return {"openapi": schema, "docs": docs, "manifest": manifest}


def validate_fixture_library() -> None:
    success_condition()
    success_result()
    empty_result()
    success_board()
    success_patch()
    success_batch()
    partial_batch_receipt()
    conflict_409()
    success_cohort()
    success_candidates()
    empty_candidates()
    success_draft()
    expired_draft()
    from pydantic import ValidationError
    rejects = {
        "condition": (CompetitionCondition, param_error_payloads()["condition"]),
        "board": (CompetitionBoardSpec, param_error_payloads()["board"]),
        "audience": (CompetitionCandidateSet, param_error_payloads()["audience"]),
        "error": (CompetitionErrorResponse, param_error_payloads()["error"]),
        "capabilities": (CompetitionCapability, param_error_payloads()["capabilities"]),
        "result": (CompetitionResultRef, param_error_payloads()["result"]),
    }
    for name, (model, payload) in rejects.items():
        try:
            model.model_validate(payload)
        except (ValidationError, ValueError):
            continue
        raise AssertionError(f"expected {name} payload to be rejected")
