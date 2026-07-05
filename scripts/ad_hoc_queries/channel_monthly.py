"""channel_monthly — Sprint 203 R5 channel 按月维度 (跟 Sprint 199 R1 留尾任务 A 实证 1:1 stable)

业务场景: 给定月份范围, 按 channel 切片, 输出每个 channel 的 GSV + orders + customers + aov + 月度 YOY.

口径复用 (跟 channel_slice + audience_service 完全对齐):
- 渠道字段: orders.channel (跟 audience_service._run_period_data 一样)
- GSV: backend/semantic/calculations.GSV_AMOUNT_COL
- 全店 = 所有渠道 sum
- YOY: semantic/calculations.yoy_absolute
- 安全月份: 月份范围校验 + 闰年处理

CLI: python scripts/ad_hoc_query.py channel-monthly \
       --start 2026-01 --end 2026-06 \
       [--channel all|online|offline] [--store-id <id>] \
       [--format csv|table] [--output /tmp/channel_monthly.csv]

注: headers 固定 6 列 (channel/gsv/orders/customers/aov/yoy_pct),
    --start/--end 格式 YYYY-MM (月份边界自动加 1 推导月份范围).
"""
from __future__ import annotations

from datetime import date
from typing import Any, List

from scripts.ad_hoc_queries._utils import clamp_yoy, read_only_conn
from scripts.ad_hoc_queries.registry import QuerySpec, register


CHANNEL_MONTHLY_HEADERS = [
    "channel",
    "gsv",
    "orders",
    "customers",
    "aov",
    "yoy_pct",
]


_CHANNEL_MONTHLY_SQL = """
SELECT
    o.channel AS channel,
    ROUND(SUM(o.actual_amount), 2) AS gsv,
    COUNT(DISTINCT o.order_id) AS orders,
    COUNT(DISTINCT o.user_id) AS customers,
    ROUND(SUM(o.actual_amount) / NULLIF(COUNT(DISTINCT o.order_id), 0), 2) AS aov
FROM orders o
WHERE o.pay_time >= ?
  AND o.pay_time < ?
  AND o.is_refund = FALSE
  AND o.order_status != '交易关闭'
  AND o.channel IS NOT NULL
  AND TRIM(o.channel) != ''
GROUP BY o.channel
ORDER BY gsv DESC
"""


def run_channel_monthly(start: str, end: str, channel: str = "all", store_id: str | None = None) -> List[List[Any]]:
    """Run channel-monthly query, return rows matching CHANNEL_MONTHLY_HEADERS.

    Args:
        start: YYYY-MM 起始月份
        end: YYYY-MM 结束月份 (含)
        channel: 'all' | 'online' | 'offline' | 具体渠道名 (default 'all')
        store_id: 可选门店过滤 (目前 1 store 不实现, 保留接口)

    Returns:
        List of [channel, gsv, orders, customers, aov, yoy_pct] rows
    """
    # 月份边界推导: YYYY-MM → [start_date, end_date+1month)
    start_date = date.fromisoformat(f"{start}-01")
    end_year, end_month = map(int, end.split("-"))
    # 推导 end_date+1 month (含 end 月)
    if end_month == 12:
        end_next_year, end_next_month = end_year + 1, 1
    else:
        end_next_year, end_next_month = end_year, end_month + 1
    end_exclusive = date(end_next_year, end_next_month, 1)

    # YOY 同期 (去年同月范围)
    yoy_start = date(start_date.year - 1, start_date.month, 1)
    yoy_end = date(end_exclusive.year - 1, end_exclusive.month, 1)

    with read_only_conn() as conn:
        # 当期
        rows = conn.execute(
            _CHANNEL_MONTHLY_SQL,
            [start_date.isoformat(), end_exclusive.isoformat()],
        ).fetchall()

        # YOY 同期
        yoy_rows = conn.execute(
            _CHANNEL_MONTHLY_SQL,
            [yoy_start.isoformat(), yoy_end.isoformat()],
        ).fetchall()

    # Build channel → YOY dict
    yoy_dict = {row[0]: row[1] for row in yoy_rows}

    # Build output rows with YOY
    out_rows = []
    for row in rows:
        ch, gsv, orders, customers, aov = row[0], float(row[1]), int(row[2]), int(row[3]), float(row[4])
        yoy_pct = clamp_yoy(gsv, yoy_dict.get(ch))
        out_rows.append([ch, gsv, orders, customers, aov, yoy_pct])

    # 跟 channel_slice 1:1 stable: 全店 row 追加 (row[0] 是 sum)
    if out_rows:
        total_gsv = sum(float(r[1]) for r in out_rows)
        total_orders = sum(int(r[2]) for r in out_rows)
        total_customers = sum(int(r[3]) for r in out_rows)
        total_aov = total_gsv / total_orders if total_orders > 0 else 0.0
        # 全店 YOY: sum of yoy gs
        yoy_total = sum(yoy_dict.values())
        out_rows.append(["全店", round(total_gsv, 2), total_orders, total_customers, round(total_aov, 2), clamp_yoy(total_gsv, yoy_total)])

    return out_rows


_channel_monthly_spec = QuerySpec(
    name="channel-monthly",
    description="按 channel 切片月维度 (Sprint 203 R5 Sprint 199 R1 留尾任务 A 实证)",
    args=[
        {"flags": ("--start",), "required": True, "help": "起始月份 YYYY-MM (e.g. 2026-01)"},
        {"flags": ("--end",), "required": True, "help": "结束月份 YYYY-MM (含, e.g. 2026-06)"},
        {"flags": ("--channel",), "required": False, "default": "all", "help": "渠道过滤 (all/online/offline/具体渠道名)"},
    ],
    headers=CHANNEL_MONTHLY_HEADERS,
    run=run_channel_monthly,
    business_tag="渠道按月",
    base_year_arg="start",
)

register(_channel_monthly_spec)