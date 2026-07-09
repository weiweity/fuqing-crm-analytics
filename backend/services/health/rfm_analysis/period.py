"""
老客健康分析仪表盘 - RFM完整分析（8象限人群分群）

基于R/F/M三维评分，将用户划分为8个经典象限，计算各象限回购率。
逻辑同R区间分析，仅将 r_segment 替换为 rfm_segment（8象限+TTL）。
"""

import logging
import os
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional

import duckdb

from backend.semantic.calculations import yoy_absolute, yoy_repurchase_rate
from backend.semantic.segments import RFM_THRESHOLDS
from backend.semantic.time import PeriodBuilder
from ._shared import _VALID_BASE, RFM_SEGMENT_ORDER

logger = logging.getLogger(__name__)


RFM_DASHBOARD_FULL_TABLE = "rfm_dashboard_full"
USER_RFM_PRECOMPUTE_TABLE = "user_rfm_precompute"
DEFAULT_RFM_PRECOMPUTE_LOOKBACK_DAYS = 3650


def _precompute_min_lookback_days() -> int:
    try:
        return int(os.environ.get(
            "FQ_RFM_PRECOMPUTE_MIN_LOOKBACK_DAYS",
            str(DEFAULT_RFM_PRECOMPUTE_LOOKBACK_DAYS),
        ))
    except ValueError:
        return DEFAULT_RFM_PRECOMPUTE_LOOKBACK_DAYS


def _date_part(value: str) -> str:
    return value.split(" ", 1)[0]


def _last90days_ranges(today: date) -> dict:
    yesterday = today - timedelta(days=1)
    start = yesterday - timedelta(days=89)
    return PeriodBuilder.free(start.isoformat(), yesterday.isoformat())


def _hot_period_ranges(today: date) -> list[tuple[str, dict]]:
    return [
        ("MTD", PeriodBuilder.mtd(today=today)),
        ("YTD", PeriodBuilder.ytd(today=today)),
        ("last90days", _last90days_ranges(today)),
        ("last180days", PeriodBuilder.last180days(today=today)),
        ("last365days", PeriodBuilder.last365days(today=today)),
    ]


def _resolve_period_type(start_dt: str, end_dt: Optional[str] = None, today: Optional[date] = None) -> str:
    """Map hot RFM dashboard date ranges to the frontend period_type."""
    start_date = _date_part(start_dt)
    end_date = _date_part(end_dt) if end_dt else None
    reference_days: list[date] = []
    if today is not None:
        reference_days.append(today)
    else:
        reference_days.append(date.today())
        if end_date:
            try:
                reference_days.append(date.fromisoformat(end_date) + timedelta(days=1))
            except ValueError:
                pass

    seen: set[date] = set()
    for ref_today in reference_days:
        if ref_today in seen:
            continue
        seen.add(ref_today)
        start_only_match = ""
        for period_type, ranges in _hot_period_ranges(ref_today):
            for period_range in ranges.values():
                if period_range.start != start_date:
                    continue
                if end_date and period_range.end == end_date:
                    return period_type
                if not start_only_match:
                    start_only_match = period_type
        if start_only_match:
            return start_only_match
    return ""


def _supports_user_rfm_precompute(
    channel: Optional[str],
    metric_type: str,
    exclude_channels: Optional[List[str]],
) -> bool:
    """Return whether the current request can use user_rfm_precompute safely.

    The L4.71 table is an all-store GSV historical segmentation snapshot. Channel
    or exclude-channel requests need channel-specific historical F/M/R stats, so
    they must keep using the live SQL path until a channel-aware precompute table
    exists.
    """
    if metric_type.upper() != "GSV":
        return False
    if channel and channel != "全店":
        return False
    return not exclude_channels


def _rows_to_rfm_results(
    rows: list[tuple],
) -> tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, float]], Dict[str, Dict[str, float]], Dict[str, Dict[str, float]]]:
    all_result: Dict[str, Dict[str, float]] = {}
    same_result: Dict[str, Dict[str, float]] = {}
    member_all_result: Dict[str, Dict[str, float]] = {}
    member_same_result: Dict[str, Dict[str, float]] = {}
    total_gsv_all = 0.0
    total_gsv_same = 0.0
    total_gsv_member_all = 0.0
    total_gsv_member_same = 0.0

    for r in rows:
        mode, segment, hist_users, repurchase_users, repurchase_gsv = r
        entry = {
            "hist_users": int(hist_users or 0),
            "repurchase_users": int(repurchase_users or 0),
            "repurchase_rate": (
                round(float(repurchase_users or 0) / float(hist_users or 1), 4)
                if hist_users else 0.0
            ),
            "repurchase_gsv": float(repurchase_gsv or 0),
            "repurchase_gsv_ratio": 0.0,
        }
        if mode == "all":
            # Sprint 60.2 治本: total_gsv_all 累加排除 TTL 行 (TTL = 8 象限老客 GSV 之和,
            # 跟 8 象限 sum 重合, 累加会双计). 修后 8 象限 ratio 分母 = 8 象限 sum = 老客 GSV,
            # 8 象限 ratio 之和 = 100%, TTL ratio = 1.0 (自己除以自己, 用户新定义).
            if segment != "已购客TTL":
                total_gsv_all += float(repurchase_gsv or 0)
            all_result[segment] = entry
        elif mode == "same":
            if segment != "已购客TTL":
                total_gsv_same += float(repurchase_gsv or 0)
            same_result[segment] = entry
        elif mode == "member_all":
            if segment != "已购客TTL":
                total_gsv_member_all += float(repurchase_gsv or 0)
            member_all_result[segment] = entry
        elif mode == "member_same":
            if segment != "已购客TTL":
                total_gsv_member_same += float(repurchase_gsv or 0)
            member_same_result[segment] = entry

    # repurchase_gsv_ratio
    # Sprint 60.2 治本: TTL 行 ratio 强制 1.0 (老客 GSV / 老客 GSV, 自己除以自己)
    # 8 象限 ratio 跟 TTL ratio 各自独立 (分桶 vs 合计, 业务合理双计, 9 行 sum = 200%)
    for seg in all_result:
        gsv = all_result[seg]["repurchase_gsv"]
        if seg == "已购客TTL":
            all_result[seg]["repurchase_gsv_ratio"] = 1.0
        else:
            all_result[seg]["repurchase_gsv_ratio"] = round(gsv / total_gsv_all, 4) if total_gsv_all > 0 else 0.0
    for seg in same_result:
        gsv = same_result[seg]["repurchase_gsv"]
        if seg == "已购客TTL":
            same_result[seg]["repurchase_gsv_ratio"] = 1.0
        else:
            same_result[seg]["repurchase_gsv_ratio"] = round(gsv / total_gsv_same, 4) if total_gsv_same > 0 else 0.0
    for seg in member_all_result:
        gsv = member_all_result[seg]["repurchase_gsv"]
        if seg == "已购客TTL":
            member_all_result[seg]["repurchase_gsv_ratio"] = 1.0
        else:
            member_all_result[seg]["repurchase_gsv_ratio"] = round(gsv / total_gsv_member_all, 4) if total_gsv_member_all > 0 else 0.0
    for seg in member_same_result:
        gsv = member_same_result[seg]["repurchase_gsv"]
        if seg == "已购客TTL":
            member_same_result[seg]["repurchase_gsv_ratio"] = 1.0
        else:
            member_same_result[seg]["repurchase_gsv_ratio"] = round(gsv / total_gsv_member_same, 4) if total_gsv_member_same > 0 else 0.0

    # 补零
    for seg in RFM_SEGMENT_ORDER:
        if seg not in all_result:
            all_result[seg] = {"hist_users": 0, "repurchase_users": 0, "repurchase_rate": 0.0, "repurchase_gsv": 0.0, "repurchase_gsv_ratio": 0.0}
        if seg not in same_result:
            same_result[seg] = {"hist_users": 0, "repurchase_users": 0, "repurchase_rate": 0.0, "repurchase_gsv": 0.0, "repurchase_gsv_ratio": 0.0}
        if seg not in member_all_result:
            member_all_result[seg] = {"hist_users": 0, "repurchase_users": 0, "repurchase_rate": 0.0, "repurchase_gsv": 0.0, "repurchase_gsv_ratio": 0.0}
        if seg not in member_same_result:
            member_same_result[seg] = {"hist_users": 0, "repurchase_users": 0, "repurchase_rate": 0.0, "repurchase_gsv": 0.0, "repurchase_gsv_ratio": 0.0}

    return all_result, same_result, member_all_result, member_same_result


def _run_rfm_period(
    conn: duckdb.DuckDBPyConnection,
    start_dt: str,
    end_dt: str,
    cutoff_dt: str,
    channel: Optional[str] = None,
    metric_type: str = "GSV",
    exclude_channels: Optional[List[str]] = None,
) -> tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, float]], Dict[str, Dict[str, float]], Dict[str, Dict[str, float]]]:
    dashboard_full = _run_rfm_period_dashboard_full(
        conn, start_dt, end_dt,
        channel, metric_type, exclude_channels,
    )
    if dashboard_full is not None:
        return dashboard_full

    # L4.71 fast path: only use the new all-store GSV precompute table when the
    # partition exactly matches this period start and has enough history to cover
    # the 731+ bucket. The old user_rfm table remains disabled because its
    # lookback_days=90 partition caused 10x hist_user drift.
    precomputed = _run_rfm_period_precomputed(
        conn, start_dt, end_dt, cutoff_dt,
        channel, metric_type, exclude_channels,
    )
    if precomputed is not None:
        return precomputed

    return _run_rfm_period_live(
        conn, start_dt, end_dt, cutoff_dt,
        channel, metric_type, exclude_channels,
    )


# ── 辅助函数：轻量计算 repurchase 指标（复用预计算的 hist_users） ──

def _run_rfm_period_dashboard_full(
    conn: duckdb.DuckDBPyConnection,
    start_dt: str,
    end_dt: str,
    channel: Optional[str],
    metric_type: str,
    exclude_channels: Optional[List[str]],
) -> Optional[tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, float]], Dict[str, Dict[str, float]], Dict[str, Dict[str, float]]]]:
    """L4.72.5 0-SQL fast path: read final RFM dashboard aggregates."""
    if not _supports_user_rfm_precompute(channel, metric_type, exclude_channels):
        return None

    period_type = _resolve_period_type(start_dt, end_dt)
    if not period_type:
        return None

    as_of_date = _date_part(start_dt)
    end_date = _date_part(end_dt)
    min_lookback_days = _precompute_min_lookback_days()
    sql = f"""
    WITH matched AS (
        SELECT mode, rfm_segment, hist_users, repurchase_users, repurchase_gsv,
               end_date, lookback_days
        FROM {RFM_DASHBOARD_FULL_TABLE}
        WHERE period_type = ?::VARCHAR
          AND as_of_date = ?::DATE
          AND end_date <= ?::DATE
          AND lookback_days >= ?::INTEGER
    ),
    chosen AS (
        SELECT MAX(end_date) AS end_date, MAX(lookback_days) AS lookback_days
        FROM matched
    )
    SELECT mode, rfm_segment, hist_users, repurchase_users, repurchase_gsv
    FROM matched m, chosen c
    WHERE m.end_date = c.end_date
      AND m.lookback_days = c.lookback_days
    """
    try:
        rows = conn.execute(sql, [period_type, as_of_date, end_date, min_lookback_days]).fetchall()
    except Exception as exc:
        logger.debug("L4.72.5 rfm_dashboard_full miss for %s/%s: %s", period_type, as_of_date, exc)
        return None
    if not rows:
        return None
    return _rows_to_rfm_results(rows)


def _run_rfm_period_precomputed(
    conn: duckdb.DuckDBPyConnection,
    start_dt: str,
    end_dt: str,
    cutoff_dt: str,
    channel: Optional[str],
    metric_type: str,
    exclude_channels: Optional[List[str]],
) -> Optional[tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, float]], Dict[str, Dict[str, float]], Dict[str, Dict[str, float]]]]:
    if not _supports_user_rfm_precompute(channel, metric_type, exclude_channels):
        return None

    as_of_date = _date_part(start_dt)
    min_lookback_days = _precompute_min_lookback_days()
    try:
        partition = conn.execute(
            f"""
            SELECT lookback_days, COUNT(*) AS users
            FROM {USER_RFM_PRECOMPUTE_TABLE}
            WHERE as_of_date = ?::DATE
              AND lookback_days >= ?::INTEGER
            GROUP BY lookback_days
            ORDER BY lookback_days DESC
            LIMIT 1
            """,
            [as_of_date, min_lookback_days],
        ).fetchone()
    except Exception as exc:
        logger.debug("L4.71 user_rfm_precompute miss for %s: %s", as_of_date, exc)
        return None

    if not partition or int(partition[1] or 0) == 0:
        return None
    lookback_days = int(partition[0])

    sql = f"""
    WITH
    hist AS (
        SELECT user_id, rfm_segment, is_member
        FROM {USER_RFM_PRECOMPUTE_TABLE}
        WHERE as_of_date = ?::DATE
          AND lookback_days = ?::INTEGER
    ),
    base_orders AS (
        SELECT user_id, actual_amount
        FROM orders o
        WHERE pay_time >= ?::TIMESTAMP
          AND pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE}
          AND is_refund = FALSE
          AND user_id IS NOT NULL
    ),
    repurchase_users AS (
        SELECT DISTINCT user_id FROM base_orders
    ),
    repurchase_amounts AS (
        SELECT bo.user_id, SUM(bo.actual_amount) AS repurchase_gsv
        FROM base_orders bo
        INNER JOIN repurchase_users rp ON bo.user_id = rp.user_id
        GROUP BY bo.user_id
    ),
    segment_stats_all AS (
        SELECT h.rfm_segment,
               COUNT(DISTINCT h.user_id) AS hist_users,
               COUNT(DISTINCT rp.user_id) AS repurchase_users,
               COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM hist h
        LEFT JOIN repurchase_users rp ON h.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON h.user_id = ra.user_id
        GROUP BY h.rfm_segment
    ),
    member_stats_all AS (
        SELECT h.rfm_segment,
               COUNT(DISTINCT h.user_id) AS hist_users,
               COUNT(DISTINCT rp.user_id) AS repurchase_users,
               COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM hist h
        LEFT JOIN repurchase_users rp ON h.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON h.user_id = ra.user_id
        WHERE h.is_member = TRUE
        GROUP BY h.rfm_segment
    ),
    ttl_stats_all AS (
        SELECT '已购客TTL' AS rfm_segment,
               (SELECT COUNT(*) FROM hist) AS hist_users,
               (SELECT COUNT(DISTINCT bo.user_id) FROM base_orders bo INNER JOIN hist h ON bo.user_id = h.user_id) AS repurchase_users,
               (SELECT COALESCE(SUM(bo.actual_amount), 0) FROM base_orders bo INNER JOIN hist h ON bo.user_id = h.user_id) AS repurchase_gsv
    ),
    member_ttl_stats_all AS (
        SELECT '已购客TTL' AS rfm_segment,
               (SELECT COUNT(*) FROM hist WHERE is_member = TRUE) AS hist_users,
               (SELECT COUNT(DISTINCT bo.user_id) FROM base_orders bo INNER JOIN hist h ON bo.user_id = h.user_id AND h.is_member = TRUE) AS repurchase_users,
               (SELECT COALESCE(SUM(bo.actual_amount), 0) FROM base_orders bo INNER JOIN hist h ON bo.user_id = h.user_id AND h.is_member = TRUE) AS repurchase_gsv
    )
    SELECT 'all' AS mode, rfm_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM segment_stats_all UNION ALL SELECT * FROM ttl_stats_all
    )
    UNION ALL
    SELECT 'same' AS mode, rfm_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM segment_stats_all UNION ALL SELECT * FROM ttl_stats_all
    )
    UNION ALL
    SELECT 'member_all' AS mode, rfm_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM member_stats_all UNION ALL SELECT * FROM member_ttl_stats_all
    )
    UNION ALL
    SELECT 'member_same' AS mode, rfm_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM member_stats_all UNION ALL SELECT * FROM member_ttl_stats_all
    )
    """

    try:
        rows = conn.execute(sql, [as_of_date, lookback_days, start_dt, end_dt]).fetchall()
    except Exception as exc:
        logger.debug("L4.71 user_rfm_precompute fallback for %s: %s", as_of_date, exc)
        return None
    return _rows_to_rfm_results(rows)

def _run_rfm_period_live(
    conn: duckdb.DuckDBPyConnection,
    start_dt: str,
    end_dt: str,
    cutoff_dt: str,
    channel: Optional[str],
    metric_type: str,
    exclude_channels: Optional[List[str]],
) -> tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, float]], Dict[str, Dict[str, float]], Dict[str, Dict[str, float]]]:
    """全量实时 SQL 计算（预计算表未命中时的 fallback）。

    参数顺序（对应 SQL 占位符）：
    1. base_orders: start_dt, end_dt [, channel]
    2. user_stats_all: start_dt（观察期前行为）
    3. user_stats_same: start_dt [, channel]（观察期前行为）
    4. rfm_scored_all: start_dt × 4（DATEDIFF 参考 start_dt）
    5. rfm_scored_same: start_dt × 4（DATEDIFF 参考 start_dt）
    6. ttl_users_all: end_dt
    7. ttl_users_same: end_dt [, channel]
    8. ttl_users_all (member 子查询): end_dt
    9. ttl_users_same (member 子查询): end_dt

    R/F/M 分类基于"start_dt 之前的行为"（观察期前行为，避免循环论证）。
    回购口径：≥1 单（与 R/F/M 区间流转一致）。
    TTL 仍基于 end_dt（含当期），是商业指标。
    """
    params: List[Any] = [start_dt, end_dt]

    channel_where_base = ""
    channel_where_hist = ""
    db_channels: List[str] = []
    if channel and channel != "全店":
        from backend.semantic.filters import expand_channels
        db_channels = expand_channels([channel])
        if len(db_channels) == 1:
            channel_where_base = " AND o.channel = ?"
            channel_where_hist = " AND o.channel = ?"
            params.append(db_channels[0])
        else:
            placeholders = ",".join(["?"] * len(db_channels))
            channel_where_base = f" AND o.channel IN ({placeholders})"
            channel_where_hist = f" AND o.channel IN ({placeholders})"
            params.extend(db_channels)

    params.append(start_dt)  # user_stats_all（观察期前行为）
    params.append(start_dt)  # user_stats_same（观察期前行为）
    if db_channels:
        params.extend(db_channels)  # user_stats_same channel

    params.extend([start_dt] * 4)  # rfm_scored_all DATEDIFF 参考 start_dt
    params.extend([start_dt] * 4)  # rfm_scored_same DATEDIFF 参考 start_dt

    # ── TTL 独立口径：截至 end_dt（含当期）的累计去重用户 ──
    # 与 8 象限 RFM 分类的 cutoff 语义解耦：RFM 分类基于观察期前行为
    # （避免循环论证），但"已购客 TTL"是商业指标，应包含当期新增用户
    params.append(end_dt)  # ttl_users_all
    params.append(end_dt)  # ttl_users_same
    if db_channels:
        params.extend(db_channels)  # ttl_users_same channel
    params.append(end_dt)  # member_ttl_users_all
    params.append(end_dt)  # member_ttl_users_same
    if db_channels:
        params.extend(db_channels)  # member_ttl_users_same channel

    exclude_where_base = ""
    exclude_where_hist = ""
    if exclude_channels:
        from backend.semantic.filters import expand_channels
        db_exclude_channels = expand_channels(exclude_channels)
        safe_ch = [ch.replace("'", "''") for ch in db_exclude_channels]
        quoted = ", ".join([f"'{c}'" for c in safe_ch])
        exclude_where_base = f" AND o.channel NOT IN ({quoted})"
        exclude_where_hist = f" AND o.channel NOT IN ({quoted})"

    refund_where = "AND is_refund = FALSE" if metric_type == "GSV" else ""
    _rt = RFM_THRESHOLDS["r"]
    _ft = RFM_THRESHOLDS["f"]
    _mt = RFM_THRESHOLDS["m"]

    sql = f"""
    WITH
    base_orders AS (
        SELECT user_id, actual_amount
        FROM orders o
        WHERE pay_time >= ?::TIMESTAMP
          AND pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE}
          {refund_where}
          {channel_where_base}
          {exclude_where_base}
    ),
    user_stats_all AS (
        SELECT user_id, MAX(pay_time) as last_pay_time,
               COUNT(DISTINCT order_id) as order_count,
               SUM(actual_amount) as gsv,
               BOOL_OR(is_member) AS is_member
        FROM orders o
        WHERE pay_time < ?::TIMESTAMP
          AND {_VALID_BASE}
          {refund_where}
          {exclude_where_base}
        GROUP BY user_id
    ),
    user_stats_same AS (
        SELECT user_id, MAX(pay_time) as last_pay_time,
               COUNT(DISTINCT order_id) as order_count,
               SUM(actual_amount) as gsv,
               BOOL_OR(is_member) AS is_member
        FROM orders o
        WHERE pay_time < ?::TIMESTAMP
          AND {_VALID_BASE}
          {refund_where}
          {channel_where_hist}
          {exclude_where_hist}
        GROUP BY user_id
    ),
    rfm_scored_all AS (
        SELECT user_id, is_member,
            CASE
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[0]} THEN 5
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[1]} THEN 4
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[2]} THEN 3
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[3]} THEN 2
                ELSE 1
            END as r_score,
            CASE WHEN order_count >= {_ft[3] + 1} THEN 5 WHEN order_count >= {_ft[2] + 1} THEN 4 WHEN order_count = {_ft[2]} THEN 3 WHEN order_count = {_ft[1]} THEN 2 ELSE 1 END as f_score,
            CASE WHEN gsv >= {_mt[3]} THEN 5 WHEN gsv >= {_mt[2]} THEN 4 WHEN gsv >= {_mt[1]} THEN 3 WHEN gsv >= {_mt[0]} THEN 2 ELSE 1 END as m_score
        FROM user_stats_all
    ),
    rfm_scored_same AS (
        SELECT user_id, is_member,
            CASE
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[0]} THEN 5
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[1]} THEN 4
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[2]} THEN 3
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[3]} THEN 2
                ELSE 1
            END as r_score,
            CASE WHEN order_count >= {_ft[3] + 1} THEN 5 WHEN order_count >= {_ft[2] + 1} THEN 4 WHEN order_count = {_ft[2]} THEN 3 WHEN order_count = {_ft[1]} THEN 2 ELSE 1 END as f_score,
            CASE WHEN gsv >= {_mt[3]} THEN 5 WHEN gsv >= {_mt[2]} THEN 4 WHEN gsv >= {_mt[1]} THEN 3 WHEN gsv >= {_mt[0]} THEN 2 ELSE 1 END as m_score
        FROM user_stats_same
    ),
    segmented_all AS (
        SELECT user_id, is_member,
            CASE
                WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN '重要价值客户'
                WHEN r_score < 4 AND f_score >= 4 AND m_score >= 4 THEN '重要保持客户'
                WHEN r_score >= 4 AND f_score < 4 AND m_score >= 4 THEN '重要发展客户'
                WHEN r_score < 4 AND f_score < 4 AND m_score >= 4 THEN '重要挽留客户'
                WHEN r_score >= 4 AND f_score >= 4 AND m_score < 4 THEN '一般价值客户'
                WHEN r_score < 4 AND f_score >= 4 AND m_score < 4 THEN '一般保持客户'
                WHEN r_score >= 4 AND f_score < 4 AND m_score < 4 THEN '一般发展客户'
                ELSE '一般挽留客户'
            END as rfm_segment
        FROM rfm_scored_all
    ),
    segmented_same AS (
        SELECT user_id, is_member,
            CASE
                WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN '重要价值客户'
                WHEN r_score < 4 AND f_score >= 4 AND m_score >= 4 THEN '重要保持客户'
                WHEN r_score >= 4 AND f_score < 4 AND m_score >= 4 THEN '重要发展客户'
                WHEN r_score < 4 AND f_score < 4 AND m_score >= 4 THEN '重要挽留客户'
                WHEN r_score >= 4 AND f_score >= 4 AND m_score < 4 THEN '一般价值客户'
                WHEN r_score < 4 AND f_score >= 4 AND m_score < 4 THEN '一般保持客户'
                WHEN r_score >= 4 AND f_score < 4 AND m_score < 4 THEN '一般发展客户'
                ELSE '一般挽留客户'
            END as rfm_segment
        FROM rfm_scored_same
    ),
    member_segmented_all AS (SELECT user_id, rfm_segment FROM segmented_all WHERE is_member = TRUE),
    member_segmented_same AS (SELECT user_id, rfm_segment FROM segmented_same WHERE is_member = TRUE),
    repurchase_users AS (
        SELECT DISTINCT user_id FROM base_orders
    ),
    repurchase_amounts AS (
        SELECT bo.user_id, SUM(bo.actual_amount) AS repurchase_gsv
        FROM base_orders bo INNER JOIN repurchase_users rp ON bo.user_id = rp.user_id
        GROUP BY bo.user_id
    ),
    segment_stats_all AS (
        SELECT r.rfm_segment,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT rp.user_id) AS repurchase_users,
               COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM segmented_all r
        LEFT JOIN repurchase_users rp ON r.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON r.user_id = ra.user_id
        GROUP BY r.rfm_segment
    ),
    segment_stats_same AS (
        SELECT r.rfm_segment,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT rp.user_id) AS repurchase_users,
               COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM segmented_same r
        LEFT JOIN repurchase_users rp ON r.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON r.user_id = ra.user_id
        GROUP BY r.rfm_segment
    ),
    member_stats_all AS (
        SELECT r.rfm_segment,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT rp.user_id) AS repurchase_users,
               COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM member_segmented_all r
        LEFT JOIN repurchase_users rp ON r.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON r.user_id = ra.user_id
        GROUP BY r.rfm_segment
    ),
    member_stats_same AS (
        SELECT r.rfm_segment,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT rp.user_id) AS repurchase_users,
               COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM member_segmented_same r
        LEFT JOIN repurchase_users rp ON r.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON r.user_id = ra.user_id
        GROUP BY r.rfm_segment
    ),
    ttl_users_all AS (
        SELECT user_id FROM orders o
        WHERE pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE}
          {refund_where}
          {exclude_where_base}
        GROUP BY user_id
    ),
    ttl_users_same AS (
        SELECT user_id FROM orders o
        WHERE pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE}
          {refund_where}
          {channel_where_hist}
          {exclude_where_hist}
        GROUP BY user_id
    ),
    member_ttl_users_all AS (
        SELECT user_id FROM orders o
        WHERE pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE}
          AND is_member = TRUE
          {refund_where}
          {exclude_where_base}
        GROUP BY user_id
    ),
    member_ttl_users_same AS (
        SELECT user_id FROM orders o
        WHERE pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE}
          AND is_member = TRUE
          {refund_where}
          {channel_where_hist}
          {exclude_where_hist}
        GROUP BY user_id
    ),
    ttl_stats_all AS (
        SELECT '已购客TTL' AS rfm_segment,
               -- Sprint 60.2 治本: hist_users 改用 user_stats_all (RFM 评分用户, 老客)
               -- 跟 8 象限口径一致 (老客 GSV TTL = 8 象限老客 GSV 之和).
               -- 修前用 ttl_users_all (`pay_time <= end_dt` 含新客), 算 3,352,390 多 34,611 新客.
               (SELECT COUNT(*) FROM user_stats_all) AS hist_users,
               -- Sprint 60.2 治本: TTL 行 repurchase_users/gsv 用 user_stats_all JOIN base_orders
               -- (老客 GSV TTL = 8 象限老客 GSV 之和, 自己除以自己 ratio 100%).
               -- 修前用 base_orders 全部 (含新客 642 万 GSV), 算 ratio 67.34% 错.
               (SELECT COUNT(DISTINCT bo.user_id) FROM base_orders bo INNER JOIN user_stats_all us ON bo.user_id = us.user_id) AS repurchase_users,
               (SELECT COALESCE(SUM(bo.actual_amount), 0) FROM base_orders bo INNER JOIN user_stats_all us ON bo.user_id = us.user_id) AS repurchase_gsv
    ),
    ttl_stats_same AS (
        SELECT '已购客TTL' AS rfm_segment,
               (SELECT COUNT(*) FROM user_stats_same) AS hist_users,
               (SELECT COUNT(DISTINCT bo.user_id) FROM base_orders bo INNER JOIN user_stats_same us ON bo.user_id = us.user_id) AS repurchase_users,
               (SELECT COALESCE(SUM(bo.actual_amount), 0) FROM base_orders bo INNER JOIN user_stats_same us ON bo.user_id = us.user_id) AS repurchase_gsv
    ),
    member_ttl_stats_all AS (
        SELECT '已购客TTL' AS rfm_segment,
               (SELECT COUNT(*) FROM member_ttl_users_all) AS hist_users,
               (SELECT COUNT(DISTINCT bo.user_id) FROM base_orders bo INNER JOIN user_stats_all us ON bo.user_id = us.user_id AND us.is_member = TRUE) AS repurchase_users,
               (SELECT COALESCE(SUM(bo.actual_amount), 0) FROM base_orders bo INNER JOIN user_stats_all us ON bo.user_id = us.user_id AND us.is_member = TRUE) AS repurchase_gsv
    ),
    member_ttl_stats_same AS (
        SELECT '已购客TTL' AS rfm_segment,
               (SELECT COUNT(*) FROM member_ttl_users_same) AS hist_users,
               (SELECT COUNT(DISTINCT bo.user_id) FROM base_orders bo INNER JOIN user_stats_same us ON bo.user_id = us.user_id AND us.is_member = TRUE) AS repurchase_users,
               (SELECT COALESCE(SUM(bo.actual_amount), 0) FROM base_orders bo INNER JOIN user_stats_same us ON bo.user_id = us.user_id AND us.is_member = TRUE) AS repurchase_gsv
    )
    SELECT 'all' AS mode, rfm_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM segment_stats_all UNION ALL SELECT * FROM ttl_stats_all
    )
    UNION ALL
    SELECT 'same' AS mode, rfm_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM segment_stats_same UNION ALL SELECT * FROM ttl_stats_same
    )
    UNION ALL
    SELECT 'member_all' AS mode, rfm_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM member_stats_all UNION ALL SELECT * FROM member_ttl_stats_all
    )
    UNION ALL
    SELECT 'member_same' AS mode, rfm_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM member_stats_same UNION ALL SELECT * FROM member_ttl_stats_same
    )
    """

    rows = conn.execute(sql, params).fetchall()
    return _rows_to_rfm_results(rows)


def _run_and_build(
    conn: duckdb.DuckDBPyConnection,
    start_dt: str,
    end_dt: str,
    cutoff_dt: str,
    channel: Optional[str],
    metric_type: str,
    exclude_channels: Optional[List[str]],
) -> tuple[
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
]:
    """对单个周期执行 SQL 并返回 4 套原始 dict（不做 YoY 计算）"""
    return _run_rfm_period(conn, start_dt, end_dt, cutoff_dt, channel, metric_type, exclude_channels)


def _build_rows(all_data, comp_data, prev2_data):
    """将3个周期的 dict 数据构建为带 YoY 的行列表"""
    rows = []
    for seg in RFM_SEGMENT_ORDER:
        c = all_data.get(seg, {})
        p = comp_data.get(seg, {})
        p2 = prev2_data.get(seg, {})
        rows.append({
            "rfm_segment": seg,
            "hist_users_current": c.get("hist_users", 0),
            "repurchase_users_current": c.get("repurchase_users", 0),
            "repurchase_rate_current": round(c.get("repurchase_rate", 0.0), 4),
            "repurchase_gsv_current": round(c.get("repurchase_gsv", 0.0), 2),
            "repurchase_gsv_ratio_current": round(c.get("repurchase_gsv_ratio", 0.0), 4),
            "hist_users_comp": p.get("hist_users", 0),
            "repurchase_users_comp": p.get("repurchase_users", 0),
            "repurchase_rate_comp": round(p.get("repurchase_rate", 0.0), 4),
            "repurchase_gsv_comp": round(p.get("repurchase_gsv", 0.0), 2),
            "repurchase_gsv_ratio_comp": round(p.get("repurchase_gsv_ratio", 0.0), 4),
            "hist_users_prev2": p2.get("hist_users", 0),
            "repurchase_users_prev2": p2.get("repurchase_users", 0),
            "repurchase_rate_prev2": round(p2.get("repurchase_rate", 0.0), 4),
            "repurchase_gsv_prev2": round(p2.get("repurchase_gsv", 0.0), 2),
            "repurchase_gsv_ratio_prev2": round(p2.get("repurchase_gsv_ratio", 0.0), 4),
            "yoy_hist_users": yoy_absolute(c.get("hist_users", 0), p.get("hist_users", 0)),
            "yoy_repurchase_users": yoy_absolute(c.get("repurchase_users", 0), p.get("repurchase_users", 0)),
            "yoy_repurchase_rate": yoy_repurchase_rate(c.get("repurchase_rate", 0.0), p.get("repurchase_rate", 0.0)),
            "yoy_repurchase_gsv": yoy_absolute(c.get("repurchase_gsv", 0.0), p.get("repurchase_gsv", 0.0)),
            "yoy_repurchase_gsv_ratio_ppt": yoy_repurchase_rate(c.get("repurchase_gsv_ratio", 0.0), p.get("repurchase_gsv_ratio", 0.0)),
        })
    return rows


def _resolve_single_period(
    period: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    year_offset: int = 0,
) -> tuple[str, str, str]:
    """解析单个周期的日期字符串（返回 start, end, cutoff）"""
    if period:
        today = datetime.now().date()
        try:
            pb_func = getattr(__import__(
                "backend.semantic.time", fromlist=["PeriodBuilder"]
            ).PeriodBuilder, period.lower())
            ranges = pb_func(today=today)
            cur_range = ranges["current"]
            return (
                f"{cur_range.start} 00:00:00",
                f"{cur_range.end} 23:59:59",
                cur_range.cutoff,
            )
        except (AttributeError, KeyError):
            pass
    # 自定义日期
    if start_date and end_date:
        sy, sm, sd = map(int, start_date.split("-"))
        ey, em, ed = map(int, end_date.split("-"))
        from calendar import monthrange
        from datetime import date, timedelta
        cutoff_date = date(sy, sm, 1) - timedelta(days=1)
        return (
            f"{start_date} 00:00:00",
            f"{end_date} 23:59:59",
            cutoff_date.strftime("%Y-%m-%d"),
        )
    # 默认 MTD（含 year_offset）
    today = datetime.now().date()
    from calendar import monthrange
    from datetime import timedelta
    y = today.year + year_offset
    m = today.month
    _, last = monthrange(y, m)
    start = f"{y}-{m:02d}-01"
    end = f"{y}-{m:02d}-{last:02d}"
    cutoff = date(y, m, 1) - timedelta(days=1)
    return (
        f"{start} 00:00:00",
        f"{end} 23:59:59",
        cutoff.strftime("%Y-%m-%d"),
    )


def _get_period_label(period: Optional[str], start_date: Optional[str]) -> str:
    """生成年份标签（用于 _build_rows 中取 comp/prev2 的正确偏移）"""
    # 返回当前实际年份数字（用于 _build_rows 识别 comp/prev2）
    # year_offset 由调用方控制，这里只返回基准年
    if start_date:
        return start_date[:4]
    return str(datetime.now().year)
