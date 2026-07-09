"""L4.71 user_rfm_precompute regression tests."""
from __future__ import annotations

import plistlib
import inspect
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.semantic.segments import R_INTERVALS  # noqa: E402
from scripts.etl import build_user_rfm_precompute_table as user_rfm  # noqa: E402


def test_user_rfm_insert_sql_parameter_count_matches_builder() -> None:
    sql = user_rfm.insert_sql()
    params = user_rfm.build_params("2026-07-09", 365)

    assert sql.count("?") == len(params)
    assert len(params) == 13


def test_user_rfm_build_params_excludes_as_of_day_from_history() -> None:
    params = user_rfm.build_params("2026-07-01", 3)

    assert params[0] == "2026-06-28 00:00:00"
    assert params[1] == "2026-06-30 23:59:59.999999"
    assert params[2:11] == ["2026-07-01"] * 9
    assert params[-2:] == ["2026-07-01", 3]


def test_user_rfm_default_lookback_covers_two_year_outer_bucket() -> None:
    assert user_rfm.DEFAULT_LOOKBACK_DAYS >= 731


def test_user_rfm_default_as_of_dates_cover_hot_period_starts() -> None:
    assert user_rfm.default_as_of_dates(date(2026, 7, 9)) == [
        "2023-07-09",
        "2024-01-01",
        "2024-01-10",
        "2024-04-10",
        "2024-07-01",
        "2024-07-09",
        "2025-01-01",
        "2025-01-10",
        "2025-04-10",
        "2025-07-01",
        "2025-07-09",
        "2026-01-01",
        "2026-01-10",
        "2026-04-10",
        "2026-07-01",
    ]


def test_user_rfm_sql_uses_verified_r_intervals() -> None:
    sql = user_rfm.insert_sql()

    for label, start, end in R_INTERVALS:
        assert label in sql
        if end < 99999:
            assert f"BETWEEN {start} AND {end}" in sql


def test_user_rfm_schema_is_incremental_not_drop_replace() -> None:
    create_sql = user_rfm.create_table_sql()
    insert_sql = user_rfm.insert_sql()

    assert "PRIMARY KEY (as_of_date, lookback_days, user_id)" in create_sql
    assert "CREATE OR REPLACE" not in create_sql.upper()
    assert "DROP TABLE" not in (create_sql + insert_sql).upper()
    rebuild_src = inspect.getsource(user_rfm.rebuild_table)
    assert "DELETE FROM {TABLE_NAME} WHERE as_of_date" in rebuild_src


def test_user_rfm_main_builds_default_hot_period_partitions(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, int]] = []

    def fake_rebuild(duckdb_path: Path, as_of_date: str, lookback_days: int, dry_run: bool = False) -> int:
        calls.append((as_of_date, lookback_days))
        return 0

    class FixedDate(date):
        @classmethod
        def today(cls) -> "FixedDate":
            return cls(2026, 7, 9)

    monkeypatch.setattr(user_rfm, "date", FixedDate)
    monkeypatch.setattr(user_rfm, "rebuild_table", fake_rebuild)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_user_rfm_precompute_table.py",
            "--duckdb-path",
            str(tmp_path / "missing.duckdb"),
        ],
    )

    assert user_rfm.main() == 0
    assert calls == [
        ("2023-07-09", user_rfm.DEFAULT_LOOKBACK_DAYS),
        ("2024-01-01", user_rfm.DEFAULT_LOOKBACK_DAYS),
        ("2024-01-10", user_rfm.DEFAULT_LOOKBACK_DAYS),
        ("2024-04-10", user_rfm.DEFAULT_LOOKBACK_DAYS),
        ("2024-07-01", user_rfm.DEFAULT_LOOKBACK_DAYS),
        ("2024-07-09", user_rfm.DEFAULT_LOOKBACK_DAYS),
        ("2025-01-01", user_rfm.DEFAULT_LOOKBACK_DAYS),
        ("2025-01-10", user_rfm.DEFAULT_LOOKBACK_DAYS),
        ("2025-04-10", user_rfm.DEFAULT_LOOKBACK_DAYS),
        ("2025-07-01", user_rfm.DEFAULT_LOOKBACK_DAYS),
        ("2025-07-09", user_rfm.DEFAULT_LOOKBACK_DAYS),
        ("2026-01-01", user_rfm.DEFAULT_LOOKBACK_DAYS),
        ("2026-01-10", user_rfm.DEFAULT_LOOKBACK_DAYS),
        ("2026-04-10", user_rfm.DEFAULT_LOOKBACK_DAYS),
        ("2026-07-01", user_rfm.DEFAULT_LOOKBACK_DAYS),
    ]


def test_user_rfm_precompute_plist_uses_python3_not_bash() -> None:
    plist_path = ROOT / "scripts/launchd/com.fuqing.build-user-rfm-precompute.daily.plist"
    data = plistlib.loads(plist_path.read_bytes())
    args = data["ProgramArguments"]

    assert args[0].endswith("python3")
    assert all("bash" not in arg for arg in args)
    assert "build_user_rfm_precompute_table.py" in args[1]
