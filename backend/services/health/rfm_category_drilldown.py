"""
RFM 品类下钻服务

点击回购率柱状图中的象限 → 展开该象限下各品类的回购率拆解。
"""

import duckdb
from typing import Dict, Any, List, Optional, Tuple

from backend.db.connection import get_connection
from backend.services.rfm import _resolve_date_ranges
from backend.semantic.calculations import yoy_absolute, yoy_repurchase_rate
from backend.semantic.segments import RFM_THRESHOLDS, SEGMENTS
from backend.semantic.filters import VALID_ORDER_BASE

# 语义层统一口径（向后兼容别名）
_VALID_BASE = VALID_ORDER_BASE


# ============================================================
# 8象限中文名称常量（单一数据源，禁止手写字符串）
# ============================================================
RFM_SEGMENT_NAMES: List[str] = [s.name_cn for s in SEGMENTS if s.segment_id != 9]

_R_SEGMENT_CASE_WHEN = "".join([
    f"WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN '{s.name_cn.replace("'", "''")}'"
    if s.segment_id == 1 else
    f"WHEN r_score < 4 AND f_score >= 4 AND m_score >= 4 THEN '{s.name_cn.replace("'", "''")}'"
    if s.segment_id == 2 else
    f"WHEN r_score >= 4 AND f_score < 4 AND m_score >= 4 THEN '{s.name_cn.replace("'", "''")}'"
    if s.segment_id == 3 else
    f"WHEN r_score < 4 AND f_score < 4 AND m_score >= 4 THEN '{s.name_cn.replace("'", "''")}'"
    if s.segment_id == 4 else
    f"WHEN r_score >= 4 AND f_score >= 4 AND m_score < 4 THEN '{s.name_cn.replace("'", "''")}'"
    if s.segment_id == 5 else
    f"WHEN r_score < 4 AND f_score >= 4 AND m_score < 4 THEN '{s.name_cn.replace("'", "''")}'"
    if s.segment_id == 6 else
    f"WHEN r_score >= 4 AND f_score < 4 AND m_score < 4 THEN '{s.name_cn.replace("'", "''")}'"
    if s.segment_id == 7 else
    f"ELSE '{s.name_cn.replace("'", "''")}'"
    for s in SEGMENTS if s.segment_id != 9
])


def _build_exclude_condition(
    exclude_channels: Optional[List[str]], alias: str
) -> Tuple[str, List[str]]:
    """
    构建参数化的 NOT IN 子句，返回 (sql_fragment, params)。

    Parameters
    ----------
    exclude_channels : Optional[List[str]]
        排除渠道列表
    alias : str
        表别名，如 "o"

    Returns
    -------
    Tuple[str, List[str]]
        (sql_fragment, params) — sql_fragment 可能为空字符串
    """
    if not exclude_channels:
        return "", []
    from backend.semantic.filters import expand_channels
    db_exclude = expand_channels(exclude_channels)
    placeholders = ",".join(["?"] * len(db_exclude))
    return f" AND {alias}.channel NOT IN ({placeholders})", db_exclude


def _build_segmented_cte(source_table: str) -> str:
    """生成 segmented_{suffix} CTE，复用同一套 CASE WHEN 逻辑。"""
    return f"""
        SELECT user_id, is_member,
            CASE {_R_SEGMENT_CASE_WHEN} END as rfm_segment
        FROM {source_table}
    """


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
    _rt = RFM_THRESHOLDS["r"]   # [30, 90, 180, 365]
    _ft = RFM_THRESHOLDS["f"]   # [1, 2, 3, 4]
    _mt = RFM_THRESHOLDS["m"]   # [100, 300, 500, 1000]

    # ---------------------------------------------------------------
    # 参数顺序 = SQL 文本中 ? 的顺序（关键：避免 DuckDB CTE 链错位）
    # ---------------------------------------------------------------
    # 1. user_stats_all:  cutoff_dt, [channel], [exclude]
    # 2. user_stats_same: cutoff_dt, [channel], [exclude]
    # 3. rfm_scored_all:  cutoff_dt x 4
    # 4. rfm_scored_same: cutoff_dt x 4
    # 5. base_orders:     start_dt, end_dt, [channel], [exclude], rfm_segment
    # 6. category_hist:   cutoff_dt, [exclude], rfm_segment
    # ---------------------------------------------------------------

    params: List[Any] = []

    # -- exclude_channels: 参数化 NOT IN（共享展开结果） --
    exclude_where_base, exclude_params_base = _build_exclude_condition(exclude_channels, "o")
    exclude_where_hist, exclude_params_hist = _build_exclude_condition(exclude_channels, "o")

    # -- user_stats_all: cutoff_dt, [channel], [exclude] --
    params.append(cutoff_dt)  # user_stats_all cutoff_dt
    channel_where_all = ""
    if channel and channel != "全店":
        from backend.semantic.filters import expand_channels
        db_channels = expand_channels([channel])
        if len(db_channels) == 1:
            channel_where_all = " AND o.channel = ?"
            params.append(db_channels[0])
        else:
            placeholders = ",".join(["?"] * len(db_channels))
            channel_where_all = f" AND o.channel IN ({placeholders})"
            params.extend(db_channels)
    params.extend(exclude_params_base)  # exclude for user_stats_all

    # -- user_stats_same: cutoff_dt, [channel], [exclude] --
    params.append(cutoff_dt)  # user_stats_same cutoff_dt
    channel_where_same = ""
    if channel and channel != "全店":
        from backend.semantic.filters import expand_channels
        db_channels = expand_channels([channel])
        if len(db_channels) == 1:
            channel_where_same = " AND o.channel = ?"
            params.append(db_channels[0])
        else:
            placeholders = ",".join(["?"] * len(db_channels))
            channel_where_same = f" AND o.channel IN ({placeholders})"
            params.extend(db_channels)
    params.extend(exclude_params_hist)  # exclude for user_stats_same

    # -- rfm_scored_all: cutoff_dt x 4 --
    params.extend([cutoff_dt] * 4)
    # -- rfm_scored_same: cutoff_dt x 4 --
    params.extend([cutoff_dt] * 4)

    # -- base_orders: start_dt, end_dt, [channel], [exclude], rfm_segment --
    params.append(start_dt)
    params.append(end_dt)
    channel_where_base = ""
    if channel and channel != "全店":
        from backend.semantic.filters import expand_channels
        db_channels = expand_channels([channel])
        if len(db_channels) == 1:
            channel_where_base = " AND o.channel = ?"
            params.append(db_channels[0])
        else:
            placeholders = ",".join(["?"] * len(db_channels))
            channel_where_base = f" AND o.channel IN ({placeholders})"
            params.extend(db_channels)
    params.extend(exclude_params_base)  # exclude for base_orders
    params.append(rfm_segment)          # base_orders rfm_segment

    # -- category_hist: cutoff_dt, [exclude], rfm_segment --
    params.append(cutoff_dt)
    params.extend(exclude_params_hist)  # exclude for category_hist
    params.append(rfm_segment)          # category_hist rfm_segment

    # -- refund 过滤条件 --
    refund_where = "AND is_refund = FALSE" if metric_type == "GSV" else ""

    # -- member 过滤直接在 category_hist 中处理，不单独走 target_table --
    member_where_hist = "AND sa.is_member = TRUE" if is_member else ""

    # -- rfm_segment 验证（在参数追加之后，确保参数列表完整） --
    if rfm_segment not in RFM_SEGMENT_NAMES:
        raise ValueError(f"无效的 RFM 象限名称: {rfm_segment}，有效值: {RFM_SEGMENT_NAMES}")

    sql = f"""
    WITH
    user_stats_all AS (
        SELECT
            user_id,
            MAX(pay_time) as last_pay_time,
            COUNT(DISTINCT order_id) as order_count,
            SUM(actual_amount) as gsv,
            BOOL_OR(is_member) AS is_member
        FROM orders o
        WHERE pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE}
          {refund_where}
          {channel_where_all}
          {exclude_where_base}
        GROUP BY user_id
    ),
    user_stats_same AS (
        SELECT
            user_id,
            MAX(pay_time) as last_pay_time,
            COUNT(DISTINCT order_id) as order_count,
            SUM(actual_amount) as gsv,
            BOOL_OR(is_member) AS is_member
        FROM orders o
        WHERE pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE}
          {refund_where}
          {channel_where_same}
          {exclude_where_hist}
        GROUP BY user_id
    ),
    rfm_scored_all AS (
        SELECT
            user_id,
            is_member,
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
        SELECT
            user_id,
            is_member,
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
        {_build_segmented_cte("rfm_scored_all")}
    ),
    segmented_same AS (
        {_build_segmented_cte("rfm_scored_same")}
    ),
    base_orders AS (
        SELECT o.user_id, o.actual_amount, COALESCE(o.spu_product_class, '未知') AS category
        FROM orders o
        INNER JOIN segmented_all sa ON o.user_id = sa.user_id
        WHERE o.pay_time >= ?::TIMESTAMP
          AND o.pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE}
          {refund_where}
          {channel_where_base}
          {exclude_where_base}
          AND sa.rfm_segment = ?
    ),
    category_hist AS (
        SELECT DISTINCT
            COALESCE(o.spu_product_class, '未知') AS category,
            sa.user_id
        FROM orders o
        INNER JOIN segmented_all sa ON o.user_id = sa.user_id
        WHERE o.pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE}
          {refund_where}
          {exclude_where_hist}
          {member_where_hist}
          AND sa.rfm_segment = ?
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

    rows = conn.execute(sql, params).fetchall()

    # 额外查询：象限去重用户数 + 当期复购去重用户数
    # 参数：cutoff_dt + [channel] + [exclude] + cutoff_dt x 4 + start_dt + end_dt + [channel] + [exclude] + rfm_segment
    seg_count_params: List[Any] = []
    seg_count_params.append(cutoff_dt)
    if channel and channel != "全店":
        from backend.semantic.filters import expand_channels
        db_ch = expand_channels([channel])
        for ch in db_ch:
            seg_count_params.append(ch)
    seg_count_params.extend(exclude_params_base)  # exclude for user_stats
    seg_count_params.extend([cutoff_dt] * 4)
    # SQL 占位符顺序: user_stats(1) + rfm_scored(4) + seg_users(1) + repurchase_users(2) + channel(?) + exclude(?)
    seg_count_params.append(rfm_segment)  # seg_users rfm_segment (位置 6)
    # base_orders 参数: start_dt, end_dt, [channel], [exclude]
    seg_count_params.append(start_dt)
    seg_count_params.append(end_dt)
    if channel and channel != "全店":
        from backend.semantic.filters import expand_channels
        db_ch = expand_channels([channel])
        for ch in db_ch:
            seg_count_params.append(ch)
    seg_count_params.extend(exclude_params_base)  # exclude for repurchase_users

    seg_channel_where = ""
    if channel and channel != "全店":
        from backend.semantic.filters import expand_channels
        db_ch = expand_channels([channel])
        if len(db_ch) == 1:
            seg_channel_where = " AND o.channel = ?"
        else:
            placeholders = ",".join(["?"] * len(db_ch))
            seg_channel_where = f" AND o.channel IN ({placeholders})"

    seg_count_sql = f"""
    WITH
    user_stats AS (
        SELECT user_id, MAX(pay_time) as last_pay_time,
            COUNT(DISTINCT order_id) as order_count, SUM(actual_amount) as gsv,
            BOOL_OR(is_member) AS is_member
        FROM orders o
        WHERE pay_time <= ?::TIMESTAMP
          AND is_goujinjin = FALSE AND order_status != '交易关闭'
          {refund_where}
          {seg_channel_where}
          {exclude_where_base}
        GROUP BY user_id
    ),
    rfm_scored AS (
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
        FROM user_stats
    ),
    segmented AS (
        {_build_segmented_cte("rfm_scored")}
    ),
    seg_users AS (
        SELECT user_id FROM segmented WHERE rfm_segment = ?
    ),
    repurchase_users AS (
        SELECT DISTINCT o.user_id
        FROM orders o
        INNER JOIN seg_users su ON o.user_id = su.user_id
        WHERE o.pay_time >= ?::TIMESTAMP
          AND o.pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE}
          {refund_where}
          {seg_channel_where}
          {exclude_where_base}
    )
    SELECT
        (SELECT COUNT(*) FROM seg_users) AS seg_count,
        (SELECT COUNT(*) FROM repurchase_users) AS repurchase_count
    """
    seg_count_result = conn.execute(seg_count_sql, seg_count_params).fetchone()
    seg_user_count = int(seg_count_result[0] or 0)
    seg_repurchase_count = int(seg_count_result[1] or 0)

    result: Dict[str, Dict[str, float]] = {}
    total_repurchase_gsv = 0.0
    for r in rows:
        category, hist_users, repurchase_users, repurchase_gsv, _ = r
        repurchase_rate = float(repurchase_users or 0) / float(hist_users or 1) if hist_users else 0.0
        result[category] = {
            "hist_users": int(hist_users or 0),
            "repurchase_users": int(repurchase_users or 0),
            "repurchase_rate": repurchase_rate,
            "repurchase_gsv": float(repurchase_gsv or 0),
            "repurchase_gsv_ratio": 0.0,
            "_segment_user_count": seg_user_count,
            "_seg_repurchase_count": seg_repurchase_count,
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
        周期名称（如 "YTD"、"MTD"），由系统根据 start_date/end_date 自动推断；此参数为内部兼容预留，外部调用可不传
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
        pass

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

    sum(c.get("hist_users_comp", 0) for c in categories)
    sum(c.get("repurchase_users_comp", 0) for c in categories)

    # 象限去重用户数 + 复购用户数（用户维度，与柱状图口径一致）
    seg_user_count = 0
    seg_repurchase_count = 0
    seg_user_count_comp = 0
    seg_repurchase_count_comp = 0
    for cat_data in cur_all.values():
        seg_user_count = int(cat_data.get("_segment_user_count", 0))
        seg_repurchase_count = int(cat_data.get("_seg_repurchase_count", 0))
        break
    for cat_data in comp_all.values():
        seg_user_count_comp = int(cat_data.get("_segment_user_count", 0))
        seg_repurchase_count_comp = int(cat_data.get("_seg_repurchase_count", 0))
        break

    # 用户维度回购率（与柱状图口径一致：复购用户数 / 象限总用户数）
    overall_rate = float(seg_repurchase_count) / float(seg_user_count) if seg_user_count > 0 else 0.0
    overall_rate_comp = float(seg_repurchase_count_comp) / float(seg_user_count_comp) if seg_user_count_comp > 0 else 0.0
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

    # 象限去重用户数（从 cur_all 中提取，所有品类共享同一个值）
    seg_user_count = 0
    for cat_data in cur_all.values():
        seg_user_count = int(cat_data.get("_segment_user_count", 0))
        break  # 只需取一次

    # 影响因子 TOP 3：按 hist_users × |yoy_rate| 降序
    def _impact_key(c: Dict[str, Any]) -> float:
        return c.get("hist_users_current", 0) * abs(c.get("yoy_repurchase_rate") or 0)
    top_drivers = [
        {
            "category_name": c["category_name"],
            "repurchase_rate_current": c["repurchase_rate_current"],
            "yoy_repurchase_rate": c.get("yoy_repurchase_rate"),
            "hist_users_current": c["hist_users_current"],
        }
        for c in sorted(categories, key=_impact_key, reverse=True)[:3]
    ]

    summary = {
        "total_hist_users": total_hist,
        "total_repurchase_users": total_repurchase,
        "overall_repurchase_rate": round(overall_rate, 4),
        "overall_repurchase_rate_comp": round(overall_rate_comp, 4),
        "overall_repurchase_rate_yoy": overall_rate_yoy if overall_rate_yoy is not None else 0.0,
        "segment_user_count": seg_user_count,
        "top_drivers": top_drivers,
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
