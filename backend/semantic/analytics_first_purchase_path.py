"""Independent first-purchase product-path contract and fixed SQL.

Offline synthetic candidate only. This module does not open DuckDB, HTTP, or a
worker, and it does not go through catalog.require_supported_query.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

QUERY_SCHEMA = "analytics-first-purchase-path/v1"
QUERY_ID = "first_purchase_product_path"
QUERY_VERSION = "first-purchase-path-query/v1"
METRIC_ID = "first_purchase_product_n_day_path"
METRIC_VERSION = "first-purchase-path-metric/v1"
DATA_VERSION = "synthetic-first-purchase-path-data/v1"
HASH_VERSION = "first-purchase-path-filter-hash/v1"
SNAPSHOT_ID = "synthetic-first-purchase-path-v1"
MAPPING_VERSION = "sample-full-map/v1"
DISPLAY_NAME = "首购商品路径 / N日后续与小样转正装"
TIMEZONE = "Asia/Shanghai"
CURRENCY = "CNY"
AMOUNT_UNIT = "minor"
AMOUNT_PRECISION = "integer_fen"
SCOPE = "synthetic"
REGISTERED_CHANNELS = ("A", "B")
OBSERVATION_DAYS = (30, 60, 90)
EMPTY_MATURE_COHORT = "EMPTY_MATURE_COHORT"
JS_MAX_SAFE_INTEGER = 9007199254740991
FAMILY_STATUS = "SUPPORTED_CONTRACT"

LIMITATIONS = (
    "synthetic 候选口径：首购商品路径，不是真实获客、终身复购或会计批准。",
    "每用户按全历史最早有效订单入组一次，本族再按该首单去重商品行展开；展开行之和不是独立人数。",
    "sample_to_full 只计 mapping 表中的小样 SKU，窗口含首单篮子内的映射正装。",
    "空成熟分母的比例为 null + EMPTY_MATURE_COHORT，不得写 0。",
    "filter_hash 只证明规范化 payload 自洽，不是权限凭证。",
)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_REQUEST_KEYS = frozenset({
    "schema_version",
    "query_id",
    "query_version",
    "metric_id",
    "metric_version",
    "cohort_window",
    "observation_days",
    "data_snapshot_ref",
    "timezone",
    "channel_ids",
    "product_ids",
    "mapping_version",
})
_SNAPSHOT_KEYS = frozenset({
    "schema_version",
    "snapshot_id",
    "data_version",
    "as_of",
    "timezone",
    "currency",
    "amount_unit",
    "amount_precision",
    "scope",
    "contains_real_data",
    "orders",
    "lines",
    "refunds",
    "sku_mappings",
})

FIRST_PURCHASE_PATH_SQL = """
WITH refunds_as_of AS (
    SELECT synthetic_user_id, order_id, SUM(refund_minor) AS refund_minor
    FROM main.first_purchase_refunds
    WHERE refunded_at <= ?
    GROUP BY encode(synthetic_user_id), encode(order_id), synthetic_user_id, order_id
),
valid_orders AS (
    SELECT
        o.synthetic_user_id,
        o.order_id,
        o.paid_at,
        o.channel,
        (o.gross_paid_minor - COALESCE(r.refund_minor, 0)) AS net_paid_minor
    FROM main.first_purchase_orders o
    LEFT JOIN refunds_as_of r
      ON encode(r.synthetic_user_id) = encode(o.synthetic_user_id)
     AND encode(r.order_id) = encode(o.order_id)
    WHERE o.status = 'PAID'
      AND o.paid_at <= ?
      AND (o.gross_paid_minor - COALESCE(r.refund_minor, 0)) > 0
),
firsts AS (
    SELECT synthetic_user_id, order_id, paid_at, channel, net_paid_minor
    FROM (
        SELECT
            valid_orders.*,
            ROW_NUMBER() OVER (
                PARTITION BY encode(synthetic_user_id)
                ORDER BY paid_at ASC, encode(order_id) ASC
            ) AS rn
        FROM valid_orders
    ) ranked
    WHERE rn = 1
),
cohort AS (
    SELECT *
    FROM firsts
    WHERE paid_at >= ?
      AND paid_at < ?
      AND list_contains(list_transform(?::VARCHAR[], x -> encode(x)), encode(channel))
),
first_products AS (
    SELECT
        c.synthetic_user_id,
        c.order_id,
        c.paid_at,
        l.product_id,
        (? >= c.paid_at + (? * INTERVAL '24 hours')) AS is_mature
    FROM cohort c
    INNER JOIN main.first_purchase_lines l
      ON encode(l.synthetic_user_id) = encode(c.synthetic_user_id)
     AND encode(l.order_id) = encode(c.order_id)
    WHERE len(?::VARCHAR[]) = 0
       OR list_contains(list_transform(?::VARCHAR[], x -> encode(x)), encode(l.product_id))
    GROUP BY encode(c.synthetic_user_id), encode(c.order_id), encode(l.product_id),
             c.synthetic_user_id, c.order_id, c.paid_at, l.product_id
),
subsequent AS (
    SELECT DISTINCT fp.synthetic_user_id, fp.product_id
    FROM first_products fp
    INNER JOIN valid_orders vo
      ON encode(vo.synthetic_user_id) = encode(fp.synthetic_user_id)
     AND (
            vo.paid_at > fp.paid_at
            OR (vo.paid_at = fp.paid_at AND encode(vo.order_id) > encode(fp.order_id))
         )
     AND vo.paid_at <= fp.paid_at + (? * INTERVAL '24 hours')
),
converted AS (
    SELECT DISTINCT fp.synthetic_user_id, fp.product_id
    FROM first_products fp
    INNER JOIN main.first_purchase_sku_map m
      ON encode(m.sample_product_id) = encode(fp.product_id)
    INNER JOIN valid_orders vo
      ON encode(vo.synthetic_user_id) = encode(fp.synthetic_user_id)
     AND vo.paid_at >= fp.paid_at
     AND vo.paid_at <= fp.paid_at + (? * INTERVAL '24 hours')
    INNER JOIN main.first_purchase_lines l
      ON encode(l.synthetic_user_id) = encode(vo.synthetic_user_id)
     AND encode(l.order_id) = encode(vo.order_id)
     AND encode(l.product_id) = encode(m.full_product_id)
)
SELECT
    fp.product_id,
    COUNT(*) FILTER (WHERE fp.is_mature) AS mature_count,
    COUNT(*) FILTER (WHERE NOT fp.is_mature) AS immature_count,
    COUNT(*) FILTER (WHERE fp.is_mature AND s.synthetic_user_id IS NOT NULL) AS subsequent_any_count,
    COUNT(*) FILTER (WHERE fp.is_mature AND c.synthetic_user_id IS NOT NULL) AS sample_to_full_count
FROM first_products fp
LEFT JOIN subsequent s
  ON encode(s.synthetic_user_id) = encode(fp.synthetic_user_id)
 AND encode(s.product_id) = encode(fp.product_id)
LEFT JOIN converted c
  ON encode(c.synthetic_user_id) = encode(fp.synthetic_user_id)
 AND encode(c.product_id) = encode(fp.product_id)
GROUP BY encode(fp.product_id), fp.product_id
ORDER BY encode(fp.product_id)
"""

COHORT_COUNT_SQL = """
WITH refunds_as_of AS (
    SELECT synthetic_user_id, order_id, SUM(refund_minor) AS refund_minor
    FROM main.first_purchase_refunds
    WHERE refunded_at <= ?
    GROUP BY encode(synthetic_user_id), encode(order_id), synthetic_user_id, order_id
),
valid_orders AS (
    SELECT
        o.synthetic_user_id,
        o.order_id,
        o.paid_at,
        o.channel,
        (o.gross_paid_minor - COALESCE(r.refund_minor, 0)) AS net_paid_minor
    FROM main.first_purchase_orders o
    LEFT JOIN refunds_as_of r
      ON encode(r.synthetic_user_id) = encode(o.synthetic_user_id)
     AND encode(r.order_id) = encode(o.order_id)
    WHERE o.status = 'PAID'
      AND o.paid_at <= ?
      AND (o.gross_paid_minor - COALESCE(r.refund_minor, 0)) > 0
),
firsts AS (
    SELECT synthetic_user_id, order_id, paid_at, channel
    FROM (
        SELECT
            valid_orders.*,
            ROW_NUMBER() OVER (
                PARTITION BY encode(synthetic_user_id)
                ORDER BY paid_at ASC, encode(order_id) ASC
            ) AS rn
        FROM valid_orders
    ) ranked
    WHERE rn = 1
),
cohort AS (
    SELECT *
    FROM firsts
    WHERE paid_at >= ?
      AND paid_at < ?
      AND list_contains(list_transform(?::VARCHAR[], x -> encode(x)), encode(channel))
)
SELECT
    COUNT(*) AS enrolled_count,
    COUNT(*) FILTER (WHERE ? >= paid_at + (? * INTERVAL '24 hours')) AS mature_count,
    COUNT(*) FILTER (WHERE ? < paid_at + (? * INTERVAL '24 hours')) AS immature_count
FROM cohort
"""


@dataclass(frozen=True)
class FirstPurchaseResolved:
    resolved_cohort_start: datetime
    resolved_cohort_end: datetime
    observation_days: int
    as_of: datetime
    channel_ids: tuple[str, ...]
    product_ids: tuple[str, ...]
    permission_scope: str
    data_digest: str
    mapping_version: str
    filter_hash: str

    def as_dict(self) -> dict:
        return {
            "resolved_cohort_start": canonical_rfc3339(self.resolved_cohort_start),
            "resolved_cohort_end": canonical_rfc3339(self.resolved_cohort_end),
            "observation_days": self.observation_days,
            "as_of": canonical_rfc3339(self.as_of),
            "channel_ids": list(self.channel_ids),
            "product_ids": list(self.product_ids),
            "permission_scope": self.permission_scope,
            "data_digest": self.data_digest,
            "mapping_version": self.mapping_version,
            "filter_hash": self.filter_hash,
            "hash_version": HASH_VERSION,
            "timezone": TIMEZONE,
        }


def utc_naive_instant(value) -> datetime:
    parsed = parse_aware(value)
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def parse_aware(value) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        return value
    if type(value) is not str or not value:
        raise ValueError("timestamps must be RFC3339 strings")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return parsed


def parse_iso_date(value) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if type(value) is not str or not _ISO_DATE.fullmatch(value):
        raise ValueError("calendar dates must be ISO YYYY-MM-DD")
    return date.fromisoformat(value)


def canonical_rfc3339(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("canonical timestamps require a timezone-aware datetime")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def require_str_id(value, *, name: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def require_minor(value, *, name: str) -> int:
    if type(value) is not int or type(value) is bool or value < 0 or value > JS_MAX_SAFE_INTEGER:
        raise ValueError(f"{name} must be integer fen in [0, {JS_MAX_SAFE_INTEGER}]")
    return value


def require_count(value, *, name: str) -> int:
    if type(value) is not int or type(value) is bool or value < 0 or value > JS_MAX_SAFE_INTEGER:
        raise ValueError(f"{name} must be a non-bool integer count")
    return value


def ratio_from_counts(numerator: int, denominator: int):
    numerator = require_count(numerator, name="numerator")
    denominator = require_count(denominator, name="denominator")
    if denominator == 0:
        return None, EMPTY_MATURE_COHORT
    return numerator / denominator, None


def product_metric_row(product_id: str, mature: int, immature: int, subsequent: int, converted: int) -> dict:
    product_id = require_str_id(product_id, name="product_id")
    mature = require_count(mature, name="mature_count")
    immature = require_count(immature, name="immature_count")
    subsequent = require_count(subsequent, name="subsequent_any_count")
    converted = require_count(converted, name="sample_to_full_count")
    if subsequent > mature or converted > mature:
        raise ValueError("product numerators cannot exceed mature_count")
    subsequent_ratio, empty = ratio_from_counts(subsequent, mature)
    converted_ratio, converted_empty = ratio_from_counts(converted, mature)
    if empty != converted_empty:
        raise ValueError("product empty-denominator markers diverged")
    return {
        "product_id": product_id,
        "mature_count": mature,
        "immature_count": immature,
        "subsequent_any_count": subsequent if mature else 0,
        "subsequent_any_ratio": subsequent_ratio,
        "sample_to_full_count": converted if mature else 0,
        "sample_to_full_ratio": converted_ratio,
        "empty_reason": empty,
    }


def _unique_str_tuple(values, *, name: str, allowed=None) -> tuple[str, ...]:
    if values is None:
        values = []
    if not isinstance(values, list) or any(type(item) is not str or not item for item in values):
        raise ValueError(f"{name} must be a list of non-empty strings")
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must not contain duplicates")
    if allowed is not None:
        extra = [item for item in values if item not in allowed]
        if extra:
            raise ValueError(f"{name} contains unregistered values")
    return tuple(values)


def validate_first_purchase_request(request: dict) -> dict:
    if not isinstance(request, dict):
        raise ValueError("request must be an object")
    extra = set(request) - _REQUEST_KEYS
    if extra:
        raise ValueError(f"unsupported request fields: {sorted(extra)}")
    missing = _REQUEST_KEYS - set(request)
    if missing:
        raise ValueError(f"missing request fields: {sorted(missing)}")
    if request["schema_version"] != QUERY_SCHEMA:
        raise ValueError("unsupported first-purchase schema_version")
    if request["query_id"] != QUERY_ID:
        raise ValueError("query_id must be first_purchase_product_path")
    if request["query_version"] != QUERY_VERSION or request["metric_id"] != METRIC_ID:
        raise ValueError("unsupported query or metric id")
    if request["metric_version"] != METRIC_VERSION:
        raise ValueError("unsupported metric_version")
    if request["timezone"] != TIMEZONE:
        raise ValueError("timezone must match the registered snapshot")
    if request["mapping_version"] != MAPPING_VERSION:
        raise ValueError("unsupported mapping_version")
    if request["data_snapshot_ref"] != SNAPSHOT_ID:
        raise ValueError("data_snapshot_ref does not match the snapshot")
    days = request["observation_days"]
    if type(days) is not int or type(days) is bool or days not in OBSERVATION_DAYS:
        raise ValueError("observation_days must be integer 30, 60 or 90")
    window = request["cohort_window"]
    if not isinstance(window, dict) or set(window) != {"kind", "start_date", "end_date"}:
        raise ValueError("cohort_window must be FIXED with start_date and end_date")
    if window["kind"] != "FIXED":
        raise ValueError("only FIXED cohort windows are supported")
    start = parse_iso_date(window["start_date"])
    end = parse_iso_date(window["end_date"])
    if end <= start:
        raise ValueError("cohort_window end must be after start")
    channels = _unique_str_tuple(request["channel_ids"], name="channel_ids", allowed=REGISTERED_CHANNELS)
    products = _unique_str_tuple(request["product_ids"], name="product_ids")
    return {
        "observation_days": days,
        "start_date": start,
        "end_date": end,
        "channel_ids": channels or REGISTERED_CHANNELS,
        "product_ids": products,
        "mapping_version": request["mapping_version"],
        "data_snapshot_ref": request["data_snapshot_ref"],
    }


def validate_first_purchase_snapshot(snapshot: dict) -> dict:
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be an object")
    extra = set(snapshot) - _SNAPSHOT_KEYS
    if extra:
        raise ValueError(f"unsupported snapshot fields: {sorted(extra)}")
    missing = _SNAPSHOT_KEYS - set(snapshot)
    if missing:
        raise ValueError(f"missing snapshot fields: {sorted(missing)}")
    if snapshot["schema_version"] != QUERY_SCHEMA or snapshot["snapshot_id"] != SNAPSHOT_ID:
        raise ValueError("unsupported first-purchase snapshot identity")
    if snapshot["data_version"] != DATA_VERSION:
        raise ValueError("unsupported data_version")
    if snapshot["timezone"] != TIMEZONE or snapshot["currency"] != CURRENCY:
        raise ValueError("snapshot timezone/currency mismatch")
    if snapshot["amount_unit"] != AMOUNT_UNIT or snapshot["amount_precision"] != AMOUNT_PRECISION:
        raise ValueError("snapshot amount unit mismatch")
    if snapshot["scope"] != SCOPE or snapshot["contains_real_data"] is not False:
        raise ValueError("snapshot must be synthetic with contains_real_data=false")
    as_of = parse_aware(snapshot["as_of"])
    orders = snapshot["orders"]
    lines = snapshot["lines"]
    refunds = snapshot["refunds"]
    mappings = snapshot["sku_mappings"]
    if not isinstance(orders, list) or not isinstance(lines, list) or not isinstance(refunds, list):
        raise ValueError("orders/lines/refunds must be lists")
    if not isinstance(mappings, dict) or set(mappings) != {"mapping_version", "pairs"}:
        raise ValueError("sku_mappings must have mapping_version and pairs")
    if mappings["mapping_version"] != MAPPING_VERSION:
        raise ValueError("unsupported mapping_version")
    pairs = mappings["pairs"]
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("sku_mappings.pairs must be a non-empty list")
    seen_samples = set()
    normalized_pairs = []
    for pair in pairs:
        if not isinstance(pair, dict) or set(pair) != {"sample_product_id", "full_product_id"}:
            raise ValueError("mapping pair must be sample_product_id and full_product_id")
        sample = require_str_id(pair["sample_product_id"], name="sample_product_id")
        full = require_str_id(pair["full_product_id"], name="full_product_id")
        if sample == full:
            raise ValueError("sample_product_id cannot equal full_product_id")
        if sample in seen_samples:
            raise ValueError("duplicate sample_product_id in mapping")
        seen_samples.add(sample)
        normalized_pairs.append((sample, full))
    order_keys = set()
    normalized_orders = []
    gross_by_key = {}
    for order in orders:
        if not isinstance(order, dict):
            raise ValueError("order rows must be objects")
        required = {"order_id", "synthetic_user_id", "paid_at", "channel", "gross_paid_minor", "status"}
        if set(order) != required:
            raise ValueError("order row fields are invalid")
        user_id = require_str_id(order["synthetic_user_id"], name="synthetic_user_id")
        order_id = require_str_id(order["order_id"], name="order_id")
        key = (user_id, order_id)
        if key in order_keys:
            raise ValueError("duplicate (synthetic_user_id, order_id)")
        order_keys.add(key)
        channel = require_str_id(order["channel"], name="channel")
        if channel not in REGISTERED_CHANNELS:
            raise ValueError("unregistered channel")
        status = require_str_id(order["status"], name="status")
        if status not in {"PAID", "CANCELLED"}:
            raise ValueError("order status must be PAID or CANCELLED")
        gross = require_minor(order["gross_paid_minor"], name="gross_paid_minor")
        paid_at = parse_aware(order["paid_at"])
        gross_by_key[key] = gross
        normalized_orders.append((user_id, order_id, paid_at, channel, gross, status))
    line_ids = set()
    normalized_lines = []
    for line in lines:
        if not isinstance(line, dict):
            raise ValueError("line rows must be objects")
        required = {"line_id", "order_id", "synthetic_user_id", "product_id", "quantity"}
        if set(line) != required:
            raise ValueError("line row fields are invalid")
        line_id = require_str_id(line["line_id"], name="line_id")
        if line_id in line_ids:
            raise ValueError("duplicate line_id")
        line_ids.add(line_id)
        user_id = require_str_id(line["synthetic_user_id"], name="synthetic_user_id")
        order_id = require_str_id(line["order_id"], name="order_id")
        if (user_id, order_id) not in order_keys:
            raise ValueError("line does not reference (synthetic_user_id, order_id)")
        quantity = line["quantity"]
        if type(quantity) is not int or type(quantity) is bool or quantity < 1:
            raise ValueError("quantity must be a positive integer")
        normalized_lines.append(
            (line_id, user_id, order_id, require_str_id(line["product_id"], name="product_id"), quantity)
        )
    refund_ids = set()
    refund_totals = {}
    normalized_refunds = []
    for refund in refunds:
        if not isinstance(refund, dict):
            raise ValueError("refund rows must be objects")
        required = {"refund_id", "order_id", "synthetic_user_id", "refunded_at", "refund_minor"}
        if set(refund) != required:
            raise ValueError("refund row fields are invalid")
        refund_id = require_str_id(refund["refund_id"], name="refund_id")
        if refund_id in refund_ids:
            raise ValueError("duplicate refund_id")
        refund_ids.add(refund_id)
        user_id = require_str_id(refund["synthetic_user_id"], name="synthetic_user_id")
        order_id = require_str_id(refund["order_id"], name="order_id")
        key = (user_id, order_id)
        if key not in order_keys:
            raise ValueError("refund does not reference (synthetic_user_id, order_id)")
        amount = require_minor(refund["refund_minor"], name="refund_minor")
        if amount < 1:
            raise ValueError("refund_minor must be positive")
        refund_totals[key] = refund_totals.get(key, 0) + amount
        if refund_totals[key] > gross_by_key[key]:
            raise ValueError("refunds exceed gross_paid_minor")
        normalized_refunds.append((refund_id, user_id, order_id, parse_aware(refund["refunded_at"]), amount))
    return {
        "as_of": as_of,
        "orders": normalized_orders,
        "lines": normalized_lines,
        "refunds": normalized_refunds,
        "pairs": normalized_pairs,
        "mapping_version": mappings["mapping_version"],
        "raw": snapshot,
    }


def snapshot_digest(snapshot: dict) -> str:
    validated = validate_first_purchase_snapshot(snapshot)
    payload = {
        "as_of": canonical_rfc3339(validated["as_of"]),
        "data_version": DATA_VERSION,
        "lines": [
            {
                "line_id": line[0],
                "order_id": line[2],
                "product_id": line[3],
                "quantity": line[4],
                "synthetic_user_id": line[1],
            }
            for line in sorted(validated["lines"], key=lambda row: (row[1], row[0]))
        ],
        "mapping_version": validated["mapping_version"],
        "orders": [
            {
                "channel": order[3],
                "gross_paid_minor": order[4],
                "order_id": order[1],
                "paid_at": canonical_rfc3339(order[2]),
                "status": order[5],
                "synthetic_user_id": order[0],
            }
            for order in sorted(validated["orders"], key=lambda row: (row[0], row[1]))
        ],
        "refunds": [
            {
                "order_id": refund[2],
                "refund_id": refund[0],
                "refund_minor": refund[4],
                "refunded_at": canonical_rfc3339(refund[3]),
                "synthetic_user_id": refund[1],
            }
            for refund in sorted(validated["refunds"], key=lambda row: (row[1], row[0]))
        ],
        "sku_mappings": [
            {"full_product_id": full, "sample_product_id": sample}
            for sample, full in sorted(validated["pairs"])
        ],
        "snapshot_id": SNAPSHOT_ID,
    }
    return sha256_hex(canonical_json(payload))


def resolve_first_purchase(request: dict, snapshot: dict, permission_scope: str) -> FirstPurchaseResolved:
    parsed_request = validate_first_purchase_request(request)
    parsed_snapshot = validate_first_purchase_snapshot(snapshot)
    if type(permission_scope) is not str or not permission_scope:
        raise ValueError("permission_scope must be a non-empty string")
    zone = ZoneInfo(TIMEZONE)
    start = datetime.combine(parsed_request["start_date"], time.min, tzinfo=zone)
    end = datetime.combine(parsed_request["end_date"], time.min, tzinfo=zone)
    digest = snapshot_digest(snapshot)
    payload = {
        "as_of": canonical_rfc3339(parsed_snapshot["as_of"]),
        "channel_ids": list(parsed_request["channel_ids"]),
        "data_digest": digest,
        "data_snapshot_ref": parsed_request["data_snapshot_ref"],
        "data_version": DATA_VERSION,
        "hash_version": HASH_VERSION,
        "mapping_version": parsed_request["mapping_version"],
        "metric_id": METRIC_ID,
        "metric_version": METRIC_VERSION,
        "observation_days": parsed_request["observation_days"],
        "permission_scope": permission_scope,
        "product_ids": list(parsed_request["product_ids"]),
        "query_id": QUERY_ID,
        "query_version": QUERY_VERSION,
        "resolved_cohort_end": canonical_rfc3339(end),
        "resolved_cohort_start": canonical_rfc3339(start),
        "timezone": TIMEZONE,
    }
    return FirstPurchaseResolved(
        resolved_cohort_start=start,
        resolved_cohort_end=end,
        observation_days=parsed_request["observation_days"],
        as_of=parsed_snapshot["as_of"],
        channel_ids=parsed_request["channel_ids"],
        product_ids=parsed_request["product_ids"],
        permission_scope=permission_scope,
        data_digest=digest,
        mapping_version=parsed_request["mapping_version"],
        filter_hash=sha256_hex(canonical_json(payload)),
    )


def first_purchase_path_parameters(resolved: FirstPurchaseResolved) -> list:
    as_of = utc_naive_instant(resolved.as_of)
    start = utc_naive_instant(resolved.resolved_cohort_start)
    end = utc_naive_instant(resolved.resolved_cohort_end)
    channels = list(resolved.channel_ids)
    products = list(resolved.product_ids)
    days = resolved.observation_days
    return [as_of, as_of, start, end, channels, as_of, days, products, products, days, days]


def first_purchase_cohort_parameters(resolved: FirstPurchaseResolved) -> list:
    as_of = utc_naive_instant(resolved.as_of)
    start = utc_naive_instant(resolved.resolved_cohort_start)
    end = utc_naive_instant(resolved.resolved_cohort_end)
    channels = list(resolved.channel_ids)
    days = resolved.observation_days
    return [as_of, as_of, start, end, channels, as_of, days, as_of, days]
