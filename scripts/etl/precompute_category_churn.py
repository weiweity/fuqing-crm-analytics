"""
品类流失预警预计算脚本
输出: DuckDB category_churn_cache 表

覆盖写入（幂等）：每次运行先 DELETE 再 INSERT。

表结构:
    category_name   VARCHAR   -- 品类名称
    month           VARCHAR   -- 月份 (YYYY-MM)
    total_users     INTEGER   -- 当月购买该品类用户数
    churned_users   INTEGER   -- 流失用户数（品类间流失 + 沉默流失）
    inter_churn     INTEGER   -- 品类间流失（上期买A，本期买B≠A，且本期有订单）
    silent_churn    INTEGER   -- 沉默流失（上期买A，本期无任何订单）
    retained_users  INTEGER   -- 留存用户数
    retention_rate  DOUBLE   -- 留存率
    churn去向_json  VARCHAR   -- JSON: 品类间流失用户的本期购买品类分布
    generated_at    TIMESTAMP -- 生成时间

口径:
    - 本期 = 当前筛选的日期范围
    - 上期 = 同等长度往前推一个周期（严格相等，确保MoM可比）
    - 流失用户 = 上期购买了该品类、本期未购买该品类且购买了其他品类的用户
    - 品类间流失 = 上期买A，本期买B（B≠A，且本期有订单）
    - 沉默流失 = 上期买A，本期无任何订单
    - 两者互斥，合计 = 总流失用户数

Usage:
    python scripts/precompute_category_churn.py --start 2026-01-01 --end 2026-03-31
    python scripts/precompute_category_churn.py --full   # 全量预计算所有月份
"""

import sys
import argparse
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# 添加项目根目录到 Python 路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

import duckdb
from backend.db.connection import get_connection
from backend.semantic.filters import OrderFilters

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

# DuckDB 表名
TABLE_NAME = "category_churn_cache"


def _normalize_date(date_val) -> str:
    """统一日期格式处理"""
    if hasattr(date_val, 'strftime'):
        return date_val.strftime("%Y-%m-%d")
    if isinstance(date_val, str):
        return date_val[:10] if len(date_val) > 10 else date_val
    return str(date_val)


def _ensure_table(conn: duckdb.DuckDBPyConnection):
    """确保品类流失缓存表存在（幂等）"""
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            category_name   VARCHAR,
            month           VARCHAR,
            total_users     INTEGER,
            churned_users   INTEGER,
            inter_churn     INTEGER,
            silent_churn    INTEGER,
            retained_users  INTEGER,
            retention_rate  DOUBLE,
            churn去向_json  VARCHAR,
            generated_at    TIMESTAMP,
            PRIMARY KEY (category_name, month)
        )
    """)


def _clear_table(conn: duckdb.DuckDBPyConnection):
    """清空表（幂等覆盖写入）"""
    conn.execute(f"DELETE FROM {TABLE_NAME}")


def precompute_category_churn_month(
    conn: duckdb.DuckDBPyConnection,
    current_start: str,
    current_end: str,
    period_days: int,
    level: str = "class",
    exclude_channels: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    计算单个周期的品类流失数据。

    Args:
        conn: DuckDB 连接
        current_start: 本期起始日期 (YYYY-MM-DD)
        current_end: 本期结束日期 (YYYY-MM-DD)
        period_days: 周期天数（用于计算上期）
        level: 品类维度
        exclude_channels: 排除渠道列表

    Returns:
        List of dicts with churn metrics per category
    """
    category_field = SPU_LEVELS.get(level, "spu_product_class")
    valid_sql, _ = OrderFilters.valid_order()

    # 上期计算：往前推 period_days 天
    curr_end_dt = datetime.strptime(current_end, "%Y-%m-%d")
    prev_end_dt = curr_end_dt - timedelta(days=period_days)
    prev_start_dt = prev_end_dt - timedelta(days=period_days - 1)
    prev_start = prev_start_dt.strftime("%Y-%m-%d")
    prev_end = prev_end_dt.strftime("%Y-%m-%d")

    # 构建排除渠道过滤
    exclude_filter = ""
    exclude_params = []
    if exclude_channels:
        placeholders = ",".join(["?"] * len(exclude_channels))
        exclude_filter = f"AND o.channel NOT IN ({placeholders})"
        exclude_params = list(exclude_channels)

    # ─────────────────────────────────────────────────────────────
    # CTE: 本期每个用户购买的品类集合
    # ─────────────────────────────────────────────────────────────
    current_categories_sql = f"""
        SELECT
            o.user_id,
            COALESCE(o.{category_field}, '未知') as category
        FROM orders o
        WHERE o.pay_time >= ? AND o.pay_time <= ?
          AND {valid_sql}
          {exclude_filter}
        GROUP BY o.user_id, COALESCE(o.{category_field}, '未知')
    """

    # ─────────────────────────────────────────────────────────────
    # CTE: 上期每个用户购买的品类集合
    # ─────────────────────────────────────────────────────────────
    prev_categories_sql = f"""
        SELECT
            o.user_id,
            COALESCE(o.{category_field}, '未知') as category
        FROM orders o
        WHERE o.pay_time >= ? AND o.pay_time <= ?
          AND {valid_sql}
          {exclude_filter}
        GROUP BY o.user_id, COALESCE(o.{category_field}, '未知')
    """

    # ─────────────────────────────────────────────────────────────
    # 主查询：按品类计算流失
    # ─────────────────────────────────────────────────────────────
    params = []
    params.extend([current_start, current_end])  # current_categories
    params.extend(exclude_params)                # exclude
    params.extend([prev_start, prev_end])        # prev_categories
    params.extend(exclude_params)                # exclude

    query = f"""
        WITH current_categories AS (
            {current_categories_sql}
        ),
        prev_categories AS (
            {prev_categories_sql}
        ),
        -- 上期每个品类的用户集合
        prev_category_users AS (
            SELECT user_id, category as prev_category
            FROM prev_categories
        ),
        -- 本期每个品类的用户集合
        curr_category_users AS (
            SELECT user_id, category as curr_category
            FROM current_categories
        ),
        -- 上期各品类总用户数
        category_base AS (
            SELECT prev_category, COUNT(DISTINCT user_id) as total_users
            FROM prev_category_users
            GROUP BY prev_category
        ),
        -- 品类间流失：上期买A，本期买B（B≠A，且本期有订单）
        inter_churn_calc AS (
            SELECT
                p.prev_category,
                COUNT(DISTINCT p.user_id) as inter_churn_count,
                LIST(DISTINCT c.curr_category) as churn_destinations
            FROM prev_category_users p
            INNER JOIN curr_category_users c ON p.user_id = c.user_id
            WHERE p.prev_category != c.curr_category
            GROUP BY p.prev_category
        ),
        -- 沉默流失：上期买A，本期无任何订单
        silent_churn_calc AS (
            SELECT
                p.prev_category,
                COUNT(DISTINCT p.user_id) as silent_churn_count
            FROM prev_category_users p
            WHERE p.user_id NOT IN (SELECT user_id FROM curr_category_users)
            GROUP BY p.prev_category
        ),
        -- 留存用户：上期买A，本期继续买A
        retained_calc AS (
            SELECT
                p.prev_category,
                COUNT(DISTINCT p.user_id) as retained_count
            FROM prev_category_users p
            INNER JOIN curr_category_users c ON p.user_id = c.user_id
            WHERE p.prev_category = c.curr_category
            GROUP BY p.prev_category
        )
        SELECT
            b.prev_category as category_name,
            b.total_users,
            COALESCE(ic.inter_churn_count, 0) as inter_churn,
            COALESCE(sc.silent_churn_count, 0) as silent_churn,
            COALESCE(r.retained_count, 0) as retained_users,
            -- 流失去向（品类间流失用户本期购买的品类分布）
            CASE
                WHEN ic.churn_destinations IS NOT NULL
                THEN ic.churn_destinations
                ELSE []
            END as churn_destinations
        FROM category_base b
        LEFT JOIN inter_churn_calc ic ON b.prev_category = ic.prev_category
        LEFT JOIN silent_churn_calc sc ON b.prev_category = sc.prev_category
        LEFT JOIN retained_calc r ON b.prev_category = r.prev_category
        ORDER BY b.total_users DESC
    """

    result_df = conn.execute(query, params).fetchdf()
    return result_df


def precompute_category_churn(
    start_date: str,
    end_date: str,
    level: str = "class",
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    品类流失预警预计算核心逻辑。

    Args:
        start_date: 分析起始日期 (YYYY-MM-DD)
        end_date: 分析结束日期 (YYYY-MM-DD)
        level: 品类维度
        exclude_channels: 排除渠道列表

    Returns:
        {
            "success": bool,
            "rows_written": int,
            "month": str,
            "generated_at": str
        }
    """
    conn = get_connection()

    # 确定周期长度（天数）
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    period_days = (end_dt - start_dt).days + 1

    # 确定月份（取 end_date 所在月作为 month 标签）
    month_label = end_dt.strftime("%Y-%m")

    # 确保表存在
    _ensure_table(conn)

    # 清空该月份数据（幂等）
    conn.execute(f"DELETE FROM {TABLE_NAME} WHERE month = ?", [month_label])

    # 计算流失
    churn_df = precompute_category_churn_month(
        conn=conn,
        current_start=start_date,
        current_end=end_date,
        period_days=period_days,
        level=level,
        exclude_channels=exclude_channels,
    )

    # 写入数据库
    rows_written = 0
    now = datetime.now()

    for _, row in churn_df.iterrows():
        total = int(row['total_users'])
        inter = int(row['inter_churn'])
        silent = int(row['silent_churn'])
        retained = int(row['retained_users'])
        churned = inter + silent
        retention_rate = round(retained / total, 4) if total > 0 else 0.0

        # 流失去向转为 JSON
        destinations = row.get('churn_destinations', [])
        if isinstance(destinations, list):
            churn_destinations = destinations
        else:
            churn_destinations = []

        # 统计流向
        dest_counts = {}
        for dest in churn_destinations:
            dest_counts[dest] = dest_counts.get(dest, 0) + 1

        # 按人数排序取TOP3
        top3 = dict(sorted(dest_counts.items(), key=lambda x: -x[1])[:3])

        conn.execute(f"""
            INSERT INTO {TABLE_NAME}
            (category_name, month, total_users, churned_users, inter_churn, silent_churn,
             retained_users, retention_rate, churn去向_json, generated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            row['category_name'],
            month_label,
            total,
            churned,
            inter,
            silent,
            retained,
            retention_rate,
            json.dumps(top3, ensure_ascii=False),
            now
        ])
        rows_written += 1

    conn.close()

    return {
        "success": True,
        "rows_written": rows_written,
        "month": month_label,
        "period_days": period_days,
        "generated_at": now.isoformat()
    }


def run_precomputation(
    start_date: str,
    end_date: str,
    level: str = "class",
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    运行预计算并保存到 DuckDB。
    """
    print(f"\n品类流失预警预计算: {start_date} ~ {end_date} (level={level})")

    result = precompute_category_churn(
        start_date=start_date,
        end_date=end_date,
        level=level,
        exclude_channels=exclude_channels,
    )

    if result['success']:
        print(f"  [已写入] {result['month']} 月, {result['rows_written']} 个品类")
    else:
        print(f"  [失败] {result}")

    return result


def run_full_precomputation():
    """
    全量预计算：覆盖所有历史月份。
    用于 ETL --update 后自动触发。
    """
    print("\n" + "=" * 60)
    print("品类流失预警预计算 - 全量模式")
    print("=" * 60)

    conn = get_connection()
    try:
        _ensure_table(conn)
        # 获取数据库日期范围
        date_range = conn.execute("""
            SELECT MIN(pay_time) as min_date, MAX(pay_time) as max_date
            FROM orders
            WHERE pay_time IS NOT NULL
        """).fetchone()

        if date_range is None or date_range[0] is None:
            print("  [警告] 数据库为空，跳过预计算")
            return

        min_date = _normalize_date(date_range[0])
        max_date = _normalize_date(date_range[1])
    finally:
        conn.close()

    print(f"  数据范围: {min_date} ~ {max_date}")

    # 生成所有月份组合
    import calendar
    months = []
    cursor = datetime.strptime(min_date[:7] + "-01", "%Y-%m-%d")
    max_dt = datetime.strptime(max_date[:7] + "-01", "%Y-%m-%d")

    while cursor <= max_dt:
        year, month = cursor.year, cursor.month
        last_day = calendar.monthrange(year, month)[1]
        months.append(f"{year}-{month:02d}")
        # 下一月
        if month == 12:
            cursor = datetime(year + 1, 1, 1)
        else:
            cursor = datetime(year, month + 1, 1)

    print(f"  待计算月份: {len(months)} 个")

    # 使用30天固定窗口（MoM可比）
    _period_days = 30

    completed = 0
    for month_str in months:
        year, month = int(month_str[:4]), int(month_str[5:7])
        last_day = calendar.monthrange(year, month)[1]
        end_date = f"{year}-{month:02d}-{last_day:02d}"
        start_date_dt = datetime(year, month, 1)
        start_date = start_date_dt.strftime("%Y-%m-%d")

        # 检查是否已有该月数据
        conn2 = get_connection()
        existing = conn2.execute(
            f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE month = ?",
            [month_str]
        ).fetchone()[0]
        conn2.close()

        if existing > 0:
            print(f"  [跳过] {month_str} (已有 {existing} 条)")
            continue

        try:
            result = precompute_category_churn(
                start_date=start_date,
                end_date=end_date,
                level="class",
                exclude_channels=None,
            )
            if result['success']:
                completed += 1
                if completed % 10 == 0:
                    print(f"  进度: {completed}/{len(months)}")
        except Exception as e:
            print(f"  [错误] {month_str}: {e}")

    print(f"\n  全量预计算完成: {completed} 个月")


def get_churn_data(
    start_date: str,
    end_date: str,
    level: str = "class",
) -> List[Dict[str, Any]]:
    """
    从缓存表读取品类流失数据（供 Service 调用）。

    Returns:
        List of churn records for the specified period
    """
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    month_label = end_dt.strftime("%Y-%m")

    conn = get_connection()
    try:
        df = conn.execute(f"""
            SELECT
                category_name,
                month,
                total_users,
                churned_users,
                inter_churn,
                silent_churn,
                retained_users,
                retention_rate,
                churn去向_json
            FROM {TABLE_NAME}
            WHERE month = ?
            ORDER BY total_users DESC
        """, [month_label]).fetchdf()
    finally:
        conn.close()

    result = []
    for _, row in df.iterrows():
        result.append({
            "category_name": row['category_name'],
            "month": row['month'],
            "total_users": int(row['total_users']),
            "churned_users": int(row['churned_users']),
            "inter_churn": int(row['inter_churn']),
            "silent_churn": int(row['silent_churn']),
            "retained_users": int(row['retained_users']),
            "retention_rate": float(row['retention_rate']),
            "churn_destinations": json.loads(row['churn去向_json']) if row['churn去向_json'] else {}
        })
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='品类流失预警预计算')
    parser.add_argument('--start', type=str, help='起始日期 YYYY-MM-DD')
    parser.add_argument('--end', type=str, help='结束日期 YYYY-MM-DD')
    parser.add_argument('--level', type=str, default='class', help='品类级别 (默认class)')
    parser.add_argument('--full', action='store_true', help='全量预计算所有月份')
    args = parser.parse_args()

    if args.full:
        run_full_precomputation()
    elif args.start and args.end:
        result = run_precomputation(
            start_date=args.start,
            end_date=args.end,
            level=args.level,
        )
        print(f"\n  写入行数: {result['rows_written']}")
    else:
        parser.print_help()
