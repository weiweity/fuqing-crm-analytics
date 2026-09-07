"""Independent synthetic channel-follow-up query contract.

Schema: analytics-channel-followup/v1. Not analytics-run-b0/v1.
This module does not expose HTTP routes, run SQL, or schedule workers.

Canonical timestamps (hash/digest): convert the instant to UTC and emit
YYYY-MM-DDTHH:MM:SS.ffffff+00:00 with exactly six fractional digits. Equivalent
offsets of the same instant hash identically. Naive values, numeric epochs, and
more than six fractional digits are rejected rather than truncated.
filter_hash is a self-consistent digest of the normalized payload, not a
permission credential. G4 must still bind the trusted request/snapshot/scope.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date, datetime, time, timezone
from enum import StrEnum
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator
from pydantic.json_schema import models_json_schema

QUERY_SCHEMA = "analytics-channel-followup/v1"
QUERY_ID = "channel_first_observed_followup"
QUERY_VERSION = "channel-followup-query/v1"
METRIC_ID = "channel_first_observed_n_day_repeat"
METRIC_VERSION = "channel-followup-metric/v1"
DATA_VERSION = "synthetic-channel-followup-data/v1"
HASH_VERSION = "channel-followup-filter-hash/v1"
SNAPSHOT_ID = "synthetic-channel-followup-v1"
DISPLAY_NAME = "首次观察到的渠道 / N日二单率"
REGISTERED_CHANNELS = ("A", "B")
B0_RUN_SCHEMA = "analytics-run-b0/v1"
JS_MAX_SAFE_INTEGER = 9007199254740991
SHANGHAI = "Asia/Shanghai"
TIMESTAMP_CANONICAL_RULE = (
    "Timezone-aware instants are converted to UTC and formatted as "
    "YYYY-MM-DDTHH:MM:SS.ffffff+00:00 (always six fractional digits). "
    "Equivalent offsets of the same instant hash identically. "
    "Naive datetimes, numeric epochs, and >6 fractional digits are rejected."
)
EMPTY_PRODUCT_IDS_SCHEMA = {
    "title": "Product Ids",
    "type": "array",
    "default": [],
    "const": [],
    "maxItems": 0,
    "minItems": 0,
    "prefixItems": [],
    "items": False,
    "description": "This subset rejects any product filter; only the empty array is valid.",
}

QueryOpaqueId = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$", strict=True),
]
Sha256Hex = Annotated[str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$", strict=True)]
ChannelId = Literal["A", "B"]
_RFC3339 = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})T(?P<hms>\d{2}:\d{2}:\d{2})(?P<frac>\.\d{1,6})?(?P<off>Z|[+-]\d{2}:\d{2})$"
)
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def require_nonbool_int(value: object) -> object:
    if type(value) is bool:
        raise ValueError("counts and amounts must be non-bool integers")
    return value


def require_json_false(value: object) -> bool:
    if type(value) is not bool or value is not False:
        raise ValueError("value must be boolean false")
    return False


def require_observation_days(value: object) -> int:
    if type(value) is bool or type(value) is not int or value not in (30, 60, 90):
        raise ValueError("observation_days must be integer 30, 60 or 90")
    return value


def parse_query_date(value: object) -> date:
    if isinstance(value, datetime):
        raise ValueError("calendar dates must be ISO YYYY-MM-DD, not datetime")
    if isinstance(value, date):
        return value
    if isinstance(value, str) and _ISO_DATE.fullmatch(value):
        return date.fromisoformat(value)
    raise ValueError("calendar dates must be ISO YYYY-MM-DD strings or date objects, not numbers")


def parse_query_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("naive datetime is not allowed")
        return value
    if isinstance(value, str):
        match = _RFC3339.fullmatch(value)
        if match is None:
            raise ValueError("datetime must be RFC3339 with timezone; numeric epochs are rejected")
        frac = match.group("frac") or ".000000"
        frac = "." + frac[1:].ljust(6, "0")
        offset = "+00:00" if match.group("off") == "Z" else match.group("off")
        return datetime.fromisoformat(f"{match.group('date')}T{match.group('hms')}{frac}{offset}")
    raise ValueError("datetime must be RFC3339 with timezone or an aware datetime")


def canonical_rfc3339(value: datetime) -> str:
    """Lossless UTC instant form used by snapshot_digest and filter_hash."""
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("canonical timestamps require a timezone-aware datetime")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)


def compute_filter_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()


def filter_hash_payload(
    *,
    as_of: datetime,
    channel_ids: tuple[str, ...] | list[str],
    data_digest: str,
    data_snapshot_ref: str,
    data_version: str,
    observation_days: int,
    permission_scope: str,
    resolved_cohort_end: datetime,
    resolved_cohort_start: datetime,
    timezone_name: str,
) -> dict[str, Any]:
    return {
        "as_of": canonical_rfc3339(as_of),
        "channel_ids": list(channel_ids),
        "cohort_ref": None,
        "comparison": None,
        "data_digest": data_digest,
        "data_snapshot_ref": data_snapshot_ref,
        "data_version": data_version,
        "exclude_low_price": False,
        "hash_version": HASH_VERSION,
        "metric_id": METRIC_ID,
        "metric_version": METRIC_VERSION,
        "observation_days": observation_days,
        "permission_scope": permission_scope,
        "product_ids": [],
        "query_id": QUERY_ID,
        "query_version": QUERY_VERSION,
        "resolved_cohort_end": canonical_rfc3339(resolved_cohort_end),
        "resolved_cohort_start": canonical_rfc3339(resolved_cohort_start),
        "timezone": timezone_name,
    }


def shanghai_date_midnight(value: datetime) -> date:
    zone = ZoneInfo(SHANGHAI)
    local = value.astimezone(zone)
    boundary = datetime.combine(local.date(), time.min, tzinfo=zone)
    if local != boundary:
        raise ValueError("resolved cohort bounds must be Asia/Shanghai calendar-date midnights")
    return local.date()


def revalidate_model(cls, value):
    if isinstance(value, cls):
        return cls.model_validate(value.model_dump(mode="python"))
    return cls.model_validate(value)


def _checked_sum(values: list[int]) -> int:
    total = 0
    for value in values:
        total += value
        if total > JS_MAX_SAFE_INTEGER:
            raise ValueError("aggregate exceeds JSON/JS safe integer transport limit")
    return total


def _force_empty_product_ids(node: object) -> None:
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict) and "product_ids" in props:
            props["product_ids"] = dict(EMPTY_PRODUCT_IDS_SCHEMA)
        for child in node.values():
            _force_empty_product_ids(child)
    elif isinstance(node, list):
        for child in node:
            _force_empty_product_ids(child)


StrictCount = Annotated[
    int,
    BeforeValidator(require_nonbool_int),
    Field(strict=True, ge=0, le=JS_MAX_SAFE_INTEGER),
]
MinorAmount = Annotated[
    int,
    BeforeValidator(require_nonbool_int),
    Field(strict=True, ge=0, le=JS_MAX_SAFE_INTEGER),
]
PositiveMinor = Annotated[
    int,
    BeforeValidator(require_nonbool_int),
    Field(strict=True, ge=1, le=JS_MAX_SAFE_INTEGER),
]
PositiveQuantity = Annotated[
    int,
    BeforeValidator(require_nonbool_int),
    Field(strict=True, ge=1, le=JS_MAX_SAFE_INTEGER),
]
ObservationDays = Annotated[Literal[30, 60, 90], BeforeValidator(require_observation_days)]
QueryDate = Annotated[date, BeforeValidator(parse_query_date)]
QueryDateTime = Annotated[datetime, BeforeValidator(parse_query_datetime)]
JsonFalse = Annotated[Literal[False], BeforeValidator(require_json_false)]
EmptyProductIds = Annotated[
    list[str],
    Field(default_factory=list, max_length=0, json_schema_extra=dict(EMPTY_PRODUCT_IDS_SCHEMA)),
]


class AnalyticsQueryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class ChannelFollowupFixedWindow(AnalyticsQueryModel):
    kind: Literal["FIXED"]
    start_date: QueryDate
    end_date: QueryDate

    @model_validator(mode="after")
    def inclusive_start_exclusive_end(self):
        if self.start_date >= self.end_date:
            raise ValueError("FIXED cohort_window is inclusive start and exclusive end")
        return self


class ChannelFollowupQueryRequest(AnalyticsQueryModel):
    schema_version: Literal["analytics-channel-followup/v1"] = QUERY_SCHEMA
    query_id: Literal["channel_first_observed_followup"] = QUERY_ID
    query_version: Literal["channel-followup-query/v1"] = QUERY_VERSION
    metric_id: Literal["channel_first_observed_n_day_repeat"] = METRIC_ID
    metric_version: Literal["channel-followup-metric/v1"] = METRIC_VERSION
    cohort_window: ChannelFollowupFixedWindow
    observation_days: ObservationDays
    data_snapshot_ref: Literal["synthetic-channel-followup-v1"] = SNAPSHOT_ID
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"
    channel_ids: list[ChannelId] = Field(default_factory=list)
    cohort_ref: None = None
    product_ids: EmptyProductIds = Field(default_factory=list)
    exclude_low_price: JsonFalse = False
    comparison: None = None

    @field_validator("schema_version", mode="before")
    @classmethod
    def reject_foreign_schema(cls, value: object) -> object:
        if value == B0_RUN_SCHEMA:
            raise ValueError("analytics-run-b0/v1 cannot be used as the channel-follow-up query schema")
        return value

    @field_validator("cohort_window", mode="before")
    @classmethod
    def reject_rolling(cls, value: object) -> object:
        if isinstance(value, dict) and value.get("kind") == "ROLLING":
            raise ValueError("ROLLING cohort_window is not supported; this subset only accepts FIXED")
        return value

    @field_validator("channel_ids")
    @classmethod
    def unique_registered_channels(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("channel_ids must not contain duplicates")
        return list(value)

    @field_validator("product_ids")
    @classmethod
    def reject_product_filter(cls, value: list[str]) -> list[str]:
        if value:
            raise ValueError("product_ids is not supported by analytics-channel-followup/v1")
        return []

    @field_validator("cohort_ref", "comparison", mode="before")
    @classmethod
    def reject_unsupported_optional(cls, value: object) -> object:
        if value is not None:
            raise ValueError("cohort_ref and comparison are not supported by analytics-channel-followup/v1")
        return value


class ChannelFollowupOrderHeader(AnalyticsQueryModel):
    order_id: QueryOpaqueId
    synthetic_user_id: QueryOpaqueId
    paid_at: QueryDateTime
    channel: ChannelId
    gross_paid_minor: MinorAmount
    status: Literal["PAID", "CANCELLED"]


class ChannelFollowupOrderLine(AnalyticsQueryModel):
    line_id: QueryOpaqueId
    order_id: QueryOpaqueId
    synthetic_user_id: QueryOpaqueId
    product_id: QueryOpaqueId
    quantity: PositiveQuantity


class ChannelFollowupRefund(AnalyticsQueryModel):
    refund_id: QueryOpaqueId
    order_id: QueryOpaqueId
    synthetic_user_id: QueryOpaqueId
    refunded_at: QueryDateTime
    refund_minor: PositiveMinor


class ChannelFollowupSnapshot(AnalyticsQueryModel):
    schema_version: Literal["analytics-channel-followup/v1"] = QUERY_SCHEMA
    snapshot_id: Literal["synthetic-channel-followup-v1"] = SNAPSHOT_ID
    data_version: Literal["synthetic-channel-followup-data/v1"] = DATA_VERSION
    as_of: QueryDateTime
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"
    currency: Literal["CNY"] = "CNY"
    amount_unit: Literal["minor"] = "minor"
    amount_precision: Literal["integer_fen"] = "integer_fen"
    scope: Literal["synthetic"] = "synthetic"
    contains_real_data: JsonFalse = False
    orders: list[ChannelFollowupOrderHeader]
    lines: list[ChannelFollowupOrderLine]
    refunds: list[ChannelFollowupRefund]

    @model_validator(mode="after")
    def layered_identity_and_amounts(self):
        headers: dict[tuple[str, str], ChannelFollowupOrderHeader] = {}
        for order in self.orders:
            key = (order.synthetic_user_id, order.order_id)
            previous = headers.get(key)
            if previous is not None:
                if previous.model_dump() != order.model_dump():
                    raise ValueError("conflicting order headers for (synthetic_user_id, order_id)")
                raise ValueError("duplicate order identity (synthetic_user_id, order_id)")
            headers[key] = order
        line_ids: set[str] = set()
        covered: set[tuple[str, str]] = set()
        for line in self.lines:
            if line.line_id in line_ids:
                raise ValueError("duplicate line_id")
            line_ids.add(line.line_id)
            key = (line.synthetic_user_id, line.order_id)
            if key not in headers:
                raise ValueError("order line must reference the same (synthetic_user_id, order_id)")
            covered.add(key)
        missing = [key for key in headers if key not in covered]
        if missing:
            raise ValueError("each order header must have at least one product line")
        refund_ids: set[str] = set()
        refund_sum: dict[tuple[str, str], int] = {}
        for refund in self.refunds:
            if refund.refund_id in refund_ids:
                raise ValueError("duplicate refund_id")
            refund_ids.add(refund.refund_id)
            key = (refund.synthetic_user_id, refund.order_id)
            if key not in headers:
                raise ValueError("refund must reference the same (synthetic_user_id, order_id)")
            refund_sum[key] = _checked_sum([refund_sum.get(key, 0), refund.refund_minor])
        for key, total in refund_sum.items():
            if total > headers[key].gross_paid_minor:
                raise ValueError("refunds exceed original gross_paid_minor")
        return self


def snapshot_digest(snapshot: ChannelFollowupSnapshot | dict[str, Any]) -> str:
    snapshot = revalidate_model(ChannelFollowupSnapshot, snapshot)
    payload = {
        "amount_precision": snapshot.amount_precision,
        "amount_unit": snapshot.amount_unit,
        "as_of": canonical_rfc3339(snapshot.as_of),
        "contains_real_data": snapshot.contains_real_data,
        "currency": snapshot.currency,
        "data_version": snapshot.data_version,
        "lines": sorted(
            (line.model_dump(mode="json") for line in snapshot.lines),
            key=lambda row: row["line_id"],
        ),
        "orders": sorted(
            (
                {**order.model_dump(mode="json"), "paid_at": canonical_rfc3339(order.paid_at)}
                for order in snapshot.orders
            ),
            key=lambda row: (row["synthetic_user_id"], row["order_id"]),
        ),
        "refunds": sorted(
            (
                {**refund.model_dump(mode="json"), "refunded_at": canonical_rfc3339(refund.refunded_at)}
                for refund in snapshot.refunds
            ),
            key=lambda row: row["refund_id"],
        ),
        "schema_version": snapshot.schema_version,
        "scope": snapshot.scope,
        "snapshot_id": snapshot.snapshot_id,
        "timezone": snapshot.timezone,
    }
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()


class ChannelFollowupResolvedFilters(AnalyticsQueryModel):
    schema_version: Literal["analytics-channel-followup/v1"] = QUERY_SCHEMA
    query_id: Literal["channel_first_observed_followup"] = QUERY_ID
    query_version: Literal["channel-followup-query/v1"] = QUERY_VERSION
    metric_id: Literal["channel_first_observed_n_day_repeat"] = METRIC_ID
    metric_version: Literal["channel-followup-metric/v1"] = METRIC_VERSION
    data_version: Literal["synthetic-channel-followup-data/v1"] = DATA_VERSION
    hash_version: Literal["channel-followup-filter-hash/v1"] = HASH_VERSION
    cohort_window_kind: Literal["FIXED"] = "FIXED"
    resolved_cohort_start: QueryDateTime
    resolved_cohort_end: QueryDateTime
    observation_days: ObservationDays
    data_snapshot_ref: Literal["synthetic-channel-followup-v1"] = SNAPSHOT_ID
    as_of: QueryDateTime
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"
    channel_ids: tuple[ChannelId, ...]
    cohort_ref: None = None
    product_ids: EmptyProductIds = Field(default_factory=list)
    exclude_low_price: JsonFalse = False
    comparison: None = None
    permission_scope: QueryOpaqueId
    data_digest: Sha256Hex
    filter_hash: Sha256Hex

    @field_validator("channel_ids")
    @classmethod
    def canonical_channels(cls, value: tuple[str, ...] | list[str]) -> tuple[str, ...]:
        ordered = tuple(value)
        if tuple(sorted(ordered)) != ordered:
            raise ValueError("resolved channel_ids must be sorted")
        if len(ordered) != len(set(ordered)):
            raise ValueError("resolved channel_ids must be unique")
        if not ordered:
            raise ValueError("resolved channel_ids cannot be empty")
        return ordered

    @field_validator("product_ids")
    @classmethod
    def empty_products(cls, value: list[str]) -> list[str]:
        if value:
            raise ValueError("resolved product_ids must be empty in this subset")
        return []

    @model_validator(mode="after")
    def canonical_window_and_hash(self):
        start_date = shanghai_date_midnight(self.resolved_cohort_start)
        end_date = shanghai_date_midnight(self.resolved_cohort_end)
        if start_date >= end_date:
            raise ValueError("FIXED resolved window is inclusive start and exclusive end")
        expected = compute_filter_hash(filter_hash_payload(
            as_of=self.as_of,
            channel_ids=self.channel_ids,
            data_digest=self.data_digest,
            data_snapshot_ref=self.data_snapshot_ref,
            data_version=self.data_version,
            observation_days=self.observation_days,
            permission_scope=self.permission_scope,
            resolved_cohort_end=self.resolved_cohort_end,
            resolved_cohort_start=self.resolved_cohort_start,
            timezone_name=self.timezone,
        ))
        if expected != self.filter_hash:
            raise ValueError("filter_hash does not match the canonical normalized payload")
        return self


class ChannelFollowupEmptyReason(StrEnum):
    EMPTY_MATURE_COHORT = "EMPTY_MATURE_COHORT"


class ChannelFollowupCounts(BaseModel):
    """Count/ratio block; inherits BaseModel so contract lint sees *_ratio fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)
    channel_mature_cohort_count: StrictCount
    channel_immature_count: StrictCount
    channel_repeat_count: StrictCount
    channel_cross_channel_count: StrictCount
    channel_repeat_ratio: Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)] | None = None
    channel_cross_channel_ratio: Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)] | None = None
    channel_window_net_paid_minor: Annotated[int, Field(ge=0, le=JS_MAX_SAFE_INTEGER)] | None = None
    channel_empty_reason: Literal["EMPTY_MATURE_COHORT"] | None = None

    @field_validator("channel_window_net_paid_minor", mode="before")
    @classmethod
    def safe_optional_net(cls, value: object) -> object:
        if value is None:
            return None
        if type(value) is bool or type(value) is not int:
            raise ValueError("net paid must be a non-bool integer or null")
        if value < 0 or value > JS_MAX_SAFE_INTEGER:
            raise ValueError("net paid exceeds JSON/JS safe integer transport limit")
        return value

    @field_validator("channel_repeat_ratio", "channel_cross_channel_ratio")
    @classmethod
    def finite_ratio(cls, value: float | None) -> float | None:
        if value is None:
            return value
        if type(value) is not float or not math.isfinite(value):
            raise ValueError("ratio must be a finite float in [0, 1]")
        return value

    @model_validator(mode="after")
    def count_ratio_invariants(self):
        mature = self.channel_mature_cohort_count
        repeat = self.channel_repeat_count
        cross = self.channel_cross_channel_count
        if repeat > mature or cross > repeat:
            raise ValueError("repeat must be <= mature and cross must be <= repeat")
        if mature == 0:
            if repeat != 0 or cross != 0:
                raise ValueError("empty mature cohort cannot have repeat or cross counts")
            if self.channel_repeat_ratio is not None or self.channel_cross_channel_ratio is not None:
                raise ValueError("empty mature cohort ratios must be null")
            if self.channel_window_net_paid_minor is not None:
                raise ValueError("empty mature cohort net paid must be null")
            if self.channel_empty_reason != ChannelFollowupEmptyReason.EMPTY_MATURE_COHORT:
                raise ValueError("empty mature cohort requires EMPTY_MATURE_COHORT")
            return self
        if self.channel_empty_reason is not None:
            raise ValueError("non-empty mature cohort cannot set empty reason")
        if self.channel_repeat_ratio is None or self.channel_cross_channel_ratio is None:
            raise ValueError("non-empty mature cohort ratios are required")
        if self.channel_window_net_paid_minor is None:
            raise ValueError("non-empty mature cohort net paid is required")
        if self.channel_repeat_ratio != repeat / mature:
            raise ValueError("channel_repeat_ratio must equal repeat/mature")
        if self.channel_cross_channel_ratio != cross / mature:
            raise ValueError("channel_cross_channel_ratio must equal cross/mature")
        return self


class ChannelFollowupChannelRow(ChannelFollowupCounts):
    channel_id: ChannelId


class ChannelFollowupFacts(AnalyticsQueryModel):
    display_name: Literal["首次观察到的渠道 / N日二单率"] = DISPLAY_NAME
    currency: Literal["CNY"] = "CNY"
    amount_unit: Literal["minor"] = "minor"
    amount_precision: Literal["integer_fen"] = "integer_fen"
    observation_days: ObservationDays
    channels: list[ChannelFollowupChannelRow]
    totals: ChannelFollowupCounts

    @model_validator(mode="after")
    def totals_match_selected_channels(self):
        ids = [row.channel_id for row in self.channels]
        if len(ids) != len(set(ids)):
            raise ValueError("channel rows must not repeat channel_id")
        mature = _checked_sum([row.channel_mature_cohort_count for row in self.channels])
        immature = _checked_sum([row.channel_immature_count for row in self.channels])
        repeat = _checked_sum([row.channel_repeat_count for row in self.channels])
        cross = _checked_sum([row.channel_cross_channel_count for row in self.channels])
        totals = self.totals
        if (
            totals.channel_mature_cohort_count != mature
            or totals.channel_immature_count != immature
            or totals.channel_repeat_count != repeat
            or totals.channel_cross_channel_count != cross
        ):
            raise ValueError("totals counts must equal the sum of selected channel rows")
        if totals.channel_mature_cohort_count == 0:
            return self
        net = _checked_sum([
            row.channel_window_net_paid_minor
            for row in self.channels
            if row.channel_window_net_paid_minor is not None
        ])
        if totals.channel_window_net_paid_minor != net:
            raise ValueError("totals net paid must equal the sum of non-null channel nets")
        return self


class ChannelFollowupResult(AnalyticsQueryModel):
    schema_version: Literal["analytics-channel-followup/v1"] = QUERY_SCHEMA
    answer_mode: Literal["DETERMINISTIC_TOOL"] = "DETERMINISTIC_TOOL"
    query_id: Literal["channel_first_observed_followup"] = QUERY_ID
    query_version: Literal["channel-followup-query/v1"] = QUERY_VERSION
    metric_id: Literal["channel_first_observed_n_day_repeat"] = METRIC_ID
    metric_version: Literal["channel-followup-metric/v1"] = METRIC_VERSION
    data_version: Literal["synthetic-channel-followup-data/v1"] = DATA_VERSION
    hash_version: Literal["channel-followup-filter-hash/v1"] = HASH_VERSION
    contains_real_data: JsonFalse = False
    data_source: Literal["SYNTHETIC_SNAPSHOT"] = "SYNTHETIC_SNAPSHOT"
    data_snapshot_ref: Literal["synthetic-channel-followup-v1"] = SNAPSHOT_ID
    as_of: QueryDateTime
    resolved_filters: ChannelFollowupResolvedFilters
    filter_hash: Sha256Hex
    facts: ChannelFollowupFacts
    limitations: Annotated[list[str], Field(min_length=1)]

    @model_validator(mode="after")
    def bind_resolved_projection(self):
        resolved = self.resolved_filters
        if self.filter_hash != resolved.filter_hash:
            raise ValueError("result filter_hash must match resolved_filters.filter_hash")
        if canonical_rfc3339(self.as_of) != canonical_rfc3339(resolved.as_of):
            raise ValueError("result as_of must match the snapshot-resolved as_of")
        if self.facts.observation_days != resolved.observation_days:
            raise ValueError("facts.observation_days must match resolved_filters")
        selected = {row.channel_id for row in self.facts.channels}
        if selected != set(resolved.channel_ids):
            raise ValueError("facts channels must match the resolved channel set")
        return self


OPENAPI_MODELS = (
    ChannelFollowupFixedWindow,
    ChannelFollowupQueryRequest,
    ChannelFollowupOrderHeader,
    ChannelFollowupOrderLine,
    ChannelFollowupRefund,
    ChannelFollowupSnapshot,
    ChannelFollowupResolvedFilters,
    ChannelFollowupCounts,
    ChannelFollowupChannelRow,
    ChannelFollowupFacts,
    ChannelFollowupResult,
)


def query_contract_openapi() -> dict:
    """OpenAPI 3.1 document with components only. Not a callable HTTP API."""
    keyed, document = models_json_schema(
        [(model, "validation") for model in OPENAPI_MODELS],
        ref_template="#/components/schemas/{model}",
    )
    definitions = dict(document.get("$defs", {}))
    for (model, _mode), item in keyed.items():
        definitions.setdefault(model.__name__, item)
    schema = {
        "openapi": "3.1.0",
        "info": {
            "title": "analytics-channel-followup/v1 query contract",
            "description": (
                "Offline schema for the synthetic channel first-observed follow-up "
                "candidate. paths is empty: this unit does not implement a callable "
                "HTTP API, run kernel, SQL, or worker. Integer wire fields are capped "
                f"at {JS_MAX_SAFE_INTEGER} (JSON/JS safe integer transport limit, not a "
                "business threshold). Timestamps follow TIMESTAMP_CANONICAL_RULE. "
                "filter_hash is self-consistent, not a permission credential."
            ),
            "version": QUERY_SCHEMA,
        },
        "paths": {},
        "components": {"schemas": definitions},
        "x-not-an-http-api": True,
        "x-query-schema": QUERY_SCHEMA,
        "x-b0-run-schema-untouched": B0_RUN_SCHEMA,
        "x-js-max-safe-integer": JS_MAX_SAFE_INTEGER,
        "x-timestamp-canonical-rule": TIMESTAMP_CANONICAL_RULE,
    }
    _force_empty_product_ids(schema)
    return schema
