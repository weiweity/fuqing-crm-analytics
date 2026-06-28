"""Sprint 143 用户生命周期价值 (LTV) service."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from statistics import median
from typing import Dict, List

from backend.contracts.lifetime_value import LifetimeValueSummary
from backend.db.connection import get_connection
from backend.semantic.filters import FilterBuilder
from backend.semantic.lifetime_value import LTVResult, compute_ltv_for_user
from backend.services.rfm.cache import RfmQueryCache


LTV_CACHE_ENDPOINT = "ltv-v1"
LTV_SUMMARY_CACHE_ENDPOINT = "ltv-summary-v1"


def _read_ltv_cache(cache_key: dict) -> LTVResult | None:
    cached = RfmQueryCache().get(LTV_CACHE_ENDPOINT, cache_key)
    if not cached:
        return None
    return LTVResult(**cached)


def _write_ltv_cache(cache_key: dict, result: LTVResult) -> None:
    RfmQueryCache().set(LTV_CACHE_ENDPOINT, cache_key, asdict(result))


def get_user_ltv(
    user_id: str,
    cohort_date: str,
    use_cache: bool = True,
) -> LTVResult:
    """获取单用户 90/180/365 天 LTV."""
    cache_key = {"user_id": user_id, "cohort_date": cohort_date}
    if use_cache:
        cached = _read_ltv_cache(cache_key)
        if cached is not None:
            return cached

    conn = get_connection()
    result = compute_ltv_for_user(conn, user_id, cohort_date)
    if use_cache:
        _write_ltv_cache(cache_key, result)
    return result


def get_users_ltv_batch(
    user_ids: List[str],
    cohort_date: str,
    use_cache: bool = True,
) -> Dict[str, LTVResult]:
    """批量获取用户 LTV."""
    return {
        user_id: get_user_ltv(user_id, cohort_date, use_cache=use_cache)
        for user_id in user_ids
    }


def _cohort_user_ids(conn, cohort_date: str, channel: str = "全店") -> List[str]:
    fb = FilterBuilder().with_table_alias("o")
    if channel != "全店":
        fb.with_channels([channel])
    fb.add_extra("CAST(o.pay_time AS DATE) = ?::DATE", [cohort_date])
    where_sql, params = fb.build()
    sql = f"""
        SELECT DISTINCT o.user_id
        FROM orders o
        WHERE {where_sql}
          AND o.user_id IS NOT NULL
    """
    assert sql.count("?") == len(params), "Sprint 143 LTV cohort SQL params mismatch"
    rows = conn.execute(sql, params).fetchall()
    return [str(row[0]) for row in rows if row and row[0] is not None]


def _pct_change(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return round((current - previous) / abs(previous) * 100, 2)


def _summary_without_yoy(
    cohort_date: str,
    channel: str = "全店",
    use_cache: bool = True,
) -> LifetimeValueSummary:
    conn = get_connection()
    user_ids = _cohort_user_ids(conn, cohort_date, channel)
    results = list(get_users_ltv_batch(user_ids, cohort_date, use_cache=use_cache).values())
    user_count = len(results)

    gsv_90 = [r.gsv_90d for r in results]
    gsv_180 = [r.gsv_180d for r in results]
    gsv_365 = [r.gsv_365d for r in results]

    def avg(values: List[float]) -> float:
        return round(sum(values) / user_count, 2) if user_count else 0.0

    def med(values: List[float]) -> float:
        return round(float(median(values)), 2) if values else 0.0

    return LifetimeValueSummary(
        cohort_date=cohort_date,
        user_count=user_count,
        ltv_90d_avg=avg(gsv_90),
        ltv_180d_avg=avg(gsv_180),
        ltv_365d_avg=avg(gsv_365),
        ltv_90d_median=med(gsv_90),
        ltv_180d_median=med(gsv_180),
        ltv_365d_median=med(gsv_365),
        ltv_90d_yoy_pct=0.0,
        ltv_180d_yoy_pct=0.0,
        ltv_365d_yoy_pct=0.0,
    )


def get_lifetime_value_summary(
    cohort_date: str,
    channel: str = "全店",
    use_cache: bool = True,
) -> LifetimeValueSummary:
    """获取 cohort LTV 汇总，含去年同日 YoY."""
    cache_key = {"cohort_date": cohort_date, "channel": channel}
    cache = RfmQueryCache()
    if use_cache:
        cached = cache.get(LTV_SUMMARY_CACHE_ENDPOINT, cache_key)
        if cached:
            return LifetimeValueSummary(**cached)

    current = _summary_without_yoy(cohort_date, channel, use_cache=use_cache)
    cohort_dt = datetime.strptime(cohort_date, "%Y-%m-%d")
    previous_date = cohort_dt.replace(year=cohort_dt.year - 1).strftime("%Y-%m-%d")
    previous = _summary_without_yoy(previous_date, channel, use_cache=use_cache)

    summary = current.model_copy(update={
        "ltv_90d_yoy_pct": _pct_change(current.ltv_90d_avg, previous.ltv_90d_avg),
        "ltv_180d_yoy_pct": _pct_change(current.ltv_180d_avg, previous.ltv_180d_avg),
        "ltv_365d_yoy_pct": _pct_change(current.ltv_365d_avg, previous.ltv_365d_avg),
    })
    if use_cache:
        cache.set(LTV_SUMMARY_CACHE_ENDPOINT, cache_key, summary.model_dump())
    return summary
