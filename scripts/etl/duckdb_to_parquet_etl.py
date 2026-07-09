#!/usr/bin/env python3
"""L4.74 DuckDB to Parquet export for PostgreSQL 16 POC loading."""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path


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


def export_sql(table: str, output_file: Path, limit: int | None = None) -> str:
    safe_table = _validate_table_name(table)
    limit_sql = f" LIMIT {int(limit)}" if limit is not None else ""
    return (
        f"COPY (SELECT * FROM {safe_table}{limit_sql}) "
        f"TO {_quote_literal(str(output_file))} "
        "(FORMAT PARQUET, COMPRESSION ZSTD)"
    )


def export_tables(
    duckdb_path: Path,
    output_dir: Path,
    tables: tuple[str, ...],
    snapshot_date: str,
    limit: int | None = None,
    dry_run: bool = False,
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for table in tables:
        _validate_table_name(table)
    if dry_run:
        for table in tables:
            output_file = output_dir / table / f"snapshot_date={snapshot_date}" / "part-000.parquet"
            results.append({"table": table, "path": str(output_file), "sql": export_sql(table, output_file, limit)})
        return results
    if not duckdb_path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {duckdb_path}")

    import duckdb

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        for table in tables:
            output_file = output_dir / table / f"snapshot_date={snapshot_date}" / "part-000.parquet"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            sql = export_sql(table, output_file, limit)
            conn.execute(sql)
            rows = conn.execute(f"SELECT COUNT(*) FROM {_validate_table_name(table)}").fetchone()
            results.append({"table": table, "path": str(output_file), "source_rows": int(rows[0] if rows else 0)})
    finally:
        conn.close()
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb-path", type=Path, default=Path(os.environ.get("DUCKDB_PATH", DEFAULT_DUCKDB_PATH)))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--snapshot-date", default=os.environ.get("FQ_PARQUET_SNAPSHOT_DATE", date.today().isoformat()))
    parser.add_argument("--tables", default=",".join(DEFAULT_TABLES))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tables = tuple(item.strip() for item in args.tables.split(",") if item.strip())
    try:
        for result in export_tables(args.duckdb_path, args.output_dir, tables, args.snapshot_date, args.limit, args.dry_run):
            print(result)
        return 0
    except Exception as exc:
        print(f"[L4.74_PARQUET_ETL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
