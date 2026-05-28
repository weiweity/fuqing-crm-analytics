"""
老客健康分析仪表盘 - RFM完整分析（8象限人群分群）

基于R/F/M三维评分，将用户划分为8个经典象限，计算各象限回购率。
逻辑同R区间分析，仅将 r_segment 替换为 rfm_segment（8象限+TTL）。
"""

import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional

from backend.db.connection import get_connection
from backend.services.rfm_service import _resolve_date_ranges
from ._shared import _fetch_max_pay_time, RFM_CACHE_TABLE
from .period import _run_rfm_period, _build_rows
from .cache import _read_db_cache, _write_db_cache

logger = logging.getLogger(__name__)




def get_rfm_analysis(
    year: int = 2026,
    metric_type: str = "GSV",
    period: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
    compare_start_date: Optional[str] = None,
    compare_end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    RFM 8象限完整分析。

    缓存策略：
    - 历史周期（end_date < 今天）：读缓存 / 写缓存（全量口径 live SQL）
    - 当前周期（含今天）：始终 live SQL，不缓存

    缓存口径保证：所有缓存数据均来自 _run_rfm_period_live（全量口径），
    与 user_rfm 预计算表（lookback_days=90）完全独立，不会产生10倍差异。
    """
    ranges = _resolve_date_ranges(period, start_date, end_date, compare_start_date, compare_end_date)
    cur_start_dt, cur_end_dt, cutoff = ranges["current"]
    comp_start_dt, comp_end_dt, comp_cutoff = ranges["comp"]
    prev2_start_dt, prev2_end_dt, prev2_cutoff = ranges["prev2"]
    current_year_label, comp_year_label, prev2_year_label = ranges["labels"]

    # 判断当前周期是否为历史周期（可缓存）
    cur_end_date_str = cur_end_dt.split(" ")[0]
    cur_end_date = datetime.strptime(cur_end_date_str, "%Y-%m-%d").date()
    today = date.today()
    is_historical = cur_end_date < today

    # ── 全量 live SQL 计算（所有周期走同一口径，保证一致性） ──
    conn = get_connection()
    try:
        # 预先获取 data_version，避免后续每个函数都新建连接
        if is_historical:
            data_version = _fetch_max_pay_time(conn)
        else:
            data_version = None

        # ── 缓存读取（仅历史周期，复用同一 conn） ──
        if is_historical:
            cached = _read_db_cache(
                period, start_date, end_date, channel, metric_type,
                exclude_channels, data_version, conn, compare_start_date, compare_end_date
            )
            if cached:
                logger.info(f"RFM 缓存命中（历史周期 end={cur_end_date_str}），跳过计算")
                return cached

        cur_all, cur_same, cur_member_all, cur_member_same = _run_rfm_period(
            conn, cur_start_dt, cur_end_dt, cutoff, channel, metric_type, exclude_channels
        )
        comp_all, comp_same, comp_member_all, comp_member_same = _run_rfm_period(
            conn, comp_start_dt, comp_end_dt, comp_cutoff, channel, metric_type, exclude_channels
        )
        prev2_all, prev2_same, prev2_member_all, prev2_member_same = _run_rfm_period(
            conn, prev2_start_dt, prev2_end_dt, prev2_cutoff, channel, metric_type, exclude_channels
        )

        rows = _build_rows(cur_all, comp_all, prev2_all)
        same_channel_rows = _build_rows(cur_same, comp_same, prev2_same)
        member_rows = _build_rows(cur_member_all, comp_member_all, prev2_member_all)
        member_same_channel_rows = _build_rows(cur_member_same, comp_member_same, prev2_member_same)

        result = {
            "year_label": current_year_label,
            "comp_year_label": comp_year_label,
            "prev2_year_label": prev2_year_label,
            "metric_type": metric_type,
            "rows": rows,
            "same_channel_rows": same_channel_rows,
            "member_rows": member_rows,
            "member_same_channel_rows": member_same_channel_rows,
        }

        # ── 缓存写入（必须在 conn.close() 之前，使用同一连接） ──
        if is_historical and data_version:
            try:
                _write_db_cache(
                    period, start_date, end_date, channel, metric_type,
                    exclude_channels, conn, data_version, result, compare_start_date, compare_end_date
                )
                logger.info(f"RFM 缓存写入完成（历史周期 end={cur_end_date_str}）")
            except Exception as e:
                logger.warning(f"RFM 缓存写入失败（不影响返回）: {e}")
    finally:
        conn.close()

    return result


# ============================================================
# ============================================================
# Plan P1: DuckDB 预计算表（ETL 钩子预热，历史周期直接读表）
# ============================================================
