"""W4 shared customer features over a published synthetic warehouse. No DuckDB on import."""

from backend.services.analytics.customer_features.compute import (
    CustomerFeatureRun,
    compute_customer_features,
    write_customer_features,
)
from backend.services.analytics.customer_features.contract import (
    FEATURE_LAYER_VERSION,
    FEATURE_PIPELINE_VERSION,
    RECENCY_UNIT,
    SECONDS_PER_DAY,
    VALID_ORDER_RULE,
)

from backend.services.analytics.customer_features.published import (
    FeaturePublicationStore, FeatureSnapshot, PublicationConflict,
)

__all__ = [
    "FeaturePublicationStore",
    "FeatureSnapshot",
    "PublicationConflict",
    "CustomerFeatureRun",
    "FEATURE_LAYER_VERSION",
    "FEATURE_PIPELINE_VERSION",
    "RECENCY_UNIT",
    "SECONDS_PER_DAY",
    "VALID_ORDER_RULE",
    "compute_customer_features",
    "write_customer_features",
]
