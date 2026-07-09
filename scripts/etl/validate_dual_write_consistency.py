#!/usr/bin/env python3
"""Validate DuckDB and PostgreSQL 16 dual-write consistency for L4.74."""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DUCKDB_PATH = REPO_ROOT / "data" / "processed" / "fuqing_crm.duckdb"
DEFAULT_CHECKS = ("orders_daily", "rfm_segment_distribution", "r_interval_distribution")


@dataclass(frozen=True)
class ConsistencyQuery:
    name: str
    duckdb_sql: str
    postgres_sql: str
    tolerance_ratio: float
    key_columns: tuple[str, ...] = ()
    require_non_empty: bool = True
    require_positive_metric: str | None = "row_count"


def _date_literal(engine: str, value: str) -> str:
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError(f"snapshot_date must be YYYY-MM-DD: {value}")
    if engine == "postgres":
        return f"DATE '{value}'"
    return f"DATE '{value}'"


def build_consistency_queries(snapshot_date: str) -> list[ConsistencyQuery]:
    duck_date = _date_literal("duckdb", snapshot_date)
    pg_date = _date_literal("postgres", snapshot_date)
    return [
        ConsistencyQuery(
            name="orders_daily",
            duckdb_sql=f"""
                SELECT
                    COUNT(*)::DOUBLE AS row_count,
                    COUNT(DISTINCT user_id)::DOUBLE AS distinct_users,
                    COALESCE(SUM(actual_amount), 0)::DOUBLE AS amount_sum
                FROM orders
                WHERE DATE(pay_time) = {duck_date}
            """,
            postgres_sql=f"""
                SELECT
                    COUNT(*)::DOUBLE PRECISION AS row_count,
                    COUNT(DISTINCT user_id)::DOUBLE PRECISION AS distinct_users,
                    COALESCE(SUM(actual_amount), 0)::DOUBLE PRECISION AS amount_sum
                FROM orders
                WHERE pay_time::date = {pg_date}
            """,
            tolerance_ratio=0.001,
        ),
        ConsistencyQuery(
            name="rfm_segment_distribution",
            duckdb_sql=f"""
                SELECT
                    rfm_segment,
                    COUNT(*)::DOUBLE AS row_count,
                    COUNT(DISTINCT user_id)::DOUBLE AS distinct_users
                FROM user_rfm_precompute
                WHERE as_of_date = {duck_date}
                GROUP BY rfm_segment
                ORDER BY rfm_segment
            """,
            postgres_sql=f"""
                SELECT
                    rfm_segment,
                    COUNT(*)::DOUBLE PRECISION AS row_count,
                    COUNT(DISTINCT user_id)::DOUBLE PRECISION AS distinct_users
                FROM user_rfm_precompute
                WHERE as_of_date = {pg_date}
                GROUP BY rfm_segment
                ORDER BY rfm_segment
            """,
            tolerance_ratio=0.0,
            key_columns=("rfm_segment",),
        ),
        ConsistencyQuery(
            name="r_interval_distribution",
            duckdb_sql=f"""
                SELECT
                    r_interval,
                    COUNT(*)::DOUBLE AS row_count,
                    COUNT(DISTINCT user_id)::DOUBLE AS distinct_users
                FROM user_rfm_precompute
                WHERE as_of_date = {duck_date}
                GROUP BY r_interval
                ORDER BY r_interval
            """,
            postgres_sql=f"""
                SELECT
                    r_interval,
                    COUNT(*)::DOUBLE PRECISION AS row_count,
                    COUNT(DISTINCT user_id)::DOUBLE PRECISION AS distinct_users
                FROM user_rfm_precompute
                WHERE as_of_date = {pg_date}
                GROUP BY r_interval
                ORDER BY r_interval
            """,
            tolerance_ratio=0.0,
            key_columns=("r_interval",),
        ),
    ]


def compare_metric(duckdb_value: float, postgres_value: float, tolerance_ratio: float) -> dict[str, Any]:
    delta = postgres_value - duckdb_value
    denominator = max(abs(duckdb_value), 1.0)
    ratio = abs(delta) / denominator
    return {
        "duckdb": duckdb_value,
        "postgres": postgres_value,
        "delta": delta,
        "ratio": ratio,
        "ok": ratio <= tolerance_ratio or math.isclose(duckdb_value, postgres_value, abs_tol=1e-9),
    }


def compare_rows(
    name: str,
    duckdb_row: dict[str, Any],
    postgres_row: dict[str, Any],
    tolerance_ratio: float,
    key: tuple[Any, ...] = (),
    key_columns: tuple[str, ...] = (),
) -> dict[str, Any]:
    metrics = sorted((set(duckdb_row) | set(postgres_row)) - set(key_columns))
    comparisons = {
        metric: compare_metric(
            float(duckdb_row.get(metric, 0.0)),
            float(postgres_row.get(metric, 0.0)),
            tolerance_ratio,
        )
        for metric in metrics
    }
    return {
        "name": name,
        "key": list(key),
        "key_columns": list(key_columns),
        "tolerance_ratio": tolerance_ratio,
        "ok": all(item["ok"] for item in comparisons.values()),
        "comparisons": comparisons,
    }


def compare_query_rows(
    query: ConsistencyQuery,
    duckdb_rows: list[dict[str, Any]],
    postgres_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if query.require_non_empty and not duckdb_rows and not postgres_rows:
        return {
            "name": query.name,
            "key_columns": list(query.key_columns),
            "tolerance_ratio": query.tolerance_ratio,
            "ok": False,
            "error": "both sources returned no rows",
        }

    if not query.key_columns:
        duckdb_row = duckdb_rows[0] if duckdb_rows else {}
        postgres_row = postgres_rows[0] if postgres_rows else {}
        result = compare_rows(query.name, duckdb_row, postgres_row, query.tolerance_ratio)
        _attach_positive_metric_check(result, query, duckdb_rows, postgres_rows)
        return result

    def index_rows(rows: list[dict[str, Any]]) -> dict[tuple[Any, ...], dict[str, Any]]:
        return {
            tuple(row.get(column) for column in query.key_columns): row
            for row in rows
        }

    duckdb_index = index_rows(duckdb_rows)
    postgres_index = index_rows(postgres_rows)
    keys = sorted(set(duckdb_index) | set(postgres_index))
    comparisons = [
        compare_rows(
            query.name,
            duckdb_index.get(key, {}),
            postgres_index.get(key, {}),
            query.tolerance_ratio,
            key=key,
            key_columns=query.key_columns,
        )
        for key in keys
    ]
    result = {
        "name": query.name,
        "key_columns": list(query.key_columns),
        "tolerance_ratio": query.tolerance_ratio,
        "ok": all(item["ok"] for item in comparisons),
        "rows": comparisons,
    }
    _attach_positive_metric_check(result, query, duckdb_rows, postgres_rows)
    return result


def _sum_metric(rows: list[dict[str, Any]], metric: str) -> float:
    return sum(float(row.get(metric, 0.0)) for row in rows)


def _attach_positive_metric_check(
    result: dict[str, Any],
    query: ConsistencyQuery,
    duckdb_rows: list[dict[str, Any]],
    postgres_rows: list[dict[str, Any]],
) -> None:
    metric = query.require_positive_metric
    if metric is None:
        return
    duckdb_total = _sum_metric(duckdb_rows, metric)
    postgres_total = _sum_metric(postgres_rows, metric)
    check = {
        "metric": metric,
        "duckdb_total": duckdb_total,
        "postgres_total": postgres_total,
        "ok": duckdb_total > 0 and postgres_total > 0,
    }
    result["non_empty_check"] = check
    result["ok"] = bool(result["ok"] and check["ok"])


def _coerce_cell(value: Any) -> float | str:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


def _fetch_duckdb_rows(duckdb_path: Path, sql: str) -> list[dict[str, Any]]:
    import duckdb

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        cursor = conn.execute(sql)
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
    finally:
        conn.close()
    return [
        {column: _coerce_cell(value) for column, value in zip(columns, row)}
        for row in rows
    ]


def _fetch_postgres_rows(postgres_dsn: str, sql: str) -> list[dict[str, Any]]:
    proc = subprocess.run(
        ["psql", "-X", "-A", "-F", ",", "--csv", postgres_dsn, "-c", sql],
        check=True,
        text=True,
        capture_output=True,
    )
    rows = list(csv.DictReader(proc.stdout.splitlines()))
    return [
        {key: _coerce_cell(value) for key, value in row.items()}
        for row in rows
    ]


def run_validation(
    *,
    duckdb_path: Path,
    postgres_dsn: str,
    snapshot_date: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    queries = build_consistency_queries(snapshot_date)
    if dry_run:
        return {
            "snapshot_date": snapshot_date,
            "dry_run": True,
            "queries": [query.__dict__ for query in queries],
        }
    if not duckdb_path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {duckdb_path}")
    results = []
    for query in queries:
        duckdb_rows = _fetch_duckdb_rows(duckdb_path, query.duckdb_sql)
        postgres_rows = _fetch_postgres_rows(postgres_dsn, query.postgres_sql)
        results.append(compare_query_rows(query, duckdb_rows, postgres_rows))
    return {
        "snapshot_date": snapshot_date,
        "dry_run": False,
        "ok": all(result["ok"] for result in results),
        "results": results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb-path", type=Path, default=Path(os.environ.get("DUCKDB_PATH", DEFAULT_DUCKDB_PATH)))
    parser.add_argument("--postgres-dsn", default=os.environ.get("FQ_POSTGRES_DSN", "postgresql://fuqing:fuqing_dev_password@localhost:5434/fuqing_crm"))
    parser.add_argument("--snapshot-date", required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = run_validation(
            duckdb_path=args.duckdb_path,
            postgres_dsn=args.postgres_dsn,
            snapshot_date=args.snapshot_date,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"[L4.74_DUAL_WRITE_VALIDATE] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload.get("ok", True) else 2


if __name__ == "__main__":
    raise SystemExit(main())
