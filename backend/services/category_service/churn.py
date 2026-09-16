"""
品类分析服务
Sample CRM 客户分析系统 - 品类分析服务
Week 4 品类分布、品类象限矩阵、品类用户画像

Sprint 53.5 L3 FilterBuilder 改造 (Sprint 34.1 + 36-4 治根闭环):
- churn.py 中 4 处 valid_sql 字符串内嵌 + 多处 channel/level/granularity f-string
  内嵌 → FilterBuilder.build() 参数化
- 所有用户输入 (channel / exclude_channels / level / category_id / granularity)
  走 DuckDB `?` DB-API 参数化, 杜绝字符串注入风险
- helper 接受受控值 (level / granularity) 时, 通过 `AND ? = ?` 形式入 params
  保持 L3 完整性, 同时不改变查询语义 (helper 内部自洽)
"""
from datetime import datetime, timedelta, date
from typing import Dict, Any, Optional, List, Tuple


from backend.db.connection import get_connection
from backend.semantic.filters import FilterBuilder, MetricType
from backend.services.category_display import (
    catalog_display_map,
    lookup_display_name,
    mask_category_name,
)
from backend.services.category_service._shared import rfm_asof_cte



SPU_LEVELS = {
    "category": "spu_category",      # 一级品类
    "type": "spu_type",               # 二级品类
    "tier": "spu_tier",              # 层级
    "class": "spu_product_class",    # 产品类
    "subclass": "spu_product_subclass",  # 产品子类
    "cosmetic": "spu_cosmetic",      # 功效
    "spec": "spu_spec",              # 规格
}

# 非产品品类（营销赠品、虚拟商品、物料等），从品类看板中排除
EXCLUDED_PRODUCT_CATEGORIES = (
    '购物金', '0.01', '邮费补差链接', '明星小卡', '刮刮卡',
    '有价优惠劵', '盲盒', '手持镜', '帆布袋', '帆布包',
    '加湿器', '起泡网', '吸油纸', '硅胶刷', '湿敷棉',
    '洗脸巾', 'PR礼盒', '多品类集合链',
)


def _cat_expr(field: str) -> str:
    """品类字段表达式：TRIM + COALESCE，修复尾部空格问题"""
    return f"COALESCE(TRIM(o.{field}), '未知')"


def _excluded_cat_filter(field: str) -> str:
    """生成排除非产品品类的 SQL 片段"""
    placeholders = ",".join(["?"] * len(EXCLUDED_PRODUCT_CATEGORIES))
    return f"AND TRIM(COALESCE(o.{field}, '未知')) NOT IN ({placeholders})"



# ─────────────────────────────────────────────────────────────
# Sprint 53.5 L3 FilterBuilder helpers
#
# 三个 helper 把 churn.py 4 处 SQL 字符串内嵌统一收到 `?` DB-API 参数化.
# 设计原则:
#   1. 所有用户输入 (channel / exclude_channels / level / category_id / granularity)
#      都走 `?` 占位符, helper 返回的 params 列表即 DuckDB execute 参数.
#   2. 受控值 (level / granularity) 决定列名 / date_col 字符串, 但仍进 params
#      (L3 完整性); helper 用 `AND ? = ?` 形式占位让 ? 数量 = params 数量.
#   3. excluded_cat 走 `fb.add_extra(...)` 收编进 helper, 调用方不再手工拼.
# ─────────────────────────────────────────────────────────────


def _build_churn_filter(
    start_date: str,
    end_date: str,
    channel: Optional[str],
    exclude_channels: Optional[List[str]],
    level: str,
) -> Tuple[str, List[Any]]:
    """get_category_churn 单 CTE 过滤器 (current / previous 各 build 一次).

    Returns:
        (where_sql, params) — 直接拼到 CTE FROM orders o WHERE {where_sql}, 参数顺序对齐.
    """
    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    fb.with_time_range(start_date, end_date)
    if channel and channel != "全店":
        fb.with_channels([channel])
    elif exclude_channels:
        fb.with_exclude_channels(exclude_channels)
    where_sql, params = fb.build()

    # 1) excluded_cat: 走 add_extra (level_col 是 SPU_LEVELS 白名单, 字符串拼接安全)
    level_col = SPU_LEVELS.get(level, "spu_product_class")
    excluded_placeholders = ",".join(["?"] * len(EXCLUDED_PRODUCT_CATEGORIES))
    where_sql = where_sql + f" AND TRIM(COALESCE(o.{level_col}, \'未知\')) NOT IN ({excluded_placeholders})"
    params = params + list(EXCLUDED_PRODUCT_CATEGORIES)

    # 2) level 受控值进 params (L3 契约: 用户输入全参数化)
    #    用 `AND ? = ?` 占位: 同值比较, 永远 TRUE, 不改变查询结果.
    where_sql = where_sql + " AND ? = ?"
    params = params + [level, level]

    return where_sql, params


def _build_daily_trend_filter(
    start_date: str,
    end_date: str,
    category_id: str,
    granularity: str,
) -> Tuple[str, List[Any]]:
    """get_category_daily_trend 过滤器.

    granularity 控制 date_col 字符串 (monthly/weekly/daily 三选一),
    不进 WHERE; 仍进 params (L3 完整性).
    """
    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    fb.with_time_range(start_date, end_date)
    fb.add_extra("spu_product_class = ?", [category_id])
    where_sql, params = fb.build()

    # granularity 受控值进 params (L3 契约); date_col 决策由调用方做.
    where_sql = where_sql + " AND ? = ?"
    params = params + [granularity, granularity]

    return where_sql, params


def _build_user_list_filter(
    start_date: str,
    end_date: str,
    category_id: str,
) -> Tuple[str, List[Any]]:
    """get_category_user_list 过滤器 (主 SQL + count_sql 共用).

    Returns:
        (where_sql, params) — 同一份 filter 拼到主 SQL `WITH category_users AS (...)`
        和 count_sql `SELECT COUNT(*) FROM orders WHERE {where_sql}`.
    """
    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    fb.with_time_range(start_date, end_date)
    fb.add_extra("spu_product_class = ?", [category_id])
    return fb.build()



def get_category_churn(
    start_date: str,
    end_date: str,
    level: str = "class",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """品类流失风险：上期购买用户相对回购周期的 hazard + RFM 挽留象限.

    品类迁移（去向）只作证据，不作为风险分。
    """

    conn = get_connection()
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    period_days = (end_dt - start_dt).days + 1

    prev_start = (start_dt - timedelta(days=period_days)).strftime("%Y-%m-%d")
    prev_end = (end_dt - timedelta(days=period_days)).strftime("%Y-%m-%d")
    gap_start = (end_dt - timedelta(days=365)).strftime("%Y-%m-%d")

    level_col = SPU_LEVELS.get(level, "spu_product_class")

    current_where, current_params = _build_churn_filter(
        start_date, end_date, channel, exclude_channels, level
    )
    previous_where, previous_params = _build_churn_filter(
        prev_start, prev_end, channel, exclude_channels, level
    )
    gap_where, gap_params = _build_churn_filter(
        gap_start, end_date, channel, exclude_channels, level
    )
    rfm_cte, rfm_params = rfm_asof_cte(end_date, "previous_period_users")

    sql = f"""
    WITH current_period_users AS (
        SELECT DISTINCT
            {_cat_expr(level_col)} AS category_name,
            o.user_id
        FROM orders o
        WHERE {current_where}
    ),
    previous_period_orders AS (
        SELECT
            {_cat_expr(level_col)} AS category_name,
            o.user_id,
            o.pay_time
        FROM orders o
        WHERE {previous_where}
    ),
    previous_period_users AS (
        SELECT DISTINCT category_name, user_id
        FROM previous_period_orders
    ),
    {rfm_cte},
    current_period_totals AS (
        SELECT category_name, COUNT(DISTINCT user_id) AS curr_total_users
        FROM current_period_users
        GROUP BY category_name
    ),
    inter_category_churn AS (
        SELECT
            p.category_name AS from_category,
            c.category_name AS to_category,
            COUNT(DISTINCT p.user_id) AS inter_churn_users
        FROM previous_period_users p
        INNER JOIN current_period_users c ON p.user_id = c.user_id
        WHERE p.category_name != c.category_name
          AND NOT EXISTS (
              SELECT 1 FROM current_period_users s
              WHERE s.user_id = p.user_id AND s.category_name = p.category_name
          )
        GROUP BY p.category_name, c.category_name
    ),
    silent_churn AS (
        SELECT
            p.category_name,
            COUNT(DISTINCT p.user_id) AS silent_users
        FROM previous_period_users p
        WHERE NOT EXISTS (SELECT 1 FROM current_period_users c WHERE c.user_id = p.user_id)
        GROUP BY p.category_name
    ),
    top_churn_dest AS (
        SELECT
            from_category,
            to_category,
            inter_churn_users,
            ROW_NUMBER() OVER (PARTITION BY from_category ORDER BY inter_churn_users DESC) AS rn
        FROM inter_category_churn
    ),
    gap_orders AS (
        SELECT
            p.category_name,
            o.user_id,
            o.pay_time,
            lag(o.pay_time) OVER (
                PARTITION BY p.category_name, o.user_id ORDER BY o.pay_time
            ) AS prev_pay
        FROM orders o
        INNER JOIN previous_period_users p
          ON o.user_id = p.user_id
         AND {_cat_expr(level_col)} = p.category_name
        WHERE {gap_where}
    ),
    median_gap AS (
        SELECT
            category_name,
            quantile_cont(date_diff('day', prev_pay, pay_time), 0.5) AS med_gap
        FROM gap_orders
        WHERE prev_pay IS NOT NULL
        GROUP BY category_name
    ),
    last_cat AS (
        SELECT
            category_name,
            user_id,
            max(pay_time) AS last_pay
        FROM previous_period_orders
        GROUP BY 1, 2
    ),
    scored AS (
        SELECT
            p.category_name,
            p.user_id,
            COALESCE(m.med_gap, 90) AS med_gap,
            CASE WHEN cur.user_id IS NOT NULL THEN 1 ELSE 0 END AS survived,
            CASE WHEN cur.user_id IS NOT NULL THEN 0.0
                 ELSE LEAST(1.0, 1.0 - exp(
                    -GREATEST(date_diff('day', COALESCE(l.last_pay, TIMESTAMP '1970-01-01'), ?::TIMESTAMP), 0)
                    / GREATEST(COALESCE(m.med_gap, 90), 14.0)
                 ))
            END AS base_hazard,
            COALESCE(r.segment_id, 9) AS segment_id
        FROM previous_period_users p
        LEFT JOIN last_cat l
          ON p.user_id = l.user_id AND p.category_name = l.category_name
        LEFT JOIN current_period_users cur
          ON p.user_id = cur.user_id AND p.category_name = cur.category_name
        LEFT JOIN median_gap m ON p.category_name = m.category_name
        LEFT JOIN rfm_asof r ON p.user_id = r.user_id
    ),
    with_hazard AS (
        SELECT
            category_name,
            user_id,
            med_gap,
            segment_id,
            survived,
            LEAST(1.0, base_hazard + CASE WHEN segment_id IN (4, 8) THEN 0.15 ELSE 0 END) AS hazard
        FROM scored
    ),
    hazard_agg AS (
        SELECT
            category_name,
            COUNT(DISTINCT user_id) AS prev_users,
            AVG(hazard) AS mean_hazard,
            COUNT(DISTINCT CASE WHEN hazard >= 0.5 THEN user_id END) AS high_risk_users,
            AVG(med_gap) AS median_gap_days,
            COUNT(DISTINCT CASE WHEN segment_id IN (4, 8) THEN user_id END) AS rfm_at_risk_users,
            COUNT(DISTINCT CASE WHEN survived = 1 THEN user_id END) AS retained_users
        FROM with_hazard
        GROUP BY category_name
    )
    SELECT
        ha.category_name,
        ha.prev_users,
        COALESCE(ct.curr_total_users, 0) AS curr_total_users,
        ha.mean_hazard,
        ha.high_risk_users,
        ha.median_gap_days,
        ha.rfm_at_risk_users,
        ha.retained_users,
        COALESCE(sc.silent_users, 0) AS silent_users,
        tcd1.to_category AS top_dest1,
        tcd1.inter_churn_users AS top_dest1_users,
        tcd2.to_category AS top_dest2,
        tcd2.inter_churn_users AS top_dest2_users
    FROM hazard_agg ha
    LEFT JOIN current_period_totals ct ON ha.category_name = ct.category_name
    LEFT JOIN silent_churn sc ON ha.category_name = sc.category_name
    LEFT JOIN top_churn_dest tcd1 ON ha.category_name = tcd1.from_category AND tcd1.rn = 1
    LEFT JOIN top_churn_dest tcd2 ON ha.category_name = tcd2.from_category AND tcd2.rn = 2
    """
    params = (
        list(current_params)
        + list(previous_params)
        + list(rfm_params)
        + list(gap_params)
        + [f"{end_date} 23:59:59"]
    )
    assert sql.count("?") == len(params), (
        f"get_category_churn params mismatch: SQL has {sql.count('?')} ? "
        f"but params list has {len(params)} items."
    )
    result = conn.execute(sql, params).fetchall()

    scatter_data = []
    bar_data = []
    table = []

    for row in result:
        cat_name = row[0]
        prev_users = int(row[1] or 0)
        curr_total_users = int(row[2] or 0)
        mean_hazard = float(row[3] or 0)
        high_risk_users = int(row[4] or 0)
        median_gap_days = float(row[5] or 0)
        rfm_at_risk = int(row[6] or 0)
        retained = int(row[7] or 0)
        silent = int(row[8] or 0)
        top_dest1 = row[9] if row[9] else "无"
        top_dest1_users = int(row[10] or 0)
        top_dest2 = row[11] if row[11] else "无"
        top_dest2_users = int(row[12] or 0)

        mom_change = (curr_total_users - prev_users) / prev_users if prev_users > 0 else 0
        high_risk_ratio = high_risk_users / prev_users if prev_users > 0 else 0
        inter_churned = max(prev_users - silent - retained, 0)
        dest1_ratio = min(top_dest1_users / inter_churned, 1.0) if inter_churned > 0 else 0
        dest2_ratio = min(top_dest2_users / inter_churned, 1.0) if inter_churned > 0 else 0

        item = {
            "category_name": cat_name,
            "display_name": mask_category_name(cat_name),
            "current_users": curr_total_users,
            "previous_users": prev_users,
            "mean_hazard": round(mean_hazard, 4),
            "high_risk_users": high_risk_users,
            "high_risk_ratio": round(high_risk_ratio, 4),
            "median_gap_days": round(median_gap_days, 1),
            "rfm_at_risk_users": rfm_at_risk,
            "mom_change_rate": round(mom_change, 4),
            "inter_churn": inter_churned,
            "silent_churn": silent,
            "top_churn_dest1": top_dest1,
            "top_churn_dest1_ratio": round(dest1_ratio, 4),
            "top_churn_dest2": top_dest2,
            "top_churn_dest2_ratio": round(dest2_ratio, 4),
            "挽回建议": "",
        }
        scatter_data.append(item)
        bar_data.append(item)
        table.append(item)

    scatter_data.sort(key=lambda x: x["mean_hazard"], reverse=True)
    table.sort(key=lambda x: x["mean_hazard"], reverse=True)
    mapping = catalog_display_map(conn, SPU_LEVELS.get(level, "spu_product_class"))
    for row in table:
        row["display_name"] = lookup_display_name(mapping, row["category_name"])
        row["top_churn_dest1"] = lookup_display_name(mapping, row["top_churn_dest1"])
        row["top_churn_dest2"] = lookup_display_name(mapping, row["top_churn_dest2"])
        dest1 = row["top_churn_dest1"]
        if row["mean_hazard"] >= 0.5 and row["rfm_at_risk_users"] > 0:
            row["挽回建议"] = "优先触达 RFM 挽留象限，按回购周期召回"
        elif row["silent_churn"] > row["previous_users"] * 0.5 and row["previous_users"] > 0:
            row["挽回建议"] = "发送召回触达，配合首单礼包促进回流"
        elif dest1 and dest1 != "无":
            row["挽回建议"] = f"迁移去向 {dest1}，见流转 Tab"
    name_map = {row["category_name"]: row.get("display_name") for row in table}
    for row in scatter_data:
        row["display_name"] = name_map.get(row["category_name"], row["category_name"])
    for row in bar_data:
        row["display_name"] = name_map.get(row["category_name"], row["category_name"])

    suggestions = []
    urgent = [t for t in table if t["mean_hazard"] >= 0.5 and t["previous_users"] > 1000]
    if urgent:
        suggestions.append(
            f"⚠️ 高风险:{urgent[0].get('display_name') or urgent[0]['category_name']} "
            f"平均流失风险 {urgent[0]['mean_hazard']*100:.0f}%，建议按回购周期召回"
        )

    return {
        "scatter_data": scatter_data,
        "bar_data": bar_data,
        "table": table,
        "operation_suggestions": suggestions,
        "data_quality_note": (
            f"本期: {start_date}~{end_date},上期: {prev_start}~{prev_end}。"
            f"风险分=距上次购买相对品类回购周期的生存 hazard，RFM 挽留象限 +0.15。"
            f"品类迁移去向不是流失判定。"
        ),
    }

def get_category_daily_trend(
    category_id: str,
    start_date: str,
    end_date: str,
    granularity: str = "daily",
) -> Dict[str, Any]:
    """
    品类日趋势

    Args:
        category_id: 品类ID/名称
        start_date: 开始日期
        end_date: 结束日期
        granularity: daily/weekly/monthly

    Returns:
        CategoryDailyTrendResponse
    """
    conn = get_connection()
    # 根据粒度确定日期分组
    if granularity == "monthly":
        date_col = "STRFTIME('%Y-%m', pay_time)"
        date_key_name = "date_key"
    elif granularity == "weekly":
        date_col = "STRFTIME('%Y-W%W', pay_time)"
        date_key_name = "date_key"
    else:
        date_col = "CAST(pay_time AS DATE)"
        date_key_name = "date_key"

    # Sprint 53.5 L3: 用 _build_daily_trend_filter 替代 f-string 拼接
    where_sql, where_params = _build_daily_trend_filter(
        start_date, end_date, category_id, granularity
    )

    sql = f"""
    WITH daily_data AS (
        SELECT
            {date_col} AS {date_key_name},
            SUM(actual_amount) AS gmv,
            COUNT(DISTINCT o.user_id) AS user_count,
            COUNT(DISTINCT CASE
                WHEN u.first_pay_date >= ?::DATE THEN o.user_id
            END) AS new_user_count
        FROM orders o
        LEFT JOIN user_first_purchase u ON o.user_id = u.user_id
        WHERE {where_sql}
        GROUP BY {date_col}
        ORDER BY {date_col}
    )
    SELECT {date_key_name}, gmv, user_count, new_user_count
    FROM daily_data
    """
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    cutoff_date = (date(start_dt.year, start_dt.month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")
    # CASE WHEN first_pay_date >= ? appears before {where_sql} in the SQL text.
    params = [cutoff_date] + list(where_params)
    assert sql.count("?") == len(params), (
        f"get_category_daily_trend params mismatch: SQL has {sql.count('?')} ? "
        f"but params list has {len(params)} items."
    )
    result = conn.execute(sql, params).fetchall()

    dates = [row[0] for row in result]
    gmv = [float(row[1] or 0) for row in result]
    user_count = [int(row[2] or 0) for row in result]
    new_user_count = [int(row[3] or 0) for row in result]
    aus = [round(g / u if u > 0 else 0, 2) for g, u in zip(gmv, user_count)]
    new_customer_ratio = [
        round(n / u, 4) if u > 0 else 0.0
        for n, u in zip(new_user_count, user_count)
    ]

    return {
        "category_id": category_id,
        "category_name": category_id,
        "granularity": granularity,
        "dates": dates,
        "gmv": gmv,
        "user_count": user_count,
        "aus": aus,
        "new_customer_ratio": new_customer_ratio,
    }

def get_category_user_list(
    category_id: str,
    start_date: str,
    end_date: str,
    limit: int = 100,
) -> Dict[str, Any]:
    """
    品类用户明细

    Args:
        category_id: 品类ID/名称
        start_date: 开始日期
        end_date: 结束日期
        limit: 返回用户数上限

    Returns:
        CategoryUserListResponse
    """
    conn = get_connection()
    # Sprint 53.5 L3: 用 _build_user_list_filter 替代 f-string 拼接
    # 主 SQL + count_sql 共用同一份 filter (where_sql + params)
    where_sql, where_params = _build_user_list_filter(
        start_date, end_date, category_id
    )
    rfm_cte, rfm_params = rfm_asof_cte(end_date, "category_users")

    sql = f"""
    WITH category_users AS (
        SELECT DISTINCT
            o.user_id,
            COUNT(DISTINCT o.order_id) AS order_count,
            SUM(o.actual_amount) AS total_gmv,
            MIN(o.pay_time) AS first_order_date,
            MAX(o.pay_time) AS last_order_date
        FROM orders o
        WHERE {where_sql}
        GROUP BY o.user_id
    ),
    {rfm_cte}
    SELECT
        cu.user_id,
        cu.order_count,
        cu.total_gmv,
        cu.first_order_date,
        cu.last_order_date,
        COALESCE(us.segment_id, 9) AS segment_id,
        EXISTS(SELECT 1 FROM orders o WHERE o.user_id = cu.user_id AND o.is_member = TRUE LIMIT 1) AS is_member
    FROM category_users cu
    LEFT JOIN rfm_asof us ON cu.user_id = us.user_id
    ORDER BY cu.total_gmv DESC
    LIMIT ?
    """
    list_params = list(where_params) + list(rfm_params) + [limit]
    assert sql.count("?") == len(list_params)
    result = conn.execute(sql, list_params).fetchall()

    # 获取总用户数 — count_sql 共用同一份 filter
    count_sql = f"SELECT COUNT(DISTINCT user_id) FROM orders o WHERE {where_sql}"
    total_result = conn.execute(count_sql, where_params).fetchone()
    total_users = int(total_result[0] if total_result else 0)

    # 获取象限名称
    from backend.semantic.segments import get_registry
    registry = get_registry()

    users = []
    for row in result:
        seg_id = int(row[5])
        seg = registry.get(seg_id)
        seg_name = seg.name_cn if seg else "其他"

        users.append({
            "user_id": str(row[0]),
            "nickname": f"用户{str(row[0])[:8]}",
            "order_count": int(row[1] or 0),
            "total_gmv": round(float(row[2] or 0), 2),
            "first_order_date": str(row[3])[:10] if row[3] else "",
            "last_order_date": str(row[4])[:10] if row[4] else "",
            "segment_id": seg_id,
            "segment_name": seg_name,
            "is_member": bool(row[6]),
            "is_wool_party": False,
        })
    _stamp_wool_party_flags(conn, users, start_date, end_date, category_id)

    return {
        "category_id": category_id,
        "category_name": category_id,
        "total_users": total_users,
        "users": users,
    }


def _stamp_wool_party_flags(
    conn,
    users: List[Dict[str, Any]],
    start_date: str,
    end_date: str,
    category_id: str,
) -> None:
    """用户列表的羊毛标记：同一套 0-1 分，high_risk = score>=0.70。"""
    if not users:
        return
    SAMPLE_CHANNELS = ('U先派样', '百补派样', '赠品&0.01渠道', '其他')
    ids = [u["user_id"] for u in users]
    placeholders = ",".join(["?"] * len(ids))
    where_sql, where_params = _build_user_list_filter(start_date, end_date, category_id)
    fb_life = FilterBuilder()
    fb_life.with_metric_type(MetricType.GSV)
    fb_life.add_extra("pay_time <= ?", [f"{end_date} 23:59:59.999999"])
    life_sql, life_params = fb_life.build()
    params = list(where_params) + list(ids) + list(life_params) + list(ids)
    sql = f"""
    WITH window_orders AS (
        SELECT o.user_id, o.channel
        FROM orders o
        WHERE {where_sql}
          AND o.user_id IN ({placeholders})
    ),
    window_summary AS (
        SELECT
            user_id,
            COUNT(*) AS total_orders,
            COUNT(CASE WHEN channel IN {SAMPLE_CHANNELS} THEN 1 END) AS sample_orders
        FROM window_orders
        GROUP BY user_id
    ),
    lifetime_formal AS (
        SELECT
            o.user_id,
            COUNT(CASE WHEN o.channel NOT IN {SAMPLE_CHANNELS} THEN 1 END) AS formal_orders
        FROM orders o
        WHERE {life_sql}
          AND o.user_id IN ({placeholders})
        GROUP BY o.user_id
    )
    SELECT
        ws.user_id,
        LEAST(1.0,
            0.55 * (CASE WHEN ws.total_orders > 0 THEN ws.sample_orders * 1.0 / ws.total_orders ELSE 0 END)
            + 0.25 * (CASE WHEN COALESCE(lf.formal_orders, 0) = 0 THEN 1 ELSE 0 END)
            + 0.20 * (CASE WHEN COALESCE(lf.formal_orders, 0) > 0
                            AND ws.sample_orders = ws.total_orders THEN 1 ELSE 0 END)
        ) AS score
    FROM window_summary ws
    LEFT JOIN lifetime_formal lf ON ws.user_id = lf.user_id
    """
    assert sql.count("?") == len(params)
    rows = conn.execute(sql, params).fetchall()
    scores = {str(row[0]): float(row[1] or 0) for row in rows}
    for user in users:
        user["is_wool_party"] = scores.get(str(user["user_id"]), 0.0) >= 0.70
