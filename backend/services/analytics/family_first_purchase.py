"""Offline first-purchase product-path compute. No HTTP, worker, or catalog success path."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from backend.semantic.analytics_first_purchase_path import (
    AMOUNT_PRECISION,
    AMOUNT_UNIT,
    COHORT_COUNT_SQL,
    CURRENCY,
    DATA_VERSION,
    DISPLAY_NAME,
    FIRST_PURCHASE_PATH_SQL,
    HASH_VERSION,
    LIMITATIONS,
    METRIC_ID,
    METRIC_VERSION,
    QUERY_ID,
    QUERY_SCHEMA,
    QUERY_VERSION,
    first_purchase_cohort_parameters,
    first_purchase_path_parameters,
    product_metric_row,
    resolve_first_purchase,
    utc_naive_instant,
    validate_first_purchase_snapshot,
)

DATABASE_NAME = "first-purchase-path.duckdb"
MAX_DATABASE_BYTES = 4 * 1024 * 1024
DUCKDB_MEMORY_MIB = 32
DUCKDB_THREADS = 2
DUCKDB_TEMP_MIB = 32

_CREATE_SQL = """
CREATE TABLE first_purchase_orders (
    synthetic_user_id VARCHAR COLLATE C NOT NULL,
    order_id VARCHAR COLLATE C NOT NULL,
    paid_at TIMESTAMP NOT NULL,
    channel VARCHAR COLLATE C NOT NULL,
    gross_paid_minor BIGINT NOT NULL,
    status VARCHAR COLLATE C NOT NULL,
    PRIMARY KEY (synthetic_user_id, order_id)
);
CREATE TABLE first_purchase_lines (
    line_id VARCHAR COLLATE C NOT NULL PRIMARY KEY,
    synthetic_user_id VARCHAR COLLATE C NOT NULL,
    order_id VARCHAR COLLATE C NOT NULL,
    product_id VARCHAR COLLATE C NOT NULL,
    quantity BIGINT NOT NULL,
    FOREIGN KEY (synthetic_user_id, order_id)
        REFERENCES first_purchase_orders(synthetic_user_id, order_id)
);
CREATE TABLE first_purchase_refunds (
    refund_id VARCHAR COLLATE C NOT NULL PRIMARY KEY,
    synthetic_user_id VARCHAR COLLATE C NOT NULL,
    order_id VARCHAR COLLATE C NOT NULL,
    refunded_at TIMESTAMP NOT NULL,
    refund_minor BIGINT NOT NULL,
    FOREIGN KEY (synthetic_user_id, order_id)
        REFERENCES first_purchase_orders(synthetic_user_id, order_id)
);
CREATE TABLE first_purchase_sku_map (
    sample_product_id VARCHAR COLLATE C NOT NULL PRIMARY KEY,
    full_product_id VARCHAR COLLATE C NOT NULL,
    mapping_version VARCHAR COLLATE C NOT NULL
);
"""


def _private_directory(value) -> Path:
    original = Path(value)
    if original.is_symlink():
        raise ValueError("directory cannot be a symlink")
    path = original.resolve(strict=True)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("directory must be private and owned")
    return path


def _write_config():
    return {
        "memory_limit": f"{DUCKDB_MEMORY_MIB}MiB",
        "threads": DUCKDB_THREADS,
        "default_collation": "C",
        "enable_external_access": False,
        "autoload_known_extensions": False,
        "autoinstall_known_extensions": False,
        "allow_community_extensions": False,
        "allow_persistent_secrets": False,
    }


def _read_config(temp_directory: Path):
    return {
        "memory_limit": f"{DUCKDB_MEMORY_MIB}MiB",
        "threads": DUCKDB_THREADS,
        "temp_directory": str(temp_directory),
        "max_temp_directory_size": f"{DUCKDB_TEMP_MIB}MiB",
        "default_collation": "C",
        "autoload_known_extensions": False,
        "autoinstall_known_extensions": False,
        "allow_community_extensions": False,
        "allow_persistent_secrets": False,
    }


def _file_sha256(path: Path) -> str:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as source:
        info = os.fstat(source.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1
                or info.st_mode & 0o077 or info.st_size > MAX_DATABASE_BYTES):
            raise ValueError("database file is not a small owned private regular file")
        data = source.read(MAX_DATABASE_BYTES + 1)
        if len(data) > MAX_DATABASE_BYTES:
            raise ValueError("database exceeds its bound")
        return hashlib.sha256(data).hexdigest()


def _require_readonly(connection) -> None:
    settings = dict(connection.execute(
        "SELECT name, value FROM duckdb_settings() WHERE name IN (?, ?, ?, ?)",
        ["access_mode", "enable_external_access", "lock_configuration", "default_collation"],
    ).fetchall())
    if str(settings.get("access_mode", "")).lower() != "read_only":
        raise ValueError("first-purchase query requires read_only access_mode")
    if str(settings.get("enable_external_access", "")).lower() != "false":
        raise ValueError("first-purchase query requires enable_external_access=false")
    if str(settings.get("lock_configuration", "")).lower() != "true":
        raise ValueError("first-purchase query requires lock_configuration=true")
    collation = str(settings.get("default_collation", "")).lower()
    if collation not in ("", "c"):
        raise ValueError("first-purchase query requires binary C collation")


@dataclass(frozen=True)
class FirstPurchaseFixture:
    directory: str
    database_sha256: str

    def database_path(self) -> Path:
        return _private_directory(self.directory) / DATABASE_NAME

    def physical_sha256(self) -> str:
        return _file_sha256(self.database_path())


def materialize_first_purchase_fixture(directory, snapshot) -> FirstPurchaseFixture:
    import duckdb

    parsed = validate_first_purchase_snapshot(snapshot)
    root = _private_directory(directory)
    if any(root.iterdir()):
        raise ValueError("fixture creation requires an empty directory")
    database = root / DATABASE_NAME
    connection = duckdb.connect(str(database), config=_write_config())
    try:
        connection.execute("SET default_collation = 'C'")
        connection.execute(_CREATE_SQL)
        connection.executemany(
            "INSERT INTO first_purchase_orders VALUES (?, ?, ?, ?, ?, ?)",
            [
                (user_id, order_id, utc_naive_instant(paid_at), channel, gross, status)
                for user_id, order_id, paid_at, channel, gross, status in parsed["orders"]
            ],
        )
        if parsed["lines"]:
            connection.executemany(
                "INSERT INTO first_purchase_lines VALUES (?, ?, ?, ?, ?)",
                parsed["lines"],
            )
        if parsed["refunds"]:
            connection.executemany(
                "INSERT INTO first_purchase_refunds VALUES (?, ?, ?, ?, ?)",
                [
                    (refund_id, user_id, order_id, utc_naive_instant(refunded_at), amount)
                    for refund_id, user_id, order_id, refunded_at, amount in parsed["refunds"]
                ],
            )
        connection.executemany(
            "INSERT INTO first_purchase_sku_map VALUES (?, ?, ?)",
            [(sample, full, parsed["mapping_version"]) for sample, full in parsed["pairs"]],
        )
        connection.execute("CHECKPOINT")
    finally:
        connection.close()
    database.chmod(0o600)
    return FirstPurchaseFixture(str(root), _file_sha256(database))


def connect_first_purchase_readonly(fixture: FirstPurchaseFixture, temp_directory):
    import duckdb

    database = fixture.database_path()
    if fixture.physical_sha256() != fixture.database_sha256:
        raise ValueError("first-purchase database hash changed")
    temp = _private_directory(temp_directory)
    connection = duckdb.connect(str(database), read_only=True, config=_read_config(temp))
    try:
        connection.execute("SET default_collation = 'C'")
        connection.execute("SET max_temp_directory_size = ?", [f"{DUCKDB_TEMP_MIB}MiB"])
        connection.execute("SET enable_external_access=false")
        connection.execute("SET lock_configuration=true")
    except Exception:
        connection.close()
        raise
    return connection


def execute_first_purchase_path(
    *,
    request: dict,
    snapshot: dict,
    permission_scope: str,
    fixture_directory,
    temp_directory,
) -> dict:
    """Deterministic offline compute. Does not call require_supported_query."""
    resolved = resolve_first_purchase(request, snapshot, permission_scope)
    fixture = materialize_first_purchase_fixture(fixture_directory, snapshot)
    before = fixture.physical_sha256()
    connection = connect_first_purchase_readonly(fixture, temp_directory)
    try:
        _require_readonly(connection)
        product_rows = connection.execute(
            FIRST_PURCHASE_PATH_SQL, first_purchase_path_parameters(resolved)
        ).fetchall()
        cohort_row = connection.execute(
            COHORT_COUNT_SQL, first_purchase_cohort_parameters(resolved)
        ).fetchone()
    finally:
        connection.close()
    after = fixture.physical_sha256()
    if after != before:
        raise ValueError("first-purchase database hash changed during query")
    if cohort_row is None:
        raise ValueError("cohort count query returned no row")
    enrolled, mature, immature = (int(cohort_row[0]), int(cohort_row[1]), int(cohort_row[2]))
    products = []
    seen = set()
    for row in product_rows:
        product_id, product_mature, product_immature, subsequent, converted = row
        if type(product_id) is not str:
            raise ValueError("product_id must remain a string")
        if product_id in seen:
            raise ValueError("duplicate product_id in query result")
        seen.add(product_id)
        products.append(
            product_metric_row(
                product_id,
                int(product_mature),
                int(product_immature),
                int(subsequent),
                int(converted),
            )
        )
    if resolved.product_ids:
        by_id = {row["product_id"]: row for row in products}
        products = [
            by_id.get(product_id, product_metric_row(product_id, 0, 0, 0, 0))
            for product_id in resolved.product_ids
        ]
    return {
        "schema_version": QUERY_SCHEMA,
        "answer_mode": "DETERMINISTIC_TOOL",
        "query_id": QUERY_ID,
        "query_version": QUERY_VERSION,
        "metric_id": METRIC_ID,
        "metric_version": METRIC_VERSION,
        "data_version": DATA_VERSION,
        "hash_version": HASH_VERSION,
        "contains_real_data": False,
        "data_source": "SYNTHETIC_SNAPSHOT",
        "data_snapshot_ref": request["data_snapshot_ref"],
        "as_of": snapshot["as_of"],
        "resolved_filters": resolved.as_dict(),
        "filter_hash": resolved.filter_hash,
        "facts": {
            "display_name": DISPLAY_NAME,
            "currency": CURRENCY,
            "amount_unit": AMOUNT_UNIT,
            "amount_precision": AMOUNT_PRECISION,
            "observation_days": resolved.observation_days,
            "mapping_version": resolved.mapping_version,
            "cohort_enrolled_count": enrolled,
            "cohort_mature_count": mature,
            "cohort_immature_count": immature,
            "products": products,
        },
        "limitations": list(LIMITATIONS),
        "database_sha256": after,
    }
