"""
芙清 CRM - RFM Flow 通用引擎

将 R/F/M 三个维度的区间流转逻辑抽象为参数化引擎。
三个维度的差异仅在于：
  - hist_extra_cols: 历史 CTE 额外聚合列（F: frequency, M: monetary, R: 无）
  - segmentation_cte: 分段 CASE WHEN 逻辑
  - segment_order: 区间排序列表
  - segment_col: 分段列名（r_segment / f_segment / m_segment）
  - data_col: 分段依据列名（recency_days / frequency / monetary）
"""

import duckdb

from typing import Any, Dict, List, Optional, Tuple

from backend.semantic.calculations import yoy_absolute, yoy_repurchase_rate
from backend.db.connection import get_connection
from backend.services.rfm._shared import (
    _VALID_BASE,
    _resolve_date_ranges,
    _fetch_data_version, _flow_cache_key,
    _get_cached_flow, _set_cached_flow,
)


# ============================================================
# 渠道过滤 SQL 构建（公共逻辑）
# ============================================================

def _build_channel_filter(
    channel: Optional[str],
    exclude_channels: Optional[List[str]],
) -> Tuple[str, str, str, str, List, List]:
    """
    构建 base / hist 的渠道过滤 SQL 片段和参数。

    返回:
        channel_where_base, channel_where_hist,
        exclude_where_base, exclude_where_hist,
        base_extra_params, hist_same_extra_params
    """
    base_extra_params: List = []
    hist_same_extra_params: List = []

    channel_where_base = ""
    channel_where_hist = ""
    if channel and channel != "全店":
        from backend.semantic.filters import expand_channels
        db_channels = expand_channels([channel])
        if len(db_channels) == 1:
            channel_where_base = " AND o.channel = ?"
            channel_where_hist = " AND o.channel = ?"
            base_extra_params.append(db_channels[0])
            hist_same_extra_params.append(db_channels[0])
        else:
            placeholders = ",".join(["?"] * len(db_channels))
            channel_where_base = f" AND o.channel IN ({placeholders})"
            channel_where_hist = f" AND o.channel IN ({placeholders})"
            base_extra_params.extend(db_channels)
            hist_same_extra_params.extend(db_channels)

    exclude_where_base = ""
    exclude_where_hist = ""
    if exclude_channels:
        from backend.semantic.filters import expand_channels
        db_exclude_channels = expand_channels(exclude_channels)
        safe_ch = [ch.replace("'", "''") for ch in db_exclude_channels]
        quoted = ", ".join([f"'{c}'" for c in safe_ch])
        exclude_where_base = f" AND o.channel NOT IN ({quoted})"
        exclude_where_hist = f" AND o.channel NOT IN ({quoted})"

    return (
        channel_where_base, channel_where_hist,
        exclude_where_base, exclude_where_hist,
        base_extra_params, hist_same_extra_params,
    )


# ============================================================
# 结果解析（公共逻辑）
# ============================================================

_DEFAULT_ENTRY = {
    "hist_users": 0,
    "repurchase_users": 0,
    "repurchase_rate": 0.0,
    "repurchase_gsv": 0.0,
    "repurchase_gsv_ratio": 0.0,
}


def _parse_flow_rows(
    rows: list,
    segment_order: List[str],
) -> Tuple[
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
]:
    """
    解析 SQL 结果行，计算 repurchase_rate / repurchase_gsv_ratio，
    补全缺失 segment。返回 (all, same, member_all, member_same)。
    """
    all_result: Dict[str, Dict[str, float]] = {}
    same_result: Dict[str, Dict[str, float]] = {}
    member_all_result: Dict[str, Dict[str, float]] = {}
    member_same_result: Dict[str, Dict[str, float]] = {}
    totals = {"all": 0.0, "same": 0.0, "member_all": 0.0, "member_same": 0.0}

    result_map = {
        "all": all_result,
        "same": same_result,
        "member_all": member_all_result,
        "member_same": member_same_result,
    }

    for r in rows:
        mode, segment, hist_users, repurchase_users, repurchase_gsv = r
        entry = {
            "hist_users": int(hist_users or 0),
            "repurchase_users": int(repurchase_users or 0),
            "repurchase_rate": float(repurchase_users or 0) / float(hist_users or 1) if hist_users else 0.0,
            "repurchase_gsv": float(repurchase_gsv or 0),
            "repurchase_gsv_ratio": 0.0,
        }
        target = result_map.get(mode)
        if target is None:
            continue
        target[segment] = entry
        if segment != "已购客TTL":
            totals[mode] += float(repurchase_gsv or 0)

    # 计算 gsv_ratio
    for mode, result in result_map.items():
        total = totals[mode]
        for seg in result:
            gsv = result[seg]["repurchase_gsv"]
            result[seg]["repurchase_gsv_ratio"] = gsv / total if total > 0 else 0.0

    # 补全缺失 segment
    for seg in segment_order:
        for result in result_map.values():
            if seg not in result:
                result[seg] = dict(_DEFAULT_ENTRY)

    return all_result, same_result, member_all_result, member_same_result


# ============================================================
# 单周期执行引擎
# ============================================================

def run_flow_period(
    conn: duckdb.DuckDBPyConnection,
    start_dt: str,
    end_dt: str,
    cutoff_dt: str,
    dimension: str,
    segment_order: List[str],
    hist_extra_cols: str,
    segmentation_cte: str,
    channel: Optional[str] = None,
    metric_type: str = "GSV",
    exclude_channels: Optional[List[str]] = None,
) -> Tuple[
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
]:
    """
    执行单个周期的 RFM 区间流转查询。

    Args:
        conn: DuckDB 连接
        start_dt: 周期开始时间
        end_dt: 周期结束时间
        cutoff_dt: 历史截止日期
        dimension: 维度名（"r"/"f"/"m"），用作 segment 列名前缀
        segment_order: 区间排序列表
        hist_extra_cols: 历史 CTE 额外聚合列，如 "COUNT(*) AS frequency" 或 ""
        segmentation_cte: 分段 CTE 定义（含 {alias} 占位符）
        channel: 渠道过滤
        metric_type: 指标类型（GSV/GMV）
        exclude_channels: 排除渠道列表

    Returns: (all_result, same_result, member_all_result, member_same_result)
    """
    seg_col = f"{dimension}_segment"

    # 渠道过滤
    (
        channel_where_base, channel_where_hist,
        exclude_where_base, exclude_where_hist,
        base_extra, hist_same_extra,
    ) = _build_channel_filter(channel, exclude_channels)

    base_params = [start_dt, end_dt] + base_extra
    hist_all_params = [cutoff_dt, cutoff_dt]
    hist_same_params = [cutoff_dt, cutoff_dt] + hist_same_extra

    full_params = base_params + hist_all_params + hist_same_params

    refund_where = "AND is_refund = FALSE" if metric_type == "GSV" else ""

    # 额外列的逗号前缀（有内容时加 ",\n            "）
    extra_prefix = f",\n            {hist_extra_cols}" if hist_extra_cols else ""

    # 格式化 segmentation CTE（替换 {alias} 占位符）
    seg_all = segmentation_cte.replace("{alias}", "all")
    seg_same = segmentation_cte.replace("{alias}", "same")

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
            DATEDIFF('day', MAX(pay_time)::DATE, ?::DATE) AS recency_days
            {extra_prefix},
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
            DATEDIFF('day', MAX(pay_time)::DATE, ?::DATE) AS recency_days
            {extra_prefix},
            BOOL_OR(is_member) AS is_member
        FROM orders o
        WHERE pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE}
          {refund_where}
          {channel_where_hist}
          {exclude_where_hist}
        GROUP BY user_id
    ),
    {seg_all},
    {seg_same},
    member_segmented_all AS (
        SELECT user_id, {seg_col} FROM {dimension}_segmented_all WHERE is_member = TRUE
    ),
    member_segmented_same AS (
        SELECT user_id, {seg_col} FROM {dimension}_segmented_same WHERE is_member = TRUE
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
            s.{seg_col},
            COUNT(DISTINCT s.user_id) AS hist_users,
            COUNT(DISTINCT rp.user_id) AS repurchase_users,
            COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM {dimension}_segmented_all s
        LEFT JOIN repurchase_users rp ON s.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON s.user_id = ra.user_id
        GROUP BY s.{seg_col}
    ),
    segment_stats_same AS (
        SELECT
            s.{seg_col},
            COUNT(DISTINCT s.user_id) AS hist_users,
            COUNT(DISTINCT rp.user_id) AS repurchase_users,
            COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM {dimension}_segmented_same s
        LEFT JOIN repurchase_users rp ON s.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON s.user_id = ra.user_id
        GROUP BY s.{seg_col}
    ),
    member_stats_all AS (
        SELECT
            s.{seg_col},
            COUNT(DISTINCT s.user_id) AS hist_users,
            COUNT(DISTINCT rp.user_id) AS repurchase_users,
            COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM member_segmented_all s
        LEFT JOIN repurchase_users rp ON s.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON s.user_id = ra.user_id
        GROUP BY s.{seg_col}
    ),
    member_stats_same AS (
        SELECT
            s.{seg_col},
            COUNT(DISTINCT s.user_id) AS hist_users,
            COUNT(DISTINCT rp.user_id) AS repurchase_users,
            COALESCE(SUM(ra.repurchase_gsv), 0) AS repurchase_gsv
        FROM member_segmented_same s
        LEFT JOIN repurchase_users rp ON s.user_id = rp.user_id
        LEFT JOIN repurchase_amounts ra ON s.user_id = ra.user_id
        GROUP BY s.{seg_col}
    ),
    ttl_stats_all AS (
        SELECT '已购客TTL' AS {seg_col}, SUM(hist_users) AS hist_users, SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv FROM segment_stats_all
    ),
    ttl_stats_same AS (
        SELECT '已购客TTL' AS {seg_col}, SUM(hist_users) AS hist_users, SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv FROM segment_stats_same
    ),
    member_ttl_stats_all AS (
        SELECT '已购客TTL' AS {seg_col}, SUM(hist_users) AS hist_users, SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv FROM member_stats_all
    ),
    member_ttl_stats_same AS (
        SELECT '已购客TTL' AS {seg_col}, SUM(hist_users) AS hist_users, SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv FROM member_stats_same
    )
    SELECT 'all' AS mode, {seg_col}, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM segment_stats_all UNION ALL SELECT * FROM ttl_stats_all
    )
    UNION ALL
    SELECT 'same' AS mode, {seg_col}, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM segment_stats_same UNION ALL SELECT * FROM ttl_stats_same
    )
    UNION ALL
    SELECT 'member_all' AS mode, {seg_col}, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM member_stats_all UNION ALL SELECT * FROM member_ttl_stats_all
    )
    UNION ALL
    SELECT 'member_same' AS mode, {seg_col}, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM member_stats_same UNION ALL SELECT * FROM member_ttl_stats_same
    )
    """

    rows = conn.execute(sql, full_params).fetchall()
    return _parse_flow_rows(rows, segment_order)


# ============================================================
# 流转看板接口引擎
# ============================================================

def get_rfm_flow(
    dimension: str,
    segment_order: List[str],
    hist_extra_cols: str,
    segmentation_cte: str,
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
    RFM 区间流转看板通用接口。

    Args:
        dimension: 维度名（"r"/"f"/"m"）
        segment_order: 区间排序列表
        hist_extra_cols: 历史 CTE 额外聚合列
        segmentation_cte: 分段 CTE 定义模板
        其余参数同 get_rfm_r_flow

    Returns: 包含 rows / same_channel_rows / member_rows / member_same_channel_rows 的字典
    """
    flow_type = f"{dimension}_flow"
    seg_col = f"{dimension}_segment"

    ranges = _resolve_date_ranges(period, start_date, end_date, compare_start_date, compare_end_date)
    cur_start_dt, cur_end_dt, cutoff = ranges["current"]
    comp_start_dt, comp_end_dt, comp_cutoff = ranges["comp"]
    prev2_start_dt, prev2_end_dt, prev2_cutoff = ranges["prev2"]
    current_year_label, comp_year_label, prev2_year_label = ranges["labels"]

    # 缓存检查
    data_version = _fetch_data_version()
    cache_key = _flow_cache_key(
        flow_type, start_date or "", end_date or "",
        channel, metric_type, exclude_channels,
        compare_start_date, compare_end_date, data_version,
    )
    cached = _get_cached_flow(cache_key, data_version)
    if cached is not None:
        return cached

    conn = get_connection()
    try:
        cur_all, cur_same, cur_member_all, cur_member_same = run_flow_period(
            conn, cur_start_dt, cur_end_dt, cutoff,
            dimension, segment_order, hist_extra_cols, segmentation_cte,
            channel, metric_type, exclude_channels,
        )
        comp_all, comp_same, comp_member_all, comp_member_same = run_flow_period(
            conn, comp_start_dt, comp_end_dt, comp_cutoff,
            dimension, segment_order, hist_extra_cols, segmentation_cte,
            channel, metric_type, exclude_channels,
        )
        prev2_all, prev2_same, prev2_member_all, prev2_member_same = run_flow_period(
            conn, prev2_start_dt, prev2_end_dt, prev2_cutoff,
            dimension, segment_order, hist_extra_cols, segmentation_cte,
            channel, metric_type, exclude_channels,
        )
    finally:
        pass

    def _build_rows(all_data, comp_data, prev2_data):
        rows = []
        for seg in segment_order:
            c = all_data.get(seg, {})
            p = comp_data.get(seg, {})
            p2 = prev2_data.get(seg, {})
            rows.append({
                seg_col: seg,
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

    _set_cached_flow(cache_key, data_version, result)
    return result
