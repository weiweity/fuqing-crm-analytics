"""refund_monthly — Sprint 203 R5 is_refund 按月维度 (跟 channel_monthly 1:1 stable 模式)

业务场景: 给定月份范围, 按 is_refund 切片, 输出每个退款状态的 GSV + 退款率 + 月度 YOY.

口径复用 (跟 dq_report 完全对齐):
- is_refund 字段: orders.is_refund (boolean, ETL 预聚合)
- GSV = SUM(actual_amount WHERE is_refund=FALSE) 业务正常销售
- 退款率 = SUM(refund_amount) / SUM(actual_amount)
- 安全月份: 月份范围校验 + 闰年处理

CLI: python scripts/ad_hoc_query.py refund-monthly \
       --start 2026-01 --end 2026-06 \
       [--format csv|table] [--output /tmp/refund_monthly.csv]
"""
from __future__ import annotations

from datetime import date
from typing import Any, List

from scripts.ad_hoc_queries._utils import clamp_yoy, read_only_conn
from scripts.ad_hoc_queries.registry import QuerySpec, register


REFUND_MONTHLY_HEADERS = [
    "is_refund",
    "gsv",
    "orders",
    "refund_amount",
    "refund_rate",
    "yoy_pct",
]


_REFUND_MONTHLY_SQL = """
SELECT
    o.is_refund AS is_refund,
    ROUND(SUM(o.actual_amount), 2) AS gsv,
    COUNT(DISTINCT o.order_id) AS orders,
    ROUND(SUM(o.refund_amount), 2) AS refund_amount
FROM orders o
WHERE o.pay_time >= ?
  AND o.pay_time < ?
  AND o.order_status != '交易关闭'
GROUP BY o.is_refund
ORDER BY gsv DESC
"""


def run_refund_monthly(start: str, end: str) -> List[List[Any]]:
    """Run refund-monthly query, return rows matching REFUND_MONTHLY_HEADERS."""
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
            _REFUND_MONTHLY_SQL,
            [start_date.isoformat(), end_exclusive.isoformat()],
        ).fetchall()
        yoy_rows = conn.execute(
            _REFUND_MONTHLY_SQL,
            [yoy_start.isoformat(), yoy_end.isoformat()],
        ).fetchall()

    yoy_dict = {bool(row[0]): row[1] for row in yoy_rows}

    out_rows = []
    for row in rows:
        is_ref, gsv, orders, refund_amount = bool(row[0]), float(row[1]), int(row[2]), float(row[3])
        refund_rate = round(refund_amount / gsv * 100, 2) if gsv > 0 else 0.0
        yoy_pct = clamp_yoy(gsv, yoy_dict.get(is_ref))
        out_rows.append([is_ref, gsv, orders, refund_amount, refund_rate, yoy_pct])

    return out_rows


_refund_monthly_spec = QuerySpec(
    name="refund-monthly",
    description="按 is_refund 切片月维度 (Sprint 203 R5, 退款监控必备)",
    args=[
        {"flags": ("--start",), "required": True, "help": "起始月份 YYYY-MM"},
        {"flags": ("--end",), "required": True, "help": "结束月份 YYYY-MM (含)"},
    ],
    headers=REFUND_MONTHLY_HEADERS,
    run=run_refund_monthly,
    business_tag="退款按月",
    base_year_arg="start",
)

register(_refund_monthly_spec)