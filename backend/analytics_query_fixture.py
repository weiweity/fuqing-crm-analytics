"""Sealed synthetic channel-follow-up DuckDB snapshot. Never a path fallback.

Creation is a separate setup action into an owned empty private directory.
validate() only checks bounded files and hashes; it does not open DuckDB.
Schema and content checks run on a caller-held restricted connection.

Timestamps are stored as UTC-naive TIMESTAMP instants so this isolated engine
does not SET TimeZone (ICU cannot autoload). Logical snapshot_digest is
independent of the physical DuckDB file hash.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from backend.analytics_fixture import MAX_DATABASE_BYTES, bounded_bytes, private_directory
from backend.contracts.analytics_query import (
    DATA_VERSION,
    QUERY_SCHEMA,
    SNAPSHOT_ID,
    ChannelFollowupSnapshot,
    canonical_rfc3339,
    parse_query_datetime,
    revalidate_model,
    snapshot_digest,
)
from backend.semantic.analytics_channel_followup import utc_naive_instant

DATABASE_NAME = "channel-followup.duckdb"
MANIFEST_NAME = "manifest.json"
DATA_SOURCE = "SYNTHETIC_SNAPSHOT"
MAX_MANIFEST_BYTES = 8192
MAX_SNAPSHOT_JSON_BYTES = 512 * 1024
MAX_ORDERS = 1000
MAX_LINES = 3000
MAX_REFUNDS = 1000
QUERY_DUCKDB_MEMORY_MIB = 32
QUERY_DUCKDB_THREADS = 2
QUERY_TEMP_MIB = 32

ORDERS_TABLE = "channel_followup_orders"
LINES_TABLE = "channel_followup_lines"
REFUNDS_TABLE = "channel_followup_refunds"
META_TABLE = "channel_followup_snapshot_meta"

EXPECTED_TABLES = (META_TABLE, ORDERS_TABLE, LINES_TABLE, REFUNDS_TABLE)
EXPECTED_COLUMNS = {
    META_TABLE: {
        "snapshot_id": "VARCHAR",
        "data_version": "VARCHAR",
        "schema_version": "VARCHAR",
        "as_of": "TIMESTAMP",
        "timezone": "VARCHAR",
        "currency": "VARCHAR",
        "amount_unit": "VARCHAR",
        "amount_precision": "VARCHAR",
        "scope": "VARCHAR",
        "contains_real_data": "BOOLEAN",
        "data_digest": "VARCHAR",
    },
    ORDERS_TABLE: {
        "synthetic_user_id": "VARCHAR",
        "order_id": "VARCHAR",
        "paid_at": "TIMESTAMP",
        "channel": "VARCHAR",
        "gross_paid_minor": "BIGINT",
        "status": "VARCHAR",
    },
    LINES_TABLE: {
        "line_id": "VARCHAR",
        "synthetic_user_id": "VARCHAR",
        "order_id": "VARCHAR",
        "product_id": "VARCHAR",
        "quantity": "BIGINT",
    },
    REFUNDS_TABLE: {
        "refund_id": "VARCHAR",
        "synthetic_user_id": "VARCHAR",
        "order_id": "VARCHAR",
        "refunded_at": "TIMESTAMP",
        "refund_minor": "BIGINT",
    },
}
EXPECTED_PRIMARY_KEYS = {
    META_TABLE: ["snapshot_id"],
    ORDERS_TABLE: ["synthetic_user_id", "order_id"],
    LINES_TABLE: ["line_id"],
    REFUNDS_TABLE: ["refund_id"],
}
EXPECTED_FOREIGN_KEYS = {
    LINES_TABLE: (["synthetic_user_id", "order_id"], ORDERS_TABLE, ["synthetic_user_id", "order_id"]),
    REFUNDS_TABLE: (["synthetic_user_id", "order_id"], ORDERS_TABLE, ["synthetic_user_id", "order_id"]),
}

_CREATE_SQL = f"""
CREATE TABLE {ORDERS_TABLE} (
    synthetic_user_id VARCHAR COLLATE C NOT NULL,
    order_id VARCHAR COLLATE C NOT NULL,
    paid_at TIMESTAMP NOT NULL,
    channel VARCHAR COLLATE C NOT NULL,
    gross_paid_minor BIGINT NOT NULL,
    status VARCHAR COLLATE C NOT NULL,
    PRIMARY KEY (synthetic_user_id, order_id)
);
CREATE TABLE {LINES_TABLE} (
    line_id VARCHAR COLLATE C NOT NULL PRIMARY KEY,
    synthetic_user_id VARCHAR COLLATE C NOT NULL,
    order_id VARCHAR COLLATE C NOT NULL,
    product_id VARCHAR COLLATE C NOT NULL,
    quantity BIGINT NOT NULL,
    FOREIGN KEY (synthetic_user_id, order_id)
        REFERENCES {ORDERS_TABLE}(synthetic_user_id, order_id)
);
CREATE TABLE {REFUNDS_TABLE} (
    refund_id VARCHAR COLLATE C NOT NULL PRIMARY KEY,
    synthetic_user_id VARCHAR COLLATE C NOT NULL,
    order_id VARCHAR COLLATE C NOT NULL,
    refunded_at TIMESTAMP NOT NULL,
    refund_minor BIGINT NOT NULL,
    FOREIGN KEY (synthetic_user_id, order_id)
        REFERENCES {ORDERS_TABLE}(synthetic_user_id, order_id)
);
CREATE TABLE {META_TABLE} (
    snapshot_id VARCHAR COLLATE C NOT NULL PRIMARY KEY,
    data_version VARCHAR COLLATE C NOT NULL,
    schema_version VARCHAR COLLATE C NOT NULL,
    as_of TIMESTAMP NOT NULL,
    timezone VARCHAR COLLATE C NOT NULL,
    currency VARCHAR COLLATE C NOT NULL,
    amount_unit VARCHAR COLLATE C NOT NULL,
    amount_precision VARCHAR COLLATE C NOT NULL,
    scope VARCHAR COLLATE C NOT NULL,
    contains_real_data BOOLEAN NOT NULL,
    data_digest VARCHAR COLLATE C NOT NULL
);
"""


def _write_config():
    return {
        "memory_limit": f"{QUERY_DUCKDB_MEMORY_MIB}MiB",
        "threads": QUERY_DUCKDB_THREADS,
        "default_collation": "C",
        "enable_external_access": False,
        "autoload_known_extensions": False,
        "autoinstall_known_extensions": False,
        "allow_community_extensions": False,
        "allow_persistent_secrets": False,
    }


def _read_config(temp_directory: Path, *, memory_mib: int, threads: int, temp_mib: int):
    return {
        "memory_limit": f"{memory_mib}MiB",
        "threads": threads,
        "temp_directory": str(temp_directory),
        "max_temp_directory_size": f"{temp_mib}MiB",
        "default_collation": "C",
        "autoload_known_extensions": False,
        "autoinstall_known_extensions": False,
        "allow_community_extensions": False,
        "allow_persistent_secrets": False,
    }


def _sha256_hex(value: object) -> bool:
    return type(value) is str and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def aware_utc_instant(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError("snapshot timestamps must be datetime values")
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _reject_over_caps(snapshot: ChannelFollowupSnapshot) -> None:
    if len(snapshot.orders) > MAX_ORDERS or len(snapshot.lines) > MAX_LINES or len(snapshot.refunds) > MAX_REFUNDS:
        raise ValueError("synthetic channel-follow-up snapshot exceeds its row caps")
    encoded = snapshot.model_dump_json().encode()
    if len(encoded) > MAX_SNAPSHOT_JSON_BYTES:
        raise ValueError("synthetic channel-follow-up snapshot exceeds its JSON size cap")


def _manifest_bytes(manifest: dict) -> bytes:
    return (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()


@dataclass(frozen=True)
class ChannelFollowupFixture:
    directory: str
    manifest_sha256: str

    def validate(self):
        """Bounded file and hash checks only. Does not open an analysis connection."""
        root = private_directory(self.directory)
        raw = bounded_bytes(root / MANIFEST_NAME, MAX_MANIFEST_BYTES)
        if hashlib.sha256(raw).hexdigest() != self.manifest_sha256:
            raise ValueError("channel-follow-up manifest changed")
        manifest = json.loads(raw)
        expected = {
            "schema_version": QUERY_SCHEMA,
            "snapshot_id": SNAPSHOT_ID,
            "data_version": DATA_VERSION,
            "fixture_id": SNAPSHOT_ID,
            "contains_real_data": False,
            "data_source": DATA_SOURCE,
            "database": DATABASE_NAME,
            "timezone": "Asia/Shanghai",
        }
        if (not isinstance(manifest, dict)
                or set(manifest) != {*expected, "data_digest", "database_sha256", "as_of", "orders", "lines", "refunds"}
                or {key: manifest[key] for key in expected} != expected
                or manifest.get("contains_real_data") is not False
                or type(manifest.get("orders")) is not int
                or type(manifest.get("lines")) is not int
                or type(manifest.get("refunds")) is not int
                or manifest["orders"] > MAX_ORDERS
                or manifest["lines"] > MAX_LINES
                or manifest["refunds"] > MAX_REFUNDS
                or manifest["orders"] < 0 or manifest["lines"] < 0 or manifest["refunds"] < 0):
            raise ValueError("channel-follow-up synthetic manifest is invalid")
        digest = manifest.get("data_digest")
        if not _sha256_hex(digest) or not _sha256_hex(manifest.get("database_sha256")):
            raise ValueError("channel-follow-up data digest is invalid")
        as_of = manifest.get("as_of")
        if type(as_of) is not str:
            raise ValueError("channel-follow-up manifest as_of is invalid")
        try:
            parsed_as_of = parse_query_datetime(as_of)
        except ValueError as exc:
            raise ValueError("channel-follow-up manifest as_of is invalid") from exc
        if canonical_rfc3339(parsed_as_of) != as_of:
            raise ValueError("channel-follow-up manifest as_of is invalid")
        database = root / DATABASE_NAME
        physical = hashlib.sha256(bounded_bytes(database, MAX_DATABASE_BYTES)).hexdigest()
        if physical != manifest.get("database_sha256"):
            raise ValueError("channel-follow-up database checksum is invalid")
        return database

    def physical_sha256(self) -> str:
        database = self.validate()
        return hashlib.sha256(bounded_bytes(database, MAX_DATABASE_BYTES)).hexdigest()

    def manifest(self) -> dict:
        root = private_directory(self.directory)
        return json.loads(bounded_bytes(root / MANIFEST_NAME, MAX_MANIFEST_BYTES))

    def binding_descriptor(self) -> dict:
        """Sealed identity only. Does not open DuckDB or copy snapshot rows."""
        self.validate()
        manifest = self.manifest()
        return {
            "snapshot_id": manifest["snapshot_id"],
            "data_version": manifest["data_version"],
            "data_digest": manifest["data_digest"],
            "as_of": manifest["as_of"],
            "timezone": manifest["timezone"],
            "physical_sha256": manifest["database_sha256"],
        }


def create_channel_followup_fixture(directory, snapshot) -> ChannelFollowupFixture:
    """Create only in an explicit, empty private fixture directory; no overwrite."""
    import duckdb

    snapshot = revalidate_model(ChannelFollowupSnapshot, snapshot)
    _reject_over_caps(snapshot)
    digest = snapshot_digest(snapshot)
    root = private_directory(directory)
    if any(root.iterdir()):
        raise ValueError("fixture creation requires an empty directory")
    database = root / DATABASE_NAME
    con = duckdb.connect(str(database), config=_write_config())
    try:
        con.execute("SET default_collation = 'C'")
        con.execute(_CREATE_SQL)
        order_rows = [
            (order.synthetic_user_id, order.order_id, utc_naive_instant(order.paid_at),
             order.channel, order.gross_paid_minor, order.status)
            for order in snapshot.orders
        ]
        if order_rows:
            con.executemany(f"INSERT INTO {ORDERS_TABLE} VALUES (?, ?, ?, ?, ?, ?)", order_rows)
        line_rows = [
            (line.line_id, line.synthetic_user_id, line.order_id, line.product_id, line.quantity)
            for line in snapshot.lines
        ]
        if line_rows:
            con.executemany(f"INSERT INTO {LINES_TABLE} VALUES (?, ?, ?, ?, ?)", line_rows)
        refund_rows = [
            (refund.refund_id, refund.synthetic_user_id, refund.order_id,
             utc_naive_instant(refund.refunded_at), refund.refund_minor)
            for refund in snapshot.refunds
        ]
        if refund_rows:
            con.executemany(f"INSERT INTO {REFUNDS_TABLE} VALUES (?, ?, ?, ?, ?)", refund_rows)
        con.execute(
            f"INSERT INTO {META_TABLE} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                snapshot.snapshot_id, snapshot.data_version, snapshot.schema_version,
                utc_naive_instant(snapshot.as_of), snapshot.timezone, snapshot.currency,
                snapshot.amount_unit, snapshot.amount_precision, snapshot.scope,
                snapshot.contains_real_data, digest,
            ],
        )
        con.execute("CHECKPOINT")
    finally:
        con.close()
    database.chmod(0o600)
    manifest = {
        "schema_version": QUERY_SCHEMA,
        "snapshot_id": SNAPSHOT_ID,
        "data_version": DATA_VERSION,
        "fixture_id": SNAPSHOT_ID,
        "contains_real_data": False,
        "data_source": DATA_SOURCE,
        "database": DATABASE_NAME,
        "timezone": snapshot.timezone,
        "as_of": canonical_rfc3339(snapshot.as_of),
        "data_digest": digest,
        "orders": len(snapshot.orders),
        "lines": len(snapshot.lines),
        "refunds": len(snapshot.refunds),
        "database_sha256": hashlib.sha256(bounded_bytes(database, MAX_DATABASE_BYTES)).hexdigest(),
    }
    raw = _manifest_bytes(manifest)
    fd = os.open(root / MANIFEST_NAME, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as target:
        target.write(raw)
        target.flush()
        os.fsync(target.fileno())
    result = ChannelFollowupFixture(str(root), hashlib.sha256(raw).hexdigest())
    result.validate()
    return result


def connect_channel_followup_readonly(
    fixture: ChannelFollowupFixture,
    temp_directory,
    *,
    memory_mib: int = QUERY_DUCKDB_MEMORY_MIB,
    threads: int = QUERY_DUCKDB_THREADS,
    temp_mib: int = QUERY_TEMP_MIB,
):
    """Open a restricted read-only connection. Caller owns close().

    Isolated offline compute only. This is not the legacy Web DuckDB singleton
    and does not relax backend/service Web singleton rules.
    """
    import duckdb

    if memory_mib > QUERY_DUCKDB_MEMORY_MIB or threads > QUERY_DUCKDB_THREADS or temp_mib > QUERY_TEMP_MIB:
        raise ValueError("channel-follow-up connection caps cannot be raised by the caller")
    database = fixture.validate()
    temp = private_directory(temp_directory)
    con = duckdb.connect(str(database), read_only=True, config=_read_config(temp, memory_mib=memory_mib,
                                                                           threads=threads, temp_mib=temp_mib))
    try:
        con.execute("SET default_collation = 'C'")
        con.execute("SET max_temp_directory_size = ?", [f"{temp_mib}MiB"])
        con.execute("SET enable_external_access=false")
        con.execute("SET lock_configuration=true")
    except Exception:
        con.close()
        raise
    return con


def require_restricted_connection(connection) -> None:
    settings = dict(connection.execute(
        "SELECT name, value FROM duckdb_settings() WHERE name IN (?, ?, ?, ?)",
        ["access_mode", "enable_external_access", "lock_configuration", "default_collation"],
    ).fetchall())
    if str(settings.get("access_mode", "")).lower() != "read_only":
        raise ValueError("channel follow-up query requires read_only access_mode")
    if str(settings.get("enable_external_access", "")).lower() != "false":
        raise ValueError("channel follow-up query requires enable_external_access=false")
    if str(settings.get("lock_configuration", "")).lower() != "true":
        raise ValueError("channel follow-up query requires lock_configuration=true")
    collation = str(settings.get("default_collation", "")).lower()
    if collation not in ("", "c"):
        raise ValueError("channel follow-up query requires binary C collation")


def _current_database(connection) -> str:
    row = connection.execute("SELECT current_database()").fetchone()
    if row is None or type(row[0]) is not str or not row[0]:
        raise ValueError("channel-follow-up snapshot catalog is missing")
    return row[0]


def _fetch_capped(connection, sql: str, cap: int):
    if cap < 0:
        raise ValueError("invalid fetch cap")
    rows = connection.execute(f"{sql} LIMIT ?", [cap + 1]).fetchall()
    if len(rows) > cap:
        raise ValueError("channel-follow-up snapshot exceeds its row caps")
    return rows


def _assert_schema(connection) -> None:
    database = _current_database(connection)
    user_databases = [
        row[0]
        for row in connection.execute(
            "SELECT database_name FROM duckdb_databases() WHERE NOT internal"
        ).fetchall()
    ]
    if user_databases != [database]:
        raise ValueError("channel-follow-up snapshot catalog is not the sealed database")
    extra_schemas = connection.execute(
        "SELECT database_name, schema_name FROM duckdb_schemas() WHERE NOT internal"
    ).fetchall()
    if extra_schemas:
        raise ValueError("channel-follow-up snapshot contains unregistered schemas")
    tables = connection.execute(
        "SELECT database_name, schema_name, table_name FROM duckdb_tables() "
        "WHERE NOT internal AND NOT temporary"
    ).fetchall()
    if len(tables) != len(set(tables)):
        raise ValueError("channel-follow-up snapshot table catalog is ambiguous")
    expected_tables = {(database, "main", name) for name in EXPECTED_TABLES}
    if set(tables) != expected_tables:
        raise ValueError("channel-follow-up snapshot tables do not match the sealed schema")
    views = connection.execute(
        "SELECT database_name, schema_name, view_name FROM duckdb_views() "
        "WHERE NOT internal AND NOT temporary"
    ).fetchall()
    if views:
        raise ValueError("channel-follow-up snapshot contains unregistered views")
    create_sql = connection.execute(
        "SELECT table_name, sql FROM duckdb_tables() "
        "WHERE NOT internal AND NOT temporary AND database_name = current_database() "
        "AND schema_name = 'main'"
    ).fetchall()
    if {row[0] for row in create_sql} != set(EXPECTED_TABLES):
        raise ValueError("channel-follow-up snapshot tables do not match the sealed schema")
    for table, sql in create_sql:
        text = (sql or "").upper()
        if "NOCASE" in text.replace(" ", ""):
            raise ValueError("channel-follow-up snapshot collation is not binary C")
        if table in EXPECTED_COLUMNS and "COLLATE C" not in text:
            raise ValueError("channel-follow-up snapshot collation is not binary C")
    columns = connection.execute(
        "SELECT database_name, schema_name, table_name, column_name, data_type "
        "FROM duckdb_columns() WHERE NOT internal "
        "ORDER BY database_name, schema_name, table_name, column_index"
    ).fetchall()
    actual: dict[str, dict[str, str]] = {}
    for catalog, schema, table, column, data_type in columns:
        if (catalog, schema, table) not in expected_tables:
            raise ValueError("channel-follow-up snapshot columns do not match the sealed schema")
        actual.setdefault(table, {})[column] = data_type
    if actual != EXPECTED_COLUMNS:
        raise ValueError("channel-follow-up snapshot columns do not match the sealed schema")
    primary = {
        row[0]: list(row[1])
        for row in connection.execute(
            "SELECT table_name, constraint_column_names FROM duckdb_constraints() "
            "WHERE database_name = current_database() AND schema_name = 'main' "
            "AND constraint_type = 'PRIMARY KEY'"
        ).fetchall()
    }
    if primary != EXPECTED_PRIMARY_KEYS:
        raise ValueError("channel-follow-up snapshot keys do not match the sealed schema")
    foreign = {
        row[0]: (list(row[1]), row[2], list(row[3]))
        for row in connection.execute(
            "SELECT table_name, constraint_column_names, referenced_table, referenced_column_names "
            "FROM duckdb_constraints() WHERE database_name = current_database() "
            "AND schema_name = 'main' AND constraint_type = 'FOREIGN KEY'"
        ).fetchall()
    }
    if foreign != EXPECTED_FOREIGN_KEYS:
        raise ValueError("channel-follow-up snapshot foreign keys do not match the sealed schema")


def load_snapshot_from_connection(connection) -> ChannelFollowupSnapshot:
    meta_rows = _fetch_capped(
        connection,
        f"SELECT snapshot_id, data_version, schema_version, as_of, timezone, currency, "
        f"amount_unit, amount_precision, scope, contains_real_data, data_digest "
        f"FROM main.{META_TABLE}",
        1,
    )
    if len(meta_rows) != 1:
        raise ValueError("channel-follow-up snapshot metadata must be a single row")
    meta = meta_rows[0]
    orders = _fetch_capped(
        connection,
        f"SELECT order_id, synthetic_user_id, paid_at, channel, gross_paid_minor, status "
        f"FROM main.{ORDERS_TABLE}",
        MAX_ORDERS,
    )
    lines = _fetch_capped(
        connection,
        f"SELECT line_id, order_id, synthetic_user_id, product_id, quantity "
        f"FROM main.{LINES_TABLE}",
        MAX_LINES,
    )
    refunds = _fetch_capped(
        connection,
        f"SELECT refund_id, order_id, synthetic_user_id, refunded_at, refund_minor "
        f"FROM main.{REFUNDS_TABLE}",
        MAX_REFUNDS,
    )
    payload = {
        "schema_version": meta[2],
        "snapshot_id": meta[0],
        "data_version": meta[1],
        "as_of": aware_utc_instant(meta[3]),
        "timezone": meta[4],
        "currency": meta[5],
        "amount_unit": meta[6],
        "amount_precision": meta[7],
        "scope": meta[8],
        "contains_real_data": meta[9],
        "orders": [
            {
                "order_id": row[0],
                "synthetic_user_id": row[1],
                "paid_at": aware_utc_instant(row[2]),
                "channel": row[3],
                "gross_paid_minor": int(row[4]),
                "status": row[5],
            }
            for row in orders
        ],
        "lines": [
            {
                "line_id": row[0],
                "order_id": row[1],
                "synthetic_user_id": row[2],
                "product_id": row[3],
                "quantity": int(row[4]),
            }
            for row in lines
        ],
        "refunds": [
            {
                "refund_id": row[0],
                "order_id": row[1],
                "synthetic_user_id": row[2],
                "refunded_at": aware_utc_instant(row[3]),
                "refund_minor": int(row[4]),
            }
            for row in refunds
        ],
    }
    snapshot = ChannelFollowupSnapshot.model_validate(payload)
    _reject_over_caps(snapshot)
    digest = snapshot_digest(snapshot)
    if digest != meta[10]:
        raise ValueError("rebuilt snapshot digest does not match sealed metadata")
    return snapshot


def verify_sealed_content(connection, fixture: ChannelFollowupFixture) -> ChannelFollowupSnapshot:
    """Schema plus content digest on the same restricted connection."""
    require_restricted_connection(connection)
    fixture.validate()
    _assert_schema(connection)
    snapshot = load_snapshot_from_connection(connection)
    sealed = fixture.manifest()
    digest = snapshot_digest(snapshot)
    if digest != sealed["data_digest"]:
        raise ValueError("rebuilt snapshot digest does not match sealed manifest")
    if (
        len(snapshot.orders) != sealed["orders"]
        or len(snapshot.lines) != sealed["lines"]
        or len(snapshot.refunds) != sealed["refunds"]
        or canonical_rfc3339(snapshot.as_of) != sealed["as_of"]
        or snapshot.schema_version != sealed["schema_version"]
        or snapshot.snapshot_id != sealed["snapshot_id"]
        or snapshot.data_version != sealed["data_version"]
        or snapshot.timezone != sealed["timezone"]
        or snapshot.contains_real_data is not False
        or sealed["contains_real_data"] is not False
    ):
        raise ValueError("sealed manifest metadata does not match snapshot contents")
    return snapshot
