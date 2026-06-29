"""品类分析服务 - 复购分析"""
import duckdb
from typing import Dict, Optional, List

from backend.semantic.filters import FilterBuilder, MetricType
# Sprint 170: 业务口径由 RFM 8 象限改为 R 桶 (6 档 Recency + TTL)
from backend.semantic.segments import R_SEGMENT_ORDER


def _build_repurchase_rfm_filter(
    channel,
    exclude_channels,
):
    """Sprint 54 Lane C L3: 收编 valid_order() + channel + exclude 到 FilterBuilder
    避免 f-string 内嵌 (本函数本身无 f-string 输出,所有用户输入走 add_extra 参数化).
    """
    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    if channel and channel != "全店":
        fb.with_channels([channel])
    elif exclude_channels:
        fb.with_exclude_channels(exclude_channels)
    return fb.build()


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

    # Sprint 54 Lane C L3: valid_order 收编到 FilterBuilder (helper 在文件顶部)
    valid_where_clause, valid_where_params = _build_repurchase_rfm_filter(channel, exclude_channels)

    refund_where = "AND is_refund = FALSE" if metric_type == "GSV" else ""

    # Sprint 170: 业务口径由 RFM 8 象限改为 R 桶 (6 档 Recency + TTL).
    # 阈值定义在 backend.semantic.segments.R_INTERVALS (L4 永久规则: 禁止硬编码).
    # R 桶 CASE WHEN 直接按 recency_days 分桶, 不再需要 R/F/M 评分.

    # 参数组装
    # hist_customers: 1(cutoff_DATEDIFF) + 1(cutoff_pay_time) + ex
    # base_orders: start_dt, end_dt
    # Sprint 54 Lane C L3: valid_where_params (含 ch+ex) 替代原 exclude_params
    hist_params: List[str] = [cutoff_dt, cutoff_dt] + list(valid_where_params)
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
          AND {valid_where_clause}
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
          AND {valid_where_clause}
        GROUP BY user_id
    ),
    -- Sprint 170: RFM 8 象限 → R 桶 (6 档 Recency + TTL)
    -- 名称与 semantic.segments.R_SEGMENT_ORDER 公共 SSOT 完全一致
    r_bucketed AS (
        SELECT
            user_id, is_member,
            CASE
                WHEN recency_days <= 30 THEN '近1个月已购客'
                WHEN recency_days <= 90 THEN '近2-3个月已购客'
                WHEN recency_days <= 180 THEN '近4-6月已购客'
                WHEN recency_days <= 365 THEN '近7-12个月已购客'
                WHEN recency_days <= 730 THEN '近13个月-近24个月已购客'
                ELSE '2年外已购客'
            END AS r_bucket
        FROM hist_customers
    ),
    member_bucketed AS (
        SELECT user_id, r_bucket FROM r_bucketed WHERE is_member = TRUE
    ),
    -- 同品回购：分析期内购买同一品类的用户
    same_repurchase AS (
        SELECT DISTINCT user_id
        FROM orders o
        WHERE o.{category_field} = ?
          AND pay_time >= ?::TIMESTAMP
          AND pay_time <= ?::TIMESTAMP
          AND {valid_where_clause}
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
          AND {valid_where_clause}
          {refund_where}
    ),
    -- 同品回购金额
    same_repurchase_amounts AS (
        SELECT o.user_id, SUM(o.actual_amount) AS repurchase_gsv
        FROM orders o
        WHERE o.{category_field} = ?
          AND o.pay_time >= ?::TIMESTAMP
          AND o.pay_time <= ?::TIMESTAMP
          AND {valid_where_clause}
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
          AND {valid_where_clause}
          {refund_where}
        GROUP BY o.user_id
    ),
    -- 全店 同品
    stats_all_same AS (
        SELECT r.r_bucket,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT sr.user_id) AS repurchase_users,
               COALESCE(SUM(sra.repurchase_gsv), 0) AS repurchase_gsv
        FROM r_bucketed r
        LEFT JOIN same_repurchase sr ON r.user_id = sr.user_id
        LEFT JOIN same_repurchase_amounts sra ON r.user_id = sra.user_id
        GROUP BY r.r_bucket
    ),
    ttl_all_same AS (
        SELECT '已购客TTL' AS r_bucket, SUM(hist_users) AS hist_users,
               SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv
        FROM stats_all_same
    ),
    -- 全店 跨品类
    stats_all_cross AS (
        SELECT r.r_bucket,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT cr.user_id) AS repurchase_users,
               COALESCE(SUM(cra.repurchase_gsv), 0) AS repurchase_gsv
        FROM r_bucketed r
        LEFT JOIN cross_repurchase cr ON r.user_id = cr.user_id
        LEFT JOIN cross_repurchase_amounts cra ON r.user_id = cra.user_id
        GROUP BY r.r_bucket
    ),
    ttl_all_cross AS (
        SELECT '已购客TTL' AS r_bucket, SUM(hist_users) AS hist_users,
               SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv
        FROM stats_all_cross
    ),
    -- 会员 同品
    stats_member_same AS (
        SELECT r.r_bucket,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT sr.user_id) AS repurchase_users,
               COALESCE(SUM(sra.repurchase_gsv), 0) AS repurchase_gsv
        FROM member_bucketed r
        LEFT JOIN same_repurchase sr ON r.user_id = sr.user_id
        LEFT JOIN same_repurchase_amounts sra ON r.user_id = sra.user_id
        GROUP BY r.r_bucket
    ),
    ttl_member_same AS (
        SELECT '已购客TTL' AS r_bucket, SUM(hist_users) AS hist_users,
               SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv
        FROM stats_member_same
    ),
    -- 会员 跨品类
    stats_member_cross AS (
        SELECT r.r_bucket,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT cr.user_id) AS repurchase_users,
               COALESCE(SUM(cra.repurchase_gsv), 0) AS repurchase_gsv
        FROM member_bucketed r
        LEFT JOIN cross_repurchase cr ON r.user_id = cr.user_id
        LEFT JOIN cross_repurchase_amounts cra ON r.user_id = cra.user_id
        GROUP BY r.r_bucket
    ),
    ttl_member_cross AS (
        SELECT '已购客TTL' AS r_bucket, SUM(hist_users) AS hist_users,
               SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv
        FROM stats_member_cross
    )
    SELECT 'all_same' AS mode, r_bucket, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM stats_all_same UNION ALL SELECT * FROM ttl_all_same
    )
    UNION ALL
    SELECT 'all_cross' AS mode, r_bucket, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM stats_all_cross UNION ALL SELECT * FROM ttl_all_cross
    )
    UNION ALL
    SELECT 'member_same' AS mode, r_bucket, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM stats_member_same UNION ALL SELECT * FROM ttl_member_same
    )
    UNION ALL
    SELECT 'member_cross' AS mode, r_bucket, hist_users, repurchase_users, repurchase_gsv FROM (
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
    # 参数组装（严格对应 SQL 中每个 CTE 的 ? 出现顺序，40 params）
    # base_orders: 2(start,end) + ch + ex  = 6
    # hist_customers: 1(cutoff_DATEDIFF) + 1(cutoff_pay_time) + ex = 6（无 category 过滤）
    # same/cross_repurchase + amounts: each 7 params
    # LEFT JOIN 引用已定义 CTE 不占额外参数
    # SQL ?顺序: category → start → end → channel → exclude
    # Sprint 54 Lane C L3: valid_where_params (含 ch+ex) 替代 base_params_extra + exclude_params
    _sr = [safe_category] + base_params + list(valid_where_params)
    _cr = [safe_category] + base_params + list(valid_where_params)
    _sa = [safe_category] + base_params + list(valid_where_params)
    _ca = [safe_category] + base_params + list(valid_where_params)
    full_params = (
        base_params + list(valid_where_params)
        + hist_params  # hist_customers params: cutoff_DATEDIFF, cutoff_pay_time, ex
        + _sr + _cr + _sa + _ca
    )
    # total: 2 + 1 + 4*7 = 31

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
        for seg in R_SEGMENT_ORDER:
            if seg not in results[mode]:
                results[mode][seg] = {
                    "hist_users": 0, "repurchase_users": 0,
                    "repurchase_rate": 0.0, "repurchase_gsv": 0.0, "repurchase_gsv_ratio": 0.0,
                }

    return results["all_same"], results["all_cross"], results["member_same"], results["member_cross"]
