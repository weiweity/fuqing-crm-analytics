"""品类分析服务"""
import duckdb
from datetime import datetime
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


def _compute_market_basket(
    conn: "duckdb.DuckDBPyConnection",
    target_category: str,
    start_date: str,
    end_date: str,
    level: str,
    channel: Optional[str],
    exclude_channels: Optional[List[str]],
) -> Dict[str, Any]:
    """
    计算单个周期的购物篮关联数据

    Returns:
        {
            "target_category": str,
            "total_orders": int,
            "target_order_count": int,
            "items": [
                {
                    "category_name": str,
                    "co_order_count": int,
                    "support": float,
                    "confidence": float,
                    "lift": float,
                    "target_order_count": int,
                }
            ]
        }
    """
    level_col = SPU_LEVELS.get(level, "spu_product_class")
    valid_sql, _ = OrderFilters.valid_order()
    excluded_cat_sql = _excluded_cat_filter(level_col)

    # 渠道参数
    channel_params: List[Any] = []
    exclude_params: List[Any] = []
    list(EXCLUDED_PRODUCT_CATEGORIES)
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

    # 日期参数
    date_params = [start_date, end_date]
    base_params = date_params + list(EXCLUDED_PRODUCT_CATEGORIES) + channel_params + exclude_params

    sql = f"""
    WITH
    -- 周期内所有有效订单
    period_orders AS (
        SELECT DISTINCT order_id, user_id, {_cat_expr(level_col)} AS category_name
        FROM orders o
        WHERE o.pay_time >= ?
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          {excluded_cat_sql}
          {channel_sql}
          {exclude_sql}
    ),
    -- 包含目标品类的订单
    target_orders AS (
        SELECT DISTINCT order_id
        FROM period_orders
        WHERE category_name = ?
    ),
    -- 目标品类订单的金额和用户（用于计算人均GSV baseline）
    target_order_values AS (
        SELECT order_id, user_id, SUM(actual_amount) AS actual_amount
        FROM orders
        WHERE order_id IN (SELECT order_id FROM target_orders)
        GROUP BY order_id, user_id
    ),
    -- 目标品类人均GSV（baseline = GSV / 人数）
    target_avg AS (
        SELECT
            SUM(actual_amount) AS target_gsv,
            COUNT(DISTINCT user_id) AS target_user_count
        FROM target_order_values
    ),
    -- 目标品类的订单数
    target_count AS (
        SELECT COUNT(*) AS target_order_count FROM target_orders
    ),
    -- 总订单数(去重)
    total_count AS (
        SELECT COUNT(DISTINCT order_id) AS total_orders FROM period_orders
    ),
    -- 关联品类在订单中的自身金额（用于 co_own_gsv：可加总、不重复）
    co_own_values AS (
        SELECT
            {_cat_expr(level_col)} AS category_name,
            o.order_id,
            o.user_id,
            SUM(o.actual_amount) AS own_amount
        FROM orders o
        WHERE o.order_id IN (SELECT order_id FROM target_orders)
          AND {_cat_expr(level_col)} != ?
        GROUP BY {_cat_expr(level_col)}, o.order_id, o.user_id
    ),
    -- 与目标品类同单出现的其他品类及其连带GSV和用户数
    basket_items AS (
        SELECT
            po.category_name,
            COUNT(DISTINCT po.order_id) AS co_order_count,
            COUNT(DISTINCT po.user_id) AS co_user_count,
            SUM(tov.actual_amount) AS co_gsv,
            SUM(cov.own_amount) AS co_own_gsv
        FROM (
            SELECT order_id, user_id, category_name
            FROM period_orders
            WHERE order_id IN (SELECT order_id FROM target_orders)
              AND category_name != ?
        ) po
        JOIN target_order_values tov ON tov.order_id = po.order_id AND tov.user_id = po.user_id
        LEFT JOIN co_own_values cov
            ON cov.order_id = po.order_id
            AND cov.user_id = po.user_id
            AND cov.category_name = po.category_name
        GROUP BY po.category_name
    ),
    -- 各品类的独立订单数(用于lift分母)
    item_orders AS (
        SELECT
            category_name,
            COUNT(DISTINCT order_id) AS item_order_count
        FROM period_orders
        GROUP BY category_name
    )
    SELECT
        b.category_name,
        b.co_order_count,
        b.co_user_count,
        b.co_gsv,
        b.co_own_gsv,
        tc.target_order_count,
        tc2.total_orders,
        tavg.target_gsv,
        tavg.target_user_count,
        i.item_order_count
    FROM basket_items b
    LEFT JOIN item_orders i ON b.category_name = i.category_name
    CROSS JOIN target_count tc
    CROSS JOIN total_count tc2
    CROSS JOIN target_avg tavg
    ORDER BY b.co_order_count DESC
    LIMIT 50
    """

    # 参数: date(2) + channel + exclude + target(1) + target(1 for co_own_values) + target(1 for basket_items subquery)
    params = base_params + [target_category, target_category, target_category]
    rows = conn.execute(sql, params).fetchall()

    items = []
    total_orders = 0
    target_count = 0
    for row in rows:
        cat_name = row[0]
        co_count = int(row[1] or 0)
        co_user_count = int(row[2] or 0)
        co_gsv = float(row[3] or 0)
        co_own_gsv = float(row[4] or 0)
        target_count = int(row[5] or 0)
        total_orders = int(row[6] or 0)
        target_gsv = float(row[7] or 0)
        target_user_count = int(row[8] or 0)
        item_count = int(row[9] or 0)

        if target_count == 0 or total_orders == 0:
            continue

        support = co_count / total_orders
        confidence = co_count / target_count
        item_prob = item_count / total_orders if total_orders > 0 else 0
        lift = confidence / item_prob if item_prob > 0 else 0
        # 客单价口径：GSV / 人数
        target_aus = target_gsv / target_user_count if target_user_count > 0 else 0
        co_aus = co_gsv / co_user_count if co_user_count > 0 else 0
        gsv_lift = co_aus / target_aus if target_aus > 0 else 0

        items.append({
            "category_name": cat_name,
            "co_order_count": co_count,
            "support": round(support, 4),
            "confidence": round(confidence, 4),
            "lift": round(lift, 4),
            "target_order_count": target_count,
            "co_gsv": round(co_gsv, 2),
            "co_own_gsv": round(co_own_gsv, 2),
            "co_aus": round(co_aus, 2),
            "target_aus": round(target_aus, 2),
            "gsv_lift": round(gsv_lift, 2),
        })

    return {
        "target_category": target_category,
        "total_orders": total_orders,
        "target_order_count": target_count,
        "items": items,
    }

def get_market_basket(
    start_date: str,
    end_date: str,
    target_category: str,
    level: str = "class",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    购物篮分析 - 目标品类的关联品类 + YoY对比

    Args:
        start_date: 周期开始日期
        end_date: 周期结束日期
        target_category: 目标品类名称
        level: 品类级别
        channel: 渠道筛选
        exclude_channels: 排除渠道列表

    Returns:
        MarketBasketResponse 结构
    """
    from dateutil.relativedelta import relativedelta

    conn = get_connection()

    try:
        # 当期
        current = _compute_market_basket(
            conn, target_category, start_date, end_date,
            level, channel, exclude_channels)

        # 去年同期
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        prev_start = (start_dt - relativedelta(years=1)).strftime("%Y-%m-%d")
        prev_end = (end_dt - relativedelta(years=1)).strftime("%Y-%m-%d")

        previous = _compute_market_basket(
            conn, target_category, prev_start, prev_end,
            level, channel, exclude_channels)

    finally:
        conn.close()

    # 构建排名映射
    prev_rank = {item["category_name"]: i + 1 for i, item in enumerate(previous["items"])}
    prev_conf = {item["category_name"]: item["confidence"] for item in previous["items"]}
    prev_lift = {item["category_name"]: item["lift"] for item in previous["items"]}
    prev_gsv = {item["category_name"]: item["co_gsv"] for item in previous["items"]}

    yoy_items = []
    for i, cur_item in enumerate(current["items"]):
        cat = cur_item["category_name"]
        prev_item = next((p for p in previous["items"] if p["category_name"] == cat), None)

        rank_chg = None
        conf_chg = None
        lift_chg = None
        gsv_chg = None

        if prev_item:
            rank_chg = i + 1 - prev_rank.get(cat, i + 1)
            conf_chg = round(cur_item["confidence"] - prev_conf.get(cat, 0), 4)
            lift_chg = round(cur_item["lift"] - prev_lift.get(cat, 0), 4)
            gsv_chg = round(cur_item["co_gsv"] - prev_gsv.get(cat, 0), 2)

        yoy_items.append({
            "category_name": cat,
            "current": cur_item,
            "previous": prev_item,
            "confidence_change": conf_chg,
            "lift_change": lift_chg,
            "rank_change": rank_chg,
            "gsv_change": gsv_chg,
        })

    return {
        "target_category": target_category,
        "total_orders": current["total_orders"],
        "target_order_count": current["target_order_count"],
        "period_label": f"{start_date}~{end_date}",
        "yoy_period_label": f"{prev_start}~{prev_end}",
        "items": yoy_items,
        "data_quality_note": (
            f"本Tab基于 {current['total_orders']} 笔订单 / "
            f"{current['target_order_count']} 笔目标品类订单计算"
        ),
    }
