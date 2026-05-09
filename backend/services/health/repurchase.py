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
from backend.semantic.calculations import safe_ratio


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
    """执行品类复购查询，返回以品类名为key的字典"""
    rows = conn.execute(f"""
        WITH product_users AS (
            SELECT spu_product_class, user_id,
                COUNT(DISTINCT order_id) as order_count,
                SUM(actual_amount) as gsv,
                AVG(actual_amount) as avg_order_value
            FROM orders
            WHERE {where_sql}
              AND spu_product_class IS NOT NULL
            GROUP BY spu_product_class, user_id
        ),
        repurchase_gaps AS (
            SELECT user_id, spu_product_class, pay_time,
                LAG(pay_time) OVER (PARTITION BY user_id, spu_product_class ORDER BY pay_time) as prev_pay_time
            FROM orders
            WHERE {where_sql}
              AND spu_product_class IS NOT NULL
        ),
        gap_stats AS (
            SELECT spu_product_class,
                quantile_cont(DATEDIFF('day', prev_pay_time, pay_time), 0.5) as median_days,
                quantile_cont(DATEDIFF('day', prev_pay_time, pay_time), 0.25) as p25,
                quantile_cont(DATEDIFF('day', prev_pay_time, pay_time), 0.75) as p75,
                AVG(DATEDIFF('day', prev_pay_time, pay_time)) as avg_days
            FROM repurchase_gaps
            WHERE prev_pay_time IS NOT NULL
              AND DATEDIFF('day', prev_pay_time, pay_time) > 0
            GROUP BY spu_product_class
        )
        SELECT
            p.spu_product_class,
            COUNT(DISTINCT p.user_id) as total_buyers,
            COUNT(DISTINCT CASE WHEN p.order_count >= 2 THEN p.user_id END) as repurchase_users,
            SUM(p.gsv) as gsv,
            SUM(p.gsv) / NULLIF(SUM(p.order_count), 0) as avg_order_value,
            COALESCE(g.median_days, 0) as median_days,
            COALESCE(g.p25, 0) as p25,
            COALESCE(g.p75, 0) as p75,
            COALESCE(g.avg_days, 0) as avg_days
        FROM product_users p
        LEFT JOIN gap_stats g ON p.spu_product_class = g.spu_product_class
        GROUP BY p.spu_product_class, g.median_days, g.p25, g.p75, g.avg_days
        ORDER BY SUM(p.gsv) DESC
    """, params + params).fetchall()  # 两个CTE各引用一次where_sql，需两份参数

    result: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        total_buyers = int(r[1])
        repurchase_users = int(r[2])
        result[r[0]] = {
            "product_class": r[0],
            "total_buyers": total_buyers,
            "repurchase_users": repurchase_users,
            "repurchase_rate": round(safe_ratio(repurchase_users, total_buyers, 0.0), 4),
            "median_days": int(r[5]) if r[5] else 0,
            "p25_days": int(r[6]) if r[6] else 0,
            "p75_days": int(r[7]) if r[7] else 0,
            "avg_days": round(float(r[8]), 1) if r[8] else 0.0,
            "avg_order_value": round(float(r[4]) if r[4] else 0.0, 2),
            "gsv": round(float(r[3]) if r[3] else 0.0, 2),
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
        if channel:
            fb.with_channels([channel])
        if exclude_channels:
            fb.with_exclude_channels(exclude_channels)
        where_sql, params = fb.build()

        # ── 1. 全店复购间隔统计（分位数 + 分桶 合并为单次查询） ──
        row = conn.execute(f"""
            WITH user_orders AS (
                SELECT user_id, pay_time,
                    LAG(pay_time) OVER (PARTITION BY user_id ORDER BY pay_time) as prev_pay_time
                FROM orders
                WHERE {where_sql}
            ),
            gaps AS (
                SELECT DATEDIFF('day', prev_pay_time, pay_time) as gap_days
                FROM user_orders
                WHERE prev_pay_time IS NOT NULL
                  AND DATEDIFF('day', prev_pay_time, pay_time) > 0
            )
            SELECT
                COUNT(*) as total_gaps,
                quantile_cont(gap_days, 0.5) as median_days,
                quantile_cont(gap_days, 0.25) as p25,
                quantile_cont(gap_days, 0.75) as p75,
                AVG(gap_days) as avg_days,
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

        total_gaps = int(row[0]) if row[0] else 0
        median_days = int(row[1]) if row[1] else 0
        p25 = int(row[2]) if row[2] else 0
        p75 = int(row[3]) if row[3] else 0
        avg_days = round(float(row[4]), 1) if row[4] else 0.0

        # ── 2. 分桶分布（当前周期 + 对比期 + 前年同期） ──
        bucket_distribution = []
        bucket_counts = {
            "0-7天": int(row[5] or 0),
            "8-14天": int(row[6] or 0),
            "15-30天": int(row[7] or 0),
            "31-60天": int(row[8] or 0),
            "61-90天": int(row[9] or 0),
            "91-180天": int(row[10] or 0),
            "181-365天": int(row[11] or 0),
            "365天以上": int(row[12] or 0),
        }

        def _fetch_bucket_distribution(s_date: str, e_date: str) -> tuple[int, Dict[str, int]]:
            """获取指定日期范围的复购间隔分桶分布"""
            fb_inner = FilterBuilder()
            fb_inner.with_metric_type(MetricType.GSV)
            fb_inner.with_time_range(s_date, e_date)
            if channel:
                fb_inner.with_channels([channel])
            if exclude_channels:
                fb_inner.with_exclude_channels(exclude_channels)
            where_sql_inner, params_inner = fb_inner.build()

            r = conn.execute(f"""
                WITH user_orders AS (
                    SELECT user_id, pay_time,
                        LAG(pay_time) OVER (PARTITION BY user_id ORDER BY pay_time) as prev_pay_time
                    FROM orders
                    WHERE {where_sql_inner}
                ),
                gaps AS (
                    SELECT DATEDIFF('day', prev_pay_time, pay_time) as gap_days
                    FROM user_orders
                    WHERE prev_pay_time IS NOT NULL
                      AND DATEDIFF('day', prev_pay_time, pay_time) > 0
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
            """, params_inner).fetchone()

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

        # 对比期：优先使用自定义对比日期（环比 / 自定义），否则默认去年同期
        if compare_start_date and compare_end_date:
            ly_start = compare_start_date
            ly_end = compare_end_date
        else:
            ly_start = _shift_date_year(start_date, -1)
            ly_end = _shift_date_year(end_date, -1)
        ly_total_gaps, ly_bucket_counts = _fetch_bucket_distribution(ly_start, ly_end)

        # 前年同期
        p2_start = _shift_date_year(start_date, -2)
        p2_end = _shift_date_year(end_date, -2)
        p2_total_gaps, p2_bucket_counts = _fetch_bucket_distribution(p2_start, p2_end)

        for start, end, label in BUCKETS:
            count = bucket_counts.get(label, 0)
            ratio = safe_ratio(count, total_gaps, 0.0)
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

        # 对比期
        fb_ly = FilterBuilder()
        fb_ly.with_metric_type(MetricType.GSV)
        fb_ly.with_time_range(ly_start, ly_end)
        if exclude_channels:
            fb_ly.with_exclude_channels(exclude_channels)
        where_sql_ly, params_ly = fb_ly.build()
        ly_products = _compute_product_repurchase(conn, where_sql_ly, params_ly)

        by_product_class = []
        for pc, cur in cur_products.items():
            ly = ly_products.get(pc)
            item = {**cur}
            if ly:
                item["ly_repurchase_rate"] = ly["repurchase_rate"]
                item["ly_median_days"] = ly["median_days"]
                item["ly_avg_days"] = ly.get("avg_days", 0.0)
                item["ly_gsv"] = ly["gsv"]
                # 复购率YOY = 百分点差（占比类指标）
                item["repurchase_rate_yoy"] = round(cur["repurchase_rate"] - ly["repurchase_rate"], 4)
                # 中位天数YOY = 百分点差（天数变化用差值更直观）
                item["median_days_yoy"] = round(cur["median_days"] - ly["median_days"], 4) if ly["median_days"] > 0 else None
                # 平均天数YOY = 差值
                item["avg_days_yoy"] = round(cur["avg_days"] - ly["avg_days"], 1) if ly["avg_days"] > 0 else None
                # GSV YOY = 百分比变化（绝对值类指标）
                item["gsv_yoy"] = round(safe_ratio(cur["gsv"] - ly["gsv"], ly["gsv"], 0.0), 4) if ly["gsv"] > 0 else None
            by_product_class.append(item)

        return {
            "period_start": start_date,
            "period_end": end_date,
            "all_store_median_days": median_days,
            "all_store_p25_days": p25,
            "all_store_p75_days": p75,
            "all_store_avg_days": avg_days,
            "bucket_distribution": bucket_distribution,
            "by_product_class": by_product_class,
            "year_label": start_date[:4],
            "comp_year_label": ly_start[:4],
            "prev2_year_label": p2_start[:4],
        }

    finally:
        conn.close()


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
            FROM orders
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
        conn.close()
