#!/usr/bin/env python3
"""Build the L4.71 user_rfm_precompute table from orders."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

DEFAULT_DUCKDB_PATH = REPO_ROOT / "data" / "processed" / "fuqing_crm.duckdb"
TABLE_NAME = "user_rfm_precompute"
DEFAULT_LOOKBACK_DAYS = 3650


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def create_table_sql(table_name: str = TABLE_NAME) -> str:
    return f"""
CREATE TABLE IF NOT EXISTS {table_name} (
    as_of_date DATE NOT NULL,
    lookback_days INTEGER NOT NULL,
    user_id VARCHAR NOT NULL,
    last_pay_time TIMESTAMP,
    order_count BIGINT NOT NULL,
    gsv DOUBLE NOT NULL,
    is_member BOOLEAN NOT NULL,
    r_score INTEGER NOT NULL,
    f_score INTEGER NOT NULL,
    m_score INTEGER NOT NULL,
    r_interval VARCHAR NOT NULL,
    rfm_segment VARCHAR NOT NULL,
    updated_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (as_of_date, lookback_days, user_id)
);
"""


def index_sql(table_name: str = TABLE_NAME) -> str:
    return f"""
CREATE INDEX IF NOT EXISTS idx_{table_name}_date_segment
    ON {table_name} (as_of_date, lookback_days, rfm_segment);
CREATE INDEX IF NOT EXISTS idx_{table_name}_date_r_interval
    ON {table_name} (as_of_date, lookback_days, r_interval);
"""


def insert_sql(table_name: str = TABLE_NAME) -> str:
    return f"""
INSERT INTO {table_name} (
    as_of_date, lookback_days, user_id, last_pay_time, order_count, gsv,
    is_member, r_score, f_score, m_score, r_interval, rfm_segment
)
WITH user_stats AS (
    SELECT
        user_id,
        MAX(pay_time) AS last_pay_time,
        COUNT(DISTINCT order_id) AS order_count,
        COALESCE(SUM(actual_amount), 0) AS gsv,
        BOOL_OR(is_member) AS is_member
    FROM orders o
    WHERE o.pay_time >= ?::TIMESTAMP
      AND o.pay_time <= ?::TIMESTAMP
      AND o.is_goujinjin = FALSE
      AND o.order_status != '交易关闭'
      AND o.is_refund = FALSE
      AND o.user_id IS NOT NULL
    GROUP BY user_id
),
scored AS (
    SELECT
        user_id,
        last_pay_time,
        order_count,
        gsv,
        is_member,
        CASE
            WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < 30 THEN 5
            WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < 90 THEN 4
            WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < 180 THEN 3
            WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < 365 THEN 2
            ELSE 1
        END AS r_score,
        CASE
            WHEN order_count >= 5 THEN 5
            WHEN order_count >= 4 THEN 4
            WHEN order_count = 3 THEN 3
            WHEN order_count = 2 THEN 2
            ELSE 1
        END AS f_score,
        CASE
            WHEN gsv >= 1000 THEN 5
            WHEN gsv >= 500 THEN 4
            WHEN gsv >= 300 THEN 3
            WHEN gsv >= 100 THEN 2
            ELSE 1
        END AS m_score,
        CASE
            WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) BETWEEN 0 AND 30 THEN '近1个月已购客'
            WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) BETWEEN 31 AND 90 THEN '近2-3个月已购客'
            WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) BETWEEN 91 AND 180 THEN '近4-6月已购客'
            WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) BETWEEN 181 AND 365 THEN '近7-12个月已购客'
            WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) BETWEEN 366 AND 730 THEN '近13个月-近24个月已购客'
            ELSE '2年外已购客'
        END AS r_interval
    FROM user_stats
)
SELECT
    ?::DATE AS as_of_date,
    ?::INTEGER AS lookback_days,
    user_id,
    last_pay_time,
    order_count,
    gsv,
    is_member,
    r_score,
    f_score,
    m_score,
    r_interval,
    CASE
        WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN '重要价值客户'
        WHEN r_score < 4 AND f_score >= 4 AND m_score >= 4 THEN '重要保持客户'
        WHEN r_score >= 4 AND f_score < 4 AND m_score >= 4 THEN '重要发展客户'
        WHEN r_score < 4 AND f_score < 4 AND m_score >= 4 THEN '重要挽留客户'
        WHEN r_score >= 4 AND f_score >= 4 AND m_score < 4 THEN '一般价值客户'
        WHEN r_score < 4 AND f_score >= 4 AND m_score < 4 THEN '一般保持客户'
        WHEN r_score >= 4 AND f_score < 4 AND m_score < 4 THEN '一般发展客户'
        ELSE '一般挽留客户'
    END AS rfm_segment
FROM scored;
"""


def build_params(as_of_date: str, lookback_days: int) -> list[object]:
    reference = _parse_date(as_of_date)
    start = reference - timedelta(days=lookback_days)
    end = reference - timedelta(days=1)
    start_dt = f"{start.isoformat()} 00:00:00"
    end_dt = f"{end.isoformat()} 23:59:59.999999"
    cutoff_values = [as_of_date] * 9
    return [start_dt, end_dt, *cutoff_values, as_of_date, lookback_days]


def default_as_of_dates(today: date | None = None) -> list[str]:
    """Return the MTD current/YoY/prev2 history reference dates.

    RFM analysis classifies users from behavior before each period start. A
    daily no-arg run should therefore warm the three period starts that the
    default RFM request uses, not only today's date.
    """
    today = today or date.today()
    return [
        date(today.year, today.month, 1).isoformat(),
        date(today.year - 1, today.month, 1).isoformat(),
        date(today.year - 2, today.month, 1).isoformat(),
    ]


def rebuild_table(duckdb_path: Path, as_of_date: str, lookback_days: int, dry_run: bool = False) -> int:
    params = build_params(as_of_date, lookback_days)
    sql_parts = [
        create_table_sql(),
        index_sql(),
        f"DELETE FROM {TABLE_NAME} WHERE as_of_date = ?::DATE AND lookback_days = ?::INTEGER;",
        insert_sql(),
    ]
    if dry_run:
        print("\n".join(sql_parts))
        print(f"params={params}")
        return 0
    if not duckdb_path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {duckdb_path}")

    import duckdb

    conn = duckdb.connect(str(duckdb_path))
    try:
        conn.execute(create_table_sql())
        conn.execute(index_sql())
        conn.execute(f"DELETE FROM {TABLE_NAME} WHERE as_of_date = ?::DATE AND lookback_days = ?::INTEGER", [as_of_date, lookback_days])
        conn.execute(insert_sql(), params)
        conn.execute("CHECKPOINT")
        row = conn.execute(
            f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE as_of_date = ?::DATE AND lookback_days = ?::INTEGER",
            [as_of_date, lookback_days],
        ).fetchone()
    finally:
        conn.close()
    print(f"{TABLE_NAME} rebuilt for {as_of_date}/{lookback_days}d: {int(row[0] if row else 0):,} users")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb-path", type=Path, default=Path(os.environ.get("DUCKDB_PATH", DEFAULT_DUCKDB_PATH)))
    parser.add_argument("--as-of-date", default=os.environ.get("FQ_USER_RFM_AS_OF_DATE"))
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=int(os.environ.get("FQ_USER_RFM_LOOKBACK_DAYS", str(DEFAULT_LOOKBACK_DAYS))),
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        as_of_dates = [args.as_of_date] if args.as_of_date else default_as_of_dates()
        for as_of_date in as_of_dates:
            rc = rebuild_table(args.duckdb_path, as_of_date, args.lookback_days, args.dry_run)
            if rc != 0:
                return rc
        return 0
    except Exception as exc:
        print(f"[L4.71_USER_RFM] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
