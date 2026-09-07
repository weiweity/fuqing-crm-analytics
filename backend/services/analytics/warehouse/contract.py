"""Warehouse versions, amount units, and shared helpers. No DuckDB I/O."""

from __future__ import annotations

from datetime import datetime, timezone

SCHEMA_VERSION = "analytics-warehouse-schema/v1"
RULE_VERSION = "analytics-warehouse-rules/v1"
GENERATOR_VERSION = "analytics-warehouse-generator/v1"
PIPELINE_VERSION = "analytics-warehouse-pipeline/v1"
TIMEZONE = "Asia/Shanghai"
CURRENCY = "CNY"
AMOUNT_UNIT = "minor"
AMOUNT_PRECISION = "integer_fen"
DATA_SOURCE = "SYNTHETIC_WAREHOUSE"
DEFAULT_AS_OF = "2026-09-01T00:00:00+08:00"
DEFAULT_SEED = 20260907
MAX_WIRE_INT = 9007199254740991
WAREHOUSE_DUCKDB_MEMORY_MIB = 32
WAREHOUSE_DUCKDB_THREADS = 2
WAREHOUSE_TEMP_MIB = 32
DATABASE_NAME = "warehouse.duckdb"
MANIFEST_NAME = "manifest.json"
PUBLISHED_MANIFEST_NAME = "published.json"
EMPTY_DENOMINATOR = "EMPTY_DENOMINATOR"
STATUS_PAID = "PAID"
STATUS_CANCELLED = "CANCELLED"


class PermissionScopeDenied(ValueError):
    """Cross permission_scope access is refused, not silently filtered."""


class WarehouseContractError(ValueError):
    """Synthetic warehouse input or grain contract failed."""


def require_minor(value, *, name: str) -> int:
    if type(value) is not int or value < 0 or value > MAX_WIRE_INT:
        raise WarehouseContractError(f"{name} must be integer fen in [0, {MAX_WIRE_INT}]")
    return value


def require_str_id(value, *, name: str) -> str:
    if type(value) is not str or not value:
        raise WarehouseContractError(f"{name} must be a non-empty string")
    return value


def parse_aware_instant(value) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise WarehouseContractError("timestamps must be timezone-aware")
        return value
    if type(value) is not str or not value:
        raise WarehouseContractError("timestamps must be RFC3339 strings")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise WarehouseContractError("timestamps must be timezone-aware")
    return parsed


def utc_naive_instant(value) -> datetime:
    """Store/compare aware instants as UTC TIMESTAMP without session TZ (no ICU)."""
    return parse_aware_instant(value).astimezone(timezone.utc).replace(tzinfo=None)


def ratio_from_counts(numerator: int, denominator: int):
    """Fact-layer empty-denominator policy: null, never a fake 0 ratio."""
    if type(numerator) is not int or type(denominator) is not int:
        raise WarehouseContractError("ratio counts must be integers")
    if numerator < 0 or denominator < 0:
        raise WarehouseContractError("ratio counts must be non-negative")
    if denominator == 0:
        return None, EMPTY_DENOMINATOR
    return numerator / denominator, None
