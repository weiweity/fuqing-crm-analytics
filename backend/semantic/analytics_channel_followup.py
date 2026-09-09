"""Candidate metric and fixed SQL for channel first-observed follow-up.

SQL lives here so the service does not scatter metric definitions. This module
does not open DuckDB, HTTP, or a worker. The subset remains a synthetic
candidate; it is not an accounting-approved metric.
"""

QUERY_SCHEMA = "analytics-channel-followup/v1"
QUERY_ID = "channel_first_observed_followup"
QUERY_VERSION = "channel-followup-query/v1"
METRIC_ID = "channel_first_observed_n_day_repeat"
METRIC_VERSION = "channel-followup-metric/v1"
DATA_VERSION = "synthetic-channel-followup-data/v1"
HASH_VERSION = "channel-followup-filter-hash/v1"
SNAPSHOT_ID = "synthetic-channel-followup-v1"
DISPLAY_NAME = "首次观察到的渠道 / N日二单率"
TIMEZONE = "Asia/Shanghai"
CURRENCY = "CNY"
AMOUNT_UNIT = "minor"
AMOUNT_PRECISION = "integer_fen"
SCOPE = "synthetic"
REGISTERED_CHANNELS = ("A", "B")
OBSERVATION_DAYS = (30, 60, 90)
AS_OF = "2026-09-01T00:00:00+08:00"
COHORT_START_DATE = "2026-06-01"
COHORT_END_DATE = "2026-09-01"

FAMILY_CHANNEL_FOLLOWUP = QUERY_ID
FAMILY_FIRST_PURCHASE_PRODUCT_PATH = "first_purchase_product_path"
FAMILY_CANDIDATE_HANDOFF_AUDIENCE = "candidate_handoff_audience"

FAMILY_STATUS_SUPPORTED_CONTRACT = "SUPPORTED_CONTRACT"
FAMILY_STATUS_DEFERRED = "DEFERRED"

QUERY_FAMILY_STATUS = {
    FAMILY_CHANNEL_FOLLOWUP: FAMILY_STATUS_SUPPORTED_CONTRACT,
    FAMILY_FIRST_PURCHASE_PRODUCT_PATH: FAMILY_STATUS_SUPPORTED_CONTRACT,
    FAMILY_CANDIDATE_HANDOFF_AUDIENCE: FAMILY_STATUS_DEFERRED,
}

LIMITATIONS = (
    "synthetic 候选口径：首次观察到的渠道 / N日二单率，不是真实获客、终身复购或会计批准。",
    "窗口净支付含有效首单观察值，不是利润或增量；缺成本为 null，不填 ROI。",
    "filter_hash 只证明规范化 payload 自洽，不是权限凭证；G4 仍须按 trusted request/snapshot/scope 绑定核验。",
    "整数 wire 字段上限 9007199254740991 是 JSON/JS 安全整数传输约束，不是经营阈值。",
)

# UTC-naive TIMESTAMP instants. TIMESTAMPTZ/SET TimeZone needs ICU, which this
# isolated engine must not autoload. String identity uses encode() so join,
# group, and ASCII order cannot follow session/column collation.
CHANNEL_FOLLOWUP_SQL = """
WITH refunds_as_of AS (
    SELECT synthetic_user_id, order_id, SUM(refund_minor) AS refund_minor
    FROM main.channel_followup_refunds
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
    FROM main.channel_followup_orders o
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
windowed AS (
    SELECT
        c.synthetic_user_id,
        c.paid_at AS first_paid_at,
        c.channel AS first_channel,
        c.net_paid_minor AS first_net,
        later.order_id AS later_order_id,
        later.channel AS later_channel,
        later.net_paid_minor AS later_net
    FROM cohort c
    LEFT JOIN valid_orders later
      ON encode(later.synthetic_user_id) = encode(c.synthetic_user_id)
     AND (
            later.paid_at > c.paid_at
            OR (later.paid_at = c.paid_at AND encode(later.order_id) > encode(c.order_id))
         )
     AND later.paid_at <= c.paid_at + (? * INTERVAL '24 hours')
),
user_metrics AS (
    SELECT
        first_channel,
        synthetic_user_id,
        BOOL_OR(later_order_id IS NOT NULL) AS has_repeat,
        BOOL_OR(later_order_id IS NOT NULL AND encode(later_channel) <> encode(first_channel)) AS has_cross,
        first_net + COALESCE(SUM(later_net), 0) AS window_net,
        (? >= first_paid_at + (? * INTERVAL '24 hours')) AS is_mature
    FROM windowed
    GROUP BY encode(first_channel), encode(synthetic_user_id),
             first_channel, synthetic_user_id, first_paid_at, first_net
),
channel_metrics AS (
    SELECT
        first_channel AS channel_id,
        COUNT(*) FILTER (WHERE is_mature) AS channel_mature_cohort_count,
        COUNT(*) FILTER (WHERE NOT is_mature) AS channel_immature_count,
        COUNT(*) FILTER (WHERE is_mature AND has_repeat) AS channel_repeat_count,
        COUNT(*) FILTER (WHERE is_mature AND has_cross) AS channel_cross_channel_count,
        CASE
            WHEN COUNT(*) FILTER (WHERE is_mature) = 0 THEN NULL
            ELSE SUM(window_net) FILTER (WHERE is_mature)
        END AS channel_window_net_paid_minor
    FROM user_metrics
    GROUP BY encode(first_channel), first_channel
)
SELECT
    selected.channel_id,
    COALESCE(channel_metrics.channel_mature_cohort_count, 0) AS channel_mature_cohort_count,
    COALESCE(channel_metrics.channel_immature_count, 0) AS channel_immature_count,
    COALESCE(channel_metrics.channel_repeat_count, 0) AS channel_repeat_count,
    COALESCE(channel_metrics.channel_cross_channel_count, 0) AS channel_cross_channel_count,
    channel_metrics.channel_window_net_paid_minor
FROM (SELECT UNNEST(?::VARCHAR[]) AS channel_id) AS selected
LEFT JOIN channel_metrics
  ON encode(selected.channel_id) = encode(channel_metrics.channel_id)
ORDER BY encode(selected.channel_id)
"""

CHANNEL_FOLLOWUP_PARAM_ORDER = (
    "as_of",
    "as_of",
    "cohort_start",
    "cohort_end",
    "channel_ids",
    "observation_days",
    "as_of",
    "observation_days",
    "channel_ids",
)


def utc_naive_instant(value):
    """Store/compare timezone-aware instants as UTC TIMESTAMP without session TZ."""
    from datetime import datetime, timezone

    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("query timestamps must be timezone-aware instants")
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def channel_followup_query():
    """Fixed parameterized query. No model SQL and no inherited FilterSpec."""
    return CHANNEL_FOLLOWUP_SQL, CHANNEL_FOLLOWUP_PARAM_ORDER


def channel_followup_query_parameters(resolved):
    as_of = utc_naive_instant(resolved.as_of)
    start = utc_naive_instant(resolved.resolved_cohort_start)
    end = utc_naive_instant(resolved.resolved_cohort_end)
    channels = list(resolved.channel_ids)
    days = resolved.observation_days
    return [as_of, as_of, start, end, channels, days, as_of, days, channels]
