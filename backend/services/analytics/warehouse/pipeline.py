"""Synthetic warehouse pipeline: ingest → range join → identity → facts → publish."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from backend.services.analytics.warehouse.contract import (
    AMOUNT_PRECISION,
    AMOUNT_UNIT,
    CURRENCY,
    DATABASE_NAME,
    DATA_SOURCE,
    DEFAULT_AS_OF,
    GENERATOR_VERSION,
    MANIFEST_NAME,
    PIPELINE_VERSION,
    PUBLISHED_MANIFEST_NAME,
    RULE_VERSION,
    SCHEMA_VERSION,
    TIMEZONE,
    WAREHOUSE_DUCKDB_MEMORY_MIB,
    WAREHOUSE_DUCKDB_THREADS,
    WAREHOUSE_TEMP_MIB,
    WarehouseContractError,
    normalize_rules,
    utc_naive_instant,
)
from backend.services.analytics.warehouse.facts import (
    CREATE_SQL,
    STAGING_SQL,
    attach_product_versions,
    count_unconstrained_product_join,
    load_identities,
    load_staging_lines,
    load_staging_orders,
    load_staging_refunds,
    load_staging_versions,
)
from backend.services.analytics.warehouse.incremental import (
    classify_affected_orders,
    count_future_refunds,
    install_rules,
    merge_staging_into_source,
    read_previous_meta,
    rebuild_affected_facts,
)
from backend.services.analytics.warehouse.ingest import (
    assert_read_matches_plan,
    list_matching_sources,
    list_named_sources,
    plan_ingest,
    read_planned_jsonl,
)
from backend.services.analytics.warehouse.generate import content_hash_from_file_hashes
from backend.services.analytics.warehouse.observe import PipelineObservation, StageTimer, process_ru_maxrss_bytes


def _write_config():
    return {
        "memory_limit": f"{WAREHOUSE_DUCKDB_MEMORY_MIB}MiB",
        "threads": WAREHOUSE_DUCKDB_THREADS,
        "default_collation": "C",
        "enable_external_access": False,
        "autoload_known_extensions": False,
        "autoinstall_known_extensions": False,
        "allow_community_extensions": False,
        "allow_persistent_secrets": False,
    }


def _read_config(temp_directory: Path):
    return {
        "memory_limit": f"{WAREHOUSE_DUCKDB_MEMORY_MIB}MiB",
        "threads": WAREHOUSE_DUCKDB_THREADS,
        "temp_directory": str(temp_directory),
        "max_temp_directory_size": f"{WAREHOUSE_TEMP_MIB}MiB",
        "default_collation": "C",
        "autoload_known_extensions": False,
        "autoinstall_known_extensions": False,
        "allow_community_extensions": False,
        "allow_persistent_secrets": False,
    }


def connect_warehouse(path, *, write: bool, temp_directory=None):
    import duckdb

    if write:
        connection = duckdb.connect(str(path), config=_write_config())
    else:
        if temp_directory is None:
            raise WarehouseContractError("read-only warehouse connections need a private temp directory")
        connection = duckdb.connect(str(path), read_only=True, config=_read_config(Path(temp_directory)))
    try:
        connection.execute("SET default_collation = 'C'")
        if not write:
            connection.execute("SET enable_external_access=false")
            connection.execute("SET lock_configuration=true")
    except Exception:
        connection.close()
        raise
    return connection


def _reset_staging(connection) -> None:
    for table in (
        "stg_line_version",
        "stg_affected_order",
        "stg_identity",
        "stg_order_header",
        "stg_order_line",
        "stg_refund",
        "stg_product_version",
    ):
        connection.execute(f"DROP TABLE IF EXISTS {table}")
    connection.execute(STAGING_SQL)


def _ensure_schema(connection) -> None:
    existing = {
        row[0]
        for row in connection.execute(
            "SELECT table_name FROM duckdb_tables() WHERE schema_name = 'main' AND NOT internal"
        ).fetchall()
    }
    if "fact_order_header" not in existing:
        connection.execute(CREATE_SQL)
        connection.execute(STAGING_SQL)
        return
    _reset_staging(connection)


def _insert_or_replace_meta(connection, *, as_of, content_hash: str, seed, rules, rule_version: str) -> None:
    connection.execute("DELETE FROM warehouse_meta")
    connection.execute(
        """
        INSERT INTO warehouse_meta VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            SCHEMA_VERSION,
            rule_version,
            GENERATOR_VERSION,
            PIPELINE_VERSION,
            utc_naive_instant(as_of),
            TIMEZONE,
            CURRENCY,
            AMOUNT_UNIT,
            AMOUNT_PRECISION,
            content_hash,
            seed,
            False,
            json.dumps(normalize_rules(rules), sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        ],
    )


def _read_group(source_dir: Path, names: tuple[str, ...], *, now, max_age_days, file_hashes, extra_patterns=()) -> tuple[list[dict], int, list[str], list[str]]:
    files = list_named_sources(source_dir, names)
    if {path.name for path in files} != set(names):
        raise WarehouseContractError("required source file missing")
    for pattern in extra_patterns:
        files.extend(path for path in list_matching_sources(source_dir, pattern) if path not in files)
    files = sorted(files, key=lambda path: path.name)
    plan = plan_ingest(files, now=now, max_age_days=max_age_days)
    result = read_planned_jsonl(plan, file_hashes=file_hashes)
    assert_read_matches_plan(plan, result)
    return result.records, result.bytes_read, result.opened, [path.name for path in plan.skipped]


def _validate_existing_schema(database: Path) -> None:
    """Reject incompatible state without resetting staging or opening a writer."""
    import duckdb

    connection = duckdb.connect(str(database), read_only=True, config=_write_config())
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info('warehouse_meta')").fetchall()}
        if "schema_version" not in columns or "rules_json" not in columns:
            raise WarehouseContractError("incompatible warehouse schema; preserve old state and rebuild synthetic sources in a separate empty directory")
        versions = connection.execute("SELECT schema_version FROM warehouse_meta").fetchall()
        if versions != [(SCHEMA_VERSION,)]:
            raise WarehouseContractError("incompatible warehouse schema; preserve old state and rebuild synthetic sources in a separate empty directory")
    finally:
        connection.close()


def _validated_file_hashes(manifest: dict) -> dict[str, str]:
    # v1 source JSONL remains readable; only the persisted warehouse schema changed.
    if manifest.get("schema_version") not in {"analytics-warehouse-schema/v1", SCHEMA_VERSION}:
        raise WarehouseContractError("unsupported source schema")
    hashes = manifest.get("file_hashes")
    if not isinstance(hashes, dict) or not hashes:
        raise WarehouseContractError("source file_hashes required")
    for name, digest in hashes.items():
        if not isinstance(name, str) or Path(name).name != name or name in {".", ".."}:
            raise WarehouseContractError("source hash names must be filenames")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise WarehouseContractError("source file hash must be SHA-256")
    if content_hash_from_file_hashes(hashes) != manifest.get("content_hash"):
        raise WarehouseContractError("source content hash mismatch")
    return hashes


@dataclass(frozen=True)
class WarehouseRun:
    directory: str
    database: str
    source_manifest: dict
    published_manifest: dict
    observation: dict
    content_hash: str
    row_counts: dict

    def connect_readonly(self, temp_directory):
        return connect_warehouse(self.database, write=False, temp_directory=temp_directory)


def run_warehouse_pipeline(
    source_dir,
    warehouse_dir,
    *,
    as_of: str = DEFAULT_AS_OF,
    now: datetime | None = None,
    max_age_days: int | None = None,
    incremental: bool = False,
    extra_order_patterns: tuple[str, ...] = (),
    order_file_names: tuple[str, ...] = ("orders.jsonl",),
) -> WarehouseRun:
    source_root = Path(source_dir)
    warehouse_root = Path(warehouse_dir)
    if not warehouse_root.is_dir():
        raise WarehouseContractError("warehouse directory must exist")
    database = warehouse_root / DATABASE_NAME
    if incremental:
        if not database.is_file():
            raise WarehouseContractError("incremental load requires an existing warehouse")
        _validate_existing_schema(database)
    elif any(warehouse_root.iterdir()):
        raise WarehouseContractError("full warehouse publish requires an empty directory")

    observation = PipelineObservation(
        timer_start_mark="before_generate",
        resource_limits={
            "duckdb_memory_mib": WAREHOUSE_DUCKDB_MEMORY_MIB,
            "duckdb_threads": WAREHOUSE_DUCKDB_THREADS,
            "duckdb_temp_mib": WAREHOUSE_TEMP_MIB,
            "python_version": sys.version.split()[0],
            "platform": sys.platform,
        },
    )
    timer_start = time.perf_counter_ns()
    observation.marks_ns["start"] = 0
    connection = None
    transaction_open = False
    try:
        source_manifest_path = source_root / MANIFEST_NAME
        source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
        if source_manifest.get("contains_real_data") is not False:
            raise WarehouseContractError("warehouse pipeline refuses non-synthetic sources")
        file_hashes = _validated_file_hashes(source_manifest)
        content_hash = source_manifest["content_hash"]
        seed = source_manifest.get("seed")
        as_of_value = source_manifest.get("as_of") or as_of

        with StageTimer(observation, "ingest") as ingest_stage:
            orders, order_bytes, orders_read, orders_skipped = _read_group(
                source_root,
                order_file_names,
                now=now,
                max_age_days=max_age_days,
                extra_patterns=extra_order_patterns,
                file_hashes=file_hashes,
            )
            lines, line_bytes, lines_read, _lines_skipped = _read_group(
                source_root, ("lines.jsonl",), now=now, max_age_days=None, file_hashes=file_hashes
            )
            refunds, refund_bytes, refunds_read, _ = _read_group(
                source_root, ("refunds.jsonl",), now=now, max_age_days=None, file_hashes=file_hashes
            )
            versions, version_bytes, versions_read, _ = _read_group(
                source_root, ("product_versions.jsonl",), now=now, max_age_days=None, file_hashes=file_hashes
            )
            identities, identity_bytes, identities_read, _ = _read_group(
                source_root, ("identities.jsonl",), now=now, max_age_days=None, file_hashes=file_hashes
            )
            ingest_stage.bytes_read = order_bytes + line_bytes + refund_bytes + version_bytes + identity_bytes
            ingest_stage.rows_in = (
                len(orders) + len(lines) + len(refunds) + len(versions) + len(identities)
            )
            ingest_stage.rows_out = ingest_stage.rows_in
            ingest_stage.extra = {
                "orders_read": orders_read,
                "orders_skipped": orders_skipped,
                "lines_read": lines_read,
                "refunds_read": refunds_read,
                "versions_read": versions_read,
                "identities_read": identities_read,
                "planned_equals_read": True,
            }

        observation.marks_ns["after_ingest"] = time.perf_counter_ns() - timer_start
        connection = connect_warehouse(database, write=True)
        connection.execute("BEGIN TRANSACTION")
        transaction_open = True
        _ensure_schema(connection)
        previous = read_previous_meta(connection) if incremental else None
        if incremental and previous is None:
            raise WarehouseContractError("incremental load requires warehouse_meta")
        if not incremental and not identities:
            raise WarehouseContractError("identities are required")
        rules = normalize_rules(source_manifest.get("rules"))
        rule_version = source_manifest.get("rule_version") or RULE_VERSION
        rules_changed = previous is not None and (
            previous.rules != rules or previous.rule_version != rule_version
        )
        install_rules(connection, rules)
        _insert_or_replace_meta(
            connection,
            as_of=as_of_value,
            content_hash=content_hash,
            seed=seed,
            rules=rules,
            rule_version=rule_version,
        )

        with StageTimer(observation, "identity", rows_in=len(identities)) as identity_stage:
            identity_rows = load_identities(connection, identities)
            identity_stage.rows_out = identity_rows

        with StageTimer(observation, "transform", rows_in=len(lines)) as transform_stage:
            header_rows = load_staging_orders(connection, orders)
            line_rows = load_staging_lines(connection, lines)
            load_staging_refunds(connection, refunds)
            load_staging_versions(connection, versions)
            unconstrained = count_unconstrained_product_join(connection)
            matched = attach_product_versions(connection)
            affected = classify_affected_orders(
                connection,
                previous=previous,
                new_as_of=as_of_value,
                rules_changed=rules_changed,
            )
            merge_staging_into_source(connection)
            transform_stage.rows_out = matched
            transform_stage.extra = {
                "header_rows": header_rows,
                "line_rows": line_rows,
                "range_join_rows": matched,
                "unconstrained_product_join_rows": unconstrained,
                "header_amounts_aggregated_from_join": False,
                **affected.to_extra(),
            }

        with StageTimer(observation, "load", rows_in=len(orders)) as load_stage:
            counts = rebuild_affected_facts(connection)
            future_refunds = count_future_refunds(connection)
            load_stage.rows_out = counts["fact_order_header"]
            load_stage.extra = {
                "incremental": incremental,
                "used_global_max_pay_time": False,
                "used_mtime_as_incremental_cursor": False,
                "full_table_rebuild": False if incremental else True,
                "grain": ["synthetic_user_id", "order_id"],
                "row_counts": counts,
                "affected_order_keys": affected.affected_order_keys,
                "headers_rewritten": affected.affected_order_keys,
                "unchanged_records": affected.unchanged_records,
                "new_or_changed_records": affected.new_or_changed_records,
                "content_hash_compared": True,
                "as_of_unchanged": affected.as_of_unchanged,
                "rules_changed": affected.rules_changed,
                "future_refunds_held": future_refunds,
            }

        observation.marks_ns["before_publish"] = time.perf_counter_ns() - timer_start
        with StageTimer(observation, "publish", rows_in=counts["fact_order_header"]) as publish_stage:
            connection.execute("COMMIT")
            transaction_open = False
            connection.execute("CHECKPOINT")
            observation.checkpoint = True
            observation.marks_ns["after_checkpoint"] = time.perf_counter_ns() - timer_start
            connection.close()
            connection = None
            observation.connection_closed = True
            observation.marks_ns["after_close"] = time.perf_counter_ns() - timer_start
            database.chmod(0o600)
            db_hash = hashlib.sha256(database.read_bytes()).hexdigest()
            published = {
                "schema_version": SCHEMA_VERSION,
                "rule_version": rule_version,
                "generator_version": GENERATOR_VERSION,
                "pipeline_version": PIPELINE_VERSION,
                "source_identity": source_manifest.get("source_identity"),
                "content_hash": content_hash,
                "file_hashes": source_manifest.get("file_hashes"),
                "consumed_file_hashes": {
                    name: file_hashes[name]
                    for name in orders_read + lines_read + refunds_read + versions_read + identities_read
                },
                "skipped_order_files": orders_skipped,
                "contains_real_data": False,
                "data_source": DATA_SOURCE,
                "database": DATABASE_NAME,
                "database_sha256": db_hash,
                "as_of": as_of_value,
                "timezone": TIMEZONE,
                "currency": CURRENCY,
                "amount_unit": AMOUNT_UNIT,
                "amount_precision": AMOUNT_PRECISION,
                "seed": seed,
                "row_counts": counts,
                "resource_limits": observation.resource_limits,
            }
            payload = (
                json.dumps(published, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
            ).encode("utf-8")
            published_path = warehouse_root / PUBLISHED_MANIFEST_NAME
            flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW
            flags |= os.O_TRUNC if incremental and published_path.exists() else os.O_EXCL
            fd = os.open(published_path, flags, 0o600)
            with os.fdopen(fd, "wb") as target:
                target.write(payload)
                target.flush()
                os.fsync(target.fileno())
            observation.manifest_written = True
            observation.published = True
            publish_stage.rows_out = counts["fact_order_header"]
            publish_stage.extra = {"database_sha256": db_hash, "checkpoint": True, "connection_closed": True}
        observation.marks_ns["after_publish"] = time.perf_counter_ns() - timer_start
        observation.timer_end_mark = "after_publish_close"
        observation.total_duration_ns = time.perf_counter_ns() - timer_start
        observation.process_ru_maxrss_bytes = process_ru_maxrss_bytes()
        observation.process_ru_maxrss_is_stage_peak = False
        return WarehouseRun(
            directory=str(warehouse_root),
            database=str(database),
            source_manifest=source_manifest,
            published_manifest=published,
            observation=observation.to_dict(),
            content_hash=content_hash,
            row_counts=counts,
        )
    except BaseException:
        if connection is not None:
            try:
                if transaction_open:
                    connection.execute("ROLLBACK")
            finally:
                connection.close()
        raise


def load_source_manifest(source_dir) -> dict:
    path = Path(source_dir) / MANIFEST_NAME
    return json.loads(path.read_text(encoding="utf-8"))
