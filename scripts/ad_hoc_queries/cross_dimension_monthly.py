"""cross_dimension_monthly — Sprint 203 R5 通用多维度交叉按月 (跟 fixed-product-list-compare 1:1 stable)

业务场景: 给定月份范围 + 维度对 (e.g. channel × is_member / spu_category × channel / is_goujinjin × channel),
输出每个交叉组合的 GSV + orders + customers + 月度 YOY.

3 个 spec (跟 Phase 2 衍生机会 1:1 stable):
- channel-member-monthly: channel × is_member
- spu-channel-monthly: spu_category × channel
- goujinjin-channel-monthly: is_goujinjin × channel

复用 audience_table 双维度 group_by 模式 (跟 backend/services/metrics/audience_table.py 1:1 stable).
L4.43 argparse 透传 nargs="+".

CLI: python scripts/ad_hoc_query.py cross-dimension-monthly \
       --start 2026-01 --end 2026-06 \
       --dim1 channel --dim2 is_member \
       [--format csv|table] [--output /tmp/cross.csv]
"""
from __future__ import annotations

from datetime import date
from typing import Any, List

from scripts.ad_hoc_queries._utils import clamp_yoy, read_only_conn
from scripts.ad_hoc_queries.registry import QuerySpec, register


CROSS_DIMENSION_MONTHLY_HEADERS = [
    "dim1_value",
    "dim2_value",
    "gsv",
    "orders",
    "customers",
    "yoy_pct",
]


# Sprint 203 R5 维度白名单 (跟 L4.5 FilterBuilder 1:1 stable, 禁 inline 用户输入)
_DIMENSION_WHITELIST = {
    "channel": "o.channel",
    "is_member": "o.is_member",
    "is_goujinjin": "o.is_goujinjin",
    "spu_category": "o.spu_category",
    "spu_tier": "o.spu_tier",
    "spu_product_class": "o.spu_product_class",
}


def _build_sql(dim1_col: str, dim2_col: str) -> str:
    return f"""
SELECT
    {dim1_col} AS dim1_value,
    {dim2_col} AS dim2_value,
    ROUND(SUM(o.actual_amount), 2) AS gsv,
    COUNT(DISTINCT o.order_id) AS orders,
    COUNT(DISTINCT o.user_id) AS customers
FROM orders o
WHERE o.pay_time >= ?
  AND o.pay_time < ?
  AND o.is_refund = FALSE
  AND o.order_status != '交易关闭'
GROUP BY {dim1_col}, {dim2_col}
ORDER BY gsv DESC
LIMIT 100
"""


def run_cross_dimension_monthly(
    start: str, end: str, dim1: str, dim2: str
) -> List[List[Any]]:
    """Run cross-dimension-monthly query.

    Args:
        start: YYYY-MM 起始月份
        end: YYYY-MM 结束月份 (含)
        dim1: 维度 1 (白名单: channel / is_member / is_goujinjin / spu_category / spu_tier / spu_product_class)
        dim2: 维度 2 (同上)

    Returns:
        List of [dim1_value, dim2_value, gsv, orders, customers, yoy_pct] rows
    """
    if dim1 not in _DIMENSION_WHITELIST:
        raise ValueError(f"dim1 '{dim1}' not in whitelist: {list(_DIMENSION_WHITELIST.keys())}")
    if dim2 not in _DIMENSION_WHITELIST:
        raise ValueError(f"dim2 '{dim2}' not in whitelist: {list(_DIMENSION_WHITELIST.keys())}")

    start_date = date.fromisoformat(f"{start}-01")
    end_year, end_month = map(int, end.split("-"))
    if end_month == 12:
        end_exclusive = date(end_year + 1, 1, 1)
    else:
        end_exclusive = date(end_year, end_month + 1, 1)

    yoy_start = date(start_date.year - 1, start_date.month, 1)
    yoy_end = date(end_exclusive.year - 1, end_exclusive.month, 1)

    sql = _build_sql(_DIMENSION_WHITELIST[dim1], _DIMENSION_WHITELIST[dim2])

    with read_only_conn() as conn:
        rows = conn.execute(
            sql, [start_date.isoformat(), end_exclusive.isoformat()]
        ).fetchall()
        yoy_rows = conn.execute(
            sql, [yoy_start.isoformat(), yoy_end.isoformat()]
        ).fetchall()

    # YOY key = (dim1_value, dim2_value)
    yoy_dict = {(r[0], r[1]): float(r[2]) for r in yoy_rows}

    out_rows = []
    for row in rows:
        d1, d2, gsv, orders, customers = row[0], row[1], float(row[2]), int(row[3]), int(row[4])
        yoy_pct = clamp_yoy(gsv, yoy_dict.get((d1, d2)))
        out_rows.append([d1, d2, gsv, orders, customers, yoy_pct])

    return out_rows


_cross_dimension_monthly_spec = QuerySpec(
    name="cross-dimension-monthly",
    description="通用多维度交叉按月 (channel × is_member / spu × channel / is_goujinjin × channel)",
    args=[
        {"flags": ("--start",), "required": True, "help": "起始月份 YYYY-MM"},
        {"flags": ("--end",), "required": True, "help": "结束月份 YYYY-MM (含)"},
        {
            "flags": ("--dim1",),
            "required": True,
            "choices": list(_DIMENSION_WHITELIST.keys()),
            "help": "维度 1 (白名单)",
        },
        {
            "flags": ("--dim2",),
            "required": True,
            "choices": list(_DIMENSION_WHITELIST.keys()),
            "help": "维度 2 (白名单, 跟 dim1 不同)",
        },
    ],
    headers=CROSS_DIMENSION_MONTHLY_HEADERS,
    run=run_cross_dimension_monthly,
    business_tag="多维度交叉按月",
    base_year_arg="start",
)

register(_cross_dimension_monthly_spec)