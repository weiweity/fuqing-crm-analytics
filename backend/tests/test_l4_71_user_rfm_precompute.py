"""L4.71 user_rfm_precompute regression tests."""
from __future__ import annotations

import plistlib
import inspect
import sys
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


def test_user_rfm_precompute_plist_uses_python3_not_bash() -> None:
    plist_path = ROOT / "scripts/launchd/com.fuqing.build-user-rfm-precompute.daily.plist"
    data = plistlib.loads(plist_path.read_bytes())
    args = data["ProgramArguments"]

    assert args[0].endswith("python3")
    assert all("bash" not in arg for arg in args)
    assert "build_user_rfm_precompute_table.py" in args[1]
