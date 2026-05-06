"""
访客数据服务 - 提供会员入会率及入会趋势查询
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from backend.db.connection import get_connection
from backend.semantic.calculations import yoy_absolute, safe_ratio


def get_visitor_summary(start_date: str, end_date: str) -> Dict[str, Any]:
    """
    获取指定日期范围内的访客汇总数据
    返回：访客数、新增会员数、入会率 + 同比
    """
    conn = get_connection()
    try:
        # 当期
        result = conn.execute("""
            SELECT
                COALESCE(SUM(visitors), 0) as total_visitors,
                COALESCE(SUM(new_members), 0) as total_new_members,
                CASE WHEN SUM(visitors) > 0
                     THEN ROUND(SUM(new_members)::DOUBLE / SUM(visitors)::DOUBLE, 6)
                     ELSE 0
                END as member_join_rate
            FROM daily_visitors
            WHERE date >= ?::DATE AND date <= ?::DATE
        """, [start_date, end_date]).fetchone()

        total_visitors = int(result[0]) if result[0] else 0
        total_new_members = int(result[1]) if result[1] else 0
        member_join_rate = float(result[2]) * 100 if result[2] else 0.0

        # 同比：去年同期
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        ly_start = (start_dt - timedelta(days=365)).strftime("%Y-%m-%d")
        ly_end = (end_dt - timedelta(days=365)).strftime("%Y-%m-%d")

        ly_result = conn.execute("""
            SELECT
                COALESCE(SUM(visitors), 0) as total_visitors,
                COALESCE(SUM(new_members), 0) as total_new_members,
                CASE WHEN SUM(visitors) > 0
                     THEN ROUND(SUM(new_members)::DOUBLE / SUM(visitors)::DOUBLE, 6)
                     ELSE 0
                END as member_join_rate
            FROM daily_visitors
            WHERE date >= ?::DATE AND date <= ?::DATE
        """, [ly_start, ly_end]).fetchone()

        ly_visitors = int(ly_result[0]) if ly_result[0] else 0
        ly_new_members = int(ly_result[1]) if ly_result[1] else 0
        ly_member_join_rate = float(ly_result[2]) * 100 if ly_result[2] else 0.0

        # 入会率同比（百分点差）
        member_join_rate_yoy = (member_join_rate - ly_member_join_rate) if ly_member_join_rate is not None else None

        # 访客数同比（百分比变化）
        visitors_yoy = yoy_absolute(total_visitors, ly_visitors)
        new_members_yoy = yoy_absolute(total_new_members, ly_new_members)

        return {
            "start_date": start_date,
            "end_date": end_date,
            "visitors": total_visitors,
            "new_members": total_new_members,
            "member_join_rate": member_join_rate,
            "ly_visitors": ly_visitors,
            "ly_new_members": ly_new_members,
            "ly_member_join_rate": ly_member_join_rate,
            "visitors_yoy": visitors_yoy,
            "new_members_yoy": new_members_yoy,
            "member_join_rate_yoy": member_join_rate_yoy,
        }
    finally:
        conn.close()


def get_visitor_daily_trend(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """
    获取每日访客/入会率趋势（含去年同期）
    返回按日期排序的列表
    """
    conn = get_connection()
    try:
        # 获取当期数据
        rows = conn.execute("""
            SELECT
                date,
                visitors,
                new_members,
                member_join_rate
            FROM daily_visitors
            WHERE date >= ?::DATE AND date <= ?::DATE
            ORDER BY date
        """, [start_date, end_date]).fetchall()

        # 计算去年同期日期范围
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        ly_start = (start_dt - timedelta(days=365)).strftime("%Y-%m-%d")
        ly_end = (end_dt - timedelta(days=365)).strftime("%Y-%m-%d")

        # 获取去年同期数据，按日期映射
        ly_rows = conn.execute("""
            SELECT
                date,
                visitors,
                new_members,
                member_join_rate
            FROM daily_visitors
            WHERE date >= ?::DATE AND date <= ?::DATE
            ORDER BY date
        """, [ly_start, ly_end]).fetchall()

        ly_map = {row[0]: row for row in ly_rows}

        result = []
        for row in rows:
            date_val = row[0]
            visitors = int(row[1]) if row[1] else 0
            new_members = int(row[2]) if row[2] else 0
            rate = float(row[3]) if row[3] else 0.0

            # 找去年同期同一天
            ly_date = (datetime.strptime(str(date_val), "%Y-%m-%d") - timedelta(days=365)).date()
            ly_row = ly_map.get(ly_date)

            ly_visitors = int(ly_row[1]) if ly_row else 0
            ly_new_members = int(ly_row[2]) if ly_row else 0
            ly_rate = float(ly_row[3]) if ly_row else 0.0

            result.append({
                "date": str(date_val),
                "visitors": visitors,
                "new_members": new_members,
                "member_join_rate": round(rate * 100, 4),  # 返回百分比数值（如 2.35）
                "ly_visitors": ly_visitors,
                "ly_new_members": ly_new_members,
                "ly_member_join_rate": round(ly_rate * 100, 4),
            })

        return result
    finally:
        conn.close()
