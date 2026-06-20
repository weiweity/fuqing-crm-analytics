#!/usr/bin/env python3
"""Run the production ETL against an isolated synthetic-order benchmark."""

from __future__ import annotations

import argparse
import json
import os
import resource
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.etl.benchmarks.generate_synthetic_orders import (  # noqa: E402
    FIFTY_MILLION,
    MIN_FREE_BYTES_FOR_50M,
    generate_synthetic_orders,
)


DEFAULT_REPORT = Path(__file__).with_name("scale_report_50m.md")


def _directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def _peak_rss_mb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return peak / 1024**2
    return peak / 1024


def _host_memory_bytes() -> int:
    if sys.platform == "darwin":
        try:
            return int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip())
        except (OSError, subprocess.SubprocessError, ValueError):
            return 0
    try:
        return int(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"))
    except (OSError, ValueError):
        return 0


class DiskMonitor:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.peak_bytes = _directory_size(root)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.wait(0.5):
            self.peak_bytes = max(self.peak_bytes, _directory_size(self.root))

    def __enter__(self) -> "DiskMonitor":
        self._thread.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self._stop.set()
        self._thread.join(timeout=2)
        self.peak_bytes = max(self.peak_bytes, _directory_size(self.root))


def _patch_benchmark_config(run_dir: Path, parquet_dir: Path, db_path: Path) -> Path:
    """Patch path constants before importing any ETL implementation module."""
    source_dir = run_dir / "source"
    processed_dir = run_dir / "processed"
    for path in (
        source_dir / "shop",
        source_dir / "member",
        source_dir / "taoke",
        source_dir / "live",
        source_dir / "visitor",
        processed_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)

    os.environ.update({
        "DUCKDB_PATH": str(db_path),
        "SHOP_DATA_SOURCE": str(source_dir / "shop"),
        "MEMBER_DATA_SOURCE": str(source_dir / "member"),
        "SPU_MAPPING_SOURCE": str(source_dir / "missing_spu.csv"),
        "CHANNEL_RULES_SOURCE": str(source_dir / "missing_channel_rules.csv"),
        "TAOKE_DATA_SOURCE": str(source_dir / "taoke"),
        "TAOKE_PRODUCT_SOURCE": str(source_dir / "missing_taoke_products.csv"),
        "LIVE_DATA_SOURCE": str(source_dir / "live"),
        "VISITOR_DATA_SOURCE": str(source_dir / "visitor"),
        "CAMPAIGN_SCHEDULE_SOURCE": str(source_dir / "missing_campaign.csv"),
        "FQ_ETL_LENIENT_LOAD": "1",
        "ETL_BASELINE_DATE": f"benchmark_{run_dir.name}",
    })

    import backend.config as backend_config

    replacements: dict[str, Any] = {
        "DATA_DIR": run_dir,
        "PROCESSED_DATA_DIR": processed_dir,
        "PARQUET_DATA_DIR": parquet_dir,
        "DUCKDB_PATH": db_path,
        "SHOP_DATA_SOURCE": source_dir / "shop",
        "MEMBER_DATA_SOURCE": source_dir / "member",
        "SPU_MAPPING_SOURCE": source_dir / "missing_spu.csv",
        "CHANNEL_RULES_SOURCE": source_dir / "missing_channel_rules.csv",
        "TAOKE_DATA_SOURCE": source_dir / "taoke",
        "TAOKE_PRODUCT_SOURCE": source_dir / "missing_taoke_products.csv",
        "LIVE_DATA_SOURCE": source_dir / "live",
        "VISITOR_DATA_SOURCE": source_dir / "visitor",
        "CAMPAIGN_SCHEDULE_SOURCE": source_dir / "missing_campaign.csv",
    }
    for name, value in replacements.items():
        setattr(backend_config, name, value)

    from scripts.etl import config as etl_config

    for name, value in replacements.items():
        if hasattr(etl_config, name):
            setattr(etl_config, name, value)
    return processed_dir


def _bootstrap_database(db_path: Path) -> float:
    import duckdb
    from backend.config import DUCKDB_MEMORY_LIMIT
    from backend.db.init import create_user_rfm_table
    from scripts.etl.load import _create_metrics_tables, init_database
    from scripts.etl.precompute_fact_rfm import create_fact_rfm_table

    started = time.perf_counter()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    init_database()
    conn = duckdb.connect(str(db_path), config={"memory_limit": DUCKDB_MEMORY_LIMIT})
    try:
        conn.execute("DROP TABLE IF EXISTS daily_metrics")
        conn.execute("DROP TABLE IF EXISTS monthly_metrics")
        _create_metrics_tables(conn)
        create_user_rfm_table(conn)
        create_fact_rfm_table(conn)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_pay_time ON orders(pay_time)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_year_month ON orders(year, month)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_product ON orders(product_id)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_orders_channel_pay_time ON orders(channel, pay_time)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_orders_channel_member ON orders(channel, is_member)"
        )
        conn.execute(
            """
            INSERT INTO orders (
                order_id, sub_order_id, user_id, order_time, pay_time, ship_time,
                order_status, product_id, product_title, sku_name, quantity,
                amount, refund_amount, actual_amount, year, month, is_member,
                spu_type, spu_product_class, channel, is_goujinjin, is_refund
            ) VALUES (
                'BENCHMARK-SEED', 'BENCHMARK-SEED-1', 'BENCHMARK-SEED-USER',
                TIMESTAMP '2024-12-31 00:00:00', TIMESTAMP '2024-12-31 00:05:00',
                TIMESTAMP '2025-01-01 00:00:00', '交易成功', 'BENCHMARK-PRODUCT',
                'Benchmark Seed Product', 'Benchmark Seed SKU', 1, 1.00, 0.00,
                1.00, 2024, 12, FALSE, '正装', 'Benchmark', '货架', FALSE, FALSE
            )
            """
        )
    finally:
        conn.close()
    return time.perf_counter() - started


def _run_production_etl(db_path: Path) -> tuple[float, list[dict[str, Any]], int]:
    import duckdb
    from backend.config import DUCKDB_MEMORY_LIMIT
    from scripts.etl._timer import get_records, reset
    from scripts.etl.pipeline import run_full_etl

    reset()
    started = time.perf_counter()
    run_full_etl(mode="inc", force_continue=True, skip_dq=False, skip_w4=False)
    elapsed = time.perf_counter() - started
    records = [record.to_dict() for record in get_records()]

    conn = duckdb.connect(str(db_path), config={"memory_limit": DUCKDB_MEMORY_LIMIT})
    try:
        count = int(conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0])
    finally:
        conn.close()
    return elapsed, records, count


def _format_size(size: int | float) -> str:
    return f"{size / 1024**3:.2f} GiB"


def _load_results(root: Path) -> list[dict[str, Any]]:
    results = []
    for result_path in root.glob("scale-*/result.json"):
        try:
            results.append(json.loads(result_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(results, key=lambda item: int(item.get("n_orders", 0)))


def render_report(results_root: Path, report_path: Path) -> None:
    results = _load_results(results_root)
    rows = []
    for item in results:
        rows.append(
            "| {n_orders:,} | {status} | {total:.2f} | {generate:.2f} | {etl:.2f} | "
            "{rss:.1f} MiB | {peak_disk} | {db_size} |".format(
                n_orders=int(item.get("n_orders", 0)),
                status=item.get("status", "unknown"),
                total=float(item.get("total_sec", 0)),
                generate=float(item.get("generation_sec", 0)),
                etl=float(item.get("etl_sec", 0)),
                rss=float(item.get("peak_rss_mb", 0)),
                peak_disk=_format_size(float(item.get("peak_disk_bytes", 0))),
                db_size=_format_size(float(item.get("duckdb_bytes", 0))),
            )
        )
    if not rows:
        rows.append("| - | pending | - | - | - | - | - | - |")

    passed_results = [item for item in results if item.get("status") == "passed"]
    latest = passed_results[-1] if passed_results else (results[-1] if results else {})
    step_rows = []
    for step in latest.get("per_step", []):
        step_rows.append(
            f"| {step.get('name', 'unknown')} | {float(step.get('wall_sec', 0)):.4f} | "
            f"{float(step.get('cpu_sec', 0)):.4f} | {float(step.get('rss_peak_mb', 0)):.1f} |"
        )
    if not step_rows:
        step_rows.append("| - | - | - | - |")

    host_memory = _host_memory_bytes()
    capacity_rows = []
    measured_counts = {int(item.get("n_orders", 0)) for item in passed_results}
    latest_count = int(latest.get("n_orders", 0))
    latest_rss = float(latest.get("peak_rss_mb", 0))
    for target in (5_000_000, 10_000_000, 50_000_000):
        if target in measured_counts:
            target_result = next(item for item in passed_results if int(item["n_orders"]) == target)
            capacity_rows.append(
                f"| {target:,} | measured | {float(target_result['peak_rss_mb']) / 1024:.2f} GiB | - |"
            )
            continue
        projected_mb = latest_rss * target / latest_count if latest_count else 0
        projected_bytes = projected_mb * 1024**2
        if target == FIFTY_MILLION:
            decision = "approval required; current host memory is insufficient"
        elif host_memory and projected_bytes >= host_memory * 0.8:
            decision = "not run; projected RSS exceeds 80% of host memory"
        else:
            decision = "not run"
        capacity_rows.append(
            f"| {target:,} | projected from {latest_count:,} | {projected_mb / 1024:.2f} GiB | {decision} |"
        )

    slowest = max(
        latest.get("per_step", []),
        key=lambda step: float(step.get("wall_sec", 0)),
        default={},
    )
    slowest_note = (
        f"- Slowest measured ETL timer: `{slowest.get('name')}` at "
        f"{float(slowest.get('wall_sec', 0)):.2f}s."
        if slowest
        else "- No ETL timer result is available yet."
    )

    content = f"""# Sprint 52 - 50m Scale Benchmark

## Reproduce

```bash
python3 scripts/etl/benchmarks/run_scale_benchmark.py --n_orders 1000000
python3 scripts/etl/benchmarks/run_scale_benchmark.py --n_orders 5000000
python3 scripts/etl/benchmarks/run_scale_benchmark.py --n_orders 10000000
# Run only after explicit approval and with >200 GiB free:
python3 scripts/etl/benchmarks/run_scale_benchmark.py --n_orders 50000000 --allow-50m
```

All generated inputs, trackers, performance output, and DuckDB files live under
`data/benchmarks/scale-<N>/`; the production DuckDB is never opened.

## Scale Results

| Orders | Status | Total sec | W1 generate sec | W2-W7 ETL sec | Peak RSS | Peak disk | DuckDB |
|---:|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

## Latest ETL Step Timings

The end-to-end ETL total includes every production stage, including W4 fact-RFM.
The per-step timers below expose source load, transform, DuckDB upsert, user
tables, daily metrics, category precompute, and W3 DQ assertions; W4 currently
has no dedicated `PerfTimer`, so it remains inside the aggregate ETL time.

| Timer | Wall sec | CPU sec | Peak RSS MiB |
|---|---:|---:|---:|
{chr(10).join(step_rows)}

## Capacity Gate

Current host physical memory: {_format_size(host_memory)}. Projections are linear
planning estimates from the largest completed rung, not substitute measurements.

| Orders | Evidence | Peak RSS | Decision |
|---:|---|---:|---|
{chr(10).join(capacity_rows)}

## Bottleneck Notes

- W1 generates Parquet inside DuckDB, so Python does not materialize all rows.
- W2-W7 intentionally use the production incremental ETL. Its current Parquet
  ingest concatenates source files into Pandas DataFrames, so peak RSS is the
  primary scaling risk to watch at 10m and 50m.
{slowest_note}
- A failed rung still writes `result.json` and updates this report before exit.
"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(content, encoding="utf-8")


def run_benchmark(
    n_orders: int,
    output_dir: Path,
    report_path: Path,
    *,
    force: bool = False,
    allow_50m: bool = False,
    generate_only: bool = False,
) -> dict[str, Any]:
    if n_orders >= FIFTY_MILLION:
        if not allow_50m:
            raise ValueError("50m benchmark requires explicit approval: pass --allow-50m")
        output_dir.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(output_dir).free
        if free < MIN_FREE_BYTES_FOR_50M:
            raise OSError(f"50m benchmark requires >200 GiB free; available={free / 1024**3:.1f} GiB")

    output_dir = output_dir.resolve()
    input_dir = output_dir / "input"
    db_path = output_dir / "benchmark.duckdb"
    started = time.perf_counter()
    result: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "n_orders": n_orders,
        "status": "running",
        "command": f"python3 scripts/etl/benchmarks/run_scale_benchmark.py --n_orders {n_orders}",
        "run_dir": str(output_dir),
        "duckdb_path": str(db_path),
        "generation_sec": 0.0,
        "bootstrap_sec": 0.0,
        "etl_sec": 0.0,
        "per_step": [],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "result.json"
    try:
        manifest = generate_synthetic_orders(
            n_orders,
            input_dir,
            force=force,
            allow_50m=allow_50m,
        )
        result["generation_sec"] = float(manifest["generation_sec"])
        result["input_bytes"] = int(manifest["shop_bytes"]) + int(manifest["member_bytes"])

        if generate_only:
            result["status"] = "generated_only"
        else:
            shutil.rmtree(output_dir / "processed", ignore_errors=True)
            _patch_benchmark_config(output_dir, input_dir, db_path)
            result["bootstrap_sec"] = round(_bootstrap_database(db_path), 4)
            with DiskMonitor(output_dir) as disk_monitor:
                etl_sec, per_step, row_count = _run_production_etl(db_path)
            result.update({
                "etl_sec": round(etl_sec, 4),
                "per_step": per_step,
                "orders_count": row_count,
                "expected_orders_count": n_orders + 1,
                "peak_disk_bytes": disk_monitor.peak_bytes,
            })
            if row_count != n_orders + 1:
                raise AssertionError(
                    f"orders count mismatch: expected {n_orders + 1:,}, got {row_count:,}"
                )
            result["status"] = "passed"
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        result["total_sec"] = round(time.perf_counter() - started, 4)
        result["peak_rss_mb"] = round(_peak_rss_mb(), 2)
        result["host_memory_bytes"] = _host_memory_bytes()
        result["peak_disk_bytes"] = max(
            int(result.get("peak_disk_bytes", 0)), _directory_size(output_dir)
        )
        result["duckdb_bytes"] = db_path.stat().st_size if db_path.exists() else 0
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        render_report(output_dir.parent, report_path)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n_orders", "--n-orders", type=int, default=1_000_000)
    parser.add_argument("--output_dir", "--output-dir", type=Path)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--allow-50m", action="store_true")
    parser.add_argument("--generate-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = args.output_dir or PROJECT_ROOT / "data" / "benchmarks" / f"scale-{args.n_orders}"
    try:
        result = run_benchmark(
            args.n_orders,
            output_dir,
            args.report,
            force=args.force,
            allow_50m=args.allow_50m,
            generate_only=args.generate_only,
        )
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"passed", "generated_only"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
