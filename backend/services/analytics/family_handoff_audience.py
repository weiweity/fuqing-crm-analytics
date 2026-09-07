"""Offline candidate handoff-audience compute. No HTTP, worker, or catalog success path."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from backend.semantic.analytics_handoff_audience import (
    AMOUNT_PRECISION,
    AMOUNT_UNIT,
    AUDIENCE_KIND,
    CURRENCY,
    DATA_VERSION,
    DISPLAY_NAME,
    EXCLUDE_MIN_VALID_ORDERS,
    EXPORT_STATUS,
    HANDOFF_AUDIENCE_SQL,
    HASH_VERSION,
    LIMITATIONS,
    QUERY_ID,
    QUERY_SCHEMA,
    QUERY_VERSION,
    RULE_VERSION,
    audience_digest,
    handoff_audience_parameters,
    resolve_handoff,
    utc_naive_instant,
    validate_handoff_snapshot,
)

DATABASE_NAME = "handoff-audience.duckdb"
MAX_DATABASE_BYTES = 4 * 1024 * 1024
DUCKDB_MEMORY_MIB = 32
DUCKDB_THREADS = 2
DUCKDB_TEMP_MIB = 32

_CREATE_SQL = """
CREATE TABLE handoff_orders (
    synthetic_user_id VARCHAR COLLATE C NOT NULL,
    order_id VARCHAR COLLATE C NOT NULL,
    paid_at TIMESTAMP NOT NULL,
    channel VARCHAR COLLATE C NOT NULL,
    gross_paid_minor BIGINT NOT NULL,
    status VARCHAR COLLATE C NOT NULL,
    PRIMARY KEY (synthetic_user_id, order_id)
);
CREATE TABLE handoff_lines (
    line_id VARCHAR COLLATE C NOT NULL PRIMARY KEY,
    synthetic_user_id VARCHAR COLLATE C NOT NULL,
    order_id VARCHAR COLLATE C NOT NULL,
    product_id VARCHAR COLLATE C NOT NULL,
    quantity BIGINT NOT NULL,
    FOREIGN KEY (synthetic_user_id, order_id)
        REFERENCES handoff_orders(synthetic_user_id, order_id)
);
CREATE TABLE handoff_refunds (
    refund_id VARCHAR COLLATE C NOT NULL PRIMARY KEY,
    synthetic_user_id VARCHAR COLLATE C NOT NULL,
    order_id VARCHAR COLLATE C NOT NULL,
    refunded_at TIMESTAMP NOT NULL,
    refund_minor BIGINT NOT NULL,
    FOREIGN KEY (synthetic_user_id, order_id)
        REFERENCES handoff_orders(synthetic_user_id, order_id)
);
CREATE TABLE handoff_sku_map (
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
        raise ValueError("handoff query requires read_only access_mode")
    if str(settings.get("enable_external_access", "")).lower() != "false":
        raise ValueError("handoff query requires enable_external_access=false")
    if str(settings.get("lock_configuration", "")).lower() != "true":
        raise ValueError("handoff query requires lock_configuration=true")
    collation = str(settings.get("default_collation", "")).lower()
    if collation not in ("", "c"):
        raise ValueError("handoff query requires binary C collation")


@dataclass(frozen=True)
class HandoffFixture:
    directory: str
    database_sha256: str

    def database_path(self) -> Path:
        return _private_directory(self.directory) / DATABASE_NAME

    def physical_sha256(self) -> str:
        return _file_sha256(self.database_path())


def materialize_handoff_fixture(directory, snapshot) -> HandoffFixture:
    import duckdb

    parsed = validate_handoff_snapshot(snapshot)
    root = _private_directory(directory)
    if any(root.iterdir()):
        raise ValueError("fixture creation requires an empty directory")
    database = root / DATABASE_NAME
    connection = duckdb.connect(str(database), config=_write_config())
    try:
        connection.execute("SET default_collation = 'C'")
        connection.execute(_CREATE_SQL)
        connection.executemany(
            "INSERT INTO handoff_orders VALUES (?, ?, ?, ?, ?, ?)",
            [
                (user_id, order_id, utc_naive_instant(paid_at), channel, gross, status)
                for user_id, order_id, paid_at, channel, gross, status in parsed["orders"]
            ],
        )
        if parsed["lines"]:
            connection.executemany(
                "INSERT INTO handoff_lines VALUES (?, ?, ?, ?, ?)",
                parsed["lines"],
            )
        if parsed["refunds"]:
            connection.executemany(
                "INSERT INTO handoff_refunds VALUES (?, ?, ?, ?, ?)",
                [
                    (refund_id, user_id, order_id, utc_naive_instant(refunded_at), amount)
                    for refund_id, user_id, order_id, refunded_at, amount in parsed["refunds"]
                ],
            )
        connection.executemany(
            "INSERT INTO handoff_sku_map VALUES (?, ?, ?)",
            [(sample, full, parsed["mapping_version"]) for sample, full in parsed["pairs"]],
        )
        connection.execute("CHECKPOINT")
    finally:
        connection.close()
    database.chmod(0o600)
    return HandoffFixture(str(root), _file_sha256(database))


def connect_handoff_readonly(fixture: HandoffFixture, temp_directory):
    import duckdb

    database = fixture.database_path()
    if fixture.physical_sha256() != fixture.database_sha256:
        raise ValueError("handoff database hash changed")
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


def execute_handoff_audience(
    *,
    request: dict,
    snapshot: dict,
    permission_scope: str,
    fixture_directory,
    temp_directory,
) -> dict:
    """Deterministic offline compute. Does not call require_supported_query."""
    resolved = resolve_handoff(request, snapshot, permission_scope)
    fixture = materialize_handoff_fixture(fixture_directory, snapshot)
    before = fixture.physical_sha256()
    connection = connect_handoff_readonly(fixture, temp_directory)
    try:
        _require_readonly(connection)
        rows = connection.execute(
            HANDOFF_AUDIENCE_SQL, handoff_audience_parameters(resolved)
        ).fetchall()
    finally:
        connection.close()
    after = fixture.physical_sha256()
    if after != before:
        raise ValueError("handoff database hash changed during query")
    members = []
    seen = set()
    for row in rows:
        user_id = row[0]
        if type(user_id) is not str:
            raise ValueError("synthetic_user_id must remain a string")
        if user_id in seen:
            raise ValueError("duplicate synthetic_user_id in audience")
        seen.add(user_id)
        members.append(user_id)
    digest = audience_digest(members, resolved.rule_version)
    facts = {
        "display_name": DISPLAY_NAME,
        "currency": CURRENCY,
        "amount_unit": AMOUNT_UNIT,
        "amount_precision": AMOUNT_PRECISION,
        "observation_days": resolved.observation_days,
        "mapping_version": resolved.mapping_version,
        "rule_version": resolved.rule_version,
        "first_channel": resolved.first_channel,
        "sample_product_id": resolved.sample_product_id,
        "full_product_id": resolved.full_product_id,
        "exclude_min_valid_orders_in_window": EXCLUDE_MIN_VALID_ORDERS,
        "source_result_ref": resolved.source_result_ref,
        "audience_kind": AUDIENCE_KIND,
        "export_status": EXPORT_STATUS,
        "marketing_sent": False,
        "cohort_count": len(members),
        "cohort_digest": digest,
    }
    dumped = str(facts)
    if "members" in facts or "synthetic_user_ids" in facts:
        raise ValueError("audience facts must not include member lists")
    if any(user_id in dumped for user_id in members):
        raise ValueError("audience facts must not embed member identifiers")
    return {
        "schema_version": QUERY_SCHEMA,
        "answer_mode": "DETERMINISTIC_TOOL",
        "query_id": QUERY_ID,
        "query_version": QUERY_VERSION,
        "data_version": DATA_VERSION,
        "hash_version": HASH_VERSION,
        "rule_version": RULE_VERSION,
        "contains_real_data": False,
        "data_source": "SYNTHETIC_SNAPSHOT",
        "data_snapshot_ref": request["data_snapshot_ref"],
        "as_of": snapshot["as_of"],
        "resolved_filters": resolved.as_dict(),
        "filter_hash": resolved.filter_hash,
        "facts": facts,
        "limitations": list(LIMITATIONS),
        "database_sha256": after,
    }
