"""指标服务 - 概览指标
calculate_metrics, get_overview_metrics, get_daily_trend, get_product_metrics
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from dateutil.relativedelta import relativedelta
from backend.db.connection import get_connection
from backend.semantic.filters import FilterBuilder, MetricType
from backend.semantic.calculations import yoy_ratio, yoy_absolute, mom_absolute, mom_ratio


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
        # Sprint 97 fix: channel 加 o. 前缀, 配 JOIN 兼容 (避免 channel 字段 ambiguous)
        where_sql = where_sql.replace("channel IN (", "o.channel IN (")
        where_sql = where_sql.replace("channel NOT IN (", "o.channel NOT IN (")

        amount_expr = fb.build_amount_expr()
        count_expr = fb.build_count_expr()

        result = conn.execute(f"""
            SELECT
                {amount_expr} as total_amount,
                {count_expr} as order_count,
                AVG(actual_amount) as avg_order_value
            FROM orders o
            WHERE {where_sql}
        """, params).fetchone()

        return {
            "amount": float(result[0]) if result[0] else 0,
            "order_count": int(result[1]) if result[1] else 0,
            "avg_order_value": float(result[2]) if result[2] else 0
        }
    finally:
        pass


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
    from datetime import timedelta

    conn = get_connection()
    try:
        start_dt_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        cutoff_date = (start_dt_obj - timedelta(days=1)).strftime("%Y-%m-%d")

        # Sprint 54 Lane A L3: 用 FilterBuilder.build() 替代 f-string 拼接
        # (time_sql, valid_sql, ch_sql 三段全部走 ? 参数化).
        fb = FilterBuilder()
        fb.with_metric_type(MetricType.GSV)
        fb.with_time_range(start_date, end_date)
        if channel and channel != "全店":
            fb.with_channels([channel])
        if exclude_channels:
            fb.with_exclude_channels(exclude_channels)
        where_sql, where_params = fb.build()
        # Sprint 97 fix: channel 加 o. 前缀, 配 JOIN 兼容 (避免 channel 字段 ambiguous)
        where_sql = where_sql.replace("channel IN (", "o.channel IN (")
        where_sql = where_sql.replace("channel NOT IN (", "o.channel NOT IN (")

        result = conn.execute(f"""
            WITH period_users AS (
                SELECT
                    o.user_id,
                    SUM(o.actual_amount) as period_amount
                FROM orders o
                JOIN user_first_purchase u ON o.user_id = u.user_id
                WHERE {where_sql}
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
        """, where_params + [cutoff_date]).fetchone()

        return {
            "new_user_count": int(result[0]) if result[0] else 0,
            "old_user_count": int(result[1]) if result[1] else 0,
            "new_user_amount": float(result[2]) if result[2] else 0.0,
            "old_user_amount": float(result[3]) if result[3] else 0.0,
        }
    finally:
        pass


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
        # Sprint 97 fix: channel 加 o. 前缀, 配 JOIN 兼容 (避免 channel 字段 ambiguous)
        where_sql = where_sql.replace("channel IN (", "o.channel IN (")
        where_sql = where_sql.replace("channel NOT IN (", "o.channel NOT IN (")

        amount_expr = fb.build_amount_expr()
        count_expr = fb.build_count_expr()

        result = conn.execute(f"""
            SELECT
                COUNT(DISTINCT user_id) as member_count,
                {amount_expr} as member_amount,
                {count_expr} as member_order_count
            FROM orders o
            WHERE {where_sql}
        """, params).fetchone()

        return {
            "member_count": int(result[0]) if result[0] else 0,
            "member_amount": float(result[1]) if result[1] else 0,
            "member_order_count": int(result[2]) if result[2] else 0
        }
    finally:
        pass


def _query_period(conn, start_date: str, end_date: str, metric_type: str,
                  channel: Optional[str], exclude_channels: Optional[List[str]]) -> Dict[str, Any]:
    """
    单次查询返回一个时间段的全部指标（core + new_old + member）。
    使用 CTE + 条件聚合，将原本 3 次独立查询合并为 1 次。
    """
    # 使用 GMV 基础过滤（最宽泛）作为 WHERE 条件
    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GMV)
    fb.with_time_range(start_date, end_date)
    if channel and channel != "全店":
        fb.with_channels([channel])
    if exclude_channels:
        fb.with_exclude_channels(exclude_channels)
    where_sql, where_params = fb.build()
    # Sprint 97 fix: channel 加 o. 前缀, 配 JOIN 兼容 (避免 channel 字段 ambiguous)
    where_sql = where_sql.replace("channel IN (", "o.channel IN (")
    where_sql = where_sql.replace("channel NOT IN (", "o.channel NOT IN (")

    # GSV 模式需额外排除退款订单；GMV 模式包含退款
    gsv_cond = "is_refund = FALSE" if metric_type == "GSV" else "TRUE"

    # 新老客分类截止日（与 calculate_new_old_users 口径一致）
    start_dt_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
    cutoff_date = (start_dt_obj - timedelta(days=1)).strftime("%Y-%m-%d")

    sql = f"""
        WITH base AS (
            SELECT
                o.order_id, o.user_id, o.actual_amount,
                o.is_member, o.is_refund,
                u.first_pay_date
            FROM orders o
            LEFT JOIN user_first_purchase u ON o.user_id = u.user_id
            WHERE {where_sql}
        )
        SELECT
            -- 核心指标（GMV: 全量 / GSV: 排除退款）
            SUM(CASE WHEN {gsv_cond} THEN actual_amount ELSE 0 END)            AS amount,
            COUNT(DISTINCT CASE WHEN {gsv_cond} THEN order_id END)              AS order_count,
            AVG(CASE WHEN {gsv_cond} THEN actual_amount END)                    AS avg_order_value,
            -- 新老客（始终使用 valid_order 口径，即排除退款）
            COUNT(DISTINCT CASE WHEN is_refund = FALSE
                            AND first_pay_date > ?::DATE THEN user_id END)      AS new_user_count,
            COUNT(DISTINCT CASE WHEN is_refund = FALSE
                            AND first_pay_date <= ?::DATE THEN user_id END)     AS old_user_count,
            COALESCE(SUM(CASE WHEN is_refund = FALSE
                            AND first_pay_date > ?::DATE THEN actual_amount
                             ELSE 0 END), 0)                                    AS new_user_amount,
            COALESCE(SUM(CASE WHEN is_refund = FALSE
                            AND first_pay_date <= ?::DATE THEN actual_amount
                             ELSE 0 END), 0)                                    AS old_user_amount,
            -- 会员指标
            COUNT(DISTINCT CASE WHEN is_member = TRUE
                            AND {gsv_cond} THEN user_id END)                    AS member_count,
            SUM(CASE WHEN is_member = TRUE
                            AND {gsv_cond} THEN actual_amount ELSE 0 END)       AS member_amount,
            COUNT(DISTINCT CASE WHEN is_member = TRUE
                            AND {gsv_cond} THEN order_id END)                   AS member_order_count
        FROM base
    """

    all_params = where_params + [cutoff_date] * 4
    result = conn.execute(sql, all_params).fetchone()

    if result is None:
        return {
            "amount": 0, "order_count": 0, "avg_order_value": 0,
            "new_user_count": 0, "old_user_count": 0,
            "new_user_amount": 0.0, "old_user_amount": 0.0,
            "member_count": 0, "member_amount": 0, "member_order_count": 0,
        }

    return {
        "amount": float(result[0]) if result[0] is not None else 0,
        "order_count": int(result[1]) if result[1] is not None else 0,
        "avg_order_value": float(result[2]) if result[2] is not None else 0,
        "new_user_count": int(result[3]) if result[3] is not None else 0,
        "old_user_count": int(result[4]) if result[4] is not None else 0,
        "new_user_amount": float(result[5]) if result[5] is not None else 0.0,
        "old_user_amount": float(result[6]) if result[6] is not None else 0.0,
        "member_count": int(result[7]) if result[7] is not None else 0,
        "member_amount": float(result[8]) if result[8] is not None else 0,
        "member_order_count": int(result[9]) if result[9] is not None else 0,
    }


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

    每个时间段（当期 / 环比 / 同比）各执行 1 次合并查询，共 3 次。
    """
    conn = get_connection()

    # ── 当期（1 次查询取代原来的 3 次）──
    current = _query_period(conn, start_date, end_date, metric_type, channel, exclude_channels)

    # ── 环比期（1 次查询）──
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    period_days = (end_dt - start_dt).days + 1

    prev_start = (start_dt - timedelta(days=period_days)).strftime("%Y-%m-%d")
    prev_end = (start_dt - timedelta(days=1)).strftime("%Y-%m-%d")
    prev = _query_period(conn, prev_start, prev_end, metric_type, channel, exclude_channels)

    mom_amount = mom_absolute(current['amount'], prev['amount']) or 0
    mom_orders = mom_absolute(current['order_count'], prev['order_count']) or 0
    mom_old_amount = mom_absolute(current['old_user_amount'], prev['old_user_amount']) or 0
    mom_new_amount = mom_absolute(current['new_user_amount'], prev['new_user_amount']) or 0
    mom_member_amount = mom_absolute(current['member_amount'], prev['member_amount']) or 0
    # 占比（小数形式，如 0.75 表示 75%）
    curr_old_ratio = current['old_user_amount'] / current['amount'] if current['amount'] > 0 else 0
    curr_new_ratio = current['new_user_amount'] / current['amount'] if current['amount'] > 0 else 0
    curr_member_ratio = current['member_amount'] / current['amount'] if current['amount'] > 0 else 0
    prev_old_ratio = prev['old_user_amount'] / prev['amount'] if prev['amount'] > 0 else 0
    prev_new_ratio = prev['new_user_amount'] / prev['amount'] if prev['amount'] > 0 else 0
    prev_member_ratio = prev['member_amount'] / prev['amount'] if prev['amount'] > 0 else 0
    mom_old_ratio = mom_ratio(curr_old_ratio, prev_old_ratio) or 0
    mom_new_ratio = mom_ratio(curr_new_ratio, prev_new_ratio) or 0
    mom_member_ratio = mom_ratio(curr_member_ratio, prev_member_ratio) or 0

    # 会员溢价 = 会员AUS / 全店AUS（比值，不乘100）
    member_avg_order_value = current['member_amount'] / current['member_order_count'] if current['member_order_count'] > 0 else 0
    member_premium = member_avg_order_value / current['avg_order_value'] if current['avg_order_value'] > 0 else 0
    prev_member_avg = prev['member_amount'] / prev['member_order_count'] if prev['member_order_count'] > 0 else 0
    prev_member_premium = prev_member_avg / prev['avg_order_value'] if prev['avg_order_value'] > 0 else 0
    mom_member_premium = mom_absolute(member_premium, prev_member_premium) or 0

    # ── 同比期（1 次查询，支持自定义对比期覆盖 Y-1 推算）──
    if compare_start_date and compare_end_date:
        last_year_start = compare_start_date
        last_year_end = compare_end_date
    else:
        last_year_start = (start_dt - relativedelta(years=1)).strftime("%Y-%m-%d")
        last_year_end = (end_dt - relativedelta(years=1)).strftime("%Y-%m-%d")
    last_year = _query_period(conn, last_year_start, last_year_end, metric_type, channel, exclude_channels)

    yoy_amount = yoy_absolute(current['amount'], last_year['amount']) or 0
    yoy_orders = yoy_absolute(current['order_count'], last_year['order_count']) or 0
    yoy_old_amount = yoy_absolute(current['old_user_amount'], last_year['old_user_amount']) or 0
    yoy_new_amount = yoy_absolute(current['new_user_amount'], last_year['new_user_amount']) or 0
    yoy_member_amount = yoy_absolute(current['member_amount'], last_year['member_amount']) or 0
    ly_old_ratio = last_year['old_user_amount'] / last_year['amount'] if last_year['amount'] > 0 else 0
    ly_new_ratio = last_year['new_user_amount'] / last_year['amount'] if last_year['amount'] > 0 else 0
    ly_member_ratio = last_year['member_amount'] / last_year['amount'] if last_year['amount'] > 0 else 0
    yoy_old_ratio = yoy_ratio(curr_old_ratio, ly_old_ratio) or 0
    yoy_new_ratio = yoy_ratio(curr_new_ratio, ly_new_ratio) or 0
    yoy_member_ratio = yoy_ratio(curr_member_ratio, ly_member_ratio) or 0

    ly_member_avg = last_year['member_amount'] / last_year['member_order_count'] if last_year['member_order_count'] > 0 else 0
    ly_member_premium = ly_member_avg / last_year['avg_order_value'] if last_year['avg_order_value'] > 0 else 0
    # 会员溢价 YoY（比值跑 yoy_absolute 返回百分比变化率）
    yoy_member_premium = yoy_absolute(member_premium, ly_member_premium) or 0

    return {
        "metric_type": metric_type,
        "date_range": {"start": start_date, "end": end_date},
        "amount": round(current['amount'], 2),
        "order_count": current['order_count'],
        "avg_order_value": round(current['avg_order_value'], 2),
        "new_users": current['new_user_count'],
        "old_users": current['old_user_count'],
        "new_user_amount": round(current['new_user_amount'], 2),
        "old_user_amount": round(current['old_user_amount'], 2),
        "member_amount": round(current['member_amount'], 2),
        "member_count": current['member_count'],
        "member_order_count": current['member_order_count'],
        # Sprint 14.5 治根: service /100 同步 RatioField 0-1 contract (codex P0 建议)
        "old_user_ratio": round(curr_old_ratio, 4),
        "new_user_ratio": round(curr_new_ratio, 4),
        "member_ratio": round(curr_member_ratio, 4),
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
        # Sprint 97 fix: channel 加 o. 前缀, 配 JOIN 兼容 (避免 channel 字段 ambiguous)
        where_sql = where_sql.replace("channel IN (", "o.channel IN (")
        where_sql = where_sql.replace("channel NOT IN (", "o.channel NOT IN (")

        amount_expr = fb.build_amount_expr()

        from backend.semantic.filters import AmountExprBuilder
        member_amount_expr = f"SUM(CASE WHEN is_member = TRUE THEN {AmountExprBuilder.gsv() if metric_type == 'GSV' else 'actual_amount'} ELSE 0 END)"

        result = conn.execute(f"""
            SELECT
                DATE(pay_time) as date,
                {amount_expr} as daily_amount,
                {member_amount_expr} as member_amount,
                COUNT(DISTINCT CASE WHEN is_member = TRUE THEN order_id END) as member_orders,
                COUNT(DISTINCT order_id) as daily_orders
            FROM orders o
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
        # Sprint 97 fix: channel 加 o. 前缀, 配 JOIN 兼容 (避免 channel 字段 ambiguous)
        where_ly = where_ly.replace("channel IN (", "o.channel IN (")
        where_ly = where_ly.replace("channel NOT IN (", "o.channel NOT IN (")
        amount_ly = fb_ly.build_amount_expr()

        member_amount_ly_expr = f"SUM(CASE WHEN is_member = TRUE THEN {AmountExprBuilder.gsv() if metric_type == 'GSV' else 'actual_amount'} ELSE 0 END)"

        result_ly = conn.execute(f"""
            SELECT
                DATE(pay_time) as date,
                {amount_ly} as daily_amount,
                {member_amount_ly_expr} as member_amount,
                COUNT(DISTINCT CASE WHEN is_member = TRUE THEN order_id END) as member_orders,
                COUNT(DISTINCT order_id) as daily_orders
            FROM orders o
            WHERE {where_ly}
            GROUP BY DATE(pay_time)
            ORDER BY date
        """, params_ly).fetchall()

        # 今年会员GSV占比（0-1 decimal, 跟 Sprint 14.5 OverviewMetrics.member_ratio 治根路线一致;
        # Sprint 27 借机补: 之前 service 端 ×100 返 0-100 percentage, 违反 CLAUDE.md Ratio Convention;
        # 现在改 0-1 decimal, 前端展示层 (tooltip / Y 轴 formatter) 自己 ×100)
        member_ratios = []
        for r in result:
            total_amount = r[1] if r[1] else 0
            member_amount = r[2] if r[2] else 0
            ratio = (member_amount / total_amount) if total_amount > 0 else 0
            member_ratios.append(round(ratio, 4))

        # 去年同周期会员GSV占比（0-1 decimal, 跟 member_ratios 对齐）
        ly_member_ratios = []
        for r in result_ly:
            total_amount = r[1] if r[1] else 0
            member_amount = r[2] if r[2] else 0
            ratio = (member_amount / total_amount) if total_amount > 0 else 0
            ly_member_ratios.append(round(ratio, 4))

        # 计算整体会员GSV占比（与人群看板一致, 0-1 decimal）
        total_amount = sum(float(r[1]) for r in result) if result else 0
        total_member_amount = sum(float(r[2]) for r in result) if result else 0
        overall_member_ratio = round(total_member_amount / total_amount, 4) if total_amount > 0 else 0

        total_amount_ly = sum(float(r[1]) for r in result_ly) if result_ly else 0
        total_member_amount_ly = sum(float(r[2]) for r in result_ly) if result_ly else 0
        overall_member_ratio_ly = round(total_member_amount_ly / total_amount_ly, 4) if total_amount_ly > 0 else 0

        return {
            "metric_type": metric_type,
            "dates": [str(r[0]) for r in result],
            "amounts": [float(r[1]) for r in result],
            "member_ratios": member_ratios,
            "overall_member_ratio": overall_member_ratio,
            "ly_amounts": [float(r[1]) for r in result_ly],
            "ly_member_ratios": ly_member_ratios,
            "overall_member_ratio_ly": overall_member_ratio_ly,
        }
    finally:
        pass

def get_product_metrics(start_date: str, end_date: str, limit: int = 20) -> Dict[str, Any]:
    """获取单品 metrics（按 GMV/GSV 排名，参数化查询）"""
    conn = get_connection()
    try:
        # 使用 FilterBuilder 构建统一过滤条件（默认 GMV）
        fb = FilterBuilder()
        fb.with_metric_type(MetricType.GMV)
        fb.with_time_range(start_date, end_date)
        where_sql, params = fb.build()
        # Sprint 97 fix: channel 加 o. 前缀, 配 JOIN 兼容 (避免 channel 字段 ambiguous)
        where_sql = where_sql.replace("channel IN (", "o.channel IN (")
        where_sql = where_sql.replace("channel NOT IN (", "o.channel NOT IN (")

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
            FROM orders o
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
        pass
