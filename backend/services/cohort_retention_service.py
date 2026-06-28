"""Sprint 143 cohort retention matrix service."""

from __future__ import annotations

from dataclasses import asdict
from typing import List

from backend.db.connection import get_connection
from backend.semantic.cohort_retention import CohortRetentionRow, compute_cohort_retention
from backend.services.rfm.cache import RfmQueryCache


COHORT_RETENTION_CACHE_ENDPOINT = "cohort-retention-v1"


def _rows_from_cache(cached: list[dict]) -> List[CohortRetentionRow]:
    return [
        CohortRetentionRow(
            cohort_month=str(row["cohort_month"]),
            cohort_size=int(row["cohort_size"]),
            retention={int(k): float(v) for k, v in row.get("retention", {}).items()},
        )
        for row in cached
    ]


def _read_cohort_cache(cache_key: dict) -> List[CohortRetentionRow] | None:
    cached = RfmQueryCache().get(COHORT_RETENTION_CACHE_ENDPOINT, cache_key)
    if not cached:
        return None
    return _rows_from_cache(cached)


def _write_cohort_cache(cache_key: dict, result: List[CohortRetentionRow]) -> None:
    RfmQueryCache().set(
        COHORT_RETENTION_CACHE_ENDPOINT,
        cache_key,
        [asdict(row) for row in result],
    )


def get_cohort_retention_matrix(
    start_month: str,
    end_month: str,
    channel: str = "全店",
    use_cache: bool = True,
) -> List[CohortRetentionRow]:
    """获取 cohort retention matrix."""
    cache_key = {
        "start_month": start_month,
        "end_month": end_month,
        "channel": channel,
    }
    if use_cache:
        cached = _read_cohort_cache(cache_key)
        if cached is not None:
            return cached

    conn = get_connection()
    result = compute_cohort_retention(conn, start_month, end_month, channel)
    if use_cache:
        _write_cohort_cache(cache_key, result)
    return result
