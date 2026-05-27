"""
品类流转预计算脚本
输出: backend/cache/category_flow/{start_date}_{end_date}_window{window_days}_level{level}.json

覆盖写入（幂等）：每次运行先删除旧缓存再写入新缓存。

降级策略：缓存不存在时返回最近缓存 + data_stale=true

Usage:
    python scripts/precompute_category_flow.py --start 2026-01-01 --end 2026-03-31 --window 90 --level class
    python scripts/precompute_category_flow.py --full   # 全量预计算所有支持的时间窗口组合
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# 添加项目根目录到 Python 路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

import duckdb
from backend.config import DUCKDB_PATH
from backend.db.connection import get_connection
from backend.semantic.filters import OrderFilters

# 缓存目录
CACHE_DIR = PROJECT_ROOT / "backend" / "cache" / "category_flow"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# SPU 字段映射（与 category_service.py 保持一致）
SPU_LEVELS = {
    "category": "spu_category",
    "type": "spu_type",
    "tier": "spu_tier",
    "class": "spu_product_class",
    "subclass": "spu_product_subclass",
    "cosmetic": "spu_cosmetic",
    "spec": "spu_spec",
}


def _normalize_date(date_val) -> str:
    """统一日期格式处理"""
    if hasattr(date_val, 'strftime'):
        return date_val.strftime("%Y-%m-%d")
    if isinstance(date_val, str):
        return date_val[:10] if len(date_val) > 10 else date_val
    return str(date_val)


def _get_cache_path(start_date: str, end_date: str, window_days: int, level: str) -> Path:
    """生成缓存文件路径"""
    return CACHE_DIR / f"{start_date}_{end_date}_window{window_days}_level{level}.json"


def _get_latest_cache() -> Optional[Path]:
    """获取最新的缓存文件（用于降级）"""
    if not CACHE_DIR.exists():
        return None
    files = list(CACHE_DIR.glob("*.json"))
    if not files:
        return None
    return max(files, key=lambda f: f.stat().st_mtime)


def _get_top_categories(conn, start_date: str, end_date: str, level: str, top_n: int = 12) -> List[str]:
    """
    获取 GMV TOP N 的品类列表（用于限定桑基图节点）。
    包含 TOP(N-1) + "其他"，最多返回 top_n 个。
    """
    category_field = SPU_LEVELS.get(level, "spu_product_class")
    valid_sql, _ = OrderFilters.valid_order()

    query = f"""
        SELECT COALESCE({category_field}, '未知') as category,
               SUM(o.actual_amount) as gmv
        FROM orders o
        WHERE o.pay_time >= ? AND o.pay_time <= ?
          AND {valid_sql}
          AND {category_field} IS NOT NULL
        GROUP BY {category_field}
        ORDER BY gmv DESC
        LIMIT ?
    """
    df = conn.execute(query, [f"{start_date} 00:00:00", f"{end_date} 23:59:59", top_n - 1]).fetchdf()

    categories = df['category'].tolist()
    # 如果品类不足 top_n-1 个，补 "其他" 节点
    if len(categories) < top_n - 1:
        pass  # 已有足够品类
    elif len(categories) >= top_n - 1:
        categories = categories[:top_n - 1]

    return categories


def precompute_category_flow(
    start_date: str,
    end_date: str,
    window_days: int = 90,
    level: str = "class",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    品类流转预计算核心逻辑。

    定义"流转"：在查询时间窗口内，用户先购买了品类A（该用户在此窗口内的首单所属品类），
    后购买了品类B（该用户的第二单所属品类，A ≠ B）。

    Args:
        start_date: 分析起始日期 (YYYY-MM-DD)
        end_date: 分析结束日期 (YYYY-MM-DD)
        window_days: 流转判断窗口天数（默认90天，从end_date往前推）
        level: 品类维度（class/type/tier等）
        channel: 渠道筛选（可选）
        exclude_channels: 排除渠道列表（可选）

    Returns:
        {
            "sankey_data": {
                "nodes": [{"name": str}, ...],
                "links": [{"source": str, "target": str, "value": int}, ...]
            },
            "matrix": [[row_category, col_category, user_count], ...],
            "source_concentration": {target_category: {"top1_source": str, "top1_ratio": float}, ...},
            "data_stale": bool,
            "meta": {...}
        }
    """
    # 实际计算窗口：end_date 往前 window_days 天
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    calc_start = (end_dt - timedelta(days=window_days)).strftime("%Y-%m-%d")

    category_field = SPU_LEVELS.get(level, "spu_product_class")
    valid_sql, _ = OrderFilters.valid_order()

    conn = get_connection()

    # 获取 TOP 品类列表（用于限定节点数量）
    top_categories = _get_top_categories(conn, calc_start, end_date, level, top_n=12)

    # 构建渠道过滤
    channel_filter = ""
    channel_params = []
    if channel:
        channel_filter = "AND o.channel = ?"
        channel_params = [channel]

    exclude_filter = ""
    exclude_params = []
    if exclude_channels:
        placeholders = ",".join(["?"] * len(exclude_channels))
        exclude_filter = f"AND o.channel NOT IN ({placeholders})"
        exclude_params = list(exclude_channels)

    # ─────────────────────────────────────────────────────────────
    # Step 1: 找出每个用户在窗口内的所有订单，按时间排序
    # ─────────────────────────────────────────────────────────────
    # 过滤条件参数
    filter_params = [f"{calc_start} 00:00:00", f"{end_date} 23:59:59"]
    filter_params.extend(channel_params)
    filter_params.extend(exclude_params)

    # CTE: 用户在窗口内的所有有效订单（带品类）
    query = f"""
        WITH window_orders AS (
            SELECT
                o.user_id,
                o.order_id,
                o.pay_time,
                COALESCE(o.{category_field}, '未知') as category,
                ROW_NUMBER() OVER (
                    PARTITION BY o.user_id
                    ORDER BY o.pay_time ASC, o.order_id ASC
                ) as order_seq
            FROM orders o
            WHERE o.pay_time >= ? AND o.pay_time <= ?
              AND {valid_sql}
              {channel_filter}
              {exclude_filter}
        ),
        -- Step 2: 找首购和次购
        first_purchases AS (
            SELECT user_id, category as first_category
            FROM window_orders
            WHERE order_seq = 1
        ),
        second_purchases AS (
            SELECT user_id, category as second_category
            FROM window_orders
            WHERE order_seq = 2
        )
        -- Step 3: 流转匹配（首购 ≠ 次购）
        SELECT
            f.first_category,
            s.second_category,
            COUNT(DISTINCT f.user_id) as user_count
        FROM first_purchases f
        INNER JOIN second_purchases s ON f.user_id = s.user_id
        WHERE f.first_category != s.second_category
        GROUP BY f.first_category, s.second_category
        ORDER BY user_count DESC
    """

    flow_df = conn.execute(query, filter_params).fetchdf()
    conn.close()

    # ─────────────────────────────────────────────────────────────
    # Step 4: 构建桑基图数据
    # ─────────────────────────────────────────────────────────────
    # 节点列表：TOP10 品类 + "其他" + "流失" 节点
    all_categories = set(flow_df['first_category'].dropna().unique()) | \
                     set(flow_df['second_category'].dropna().unique())

    # 使用 TOP10 作为节点，之外的归为"其他"
    top_set = set(top_categories)
    other_categories = [c for c in all_categories if c not in top_set and c != '未知']

    # 节点
    nodes = []
    node_names = set()

    for cat in top_categories:
        if cat not in node_names:
            nodes.append({"name": cat})
            node_names.add(cat)

    if other_categories:
        nodes.append({"name": "其他"})
        node_names.add("其他")

    # "流失"节点：首购但无次购的用户（窗口内只有一单）
    conn2 = get_connection()

    # 计算流失用户数（有首购无次购）
    loss_query = f"""
        WITH window_orders AS (
            SELECT
                o.user_id,
                COALESCE(o.{category_field}, '未知') as category,
                COALESCE(o.{category_field}, '未知') as first_category,
                ROW_NUMBER() OVER (
                    PARTITION BY o.user_id
                    ORDER BY o.pay_time ASC, o.order_id ASC
                ) as order_seq,
                COUNT(*) OVER (PARTITION BY o.user_id) as total_orders
            FROM orders o
            WHERE o.pay_time >= ? AND o.pay_time <= ?
              AND {valid_sql}
              {channel_filter}
              {exclude_filter}
        )
        SELECT
            first_category,
            COUNT(DISTINCT user_id) as loss_users
        FROM window_orders
        WHERE order_seq = 1 AND total_orders = 1
        GROUP BY first_category
    """
    loss_params = [f"{calc_start} 00:00:00", f"{end_date} 23:59:59"]
    loss_params.extend(channel_params)
    loss_params.extend(exclude_params)

    loss_df = conn2.execute(loss_query, loss_params).fetchdf()
    conn2.close()

    # 添加流失节点
    loss_categories_in_top = [row['first_category'] for _, row in loss_df.iterrows()
                              if row['first_category'] in node_names]
    if loss_categories_in_top:
        nodes.append({"name": "流失"})
        node_names.add("流失")

    # 边（流转）
    links = []
    for _, row in flow_df.iterrows():
        src = row['first_category']
        tgt = row['second_category']

        # 映射到节点名称（不在 TOP 里的归为"其他"）
        if src not in node_names:
            src = "其他"
        if tgt not in node_names:
            tgt = "其他"

        links.append({
            "source": src,
            "target": tgt,
            "value": int(row['user_count'])
        })

    # 流失边
    for _, row in loss_df.iterrows():
        src = row['first_category']
        if src not in node_names:
            continue
        links.append({
            "source": src,
            "target": "流失",
            "value": int(row['loss_users'])
        })

    # ─────────────────────────────────────────────────────────────
    # Step 5: 流转矩阵
    # ─────────────────────────────────────────────────────────────
    matrix = []
    for _, row in flow_df.iterrows():
        matrix.append([
            row['first_category'],
            row['second_category'],
            int(row['user_count'])
        ])

    # ─────────────────────────────────────────────────────────────
    # Step 6: 来源集中度
    # ─────────────────────────────────────────────────────────────
    source_concentration = {}
    # 按目标品类聚合
    inflow_by_target = flow_df.groupby('second_category')['user_count'].sum()
    top1_source_by_target = flow_df.loc[
        flow_df.groupby('second_category')['user_count'].idxmax()
    ]

    for _, row in top1_source_by_target.iterrows():
        tgt = row['second_category']
        if tgt not in inflow_by_target.index:
            continue
        total = inflow_by_target[tgt]
        if total > 0:
            ratio = row['user_count'] / total
            source_concentration[tgt] = {
                "top1_source": row['first_category'],
                "top1_ratio": round(float(ratio), 4)
            }

    # ─────────────────────────────────────────────────────────────
    # Step 7: 合并links中相同source-target的value
    # ─────────────────────────────────────────────────────────────
    merged_links = {}
    for link in links:
        key = (link['source'], link['target'])
        merged_links[key] = merged_links.get(key, 0) + link['value']

    final_links = [
        {"source": k[0], "target": k[1], "value": v}
        for k, v in merged_links.items()
    ]

    result = {
        "sankey_data": {
            "nodes": nodes,
            "links": final_links
        },
        "matrix": matrix,
        "source_concentration": source_concentration,
        "data_stale": False,
        "meta": {
            "start_date": calc_start,
            "end_date": end_date,
            "window_days": window_days,
            "level": level,
            "channel": channel,
            "exclude_channels": exclude_channels,
            "total_categories": len(top_categories),
            "total_flow_users": int(flow_df['user_count'].sum()),
            "generated_at": datetime.now().isoformat()
        }
    }

    return result


def save_cache(
    start_date: str,
    end_date: str,
    window_days: int,
    level: str,
    data: Dict[str, Any]
) -> Path:
    """
    保存预计算结果到缓存文件（覆盖写入，幂等）。
    """
    cache_path = _get_cache_path(start_date, end_date, window_days, level)
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return cache_path


def load_cache(
    start_date: str,
    end_date: str,
    window_days: int,
    level: str
) -> Optional[Dict[str, Any]]:
    """
    加载指定参数的缓存文件。
    """
    cache_path = _get_cache_path(start_date, end_date, window_days, level)
    if cache_path.exists():
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def load_latest_cache_with_stale_flag() -> tuple:
    """
    降级策略：返回最新缓存 + data_stale=True。
    Returns: (data_dict, cache_path) or (None, None)
    """
    latest = _get_latest_cache()
    if latest is None:
        return None, None

    with open(latest, 'r', encoding='utf-8') as f:
        data = json.load(f)

    data['data_stale'] = True
    return data, latest


def run_precomputation(
    start_date: str,
    end_date: str,
    window_days: int = 90,
    level: str = "class",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    运行预计算：先计算再保存到缓存。
    Returns the computed result (also saved to cache).
    """
    print(f"\n品类流转预计算: {start_date} ~ {end_date} (窗口: {window_days}天, level={level})")

    # 尝试加载缓存（幂等：已有缓存则跳过重新计算）
    cached = load_cache(start_date, end_date, window_days, level)
    if cached is not None:
        print(f"  [缓存命中] {cached.get('meta', {}).get('generated_at', 'unknown')}")
        cached['data_stale'] = False
        return cached

    # 执行预计算
    result = precompute_category_flow(
        start_date=start_date,
        end_date=end_date,
        window_days=window_days,
        level=level,
        channel=channel,
        exclude_channels=exclude_channels,
    )

    # 保存缓存
    cache_path = save_cache(start_date, end_date, window_days, level, result)
    print(f"  [已保存] {cache_path.name}")
    print(f"  流转用户总数: {result['meta']['total_flow_users']:,}")

    return result


def run_full_precomputation():
    """
    全量预计算：覆盖所有支持的时间窗口组合。
    用于 ETL --update 后自动触发。
    """
    print("\n" + "=" * 60)
    print("品类流转预计算 - 全量模式")
    print("=" * 60)

    from backend.config import DUCKDB_PATH

    # 获取数据库最新数据日期
    conn = get_connection()
    try:
        max_pay = conn.execute("SELECT MAX(pay_time) FROM orders").fetchone()[0]
        if max_pay is None:
            print("  [警告] 数据库为空，跳过预计算")
            return
        end_date = _normalize_date(max_pay)
    finally:
        conn.close()

    # 定义预计算组合
    window_days_list = [30, 90, 180]
    level_list = ["class", "category"]

    # 生成历史时间窗口（近2年，每季度一个end_date）
    import calendar
    end_dates = []
    for year in [2025, 2026]:
        for month in range(1, 13):
            last_day = calendar.monthrange(year, month)[1]
            end_dates.append(f"{year}-{month:02d}-{last_day:02d}")

    total = len(window_days_list) * len(level_list) * len(end_dates)
    print(f"  预计算组合: {len(window_days_list)} 窗口 × {len(level_list)} 级别 × {len(end_dates)} 期间 = {total} 个")

    completed = 0
    skipped = 0

    for window_days in window_days_list:
        for level in level_list:
            for end_date in end_dates:
                # 计算start_date（往前推window_days，但不超过数据起始）
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                start_dt = end_dt - timedelta(days=window_days)
                start_date = start_dt.strftime("%Y-%m-%d")

                # 检查是否已有缓存
                cached = load_cache(start_date, end_date, window_days, level)
                if cached is not None:
                    skipped += 1
                    continue

                # 执行预计算
                try:
                    precompute_category_flow(
                        start_date=start_date,
                        end_date=end_date,
                        window_days=window_days,
                        level=level,
                    )
                    completed += 1
                    if completed % 20 == 0:
                        print(f"  进度: {completed}/{total} (跳过 {skipped})")
                except Exception as e:
                    print(f"  [错误] {start_date}~{end_date} w={window_days} l={level}: {e}")

    print(f"\n  全量预计算完成: {completed} 新增, {skipped} 跳过")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='品类流转预计算')
    parser.add_argument('--start', type=str, help='起始日期 YYYY-MM-DD')
    parser.add_argument('--end', type=str, help='结束日期 YYYY-MM-DD')
    parser.add_argument('--window', type=int, default=90, help='窗口天数 (默认90)')
    parser.add_argument('--level', type=str, default='class', help='品类级别 (默认class)')
    parser.add_argument('--full', action='store_true', help='全量预计算所有组合')
    args = parser.parse_args()

    if args.full:
        run_full_precomputation()
    elif args.start and args.end:
        result = run_precomputation(
            start_date=args.start,
            end_date=args.end,
            window_days=args.window,
            level=args.level,
        )
        print(f"\n  桑基图节点数: {len(result['sankey_data']['nodes'])}")
        print(f"  桑基图边数: {len(result['sankey_data']['links'])}")
        print(f"  来源集中度品类数: {len(result['source_concentration'])}")
    else:
        parser.print_help()
