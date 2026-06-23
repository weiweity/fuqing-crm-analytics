"""指标服务 - 人群表格
get_audience_table
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from backend.db.connection import get_connection
from backend.semantic.calculations import yoy_ratio, yoy_absolute, safe_ratio

from backend.semantic.filters import FilterBuilder, MetricType

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
            FROM orders o
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
        pass

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
        member_old_gsv_ratio = safe_ratio(member_old_gsv, member_gsv)
        member_old_users_ratio = safe_ratio(member_old_users, member_users)
        member_new_gsv = max(0, member_gsv - member_old_gsv)
        member_new_users = max(0, member_users - member_old_users)
        member_new_aus = member_new_gsv / member_new_users if member_new_users > 0 else 0.0
        member_new_gsv_ratio = safe_ratio(member_new_gsv, member_gsv)
        member_new_users_ratio = safe_ratio(member_new_users, member_users)

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
        comp_member_old_gsv_ratio_val = round(safe_ratio(comp_member_old_gsv_val, _n(comp_member_gsv)), 4)
        comp_member_old_users_ratio_val = round(
            safe_ratio(comp_member_old_users_val, int(comp_member_users) if comp_member_users else 0), 4)
        comp_member_new_users_val = max(0, int(comp_member_users) - comp_member_old_users_val) if comp_member_users is not None else 0
        comp_member_new_gsv_val = max(0.0, _n(comp_member_gsv) - comp_member_old_gsv_val)
        comp_member_new_aus_val = comp_member_new_gsv_val / comp_member_new_users_val if comp_member_new_users_val > 0 else 0.0
        comp_member_new_gsv_ratio_val = round(safe_ratio(comp_member_new_gsv_val, _n(comp_member_gsv)), 4)
        comp_member_new_users_ratio_val = round(
            safe_ratio(comp_member_new_users_val, int(comp_member_users) if comp_member_users else 0), 4)

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
        prev2_member_old_gsv_ratio_val = round(safe_ratio(prev2_member_old_gsv_val, _n(prev2_member_gsv)), 4)
        prev2_member_old_users_ratio_val = round(
            safe_ratio(prev2_member_old_users_val, int(prev2_member_users) if prev2_member_users else 0), 4)
        prev2_member_new_users_val = max(0, int(prev2_member_users) - prev2_member_old_users_val) if prev2_member_users is not None else 0
        prev2_member_new_gsv_val = max(0.0, _n(prev2_member_gsv) - prev2_member_old_gsv_val)
        prev2_member_new_aus_val = prev2_member_new_gsv_val / prev2_member_new_users_val if prev2_member_new_users_val > 0 else 0.0
        prev2_member_new_gsv_ratio_val = round(safe_ratio(prev2_member_new_gsv_val, _n(prev2_member_gsv)), 4)
        prev2_member_new_users_ratio_val = round(
            safe_ratio(prev2_member_new_users_val, int(prev2_member_users) if prev2_member_users else 0), 4)

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
            # Sprint 19 #2: 改命名 yoy_*_ratio → yoy_*_ratio_ppt
            "yoy_old_gsv_ratio_ppt": yoy_ratio(old_gsv_ratio, comp_old_gsv_ratio_val),
            "yoy_old_users_ratio_ppt": yoy_ratio(old_users_ratio, comp_old_users_ratio_val),
            "yoy_new_gsv_ratio_ppt": yoy_ratio(new_gsv_ratio, comp_new_gsv_ratio_val),
            "yoy_new_users_ratio_ppt": yoy_ratio(new_users_ratio, comp_new_users_ratio_val),
            "yoy_member_gsv_ratio_ppt": yoy_ratio(member_gsv_ratio, comp_member_gsv_ratio_val),
            "yoy_member_users_ratio_ppt": yoy_ratio(member_users_ratio, comp_member_users_ratio_val),
            "yoy_member_old_gsv_ratio_ppt": yoy_ratio(member_old_gsv_ratio, comp_member_old_gsv_ratio_val),
            "yoy_member_old_users_ratio_ppt": yoy_ratio(member_old_users_ratio, comp_member_old_users_ratio_val),
            "yoy_member_new_gsv_ratio_ppt": yoy_ratio(member_new_gsv_ratio, comp_member_new_gsv_ratio_val),
            "yoy_member_new_users_ratio_ppt": yoy_ratio(member_new_users_ratio, comp_member_new_users_ratio_val),
        })

    return {
        "dimension": dimension,
        "mode": mode,
        "current_period": {"start": cur_start, "end": cur_end, "cutoff": cutoff},
        "comparison_period": {"start": comp_start, "end": comp_end, "cutoff": comp_cutoff},
        "prev2_period": {"start": prev2_start, "end": prev2_end} if prev2_start else None,
        "rows": rows,
    }
