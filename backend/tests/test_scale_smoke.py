from __future__ import annotations

import time
from pathlib import Path

import duckdb

from scripts.etl.benchmarks.generate_synthetic_orders import generate_synthetic_orders
from scripts.etl.benchmarks.run_scale_benchmark import run_benchmark


REQUIRED_COLUMNS = {
    "order_id",
    "sub_order_id",
    "user_id",
    "pay_time",
    "actual_amount",
    "is_member",
    "channel",
    "is_refund",
}


def test_generate_10k_orders_is_fast_and_production_shaped(tmp_path: Path) -> None:
    started = time.perf_counter()
    manifest = generate_synthetic_orders(10_000, tmp_path / "input")

    assert time.perf_counter() - started < 10
    assert manifest["n_orders"] == 10_000
    assert REQUIRED_COLUMNS.issubset(set(manifest["schema"]))

    conn = duckdb.connect()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM read_parquet(?)",
            [manifest["shop_parquet"]],
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 10_000


def test_benchmark_generate_only_writes_result_and_report(tmp_path: Path) -> None:
    run_dir = tmp_path / "scale-10000"
    report = tmp_path / "scale_report.md"

    result = run_benchmark(10_000, run_dir, report, generate_only=True)

    assert result["status"] == "generated_only"
    assert (run_dir / "result.json").is_file()
    assert report.is_file()
    assert "10,000" in report.read_text(encoding="utf-8")
