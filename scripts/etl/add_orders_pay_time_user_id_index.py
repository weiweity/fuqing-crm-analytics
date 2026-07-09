#!/usr/bin/env python3
"""Apply the L4.70 orders(pay_time, user_id) index in DuckDB."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SQL_PATH = REPO_ROOT / "scripts" / "etl" / "add_orders_pay_time_user_id_index.sql"
DEFAULT_DUCKDB_PATH = REPO_ROOT / "data" / "processed" / "fuqing_crm.duckdb"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb-path", type=Path, default=Path(os.environ.get("DUCKDB_PATH", DEFAULT_DUCKDB_PATH)))
    parser.add_argument("--sql-path", type=Path, default=SQL_PATH)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def apply_index(duckdb_path: Path, sql_path: Path, dry_run: bool = False) -> int:
    sql = sql_path.read_text(encoding="utf-8")
    if "CREATE INDEX IF NOT EXISTS idx_orders_pay_time_user_id" not in sql:
        raise ValueError(f"unexpected SQL file content: {sql_path}")
    if dry_run:
        print(sql.strip())
        return 0
    if not duckdb_path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {duckdb_path}")

    import duckdb

    conn = duckdb.connect(str(duckdb_path))
    try:
        conn.execute(sql)
        conn.execute("CHECKPOINT")
    finally:
        conn.close()
    print(f"L4.70 index ensured on {duckdb_path}")
    return 0


def main() -> int:
    args = parse_args()
    try:
        return apply_index(args.duckdb_path, args.sql_path, dry_run=args.dry_run)
    except Exception as exc:
        print(f"[L4.70_INDEX] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
