#!/usr/bin/env python3
"""L4.74 DuckDB to Parquet export for PostgreSQL 16 POC loading."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DUCKDB_PATH = REPO_ROOT / "data" / "processed" / "fuqing_crm.duckdb"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "processed" / "postgresql16_parquet"
DEFAULT_TABLES = ("orders", "user_first_purchase", "user_rfm", "fact_rfm_long")
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _validate_table_name(table: str) -> str:
    if not IDENTIFIER_RE.match(table):
        raise ValueError(f"unsafe table name: {table}")
    return table


def _validate_snapshot_date(snapshot_date: str) -> str:
    parsed = date.fromisoformat(snapshot_date)
    if parsed.isoformat() != snapshot_date:
        raise ValueError(f"snapshot_date must be YYYY-MM-DD: {snapshot_date}")
    return snapshot_date


def _validate_limit(limit: int | None) -> int | None:
    if limit is not None and limit < 0:
        raise ValueError(f"limit must be >= 0: {limit}")
    return limit


def _atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
        tmp_name = fh.name
    Path(tmp_name).replace(path)


def export_sql(table: str, output_file: Path, limit: int | None = None) -> str:
    safe_table = _validate_table_name(table)
    safe_limit = _validate_limit(limit)
    limit_sql = f" LIMIT {safe_limit}" if safe_limit is not None else ""
    return (
        f"COPY (SELECT * FROM {safe_table}{limit_sql}) "
        f"TO {_quote_literal(str(output_file))} "
        "(FORMAT PARQUET, COMPRESSION ZSTD)"
    )


def _count_sql(table: str, limit: int | None = None) -> str:
    safe_table = _validate_table_name(table)
    safe_limit = _validate_limit(limit)
    if safe_limit is None:
        return f"SELECT COUNT(*) FROM {safe_table}"
    return f"SELECT COUNT(*) FROM (SELECT 1 FROM {safe_table} LIMIT {safe_limit}) t"


def _default_manifest_file(output_dir: Path, snapshot_date: str) -> Path:
    return output_dir / "_manifest" / f"snapshot_date={snapshot_date}.json"


def build_manifest(
    *,
    duckdb_path: Path,
    output_dir: Path,
    snapshot_date: str,
    tables: tuple[str, ...],
    results: list[dict[str, object]],
    dry_run: bool,
) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "duckdb_path": str(duckdb_path),
        "output_dir": str(output_dir),
        "snapshot_date": snapshot_date,
        "tables": list(tables),
        "dry_run": dry_run,
        "results": results,
    }


def export_tables(
    duckdb_path: Path,
    output_dir: Path,
    tables: tuple[str, ...],
    snapshot_date: str,
    limit: int | None = None,
    dry_run: bool = False,
    manifest_file: Path | None = None,
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    safe_snapshot_date = _validate_snapshot_date(snapshot_date)
    safe_limit = _validate_limit(limit)
    for table in tables:
        _validate_table_name(table)

    if dry_run:
        for table in tables:
            output_file = output_dir / table / f"snapshot_date={safe_snapshot_date}" / "part-000.parquet"
            results.append(
                {
                    "table": table,
                    "path": str(output_file),
                    "sql": export_sql(table, output_file, safe_limit),
                    "source_rows": None,
                    "exported_rows": None,
                    "bytes": None,
                    "status": "dry_run",
                }
            )
        if manifest_file is not None:
            _atomic_json_write(
                manifest_file,
                build_manifest(
                    duckdb_path=duckdb_path,
                    output_dir=output_dir,
                    snapshot_date=safe_snapshot_date,
                    tables=tables,
                    results=results,
                    dry_run=True,
                ),
            )
        return results

    if not duckdb_path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {duckdb_path}")

    import duckdb

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    staging_root = output_dir / "_staging" / f"snapshot_date={safe_snapshot_date}.{os.getpid()}"
    publish_queue: list[tuple[Path, Path, dict[str, object]]] = []
    try:
        for table in tables:
            output_file = output_dir / table / f"snapshot_date={safe_snapshot_date}" / "part-000.parquet"
            staging_file = staging_root / table / "part-000.parquet"
            staging_file.parent.mkdir(parents=True, exist_ok=True)
            sql = export_sql(table, staging_file, safe_limit)
            source_rows = conn.execute(_count_sql(table, safe_limit)).fetchone()
            conn.execute(sql)
            exported_rows = conn.execute(
                "SELECT COUNT(*) FROM read_parquet(?)",
                [str(staging_file)],
            ).fetchone()
            source_count = int(source_rows[0] if source_rows else 0)
            exported_count = int(exported_rows[0] if exported_rows else 0)
            if source_count != exported_count:
                raise ValueError(
                    f"Parquet row mismatch for {table}: source={source_count}, exported={exported_count}"
                )
            result = (
                {
                    "table": table,
                    "path": str(output_file),
                    "source_rows": source_count,
                    "exported_rows": exported_count,
                    "bytes": None,
                    "status": "ok",
                }
            )
            publish_queue.append((staging_file, output_file, result))

        for staging_file, output_file, result in publish_queue:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            staging_file.replace(output_file)
            result["bytes"] = output_file.stat().st_size
            results.append(result)
    finally:
        conn.close()
        shutil.rmtree(staging_root, ignore_errors=True)
        try:
            staging_root.parent.rmdir()
        except OSError:
            pass

    if manifest_file is not None:
        _atomic_json_write(
            manifest_file,
            build_manifest(
                duckdb_path=duckdb_path,
                output_dir=output_dir,
                snapshot_date=safe_snapshot_date,
                tables=tables,
                results=results,
                dry_run=False,
            ),
        )
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb-path", type=Path, default=Path(os.environ.get("DUCKDB_PATH", DEFAULT_DUCKDB_PATH)))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--snapshot-date", default=os.environ.get("FQ_PARQUET_SNAPSHOT_DATE", date.today().isoformat()))
    parser.add_argument("--tables", default=",".join(DEFAULT_TABLES))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--manifest-file", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tables = tuple(item.strip() for item in args.tables.split(",") if item.strip())
    manifest_file = args.manifest_file or _default_manifest_file(args.output_dir, args.snapshot_date)
    try:
        for result in export_tables(
            args.duckdb_path,
            args.output_dir,
            tables,
            args.snapshot_date,
            args.limit,
            args.dry_run,
            manifest_file,
        ):
            print(result)
        print({"manifest": str(manifest_file)})
        return 0
    except Exception as exc:
        print(f"[L4.74_PARQUET_ETL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
