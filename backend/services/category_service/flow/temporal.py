"""
品类分析服务
Sample CRM 客户分析系统 - 品类分析服务
Week 4 品类分布、品类象限矩阵、品类用户画像
"""
import duckdb
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List


from backend.semantic.filters import OrderFilters, expand_channels
from .._shared import _cat_expr, _excluded_cat_filter


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



def _compute_temporal_association(
    conn: "duckdb.DuckDBPyConnection",
    target_category: str,
    start_date: str,
    end_date: str,
    level: str,
    window_days: int,
    channel: Optional[str],
    exclude_channels: Optional[List[str]],
    anchor_mode: str = "first",
    path_depth: int = 1,
) -> Dict[str, Any]:
    """
    时序关联分析: 买 target_category 的用户前后买了什么

    Args:
        anchor_mode: first=首次购买, last=末次购买, every=每次购买(按事件统计)
        path_depth: 路径深度(1=直接前后置, 2=再向外延伸一步，形成A→B→C链)

    Returns:
        {"post_purchase": [...], "pre_purchase": [...], "post_sankey": ..., "pre_sankey": ...}
    """

    # 目标订单分析范围：[end_date - window_days, end_date]
    target_start = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=window_days)).strftime("%Y-%m-%d")

    level_col = SPU_LEVELS.get(level, "spu_product_class")
    valid_sql, _ = OrderFilters.valid_order()
    excluded_cat_sql = _excluded_cat_filter(level_col)

    # 渠道参数
    channel_params: List[Any] = []
    exclude_params: List[Any] = []
    excluded_params = list(EXCLUDED_PRODUCT_CATEGORIES)
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

    # 根据锚点模式生成 target_orders SQL
    if anchor_mode == "last":
        target_orders_sql = f"""SELECT o.user_id, MAX(o.pay_time) as anchor_pay_time
        FROM orders o
        WHERE {_cat_expr(level_col)} = ?
          AND o.pay_time >= ?
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          {channel_sql}
          {exclude_sql}
        GROUP BY o.user_id"""
    elif anchor_mode == "every":
        target_orders_sql = f"""SELECT DISTINCT o.user_id, o.pay_time as anchor_pay_time, o.order_id
        FROM orders o
        WHERE {_cat_expr(level_col)} = ?
          AND o.pay_time >= ?
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          {channel_sql}
          {exclude_sql}"""
    else:  # default: first
        target_orders_sql = f"""SELECT o.user_id, MIN(o.pay_time) as anchor_pay_time
        FROM orders o
        WHERE {_cat_expr(level_col)} = ?
          AND o.pay_time >= ?
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          {channel_sql}
          {exclude_sql}
        GROUP BY o.user_id"""

    # 后置购买: 买 target 之后买的其他品类(限制 window_days 内)
    post_sql = f"""
    WITH target_orders AS (
        {target_orders_sql}
    ),
    post_orders AS (
        SELECT
            {_cat_expr(level_col)} AS category_name,
            o.user_id,
            o.actual_amount,
            o.pay_time,
            t.anchor_pay_time AS target_pay_time
        FROM orders o
        INNER JOIN target_orders t ON o.user_id = t.user_id
        WHERE o.pay_time > t.anchor_pay_time
          AND o.pay_time <= t.anchor_pay_time + INTERVAL '1' DAY * ?
          AND {_cat_expr(level_col)} != ?
          AND {valid_sql}
          {excluded_cat_sql}
          {channel_sql}
          {exclude_sql}
    )
    SELECT
        category_name,
        COUNT(DISTINCT user_id) AS user_count,
        COUNT(*) AS order_count,
        SUM(actual_amount) AS gsv,
        AVG(DATEDIFF('day', target_pay_time::DATE, pay_time::DATE)) AS avg_days_gap
    FROM post_orders
    GROUP BY category_name
    ORDER BY user_count DESC
    LIMIT 20
    """
    # target_category, target_start, end_date, + channel + exclude + window_days + target_category + excluded_cat + channel + exclude
    post_params = [target_category, target_start, end_date] + channel_params + exclude_params + [window_days, target_category] + excluded_params + channel_params + exclude_params
    post_result = conn.execute(post_sql, post_params).fetchall()

    # 前置购买: 买 target 之前买的其他品类(限制 window_days 内)
    pre_sql = f"""
    WITH target_orders AS (
        {target_orders_sql}
    ),
    pre_orders AS (
        SELECT
            {_cat_expr(level_col)} AS category_name,
            o.user_id,
            o.actual_amount,
            o.pay_time,
            t.anchor_pay_time AS target_pay_time
        FROM orders o
        INNER JOIN target_orders t ON o.user_id = t.user_id
        WHERE o.pay_time < t.anchor_pay_time
          AND o.pay_time >= t.anchor_pay_time - INTERVAL '1' DAY * ?
          AND {_cat_expr(level_col)} != ?
          AND {valid_sql}
          {excluded_cat_sql}
          {channel_sql}
          {exclude_sql}
    )
    SELECT
        category_name,
        COUNT(DISTINCT user_id) AS user_count,
        COUNT(*) AS order_count,
        SUM(actual_amount) AS gsv,
        AVG(DATEDIFF('day', pay_time::DATE, target_pay_time::DATE)) AS avg_days_gap
    FROM pre_orders
    GROUP BY category_name
    ORDER BY user_count DESC
    LIMIT 20
    """
    # target_category, target_start, end_date, + channel + exclude + window_days + target_category + excluded_cat + channel + exclude
    pre_params = [target_category, target_start, end_date] + channel_params + exclude_params + [window_days, target_category] + excluded_params + channel_params + exclude_params
    pre_result = conn.execute(pre_sql, pre_params).fetchall()

    # 目标品类总购买用户数(用于计算 ratio)
    total_sql = f"""
    SELECT COUNT(DISTINCT user_id)
    FROM orders o
    WHERE {_cat_expr(level_col)} = ?
      AND o.pay_time >= ?
      AND o.pay_time < DATE(?) + INTERVAL '1' DAY
      AND {valid_sql}
      {channel_sql}
      {exclude_sql}
    """
    total_result = conn.execute(total_sql, [target_category, target_start, end_date] + channel_params + exclude_params).fetchone()
    total_users = int(total_result[0] or 0) if total_result else 0

    # 计算有前置/后置购买的用户数（用于流失分析）
    post_users_sql = f"""
    WITH target_orders AS (
        {target_orders_sql}
    )
    SELECT COUNT(DISTINCT o.user_id)
    FROM orders o
    INNER JOIN target_orders t ON o.user_id = t.user_id
    WHERE o.pay_time > t.anchor_pay_time
      AND o.pay_time <= t.anchor_pay_time + INTERVAL '1' DAY * ?
      AND {_cat_expr(level_col)} != ?
      AND {valid_sql}
      {excluded_cat_sql}
      {channel_sql}
      {exclude_sql}
    """
    post_users_result = conn.execute(post_users_sql, [target_category, target_start, end_date] + channel_params + exclude_params + [window_days, target_category] + excluded_params + channel_params + exclude_params).fetchone()
    post_users_with_purchase = int(post_users_result[0] or 0) if post_users_result else 0

    pre_users_sql = f"""
    WITH target_orders AS (
        {target_orders_sql}
    )
    SELECT COUNT(DISTINCT o.user_id)
    FROM orders o
    INNER JOIN target_orders t ON o.user_id = t.user_id
    WHERE o.pay_time < t.anchor_pay_time
      AND o.pay_time >= t.anchor_pay_time - INTERVAL '1' DAY * ?
      AND {_cat_expr(level_col)} != ?
      AND {valid_sql}
      {excluded_cat_sql}
      {channel_sql}
      {exclude_sql}
    """
    pre_users_result = conn.execute(pre_users_sql, [target_category, target_start, end_date] + channel_params + exclude_params + [window_days, target_category] + excluded_params + channel_params + exclude_params).fetchone()
    pre_users_with_purchase = int(pre_users_result[0] or 0) if pre_users_result else 0

    def _build_assoc(rows) -> List[Dict[str, Any]]:
        result = []
        for row in rows:
            uc = int(row[1] or 0)
            if total_users > 0:
                result.append({
                    "category_name": row[0],
                    "user_count": uc,
                    "order_count": int(row[2] or 0),
                    "gsv": round(float(row[3] or 0), 2),
                    "ratio": round(uc / total_users, 4),
                    "avg_days_gap": round(float(row[4] or 0), 1),
                })
        return result

    post_assoc = _build_assoc(post_result)
    pre_assoc = _build_assoc(pre_result)

    # ── 路径深度=2：再向外延伸一步 ──
    post_step2_assoc: List[Dict[str, Any]] = []
    pre_step2_assoc: List[Dict[str, Any]] = []

    if path_depth >= 2 and post_assoc:
        # 后置2步：从step1的TOP品类再往后走一步
        # 取TOP10品类作为中间节点（避免查询爆炸）
        top_post_cats = [item["category_name"] for item in post_assoc[:10]]
        placeholders = ",".join(["?"] * len(top_post_cats))
        post_step2_sql = f"""
        WITH target_orders AS (
            {target_orders_sql}
        ),
        step1 AS (
            SELECT
                o.user_id,
                o.pay_time as step1_time,
                {_cat_expr(level_col)} as step1_cat
            FROM orders o
            INNER JOIN target_orders t ON o.user_id = t.user_id
            WHERE o.pay_time > t.anchor_pay_time
              AND o.pay_time <= t.anchor_pay_time + INTERVAL '1' DAY * ?
              AND {_cat_expr(level_col)} != ?
              AND {_cat_expr(level_col)} IN ({placeholders})
              AND {valid_sql}
              {excluded_cat_sql}
              {channel_sql}
              {exclude_sql}
            QUALIFY ROW_NUMBER() OVER (PARTITION BY o.user_id ORDER BY o.pay_time) = 1
        ),
        step2 AS (
            SELECT
                o.user_id,
                s.step1_cat,
                {_cat_expr(level_col)} as step2_cat
            FROM orders o
            INNER JOIN step1 s ON o.user_id = s.user_id
            WHERE o.pay_time > s.step1_time
              AND o.pay_time <= s.step1_time + INTERVAL '1' DAY * ?
              AND {_cat_expr(level_col)} != s.step1_cat
              AND {_cat_expr(level_col)} != ?
              AND {valid_sql}
              {excluded_cat_sql}
              {channel_sql}
              {exclude_sql}
            QUALIFY ROW_NUMBER() OVER (PARTITION BY o.user_id, s.step1_cat ORDER BY o.pay_time) = 1
        )
        SELECT step1_cat, step2_cat, COUNT(DISTINCT user_id) as user_count
        FROM step2
        GROUP BY step1_cat, step2_cat
        ORDER BY user_count DESC
        LIMIT 20
        """
        post_step2_params = (
            [target_category, target_start, end_date] + channel_params + exclude_params +
            [window_days, target_category] + top_post_cats + excluded_params + channel_params + exclude_params +
            [window_days, target_category] + excluded_params + channel_params + exclude_params
        )
        post_step2_result = conn.execute(post_step2_sql, post_step2_params).fetchall()
        for row in post_step2_result:
            post_step2_assoc.append({
                "from_cat": row[0],
                "to_cat": row[1],
                "user_count": int(row[2] or 0),
            })

    if path_depth >= 2 and pre_assoc:
        # 前置2步：从step1的TOP品类再往前走一步
        top_pre_cats = [item["category_name"] for item in pre_assoc[:10]]
        placeholders = ",".join(["?"] * len(top_pre_cats))
        pre_step2_sql = f"""
        WITH target_orders AS (
            {target_orders_sql}
        ),
        step1 AS (
            SELECT
                o.user_id,
                o.pay_time as step1_time,
                {_cat_expr(level_col)} as step1_cat
            FROM orders o
            INNER JOIN target_orders t ON o.user_id = t.user_id
            WHERE o.pay_time < t.anchor_pay_time
              AND o.pay_time >= t.anchor_pay_time - INTERVAL '1' DAY * ?
              AND {_cat_expr(level_col)} != ?
              AND {_cat_expr(level_col)} IN ({placeholders})
              AND {valid_sql}
              {excluded_cat_sql}
              {channel_sql}
              {exclude_sql}
            QUALIFY ROW_NUMBER() OVER (PARTITION BY o.user_id ORDER BY o.pay_time DESC) = 1
        ),
        step2 AS (
            SELECT
                o.user_id,
                s.step1_cat,
                {_cat_expr(level_col)} as step2_cat
            FROM orders o
            INNER JOIN step1 s ON o.user_id = s.user_id
            WHERE o.pay_time < s.step1_time
              AND o.pay_time >= s.step1_time - INTERVAL '1' DAY * ?
              AND {_cat_expr(level_col)} != s.step1_cat
              AND {_cat_expr(level_col)} != ?
              AND {valid_sql}
              {excluded_cat_sql}
              {channel_sql}
              {exclude_sql}
            QUALIFY ROW_NUMBER() OVER (PARTITION BY o.user_id, s.step1_cat ORDER BY o.pay_time DESC) = 1
        )
        SELECT step1_cat, step2_cat, COUNT(DISTINCT user_id) as user_count
        FROM step2
        GROUP BY step1_cat, step2_cat
        ORDER BY user_count DESC
        LIMIT 20
        """
        pre_step2_params = (
            [target_category, target_start, end_date] + channel_params + exclude_params +
            [window_days, target_category] + top_pre_cats + excluded_params + channel_params + exclude_params +
            [window_days, target_category] + excluded_params + channel_params + exclude_params
        )
        pre_step2_result = conn.execute(pre_step2_sql, pre_step2_params).fetchall()
        for row in pre_step2_result:
            pre_step2_assoc.append({
                "from_cat": row[0],
                "to_cat": row[1],
                "user_count": int(row[2] or 0),
            })

    # ── 构建后置桑基图：目标品类 → 其他品类 [→ 再一步] ──
    post_nodes = [{"name": target_category, "category_name": target_category}]
    post_links = []
    post_node_names = {target_category}
    for item in post_assoc:
        post_nodes.append({"name": item["category_name"], "category_name": item["category_name"]})
        post_node_names.add(item["category_name"])
        post_links.append({
            "source": target_category,
            "target": item["category_name"],
            "value": item["user_count"],
        })
    # 2步后置扩展
    for item in post_step2_assoc:
        if item["to_cat"] not in post_node_names:
            post_nodes.append({"name": item["to_cat"], "category_name": item["to_cat"]})
            post_node_names.add(item["to_cat"])
        post_links.append({
            "source": item["from_cat"],
            "target": item["to_cat"],
            "value": item["user_count"],
        })
    # 流失节点：买了目标品类后未购买其他品类的用户
    post_churn = total_users - post_users_with_purchase
    if post_churn > 0:
        post_nodes.append({"name": "未购买其他", "category_name": "未购买其他"})
        post_links.append({
            "source": target_category,
            "target": "未购买其他",
            "value": post_churn,
        })

    # ── 构建前置桑基图：[再一步 →] 其他品类 → 目标品类 ──
    pre_nodes = []
    pre_links = []
    pre_node_names = set()
    for item in pre_assoc:
        pre_nodes.append({"name": item["category_name"], "category_name": item["category_name"]})
        pre_node_names.add(item["category_name"])
        pre_links.append({
            "source": item["category_name"],
            "target": target_category,
            "value": item["user_count"],
        })
    # 2步前置扩展
    for item in pre_step2_assoc:
        if item["from_cat"] not in pre_node_names:
            pre_nodes.append({"name": item["from_cat"], "category_name": item["from_cat"]})
            pre_node_names.add(item["from_cat"])
        pre_links.append({
            "source": item["from_cat"],
            "target": item["to_cat"],
            "value": item["user_count"],
        })
    pre_nodes.append({"name": target_category, "category_name": target_category})
    # 流失节点：买目标品类前未购买其他品类的用户
    pre_churn = total_users - pre_users_with_purchase
    if pre_churn > 0:
        pre_nodes.append({"name": "未购买其他", "category_name": "未购买其他"})
        pre_links.append({
            "source": "未购买其他",
            "target": target_category,
            "value": pre_churn,
        })

    return {
        "post_purchase": post_assoc,
        "pre_purchase": pre_assoc,
        "post_sankey": {"nodes": post_nodes, "links": post_links},
        "pre_sankey": {"nodes": pre_nodes, "links": pre_links},
    }
