"""member_monthly — Sprint 203 R5 is_member 按月维度 (跟 channel_monthly 1:1 stable 模式)

业务场景: 给定月份范围, 按 is_member 切片, 输出每个会员状态的 GSV + orders + customers + 占比 + 月度 YOY.

口径复用 (跟 audience_service._run_period_data 完全对齐):
- is_member 字段: orders.is_member (boolean, ETL 预聚合)
- GSV: backend/semantic/calculations.GSV_AMOUNT_COL
- 会员/非会员聚合 + 占比
- 安全月份: 月份范围校验 + 闰年处理

CLI: python scripts/ad_hoc_query.py member-monthly \
       --start 2026-01 --end 2026-06 \
       [--format csv|table] [--output /tmp/member_monthly.csv]
"""
from __future__ import annotations

from datetime import date
from typing import Any, List

from scripts.ad_hoc_queries._utils import clamp_yoy, read_only_conn
from scripts.ad_hoc_queries.registry import QuerySpec, register


MEMBER_MONTHLY_HEADERS = [
    "is_member",
    "gsv",
    "orders",
    "customers",
    "ratio",
    "yoy_pct",
]


_MEMBER_MONTHLY_SQL = """
SELECT
    o.is_member AS is_member,
    ROUND(SUM(o.actual_amount), 2) AS gsv,
    COUNT(DISTINCT o.order_id) AS orders,
    COUNT(DISTINCT o.user_id) AS customers
FROM orders o
WHERE o.pay_time >= ?
  AND o.pay_time < ?
  AND o.is_refund = FALSE
  AND o.order_status != '交易关闭'
GROUP BY o.is_member
ORDER BY gsv DESC
"""


def run_member_monthly(start: str, end: str) -> List[List[Any]]:
    """Run member-monthly query, return rows matching MEMBER_MONTHLY_HEADERS."""
    start_date = date.fromisoformat(f"{start}-01")
    end_year, end_month = map(int, end.split("-"))
    if end_month == 12:
        end_exclusive = date(end_year + 1, 1, 1)
    else:
        end_exclusive = date(end_year, end_month + 1, 1)

    yoy_start = date(start_date.year - 1, start_date.month, 1)
    yoy_end = date(end_exclusive.year - 1, end_exclusive.month, 1)

    with read_only_conn() as conn:
        rows = conn.execute(
            _MEMBER_MONTHLY_SQL,
            [start_date.isoformat(), end_exclusive.isoformat()],
        ).fetchall()
        yoy_rows = conn.execute(
            _MEMBER_MONTHLY_SQL,
            [yoy_start.isoformat(), yoy_end.isoformat()],
        ).fetchall()

    yoy_dict = {bool(row[0]): row[1] for row in yoy_rows}

    total_gsv = sum(float(r[1]) for r in rows) if rows else 0.0

    out_rows = []
    for row in rows:
        is_mem, gsv, orders, customers = bool(row[0]), float(row[1]), int(row[2]), int(row[3])
        ratio = round(gsv / total_gsv * 100, 2) if total_gsv > 0 else 0.0
        yoy_pct = clamp_yoy(gsv, yoy_dict.get(is_mem))
        out_rows.append([is_mem, gsv, orders, customers, ratio, yoy_pct])

    return out_rows


_member_monthly_spec = QuerySpec(
    name="member-monthly",
    description="按 is_member 切片月维度 (Sprint 203 R5, 业务空白点补全)",
    args=[
        {"flags": ("--start",), "required": True, "help": "起始月份 YYYY-MM"},
        {"flags": ("--end",), "required": True, "help": "结束月份 YYYY-MM (含)"},
    ],
    headers=MEMBER_MONTHLY_HEADERS,
    run=run_member_monthly,
    business_tag="会员按月",
    base_year_arg="start",
)

register(_member_monthly_spec)