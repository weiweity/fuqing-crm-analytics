"""
芙清 CRM 客户分析系统 - 资产分析服务
Week 3 资产趋势（用订单模拟）

接入语义层: 使用 semantic/segments.py 和 semantic/filters.py 作为唯一真实数据源。
"""

import pandas as pd
from typing import Dict, Any, List
from backend.db.connection import get_connection
from backend.semantic.segments import get_registry
from backend.semantic.filters import OrderFilters


def get_asset_summary(date: str) -> Dict[str, Any]:
    """
    获取资产汇总（当前时间点）
    用订单 GMV 模拟用户价值资产

    Returns:
        {
            "date": str,
            "total_users": int,
            "total_gmv": float,
            "avg_gmv_per_user": float,
            "by_segment": {
                "1": {"name": "重要价值客户", "user_count": int, "gmv": float, "avg_gmv": float},
                ...
            }
        }
    """
    conn = get_connection()

    try:
        # 用 user_rfm 获取各象限用户数，用 orders 汇总 GMV
        sql = f"""
        WITH user_segment AS (
            -- 获取用户在特定日期的象限
            SELECT
                r.user_id,
                r.segment_id,
                r.monetary,
                r.frequency
            FROM user_rfm r
            WHERE r.analysis_date = DATE(?)
              AND r.metric_type = 'GMV'
              AND r.lookback_days = 90
        ),
        segment_summary AS (
            SELECT
                COALESCE(segment_id, 9) AS segment_id,
                COUNT(DISTINCT user_id) AS user_count,
                SUM(monetary) AS segment_gmv,
                AVG(monetary) AS avg_gmv
            FROM user_segment
            GROUP BY segment_id
        )
        SELECT
            segment_id,
            MAX(user_count) AS user_count,
            MAX(segment_gmv) AS segment_gmv,
            MAX(avg_gmv) AS avg_gmv
        FROM segment_summary
        GROUP BY segment_id
        ORDER BY segment_id
        """

        df = conn.execute(sql, [date]).fetchdf()

        by_segment = {}
        total_users = 0
        total_gmv = 0.0

        registry = get_registry()
        for _, row in df.iterrows():
            seg_id = int(row["segment_id"])
            user_count = int(row["user_count"])
            gmv = float(row["segment_gmv"]) if row["segment_gmv"] else 0.0
            avg_gmv = float(row["avg_gmv"]) if row["avg_gmv"] else 0.0

            seg_def = registry.get(seg_id)
            seg_name = seg_def.name_cn if seg_def else "其他"

            by_segment[str(seg_id)] = {
                "name": seg_name,
                "user_count": user_count,
                "gmv": round(gmv, 2),
                "avg_gmv": round(avg_gmv, 2)
            }
            total_users += user_count
            total_gmv += gmv

        return {
            "date": date,
            "total_users": total_users,
            "total_gmv": round(total_gmv, 2),
            "avg_gmv_per_user": round(total_gmv / total_users, 2) if total_users > 0 else 0,
            "by_segment": by_segment
        }
    finally:
        conn.close()


def get_asset_trend(
    start_date: str,
    end_date: str,
    granularity: str = "month"
) -> Dict[str, Any]:
    """
    获取资产趋势（多月/周）

    Args:
        start_date: 开始日期
        end_date: 结束日期
        granularity: 'month' 或 'week'

    Returns:
        {
            "time_points": ["2025-01", "2025-02", ...],
            "segments": [{"id": 1, "name": "重要价值客户", ...}, ...],
            "gmv_trend": {"1": [1000, 2000, ...], ...},
            "user_trend": {"1": [10, 20, ...], ...}
        }
    """
    conn = get_connection()

    try:
        if granularity == "month":
            date_trunc = "year || '-' || LPAD(month::VARCHAR, 2, '0')"
            date_group = "year, month"
        else:
            date_trunc = "STRFTIME(pay_time, '%Y-W%W')"
            date_group = "STRFTIME(pay_time, '%Y-W%W')"

        # 使用语义层构建过滤条件
        valid_sql, _ = OrderFilters.valid_order()

        sql = f"""
        WITH period_orders AS (
            SELECT
                o.user_id,
                o.pay_time,
                o.actual_amount,
                o.year,
                o.month,
                {date_trunc} AS period,
                r.segment_id
            FROM orders o
            LEFT JOIN user_rfm r
                ON o.user_id = r.user_id
                AND r.analysis_date = DATE(?)
                AND r.metric_type = 'GMV'
                AND r.lookback_days = 90
            WHERE o.pay_time >= ?
              AND o.pay_time <= ?
              AND {valid_sql}
        ),
        segment_trend AS (
            SELECT
                period,
                COALESCE(segment_id, 9) AS segment_id,
                COUNT(DISTINCT user_id) AS user_count,
                SUM(actual_amount) AS gmv
            FROM period_orders
            GROUP BY period, segment_id
        )
        SELECT
            period,
            segment_id,
            user_count,
            gmv
        FROM segment_trend
        ORDER BY period, segment_id
        """

        df = conn.execute(sql, [end_date, start_date, f"{end_date} 23:59:59"]).fetchdf()

        if df.empty:
            registry = get_registry()
            all_segs = registry.list_all()
            return {
                "time_points": [],
                "segments": [{"id": s.segment_id, "name": s.name_cn} for s in all_segs],
                "gmv_trend": {str(s.segment_id): [] for s in all_segs},
                "user_trend": {str(s.segment_id): [] for s in all_segs}
            }

        registry = get_registry()
        all_segs = registry.list_all()
        time_points = sorted(df["period"].unique().tolist())
        segments = [{"id": s.segment_id, "name": s.name_cn} for s in all_segs]

        gmv_trend = {str(s.segment_id): [] for s in all_segs}
        user_trend = {str(s.segment_id): [] for s in all_segs}

        for period in time_points:
            period_df = df[df["period"] == period]
            for _, row in period_df.iterrows():
                sid = str(int(row["segment_id"]))
                if sid in gmv_trend:
                    gmv_trend[sid].append(round(float(row["gmv"]), 2))
                    user_trend[sid].append(int(row["user_count"]))

        # 补齐所有象限（确保所有segment_id都有条目）
        for s in all_segs:
            sid_str = str(s.segment_id)
            if sid_str not in gmv_trend:
                gmv_trend[sid_str] = []
            if sid_str not in user_trend:
                user_trend[sid_str] = []

        return {
            "time_points": time_points,
            "segments": segments,
            "gmv_trend": gmv_trend,
            "user_trend": user_trend
        }
    finally:
        conn.close()