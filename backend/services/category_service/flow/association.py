"""
品类分析服务
Sample CRM 客户分析系统 - 品类分析服务
Week 4 品类分布、品类象限矩阵、品类用户画像
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List


from backend.db.connection import get_connection
from .._shared import _assoc_cache_lock, _assoc_cache, _ASSOC_CACHE_MAX_SIZE, _cat_expr, _excluded_cat_filter
from .temporal import _compute_temporal_association
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
            pass

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
        for link in raw_links:
            key = (link["source"], link["target"])
            if key in merged:
                merged[key]["value"] += link["value"]
            else:
                merged[key] = {"source": link["source"], "target": link["target"], "value": link["value"]}
        links = list(merged.values())

        # 重新构建节点列表
        node_names = list(dict.fromkeys(top_cats))  # 去重保序
        for link in links:
            if link["source"] not in node_names:
                node_names.append(link["source"])
            if link["target"] not in node_names:
                node_names.append(link["target"])
        if other_node not in node_names:
            has_other = any(link["source"] == other_node or link["target"] == other_node for link in links)
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
        pass

    return result
