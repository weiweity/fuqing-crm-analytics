"""
老客健康分析仪表盘 - 模块5: 大促日历

大促 vs 日常对比（简化版 Phase 2）
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from backend.db.connection import get_connection
from backend.semantic.filters import FilterBuilder, MetricType
from backend.semantic.calculations import safe_ratio
from . import config as health_config


def _build_promotions(year: int) -> List[Dict[str, Any]]:
    """从配置构建大促列表（支持按年份配置，无配置则回退到2025年模板）"""
    periods = health_config.PROMOTION_PERIODS.get(year)
    if not periods:
        periods = health_config.PROMOTION_PERIODS.get(2025, [])
    promotions = []
    for p in periods:
        promotions.append({
            "name": p["name"],
            "start_date": f"{year}-{p['start_date']}",
            "end_date": f"{year}-{p['end_date']}",
            "year": year,
        })
    return promotions


def get_promotion_calendar(year: int = 2025,
                           exclude_channels: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    大促日历对比（简化版）
    """
    conn = get_connection()
    try:
        year_promos = _build_promotions(year)
        promotions_result = []
        total_promo_gsv = 0.0
        total_promo_users = 0

        last_daily_end: Optional[str] = None
        for promo in year_promos:
            # 大促期间
            fb_promo = FilterBuilder()
            fb_promo.with_metric_type(MetricType.GSV)
            fb_promo.with_time_range(promo["start_date"], promo["end_date"])
            if exclude_channels:
                fb_promo.with_exclude_channels(exclude_channels)
            where_promo, params_promo = fb_promo.build()

            # 日常期间（大促前30天）
            daily_start = (datetime.strptime(promo["start_date"], "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
            daily_end = (datetime.strptime(promo["start_date"], "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")

            # ── P2-8: 大促日常期重叠检测 ──
            if last_daily_end is not None:
                last_end_dt = datetime.strptime(last_daily_end, "%Y-%m-%d")
                start_dt = datetime.strptime(daily_start, "%Y-%m-%d")
                if start_dt <= last_end_dt:
                    # 与前一个大促日常期重叠，调整为紧接着的日期
                    new_start_dt = last_end_dt + timedelta(days=1)
                    daily_start = new_start_dt.strftime("%Y-%m-%d")
                    # 如果调整后的开始日晚于结束日，则日常期无效（间隔过近）
                    if daily_start > daily_end:
                        daily_start = daily_end

            last_daily_end = daily_end

            fb_daily = FilterBuilder()
            fb_daily.with_metric_type(MetricType.GSV)
            fb_daily.with_time_range(daily_start, daily_end)
            if exclude_channels:
                fb_daily.with_exclude_channels(exclude_channels)
            where_daily, params_daily = fb_daily.build()

            # 老客定义（大促前已有购买）—— 统一使用大促开始日作为cutoff
            cutoff = promo["start_date"]

            promo_row = conn.execute(f"""
                SELECT
                    COUNT(DISTINCT o.user_id),
                    SUM(o.actual_amount)
                FROM orders o
                JOIN (SELECT DISTINCT user_id, first_pay_date FROM user_first_purchase) u
                    ON o.user_id = u.user_id
                WHERE {where_promo}
                  AND u.first_pay_date <= ?::DATE
            """, params_promo + [cutoff]).fetchone()

            daily_row = conn.execute(f"""
                SELECT
                    COUNT(DISTINCT o.user_id),
                    SUM(o.actual_amount)
                FROM orders o
                JOIN (SELECT DISTINCT user_id, first_pay_date FROM user_first_purchase) u
                    ON o.user_id = u.user_id
                WHERE {where_daily}
                  AND u.first_pay_date <= ?::DATE
            """, params_daily + [cutoff]).fetchone()

            promo_users = int(promo_row[0]) if promo_row[0] else 0
            promo_gsv = float(promo_row[1]) if promo_row[1] else 0.0
            daily_users = int(daily_row[0]) if daily_row[0] else 0
            daily_gsv = float(daily_row[1]) if daily_row[1] else 0.0

            total_promo_gsv += promo_gsv
            total_promo_users += promo_users

            promotions_result.append({
                "promotion": promo,
                "promo_old_customer_count": promo_users,
                "promo_old_customer_gsv": round(promo_gsv, 2),
                "promo_old_customer_aus": round(safe_ratio(promo_gsv, promo_users, 0.0), 2),
                "daily_old_customer_count": daily_users,
                "daily_old_customer_gsv": round(daily_gsv, 2),
                "daily_old_customer_aus": round(safe_ratio(daily_gsv, daily_users, 0.0), 2),
                "gsv_lift": round(safe_ratio(promo_gsv - daily_gsv, daily_gsv, 0.0), 4) if daily_gsv > 0 else None,
            })

        # 年度汇总
        fb_year = FilterBuilder()
        fb_year.with_metric_type(MetricType.GSV)
        fb_year.with_time_range(f"{year}-01-01", f"{year}-12-31")
        if exclude_channels:
            fb_year.with_exclude_channels(exclude_channels)
        where_year, params_year = fb_year.build()

        year_row = conn.execute(f"""
            SELECT SUM(o.actual_amount), COUNT(DISTINCT o.user_id)
            FROM orders o
            JOIN (SELECT DISTINCT user_id, first_pay_date FROM user_first_purchase) u
                ON o.user_id = u.user_id
            WHERE {where_year}
              AND u.first_pay_date <= ?::DATE
        """, params_year + [f"{year}-01-01"]).fetchone()

        year_gsv = float(year_row[0]) if year_row[0] else 0.0
        year_users = int(year_row[1]) if year_row[1] else 0

        dependency = safe_ratio(total_promo_gsv, year_gsv, 0.0)

        return {
            "analysis_year": year,
            "promotions": promotions_result,
            "annual_promo_gsv_ratio": round(dependency, 4),
            "annual_promo_user_ratio": round(safe_ratio(total_promo_users, year_users, 0.0), 4),
            "promo_dependency_score": round(dependency, 4),
            "dependency_level": "high" if dependency > 0.6 else "medium" if dependency > 0.4 else "low",
            "yearly_trend": [],
        }

    finally:
        pass
