"""L4.71 RFM user_rfm_precompute fast-path regression tests."""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.services.health.rfm_analysis import period  # noqa: E402


def _seed_conn() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    conn.execute("""
        CREATE TABLE orders (
            order_id VARCHAR,
            user_id VARCHAR,
            pay_time TIMESTAMP,
            actual_amount DOUBLE,
            order_status VARCHAR,
            is_goujinjin BOOLEAN,
            is_refund BOOLEAN,
            is_member BOOLEAN,
            channel VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE user_rfm_precompute (
            as_of_date DATE,
            lookback_days INTEGER,
            user_id VARCHAR,
            rfm_segment VARCHAR,
            is_member BOOLEAN
        )
    """)
    conn.executemany(
        "INSERT INTO user_rfm_precompute VALUES (?, ?, ?, ?, ?)",
        [
            ("2026-07-01", 3650, "u1", "重要价值客户", True),
            ("2026-07-01", 3650, "u2", "一般挽留客户", False),
        ],
    )
    conn.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("o1", "u1", "2026-07-05 10:00:00", 100.0, "交易成功", False, False, True, "直播"),
            ("o2", "u3", "2026-07-06 10:00:00", 80.0, "交易成功", False, False, False, "直播"),
        ],
    )
    return conn


def test_rfm_period_uses_user_rfm_precompute_when_partition_matches() -> None:
    conn = _seed_conn()
    try:
        all_result, same_result, member_result, member_same = period._run_rfm_period(
            conn,
            "2026-07-01 00:00:00",
            "2026-07-31 23:59:59",
            "2026-06-30",
            None,
            "GSV",
            None,
        )
    finally:
        conn.close()

    assert all_result["重要价值客户"]["hist_users"] == 1
    assert all_result["重要价值客户"]["repurchase_users"] == 1
    assert all_result["重要价值客户"]["repurchase_gsv"] == 100.0
    assert all_result["重要价值客户"]["repurchase_gsv_ratio"] == 1.0
    assert all_result["已购客TTL"]["hist_users"] == 2
    assert all_result["已购客TTL"]["repurchase_users"] == 1
    assert all_result["已购客TTL"]["repurchase_gsv"] == 100.0
    assert same_result == all_result
    assert member_result["已购客TTL"]["hist_users"] == 1
    assert member_same == member_result


def test_rfm_period_falls_back_when_precompute_table_missing(monkeypatch) -> None:
    called = {"live": False}

    def fake_live(conn, start_dt, end_dt, cutoff_dt, channel, metric_type, exclude_channels):
        called["live"] = True
        return ("live",)

    class MissingPrecomputeConn:
        def execute(self, *args, **kwargs):
            raise RuntimeError("no user_rfm_precompute")

    monkeypatch.setattr(period, "_run_rfm_period_live", fake_live)

    assert period._run_rfm_period(
        MissingPrecomputeConn(),
        "2026-07-01 00:00:00",
        "2026-07-31 23:59:59",
        "2026-06-30",
        None,
        "GSV",
        None,
    ) == ("live",)
    assert called["live"] is True


def test_rfm_period_falls_back_for_channel_or_exclude_filters(monkeypatch) -> None:
    called = {"live": 0}

    def fake_live(conn, start_dt, end_dt, cutoff_dt, channel, metric_type, exclude_channels):
        called["live"] += 1
        return ("live",)

    class NoFastPathConn:
        def execute(self, *args, **kwargs):
            raise AssertionError("unsupported params must not query user_rfm_precompute")

    monkeypatch.setattr(period, "_run_rfm_period_live", fake_live)

    assert period._run_rfm_period(
        NoFastPathConn(),
        "2026-07-01 00:00:00",
        "2026-07-31 23:59:59",
        "2026-06-30",
        "直播",
        "GSV",
        None,
    ) == ("live",)
    assert period._run_rfm_period(
        NoFastPathConn(),
        "2026-07-01 00:00:00",
        "2026-07-31 23:59:59",
        "2026-06-30",
        None,
        "GSV",
        ["低价"],
    ) == ("live",)
    assert called["live"] == 2
