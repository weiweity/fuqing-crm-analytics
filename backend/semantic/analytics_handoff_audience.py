"""Independent read-only candidate handoff-audience contract and fixed SQL.

Offline synthetic candidate only. Not DRAFT_EXPORT and not a marketing send.
This module does not open DuckDB, HTTP, or a worker, and it does not go through
catalog.require_supported_query.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

QUERY_SCHEMA = "analytics-handoff-audience/v1"
QUERY_ID = "candidate_handoff_audience"
QUERY_VERSION = "handoff-audience-query/v1"
RULE_VERSION = "handoff-audience-rule/v1"
DATA_VERSION = "synthetic-handoff-audience-data/v1"
HASH_VERSION = "handoff-audience-filter-hash/v1"
SNAPSHOT_ID = "synthetic-handoff-audience-v1"
MAPPING_VERSION = "sample-full-map/v1"
DISPLAY_NAME = "候选承接人群"
TIMEZONE = "Asia/Shanghai"
CURRENCY = "CNY"
AMOUNT_UNIT = "minor"
AMOUNT_PRECISION = "integer_fen"
SCOPE = "synthetic"
REGISTERED_CHANNELS = ("A", "B")
OBSERVATION_DAYS = (30, 60, 90)
EXCLUDE_MIN_VALID_ORDERS = 2
AUDIENCE_KIND = "READ_ONLY_DEFINITION"
EXPORT_STATUS = "NOT_DRAFT_EXPORT"
FAMILY_STATUS = "DEFERRED"
JS_MAX_SAFE_INTEGER = 9007199254740991

LIMITATIONS = (
    "synthetic 候选口径：只读人群定义，不是 DRAFT_EXPORT，不发送营销。",
    "成员列表只用于 cohort_digest，不进入 facts，不导出名单。",
    "规则：首购渠道、首购含指定小样、N 日内买到映射正装、排除窗口内有效订单数≥2 的人；仅成熟用户入选。",
    "同篮小样+正装且观察窗内无第二笔有效订单才可能入选；未成熟不能断定不会出现第二笔。",
    "无成员时 cohort_count=0 且 digest 仍由空成员集+规则版本稳定计算，不得伪造人数。",
    "cohort_digest / filter_hash 不是权限凭证；source_result_ref 只是离线绑定字段，本子集不访问 HTTP。",
)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RESULT_REF = re.compile(r"^[A-Za-z0-9_.:#-]+$")
_REQUEST_KEYS = frozenset({
    "schema_version",
    "query_id",
    "query_version",
    "cohort_window",
    "observation_days",
    "data_snapshot_ref",
    "timezone",
    "first_channel",
    "sample_product_id",
    "mapping_version",
    "rule_version",
    "source_result_ref",
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
    "rule",
})
_RULE_KEYS = frozenset({
    "rule_version",
    "first_channel",
    "sample_product_id",
    "requires_mapped_full_in_window",
    "exclude_min_valid_orders_in_window",
    "require_mature",
    "window_includes_first_order",
    "sample_to_full_includes_first_order",
    "notes",
})

HANDOFF_AUDIENCE_SQL = """
WITH refunds_as_of AS (
    SELECT synthetic_user_id, order_id, SUM(refund_minor) AS refund_minor
    FROM main.handoff_refunds
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
    FROM main.handoff_orders o
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
      AND encode(channel) = encode(?)
),
window_counts AS (
    SELECT
        c.synthetic_user_id,
        c.order_id,
        c.paid_at,
        COUNT(vo.order_id) AS valid_orders_in_window
    FROM cohort c
    INNER JOIN valid_orders vo
      ON encode(vo.synthetic_user_id) = encode(c.synthetic_user_id)
     AND vo.paid_at >= c.paid_at
     AND vo.paid_at <= c.paid_at + (? * INTERVAL '24 hours')
    GROUP BY encode(c.synthetic_user_id), encode(c.order_id), c.synthetic_user_id, c.order_id, c.paid_at
)
SELECT c.synthetic_user_id
FROM cohort c
INNER JOIN window_counts w
  ON encode(w.synthetic_user_id) = encode(c.synthetic_user_id)
WHERE ? >= c.paid_at + (? * INTERVAL '24 hours')
  AND w.valid_orders_in_window < ?
  AND EXISTS (
        SELECT 1
        FROM main.handoff_lines l
        WHERE encode(l.synthetic_user_id) = encode(c.synthetic_user_id)
          AND encode(l.order_id) = encode(c.order_id)
          AND encode(l.product_id) = encode(?)
      )
  AND EXISTS (
        SELECT 1
        FROM main.handoff_sku_map m
        INNER JOIN valid_orders vo
          ON encode(vo.synthetic_user_id) = encode(c.synthetic_user_id)
         AND vo.paid_at >= c.paid_at
         AND vo.paid_at <= c.paid_at + (? * INTERVAL '24 hours')
        INNER JOIN main.handoff_lines l
          ON encode(l.synthetic_user_id) = encode(vo.synthetic_user_id)
         AND encode(l.order_id) = encode(vo.order_id)
         AND encode(l.product_id) = encode(m.full_product_id)
        WHERE encode(m.sample_product_id) = encode(?)
      )
ORDER BY encode(c.synthetic_user_id)
"""


@dataclass(frozen=True)
class HandoffResolved:
    resolved_cohort_start: datetime
    resolved_cohort_end: datetime
    observation_days: int
    as_of: datetime
    first_channel: str
    sample_product_id: str
    full_product_id: str
    mapping_version: str
    rule_version: str
    source_result_ref: str
    permission_scope: str
    data_digest: str
    filter_hash: str

    def as_dict(self) -> dict:
        return {
            "resolved_cohort_start": canonical_rfc3339(self.resolved_cohort_start),
            "resolved_cohort_end": canonical_rfc3339(self.resolved_cohort_end),
            "observation_days": self.observation_days,
            "as_of": canonical_rfc3339(self.as_of),
            "first_channel": self.first_channel,
            "sample_product_id": self.sample_product_id,
            "full_product_id": self.full_product_id,
            "mapping_version": self.mapping_version,
            "rule_version": self.rule_version,
            "source_result_ref": self.source_result_ref,
            "permission_scope": self.permission_scope,
            "data_digest": self.data_digest,
            "filter_hash": self.filter_hash,
            "hash_version": HASH_VERSION,
            "timezone": TIMEZONE,
            "exclude_min_valid_orders_in_window": EXCLUDE_MIN_VALID_ORDERS,
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
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True, allow_nan=False)


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


def audience_digest_canonical(members: list[str], rule_version: str) -> str:
    if any(type(item) is not str or not item for item in members):
        raise ValueError("members used for digest must be non-empty strings")
    payload = {
        "members": sorted(members),
        "rule_version": require_str_id(rule_version, name="rule_version"),
    }
    return canonical_json(payload)


def audience_digest(members: list[str], rule_version: str) -> str:
    return sha256_hex(audience_digest_canonical(members, rule_version))


def mapping_full_product(pairs: list[tuple[str, str]], sample_product_id: str) -> str:
    matches = [full for sample, full in pairs if sample == sample_product_id]
    if len(matches) != 1:
        raise ValueError("sample_product_id must exist exactly once in the mapping")
    return matches[0]


def validate_handoff_request(request: dict) -> dict:
    if not isinstance(request, dict):
        raise ValueError("request must be an object")
    extra = set(request) - _REQUEST_KEYS
    if extra:
        raise ValueError(f"unsupported request fields: {sorted(extra)}")
    missing = _REQUEST_KEYS - set(request)
    if missing:
        raise ValueError(f"missing request fields: {sorted(missing)}")
    if request["schema_version"] != QUERY_SCHEMA:
        raise ValueError("unsupported handoff schema_version")
    if request["query_id"] != QUERY_ID:
        raise ValueError("query_id must be candidate_handoff_audience")
    if request["query_version"] != QUERY_VERSION:
        raise ValueError("unsupported query_version")
    if request["timezone"] != TIMEZONE:
        raise ValueError("timezone must match the registered snapshot")
    if request["mapping_version"] != MAPPING_VERSION:
        raise ValueError("unsupported mapping_version")
    if request["rule_version"] != RULE_VERSION:
        raise ValueError("unsupported rule_version")
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
    first_channel = require_str_id(request["first_channel"], name="first_channel")
    if first_channel not in REGISTERED_CHANNELS:
        raise ValueError("unregistered first_channel")
    source_result_ref = require_str_id(request["source_result_ref"], name="source_result_ref")
    if not _RESULT_REF.fullmatch(source_result_ref):
        raise ValueError("source_result_ref is invalid")
    return {
        "observation_days": days,
        "start_date": start,
        "end_date": end,
        "first_channel": first_channel,
        "sample_product_id": require_str_id(request["sample_product_id"], name="sample_product_id"),
        "mapping_version": request["mapping_version"],
        "rule_version": request["rule_version"],
        "source_result_ref": source_result_ref,
        "data_snapshot_ref": request["data_snapshot_ref"],
    }


def _validate_rule(rule: dict) -> dict:
    if not isinstance(rule, dict) or set(rule) != _RULE_KEYS:
        raise ValueError("handoff rule fields are invalid")
    if rule["rule_version"] != RULE_VERSION:
        raise ValueError("unsupported rule_version")
    if rule["first_channel"] not in REGISTERED_CHANNELS:
        raise ValueError("unregistered rule first_channel")
    if rule["requires_mapped_full_in_window"] is not True:
        raise ValueError("rule requires mapped full in window")
    if rule["exclude_min_valid_orders_in_window"] != EXCLUDE_MIN_VALID_ORDERS:
        raise ValueError("exclude_min_valid_orders_in_window must be 2")
    if rule["require_mature"] is not True:
        raise ValueError("rule requires mature users")
    if rule["window_includes_first_order"] is not True:
        raise ValueError("rule window must include the first order")
    if rule["sample_to_full_includes_first_order"] is not True:
        raise ValueError("rule sample_to_full must include the first order")
    notes = rule["notes"]
    if not isinstance(notes, list) or any(type(item) is not str or not item for item in notes):
        raise ValueError("rule notes must be non-empty strings")
    return rule


def validate_handoff_snapshot(snapshot: dict) -> dict:
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be an object")
    extra = set(snapshot) - _SNAPSHOT_KEYS
    if extra:
        raise ValueError(f"unsupported snapshot fields: {sorted(extra)}")
    missing = _SNAPSHOT_KEYS - set(snapshot)
    if missing:
        raise ValueError(f"missing snapshot fields: {sorted(missing)}")
    if snapshot["schema_version"] != QUERY_SCHEMA or snapshot["snapshot_id"] != SNAPSHOT_ID:
        raise ValueError("unsupported handoff snapshot identity")
    if snapshot["data_version"] != DATA_VERSION:
        raise ValueError("unsupported data_version")
    if snapshot["timezone"] != TIMEZONE or snapshot["currency"] != CURRENCY:
        raise ValueError("snapshot timezone/currency mismatch")
    if snapshot["amount_unit"] != AMOUNT_UNIT or snapshot["amount_precision"] != AMOUNT_PRECISION:
        raise ValueError("snapshot amount unit mismatch")
    if snapshot["scope"] != SCOPE or snapshot["contains_real_data"] is not False:
        raise ValueError("snapshot must be synthetic with contains_real_data=false")
    as_of = parse_aware(snapshot["as_of"])
    rule = _validate_rule(snapshot["rule"])
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
    if rule["sample_product_id"] not in seen_samples:
        raise ValueError("rule sample_product_id is not in the mapping")
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
        "rule": rule,
        "raw": snapshot,
    }


def snapshot_digest(snapshot: dict) -> str:
    validated = validate_handoff_snapshot(snapshot)
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
        "rule_version": validated["rule"]["rule_version"],
        "sku_mappings": [
            {"full_product_id": full, "sample_product_id": sample}
            for sample, full in sorted(validated["pairs"])
        ],
        "snapshot_id": SNAPSHOT_ID,
    }
    return sha256_hex(canonical_json(payload))


def resolve_handoff(request: dict, snapshot: dict, permission_scope: str) -> HandoffResolved:
    parsed_request = validate_handoff_request(request)
    parsed_snapshot = validate_handoff_snapshot(snapshot)
    if type(permission_scope) is not str or not permission_scope:
        raise ValueError("permission_scope must be a non-empty string")
    rule = parsed_snapshot["rule"]
    if parsed_request["rule_version"] != rule["rule_version"]:
        raise ValueError("request rule_version does not match snapshot rule")
    if parsed_request["first_channel"] != rule["first_channel"]:
        raise ValueError("request first_channel does not match snapshot rule")
    if parsed_request["sample_product_id"] not in {sample for sample, _full in parsed_snapshot["pairs"]}:
        raise ValueError("sample_product_id is not in the mapping")
    zone = ZoneInfo(TIMEZONE)
    start = datetime.combine(parsed_request["start_date"], time.min, tzinfo=zone)
    end = datetime.combine(parsed_request["end_date"], time.min, tzinfo=zone)
    digest = snapshot_digest(snapshot)
    full_product_id = mapping_full_product(parsed_snapshot["pairs"], parsed_request["sample_product_id"])
    payload = {
        "as_of": canonical_rfc3339(parsed_snapshot["as_of"]),
        "data_digest": digest,
        "data_snapshot_ref": parsed_request["data_snapshot_ref"],
        "data_version": DATA_VERSION,
        "first_channel": parsed_request["first_channel"],
        "hash_version": HASH_VERSION,
        "mapping_version": parsed_request["mapping_version"],
        "observation_days": parsed_request["observation_days"],
        "permission_scope": permission_scope,
        "query_id": QUERY_ID,
        "query_version": QUERY_VERSION,
        "resolved_cohort_end": canonical_rfc3339(end),
        "resolved_cohort_start": canonical_rfc3339(start),
        "rule_version": parsed_request["rule_version"],
        "sample_product_id": parsed_request["sample_product_id"],
        "source_result_ref": parsed_request["source_result_ref"],
        "timezone": TIMEZONE,
    }
    return HandoffResolved(
        resolved_cohort_start=start,
        resolved_cohort_end=end,
        observation_days=parsed_request["observation_days"],
        as_of=parsed_snapshot["as_of"],
        first_channel=parsed_request["first_channel"],
        sample_product_id=parsed_request["sample_product_id"],
        full_product_id=full_product_id,
        mapping_version=parsed_request["mapping_version"],
        rule_version=parsed_request["rule_version"],
        source_result_ref=parsed_request["source_result_ref"],
        permission_scope=permission_scope,
        data_digest=digest,
        filter_hash=sha256_hex(canonical_json(payload)),
    )


def handoff_audience_parameters(resolved: HandoffResolved) -> list:
    as_of = utc_naive_instant(resolved.as_of)
    start = utc_naive_instant(resolved.resolved_cohort_start)
    end = utc_naive_instant(resolved.resolved_cohort_end)
    days = resolved.observation_days
    return [
        as_of,
        as_of,
        start,
        end,
        resolved.first_channel,
        days,
        as_of,
        days,
        EXCLUDE_MIN_VALID_ORDERS,
        resolved.sample_product_id,
        days,
        resolved.sample_product_id,
    ]
