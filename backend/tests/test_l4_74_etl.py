"""L4.74 DuckDB to Parquet ETL regression tests."""
from __future__ import annotations

import json
import plistlib
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.etl import duckdb_to_parquet_etl as parquet_etl  # noqa: E402
from scripts.etl import validate_dual_write_consistency as dual_write  # noqa: E402


def test_export_sql_rejects_unsafe_table_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        parquet_etl.export_sql("orders;DROP", tmp_path / "x.parquet")


def test_export_sql_rejects_negative_limit(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        parquet_etl.export_sql("orders", tmp_path / "x.parquet", limit=-1)


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


def test_export_tables_rejects_unsafe_snapshot_date(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        parquet_etl.export_tables(
            duckdb_path=tmp_path / "missing.duckdb",
            output_dir=tmp_path / "out",
            tables=("orders",),
            snapshot_date="2026-07-09';DROP TABLE orders;--",
            dry_run=True,
        )


def test_export_tables_dry_run_writes_manifest(tmp_path: Path) -> None:
    manifest_file = tmp_path / "manifest" / "snapshot.json"

    result = parquet_etl.export_tables(
        duckdb_path=tmp_path / "missing.duckdb",
        output_dir=tmp_path / "out",
        tables=("orders",),
        snapshot_date="2026-07-09",
        dry_run=True,
        manifest_file=manifest_file,
    )

    payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert payload["snapshot_date"] == "2026-07-09"
    assert payload["dry_run"] is True
    assert payload["results"] == result
    assert payload["results"][0]["status"] == "dry_run"


def test_export_tables_real_export_counts_parquet_rows(tmp_path: Path) -> None:
    duckdb = pytest.importorskip("duckdb")
    db_path = tmp_path / "mini.duckdb"
    manifest_file = tmp_path / "out" / "_manifest" / "snapshot.json"

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE orders(user_id INTEGER, actual_amount DOUBLE, pay_time TIMESTAMP)")
        conn.execute(
            """
            INSERT INTO orders VALUES
                (1, 10.5, TIMESTAMP '2026-07-09 10:00:00'),
                (2, 20.0, TIMESTAMP '2026-07-09 11:00:00')
            """
        )
    finally:
        conn.close()

    result = parquet_etl.export_tables(
        duckdb_path=db_path,
        output_dir=tmp_path / "out",
        tables=("orders",),
        snapshot_date="2026-07-09",
        limit=1,
        manifest_file=manifest_file,
    )

    assert result[0]["source_rows"] == 1
    assert result[0]["exported_rows"] == 1
    assert result[0]["bytes"] > 0
    assert result[0]["status"] == "ok"
    assert not (tmp_path / "out" / "_staging").exists()
    assert json.loads(manifest_file.read_text(encoding="utf-8"))["dry_run"] is False


def test_export_tables_rejects_row_count_mismatch_before_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duckdb = pytest.importorskip("duckdb")
    db_path = tmp_path / "mini.duckdb"
    db_path.touch()
    output_dir = tmp_path / "out"

    class FakeConnection:
        def __init__(self) -> None:
            self._row = (0,)

        def execute(self, sql: str, params: list[str] | None = None) -> "FakeConnection":
            if "FROM read_parquet" in sql:
                self._row = (1,)
            elif sql.startswith("SELECT COUNT(*)"):
                self._row = (2,)
            return self

        def fetchone(self) -> tuple[int]:
            return self._row

        def close(self) -> None:
            pass

    monkeypatch.setattr(duckdb, "connect", lambda *args, **kwargs: FakeConnection())

    with pytest.raises(ValueError, match="Parquet row mismatch"):
        parquet_etl.export_tables(
            duckdb_path=db_path,
            output_dir=output_dir,
            tables=("orders",),
            snapshot_date="2026-07-09",
        )

    assert not (output_dir / "orders" / "snapshot_date=2026-07-09" / "part-000.parquet").exists()
    assert not (output_dir / "_staging").exists()


def test_dual_write_validator_dry_run_exposes_duckdb_and_postgres_sql(tmp_path: Path) -> None:
    payload = dual_write.run_validation(
        duckdb_path=tmp_path / "missing.duckdb",
        postgres_dsn="postgresql://example",
        snapshot_date="2026-07-09",
        dry_run=True,
    )

    assert payload["dry_run"] is True
    assert len(payload["queries"]) == 3
    assert "DATE(pay_time)" in payload["queries"][0]["duckdb_sql"]
    assert "pay_time::date" in payload["queries"][0]["postgres_sql"]
    assert "DOUBLE PRECISION" in payload["queries"][0]["postgres_sql"]
    assert "GROUP BY rfm_segment" in payload["queries"][1]["duckdb_sql"]
    assert tuple(payload["queries"][1]["key_columns"]) == ("rfm_segment",)
    assert "GROUP BY r_interval" in payload["queries"][2]["duckdb_sql"]
    assert tuple(payload["queries"][2]["key_columns"]) == ("r_interval",)


def test_dual_write_validator_rejects_unsafe_snapshot_date(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        dual_write.run_validation(
            duckdb_path=tmp_path / "missing.duckdb",
            postgres_dsn="postgresql://example",
            snapshot_date="2026-07-09';DROP TABLE orders;--",
            dry_run=True,
        )


def test_dual_write_compare_metric_respects_tolerance() -> None:
    ok = dual_write.compare_metric(100.0, 100.05, tolerance_ratio=0.001)
    fail = dual_write.compare_metric(100.0, 101.0, tolerance_ratio=0.001)

    assert ok["ok"] is True
    assert fail["ok"] is False


def test_dual_write_grouped_compare_catches_bucket_swaps() -> None:
    query = dual_write.ConsistencyQuery(
        name="rfm_segment_distribution",
        duckdb_sql="",
        postgres_sql="",
        tolerance_ratio=0.0,
        key_columns=("rfm_segment",),
    )

    result = dual_write.compare_query_rows(
        query,
        [
            {"rfm_segment": "重要价值客户", "row_count": 10.0},
            {"rfm_segment": "一般挽留客户", "row_count": 5.0},
        ],
        [
            {"rfm_segment": "重要价值客户", "row_count": 5.0},
            {"rfm_segment": "一般挽留客户", "row_count": 10.0},
        ],
    )

    assert result["ok"] is False
    assert result["rows"][0]["comparisons"]["row_count"]["ok"] is False


def test_dual_write_grouped_compare_rejects_empty_snapshots() -> None:
    query = dual_write.ConsistencyQuery(
        name="rfm_segment_distribution",
        duckdb_sql="",
        postgres_sql="",
        tolerance_ratio=0.0,
        key_columns=("rfm_segment",),
    )

    result = dual_write.compare_query_rows(query, [], [])

    assert result["ok"] is False
    assert result["error"] == "both sources returned no rows"


def test_dual_write_single_row_compare_rejects_zero_row_count_snapshot() -> None:
    query = dual_write.ConsistencyQuery(
        name="orders_daily",
        duckdb_sql="",
        postgres_sql="",
        tolerance_ratio=0.001,
    )

    result = dual_write.compare_query_rows(
        query,
        [{"row_count": 0.0, "distinct_users": 0.0, "amount_sum": 0.0}],
        [{"row_count": 0.0, "distinct_users": 0.0, "amount_sum": 0.0}],
    )

    assert result["ok"] is False
    assert result["non_empty_check"]["ok"] is False


def test_duckdb_to_parquet_plist_uses_python3_not_bash() -> None:
    plist_path = ROOT / "scripts/launchd/com.fuqing.duckdb-to-parquet-etl.daily.plist"
    data = plistlib.loads(plist_path.read_bytes())
    args = data["ProgramArguments"]

    assert args[0].endswith("python3")
    assert all("bash" not in arg for arg in args)
    assert "duckdb_to_parquet_etl.py" in args[1]
