"""RFM cache reads and writes must use the same isolated cache database."""
from __future__ import annotations

import threading
import time

import duckdb

from backend import config
from backend.services import dual_conn
from backend.services.health.rfm_analysis import cache


def test_cache_write_is_read_back_from_cache_db_not_business_conn(tmp_path, monkeypatch):
    cache_path = tmp_path / "rfm-cache.duckdb"
    monkeypatch.setattr(config, "CACHE_DUCKDB_PATH", str(cache_path))
    dual_conn.close_all_connections()
    business_conn = duckdb.connect(":memory:")

    try:
        expected = {"rows": [{"segment": "重要价值客户", "users": 3}]}
        cache._write_db_cache(
            "MTD",
            "2026-07-01",
            "2026-07-10",
            None,
            "GSV",
            None,
            "2026-07-10 23:59:59",
            expected,
            orders_count=10,
        )

        tables = business_conn.execute(
            "SELECT table_name FROM duckdb_tables() WHERE table_name = ?",
            [cache.RFM_CACHE_TABLE],
        ).fetchall()
        assert tables == []
        actual = cache._read_db_cache(
            "MTD",
            "2026-07-01",
            "2026-07-10",
            None,
            "GSV",
            None,
            "2026-07-10 23:59:59",
            business_conn,
            current_orders_count=10,
        )
        assert actual == expected
    finally:
        business_conn.close()
        dual_conn.close_all_connections()


def test_cache_operations_serialize_shared_raw_connection(monkeypatch):
    overlap_detected = False
    active = 0
    state_lock = threading.Lock()

    class DetectingConnection:
        def execute(self, *_args, **_kwargs):
            nonlocal active, overlap_detected
            with state_lock:
                active += 1
                overlap_detected = overlap_detected or active > 1
            time.sleep(0.005)
            with state_lock:
                active -= 1
            return self

    fake_conn = DetectingConnection()
    monkeypatch.setattr(cache, "_get_cache_conn", lambda: fake_conn)

    threads = [
        threading.Thread(
            target=cache._write_db_cache,
            args=("MTD", f"2026-07-0{index}", "2026-07-10", None, "GSV", None, "v1", {"rows": []}),
        )
        for index in range(1, 5)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)

    assert all(not thread.is_alive() for thread in threads)
    assert overlap_detected is False
