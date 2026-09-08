"""Independent synthetic first-purchase product-path contract.

Schema: analytics-first-purchase-path/v1. Not analytics-channel-followup/v1
and not analytics-run-b0/v1. This module does not expose HTTP, SQL, DuckDB,
or a worker.

Canonical timestamps (hash/digest): convert the instant to UTC and emit
YYYY-MM-DDTHH:MM:SS.ffffff+00:00 with exactly six fractional digits. Equivalent
offsets of the same instant hash identically. Naive values, numeric epochs, and
more than six fractional digits are rejected rather than truncated.
filter_hash is a self-consistent digest of the normalized payload, not a
permission credential.
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

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_serializer, field_validator, model_validator

QUERY_SCHEMA = "analytics-first-purchase-path/v1"
QUERY_ID = "first_purchase_product_path"
QUERY_VERSION = "first-purchase-path-query/v1"
METRIC_ID = "first_purchase_product_n_day_finished"
METRIC_VERSION = "first-purchase-path-metric/v1"
DATA_VERSION = "synthetic-first-purchase-data/v1"
HASH_VERSION = "first-purchase-path-filter-hash/v1"
SNAPSHOT_ID = "synthetic-first-purchase-v1"
DISPLAY_NAME = "首购商品路径 / N日正装转化"
REGISTERED_CHANNELS = ("A", "B")
REGISTERED_ROLES = ("sample", "finished")
B0_RUN_SCHEMA = "analytics-run-b0/v1"
CHANNEL_QUERY_SCHEMA = "analytics-channel-followup/v1"
JS_MAX_SAFE_INTEGER = 9007199254740991
SHANGHAI = "Asia/Shanghai"
EMPTY_MATURE_COHORT = "EMPTY_MATURE_COHORT"
MISSING_PRODUCT_ROLE = "MISSING_PRODUCT_ROLE"
TIMESTAMP_CANONICAL_RULE = (
    "Timezone-aware instants are converted to UTC and formatted as "
    "YYYY-MM-DDTHH:MM:SS.ffffff+00:00 (always six fractional digits). "
    "Equivalent offsets of the same instant hash identically. "
    "Naive datetimes, numeric epochs, and >6 fractional digits are rejected."
)

LIMITATIONS = (
    "synthetic 候选口径：首购商品路径 / N日正装转化，不是真实获客、终身复购或会计批准。",
    "每用户按全历史最早有效订单入组一次；本族按该首单去重商品行展开，展开行之和不是独立人数。",
    "正装转化只计观察窗内、排序晚于首单的另一有效订单上的 finished 角色 SKU，不含首单同篮。",
    "商品角色映射缺失时整单拒绝（MISSING_PRODUCT_ROLE），facts 为 null，不得输出转化率。",
    "空成熟分母的比例为 null + EMPTY_MATURE_COHORT，不得写 0。",
    "filter_hash 只证明规范化 payload 自洽，不是权限凭证。",
    "整数 wire 字段上限 9007199254740991 是 JSON/JS 安全整数传输约束，不是经营阈值。",
)

QueryOpaqueId = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$", strict=True),
]
Sha256Hex = Annotated[str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$", strict=True)]
ChannelId = Literal["A", "B"]
ProductRole = Literal["sample", "finished"]
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


def encode_key(value: str) -> bytes:
    if type(value) is not str:
        raise ValueError("identity keys must remain strings")
    return value.encode("utf-8")


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
EmptyProductIds = Annotated[list[str], Field(default_factory=list, max_length=0)]


class FirstPurchaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class FirstPurchaseFixedWindow(FirstPurchaseModel):
    kind: Literal["FIXED"]
    start_date: QueryDate
    end_date: QueryDate

    @model_validator(mode="after")
    def inclusive_start_exclusive_end(self):
        if self.start_date >= self.end_date:
            raise ValueError("FIXED cohort_window is inclusive start and exclusive end")
        return self


class FirstPurchaseQueryRequest(FirstPurchaseModel):
    schema_version: Literal["analytics-first-purchase-path/v1"] = QUERY_SCHEMA
    query_id: Literal["first_purchase_product_path"] = QUERY_ID
    query_version: Literal["first-purchase-path-query/v1"] = QUERY_VERSION
    metric_id: Literal["first_purchase_product_n_day_finished"] = METRIC_ID
    metric_version: Literal["first-purchase-path-metric/v1"] = METRIC_VERSION
    cohort_window: FirstPurchaseFixedWindow
    observation_days: ObservationDays
    data_snapshot_ref: Literal["synthetic-first-purchase-v1"] = SNAPSHOT_ID
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"
    channel_ids: list[ChannelId] = Field(default_factory=list)
    cohort_ref: None = None
    product_ids: EmptyProductIds = Field(default_factory=list)
    exclude_low_price: JsonFalse = False
    comparison: None = None

    @field_validator("schema_version", mode="before")
    @classmethod
    def reject_foreign_schema(cls, value: object) -> object:
        if value in {B0_RUN_SCHEMA, CHANNEL_QUERY_SCHEMA}:
            raise ValueError("foreign analytics schema cannot be used as first-purchase-path query schema")
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
            raise ValueError("product_ids is not supported by analytics-first-purchase-path/v1")
        return []

    @field_validator("cohort_ref", "comparison", mode="before")
    @classmethod
    def reject_unsupported_optional(cls, value: object) -> object:
        if value is not None:
            raise ValueError("cohort_ref and comparison are not supported by analytics-first-purchase-path/v1")
        return value


class FirstPurchaseOrderHeader(FirstPurchaseModel):
    order_id: QueryOpaqueId
    synthetic_user_id: QueryOpaqueId
    paid_at: QueryDateTime
    channel: ChannelId
    gross_paid_minor: MinorAmount
    status: Literal["PAID", "CANCELLED"]


class FirstPurchaseOrderLine(FirstPurchaseModel):
    line_id: QueryOpaqueId
    order_id: QueryOpaqueId
    synthetic_user_id: QueryOpaqueId
    product_id: QueryOpaqueId
    quantity: PositiveQuantity


class FirstPurchaseRefund(FirstPurchaseModel):
    refund_id: QueryOpaqueId
    order_id: QueryOpaqueId
    synthetic_user_id: QueryOpaqueId
    refunded_at: QueryDateTime
    refund_minor: PositiveMinor


class FirstPurchaseProductRole(FirstPurchaseModel):
    product_id: QueryOpaqueId
    role: ProductRole


class FirstPurchaseSnapshot(FirstPurchaseModel):
    schema_version: Literal["analytics-first-purchase-path/v1"] = QUERY_SCHEMA
    snapshot_id: Literal["synthetic-first-purchase-v1"] = SNAPSHOT_ID
    data_version: Literal["synthetic-first-purchase-data/v1"] = DATA_VERSION
    as_of: QueryDateTime
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"
    currency: Literal["CNY"] = "CNY"
    amount_unit: Literal["minor"] = "minor"
    amount_precision: Literal["integer_fen"] = "integer_fen"
    scope: Literal["synthetic"] = "synthetic"
    contains_real_data: JsonFalse = False
    product_roles: list[FirstPurchaseProductRole]
    orders: list[FirstPurchaseOrderHeader]
    lines: list[FirstPurchaseOrderLine]
    refunds: list[FirstPurchaseRefund]

    @model_validator(mode="after")
    def layered_identity_and_amounts(self):
        roles: dict[str, str] = {}
        for row in self.product_roles:
            if row.product_id in roles:
                raise ValueError("duplicate product_id in product_roles")
            roles[row.product_id] = row.role
        headers: dict[tuple[str, str], FirstPurchaseOrderHeader] = {}
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
            refund_sum[key] = refund_sum.get(key, 0) + refund.refund_minor
            if refund_sum[key] > JS_MAX_SAFE_INTEGER:
                raise ValueError("aggregate exceeds JSON/JS safe integer transport limit")
        for key, total in refund_sum.items():
            if total > headers[key].gross_paid_minor:
                raise ValueError("refunds exceed original gross_paid_minor")
        return self

    def role_map(self) -> dict[str, str]:
        return {row.product_id: row.role for row in self.product_roles}

    def unmapped_product_ids(self) -> tuple[str, ...]:
        mapped = self.role_map()
        missing = {line.product_id for line in self.lines if line.product_id not in mapped}
        return tuple(sorted(missing, key=encode_key))


def snapshot_digest(snapshot: FirstPurchaseSnapshot | dict[str, Any]) -> str:
    snapshot = revalidate_model(FirstPurchaseSnapshot, snapshot)
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
        "product_roles": sorted(
            (row.model_dump(mode="json") for row in snapshot.product_roles),
            key=lambda row: row["product_id"],
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


class FirstPurchaseResolvedFilters(FirstPurchaseModel):
    schema_version: Literal["analytics-first-purchase-path/v1"] = QUERY_SCHEMA
    query_id: Literal["first_purchase_product_path"] = QUERY_ID
    query_version: Literal["first-purchase-path-query/v1"] = QUERY_VERSION
    metric_id: Literal["first_purchase_product_n_day_finished"] = METRIC_ID
    metric_version: Literal["first-purchase-path-metric/v1"] = METRIC_VERSION
    data_version: Literal["synthetic-first-purchase-data/v1"] = DATA_VERSION
    hash_version: Literal["first-purchase-path-filter-hash/v1"] = HASH_VERSION
    cohort_window_kind: Literal["FIXED"] = "FIXED"
    resolved_cohort_start: QueryDateTime
    resolved_cohort_end: QueryDateTime
    observation_days: ObservationDays
    data_snapshot_ref: Literal["synthetic-first-purchase-v1"] = SNAPSHOT_ID
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

    @field_serializer("resolved_cohort_start", "resolved_cohort_end", "as_of")
    def serialize_resolved_times(self, value: datetime) -> str:
        return canonical_rfc3339(value)

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


def bind_resolved_filters(
    request: FirstPurchaseQueryRequest | dict[str, Any],
    snapshot: FirstPurchaseSnapshot | dict[str, Any],
    permission_scope: str,
) -> FirstPurchaseResolvedFilters:
    request = revalidate_model(FirstPurchaseQueryRequest, request)
    snapshot = revalidate_model(FirstPurchaseSnapshot, snapshot)
    if type(permission_scope) is not str or not permission_scope:
        raise ValueError("permission_scope must be a non-empty string")
    if request.data_snapshot_ref != snapshot.snapshot_id:
        raise ValueError("data_snapshot_ref does not match the snapshot")
    if request.timezone != snapshot.timezone:
        raise ValueError("timezone must match the registered snapshot")
    zone = ZoneInfo(request.timezone)
    start = datetime.combine(request.cohort_window.start_date, time.min, tzinfo=zone)
    end = datetime.combine(request.cohort_window.end_date, time.min, tzinfo=zone)
    channels = tuple(sorted(request.channel_ids)) if request.channel_ids else REGISTERED_CHANNELS
    digest = snapshot_digest(snapshot)
    payload = filter_hash_payload(
        as_of=snapshot.as_of,
        channel_ids=channels,
        data_digest=digest,
        data_snapshot_ref=snapshot.snapshot_id,
        data_version=snapshot.data_version,
        observation_days=request.observation_days,
        permission_scope=permission_scope,
        resolved_cohort_end=end,
        resolved_cohort_start=start,
        timezone_name=request.timezone,
    )
    return FirstPurchaseResolvedFilters(
        resolved_cohort_start=start,
        resolved_cohort_end=end,
        observation_days=request.observation_days,
        as_of=snapshot.as_of,
        channel_ids=channels,
        permission_scope=permission_scope,
        data_digest=digest,
        filter_hash=compute_filter_hash(payload),
    )


class FirstPurchaseEmptyReason(StrEnum):
    EMPTY_MATURE_COHORT = EMPTY_MATURE_COHORT


class FirstPurchaseProductRow(FirstPurchaseModel):
    product_id: QueryOpaqueId
    role: ProductRole
    enrolled_count: StrictCount
    mature_count: StrictCount
    immature_count: StrictCount
    finished_conversion_count: StrictCount
    finished_conversion_ratio: Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)] | None = None
    empty_reason: Literal["EMPTY_MATURE_COHORT"] | None = None

    @field_validator("finished_conversion_ratio")
    @classmethod
    def finite_ratio(cls, value: float | None) -> float | None:
        if value is None:
            return value
        if type(value) is not float or not math.isfinite(value):
            raise ValueError("ratio must be a finite float in [0, 1]")
        return value

    @model_validator(mode="after")
    def count_ratio_invariants(self):
        if self.enrolled_count != self.mature_count + self.immature_count:
            raise ValueError("enrolled_count must equal mature_count + immature_count")
        if self.finished_conversion_count > self.mature_count:
            raise ValueError("finished_conversion_count must be <= mature_count")
        if self.mature_count == 0:
            if self.finished_conversion_count != 0:
                raise ValueError("empty mature cohort cannot have conversion counts")
            if self.finished_conversion_ratio is not None:
                raise ValueError("empty mature cohort ratio must be null")
            if self.empty_reason != FirstPurchaseEmptyReason.EMPTY_MATURE_COHORT:
                raise ValueError("empty mature cohort requires EMPTY_MATURE_COHORT")
            return self
        if self.empty_reason is not None:
            raise ValueError("non-empty mature cohort cannot set empty reason")
        if self.finished_conversion_ratio is None:
            raise ValueError("non-empty mature cohort ratio is required")
        if self.finished_conversion_ratio != self.finished_conversion_count / self.mature_count:
            raise ValueError("finished_conversion_ratio must equal conversion/mature")
        return self


class FirstPurchaseFacts(FirstPurchaseModel):
    display_name: Literal["首购商品路径 / N日正装转化"] = DISPLAY_NAME
    currency: Literal["CNY"] = "CNY"
    amount_unit: Literal["minor"] = "minor"
    amount_precision: Literal["integer_fen"] = "integer_fen"
    observation_days: ObservationDays
    cohort_enrolled_count: StrictCount
    cohort_mature_count: StrictCount
    cohort_immature_count: StrictCount
    products: list[FirstPurchaseProductRow]

    @model_validator(mode="after")
    def cohort_and_product_invariants(self):
        if self.cohort_enrolled_count != self.cohort_mature_count + self.cohort_immature_count:
            raise ValueError("cohort enrolled must equal mature + immature")
        ids = [row.product_id for row in self.products]
        if ids != sorted(ids, key=encode_key):
            raise ValueError("product rows must be ordered by encode(product_id)")
        if len(ids) != len(set(ids)):
            raise ValueError("product rows must not repeat product_id")
        dumped = canonical_json(self.model_dump(mode="json"))
        for banned in ("user_ids", "order_ids", "synthetic_user_ids", "members", "cohort_members"):
            if banned in dumped:
                raise ValueError("facts must not include member identity lists")
        return self


class FirstPurchaseResult(FirstPurchaseModel):
    schema_version: Literal["analytics-first-purchase-path/v1"] = QUERY_SCHEMA
    answer_mode: Literal["DETERMINISTIC_TOOL"] = "DETERMINISTIC_TOOL"
    query_id: Literal["first_purchase_product_path"] = QUERY_ID
    query_version: Literal["first-purchase-path-query/v1"] = QUERY_VERSION
    metric_id: Literal["first_purchase_product_n_day_finished"] = METRIC_ID
    metric_version: Literal["first-purchase-path-metric/v1"] = METRIC_VERSION
    data_version: Literal["synthetic-first-purchase-data/v1"] = DATA_VERSION
    hash_version: Literal["first-purchase-path-filter-hash/v1"] = HASH_VERSION
    contains_real_data: JsonFalse = False
    data_source: Literal["SYNTHETIC_SNAPSHOT"] = "SYNTHETIC_SNAPSHOT"
    data_snapshot_ref: Literal["synthetic-first-purchase-v1"] = SNAPSHOT_ID
    as_of: QueryDateTime
    resolved_filters: FirstPurchaseResolvedFilters
    filter_hash: Sha256Hex
    status: Literal["OK", "REJECTED"]
    reason_code: Literal["MISSING_PRODUCT_ROLE"] | None = None
    missing_product_ids: list[str] = Field(default_factory=list)
    facts: FirstPurchaseFacts | None = None
    limitations: Annotated[list[str], Field(min_length=1)]

    @field_serializer("as_of")
    def serialize_as_of(self, value: datetime) -> str:
        return canonical_rfc3339(value)

    @model_validator(mode="after")
    def bind_resolved_projection(self):
        resolved = self.resolved_filters
        if self.filter_hash != resolved.filter_hash:
            raise ValueError("result filter_hash must match resolved_filters.filter_hash")
        if canonical_rfc3339(self.as_of) != canonical_rfc3339(resolved.as_of):
            raise ValueError("result as_of must match the snapshot-resolved as_of")
        if self.status == "OK":
            if self.facts is None:
                raise ValueError("OK result requires facts")
            if self.reason_code is not None or self.missing_product_ids:
                raise ValueError("OK result cannot include a missing-role reject")
            if self.facts.observation_days != resolved.observation_days:
                raise ValueError("facts.observation_days must match resolved_filters")
            return self
        if self.facts is not None:
            raise ValueError("REJECTED result cannot include facts or conversion ratios")
        if self.reason_code != MISSING_PRODUCT_ROLE:
            raise ValueError("REJECTED result requires MISSING_PRODUCT_ROLE")
        if not self.missing_product_ids:
            raise ValueError("REJECTED result requires missing_product_ids")
        if self.missing_product_ids != sorted(self.missing_product_ids, key=encode_key):
            raise ValueError("missing_product_ids must be ordered by encode(product_id)")
        if len(self.missing_product_ids) != len(set(self.missing_product_ids)):
            raise ValueError("missing_product_ids must be unique")
        dumped = canonical_json(self.model_dump(mode="json"))
        for banned in ("finished_conversion_ratio", "finished_conversion_count"):
            if banned in dumped:
                raise ValueError("REJECTED result must not emit conversion fields")
        return self


def result_to_json(result: FirstPurchaseResult) -> dict[str, Any]:
    return json.loads(result.model_dump_json())
