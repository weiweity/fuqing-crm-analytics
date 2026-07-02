#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按月汇总 2026H1 vs 2025H1 的 8 维度指标，输出 CSV（横向：指标为列）。

时间范围：2026-01-01 至 2026-06-30、2025-01-01 至 2025-06-30
月份：1月、2月、3月、4月、5月、6月
"""
import csv
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, "/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics")
from scripts.ad_hoc_queries._utils import build_take_path, read_only_conn

_SAMPLE_CHANNELS = ["U先派样", "百补派样"]

PERIODS: list[tuple[str, str, str]] = [
    ("2026-01-01", "2026-06-30", "Y26"),
    ("2025-01-01", "2025-06-30", "Y25"),
]

CSV_HEADER = [
    "周期",
    "月份",
    "小样GMV",
    "小样GSV",
    "会员GMV",
    "会员GSV",
    "新客人数",
    "新客GSV",
    "老客人数",
    "老客GSV",
]

SQL = """
WITH
order_month AS (
    SELECT
        EXTRACT(YEAR FROM pay_time)::INTEGER AS y,
        EXTRACT(MONTH FROM pay_time)::INTEGER AS m,
        user_id,
        actual_amount,
        is_refund,
        is_member,
        channel
    FROM orders
    WHERE pay_time >= ?::TIMESTAMP AND pay_time < ?::TIMESTAMP
      AND is_goujinjin = FALSE
      AND order_status != '交易关闭'
),
old_flag AS (
    SELECT
        om.y,
        om.m,
        om.user_id,
        om.actual_amount,
        om.is_refund,
        om.is_member,
        om.channel,
        CASE WHEN ufp.first_pay_date <= MAKE_DATE(om.y, om.m, 1) - INTERVAL 1 DAY THEN 1 ELSE 0 END AS is_old
    FROM order_month om
    LEFT JOIN user_first_purchase ufp ON om.user_id = ufp.user_id
)
SELECT
    y,
    m,
    SUM(CASE WHEN channel IN ({sample_ch_ph}) THEN actual_amount ELSE 0 END) AS sample_gmv,
    SUM(CASE WHEN channel IN ({sample_ch_ph}) AND is_refund = FALSE THEN actual_amount ELSE 0 END) AS sample_gsv,
    SUM(CASE WHEN is_member = TRUE THEN actual_amount ELSE 0 END) AS member_gmv,
    SUM(CASE WHEN is_member = TRUE AND is_refund = FALSE THEN actual_amount ELSE 0 END) AS member_gsv,
    COUNT(DISTINCT CASE WHEN is_old = 0 AND is_refund = FALSE THEN user_id END) AS new_users,
    SUM(CASE WHEN is_old = 0 AND is_refund = FALSE THEN actual_amount ELSE 0 END) AS new_gsv,
    COUNT(DISTINCT CASE WHEN is_old = 1 AND is_refund = FALSE THEN user_id END) AS old_users,
    SUM(CASE WHEN is_old = 1 AND is_refund = FALSE THEN actual_amount ELSE 0 END) AS old_gsv
FROM old_flag
GROUP BY y, m
ORDER BY y, m
"""


def _date_range(start: str, end: str) -> tuple[date, date]:
    return date.fromisoformat(start), date.fromisoformat(end)


def _run_period(start: str, end: str, label: str) -> list[list]:
    s, e = _date_range(start, end)
    start_dt = f"{s} 00:00:00"
    end_excl_dt = f"{e + timedelta(days=1)} 00:00:00"

    sample_ph = ",".join(["?"] * len(_SAMPLE_CHANNELS))
    sql = SQL.format(sample_ch_ph=sample_ph)
    params = [start_dt, end_excl_dt] + _SAMPLE_CHANNELS + _SAMPLE_CHANNELS

    rows: list[list] = []
    with read_only_conn() as conn:
        cur = conn.execute(sql, params)
        for row in cur.fetchall():
            y, m, sample_gmv, sample_gsv, member_gmv, member_gsv, new_users, new_gsv, old_users, old_gsv = row
            rows.append([
                label,
                f"{int(y)}年{int(m)}月",
                round(float(sample_gmv), 2),
                round(float(sample_gsv), 2),
                round(float(member_gmv), 2),
                round(float(member_gsv), 2),
                int(new_users),
                round(float(new_gsv), 2),
                int(old_users),
                round(float(old_gsv), 2),
            ])
    return rows


def main() -> None:
    today = datetime.now()
    base_year = 2026
    date_range = "H1月汇总"
    out_dir = build_take_path("H1月汇总", base_year, date_range, extension="csv").parent
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "monthly_segment_H1_comparison.csv"

    rows: list[list] = []
    for start, end, label in PERIODS:
        rows.extend(_run_period(start, end, label))

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        writer.writerows(rows)

    print(f"CSV: {csv_path} ({len(rows)} rows)")
    print(f"Output: {out_dir}")


if __name__ == "__main__":
    main()
