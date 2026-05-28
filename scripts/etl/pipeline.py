"""ETL 主流程编排
run_full_etl、增量更新、RFM 预计算、访客数据刷新。
"""
import gc
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.etl.config import (
    DUCKDB_PATH, SHOP_DATA_SOURCE, MEMBER_DATA_SOURCE,
    PROCESSED_DATA_DIR, PARQUET_DATA_DIR, COLUMN_MAPPING,
    _get_processed_files_path, _load_processed_files, _save_processed_files,
    _ETL_SOURCE_STATS,
)

from scripts.etl.sources import (
    load_spu_mapping, load_channel_rules,
    load_taoke_order_ids, load_live_order_ids, load_taoke_product_rules,
)
from scripts.etl.ingest import load_data_files
from scripts.etl.transform import match_channel, clean_data
from scripts.etl.load import (
    init_database, write_to_duckdb, upsert_to_duckdb,
    filter_rolling_window, get_db_max_pay_time,
    _create_orders_table, _create_indexes,
    _create_orders_table_custom, _create_indexes_custom,
    _create_metrics_tables,
)

import pandas as pd
import duckdb

def run_full_etl(mode='auto', window_days=30, force_continue=False):
    """
    完整 ETL 流程（滑动窗口增量模式）

    mode:
      'auto'    - 自动检测：数据库空则全量，有数据则增量
      'full'    - 强制全量重建
      'inc'     - 强制增量（数据库必须已有数据）
    window_days:
      滑动窗口天数，刷新最近 N 天的订单状态（默认30天，覆盖退款周期）
    """
    print("=" * 60)
    print(f"芙清 CRM - 数据清洗 ETL v6 (滑动窗口: {window_days}天)")
    print("=" * 60)

    # Step 0: 确定模式（get_db_max_pay_time 有 lru_cache，重复调用无开销）
    cached_max_time = get_db_max_pay_time()
    db_has_data = cached_max_time is not None

    if mode == 'full':
        run_mode = 'full'
        print("[模式] 强制全量重建")
    elif mode == 'inc':
        if not db_has_data:
            print("[错误] 强制增量模式，但数据库为空，请先执行全量导入")
            return
        run_mode = 'incremental'
        print("[模式] 强制增量")
    else:
        # auto 模式
        if db_has_data:
            run_mode = 'incremental'
            print(f"[模式] 自动增量 (数据库已有数据，最大时间: {cached_max_time})")
        else:
            run_mode = 'full'
            print("[模式] 自动全量 (数据库为空)")

    # Step 0.5: 冷启动修复 — 数据库有数据但 processed_files 为空时，自动标记历史文件
    # 这样第一次增量就不会把 113 个历史 xlsx 全读一遍
    if run_mode == 'incremental':
        for data_type, data_source in [('shop', SHOP_DATA_SOURCE), ('member', MEMBER_DATA_SOURCE)]:
            processed = _load_processed_files(data_type)
            if not processed and data_source.exists():
                total_files = len(list(data_source.rglob("*.xlsx")))
                if total_files > 0:
                    print(f"  [冷启动] {data_type}: 数据库有数据但无处理记录，自动标记 {total_files} 个历史文件")
                    _mark_all_files_processed()
                    break  # _mark_all_files_processed 一次性标记 shop+member

    # Step 1: 加载 SPU 匹配表、渠道规则、淘客数据和直播数据源
    spu_df = load_spu_mapping()
    keyword_rules, id_rules = load_channel_rules()
    taoke_order_ids = load_taoke_order_ids()
    live_order_ids = load_live_order_ids()
    taoke_product_rules = load_taoke_product_rules()  # 商品ID+时间范围补充淘客

    # 用会员 order_id 集合做 LEFT JOIN 语义标记
    # 增量模式：从 DuckDB 读取历史会员 order_id（避免只拿到新增会员数据）
    if run_mode == 'incremental':
        shop_df = load_data_files(SHOP_DATA_SOURCE, data_type='shop', run_mode=run_mode)
        member_df = load_data_files(MEMBER_DATA_SOURCE, data_type='member', run_mode=run_mode)
        if shop_df.empty:
            print("错误: 没有加载到任何店铺数据!")
            return
        if member_df.empty:
            print("  增量模式：从 DuckDB 加载历史 member_order_ids...")
            conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)
            try:
                member_order_ids = set(conn.execute(
                    "SELECT DISTINCT order_id FROM orders WHERE is_member = TRUE"
                ).fetchdf()['order_id'].dropna())
                print(f"  从 DuckDB 加载 {len(member_order_ids):,} 个历史会员订单号")
            except Exception as e:
                print(f"  [警告] 从 DuckDB 加载 member_order_ids 失败: {e}")
                member_order_ids = set()
            finally:
                conn.close()
        else:
            member_order_ids = set(member_df['order_id'].dropna())
    else:
        # 全量模式：不预加载所有数据，避免内存耗尽
        shop_df = pd.DataFrame()
        member_df = pd.DataFrame()
        member_order_ids = set()

    if run_mode == 'full':
        # ===== 全量模式：逐文件处理，不累积DataFrame，彻底避免内存峰值 =====
        conn = duckdb.connect(str(DUCKDB_PATH))
        # FIX(2026-04-27): DuckDB大库执行TRUNCATE可能段错误(sigsegv)，改用DROP+重建
        conn.execute("DROP TABLE IF EXISTS orders")
        _create_orders_table(conn)
        _create_indexes(conn)
        print("  [全量模式] 已重建 orders 表")
        try:
            table_columns = [
                'order_id', 'sub_order_id', 'user_id', 'user_nickname',
                'order_time', 'pay_time', 'ship_time', 'order_type', 'order_status',
                'product_id', 'merchant_code', 'product_title', 'sku_id', 'sku_code',
                'sku_name', 'quantity', 'amount', 'refund_status', 'refund_amount',
                'actual_amount', 'province', 'city', 'influencer_name', 'influencer_id',
                'live_room_id', 'video_id', 'traffic_source', 'traffic_type',
                'seller_note', 'year', 'month', 'is_member', 'spu_category',
                'spu_type', 'spu_tier', 'spu_product_class', 'spu_product_subclass',
                'spu_cosmetic', 'spu_spec', 'channel',
                'is_goujinjin', 'is_refund'
            ]

            # --- Step A: 逐文件处理原始库 ---
            shop_files = sorted(SHOP_DATA_SOURCE.rglob("*.xlsx"))
            print(f"\n--- 处理原始库 ({len(shop_files)} 个文件) ---")
            total_inserted = 0
            for i, f in enumerate(shop_files):
                print(f"  [{i+1}/{len(shop_files)}] {f.name}")
                try:
                    df = pd.read_excel(f, engine='openpyxl', header=0)
                    df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]
                    df = rename_columns(df)
                    if 'order_time' in df.columns:
                        df['order_time'] = pd.to_datetime(df['order_time'], errors='coerce')
                        df['year'] = df['order_time'].dt.year
                        df['month'] = df['order_time'].dt.month
                    if df.empty or 'order_id' not in df.columns:
                        print(f"    跳过")
                        continue
                    df['is_member'] = False
                    df = clean_data(df, spu_df, keyword_rules, id_rules,
                                    taoke_order_ids=taoke_order_ids, live_order_ids=live_order_ids,
                                    taoke_product_rules=taoke_product_rules)
                    existing_cols = [c for c in table_columns if c in df.columns]
                    count = _copy_df_to_duckdb(df, conn, existing_cols)
                    total_inserted += count
                    del df
                    gc.collect()
                except Exception as e:
                    print(f"    错误: {e}")
                    continue
            print(f"  原始库写入: {total_inserted:,} 行")

            # --- Step B: 处理会员库（逐文件，避免内存峰值） ---
            # 注意：会员文件和店铺文件包含相同order_id，Step A已将所有订单以is_member=FALSE写入
            # Step B的正确逻辑：(1) INSERT全新订单 (2) UPDATE现有订单的is_member=TRUE
            member_files = sorted(MEMBER_DATA_SOURCE.rglob("*.xlsx"))
            if member_files:
                print("\n--- 处理会员库 ---")
                try:
                    existing_ids = set(conn.execute(
                        "SELECT DISTINCT order_id FROM orders WHERE order_id IS NOT NULL"
                    ).fetchdf()['order_id'].dropna())
                except Exception:
                    existing_ids = set()

                # 第一轮：INSERT全新订单（会员文件中有但店铺数据中没有的）
                all_member_order_ids = set()
                for i, f in enumerate(member_files):
                    print(f"  [{i+1}/{len(member_files)}] {f.name}")
                    try:
                        df = pd.read_excel(f, engine='openpyxl', header=0)
                        df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]
                        df = rename_columns(df)
                        if df.empty or 'order_id' not in df.columns:
                            del df; gc.collect()
                            continue
                        # 收集所有会员order_id用于后续UPDATE
                        file_ids = df['order_id'].dropna().astype(str).unique()
                        all_member_order_ids.update(file_ids)
                        # INSERT新订单（不在existing_ids中的）
                        member_only = df[~df['order_id'].astype(str).isin(existing_ids)]
                        if not member_only.empty:
                            member_only = member_only.copy()
                            member_only['is_member'] = True
                            member_only = clean_data(member_only, spu_df, keyword_rules, id_rules,
                                                    taoke_order_ids=taoke_order_ids, live_order_ids=live_order_ids,
                                                    taoke_product_rules=taoke_product_rules)
                            existing_cols = [c for c in table_columns if c in member_only.columns]
                            count = _copy_df_to_duckdb(member_only, conn, existing_cols)
                            total_inserted += count
                            existing_ids.update(member_only['order_id'].dropna().astype(str))
                            print(f"    会员写入: {count:,} 行")
                        del df; gc.collect()
                    except Exception as e:
                        print(f"    错误: {e}")
                        continue

                # 第二轮：UPDATE现有订单的is_member=TRUE
                # 会员文件order_id和店铺文件order_id高度重叠，需要UPDATE而非INSERT
                print(f"  更新会员标记: {len(all_member_order_ids):,} 个order_id")
                batch_size = 100000
                id_list = sorted(all_member_order_ids)
                updated_total = 0
                for i in range(0, len(id_list), batch_size):
                    batch = id_list[i:i+batch_size]
                    # P1 fix: 使用 DuckDB 参数化查询替代字符串拼接，防止 SQL 注入
                    params = [str(oid) for oid in batch]
                    placeholders = ','.join(['?' for _ in params])
                    sql = f"UPDATE orders SET is_member = TRUE WHERE order_id IN ({placeholders}) AND is_member = FALSE"
                    conn.execute(sql, params)
                    updated_total += len(batch)
                print(f"  会员标记更新: {updated_total:,} 行")
            else:
                print("  会员库无文件")

            total = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            print(f"\n写入 DuckDB 总计: {total:,} 行")
        finally:
            conn.close()

        new_df, refresh_df = pd.DataFrame(), pd.DataFrame()

        # Step 5: 预计算每日指标（全量模式）
        _rebuild_metrics()

        # Step 6: 创建 user_rfm 表 + 热点日期预加载
        print("\n" + "-" * 40)
        print("Step 6: 创建 user_rfm 表 + 热点日期预加载")
        print("-" * 40)
        from backend.database import create_user_rfm_table
        create_user_rfm_table()
        from scripts.preload_rfm import run_auto_preload
        results = run_auto_preload()
        success = [r for r in results if r[4] > 0]
        print(f"  user_rfm 预加载完成: {len(success)} 个组合")
    else:
        # ===== 增量模式：保持原逻辑 =====
        shop_df['is_member'] = shop_df['order_id'].isin(member_order_ids)

        # 合并：店铺全部保留，再拼接会员新增的（不在店铺里的）订单
        if not member_df.empty:
            member_only = member_df[~member_df['order_id'].isin(member_order_ids)]
            if not member_only.empty:
                member_only = member_only.copy()
                member_only['is_member'] = True
                combined_df = pd.concat([shop_df, member_only], ignore_index=True)
            else:
                combined_df = shop_df
        else:
            combined_df = shop_df

        print(f"\n合并后总数据: {len(combined_df)} 行")

        # Step 2.5: 滑动窗口过滤（全新订单 + 窗口内刷新）
        new_df, refresh_df = combined_df.copy(), pd.DataFrame()
        if run_mode == 'incremental':
            max_time = get_db_max_pay_time()
            if max_time:
                new_df, refresh_df = filter_rolling_window(combined_df, max_time, window_days=window_days)
                if len(new_df) == 0 and len(refresh_df) == 0:
                    if force_continue:
                        print("没有新增/刷新数据，但强制继续（刷新缓存/指标）")
                    else:
                        print("没有新增/刷新数据，ETL 跳过")
                        return

        # Step 3: 清洗数据
        if len(new_df) > 0:
            new_df = clean_data(new_df, spu_df, keyword_rules, id_rules,
                               taoke_order_ids=taoke_order_ids, live_order_ids=live_order_ids,
                               taoke_product_rules=taoke_product_rules,
                               force_continue=force_continue)
        if len(refresh_df) > 0:
            refresh_df = clean_data(refresh_df, spu_df, keyword_rules, id_rules,
                                   taoke_order_ids=taoke_order_ids, live_order_ids=live_order_ids,
                                   taoke_product_rules=taoke_product_rules,
                                   force_continue=force_continue)

        # Step 4: 写入数据库（滑动窗口模式）
        upsert_to_duckdb(new_df, refresh_df, mode=run_mode, window_days=window_days)

        # Step 4.5: 事务化——DuckDB 写入成功后，才标记文件为已处理
        if run_mode == 'incremental':
            for df_src, dtype in [(shop_df, 'shop'), (member_df, 'member')]:
                updates = getattr(df_src, 'attrs', {}).get('_etl_processed_updates', {})
                if updates:
                    processed = _load_processed_files(dtype)
                    processed.update(updates)
                    _save_processed_files(dtype, processed)
                    print(f"  [事务化] 已标记 {len(updates)} 个 {dtype} 文件为已处理")

        # Step 5: 预计算每日指标（增量模式）
        _update_incremental_metrics(new_df, refresh_df, window_days=window_days)

    # Step 6: 维护 user_first_purchase 表（滑动窗口模式）
    _build_user_first_purchase_table(run_mode, window_days=window_days)

    # Step 7: 全量模式下标记所有源文件为已处理
    if run_mode == 'full':
        _mark_all_files_processed()

    # Step 8: 品类看板 v2 预计算（品类流转 + 流失预警）
    print("\n品类看板 v2 预计算...")
    try:
        from scripts.precompute_category_flow import run_full_precomputation as run_flow_full
        from scripts.precompute_category_churn import run_full_precomputation as run_churn_full
        # 全量预计算（覆盖写入幂等）
        run_flow_full()
        run_churn_full()
        print("  预计算完成")
    except Exception as e:
        print(f"  ⚠️ 预计算跳过（可稍后手动运行）：{e}")

    print("\n" + "=" * 60)
    print("滑动窗口 ETL 完成!")
    print("=" * 60)

    # 强制 GC 立即释放 DuckDB 文件锁，避免 ETL 完成后后端仍被阻塞
    import gc as _gc; _gc.collect()


def _mark_all_files_processed():
    """
    全量 ETL 完成后，将所有源文件标记为已处理（记录 mtime）。
    这样下次增量运行时不会重读这些历史文件（除非文件被修改过）。
    同时也处理"数据库已有数据但 processed_files 为空"的冷启动场景。
    """
    print("\n标记所有源文件为已处理...")
    for data_type, data_source in [('shop', SHOP_DATA_SOURCE), ('member', MEMBER_DATA_SOURCE)]:
        if not data_source.exists():
            continue
        files = list(data_source.rglob("*.xlsx"))
        # 用相对路径→mtime 作为唯一键
        rel_paths = {str(f.relative_to(data_source)): f.stat().st_mtime for f in files}
        _save_processed_files(data_type, rel_paths)
        print(f"  {data_type}: 标记 {len(rel_paths)} 个文件为已处理")


def _rebuild_metrics():
    """重建指标表（全量模式）"""
    print("\n重建每日指标...")
    conn = duckdb.connect(str(DUCKDB_PATH))
    conn.execute("DELETE FROM daily_metrics")

    conn.execute("""
        INSERT INTO daily_metrics
        SELECT
            DATE(pay_time) as date,
            COALESCE(SUM(actual_amount), 0) as gmv,
            COALESCE(SUM(CASE WHEN (is_goujinjin = FALSE AND is_refund = FALSE) THEN actual_amount ELSE 0 END), 0) as gsv,
            COUNT(DISTINCT order_id) as order_count,
            COUNT(DISTINCT CASE WHEN (is_goujinjin = FALSE AND is_refund = FALSE) THEN order_id END) as gsv_order_count,
            COUNT(DISTINCT user_id) as new_user_count,
            0 as old_user_count,
            COALESCE(SUM(CASE WHEN is_member = TRUE THEN actual_amount ELSE 0 END), 0) as member_gmv,
            COALESCE(SUM(CASE WHEN is_member = TRUE AND (is_goujinjin = FALSE AND is_refund = FALSE) THEN actual_amount ELSE 0 END), 0) as member_gsv,
            COUNT(DISTINCT CASE WHEN is_member = TRUE THEN user_id END) as member_count,
            COALESCE(AVG(actual_amount), 0) as avg_order_value,
            0 as new_user_gmv,
            0 as old_user_gmv
        FROM orders
        WHERE pay_time IS NOT NULL
        GROUP BY DATE(pay_time)
        ORDER BY date
    """)

    count = conn.execute("SELECT COUNT(*) FROM daily_metrics").fetchone()[0]
    print(f"  每日指标: {count} 天")
    conn.close()


def _update_incremental_metrics(new_df, refresh_df, window_days=30):
    """增量更新每日指标（滑动窗口模式：新日期 + 窗口内日期都刷新）"""
    from datetime import datetime, timedelta

    # 收集所有需要更新的日期
    all_dates = set()
    if not new_df.empty:
        all_dates.update(new_df['pay_time'].dt.date.dropna().unique())
    if not refresh_df.empty:
        all_dates.update(refresh_df['pay_time'].dt.date.dropna().unique())

    if not all_dates:
        return

    # 窗口内的日期也要加入（已有订单状态变化可能影响历史日期的指标）
    today = datetime.now().date()
    window_start = today - timedelta(days=window_days)
    for d in pd.date_range(start=window_start, end=today):
        all_dates.add(d.date())

    date_list = sorted(all_dates)
    print(f"\n增量更新每日指标 ({len(date_list)} 个日期)...")

    conn = duckdb.connect(str(DUCKDB_PATH))
    conn.execute("DELETE FROM daily_metrics WHERE date IN (SELECT unnest(?))", [date_list])
    conn.execute("""
        INSERT INTO daily_metrics
        SELECT
            DATE(pay_time) as date,
            COALESCE(SUM(actual_amount), 0) as gmv,
            COALESCE(SUM(CASE WHEN (is_goujinjin = FALSE AND is_refund = FALSE) THEN actual_amount ELSE 0 END), 0) as gsv,
            COUNT(DISTINCT order_id) as order_count,
            COUNT(DISTINCT CASE WHEN (is_goujinjin = FALSE AND is_refund = FALSE) THEN order_id END) as gsv_order_count,
            COUNT(DISTINCT user_id) as new_user_count,
            0 as old_user_count,
            COALESCE(SUM(CASE WHEN is_member = TRUE THEN actual_amount ELSE 0 END), 0) as member_gmv,
            COALESCE(SUM(CASE WHEN is_member = TRUE AND (is_goujinjin = FALSE AND is_refund = FALSE) THEN actual_amount ELSE 0 END), 0) as member_gsv,
            COUNT(DISTINCT CASE WHEN is_member = TRUE THEN user_id END) as member_count,
            COALESCE(AVG(actual_amount), 0) as avg_order_value,
            0 as new_user_gmv,
            0 as old_user_gmv
        FROM orders
        WHERE pay_time IS NOT NULL AND DATE(pay_time) IN (SELECT unnest(?))
        GROUP BY DATE(pay_time)
    """, [date_list])

    print(f"  已更新 {len(date_list)} 个日期的指标")
    conn.close()


def _build_user_first_purchase_table(mode: str = 'full', window_days: int = 30):
    """
    构建 user_first_purchase 表（滑动窗口模式）。

    全量模式  : DROP 后全量重建
    增量模式  :
      1. 窗口内用户：DELETE 后重新计算（状态变化可能影响首购日期）
      2. 全新用户：INSERT 不在表中的用户
    """
    from datetime import datetime, timedelta
    print("\n维护 user_first_purchase 表...")

    conn = duckdb.connect(str(DUCKDB_PATH))

    if mode == 'full':
        conn.execute("DROP TABLE IF EXISTS user_first_purchase")
        conn.execute("""
            CREATE TABLE user_first_purchase (
                user_id     VARCHAR PRIMARY KEY,
                first_pay_date DATE
            )
        """)
        conn.execute("""
            INSERT INTO user_first_purchase
            SELECT user_id, MIN(DATE(pay_time)) AS first_pay_date
            FROM orders
            WHERE pay_time IS NOT NULL
              AND is_goujinjin = FALSE
              AND is_refund = FALSE
              AND user_id IS NOT NULL
              AND user_id != ''
            GROUP BY user_id
        """)
        count = conn.execute("SELECT COUNT(*) FROM user_first_purchase").fetchone()[0]
        print(f"  user_first_purchase 全量重建: {count:,} 用户")
    else:
        today = datetime.now().date()
        window_start = today - timedelta(days=window_days)

        existing_tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
        if 'user_first_purchase' not in existing_tables:
            conn.execute("""
                CREATE TABLE user_first_purchase (
                    user_id     VARCHAR PRIMARY KEY,
                    first_pay_date DATE
                )
            """)

        # 1. 窗口内用户：先删除再重新计算
        conn.execute("""
            DELETE FROM user_first_purchase
            WHERE user_id IN (
                SELECT DISTINCT user_id FROM orders
                WHERE DATE(pay_time) >= ? AND DATE(pay_time) <= ?
            )
        """, [window_start, today])

        conn.execute("""
            INSERT INTO user_first_purchase
            SELECT user_id, MIN(DATE(pay_time)) AS first_pay_date
            FROM orders
            WHERE pay_time IS NOT NULL
              AND is_goujinjin = FALSE
              AND is_refund = FALSE
              AND user_id IS NOT NULL
              AND user_id != ''
              AND user_id IN (
                  SELECT DISTINCT user_id FROM orders
                  WHERE DATE(pay_time) >= ? AND DATE(pay_time) <= ?
              )
            GROUP BY user_id
        """, [window_start, today])

        # 2. 全新用户
        conn.execute("""
            INSERT INTO user_first_purchase
            SELECT user_id, MIN(DATE(pay_time)) AS first_pay_date
            FROM orders
            WHERE pay_time IS NOT NULL
              AND is_goujinjin = FALSE
              AND is_refund = FALSE
              AND user_id IS NOT NULL
              AND user_id != ''
              AND user_id NOT IN (SELECT user_id FROM user_first_purchase)
            GROUP BY user_id
        """)
        count = conn.execute("SELECT COUNT(*) FROM user_first_purchase").fetchone()[0]
        print(f"  user_first_purchase 增量更新: 当前合计 {count:,} 用户")

    conn.close()

def update_taoke_channel():
    """
    全量纠正淘客渠道标记（完整重建，非增量）。

    策略：仅将当前标为'淘客'的订单重置为'其他'，再重新应用 P6(订单号) / P6-2(关键词) 规则。
    这样当淘客数据库变更或关键词规则变化时，历史订单能自动纠正。

    保护渠道（不受影响）：U先派样、百补派样、赠品&0.01渠道、直播、货架、达播、微博、购物金
    """
    print("\n" + "=" * 60)
    print("淘客渠道全量纠正")
    print("=" * 60)

    taoke_ids = load_taoke_order_ids()

    conn = duckdb.connect(str(DUCKDB_PATH))

    before = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE channel = '淘客'"
    ).fetchone()[0]
    print("纠正前淘客订单: " + str(before) + " 条")

    try:
        # Step 1: 仅将当前标为'淘客'的订单重置为'其他'（历史误标纠正）
        # 其他渠道（U先/百补/赠品/直播/货架/微博/达播/购物金）完全不动
        reset_sql = (
            "UPDATE orders "
            "SET channel = '其他' "
            "WHERE channel = '淘客'"
        )
        conn.execute(reset_sql)
        reset_count = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE channel = '淘客'"
        ).fetchone()[0]
        print("  已重置 " + str(before - reset_count) + " 个淘客订单为'其他'")

        # Step 2: P6 订单号匹配
        marked_p6 = 0
        if taoke_ids:
            conn.execute("CREATE OR REPLACE TEMP TABLE _taoke_ids (order_id VARCHAR PRIMARY KEY)")
            id_list = list(taoke_ids)
            BATCH = 10000
            for i in range(0, len(id_list), BATCH):
                batch = id_list[i:i + BATCH]
                safe_batch = [str(oid).replace("'", "''") for oid in batch]
                values = ",".join(["('" + oid + "')" for oid in safe_batch])
                conn.execute("INSERT INTO _taoke_ids VALUES " + values)

            p6_sql = (
                "UPDATE orders "
                "SET channel = '淘客' "
                "FROM _taoke_ids t "
                "WHERE orders.order_id = t.order_id "
                "AND orders.channel = '其他'"
            )
            conn.execute(p6_sql)
            marked_p6 = conn.execute(
                "SELECT COUNT(*) FROM orders WHERE channel = '淘客'"
            ).fetchone()[0]
            print("  P6 订单号匹配: +" + str(marked_p6) + " 条")

        # Step 3: P6-2 关键词匹配（芙清淘客商品标识后缀：T1/T2/T4/TK，大小写不敏感）
        marked_p62 = 0
        p62_sql = (
            "UPDATE orders "
            "SET channel = '淘客' "
            "WHERE channel = '其他' "
            "AND (LOWER(product_title) LIKE '%t1%' OR LOWER(product_title) LIKE '%t2%' "
            "     OR LOWER(product_title) LIKE '%t4%' OR LOWER(product_title) LIKE '%tk%')"
        )
        conn.execute(p62_sql)
        marked_p62 = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE channel = '淘客'"
        ).fetchone()[0] - marked_p6
        print("  P6-2 关键词匹配: +" + str(marked_p62) + " 条")

        after = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE channel = '淘客'"
        ).fetchone()[0]
        delta = after - before
        print("\n纠正完成！淘客订单: " + str(before) + " -> " + str(after) + "（净变化: " + ("+" if delta >= 0 else "") + str(delta) + "）")

    finally:
        conn.execute("DROP TABLE IF EXISTS _taoke_ids")
        conn.close()


def refresh_visitor_data():
    """
    增量刷新 daily_visitors 表（访客数/新增会员数）。

    策略：
      1. 扫描店铺流量数据库目录下的最新 xlsx 文件
      2. 比对 daily_visitors 表最新日期，只写入新数据
      3. xlsx 结构：日期 / 访客数 / 新增会员数
    """
    from backend.config import VISITOR_DATA_SOURCE, DUCKDB_PATH

    print("\n" + "-" * 40)
    print("刷新访客数据（daily_visitors）")
    print("-"  * 40)

    if not VISITOR_DATA_SOURCE.exists():
        print(f"  目录不存在: {VISITOR_DATA_SOURCE}")
        return

    # 找最新的 xlsx 文件
    xlsx_files = sorted(VISITOR_DATA_SOURCE.glob("*.xlsx"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not xlsx_files:
        print(f"  目录中无 xlsx 文件")
        return

    latest = xlsx_files[0]
    print(f"  读取: {latest.name}")

    try:
        df = pd.read_excel(latest, engine='openpyxl', header=0)
    except Exception as e:
        print(f"  读取失败: {e}")
        return

    # 列名标准化
    df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]
    if '日期' not in df.columns or '访客数' not in df.columns:
        print(f"  缺少必需列，实际列: {list(df.columns)}")
        return

    df['date'] = pd.to_datetime(df['日期'], errors='coerce').dt.date
    df = df.dropna(subset=['date'])

    # 新增会员数列名可能不同
    member_col = None
    for cand in ['新增会员数', '新增会员', 'new_members']:
        if cand in df.columns:
            member_col = cand
            break

    df['visitors'] = pd.to_numeric(df['访客数'], errors='coerce').fillna(0).astype(int)
    df['new_members'] = pd.to_numeric(df[member_col], errors='coerce').fillna(0).astype(int) if member_col else 0
    df['member_join_rate'] = (df['new_members'] / df['visitors'].replace(0, 1)).round(6)

    result = df[['date', 'visitors', 'new_members', 'member_join_rate']].copy()

    conn = duckdb.connect(str(DUCKDB_PATH))
    try:
        # 确保表存在
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_visitors (
                date DATE PRIMARY KEY,
                visitors BIGINT,
                new_members BIGINT,
                member_join_rate DOUBLE
            )
        """)

        # 查已有日期范围
        existing = conn.execute("SELECT max(date) FROM daily_visitors").fetchone()
        max_existing = existing[0] if existing and existing[0] else None

        if max_existing:
            new_rows = result[result['date'] > max_existing]
            print(f"  已有数据至 {max_existing}，新增 {len(new_rows)} 天")
        else:
            new_rows = result
            print(f"  表为空，全量导入 {len(new_rows)} 天")

        if new_rows.empty:
            print("  无新数据")
            conn.close()
            return

        # 批量插入
        for _, row in new_rows.iterrows():
            conn.execute(
                "INSERT OR REPLACE INTO daily_visitors (date, visitors, new_members, member_join_rate) VALUES (?, ?, ?, ?)",
                [row['date'], int(row['visitors']), int(row['new_members']), float(row['member_join_rate'])]
            )

        final_count = conn.execute("SELECT COUNT(*) FROM daily_visitors").fetchone()[0]
        new_max = conn.execute("SELECT max(date) FROM daily_visitors").fetchone()[0]
        print(f"  写入完成: +{len(new_rows)} 天，合计 {final_count} 天，最新 {new_max}")

    finally:
        conn.close()


def refresh_campaign_schedule():
    """
    刷新 campaign_schedule 表（大促时间 + 0.01锁权时间）。

    策略：
      1. 读取活动节奏 CSV → 写入 conversion_start/end
      2. 基于 orders 表中 0.01 购买数据自动推算 lock_start/lock_end
      3. 已有完整记录时跳过，仅补算缺失的锁权时间
    """
    from backend.config import CAMPAIGN_SCHEDULE_SOURCE, DUCKDB_PATH
    from datetime import timedelta as _td

    print("\n" + "-" * 40)
    print("刷新活动节奏表（campaign_schedule）")
    print("-" * 40)

    if not CAMPAIGN_SCHEDULE_SOURCE.exists():
        print(f"  文件不存在: {CAMPAIGN_SCHEDULE_SOURCE}")
        return

    try:
        df = pd.read_csv(CAMPAIGN_SCHEDULE_SOURCE)
    except Exception as e:
        print(f"  读取失败: {e}")
        return

    # 列名标准化
    df.columns = [c.strip() for c in df.columns]
    required = ['year', '活动名称', '开始时间', '结束时间']
    if not all(c in df.columns for c in required):
        print(f"  缺少必需列，实际列: {list(df.columns)}")
        return

    # 转换日期
    df['conversion_start'] = pd.to_datetime(df['开始时间'], errors='coerce').dt.date
    df['conversion_end'] = pd.to_datetime(df['结束时间'], errors='coerce').dt.date
    df = df.dropna(subset=['conversion_start', 'conversion_end'])

    conn = duckdb.connect(str(DUCKDB_PATH))
    try:
        # 创建表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS campaign_schedule (
                id INTEGER PRIMARY KEY,
                year INTEGER,
                campaign_name VARCHAR,
                conversion_start DATE,
                conversion_end DATE,
                lock_start DATE,
                lock_end DATE,
                source VARCHAR DEFAULT 'auto'
            )
        """)

        existing_count = conn.execute("SELECT COUNT(*) FROM campaign_schedule").fetchone()[0]
        missing_locks = conn.execute("SELECT COUNT(*) FROM campaign_schedule WHERE lock_start IS NULL").fetchone()[0]

        if existing_count > 0 and missing_locks == 0:
            print(f"  表已有 {existing_count} 条记录且锁权时间完整，跳过")
            return

        # 首次写入：从 CSV 导入转化时间
        if existing_count == 0:
            for idx, row in df.iterrows():
                conn.execute("""
                    INSERT INTO campaign_schedule (id, year, campaign_name, conversion_start, conversion_end, source)
                    VALUES (?, ?, ?, ?, ?, 'auto')
                """, [idx + 1, int(row['year']), row['活动名称'], row['conversion_start'], row['conversion_end']])
            print(f"  从 CSV 写入 {len(df)} 条活动记录")

        # 补算锁权时间（仅针对 lock_start IS NULL 的记录）
        campaigns = conn.execute("""
            SELECT id, year, campaign_name, conversion_start
            FROM campaign_schedule WHERE lock_start IS NULL
            ORDER BY year, id
        """).fetchall()

        if not campaigns:
            print("  无需补算锁权时间")
            return

        for camp in campaigns:
            camp_id, year, name, conv_start = camp
            # 锁权搜索窗口：转化开始前30天 ~ 转化开始前1天
            search_start = conv_start - _td(days=30)
            search_end = conv_start - _td(days=1)

            lock_range = conn.execute("""
                SELECT MIN(DATE(pay_time)) as lock_start, MAX(DATE(pay_time)) as lock_end
                FROM orders
                WHERE channel = '赠品&0.01渠道'
                  AND actual_amount = 0.01
                  AND pay_time >= ?::DATE AND pay_time <= ?::DATE
            """, [str(search_start), str(search_end)]).fetchone()

            if lock_range and lock_range[0]:
                conn.execute("""
                    UPDATE campaign_schedule SET lock_start = ?, lock_end = ?, source = 'auto'
                    WHERE id = ?
                """, [lock_range[0], lock_range[1], camp_id])
                print(f"  {year} {name}: 锁权 {lock_range[0]} ~ {lock_range[1]}")
            else:
                # 无0.01数据时，用转化开始前7天作为默认
                default_lock_start = conv_start - _td(days=7)
                default_lock_end = search_end
                conn.execute("""
                    UPDATE campaign_schedule SET lock_start = ?, lock_end = ?, source = 'default'
                    WHERE id = ?
                """, [default_lock_start, default_lock_end, camp_id])
                print(f"  {year} {name}: 无0.01数据，使用默认 {default_lock_start} ~ {default_lock_end}")

        final_count = conn.execute("SELECT COUNT(*) FROM campaign_schedule").fetchone()[0]
        print(f"  完成: 共 {final_count} 条活动记录")

    finally:
        conn.close()
