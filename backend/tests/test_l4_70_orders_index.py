"""L4.70 orders(pay_time, user_id) index regression tests."""
from __future__ import annotations

import plistlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.etl import add_orders_pay_time_user_id_index as add_index  # noqa: E402


def test_orders_pay_time_user_id_index_sql_is_idempotent() -> None:
    sql = (ROOT / "scripts/etl/add_orders_pay_time_user_id_index.sql").read_text(encoding="utf-8")

    assert "CREATE INDEX IF NOT EXISTS idx_orders_pay_time_user_id" in sql
    assert "ON orders (pay_time, user_id)" in sql
    assert "DROP" not in sql.upper()


def test_add_orders_index_dry_run_does_not_require_duckdb(tmp_path: Path, capsys) -> None:
    sql_path = tmp_path / "index.sql"
    sql_path.write_text(
        "CREATE INDEX IF NOT EXISTS idx_orders_pay_time_user_id ON orders (pay_time, user_id);",
        encoding="utf-8",
    )

    rc = add_index.apply_index(tmp_path / "missing.duckdb", sql_path, dry_run=True)
    out = capsys.readouterr().out

    assert rc == 0
    assert "idx_orders_pay_time_user_id" in out


def test_add_orders_index_plist_is_one_shot_python3() -> None:
    plist_path = ROOT / "scripts/launchd/com.fuqing.add-orders-index.one-shot.plist"
    data = plistlib.loads(plist_path.read_bytes())
    args = data["ProgramArguments"]

    assert data["RunAtLoad"] is True
    assert args[0].endswith("python3")
    assert all("bash" not in arg for arg in args)
    assert "add_orders_pay_time_user_id_index.py" in args[1]
