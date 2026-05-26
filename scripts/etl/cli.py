"""ETL CLI 入口
命令行参数解析、子命令分发。
"""
import gc
import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.etl.config import (
    DUCKDB_PATH, COLUMN_MAPPING, SPU_COLUMNS, TAOKE_COL,
    _ETL_SOURCE_STATS,
)

from scripts.etl.sources import (
    load_spu_mapping, load_channel_rules,
    load_taoke_order_ids, load_live_order_ids, load_taoke_product_rules,
)
from scripts.etl.ingest import load_data_files
from scripts.etl.transform import match_channel, clean_data
from scripts.etl.load import upsert_to_duckdb
from scripts.etl.pipeline import (
    run_full_etl, update_taoke_channel,
    refresh_visitor_data, refresh_campaign_schedule,
)

import pandas as pd
import duckdb

def backup_and_update_orders(
    df: pd.DataFrame,
    update_columns: dict,
    backup_label: str,
    filter_condition: str = None,
    filter_params: list = None
):
    """
    通用备份+批量UPDATE函数。

    Args:
        df: 包含 order_id 和更新字段的 DataFrame
        update_columns: {db_column: df_column} 映射
        backup_label: 备份文件名前缀
        filter_condition: 备份时可选的 WHERE 条件（如 "product_id IN ({placeholders})"）
        filter_params: 备份条件参数列表
    """
    from datetime import datetime

    conn = duckdb.connect(str(DUCKDB_PATH))
    try:
        # 备份（parquet）
        backup_dir = PROCESSED_DATA_DIR / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = backup_dir / f"orders_{backup_label}_backup_{timestamp}.parquet"
        backup_path_str = str(backup_path).replace("'", "''")

        if filter_condition and filter_params:
            placeholders = ', '.join(['?' for _ in filter_params])
            conn.execute(f"""
                COPY (SELECT * FROM orders WHERE {filter_condition})
                TO '{backup_path_str}' (FORMAT PARQUET)
            """, filter_params)
        else:
            conn.execute(f"""
                COPY (SELECT * FROM orders)
                TO '{backup_path_str}' (FORMAT PARQUET)
            """)
        print(f"  备份: {backup_path}")

        # 批量 UPDATE
        set_clause = ', '.join([f"{db_col} = t.{df_col}" for db_col, df_col in update_columns.items()])
        df_cols = ', '.join(['order_id'] + list(update_columns.values()))

        update_sql = f"""
            UPDATE orders
            SET {set_clause}
            FROM (
                SELECT {df_cols} FROM df
            ) AS t
            WHERE orders.order_id = t.order_id
        """
        update_count = conn.execute(update_sql).rowcount
        print(f"  更新完成: {update_count:,} 条")
    finally:
        conn.close()


def rescan_channel(since: str = None, dry_run: bool = True):
    """
    渠道重匹配：对已有 orders 重新应用渠道规则，不重新解析源文件。

    复用 load_channel_rules() + match_channel() 逻辑，保证口径与全量一致。

    用法:
      python run_etl.py --rescan-channel --dry-run
      python run_etl.py --rescan-channel --apply
      python run_etl.py --rescan-channel --since 2024-01-01 --apply
    """
    print(f"\n{'='*60}")
    print("渠道重匹配")
    print(f"{'='*60}")
    print(f"  模式: {'预览 (dry-run)' if dry_run else '执行写入 (apply)'}")
    if since:
        print(f"  日期过滤: pay_time >= {since}")

    # Step 1: 加载渠道规则（复用现有函数）
    keyword_rules, id_rules = load_channel_rules()
    taoke_order_ids = load_taoke_order_ids()
    live_order_ids = load_live_order_ids()
    taoke_product_rules = load_taoke_product_rules()

    # Step 2: 从 DuckDB 读取订单
    print(f"\n读取 DuckDB 订单...")
    conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        if since:
            orders_df = conn.execute("""
                SELECT order_id, product_title, product_id, actual_amount,
                       pay_time, is_member, spu_type, channel AS old_channel
                FROM orders
                WHERE pay_time >= ?
            """, [since]).fetchdf()
        else:
            orders_df = conn.execute("""
                SELECT order_id, product_title, product_id, actual_amount,
                       pay_time, is_member, spu_type, channel AS old_channel
                FROM orders
            """).fetchdf()
    finally:
        conn.close()

    print(f"  找到订单: {len(orders_df):,} 条")
    if orders_df.empty:
        print("  无订单，退出")
        return

    # Step 3: 重新匹配渠道
    print(f"\n执行渠道匹配...")
    orders_df['channel'] = '其他'  # 重置为漏斗起点

    matched_df = match_channel(
        orders_df, keyword_rules, id_rules,
        taoke_order_ids=taoke_order_ids,
        live_order_ids=live_order_ids,
        taoke_product_rules=taoke_product_rules
    )

    # Step 4: 对比新旧 channel
    matched_df['new_channel'] = matched_df['channel']
    matched_df['channel_changed'] = matched_df['old_channel'].fillna('') != matched_df['new_channel'].fillna('')

    changed_df = matched_df[matched_df['channel_changed']].copy()
    unchanged_count = len(matched_df) - len(changed_df)

    print(f"\n{'='*60}")
    print("变更报告")
    print(f"{'='*60}")
    print(f"  总订单数: {len(matched_df):,}")
    print(f"  channel 无变化: {unchanged_count:,}")
    print(f"  channel 有变化: {len(changed_df):,}")

    if not changed_df.empty:
        print(f"\n  变更明细:")
        change_summary = changed_df.groupby(['old_channel', 'new_channel']).size().reset_index(name='count')
        for _, row in change_summary.iterrows():
            old = row['old_channel'] or '(空)'
            new = row['new_channel'] or '(空)'
            print(f"    {old} → {new}: {row['count']:,} 条")

    # Step 5: 写入或预览
    if dry_run:
        print(f"\n{'='*60}")
        print("DRY-RUN 完成（未写入）")
        print(f"{'='*60}")
        print("  如需写入，请添加 --apply 参数")
    else:
        if changed_df.empty:
            print(f"\n  无需更新，退出")
            return

        print(f"\n写入 DuckDB...")
        backup_and_update_orders(
            df=changed_df,
            update_columns={'channel': 'new_channel'},
            backup_label='rescan_channel'
        )

        print(f"\n{'='*60}")
        print("渠道重匹配完成！")
        print(f"{'='*60}")


def rescan_spu_mapping(product_ids: list, dry_run: bool = True):
    """
    SPU 重匹配：重新计算指定 product_id 的 spu_type 和 channel。

    复用 load_spu_mapping() + match_channel() 的逻辑，保证口径一致。
    仅对 spu_type 发生变化的订单重新匹配渠道。

    用法:
      python run_etl.py --rescan-spu --product-ids 1008376905465 --dry-run
      python run_etl.py --rescan-spu --product-ids 1008376905465 --apply
    """
    from datetime import datetime

    print(f"\n{'='*60}")
    print("SPU 重匹配")
    print(f"{'='*60}")
    print(f"  目标 product_id: {product_ids}")
    print(f"  模式: {'预览 (dry-run)' if dry_run else '执行写入 (apply)'}")

    # Step 1: 加载 SPU 匹配表（复用现有函数）
    spu_df = load_spu_mapping()
    if spu_df is None:
        print("  错误: SPU 匹配表加载失败")
        return

    # Step 2: 加载渠道规则（复用现有函数）
    keyword_rules, id_rules = load_channel_rules()
    taoke_order_ids = load_taoke_order_ids()
    live_order_ids = load_live_order_ids()
    taoke_product_rules = load_taoke_product_rules()

    # Step 3: 从 DuckDB 读取指定 product_id 的订单
    print(f"\n读取 DuckDB 中目标订单...")
    conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        # 使用参数化查询，防止SQL注入（CLAUDE.md规则：DuckDB用?参数化，禁止字符串拼接）
        placeholders = ', '.join(['?' for _ in product_ids])
        orders_df = conn.execute(f"""
            SELECT order_id, product_id, pay_time, product_title,
                   actual_amount, spu_type AS old_spu_type, channel AS old_channel
            FROM orders
            WHERE product_id IN ({placeholders})
        """, product_ids).fetchdf()
    finally:
        conn.close()

    print(f"  找到订单: {len(orders_df):,} 条")
    if orders_df.empty:
        print("  无订单，退出")
        return

    # Step 4: SPU 时间窗口匹配（复用 clean_data 中的逻辑）
    print(f"\n执行 SPU 时间窗口匹配...")
    spu_cols = ['product_id', 'spu_category', 'spu_type', 'spu_tier',
                'spu_product_class', 'spu_product_subclass', 'spu_cosmetic',
                'spu_spec', 'spu_start_date', 'spu_end_date']
    spu_cols = [c for c in spu_cols if c in spu_df.columns]
    spu_valid = spu_df[spu_cols].dropna(subset=['product_id', 'spu_start_date']).copy()

    # 统一 product_id 类型
    orders_df['product_id'] = orders_df['product_id'].astype(str)
    spu_valid['product_id'] = spu_valid['product_id'].apply(
        lambda x: str(int(x)) if pd.notna(x) else x
    )

    # 解析 pay_time
    orders_df['pay_time'] = pd.to_datetime(orders_df['pay_time'], errors='coerce')
    orders_df['order_idx'] = orders_df.index

    # merge
    spu_attr_cols = [c for c in spu_cols if c not in ['product_id', 'spu_start_date', 'spu_end_date']]
    merged = orders_df.merge(
        spu_valid[['product_id', 'spu_start_date', 'spu_end_date'] + spu_attr_cols],
        on='product_id', how='left'
    )

    # 时间窗口过滤
    valid_mask = (
        (merged['spu_start_date'].isna() | (merged['pay_time'].dt.normalize() >= merged['spu_start_date'].dt.normalize())) &
        (merged['spu_end_date'].isna() | (merged['spu_end_date'].dt.normalize() >= merged['pay_time'].dt.normalize()))
    )
    merged_valid = merged[valid_mask].copy()

    # 评分排序取最优
    merged_valid['_spu_score'] = (
        merged_valid['spu_product_class'].notna().astype(int) * 100 +
        merged_valid['spu_type'].notna().astype(int) * 10 +
        merged_valid['spu_start_date'].notna().astype(int)
    )
    merged_valid = merged_valid.sort_values(
        ['_spu_score', 'spu_start_date'], ascending=[False, False]
    ).drop_duplicates(subset='order_idx', keep='first')

    # 写回 orders_df
    if len(merged_valid) > 0:
        result = merged_valid.set_index('order_idx')[spu_attr_cols]
        for col in spu_attr_cols:
            if col in result.columns:
                orders_df[col] = result[col].reindex(orders_df.index)

    # Step 5: 对比新旧 spu_type
    orders_df['new_spu_type'] = orders_df.get('spu_type', pd.Series(dtype=str)).reindex(orders_df.index)
    orders_df['spu_changed'] = orders_df['old_spu_type'].fillna('') != orders_df['new_spu_type'].fillna('')

    changed_df = orders_df[orders_df['spu_changed']].copy()
    unchanged_count = len(orders_df) - len(changed_df)

    print(f"\n{'='*60}")
    print("变更报告")
    print(f"{'='*60}")
    print(f"  总订单数: {len(orders_df):,}")
    print(f"  spu_type 无变化: {unchanged_count:,}")
    print(f"  spu_type 有变化: {len(changed_df):,}")

    if not changed_df.empty:
        print(f"\n  变更明细:")
        change_summary = changed_df.groupby(['old_spu_type', 'new_spu_type']).size().reset_index(name='count')
        for _, row in change_summary.iterrows():
            old = row['old_spu_type'] or '(空)'
            new = row['new_spu_type'] or '(空)'
            print(f"    {old} → {new}: {row['count']:,} 条")

    # Step 6: 对变更订单重匹配渠道（复用 match_channel 逻辑）
    if not changed_df.empty:
        print(f"\n对变更订单重新匹配渠道...")
        # 构造 match_channel 需要的 DataFrame
        channel_df = changed_df.copy()
        channel_df['spu_type'] = channel_df['new_spu_type']
        channel_df['channel'] = '其他'

        channel_df = match_channel(
            channel_df, keyword_rules, id_rules,
            taoke_order_ids=taoke_order_ids,
            live_order_ids=live_order_ids,
            taoke_product_rules=taoke_product_rules
        )

        # 渠道变化统计
        channel_changed = channel_df[channel_df['old_channel'] != channel_df['channel']]
        print(f"\n  渠道变化: {len(channel_changed):,} 条")
        if not channel_changed.empty:
            channel_summary = channel_changed.groupby(['old_channel', 'channel']).size().reset_index(name='count')
            for _, row in channel_summary.iterrows():
                print(f"    {row['old_channel']} → {row['channel']}: {row['count']:,} 条")
    else:
        channel_df = changed_df
        channel_changed = pd.DataFrame()

    # Step 7: 写入或预览
    if dry_run:
        print(f"\n{'='*60}")
        print("DRY-RUN 完成（未写入）")
        print(f"{'='*60}")
        print("  如需写入，请添加 --apply 参数")
    else:
        if changed_df.empty:
            print(f"\n  无需更新，退出")
            return

        print(f"\n写入 DuckDB...")
        backup_and_update_orders(
            df=channel_df,
            update_columns={'spu_type': 'new_spu_type', 'channel': 'channel'},
            backup_label='rescan',
            filter_condition=f"product_id IN ({', '.join(['?' for _ in product_ids])})",
            filter_params=product_ids
        )

        print(f"\n{'='*60}")
        print("SPU 重匹配完成！")
        print(f"{'='*60}")

def main():
    """CLI 入口函数"""
    parser = argparse.ArgumentParser(description='芙清 CRM ETL')
    parser.add_argument('--full', action='store_true', help='强制全量重建')
    parser.add_argument('--inc', action='store_true', help='强制增量')
    parser.add_argument('--update', action='store_true',
                        help='一键增量更新：ETL增量 + 淘客渠道同步 + 状态覆盖表刷新')
    parser.add_argument('--update-taoke', action='store_true',
                        help='仅运行淘客渠道增量更新')
    parser.add_argument('--refresh-status', action='store_true',
                        help='仅刷新订单状态覆盖表（从CSV读取近30天最新状态）')
    parser.add_argument('--window-days', type=int, default=30,
                        help='滑动窗口天数：刷新最近N天的订单状态（默认30，覆盖退款周期）')
    parser.add_argument('--rescan-spu', action='store_true',
                        help='SPU重匹配：重新计算指定product_id的spu_type和channel')
    parser.add_argument('--rescan-channel', action='store_true',
                        help='渠道重匹配：对已有orders重新应用渠道规则（不重新解析源文件）')
    parser.add_argument('--product-ids', nargs='+', default=[],
                        help='指定product_id列表（与--rescan-spu配合使用）')
    parser.add_argument('--since', type=str, default=None,
                        help='渠道重匹配时限制日期范围（格式: YYYY-MM-DD，与--rescan-channel配合）')
    parser.add_argument('--dry-run', action='store_true',
                        help='仅预览变更，不写入DuckDB（与--rescan-spu/--rescan-channel配合）')
    parser.add_argument('--apply', action='store_true',
                        help='执行变更并写入DuckDB（与--rescan-spu/--rescan-channel配合）')
    args = parser.parse_args()

    # 单独刷新状态覆盖表
    if args.refresh_status:
        print("\n" + "=" * 60)
        print("刷新订单状态覆盖表（CSV 模式）")
        print("=" * 60)
        from scripts.etl_status_override import refresh_status_override
        from backend.config import DUCKDB_PATH
        refresh_status_override(DUCKDB_PATH, window_days=args.window_days)
        print("\n" + "=" * 60)
        print("状态覆盖表刷新完成！")
        print("=" * 60)
        sys.exit(0)

    # 一键更新：ETL 增量 → 淘客同步 → 状态覆盖表刷新
    if args.update:
        print("\n" + "=" * 60)
        print("一键增量更新（全店+会员+淘客+状态刷新）")
        print("=" * 60)
        # Step 1: ETL 增量（滑动窗口模式，force_continue 确保 Step 5/6 必定执行）
        run_full_etl(mode='inc', window_days=args.window_days, force_continue=True)
        # Step 2: 淘客渠道同步（确保新增淘客订单被正确标记）
        update_taoke_channel()
        # Step 3: 刷新订单状态覆盖表（从 zip/csv 读取最新退款/交易关闭状态）
        print("\n" + "-" * 40)
        print("Step 3: 刷新订单状态覆盖表")
        print("-" * 40)
        from scripts.etl_status_override import refresh_status_override
        from backend.config import DUCKDB_PATH
        refresh_status_override(DUCKDB_PATH, window_days=args.window_days)

        # Step 4: 反向同步 override → orders（看板直接生效，无需改 SQL）
        print("\n" + "-" * 40)
        print("Step 4: 反向同步 override → orders")
        print("-" * 40)
        from scripts.etl_status_override import sync_override_to_orders
        sync_override_to_orders(DUCKDB_PATH, window_days=args.window_days)

        # Step 5: 刷新访客数据（daily_visitors 表，访客数/新增会员数）
        print("\n" + "-" * 40)
        print("Step 5: 刷新访客数据")
        print("-" * 40)
        refresh_visitor_data()

        # Step 6: 预计算 RFM 8象限结果（DuckDB 缓存表，ETL 完成后一次性写入）
        print("\n" + "-" * 40)
        print("Step 6: 预计算 RFM 8象限历史周期缓存")
        print("-" * 40)
        from backend.services.health.rfm_analysis import precompute_rfm_cache
        count = precompute_rfm_cache()
        print(f"  预计算完成: {count} 个组合")

        # Step 7: 创建 user_rfm 表 + 热点日期预加载（品类/地域等服务的依赖）
        print("\n" + "-" * 40)
        print("Step 7: 创建 user_rfm 表 + 热点日期预加载")
        print("-" * 40)
        from backend.database import create_user_rfm_table
        create_user_rfm_table()
        from scripts.preload_rfm import run_auto_preload
        results = run_auto_preload()
        success = [r for r in results if r[4] > 0]
        print(f"  user_rfm 预加载完成: {len(success)} 个组合")

        # Step 7.5: 刷新活动节奏表（campaign_schedule）
        print("\n" + "-" * 40)
        print("Step 7.5: 刷新活动节奏表")
        print("-" * 40)
        refresh_campaign_schedule()

        # Step 8: 数据源扫描摘要（防截断，固定输出在结尾）
        print("\n" + "=" * 60)
        print("ETL 数据源扫描摘要")
        print("=" * 60)
        print(f"{'数据源':<16} {'文件数':>8} {'记录数':>12} {'重新读取':>10} {'缓存命中':>10}")
        print("-" * 60)

        # 淘客
        tk = _ETL_SOURCE_STATS.get('taoke', {})
        print(f"{'淘客数据库':<16} {tk.get('files', 0):>8} {tk.get('total_ids', 0):>12,} {tk.get('reloaded', 0):>10} {tk.get('skipped', 0):>10}")

        # 淘客商品ID表
        tp = _ETL_SOURCE_STATS.get('taoke_product', {})
        print(f"{'淘客商品ID表':<16} {tp.get('files', 0):>8} {tp.get('total_rules', 0):>12,} {'—':>10} {'—':>10}")

        # 直播
        lv = _ETL_SOURCE_STATS.get('live', {})
        print(f"{'直播间数据源':<16} {lv.get('files', 0):>8} {lv.get('total_ids', 0):>12,} {lv.get('reloaded', 0):>10} {lv.get('skipped', 0):>10}")

        # DuckDB 总行数
        try:
            conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)
            try:
                total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
                total_users = conn.execute("SELECT COUNT(DISTINCT user_id) FROM orders").fetchone()[0]
                print(f"{'DuckDB 订单表':<16} {'—':>8} {total_orders:>12,} {'—':>10} {'—':>10}")
                print(f"{'DuckDB 用户数':<16} {'—':>8} {total_users:>12,} {'—':>10} {'—':>10}")
            finally:
                conn.close()
        except Exception:
            pass

        print("=" * 60)
        print("一键更新完成！")
        print("=" * 60)
        sys.exit(0)

    # 渠道重匹配子命令
    if args.rescan_channel:
        if not args.dry_run and not args.apply:
            print("错误: --rescan-channel 需要指定 --dry-run 或 --apply")
            print("用法: python run_etl.py --rescan-channel --dry-run")
            sys.exit(1)
        rescan_channel(
            since=args.since,
            dry_run=args.dry_run
        )
        sys.exit(0)

    # SPU 重匹配子命令
    if args.rescan_spu:
        if not args.product_ids:
            print("错误: --rescan-spu 需要配合 --product-ids 使用")
            print("用法: python run_etl.py --rescan-spu --product-ids 1008376905465 --dry-run")
            sys.exit(1)
        if not args.dry_run and not args.apply:
            print("错误: --rescan-spu 需要指定 --dry-run 或 --apply")
            sys.exit(1)
        print("\n" + "=" * 60)
        print("SPU 重匹配")
        print("=" * 60)
        rescan_spu_mapping(
            product_ids=args.product_ids,
            dry_run=args.dry_run
        )
        sys.exit(0)

    # 纯淘客渠道更新
    if args.update_taoke:
        update_taoke_channel()
        sys.exit(0)

    if args.full:
        mode = 'full'
    elif args.inc:
        mode = 'inc'
    else:
        mode = 'auto'


if __name__ == '__main__':
    main()
