"""
RFM 分析服务包
"""

from ._shared import (
    _VALID_BASE,
    logger,
    DB_FILE,
    RFM_CACHE_TABLE,
    _fetch_max_pay_time,
    _cache_key,
    RFM_SEGMENT_ORDER,
)
from .period import (
    _run_rfm_period,
    _run_rfm_period_live,
    _run_and_build,
    _build_rows,
    _resolve_single_period,
    _get_period_label,
)
from .analysis import get_rfm_analysis
from .cache import (
    _ensure_db_cache_table,
    _read_db_cache,
    _write_db_cache,
    precompute_rfm_cache,
    is_stale,
    clear_rfm_cache,
    RFM_CACHE_TTL_HOURS,
)

__all__ = [
    # _shared
    "_VALID_BASE",
    "logger",
    "DB_FILE",
    "RFM_CACHE_TABLE",
    "_fetch_max_pay_time",
    "_cache_key",
    "RFM_SEGMENT_ORDER",
    # period
    "_run_rfm_period",
    "_run_rfm_period_live",
    "_run_and_build",
    "_build_rows",
    "_resolve_single_period",
    "_get_period_label",
    # analysis
    "get_rfm_analysis",
    # cache
    "_ensure_db_cache_table",
    "_read_db_cache",
    "_write_db_cache",
    "precompute_rfm_cache",
    "is_stale",
    "clear_rfm_cache",
    "RFM_CACHE_TTL_HOURS",
]
