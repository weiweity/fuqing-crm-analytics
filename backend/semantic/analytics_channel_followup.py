"""Candidate metric/query versions for channel first-observed follow-up.

This module is metadata only. It does not query data, run SQL, or schedule work.
The subset remains a synthetic candidate; it is not an accounting-approved metric.
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
    FAMILY_FIRST_PURCHASE_PRODUCT_PATH: FAMILY_STATUS_DEFERRED,
    FAMILY_CANDIDATE_HANDOFF_AUDIENCE: FAMILY_STATUS_DEFERRED,
}

LIMITATIONS = (
    "synthetic 候选口径：首次观察到的渠道 / N日二单率，不是真实获客、终身复购或会计批准。",
    "窗口净支付含有效首单观察值，不是利润或增量；缺成本为 null，不填 ROI。",
    "本单元只有查询合同与手工金标准；SQL、worker、调度与 HTTP API 尚未实现。",
    "filter_hash 只证明规范化 payload 自洽，不是权限凭证；G4 仍须按 trusted request/snapshot/scope 绑定核验。",
    "整数 wire 字段上限 9007199254740991 是 JSON/JS 安全整数传输约束，不是经营阈值。",
)
