"""Sprint 143 cohort retention matrix 计算."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from backend.semantic.filters import FilterBuilder


MAX_RETENTION_MONTHS = 12


@dataclass
class CohortRetentionRow:
    """单 cohort retention 矩阵行."""

    cohort_month: str
    cohort_size: int
    retention: Dict[int, float]


def _channel_filter(channel: str) -> List[str] | None:
    return None if channel == "全店" else [channel]


def compute_cohort_retention(
    conn,
    start_month: str,
    end_month: str,
    channel: str = "全店",
) -> List[CohortRetentionRow]:
    """计算按月 cohort 的 0-12 月留存矩阵."""
    cohort_fb = FilterBuilder().with_table_alias("o").with_channels(_channel_filter(channel))
    cohort_fb.add_extra("strftime(o.pay_time, '%Y-%m') <= ?", [end_month])
    cohort_where, cohort_params = cohort_fb.build()

    activity_fb = FilterBuilder().with_table_alias("o").with_channels(_channel_filter(channel))
    activity_where, activity_params = activity_fb.build()

    sql = f"""
        WITH cohort_users AS (
            SELECT
                o.user_id,
                strftime(MIN(o.pay_time), '%Y-%m') AS cohort_month
            FROM orders o
            WHERE {cohort_where}
              AND o.user_id IS NOT NULL
            GROUP BY o.user_id
            HAVING strftime(MIN(o.pay_time), '%Y-%m') BETWEEN ? AND ?
        ),
        cohort_sizes AS (
            SELECT cohort_month, COUNT(DISTINCT user_id) AS cohort_size
            FROM cohort_users
            GROUP BY cohort_month
        ),
        cohort_activity AS (
            SELECT
                cu.cohort_month,
                DATEDIFF(
                    'month',
                    CAST(cu.cohort_month || '-01' AS DATE),
                    CAST(strftime(o.pay_time, '%Y-%m') || '-01' AS DATE)
                ) AS month_offset,
                COUNT(DISTINCT cu.user_id) AS active_users
            FROM cohort_users cu
            JOIN orders o ON cu.user_id = o.user_id
            WHERE {activity_where}
            GROUP BY cu.cohort_month, month_offset
        )
        SELECT
            cs.cohort_month,
            cs.cohort_size,
            ca.month_offset,
            ca.active_users
        FROM cohort_sizes cs
        JOIN cohort_activity ca ON cs.cohort_month = ca.cohort_month
        WHERE ca.month_offset BETWEEN 0 AND {MAX_RETENTION_MONTHS}
        ORDER BY cs.cohort_month, ca.month_offset
    """
    params = [
        *cohort_params,
        start_month,
        end_month,
        *activity_params,
    ]
    assert sql.count("?") == len(params), "Sprint 143 cohort SQL params mismatch"
    rows = conn.execute(sql, params).fetchall()

    cohort_map: Dict[str, CohortRetentionRow] = {}
    for cohort_month, cohort_size, month_offset, active_users in rows:
        key = str(cohort_month)
        size = int(cohort_size or 0)
        if key not in cohort_map:
            cohort_map[key] = CohortRetentionRow(
                cohort_month=key,
                cohort_size=size,
                retention={},
            )
        if size > 0 and month_offset is not None:
            cohort_map[key].retention[int(month_offset)] = round(
                float(active_users or 0) / size,
                4,
            )

    return list(cohort_map.values())
