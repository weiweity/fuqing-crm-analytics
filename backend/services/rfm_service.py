"""
芙清 CRM 客户分析系统 - RFM 专项服务
R 区间流转看板后端实现
"""

import duckdb
from typing import Dict, Any, List, Optional
from datetime import date, timedelta, datetime
from calendar import monthrange
from backend.db.connection import get_connection
from backend.semantic.time import PeriodBuilder
from backend.semantic.calculations import yoy_absolute, yoy_repurchase_rate
from backend.semantic.filters import expand_channels

# 语义层统一口径
_VALID_BASE = "is_goujinjin = FALSE AND order_status != '交易关闭'"
_VALID_BASE_T = "o.is_goujinjin = FALSE AND o.order_status != '交易关闭'"

R_SEGMENT_ORDER = [
    "近1个月已购客",
    "近2-3个月已购客",
    "近4-6月已购客",
    "近7-12个月已购客",
    "近13个月-近24个月已购客",
    "2年外已购客",
    "已购客TTL",
]

F_SEGMENT_ORDER = [
    "1次购买",
    "2次购买",
    "3次购买",
    "4次购买",
    "5次及以上",
    "已购客TTL",
]

M_SEGMENT_ORDER = [
    "0-100元",
    "100-300元",
    "300-500元",
    "500-1000元",
    "1000元以上",
    "已购客TTL",
]


def _resolve_date_ranges(
    period: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    compare_start_date: Optional[str] = None,
    compare_end_date: Optional[str] = None,
):
    """
    解析当前期 / 对比期 / 前年期 的日期范围。
    与 calculate_audience_summary 保持一致。

    当传入 compare_start_date/compare_end_date 时，对比期使用自定义日期
    而不是自动计算的去年同期（支持环比 / 自定义对比）。
    """
    today = date.today()
    current_year_label = str(today.year)
    comp_year_label = str(today.year - 1)
    prev2_year_label = str(today.year - 2)

    if period:
        try:
            pb_func = getattr(PeriodBuilder, period.lower())
            ranges = pb_func(today=today)
            cur_range = ranges["current"]
            comp_range = ranges["comparison"]
            prev2_range = ranges["prev2"]
            cur_start_dt = f"{cur_range.start} 00:00:00"
            cur_end_dt = f"{cur_range.end} 23:59:59"
            ly_start_dt = f"{comp_range.start} 00:00:00"
            ly_end_dt = f"{comp_range.end} 23:59:59"
            y2_start_dt = f"{prev2_range.start} 00:00:00"
            y2_end_dt = f"{prev2_range.end} 23:59:59"
            cutoff = cur_range.cutoff
            ly_cutoff_str = comp_range.cutoff
            y2_cutoff_str = prev2_range.cutoff
            return {
                "current": (cur_start_dt, cur_end_dt, cutoff),
                "comp": (ly_start_dt, ly_end_dt, ly_cutoff_str),
                "prev2": (y2_start_dt, y2_end_dt, y2_cutoff_str),
                "labels": (current_year_label, comp_year_label, prev2_year_label),
            }
        except (AttributeError, KeyError):
            period = None

    if start_date and end_date:
        cur_start_dt = f"{start_date} 00:00:00"
        cur_end_dt = f"{end_date} 23:59:59"
        cur_start_y, cur_start_m, cur_start_d = map(int, start_date.split("-"))
        cur_end_y, cur_end_m, cur_end_d = map(int, end_date.split("-"))
        cutoff_date = date(cur_start_y, cur_start_m, 1) - timedelta(days=1)
        cutoff = cutoff_date.strftime("%Y-%m-%d")

        # ── 对比期：优先使用自定义对比日期（环比 / 自定义）──
        if compare_start_date and compare_end_date:
            comp_start_y, comp_start_m, comp_start_d = map(int, compare_start_date.split("-"))
            ly_start_dt = f"{compare_start_date} 00:00:00"
            ly_end_dt = f"{compare_end_date} 23:59:59"
            ly_cutoff = date(comp_start_y, comp_start_m, 1) - timedelta(days=1)
            ly_cutoff_str = ly_cutoff.strftime("%Y-%m-%d")
            comp_year_label = str(comp_start_y)
        else:
            # 默认：去年同期
            ly_date = date(cur_start_y - 1, cur_start_m, cur_start_d)
            ly_start_dt = f"{ly_date.year}-{ly_date.month:02d}-{ly_date.day:02d} 00:00:00"
            ly_end_year, ly_end_month = cur_end_y - 1, cur_end_m
            ly_end_day = min(cur_end_d, monthrange(ly_end_year, ly_end_month)[1])
            ly_end_dt = f"{ly_end_year}-{ly_end_month:02d}-{ly_end_day:02d} 23:59:59"
            ly_cutoff = date(ly_date.year, ly_date.month, 1) - timedelta(days=1)
            ly_cutoff_str = ly_cutoff.strftime("%Y-%m-%d")
            comp_year_label = str(cur_start_y - 1)

        # prev2 始终为前年同期（固定基准）
        y2_date = date(cur_start_y - 2, cur_start_m, cur_start_d)
        y2_start_dt = f"{y2_date.year}-{y2_date.month:02d}-{y2_date.day:02d} 00:00:00"
        y2_end_year, y2_end_month = cur_end_y - 2, cur_end_m
        y2_end_day = min(cur_end_d, monthrange(y2_end_year, y2_end_month)[1])
        y2_end_dt = f"{y2_end_year}-{y2_end_month:02d}-{y2_end_day:02d} 23:59:59"
        y2_cutoff = date(y2_date.year, y2_date.month, 1) - timedelta(days=1)
        y2_cutoff_str = y2_cutoff.strftime("%Y-%m-%d")

        current_year_label = str(cur_start_y)
        prev2_year_label = str(cur_start_y - 2)

        return {
            "current": (cur_start_dt, cur_end_dt, cutoff),
            "comp": (ly_start_dt, ly_end_dt, ly_cutoff_str),
            "prev2": (y2_start_dt, y2_end_dt, y2_cutoff_str),
            "labels": (current_year_label, comp_year_label, prev2_year_label),
        }

    # 默认 MTD
    yesterday = today - timedelta(days=1)
    cur_month = today.month
    _, last_day_cur = monthrange(today.year, cur_month)
    cur_start = f"{today.year}-{cur_month:02d}-01"
    cur_end = f"{today.year}-{cur_month:02d}-{min(yesterday.day, last_day_cur):02d}"
    cur_start_dt = f"{cur_start} 00:00:00"
    cur_end_dt = f"{cur_end} 23:59:59"
    cutoff = (datetime(today.year, cur_month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")

    comp_year = today.year - 1
    _, last_day_comp = monthrange(comp_year, cur_month)
    comp_start = f"{comp_year}-{cur_month:02d}-01"
    comp_end = f"{comp_year}-{cur_month:02d}-{min(yesterday.day, last_day_comp):02d}"
    ly_start_dt = f"{comp_start} 00:00:00"
    ly_end_dt = f"{comp_end} 23:59:59"
    ly_cutoff_str = (datetime(comp_year, cur_month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")

    prev2_year = today.year - 2
    _, last_day_prev2 = monthrange(prev2_year, cur_month)
    prev2_start = f"{prev2_year}-{cur_month:02d}-01"
    prev2_end = f"{prev2_year}-{cur_month:02d}-{min(yesterday.day, last_day_prev2):02d}"
    y2_start_dt = f"{prev2_start} 00:00:00"
    y2_end_dt = f"{prev2_end} 23:59:59"
    y2_cutoff_str = (datetime(prev2_year, cur_month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")

    return {
        "current": (cur_start_dt, cur_end_dt, cutoff),
        "comp": (ly_start_dt, ly_end_dt, ly_cutoff_str),
        "prev2": (y2_start_dt, y2_end_dt, y2_cutoff_str),
        "labels": (str(today.year), str(comp_year), str(prev2_year)),
    }


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

    return {
        "year_label": current_year_label,
        "comp_year_label": comp_year_label,
        "prev2_year_label": prev2_year_label,
        "metric_type": metric_type,
        "rows": _build_rows(cur_all, comp_all, prev2_all),
        "same_channel_rows": _build_rows(cur_same, comp_same, prev2_same),
        "member_rows": _build_rows(cur_member_all, comp_member_all, prev2_member_all),
        "member_same_channel_rows": _build_rows(cur_member_same, comp_member_same, prev2_member_same),
    }


# ============================================================
# M 区间流转
# ============================================================

def _run_m_flow_period(
    conn: duckdb.DuckDBPyConnection,
    start_dt: str,
    end_dt: str,
    cutoff_dt: str,
    channel: Optional[str] = None,
    metric_type: str = "GSV",
    exclude_channels: Optional[List[str]] = None,
) -> tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, float]], Dict[str, Dict[str, float]], Dict[str, Dict[str, float]]]:
    """
    执行单个周期的 M 区间流转查询。
    M 区间按历史周期内累计消费金额分段。
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
            SUM(actual_amount) AS monetary,
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
            SUM(actual_amount) AS monetary,
            BOOL_OR(is_member) AS is_member
        FROM orders o
        WHERE pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE}
          {refund_where}
          {channel_where_hist}
          {exclude_where_hist}
        GROUP BY user_id
    ),
    m_segmented_all AS (
        SELECT
            user_id,
            monetary,
            is_member,
            CASE
                WHEN monetary < 100 THEN '0-100元'
                WHEN monetary < 300 THEN '100-300元'
                WHEN monetary < 500 THEN '300-500元'
                WHEN monetary < 1000 THEN '500-1000元'
                ELSE '1000元以上'
            END AS m_segment
        FROM hist_customers_all
    ),
    m_segmented_same AS (
        SELECT
            user_id,
            monetary,
            is_member,
            CASE
                WHEN monetary < 100 THEN '0-100元'
                WHEN monetary < 300 THEN '100-300元'
                WHEN monetary < 500 THEN '300-500元'
                WHEN monetary < 1000 THEN '500-1000元'
                ELSE '1000元以上'
            END AS m_segment
        FROM hist_customers_same
    ),
    member_segmented_all AS (
        SELECT user_id, monetary, m_segment FROM m_segmented_all WHERE is_member = TRUE
    ),
    member_segmented_same AS (
        SELECT user_id, monetary, m_segment FROM m_segmented_same WHERE is_member = TRUE
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
            m.m_segment,
            COUNT(DISTINCT m.user_id) AS hist_users,
            COUNT(DISTINCT rp.user_id) AS repurchase_users,
            COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM m_segmented_all m
        LEFT JOIN repurchase_users rp ON m.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON m.user_id = ra.user_id
        GROUP BY m.m_segment
    ),
    segment_stats_same AS (
        SELECT
            m.m_segment,
            COUNT(DISTINCT m.user_id) AS hist_users,
            COUNT(DISTINCT rp.user_id) AS repurchase_users,
            COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM m_segmented_same m
        LEFT JOIN repurchase_users rp ON m.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON m.user_id = ra.user_id
        GROUP BY m.m_segment
    ),
    member_stats_all AS (
        SELECT
            m.m_segment,
            COUNT(DISTINCT m.user_id) AS hist_users,
            COUNT(DISTINCT rp.user_id) AS repurchase_users,
            COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM member_segmented_all m
        LEFT JOIN repurchase_users rp ON m.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON m.user_id = ra.user_id
        GROUP BY m.m_segment
    ),
    member_stats_same AS (
        SELECT
            m.m_segment,
            COUNT(DISTINCT m.user_id) AS hist_users,
            COUNT(DISTINCT rp.user_id) AS repurchase_users,
            COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM member_segmented_same m
        LEFT JOIN repurchase_users rp ON m.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON m.user_id = ra.user_id
        GROUP BY m.m_segment
    ),
    ttl_stats_all AS (
        SELECT '已购客TTL' AS m_segment, SUM(hist_users) AS hist_users, SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv FROM segment_stats_all
    ),
    ttl_stats_same AS (
        SELECT '已购客TTL' AS m_segment, SUM(hist_users) AS hist_users, SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv FROM segment_stats_same
    ),
    member_ttl_stats_all AS (
        SELECT '已购客TTL' AS m_segment, SUM(hist_users) AS hist_users, SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv FROM member_stats_all
    ),
    member_ttl_stats_same AS (
        SELECT '已购客TTL' AS m_segment, SUM(hist_users) AS hist_users, SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv FROM member_stats_same
    )
    SELECT 'all' AS mode, m_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM segment_stats_all UNION ALL SELECT * FROM ttl_stats_all
    )
    UNION ALL
    SELECT 'same' AS mode, m_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM segment_stats_same UNION ALL SELECT * FROM ttl_stats_same
    )
    UNION ALL
    SELECT 'member_all' AS mode, m_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM member_stats_all UNION ALL SELECT * FROM member_ttl_stats_all
    )
    UNION ALL
    SELECT 'member_same' AS mode, m_segment, hist_users, repurchase_users, repurchase_gsv FROM (
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

    for seg in M_SEGMENT_ORDER:
        if seg not in all_result:
            all_result[seg] = {"hist_users": 0, "repurchase_users": 0, "repurchase_rate": 0.0, "repurchase_gsv": 0.0, "repurchase_gsv_ratio": 0.0}
        if seg not in same_result:
            same_result[seg] = {"hist_users": 0, "repurchase_users": 0, "repurchase_rate": 0.0, "repurchase_gsv": 0.0, "repurchase_gsv_ratio": 0.0}
        if seg not in member_all_result:
            member_all_result[seg] = {"hist_users": 0, "repurchase_users": 0, "repurchase_rate": 0.0, "repurchase_gsv": 0.0, "repurchase_gsv_ratio": 0.0}
        if seg not in member_same_result:
            member_same_result[seg] = {"hist_users": 0, "repurchase_users": 0, "repurchase_rate": 0.0, "repurchase_gsv": 0.0, "repurchase_gsv_ratio": 0.0}

    return all_result, same_result, member_all_result, member_same_result


def get_rfm_m_flow(
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
    M 区间流转看板接口
    """
    ranges = _resolve_date_ranges(period, start_date, end_date, compare_start_date, compare_end_date)
    cur_start_dt, cur_end_dt, cutoff = ranges["current"]
    comp_start_dt, comp_end_dt, comp_cutoff = ranges["comp"]
    prev2_start_dt, prev2_end_dt, prev2_cutoff = ranges["prev2"]
    current_year_label, comp_year_label, prev2_year_label = ranges["labels"]

    conn = get_connection()
    try:
        cur_all, cur_same, cur_member_all, cur_member_same = _run_m_flow_period(conn, cur_start_dt, cur_end_dt, cutoff, channel, metric_type, exclude_channels)
        comp_all, comp_same, comp_member_all, comp_member_same = _run_m_flow_period(conn, comp_start_dt, comp_end_dt, comp_cutoff, channel, metric_type, exclude_channels)
        prev2_all, prev2_same, prev2_member_all, prev2_member_same = _run_m_flow_period(conn, prev2_start_dt, prev2_end_dt, prev2_cutoff, channel, metric_type, exclude_channels)
    finally:
        conn.close()

    def _build_rows(all_data, comp_data, prev2_data):
        rows = []
        for seg in M_SEGMENT_ORDER:
            c = all_data.get(seg, {})
            p = comp_data.get(seg, {})
            p2 = prev2_data.get(seg, {})
            rows.append({
                "m_segment": seg,
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

    return {
        "year_label": current_year_label,
        "comp_year_label": comp_year_label,
        "prev2_year_label": prev2_year_label,
        "metric_type": metric_type,
        "rows": _build_rows(cur_all, comp_all, prev2_all),
        "same_channel_rows": _build_rows(cur_same, comp_same, prev2_same),
        "member_rows": _build_rows(cur_member_all, comp_member_all, prev2_member_all),
        "member_same_channel_rows": _build_rows(cur_member_same, comp_member_same, prev2_member_same),
    }


# ============================================================
# RFM 区间订单明细导出
# ============================================================

def get_segment_orders(
    dimension: str,
    segment: str,
    start_date: str,
    end_date: str,
    metric_type: str = "GSV",
    mode: str = "all",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    根据 RFM 维度和区间，导出该区间内所有用户的订单号明细。
    """
    cur_start_dt = f"{start_date} 00:00:00"
    cur_end_dt = f"{end_date} 23:59:59"
    cutoff_date = date(int(start_date[:4]), int(start_date[5:7]), 1) - timedelta(days=1)
    cutoff = cutoff_date.strftime("%Y-%m-%d")

    refund_where = "AND is_refund = FALSE" if metric_type == "GSV" else ""

    # 渠道条件 - base_orders（回购订单）
    channel_where_base = ""
    base_params_extra: List = []
    if channel and channel != "全店":
        db_ch = expand_channels([channel])
        if len(db_ch) == 1:
            channel_where_base = " AND o.channel = ?"
            base_params_extra = [db_ch[0]]
        else:
            ph = ",".join(["?"] * len(db_ch))
            channel_where_base = f" AND o.channel IN ({ph})"
            base_params_extra = list(db_ch)

    # 渠道条件 - history（same_channel / member_same_channel 限渠道）
    channel_where_hist = ""
    hist_params_extra: List = []
    if mode in ("same_channel", "member_same_channel") and channel and channel != "全店":
        db_ch = expand_channels([channel])
        if len(db_ch) == 1:
            channel_where_hist = " AND o.channel = ?"
            hist_params_extra = [db_ch[0]]
        else:
            ph = ",".join(["?"] * len(db_ch))
            channel_where_hist = f" AND o.channel IN ({ph})"
            hist_params_extra = list(db_ch)

    # 排除渠道（统一参数化，避免 SQL 注入风险）
    # db_exc 同时用于 hist_sql（CTE 内）和 target_orders（CTE 外），需要追加到两处 params
    exc_params: List[str] = []
    exclude_where_base = ""
    exclude_where_hist = ""
    if exclude_channels:
        db_exc = expand_channels(exclude_channels)
        exc_params = list(db_exc)  # 保持独立副本
        exc_placeholders = ",".join(["?"] * len(db_exc))
        exclude_where_base = f" AND o.channel NOT IN ({exc_placeholders})"
        exclude_where_hist = f" AND o.channel NOT IN ({exc_placeholders})"

    member_where = "AND hc.is_member = TRUE" if mode in ("member", "member_same_channel") else ""

    # 维度分段
    if dimension == "r":
        seg_case = """CASE
            WHEN recency_days BETWEEN 0 AND 30 THEN '近1个月已购客'
            WHEN recency_days BETWEEN 31 AND 90 THEN '近2-3个月已购客'
            WHEN recency_days BETWEEN 91 AND 180 THEN '近4-6月已购客'
            WHEN recency_days BETWEEN 181 AND 365 THEN '近7-12个月已购客'
            WHEN recency_days BETWEEN 366 AND 730 THEN '近13个月-近24个月已购客'
            WHEN recency_days > 730 THEN '2年外已购客'
        END AS segment_label"""
        hist_sql = (
            "SELECT user_id, DATEDIFF('day', MAX(pay_time)::DATE, ?::DATE) AS recency_days, "
            "0 AS frequency, 0 AS monetary, BOOL_OR(is_member) AS is_member "
            "FROM orders o "
            f"WHERE pay_time <= ?::TIMESTAMP AND {_VALID_BASE} "
            f"{refund_where} {channel_where_hist} {exclude_where_hist} "
            "GROUP BY user_id"
        )
        hist_params: List = [cutoff, cutoff] + hist_params_extra + exc_params
    elif dimension == "f":
        seg_case = """CASE
            WHEN frequency = 1 THEN '1次购买'
            WHEN frequency = 2 THEN '2次购买'
            WHEN frequency = 3 THEN '3次购买'
            WHEN frequency = 4 THEN '4次购买'
            ELSE '5次及以上'
        END AS segment_label"""
        hist_sql = (
            "SELECT user_id, DATEDIFF('day', MAX(pay_time)::DATE, ?::DATE) AS recency_days, "
            "COUNT(*) AS frequency, 0 AS monetary, BOOL_OR(is_member) AS is_member "
            "FROM orders o "
            f"WHERE pay_time <= ?::TIMESTAMP AND {_VALID_BASE} "
            f"{refund_where} {channel_where_hist} {exclude_where_hist} "
            "GROUP BY user_id"
        )
        hist_params = [cutoff, cutoff] + hist_params_extra + exc_params
    elif dimension == "m":
        seg_case = """CASE
            WHEN monetary < 100 THEN '0-100元'
            WHEN monetary < 300 THEN '100-300元'
            WHEN monetary < 500 THEN '300-500元'
            WHEN monetary < 1000 THEN '500-1000元'
            ELSE '1000元以上'
        END AS segment_label"""
        hist_sql = (
            "SELECT user_id, DATEDIFF('day', MAX(pay_time)::DATE, ?::DATE) AS recency_days, "
            "0 AS frequency, SUM(actual_amount) AS monetary, BOOL_OR(is_member) AS is_member "
            "FROM orders o "
            f"WHERE pay_time <= ?::TIMESTAMP AND {_VALID_BASE} "
            f"{refund_where} {channel_where_hist} {exclude_where_hist} "
            "GROUP BY user_id"
        )
        hist_params = [cutoff, cutoff] + hist_params_extra + exc_params
    else:
        raise ValueError(f"Invalid dimension: {dimension}")

    sql = f"""
    WITH
    hist_customers AS ({hist_sql}),
    hist_segmented AS (
        SELECT user_id, is_member, {seg_case}
        FROM hist_customers hc
        WHERE 1=1 {member_where}
    ),
    target_users AS (
        SELECT user_id FROM hist_segmented WHERE segment_label = ?
    ),
    target_orders AS (
        SELECT o.order_id, o.user_id,
               CAST(o.pay_time AS VARCHAR) AS pay_time,
               o.actual_amount, o.channel, o.spu_product_class
        FROM orders o
        INNER JOIN target_users tu ON o.user_id = tu.user_id
        WHERE o.pay_time >= ?::TIMESTAMP
          AND o.pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE_T}
          {refund_where}
          {channel_where_base}
          {exclude_where_base}
    )
    SELECT order_id, user_id, pay_time, actual_amount, channel, spu_product_class
    FROM target_orders
    ORDER BY pay_time DESC
    """

    params = hist_params + [segment, cur_start_dt, cur_end_dt] + base_params_extra + exc_params

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    order_rows = []
    for r in rows:
        order_rows.append({
            "order_id": str(r[0]) if r[0] else "",
            "user_id": str(r[1]) if r[1] else "",
            "pay_time": str(r[2]) if r[2] else "",
            "actual_amount": float(r[3] or 0),
            "channel": str(r[4]) if r[4] else "",
            "spu_product_class": str(r[5]) if r[5] else None,
        })

    return {
        "dimension": dimension,
        "segment": segment,
        "mode": mode,
        "total_orders": len(order_rows),
        "rows": order_rows,
    }
