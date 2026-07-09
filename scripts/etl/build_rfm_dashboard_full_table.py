#!/usr/bin/env python3
"""Build the L4.72.5 rfm_dashboard_full table from user_rfm_precompute."""
from __future__ import annotations

import argparse
import os
import sys
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backend.semantic.channels import CHANNEL_ORDER  # noqa: E402
from backend.semantic.filters import VALID_ORDER_BASE  # noqa: E402
from backend.services.health.rfm_analysis._shared import RFM_SEGMENT_ORDER  # noqa: E402

DEFAULT_DUCKDB_PATH = REPO_ROOT / "data" / "processed" / "fuqing_crm.duckdb"
TABLE_NAME = "rfm_dashboard_full"
USER_RFM_PRECOMPUTE_TABLE = "user_rfm_precompute"
DEFAULT_LOOKBACK_DAYS = 3650
HOT_PERIOD_TYPES = ("MTD", "YTD", "last90days", "last180days", "last365days")
DEFAULT_CHANNELS = ("全店", *CHANNEL_ORDER)
LOW_PRICE_CHANNELS = ("U先派样", "百补派样", "赠品&0.01", "其他")
DEFAULT_EXCLUDE_CHANNELS = ("", "LOW_PRICE_CHANNELS")


@dataclass(frozen=True)
class PeriodTarget:
    period_type: str
    as_of_date: str
    end_date: str


@dataclass(frozen=True)
class ExtendedTarget:
    period_type: str
    as_of_date: str
    end_date: str
    channel: str
    exclude_label: str
    lookback_days: int


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _shift_year(value: date, years_back: int) -> date:
    year = value.year - years_back
    day = min(value.day, monthrange(year, value.month)[1])
    return date(year, value.month, day)


def create_table_sql(table_name: str = TABLE_NAME) -> str:
    return f"""
CREATE TABLE IF NOT EXISTS {table_name} (
    period_type VARCHAR NOT NULL,
    as_of_date DATE NOT NULL,
    end_date DATE NOT NULL,
    lookback_days INTEGER NOT NULL,
    mode VARCHAR NOT NULL,
    rfm_segment VARCHAR NOT NULL,
    hist_users BIGINT NOT NULL,
    repurchase_users BIGINT NOT NULL,
    repurchase_rate DOUBLE NOT NULL,
    repurchase_gsv DOUBLE NOT NULL,
    repurchase_gsv_ratio DOUBLE NOT NULL,
    updated_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (period_type, as_of_date, end_date, lookback_days, mode, rfm_segment)
);
"""


def index_sql(table_name: str = TABLE_NAME) -> str:
    return f"""
CREATE INDEX IF NOT EXISTS idx_{table_name}_period
    ON {table_name} (period_type, as_of_date, end_date, lookback_days);
CREATE INDEX IF NOT EXISTS idx_{table_name}_updated
    ON {table_name} (updated_at);
"""


def _segment_values_sql() -> str:
    escaped_segments = [seg.replace("'", "''") for seg in RFM_SEGMENT_ORDER]
    values = ",\n        ".join(f"('{seg}')" for seg in escaped_segments)
    return f"VALUES\n        {values}"


def insert_sql(table_name: str = TABLE_NAME) -> str:
    segment_values = _segment_values_sql()
    return f"""
INSERT INTO {table_name} (
    period_type, as_of_date, end_date, lookback_days, mode, rfm_segment,
    hist_users, repurchase_users, repurchase_rate, repurchase_gsv,
    repurchase_gsv_ratio, updated_at
)
WITH
period_base AS (
    SELECT
        ?::VARCHAR AS period_type,
        ?::DATE AS as_of_date,
        ?::DATE AS end_date,
        ?::INTEGER AS lookback_days
),
segments(rfm_segment) AS (
    {segment_values}
),
hist AS (
    SELECT u.user_id, u.rfm_segment, u.is_member
    FROM {USER_RFM_PRECOMPUTE_TABLE} u, period_base p
    WHERE u.as_of_date = p.as_of_date
      AND u.lookback_days = p.lookback_days
),
hist_count AS (
    SELECT COUNT(*) AS users FROM hist
),
base_orders AS (
    SELECT o.user_id, o.actual_amount
    FROM orders o, period_base p
    WHERE o.pay_time >= p.as_of_date::TIMESTAMP
      AND o.pay_time <= (p.end_date::TIMESTAMP + INTERVAL '23 hours 59 minutes 59 seconds')
      AND {VALID_ORDER_BASE}
      AND o.is_refund = FALSE
      AND o.user_id IS NOT NULL
),
repurchase_amounts AS (
    SELECT bo.user_id, SUM(bo.actual_amount) AS repurchase_gsv
    FROM base_orders bo
    GROUP BY bo.user_id
),
segment_stats_all_raw AS (
    SELECT h.rfm_segment,
           COUNT(DISTINCT h.user_id) AS hist_users,
           COUNT(DISTINCT ra.user_id) AS repurchase_users,
           COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
    FROM hist h
    LEFT JOIN repurchase_amounts ra ON h.user_id = ra.user_id
    GROUP BY h.rfm_segment
),
segment_stats_all AS (
    SELECT s.rfm_segment,
           COALESCE(r.hist_users, 0) AS hist_users,
           COALESCE(r.repurchase_users, 0) AS repurchase_users,
           COALESCE(r.repurchase_gsv, 0) AS repurchase_gsv
    FROM segments s
    LEFT JOIN segment_stats_all_raw r ON s.rfm_segment = r.rfm_segment
    WHERE s.rfm_segment != '已购客TTL'
),
member_stats_all_raw AS (
    SELECT h.rfm_segment,
           COUNT(DISTINCT h.user_id) AS hist_users,
           COUNT(DISTINCT ra.user_id) AS repurchase_users,
           COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
    FROM hist h
    LEFT JOIN repurchase_amounts ra ON h.user_id = ra.user_id
    WHERE h.is_member = TRUE
    GROUP BY h.rfm_segment
),
member_stats_all AS (
    SELECT s.rfm_segment,
           COALESCE(r.hist_users, 0) AS hist_users,
           COALESCE(r.repurchase_users, 0) AS repurchase_users,
           COALESCE(r.repurchase_gsv, 0) AS repurchase_gsv
    FROM segments s
    LEFT JOIN member_stats_all_raw r ON s.rfm_segment = r.rfm_segment
    WHERE s.rfm_segment != '已购客TTL'
),
ttl_stats_all AS (
    SELECT '已购客TTL' AS rfm_segment,
           (SELECT COUNT(*) FROM hist) AS hist_users,
           COUNT(DISTINCT h.user_id) AS repurchase_users,
           COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
    FROM hist h
    LEFT JOIN repurchase_amounts ra ON h.user_id = ra.user_id
    WHERE ra.user_id IS NOT NULL
),
member_ttl_stats_all AS (
    SELECT '已购客TTL' AS rfm_segment,
           (SELECT COUNT(*) FROM hist WHERE is_member = TRUE) AS hist_users,
           COUNT(DISTINCT h.user_id) AS repurchase_users,
           COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
    FROM hist h
    LEFT JOIN repurchase_amounts ra ON h.user_id = ra.user_id
    WHERE h.is_member = TRUE
      AND ra.user_id IS NOT NULL
),
mode_rows AS (
    SELECT 'all' AS mode, * FROM segment_stats_all
    UNION ALL SELECT 'all' AS mode, * FROM ttl_stats_all
    UNION ALL SELECT 'same' AS mode, * FROM segment_stats_all
    UNION ALL SELECT 'same' AS mode, * FROM ttl_stats_all
    UNION ALL SELECT 'member_all' AS mode, * FROM member_stats_all
    UNION ALL SELECT 'member_all' AS mode, * FROM member_ttl_stats_all
    UNION ALL SELECT 'member_same' AS mode, * FROM member_stats_all
    UNION ALL SELECT 'member_same' AS mode, * FROM member_ttl_stats_all
),
ratio_rows AS (
    SELECT
        mode,
        rfm_segment,
        hist_users,
        repurchase_users,
        repurchase_gsv,
        SUM(
            CASE WHEN rfm_segment != '已购客TTL' THEN repurchase_gsv ELSE 0 END
        ) OVER (PARTITION BY mode) AS mode_gsv
    FROM mode_rows
)
SELECT
    p.period_type,
    p.as_of_date,
    p.end_date,
    p.lookback_days,
    r.mode,
    r.rfm_segment,
    r.hist_users,
    r.repurchase_users,
    CASE
        WHEN r.hist_users > 0 THEN ROUND(r.repurchase_users::DOUBLE / r.hist_users::DOUBLE, 4)
        ELSE 0.0
    END AS repurchase_rate,
    r.repurchase_gsv,
    CASE
        WHEN r.rfm_segment = '已购客TTL' THEN 1.0
        WHEN r.mode_gsv > 0 THEN ROUND(r.repurchase_gsv / r.mode_gsv, 4)
        ELSE 0.0
    END AS repurchase_gsv_ratio,
    now() AS updated_at
FROM period_base p, ratio_rows r, hist_count hc
WHERE hc.users > 0;
"""


def max_orders_date(conn) -> date | None:
    row = conn.execute("SELECT MAX(pay_time)::DATE FROM orders").fetchone()
    if not row or row[0] is None:
        return None
    if isinstance(row[0], date):
        return row[0]
    return _parse_date(str(row[0])[:10])


def default_period_targets(today: date, available_end_date: date | None = None) -> list[PeriodTarget]:
    reference_end = today - timedelta(days=1)
    end_date = min(reference_end, available_end_date) if available_end_date else reference_end
    current_starts = [
        ("MTD", date(today.year, today.month, 1)),
        ("YTD", date(today.year, 1, 1)),
        ("last90days", reference_end - timedelta(days=89)),
        ("last180days", reference_end - timedelta(days=179)),
        ("last365days", reference_end - timedelta(days=364)),
    ]
    targets: list[PeriodTarget] = []
    for period_type, start in current_starts:
        for years_back in (0, 1, 2):
            shifted_start = _shift_year(start, years_back)
            shifted_end = _shift_year(end_date, years_back)
            if shifted_start <= shifted_end:
                targets.append(PeriodTarget(period_type, shifted_start.isoformat(), shifted_end.isoformat()))
    return targets


def get_full_extended_targets(today: date | None = None) -> list[tuple[str, str, str, str, int]]:
    """Plan L4.72.6 hot RFM dashboard combinations without mutating the table schema.

    Returns `(period_type, as_of_date, channel, exclude_label, lookback_days)` tuples.
    The current build table has no channel/exclude dimensions, so this is a planner
    for the next schema-aware materialization step rather than write-path behavior.
    """

    reference_today = today or date.today()
    targets = default_period_targets(reference_today)
    planned: list[tuple[str, str, str, str, int]] = []
    for target in targets:
        for channel in DEFAULT_CHANNELS:
            for exclude_label in DEFAULT_EXCLUDE_CHANNELS:
                planned.append(
                    (
                        target.period_type,
                        target.as_of_date,
                        channel,
                        exclude_label,
                        DEFAULT_LOOKBACK_DAYS,
                    )
                )
    return planned


def get_full_extended_target_objects(today: date | None = None) -> list[ExtendedTarget]:
    """Typed companion to `get_full_extended_targets` for future ETL wiring."""

    reference_today = today or date.today()
    targets = default_period_targets(reference_today)
    planned: list[ExtendedTarget] = []
    for target in targets:
        for channel in DEFAULT_CHANNELS:
            for exclude_label in DEFAULT_EXCLUDE_CHANNELS:
                planned.append(
                    ExtendedTarget(
                        period_type=target.period_type,
                        as_of_date=target.as_of_date,
                        end_date=target.end_date,
                        channel=channel,
                        exclude_label=exclude_label,
                        lookback_days=DEFAULT_LOOKBACK_DAYS,
                    )
                )
    return planned


def rebuild_period(conn, target: PeriodTarget, lookback_days: int, dry_run: bool = False) -> int:
    params = [target.period_type, target.as_of_date, target.end_date, lookback_days]
    if dry_run:
        print(create_table_sql())
        print(index_sql())
        print(insert_sql())
        print(f"params={params}")
        return 0

    conn.execute(create_table_sql())
    conn.execute(index_sql())
    conn.execute(
        f"""
        DELETE FROM {TABLE_NAME}
        WHERE period_type = ?::VARCHAR
          AND as_of_date = ?::DATE
          AND end_date = ?::DATE
          AND lookback_days = ?::INTEGER
        """,
        params,
    )
    conn.execute(insert_sql(), params)
    row = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM {TABLE_NAME}
        WHERE period_type = ?::VARCHAR
          AND as_of_date = ?::DATE
          AND end_date = ?::DATE
          AND lookback_days = ?::INTEGER
        """,
        params,
    ).fetchone()
    count = int(row[0] if row else 0)
    print(
        f"{TABLE_NAME} rebuilt for {target.period_type} "
        f"{target.as_of_date}..{target.end_date}/{lookback_days}d: {count} rows"
    )
    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb-path", type=Path, default=Path(os.environ.get("DUCKDB_PATH", DEFAULT_DUCKDB_PATH)))
    parser.add_argument("--period-type", choices=HOT_PERIOD_TYPES)
    parser.add_argument("--as-of-date")
    parser.add_argument("--end-date")
    parser.add_argument("--today", help="Reference today for default hot-period starts, YYYY-MM-DD")
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=int(os.environ.get("FQ_RFM_DASHBOARD_FULL_LOOKBACK_DAYS", str(DEFAULT_LOOKBACK_DAYS))),
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _explicit_targets(args: argparse.Namespace) -> list[PeriodTarget] | None:
    if args.as_of_date or args.end_date:
        if not (args.period_type and args.as_of_date and args.end_date):
            raise ValueError("--period-type, --as-of-date, and --end-date must be provided together")
        return [PeriodTarget(args.period_type, args.as_of_date, args.end_date)]
    return None


def main() -> int:
    args = parse_args()
    try:
        explicit = _explicit_targets(args)
        today = _parse_date(args.today) if args.today else date.today()

        if args.dry_run:
            targets = explicit or default_period_targets(today)
            if args.period_type and explicit is None:
                targets = [target for target in targets if target.period_type == args.period_type]
            for target in targets:
                rebuild_period(None, target, args.lookback_days, dry_run=True)
            return 0

        if not args.duckdb_path.exists():
            raise FileNotFoundError(f"DuckDB file not found: {args.duckdb_path}")

        import duckdb

        conn = duckdb.connect(str(args.duckdb_path))
        try:
            available_end = max_orders_date(conn)
            targets = explicit or default_period_targets(today, available_end)
            if args.period_type and explicit is None:
                targets = [target for target in targets if target.period_type == args.period_type]

            total_rows = 0
            for target in targets:
                total_rows += rebuild_period(conn, target, args.lookback_days)
            conn.execute("CHECKPOINT")
        finally:
            conn.close()

        print(f"{TABLE_NAME} rebuild complete: {len(targets)} targets, {total_rows} rows")
        return 0
    except Exception as exc:
        print(f"[L4.72.5_RFM_DASHBOARD_FULL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
