"""品类分析服务"""
import duckdb
from datetime import datetime, timedelta, date
from typing import Dict, Any, Optional, List
from collections import OrderedDict

"""
芙清 CRM 客户分析系统 - 品类分析服务
Week 4 品类分布、品类象限矩阵、品类用户画像
"""

import duckdb
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from collections import OrderedDict
from backend.db.connection import get_connection
from backend.semantic.filters import OrderFilters, expand_channels
from backend.semantic.calculations import yoy_absolute, yoy_ratio
from backend.semantic.segments import RFM_THRESHOLDS


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
    from datetime import timedelta

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


def get_category_flow_matrix(
    start_date: str,
    end_date: str,
    level: str = "class",
    top_n: int = 10,
    window_days: int = 90,
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    品类流转 - 全局流转矩阵（首购→次购鸟瞰）
    独立接口，供前端懒加载使用。
    """
    import json
    from pathlib import Path
    import hashlib

    # 默认排除赠品&0.01和其他渠道
    DEFAULT_EXCLUDED_CHANNELS = ['赠品&0.01', '其他']
    if exclude_channels is None:
        exclude_channels = DEFAULT_EXCLUDED_CHANNELS.copy()
    else:
        merged = list(dict.fromkeys(exclude_channels + DEFAULT_EXCLUDED_CHANNELS))
        exclude_channels = merged

    cache_dir = Path("backend/cache/category_flow")
    channel_key = (channel or "") + "|" + "|".join(sorted(exclude_channels or []))
    channel_hash = hashlib.md5(channel_key.encode()).hexdigest()[:8]
    cache_file = cache_dir / f"flow_{start_date}_{end_date}_w{window_days}_full_{level}_{channel_hash}.json"

    # 尝试读取缓存（24小时TTL）
    import time
    _CACHE_TTL_SECONDS = 24 * 3600
    if cache_file.exists():
        try:
            if time.time() - cache_file.stat().st_mtime < _CACHE_TTL_SECONDS:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                return {
                    **cached,
                    "data_stale": False,
                    "data_quality_note": f"本Tab基于 {start_date}~{end_date} 窗口 {window_days} 天的流转数据计算（已排除赠品&0.01、其他渠道）",
                }
        except Exception:
            pass

    conn = get_connection()
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        window_start = (start_dt - timedelta(days=window_days)).strftime("%Y-%m-%d")

        level_col = SPU_LEVELS.get(level, "spu_product_class")
        valid_sql, _ = OrderFilters.valid_order()
        excluded_cat_sql = _excluded_cat_filter(level_col)

        base_params: List[Any] = [window_start, end_date] + list(EXCLUDED_PRODUCT_CATEGORIES)

        channel_sql = ""
        db_channels: List[str] = []
        if channel and channel != "全店":
            db_channels = [c for c in expand_channels([channel]) if c]
            if not db_channels:
                raise ValueError(f"渠道'{channel}'未在channels.py中注册，请检查UI_TO_DB映射")
            if len(db_channels) == 1:
                channel_sql = "AND o.channel = ?"
                base_params.append(db_channels[0])
            else:
                placeholders = ",".join(["?"] * len(db_channels))
                channel_sql = f"AND o.channel IN ({placeholders})"
                base_params.extend(db_channels)

        exclude_sql = ""
        db_ex: List[str] = []
        if exclude_channels:
            from backend.semantic.filters import expand_channels as _ec
            db_ex = _ec(exclude_channels)
            placeholders = ",".join(["?"] * len(db_ex))
            exclude_sql = f"AND o.channel NOT IN ({placeholders})"
            base_params.extend(db_ex)

        # TOP N 品类
        top_cat_sql = f"""
        WITH all_orders AS (
            SELECT {_cat_expr(level_col)} AS category_name, o.user_id, o.pay_time, o.order_id
            FROM orders o
            WHERE o.pay_time >= ? AND o.pay_time < DATE(?) + INTERVAL '1' DAY
              AND {valid_sql} {excluded_cat_sql} {channel_sql} {exclude_sql}
        ),
        user_first_order AS (
            SELECT user_id, category_name AS first_category, pay_time
            FROM all_orders o1
            WHERE order_id = (SELECT order_id FROM all_orders o2 WHERE o2.user_id = o1.user_id ORDER BY pay_time ASC LIMIT 1)
        )
        SELECT first_category, COUNT(DISTINCT user_id) AS first_users
        FROM user_first_order GROUP BY first_category ORDER BY first_users DESC LIMIT ?
        """
        top_cats_result = conn.execute(top_cat_sql + " OFFSET 0", base_params + [top_n]).fetchall()
        top_cats = [row[0] for row in top_cats_result]
        if len(top_cats) < top_n:
            top_cats_result = conn.execute(top_cat_sql, base_params + [top_n]).fetchall()
            top_cats = [row[0] for row in top_cats_result[:top_n]]

        # 全量流转
        params_flow = [window_start, end_date] + list(EXCLUDED_PRODUCT_CATEGORIES)
        if channel and channel != "全店":
            params_flow.extend(db_channels)
        if exclude_channels:
            params_flow.extend(db_ex)

        flow_sql = f"""
        WITH all_orders AS (
            SELECT {_cat_expr(level_col)} AS category_name, o.user_id, o.pay_time, o.order_id
            FROM orders o
            WHERE o.pay_time >= ? AND o.pay_time < DATE(?) + INTERVAL '1' DAY
              AND {valid_sql} {excluded_cat_sql} {channel_sql} {exclude_sql}
        ),
        user_first_order AS (
            SELECT user_id, category_name AS first_category, pay_time
            FROM all_orders o1
            WHERE order_id = (SELECT order_id FROM all_orders o2 WHERE o2.user_id = o1.user_id ORDER BY pay_time ASC LIMIT 1)
        ),
        user_second_order AS (
            SELECT user_id, category_name AS second_category, pay_time
            FROM all_orders o1
            WHERE order_id = (SELECT order_id FROM all_orders o2 WHERE o2.user_id = o1.user_id ORDER BY pay_time ASC LIMIT 1 OFFSET 1)
        ),
        flow_pairs AS (
            SELECT COALESCE(fo.first_category, '未知') AS from_cat,
                   COALESCE(so.second_category, '未知') AS to_cat,
                   COUNT(DISTINCT fo.user_id) AS flow_users
            FROM user_first_order fo
            INNER JOIN user_second_order so ON fo.user_id = so.user_id
            GROUP BY fo.first_category, so.second_category
        )
        SELECT from_cat, to_cat, flow_users FROM flow_pairs WHERE from_cat != to_cat ORDER BY flow_users DESC
        """
        flow_result = conn.execute(flow_sql, params_flow).fetchall()

        # 构建桑基图
        other_node = "其他"
        raw_links = []
        for row in flow_result:
            from_cat, to_cat, users = row[0], row[1], int(row[2] or 0)
            if users > 0 and from_cat != to_cat:
                src = from_cat if from_cat in top_cats else other_node
                tgt = to_cat if to_cat in top_cats else other_node
                raw_links.append({"source": src, "target": tgt, "value": users})

        merged = {}
        for l in raw_links:
            key = (l["source"], l["target"])
            if key in merged:
                merged[key]["value"] += l["value"]
            else:
                merged[key] = {"source": l["source"], "target": l["target"], "value": l["value"]}
        links = list(merged.values())

        node_names = list(dict.fromkeys(top_cats))
        for l in links:
            if l["source"] not in node_names: node_names.append(l["source"])
            if l["target"] not in node_names: node_names.append(l["target"])
        if other_node not in node_names:
            has_other = any(l["source"] == other_node or l["target"] == other_node for l in links)
            if has_other: node_names.append(other_node)

        sankey_data = {"nodes": [{"name": n, "category_name": n} for n in node_names], "links": links}

        # 全量矩阵
        all_from_cats, all_to_cats = [], []
        for row in flow_result:
            fc, tc = row[0], row[1]
            if fc not in all_from_cats: all_from_cats.append(fc)
            if tc not in all_to_cats: all_to_cats.append(tc)

        from_totals = {cat: 0 for cat in all_from_cats}
        to_totals = {cat: 0 for cat in all_to_cats}
        for row in flow_result:
            fc, tc, users = row[0], row[1], int(row[2] or 0)
            if fc in from_totals: from_totals[fc] += users
            if tc in to_totals: to_totals[tc] += users

        sources = sorted(all_from_cats, key=lambda c: from_totals.get(c, 0), reverse=True)
        targets = sorted(all_to_cats, key=lambda c: to_totals.get(c, 0), reverse=True)

        matrix = [[0] * len(targets) for _ in range(len(sources))]
        for row in flow_result:
            from_cat, to_cat, users = row[0], row[1], int(row[2] or 0)
            if from_cat in sources and to_cat in targets:
                matrix[sources.index(from_cat)][targets.index(to_cat)] = users

        row_totals = [sum(r) for r in matrix]
        concentration_warnings = []
        for i, src in enumerate(sources):
            total_inflow = sum(matrix[j][i] for j in range(len(sources)))
            if total_inflow > 0:
                max_source_ratio = max(matrix[j][i] for j in range(len(sources))) / total_inflow
                if max_source_ratio > 0.6:
                    concentration_warnings.append(f"{src} 过度依赖单一来源(占比>{int(max_source_ratio*100)}%)")

        flow_matrix_data = {
            "sources": sources, "targets": targets, "matrix": matrix,
            "row_totals": row_totals, "concentration_warnings": concentration_warnings,
        }

        # 保存缓存
        cache_dir.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"sankey_data": sankey_data, "matrix": flow_matrix_data}, f, ensure_ascii=False)

        return {
            "sankey_data": sankey_data,
            "matrix": flow_matrix_data,
            "data_stale": False,
            "data_quality_note": f"本Tab基于 {start_date}~{end_date} 窗口 {window_days} 天的流转数据计算（已排除赠品&0.01、其他渠道）",
        }
    finally:
        conn.close()

def _get_cached_association(cache_key: str, compute_fn):
    """
    带锁的内存缓存，5分钟TTL，LRU淘汰（最多保留100条）。
    锁覆盖 check+compute 全程，避免并发 cache-miss 导致的重复计算。
    """
    import time

    # ── 锁内检查：命中则直接返回 ──
    with _assoc_cache_lock:
        now = time.time()
        entry = _assoc_cache.get(cache_key)
        if entry and (now - entry["ts"]) < 300:
            _assoc_cache.move_to_end(cache_key)
            return entry["data"]

    # ── 未命中：在锁外计算（避免长时间持锁阻塞其他线程访问缓存）────
    # 但写回仍需竞争锁，避免并发写入覆盖
    data = compute_fn()

    with _assoc_cache_lock:
        _assoc_cache[cache_key] = {"data": data, "ts": now}
        # LRU淘汰：超过上限时移除最老的条目
        while len(_assoc_cache) > _ASSOC_CACHE_MAX_SIZE:
            _assoc_cache.pop(next(iter(_assoc_cache)))
    return data

def get_category_flow_association(
    start_date: str,
    end_date: str,
    level: str = "class",
    window_days: int = 90,
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
    target_category: Optional[str] = None,
    anchor_mode: str = "last",
    path_depth: int = 1,
) -> Dict[str, Any]:
    """
    品类流转 - 时序关联分析（买了产品A之后/之前买了什么）
    独立接口，支持内存缓存。
    """
    if not target_category:
        return {
            "target_category": "",
            "post_purchase": [],
            "pre_purchase": [],
            "post_sankey": {"nodes": [], "links": []},
            "pre_sankey": {"nodes": [], "links": []},
            "data_quality_note": "",
        }

    import hashlib
    # 对列表参数排序，确保缓存键顺序稳定
    _excluded = tuple(sorted(exclude_channels)) if exclude_channels else ()
    cache_key = hashlib.md5(
        f"{start_date}|{end_date}|{level}|{window_days}|{channel}|{_excluded}|{target_category}|{anchor_mode}|{path_depth}".encode()
    ).hexdigest()

    def _compute():
        conn = get_connection()
        try:
            temporal = _compute_temporal_association(
                conn, target_category, start_date, end_date,
                level, window_days, channel, exclude_channels, anchor_mode, path_depth)
            return {
                "target_category": target_category,
                "post_purchase": temporal["post_purchase"],
                "pre_purchase": temporal["pre_purchase"],
                "post_sankey": temporal["post_sankey"],
                "pre_sankey": temporal["pre_sankey"],
                "data_quality_note": f"基于 {end_date} 往前追溯 {window_days} 天 · 锚点={anchor_mode} · 目标品类={target_category}",
            }
        finally:
            conn.close()

    return _get_cached_association(cache_key, _compute)

def get_category_flow(
    start_date: str,
    end_date: str,
    level: str = "class",
    top_n: int = 10,
    window_days: int = 90,
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
    target_category: Optional[str] = None,
    anchor_mode: str = "every",
    path_depth: int = 1,
) -> Dict[str, Any]:
    """
    品类流转 - 桑基图数据 + 流转矩阵 + 时序关联分析

    Args:
        start_date: 周期开始日期
        end_date: 周期结束日期
        level: 品类级别
        top_n: TOP N 品类（仅用于桑基图归类，矩阵返回全量）
        window_days: 流转时间窗口(天)
        channel: 渠道筛选
        exclude_channels: 排除渠道列表（默认排除赠品&0.01、其他）
        target_category: 目标品类(传入时返回前后置购买关联)
        path_depth: 路径深度(1=直接前后置, 2=再向外延伸一步)

    Returns:
        CategoryFlowResponse 结构（matrix为全量矩阵，含row_totals）
    """
    import json
    from pathlib import Path

    # 默认排除赠品&0.01和其他渠道，避免污染品类流转数据
    # 注意：UI名后续通过 expand_channels() 映射为 DB 名
    # 数据来源：channels.py UI_TO_DB 的键名
    DEFAULT_EXCLUDED_CHANNELS = ['赠品&0.01', '其他']
    if exclude_channels is None:
        exclude_channels = DEFAULT_EXCLUDED_CHANNELS.copy()
    else:
        # 合并用户指定和默认排除的渠道
        merged = list(dict.fromkeys(exclude_channels + DEFAULT_EXCLUDED_CHANNELS))
        exclude_channels = merged

    # 有 target_category 时不走缓存(动态分析)
    cache_dir = Path("backend/cache/category_flow")
    import hashlib
    channel_key = (channel or "") + "|" + "|".join(sorted(exclude_channels or []))
    channel_hash = hashlib.md5(channel_key.encode()).hexdigest()[:8]
    # 缓存key增加 _full 后缀，与旧版10x10矩阵缓存区分
    cache_file = cache_dir / f"flow_{start_date}_{end_date}_w{window_days}_full_{level}_{channel_hash}.json"

    # 尝试读取缓存(仅在无 target_category 时)
    data_stale = False
    if target_category is None and cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
            # 时序关联为空(缓存数据不带此字段)
            cached.setdefault("target_category", None)
            cached.setdefault("post_purchase", None)
            cached.setdefault("pre_purchase", None)
            return {
                **cached,
                "data_stale": False,
                "data_quality_note": f"本Tab基于 {start_date}~{end_date} 窗口 {window_days} 天的流转数据计算（已排除赠品&0.01、其他渠道）",
            }
        except Exception:
            data_stale = True

    conn = get_connection()
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        window_start = (start_dt - timedelta(days=window_days)).strftime("%Y-%m-%d")

        level_col = SPU_LEVELS.get(level, "spu_product_class")
        valid_sql, _ = OrderFilters.valid_order()
        excluded_cat_sql = _excluded_cat_filter(level_col)

        # 构建基础 params(只包含日期过滤,channel/exclude 动态追加)
        base_params: List[Any] = [window_start, end_date] + list(EXCLUDED_PRODUCT_CATEGORIES)

        channel_sql = ""
        db_channels: List[str] = []
        if channel and channel != "全店":
            db_channels = [c for c in expand_channels([channel]) if c]
            if not db_channels:
                raise ValueError(f"渠道'{channel}'未在channels.py中注册，请检查UI_TO_DB映射")
            if len(db_channels) == 1:
                channel_sql = "AND o.channel = ?"
                base_params.append(db_channels[0])
            else:
                placeholders = ",".join(["?"] * len(db_channels))
                channel_sql = f"AND o.channel IN ({placeholders})"
                base_params.extend(db_channels)

        exclude_sql = ""
        db_ex: List[str] = []
        if exclude_channels:
            from backend.semantic.filters import expand_channels as _ec
            db_ex = _ec(exclude_channels)
            placeholders = ",".join(["?"] * len(db_ex))
            exclude_sql = f"AND o.channel NOT IN ({placeholders})"
            base_params.extend(db_ex)

        # 查找TOP N品类（仅用于桑基图归类）
        top_cat_sql = f"""
        WITH all_orders AS (
            SELECT
                {_cat_expr(level_col)} AS category_name,
                o.user_id,
                o.pay_time,
                o.order_id
            FROM orders o
            WHERE o.pay_time >= ?
              AND o.pay_time < DATE(?) + INTERVAL '1' DAY
              AND {valid_sql}
              {excluded_cat_sql}
              {channel_sql}
              {exclude_sql}
        ),
        user_first_order AS (
            SELECT user_id, category_name AS first_category, pay_time
            FROM all_orders o1
            WHERE order_id = (
                SELECT order_id FROM all_orders o2
                WHERE o2.user_id = o1.user_id
                ORDER BY pay_time ASC LIMIT 1
            )
        ),
        user_second_order AS (
            SELECT user_id, category_name AS second_category, pay_time
            FROM all_orders o1
            WHERE order_id = (
                SELECT order_id FROM all_orders o2
                WHERE o2.user_id = o1.user_id
                ORDER BY pay_time ASC LIMIT 1 OFFSET 1
            )
        )
        SELECT first_category, COUNT(DISTINCT user_id) AS first_users
        FROM user_first_order
        GROUP BY first_category
        ORDER BY first_users DESC
        LIMIT ?
        """
        top_cats_result = conn.execute(top_cat_sql + " OFFSET 0", base_params + [top_n]).fetchall()
        top_cats = [row[0] for row in top_cats_result]

        if len(top_cats) < top_n:
            top_cats_result = conn.execute(top_cat_sql, base_params + [top_n]).fetchall()
            top_cats = [row[0] for row in top_cats_result[:top_n]]

        # 全量流转SQL：不限制在top_cats内，查询全部品类的流转
        # 参数: 2个日期 + excluded_cat + channel + exclude
        params_flow = [window_start, end_date] + list(EXCLUDED_PRODUCT_CATEGORIES)
        if channel and channel != "全店":
            params_flow.extend(db_channels)
        if exclude_channels:
            params_flow.extend(db_ex)

        flow_sql = f"""
        WITH all_orders AS (
            SELECT
                {_cat_expr(level_col)} AS category_name,
                o.user_id,
                o.pay_time,
                o.order_id
            FROM orders o
            WHERE o.pay_time >= ?
              AND o.pay_time < DATE(?) + INTERVAL '1' DAY
              AND {valid_sql}
              {excluded_cat_sql}
              {channel_sql}
              {exclude_sql}
        ),
        user_first_order AS (
            SELECT user_id, category_name AS first_category, pay_time
            FROM all_orders o1
            WHERE order_id = (
                SELECT order_id FROM all_orders o2
                WHERE o2.user_id = o1.user_id
                ORDER BY pay_time ASC LIMIT 1
            )
        ),
        user_second_order AS (
            SELECT user_id, category_name AS second_category, pay_time
            FROM all_orders o1
            WHERE order_id = (
                SELECT order_id FROM all_orders o2
                WHERE o2.user_id = o1.user_id
                ORDER BY pay_time ASC LIMIT 1 OFFSET 1
            )
        ),
        flow_pairs AS (
            SELECT
                COALESCE(fo.first_category, '未知') AS from_cat,
                COALESCE(so.second_category, '未知') AS to_cat,
                COUNT(DISTINCT fo.user_id) AS flow_users
            FROM user_first_order fo
            INNER JOIN user_second_order so ON fo.user_id = so.user_id
            GROUP BY fo.first_category, so.second_category
        )
        SELECT from_cat, to_cat, flow_users
        FROM flow_pairs
        WHERE from_cat != to_cat
        ORDER BY flow_users DESC
        """
        flow_result = conn.execute(flow_sql, params_flow).fetchall()

        # 构建桑基图数据（仍按TOP10+其他归类，保证可视化可读性）
        other_node = "其他"
        raw_links = []
        for row in flow_result:
            from_cat, to_cat, users = row[0], row[1], int(row[2] or 0)
            if users > 0 and from_cat != to_cat:
                # 非TOP品类归类到"其他"
                src = from_cat if from_cat in top_cats else other_node
                tgt = to_cat if to_cat in top_cats else other_node
                raw_links.append({"source": src, "target": tgt, "value": users})

        # 合并同名link（归类后可能产生重复source→target）
        merged = {}
        for l in raw_links:
            key = (l["source"], l["target"])
            if key in merged:
                merged[key]["value"] += l["value"]
            else:
                merged[key] = {"source": l["source"], "target": l["target"], "value": l["value"]}
        links = list(merged.values())

        # 重新构建节点列表
        node_names = list(dict.fromkeys(top_cats))  # 去重保序
        for l in links:
            if l["source"] not in node_names:
                node_names.append(l["source"])
            if l["target"] not in node_names:
                node_names.append(l["target"])
        if other_node not in node_names:
            has_other = any(l["source"] == other_node or l["target"] == other_node for l in links)
            if has_other:
                node_names.append(other_node)

        sankey_data = {
            "nodes": [{"name": n, "category_name": n} for n in node_names],
            "links": links,
        }

        # 全量流转矩阵构建
        # 收集所有作为来源或目标出现过的品类
        all_from_cats = []
        all_to_cats = []
        for row in flow_result:
            fc, tc = row[0], row[1]
            if fc not in all_from_cats:
                all_from_cats.append(fc)
            if tc not in all_to_cats:
                all_to_cats.append(tc)

        # 按总流转量排序（来源按总流出量，目标按总流入量）
        from_totals = {cat: 0 for cat in all_from_cats}
        to_totals = {cat: 0 for cat in all_to_cats}
        for row in flow_result:
            fc, tc, users = row[0], row[1], int(row[2] or 0)
            if fc in from_totals:
                from_totals[fc] += users
            if tc in to_totals:
                to_totals[tc] += users

        sources = sorted(all_from_cats, key=lambda c: from_totals.get(c, 0), reverse=True)
        targets = sorted(all_to_cats, key=lambda c: to_totals.get(c, 0), reverse=True)

        # 构建全量矩阵
        matrix = [[0] * len(targets) for _ in range(len(sources))]
        for row in flow_result:
            from_cat, to_cat, users = row[0], row[1], int(row[2] or 0)
            if from_cat in sources and to_cat in targets:
                from_idx = sources.index(from_cat)
                to_idx = targets.index(to_cat)
                matrix[from_idx][to_idx] = users

        # 计算每行总和（用于前端行百分比计算）
        row_totals = [sum(row) for row in matrix]

        # 来源集中度警告
        concentration_warnings = []
        for i, src in enumerate(sources):
            total_inflow = sum(matrix[j][i] for j in range(len(sources)))
            if total_inflow > 0:
                max_source_ratio = max(matrix[j][i] for j in range(len(sources))) / total_inflow
                if max_source_ratio > 0.6:
                    concentration_warnings.append(f"{src} 过度依赖单一来源(占比>{int(max_source_ratio*100)}%)")

        flow_matrix_data = {
            "sources": sources,
            "targets": targets,
            "matrix": matrix,
            "row_totals": row_totals,
            "concentration_warnings": concentration_warnings,
        }

        # 保存缓存
        cache_dir.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"sankey_data": sankey_data, "matrix": flow_matrix_data}, f, ensure_ascii=False)

        result = {
            "sankey_data": sankey_data,
            "matrix": flow_matrix_data,
            "data_stale": data_stale,
            "data_quality_note": f"本Tab基于 {start_date}~{end_date} 窗口 {window_days} 天的流转数据计算（已排除赠品&0.01、其他渠道）",
        }

        # 时序关联分析
        if target_category:
            temporal = _compute_temporal_association(
                conn, target_category, start_date, end_date,
                level, window_days, channel, exclude_channels, anchor_mode, path_depth)
            result["target_category"] = target_category
            result["post_purchase"] = temporal["post_purchase"]
            result["pre_purchase"] = temporal["pre_purchase"]
            result["post_sankey"] = temporal["post_sankey"]
            result["pre_sankey"] = temporal["pre_sankey"]
    finally:
        conn.close()

    return result
