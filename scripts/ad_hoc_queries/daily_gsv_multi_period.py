"""daily_gsv_multi_period — Sprint 183 multi-period daily metrics query.

业务场景: 多周期 x 8 维度 (sample/member x GMV/GSV + new/old x users/GSV).

L4.5 exception: scripts/ad_hoc_queries/* 是 CLI 层, 允许 inline SQL,
但必须使用 ? DB-API 参数化并复用 _utils helpers.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from scripts.ad_hoc_queries._utils import read_only_conn, validate_date_window
from scripts.ad_hoc_queries.registry import QuerySpec, register


_METRIC_SQL = {
    "sample_gmv": """
        SUM(CASE WHEN o.channel IN ('U先派样', '百补派样')
                 AND o.is_goujinjin = FALSE
                 AND o.order_status != '交易关闭'
                 THEN o.actual_amount ELSE 0 END)
    """,
    "sample_gsv": """
        SUM(CASE WHEN o.channel IN ('U先派样', '百补派样')
                 AND o.is_goujinjin = FALSE
                 AND o.order_status != '交易关闭'
                 AND o.is_refund = FALSE
                 THEN o.actual_amount ELSE 0 END)
    """,
    "member_gmv": """
        SUM(CASE WHEN o.is_member = TRUE
                 AND o.is_goujinjin = FALSE
                 AND o.order_status != '交易关闭'
                 THEN o.actual_amount ELSE 0 END)
    """,
    "member_gsv": """
        SUM(CASE WHEN o.is_member = TRUE
                 AND o.is_goujinjin = FALSE
                 AND o.order_status != '交易关闭'
                 AND o.is_refund = FALSE
                 THEN o.actual_amount ELSE 0 END)
    """,
    "new_users": """
        COUNT(DISTINCT CASE WHEN ufp.first_pay_date > ?::DATE
                 AND o.is_goujinjin = FALSE
                 AND o.order_status != '交易关闭'
                 AND o.is_refund = FALSE
                 THEN o.user_id END)
    """,
    "new_gsv": """
        SUM(CASE WHEN ufp.first_pay_date > ?::DATE
                 AND o.is_goujinjin = FALSE
                 AND o.order_status != '交易关闭'
                 AND o.is_refund = FALSE
                 THEN o.actual_amount ELSE 0 END)
    """,
    "old_users": """
        COUNT(DISTINCT CASE WHEN ufp.first_pay_date <= ?::DATE
                 AND o.is_goujinjin = FALSE
                 AND o.order_status != '交易关闭'
                 AND o.is_refund = FALSE
                 THEN o.user_id END)
    """,
    "old_gsv": """
        SUM(CASE WHEN ufp.first_pay_date <= ?::DATE
                 AND o.is_goujinjin = FALSE
                 AND o.order_status != '交易关闭'
                 AND o.is_refund = FALSE
                 THEN o.actual_amount ELSE 0 END)
    """,
}

_HEADERS = [
    "period_label",
    "date",
    "sample_gmv",
    "sample_gsv",
    "member_gmv",
    "member_gsv",
    "new_users",
    "new_gsv",
    "old_users",
    "old_gsv",
]


def run_daily_gsv_multi_period(
    periods: list[tuple[str, str]],
    metrics: list[str],
) -> list[list[Any]]:
    """Run multi-period daily query and return wide daily rows."""
    if not periods:
        raise ValueError("periods 不能为空")
    if not metrics:
        raise ValueError("metrics 不能为空")
    invalid = [metric for metric in metrics if metric not in _METRIC_SQL]
    if invalid:
        raise ValueError(f"未知 metric: {invalid}; 可选 {list(_METRIC_SQL.keys())}")

    rows: list[list[Any]] = []
    with read_only_conn() as conn:
        for start_str, end_str in periods:
            validate_date_window(start_str, end_str)
            start_d = datetime.strptime(start_str, "%Y-%m-%d").date()
            end_d = datetime.strptime(end_str, "%Y-%m-%d").date()
            cutoff = start_d - timedelta(days=1)
            period_label = f"{start_str}至{end_str}"

            sql = f"""
                SELECT
                    CAST(o.pay_time AS DATE) AS date,
                    {_METRIC_SQL['sample_gmv']} AS sample_gmv,
                    {_METRIC_SQL['sample_gsv']} AS sample_gsv,
                    {_METRIC_SQL['member_gmv']} AS member_gmv,
                    {_METRIC_SQL['member_gsv']} AS member_gsv,
                    {_METRIC_SQL['new_users']} AS new_users,
                    {_METRIC_SQL['new_gsv']} AS new_gsv,
                    {_METRIC_SQL['old_users']} AS old_users,
                    {_METRIC_SQL['old_gsv']} AS old_gsv
                FROM orders o
                LEFT JOIN user_first_purchase ufp ON o.user_id = ufp.user_id
                WHERE o.pay_time >= ?::TIMESTAMP AND o.pay_time < ?::TIMESTAMP
                GROUP BY 1
                ORDER BY 1
            """
            cur_start_dt = f"{start_d} 00:00:00"
            cur_end_excl = f"{end_d + timedelta(days=1)} 00:00:00"
            params = [
                cutoff.isoformat(),
                cutoff.isoformat(),
                cutoff.isoformat(),
                cutoff.isoformat(),
                cur_start_dt,
                cur_end_excl,
            ]
            assert sql.count("?") == len(params), (
                f"placeholder mismatch: {sql.count('?')} vs {len(params)}"
            )

            metric_names = list(_METRIC_SQL.keys())
            for row in conn.execute(sql, params).fetchall():
                date_val = row[0]
                metric_values = dict(zip(metric_names, row[1:]))
                rows.append([
                    period_label,
                    str(date_val),
                    *[metric_values[metric] for metric in metrics],
                ])
    return rows


def _parse_period_pairs(raw_periods: list[str]) -> list[tuple[str, str]]:
    if len(raw_periods) % 2 != 0:
        raise ValueError("--periods 必须按 start end 成对传入")
    return list(zip(raw_periods[::2], raw_periods[1::2]))


_daily_gsv_multi_period_spec = QuerySpec(
    name="daily-gsv-multi-period",
    description=(
        "多周期 x 8 维度 daily rows: sample/member x GMV/GSV + "
        "new/old x users/GSV"
    ),
    args=[
        {
            "flags": ("--periods",),
            "required": True,
            "nargs": "+",
            "help": "多周期列表, start end 成对传入",
        },
        {
            "flags": ("--metrics",),
            "required": False,
            "nargs": "+",
            "default": None,
            "help": "metric 名列表, 默认全 8 个",
        },
        {
            "flags": ("--format",),
            "required": False,
            "default": "table",
            "choices": ["table", "csv", "xlsx"],
        },
        {"flags": ("--output", "-o"), "required": False, "default": None},
    ],
    headers=_HEADERS,
    run=lambda **kw: run_daily_gsv_multi_period(
        periods=_parse_period_pairs(kw["periods"]),
        metrics=kw.get("metrics") or list(_METRIC_SQL.keys()),
    ),
    business_tag="多周期8维度日指标",
    base_year_arg="periods",
)
register(_daily_gsv_multi_period_spec)
