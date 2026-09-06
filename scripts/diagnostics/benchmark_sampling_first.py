#!/usr/bin/env python3
"""Bounded synthetic SQL microbenchmark, not full RFM/dashboard capacity proof.

Only the known sample_users_sql literal is compiled from the service. No config,
dotenv, server, ETL or private database imports/connections. No data-path option.
Both variants run in fresh child processes with identical native resource caps.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE = REPO_ROOT / "backend/services/sampling_service.py"


def sample_users_query(field="spu_category"):
    """Extract the exact service literal; only fixture-controlled bindings exist."""
    if field not in ("spu_category", "spu_tier"):
        raise ValueError("Probe field must be spu_category or spu_tier")
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "get_sampling_roi")
    nodes = [node.value for node in ast.walk(function)
             if isinstance(node, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == "sample_users_sql" for t in node.targets)]
    if len(nodes) != 1 or not isinstance(nodes[0], ast.JoinedStr):
        raise ValueError("Service SQL shape changed; review probe before rerunning")
    # Bind a synthetic channel name; channel logic itself is not benchmarked.
    return eval(compile(ast.Expression(nodes[0]), str(SOURCE), "eval"),
                {"__builtins__": {}},
                {"cat_field": field, "GIFT_SAMPLE_DB": "fixture-gift",
                 "ch_placeholders": "?,?"})


def legacy_query(query):
    for field in ("spu_category", "spu_tier"):
        query = query.replace(
            f"FIRST(COALESCE(o.{field}, '未知') ORDER BY o.pay_time ASC)",
            f"(ARRAY_AGG(COALESCE(o.{field}, '未知') ORDER BY o.pay_time ASC))[1]",
        )
    return query


def run_case(case, rows, key_type="string"):
    import duckdb

    query = sample_users_query("spu_tier")
    if case == "legacy":
        query = legacy_query(query)
    query += " ORDER BY user_id, channel"
    customers = max(1, rows // 10)
    key_sql = ("repeat(md5(CAST(i % ? AS VARCHAR)), 4)" if key_type == "string" else "i % ?")
    params = ["fixture-sample-a", "fixture-sample-b", "2025-06-01", "2025-06-30"]
    with duckdb.connect(":memory:", config={
        "memory_limit": "512MB", "threads": 2, "temp_directory": "",
    }) as conn:
        conn.execute(f"""CREATE TABLE orders AS
            SELECT CAST(i AS VARCHAR) AS order_id, NULL::VARCHAR AS sub_order_id,
                   {key_sql} AS user_id,
                   CASE WHEN i % 3 = 0 THEN 'fixture-sample-a' ELSE 'fixture-sample-b' END AS channel,
                   TIMESTAMP '2025-06-01' + i * INTERVAL '1 second' AS pay_time,
                   NULL::TIMESTAMP AS sample_received_at,
                   CASE WHEN i % 13 = 0 THEN NULL ELSE 'category-' || CAST(i % 7 AS VARCHAR) END AS spu_category,
                   'tier-' || CAST(i % 3 AS VARCHAR) AS spu_tier
            FROM range(?) t(i)
        """, [customers, rows])
        execute_times, fetch_times, totals = [], [], []
        result = []
        for _ in range(5):
            result = []  # Do not retain the previous result while executing again.
            start = time.perf_counter()
            conn.execute(query, params)
            executed = time.perf_counter()
            result = conn.fetchall()
            fetched = time.perf_counter()
            execute_times.append(executed - start)
            fetch_times.append(fetched - executed)
            totals.append(fetched - start)
        # Normalize only for correctness comparison, OUTSIDE timed execution/fetch.
        # These are synthetic labels, not a production identity migration/hash policy.
        if key_type == "integer":
            result = sorted((hashlib.md5(str(row[0]).encode()).hexdigest() * 4, *row[1:])
                            for row in result)
        digest = hashlib.sha256(json.dumps(result, default=str, ensure_ascii=False).encode()).hexdigest()
        plan = conn.execute("EXPLAIN " + query, params).fetchall()[0][1]
        count = len(result)
    peak_rss_mib = None
    try:
        import resource
        raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_rss_mib = raw / (1024 ** 2 if sys.platform == "darwin" else 1024)
    except ImportError:
        pass
    return {
        "case": case, "outcome": "ok", "duckdb_version": duckdb.__version__, "synthetic_rows": rows,
        "customer_keys": customers, "key_type": key_type,
        "user_id_chars": 128 if key_type == "string" else None, "result_rows": count,
        "repeats": 5, "memory_limit": "512MB", "threads": 2, "spill": "disabled",
        "median_execute_seconds": statistics.median(execute_times),
        "median_fetch_seconds": statistics.median(fetch_times),
        "median_total_seconds": statistics.median(totals),
        "process_peak_rss_mib_including_fixture_and_results": peak_rss_mib,
        "scalar_arg_min_in_plan": "arg_min" in plan.lower(),
        "result_sha256": digest,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--case", choices=("legacy", "current"))
    parser.add_argument("--key-type", choices=("string", "integer"), default="string")
    args = parser.parse_args()
    if not 1 <= args.rows <= 1_000_000:
        parser.error("rows must be between 1 and 1,000,000; larger tests need a separate resource gate")
    if args.case:
        import duckdb

        try:
            result = run_case(args.case, args.rows, args.key_type)
        except duckdb.OutOfMemoryException as exc:
            # Resource exhaustion is a benchmark result, not permission to lift caps.
            result = {
                "case": args.case, "outcome": "out_of_memory", "synthetic_rows": args.rows,
                "key_type": args.key_type,
                "duckdb_version": duckdb.__version__, "memory_limit": "512MB",
                "threads": 2, "spill": "disabled", "error": str(exc).splitlines()[0],
            }
        print(json.dumps(result, ensure_ascii=False))
        return
    cases = []
    for case in ("legacy", "current"):
        child = subprocess.run(
            [sys.executable, "-B", str(Path(__file__).resolve()), "--rows", str(args.rows),
             "--case", case, "--key-type", args.key_type],
            capture_output=True, text=True, timeout=45, check=True,
            env={**os.environ, "PYTHON_DOTENV_DISABLED": "1", "PYTHONDONTWRITEBYTECODE": "1"},
        )
        cases.append(json.loads(child.stdout))
    equal = (cases[0]["result_sha256"] == cases[1]["result_sha256"]
             if all(case["outcome"] == "ok" for case in cases) else None)
    print(json.dumps({
        "scope": "SYNTHETIC SAMPLE-USER SQL ONLY; not RFM, full ROI API or multiuser SLA",
        "service_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "results_equal": equal, "cases": cases,
    }, ensure_ascii=False, indent=2))
    if equal is False:
        raise SystemExit("Result mismatch; optimization is not accepted")
    if cases[1]["outcome"] != "ok":
        raise SystemExit("Current query exceeded the resource budget")


if __name__ == "__main__":
    main()
