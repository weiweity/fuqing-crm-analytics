"""Synthetic analytics warehouse (W1/W2/W3). Importing this package never opens DuckDB."""

from backend.services.analytics.warehouse.contract import (
    AMOUNT_PRECISION,
    AMOUNT_UNIT,
    CURRENCY,
    EMPTY_DENOMINATOR,
    GENERATOR_VERSION,
    PIPELINE_VERSION,
    RULE_VERSION,
    SCHEMA_VERSION,
    TIMEZONE,
    PermissionScopeDenied,
    ratio_from_counts,
    utc_naive_instant,
)
from backend.services.analytics.warehouse.facts import (
    customer_key_for_source,
    read_fact_order_header,
    read_fact_order_line,
    read_first_purchases,
)
from backend.services.analytics.warehouse.generate import (
    generate_synthetic_sources,
    write_tabular_sources,
)
from backend.services.analytics.warehouse.pipeline import run_warehouse_pipeline

__all__ = [
    "AMOUNT_PRECISION",
    "AMOUNT_UNIT",
    "CURRENCY",
    "EMPTY_DENOMINATOR",
    "GENERATOR_VERSION",
    "PIPELINE_VERSION",
    "RULE_VERSION",
    "SCHEMA_VERSION",
    "TIMEZONE",
    "PermissionScopeDenied",
    "customer_key_for_source",
    "generate_synthetic_sources",
    "ratio_from_counts",
    "read_fact_order_header",
    "read_fact_order_line",
    "read_first_purchases",
    "run_warehouse_pipeline",
    "utc_naive_instant",
    "write_tabular_sources",
]
