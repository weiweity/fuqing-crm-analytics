"""
芙清 CRM 客户分析系统 - 核心指标计算服务 v3
支持 GMV/GSV 双维度，统一引用语义层
"""

import duckdb
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import Dict, Any, Optional, List, Tuple
from backend.config import MEMBER_BASE_DATE
from backend.semantic.filters import OrderFilters, FilterBuilder, MetricType
from backend.semantic.time import PeriodBuilder
from backend.semantic.calculations import yoy_absolute, yoy_ratio, mom_absolute, mom_ratio, safe_ratio
from backend.semantic.channels import UI_TO_DB, DB_TO_UI, CHANNEL_ORDER
from backend.db.connection import get_connection

def _get_conn():
    """连接上下文管理器（确保连接始终关闭）"""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()





def _expand_channel(ch: Optional[str]) -> List[str]:
    """将UI渠道名展开为实际DB渠道名列表（支持组合渠道如'纯派样'）"""
    if not ch or ch == "全店":
        return []
    if ch == "纯派样":
        return ["U先派样", "百补派样"]
    return [UI_TO_DB.get(ch, ch)]


def calculate_metrics(start_date: str, end_date: str, metric_type: str = "GMV",
                      channel: Optional[str] = None,
                      exclude_channels: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    计算核心指标
    metric_type: "GMV" 或 "GSV"
    channel: 可选，单渠道过滤（UI渠道名）
    exclude_channels: 可选，排除渠道列表
    """
    conn = get_connection()
    try:
        fb = FilterBuilder()
        fb.with_metric_type(MetricType(metric_type))
        fb.with_time_range(start_date, end_date)
        if channel and channel != "全店":
            fb.with_channels([channel])
        if exclude_channels:
            fb.with_exclude_channels(exclude_channels)
        where_sql, params = fb.build()

        amount_expr = fb.build_amount_expr()
        count_expr = fb.build_count_expr()

        result = conn.execute(f"""
            SELECT
                {amount_expr} as total_amount,
                {count_expr} as order_count,
                AVG(actual_amount) as avg_order_value
            FROM orders
            WHERE {where_sql}
        """, params).fetchone()

        return {
            "amount": float(result[0]) if result[0] else 0,
            "order_count": int(result[1]) if result[1] else 0,
            "avg_order_value": float(result[2]) if result[2] else 0
        }
    finally:
        conn.close()


def calculate_new_old_users(start_date: str, end_date: str,
                             channel: Optional[str] = None,
                             exclude_channels: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    计算新老客 - JOIN user_first_purchase 动态口径版本。

    口径：用户选择 T1~T2，cutoff = T1-1天
    - 新客：窗口内有购买 AND first_pay_date > cutoff
    - 老客：窗口内有购买 AND first_pay_date <= cutoff
    channel: 可选，单渠道过滤（UI渠道名）
    exclude_channels: 可选，排除渠道列表
    """
    from datetime import date, timedelta

    conn = get_connection()
    try:
        start_dt_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        cutoff_date = (start_dt_obj - timedelta(days=1)).strftime("%Y-%m-%d")

        time_sql, time_params = OrderFilters.pay_time_between_dates(start_date, end_date)
        valid_sql, _ = OrderFilters.valid_order()

        ch_sql = ""
        ch_params = []
        db_channels = _expand_channel(channel)
        if len(db_channels) == 1:
            ch_sql = "AND channel = ?"
            ch_params = [db_channels[0]]
        elif len(db_channels) > 1:
            placeholders = ",".join(["?"] * len(db_channels))
            ch_sql = f"AND channel IN ({placeholders})"
            ch_params = db_channels

        if exclude_channels:
            ex_sql, ex_params = OrderFilters.channel_not_in(exclude_channels)
            ch_sql += f" AND {ex_sql}"
            ch_params.extend(ex_params)
        else:
            ex_sql = ""
            ex_params = []

        result = conn.execute(f"""
            WITH period_users AS (
                SELECT
                    o.user_id,
                    SUM(o.actual_amount) as period_amount
                FROM orders o
                JOIN user_first_purchase u ON o.user_id = u.user_id
                WHERE {time_sql}
                  AND {valid_sql}
                  {ch_sql}
                GROUP BY o.user_id
            ),
            enriched AS (
                SELECT
                    p.user_id,
                    p.period_amount,
                    CASE WHEN u.first_pay_date > ?::DATE THEN 1 ELSE 0 END AS is_new
                FROM period_users p
                JOIN user_first_purchase u ON p.user_id = u.user_id
            )
            SELECT
                COUNT(DISTINCT CASE WHEN is_new = 1 THEN user_id END) AS new_users,
                COUNT(DISTINCT CASE WHEN is_new = 0 THEN user_id END) AS old_users,
                COALESCE(SUM(CASE WHEN is_new = 1 THEN period_amount ELSE 0 END), 0) AS new_user_amount,
                COALESCE(SUM(CASE WHEN is_new = 0 THEN period_amount ELSE 0 END), 0) AS old_user_amount
            FROM enriched
        """, time_params + ch_params + [cutoff_date]).fetchone()

        return {
            "new_user_count": int(result[0]) if result[0] else 0,
            "old_user_count": int(result[1]) if result[1] else 0,
            "new_user_amount": float(result[2]) if result[2] else 0.0,
            "old_user_amount": float(result[3]) if result[3] else 0.0,
        }
    finally:
        conn.close()


def calculate_member_metrics(start_date: str, end_date: str, metric_type: str = "GMV",
                              channel: Optional[str] = None,
                              exclude_channels: Optional[List[str]] = None) -> Dict[str, Any]:
    """计算会员指标（参数化查询）"""
    conn = get_connection()
    try:
        fb = FilterBuilder()
        fb.with_metric_type(MetricType(metric_type))
        fb.with_time_range(start_date, end_date)
        fb.with_member_only(True)
        if channel and channel != "全店":
            fb.with_channels([channel])
        if exclude_channels:
            fb.with_exclude_channels(exclude_channels)
        where_sql, params = fb.build()

        amount_expr = fb.build_amount_expr()
        count_expr = fb.build_count_expr()

        result = conn.execute(f"""
            SELECT
                COUNT(DISTINCT user_id) as member_count,
                {amount_expr} as member_amount,
                {count_expr} as member_order_count
            FROM orders
            WHERE {where_sql}
        """, params).fetchone()

        return {
            "member_count": int(result[0]) if result[0] else 0,
            "member_amount": float(result[1]) if result[1] else 0,
            "member_order_count": int(result[2]) if result[2] else 0
        }
    finally:
        conn.close()


def get_overview_metrics(start_date: str, end_date: str, metric_type: str = "GMV",
                        channel: Optional[str] = None,
                        exclude_channels: Optional[List[str]] = None,
                        compare_start_date: Optional[str] = None,
                        compare_end_date: Optional[str] = None) -> Dict[str, Any]:
    """
    获取核心指标概览
    metric_type: "GMV" 或 "GSV"
    channel: 可选，单渠道过滤（UI渠道名）
    exclude_channels: 可选，排除渠道列表
    compare_start_date/compare_end_date: 可选，自定义对比期日期（覆盖 Y-1 推算）
    """
    current = calculate_metrics(start_date, end_date, metric_type, channel, exclude_channels)
    new_old = calculate_new_old_users(start_date, end_date, channel, exclude_channels)
    member = calculate_member_metrics(start_date, end_date, metric_type, channel, exclude_channels)

    # 环比
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    period_days = (end_dt - start_dt).days + 1

    prev_start = (start_dt - timedelta(days=period_days)).strftime("%Y-%m-%d")
    prev_end = (start_dt - timedelta(days=1)).strftime("%Y-%m-%d")
    prev = calculate_metrics(prev_start, prev_end, metric_type, channel, exclude_channels)
    prev_new_old = calculate_new_old_users(prev_start, prev_end, channel, exclude_channels)
    prev_member = calculate_member_metrics(prev_start, prev_end, metric_type, channel, exclude_channels)

    mom_amount = (mom_absolute(current['amount'], prev['amount']) or 0) * 100
    mom_orders = (mom_absolute(current['order_count'], prev['order_count']) or 0) * 100
    mom_old_amount = (mom_absolute(new_old['old_user_amount'], prev_new_old['old_user_amount']) or 0) * 100
    mom_new_amount = (mom_absolute(new_old['new_user_amount'], prev_new_old['new_user_amount']) or 0) * 100
    mom_member_amount = (mom_absolute(member['member_amount'], prev_member['member_amount']) or 0) * 100
    # 占比 MoM 百分点差
    curr_old_ratio = new_old['old_user_amount'] / current['amount'] * 100 if current['amount'] > 0 else 0
    curr_new_ratio = new_old['new_user_amount'] / current['amount'] * 100 if current['amount'] > 0 else 0
    curr_member_ratio = member['member_amount'] / current['amount'] * 100 if current['amount'] > 0 else 0
    prev_old_ratio = prev_new_old['old_user_amount'] / prev['amount'] * 100 if prev['amount'] > 0 else 0
    prev_new_ratio = prev_new_old['new_user_amount'] / prev['amount'] * 100 if prev['amount'] > 0 else 0
    prev_member_ratio = prev_member['member_amount'] / prev['amount'] * 100 if prev['amount'] > 0 else 0
    # FIX: mom_ratio 期望小数输入，curr/prev已经是百分比，需要除以100转换
    mom_old_ratio = mom_ratio(curr_old_ratio / 100, prev_old_ratio / 100) or 0
    mom_new_ratio = mom_ratio(curr_new_ratio / 100, prev_new_ratio / 100) or 0
    mom_member_ratio = mom_ratio(curr_member_ratio / 100, prev_member_ratio / 100) or 0

    # 会员溢价 = 会员AUS / 全店AUS（比值，不乘100）
    member_avg_order_value = member['member_amount'] / member['member_order_count'] if member['member_order_count'] > 0 else 0
    member_premium = member_avg_order_value / current['avg_order_value'] if current['avg_order_value'] > 0 else 0
    prev_member_avg = prev_member['member_amount'] / prev_member['member_order_count'] if prev_member['member_order_count'] > 0 else 0
    prev_member_premium = prev_member_avg / prev['avg_order_value'] if prev['avg_order_value'] > 0 else 0
    mom_member_premium = member_premium - prev_member_premium

    # 同比（支持自定义对比期覆盖 Y-1 推算）
    if compare_start_date and compare_end_date:
        last_year_start = compare_start_date
        last_year_end = compare_end_date
    else:
        last_year_start = (start_dt - relativedelta(years=1)).strftime("%Y-%m-%d")
        last_year_end = (end_dt - relativedelta(years=1)).strftime("%Y-%m-%d")
    last_year = calculate_metrics(last_year_start, last_year_end, metric_type, channel, exclude_channels)
    last_year_new_old = calculate_new_old_users(last_year_start, last_year_end, channel, exclude_channels)
    last_year_member = calculate_member_metrics(last_year_start, last_year_end, metric_type, channel, exclude_channels)

    yoy_amount = (yoy_absolute(current['amount'], last_year['amount']) or 0) * 100
    yoy_orders = (yoy_absolute(current['order_count'], last_year['order_count']) or 0) * 100
    yoy_old_amount = (yoy_absolute(new_old['old_user_amount'], last_year_new_old['old_user_amount']) or 0) * 100
    yoy_new_amount = (yoy_absolute(new_old['new_user_amount'], last_year_new_old['new_user_amount']) or 0) * 100
    yoy_member_amount = (yoy_absolute(member['member_amount'], last_year_member['member_amount']) or 0) * 100
    ly_old_ratio = last_year_new_old['old_user_amount'] / last_year['amount'] * 100 if last_year['amount'] > 0 else 0
    ly_new_ratio = last_year_new_old['new_user_amount'] / last_year['amount'] * 100 if last_year['amount'] > 0 else 0
    ly_member_ratio = last_year_member['member_amount'] / last_year['amount'] * 100 if last_year['amount'] > 0 else 0
    # FIX: yoy_ratio 期望小数输入，curr/ly已经是百分比，需要除以100转换
    yoy_old_ratio = yoy_ratio(curr_old_ratio / 100, ly_old_ratio / 100) or 0
    yoy_new_ratio = yoy_ratio(curr_new_ratio / 100, ly_new_ratio / 100) or 0
    yoy_member_ratio = yoy_ratio(curr_member_ratio / 100, ly_member_ratio / 100) or 0

    ly_member_avg = last_year_member['member_amount'] / last_year_member['member_order_count'] if last_year_member['member_order_count'] > 0 else 0
    ly_member_premium = ly_member_avg / last_year['avg_order_value'] if last_year['avg_order_value'] > 0 else 0
    # 会员溢价 YoY（比值跑 yoy_absolute 返回百分比变化率，再乘100）
    yoy_member_premium = (yoy_absolute(member_premium, ly_member_premium) or 0) * 100

    return {
        "metric_type": metric_type,
        "date_range": {"start": start_date, "end": end_date},
        "amount": round(current['amount'], 2),
        "order_count": current['order_count'],
        "avg_order_value": round(current['avg_order_value'], 2),
        "new_users": new_old['new_user_count'],
        "old_users": new_old['old_user_count'],
        "new_user_amount": round(new_old['new_user_amount'], 2),
        "old_user_amount": round(new_old['old_user_amount'], 2),
        "member_amount": round(member['member_amount'], 2),
        "member_count": member['member_count'],
        "member_order_count": member['member_order_count'],
        "old_user_ratio": round(curr_old_ratio, 2),
        "new_user_ratio": round(curr_new_ratio, 2),
        "member_ratio": round(curr_member_ratio, 2),
        "member_avg_order_value": round(member_avg_order_value, 2),
        "member_premium": round(member_premium, 2),
        "mom_change": {
            "amount_pct": round(mom_amount, 2),
            "order_count_pct": round(mom_orders, 2),
            "old_user_amount_pct": round(mom_old_amount, 2),
            "new_user_amount_pct": round(mom_new_amount, 2),
            "member_amount_pct": round(mom_member_amount, 2),
            "old_user_ratio_ppt": round(mom_old_ratio, 2),
            "new_user_ratio_ppt": round(mom_new_ratio, 2),
            "member_ratio_ppt": round(mom_member_ratio, 2),
            "member_premium_ppt": round(mom_member_premium, 2),
        },
        "yoy_change": {
            "amount_pct": round(yoy_amount, 2),
            "order_count_pct": round(yoy_orders, 2),
            "old_user_amount_pct": round(yoy_old_amount, 2),
            "new_user_amount_pct": round(yoy_new_amount, 2),
            "member_amount_pct": round(yoy_member_amount, 2),
            "old_user_ratio_ppt": round(yoy_old_ratio, 2),
            "new_user_ratio_ppt": round(yoy_new_ratio, 2),
            "member_ratio_ppt": round(yoy_member_ratio, 2),
            "member_premium_ppt": round(yoy_member_premium, 2),
        }
    }


def get_daily_trend(start_date: str, end_date: str, metric_type: str = "GMV",
                   channel: Optional[str] = None,
                   exclude_channels: Optional[List[str]] = None,
                   compare_start_date: Optional[str] = None,
                   compare_end_date: Optional[str] = None) -> Dict[str, Any]:
    """获取每日趋势（参数化查询）— 含对比期数据 + 会员占比。
    compare_start_date/compare_end_date: 可选，自定义对比期日期（覆盖 Y-1 推算）
    """
    conn = get_connection()
    try:
        fb = FilterBuilder()
        fb.with_metric_type(MetricType(metric_type))
        fb.with_time_range(start_date, end_date)
        if channel and channel != "全店":
            fb.with_channels([channel])
        if exclude_channels:
            fb.with_exclude_channels(exclude_channels)
        where_sql, params = fb.build()

        amount_expr = fb.build_amount_expr()

        result = conn.execute(f"""
            SELECT
                DATE(pay_time) as date,
                {amount_expr} as daily_amount,
                COUNT(DISTINCT CASE WHEN is_member = TRUE THEN order_id END) as member_orders,
                COUNT(DISTINCT order_id) as daily_orders
            FROM orders
            WHERE {where_sql}
            GROUP BY DATE(pay_time)
            ORDER BY date
        """, params).fetchall()

        # 去年同比数据（支持自定义对比期覆盖 Y-1 推算）
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        if compare_start_date and compare_end_date:
            ly_start = compare_start_date
            ly_end = compare_end_date
        else:
            ly_start = (start_dt - relativedelta(years=1)).strftime("%Y-%m-%d")
            ly_end = (end_dt - relativedelta(years=1)).strftime("%Y-%m-%d")

        fb_ly = FilterBuilder()
        fb_ly.with_metric_type(MetricType(metric_type))
        fb_ly.with_time_range(ly_start, ly_end)
        if channel and channel != "全店":
            fb_ly.with_channels([channel])
        if exclude_channels:
            fb_ly.with_exclude_channels(exclude_channels)
        where_ly, params_ly = fb_ly.build()
        amount_ly = fb_ly.build_amount_expr()

        result_ly = conn.execute(f"""
            SELECT
                DATE(pay_time) as date,
                {amount_ly} as daily_amount,
                COUNT(DISTINCT CASE WHEN is_member = TRUE THEN order_id END) as member_orders,
                COUNT(DISTINCT order_id) as daily_orders
            FROM orders
            WHERE {where_ly}
            GROUP BY DATE(pay_time)
            ORDER BY date
        """, params_ly).fetchall()

        # 今年会员占比（%）
        member_ratios = []
        for r in result:
            total = r[3] if r[3] else 0
            member = r[2] if r[2] else 0
            ratio = (member / total * 100) if total > 0 else 0
            member_ratios.append(round(ratio, 2))

        # 去年会员占比（%）
        ly_member_ratios = []
        for r in result_ly:
            total = r[3] if r[3] else 0
            member = r[2] if r[2] else 0
            ratio = (member / total * 100) if total > 0 else 0
            ly_member_ratios.append(round(ratio, 2))

        return {
            "metric_type": metric_type,
            "dates": [str(r[0]) for r in result],
            "amounts": [float(r[1]) for r in result],
            "member_ratios": member_ratios,
            "ly_amounts": [float(r[1]) for r in result_ly],
            "ly_member_ratios": ly_member_ratios,
        }
    finally:
        conn.close()

def get_product_metrics(start_date: str, end_date: str, limit: int = 20) -> Dict[str, Any]:
    """获取单品 metrics（按 GMV/GSV 排名，参数化查询）"""
    conn = get_connection()
    try:
        # 使用 FilterBuilder 构建统一过滤条件（默认 GMV）
        fb = FilterBuilder()
        fb.with_metric_type(MetricType.GMV)
        fb.with_time_range(start_date, end_date)
        where_sql, params = fb.build()

        result = conn.execute(f"""
            SELECT
                product_id,
                product_title,
                spu_category,
                spu_tier,
                COUNT(DISTINCT order_id) as order_count,
                COUNT(DISTINCT user_id) as user_count,
                SUM(actual_amount) as total_amount,
                AVG(actual_amount) as avg_amount
            FROM orders
            WHERE {where_sql}
            GROUP BY product_id, product_title, spu_category, spu_tier
            ORDER BY total_amount DESC
            LIMIT ?
        """, params + [limit]).fetchall()

        products = []
        for r in result:
            products.append({
                "product_id": r[0],
                "product_title": r[1],
                "category": r[2],
                "tier": r[3],
                "order_count": int(r[4]),
                "user_count": int(r[5]),
                "total_amount": float(r[6]),
                "avg_amount": float(r[7])
            })

        return {"products": products}
    finally:
        conn.close()


def get_audience_table(
    dimension: str = "channel",
    mode: str = "mtd",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    channels: Optional[List[str]] = None,
    metric_type: str = "GMV",
    member_only: bool = False,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    人群看板主表（JOIN 方案，实时查询）

    dimension: "channel" 或 "spu_tier"
    mode: "mtd"（默认）或 "free"
        - mtd:   自动计算当年MTD vs 去年MTD，cutoff = 上月末
        - free:  使用传入的 start_date/end_date 作为当年期，参考期自动为去年对应月
    channels: 渠道筛选列表，默认全渠道
    """
    from calendar import monthrange
    from datetime import date

    today = date.today()
    yesterday = today - timedelta(days=1)   # MTD 截止昨天（t-1），不含当天

    # ========================================
    # 动态日期计算（三年：2026/2025/2024 MTD）
    # ========================================
    if mode == "mtd":
        # 当年MTD（结束日期用 yesterday.day，避免含当天部分数据）
        cur_year = today.year
        cur_month = today.month
        _, last_day = monthrange(cur_year, cur_month)
        cur_start = f"{cur_year}-{cur_month:02d}-01"
        cur_end = f"{cur_year}-{cur_month:02d}-{min(yesterday.day, last_day):02d}"
        # cutoff = cur_start - 1天（老客判定：first_pay_date <= cutoff）
        # MTD模式下 cur_start=当月1号，所以 cutoff=上月末（等价）
        cutoff = (datetime(cur_year, cur_month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")

        # 去年MTD（2025 MTD）
        comp_year = cur_year - 1
        comp_start = f"{comp_year}-{cur_month:02d}-01"
        comp_end = f"{comp_year}-{cur_month:02d}-{min(yesterday.day, last_day):02d}"
        # comp_cutoff = 去年当月1号 - 1天
        comp_cutoff = (datetime(comp_year, cur_month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")

        # 前年MTD（2024 MTD，用于三年对比）
        prev2_year = cur_year - 2
        prev2_start = f"{prev2_year}-{cur_month:02d}-01"
        prev2_end = f"{prev2_year}-{cur_month:02d}-{min(yesterday.day, last_day):02d}"
        # prev2_cutoff = 前年当月1号 - 1天
        prev2_cutoff = (datetime(prev2_year, cur_month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        # free 模式：使用传入日期（支持三年对比：当年 + 去年 + 前年同期）
        if not start_date or not end_date:
            raise ValueError("free 模式需要传入 start_date 和 end_date")
        cur_start, cur_end = start_date, end_date
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        # 当年 cutoff = start_date - 1天（与 calculate_new_old_users 口径一致）
        cutoff = (start_dt - timedelta(days=1)).strftime("%Y-%m-%d")

        # 去年同月同期（year-1）
        ly_start = datetime(start_dt.year - 1, start_dt.month, start_dt.day)
        ly_end = datetime(end_dt.year - 1, end_dt.month, end_dt.day)
        comp_start = ly_start.strftime("%Y-%m-%d")
        comp_end = ly_end.strftime("%Y-%m-%d")
        # comp_cutoff = 去年 start_date - 1天
        comp_cutoff = (ly_start - timedelta(days=1)).strftime("%Y-%m-%d")

        # 前年同月同期（year-2）
        p2y_start = datetime(start_dt.year - 2, start_dt.month, start_dt.day)
        p2y_end = datetime(end_dt.year - 2, end_dt.month, end_dt.day)
        prev2_start = p2y_start.strftime("%Y-%m-%d")
        prev2_end = p2y_end.strftime("%Y-%m-%d")
        # prev2_cutoff = 前年 start_date - 1天
        prev2_cutoff = (p2y_start - timedelta(days=1)).strftime("%Y-%m-%d")

    cur_start_dt = f"{cur_start} 00:00:00"
    cur_end_dt = f"{cur_end} 23:59:59"
    comp_start_dt = f"{comp_start} 00:00:00"
    comp_end_dt = f"{comp_end} 23:59:59"
    prev2_start_dt = f"{prev2_start} 00:00:00" if prev2_start else None
    prev2_end_dt = f"{prev2_end} 23:59:59" if prev2_end else None

    # ========================================
    # SQL 片段（使用语义层）
    # ========================================
    def _build_whereClause(date_start: str, date_end: str, ch_filter: Optional[List[str]] = None, ex_channels: Optional[List[str]] = None) -> tuple:
        """返回 (condition_str, params) - 使用语义层 FilterBuilder"""
        fb = FilterBuilder()
        fb.with_metric_type(MetricType.GSV)  # 人群看板统一使用 GSV 口径
        fb.with_time_range(
            date_start[:10],  # 提取日期部分
            date_end[:10]
        )
        if ch_filter:
            # 支持单字符串或列表传入（兼容旧调用）
            channels_list = ch_filter if isinstance(ch_filter, list) else [ch_filter]
            fb.with_channels(channels_list)
        if ex_channels:
            fb.with_exclude_channels(ex_channels)
        return fb.build()

    def _run_period(conn, date_start: str, date_end: str, cutoff: str,
                   group_by: str, ch_filter: Optional[List[str]] = None,
                   include_total: bool = False,
                   mtype: str = "GMV",
                   member_only: bool = False,
                   ex_channels: Optional[List[str]] = None) -> List[Dict]:
        where_clause, params = _build_whereClause(date_start, date_end, ch_filter, ex_channels)
        # 滚动新老客：用 cutoff 参数（T1-1天）作为老客判定边界
        # cutoff 传入的是日期字符串如 "2025-12-31"，用于 pay_time <= cutoff
        full_params = params + [cutoff]
        # GSV/GMV 统一使用 actual_amount（与品类服务及全系统一致）
        amt_expr = "actual_amount"

        if group_by == "channel":
            group_expr = "channel"
        elif group_by == "spu_tier":
            group_expr = "COALESCE(spu_tier, '未知')"
        elif group_by == "spu_product_class":
            group_expr = "COALESCE(spu_product_class, '未知')"
        else:
            group_expr = "COALESCE(spu_product_subclass, '未知')"

        # 使用 GROUPING SETS ((dim_key), ()) 合并分组查询与合计行
        # GROUPING(dim_key)=1 表示合计行（superglobal），=0 表示分组行
        sql = f"""
        WITH
        base AS (
            SELECT *
            FROM orders
            WHERE {where_clause}
        ),
        old_customers AS (
            SELECT DISTINCT u.user_id
            FROM user_first_purchase u
            WHERE u.first_pay_date <= ?::DATE
        ),
        enriched AS (
            SELECT
                {group_expr} AS dim_key,
                o.user_id,
                {amt_expr} AS amount,
                o.is_member,
                CASE WHEN oc.user_id IS NOT NULL THEN 1 ELSE 0 END AS is_old
            FROM base o
            LEFT JOIN old_customers oc ON o.user_id = oc.user_id
            {"WHERE o.is_member = TRUE" if member_only else ""}
        ),
        grouped AS (
            SELECT
                dim_key,
                COUNT(DISTINCT user_id)                                              AS gsv_users,
                SUM(amount)                                                            AS gsv,
                SUM(amount) / NULLIF(COUNT(DISTINCT user_id), 0)                     AS aus,
                COUNT(DISTINCT CASE WHEN is_old = 1 THEN user_id END)                 AS old_users,
                SUM(amount * CASE WHEN is_old = 1 THEN 1 ELSE 0 END)                  AS old_gsv,
                SUM(amount * CASE WHEN is_old = 1 THEN 1 ELSE 0 END) /
                    NULLIF(COUNT(DISTINCT CASE WHEN is_old = 1 THEN user_id END), 0) AS old_aus,
                COUNT(DISTINCT CASE WHEN is_member = TRUE THEN user_id END)           AS member_users,
                SUM(amount * CASE WHEN is_member = TRUE THEN 1 ELSE 0 END)            AS member_gsv,
                SUM(amount * CASE WHEN is_member = TRUE THEN 1 ELSE 0 END) /
                    NULLIF(COUNT(DISTINCT CASE WHEN is_member = TRUE THEN user_id END), 0) AS member_aus,
                COUNT(DISTINCT CASE WHEN is_member = TRUE AND is_old = 1 THEN user_id END) AS member_old_users,
                SUM(amount * CASE WHEN is_member = TRUE AND is_old = 1 THEN 1 ELSE 0 END) AS member_old_gsv,
                GROUPING(dim_key) AS _grp
            FROM enriched
            GROUP BY GROUPING SETS ((dim_key), ())
        )
        SELECT
            CASE WHEN _grp = 1 THEN '__TOTAL__' ELSE dim_key END AS dim_key,
            gsv_users, gsv, aus,
            old_users, old_gsv, old_aus,
            member_users, member_gsv, member_aus,
            member_old_users, member_old_gsv,
            _grp
        FROM grouped
        {'ORDER BY _grp ASC, gsv DESC' if include_total else 'ORDER BY gsv DESC'}
        """
        raw = conn.execute(sql, full_params).fetchall()
        # 合计行排在最前
        if include_total:
            result = [row[:-1] for row in raw]  # 去掉末尾_grp辅助列
        else:
            result = raw

        return result

    conn = get_connection()
    try:
        # 渠道筛选
        ch_filter = channels if channels else None

        # 当年（含合计行）
        cur = _run_period(conn, cur_start_dt, cur_end_dt, cutoff,
                           dimension, ch_filter, include_total=True, mtype=metric_type,
                           member_only=member_only, ex_channels=exclude_channels)
        # 去年（含合计行，用于YoY计算）
        comp = _run_period(conn, comp_start_dt, comp_end_dt, comp_cutoff,
                           dimension, ch_filter, include_total=True, mtype=metric_type,
                           member_only=member_only, ex_channels=exclude_channels)
        # 前年（2024 MTD，仅 mode=mtd 时有数据）
        prev2 = _run_period(conn, prev2_start_dt, prev2_end_dt, prev2_cutoff,
                            dimension, ch_filter, include_total=True, mtype=metric_type,
                            member_only=member_only, ex_channels=exclude_channels) if prev2_start_dt else []
    finally:
        conn.close()

    # 转换为 dict，按 dim_key 索引（保留全部12列）
    def _n(v):
        """将 DuckDB 的 NULL (None) 转为 0"""
        return float(v) if v is not None else 0.0

    cur_map = {r[0]: r for r in cur}
    comp_map = {r[0]: r for r in comp}
    prev2_map = {r[0]: r for r in prev2} if prev2 else {}

    # 合并输出（合计行 __TOTAL__ 保持首位，其他按键值排序）
    all_keys = sorted(set(cur_map.keys()) | set(comp_map.keys()) | set(prev2_map.keys()))
    # 将 __TOTAL__ 移至最前
    if '__TOTAL__' in all_keys:
        all_keys.remove('__TOTAL__')
        all_keys = ['__TOTAL__'] + all_keys

    rows = []
    for key in all_keys:
        cr = cur_map.get(key, (0,) * 12)
        vr = comp_map.get(key, (0,) * 12)
        pr = prev2_map.get(key, (0,) * 12) if prev2_map else (0,) * 12
        _, gsv_users, gsv, aus, old_users, old_gsv, old_aus, \
            member_users, member_gsv, member_aus, member_old_users, member_old_gsv = cr
        _, comp_gsv_users, comp_gsv, comp_aus, comp_old_users, comp_old_gsv, comp_old_aus, \
            comp_member_users, comp_member_gsv, comp_member_aus, comp_member_old_users, comp_member_old_gsv = vr
        _, prev2_gsv_users, prev2_gsv, prev2_aus, prev2_old_users, prev2_old_gsv, prev2_old_aus, \
            prev2_member_users, prev2_member_gsv, prev2_member_aus, \
            prev2_member_old_users, prev2_member_old_gsv = pr

        new_users = max(0, gsv_users - old_users)
        new_gsv = max(0, gsv - old_gsv)
        new_aus = new_gsv / new_users if new_users > 0 else 0.0
        old_gsv_ratio = old_gsv / gsv if gsv > 0 else 0.0
        old_users_ratio = old_users / gsv_users if gsv_users > 0 else 0.0
        new_gsv_ratio = 1 - old_gsv_ratio
        new_users_ratio = 1 - old_users_ratio
        member_gsv_ratio = member_gsv / gsv if gsv > 0 else 0.0
        member_users_ratio = member_users / gsv_users if gsv_users > 0 else 0.0
        member_old_gsv_ratio = member_old_gsv / member_gsv if member_gsv > 0 else 0.0
        member_old_users_ratio = member_old_users / member_users if member_users > 0 else 0.0
        member_new_gsv = max(0, member_gsv - member_old_gsv)
        member_new_users = max(0, member_users - member_old_users)
        member_new_aus = member_new_gsv / member_new_users if member_new_users > 0 else 0.0
        member_new_gsv_ratio = 1 - member_old_gsv_ratio
        member_new_users_ratio = 1 - member_old_users_ratio

        # 对比期（2025年）
        comp_gsv_val = round(_n(comp_gsv), 2)
        comp_gsv_users_val = int(comp_gsv_users) if comp_gsv_users is not None else 0
        comp_old_users_val = int(comp_old_users) if comp_old_users is not None else 0
        comp_old_gsv_val = round(_n(comp_old_gsv), 2)
        comp_old_gsv_ratio_val = round(comp_old_gsv_val / comp_gsv_val if comp_gsv_val > 0 else 0.0, 4)
        comp_old_users_ratio_val = round(comp_old_users_val / comp_gsv_users_val if comp_gsv_users_val > 0 else 0.0, 4)
        comp_new_users_val = max(0, comp_gsv_users_val - comp_old_users_val)
        comp_new_gsv_val = max(0.0, comp_gsv_val - comp_old_gsv_val)
        comp_new_aus_val = comp_new_gsv_val / comp_new_users_val if comp_new_users_val > 0 else 0.0
        comp_new_gsv_ratio_val = 1 - comp_old_gsv_ratio_val
        comp_new_users_ratio_val = 1 - comp_old_users_ratio_val
        comp_member_gsv_ratio_val = round(_n(comp_member_gsv) / comp_gsv_val if comp_gsv_val > 0 else 0.0, 4)
        _cm_users = int(comp_member_users) if comp_member_users else 0
        comp_member_users_ratio_val = round(_cm_users / comp_gsv_users_val if comp_gsv_users_val > 0 else 0.0, 4)
        comp_member_old_users_val = int(comp_member_old_users) if comp_member_old_users is not None else 0
        comp_member_old_gsv_val = round(_n(comp_member_old_gsv), 2)
        comp_member_old_aus_val = comp_member_old_gsv_val / comp_member_old_users_val if comp_member_old_users_val > 0 else 0.0
        comp_member_old_gsv_ratio_val = round(comp_member_old_gsv_val / _n(comp_member_gsv) if _n(comp_member_gsv) > 0 else 0.0, 4)
        comp_member_old_users_ratio_val = round(
            comp_member_old_users_val / int(comp_member_users)
            if comp_member_users and int(comp_member_users) > 0 else 0.0, 4)
        comp_member_new_users_val = max(0, int(comp_member_users) - comp_member_old_users_val) if comp_member_users is not None else 0
        comp_member_new_gsv_val = max(0.0, _n(comp_member_gsv) - comp_member_old_gsv_val)
        comp_member_new_aus_val = comp_member_new_gsv_val / comp_member_new_users_val if comp_member_new_users_val > 0 else 0.0
        comp_member_new_gsv_ratio_val = 1 - comp_member_old_gsv_ratio_val
        comp_member_new_users_ratio_val = 1 - comp_member_old_users_ratio_val

        # 前年（2024年）
        prev2_gsv_val = round(_n(prev2_gsv), 2)
        prev2_gsv_users_val = int(prev2_gsv_users) if prev2_gsv_users is not None else 0
        prev2_old_users_val = int(prev2_old_users) if prev2_old_users is not None else 0
        prev2_old_gsv_val = round(_n(prev2_old_gsv), 2)
        prev2_old_gsv_ratio_val = round(prev2_old_gsv_val / prev2_gsv_val if prev2_gsv_val > 0 else 0.0, 4)
        prev2_old_users_ratio_val = round(prev2_old_users_val / prev2_gsv_users_val if prev2_gsv_users_val > 0 else 0.0, 4)
        prev2_new_users_val = max(0, prev2_gsv_users_val - prev2_old_users_val)
        prev2_new_gsv_val = max(0.0, prev2_gsv_val - prev2_old_gsv_val)
        prev2_new_aus_val = prev2_new_gsv_val / prev2_new_users_val if prev2_new_users_val > 0 else 0.0
        prev2_new_gsv_ratio_val = 1 - prev2_old_gsv_ratio_val
        prev2_new_users_ratio_val = 1 - prev2_old_users_ratio_val
        prev2_member_gsv_ratio_val = round(_n(prev2_member_gsv) / prev2_gsv_val if prev2_gsv_val > 0 else 0.0, 4)
        _p2m_users = int(prev2_member_users) if prev2_member_users else 0
        prev2_member_users_ratio_val = round(_p2m_users / prev2_gsv_users_val if prev2_gsv_users_val > 0 else 0.0, 4)
        prev2_member_old_users_val = int(prev2_member_old_users) if prev2_member_old_users is not None else 0
        prev2_member_old_gsv_val = round(_n(prev2_member_old_gsv), 2)
        prev2_member_old_aus_val = prev2_member_old_gsv_val / prev2_member_old_users_val if prev2_member_old_users_val > 0 else 0.0
        prev2_member_old_gsv_ratio_val = round(prev2_member_old_gsv_val / _n(prev2_member_gsv) if _n(prev2_member_gsv) > 0 else 0.0, 4)
        prev2_member_old_users_ratio_val = round(prev2_member_old_users_val / int(prev2_member_users) if prev2_member_users and int(prev2_member_users) > 0 else 0.0, 4)
        prev2_member_new_users_val = max(0, int(prev2_member_users) - prev2_member_old_users_val) if prev2_member_users is not None else 0
        prev2_member_new_gsv_val = max(0.0, _n(prev2_member_gsv) - prev2_member_old_gsv_val)
        prev2_member_new_aus_val = prev2_member_new_gsv_val / prev2_member_new_users_val if prev2_member_new_users_val > 0 else 0.0
        prev2_member_new_gsv_ratio_val = 1 - prev2_member_old_gsv_ratio_val
        prev2_member_new_users_ratio_val = 1 - prev2_member_old_users_ratio_val

        rows.append({
            "dimension": key,
            # 2026年（当年）
            "gsv_users": int(gsv_users),
            "gsv": round(_n(gsv), 2),
            "aus": round(_n(aus), 2),
            "old_users": int(old_users),
            "old_gsv": round(_n(old_gsv), 2),
            "old_aus": round(_n(old_aus), 2),
            "old_gsv_ratio": round(old_gsv_ratio, 4),
            "old_users_ratio": round(old_users_ratio, 4),
            "new_users": int(new_users),
            "new_gsv": round(new_gsv, 2),
            "new_aus": round(new_aus, 2),
            "new_gsv_ratio": round(new_gsv_ratio, 4),
            "new_users_ratio": round(new_users_ratio, 4),
            "member_users": int(member_users),
            "member_gsv": round(_n(member_gsv), 2),
            "member_aus": round(_n(member_aus), 2),
            "member_gsv_ratio": round(member_gsv_ratio, 4),
            "member_users_ratio": round(member_users_ratio, 4),
            "member_old_users": int(member_old_users),
            "member_old_gsv": round(_n(member_old_gsv), 2),
            "member_old_aus": round(_n(member_old_gsv) / member_old_users if member_old_users > 0 else 0.0, 2),
            "member_old_gsv_ratio": round(member_old_gsv_ratio, 4),
            "member_old_users_ratio": round(member_old_users_ratio, 4),
            "member_new_users": int(member_new_users),
            "member_new_gsv": round(member_new_gsv, 2),
            "member_new_aus": round(member_new_aus, 2),
            "member_new_gsv_ratio": round(member_new_gsv_ratio, 4),
            "member_new_users_ratio": round(member_new_users_ratio, 4),
            # 2025年（去年）
            "comp_gsv_users": comp_gsv_users_val,
            "comp_gsv": comp_gsv_val,
            "comp_aus": round(_n(comp_aus), 2),
            "comp_old_users": comp_old_users_val,
            "comp_old_gsv": comp_old_gsv_val,
            "comp_old_aus": round(_n(comp_old_aus), 2),
            "comp_old_gsv_ratio": comp_old_gsv_ratio_val,
            "comp_old_users_ratio": comp_old_users_ratio_val,
            "comp_new_users": comp_new_users_val,
            "comp_new_gsv": round(comp_new_gsv_val, 2),
            "comp_new_aus": round(comp_new_aus_val, 2),
            "comp_new_gsv_ratio": round(comp_new_gsv_ratio_val, 4),
            "comp_new_users_ratio": round(comp_new_users_ratio_val, 4),
            "comp_member_users": int(comp_member_users) if comp_member_users is not None else 0,
            "comp_member_gsv": round(_n(comp_member_gsv), 2),
            "comp_member_aus": round(_n(comp_member_aus), 2),
            "comp_member_gsv_ratio": comp_member_gsv_ratio_val,
            "comp_member_users_ratio": comp_member_users_ratio_val,
            "comp_member_old_users": comp_member_old_users_val,
            "comp_member_old_gsv": comp_member_old_gsv_val,
            "comp_member_old_aus": round(comp_member_old_aus_val, 2),
            "comp_member_old_gsv_ratio": comp_member_old_gsv_ratio_val,
            "comp_member_old_users_ratio": comp_member_old_users_ratio_val,
            "comp_member_new_users": comp_member_new_users_val,
            "comp_member_new_gsv": round(comp_member_new_gsv_val, 2),
            "comp_member_new_aus": round(comp_member_new_aus_val, 2),
            "comp_member_new_gsv_ratio": round(comp_member_new_gsv_ratio_val, 4),
            "comp_member_new_users_ratio": round(comp_member_new_users_ratio_val, 4),
            # 2024年（前年）
            "prev2_gsv_users": prev2_gsv_users_val,
            "prev2_gsv": prev2_gsv_val,
            "prev2_aus": round(_n(prev2_aus), 2),
            "prev2_old_users": prev2_old_users_val,
            "prev2_old_gsv": prev2_old_gsv_val,
            "prev2_old_aus": round(_n(prev2_old_aus), 2),
            "prev2_old_gsv_ratio": prev2_old_gsv_ratio_val,
            "prev2_old_users_ratio": prev2_old_users_ratio_val,
            "prev2_new_users": prev2_new_users_val,
            "prev2_new_gsv": round(prev2_new_gsv_val, 2),
            "prev2_new_aus": round(prev2_new_aus_val, 2),
            "prev2_new_gsv_ratio": round(prev2_new_gsv_ratio_val, 4),
            "prev2_new_users_ratio": round(prev2_new_users_ratio_val, 4),
            "prev2_member_users": int(prev2_member_users) if prev2_member_users is not None else 0,
            "prev2_member_gsv": round(_n(prev2_member_gsv), 2),
            "prev2_member_aus": round(_n(prev2_member_aus), 2),
            "prev2_member_gsv_ratio": prev2_member_gsv_ratio_val,
            "prev2_member_users_ratio": prev2_member_users_ratio_val,
            "prev2_member_old_users": prev2_member_old_users_val,
            "prev2_member_old_gsv": prev2_member_old_gsv_val,
            "prev2_member_old_aus": round(prev2_member_old_aus_val, 2),
            "prev2_member_old_gsv_ratio": prev2_member_old_gsv_ratio_val,
            "prev2_member_old_users_ratio": prev2_member_old_users_ratio_val,
            "prev2_member_new_users": prev2_member_new_users_val,
            "prev2_member_new_gsv": round(prev2_member_new_gsv_val, 2),
            "prev2_member_new_aus": round(prev2_member_new_aus_val, 2),
            "prev2_member_new_gsv_ratio": round(prev2_member_new_gsv_ratio_val, 4),
            "prev2_member_new_users_ratio": round(prev2_member_new_users_ratio_val, 4),
            # YoY = (2026 - 2025) / 2025
            "yoy_gsv": yoy_absolute(round(_n(gsv), 2), comp_gsv_val),
            "yoy_gsv_users": yoy_absolute(int(gsv_users), comp_gsv_users_val),
            "yoy_old_gsv": yoy_absolute(round(_n(old_gsv), 2), comp_old_gsv_val),
            "yoy_old_users": yoy_absolute(int(old_users), comp_old_users_val),
            "yoy_new_gsv": yoy_absolute(round(new_gsv, 2), comp_new_gsv_val),
            "yoy_new_users": yoy_absolute(int(new_users), comp_new_users_val),
            "yoy_member_gsv": yoy_absolute(round(_n(member_gsv), 2), round(_n(comp_member_gsv), 2)),
            "yoy_member_users": yoy_absolute(int(member_users), int(comp_member_users) if comp_member_users else 0),
            "yoy_member_old_gsv": yoy_absolute(round(_n(member_old_gsv), 2), comp_member_old_gsv_val),
            "yoy_member_old_users": yoy_absolute(int(member_old_users), comp_member_old_users_val),
            "yoy_member_new_gsv": yoy_absolute(round(member_new_gsv, 2), comp_member_new_gsv_val),
            "yoy_member_new_users": yoy_absolute(int(member_new_users), comp_member_new_users_val),
            # ---- AUS YOY（人均值同比，增长率）
            "yoy_aus": yoy_absolute(round(_n(aus), 2), round(_n(comp_aus), 2)),
            "yoy_old_aus": yoy_absolute(round(_n(old_aus), 2), round(_n(comp_old_aus), 2)),
            "yoy_new_aus": yoy_absolute(round(new_aus, 2), round(comp_new_aus_val, 2)),
            "yoy_member_aus": yoy_absolute(round(_n(member_aus), 2), round(_n(comp_member_aus), 2)),
            "yoy_member_old_aus": yoy_absolute(
                round(_n(member_old_gsv) / member_old_users if member_old_users > 0 else 0.0, 2),
                round(_n(comp_member_old_gsv) / int(comp_member_old_users) if comp_member_old_users and int(comp_member_old_users) > 0 else 0.0, 2),
            ),
            "yoy_member_new_aus": yoy_absolute(round(member_new_aus, 2), round(comp_member_new_aus_val, 2)),
            # ---- Ratio YOY（占比结构变化，百分点 = cur_ratio - comp_ratio）
            "yoy_old_gsv_ratio": yoy_ratio(old_gsv_ratio, comp_old_gsv_ratio_val),
            "yoy_old_users_ratio": yoy_ratio(old_users_ratio, comp_old_users_ratio_val),
            "yoy_new_gsv_ratio": yoy_ratio(new_gsv_ratio, comp_new_gsv_ratio_val),
            "yoy_new_users_ratio": yoy_ratio(new_users_ratio, comp_new_users_ratio_val),
            "yoy_member_gsv_ratio": yoy_ratio(member_gsv_ratio, comp_member_gsv_ratio_val),
            "yoy_member_users_ratio": yoy_ratio(member_users_ratio, comp_member_users_ratio_val),
            "yoy_member_old_gsv_ratio": yoy_ratio(member_old_gsv_ratio, comp_member_old_gsv_ratio_val),
            "yoy_member_old_users_ratio": yoy_ratio(member_old_users_ratio, comp_member_old_users_ratio_val),
            "yoy_member_new_gsv_ratio": yoy_ratio(member_new_gsv_ratio, comp_member_new_gsv_ratio_val),
            "yoy_member_new_users_ratio": yoy_ratio(member_new_users_ratio, comp_member_new_users_ratio_val),
        })

    return {
        "dimension": dimension,
        "mode": mode,
        "current_period": {"start": cur_start, "end": cur_end, "cutoff": cutoff},
        "comparison_period": {"start": comp_start, "end": comp_end, "cutoff": comp_cutoff},
        "prev2_period": {"start": prev2_start, "end": prev2_end} if prev2_start else None,
        "rows": rows,
    }


def calculate_audience_summary(
    year: int = 2026,
    metric_type: str = "GSV",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    channel: Optional[str] = None,
    period: Optional[str] = None,  # WTD/MTD/YTD/Q1-Q4
    exclude_channels: Optional[List[str]] = None,
    compare_start_date: Optional[str] = None,
    compare_end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    人群看板汇总：三面板数据计算
    - Panel A: 30指标对比（当前筛选条件数据，3年同比）
    - Panel B: 渠道概览-全店（所有渠道，3年；选中渠道时仅返回该渠道）
    - Panel C: 渠道概览-会员（所有渠道，3年）

    筛选器联动：
    - period: WTD/MTD/YTD/Q1-Q4（优先，使用 PeriodBuilder 计算三周期）
    - start_date/end_date：自定义日期范围（period为空时使用，空则默认当月MTD）
    - channel：渠道筛选（为空则展示全店/所有渠道）
    - exclude_channels: 排除的渠道列表（如低价渠道）
    """
    from datetime import date
    from calendar import monthrange

    today = date.today()

    # ── 日期范围解析 ────────────────────────────────────────────────
    # 优先级：period（PeriodBuilder） > start_date/end_date（自定义） > 默认MTD
    if period:
        # 使用 PeriodBuilder（WTD/MTD/YTD/Q1-Q4）
        try:
            pb_func = getattr(PeriodBuilder, period.lower())
            ranges = pb_func(today=today)
            cur_range = ranges["current"]
            comp_range = ranges["comparison"]
            prev2_range = ranges["prev2"]
            cur_start_dt = f"{cur_range.start} 00:00:00"
            cur_end_dt = f"{cur_range.end} 23:59:59"
            ly_start_dt = f"{comp_range.start} 00:00:00"
            ly_end_dt = f"{comp_range.end} 23:59:59"
            y2_start_dt = f"{prev2_range.start} 00:00:00"
            y2_end_dt = f"{prev2_range.end} 23:59:59"
            cutoff = cur_range.cutoff
            ly_cutoff_str = comp_range.cutoff
            y2_cutoff_str = prev2_range.cutoff
            if period.upper() in ('WTD', 'MTD', 'YTD'):
                current_year_label = str(today.year)
                comp_year_label = str(today.year - 1)
                prev2_year_label = str(today.year - 2)
            else:
                # Q1-Q4
                current_year_label = str(today.year)
                comp_year_label = str(today.year - 1)
                prev2_year_label = str(today.year - 2)
        except (AttributeError, KeyError):
            period = None  # fallback

    if not period and start_date and end_date:
        # 用户自定义日期范围（已修复 end_date day bug）
        cur_start_dt = f"{start_date} 00:00:00"
        cur_end_dt = f"{end_date} 23:59:59"
        cur_start_y, cur_start_m, cur_start_d = map(int, start_date.split('-'))
        cur_end_y, cur_end_m, cur_end_d = map(int, end_date.split('-'))
        cur_start_date = date(cur_start_y, cur_start_m, cur_start_d)
        cutoff_date = date(cur_start_y, cur_start_m, 1) - timedelta(days=1)
        cutoff = cutoff_date.strftime("%Y-%m-%d")
        # 同比：同期去年（结束日改用 end_date 的 day）
        ly_date = date(cur_start_y - 1, cur_start_m, cur_start_d)
        ly_start_dt = f"{ly_date.year}-{ly_date.month:02d}-{ly_date.day:02d} 00:00:00"
        ly_end_year, ly_end_month = cur_end_y - 1, cur_end_m
        ly_end_day = min(cur_end_d, monthrange(ly_end_year, ly_end_month)[1])
        ly_end_dt = f"{ly_end_year}-{ly_end_month:02d}-{ly_end_day:02d} 23:59:59"
        # cutoff 必须以【开始月】为准，不能用结束月（否则 Q1 会切成 2-28）
        ly_cutoff = date(ly_date.year, ly_date.month, 1) - timedelta(days=1)
        ly_cutoff_str = ly_cutoff.strftime("%Y-%m-%d")
        y2_date = date(cur_start_y - 2, cur_start_m, cur_start_d)
        y2_start_dt = f"{y2_date.year}-{y2_date.month:02d}-{y2_date.day:02d} 00:00:00"
        y2_end_year, y2_end_month = cur_end_y - 2, cur_end_m
        y2_end_day = min(cur_end_d, monthrange(y2_end_year, y2_end_month)[1])
        y2_end_dt = f"{y2_end_year}-{y2_end_month:02d}-{y2_end_day:02d} 23:59:59"
        y2_cutoff = date(y2_date.year, y2_date.month, 1) - timedelta(days=1)
        y2_cutoff_str = y2_cutoff.strftime("%Y-%m-%d")
        current_year_label = str(cur_start_y)
        comp_year_label = str(cur_start_y - 1)
        prev2_year_label = str(cur_start_y - 2)
    elif not period:
        # 默认当月MTD
        yesterday = today - timedelta(days=1)
        cur_month = today.month
        _, last_day_cur = monthrange(today.year, cur_month)
        cur_start = f"{today.year}-{cur_month:02d}-01"
        cur_end = f"{today.year}-{cur_month:02d}-{min(yesterday.day, last_day_cur):02d}"
        cur_start_dt = f"{cur_start} 00:00:00"
        cur_end_dt = f"{cur_end} 23:59:59"
        cur_start_y, cur_start_m, cur_start_d = today.year, cur_month, 1
        cutoff = (datetime(today.year, cur_month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")

        comp_year = today.year - 1
        _, last_day_comp = monthrange(comp_year, cur_month)
        comp_start = f"{comp_year}-{cur_month:02d}-01"
        comp_end = f"{comp_year}-{cur_month:02d}-{min(yesterday.day, last_day_comp):02d}"
        comp_start_dt = f"{comp_start} 00:00:00"
        comp_end_dt = f"{comp_end} 23:59:59"
        comp_cutoff = (datetime(comp_year, cur_month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")

        prev2_year = today.year - 2
        _, last_day_prev2 = monthrange(prev2_year, cur_month)
        prev2_start = f"{prev2_year}-{cur_month:02d}-01"
        prev2_end = f"{prev2_year}-{cur_month:02d}-{min(yesterday.day, last_day_prev2):02d}"
        prev2_start_dt = f"{prev2_start} 00:00:00"
        prev2_end_dt = f"{prev2_end} 23:59:59"
        prev2_cutoff = (datetime(prev2_year, cur_month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")

        ly_start_dt = comp_start_dt
        ly_end_dt = comp_end_dt
        ly_cutoff_str = comp_cutoff
        y2_start_dt = prev2_start_dt
        y2_end_dt = prev2_end_dt
        y2_cutoff_str = prev2_cutoff
        current_year_label = str(today.year)
        comp_year_label = str(comp_year)
        prev2_year_label = str(prev2_year)

    # ── 自定义对比期覆盖 ─────────────────────────────────────
    if compare_start_date and compare_end_date:
        ly_start_dt = f"{compare_start_date} 00:00:00"
        ly_end_dt = f"{compare_end_date} 23:59:59"
        comp_start_y, comp_start_m, comp_start_d = map(int, compare_start_date.split('-'))
        ly_cutoff = date(comp_start_y, comp_start_m, 1) - timedelta(days=1)
        ly_cutoff_str = ly_cutoff.strftime("%Y-%m-%d")
        comp_year_label = f"对比期"
        # 用户自选对比期时，prev2 无意义，归零
        y2_start_dt = "2099-01-01 00:00:00"
        y2_end_dt = "2099-01-01 00:00:00"
        y2_cutoff_str = "2099-01-01"
        prev2_year_label = ""

    conn = get_connection()
    try:

        def _n(v):
            return float(v) if v is not None else 0.0

        def _safe_int(v):
            return int(v) if v is not None else 0

        def _aggregate_channel_rows(data_map, db_channels):
            """聚合多个 DB 渠道的数据（用于组合渠道如'纯派样'）"""
            total_gsv_users = 0
            total_gsv = 0.0
            total_old_users = 0
            total_old_gsv = 0.0
            total_member_users = 0
            total_member_gsv = 0.0
            total_member_old_users = 0
            total_member_old_gsv = 0.0
            for db_ch in db_channels:
                row = data_map.get(db_ch)
                if not row:
                    continue
                total_gsv_users += _safe_int(row[0])
                total_gsv += _n(row[1])
                total_old_users += _safe_int(row[3])
                total_old_gsv += _n(row[4])
                total_member_users += _safe_int(row[6])
                total_member_gsv += _n(row[7])
                total_member_old_users += _safe_int(row[9])
                total_member_old_gsv += _n(row[10])
            total_aus = total_gsv / total_gsv_users if total_gsv_users > 0 else 0.0
            total_old_aus = total_old_gsv / total_old_users if total_old_users > 0 else 0.0
            total_member_aus = total_member_gsv / total_member_users if total_member_users > 0 else 0.0
            return (
                total_gsv_users, total_gsv, total_aus,
                total_old_users, total_old_gsv, total_old_aus,
                total_member_users, total_member_gsv, total_member_aus,
                total_member_old_users, total_member_old_gsv,
            )

        def _run_period_data(start_dt, end_dt, cutoff_dt, ch_filter: Optional[str] = None, ex_channels: Optional[List[str]] = None):
            """执行一个周期的查询，支持可选渠道过滤"""
            params = [start_dt, end_dt]
            where_parts = ["pay_time >= ?::TIMESTAMP", "pay_time <= ?::TIMESTAMP",
                            "is_goujinjin = FALSE", "order_status != '交易关闭'", "is_refund = FALSE"]
            if ch_filter and ch_filter != "全店":
                db_channels = _expand_channel(ch_filter)
                if len(db_channels) == 1:
                    where_parts.append(f"channel = ?")
                    params.append(db_channels[0])
                elif len(db_channels) > 1:
                    placeholders = ",".join(["?"] * len(db_channels))
                    where_parts.append(f"channel IN ({placeholders})")
                    params.extend(db_channels)
            if ex_channels:
                db_ex = [UI_TO_DB.get(ch, ch) for ch in ex_channels]
                placeholders = ",".join(["?"] * len(db_ex))
                where_parts.append(f"channel NOT IN ({placeholders})")
                params.extend(db_ex)
            where_sql = " AND ".join(where_parts)
            full_params = params + [cutoff_dt]

            sql = f"""
            WITH
            base AS (
                SELECT * FROM orders
                WHERE {where_sql}
            ),
            old_customers AS (
                SELECT DISTINCT u.user_id
                FROM user_first_purchase u
                WHERE u.first_pay_date <= ?::DATE
            ),
            enriched AS (
                SELECT
                    o.channel AS dim_key,
                    o.user_id,
                    o.actual_amount AS amount,
                    o.is_member,
                    CASE WHEN oc.user_id IS NOT NULL THEN 1 ELSE 0 END AS is_old
                FROM base o
                LEFT JOIN old_customers oc ON o.user_id = oc.user_id
            ),
            grouped AS (
                SELECT
                    dim_key,
                    COUNT(DISTINCT user_id) AS gsv_users,
                    SUM(amount) AS gsv,
                    SUM(amount) / NULLIF(COUNT(DISTINCT user_id), 0) AS aus,
                    COUNT(DISTINCT CASE WHEN is_old = 1 THEN user_id END) AS old_users,
                    SUM(amount * CASE WHEN is_old = 1 THEN 1 ELSE 0 END) AS old_gsv,
                    SUM(amount * CASE WHEN is_old = 1 THEN 1 ELSE 0 END) /
                        NULLIF(COUNT(DISTINCT CASE WHEN is_old = 1 THEN user_id END), 0) AS old_aus,
                    COUNT(DISTINCT CASE WHEN is_member = TRUE THEN user_id END) AS member_users,
                    SUM(amount * CASE WHEN is_member = TRUE THEN 1 ELSE 0 END) AS member_gsv,
                    SUM(amount * CASE WHEN is_member = TRUE THEN 1 ELSE 0 END) /
                        NULLIF(COUNT(DISTINCT CASE WHEN is_member = TRUE THEN user_id END), 0) AS member_aus,
                    COUNT(DISTINCT CASE WHEN is_member = TRUE AND is_old = 1 THEN user_id END) AS member_old_users,
                    SUM(amount * CASE WHEN is_member = TRUE AND is_old = 1 THEN 1 ELSE 0 END) AS member_old_gsv,
                    GROUPING(dim_key) AS _grp
                FROM enriched
                GROUP BY GROUPING SETS ((dim_key), ())
            )
            SELECT
                CASE WHEN _grp = 1 THEN '__TOTAL__' ELSE dim_key END,
                gsv_users, gsv, aus,
                old_users, old_gsv, old_aus,
                member_users, member_gsv, member_aus,
                member_old_users, member_old_gsv
            FROM grouped
            ORDER BY _grp ASC, gsv DESC
            """
            raw = conn.execute(sql, full_params).fetchall()
            return {r[0]: r[1:] for r in raw}

        def _extract_metrics(data_map):
            r = data_map.get('__TOTAL__', (0,) * 11)
            gsv_users = _safe_int(r[0])
            gsv = _n(r[1])
            aus = _n(r[2])
            old_users = _safe_int(r[3])
            old_gsv = _n(r[4])
            old_aus = _n(r[5])
            member_users = _safe_int(r[6])
            member_gsv = _n(r[7])
            member_aus = _n(r[8])
            member_old_users = _safe_int(r[9])
            member_old_gsv = _n(r[10])
            new_users = max(0, gsv_users - old_users)
            new_gsv = max(0, gsv - old_gsv)
            new_aus = new_gsv / new_users if new_users > 0 else 0.0
            member_new_gsv = max(0, member_gsv - member_old_gsv)
            member_new_users = max(0, member_users - member_old_users)
            return {
                "gsv": gsv, "users": gsv_users, "aus": aus,
                "old_gsv": old_gsv, "old_users": old_users, "old_aus": old_aus,
                "old_gsv_ratio": old_gsv / gsv if gsv > 0 else 0.0,
                "old_users_ratio": old_users / gsv_users if gsv_users > 0 else 0.0,
                "new_gsv": new_gsv, "new_users": new_users, "new_aus": new_aus,
                "new_gsv_ratio": new_gsv / gsv if gsv > 0 else 0.0,
                "new_users_ratio": new_users / gsv_users if gsv_users > 0 else 0.0,
                "member_gsv": member_gsv, "member_users": member_users, "member_aus": member_aus,
                "member_penetration": member_users / gsv_users if gsv_users > 0 else 0.0,
                "member_users_ratio": member_users / gsv_users if gsv_users > 0 else 0.0,
                "member_old_gsv": member_old_gsv, "member_old_users": member_old_users,
                "member_old_aus": member_old_gsv / member_old_users if member_old_users > 0 else 0.0,
                "member_old_gsv_ratio": member_old_gsv / member_gsv if member_gsv > 0 else 0.0,
                "member_old_users_ratio": member_old_users / member_users if member_users > 0 else 0.0,
                "member_new_gsv": member_new_gsv,
                "member_new_users": member_new_users,
                "member_new_aus": member_new_gsv / member_new_users if member_new_users > 0 else 0.0,
                "member_new_gsv_ratio": member_new_gsv / gsv if gsv > 0 else 0.0,
                "member_new_users_ratio": member_new_users / gsv_users if gsv_users > 0 else 0.0,
            }

        # Panel A 数据：支持渠道筛选（ch_filter=channel 时取该渠道数据；为空时取全店）
        all_cur = _run_period_data(cur_start_dt, cur_end_dt, cutoff, ch_filter=channel, ex_channels=exclude_channels)
        all_comp = _run_period_data(ly_start_dt, ly_end_dt, ly_cutoff_str, ch_filter=channel, ex_channels=exclude_channels)
        all_prev2 = _run_period_data(y2_start_dt, y2_end_dt, y2_cutoff_str, ch_filter=channel, ex_channels=exclude_channels)

        # Panel A 指标使用全店数据
        cur_m = _extract_metrics(all_cur)
        comp_m = _extract_metrics(all_comp)
        prev2_m = _extract_metrics(all_prev2)

        indicators = [
            {"field": "全店GSV",        "kind": "money", "value_2026": cur_m["gsv"],         "value_2025": comp_m["gsv"],          "value_2024": prev2_m["gsv"],          "yoy": yoy_absolute(cur_m["gsv"], comp_m["gsv"])},
            {"field": "全店人数",       "kind": "count", "value_2026": cur_m["users"],        "value_2025": comp_m["users"],        "value_2024": prev2_m["users"],        "yoy": yoy_absolute(cur_m["users"], comp_m["users"])},
            {"field": "AUS",           "kind": "aus",   "value_2026": cur_m["aus"],          "value_2025": comp_m["aus"],          "value_2024": prev2_m["aus"],          "yoy": yoy_absolute(cur_m["aus"], comp_m["aus"])},
            {"field": "老客GSV",       "kind": "money", "value_2026": cur_m["old_gsv"],      "value_2025": comp_m["old_gsv"],      "value_2024": prev2_m["old_gsv"],      "yoy": yoy_absolute(cur_m["old_gsv"], comp_m["old_gsv"])},
            {"field": "老客人数",       "kind": "count", "value_2026": cur_m["old_users"],    "value_2025": comp_m["old_users"],    "value_2024": prev2_m["old_users"],    "yoy": yoy_absolute(cur_m["old_users"], comp_m["old_users"])},
            {"field": "老客AUS",       "kind": "aus",   "value_2026": cur_m["old_aus"],      "value_2025": comp_m["old_aus"],      "value_2024": prev2_m["old_aus"],      "yoy": yoy_absolute(cur_m["old_aus"], comp_m["old_aus"])},
            {"field": "老客GSV占比",   "kind": "ratio", "value_2026": cur_m["old_gsv_ratio"], "value_2025": comp_m["old_gsv_ratio"], "value_2024": prev2_m["old_gsv_ratio"], "yoy": yoy_ratio(cur_m["old_gsv_ratio"], comp_m["old_gsv_ratio"])},
            {"field": "老客人数占比",   "kind": "ratio", "value_2026": cur_m["old_users_ratio"], "value_2025": comp_m["old_users_ratio"], "value_2024": prev2_m["old_users_ratio"], "yoy": yoy_ratio(cur_m["old_users_ratio"], comp_m["old_users_ratio"])},
            {"field": "新客GSV",       "kind": "money", "value_2026": cur_m["new_gsv"],      "value_2025": comp_m["new_gsv"],      "value_2024": prev2_m["new_gsv"],      "yoy": yoy_absolute(cur_m["new_gsv"], comp_m["new_gsv"])},
            {"field": "新客人数",       "kind": "count", "value_2026": cur_m["new_users"],    "value_2025": comp_m["new_users"],    "value_2024": prev2_m["new_users"],    "yoy": yoy_absolute(cur_m["new_users"], comp_m["new_users"])},
            {"field": "新客AUS",       "kind": "aus",   "value_2026": cur_m["new_aus"],      "value_2025": comp_m["new_aus"],      "value_2024": prev2_m["new_aus"],      "yoy": yoy_absolute(cur_m["new_aus"], comp_m["new_aus"])},
            {"field": "新客GSV占比",   "kind": "ratio", "value_2026": cur_m["new_gsv_ratio"], "value_2025": comp_m["new_gsv_ratio"], "value_2024": prev2_m["new_gsv_ratio"], "yoy": yoy_ratio(cur_m["new_gsv_ratio"], comp_m["new_gsv_ratio"])},
            {"field": "新客人数占比",   "kind": "ratio", "value_2026": cur_m["new_users_ratio"], "value_2025": comp_m["new_users_ratio"], "value_2024": prev2_m["new_users_ratio"], "yoy": yoy_ratio(cur_m["new_users_ratio"], comp_m["new_users_ratio"])},
            {"field": "会员GSV",       "kind": "money", "value_2026": cur_m["member_gsv"],   "value_2025": comp_m["member_gsv"],   "value_2024": prev2_m["member_gsv"],   "yoy": yoy_absolute(cur_m["member_gsv"], comp_m["member_gsv"])},
            {"field": "会员人数",       "kind": "count", "value_2026": cur_m["member_users"],  "value_2025": comp_m["member_users"],  "value_2024": prev2_m["member_users"],  "yoy": yoy_absolute(cur_m["member_users"], comp_m["member_users"])},
            {"field": "会员AUS",       "kind": "aus",   "value_2026": cur_m["member_aus"],   "value_2025": comp_m["member_aus"],   "value_2024": prev2_m["member_aus"],   "yoy": yoy_absolute(cur_m["member_aus"], comp_m["member_aus"])},
            {"field": "会员渗透率",     "kind": "ratio", "value_2026": cur_m["member_penetration"], "value_2025": comp_m["member_penetration"], "value_2024": prev2_m["member_penetration"], "yoy": yoy_ratio(cur_m["member_penetration"], comp_m["member_penetration"])},
            {"field": "会员人数占比",   "kind": "ratio", "value_2026": cur_m["member_users_ratio"], "value_2025": comp_m["member_users_ratio"], "value_2024": prev2_m["member_users_ratio"], "yoy": yoy_ratio(cur_m["member_users_ratio"], comp_m["member_users_ratio"])},
            {"field": "会员老客GSV",   "kind": "money", "value_2026": cur_m["member_old_gsv"], "value_2025": comp_m["member_old_gsv"], "value_2024": prev2_m["member_old_gsv"], "yoy": yoy_absolute(cur_m["member_old_gsv"], comp_m["member_old_gsv"])},
            {"field": "会员老客人数",   "kind": "count", "value_2026": cur_m["member_old_users"], "value_2025": comp_m["member_old_users"], "value_2024": prev2_m["member_old_users"], "yoy": yoy_absolute(cur_m["member_old_users"], comp_m["member_old_users"])},
            {"field": "会员老客AUS",   "kind": "aus",   "value_2026": cur_m["member_old_aus"], "value_2025": comp_m["member_old_aus"], "value_2024": prev2_m["member_old_aus"], "yoy": yoy_absolute(cur_m["member_old_aus"], comp_m["member_old_aus"])},
            {"field": "会员老客GSV占比","kind": "ratio", "value_2026": cur_m["member_old_gsv_ratio"], "value_2025": comp_m["member_old_gsv_ratio"], "value_2024": prev2_m["member_old_gsv_ratio"], "yoy": yoy_ratio(cur_m["member_old_gsv_ratio"], comp_m["member_old_gsv_ratio"])},
            {"field": "会员老客人数占比","kind": "ratio", "value_2026": cur_m["member_old_users_ratio"], "value_2025": comp_m["member_old_users_ratio"], "value_2024": prev2_m["member_old_users_ratio"], "yoy": yoy_ratio(cur_m["member_old_users_ratio"], comp_m["member_old_users_ratio"])},
            {"field": "会员新客GSV",   "kind": "money", "value_2026": cur_m["member_new_gsv"], "value_2025": comp_m["member_new_gsv"], "value_2024": prev2_m["member_new_gsv"], "yoy": yoy_absolute(cur_m["member_new_gsv"], comp_m["member_new_gsv"])},
            {"field": "会员新客人数",   "kind": "count", "value_2026": cur_m["member_new_users"], "value_2025": comp_m["member_new_users"], "value_2024": prev2_m["member_new_users"], "yoy": yoy_absolute(cur_m["member_new_users"], comp_m["member_new_users"])},
            {"field": "会员新客AUS",   "kind": "aus",   "value_2026": cur_m["member_new_aus"], "value_2025": comp_m["member_new_aus"], "value_2024": prev2_m["member_new_aus"], "yoy": yoy_absolute(cur_m["member_new_aus"], comp_m["member_new_aus"])},
            {"field": "会员新客GSV占比","kind": "ratio", "value_2026": cur_m["member_new_gsv_ratio"], "value_2025": comp_m["member_new_gsv_ratio"], "value_2024": prev2_m["member_new_gsv_ratio"], "yoy": yoy_ratio(cur_m["member_new_gsv_ratio"], comp_m["member_new_gsv_ratio"])},
            {"field": "会员新客人数占比","kind": "ratio", "value_2026": cur_m["member_new_users_ratio"], "value_2025": comp_m["member_new_users_ratio"], "value_2024": prev2_m["member_new_users_ratio"], "yoy": yoy_ratio(cur_m["member_new_users_ratio"], comp_m["member_new_users_ratio"])},
        ]

        # ─── Panel B: 渠道概览-全店 ───────────────────────────────────
        # 选中渠道时只返回该渠道一行；否则返回全部9个渠道
        all_total_gsv = cur_m["gsv"]
        all_comp_total_gsv = comp_m["gsv"]

        channel_all = []
        if channel and channel != "全店":
            # 只返回选中渠道那一行（支持组合渠道自动聚合）
            db_channels = _expand_channel(channel)
            if len(db_channels) == 1:
                ch_cur_data = all_cur.get(db_channels[0], (0,) * 11)
                ch_comp_data = all_comp.get(db_channels[0], (0,) * 11)
            else:
                ch_cur_data = _aggregate_channel_rows(all_cur, db_channels)
                ch_comp_data = _aggregate_channel_rows(all_comp, db_channels)
            gsv_2026 = _n(ch_cur_data[1])
            gsv_2025 = _n(ch_comp_data[1])
            users_2026 = _safe_int(ch_cur_data[0])
            users_2025 = _safe_int(ch_comp_data[0])
            aus_2026 = _n(ch_cur_data[2])
            aus_2025 = _n(ch_comp_data[2])
            old_gsv_2026 = _n(ch_cur_data[4])
            old_gsv_2025 = _n(ch_comp_data[4])
            new_gsv_2026 = gsv_2026 - old_gsv_2026
            new_gsv_2025 = gsv_2025 - old_gsv_2025
            old_users_2026 = _safe_int(ch_cur_data[3])
            old_users_2025 = _safe_int(ch_comp_data[3])
            old_aus_2026 = _n(ch_cur_data[5])
            old_aus_2025 = _n(ch_comp_data[5])
            new_users_2026 = max(0, users_2026 - old_users_2026)
            new_users_2025 = max(0, users_2025 - old_users_2025)
            new_aus_2026 = new_gsv_2026 / new_users_2026 if new_users_2026 > 0 else 0.0
            new_aus_2025 = new_gsv_2025 / new_users_2025 if new_users_2025 > 0 else 0.0
            ratio_2026 = gsv_2026 / all_total_gsv if all_total_gsv > 0 else 0.0
            ratio_2025 = gsv_2025 / all_comp_total_gsv if all_comp_total_gsv > 0 else 0.0
            old_ratio_2026 = old_gsv_2026 / gsv_2026 if gsv_2026 > 0 else 0.0
            old_ratio_2025 = old_gsv_2025 / gsv_2025 if gsv_2025 > 0 else 0.0
            new_ratio_2026 = new_gsv_2026 / gsv_2026 if gsv_2026 > 0 else 0.0
            new_ratio_2025 = new_gsv_2025 / gsv_2025 if gsv_2025 > 0 else 0.0
            channel_all.append({
                "channel": channel,
                "gsv_2026": gsv_2026,
                "gsv_2025": gsv_2025,
                "yoy": yoy_absolute(gsv_2026, gsv_2025),
                "ratio_2026": round(ratio_2026, 4),
                "ratio_2025": round(ratio_2025, 4),
                "ratio_yoy": yoy_ratio(ratio_2026, ratio_2025),
                "users_2026": users_2026,
                "users_2025": users_2025,
                "users_yoy": yoy_absolute(users_2026, users_2025),
                "aus_2026": round(aus_2026, 2),
                "aus_2025": round(aus_2025, 2),
                "aus_yoy": yoy_absolute(aus_2026, aus_2025),
                "new_gsv_2026": new_gsv_2026,
                "new_gsv_2025": new_gsv_2025,
                "new_gsv_yoy": yoy_absolute(new_gsv_2026, new_gsv_2025),
                "new_gsv_ratio_2026": round(new_ratio_2026, 4),
                "new_gsv_ratio_2025": round(new_ratio_2025, 4),
                "new_gsv_ratio_yoy": yoy_ratio(new_ratio_2026, new_ratio_2025),
                "old_gsv_2026": old_gsv_2026,
                "old_gsv_2025": old_gsv_2025,
                "old_gsv_yoy": yoy_absolute(old_gsv_2026, old_gsv_2025),
                "old_gsv_ratio_2026": round(old_ratio_2026, 4),
                "old_gsv_ratio_2025": round(old_ratio_2025, 4),
                "old_gsv_ratio_yoy": yoy_ratio(old_ratio_2026, old_ratio_2025),
                "new_users_2026": new_users_2026,
                "new_users_2025": new_users_2025,
                "new_users_yoy": yoy_absolute(new_users_2026, new_users_2025),
                "new_aus_2026": round(new_aus_2026, 2),
                "new_aus_2025": round(new_aus_2025, 2),
                "new_aus_yoy": yoy_absolute(new_aus_2026, new_aus_2025),
                "old_users_2026": old_users_2026,
                "old_users_2025": old_users_2025,
                "old_users_yoy": yoy_absolute(old_users_2026, old_users_2025),
                "old_aus_2026": round(old_aus_2026, 2),
                "old_aus_2025": round(old_aus_2025, 2),
                "old_aus_yoy": yoy_absolute(old_aus_2026, old_aus_2025),
            })
        else:
            for ch in CHANNEL_ORDER:
                db_key = next((k for k in all_cur if DB_TO_UI.get(k, "") == ch), None)
                db_key_comp = next((k for k in all_comp if DB_TO_UI.get(k, "") == ch), None)
                r_cur = all_cur.get(db_key, (0,) * 11) if db_key else (0,) * 11
                r_comp = all_comp.get(db_key_comp, (0,) * 11) if db_key_comp else (0,) * 11
                gsv_2026 = _n(r_cur[1])
                gsv_2025 = _n(r_comp[1])
                users_2026 = _safe_int(r_cur[0])
                users_2025 = _safe_int(r_comp[0])
                aus_2026 = _n(r_cur[2])
                aus_2025 = _n(r_comp[2])
                old_gsv_2026 = _n(r_cur[4])
                old_gsv_2025 = _n(r_comp[4])
                new_gsv_2026 = gsv_2026 - old_gsv_2026
                new_gsv_2025 = gsv_2025 - old_gsv_2025
                old_users_2026 = _safe_int(r_cur[3])
                old_users_2025 = _safe_int(r_comp[3])
                old_aus_2026 = _n(r_cur[5])
                old_aus_2025 = _n(r_comp[5])
                new_users_2026 = max(0, users_2026 - old_users_2026)
                new_users_2025 = max(0, users_2025 - old_users_2025)
                new_aus_2026 = new_gsv_2026 / new_users_2026 if new_users_2026 > 0 else 0.0
                new_aus_2025 = new_gsv_2025 / new_users_2025 if new_users_2025 > 0 else 0.0
                if gsv_2026 == 0 and gsv_2025 == 0:
                    continue
                ratio_2026 = gsv_2026 / all_total_gsv if all_total_gsv > 0 else 0.0
                ratio_2025 = gsv_2025 / all_comp_total_gsv if all_comp_total_gsv > 0 else 0.0
                old_ratio_2026 = old_gsv_2026 / gsv_2026 if gsv_2026 > 0 else 0.0
                old_ratio_2025 = old_gsv_2025 / gsv_2025 if gsv_2025 > 0 else 0.0
                new_ratio_2026 = new_gsv_2026 / gsv_2026 if gsv_2026 > 0 else 0.0
                new_ratio_2025 = new_gsv_2025 / gsv_2025 if gsv_2025 > 0 else 0.0
                channel_all.append({
                    "channel": ch,
                    "gsv_2026": gsv_2026,
                    "gsv_2025": gsv_2025,
                    "yoy": yoy_absolute(gsv_2026, gsv_2025),
                    "ratio_2026": round(ratio_2026, 4),
                    "ratio_2025": round(ratio_2025, 4),
                    "ratio_yoy": yoy_ratio(ratio_2026, ratio_2025),
                    "users_2026": users_2026,
                    "users_2025": users_2025,
                    "users_yoy": yoy_absolute(users_2026, users_2025),
                    "aus_2026": round(aus_2026, 2),
                    "aus_2025": round(aus_2025, 2),
                    "aus_yoy": yoy_absolute(aus_2026, aus_2025),
                    "new_gsv_2026": new_gsv_2026,
                    "new_gsv_2025": new_gsv_2025,
                    "new_gsv_yoy": yoy_absolute(new_gsv_2026, new_gsv_2025),
                    "new_gsv_ratio_2026": round(new_ratio_2026, 4),
                    "new_gsv_ratio_2025": round(new_ratio_2025, 4),
                    "new_gsv_ratio_yoy": yoy_ratio(new_ratio_2026, new_ratio_2025),
                    "old_gsv_2026": old_gsv_2026,
                    "old_gsv_2025": old_gsv_2025,
                    "old_gsv_yoy": yoy_absolute(old_gsv_2026, old_gsv_2025),
                    "old_gsv_ratio_2026": round(old_ratio_2026, 4),
                    "old_gsv_ratio_2025": round(old_ratio_2025, 4),
                    "old_gsv_ratio_yoy": yoy_ratio(old_ratio_2026, old_ratio_2025),
                    "new_users_2026": new_users_2026,
                    "new_users_2025": new_users_2025,
                    "new_users_yoy": yoy_absolute(new_users_2026, new_users_2025),
                    "new_aus_2026": round(new_aus_2026, 2),
                    "new_aus_2025": round(new_aus_2025, 2),
                    "new_aus_yoy": yoy_absolute(new_aus_2026, new_aus_2025),
                    "old_users_2026": old_users_2026,
                    "old_users_2025": old_users_2025,
                    "old_users_yoy": yoy_absolute(old_users_2026, old_users_2025),
                    "old_aus_2026": round(old_aus_2026, 2),
                    "old_aus_2025": round(old_aus_2025, 2),
                    "old_aus_yoy": yoy_absolute(old_aus_2026, old_aus_2025),
                })

        # ─── Panel B TTL: 全店汇总行 ────────────────────────────────
        # TTL 行的 ratio_2026/ratio_2025 固定为 1.0（占全店100%）
        # 新客/老客占比 = 各自GSV / 全店总GSV（两者相加=100%）
        all_cur_ttl = all_cur.get("__TOTAL__", (0,) * 11)
        all_comp_ttl = all_comp.get("__TOTAL__", (0,) * 11)
        ttl_users_2026 = _safe_int(all_cur_ttl[0])
        ttl_users_2025 = _safe_int(all_comp_ttl[0])
        ttl_aus_2026 = _n(all_cur_ttl[2])
        ttl_aus_2025 = _n(all_comp_ttl[2])
        ttl_old_gsv_2026 = _n(all_cur_ttl[4])
        ttl_old_gsv_2025 = _n(all_comp_ttl[4])
        ttl_old_users_2026 = _safe_int(all_cur_ttl[3])
        ttl_old_users_2025 = _safe_int(all_comp_ttl[3])
        ttl_old_aus_2026 = _n(all_cur_ttl[5])
        ttl_old_aus_2025 = _n(all_comp_ttl[5])
        ttl_new_gsv_2026 = all_total_gsv - ttl_old_gsv_2026
        ttl_new_gsv_2025 = all_comp_total_gsv - ttl_old_gsv_2025
        ttl_new_users_2026 = max(0, ttl_users_2026 - ttl_old_users_2026)
        ttl_new_users_2025 = max(0, ttl_users_2025 - ttl_old_users_2025)
        ttl_new_aus_2026 = ttl_new_gsv_2026 / ttl_new_users_2026 if ttl_new_users_2026 > 0 else 0.0
        ttl_new_aus_2025 = ttl_new_gsv_2025 / ttl_new_users_2025 if ttl_new_users_2025 > 0 else 0.0
        ttl_new_ratio_2026 = ttl_new_gsv_2026 / all_total_gsv if all_total_gsv > 0 else 0.0
        ttl_new_ratio_2025 = ttl_new_gsv_2025 / all_comp_total_gsv if all_comp_total_gsv > 0 else 0.0
        ttl_old_ratio_2026 = ttl_old_gsv_2026 / all_total_gsv if all_total_gsv > 0 else 0.0
        ttl_old_ratio_2025 = ttl_old_gsv_2025 / all_comp_total_gsv if all_comp_total_gsv > 0 else 0.0
        channel_all.append({
            "channel": "TTL",
            "gsv_2026": all_total_gsv,
            "gsv_2025": all_comp_total_gsv,
            "yoy": yoy_absolute(all_total_gsv, all_comp_total_gsv),
            "ratio_2026": 1.0,
            "ratio_2025": 1.0,
            "ratio_yoy": yoy_ratio(1.0, 1.0),
            "users_2026": ttl_users_2026,
            "users_2025": ttl_users_2025,
            "users_yoy": yoy_absolute(ttl_users_2026, ttl_users_2025),
            "aus_2026": round(ttl_aus_2026, 2),
            "aus_2025": round(ttl_aus_2025, 2),
            "aus_yoy": yoy_absolute(ttl_aus_2026, ttl_aus_2025),
            "new_gsv_2026": ttl_new_gsv_2026,
            "new_gsv_2025": ttl_new_gsv_2025,
            "new_gsv_yoy": yoy_absolute(ttl_new_gsv_2026, ttl_new_gsv_2025),
            "new_gsv_ratio_2026": round(ttl_new_ratio_2026, 4),
            "new_gsv_ratio_2025": round(ttl_new_ratio_2025, 4),
            "new_gsv_ratio_yoy": yoy_ratio(ttl_new_ratio_2026, ttl_new_ratio_2025),
            "old_gsv_2026": ttl_old_gsv_2026,
            "old_gsv_2025": ttl_old_gsv_2025,
            "old_gsv_yoy": yoy_absolute(ttl_old_gsv_2026, ttl_old_gsv_2025),
            "old_gsv_ratio_2026": round(ttl_old_ratio_2026, 4),
            "old_gsv_ratio_2025": round(ttl_old_ratio_2025, 4),
            "old_gsv_ratio_yoy": yoy_ratio(ttl_old_ratio_2026, ttl_old_ratio_2025),
            "new_users_2026": ttl_new_users_2026,
            "new_users_2025": ttl_new_users_2025,
            "new_users_yoy": yoy_absolute(ttl_new_users_2026, ttl_new_users_2025),
            "new_aus_2026": round(ttl_new_aus_2026, 2),
            "new_aus_2025": round(ttl_new_aus_2025, 2),
            "new_aus_yoy": yoy_absolute(ttl_new_aus_2026, ttl_new_aus_2025),
            "old_users_2026": ttl_old_users_2026,
            "old_users_2025": ttl_old_users_2025,
            "old_users_yoy": yoy_absolute(ttl_old_users_2026, ttl_old_users_2025),
            "old_aus_2026": round(ttl_old_aus_2026, 2),
            "old_aus_2025": round(ttl_old_aus_2025, 2),
            "old_aus_yoy": yoy_absolute(ttl_old_aus_2026, ttl_old_aus_2025),
        })

        # ─── Panel C: 渠道概览-会员 ───────────────────────────────────
        mem_total_gsv = cur_m["member_gsv"]
        mem_comp_total_gsv = comp_m["member_gsv"]

        channel_member = []
        if channel and channel != "全店":
            # 只返回选中渠道那一行（支持组合渠道自动聚合）
            db_channels = _expand_channel(channel)
            if len(db_channels) == 1:
                r_cur = all_cur.get(db_channels[0], (0,) * 11)
                r_comp = all_comp.get(db_channels[0], (0,) * 11)
            else:
                r_cur = _aggregate_channel_rows(all_cur, db_channels)
                r_comp = _aggregate_channel_rows(all_comp, db_channels)
            gsv_2026 = _n(r_cur[7])
            gsv_2025 = _n(r_comp[7])
            users_2026 = _safe_int(r_cur[6])
            users_2025 = _safe_int(r_comp[6])
            aus_2026 = _n(r_cur[8])
            aus_2025 = _n(r_comp[8])
            ch_total_gsv_2026 = _n(r_cur[1])
            ch_total_gsv_2025 = _n(r_comp[1])
            member_old_gsv_2026 = _n(r_cur[10])
            member_old_gsv_2025 = _n(r_comp[10])
            member_new_gsv_2026 = gsv_2026 - member_old_gsv_2026
            member_new_gsv_2025 = gsv_2025 - member_old_gsv_2025
            member_old_users_2026 = _safe_int(r_cur[9])
            member_old_users_2025 = _safe_int(r_comp[9])
            member_old_aus_2026 = member_old_gsv_2026 / member_old_users_2026 if member_old_users_2026 > 0 else 0.0
            member_old_aus_2025 = member_old_gsv_2025 / member_old_users_2025 if member_old_users_2025 > 0 else 0.0
            member_new_users_2026 = max(0, users_2026 - member_old_users_2026)
            member_new_users_2025 = max(0, users_2025 - member_old_users_2025)
            member_new_aus_2026 = member_new_gsv_2026 / member_new_users_2026 if member_new_users_2026 > 0 else 0.0
            member_new_aus_2025 = member_new_gsv_2025 / member_new_users_2025 if member_new_users_2025 > 0 else 0.0
            ratio_2026 = gsv_2026 / mem_total_gsv if mem_total_gsv > 0 else 0.0
            ratio_2025 = gsv_2025 / mem_comp_total_gsv if mem_comp_total_gsv > 0 else 0.0
            member_ratio_2026 = gsv_2026 / ch_total_gsv_2026 if ch_total_gsv_2026 > 0 else 0.0
            member_ratio_2025 = gsv_2025 / ch_total_gsv_2025 if ch_total_gsv_2025 > 0 else 0.0
            member_new_ratio_2026 = member_new_gsv_2026 / ch_total_gsv_2026 if ch_total_gsv_2026 > 0 else 0.0
            member_new_ratio_2025 = member_new_gsv_2025 / ch_total_gsv_2025 if ch_total_gsv_2025 > 0 else 0.0
            member_old_ratio_2026 = member_old_gsv_2026 / ch_total_gsv_2026 if ch_total_gsv_2026 > 0 else 0.0
            member_old_ratio_2025 = member_old_gsv_2025 / ch_total_gsv_2025 if ch_total_gsv_2025 > 0 else 0.0
            channel_member.append({
                "channel": channel,
                "gsv_2026": gsv_2026,
                "gsv_2025": gsv_2025,
                "yoy": yoy_absolute(gsv_2026, gsv_2025),
                "ratio_2026": round(ratio_2026, 4),
                "ratio_2025": round(ratio_2025, 4),
                "ratio_yoy": yoy_ratio(ratio_2026, ratio_2025),
                "users_2026": users_2026,
                "users_2025": users_2025,
                "users_yoy": yoy_absolute(users_2026, users_2025),
                "aus_2026": round(aus_2026, 2),
                "aus_2025": round(aus_2025, 2),
                "aus_yoy": yoy_absolute(aus_2026, aus_2025),
                "member_ratio_2026": round(member_ratio_2026, 4),
                "member_ratio_2025": round(member_ratio_2025, 4),
                "member_ratio_yoy": yoy_ratio(member_ratio_2026, member_ratio_2025),
                "new_gsv_2026": member_new_gsv_2026,
                "new_gsv_2025": member_new_gsv_2025,
                "new_gsv_yoy": yoy_absolute(member_new_gsv_2026, member_new_gsv_2025),
                "new_gsv_ratio_2026": round(member_new_ratio_2026, 4),
                "new_gsv_ratio_2025": round(member_new_ratio_2025, 4),
                "new_gsv_ratio_yoy": yoy_ratio(member_new_ratio_2026, member_new_ratio_2025),
                "old_gsv_2026": member_old_gsv_2026,
                "old_gsv_2025": member_old_gsv_2025,
                "old_gsv_yoy": yoy_absolute(member_old_gsv_2026, member_old_gsv_2025),
                "old_gsv_ratio_2026": round(member_old_ratio_2026, 4),
                "old_gsv_ratio_2025": round(member_old_ratio_2025, 4),
                "old_gsv_ratio_yoy": yoy_ratio(member_old_ratio_2026, member_old_ratio_2025),
                "member_new_gsv_2026": member_new_gsv_2026,
                "member_new_gsv_2025": member_new_gsv_2025,
                "member_new_gsv_yoy": yoy_absolute(member_new_gsv_2026, member_new_gsv_2025),
                "member_new_gsv_ratio_2026": round(member_new_ratio_2026, 4),
                "member_new_gsv_ratio_2025": round(member_new_ratio_2025, 4),
                "member_new_gsv_ratio_yoy": yoy_ratio(member_new_ratio_2026, member_new_ratio_2025),
                "member_old_gsv_2026": member_old_gsv_2026,
                "member_old_gsv_2025": member_old_gsv_2025,
                "member_old_gsv_yoy": yoy_absolute(member_old_gsv_2026, member_old_gsv_2025),
                "member_old_gsv_ratio_2026": round(member_old_ratio_2026, 4),
                "member_old_gsv_ratio_2025": round(member_old_ratio_2025, 4),
                "member_old_gsv_ratio_yoy": yoy_ratio(member_old_ratio_2026, member_old_ratio_2025),
                "new_users_2026": member_new_users_2026,
                "new_users_2025": member_new_users_2025,
                "new_users_yoy": yoy_absolute(member_new_users_2026, member_new_users_2025),
                "new_aus_2026": round(member_new_aus_2026, 2),
                "new_aus_2025": round(member_new_aus_2025, 2),
                "new_aus_yoy": yoy_absolute(member_new_aus_2026, member_new_aus_2025),
                "old_users_2026": member_old_users_2026,
                "old_users_2025": member_old_users_2025,
                "old_users_yoy": yoy_absolute(member_old_users_2026, member_old_users_2025),
                "old_aus_2026": round(member_old_aus_2026, 2),
                "old_aus_2025": round(member_old_aus_2025, 2),
                "old_aus_yoy": yoy_absolute(member_old_aus_2026, member_old_aus_2025),
            })
        else:
            for ch in CHANNEL_ORDER:
                db_key = next((k for k in all_cur if DB_TO_UI.get(k, "") == ch), None)
                db_key_comp = next((k for k in all_comp if DB_TO_UI.get(k, "") == ch), None)
                r_cur = all_cur.get(db_key, (0,) * 11) if db_key else (0,) * 11
                r_comp = all_comp.get(db_key_comp, (0,) * 11) if db_key_comp else (0,) * 11
                gsv_2026 = _n(r_cur[7])
                gsv_2025 = _n(r_comp[7])
                users_2026 = _safe_int(r_cur[6])
                users_2025 = _safe_int(r_comp[6])
                aus_2026 = _n(r_cur[8])
                aus_2025 = _n(r_comp[8])
                ch_total_gsv_2026 = _n(r_cur[1])
                ch_total_gsv_2025 = _n(r_comp[1])
                member_old_gsv_2026 = _n(r_cur[10])
                member_old_gsv_2025 = _n(r_comp[10])
                member_new_gsv_2026 = gsv_2026 - member_old_gsv_2026
                member_new_gsv_2025 = gsv_2025 - member_old_gsv_2025
                member_old_users_2026 = _safe_int(r_cur[9])
                member_old_users_2025 = _safe_int(r_comp[9])
                member_old_aus_2026 = member_old_gsv_2026 / member_old_users_2026 if member_old_users_2026 > 0 else 0.0
                member_old_aus_2025 = member_old_gsv_2025 / member_old_users_2025 if member_old_users_2025 > 0 else 0.0
                member_new_users_2026 = max(0, users_2026 - member_old_users_2026)
                member_new_users_2025 = max(0, users_2025 - member_old_users_2025)
                member_new_aus_2026 = member_new_gsv_2026 / member_new_users_2026 if member_new_users_2026 > 0 else 0.0
                member_new_aus_2025 = member_new_gsv_2025 / member_new_users_2025 if member_new_users_2025 > 0 else 0.0
                if ch_total_gsv_2026 == 0 and ch_total_gsv_2025 == 0:
                    continue
                ratio_2026 = gsv_2026 / mem_total_gsv if mem_total_gsv > 0 else 0.0
                ratio_2025 = gsv_2025 / mem_comp_total_gsv if mem_comp_total_gsv > 0 else 0.0
                member_ratio_2026 = gsv_2026 / ch_total_gsv_2026 if ch_total_gsv_2026 > 0 else 0.0
                member_ratio_2025 = gsv_2025 / ch_total_gsv_2025 if ch_total_gsv_2025 > 0 else 0.0
                # 会员新客/老客 GSV 占全店 GSV 的比例
                member_new_ratio_2026 = member_new_gsv_2026 / ch_total_gsv_2026 if ch_total_gsv_2026 > 0 else 0.0
                member_new_ratio_2025 = member_new_gsv_2025 / ch_total_gsv_2025 if ch_total_gsv_2025 > 0 else 0.0
                member_old_ratio_2026 = member_old_gsv_2026 / ch_total_gsv_2026 if ch_total_gsv_2026 > 0 else 0.0
                member_old_ratio_2025 = member_old_gsv_2025 / ch_total_gsv_2025 if ch_total_gsv_2025 > 0 else 0.0
                channel_member.append({
                    "channel": ch,
                    "gsv_2026": gsv_2026,
                    "gsv_2025": gsv_2025,
                    "yoy": yoy_absolute(gsv_2026, gsv_2025),
                    "ratio_2026": round(ratio_2026, 4),
                    "ratio_2025": round(ratio_2025, 4),
                    "ratio_yoy": yoy_ratio(ratio_2026, ratio_2025),
                    "users_2026": users_2026,
                    "users_2025": users_2025,
                    "users_yoy": yoy_absolute(users_2026, users_2025),
                    "aus_2026": round(aus_2026, 2),
                    "aus_2025": round(aus_2025, 2),
                    "aus_yoy": yoy_absolute(aus_2026, aus_2025),
                    "member_ratio_2026": round(member_ratio_2026, 4),
                    "member_ratio_2025": round(member_ratio_2025, 4),
                    "member_ratio_yoy": yoy_ratio(member_ratio_2026, member_ratio_2025),
                    # 复用全店列定义：new/old GSV 在会员视角下 = 会员新客/老客 GSV
                    "new_gsv_2026": member_new_gsv_2026,
                    "new_gsv_2025": member_new_gsv_2025,
                    "new_gsv_yoy": yoy_absolute(member_new_gsv_2026, member_new_gsv_2025),
                    "new_gsv_ratio_2026": round(member_new_ratio_2026, 4),
                    "new_gsv_ratio_2025": round(member_new_ratio_2025, 4),
                    "new_gsv_ratio_yoy": yoy_ratio(member_new_ratio_2026, member_new_ratio_2025),
                    "old_gsv_2026": member_old_gsv_2026,
                    "old_gsv_2025": member_old_gsv_2025,
                    "old_gsv_yoy": yoy_absolute(member_old_gsv_2026, member_old_gsv_2025),
                    "old_gsv_ratio_2026": round(member_old_ratio_2026, 4),
                    "old_gsv_ratio_2025": round(member_old_ratio_2025, 4),
                    "old_gsv_ratio_yoy": yoy_ratio(member_old_ratio_2026, member_old_ratio_2025),
                    # 原始会员字段保留（供扩展列使用）
                    "member_new_gsv_2026": member_new_gsv_2026,
                    "member_new_gsv_2025": member_new_gsv_2025,
                    "member_new_gsv_yoy": yoy_absolute(member_new_gsv_2026, member_new_gsv_2025),
                    "member_new_gsv_ratio_2026": round(member_new_ratio_2026, 4),
                    "member_new_gsv_ratio_2025": round(member_new_ratio_2025, 4),
                    "member_new_gsv_ratio_yoy": yoy_ratio(member_new_ratio_2026, member_new_ratio_2025),
                "member_old_gsv_2026": member_old_gsv_2026,
                "member_old_gsv_2025": member_old_gsv_2025,
                "member_old_gsv_yoy": yoy_absolute(member_old_gsv_2026, member_old_gsv_2025),
                "member_old_gsv_ratio_2026": round(member_old_ratio_2026, 4),
                "member_old_gsv_ratio_2025": round(member_old_ratio_2025, 4),
                "member_old_gsv_ratio_yoy": yoy_ratio(member_old_ratio_2026, member_old_ratio_2025),
                "new_users_2026": member_new_users_2026,
                "new_users_2025": member_new_users_2025,
                "new_users_yoy": yoy_absolute(member_new_users_2026, member_new_users_2025),
                "new_aus_2026": round(member_new_aus_2026, 2),
                "new_aus_2025": round(member_new_aus_2025, 2),
                "new_aus_yoy": yoy_absolute(member_new_aus_2026, member_new_aus_2025),
                "old_users_2026": member_old_users_2026,
                "old_users_2025": member_old_users_2025,
                "old_users_yoy": yoy_absolute(member_old_users_2026, member_old_users_2025),
                "old_aus_2026": round(member_old_aus_2026, 2),
                "old_aus_2025": round(member_old_aus_2025, 2),
                "old_aus_yoy": yoy_absolute(member_old_aus_2026, member_old_aus_2025),
            })

        # ─── Panel C TTL: 会员汇总行 ────────────────────────────────
        # TTL 行的 ratio_2026/ratio_2025 固定为 1.0（占会员总盘子100%）
        # member_ratio_2026/2025 也固定为 1.0（会员 GSV 占全渠道会员 GSV 的 100%）
        ttl_mem_cur = all_cur.get("__TOTAL__", (0,) * 11)
        ttl_mem_comp = all_comp.get("__TOTAL__", (0,) * 11)
        ttl_mem_users_2026 = _safe_int(ttl_mem_cur[6])
        ttl_mem_users_2025 = _safe_int(ttl_mem_comp[6])
        ttl_mem_aus_2026 = _n(ttl_mem_cur[8])
        ttl_mem_aus_2025 = _n(ttl_mem_comp[8])
        ttl_mem_old_gsv_2026 = _n(ttl_mem_cur[10])
        ttl_mem_old_gsv_2025 = _n(ttl_mem_comp[10])
        ttl_mem_old_users_2026 = _safe_int(ttl_mem_cur[9])
        ttl_mem_old_users_2025 = _safe_int(ttl_mem_comp[9])
        ttl_mem_old_aus_2026 = ttl_mem_old_gsv_2026 / ttl_mem_old_users_2026 if ttl_mem_old_users_2026 > 0 else 0.0
        ttl_mem_old_aus_2025 = ttl_mem_old_gsv_2025 / ttl_mem_old_users_2025 if ttl_mem_old_users_2025 > 0 else 0.0
        ttl_mem_new_gsv_2026 = mem_total_gsv - ttl_mem_old_gsv_2026
        ttl_mem_new_gsv_2025 = mem_comp_total_gsv - ttl_mem_old_gsv_2025
        ttl_mem_new_users_2026 = max(0, ttl_mem_users_2026 - ttl_mem_old_users_2026)
        ttl_mem_new_users_2025 = max(0, ttl_mem_users_2025 - ttl_mem_old_users_2025)
        ttl_mem_new_aus_2026 = ttl_mem_new_gsv_2026 / ttl_mem_new_users_2026 if ttl_mem_new_users_2026 > 0 else 0.0
        ttl_mem_new_aus_2025 = ttl_mem_new_gsv_2025 / ttl_mem_new_users_2025 if ttl_mem_new_users_2025 > 0 else 0.0
        ttl_mem_new_ratio_2026 = ttl_mem_new_gsv_2026 / mem_total_gsv if mem_total_gsv > 0 else 0.0
        ttl_mem_new_ratio_2025 = ttl_mem_new_gsv_2025 / mem_comp_total_gsv if mem_comp_total_gsv > 0 else 0.0
        ttl_mem_old_ratio_2026 = ttl_mem_old_gsv_2026 / mem_total_gsv if mem_total_gsv > 0 else 0.0
        ttl_mem_old_ratio_2025 = ttl_mem_old_gsv_2025 / mem_comp_total_gsv if mem_comp_total_gsv > 0 else 0.0
        channel_member.append({
            "channel": "TTL",
            "gsv_2026": mem_total_gsv,
            "gsv_2025": mem_comp_total_gsv,
            "yoy": yoy_absolute(mem_total_gsv, mem_comp_total_gsv),
            "ratio_2026": 1.0,
            "ratio_2025": 1.0,
            "ratio_yoy": yoy_ratio(1.0, 1.0),
            "users_2026": ttl_mem_users_2026,
            "users_2025": ttl_mem_users_2025,
            "users_yoy": yoy_absolute(ttl_mem_users_2026, ttl_mem_users_2025),
            "aus_2026": round(ttl_mem_aus_2026, 2),
            "aus_2025": round(ttl_mem_aus_2025, 2),
            "aus_yoy": yoy_absolute(ttl_mem_aus_2026, ttl_mem_aus_2025),
            "member_ratio_2026": round(safe_ratio(mem_total_gsv, all_total_gsv), 4),
            "member_ratio_2025": round(safe_ratio(mem_comp_total_gsv, all_comp_total_gsv), 4),
            "member_ratio_yoy": yoy_ratio(safe_ratio(mem_total_gsv, all_total_gsv), safe_ratio(mem_comp_total_gsv, all_comp_total_gsv)),
            # 复用全店列定义：占比 = 会员新客/老客 / 会员总GSV
            "new_gsv_2026": ttl_mem_new_gsv_2026,
            "new_gsv_2025": ttl_mem_new_gsv_2025,
            "new_gsv_yoy": yoy_absolute(ttl_mem_new_gsv_2026, ttl_mem_new_gsv_2025),
            "new_gsv_ratio_2026": round(ttl_mem_new_ratio_2026, 4),
            "new_gsv_ratio_2025": round(ttl_mem_new_ratio_2025, 4),
            "new_gsv_ratio_yoy": yoy_ratio(ttl_mem_new_ratio_2026, ttl_mem_new_ratio_2025),
            "old_gsv_2026": ttl_mem_old_gsv_2026,
            "old_gsv_2025": ttl_mem_old_gsv_2025,
            "old_gsv_yoy": yoy_absolute(ttl_mem_old_gsv_2026, ttl_mem_old_gsv_2025),
            "old_gsv_ratio_2026": round(ttl_mem_old_ratio_2026, 4),
            "old_gsv_ratio_2025": round(ttl_mem_old_ratio_2025, 4),
            "old_gsv_ratio_yoy": yoy_ratio(ttl_mem_old_ratio_2026, ttl_mem_old_ratio_2025),
            "new_users_2026": ttl_mem_new_users_2026,
            "new_users_2025": ttl_mem_new_users_2025,
            "new_users_yoy": yoy_absolute(ttl_mem_new_users_2026, ttl_mem_new_users_2025),
            "new_aus_2026": round(ttl_mem_new_aus_2026, 2),
            "new_aus_2025": round(ttl_mem_new_aus_2025, 2),
            "new_aus_yoy": yoy_absolute(ttl_mem_new_aus_2026, ttl_mem_new_aus_2025),
            "old_users_2026": ttl_mem_old_users_2026,
            "old_users_2025": ttl_mem_old_users_2025,
            "old_users_yoy": yoy_absolute(ttl_mem_old_users_2026, ttl_mem_old_users_2025),
            "old_aus_2026": round(ttl_mem_old_aus_2026, 2),
            "old_aus_2025": round(ttl_mem_old_aus_2025, 2),
            "old_aus_yoy": yoy_absolute(ttl_mem_old_aus_2026, ttl_mem_old_aus_2025),
            # 原始会员字段保留
            "member_new_gsv_2026": ttl_mem_new_gsv_2026,
            "member_new_gsv_2025": ttl_mem_new_gsv_2025,
            "member_new_gsv_yoy": yoy_absolute(ttl_mem_new_gsv_2026, ttl_mem_new_gsv_2025),
            "member_new_gsv_ratio_2026": round(ttl_mem_new_ratio_2026, 4),
            "member_new_gsv_ratio_2025": round(ttl_mem_new_ratio_2025, 4),
            "member_new_gsv_ratio_yoy": yoy_ratio(ttl_mem_new_ratio_2026, ttl_mem_new_ratio_2025),
            "member_old_gsv_2026": ttl_mem_old_gsv_2026,
            "member_old_gsv_2025": ttl_mem_old_gsv_2025,
            "member_old_gsv_yoy": yoy_absolute(ttl_mem_old_gsv_2026, ttl_mem_old_gsv_2025),
            "member_old_gsv_ratio_2026": round(ttl_mem_old_ratio_2026, 4),
            "member_old_gsv_ratio_2025": round(ttl_mem_old_ratio_2025, 4),
            "member_old_gsv_ratio_yoy": yoy_ratio(ttl_mem_old_ratio_2026, ttl_mem_old_ratio_2025),
        })

        # ─── 交叉指标：会员 vs 全店 ─────────────────────────────────
        # 前端不再计算，由后端统一返回
        all_gsv_map = {r["channel"]: r for r in channel_all if r["channel"] != "TTL"}
        all_ttl_row = channel_all[-1] if channel_all and channel_all[-1]["channel"] == "TTL" else {}
        for m_row in channel_member:
            if m_row["channel"] == "TTL":
                a_row = all_ttl_row
            else:
                a_row = all_gsv_map.get(m_row["channel"], {})
            all_new_2026 = a_row.get("new_gsv_2026", 0)
            all_new_2025 = a_row.get("new_gsv_2025", 0)
            all_old_2026 = a_row.get("old_gsv_2026", 0)
            all_old_2025 = a_row.get("old_gsv_2025", 0)
            mn_2026 = m_row.get("member_new_gsv_2026", 0)
            mn_2025 = m_row.get("member_new_gsv_2025", 0)
            mo_2026 = m_row.get("member_old_gsv_2026", 0)
            mo_2025 = m_row.get("member_old_gsv_2025", 0)
            m_row["member_new_vs_all_new_2026"] = round(safe_ratio(mn_2026, all_new_2026), 4)
            m_row["member_new_vs_all_new_2025"] = round(safe_ratio(mn_2025, all_new_2025), 4)
            m_row["member_new_vs_all_new_yoy"] = yoy_ratio(m_row["member_new_vs_all_new_2026"], m_row["member_new_vs_all_new_2025"])
            m_row["member_old_vs_all_old_2026"] = round(safe_ratio(mo_2026, all_old_2026), 4)
            m_row["member_old_vs_all_old_2025"] = round(safe_ratio(mo_2025, all_old_2025), 4)
            m_row["member_old_vs_all_old_yoy"] = yoy_ratio(m_row["member_old_vs_all_old_2026"], m_row["member_old_vs_all_old_2025"])

        return {
            "year_label": current_year_label,
            "comp_year_label": comp_year_label,
            "prev2_year_label": prev2_year_label,
            "metric_type": metric_type,
            "indicators": indicators,
            "channel_all": channel_all,
            "channel_member": channel_member,
        }
    finally:
        conn.close()


if __name__ == "__main__":
    # 测试
    for metric_type in ["GMV", "GSV"]:
        print(f"\n=== {metric_type} 测试 ===")
        result = get_overview_metrics("2026-01-01", "2026-01-31", metric_type)
        print(f"金额: {result['amount']:,.2f}")
        print(f"订单: {result['order_count']:,}")
        print(f"会员金额: {result['member_amount']:,.2f}")
    # 人群看板测试
    print("\n=== 人群看板 MTD 测试 ===")
    audience = get_audience_table(dimension="channel", mode="mtd")
    print(f"当前期: {audience['current_period']}")
    print(f"对比期: {audience['comparison_period']}")
    for row in audience['rows'][:3]:
        print(f"  {row['dimension']}: GSV={row['gsv']:,.0f} 老客占比={row['old_gsv_ratio']:.1%}")
