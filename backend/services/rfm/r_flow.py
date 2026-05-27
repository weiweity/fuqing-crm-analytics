"""
芙清 CRM - RFM R 区间流转
"""

from backend.services.rfm._shared import *
from backend.services.rfm._shared import (
    _VALID_BASE, _VALID_BASE_T, _resolve_date_ranges,
    R_SEGMENT_ORDER
)

def _run_r_flow_period(
    conn: duckdb.DuckDBPyConnection,
    start_dt: str,
    end_dt: str,
    cutoff_dt: str,
    channel: Optional[str] = None,
    metric_type: str = "GSV",
    exclude_channels: Optional[List[str]] = None,
) -> tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, float]], Dict[str, Dict[str, float]], Dict[str, Dict[str, float]]]:
    """
    执行单个周期的 R 区间流转查询，同时返回四套数据：
    - all: 历史人群不限渠道，仅回购订单限渠道（本渠道唤醒贡献）
    - same: 历史人群和回购订单均限渠道（本渠道回购本渠道）
    - member_all: 会员历史人群不限渠道
    - member_same: 会员历史人群和回购订单均限渠道
    返回: (all_result, same_result, member_all_result, member_same_result)
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

    # GSV 剔除退款，GMV 包含退款
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
            BOOL_OR(is_member) AS is_member
        FROM orders o
        WHERE pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE}
          {refund_where}
          {channel_where_hist}
          {exclude_where_hist}
        GROUP BY user_id
    ),
    r_segmented_all AS (
        SELECT
            user_id,
            recency_days,
            is_member,
            CASE
                WHEN recency_days BETWEEN 0 AND 30 THEN '近1个月已购客'
                WHEN recency_days BETWEEN 31 AND 90 THEN '近2-3个月已购客'
                WHEN recency_days BETWEEN 91 AND 180 THEN '近4-6月已购客'
                WHEN recency_days BETWEEN 181 AND 365 THEN '近7-12个月已购客'
                WHEN recency_days BETWEEN 366 AND 730 THEN '近13个月-近24个月已购客'
                WHEN recency_days > 730 THEN '2年外已购客'
            END AS r_segment
        FROM hist_customers_all
    ),
    r_segmented_same AS (
        SELECT
            user_id,
            recency_days,
            is_member,
            CASE
                WHEN recency_days BETWEEN 0 AND 30 THEN '近1个月已购客'
                WHEN recency_days BETWEEN 31 AND 90 THEN '近2-3个月已购客'
                WHEN recency_days BETWEEN 91 AND 180 THEN '近4-6月已购客'
                WHEN recency_days BETWEEN 181 AND 365 THEN '近7-12个月已购客'
                WHEN recency_days BETWEEN 366 AND 730 THEN '近13个月-近24个月已购客'
                WHEN recency_days > 730 THEN '2年外已购客'
            END AS r_segment
        FROM hist_customers_same
    ),
    member_segmented_all AS (
        SELECT user_id, recency_days, r_segment FROM r_segmented_all WHERE is_member = TRUE
    ),
    member_segmented_same AS (
        SELECT user_id, recency_days, r_segment FROM r_segmented_same WHERE is_member = TRUE
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
            r.r_segment,
            COUNT(DISTINCT r.user_id) AS hist_users,
            COUNT(DISTINCT rp.user_id) AS repurchase_users,
            COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM r_segmented_all r
        LEFT JOIN repurchase_users rp ON r.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON r.user_id = ra.user_id
        GROUP BY r.r_segment
    ),
    segment_stats_same AS (
        SELECT
            r.r_segment,
            COUNT(DISTINCT r.user_id) AS hist_users,
            COUNT(DISTINCT rp.user_id) AS repurchase_users,
            COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM r_segmented_same r
        LEFT JOIN repurchase_users rp ON r.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON r.user_id = ra.user_id
        GROUP BY r.r_segment
    ),
    member_stats_all AS (
        SELECT
            r.r_segment,
            COUNT(DISTINCT r.user_id) AS hist_users,
            COUNT(DISTINCT rp.user_id) AS repurchase_users,
            COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM member_segmented_all r
        LEFT JOIN repurchase_users rp ON r.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON r.user_id = ra.user_id
        GROUP BY r.r_segment
    ),
    member_stats_same AS (
        SELECT
            r.r_segment,
            COUNT(DISTINCT r.user_id) AS hist_users,
            COUNT(DISTINCT rp.user_id) AS repurchase_users,
            COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM member_segmented_same r
        LEFT JOIN repurchase_users rp ON r.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON r.user_id = ra.user_id
        GROUP BY r.r_segment
    ),
    ttl_stats_all AS (
        SELECT '已购客TTL' AS r_segment, SUM(hist_users) AS hist_users, SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv FROM segment_stats_all
    ),
    ttl_stats_same AS (
        SELECT '已购客TTL' AS r_segment, SUM(hist_users) AS hist_users, SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv FROM segment_stats_same
    ),
    member_ttl_stats_all AS (
        SELECT '已购客TTL' AS r_segment, SUM(hist_users) AS hist_users, SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv FROM member_stats_all
    ),
    member_ttl_stats_same AS (
        SELECT '已购客TTL' AS r_segment, SUM(hist_users) AS hist_users, SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv FROM member_stats_same
    )
    SELECT 'all' AS mode, r_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM segment_stats_all UNION ALL SELECT * FROM ttl_stats_all
    )
    UNION ALL
    SELECT 'same' AS mode, r_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM segment_stats_same UNION ALL SELECT * FROM ttl_stats_same
    )
    UNION ALL
    SELECT 'member_all' AS mode, r_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM member_stats_all UNION ALL SELECT * FROM member_ttl_stats_all
    )
    UNION ALL
    SELECT 'member_same' AS mode, r_segment, hist_users, repurchase_users, repurchase_gsv FROM (
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

    # 补全缺失的 segment
    for seg in R_SEGMENT_ORDER:
        if seg not in all_result:
            all_result[seg] = {"hist_users": 0, "repurchase_users": 0, "repurchase_rate": 0.0, "repurchase_gsv": 0.0, "repurchase_gsv_ratio": 0.0}
        if seg not in same_result:
            same_result[seg] = {"hist_users": 0, "repurchase_users": 0, "repurchase_rate": 0.0, "repurchase_gsv": 0.0, "repurchase_gsv_ratio": 0.0}
        if seg not in member_all_result:
            member_all_result[seg] = {"hist_users": 0, "repurchase_users": 0, "repurchase_rate": 0.0, "repurchase_gsv": 0.0, "repurchase_gsv_ratio": 0.0}
        if seg not in member_same_result:
            member_same_result[seg] = {"hist_users": 0, "repurchase_users": 0, "repurchase_rate": 0.0, "repurchase_gsv": 0.0, "repurchase_gsv_ratio": 0.0}

    return all_result, same_result, member_all_result, member_same_result


def get_rfm_r_flow(
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
    R 区间流转看板接口
    返回 rows（本渠道唤醒贡献：hist 不限渠道，base 限渠道）
         + same_channel_rows（本渠道回购本渠道：hist 和 base 均限渠道）
         + member_rows（会员-本渠道唤醒贡献）
         + member_same_channel_rows（会员-本渠道回购本渠道）
    """
    ranges = _resolve_date_ranges(period, start_date, end_date, compare_start_date, compare_end_date)
    cur_start_dt, cur_end_dt, cutoff = ranges["current"]
    comp_start_dt, comp_end_dt, comp_cutoff = ranges["comp"]
    prev2_start_dt, prev2_end_dt, prev2_cutoff = ranges["prev2"]
    current_year_label, comp_year_label, prev2_year_label = ranges["labels"]

    conn = get_connection()
    try:
        cur_all, cur_same, cur_member_all, cur_member_same = _run_r_flow_period(conn, cur_start_dt, cur_end_dt, cutoff, channel, metric_type, exclude_channels)
        comp_all, comp_same, comp_member_all, comp_member_same = _run_r_flow_period(conn, comp_start_dt, comp_end_dt, comp_cutoff, channel, metric_type, exclude_channels)
        prev2_all, prev2_same, prev2_member_all, prev2_member_same = _run_r_flow_period(conn, prev2_start_dt, prev2_end_dt, prev2_cutoff, channel, metric_type, exclude_channels)
    finally:
        conn.close()

    def _build_rows(all_data, comp_data, prev2_data):
        rows = []
        for seg in R_SEGMENT_ORDER:
            c = all_data.get(seg, {})
            p = comp_data.get(seg, {})
            p2 = prev2_data.get(seg, {})
            rows.append({
                "r_segment": seg,
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

    rows = _build_rows(cur_all, comp_all, prev2_all)
    same_channel_rows = _build_rows(cur_same, comp_same, prev2_same)
    member_rows = _build_rows(cur_member_all, comp_member_all, prev2_member_all)
    member_same_channel_rows = _build_rows(cur_member_same, comp_member_same, prev2_member_same)

    return {
        "year_label": current_year_label,
        "comp_year_label": comp_year_label,
        "prev2_year_label": prev2_year_label,
        "metric_type": metric_type,
        "rows": rows,
        "same_channel_rows": same_channel_rows,
        "member_rows": member_rows,
        "member_same_channel_rows": member_same_channel_rows,
    }
