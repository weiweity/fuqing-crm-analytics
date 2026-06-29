"""
老客健康分析仪表盘 - 模块2: 复购周期分析

包含:
1. 复购间隔分布（直方图）
2. 品类复购周期对比
3. Cohort留存矩阵（月度）
"""

import calendar
from datetime import datetime
from typing import Dict, Any, Optional, List

from backend.db.connection import get_connection
from backend.semantic.filters import FilterBuilder, MetricType
from backend.semantic.calculations import safe_ratio, yoy_repurchase_rate
from backend.services.health.overview import compute_repurchase_rate


def _shift_date_year(date_str: str, years: int) -> str:
    """将日期/月份字符串向前/向后平移指定年数（支持 YYYY-MM-DD 或 YYYY-MM）"""
    if len(date_str) == 7:  # YYYY-MM
        d = datetime.strptime(date_str, "%Y-%m")
        d = d.replace(year=d.year + years)
        return d.strftime("%Y-%m")
    else:  # YYYY-MM-DD
        d = datetime.strptime(date_str, "%Y-%m-%d")
        try:
            d = d.replace(year=d.year + years)
        except ValueError:
            # 处理闰年2月29日
            d = d.replace(year=d.year + years, day=28)
        return d.strftime("%Y-%m-%d")


def _compute_product_repurchase(conn, where_sql: str, params: list) -> Dict[str, Dict[str, Any]]:
    """执行品类复购查询，返回以品类名为key的字典

    口径：
    - 复购判定：同一品类下，订单数 >= 2 即算复购用户（当天多单去重）
    - 复购间隔：按天去重后统计相邻购买间隔（当天多单合并为一天，自然无0天）
    - 复购客单价：复购订单（第2单及以后）的 actual_amount 平均值
    - 复购GSV：复购订单的 actual_amount 之和
    """
    rows = conn.execute(f"""
        WITH user_orders AS (
            SELECT
                spu_product_class, user_id, order_id, actual_amount, pay_time,
                LAG(pay_time) OVER (PARTITION BY user_id, spu_product_class ORDER BY pay_time) as prev_pay_time,
                ROW_NUMBER() OVER (PARTITION BY user_id, spu_product_class ORDER BY pay_time) as order_seq
            FROM orders o
            WHERE {where_sql}
              AND spu_product_class IS NOT NULL
        ),
        daily_orders AS (
            SELECT DISTINCT spu_product_class, user_id, CAST(pay_time AS DATE) as pay_date
            FROM user_orders
        ),
        daily_gap_stats AS (
            SELECT spu_product_class,
                quantile_cont(DATEDIFF('day', prev_pay_date, pay_date), 0.5) as median_days,
                quantile_cont(DATEDIFF('day', prev_pay_date, pay_date), 0.25) as p25,
                quantile_cont(DATEDIFF('day', prev_pay_date, pay_date), 0.75) as p75,
                AVG(DATEDIFF('day', prev_pay_date, pay_date)) as avg_days
            FROM (
                SELECT
                    spu_product_class, user_id, pay_date,
                    LAG(pay_date) OVER (PARTITION BY user_id, spu_product_class ORDER BY pay_date) as prev_pay_date
                FROM daily_orders
            )
            WHERE prev_pay_date IS NOT NULL
            GROUP BY spu_product_class
        ),
        product_users AS (
            SELECT
                spu_product_class, user_id,
                COUNT(DISTINCT order_id) as total_orders,
                COUNT(DISTINCT CASE WHEN order_seq >= 2 THEN order_id END) as repurchase_order_count,
                SUM(actual_amount) as gsv,
                SUM(CASE WHEN order_seq >= 2 THEN actual_amount ELSE 0 END) as repurchase_gsv
            FROM user_orders
            GROUP BY spu_product_class, user_id
        )
        SELECT
            p.spu_product_class,
            COUNT(DISTINCT p.user_id) as total_buyers,
            COUNT(DISTINCT CASE WHEN p.total_orders >= 2 THEN p.user_id END) as repurchase_users,
            SUM(p.gsv) as gsv,
            SUM(p.gsv) / NULLIF(SUM(p.total_orders), 0) as avg_order_value,
            SUM(p.repurchase_gsv) as repurchase_gsv,
            SUM(p.repurchase_gsv) / NULLIF(SUM(p.repurchase_order_count), 0) as repurchase_order_value,
            COALESCE(g.median_days, 0) as median_days,
            COALESCE(g.p25, 0) as p25,
            COALESCE(g.p75, 0) as p75,
            COALESCE(g.avg_days, 0) as avg_days
        FROM product_users p
        LEFT JOIN daily_gap_stats g ON p.spu_product_class = g.spu_product_class
        GROUP BY p.spu_product_class, g.median_days, g.p25, g.p75, g.avg_days
        ORDER BY SUM(p.gsv) DESC
    """, params).fetchall()

    result: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        total_buyers = int(r[1])
        repurchase_users = int(r[2])
        result[r[0]] = {
            "product_class": r[0],
            "total_buyers": total_buyers,
            "repurchase_users": repurchase_users,
            "repurchase_rate": round(safe_ratio(repurchase_users, total_buyers, 0.0), 4),
            "median_days": int(r[7]) if r[7] else 0,
            "p25_days": int(r[8]) if r[8] else 0,
            "p75_days": int(r[9]) if r[9] else 0,
            "avg_days": round(float(r[10]), 1) if r[10] else 0.0,
            "avg_order_value": round(float(r[4]) if r[4] else 0.0, 2),
            "gsv": round(float(r[3]) if r[3] else 0.0, 2),
            "repurchase_gsv": round(float(r[5]) if r[5] else 0.0, 2),
            "repurchase_order_value": round(float(r[6]) if r[6] else 0.0, 2),
        }
    return result


def _compute_cross_category_return(conn, where_sql: str, params: list) -> Dict[str, Dict[str, Any]]:
    """执行跨品类回购店铺查询，返回以品类名为key的字典

    口径：
    - 购买人数：周期内买过该品类的人数
    - 回购人数：首购该品类后，周期内有任意后续购买（含同品类/跨品类）的人数
    - 回购间隔：从首购该品类到下一次任意购买的间隔，按天去重后计算（自然无0天）
    - 客单价/GSV：该品类的入口价值（首购订单）
    - 回流GSV/回流客单价：首购该品类后，用户后续全店购买的金额汇总及均值
    """
    rows = conn.execute(f"""
        WITH user_product_orders AS (
            SELECT
                spu_product_class, user_id, order_id, actual_amount, pay_time,
                ROW_NUMBER() OVER (PARTITION BY user_id, spu_product_class ORDER BY pay_time) as rn
            FROM orders o
            WHERE {where_sql}
              AND spu_product_class IS NOT NULL
        ),
        first_product_purchase AS (
            SELECT spu_product_class, user_id, CAST(pay_time AS DATE) as first_pay_date, pay_time
            FROM user_product_orders
            WHERE rn = 1
        ),
        user_all_orders AS (
            SELECT DISTINCT user_id, CAST(pay_time AS DATE) as pay_date
            FROM orders o
            WHERE {where_sql}
        ),
        next_purchase AS (
            SELECT
                f.spu_product_class,
                f.user_id,
                f.first_pay_date,
                MIN(u.pay_date) as next_pay_date
            FROM first_product_purchase f
            LEFT JOIN user_all_orders u
                ON f.user_id = u.user_id
                AND u.pay_date > f.first_pay_date
            GROUP BY f.spu_product_class, f.user_id, f.first_pay_date
        ),
        subsequent_orders AS (
            SELECT
                f.spu_product_class,
                SUM(o.actual_amount) as subsequent_gsv,
                COUNT(DISTINCT o.order_id) as subsequent_order_count
            FROM first_product_purchase f
            JOIN (
                SELECT user_id, order_id, actual_amount, pay_time
                FROM orders o
                WHERE {where_sql}
            ) o
                ON f.user_id = o.user_id
                AND o.pay_time > f.pay_time
            GROUP BY f.spu_product_class
        ),
        product_stats AS (
            SELECT
                user_product_orders.spu_product_class,
                COUNT(DISTINCT user_product_orders.user_id) as total_buyers,
                COUNT(DISTINCT CASE WHEN next_pay_date IS NOT NULL THEN user_product_orders.user_id END) as repurchase_users,
                SUM(CASE WHEN rn = 1 THEN actual_amount ELSE 0 END) as gsv,
                SUM(CASE WHEN rn = 1 THEN actual_amount ELSE 0 END) /
                    NULLIF(COUNT(DISTINCT CASE WHEN rn = 1 THEN order_id END), 0) as avg_order_value
            FROM user_product_orders
            LEFT JOIN next_purchase np
                ON user_product_orders.spu_product_class = np.spu_product_class
                AND user_product_orders.user_id = np.user_id
            GROUP BY user_product_orders.spu_product_class
        ),
        gap_stats AS (
            SELECT
                spu_product_class,
                quantile_cont(DATEDIFF('day', first_pay_date, next_pay_date), 0.5) as median_days,
                quantile_cont(DATEDIFF('day', first_pay_date, next_pay_date), 0.25) as p25,
                quantile_cont(DATEDIFF('day', first_pay_date, next_pay_date), 0.75) as p75,
                AVG(DATEDIFF('day', first_pay_date, next_pay_date)) as avg_days
            FROM next_purchase
            WHERE next_pay_date IS NOT NULL
            GROUP BY spu_product_class
        )
        SELECT
            p.spu_product_class,
            p.total_buyers,
            p.repurchase_users,
            p.gsv,
            p.avg_order_value,
            COALESCE(s.subsequent_gsv, 0) as subsequent_gsv,
            COALESCE(s.subsequent_gsv, 0) / NULLIF(s.subsequent_order_count, 0) as subsequent_order_value,
            COALESCE(g.median_days, 0) as median_days,
            COALESCE(g.p25, 0) as p25,
            COALESCE(g.p75, 0) as p75,
            COALESCE(g.avg_days, 0) as avg_days
        FROM product_stats p
        LEFT JOIN gap_stats g ON p.spu_product_class = g.spu_product_class
        LEFT JOIN subsequent_orders s ON p.spu_product_class = s.spu_product_class
        ORDER BY p.gsv DESC
    """,
        # where_sql 在 user_product_orders / user_all_orders / subsequent_orders 子查询中各使用一次
        # 因此参数需要复制三份，与占位符数量一一对应
        params + params + params
    ).fetchall()

    result: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        total_buyers = int(r[1])
        repurchase_users = int(r[2])
        result[r[0]] = {
            "product_class": r[0],
            "total_buyers": total_buyers,
            "repurchase_users": repurchase_users,
            "repurchase_rate": round(safe_ratio(repurchase_users, total_buyers, 0.0), 4),
            "median_days": int(r[7]) if r[7] else 0,
            "p25_days": int(r[8]) if r[8] else 0,
            "p75_days": int(r[9]) if r[9] else 0,
            "avg_days": round(float(r[10]), 1) if r[10] else 0.0,
            "avg_order_value": round(float(r[4]) if r[4] else 0.0, 2),
            "gsv": round(float(r[3]) if r[3] else 0.0, 2),
            "repurchase_gsv": round(float(r[5]) if r[5] else 0.0, 2),
            "repurchase_order_value": round(float(r[6]) if r[6] else 0.0, 2),
        }
    return result


BUCKETS = [
    (0, 7, "0-7天"),
    (8, 14, "8-14天"),
    (15, 30, "15-30天"),
    (31, 60, "31-60天"),
    (61, 90, "61-90天"),
    (91, 180, "91-180天"),
    (181, 365, "181-365天"),
    (366, None, "365天以上"),
]


def _compute_days_stats(conn, where_sql: str, params: list) -> Dict[str, Any]:
    """全店复购间隔分位数 + 平均 (Sprint 169: 抽 helper 复用 cur/ly 期间, 跟分桶解耦)

    Returns:
        {"median_days": int, "p25_days": int, "p75_days": int, "avg_days": float}
    """
    row = conn.execute(f"""
        WITH user_orders AS (
            SELECT DISTINCT user_id, CAST(pay_time AS DATE) as pay_date
            FROM orders o
            WHERE {where_sql}
        ),
        gaps AS (
            SELECT DATEDIFF('day', prev_pay_date, pay_date) as gap_days
            FROM (
                SELECT user_id, pay_date,
                    LAG(pay_date) OVER (PARTITION BY user_id ORDER BY pay_date) as prev_pay_date
                FROM user_orders
            )
            WHERE prev_pay_date IS NOT NULL
              AND DATEDIFF('day', prev_pay_date, pay_date) > 0
        )
        SELECT
            quantile_cont(gap_days, 0.5) as median_days,
            quantile_cont(gap_days, 0.25) as p25,
            quantile_cont(gap_days, 0.75) as p75,
            AVG(gap_days) as avg_days
        FROM gaps
    """, params).fetchone()

    return {
        "median_days": int(row[0]) if row[0] else 0,
        "p25_days": int(row[1]) if row[1] else 0,
        "p75_days": int(row[2]) if row[2] else 0,
        "avg_days": round(float(row[3]), 1) if row[3] else 0.0,
    }


def _build_period_filter(start_date: str, end_date: str,
                         channel: Optional[str],
                         exclude_channels: Optional[List[str]]) -> tuple[str, list]:
    """Sprint 169: 抽 helper 复用 FilterBuilder (cur/ly 期间对比, 跟 _fetch_bucket_distribution 对齐)

    Sprint 169 hotfix: 加 channel != "全店" 守卫, 跟 overview.py:151 sentinel pattern 1:1 对齐.
    "全店" 是 sentinel = 不过滤 channel (全店聚合), 不是字面 channel name (orders.channel 没有 "全店").
    """
    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    fb.with_time_range(start_date, end_date)
    if channel and channel != "全店":
        fb.with_channels([channel])
    if exclude_channels:
        fb.with_exclude_channels(exclude_channels)
    return fb.build()


def _fetch_bucket_distribution(conn, s_date: str, e_date: str,
                               channel: Optional[str] = None,
                               exclude_channels: Optional[List[str]] = None) -> tuple[int, Dict[str, int]]:
    """Sprint 169: 提到模块级 (原 nested closure), 复用 cur/ly/p2 期间分桶查询"""
    where_sql, params = _build_period_filter(s_date, e_date, channel, exclude_channels)
    r = conn.execute(f"""
        WITH user_orders AS (
            SELECT DISTINCT user_id, CAST(pay_time AS DATE) as pay_date
            FROM orders o
            WHERE {where_sql}
        ),
        gaps AS (
            SELECT DATEDIFF('day', prev_pay_date, pay_date) as gap_days
            FROM (
                SELECT user_id, pay_date,
                    LAG(pay_date) OVER (PARTITION BY user_id ORDER BY pay_date) as prev_pay_date
                FROM user_orders
            )
            WHERE prev_pay_date IS NOT NULL
              AND DATEDIFF('day', prev_pay_date, pay_date) > 0
        )
        SELECT
            COUNT(*) as total_gaps,
            COUNT(CASE WHEN gap_days <= 7 THEN 1 END) as b_0_7,
            COUNT(CASE WHEN gap_days > 7 AND gap_days <= 14 THEN 1 END) as b_8_14,
            COUNT(CASE WHEN gap_days > 14 AND gap_days <= 30 THEN 1 END) as b_15_30,
            COUNT(CASE WHEN gap_days > 30 AND gap_days <= 60 THEN 1 END) as b_31_60,
            COUNT(CASE WHEN gap_days > 60 AND gap_days <= 90 THEN 1 END) as b_61_90,
            COUNT(CASE WHEN gap_days > 90 AND gap_days <= 180 THEN 1 END) as b_91_180,
            COUNT(CASE WHEN gap_days > 180 AND gap_days <= 365 THEN 1 END) as b_181_365,
            COUNT(CASE WHEN gap_days > 365 THEN 1 END) as b_366_plus
        FROM gaps
    """, params).fetchone()

    tg = int(r[0]) if r[0] else 0
    bc = {
        "0-7天": int(r[1] or 0),
        "8-14天": int(r[2] or 0),
        "15-30天": int(r[3] or 0),
        "31-60天": int(r[4] or 0),
        "61-90天": int(r[5] or 0),
        "91-180天": int(r[6] or 0),
        "181-365天": int(r[7] or 0),
        "365天以上": int(r[8] or 0),
    }
    return tg, bc


def get_repurchase_cycle(start_date: str, end_date: str,
                         exclude_channels: Optional[List[str]] = None,
                         channel: Optional[str] = None,
                         compare_start_date: Optional[str] = None,
                         compare_end_date: Optional[str] = None) -> Dict[str, Any]:
    """
    复购周期分析
    - 全店复购间隔分布（中位/P25/P75 + 分桶）
    - 分品类复购指标

    当传入 compare_start_date/compare_end_date 时，对比期使用自定义日期
    而不是自动计算的去年同期（支持环比 / 自定义对比）。
    """
    conn = get_connection()
    try:
        fb = FilterBuilder()
        fb.with_metric_type(MetricType.GSV)
        fb.with_time_range(start_date, end_date)
        if channel and channel != "全店":
            fb.with_channels([channel])
        if exclude_channels:
            fb.with_exclude_channels(exclude_channels)
        where_sql, params = fb.build()

        # ── 1. 全店复购分位数 + 复购率 (Sprint 169: 拆 days/buckets/rate 3 查询) ──
        # 按天去重：当天多单合并为一天，与分品类口径保持一致
        cur_days = _compute_days_stats(conn, where_sql, params)
        cur_rate, _, _ = compute_repurchase_rate(conn, where_sql, params)

        # ── 2. 分桶分布（当前周期 + 对比期 + 前年同期，复用 _fetch_bucket_distribution） ──
        # 对比期优先自定义, 否则自动 Y-1
        if compare_start_date and compare_end_date:
            ly_start = compare_start_date
            ly_end = compare_end_date
        else:
            ly_start = _shift_date_year(start_date, -1)
            ly_end = _shift_date_year(end_date, -1)
        # 前年同期
        p2_start = _shift_date_year(start_date, -2)
        p2_end = _shift_date_year(end_date, -2)

        cur_total_gaps, cur_bucket_counts = _fetch_bucket_distribution(conn, start_date, end_date, channel, exclude_channels)
        ly_total_gaps, ly_bucket_counts = _fetch_bucket_distribution(conn, ly_start, ly_end, channel, exclude_channels)
        p2_total_gaps, p2_bucket_counts = _fetch_bucket_distribution(conn, p2_start, p2_end, channel, exclude_channels)

        # Sprint 169: 去年同期全店分位数 + 复购率 (跟 cur 同口径, 用于 YOY 计算)
        where_sql_ly, params_ly = _build_period_filter(ly_start, ly_end, channel, exclude_channels)
        ly_days = _compute_days_stats(conn, where_sql_ly, params_ly)
        ly_rate, _, _ = compute_repurchase_rate(conn, where_sql_ly, params_ly)

        # Sprint 169: _fetch_bucket_distribution 已提到模块级, 复用 cur/ly/p2

        bucket_distribution = []
        for start, end, label in BUCKETS:
            count = cur_bucket_counts.get(label, 0)
            ratio = safe_ratio(count, cur_total_gaps, 0.0)
            ly_count = ly_bucket_counts.get(label, 0)
            ly_ratio = safe_ratio(ly_count, ly_total_gaps, 0.0)
            p2_count = p2_bucket_counts.get(label, 0)
            p2_ratio = safe_ratio(p2_count, p2_total_gaps, 0.0)
            bucket_distribution.append({
                "bucket_label": label,
                "bucket_start": start,
                "bucket_end": end,
                "user_count": count,
                "user_ratio": round(ratio, 4),
                "ly_user_count": ly_count if ly_total_gaps > 0 else None,
                "ly_user_ratio": round(ly_ratio, 4) if ly_total_gaps > 0 else None,
                "user_count_yoy": round(count - ly_count, 4) if ly_total_gaps > 0 else None,
                "user_ratio_yoy": round(ratio - ly_ratio, 4) if ly_total_gaps > 0 else None,
                "prev2_user_count": p2_count if p2_total_gaps > 0 else None,
                "prev2_user_ratio": round(p2_ratio, 4) if p2_total_gaps > 0 else None,
            })

        # ── 3. 分品类复购指标（当前周期 + 对比期） ──
        cur_products = _compute_product_repurchase(conn, where_sql, params)
        cur_cross = _compute_cross_category_return(conn, where_sql, params)

        # 对比期 (where_sql_ly / params_ly 已在 Sprint 169 提前计算, 复用)
        ly_products = _compute_product_repurchase(conn, where_sql_ly, params_ly)
        ly_cross = _compute_cross_category_return(conn, where_sql_ly, params_ly)

        def _merge_yoy(cur_data: Dict[str, Any], ly_data: Dict[str, Any]) -> Dict[str, Any]:
            """将当前周期数据与去年同期数据合并，计算YOY"""
            item = {**cur_data}
            if ly_data:
                item["ly_repurchase_rate"] = ly_data["repurchase_rate"]
                item["ly_median_days"] = ly_data["median_days"]
                item["ly_avg_days"] = ly_data.get("avg_days", 0.0)
                item["ly_gsv"] = ly_data["gsv"]
                item["repurchase_rate_yoy"] = round(cur_data["repurchase_rate"] - ly_data["repurchase_rate"], 4)
                item["median_days_yoy"] = round(cur_data["median_days"] - ly_data["median_days"], 4) if ly_data["median_days"] > 0 else None
                item["avg_days_yoy"] = round(cur_data["avg_days"] - ly_data["avg_days"], 1) if ly_data["avg_days"] > 0 else None
                item["gsv_yoy"] = round(safe_ratio(cur_data["gsv"] - ly_data["gsv"], ly_data["gsv"], 0.0), 4) if ly_data["gsv"] > 0 else None
            return item

        by_product_class = []
        for pc, cur in cur_products.items():
            ly = ly_products.get(pc)
            by_product_class.append(_merge_yoy(cur, ly))

        by_product_class_return = []
        for pc, cur in cur_cross.items():
            ly = ly_cross.get(pc)
            by_product_class_return.append(_merge_yoy(cur, ly))

        return {
            "period_start": start_date,
            "period_end": end_date,
            "all_store_median_days": cur_days["median_days"],
            "all_store_p25_days": cur_days["p25_days"],
            "all_store_p75_days": cur_days["p75_days"],
            "all_store_avg_days": cur_days["avg_days"],
            # Sprint 169 新增: 全店复购率 + 5 项 YOY
            "all_store_repurchase_rate": round(cur_rate, 4),
            "ly_all_store_median_days": ly_days["median_days"] if ly_total_gaps > 0 else None,
            "ly_all_store_p25_days": ly_days["p25_days"] if ly_total_gaps > 0 else None,
            "ly_all_store_p75_days": ly_days["p75_days"] if ly_total_gaps > 0 else None,
            "ly_all_store_avg_days": ly_days["avg_days"] if ly_total_gaps > 0 else None,
            "ly_all_store_repurchase_rate": round(ly_rate, 4) if ly_total_gaps > 0 else None,
            "yoy_all_store_repurchase_rate": yoy_repurchase_rate(cur_rate, ly_rate) if ly_total_gaps > 0 else None,
            # Sprint 169: 天数 YOY 用 raw diff (cur - ly), 业务直觉 "间隔缩/拉长"
            "median_days_yoy": cur_days["median_days"] - ly_days["median_days"] if ly_total_gaps > 0 else None,
            "p25_days_yoy": cur_days["p25_days"] - ly_days["p25_days"] if ly_total_gaps > 0 else None,
            "p75_days_yoy": cur_days["p75_days"] - ly_days["p75_days"] if ly_total_gaps > 0 else None,
            "avg_days_yoy": round(cur_days["avg_days"] - ly_days["avg_days"], 1) if ly_total_gaps > 0 else None,
            "bucket_distribution": bucket_distribution,
            "by_product_class": by_product_class,
            "by_product_class_return": by_product_class_return,
            "year_label": start_date[:4],
            "comp_year_label": ly_start[:4],
            "prev2_year_label": p2_start[:4],
        }

    finally:
        pass


def _compute_cohort_matrix(conn, start_month: str, end_month: str,
                           exclude_channels: Optional[List[str]] = None,
                           channel: Optional[str] = None) -> Dict[str, Any]:
    """内部函数：计算指定月份的Cohort留存矩阵"""
    # 动态获取end_month的月末日期
    end_year, end_month_num = int(end_month[:4]), int(end_month[5:7])
    _, last_day = calendar.monthrange(end_year, end_month_num)
    end_month_last_day = f"{end_month}-{last_day:02d}"

    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    fb.with_time_range(f"{start_month}-01", end_date=end_month_last_day)
    if channel:
        fb.with_channels([channel])
    if exclude_channels:
        fb.with_exclude_channels(exclude_channels)
    where_sql, params = fb.build()

    time_start = f"{start_month}-01"
    time_end = end_month_last_day

    rows = conn.execute(f"""
        WITH valid_orders AS (
            SELECT user_id, pay_time,
                DATE_TRUNC('month', pay_time) as order_month
            FROM orders o
            WHERE {where_sql}
              AND pay_time >= ?::DATE
              AND pay_time <= ?::DATE
        ),
        first_purchase AS (
            SELECT user_id, MIN(order_month) as cohort_month
            FROM valid_orders
            GROUP BY user_id
        ),
        user_monthly AS (
            SELECT DISTINCT user_id, order_month
            FROM valid_orders
        ),
        cohort_sizes AS (
            SELECT cohort_month, COUNT(DISTINCT user_id) as size
            FROM first_purchase
            GROUP BY cohort_month
        )
        SELECT
            fp.cohort_month,
            um.order_month,
            COUNT(DISTINCT um.user_id) as retained_users,
            cs.size as cohort_size
        FROM first_purchase fp
        LEFT JOIN user_monthly um
            ON fp.user_id = um.user_id
            AND um.order_month >= fp.cohort_month
        JOIN cohort_sizes cs ON fp.cohort_month = cs.cohort_month
        WHERE fp.cohort_month BETWEEN ? AND ?
        GROUP BY fp.cohort_month, um.order_month, cs.size
        ORDER BY fp.cohort_month, um.order_month
    """, params + [time_start, time_end, f"{start_month}-01", f"{end_month}-01"]).fetchall()

    # 整理为矩阵格式
    cohort_data: Dict[str, Dict[str, float]] = {}
    cohort_sizes: Dict[str, int] = {}

    for r in rows:
        cohort = r[0].strftime("%Y-%m") if hasattr(r[0], 'strftime') else str(r[0])[:7]
        period = r[1].strftime("%Y-%m") if hasattr(r[1], 'strftime') else str(r[1])[:7]
        retained = int(r[2])
        size = int(r[3])

        if cohort not in cohort_data:
            cohort_data[cohort] = {}
            cohort_sizes[cohort] = size

        cohort_data[cohort][period] = safe_ratio(retained, size, 0.0)

    cohort_months = sorted(cohort_data.keys())
    if not cohort_months:
        return {
            "cohort_months": [],
            "periods": [],
            "matrix": [],
            "avg_by_period": [],
        }

    max_periods = 0
    for cohort in cohort_months:
        periods_for_cohort = sorted(cohort_data[cohort].keys())
        max_periods = max(max_periods, len(periods_for_cohort))

    period_labels = [f"M{i}" for i in range(max_periods)]

    matrix = []
    weighted_sum = [0.0] * max_periods
    total_size = [0] * max_periods

    for cohort in cohort_months:
        row = []
        periods_for_cohort = sorted(cohort_data[cohort].keys())
        size = cohort_sizes[cohort]
        for i, period in enumerate(periods_for_cohort):
            rate = cohort_data[cohort].get(period, 0.0)
            row.append(round(rate, 4))
            weighted_sum[i] += rate * size
            total_size[i] += size

        while len(row) < max_periods:
            row.append(None)

        matrix.append(row)

    avg_by_period: List[Optional[float]] = [None] * max_periods
    for i in range(max_periods):
        if total_size[i] > 0:
            avg_by_period[i] = round(weighted_sum[i] / total_size[i], 4)

    return {
        "cohort_months": cohort_months,
        "periods": period_labels,
        "matrix": matrix,
        "avg_by_period": avg_by_period,
    }


def get_cohort_retention(start_month: str, end_month: str,
                         exclude_channels: Optional[List[str]] = None,
                         channel: Optional[str] = None) -> Dict[str, Any]:
    """
    Cohort留存矩阵（月度）含去年同期对比
    - 行: 首购月份
    - 列: 后续月份（M0, M1, M2...）
    - 值: 该cohort在对应月份的复购率
    """
    conn = get_connection()
    try:
        # 当前周期
        cur = _compute_cohort_matrix(conn, start_month, end_month, exclude_channels, channel)

        # 去年同期
        ly_start = _shift_date_year(start_month, -1)
        ly_end = _shift_date_year(end_month, -1)
        ly = _compute_cohort_matrix(conn, ly_start, ly_end, exclude_channels, channel)

        # 对齐LY矩阵到当前cohort_months（按索引对齐，第i个cohort对应去年第i个cohort）
        ly_matrix_aligned: List[List[Optional[float]]] = []
        for i, cur_cohort in enumerate(cur["cohort_months"]):
            ly_cohort = _shift_date_year(cur_cohort, -1)
            ly_row: List[Optional[float]] = [None] * len(cur["periods"])
            if ly_cohort in ly.get("cohort_months", []) and i < len(ly["matrix"]):
                # 只取与当前periods相同长度的列
                src_row = ly["matrix"][i]
                for j in range(min(len(cur["periods"]), len(src_row))):
                    ly_row[j] = src_row[j]
            ly_matrix_aligned.append(ly_row)

        return {
            "cohort_months": cur["cohort_months"],
            "periods": cur["periods"],
            "matrix": cur["matrix"],
            "avg_by_period": cur["avg_by_period"],
            "ly_matrix": ly_matrix_aligned,
            "ly_avg_by_period": ly.get("avg_by_period", []),
        }

    finally:
        pass
