"""L4.74 DuckDB to Parquet ETL regression tests."""
from __future__ import annotations

import plistlib
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.etl import duckdb_to_parquet_etl as parquet_etl  # noqa: E402


def test_export_sql_rejects_unsafe_table_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        parquet_etl.export_sql("orders;DROP", tmp_path / "x.parquet")


def test_export_tables_dry_run_builds_snapshot_paths(tmp_path: Path) -> None:
    result = parquet_etl.export_tables(
        duckdb_path=tmp_path / "missing.duckdb",
        output_dir=tmp_path / "out",
        tables=("orders", "user_rfm"),
        snapshot_date="2026-07-09",
        limit=100,
        dry_run=True,
    )

    assert len(result) == 2
    assert "snapshot_date=2026-07-09" in result[0]["path"]
    assert "LIMIT 100" in result[0]["sql"]
    assert "FORMAT PARQUET" in result[0]["sql"]


def test_duckdb_to_parquet_plist_uses_python3_not_bash() -> None:
    plist_path = ROOT / "scripts/launchd/com.fuqing.duckdb-to-parquet-etl.daily.plist"
    data = plistlib.loads(plist_path.read_bytes())
    args = data["ProgramArguments"]

    assert args[0].endswith("python3")
    assert all("bash" not in arg for arg in args)
    assert "duckdb_to_parquet_etl.py" in args[1]
