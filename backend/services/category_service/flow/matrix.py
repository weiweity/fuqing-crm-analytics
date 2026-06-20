"""
品类分析服务
Sample CRM 客户分析系统 - 品类分析服务
Week 4 品类分布、品类象限矩阵、品类用户画像
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple


from backend.db.connection import get_connection
from backend.semantic.filters import FilterBuilder, MetricType
from .._shared import _cat_expr


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


# ─────────────────────────────────────────────────────────────
# Sprint 54 Lane B L3 FilterBuilder helpers
#
# 品类流转矩阵 (`get_category_flow_matrix`) 原 3 处 `(valid_order filter)` f-string
# 内嵌 + 多处 channel/exclude/excluded_cat 字符串拼接 — 全部收到 `?` DB-API
# 参数化. 设计原则:
#   1. 所有用户输入 (channel / exclude_channels / start_date / end_date /
#      top_n) 都走 `?` 占位, helper 返回的 params 列表即 DuckDB execute 参数.
#   2. valid_order / channel / exclude_channels 用 FilterBuilder.build() 统一产出.
#   3. excluded_cat (静态白名单) 走 `add_extra` 进 helper.
#   4. pay_time 范围用 `add_extra` (跟 temporal.py 一样保持 DATE() 形式).
# ─────────────────────────────────────────────────────────────


def _build_all_orders_filter(
    level_col: str,
    start_date: str,
    end_date: str,
    channel: Optional[str],
    exclude_channels: Optional[List[str]],
) -> Tuple[str, List[Any]]:
    """品类流转矩阵 all_orders CTE 过滤器 (top_cat_sql + flow_sql 共用).

    等价于原 WHERE 子句:
        WHERE o.pay_time >= ?
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND (valid_order filter)
          AND TRIM(COALESCE(o.{level_col}, '未知')) NOT IN (...)
          (channel filter)
          (exclude-channel filter)

    Returns:
        (where_sql, params) — 拼到 all_orders CTE 的 WHERE 内, 顺序对齐:
        [start_dt, end_date, EXCLUDED..., channel..., exclude...].
    """
    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    if channel and channel != "全店":
        fb.with_channels([channel])
    elif exclude_channels:
        fb.with_exclude_channels(exclude_channels)
    where_sql, params = fb.build()
    # 时间范围 + excluded_cat 进 add_extra
    extra_sql = "o.pay_time >= ? AND o.pay_time < DATE(?) + INTERVAL '1' DAY"
    extra_params: List[Any] = [f"{start_date} 00:00:00", end_date]
    placeholders = ",".join(["?"] * len(EXCLUDED_PRODUCT_CATEGORIES))
    extra_sql += f" AND TRIM(COALESCE(o.{level_col}, '未知')) NOT IN ({placeholders})"
    extra_params.extend(EXCLUDED_PRODUCT_CATEGORIES)
    return f"{extra_sql} AND {where_sql}", extra_params + params



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

        # all_orders CTE 过滤器 (top_cat_sql + flow_sql 共用)
        all_where, all_params = _build_all_orders_filter(
            level_col=level_col,
            start_date=window_start,
            end_date=end_date,
            channel=channel,
            exclude_channels=exclude_channels,
        )

        # TOP N 品类
        top_cat_sql = f"""
        WITH all_orders AS (
            SELECT {_cat_expr(level_col)} AS category_name, o.user_id, o.pay_time, o.order_id
            FROM orders o
            WHERE {all_where}
        ),
        user_first_order AS (
            SELECT user_id, category_name AS first_category, pay_time
            FROM all_orders o1
            WHERE order_id = (SELECT order_id FROM all_orders o2 WHERE o2.user_id = o1.user_id ORDER BY pay_time ASC LIMIT 1)
        )
        SELECT first_category, COUNT(DISTINCT user_id) AS first_users
        FROM user_first_order GROUP BY first_category ORDER BY first_users DESC LIMIT ?
        """
        top_cats_result = conn.execute(top_cat_sql + " OFFSET 0", all_params + [top_n]).fetchall()
        top_cats = [row[0] for row in top_cats_result]
        if len(top_cats) < top_n:
            top_cats_result = conn.execute(top_cat_sql, all_params + [top_n]).fetchall()
            top_cats = [row[0] for row in top_cats_result[:top_n]]

        # 全量流转
        flow_sql = f"""
        WITH all_orders AS (
            SELECT {_cat_expr(level_col)} AS category_name, o.user_id, o.pay_time, o.order_id
            FROM orders o
            WHERE {all_where}
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
        flow_result = conn.execute(flow_sql, all_params).fetchall()

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
        for link in raw_links:
            key = (link["source"], link["target"])
            if key in merged:
                merged[key]["value"] += link["value"]
            else:
                merged[key] = {"source": link["source"], "target": link["target"], "value": link["value"]}
        links = list(merged.values())

        node_names = list(dict.fromkeys(top_cats))
        for link in links:
            if link["source"] not in node_names:
                node_names.append(link["source"])
            if link["target"] not in node_names:
                node_names.append(link["target"])
        if other_node not in node_names:
            has_other = any(link["source"] == other_node or link["target"] == other_node for link in links)
            if has_other:
                node_names.append(other_node)

        sankey_data = {"nodes": [{"name": n, "category_name": n} for n in node_names], "links": links}

        # 全量矩阵
        all_from_cats, all_to_cats = [], []
        for row in flow_result:
            fc, tc = row[0], row[1]
            if fc not in all_from_cats:
                all_from_cats.append(fc)
            if tc not in all_to_cats:
                all_to_cats.append(tc)

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
        pass
