"""Sprint 143 用户生命周期价值 (LTV) 计算."""

from __future__ import annotations

from dataclasses import dataclass

from backend.semantic.filters import FilterBuilder


LTV_WINDOWS = [90, 180, 365]


@dataclass
class LTVResult:
    """单用户 LTV 计算结果."""

    user_id: str
    cohort_date: str
    gsv_90d: float
    gsv_180d: float
    gsv_365d: float
    order_count_90d: int
    order_count_180d: int
    order_count_365d: int


def compute_ltv_for_user(conn, user_id: str, cohort_date: str) -> LTVResult:
    """计算单个用户从 cohort_date 次日起 90/180/365 天累计 GSV."""
    fb = FilterBuilder().with_table_alias("o")
    fb.add_extra("o.user_id = ?", [user_id])
    valid_sql, valid_params = fb.build()

    sql = f"""
        SELECT
            ? AS user_id,
            ?::DATE AS cohort_date,
            COALESCE(SUM(CASE
                WHEN DATEDIFF('day', ?::DATE, o.pay_time) BETWEEN 1 AND 90
                THEN o.actual_amount ELSE 0 END), 0) AS gsv_90d,
            COALESCE(SUM(CASE
                WHEN DATEDIFF('day', ?::DATE, o.pay_time) BETWEEN 1 AND 180
                THEN o.actual_amount ELSE 0 END), 0) AS gsv_180d,
            COALESCE(SUM(CASE
                WHEN DATEDIFF('day', ?::DATE, o.pay_time) BETWEEN 1 AND 365
                THEN o.actual_amount ELSE 0 END), 0) AS gsv_365d,
            COUNT(DISTINCT CASE
                WHEN DATEDIFF('day', ?::DATE, o.pay_time) BETWEEN 1 AND 90
                THEN o.order_id END) AS order_count_90d,
            COUNT(DISTINCT CASE
                WHEN DATEDIFF('day', ?::DATE, o.pay_time) BETWEEN 1 AND 180
                THEN o.order_id END) AS order_count_180d,
            COUNT(DISTINCT CASE
                WHEN DATEDIFF('day', ?::DATE, o.pay_time) BETWEEN 1 AND 365
                THEN o.order_id END) AS order_count_365d
        FROM orders o
        WHERE {valid_sql}
    """
    params = [
        user_id,
        cohort_date,
        cohort_date,
        cohort_date,
        cohort_date,
        cohort_date,
        cohort_date,
        cohort_date,
        *valid_params,
    ]
    assert sql.count("?") == len(params), "Sprint 143 LTV SQL params mismatch"

    row = conn.execute(sql, params).fetchone()
    if not row:
        return LTVResult(
            user_id=user_id,
            cohort_date=cohort_date,
            gsv_90d=0.0,
            gsv_180d=0.0,
            gsv_365d=0.0,
            order_count_90d=0,
            order_count_180d=0,
            order_count_365d=0,
        )

    return LTVResult(
        user_id=str(row[0]),
        cohort_date=str(row[1]),
        gsv_90d=float(row[2] or 0),
        gsv_180d=float(row[3] or 0),
        gsv_365d=float(row[4] or 0),
        order_count_90d=int(row[5] or 0),
        order_count_180d=int(row[6] or 0),
        order_count_365d=int(row[7] or 0),
    )
