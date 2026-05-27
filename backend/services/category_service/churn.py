"""品类分析服务"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

"""
芙清 CRM 客户分析系统 - 品类分析服务
Week 4 品类分布、品类象限矩阵、品类用户画像
"""

from backend.db.connection import get_connection
from backend.semantic.filters import OrderFilters, expand_channels


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


def get_category_churn(
    start_date: str,
    end_date: str,
    level: str = "class",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    品类流失 - MoM变化 + 流失去向 + 流失用户数

    Args:
        start_date: 周期开始日期
        end_date: 周期结束日期
        level: 品类级别
        channel: 渠道筛选
        exclude_channels: 排除渠道列表

    Returns:
        CategoryChurnResponse 结构
    """

    conn = get_connection()
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    period_days = (end_dt - start_dt).days + 1

    prev_start = (start_dt - timedelta(days=period_days)).strftime("%Y-%m-%d")
    prev_end = (end_dt - timedelta(days=period_days)).strftime("%Y-%m-%d")

    level_col = SPU_LEVELS.get(level, "spu_product_class")
    valid_sql, _ = OrderFilters.valid_order()
    excluded_cat_sql = _excluded_cat_filter(level_col)

    # channel/exclude 在两个CTE(current+previous)都出现,参数需传两次
    channel_params = []
    exclude_params = []
    channel_sql = ""
    if channel and channel != "全店":

        db_channels = [c for c in expand_channels([channel]) if c]

        if not db_channels:

            raise ValueError(f"渠道'{channel}'未在channels.py中注册，请检查UI_TO_DB映射")
        if len(db_channels) == 1:
            channel_sql = "AND o.channel = ?"
            channel_params = [db_channels[0]]
        else:
            placeholders = ",".join(["?"] * len(db_channels))
            channel_sql = f"AND o.channel IN ({placeholders})"
            channel_params = list(db_channels)

    exclude_sql = ""
    if exclude_channels:
        db_ex = [c for c in expand_channels(exclude_channels) if c]
        placeholders = ",".join(["?"] * len(db_ex))
        exclude_sql = f"AND o.channel NOT IN ({placeholders})"
        exclude_params = list(db_ex)

    # excluded_cat 在两个CTE中都出现,参数需传两次
    excluded_params = list(EXCLUDED_PRODUCT_CATEGORIES)

    # 参数顺序: current(start_date,end_date) + excluded + channel + exclude
    #           + previous(prev_start,prev_end) + excluded + channel + exclude
    params = (
        [start_date, end_date] + excluded_params + channel_params + exclude_params +
        [prev_start, prev_end] + excluded_params + channel_params + exclude_params
    )

    sql = f"""
    WITH current_period_users AS (
        SELECT DISTINCT
            {_cat_expr(level_col)} AS category_name,
            o.user_id
        FROM orders o
        WHERE o.pay_time >= ?
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          {excluded_cat_sql}
          {channel_sql}
          {exclude_sql}
    ),
    previous_period_users AS (
        SELECT DISTINCT
            {_cat_expr(level_col)} AS category_name,
            o.user_id
        FROM orders o
        WHERE o.pay_time >= ?
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          {excluded_cat_sql}
          {channel_sql}
          {exclude_sql}
    ),
    current_period_totals AS (
        -- 本期各品类总用户数(用于展示"本期规模")
        SELECT
            category_name,
            COUNT(DISTINCT user_id) AS curr_total_users
        FROM current_period_users
        GROUP BY category_name
    ),
    category_churn AS (
        SELECT
            p.category_name,
            COUNT(DISTINCT p.user_id) AS prev_users,
            COUNT(DISTINCT c.user_id) AS curr_users,
            COUNT(DISTINCT CASE WHEN c.user_id IS NOT NULL THEN p.user_id END) AS retained_users,
            COUNT(DISTINCT CASE WHEN c.user_id IS NULL THEN p.user_id END) AS churned_users
        FROM previous_period_users p
        LEFT JOIN current_period_users c ON p.user_id = c.user_id AND p.category_name = c.category_name
        GROUP BY p.category_name
    ),
    inter_category_churn AS (
        -- 上期买A,本期买B(B!=A)的用户
        SELECT
            p.category_name AS from_category,
            COALESCE(c.category_name, '沉默流失') AS to_category,
            COUNT(DISTINCT p.user_id) AS inter_churn_users
        FROM previous_period_users p
        INNER JOIN current_period_users c ON p.user_id = c.user_id
        WHERE p.category_name != c.category_name
        GROUP BY p.category_name, c.category_name
    ),
    silent_churn AS (
        -- 上期买A,本期无订单
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
    )
    SELECT
        cc.category_name,
        cc.prev_users,
        COALESCE(ct.curr_total_users, 0) AS curr_total_users,
        cc.retained_users,
        cc.churned_users,
        COALESCE(sc.silent_users, 0) AS silent_users,
        tcd1.to_category AS top_dest1,
        tcd1.inter_churn_users AS top_dest1_users,
        tcd2.to_category AS top_dest2,
        tcd2.inter_churn_users AS top_dest2_users
    FROM category_churn cc
    LEFT JOIN current_period_totals ct ON cc.category_name = ct.category_name
    LEFT JOIN silent_churn sc ON cc.category_name = sc.category_name
    LEFT JOIN top_churn_dest tcd1 ON cc.category_name = tcd1.from_category AND tcd1.rn = 1
    LEFT JOIN top_churn_dest tcd2 ON cc.category_name = tcd2.from_category AND tcd2.rn = 2
    """
    result = conn.execute(sql, params).fetchall()
    conn.close()

    scatter_data = []
    bar_data = []
    table = []

    for row in result:
        cat_name = row[0]
        prev_users = int(row[1] or 0)
        curr_total_users = int(row[2] or 0)  # 本期该品类总用户数
        int(row[3] or 0)
        churned = int(row[4] or 0)
        silent = int(row[5] or 0)
        inter_churned = churned - silent  # 品类间流失 = 总流失 - 沉默流失

        mom_change = (curr_total_users - prev_users) / prev_users if prev_users > 0 else 0

        top_dest1 = row[6] if row[6] else "无"
        top_dest1_users = int(row[7] or 0)
        top_dest2 = row[8] if row[8] else "无"
        top_dest2_users = int(row[9] or 0)

        dest1_ratio = top_dest1_users / inter_churned if inter_churned > 0 else 0
        dest2_ratio = top_dest2_users / inter_churned if inter_churned > 0 else 0

        scatter_data.append({
            "category_name": cat_name,
            "current_users": curr_total_users,
            "mom_change_rate": round(mom_change, 4),
            "churn_users": churned,
            "inter_churn": inter_churned,
            "silent_churn": silent,
        })

        bar_data.append({
            "category_name": cat_name,
            "current_users": curr_total_users,
            "previous_users": prev_users,
            "mom_change_rate": round(mom_change, 4),
        })

        # 挽回建议
        suggestion = ""
        if inter_churned > 0 and top_dest1 != "无":
            suggestion = f"触达推送 {top_dest1}"
        elif silent > churned * 0.5:
            suggestion = "发送召回触达,配合首单礼包促进回流"

        table.append({
            "category_name": cat_name,
            "current_users": curr_total_users,
            "previous_users": prev_users,
            "mom_change_rate": round(mom_change, 4),
            "inter_churn": inter_churned,
            "silent_churn": silent,
            "top_churn_dest1": top_dest1,
            "top_churn_dest1_ratio": round(dest1_ratio, 4),
            "top_churn_dest2": top_dest2,
            "top_churn_dest2_ratio": round(dest2_ratio, 4),
            "挽回建议": suggestion,
        })

    # 按流失严重度排序
    scatter_data.sort(key=lambda x: x["mom_change_rate"])
    table.sort(key=lambda x: x["mom_change_rate"])

    suggestions = []
    large_decline = [t for t in table if t["mom_change_rate"] < -0.2 and t["previous_users"] > 1000]
    if large_decline:
        suggestions.append(f"⚠️ 紧急:{large_decline[0]['category_name']} 流失加速(<-20%),建议重新评估资源分配")

    return {
        "scatter_data": scatter_data,
        "bar_data": bar_data,
        "table": table,
        "operation_suggestions": suggestions,
        "data_quality_note": f"本期: {start_date}~{end_date},上期: {prev_start}~{prev_end}",
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
    valid_sql, _ = OrderFilters.valid_order()

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

    sql = f"""
    WITH daily_data AS (
        SELECT
            {date_col} AS {date_key_name},
            SUM(actual_amount) AS gmv,
            COUNT(DISTINCT user_id) AS user_count
        FROM orders
        WHERE pay_time >= ?
          AND pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          AND spu_product_class = ?
        GROUP BY {date_col}
        ORDER BY {date_col}
    )
    SELECT {date_key_name}, gmv, user_count
    FROM daily_data
    """
    result = conn.execute(sql, [start_date, end_date, category_id]).fetchall()
    conn.close()

    dates = [row[0] for row in result]
    gmv = [float(row[1] or 0) for row in result]
    user_count = [int(row[2] or 0) for row in result]
    aus = [round(g / u if u > 0 else 0, 2) for g, u in zip(gmv, user_count)]
    new_customer_ratio = [0.0] * len(dates)  # 简化

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
    valid_sql, _ = OrderFilters.valid_order()

    sql = f"""
    WITH category_users AS (
        SELECT DISTINCT
            o.user_id,
            COUNT(DISTINCT o.order_id) AS order_count,
            SUM(o.actual_amount) AS total_gmv,
            MIN(o.pay_time) AS first_order_date,
            MAX(o.pay_time) AS last_order_date
        FROM orders o
        WHERE o.pay_time >= ?
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          AND spu_product_class = ?
        GROUP BY o.user_id
    ),
    user_segments AS (
        SELECT r.user_id, r.segment_id
        FROM user_rfm r
        WHERE r.analysis_date = (
            SELECT MAX(analysis_date) FROM user_rfm
        )
    )
    SELECT
        cu.user_id,
        cu.order_count,
        cu.total_gmv,
        cu.first_order_date,
        cu.last_order_date,
        COALESCE(us.segment_id, 9) AS segment_id,
        EXISTS(SELECT 1 FROM orders o WHERE o.user_id = cu.user_id AND o.is_member = TRUE LIMIT 1) AS is_member
    FROM category_users cu
    LEFT JOIN user_segments us ON cu.user_id = us.user_id
    ORDER BY cu.total_gmv DESC
    LIMIT ?
    """
    result = conn.execute(sql, [start_date, end_date, category_id, limit]).fetchall()

    # 获取总用户数
    count_sql = """
    SELECT COUNT(DISTINCT user_id)
    FROM orders
    WHERE pay_time >= ? AND pay_time < DATE(?) + INTERVAL '1' DAY
      AND {valid_sql}
      AND spu_product_class = ?
    """
    total_result = conn.execute(count_sql, [start_date, end_date, category_id]).fetchone()
    total_users = int(total_result[0] if total_result else 0)
    conn.close()

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
            "is_wool_party": False,  # 简化
        })

    return {
        "category_id": category_id,
        "category_name": category_id,
        "total_users": total_users,
        "users": users,
    }
