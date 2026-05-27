"""品类分析服务 - 复购分析"""
import duckdb
from typing import Dict, Any, Optional, List

from backend.db.connection import get_connection
from backend.semantic.filters import OrderFilters, expand_channels
from backend.semantic.calculations import yoy_absolute, yoy_ratio
from backend.semantic.segments import RFM_THRESHOLDS

from ._shared import (
    SPU_LEVELS,
    _RFM_SEGMENT_ORDER,
    _resolve_repurchase_date_ranges,
)

def _run_category_repurchase_period(
    conn: duckdb.DuckDBPyConnection,
    start_dt: str,
    end_dt: str,
    cutoff_dt: str,
    category: str,
    category_field: str = "spu_product_class",
    metric_type: str = "GSV",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> tuple[
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
]:
    """
    执行单个周期的品类回购分析查询，返回4组数据：
    - all_same: 全店-同品回购
    - all_cross: 全店-跨品类回购
    - member_same: 会员-同品回购
    - member_cross: 会员-跨品类回购
    """

    valid_sql, _ = OrderFilters.valid_order()

    # 渠道过滤
    channel_where_base = ""
    base_params_extra: List[str] = []
    if channel and channel != "全店":
        db_channels = [c for c in expand_channels([channel]) if c]
        if not db_channels:
            raise ValueError(f"渠道'{channel}'未在channels.py中注册，请检查UI_TO_DB映射")
        if len(db_channels) == 1:
            channel_where_base = " AND o.channel = ?"
            base_params_extra = [db_channels[0]]
        else:
            ph = ",".join(["?"] * len(db_channels))
            channel_where_base = f" AND o.channel IN ({ph})"
            base_params_extra = list(db_channels)

    exclude_where = ""
    exclude_params: List[str] = []
    if exclude_channels:
        db_ex = [c for c in expand_channels(exclude_channels) if c]
        ex_ph = ",".join(["?"] * len(db_ex))
        exclude_where = f" AND o.channel NOT IN ({ex_ph})"
        exclude_params = list(db_ex)

    refund_where = "AND is_refund = FALSE" if metric_type == "GSV" else ""

    # RFM 阈值（引用语义层，禁止硬编码）
    _rt = RFM_THRESHOLDS["r"]   # [30, 90, 180, 365]
    _ft = RFM_THRESHOLDS["f"]   # [1, 2, 3, 4]
    _mt = RFM_THRESHOLDS["m"]   # [100, 300, 500, 1000]

    # 参数组装
    # hist_customers: cutoff, cutoff (cutoff参数)
    # base_orders: start_dt, end_dt
    # hist_customers 的排除/渠道参数
    hist_params: List[str] = [cutoff_dt, cutoff_dt]
    base_params: List[str] = [start_dt, end_dt]

    # 品类字段安全值（白名单校验已由 level 参数约束）
    safe_category = category.replace("'", "''")

    sql = f"""
    WITH
    base_orders AS (
        SELECT user_id, actual_amount
        FROM orders o
        WHERE pay_time >= ?::TIMESTAMP
          AND pay_time <= ?::TIMESTAMP
          AND {valid_sql}
          {channel_where_base}
          {exclude_where}
          {refund_where}
    ),
    hist_customers AS (
        SELECT
            user_id,
            DATEDIFF('day', MAX(pay_time)::DATE, ?::DATE) AS recency_days,
            COUNT(DISTINCT order_id) AS order_count,
            SUM(actual_amount) AS gsv,
            BOOL_OR(is_member) AS is_member
        FROM orders o
        WHERE o.{category_field} = ?
          AND pay_time <= ?::TIMESTAMP
          AND {valid_sql}
          {exclude_where}
        GROUP BY user_id
    ),
    rfm_scored AS (
        SELECT
            user_id, is_member,
            CASE
                WHEN recency_days < {_rt[0]} THEN 5
                WHEN recency_days < {_rt[1]} THEN 4
                WHEN recency_days < {_rt[2]} THEN 3
                WHEN recency_days < {_rt[3]} THEN 2
                ELSE 1
            END AS r_score,
            CASE WHEN order_count >= {_ft[3] + 1} THEN 5 WHEN order_count >= {_ft[2] + 1} THEN 4 WHEN order_count = {_ft[2]} THEN 3 WHEN order_count = {_ft[1]} THEN 2 ELSE 1 END AS f_score,
            CASE WHEN gsv >= {_mt[3]} THEN 5 WHEN gsv >= {_mt[2]} THEN 4 WHEN gsv >= {_mt[1]} THEN 3 WHEN gsv >= {_mt[0]} THEN 2 ELSE 1 END AS m_score
        FROM hist_customers
    ),
    rfm_segmented AS (
        SELECT
            user_id, is_member,
            CASE
                WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN '重要价值客户'
                WHEN r_score < 4 AND f_score >= 4 AND m_score >= 4 THEN '重要保持客户'
                WHEN r_score >= 4 AND f_score < 4 AND m_score >= 4 THEN '重要发展客户'
                WHEN r_score < 4 AND f_score < 4 AND m_score >= 4 THEN '重要挽留客户'
                WHEN r_score >= 4 AND f_score >= 4 AND m_score < 4 THEN '一般价值客户'
                WHEN r_score < 4 AND f_score >= 4 AND m_score < 4 THEN '一般保持客户'
                WHEN r_score >= 4 AND f_score < 4 AND m_score < 4 THEN '一般发展客户'
                ELSE '一般挽留客户'
            END AS rfm_segment
        FROM rfm_scored
    ),
    member_segmented AS (
        SELECT user_id, rfm_segment FROM rfm_segmented WHERE is_member = TRUE
    ),
    -- 同品回购：分析期内购买同一品类的用户
    same_repurchase AS (
        SELECT DISTINCT user_id
        FROM orders o
        WHERE o.{category_field} = ?
          AND pay_time >= ?::TIMESTAMP
          AND pay_time <= ?::TIMESTAMP
          AND {valid_sql}
          {channel_where_base}
          {exclude_where}
          {refund_where}
    ),
    -- 跨品类回购：分析期内购买任何其他品类的用户
    cross_repurchase AS (
        SELECT DISTINCT user_id
        FROM orders o
        WHERE o.{category_field} IS NOT NULL
          AND o.{category_field} != ?
          AND pay_time >= ?::TIMESTAMP
          AND pay_time <= ?::TIMESTAMP
          AND {valid_sql}
          {channel_where_base}
          {exclude_where}
          {refund_where}
    ),
    -- 同品回购金额
    same_repurchase_amounts AS (
        SELECT o.user_id, SUM(o.actual_amount) AS repurchase_gsv
        FROM orders o
        WHERE o.{category_field} = ?
          AND o.pay_time >= ?::TIMESTAMP
          AND o.pay_time <= ?::TIMESTAMP
          AND {valid_sql}
          {channel_where_base}
          {exclude_where}
          {refund_where}
        GROUP BY o.user_id
    ),
    -- 跨品类回购金额
    cross_repurchase_amounts AS (
        SELECT o.user_id, SUM(o.actual_amount) AS repurchase_gsv
        FROM orders o
        WHERE o.{category_field} IS NOT NULL
          AND o.{category_field} != ?
          AND o.pay_time >= ?::TIMESTAMP
          AND o.pay_time <= ?::TIMESTAMP
          AND {valid_sql}
          {channel_where_base}
          {exclude_where}
          {refund_where}
        GROUP BY o.user_id
    ),
    -- 全店 同品
    stats_all_same AS (
        SELECT r.rfm_segment,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT sr.user_id) AS repurchase_users,
               COALESCE(SUM(sra.repurchase_gsv), 0) AS repurchase_gsv
        FROM rfm_segmented r
        LEFT JOIN same_repurchase sr ON r.user_id = sr.user_id
        LEFT JOIN same_repurchase_amounts sra ON r.user_id = sra.user_id
        GROUP BY r.rfm_segment
    ),
    ttl_all_same AS (
        SELECT '已购客TTL' AS rfm_segment, SUM(hist_users) AS hist_users,
               SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv
        FROM stats_all_same
    ),
    -- 全店 跨品类
    stats_all_cross AS (
        SELECT r.rfm_segment,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT cr.user_id) AS repurchase_users,
               COALESCE(SUM(cra.repurchase_gsv), 0) AS repurchase_gsv
        FROM rfm_segmented r
        LEFT JOIN cross_repurchase cr ON r.user_id = cr.user_id
        LEFT JOIN cross_repurchase_amounts cra ON r.user_id = cra.user_id
        GROUP BY r.rfm_segment
    ),
    ttl_all_cross AS (
        SELECT '已购客TTL' AS rfm_segment, SUM(hist_users) AS hist_users,
               SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv
        FROM stats_all_cross
    ),
    -- 会员 同品
    stats_member_same AS (
        SELECT r.rfm_segment,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT sr.user_id) AS repurchase_users,
               COALESCE(SUM(sra.repurchase_gsv), 0) AS repurchase_gsv
        FROM member_segmented r
        LEFT JOIN same_repurchase sr ON r.user_id = sr.user_id
        LEFT JOIN same_repurchase_amounts sra ON r.user_id = sra.user_id
        GROUP BY r.rfm_segment
    ),
    ttl_member_same AS (
        SELECT '已购客TTL' AS rfm_segment, SUM(hist_users) AS hist_users,
               SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv
        FROM stats_member_same
    ),
    -- 会员 跨品类
    stats_member_cross AS (
        SELECT r.rfm_segment,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT cr.user_id) AS repurchase_users,
               COALESCE(SUM(cra.repurchase_gsv), 0) AS repurchase_gsv
        FROM member_segmented r
        LEFT JOIN cross_repurchase cr ON r.user_id = cr.user_id
        LEFT JOIN cross_repurchase_amounts cra ON r.user_id = cra.user_id
        GROUP BY r.rfm_segment
    ),
    ttl_member_cross AS (
        SELECT '已购客TTL' AS rfm_segment, SUM(hist_users) AS hist_users,
               SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv
        FROM stats_member_cross
    )
    SELECT 'all_same' AS mode, rfm_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM stats_all_same UNION ALL SELECT * FROM ttl_all_same
    )
    UNION ALL
    SELECT 'all_cross' AS mode, rfm_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM stats_all_cross UNION ALL SELECT * FROM ttl_all_cross
    )
    UNION ALL
    SELECT 'member_same' AS mode, rfm_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM stats_member_same UNION ALL SELECT * FROM ttl_member_same
    )
    UNION ALL
    SELECT 'member_cross' AS mode, rfm_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM stats_member_cross UNION ALL SELECT * FROM ttl_member_cross
    )
    """

    # SQL中?出现顺序（严格对应）:
    # base_orders: 2(start,end) + ch + ex
    # hist_customers: 2(cutoff,cutoff) + ex
    # same_repurchase: 2(start,end) + ch + ex
    # cross_repurchase: 2(start,end) + ch + ex
    # same_repurchase_amounts: 2(start,end) + ch + ex
    # cross_repurchase_amounts: 2(start,end) + ch + ex

    # SQL参数顺序（严格对应 ? 占位符）:
    # base_orders: 2(start,end) + ch + ex
    # hist_customers: 2(cutoff) + ex + 1(category)
    # same_repurchase: 2(start,end) + ch + ex + 1(category)
    # cross_repurchase: 2(start,end) + ch + ex + 1(category)
    # same_repurchase_amounts: 2(start,end) + ch + ex + 1(category)
    # cross_repurchase_amounts: 2(start,end) + ch + ex + 1(category)
    full_params = base_params + base_params_extra + exclude_params           # base_orders (2+ch+ex)
    full_params += hist_params + exclude_params + [safe_category]            # hist_customers (2+ex+1)
    full_params += base_params + base_params_extra + exclude_params + [safe_category]  # same_repurchase (2+ch+ex+1)
    full_params += base_params + base_params_extra + exclude_params + [safe_category]  # cross_repurchase (2+ch+ex+1)
    full_params += base_params + base_params_extra + exclude_params + [safe_category]  # same_repurchase_amounts (2+ch+ex+1)
    full_params += base_params + base_params_extra + exclude_params + [safe_category]  # cross_repurchase_amounts (2+ch+ex+1)

    rows = conn.execute(sql, full_params).fetchall()

    results: Dict[str, Dict[str, Dict[str, float]]] = {
        "all_same": {}, "all_cross": {},
        "member_same": {}, "member_cross": {},
    }
    totals: Dict[str, float] = {
        "all_same": 0.0, "all_cross": 0.0,
        "member_same": 0.0, "member_cross": 0.0,
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
        if segment != "已购客TTL":
            totals[mode] += float(repurchase_gsv or 0)
        results[mode][segment] = entry

    # 计算 gsv_ratio
    for mode in results:
        for seg in results[mode]:
            gsv = results[mode][seg]["repurchase_gsv"]
            results[mode][seg]["repurchase_gsv_ratio"] = gsv / totals[mode] if totals[mode] > 0 else 0.0

    # 补全缺失的 segment
    for mode in results:
        for seg in _RFM_SEGMENT_ORDER:
            if seg not in results[mode]:
                results[mode][seg] = {
                    "hist_users": 0, "repurchase_users": 0,
                    "repurchase_rate": 0.0, "repurchase_gsv": 0.0, "repurchase_gsv_ratio": 0.0,
                }

    return results["all_same"], results["all_cross"], results["member_same"], results["member_cross"]

def _run_category_repurchase_period_by_rfm(
    conn: duckdb.DuckDBPyConnection,
    start_dt: str,
    end_dt: str,
    cutoff_dt: str,
    category: str,
    category_field: str = "spu_product_class",
    metric_type: str = "GSV",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> tuple[
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
]:
    """
    执行单个周期的历史老客回购分析查询（RFM 8象限分群，不限品类）。
    与 _run_category_repurchase_period 的区别：
    - hist_customers 包含所有历史老客（不限品类），再按 RFM 分群看各象限在分析期内是否购买目标品类
    返回4组数据：
    - all_same: 全店-同品回购
    - all_cross: 全店-跨品类回购
    - member_same: 会员-同品回购
    - member_cross: 会员-跨品类回购
    """

    valid_sql, _ = OrderFilters.valid_order()

    # 渠道过滤
    channel_where_base = ""
    base_params_extra: List[str] = []
    if channel and channel != "全店":
        db_channels = [c for c in expand_channels([channel]) if c]
        if not db_channels:
            raise ValueError(f"渠道'{channel}'未在channels.py中注册，请检查UI_TO_DB映射")
        if len(db_channels) == 1:
            channel_where_base = " AND o.channel = ?"
            base_params_extra = [db_channels[0]]
        else:
            ph = ",".join(["?"] * len(db_channels))
            channel_where_base = f" AND o.channel IN ({ph})"
            base_params_extra = list(db_channels)

    exclude_where = ""
    exclude_params: List[str] = []
    if exclude_channels:
        db_ex = [c for c in expand_channels(exclude_channels) if c]
        ex_ph = ",".join(["?"] * len(db_ex))
        exclude_where = f" AND o.channel NOT IN ({ex_ph})"
        exclude_params = list(db_ex)

    refund_where = "AND is_refund = FALSE" if metric_type == "GSV" else ""

    # RFM 阈值（引用语义层，禁止硬编码）
    _rt = RFM_THRESHOLDS["r"]   # [30, 90, 180, 365]
    _ft = RFM_THRESHOLDS["f"]   # [1, 2, 3, 4]
    _mt = RFM_THRESHOLDS["m"]   # [100, 300, 500, 1000]

    # 参数组装
    # hist_customers: cutoff, cutoff (cutoff参数)
    # base_orders: start_dt, end_dt
    # hist_customers 的排除/渠道参数
    hist_params: List[str] = [cutoff_dt, cutoff_dt]
    base_params: List[str] = [start_dt, end_dt]

    # 品类字段安全值（白名单校验已由 level 参数约束）
    safe_category = category.replace("'", "''")

    sql = f"""
    WITH
    base_orders AS (
        SELECT user_id, actual_amount
        FROM orders o
        WHERE pay_time >= ?::TIMESTAMP
          AND pay_time <= ?::TIMESTAMP
          AND {valid_sql}
          {channel_where_base}
          {exclude_where}
          {refund_where}
    ),
    hist_customers AS (
        SELECT
            user_id,
            DATEDIFF('day', MAX(pay_time)::DATE, ?::DATE) AS recency_days,
            COUNT(DISTINCT order_id) AS order_count,
            SUM(actual_amount) AS gsv,
            BOOL_OR(is_member) AS is_member
        FROM orders o
        WHERE pay_time <= ?::TIMESTAMP
          AND {valid_sql}
          {exclude_where}
        GROUP BY user_id
    ),
    rfm_scored AS (
        SELECT
            user_id, is_member,
            CASE
                WHEN recency_days < {_rt[0]} THEN 5
                WHEN recency_days < {_rt[1]} THEN 4
                WHEN recency_days < {_rt[2]} THEN 3
                WHEN recency_days < {_rt[3]} THEN 2
                ELSE 1
            END AS r_score,
            CASE WHEN order_count >= {_ft[3] + 1} THEN 5 WHEN order_count >= {_ft[2] + 1} THEN 4 WHEN order_count = {_ft[2]} THEN 3 WHEN order_count = {_ft[1]} THEN 2 ELSE 1 END AS f_score,
            CASE WHEN gsv >= {_mt[3]} THEN 5 WHEN gsv >= {_mt[2]} THEN 4 WHEN gsv >= {_mt[1]} THEN 3 WHEN gsv >= {_mt[0]} THEN 2 ELSE 1 END AS m_score
        FROM hist_customers
    ),
    rfm_segmented AS (
        SELECT
            user_id, is_member,
            CASE
                WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN '重要价值客户'
                WHEN r_score < 4 AND f_score >= 4 AND m_score >= 4 THEN '重要保持客户'
                WHEN r_score >= 4 AND f_score < 4 AND m_score >= 4 THEN '重要发展客户'
                WHEN r_score < 4 AND f_score < 4 AND m_score >= 4 THEN '重要挽留客户'
                WHEN r_score >= 4 AND f_score >= 4 AND m_score < 4 THEN '一般价值客户'
                WHEN r_score < 4 AND f_score >= 4 AND m_score < 4 THEN '一般保持客户'
                WHEN r_score >= 4 AND f_score < 4 AND m_score < 4 THEN '一般发展客户'
                ELSE '一般挽留客户'
            END AS rfm_segment
        FROM rfm_scored
    ),
    member_segmented AS (
        SELECT user_id, rfm_segment FROM rfm_segmented WHERE is_member = TRUE
    ),
    -- 同品回购：分析期内购买同一品类的用户
    same_repurchase AS (
        SELECT DISTINCT user_id
        FROM orders o
        WHERE o.{category_field} = ?
          AND pay_time >= ?::TIMESTAMP
          AND pay_time <= ?::TIMESTAMP
          AND {valid_sql}
          {channel_where_base}
          {exclude_where}
          {refund_where}
    ),
    -- 跨品类回购：分析期内购买任何其他品类的用户
    cross_repurchase AS (
        SELECT DISTINCT user_id
        FROM orders o
        WHERE o.{category_field} IS NOT NULL
          AND o.{category_field} != ?
          AND pay_time >= ?::TIMESTAMP
          AND pay_time <= ?::TIMESTAMP
          AND {valid_sql}
          {channel_where_base}
          {exclude_where}
          {refund_where}
    ),
    -- 同品回购金额
    same_repurchase_amounts AS (
        SELECT o.user_id, SUM(o.actual_amount) AS repurchase_gsv
        FROM orders o
        WHERE o.{category_field} = ?
          AND o.pay_time >= ?::TIMESTAMP
          AND o.pay_time <= ?::TIMESTAMP
          AND {valid_sql}
          {channel_where_base}
          {exclude_where}
          {refund_where}
        GROUP BY o.user_id
    ),
    -- 跨品类回购金额
    cross_repurchase_amounts AS (
        SELECT o.user_id, SUM(o.actual_amount) AS repurchase_gsv
        FROM orders o
        WHERE o.{category_field} IS NOT NULL
          AND o.{category_field} != ?
          AND o.pay_time >= ?::TIMESTAMP
          AND o.pay_time <= ?::TIMESTAMP
          AND {valid_sql}
          {channel_where_base}
          {exclude_where}
          {refund_where}
        GROUP BY o.user_id
    ),
    -- 全店 同品
    stats_all_same AS (
        SELECT r.rfm_segment,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT sr.user_id) AS repurchase_users,
               COALESCE(SUM(sra.repurchase_gsv), 0) AS repurchase_gsv
        FROM rfm_segmented r
        LEFT JOIN same_repurchase sr ON r.user_id = sr.user_id
        LEFT JOIN same_repurchase_amounts sra ON r.user_id = sra.user_id
        GROUP BY r.rfm_segment
    ),
    ttl_all_same AS (
        SELECT '已购客TTL' AS rfm_segment, SUM(hist_users) AS hist_users,
               SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv
        FROM stats_all_same
    ),
    -- 全店 跨品类
    stats_all_cross AS (
        SELECT r.rfm_segment,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT cr.user_id) AS repurchase_users,
               COALESCE(SUM(cra.repurchase_gsv), 0) AS repurchase_gsv
        FROM rfm_segmented r
        LEFT JOIN cross_repurchase cr ON r.user_id = cr.user_id
        LEFT JOIN cross_repurchase_amounts cra ON r.user_id = cra.user_id
        GROUP BY r.rfm_segment
    ),
    ttl_all_cross AS (
        SELECT '已购客TTL' AS rfm_segment, SUM(hist_users) AS hist_users,
               SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv
        FROM stats_all_cross
    ),
    -- 会员 同品
    stats_member_same AS (
        SELECT r.rfm_segment,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT sr.user_id) AS repurchase_users,
               COALESCE(SUM(sra.repurchase_gsv), 0) AS repurchase_gsv
        FROM member_segmented r
        LEFT JOIN same_repurchase sr ON r.user_id = sr.user_id
        LEFT JOIN same_repurchase_amounts sra ON r.user_id = sra.user_id
        GROUP BY r.rfm_segment
    ),
    ttl_member_same AS (
        SELECT '已购客TTL' AS rfm_segment, SUM(hist_users) AS hist_users,
               SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv
        FROM stats_member_same
    ),
    -- 会员 跨品类
    stats_member_cross AS (
        SELECT r.rfm_segment,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT cr.user_id) AS repurchase_users,
               COALESCE(SUM(cra.repurchase_gsv), 0) AS repurchase_gsv
        FROM member_segmented r
        LEFT JOIN cross_repurchase cr ON r.user_id = cr.user_id
        LEFT JOIN cross_repurchase_amounts cra ON r.user_id = cra.user_id
        GROUP BY r.rfm_segment
    ),
    ttl_member_cross AS (
        SELECT '已购客TTL' AS rfm_segment, SUM(hist_users) AS hist_users,
               SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv
        FROM stats_member_cross
    )
    SELECT 'all_same' AS mode, rfm_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM stats_all_same UNION ALL SELECT * FROM ttl_all_same
    )
    UNION ALL
    SELECT 'all_cross' AS mode, rfm_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM stats_all_cross UNION ALL SELECT * FROM ttl_all_cross
    )
    UNION ALL
    SELECT 'member_same' AS mode, rfm_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM stats_member_same UNION ALL SELECT * FROM ttl_member_same
    )
    UNION ALL
    SELECT 'member_cross' AS mode, rfm_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM stats_member_cross UNION ALL SELECT * FROM ttl_member_cross
    )
    """

    # SQL中?出现顺序（严格对应）:
    # base_orders: 2(start,end) + ch + ex
    # hist_customers: 2(cutoff,cutoff) + ex
    # same_repurchase: 2(start,end) + ch + ex
    # cross_repurchase: 2(start,end) + ch + ex
    # same_repurchase_amounts: 2(start,end) + ch + ex
    # cross_repurchase_amounts: 2(start,end) + ch + ex

    # SQL参数顺序（严格对应 ? 占位符）:
    # base_orders: 2(start,end) + ch + ex
    # hist_customers: 2(cutoff) + ex + 1(category)
    # same_repurchase: 2(start,end) + ch + ex + 1(category)
    # cross_repurchase: 2(start,end) + ch + ex + 1(category)
    # same_repurchase_amounts: 2(start,end) + ch + ex + 1(category)
    # cross_repurchase_amounts: 2(start,end) + ch + ex + 1(category)
    full_params = base_params + base_params_extra + exclude_params           # base_orders (2+ch+ex)
    full_params += hist_params + exclude_params + [safe_category]            # hist_customers (2+ex+1)
    full_params += base_params + base_params_extra + exclude_params + [safe_category]  # same_repurchase (2+ch+ex+1)
    full_params += base_params + base_params_extra + exclude_params + [safe_category]  # cross_repurchase (2+ch+ex+1)
    full_params += base_params + base_params_extra + exclude_params + [safe_category]  # same_repurchase_amounts (2+ch+ex+1)
    full_params += base_params + base_params_extra + exclude_params + [safe_category]  # cross_repurchase_amounts (2+ch+ex+1)

    rows = conn.execute(sql, full_params).fetchall()

    results: Dict[str, Dict[str, Dict[str, float]]] = {
        "all_same": {}, "all_cross": {},
        "member_same": {}, "member_cross": {},
    }
    totals: Dict[str, float] = {
        "all_same": 0.0, "all_cross": 0.0,
        "member_same": 0.0, "member_cross": 0.0,
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
        if segment != "已购客TTL":
            totals[mode] += float(repurchase_gsv or 0)
        results[mode][segment] = entry

    # 计算 gsv_ratio
    for mode in results:
        for seg in results[mode]:
            gsv = results[mode][seg]["repurchase_gsv"]
            results[mode][seg]["repurchase_gsv_ratio"] = gsv / totals[mode] if totals[mode] > 0 else 0.0

    # 补全缺失的 segment
    for mode in results:
        for seg in _RFM_SEGMENT_ORDER:
            if seg not in results[mode]:
                results[mode][seg] = {
                    "hist_users": 0, "repurchase_users": 0,
                    "repurchase_rate": 0.0, "repurchase_gsv": 0.0, "repurchase_gsv_ratio": 0.0,
                }

    return results["all_same"], results["all_cross"], results["member_same"], results["member_cross"]

def get_category_repurchase_flow(
    start_date: str,
    end_date: str,
    category: str,
    level: str = "class",
    metric_type: str = "GSV",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    品类回购分析主接口
    同品回购 + 跨品类回购，RFM 8象限分群，3年同比
    """
    if level not in SPU_LEVELS:
        raise ValueError(f"Invalid level: {level}")
    category_field = SPU_LEVELS[level]

    ranges = _resolve_repurchase_date_ranges(start_date, end_date)
    cur_start, cur_end, cutoff = ranges["current"]
    comp_start, comp_end, comp_cutoff = ranges["comp"]
    prev2_start, prev2_end, prev2_cutoff = ranges["prev2"]
    year_label, comp_label, prev2_label = ranges["labels"]

    conn = get_connection()
    try:
        # 当前年
        cur_same, cur_cross, cur_m_same, cur_m_cross = _run_category_repurchase_period(
            conn, cur_start, cur_end, cutoff, category, category_field, metric_type, channel, exclude_channels
        )
        # 去年
        comp_same, comp_cross, comp_m_same, comp_m_cross = _run_category_repurchase_period(
            conn, comp_start, comp_end, comp_cutoff, category, category_field, metric_type, channel, exclude_channels
        )
        # 前年
        prev2_same, prev2_cross, prev2_m_same, prev2_m_cross = _run_category_repurchase_period(
            conn, prev2_start, prev2_end, prev2_cutoff, category, category_field, metric_type, channel, exclude_channels
        )
    finally:
        conn.close()

    def _build_rows(cur_data, comp_data, prev2_data):
        rows = []
        for seg in _RFM_SEGMENT_ORDER:
            c = cur_data.get(seg, {})
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
                "repurchase_rate_comp": round(p.get("repurchase_rate", 0.0), 4),
                "hist_users_prev2": p2.get("hist_users", 0),
                "repurchase_rate_prev2": round(p2.get("repurchase_rate", 0.0), 4),
                "yoy_hist_users": yoy_absolute(c.get("hist_users", 0), p.get("hist_users", 0)),
                "yoy_repurchase_users": yoy_absolute(c.get("repurchase_users", 0), p.get("repurchase_users", 0)),
                "yoy_repurchase_rate": yoy_ratio(c.get("repurchase_rate", 0.0), p.get("repurchase_rate", 0.0)),
                "yoy_repurchase_gsv": yoy_absolute(c.get("repurchase_gsv", 0.0), p.get("repurchase_gsv", 0.0)),
                "yoy_repurchase_gsv_ratio": yoy_ratio(c.get("repurchase_gsv_ratio", 0.0), p.get("repurchase_gsv_ratio", 0.0)),
            })
        return rows

    return {
        "year_label": year_label,
        "comp_year_label": comp_label,
        "prev2_year_label": prev2_label,
        "target_category": category,
        "same_category_rows": _build_rows(cur_same, comp_same, prev2_same),
        "cross_category_rows": _build_rows(cur_cross, comp_cross, prev2_cross),
        "member_same_category_rows": _build_rows(cur_m_same, comp_m_same, prev2_m_same),
        "member_cross_category_rows": _build_rows(cur_m_cross, comp_m_cross, prev2_m_cross),
    }

def get_category_repurchase_flow_by_rfm(
    start_date: str,
    end_date: str,
    category: str,
    level: str = "class",
    metric_type: str = "GSV",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    历史老客回购分析主接口（RFM 8象限分群，不限品类）
    同品回购 + 跨品类回购，3年同比
    """
    if level not in SPU_LEVELS:
        raise ValueError(f"Invalid level: {level}")
    category_field = SPU_LEVELS[level]

    ranges = _resolve_repurchase_date_ranges(start_date, end_date)
    cur_start, cur_end, cutoff = ranges["current"]
    comp_start, comp_end, comp_cutoff = ranges["comp"]
    prev2_start, prev2_end, prev2_cutoff = ranges["prev2"]
    year_label, comp_label, prev2_label = ranges["labels"]

    conn = get_connection()
    try:
        # 当前年
        cur_same, cur_cross, cur_m_same, cur_m_cross = _run_category_repurchase_period_by_rfm(
            conn, cur_start, cur_end, cutoff, category, category_field, metric_type, channel, exclude_channels
        )
        # 去年
        comp_same, comp_cross, comp_m_same, comp_m_cross = _run_category_repurchase_period_by_rfm(
            conn, comp_start, comp_end, comp_cutoff, category, category_field, metric_type, channel, exclude_channels
        )
        # 前年
        prev2_same, prev2_cross, prev2_m_same, prev2_m_cross = _run_category_repurchase_period_by_rfm(
            conn, prev2_start, prev2_end, prev2_cutoff, category, category_field, metric_type, channel, exclude_channels
        )
    finally:
        conn.close()

    def _build_rows(cur_data, comp_data, prev2_data):
        rows = []
        for seg in _RFM_SEGMENT_ORDER:
            c = cur_data.get(seg, {})
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
                "repurchase_rate_comp": round(p.get("repurchase_rate", 0.0), 4),
                "hist_users_prev2": p2.get("hist_users", 0),
                "repurchase_rate_prev2": round(p2.get("repurchase_rate", 0.0), 4),
                "yoy_hist_users": yoy_absolute(c.get("hist_users", 0), p.get("hist_users", 0)),
                "yoy_repurchase_users": yoy_absolute(c.get("repurchase_users", 0), p.get("repurchase_users", 0)),
                "yoy_repurchase_rate": yoy_ratio(c.get("repurchase_rate", 0.0), p.get("repurchase_rate", 0.0)),
                "yoy_repurchase_gsv": yoy_absolute(c.get("repurchase_gsv", 0.0), p.get("repurchase_gsv", 0.0)),
                "yoy_repurchase_gsv_ratio": yoy_ratio(c.get("repurchase_gsv_ratio", 0.0), p.get("repurchase_gsv_ratio", 0.0)),
            })
        return rows

    return {
        "year_label": year_label,
        "comp_year_label": comp_label,
        "prev2_year_label": prev2_label,
        "target_category": category,
        "same_category_rows": _build_rows(cur_same, comp_same, prev2_same),
        "cross_category_rows": _build_rows(cur_cross, comp_cross, prev2_cross),
        "member_same_category_rows": _build_rows(cur_m_same, comp_m_same, prev2_m_same),
        "member_cross_category_rows": _build_rows(cur_m_cross, comp_m_cross, prev2_m_cross),
    }
