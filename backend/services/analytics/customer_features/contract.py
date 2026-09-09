"""W4 customer-feature versions. Reuses W1–W3 facts; does not define new identities."""

from __future__ import annotations

FEATURE_LAYER_VERSION = "analytics-customer-features/v1"
FEATURE_PIPELINE_VERSION = "analytics-customer-features-pipeline/v1"
SECONDS_PER_DAY = 86400
FEATURES_NAME = "customer_features.jsonl"
PUBLISHED_FEATURES_NAME = "published.json"
VALID_ORDER_RULE = "fact_order_header.is_valid"
ORDER_GRAIN = ("synthetic_user_id", "order_id")
FEATURE_GRAIN = ("permission_scope", "customer_key")
RECENCY_UNIT = "86400_second_days"
RECENCY_BASIS = "feature_as_of_minus_last_paid_at"
# Recency uses complete 86400-second days from warehouse instants, matching
# channel-followup N×24h. It is not old-CRM calendar-day RFM R, and not a bucket.
