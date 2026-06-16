"""ETL 主流程编排
run_full_etl、增量更新、RFM 预计算、访客数据刷新。
"""
import gc
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.etl.config import (
    DUCKDB_PATH, DUCKDB_MEMORY_LIMIT,
    SHOP_DATA_SOURCE, MEMBER_DATA_SOURCE,
    _load_processed_files, _save_processed_files,
    _get_processed_files_path, _get_file_hash, PARQUET_DATA_DIR,
)
# FIX-S2: 9 行 import 改 1 行用 helper 验 E2E (其余 8 行保留 DUCKDB_MEMORY_LIMIT 常量向后兼容)
from backend.config import get_duckdb_memory_limit  # noqa: E402  W7 helper

from scripts.etl.sources import (
    load_spu_mapping, load_channel_rules,
    load_taoke_order_ids, load_live_order_ids, load_taoke_product_rules,
)
from scripts.etl.ingest import load_data_files, rename_columns
from scripts.etl.load import _copy_df_to_duckdb
from scripts.etl.transform import clean_data
from scripts.etl.load import (
    upsert_to_duckdb,
    filter_rolling_window, get_db_max_pay_time,
    _create_orders_table, _create_indexes,
)
from scripts.etl._timer import PerfTimer

import pandas as pd
import duckdb

from backend.db.memory_monitor import check_memory

from datetime import datetime as _dt

def _step_log(step_name, event="start"):
    """打印带时间戳的步骤日志，方便监控 ETL 进度。"""
    ts = _dt.now().strftime("%H:%M:%S")
    print(f"  [{step_name}] {event}: {ts}")


# FIX-S5: run_full_etl 任何异常时调 notify_etl_complete(status='failed')
# 装饰器避免函数体 indent 1 个 tab; 同时避免 step 1-7 抛异常时 W6 块被跳过 (设计 doc §W6 「失败推 ❌」)
import functools as _functools

def _safe_etl_notify_on_failure(func):
    """FIX-S5: run_full_etl 任何异常时调 notify_etl_complete(status='failed').
    notify 失败不阻塞 (二次 try/except), 原异常 re-raise 不吃掉.
    """
    @_functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            try:
                from scripts.etl.notify import notify_etl_complete
                notify_etl_complete(
                    {"orders_count": "?", "user_rfm_count": "?",
                     "wall_min": 0, "gates_overall": f"failed: {type(e).__name__}"},
                    status="failed",
                )
                print(f"  [W6 通知] step 1-7 异常 status=failed: {type(e).__name__}: {str(e)[:200]}")
            except Exception as notify_e:
                print(f"  [W6 通知] 通知失败: {type(notify_e).__name__}: {str(notify_e)[:100]}")
            raise  # 保持原异常抛出
    return wrapper


def _mark_user_id_history_member(shop_df: pd.DataFrame, conn) -> int:
    """Sprint 15 Wave 3 治根: 老客回购 per-user 标.

    之前 per-order 标 (line 398) 导致老客回购标 FALSE (新单 order_id 不在历史 mark,
    但 user_id 跟历史 is_member=TRUE 订单的 user_id 重叠). 6/9+ 64 个新订单
    里有 18 个老客 (历史 is_member=TRUE) 全标 FALSE, 前端会员数据缺失.

    修法: 老客 (is_member=FALSE) 但 user_id 跟历史 is_member=TRUE 重叠 → 标 TRUE.
    Return: 标为老客回购的订单数.

    Edge cases:
        - shop_df 空或无 user_id 列 → 返 0
        - user_id IS NULL → 跳过 (WHERE 过滤)
        - shop_df.is_member 已为 TRUE → 不动 (old_customer_mask 已排除)
        - 重复调 → idempotent (loc[mask] 覆盖写同样值)
    """
    if shop_df.empty or 'user_id' not in shop_df.columns:
        return 0
    historical_member_user_ids = set(conn.execute(
        "SELECT DISTINCT user_id FROM orders WHERE is_member = TRUE AND user_id IS NOT NULL"
    ).fetchdf()['user_id'].dropna())
    old_customer_mask = (~shop_df['is_member']) & shop_df['user_id'].isin(historical_member_user_ids)
    n_old = int(old_customer_mask.sum())
    if n_old > 0:
        shop_df.loc[old_customer_mask, 'is_member'] = True
    return n_old


@_safe_etl_notify_on_failure
def run_full_etl(mode='auto', window_days=30, force_continue=False,
                 skip_dq=False, skip_w4=False) -> None:
    """
    完整 ETL 流程（滑动窗口增量模式）

    mode:
      'auto'    - 自动检测：数据库空则全量，有数据则增量
      'full'    - 强制全量重建
      'inc'     - 强制增量（数据库必须已有数据）
    window_days:
      滑动窗口天数，刷新最近 N 天的订单状态（默认30天，覆盖退款周期）
    skip_dq:
      跳过 W3 DQ assertions (6 断言 + rfm_quarantine 写入) — 调试/QA 用
    skip_w4:
      跳过 W4 fact_rfm_long 预计算 (incremental + merge T-7) — 调试/QA 用

    幂等性:
      - W3: 跑 run_assertions 前清空当天 rfm_quarantine 行（重跑不会累积冗余）
      - W4: _next_version() 续号 + UNIQUE(date, dim_key, version) + ON CONFLICT DO NOTHING
            → 同 date 重跑产生新 version 行（dbt-style snapshot 保留历史链）
    """
    print("=" * 60)
    print(f"芙清 CRM - 数据清洗 ETL v6 (滑动窗口: {window_days}天)")
    # FIX-S2: 用 get_duckdb_memory_limit() helper, 实时读 DUCKDB_MEMORY_LIMIT_OVERRIDE env
    # (W4 async 跑批时 setup_async_memory() export 16GB, 此处 print 应输出 16GB 而非默认 8GB)
    print(f"内存限制: {get_duckdb_memory_limit()}")
    print("=" * 60)
    check_memory(label="ETL 启动")

    # W6: 记录 ETL 真实 elapsed wall time（用于 notify_etl_complete stats）
    import time as _time
    _etl_wall_start = _time.perf_counter()

    # Step 0: 确定模式（get_db_max_pay_time 有 lru_cache，重复调用无开销）
    _step_log("Step 0 确定模式", "start")
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
    # Sprint 21+ P0 修复 (2026-06-12): 加 parquet 缓存目录存在性检测. 之前 bug: 用户手动
    # 删 parquet 缓存 (data/parquet) + 重置 processed_files 后, 冷启动逻辑假设 DB 跟
    # processed_files 同步, 自动标 107+82 文件"已处理" 跳过加载, 06-10/06-11/06-12 数据
    # 没进 DB, 06-09 会员数据 is_member 全 False 修复不了. 现在: parquet 目录不存在
    # (用户手动删了) → 跳过冷启动, 让 fill_parquet_cache 重新生成 + ingest 重新加载
    if run_mode == 'incremental':
        _parquet_exists = PARQUET_DATA_DIR.exists() and any(PARQUET_DATA_DIR.rglob("*.parquet"))
        if not _parquet_exists:
            print("  [Sprint 21+ 修复] parquet 缓存目录不存在或为空, 跳过冷启动标记, 强制重新加载")
            print("  [Sprint 21+ 修复] 跑批后 fill_parquet_cache 重新生成 + ingest 重新加载所有源文件")
        else:
            for data_type, data_source in [('shop', SHOP_DATA_SOURCE), ('member', MEMBER_DATA_SOURCE)]:
                processed = _load_processed_files(data_type)
                processed_path = _get_processed_files_path(data_type)
                # FIX: 只有 tracker 文件不存在时才走冷启动；空 {} 或旧格式迁移后
                # 不应把全部历史文件标为已处理，否则新增文件会被跳过。
                if not processed_path.exists() and data_source.exists():
                    total_files = len(list(data_source.rglob("*.xlsx")))
                    if total_files > 0:
                        print(f"  [冷启动] {data_type}: 数据库有数据但 tracker 不存在，自动标记 {total_files} 个历史文件")
                        _mark_all_files_processed()
                        break  # _mark_all_files_processed 一次性标记 shop+member

    # Step 1: 加载 SPU 匹配表、渠道规则、淘客数据和直播数据源
    _step_log("Step 1 加载参考数据", "start")
    with PerfTimer("pl_step1_load_ref_data"):
        spu_df = load_spu_mapping()
        keyword_rules, id_rules = load_channel_rules()
        taoke_order_ids = load_taoke_order_ids()
        live_order_ids = load_live_order_ids()
        taoke_product_rules = load_taoke_product_rules()  # 商品ID+时间范围补充淘客
    check_memory(label="Step 1 参考数据加载完成")

    # 用会员 order_id 集合做 LEFT JOIN 语义标记
    # 增量模式：从 DuckDB 读取历史会员 order_id（避免只拿到新增会员数据）
    if run_mode == 'incremental':
        shop_df = load_data_files(SHOP_DATA_SOURCE, data_type='shop', run_mode=run_mode)
        member_df = load_data_files(MEMBER_DATA_SOURCE, data_type='member', run_mode=run_mode)
        if shop_df.empty:
            print("错误: 没有加载到任何店铺数据!")
            return
        # P2 散点: pipeline.py 10 处 duckdb.connect 是合理 ETL 单例例外 (见 CLAUDE.md §2
        # "ETL 脚本连接例外条款")。每次新开连接 + 立刻 close 是为了让 read_only/READ_WRITE
        # config 不互相污染 (DUCKDB-#1: Can't open a connection to same database file
        # with a different configuration)。同进程单例会踩这个坑。
        if member_df.empty:
            print("  增量模式：从 DuckDB 加载历史 member_order_ids...")
            # 修 P0 fail-soft：之前 read_only=True 连接读历史 order_ids，
            # 污染同进程 DuckDB config，导致 cache.py:_open_write_conn() 后续
            # 开 access_mode=READ_WRITE 抛 "Can't open a connection to same database
            # file with a different configuration"。修法：去掉 read_only=True，
            # 用默认 READ_WRITE 连接，与 cache.py 后续 _open_write_conn() 保持
            # 一致 access_mode。仅 SELECT DISTINCT order_id 只读查询 + 立刻 close。
            conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": DUCKDB_MEMORY_LIMIT})
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

        # Sprint 15 B2 治根: mark 增量同步 (增量模式)
        # 之前增量 ETL 跑批时, member_order_ids 进了 orders 表的 is_member 字段,
        # 但**没 append 到 membership_mark** → mark 表 stale (1M 缺口永远在).
        # 修法: 跑批时把新拉的 member_df 跟历史会员 order_id 都 append 到 mark 表,
        # idempotent ON CONFLICT DO NOTHING, 跑批时间 +0.5s.
        # 配套 D.1 (replay_is_member.py 包事务) + B1 (mark 缺口反向回填).
        if member_order_ids:
            try:
                conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": DUCKDB_MEMORY_LIMIT})
                try:
                    mm_exists = conn.execute("""
                        SELECT COUNT(*) FROM duckdb_tables() WHERE table_name = 'membership_mark'
                    """).fetchone()[0]
                    if mm_exists == 0:
                        # Sprint 15 B1 首次跑: 兜底建表
                        conn.execute("""
                            CREATE TABLE IF NOT EXISTS membership_mark (
                                order_id VARCHAR PRIMARY KEY,
                                is_member BOOLEAN DEFAULT TRUE,
                                loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                    n_mark_before = conn.execute("SELECT COUNT(*) FROM membership_mark").fetchone()[0]
                    # 批量 append (100k 一批, 避免 N 个单 INSERT)
                    id_list = sorted(member_order_ids)
                    batch_size = 100000
                    for i in range(0, len(id_list), batch_size):
                        batch = id_list[i:i+batch_size]
                        # DuckDB VALUES 语法: VALUES (CAST(? AS VARCHAR)), (CAST(? AS VARCHAR)), ...
                        values_clause = ','.join(['(CAST(? AS VARCHAR))' for _ in batch])
                        sql = f"INSERT INTO membership_mark (order_id) VALUES {values_clause} ON CONFLICT (order_id) DO NOTHING"
                        conn.execute(sql, batch)
                    n_mark_after = conn.execute("SELECT COUNT(*) FROM membership_mark").fetchone()[0]
                    print(f"  [Sprint 15 B2] mark 增量同步 (增量模式): {n_mark_before:,} → {n_mark_after:,} (+{n_mark_after - n_mark_before:,})")
                finally:
                    conn.close()
            except Exception as _e:
                # Sprint 15 B2 fail-soft: mark 同步失败不阻塞 ETL 已完成的事实
                # (跟 W6 通知同样的 graceful degrade, B1 兜底 + replay 补)
                print(f"  [Sprint 15 B2] mark 同步失败 (D.1 兜底): {type(_e).__name__}: {str(_e)[:200]}")
    else:
        # 全量模式：不预加载所有数据，避免内存耗尽
        shop_df = pd.DataFrame()
        member_df = pd.DataFrame()
        member_order_ids = set()

    if run_mode == 'full':
        # ===== 全量模式：逐文件处理，不累积DataFrame，彻底避免内存峰值 =====
        _step_log("全量模式 orders 重建", "start")
        conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": DUCKDB_MEMORY_LIMIT})
        # 原子化: DELETE 替代 DROP。中断时表结构保留，不丢旧数据。
        # (TRUNCATE 可能 sigsegv, DROP 中断丢数据 — DELETE 是安全中间方案)
        has_orders = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'orders'"
        ).fetchone()[0] > 0
        if has_orders:
            n_before = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            conn.execute("DELETE FROM orders")
            print(f"  [全量模式] 已清空 orders 表 ({n_before:,} 行)")
        else:
            _create_orders_table(conn)
            _create_indexes(conn)
            print("  [全量模式] 已创建 orders 表")
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
                        print("    跳过")
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
            check_memory(label="Step A 原始库写入完成")

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
                except Exception as _exc:
                    # P1-#1 fail-loud: existing_ids 退化空集 → 所有会员行被当新订单 INSERT
                    # 触发重复 order_id 数据污染 (orders 表无 UNIQUE 约束)
                    raise RuntimeError(
                        f"FATAL: 加载 existing_ids 失败, 拒绝退化避免数据污染: "
                        f"{type(_exc).__name__}: {_exc}"
                    ) from _exc

                # 第一轮：INSERT全新订单（会员文件中有但店铺数据中没有的）
                all_member_order_ids = set()
                for i, f in enumerate(member_files):
                    print(f"  [{i+1}/{len(member_files)}] {f.name}")
                    try:
                        df = pd.read_excel(f, engine='openpyxl', header=0)
                        df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]
                        df = rename_columns(df)
                        if df.empty or 'order_id' not in df.columns:
                            del df
                            gc.collect()
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
                        del df
                        gc.collect()
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

                # Sprint 15 B2 治根: mark 增量同步 (全量模式)
                # 之前 all_member_order_ids 进了 orders 表, 但没 append 到 membership_mark
                # → mark 表 stale, 下次 replay 算错. 修法: 全量跑批时同步 mark 表.
                # idempotent ON CONFLICT DO NOTHING, 跑批时间 +0.5s.
                if all_member_order_ids:
                    n_mark_before = conn.execute("SELECT COUNT(*) FROM membership_mark").fetchone()[0]
                    mm_exists = conn.execute("""
                        SELECT COUNT(*) FROM duckdb_tables() WHERE table_name = 'membership_mark'
                    """).fetchone()[0]
                    if mm_exists == 0:
                        # Sprint 15 B1 首次跑: 兜底建表 (跟 build_membership_mark.py 一致)
                        conn.execute("""
                            CREATE TABLE IF NOT EXISTS membership_mark (
                                order_id VARCHAR PRIMARY KEY,
                                is_member BOOLEAN DEFAULT TRUE,
                                loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                    # 批量 INSERT (避免 100k 个单 INSERT)
                    for i in range(0, len(id_list), batch_size):
                        batch = id_list[i:i+batch_size]
                        # DuckDB VALUES 语法: VALUES (CAST(? AS VARCHAR)), (CAST(? AS VARCHAR)), ...
                        values_clause = ','.join(['(CAST(? AS VARCHAR))' for _ in batch])
                        sql = f"INSERT INTO membership_mark (order_id) VALUES {values_clause} ON CONFLICT (order_id) DO NOTHING"
                        conn.execute(sql, batch)
                    n_mark_after = conn.execute("SELECT COUNT(*) FROM membership_mark").fetchone()[0]
                    print(f"  [Sprint 15 B2] mark 增量同步: {n_mark_before:,} → {n_mark_after:,} (+{n_mark_after - n_mark_after:,})")
            else:
                print("  会员库无文件")

            total = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            print(f"\n写入 DuckDB 总计: {total:,} 行")
        finally:
            conn.close()

        new_df, refresh_df = pd.DataFrame(), pd.DataFrame()

        # Step 5: 预计算每日指标（全量模式）— 已挪到 Step 6 user_first_purchase 之后
        # 原因：metrics SQL 用 LEFT JOIN user_first_purchase 算 new/old_user_count，
        # 必须先建好 user_first_purchase 表。详见 _rebuild_metrics docstring。

        # Step 6: 创建 user_rfm 表 + 热点日期预加载
        _step_log("Step 6 user_rfm 预加载", "start")
        print("\n" + "-" * 40)
        print("Step 6: 创建 user_rfm 表 + 热点日期预加载")
        print("-" * 40)
        from backend.db.init import create_user_rfm_table
        create_user_rfm_table()
        from scripts.etl.preload_rfm import run_auto_preload
        results = run_auto_preload()
        # FIX-S1-regression-complete: run_auto_preload 返 2-tuple (date_str, rows); r[1]=rows
        success = [r for r in results if r[1] > 0]
        print(f"  user_rfm 预加载完成: {len(success)} 个组合")
    else:
        # ===== 增量模式：保持原逻辑 =====
        shop_df['is_member'] = shop_df['order_id'].isin(member_order_ids)

        # Sprint 15 Wave 3 治根 (老客回购 per-user 标): 调 _mark_user_id_history_member
        # helper. 见 helper docstring 完整治根说明 (老客回购标 FALSE bug 6/9+ 18 老客).
        if not shop_df.empty and 'user_id' in shop_df.columns:
            conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": DUCKDB_MEMORY_LIMIT})
            try:
                n_old = _mark_user_id_history_member(shop_df, conn)
                if n_old > 0:
                    print(f"  [Sprint 15 Wave 3] per-user 治根: {n_old} 个老客回购标 is_member=TRUE")
            finally:
                conn.close()

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
            _step_log("Step 2.5 滑动窗口过滤", "start")
            with PerfTimer("pl_step2_5_filter_rolling_window", window_days=window_days):
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
        _step_log("Step 3 清洗数据", f"start (new={len(new_df):,}, refresh={len(refresh_df):,})")
        if len(new_df) > 0:
            with PerfTimer("pl_step3_clean_data_new", rows=len(new_df)):
                new_df = clean_data(new_df, spu_df, keyword_rules, id_rules,
                                   taoke_order_ids=taoke_order_ids, live_order_ids=live_order_ids,
                                   taoke_product_rules=taoke_product_rules,
                                   force_continue=force_continue)
        if len(refresh_df) > 0:
            with PerfTimer("pl_step3_clean_data_refresh", rows=len(refresh_df)):
                refresh_df = clean_data(refresh_df, spu_df, keyword_rules, id_rules,
                                       taoke_order_ids=taoke_order_ids, live_order_ids=live_order_ids,
                                       taoke_product_rules=taoke_product_rules,
                                       force_continue=force_continue)

        # Step 4: 写入数据库（滑动窗口模式）
        _step_log("Step 4 写入 DuckDB", f"start (new={len(new_df):,}, refresh={len(refresh_df):,})")
        with PerfTimer("pl_step4_upsert_to_duckdb",
                       new_rows=len(new_df), refresh_rows=len(refresh_df)):
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

        # Sprint 14 B+ is_member replay 集成: 调 Sprint 10 写的 2 个手动救火脚本
        # 根因: pipeline.py:329 增量模式 shop_df.is_member = order_id in member_order_ids,
        # member_order_ids 来源有缺陷 (line 144-174):
        #   - member parquet 空 → 走 fallback 从 DuckDB WHERE is_member = TRUE → 鸡生蛋循环
        #   - member parquet 新增 → 只用新文件 order_id → 老会员丢失 → 老会员被标 FALSE
        # 修法: 调 build_membership_mark.py 重建 4.6M unique order_id 持久表,
        #       调 replay_is_member.py DROP 6 idx → UPDATE 1.8s → 重建 19.7s, 全表 is_member 重写
        # 跑批时间增量: +1-2 min (1.8s UPDATE + 19.7s index + 0.5s build)
        # 幂等: 两个脚本已幂等 (ON CONFLICT DO NOTHING / 只 UPDATE is_member=FALSE)
        # Sprint 15 Wave 3 治根: 增量模式下 B2 (line 182-215) 已做 mark 增量 append,
        # 跟 Step 4.6 build_membership_mark 全表重扫冗余, 增量模式跳过 Step 4.6 (B2 已覆盖).
        # 全量模式 (line 391 if 块之前) 仍跑 Step 4.6 兜底, 不动.
        if False:  # B2 已做增量 append, mark 跟增量数据一致, 增量模式跳过冗余全扫
            with PerfTimer("pl_step4_6_membership_mark"):
                try:
                    from scripts.etl.build_membership_mark import main as _build_membership_mark_main
                    _build_membership_mark_main()
                except Exception as _e:
                    # is_member 集成失败不阻塞 ETL 已完成的事实 (跟 W6 通知同样 graceful degrade)
                    print(f"  [Step 4.6 membership_mark] 跳过: {type(_e).__name__}: {str(_e)[:200]}")
        # Sprint 15 Wave 3 治根: Step 4.7 改增量 UPDATE (只新拉 order_id, 不全表 UPDATE + 不重建 6 索引).
        # 之前 replay_is_member.py 全表 UPDATE 10.6M + DROP/CREATE 6 索引 = 21s, 增量模式不需要.
        # 修法: BEGIN/COMMIT 包单事务 (跟 D.1 一致), UPDATE WHERE order_id IN member_order_ids.
        _step_log("Step 4.7 is_member 增量", f"start ({len(member_order_ids):,} order_ids)")
        with PerfTimer("pl_step4_7_replay_is_member_incremental"):
            try:
                if member_order_ids:
                    conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": DUCKDB_MEMORY_LIMIT})
                    try:
                        # Sprint 15 D.1 atomicity 一致: 单事务包裹, 失败 ROLLBACK.
                        conn.execute("BEGIN")
                        # 增量 UPDATE: 只本次新拉 order_id 的 is_member 跟 mark 对齐.
                        # 跟 T1 per-user 标 + B2 增量 append 配套, mark 跟 orders.is_member 永远一致.
                        placeholders = ','.join(['?' for _ in member_order_ids])
                        conn.execute(f"""
                            UPDATE orders
                            SET is_member = TRUE
                            WHERE order_id IN ({placeholders})
                            AND order_id IS NOT NULL
                        """, list(member_order_ids))
                        n_updated = conn.execute(
                            "SELECT COUNT(*) FROM orders WHERE order_id = ANY(CAST(? AS VARCHAR[])) AND is_member = TRUE",
                            [list(member_order_ids)],
                        ).fetchone()[0]
                        conn.execute("COMMIT")
                        print(f"  [Step 4.7 增量] 本次 UPDATE 影响 {n_updated} 单 is_member=TRUE")
                    except Exception:
                        conn.execute("ROLLBACK")
                        raise
                    finally:
                        conn.close()
            except Exception as _e:
                print(f"  [Step 4.7 增量] 跳过: {type(_e).__name__}: {str(_e)[:200]}")

        # Step 5: 预计算每日指标（增量模式）— 已挪到 Step 6 user_first_purchase 之后
        # 原因：metrics SQL 用 LEFT JOIN user_first_purchase 算 new/old_user_count，
        # 必须先建好 user_first_purchase 表。详见 _update_incremental_metrics docstring。

    # Step 6: 维护 user_first_purchase 表（滑动窗口模式）
    _step_log("Step 6 user_first_purchase", f"start (mode={run_mode})")
    with PerfTimer("pl_step6_user_first_purchase", run_mode=run_mode, window_days=window_days):
        _build_user_first_purchase_table(run_mode, window_days=window_days,
                                          new_df=new_df, refresh_df=refresh_df)

    # Step 6.5: 维护 user_recency 表（RFM flow 查询加速）
    _step_log("Step 6.5 user_recency", f"start (mode={run_mode})")
    with PerfTimer("pl_step6_5_user_recency", run_mode=run_mode, window_days=window_days):
        _build_user_recency_table(run_mode, window_days=window_days,
                                   new_df=new_df, refresh_df=refresh_df)

    # Step 6.7: 计算 daily_metrics（必须在 user_first_purchase 之后，SQL 用 LEFT JOIN）
    _step_log("Step 6.7 daily_metrics", "start")
    if run_mode == 'full':
        with PerfTimer("pl_step6_7_rebuild_metrics_after_ufp"):
            _rebuild_metrics()
    else:
        with PerfTimer("pl_step6_7_update_metrics_after_ufp", window_days=window_days):
            _update_incremental_metrics(new_df, refresh_df, window_days=window_days)

    # Step 7: 全量模式下标记所有源文件为已处理
    if run_mode == 'full':
        with PerfTimer("pl_step7_mark_all_files_processed"):
            _mark_all_files_processed()

    # Step 8: 品类看板 v2 预计算（品类流转 + 流失预警）
    # O5 优化: 增量模式无新数据时跳过
    _has_new_data = len(new_df) > 0 or len(refresh_df) > 0
    if run_mode == 'incremental' and not _has_new_data:
        print("\n品类看板 v2 预计算跳过（增量模式无新数据）")
        step8_ok = True
    else:
        print("\n品类看板 v2 预计算...")
        step8_ok = False
        try:
            from scripts.etl.precompute_category_flow import run_full_precomputation as run_flow_full
            from scripts.etl.precompute_category_churn import run_full_precomputation as run_churn_full
            # 全量预计算（覆盖写入幂等）
            with PerfTimer("pl_step8a_category_flow"):
                run_flow_full()
            with PerfTimer("pl_step8b_category_churn"):
                run_churn_full()
            print("  预计算完成")
            step8_ok = True
        except Exception as e:
            print(f"  ⚠️ 预计算跳过（可稍后手动运行）：{e}")

    # Step 8.5: W3 DQ assertions (6 断言) — 设计 doc v1.1 §W3 + §7.3
    # 失败入 rfm_quarantine, 不阻塞 ETL (SaaS 标准: 脏数据隔离不阻塞业务)
    # 复用 scraper/_send_lark_alert 真发 lark-cli (生产路径), 测试用 patch 绕过
    # skip_dq=True 跳过整块（调试/QA 场景，生产路径走默认 False）
    if not skip_dq:
        print("\nW3 DQ assertions (6 断言)...")
        try:
            from datetime import date as _date
            from scripts.etl.assertions import run_assertions
            from scripts.etl.config import DUCKDB_PATH as _DUCKDB_PATH
            # 独立连接 (READ_WRITE — rfm_quarantine 需要 write; 不与 ETL 单例共享, 避免 read_only/READ_WRITE config 冲突)
            _assert_conn = duckdb.connect(str(_DUCKDB_PATH), config={"memory_limit": DUCKDB_MEMORY_LIMIT})
            try:
                _assert_target = _date.today()
                # 幂等性: 跑前清空当天 quarantine 行, 重跑不会累积冗余历史
                # (W3 设计目的: 反映"当前 ETL 数据状态", 失败记录每次应反映最新检查结果)
                from scripts.etl.assertions import create_quarantine_table, QUARANTINE_TABLE
                create_quarantine_table(_assert_conn)
                _assert_conn.execute(
                    f"DELETE FROM {QUARANTINE_TABLE} WHERE date = ?::DATE",
                    [_assert_target],
                )
                with PerfTimer("pl_step8_5_dq_assertions", date=str(_assert_target)):
                    _assert_result = run_assertions(_assert_conn, _assert_target, send_alert=True)
                print(f"  DQ assertions: passed={_assert_result['passed']} failed={_assert_result['failed']} "
                      f"alert_sent={_assert_result['alert_sent']}")
                if _assert_result["failed_names"]:
                    print(f"  ⚠️ 失败断言: {_assert_result['failed_names']} (详见 rfm_quarantine 表)")
            finally:
                _assert_conn.close()
        except Exception as e:
            # 断言失败不阻塞 ETL 已完成的事实 (但要告警)
            print(f"  ⚠️ DQ assertions 异常跳过: {type(e).__name__}: {str(e)[:200]}")
    else:
        print("\nW3 DQ assertions 跳过 (--skip-dq)")

    print("\n" + "=" * 60)
    print("滑动窗口 ETL 完成!")
    print("=" * 60)

    # W4 full v0.4.12: 调 fact_rfm_long 预计算 (incremental + merge_replace T-7)
    # 设计 doc v1.1 §W4: 540 组合 append T-1 + dbt-style snapshot 修复 late-arriving
    # pipeline 集成点: ETL 末尾 (Step 8 之后), 失败不阻塞 W6 通知
    # skip_w4=True 跳过整块（调试/QA 场景，生产路径走默认 False）
    w4_stats = {"incremental": 0, "merge": 0, "merge_dates": [], "skipped": True, "reason": "未启用"}
    if not skip_w4:
        try:
            from scripts.etl.precompute_fact_rfm import (
                create_fact_rfm_table as _w4_create_table,
                incremental_load_with_merge,
            )
            # 16GB override 跑 W4 (W7 helper)
            from scripts.etl.precompute_fact_rfm import setup_async_memory, cleanup_async_memory
            setup_async_memory()
            # Sprint 9 维修: 之前 _w4_conn 用 16GB override, 跟主 conn 8GB + W3 _assert_conn 8GB
            # + cache.py _open_write_conn 8GB 不同 config. DuckDB 1.5.2 strict mode 报
            # "Can't open a connection to same database file with a different configuration".
            # 修法: 用跟主 conn 一致的 8GB memory_limit, 避免跨 connection config 冲突.
            # 16GB 过度设计, Sprint 5 真闭环 17 min 跑批 8GB 也 OK.
            _memory_limit = DUCKDB_MEMORY_LIMIT
            _w4_conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": _memory_limit})
            try:
                _w4_create_table(_w4_conn)
                from datetime import date as _date
                _inc, _merge, _dates = incremental_load_with_merge(_w4_conn, _date.today(), t_minus_days=7)
                w4_stats = {
                    "incremental": _inc,
                    "merge": _merge,
                    "merge_dates": _dates,
                    "skipped": False,
                }
                print(f"  [W4 fact_rfm_long] incremental={_inc} 行, merge={_merge} 行 ({len(_dates)} 天修复)")
            finally:
                _w4_conn.close()
                cleanup_async_memory()
        except Exception as _e:
            # W4 失败不阻塞 ETL 已完成的事实 (跟 W6 通知同样 graceful degrade)
            w4_stats = {"skipped": True, "reason": f"{type(_e).__name__}: {str(_e)[:200]}"}
            print(f"  [W4 fact_rfm_long] 跳过（可稍后手动运行 rfm_recompute_window.py）：{w4_stats['reason']}")
    else:
        w4_stats = {"incremental": 0, "merge": 0, "merge_dates": [], "skipped": True, "reason": "--skip-w4"}
        print("  [W4 fact_rfm_long] 跳过 (--skip-w4)")

    # W6: ETL 跑完 lark-cli 通知（复用 6 道门禁通道，graceful degrade）
    # 失败时也推（避免静默成功假象）。通知失败不能阻塞 ETL 已完成的事实。
    try:
        from scripts.etl.notify import notify_etl_complete
        # 收集 stats（部分字段缺失时 '?' 占位，不抛 KeyError）
        _etl_wall_min = round((_time.perf_counter() - _etl_wall_start) / 60, 1)
        _orders_count = "?"
        _user_rfm_count = "?"
        try:
            _conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": DUCKDB_MEMORY_LIMIT})
            try:
                _orders_count = _conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
                _user_rfm_count = _conn.execute("SELECT COUNT(*) FROM user_rfm").fetchone()[0]
            finally:
                _conn.close()
        except Exception as _e:
            print(f"  [W6 stats] 收集行数失败: {type(_e).__name__}: {str(_e)[:100]}")
        _stats = {
            "orders_count": _orders_count,
            "user_rfm_count": _user_rfm_count,
            "wall_min": _etl_wall_min,
            "mode": mode,
            "run_mode": run_mode,
            "gates_overall": "pass" if step8_ok else "failed",
            "w4_fact_rfm": w4_stats,  # W4 full v0.4.12 预计算结果
        }
        _sent, _reason = notify_etl_complete(_stats, status="success" if step8_ok else "failed")
        print(f"  [W6 通知] sent={_sent} reason={_reason}")
    except Exception as e:
        # 通知失败不能阻塞 ETL 已完成的事实
        print(f"  [W6 通知] 异常跳过: {type(e).__name__}: {str(e)[:200]}")

    # 强制 GC 立即释放 DuckDB 文件锁，避免 ETL 完成后后端仍被阻塞
    import gc as _gc
    _gc.collect()
    check_memory(label="ETL 完成")


def _mark_all_files_processed():
    """
    全量 ETL 完成后，将所有源文件标记为已处理（记录 mtime + hash）。
    这样下次增量运行时不会重读这些历史文件（除非文件被修改过）。
    同时也处理"数据库已有数据但 processed_files 为空"的冷启动场景。

    v2 格式：存储 {mtime, hash} dict，与 _file_changed 的检测逻辑一致。
    同时标记 Parquet 缓存文件，避免增量运行时重复读取。
    """
    print("\n标记所有源文件为已处理...")
    import time as _time
    for data_type, data_source in [('shop', SHOP_DATA_SOURCE), ('member', MEMBER_DATA_SOURCE)]:
        if not data_source.exists():
            continue
        files = list(data_source.rglob("*.xlsx"))
        # v2 格式：存储 {mtime, hash, cold_start_marked, marked_at} dict
        # Sprint 24 P0-1 治根 (2026-06-16): cold_start_marked 必须写 False (而非 True).
        # 旧实现 True 会触发 ingest._file_changed 路径 [B] (rec.get('cold_start_marked'))
        # → 强制返回 True → 冷启动后每次增量把 197 个文件全重读 (16-32h 灾难).
        # 新语义: cold_start_marked=False 表示"已登记" (mtime 短路够用), 不触发 [B].
        # 真"需重读"由 _file_changed 路径 [A] (key not in processed_files) 触发,
        # 那是 O2 增量 entry 模式 (新文件才需要), 跟冷启动批量登记无关.
        # marked_at 仍保留 (审计用, 证明这个 entry 是冷启动全量登记产物).
        # Step 4.5 加载成功后, _clean_processed_updates 把 cold_start_marked
        # 保留 (置 False) + 追加 last_processed_at, 走正常 mtime/hash 比对.
        processed = {}
        for f in files:
            rel_path = str(f.relative_to(data_source))
            processed[rel_path] = {
                'mtime': f.stat().st_mtime,
                'hash': _get_file_hash(f),
                'cold_start_marked': False,
                'marked_at': _time.time()
            }
        # Sprint 9 维修: 之前 parquet key = f.name (parquet 文件名), 但 ingest L82
        # _file_changed 用 _xlsx_stem_to_rel 反查 xlsx 相对路径. key 不一致
        # 导致冷启动后 ingest 仍把 103 个 parquet 视为新增, 走 xlsx fallback
        # 读 103 xlsx, RSS 撞 watchdog 阈值被 kill, 死循环. 修法: parquet
        # key 跟 ingest 一致, 用 _xlsx_stem_to_rel 反查 xlsx 相对路径.
        # Sprint 14 B 修 (codex P0-3): mtime 写源 xlsx mtime (而非 parquet mtime), 跟 ingest.py:144-151
        # 一致. xlsx 缺失时回退 parquet mtime (防御性, 跟 ingest 同模式).
        _xlsx_stem_to_rel = {xf.stem: str(xf.relative_to(data_source)) for xf in files}
        pq_dir = PARQUET_DATA_DIR / data_type
        if pq_dir.exists():
            for f in pq_dir.glob("*.parquet"):
                key = _xlsx_stem_to_rel.get(f.stem, f.name)
                xlsx_path = data_source / key
                xlsx_mtime = xlsx_path.stat().st_mtime if xlsx_path.exists() else f.stat().st_mtime
                processed[key] = {
                    'mtime': xlsx_mtime,
                    'hash': _get_file_hash(f),
                    # 同上: Parquet 缓存 entry 也写 cold_start_marked=False
                    # (已登记), 避免冷启动后增量走 [B] 重读所有 parquet 缓存.
                    'cold_start_marked': False,
                    'marked_at': _time.time()
                }
        _save_processed_files(data_type, processed)
        print(f"  {data_type}: 标记 {len(processed)} 个文件为已处理")


def _rebuild_metrics():
    """重建指标表（全量模式）

    P1 修复: old_user_count / new_user_gmv / old_user_gmv 之前硬编码 0，
    改为 LEFT JOIN user_first_purchase 用 first_pay_date 判定新客/老客。
    """
    print("\n重建每日指标...")
    conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": DUCKDB_MEMORY_LIMIT})

    has_ufp = conn.execute("""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_name = 'user_first_purchase'
    """).fetchone()[0] > 0
    if not has_ufp:
        print("  ⚠️ user_first_purchase 不存在，old_user_count fallback 为 0")
    conn.execute("DELETE FROM daily_metrics")

    if has_ufp:
        # Sprint 24 修复: 适配 6 列 schema (同 _update_incremental_metrics)
        conn.execute("""
            INSERT INTO daily_metrics
            SELECT
                DATE(o.pay_time) as d,
                COUNT(DISTINCT o.order_id) as order_count,
                COUNT(DISTINCT o.user_id) as user_count,
                COALESCE(SUM(CASE WHEN (o.is_goujinjin = FALSE AND o.is_refund = FALSE) THEN o.actual_amount ELSE 0 END), 0) as gsv,
                COUNT(DISTINCT CASE WHEN o.is_member = TRUE THEN o.user_id END) as member_user_count,
                COALESCE(SUM(CASE WHEN o.is_member = TRUE AND (o.is_goujinjin = FALSE AND o.is_refund = FALSE) THEN o.actual_amount ELSE 0 END), 0) as member_gsv
            FROM orders o
            LEFT JOIN user_first_purchase ufp ON o.user_id = ufp.user_id
            WHERE o.pay_time IS NOT NULL
            GROUP BY DATE(o.pay_time)
            ORDER BY d
        """)
    else:
        conn.execute("""
            INSERT INTO daily_metrics
            SELECT
                DATE(pay_time) as d,
                COUNT(DISTINCT order_id) as order_count,
                COUNT(DISTINCT user_id) as user_count,
                COALESCE(SUM(CASE WHEN (is_goujinjin = FALSE AND is_refund = FALSE) THEN actual_amount ELSE 0 END), 0) as gsv,
                COUNT(DISTINCT CASE WHEN is_member = TRUE THEN user_id END) as member_user_count,
                COALESCE(SUM(CASE WHEN is_member = TRUE AND (is_goujinjin = FALSE AND is_refund = FALSE) THEN actual_amount ELSE 0 END), 0) as member_gsv
            FROM orders
            WHERE pay_time IS NOT NULL
            GROUP BY DATE(pay_time)
            ORDER BY d
        """)

    count = conn.execute("SELECT COUNT(*) FROM daily_metrics").fetchone()[0]
    print(f"  每日指标: {count} 天")
    conn.close()


def _update_incremental_metrics(new_df, refresh_df, window_days=30):
    """增量更新每日指标（只处理实际变化的日期）

    O4 优化: 之前对整个30天窗口 DELETE+重算，现在只处理 new_df + refresh_df
    涉及的日期。refresh_df 已覆盖窗口内需要刷新的订单。

    新/老客口径（与 user_first_purchase 表保持一致）：
      - new_user: first_pay_date = 当日（用 ufp 判定，因为 ufp 只收录有效首购用户）
      - old_user: first_pay_date <  当日
      - 纯退款用户（历史从未下过有效订单）→ ufp 没记录 → 不计入 new/old
        （业务正确：他们当天只下退款单，不算新客购买行为）
      - new/old_user_gmv 加 is_refund=FALSE 过滤，与 gsv 口径一致
        （仅统计有效购买金额，不含退款）
    """
    # O4 优化: 只收集实际变化的日期（不扩展到整个窗口）
    all_dates = set()
    if not new_df.empty:
        all_dates.update(new_df['pay_time'].dt.date.dropna().unique())
    if not refresh_df.empty:
        all_dates.update(refresh_df['pay_time'].dt.date.dropna().unique())

    if not all_dates:
        return

    date_list = sorted(all_dates)
    print(f"\n增量更新每日指标 ({len(date_list)} 个日期, 之前是 {window_days + 1} 天窗口)...")

    conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": DUCKDB_MEMORY_LIMIT})
    conn.execute("DELETE FROM daily_metrics WHERE d IN (SELECT unnest(?))", [date_list])

    has_ufp = conn.execute("""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_name = 'user_first_purchase'
    """).fetchone()[0] > 0

    if has_ufp:
        # Sprint 24 修复: 适配当前生产 6 列 daily_metrics schema
        # (历史 _create_metrics_tables 仍是 13 列, 但生产表被手工简化成 6 列)
        # 6 列: d, order_count, user_count, gsv, member_user_count, member_gsv
        conn.execute("""
            INSERT INTO daily_metrics
            SELECT
                DATE(o.pay_time) as d,
                COUNT(DISTINCT o.order_id) as order_count,
                COUNT(DISTINCT o.user_id) as user_count,
                COALESCE(SUM(CASE WHEN (o.is_goujinjin = FALSE AND o.is_refund = FALSE) THEN o.actual_amount ELSE 0 END), 0) as gsv,
                COUNT(DISTINCT CASE WHEN o.is_member = TRUE THEN o.user_id END) as member_user_count,
                COALESCE(SUM(CASE WHEN o.is_member = TRUE AND (o.is_goujinjin = FALSE AND o.is_refund = FALSE) THEN o.actual_amount ELSE 0 END), 0) as member_gsv
            FROM orders o
            LEFT JOIN user_first_purchase ufp ON o.user_id = ufp.user_id
            WHERE o.pay_time IS NOT NULL AND DATE(o.pay_time) IN (SELECT unnest(?))
            GROUP BY DATE(o.pay_time)
        """, [date_list])
    else:
        conn.execute("""
            INSERT INTO daily_metrics
            SELECT
                DATE(pay_time) as d,
                COUNT(DISTINCT order_id) as order_count,
                COUNT(DISTINCT user_id) as user_count,
                COALESCE(SUM(CASE WHEN (is_goujinjin = FALSE AND is_refund = FALSE) THEN actual_amount ELSE 0 END), 0) as gsv,
                COUNT(DISTINCT CASE WHEN is_member = TRUE THEN user_id END) as member_user_count,
                COALESCE(SUM(CASE WHEN is_member = TRUE AND (is_goujinjin = FALSE AND is_refund = FALSE) THEN actual_amount ELSE 0 END), 0) as member_gsv
            FROM orders
            WHERE pay_time IS NOT NULL AND DATE(pay_time) IN (SELECT unnest(?))
            GROUP BY DATE(pay_time)
        """, [date_list])

    print(f"  已更新 {len(date_list)} 个日期的指标")
    conn.close()


def _build_user_first_purchase_table(mode: str = 'full', window_days: int = 30,
                                      new_df=None, refresh_df=None):
    """
    构建 user_first_purchase 表（滑动窗口模式）。

    全量模式  : DROP 后全量重建
    增量模式  :
      1. 窗口内用户：DELETE 后重新计算（状态变化可能影响首购日期）
      2. 全新用户：INSERT 不在表中的用户
    """
    print("\n维护 user_first_purchase 表...")

    conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": DUCKDB_MEMORY_LIMIT})

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
        existing_tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
        if 'user_first_purchase' not in existing_tables:
            conn.execute("""
                CREATE TABLE user_first_purchase (
                    user_id     VARCHAR PRIMARY KEY,
                    first_pay_date DATE
                )
            """)

        # O2 优化: 只处理新/刷新订单涉及的用户，而非整个窗口
        affected_user_ids = set()
        if new_df is not None and not new_df.empty and 'user_id' in new_df.columns:
            affected_user_ids.update(new_df['user_id'].dropna().astype(str).unique())
        if refresh_df is not None and not refresh_df.empty and 'user_id' in refresh_df.columns:
            affected_user_ids.update(refresh_df['user_id'].dropna().astype(str).unique())
        # 过滤空值
        affected_user_ids.discard('')
        affected_user_ids.discard('nan')
        affected_user_ids.discard('None')

        if affected_user_ids:
            # 1. 只删除受影响的用户
            id_list = sorted(affected_user_ids)
            batch_size = 10000
            for i in range(0, len(id_list), batch_size):
                batch = id_list[i:i+batch_size]
                placeholders = ','.join(['?' for _ in batch])
                conn.execute(f"""
                    DELETE FROM user_first_purchase
                    WHERE user_id IN ({placeholders})
                """, batch)

            # 2. 重新计算受影响用户的 first_pay_date（全历史，不只是窗口内）
            for i in range(0, len(id_list), batch_size):
                batch = id_list[i:i+batch_size]
                placeholders = ','.join(['?' for _ in batch])
                conn.execute(f"""
                    INSERT INTO user_first_purchase
                    SELECT user_id, MIN(DATE(pay_time)) AS first_pay_date
                    FROM orders
                    WHERE pay_time IS NOT NULL
                      AND is_goujinjin = FALSE
                      AND is_refund = FALSE
                      AND user_id IS NOT NULL
                      AND user_id != ''
                      AND user_id IN ({placeholders})
                    GROUP BY user_id
                """, batch)
            print(f"  user_first_purchase 增量更新: {len(affected_user_ids):,} 个受影响用户")
        else:
            print("  user_first_purchase: 无受影响用户，跳过")

        count = conn.execute("SELECT COUNT(*) FROM user_first_purchase").fetchone()[0]
        print(f"  user_first_purchase 增量更新: 当前合计 {count:,} 用户")

    conn.close()

def _build_user_recency_table(mode: str = 'full', window_days: int = 30,
                               new_df=None, refresh_df=None):
    """构建 user_recency 表（全量/增量），用于 RFM flow 查询加速。"""
    print("\n维护 user_recency 表...")
    conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": DUCKDB_MEMORY_LIMIT})
    _VB = "is_goujinjin = FALSE AND order_status != '交易关闭'"
    if mode == 'full':
        conn.execute("DROP TABLE IF EXISTS user_recency")
        conn.execute("CREATE TABLE user_recency (user_id VARCHAR PRIMARY KEY, last_pay_time TIMESTAMP, is_member BOOLEAN DEFAULT FALSE, recency_days INTEGER, total_orders INTEGER DEFAULT 0, total_amount DECIMAL(14,2) DEFAULT 0)")
        conn.execute(f"INSERT INTO user_recency SELECT user_id, MAX(pay_time), MAX(CASE WHEN is_member THEN TRUE ELSE FALSE END), DATEDIFF('day', MAX(pay_time), CURRENT_DATE), COUNT(*), SUM(actual_amount) FROM orders WHERE {_VB} AND user_id IS NOT NULL AND user_id != '' GROUP BY user_id")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ur_recency ON user_recency(recency_days)")
        cnt = conn.execute("SELECT COUNT(*) FROM user_recency").fetchone()[0]
        print(f"  user_recency 全量重建: {cnt:,} 用户")
    else:
        # O3 优化: 只处理新/刷新订单涉及的用户，而非整个窗口
        affected_user_ids = set()
        if new_df is not None and not new_df.empty and 'user_id' in new_df.columns:
            affected_user_ids.update(new_df['user_id'].dropna().astype(str).unique())
        if refresh_df is not None and not refresh_df.empty and 'user_id' in refresh_df.columns:
            affected_user_ids.update(refresh_df['user_id'].dropna().astype(str).unique())
        affected_user_ids.discard('')
        affected_user_ids.discard('nan')
        affected_user_ids.discard('None')

        if 'user_recency' not in [t[0] for t in conn.execute("SHOW TABLES").fetchall()]:
            conn.execute("CREATE TABLE user_recency (user_id VARCHAR PRIMARY KEY, last_pay_time TIMESTAMP, is_member BOOLEAN DEFAULT FALSE, recency_days INTEGER, total_orders INTEGER DEFAULT 0, total_amount DECIMAL(14,2) DEFAULT 0)")

        if affected_user_ids:
            id_list = sorted(affected_user_ids)
            batch_size = 10000
            # 1. 只删除受影响的用户
            for i in range(0, len(id_list), batch_size):
                batch = id_list[i:i+batch_size]
                placeholders = ','.join(['?' for _ in batch])
                conn.execute(f"DELETE FROM user_recency WHERE user_id IN ({placeholders})", batch)

            # 2. 重新计算受影响用户的 recency（全历史聚合）
            for i in range(0, len(id_list), batch_size):
                batch = id_list[i:i+batch_size]
                placeholders = ','.join(['?' for _ in batch])
                conn.execute(f"""
                    INSERT INTO user_recency
                    SELECT user_id, MAX(pay_time),
                           MAX(CASE WHEN is_member THEN TRUE ELSE FALSE END),
                           DATEDIFF('day', MAX(pay_time), CURRENT_DATE),
                           COUNT(*), SUM(actual_amount)
                    FROM orders
                    WHERE {_VB} AND user_id IS NOT NULL AND user_id != ''
                      AND user_id IN ({placeholders})
                    GROUP BY user_id
                """, batch)
            print(f"  user_recency 增量更新: {len(affected_user_ids):,} 个受影响用户")
        else:
            print("  user_recency: 无受影响用户，跳过")

        cnt = conn.execute("SELECT COUNT(*) FROM user_recency").fetchone()[0]
        print(f"  user_recency 增量更新: 当前合计 {cnt:,} 用户")
    conn.close()

def update_taoke_channel():
    """
    全量纠正淘客渠道标记（完整重建，非增量）。

    策略：仅将当前标为'淘客'的订单重置为'其他'，再重新应用 P6(订单号) / P6-2(关键词) 规则。
    这样当淘客数据库变更或关键词规则变化时，历史订单能自动纠正。

    保护渠道（不受影响）：U先派样、百补派样、赠品&0.01渠道、直播、货架、达播、微博、购物金

    Sprint 21 P0 治标: 加 retry 3 次 (Sprint 20+ 验证: DuckDB 1.5.x ART index 跨 connection
    race 是概率性触发, 1.88M UPDATE 触发率 ~100%, retry 3 次能把概率降到 ~0).
    - retry 1: 失败 → 等 1s → 重开新 conn → 重试
    - retry 2: 失败 → 等 1s → 重开新 conn → 重试
    - retry 3: 失败 → 等 1s → 重开新 conn → 重试
    - 3 次都失败 → raise
    """
    import time as _time
    _MAX_RETRIES = 3
    # QW4 埋点：step2 update_taoke_channel 的内部计时 (含 retry 全部 3 次)
    with PerfTimer("pl_taoke_full_correct"):
        for _attempt in range(1, _MAX_RETRIES + 1):
            try:
                _update_taoke_channel_impl()
                if _attempt > 1:
                    print(f"  [Sprint 21 P0 retry] 第 {_attempt}/{_MAX_RETRIES} 次尝试成功 (race 触发后重试恢复)")
                return
            except Exception as _e:
                _err_name = type(_e).__name__
                _err_msg = str(_e)[:200].replace("\n", " ")
                if _attempt < _MAX_RETRIES:
                    print(f"  [Sprint 21 P0 retry] 第 {_attempt}/{_MAX_RETRIES} 次失败: {_err_name}: {_err_msg}")
                    print("  [Sprint 21 P0 retry] 等 1s, 重开新 conn 重试...")
                    _time.sleep(1)
                else:
                    print(f"  [Sprint 21 P0 retry] {_attempt}/{_MAX_RETRIES} 次都失败, raise")
                    raise


def _update_taoke_channel_impl():
    print("\n" + "=" * 60)
    print("淘客渠道全量纠正")
    print("=" * 60)

    taoke_ids = load_taoke_order_ids()

    conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": DUCKDB_MEMORY_LIMIT})

    # Sprint 16 P0 治根: 跟 Sprint 10 B2-merged (99c0196) 同路 — DuckDB 1.5.x ART index
    # 内部 vector 类型推断 race, 触发 'Vector::Reference used on vector of different
    # type (source VARCHAR referenced TIMESTAMP)' 错误. 修法: 包 BEGIN/COMMIT, DROP
    # 2 个 channel 相关 secondary index, UPDATE 跟 SELECT 走 heap (无 index 触发 race),
    # 重建 index, COMMIT. 跟 Sprint 10 fix (replay_is_member.py DROP 6 indexes) 同一模式,
    # 治标: 1.5.x ART index 本身; 治本: 升级 DuckDB 1.5.3+ (requirements-lock.txt:18 已 1.5.3,
    # 但 1.5.2 积压的 index state 残留在 file 里, 1.5.3 也触发, 需要 DROP 重建清状态).
    # Sprint 10 fix 修了 replay_is_member 但漏修 _update_taoke_channel_impl, 这就是
    # Sprint 16 P0 治根目标.
    # Sprint 21 P0 治根 (1.88M 增量 ETL race "Failed to delete 0 out of 2048 rows"):
    # 跟 Sprint 10 B2-merged (99c0196) + Sprint 15 D.1 (replay_is_member.py) 模式完全对齐 —
    # DROP 全部 6 个 secondary indexes (不只 2 个 channel 相关的), UPDATE 1.88M 走 heap
    # (无任何 index 竞争), CREATE 6 重建. Sprint 16 P0 v2 fix (1.5.4.dev18 治根) 漏修
    # 4 个 (idx_orders_pay_time / idx_orders_user / idx_orders_year_month / idx_orders_product),
    # 只 DROP 2 channel 相关, 1.88M 触发跨 index race 在 COMMIT 段 (CREATE INDEX 重建时).
    _CHANNEL_INDEXES = [
        "idx_orders_pay_time",
        "idx_orders_user",
        "idx_orders_year_month",
        "idx_orders_product",
        "idx_orders_channel_pay_time",
        "idx_orders_channel_member",
    ]
    _CHANNEL_INDEX_RECREATE = [
        "CREATE INDEX idx_orders_pay_time ON orders(pay_time)",
        "CREATE INDEX idx_orders_user ON orders(user_id)",
        'CREATE INDEX idx_orders_year_month ON orders("year", "month")',
        "CREATE INDEX idx_orders_product ON orders(product_id)",
        "CREATE INDEX idx_orders_channel_pay_time ON orders(channel, pay_time)",
        "CREATE INDEX idx_orders_channel_member ON orders(channel, is_member)",
    ]
    try:
        # Sprint 16 P0 治根 (v2): 加 CHECKPOINT 前置, 强制 WAL 落盘, 清 1.5.x
        # 升级积压的 stale index state. 之前 v1 跑出来新 race: 'Failed to delete
        # all rows from index. Only deleted 0 out of 2048 rows' (DROP INDEX 删不掉
        # 残留 2048 行 ART metadata). 修法: CHECKPOINT 强制 buffer 落盘, 然后
        # DROP INDEX 干净.
        try:
            conn.execute("CHECKPOINT")
        except Exception as _e:
            print(f"  [WARN] CHECKPOINT skip: {_e}")
        conn.execute("BEGIN")
        # 1. DROP channel 相关 index (race 触发点, channel 字段 VARCHAR 跟 index metadata 类型错乱)
        for idx in _CHANNEL_INDEXES:
            try:
                conn.execute(f"DROP INDEX IF EXISTS {idx}")
            except Exception as _e:
                print(f"  [WARN] DROP {idx} skip: {_e}")
        # 2. 跟 Sprint 10 fix 一样, 单事务保证 atomicity
        before = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE channel = '淘客'"
        ).fetchone()[0]
        print("纠正前淘客订单: " + str(before) + " 条")

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

        # 3. 重建 2 个 channel index (跟 Sprint 10 fix 同一模式, 跑批后立刻重建给下游 query 加速)
        for sql in _CHANNEL_INDEX_RECREATE:
            try:
                conn.execute(sql)
            except Exception as _e:
                print(f"  [WARN] CREATE INDEX skip: {_e}")
        # 4. COMMIT 整个 DROP+UPDATE+RECREATE 序列 (D.1 atomicity 一致)
        conn.execute("COMMIT")
        print("  [Sprint 16 P0 治根] 事务 COMMIT: DROP 2 index → UPDATE 3 步 → RECREATE 2 index 全部落盘")
    except Exception:
        # Sprint 16 P0 治根: 中途 crash 自动 ROLLBACK, 跟 D.1 replay_is_member.py:90-152 一致
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        # 不管成功失败, 都尝试清 TEMP TABLE (跟原来 finally 一致)
        try:
            conn.execute("DROP TABLE IF EXISTS _taoke_ids")
        except Exception:
            pass
        conn.close()


def refresh_visitor_data():
    """
    增量刷新 daily_visitors 表（访客数/新增会员数）。

    策略：
      1. 扫描店铺流量数据库目录下的最新 xlsx 文件
      2. 比对 daily_visitors 表最新日期，只写入新数据
      3. xlsx 结构：日期 / 访客数 / 新增会员数
    """
    with PerfTimer("pl_refresh_visitor_data"):
        _refresh_visitor_data_impl()


def _refresh_visitor_data_impl():
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
        print("  目录中无 xlsx 文件")
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

    conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": DUCKDB_MEMORY_LIMIT})
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
    with PerfTimer("pl_refresh_campaign_schedule"):
        _refresh_campaign_schedule_impl()


def _refresh_campaign_schedule_impl():
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

    conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": DUCKDB_MEMORY_LIMIT})
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
