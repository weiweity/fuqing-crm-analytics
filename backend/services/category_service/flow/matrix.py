"""
品类分析服务
芙清 CRM 客户分析系统 - 品类分析服务
Week 4 品类分布、品类象限矩阵、品类用户画像
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List


from backend.db.connection import get_connection
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
