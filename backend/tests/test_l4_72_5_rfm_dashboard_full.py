"""L4.72.5 RFM dashboard-full precompute regression tests."""
from __future__ import annotations

from datetime import date, timedelta

import duckdb

from backend.services.health.rfm_analysis import period
from scripts.etl import build_rfm_dashboard_full_table as builder


def test_rfm_dashboard_full_table_constant() -> None:
    assert period.RFM_DASHBOARD_FULL_TABLE == "rfm_dashboard_full"


def test_resolve_period_type_hot_ranges_with_data_lag_end() -> None:
    today = date(2026, 7, 9)

    assert period._resolve_period_type(
        "2026-07-01 00:00:00",
        "2026-07-07 23:59:59",
        today=today,
    ) == "MTD"
    assert period._resolve_period_type(
        "2026-01-01 00:00:00",
        "2026-07-07 23:59:59",
        today=today,
    ) == "YTD"
    assert period._resolve_period_type(
        "2026-04-10 00:00:00",
        "2026-07-07 23:59:59",
        today=today,
    ) == "last90days"
    assert period._resolve_period_type(
        "2026-01-10 00:00:00",
        "2026-07-07 23:59:59",
        today=today,
    ) == "last180days"
    assert period._resolve_period_type(
        "2025-07-09 00:00:00",
        "2026-07-07 23:59:59",
        today=today,
    ) == "last365days"


def test_default_period_targets_match_handoff_shape() -> None:
    targets = builder.default_period_targets(date(2026, 7, 9), date(2026, 7, 7))

    assert len(targets) == 15
    assert builder.PeriodTarget("last90days", "2026-04-10", "2026-07-07") in targets
    assert builder.PeriodTarget("last180days", "2026-01-10", "2026-07-07") in targets
    assert builder.PeriodTarget("last365days", "2025-07-09", "2026-07-07") in targets


def test_run_rfm_period_dashboard_full_fallback_on_miss() -> None:
    conn = duckdb.connect(":memory:")
    try:
        result = period._run_rfm_period_dashboard_full(
            conn,
            "2026-07-01 00:00:00",
            "2026-07-07 23:59:59",
            None,
            "GSV",
            None,
        )
    finally:
        conn.close()

    assert result is None


def test_run_rfm_period_dashboard_full_hit() -> None:
    today = date.today()
    request_end = today - timedelta(days=1)
    start = date(today.year, today.month, 1)
    conn = duckdb.connect(":memory:")
    try:
        conn.execute("""
            CREATE TABLE rfm_dashboard_full (
                period_type VARCHAR,
                as_of_date DATE,
                end_date DATE,
                lookback_days INTEGER,
                mode VARCHAR,
                rfm_segment VARCHAR,
                hist_users BIGINT,
                repurchase_users BIGINT,
                repurchase_rate DOUBLE,
                repurchase_gsv DOUBLE,
                repurchase_gsv_ratio DOUBLE,
                updated_at TIMESTAMP
            )
        """)
        conn.execute(
            """
            INSERT INTO rfm_dashboard_full VALUES
            ('MTD', ?::DATE, ?::DATE, 3650, 'all', '重要价值客户', 2, 1, 0.5, 100.0, 1.0, now())
            """,
            [start.isoformat(), request_end.isoformat()],
        )

        all_result, same_result, member_all, member_same = period._run_rfm_period_dashboard_full(
            conn,
            f"{start.isoformat()} 00:00:00",
            f"{request_end.isoformat()} 23:59:59",
            None,
            "GSV",
            None,
        )
    finally:
        conn.close()

    assert all_result["重要价值客户"]["hist_users"] == 2
    assert all_result["重要价值客户"]["repurchase_users"] == 1
    assert all_result["重要价值客户"]["repurchase_gsv"] == 100.0
    assert same_result["重要价值客户"]["hist_users"] == 0
    assert member_all["重要价值客户"]["hist_users"] == 0
    assert member_same["重要价值客户"]["hist_users"] == 0


def test_rebuild_period_inserts_36_rows_from_user_rfm_precompute() -> None:
    conn = duckdb.connect(":memory:")
    try:
        conn.execute("""
            CREATE TABLE orders (
                order_id VARCHAR,
                user_id VARCHAR,
                pay_time TIMESTAMP,
                actual_amount DOUBLE,
                order_status VARCHAR,
                is_goujinjin BOOLEAN,
                is_refund BOOLEAN
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
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("o1", "u1", "2026-07-05 10:00:00", 100.0, "交易成功", False, False),
                ("o2", "u3", "2026-07-06 10:00:00", 80.0, "交易成功", False, False),
            ],
        )

        count = builder.rebuild_period(
            conn,
            builder.PeriodTarget("MTD", "2026-07-01", "2026-07-07"),
            3650,
        )
        row = conn.execute(
            "SELECT COUNT(*) FROM rfm_dashboard_full WHERE period_type = 'MTD'"
        ).fetchone()
    finally:
        conn.close()

    assert count == 36
    assert row[0] == 36
