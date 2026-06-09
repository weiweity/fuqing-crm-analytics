"""指标服务 - 人群汇总
calculate_audience_summary
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from backend.db.connection import get_connection
from backend.semantic.filters import OrderFilters
from backend.semantic.calculations import yoy_ratio, yoy_absolute, safe_ratio
from backend.semantic.time import PeriodBuilder

from ._shared import _expand_channel
from backend.semantic.channels import UI_TO_DB, DB_TO_UI, CHANNEL_ORDER
from .overview import get_overview_metrics
from .audience_table import get_audience_table

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
        date(cur_start_y, cur_start_m, cur_start_d)
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
        comp_year_label = "对比期"
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
            # valid_order() 来自语义层 uniform 口径
            valid_sql, _valid_params = OrderFilters.valid_order()
            where_parts = ["pay_time >= ?::TIMESTAMP", "pay_time <= ?::TIMESTAMP", valid_sql]
            if ch_filter and ch_filter != "全店":
                db_channels = _expand_channel(ch_filter)
                if len(db_channels) == 1:
                    where_parts.append("channel = ?")
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
                "old_gsv_ratio": round(old_gsv / gsv * 100, 2) if gsv > 0 else 0.0,
                "old_users_ratio": round(old_users / gsv_users * 100, 2) if gsv_users > 0 else 0.0,
                "new_gsv": new_gsv, "new_users": new_users, "new_aus": new_aus,
                "new_gsv_ratio": round(new_gsv / gsv * 100, 2) if gsv > 0 else 0.0,
                "new_users_ratio": round(new_users / gsv_users * 100, 2) if gsv_users > 0 else 0.0,
                "member_gsv": member_gsv, "member_users": member_users, "member_aus": member_aus,
                "member_penetration": round(member_users / gsv_users * 100, 2) if gsv_users > 0 else 0.0,
                "member_users_ratio": round(member_users / gsv_users * 100, 2) if gsv_users > 0 else 0.0,
                "member_old_gsv": member_old_gsv, "member_old_users": member_old_users,
                "member_old_aus": member_old_gsv / member_old_users if member_old_users > 0 else 0.0,
                "member_old_gsv_ratio": round(member_old_gsv / member_gsv * 100, 2) if member_gsv > 0 else 0.0,
                "member_old_users_ratio": round(member_old_users / member_users * 100, 2) if member_users > 0 else 0.0,
                "member_new_gsv": member_new_gsv,
                "member_new_users": member_new_users,
                "member_new_aus": member_new_gsv / member_new_users if member_new_users > 0 else 0.0,
                "member_new_gsv_ratio": round(member_new_gsv / member_gsv * 100, 2) if member_gsv > 0 else 0.0,
                "member_new_users_ratio": round(member_new_users / member_users * 100, 2) if member_users > 0 else 0.0,
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
            {"field": "全店GSV",        "kind": "money", "values_by_year": {"2026": cur_m["gsv"], "2025": comp_m["gsv"], "2024": prev2_m["gsv"]},          "yoy": yoy_absolute(cur_m["gsv"], comp_m["gsv"])},
            {"field": "全店人数",       "kind": "count", "values_by_year": {"2026": cur_m["users"], "2025": comp_m["users"], "2024": prev2_m["users"]},        "yoy": yoy_absolute(cur_m["users"], comp_m["users"])},
            {"field": "AUS",           "kind": "aus",   "values_by_year": {"2026": cur_m["aus"], "2025": comp_m["aus"], "2024": prev2_m["aus"]},          "yoy": yoy_absolute(cur_m["aus"], comp_m["aus"])},
            {"field": "老客GSV",       "kind": "money", "values_by_year": {"2026": cur_m["old_gsv"], "2025": comp_m["old_gsv"], "2024": prev2_m["old_gsv"]},      "yoy": yoy_absolute(cur_m["old_gsv"], comp_m["old_gsv"])},
            {"field": "老客人数",       "kind": "count", "values_by_year": {"2026": cur_m["old_users"], "2025": comp_m["old_users"], "2024": prev2_m["old_users"]},    "yoy": yoy_absolute(cur_m["old_users"], comp_m["old_users"])},
            {"field": "老客AUS",       "kind": "aus",   "values_by_year": {"2026": cur_m["old_aus"], "2025": comp_m["old_aus"], "2024": prev2_m["old_aus"]},      "yoy": yoy_absolute(cur_m["old_aus"], comp_m["old_aus"])},
            {"field": "老客GSV占比",   "kind": "ratio", "values_by_year": {"2026": cur_m["old_gsv_ratio"], "2025": comp_m["old_gsv_ratio"], "2024": prev2_m["old_gsv_ratio"]}, "yoy": yoy_ratio(cur_m["old_gsv_ratio"], comp_m["old_gsv_ratio"])},
            {"field": "老客人数占比",   "kind": "ratio", "values_by_year": {"2026": cur_m["old_users_ratio"], "2025": comp_m["old_users_ratio"], "2024": prev2_m["old_users_ratio"]}, "yoy": yoy_ratio(cur_m["old_users_ratio"], comp_m["old_users_ratio"])},
            {"field": "新客GSV",       "kind": "money", "values_by_year": {"2026": cur_m["new_gsv"], "2025": comp_m["new_gsv"], "2024": prev2_m["new_gsv"]},      "yoy": yoy_absolute(cur_m["new_gsv"], comp_m["new_gsv"])},
            {"field": "新客人数",       "kind": "count", "values_by_year": {"2026": cur_m["new_users"], "2025": comp_m["new_users"], "2024": prev2_m["new_users"]},    "yoy": yoy_absolute(cur_m["new_users"], comp_m["new_users"])},
            {"field": "新客AUS",       "kind": "aus",   "values_by_year": {"2026": cur_m["new_aus"], "2025": comp_m["new_aus"], "2024": prev2_m["new_aus"]},      "yoy": yoy_absolute(cur_m["new_aus"], comp_m["new_aus"])},
            {"field": "新客GSV占比",   "kind": "ratio", "values_by_year": {"2026": cur_m["new_gsv_ratio"], "2025": comp_m["new_gsv_ratio"], "2024": prev2_m["new_gsv_ratio"]}, "yoy": yoy_ratio(cur_m["new_gsv_ratio"], comp_m["new_gsv_ratio"])},
            {"field": "新客人数占比",   "kind": "ratio", "values_by_year": {"2026": cur_m["new_users_ratio"], "2025": comp_m["new_users_ratio"], "2024": prev2_m["new_users_ratio"]}, "yoy": yoy_ratio(cur_m["new_users_ratio"], comp_m["new_users_ratio"])},
            {"field": "会员GSV",       "kind": "money", "values_by_year": {"2026": cur_m["member_gsv"], "2025": comp_m["member_gsv"], "2024": prev2_m["member_gsv"]},   "yoy": yoy_absolute(cur_m["member_gsv"], comp_m["member_gsv"])},
            {"field": "会员人数",       "kind": "count", "values_by_year": {"2026": cur_m["member_users"], "2025": comp_m["member_users"], "2024": prev2_m["member_users"]},  "yoy": yoy_absolute(cur_m["member_users"], comp_m["member_users"])},
            {"field": "会员AUS",       "kind": "aus",   "values_by_year": {"2026": cur_m["member_aus"], "2025": comp_m["member_aus"], "2024": prev2_m["member_aus"]},   "yoy": yoy_absolute(cur_m["member_aus"], comp_m["member_aus"])},
            {"field": "会员渗透率",     "kind": "ratio", "values_by_year": {"2026": cur_m["member_penetration"], "2025": comp_m["member_penetration"], "2024": prev2_m["member_penetration"]}, "yoy": yoy_ratio(cur_m["member_penetration"], comp_m["member_penetration"])},
            {"field": "会员人数占比",   "kind": "ratio", "values_by_year": {"2026": cur_m["member_users_ratio"], "2025": comp_m["member_users_ratio"], "2024": prev2_m["member_users_ratio"]}, "yoy": yoy_ratio(cur_m["member_users_ratio"], comp_m["member_users_ratio"])},
            {"field": "会员老客GSV",   "kind": "money", "values_by_year": {"2026": cur_m["member_old_gsv"], "2025": comp_m["member_old_gsv"], "2024": prev2_m["member_old_gsv"]}, "yoy": yoy_absolute(cur_m["member_old_gsv"], comp_m["member_old_gsv"])},
            {"field": "会员老客人数",   "kind": "count", "values_by_year": {"2026": cur_m["member_old_users"], "2025": comp_m["member_old_users"], "2024": prev2_m["member_old_users"]}, "yoy": yoy_absolute(cur_m["member_old_users"], comp_m["member_old_users"])},
            {"field": "会员老客AUS",   "kind": "aus",   "values_by_year": {"2026": cur_m["member_old_aus"], "2025": comp_m["member_old_aus"], "2024": prev2_m["member_old_aus"]}, "yoy": yoy_absolute(cur_m["member_old_aus"], comp_m["member_old_aus"])},
            {"field": "会员老客GSV占比","kind": "ratio", "values_by_year": {"2026": cur_m["member_old_gsv_ratio"], "2025": comp_m["member_old_gsv_ratio"], "2024": prev2_m["member_old_gsv_ratio"]}, "yoy": yoy_ratio(cur_m["member_old_gsv_ratio"], comp_m["member_old_gsv_ratio"])},
            {"field": "会员老客人数占比","kind": "ratio", "values_by_year": {"2026": cur_m["member_old_users_ratio"], "2025": comp_m["member_old_users_ratio"], "2024": prev2_m["member_old_users_ratio"]}, "yoy": yoy_ratio(cur_m["member_old_users_ratio"], comp_m["member_old_users_ratio"])},
            {"field": "会员新客GSV",   "kind": "money", "values_by_year": {"2026": cur_m["member_new_gsv"], "2025": comp_m["member_new_gsv"], "2024": prev2_m["member_new_gsv"]}, "yoy": yoy_absolute(cur_m["member_new_gsv"], comp_m["member_new_gsv"])},
            {"field": "会员新客人数",   "kind": "count", "values_by_year": {"2026": cur_m["member_new_users"], "2025": comp_m["member_new_users"], "2024": prev2_m["member_new_users"]}, "yoy": yoy_absolute(cur_m["member_new_users"], comp_m["member_new_users"])},
            {"field": "会员新客AUS",   "kind": "aus",   "values_by_year": {"2026": cur_m["member_new_aus"], "2025": comp_m["member_new_aus"], "2024": prev2_m["member_new_aus"]}, "yoy": yoy_absolute(cur_m["member_new_aus"], comp_m["member_new_aus"])},
            {"field": "会员新客GSV占比","kind": "ratio", "values_by_year": {"2026": cur_m["member_new_gsv_ratio"], "2025": comp_m["member_new_gsv_ratio"], "2024": prev2_m["member_new_gsv_ratio"]}, "yoy": yoy_ratio(cur_m["member_new_gsv_ratio"], comp_m["member_new_gsv_ratio"])},
            {"field": "会员新客人数占比","kind": "ratio", "values_by_year": {"2026": cur_m["member_new_users_ratio"], "2025": comp_m["member_new_users_ratio"], "2024": prev2_m["member_new_users_ratio"]}, "yoy": yoy_ratio(cur_m["member_new_users_ratio"], comp_m["member_new_users_ratio"])},
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
                "ratio_2026": round(ratio_2026 * 100, 2),
                "ratio_2025": round(ratio_2025 * 100, 2),
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
                "new_gsv_ratio_2026": round(new_ratio_2026 * 100, 2),
                "new_gsv_ratio_2025": round(new_ratio_2025 * 100, 2),
                "new_gsv_ratio_yoy": yoy_ratio(new_ratio_2026, new_ratio_2025),
                "old_gsv_2026": old_gsv_2026,
                "old_gsv_2025": old_gsv_2025,
                "old_gsv_yoy": yoy_absolute(old_gsv_2026, old_gsv_2025),
                "old_gsv_ratio_2026": round(old_ratio_2026 * 100, 2),
                "old_gsv_ratio_2025": round(old_ratio_2025 * 100, 2),
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
                    "ratio_2026": round(ratio_2026 * 100, 2),
                    "ratio_2025": round(ratio_2025 * 100, 2),
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
                    "new_gsv_ratio_2026": round(new_ratio_2026 * 100, 2),
                    "new_gsv_ratio_2025": round(new_ratio_2025 * 100, 2),
                    "new_gsv_ratio_yoy": yoy_ratio(new_ratio_2026, new_ratio_2025),
                    "old_gsv_2026": old_gsv_2026,
                    "old_gsv_2025": old_gsv_2025,
                    "old_gsv_yoy": yoy_absolute(old_gsv_2026, old_gsv_2025),
                    "old_gsv_ratio_2026": round(old_ratio_2026 * 100, 2),
                    "old_gsv_ratio_2025": round(old_ratio_2025 * 100, 2),
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
            "ratio_2026": 100.0,
            "ratio_2025": 100.0,
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
            "new_gsv_ratio_2026": round(ttl_new_ratio_2026 * 100, 2),
            "new_gsv_ratio_2025": round(ttl_new_ratio_2025 * 100, 2),
            "new_gsv_ratio_yoy": yoy_ratio(ttl_new_ratio_2026, ttl_new_ratio_2025),
            "old_gsv_2026": ttl_old_gsv_2026,
            "old_gsv_2025": ttl_old_gsv_2025,
            "old_gsv_yoy": yoy_absolute(ttl_old_gsv_2026, ttl_old_gsv_2025),
            "old_gsv_ratio_2026": round(ttl_old_ratio_2026 * 100, 2),
            "old_gsv_ratio_2025": round(ttl_old_ratio_2025 * 100, 2),
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
            member_new_ratio_2026 = safe_ratio(member_new_gsv_2026, gsv_2026)
            member_new_ratio_2025 = safe_ratio(member_new_gsv_2025, gsv_2025)
            member_old_ratio_2026 = safe_ratio(member_old_gsv_2026, gsv_2026)
            member_old_ratio_2025 = safe_ratio(member_old_gsv_2025, gsv_2025)
            channel_member.append({
                "channel": channel,
                "gsv_2026": gsv_2026,
                "gsv_2025": gsv_2025,
                "yoy": yoy_absolute(gsv_2026, gsv_2025),
                "ratio_2026": round(ratio_2026 * 100, 2),
                "ratio_2025": round(ratio_2025 * 100, 2),
                "ratio_yoy": yoy_ratio(ratio_2026, ratio_2025),
                "users_2026": users_2026,
                "users_2025": users_2025,
                "users_yoy": yoy_absolute(users_2026, users_2025),
                "aus_2026": round(aus_2026, 2),
                "aus_2025": round(aus_2025, 2),
                "aus_yoy": yoy_absolute(aus_2026, aus_2025),
                "member_ratio_2026": round(member_ratio_2026 * 100, 2),
                "member_ratio_2025": round(member_ratio_2025 * 100, 2),
                "member_ratio_yoy": yoy_ratio(member_ratio_2026, member_ratio_2025),
                "new_gsv_2026": member_new_gsv_2026,
                "new_gsv_2025": member_new_gsv_2025,
                "new_gsv_yoy": yoy_absolute(member_new_gsv_2026, member_new_gsv_2025),
                "new_gsv_ratio_2026": round(member_new_ratio_2026 * 100, 2),
                "new_gsv_ratio_2025": round(member_new_ratio_2025 * 100, 2),
                "new_gsv_ratio_yoy": yoy_ratio(member_new_ratio_2026, member_new_ratio_2025),
                "old_gsv_2026": member_old_gsv_2026,
                "old_gsv_2025": member_old_gsv_2025,
                "old_gsv_yoy": yoy_absolute(member_old_gsv_2026, member_old_gsv_2025),
                "old_gsv_ratio_2026": round(member_old_ratio_2026 * 100, 2),
                "old_gsv_ratio_2025": round(member_old_ratio_2025 * 100, 2),
                "old_gsv_ratio_yoy": yoy_ratio(member_old_ratio_2026, member_old_ratio_2025),
                "member_new_gsv_2026": member_new_gsv_2026,
                "member_new_gsv_2025": member_new_gsv_2025,
                "member_new_gsv_yoy": yoy_absolute(member_new_gsv_2026, member_new_gsv_2025),
                "member_new_gsv_ratio_2026": round(member_new_ratio_2026 * 100, 2),
                "member_new_gsv_ratio_2025": round(member_new_ratio_2025 * 100, 2),
                "member_new_gsv_ratio_yoy": yoy_ratio(member_new_ratio_2026, member_new_ratio_2025),
                "member_old_gsv_2026": member_old_gsv_2026,
                "member_old_gsv_2025": member_old_gsv_2025,
                "member_old_gsv_yoy": yoy_absolute(member_old_gsv_2026, member_old_gsv_2025),
                "member_old_gsv_ratio_2026": round(member_old_ratio_2026 * 100, 2),
                "member_old_gsv_ratio_2025": round(member_old_ratio_2025 * 100, 2),
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
                # 会员新客/老客 GSV 占会员 GSV 的比例
                member_new_ratio_2026 = safe_ratio(member_new_gsv_2026, gsv_2026)
                member_new_ratio_2025 = safe_ratio(member_new_gsv_2025, gsv_2025)
                member_old_ratio_2026 = safe_ratio(member_old_gsv_2026, gsv_2026)
                member_old_ratio_2025 = safe_ratio(member_old_gsv_2025, gsv_2025)
                channel_member.append({
                    "channel": ch,
                    "gsv_2026": gsv_2026,
                    "gsv_2025": gsv_2025,
                    "yoy": yoy_absolute(gsv_2026, gsv_2025),
                    "ratio_2026": round(ratio_2026 * 100, 2),
                    "ratio_2025": round(ratio_2025 * 100, 2),
                    "ratio_yoy": yoy_ratio(ratio_2026, ratio_2025),
                    "users_2026": users_2026,
                    "users_2025": users_2025,
                    "users_yoy": yoy_absolute(users_2026, users_2025),
                    "aus_2026": round(aus_2026, 2),
                    "aus_2025": round(aus_2025, 2),
                    "aus_yoy": yoy_absolute(aus_2026, aus_2025),
                    "member_ratio_2026": round(member_ratio_2026 * 100, 2),
                    "member_ratio_2025": round(member_ratio_2025 * 100, 2),
                    "member_ratio_yoy": yoy_ratio(member_ratio_2026, member_ratio_2025),
                    # 复用全店列定义：new/old GSV 在会员视角下 = 会员新客/老客 GSV
                    "new_gsv_2026": member_new_gsv_2026,
                    "new_gsv_2025": member_new_gsv_2025,
                    "new_gsv_yoy": yoy_absolute(member_new_gsv_2026, member_new_gsv_2025),
                    "new_gsv_ratio_2026": round(member_new_ratio_2026 * 100, 2),
                    "new_gsv_ratio_2025": round(member_new_ratio_2025 * 100, 2),
                    "new_gsv_ratio_yoy": yoy_ratio(member_new_ratio_2026, member_new_ratio_2025),
                    "old_gsv_2026": member_old_gsv_2026,
                    "old_gsv_2025": member_old_gsv_2025,
                    "old_gsv_yoy": yoy_absolute(member_old_gsv_2026, member_old_gsv_2025),
                    "old_gsv_ratio_2026": round(member_old_ratio_2026 * 100, 2),
                    "old_gsv_ratio_2025": round(member_old_ratio_2025 * 100, 2),
                    "old_gsv_ratio_yoy": yoy_ratio(member_old_ratio_2026, member_old_ratio_2025),
                    # 原始会员字段保留（供扩展列使用）
                    "member_new_gsv_2026": member_new_gsv_2026,
                    "member_new_gsv_2025": member_new_gsv_2025,
                    "member_new_gsv_yoy": yoy_absolute(member_new_gsv_2026, member_new_gsv_2025),
                    "member_new_gsv_ratio_2026": round(member_new_ratio_2026 * 100, 2),
                    "member_new_gsv_ratio_2025": round(member_new_ratio_2025 * 100, 2),
                    "member_new_gsv_ratio_yoy": yoy_ratio(member_new_ratio_2026, member_new_ratio_2025),
                    "member_old_gsv_2026": member_old_gsv_2026,
                    "member_old_gsv_2025": member_old_gsv_2025,
                    "member_old_gsv_yoy": yoy_absolute(member_old_gsv_2026, member_old_gsv_2025),
                    "member_old_gsv_ratio_2026": round(member_old_ratio_2026 * 100, 2),
                    "member_old_gsv_ratio_2025": round(member_old_ratio_2025 * 100, 2),
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
        ttl_mem_new_ratio_2026 = safe_ratio(ttl_mem_new_gsv_2026, mem_total_gsv)
        ttl_mem_new_ratio_2025 = safe_ratio(ttl_mem_new_gsv_2025, mem_comp_total_gsv)
        ttl_mem_old_ratio_2026 = safe_ratio(ttl_mem_old_gsv_2026, mem_total_gsv)
        ttl_mem_old_ratio_2025 = safe_ratio(ttl_mem_old_gsv_2025, mem_comp_total_gsv)
        channel_member.append({
            "channel": "TTL",
            "gsv_2026": mem_total_gsv,
            "gsv_2025": mem_comp_total_gsv,
            "yoy": yoy_absolute(mem_total_gsv, mem_comp_total_gsv),
            "ratio_2026": 100.0,
            "ratio_2025": 100.0,
            "ratio_yoy": yoy_ratio(1.0, 1.0),
            "users_2026": ttl_mem_users_2026,
            "users_2025": ttl_mem_users_2025,
            "users_yoy": yoy_absolute(ttl_mem_users_2026, ttl_mem_users_2025),
            "aus_2026": round(ttl_mem_aus_2026, 2),
            "aus_2025": round(ttl_mem_aus_2025, 2),
            "aus_yoy": yoy_absolute(ttl_mem_aus_2026, ttl_mem_aus_2025),
            "member_ratio_2026": round(safe_ratio(mem_total_gsv, all_total_gsv) * 100, 2),
            "member_ratio_2025": round(safe_ratio(mem_comp_total_gsv, all_comp_total_gsv) * 100, 2),
            "member_ratio_yoy": yoy_ratio(safe_ratio(mem_total_gsv, all_total_gsv), safe_ratio(mem_comp_total_gsv, all_comp_total_gsv)),
            # 复用全店列定义：占比 = 会员新客/老客 / 会员总GSV
            "new_gsv_2026": ttl_mem_new_gsv_2026,
            "new_gsv_2025": ttl_mem_new_gsv_2025,
            "new_gsv_yoy": yoy_absolute(ttl_mem_new_gsv_2026, ttl_mem_new_gsv_2025),
            "new_gsv_ratio_2026": round(ttl_mem_new_ratio_2026 * 100, 2),
            "new_gsv_ratio_2025": round(ttl_mem_new_ratio_2025 * 100, 2),
            "new_gsv_ratio_yoy": yoy_ratio(ttl_mem_new_ratio_2026, ttl_mem_new_ratio_2025),
            "old_gsv_2026": ttl_mem_old_gsv_2026,
            "old_gsv_2025": ttl_mem_old_gsv_2025,
            "old_gsv_yoy": yoy_absolute(ttl_mem_old_gsv_2026, ttl_mem_old_gsv_2025),
            "old_gsv_ratio_2026": round(ttl_mem_old_ratio_2026 * 100, 2),
            "old_gsv_ratio_2025": round(ttl_mem_old_ratio_2025 * 100, 2),
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
            "member_new_gsv_ratio_2026": round(ttl_mem_new_ratio_2026 * 100, 2),
            "member_new_gsv_ratio_2025": round(ttl_mem_new_ratio_2025 * 100, 2),
            "member_new_gsv_ratio_yoy": yoy_ratio(ttl_mem_new_ratio_2026, ttl_mem_new_ratio_2025),
            "member_old_gsv_2026": ttl_mem_old_gsv_2026,
            "member_old_gsv_2025": ttl_mem_old_gsv_2025,
            "member_old_gsv_yoy": yoy_absolute(ttl_mem_old_gsv_2026, ttl_mem_old_gsv_2025),
            "member_old_gsv_ratio_2026": round(ttl_mem_old_ratio_2026 * 100, 2),
            "member_old_gsv_ratio_2025": round(ttl_mem_old_ratio_2025 * 100, 2),
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
            m_row["member_new_vs_all_new_2026"] = round(safe_ratio(mn_2026, all_new_2026) * 100, 2)
            m_row["member_new_vs_all_new_2025"] = round(safe_ratio(mn_2025, all_new_2025) * 100, 2)
            m_row["member_new_vs_all_new_yoy"] = yoy_ratio(safe_ratio(mn_2026, all_new_2026), safe_ratio(mn_2025, all_new_2025))
            m_row["member_old_vs_all_old_2026"] = round(safe_ratio(mo_2026, all_old_2026) * 100, 2)
            m_row["member_old_vs_all_old_2025"] = round(safe_ratio(mo_2025, all_old_2025) * 100, 2)
            m_row["member_old_vs_all_old_yoy"] = yoy_ratio(safe_ratio(mo_2026, all_old_2026), safe_ratio(mo_2025, all_old_2025))

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
        pass


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
