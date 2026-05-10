"""
RFM 品类下钻服务

点击回购率柱状图中的象限 → 展开该象限下各品类的回购率拆解。
"""

import duckdb
from typing import Dict, Any, List, Optional

from backend.db.connection import get_connection
from backend.services.rfm_service import _resolve_date_ranges
from backend.semantic.calculations import yoy_absolute, yoy_repurchase_rate
from backend.services.health.rfm_crosstab import build_rfm_segment_sql


def _run_category_period(
    conn: duckdb.DuckDBPyConnection,
    start_dt: str,
    end_dt: str,
    cutoff_dt: str,
    rfm_segment: str,
    channel: Optional[str] = None,
    metric_type: str = "GSV",
    exclude_channels: Optional[List[str]] = None,
    is_member: bool = False,
) -> Dict[str, Dict[str, float]]:
    """
    执行单个周期的品类回购统计（针对特定 RFM 象限）。

    Parameters
    ----------
    conn : duckdb.DuckDBPyConnection
        DuckDB 连接
    start_dt : str
        分析期开始（含时间）
    end_dt : str
        分析期结束（含时间）
    cutoff_dt : str
        历史截止日期
    rfm_segment : str
        目标 RFM 象限名称，如"重要价值客户"
    channel : Optional[str]
        渠道筛选
    metric_type : str
        GSV（默认）或 GMV
    exclude_channels : Optional[List[str]]
        排除渠道列表
    is_member : bool
        True=仅会员，False=全部用户

    Returns
    -------
    Dict[str, Dict[str, float]]
        key=category_name，value={hist_users, repurchase_users, repurchase_rate,
        repurchase_gsv, repurchase_gsv_ratio}
    """
    # 构建 RFM 分群 CTE
    rfm_cte_sql, rfm_params = build_rfm_segment_sql(cutoff_dt, channel, exclude_channels)

    # 渠道条件
    base_params: List = [start_dt, end_dt]
    channel_where_base = ""
    channel_where_hist = ""
    if channel and channel != "全店":
        from backend.semantic.filters import expand_channels
        db_channels = expand_channels([channel])
        if len(db_channels) == 1:
            channel_where_base = " AND o.channel = ?"
            channel_where_hist = " AND o.channel = ?"
            base_params.append(db_channels[0])
        else:
            placeholders = ",".join(["?"] * len(db_channels))
            channel_where_base = f" AND o.channel IN ({placeholders})"
            channel_where_hist = f" AND o.channel IN ({placeholders})"
            base_params.extend(db_channels)

    exclude_where_base = ""
    exclude_where_hist = ""
    if exclude_channels:
        from backend.semantic.filters import expand_channels
        db_exclude = expand_channels(exclude_channels)
        safe_ch = [ch.replace("'", "''") for ch in db_exclude]
        quoted = ", ".join([f"'{c}'" for c in safe_ch])
        exclude_where_base = f" AND o.channel NOT IN ({quoted})"
        exclude_where_hist = f" AND o.channel NOT IN ({quoted})"

    refund_where = "AND is_refund = FALSE" if metric_type == "GSV" else ""

    # member 筛选
    member_where = "AND sa.is_member = TRUE" if is_member else ""
    target_table = "member_segmented_all" if is_member else "segmented_all"

    # 完整参数顺序：
    # base_orders: start_dt, end_dt, [channel]
    # user_stats_all: cutoff_dt
    # user_stats_same: cutoff_dt
    # rfm_scored_all: cutoff_dt × 4
    # rfm_scored_same: cutoff_dt × 4
    # 合并后 + exclude_channels 占位（如果有）
    params = base_params + rfm_params

    sql = f"""
    WITH
    {rfm_cte_sql},
    base_orders AS (
        SELECT user_id, actual_amount, COALESCE(o.spu_product_class, '未知') AS category
        FROM orders o
        INNER JOIN {target_table} sa ON o.user_id = sa.user_id
        WHERE o.pay_time >= ?::TIMESTAMP
          AND o.pay_time <= ?::TIMESTAMP
          AND is_goujinjin = FALSE
          AND order_status != '交易关闭'
          {refund_where}
          {channel_where_base}
          {exclude_where_base}
    ),
    category_hist AS (
        SELECT DISTINCT
            COALESCE(o.spu_product_class, '未知') AS category,
            sa.user_id
        FROM orders o
        INNER JOIN {target_table} sa ON o.user_id = sa.user_id
        WHERE o.pay_time <= ?::TIMESTAMP
          AND is_goujinjin = FALSE
          AND order_status != '交易关闭'
          {refund_where}
          {exclude_where_hist}
          {member_where}
    ),
    category_repurchase AS (
        SELECT
            bo.category,
            bo.user_id,
            SUM(bo.actual_amount) AS repurchase_gsv
        FROM base_orders bo
        GROUP BY bo.category, bo.user_id
    ),
    category_stats AS (
        SELECT
            ch.category,
            COUNT(DISTINCT ch.user_id) AS hist_users,
            COUNT(DISTINCT cr.user_id) AS repurchase_users,
            COALESCE(SUM(cr.repurchase_gsv), 0) AS repurchase_gsv
        FROM (SELECT DISTINCT category, user_id FROM category_hist) ch
        LEFT JOIN category_repurchase cr ON ch.user_id = cr.user_id AND ch.category = cr.category
        GROUP BY ch.category
    )
    SELECT
        category,
        hist_users,
        repurchase_users,
        repurchase_gsv,
        CASE WHEN hist_users > 0 THEN repurchase_users::DOUBLE / hist_users ELSE 0 END AS repurchase_rate
    FROM category_stats
    WHERE hist_users >= 10
    ORDER BY repurchase_gsv DESC
    """

    # base_orders 额外参数: start_dt, end_dt, [channel]
    extra_params = [start_dt, end_dt]
    if channel and channel != "全店":
        from backend.semantic.filters import expand_channels
        db_channels = expand_channels([channel])
        extra_params.extend(db_channels)

    all_params = params + extra_params

    rows = conn.execute(sql, all_params).fetchall()

    result: Dict[str, Dict[str, float]] = {}
    total_repurchase_gsv = 0.0
    for r in rows:
        category, hist_users, repurchase_users, repurchase_gsv = r
        repurchase_rate = float(repurchase_users or 0) / float(hist_users or 1) if hist_users else 0.0
        result[category] = {
            "hist_users": int(hist_users or 0),
            "repurchase_users": int(repurchase_users or 0),
            "repurchase_rate": repurchase_rate,
            "repurchase_gsv": float(repurchase_gsv or 0),
            "repurchase_gsv_ratio": 0.0,  # 待后续填充
        }
        total_repurchase_gsv += float(repurchase_gsv or 0)

    # 计算 repurchase_gsv_ratio
    for category in result:
        gsv = result[category]["repurchase_gsv"]
        result[category]["repurchase_gsv_ratio"] = gsv / total_repurchase_gsv if total_repurchase_gsv > 0 else 0.0

    return result


def get_rfm_category_drilldown(
    rfm_segment: str,
    period: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    metric_type: str = "GSV",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
    compare_start_date: Optional[str] = None,
    compare_end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    RFM 品类下钻 API。

    返回指定 RFM 象限在各品类的回购率拆解（当前期/对比期/前年期）。

    Parameters
    ----------
    rfm_segment : str
        RFM 象限名称，如"重要价值客户"
    period : Optional[str]
        周期名称（如 "YTD"、"MTD"），与 start_date/end_date 二选一
    start_date : Optional[str]
        分析期开始日期 YYYY-MM-DD
    end_date : Optional[str]
        分析期结束日期 YYYY-MM-DD
    metric_type : str
        GSV（默认）或 GMV
    channel : Optional[str]
        渠道筛选
    exclude_channels : Optional[List[str]]
        排除渠道列表
    compare_start_date : Optional[str]
        自定义对比期开始日期
    compare_end_date : Optional[str]
        自定义对比期结束日期

    Returns
    -------
    Dict[str, Any]
        包含 categories / member_categories / summary 的完整响应结构
    """
    # 解析日期范围
    ranges = _resolve_date_ranges(period, start_date, end_date, compare_start_date, compare_end_date)
    cur_start_dt, cur_end_dt, cutoff = ranges["current"]
    comp_start_dt, comp_end_dt, comp_cutoff = ranges["comp"]
    prev2_start_dt, prev2_end_dt, prev2_cutoff = ranges["prev2"]
    current_year_label, comp_year_label, prev2_year_label = ranges["labels"]

    conn = get_connection()
    try:
        # 执行3个周期的品类统计（全店 + 会员）
        cur_all = _run_category_period(
            conn, cur_start_dt, cur_end_dt, cutoff, rfm_segment,
            channel, metric_type, exclude_channels, is_member=False
        )
        comp_all = _run_category_period(
            conn, comp_start_dt, comp_end_dt, comp_cutoff, rfm_segment,
            channel, metric_type, exclude_channels, is_member=False
        )
        prev2_all = _run_category_period(
            conn, prev2_start_dt, prev2_end_dt, prev2_cutoff, rfm_segment,
            channel, metric_type, exclude_channels, is_member=False
        )

        cur_member = _run_category_period(
            conn, cur_start_dt, cur_end_dt, cutoff, rfm_segment,
            channel, metric_type, exclude_channels, is_member=True
        )
        comp_member = _run_category_period(
            conn, comp_start_dt, comp_end_dt, comp_cutoff, rfm_segment,
            channel, metric_type, exclude_channels, is_member=True
        )
        prev2_member = _run_category_period(
            conn, prev2_start_dt, prev2_end_dt, prev2_cutoff, rfm_segment,
            channel, metric_type, exclude_channels, is_member=True
        )
    finally:
        conn.close()

    # 构建品类行列表
    def _build_rows(
        cur_data: Dict[str, Dict[str, float]],
        comp_data: Dict[str, Dict[str, float]],
        prev2_data: Dict[str, Dict[str, float]],
    ) -> List[Dict[str, Any]]:
        # 合并所有品类
        all_categories = set(list(cur_data.keys()) + list(comp_data.keys()) + list(prev2_data.keys()))
        rows = []
        for category in sorted(all_categories, key=lambda c: cur_data.get(c, {}).get("repurchase_gsv", 0), reverse=True):
            c = cur_data.get(category, {})
            p = comp_data.get(category, {})
            p2 = prev2_data.get(category, {})
            rows.append({
                "category_name": category,
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

    categories = _build_rows(cur_all, comp_all, prev2_all)
    member_categories = _build_rows(cur_member, comp_member, prev2_member)

    # 构建 summary
    total_hist = sum(c.get("hist_users_current", 0) for c in categories)
    total_repurchase = sum(c.get("repurchase_users_current", 0) for c in categories)
    overall_rate = float(total_repurchase) / float(total_hist) if total_hist > 0 else 0.0

    total_hist_comp = sum(c.get("hist_users_comp", 0) for c in categories)
    total_repurchase_comp = sum(c.get("repurchase_users_comp", 0) for c in categories)
    overall_rate_comp = float(total_repurchase_comp) / float(total_hist_comp) if total_hist_comp > 0 else 0.0
    overall_rate_yoy = yoy_repurchase_rate(overall_rate, overall_rate_comp)

    # 找出下滑/上升品类
    declining = []
    improving = []
    for c in categories:
        yoy_rate = c.get("yoy_repurchase_rate")
        if yoy_rate is not None and yoy_rate < 0:
            declining.append({"name": c["category_name"], "yoy_repurchase_rate": round(yoy_rate, 4)})
        elif yoy_rate is not None and yoy_rate > 0:
            improving.append({"name": c["category_name"], "yoy_repurchase_rate": round(yoy_rate, 4)})

    # 按 yoy 降序排列
    declining.sort(key=lambda x: x["yoy_repurchase_rate"])
    improving.sort(key=lambda x: x["yoy_repurchase_rate"], reverse=True)

    summary = {
        "total_hist_users": total_hist,
        "total_repurchase_users": total_repurchase,
        "overall_repurchase_rate": round(overall_rate, 4),
        "overall_repurchase_rate_comp": round(overall_rate_comp, 4),
        "overall_repurchase_rate_yoy": overall_rate_yoy if overall_rate_yoy is not None else 0.0,
        "declining_categories": declining[:10],   # 最多10个
        "improving_categories": improving[:10],
    }

    return {
        "rfm_segment": rfm_segment,
        "year_label": current_year_label,
        "comp_year_label": comp_year_label,
        "prev2_year_label": prev2_year_label,
        "metric_type": metric_type,
        "categories": categories,
        "member_categories": member_categories,
        "summary": summary,
    }
