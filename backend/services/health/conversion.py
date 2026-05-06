"""
老客健康分析仪表盘 - 模块4: 新客转化追踪

追踪首购→复购的转化漏斗，分渠道质量评级。
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from backend.db.connection import get_connection
from backend.semantic.filters import FilterBuilder, MetricType
from backend.semantic.calculations import safe_ratio


def _quality_grade(score: float) -> str:
    if score >= 80: return "A"
    if score >= 60: return "B"
    if score >= 40: return "C"
    return "D"


def get_new_customer_conversion(analysis_date: str, lookback_months: int = 12,
                                exclude_channels: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    新客转化追踪
    - 总体漏斗（最近12个月cohort平均）
    - 分渠道新客质量
    - 月度趋势
    """
    conn = get_connection()
    try:
        end_dt = datetime.strptime(analysis_date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=lookback_months * 30)
        start_date = start_dt.strftime("%Y-%m-%d")

        fb = FilterBuilder()
        fb.with_metric_type(MetricType.GSV)
        fb.with_time_range(start_date, analysis_date)
        if exclude_channels:
            fb.with_exclude_channels(exclude_channels)
        where_sql, params = fb.build()

        # ── 1. 总体漏斗（按首购月份cohort）
        # 修复：first_purchase 从 user_first_purchase 获取真实首购时间，
        # 避免在 valid_orders 时间窗口内取 MIN(pay_time) 导致伪首购。
        rows = conn.execute(f"""
            WITH valid_orders AS (
                SELECT user_id, pay_time, actual_amount, channel
                FROM orders
                WHERE {where_sql}
            ),
            first_purchase AS (
                SELECT
                    u.user_id,
                    u.first_pay_date as first_pay_time,
                    DATE_TRUNC('month', u.first_pay_date) as cohort_month
                FROM user_first_purchase u
                WHERE u.user_id IN (SELECT DISTINCT user_id FROM valid_orders)
                  AND u.first_pay_date >= ?::DATE
                  AND u.first_pay_date <= ?::DATE
            ),
            cohort_stats AS (
                SELECT
                    fp.cohort_month,
                    COUNT(DISTINCT fp.user_id) as total_first,
                    COUNT(DISTINCT CASE WHEN DATE(vo.pay_time) > fp.first_pay_time
                        AND DATE(vo.pay_time) <= fp.first_pay_time + INTERVAL '7 days'
                        THEN vo.user_id END) as day7,
                    COUNT(DISTINCT CASE WHEN DATE(vo.pay_time) > fp.first_pay_time
                        AND DATE(vo.pay_time) <= fp.first_pay_time + INTERVAL '30 days'
                        THEN vo.user_id END) as day30,
                    COUNT(DISTINCT CASE WHEN DATE(vo.pay_time) > fp.first_pay_time
                        AND DATE(vo.pay_time) <= fp.first_pay_time + INTERVAL '90 days'
                        THEN vo.user_id END) as day90
                FROM first_purchase fp
                LEFT JOIN valid_orders vo ON fp.user_id = vo.user_id
                    AND DATE(vo.pay_time) > fp.first_pay_time
                GROUP BY fp.cohort_month
            )
            SELECT * FROM cohort_stats ORDER BY cohort_month
        """, params + [start_date, analysis_date]).fetchall()

        cohort_funnels = []
        total_first = 0
        total_day7 = 0
        total_day30 = 0
        total_day90 = 0

        for r in rows:
            cohort = r[0].strftime("%Y-%m") if hasattr(r[0], 'strftime') else str(r[0])[:7]
            first = int(r[1])
            d7 = int(r[2])
            d30 = int(r[3])
            d90 = int(r[4])

            total_first += first
            total_day7 += d7
            total_day30 += d30
            total_day90 += d90

            cohort_funnels.append({
                "cohort_date": cohort,
                "total_first_purchase": first,
                "day7_repurchase": d7,
                "day7_rate": round(safe_ratio(d7, first, 0.0), 4),
                "day30_repurchase": d30,
                "day30_rate": round(safe_ratio(d30, first, 0.0), 4),
                "day90_repurchase": d90,
                "day90_rate": round(safe_ratio(d90, first, 0.0), 4),
                "day7_not_repurchased": first - d7,
                "day30_not_repurchased": first - d30,
                "day90_not_repurchased": first - d90,
            })

        overall = {
            "cohort_date": "overall",
            "total_first_purchase": total_first,
            "day7_repurchase": total_day7,
            "day7_rate": round(safe_ratio(total_day7, total_first, 0.0), 4),
            "day30_repurchase": total_day30,
            "day30_rate": round(safe_ratio(total_day30, total_first, 0.0), 4),
            "day90_repurchase": total_day90,
            "day90_rate": round(safe_ratio(total_day90, total_first, 0.0), 4),
            "day7_not_repurchased": total_first - total_day7,
            "day30_not_repurchased": total_first - total_day30,
            "day90_not_repurchased": total_first - total_day90,
        }

        # ── 2. 分渠道质量 ──
        # 修复：
        # 1. first_purchase 从 user_first_purchase 获取真实首购，避免伪首购
        # 2. GROUP BY 改为 user_id 级别，避免同一用户被拆分到多个渠道重复计数
        channel_rows = conn.execute(f"""
            WITH valid_orders AS (
                SELECT user_id, pay_time, actual_amount, channel
                FROM orders
                WHERE {where_sql}
            ),
            first_purchase AS (
                SELECT
                    u.user_id,
                    u.first_pay_date as first_pay_time,
                    FIRST(vo.channel ORDER BY vo.pay_time) as first_channel,
                    AVG(vo.actual_amount) as first_aus
                FROM user_first_purchase u
                LEFT JOIN valid_orders vo ON u.user_id = vo.user_id AND DATE(vo.pay_time) = u.first_pay_date
                WHERE u.user_id IN (SELECT DISTINCT user_id FROM valid_orders)
                  AND u.first_pay_date >= ?::DATE
                  AND u.first_pay_date <= ?::DATE
                GROUP BY u.user_id, u.first_pay_date
            ),
            repurchase AS (
                SELECT
                    fp.user_id,
                    MAX(fp.first_channel) as first_channel,
                    COUNT(CASE WHEN DATE(vo.pay_time) > fp.first_pay_time
                        AND DATE(vo.pay_time) <= fp.first_pay_time + INTERVAL '30 days'
                        THEN 1 END) as d30,
                    COUNT(CASE WHEN DATE(vo.pay_time) > fp.first_pay_time
                        AND DATE(vo.pay_time) <= fp.first_pay_time + INTERVAL '90 days'
                        THEN 1 END) as d90
                FROM first_purchase fp
                LEFT JOIN valid_orders vo ON fp.user_id = vo.user_id
                    AND DATE(vo.pay_time) > fp.first_pay_time
                GROUP BY fp.user_id
            )
            SELECT
                r.first_channel,
                COUNT(DISTINCT fp.user_id) as first_users,
                AVG(fp.first_aus) as avg_first_aus,
                AVG(CASE WHEN r.d30 > 0 THEN 1.0 ELSE 0 END) as d30_rate,
                AVG(CASE WHEN r.d90 > 0 THEN 1.0 ELSE 0 END) as d90_rate
            FROM first_purchase fp
            JOIN repurchase r ON fp.user_id = r.user_id
            GROUP BY r.first_channel
            ORDER BY COUNT(DISTINCT fp.user_id) DESC
        """, params + [start_date, analysis_date]).fetchall()

        channel_quality = []
        for r in channel_rows:
            ch = r[0]
            first_users = int(r[1])
            avg_aus = float(r[2]) if r[2] else 0.0
            d30_rate = float(r[3]) if r[3] else 0.0
            d90_rate = float(r[4]) if r[4] else 0.0

            # 质量分 = 30日复购率*40 + 90日复购率*30 + 客单价归一化*30
            score = min(d30_rate * 100, 40) + min(d90_rate * 100, 30) + min(avg_aus / 200 * 30, 30)

            channel_quality.append({
                "channel": ch,
                "first_purchase_users": first_users,
                "first_purchase_aus": round(avg_aus, 2),
                "day30_repurchase_rate": round(d30_rate, 4),
                "day90_repurchase_rate": round(d90_rate, 4),
                "quality_score": round(score, 1),
                "quality_grade": _quality_grade(score),
            })

        # 月度趋势：从cohort数据中提取
        monthly_trend = [
            {
                "month": cf["cohort_date"],
                "day7_rate": cf["day7_rate"],
                "day30_rate": cf["day30_rate"],
                "day90_rate": cf["day90_rate"],
            }
            for cf in cohort_funnels
        ]

        return {
            "analysis_date": analysis_date,
            "overall_funnel": overall,
            "cohort_funnels": cohort_funnels,
            "channel_quality": channel_quality,
            "monthly_trend": monthly_trend,
        }

    finally:
        conn.close()
