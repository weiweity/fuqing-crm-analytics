"""
芙清 CRM - RFM F 区间流转
"""
import duckdb

from typing import Any, Dict, List, Optional

from backend.semantic.calculations import yoy_absolute, yoy_repurchase_rate
from backend.db.connection import get_connection
from backend.services.rfm._shared import (
    _VALID_BASE, F_SEGMENT_ORDER,
    _resolve_date_ranges,
    _fetch_data_version, _flow_cache_key,
    _get_cached_flow, _set_cached_flow,
)

# ============================================================
# F 区间流转
# ============================================================

def _run_f_flow_period(
    conn: duckdb.DuckDBPyConnection,
    start_dt: str,
    end_dt: str,
    cutoff_dt: str,
    channel: Optional[str] = None,
    metric_type: str = "GSV",
    exclude_channels: Optional[List[str]] = None,
) -> tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, float]], Dict[str, Dict[str, float]], Dict[str, Dict[str, float]]]:
    """
    执行单个周期的 F 区间流转查询。
    F 区间按历史周期内购买频次分段。
    """
    base_params = [start_dt, end_dt]
    hist_all_params = [cutoff_dt, cutoff_dt]
    hist_same_params = [cutoff_dt, cutoff_dt]

    channel_where_base = ""
    channel_where_hist = ""
    if channel and channel != "全店":
        from backend.semantic.filters import expand_channels
        db_channels = expand_channels([channel])
        if len(db_channels) == 1:
            channel_where_base = " AND o.channel = ?"
            channel_where_hist = " AND o.channel = ?"
            base_params.append(db_channels[0])
            hist_same_params.append(db_channels[0])
        else:
            placeholders = ",".join(["?"] * len(db_channels))
            channel_where_base = f" AND o.channel IN ({placeholders})"
            channel_where_hist = f" AND o.channel IN ({placeholders})"
            base_params.extend(db_channels)
            hist_same_params.extend(db_channels)

    exclude_where_base = ""
    exclude_where_hist = ""
    if exclude_channels:
        from backend.semantic.filters import expand_channels
        db_exclude_channels = expand_channels(exclude_channels)
        safe_ch = [ch.replace("'", "''") for ch in db_exclude_channels]
        quoted = ", ".join([f"'{c}'" for c in safe_ch])
        exclude_where_base = f" AND o.channel NOT IN ({quoted})"
        exclude_where_hist = f" AND o.channel NOT IN ({quoted})"

    full_params = base_params + hist_all_params + hist_same_params

    refund_where = "AND is_refund = FALSE" if metric_type == "GSV" else ""

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
    hist_customers_all AS (
        SELECT
            user_id,
            DATEDIFF('day', MAX(pay_time)::DATE, ?::DATE) AS recency_days,
            COUNT(*) AS frequency,
            BOOL_OR(is_member) AS is_member
        FROM orders o
        WHERE pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE}
          {refund_where}
          {exclude_where_hist}
        GROUP BY user_id
    ),
    hist_customers_same AS (
        SELECT
            user_id,
            DATEDIFF('day', MAX(pay_time)::DATE, ?::DATE) AS recency_days,
            COUNT(*) AS frequency,
            BOOL_OR(is_member) AS is_member
        FROM orders o
        WHERE pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE}
          {refund_where}
          {channel_where_hist}
          {exclude_where_hist}
        GROUP BY user_id
    ),
    f_segmented_all AS (
        SELECT
            user_id,
            frequency,
            is_member,
            CASE
                WHEN frequency = 1 THEN '1次购买'
                WHEN frequency = 2 THEN '2次购买'
                WHEN frequency = 3 THEN '3次购买'
                WHEN frequency = 4 THEN '4次购买'
                ELSE '5次及以上'
            END AS f_segment
        FROM hist_customers_all
    ),
    f_segmented_same AS (
        SELECT
            user_id,
            frequency,
            is_member,
            CASE
                WHEN frequency = 1 THEN '1次购买'
                WHEN frequency = 2 THEN '2次购买'
                WHEN frequency = 3 THEN '3次购买'
                WHEN frequency = 4 THEN '4次购买'
                ELSE '5次及以上'
            END AS f_segment
        FROM hist_customers_same
    ),
    member_segmented_all AS (
        SELECT user_id, frequency, f_segment FROM f_segmented_all WHERE is_member = TRUE
    ),
    member_segmented_same AS (
        SELECT user_id, frequency, f_segment FROM f_segmented_same WHERE is_member = TRUE
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
        SELECT
            f.f_segment,
            COUNT(DISTINCT f.user_id) AS hist_users,
            COUNT(DISTINCT rp.user_id) AS repurchase_users,
            COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM f_segmented_all f
        LEFT JOIN repurchase_users rp ON f.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON f.user_id = ra.user_id
        GROUP BY f.f_segment
    ),
    segment_stats_same AS (
        SELECT
            f.f_segment,
            COUNT(DISTINCT f.user_id) AS hist_users,
            COUNT(DISTINCT rp.user_id) AS repurchase_users,
            COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM f_segmented_same f
        LEFT JOIN repurchase_users rp ON f.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON f.user_id = ra.user_id
        GROUP BY f.f_segment
    ),
    member_stats_all AS (
        SELECT
            f.f_segment,
            COUNT(DISTINCT f.user_id) AS hist_users,
            COUNT(DISTINCT rp.user_id) AS repurchase_users,
            COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM member_segmented_all f
        LEFT JOIN repurchase_users rp ON f.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON f.user_id = ra.user_id
        GROUP BY f.f_segment
    ),
    member_stats_same AS (
        SELECT
            f.f_segment,
            COUNT(DISTINCT f.user_id) AS hist_users,
            COUNT(DISTINCT rp.user_id) AS repurchase_users,
            COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM member_segmented_same f
        LEFT JOIN repurchase_users rp ON f.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON f.user_id = ra.user_id
        GROUP BY f.f_segment
    ),
    ttl_stats_all AS (
        SELECT '已购客TTL' AS f_segment, SUM(hist_users) AS hist_users, SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv FROM segment_stats_all
    ),
    ttl_stats_same AS (
        SELECT '已购客TTL' AS f_segment, SUM(hist_users) AS hist_users, SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv FROM segment_stats_same
    ),
    member_ttl_stats_all AS (
        SELECT '已购客TTL' AS f_segment, SUM(hist_users) AS hist_users, SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv FROM member_stats_all
    ),
    member_ttl_stats_same AS (
        SELECT '已购客TTL' AS f_segment, SUM(hist_users) AS hist_users, SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv FROM member_stats_same
    )
    SELECT 'all' AS mode, f_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM segment_stats_all UNION ALL SELECT * FROM ttl_stats_all
    )
    UNION ALL
    SELECT 'same' AS mode, f_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM segment_stats_same UNION ALL SELECT * FROM ttl_stats_same
    )
    UNION ALL
    SELECT 'member_all' AS mode, f_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM member_stats_all UNION ALL SELECT * FROM member_ttl_stats_all
    )
    UNION ALL
    SELECT 'member_same' AS mode, f_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM member_stats_same UNION ALL SELECT * FROM member_ttl_stats_same
    )
    """

    rows = conn.execute(sql, full_params).fetchall()
    all_result: Dict[str, Dict[str, float]] = {}
    same_result: Dict[str, Dict[str, float]] = {}
    member_all_result: Dict[str, Dict[str, float]] = {}
    member_same_result: Dict[str, Dict[str, float]] = {}
    total_repurchase_gsv_all = 0.0
    total_repurchase_gsv_same = 0.0
    total_repurchase_gsv_member_all = 0.0
    total_repurchase_gsv_member_same = 0.0

    for r in rows:
        mode, segment, hist_users, repurchase_users, repurchase_gsv = r
        entry = {
            "hist_users": int(hist_users or 0),
            "repurchase_users": int(repurchase_users or 0),
            "repurchase_rate": float(repurchase_users or 0) / float(hist_users or 1) if hist_users else 0.0,
            "repurchase_gsv": float(repurchase_gsv or 0),
            "repurchase_gsv_ratio": 0.0,
        }
        if segment != "已购客TTL":
            if mode == "all":
                total_repurchase_gsv_all += float(repurchase_gsv or 0)
                all_result[segment] = entry
            elif mode == "same":
                total_repurchase_gsv_same += float(repurchase_gsv or 0)
                same_result[segment] = entry
            elif mode == "member_all":
                total_repurchase_gsv_member_all += float(repurchase_gsv or 0)
                member_all_result[segment] = entry
            elif mode == "member_same":
                total_repurchase_gsv_member_same += float(repurchase_gsv or 0)
                member_same_result[segment] = entry
        else:
            if mode == "all":
                all_result[segment] = entry
            elif mode == "same":
                same_result[segment] = entry
            elif mode == "member_all":
                member_all_result[segment] = entry
            elif mode == "member_same":
                member_same_result[segment] = entry

    for segment in all_result:
        gsv = all_result[segment]["repurchase_gsv"]
        all_result[segment]["repurchase_gsv_ratio"] = gsv / total_repurchase_gsv_all if total_repurchase_gsv_all > 0 else 0.0
    for segment in same_result:
        gsv = same_result[segment]["repurchase_gsv"]
        same_result[segment]["repurchase_gsv_ratio"] = gsv / total_repurchase_gsv_same if total_repurchase_gsv_same > 0 else 0.0
    for segment in member_all_result:
        gsv = member_all_result[segment]["repurchase_gsv"]
        member_all_result[segment]["repurchase_gsv_ratio"] = gsv / total_repurchase_gsv_member_all if total_repurchase_gsv_member_all > 0 else 0.0
    for segment in member_same_result:
        gsv = member_same_result[segment]["repurchase_gsv"]
        member_same_result[segment]["repurchase_gsv_ratio"] = gsv / total_repurchase_gsv_member_same if total_repurchase_gsv_member_same > 0 else 0.0

    for seg in F_SEGMENT_ORDER:
        if seg not in all_result:
            all_result[seg] = {"hist_users": 0, "repurchase_users": 0, "repurchase_rate": 0.0, "repurchase_gsv": 0.0, "repurchase_gsv_ratio": 0.0}
        if seg not in same_result:
            same_result[seg] = {"hist_users": 0, "repurchase_users": 0, "repurchase_rate": 0.0, "repurchase_gsv": 0.0, "repurchase_gsv_ratio": 0.0}
        if seg not in member_all_result:
            member_all_result[seg] = {"hist_users": 0, "repurchase_users": 0, "repurchase_rate": 0.0, "repurchase_gsv": 0.0, "repurchase_gsv_ratio": 0.0}
        if seg not in member_same_result:
            member_same_result[seg] = {"hist_users": 0, "repurchase_users": 0, "repurchase_rate": 0.0, "repurchase_gsv": 0.0, "repurchase_gsv_ratio": 0.0}

    return all_result, same_result, member_all_result, member_same_result


def get_rfm_f_flow(
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
    F 区间流转看板接口
    """
    ranges = _resolve_date_ranges(period, start_date, end_date, compare_start_date, compare_end_date)
    cur_start_dt, cur_end_dt, cutoff = ranges["current"]
    comp_start_dt, comp_end_dt, comp_cutoff = ranges["comp"]
    prev2_start_dt, prev2_end_dt, prev2_cutoff = ranges["prev2"]
    current_year_label, comp_year_label, prev2_year_label = ranges["labels"]

    # ── 缓存检查 ──
    data_version = _fetch_data_version()
    cache_key = _flow_cache_key(
        "f_flow", start_date or "", end_date or "",
        channel, metric_type, exclude_channels,
        compare_start_date, compare_end_date, data_version,
    )
    cached = _get_cached_flow(cache_key, data_version)
    if cached is not None:
        return cached

    conn = get_connection()
    try:
        cur_all, cur_same, cur_member_all, cur_member_same = _run_f_flow_period(conn, cur_start_dt, cur_end_dt, cutoff, channel, metric_type, exclude_channels)
        comp_all, comp_same, comp_member_all, comp_member_same = _run_f_flow_period(conn, comp_start_dt, comp_end_dt, comp_cutoff, channel, metric_type, exclude_channels)
        prev2_all, prev2_same, prev2_member_all, prev2_member_same = _run_f_flow_period(conn, prev2_start_dt, prev2_end_dt, prev2_cutoff, channel, metric_type, exclude_channels)
    finally:
        conn.close()

    def _build_rows(all_data, comp_data, prev2_data):
        rows = []
        for seg in F_SEGMENT_ORDER:
            c = all_data.get(seg, {})
            p = comp_data.get(seg, {})
            p2 = prev2_data.get(seg, {})
            rows.append({
                "f_segment": seg,
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
                "yoy_repurchase_gsv_ratio": yoy_repurchase_rate(c.get("repurchase_gsv_ratio", 0.0), p.get("repurchase_gsv_ratio", 0.0)),
            })
        return rows

    result = {
        "year_label": current_year_label,
        "comp_year_label": comp_year_label,
        "prev2_year_label": prev2_year_label,
        "metric_type": metric_type,
        "rows": _build_rows(cur_all, comp_all, prev2_all),
        "same_channel_rows": _build_rows(cur_same, comp_same, prev2_same),
        "member_rows": _build_rows(cur_member_all, comp_member_all, prev2_member_all),
        "member_same_channel_rows": _build_rows(cur_member_same, comp_member_same, prev2_member_same),
    }

    # ── 写入缓存 ──
    _set_cached_flow(cache_key, data_version, result)
    return result
