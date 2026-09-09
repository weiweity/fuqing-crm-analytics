"""Computation must use only the supplied database, including in fresh processes."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import duckdb
import pytest


ROOT = Path(__file__).resolve().parents[2]
CHILD = """
import json
import sys
import types
from datetime import date
from pathlib import Path
import duckdb
from backend.services.metrics.competition_compute import compute_competition_metrics
from backend.services.rfm.as_of import compute_rfm_as_of

if sys.argv[3] == 'loaded':
    module = types.ModuleType('unrelated_fixture_consumer')
    module.FIXTURES = Path(sys.argv[2])
    sys.modules[module.__name__] = module
conn = duckdb.connect(sys.argv[1], read_only=sys.argv[4] == 'readonly')
try:
    result = compute_competition_metrics(
        conn, start_date='2026-09-01', end_date='2026-09-21',
        today=date(2026, 9, 22), as_of='2026-09-21', sample_mode='INCLUDE',
    )
    rfm = compute_rfm_as_of(conn, as_of='2026-09-21')
    tables = conn.execute('SHOW TABLES').fetchall()
    print(json.dumps({'metrics': result, 'rfm': rfm, 'tables': tables}, sort_keys=True))
finally:
    conn.close()
"""


@pytest.mark.parametrize("dated_refunds", [False, True])
@pytest.mark.parametrize("read_only", [False, True])
def test_loaded_fixture_module_cannot_change_computation(tmp_path, dated_refunds, read_only):
    database = tmp_path / "synthetic.duckdb"
    with duckdb.connect(str(database)) as conn:
        conn.execute("""
            CREATE TABLE orders AS SELECT
                'O-ISOLATED' AS order_id, 'S1' AS sub_order_id, 'U1' AS user_id,
                TIMESTAMP '2026-09-16 12:00:00' AS pay_time, 'CH_RETAIL' AS channel,
                100.0::DOUBLE AS actual_amount, NULL::BOOLEAN AS is_member,
                FALSE AS is_refund, FALSE AS is_goujinjin,
                '交易成功' AS order_status, 'P1' AS product_id, '正装' AS spu_type
        """)
        if dated_refunds:
            conn.execute("""
                CREATE TABLE refunds AS SELECT 'O-ISOLATED' AS order_id,
                    DATE '2026-09-18' AS refunded_at, 15.0::DOUBLE AS amount
            """)
    # Deliberately conflicting external fixture: never an input to computation.
    (tmp_path / "t02_t03_orders.json").write_text(json.dumps({
        "orders": [{"order_id": "O-ISOLATED", "refunds": [
            {"refunded_at": "2026-09-18", "amount": 27.0},
        ]}],
    }), encoding="utf-8")
    results = []
    for loaded in ("absent", "loaded"):
        process = subprocess.run(
            [sys.executable, "-c", CHILD, str(database), str(tmp_path), loaded,
             "readonly" if read_only else "writable"],
            cwd=tmp_path, env={**os.environ, "PYTHONPATH": str(ROOT),
                               "PYTHON_DOTENV_DISABLED": "1"},
            capture_output=True, text=True, timeout=30, check=True,
        )
        results.append(json.loads(process.stdout))
    assert results[0] == results[1]
    expected = 85.0 if dated_refunds else 100.0
    assert results[1]["metrics"]["gsv"] == expected
    assert results[1]["rfm"]["U1"]["m"] == expected
    assert results[1]["tables"] == ([["orders"], ["refunds"]] if dated_refunds else [["orders"]])
    with duckdb.connect(str(database), read_only=True) as conn:
        assert conn.execute("SELECT actual_amount FROM orders").fetchone() == (100.0,)
        if dated_refunds:
            assert conn.execute("SELECT amount FROM refunds").fetchall() == [(15.0,)]
