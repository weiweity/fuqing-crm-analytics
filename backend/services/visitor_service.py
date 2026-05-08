"""
访客数据服务 - 提供会员入会率及入会趋势查询
"""

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import Dict, Any, List, Optional, Tuple
from backend.db.connection import get_connection
from backend.semantic.calculations import yoy_absolute, safe_ratio


# ── 公共 SQL 模板 ──────────────────────────────────────────────
_VISITOR_PERIOD_SQL = """
    SELECT
        COALESCE(SUM(visitors), 0) as total_visitors,
        COALESCE(SUM(new_members), 0) as total_new_members,
        CASE WHEN SUM(visitors) > 0
             THEN ROUND(SUM(new_members)::DOUBLE / SUM(visitors)::DOUBLE, 6)
             ELSE 0
        END as member_join_rate
    FROM daily_visitors
    WHERE date >= ?::DATE AND date <= ?::DATE
"""


def _query_visitor_period(conn, start: str, end: str) -> Tuple[int, int, float]:
    """查询指定周期的访客汇总，返回 (visitors, new_members, join_rate%)"""
    row = conn.execute(_VISITOR_PERIOD_SQL, [start, end]).fetchone()
    visitors = int(row[0]) if row[0] else 0
    new_members = int(row[1]) if row[1] else 0
    join_rate = float(row[2]) * 100 if row[2] else 0.0
    return visitors, new_members, join_rate


def _resolve_compare_range(start_dt: datetime, end_dt: datetime,
                           compare_start_date: Optional[str],
                           compare_end_date: Optional[str]) -> Tuple[str, str]:
    """解析对比期日期范围：自定义覆盖 或 Y-1 自动推算"""
    if compare_start_date and compare_end_date:
        return compare_start_date, compare_end_date
    comp_start = (start_dt - relativedelta(years=1)).strftime("%Y-%m-%d")
    comp_end = (end_dt - relativedelta(years=1)).strftime("%Y-%m-%d")
    return comp_start, comp_end


def get_visitor_summary(start_date: str, end_date: str,
                        compare_start_date: Optional[str] = None,
                        compare_end_date: Optional[str] = None) -> Dict[str, Any]:
    """
    获取指定日期范围内的访客汇总数据
    返回：访客数、新增会员数、入会率 + 同比 + 环比
    compare_start_date/compare_end_date: 可选，自定义对比期日期（覆盖 Y-1 推算）
    """
    conn = get_connection()
    try:
        # ── 当期 ──
        total_visitors, total_new_members, member_join_rate = \
            _query_visitor_period(conn, start_date, end_date)

        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        # ── 同比（comp = 对比期） ──
        comp_start, comp_end = _resolve_compare_range(
            start_dt, end_dt, compare_start_date, compare_end_date)
        comp_visitors, comp_new_members, comp_join_rate = \
            _query_visitor_period(conn, comp_start, comp_end)

        # 入会率同比（百分点差）
        comp_rate_diff = member_join_rate - comp_join_rate
        # 访客数/新增会员同比（百分比变化）
        visitors_yoy = yoy_absolute(total_visitors, comp_visitors)
        new_members_yoy = yoy_absolute(total_new_members, comp_new_members)

        # ── 环比（MoM）：前一个等长周期 ──
        period_days = (end_dt - start_dt).days + 1
        mom_end_dt = start_dt - timedelta(days=1)
        mom_start_dt = mom_end_dt - timedelta(days=period_days - 1)
        mom_visitors, mom_new_members, mom_join_rate = \
            _query_visitor_period(conn,
                                  mom_start_dt.strftime("%Y-%m-%d"),
                                  mom_end_dt.strftime("%Y-%m-%d"))

        visitors_mom = yoy_absolute(total_visitors, mom_visitors)
        new_members_mom = yoy_absolute(total_new_members, mom_new_members)
        member_join_rate_mom = member_join_rate - mom_join_rate

        return {
            "start_date": start_date,
            "end_date": end_date,
            "visitors": total_visitors,
            "new_members": total_new_members,
            "member_join_rate": member_join_rate,
            # 对比期（同比或自定义）
            "ly_visitors": comp_visitors,
            "ly_new_members": comp_new_members,
            "ly_member_join_rate": comp_join_rate,
            "visitors_yoy": visitors_yoy,
            "new_members_yoy": new_members_yoy,
            "member_join_rate_yoy": comp_rate_diff,
            # 环比
            "visitors_mom": visitors_mom,
            "new_members_mom": new_members_mom,
            "member_join_rate_mom": member_join_rate_mom,
        }
    finally:
        conn.close()


def get_visitor_daily_trend(start_date: str, end_date: str,
                            compare_start_date: Optional[str] = None,
                            compare_end_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    获取每日访客/入会率趋势（含对比期）
    返回按日期排序的列表
    compare_start_date/compare_end_date: 可选，自定义对比期日期（覆盖 Y-1 推算）
    """
    conn = get_connection()
    try:
        # 获取当期数据
        rows = conn.execute("""
            SELECT date, visitors, new_members, member_join_rate
            FROM daily_visitors
            WHERE date >= ?::DATE AND date <= ?::DATE
            ORDER BY date
        """, [start_date, end_date]).fetchall()

        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        # 解析对比期范围
        comp_start, comp_end = _resolve_compare_range(
            start_dt, end_dt, compare_start_date, compare_end_date)

        # 获取对比期数据
        comp_rows = conn.execute("""
            SELECT date, visitors, new_members, member_join_rate
            FROM daily_visitors
            WHERE date >= ?::DATE AND date <= ?::DATE
            ORDER BY date
        """, [comp_start, comp_end]).fetchall()
        comp_map = {row[0]: row for row in comp_rows}

        # 循环前决定日期匹配策略，避免逐行判断
        is_custom = bool(compare_start_date and compare_end_date)
        if is_custom:
            comp_offset = (datetime.strptime(comp_start, "%Y-%m-%d").date()
                           - start_dt.date()).days

        result = []
        for row in rows:
            date_val = row[0]
            visitors = int(row[1]) if row[1] else 0
            new_members = int(row[2]) if row[2] else 0
            rate = float(row[3]) if row[3] else 0.0

            # 按策略找对比期对应天
            if is_custom:
                comp_date = (datetime.strptime(str(date_val), "%Y-%m-%d")
                             + timedelta(days=comp_offset)).date()
            else:
                comp_date = (datetime.strptime(str(date_val), "%Y-%m-%d")
                             - relativedelta(years=1)).date()
            comp_row = comp_map.get(comp_date)

            result.append({
                "date": str(date_val),
                "visitors": visitors,
                "new_members": new_members,
                "member_join_rate": round(rate * 100, 4),
                "ly_visitors": int(comp_row[1]) if comp_row else 0,
                "ly_new_members": int(comp_row[2]) if comp_row else 0,
                "ly_member_join_rate": round(float(comp_row[3]) * 100, 4) if comp_row else 0.0,
            })

        return result
    finally:
        conn.close()
