"""ETL DuckDB 写入
数据库初始化、表创建、索引、数据写入/upsert。
"""
import functools
import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.etl.config import DUCKDB_PATH, DUCKDB_MEMORY_LIMIT, PROCESSED_DATA_DIR

import pandas as pd
import duckdb

# QW4 埋点：load 步骤内部计时
try:
    from scripts.etl._timer import PerfTimer  # noqa: F401
except ImportError:  # perf.py 不在路径时降级为 no-op
    class PerfTimer:  # type: ignore[no-redef]
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

def init_database():
    """初始化数据库表结构"""
    print("初始化数据库...")

    conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": DUCKDB_MEMORY_LIMIT})

    # 删除旧表并重建
    conn.execute("DROP TABLE IF EXISTS orders")
    conn.execute("DROP TABLE IF EXISTS daily_metrics")
    conn.execute("DROP TABLE IF EXISTS monthly_metrics")
    conn.execute("DROP TABLE IF EXISTS spu_mapping")
    conn.execute("DROP TABLE IF EXISTS user_summary")

    # 创建订单表
    conn.execute("""
        CREATE TABLE orders (
            order_id VARCHAR,
            sub_order_id VARCHAR,
            user_id VARCHAR,
            user_nickname VARCHAR,
            order_time TIMESTAMP,
            pay_time TIMESTAMP,
            ship_time TIMESTAMP,
            order_type VARCHAR,
            order_status VARCHAR,
            product_id VARCHAR,
            merchant_code VARCHAR,
            product_title VARCHAR,
            sku_id VARCHAR,
            sku_code VARCHAR,
            sku_name VARCHAR,
            quantity INTEGER,
            amount DECIMAL(12,2),
            refund_status VARCHAR,
            refund_amount DECIMAL(12,2),
            actual_amount DECIMAL(12,2),
            province VARCHAR,
            city VARCHAR,
            influencer_name VARCHAR,
            influencer_id VARCHAR,
            live_room_id VARCHAR,
            video_id VARCHAR,
            traffic_source VARCHAR,
            traffic_type VARCHAR,
            seller_note VARCHAR,
            year INTEGER,
            month INTEGER,
            is_member BOOLEAN,
            spu_category VARCHAR,
            spu_type VARCHAR,
            spu_tier VARCHAR,
            spu_product_class VARCHAR,
            spu_product_subclass VARCHAR,
            spu_cosmetic VARCHAR,
            spu_spec VARCHAR,
            spu_hash VARCHAR,
            channel VARCHAR,
            is_goujinjin BOOLEAN DEFAULT FALSE,
            is_refund BOOLEAN DEFAULT FALSE
        )
    """)

    # 创建每日指标表
    conn.execute("""
        CREATE TABLE daily_metrics (
            date DATE PRIMARY KEY,
            gmv DECIMAL(14,2),
            gsv DECIMAL(14,2),
            order_count INTEGER,
            gsv_order_count INTEGER,
            new_user_count INTEGER,
            old_user_count INTEGER,
            member_gmv DECIMAL(14,2),
            member_gsv DECIMAL(14,2),
            member_count INTEGER,
            avg_order_value DECIMAL(10,2),
            new_user_gmv DECIMAL(14,2),
            old_user_gmv DECIMAL(14,2)
        )
    """)

    # 创建唯一索引：防止重复订单
    conn.execute("CREATE UNIQUE INDEX idx_orders_order_unique ON orders(order_id, sub_order_id)")

    conn.close()
    print("  数据库初始化完成")


def write_to_duckdb(df):
    """写入 DuckDB"""
    print(f"\n写入 DuckDB: {len(df)} 行")

    conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": DUCKDB_MEMORY_LIMIT})

    # 数据库表的所有列（按顺序）
    table_columns = [
        'order_id', 'sub_order_id', 'user_id', 'user_nickname',
        'order_time', 'pay_time', 'ship_time', 'order_type', 'order_status',
        'product_id', 'merchant_code', 'product_title', 'sku_id', 'sku_code',
        'sku_name', 'quantity', 'amount', 'refund_status', 'refund_amount',
        'actual_amount', 'province', 'city', 'influencer_name', 'influencer_id',
        'live_room_id', 'video_id', 'traffic_source', 'traffic_type',
        'seller_note', 'year', 'month', 'is_member', 'spu_category',
        'spu_type', 'spu_tier', 'spu_product_class', 'spu_product_subclass',
        'spu_cosmetic', 'spu_spec', 'spu_hash', 'channel',
        'is_goujinjin', 'is_refund'
    ]

    # 只保留存在的列，并按数据库表顺序排列
    existing_cols = [c for c in table_columns if c in df.columns]
    df_insert = df[existing_cols].copy()

    # 使用 DuckDB 的 COPY FROM parquet 方式
    # 先写入 parquet 文件，再 COPY 导入
    import os

    parquet_path = os.path.join(tempfile.gettempdir(), 'orders_temp.parquet')
    df_insert.to_parquet(parquet_path, index=False)

    cols_joined = ', '.join(existing_cols)
    conn.execute(f"COPY orders ({cols_joined}) FROM '{parquet_path}' (FORMAT PARQUET)")

    os.remove(parquet_path)

    count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    print(f"  写入完成，当前订单总数: {count:,}")

    conn.close()


# 注：calculate_daily_metrics 死代码已删除（74 行）
# 该函数 grep 全仓 0 调用方，pipeline.py Step 6.7 已用 _rebuild_metrics
# 和 _update_incremental_metrics 替代（两者均含 LEFT JOIN user_first_purchase
# 逻辑）。task #59 P1 修复在此处的改动属于无效改动（改死代码），本次清理删除。


@functools.lru_cache(maxsize=1)
def get_db_max_pay_time():
    """
    获取数据库中已有订单的最大付款时间。
    结果缓存：进程内多次调用只查一次数据库。
    """
    if not DUCKDB_PATH.exists():
        return None
    try:
        conn = duckdb.connect(str(DUCKDB_PATH), read_only=True, config={"memory_limit": DUCKDB_MEMORY_LIMIT})
        result = conn.execute("SELECT MAX(pay_time) FROM orders").fetchone()[0]
        conn.close()
        return result
    except Exception as e:
        print(f"  [警告] 读取数据库最大付款时间失败: {e}，将执行全量")
        return None


def ensure_database_schema():
    """确保数据库表结构存在（不删除数据）"""
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": DUCKDB_MEMORY_LIMIT})

    # 检查 orders 表是否存在
    tables = conn.execute("SHOW TABLES").fetchall()
    table_names = [t[0] for t in tables]

    if 'orders' not in table_names:
        # 表不存在，创建完整结构
        _create_orders_table(conn)
        _create_indexes(conn)
        _create_metrics_tables(conn)
        conn.close()
        return False  # 新建表，全量导入

    conn.close()
    return True  # 表已存在，增量模式


def _create_orders_table(conn):
    """创建订单表"""
    conn.execute("""
        CREATE TABLE orders (
            order_id VARCHAR,
            sub_order_id VARCHAR,
            user_id VARCHAR,
            user_nickname VARCHAR,
            order_time TIMESTAMP,
            pay_time TIMESTAMP,
            ship_time TIMESTAMP,
            order_type VARCHAR,
            order_status VARCHAR,
            product_id VARCHAR,
            merchant_code VARCHAR,
            product_title VARCHAR,
            sku_id VARCHAR,
            sku_code VARCHAR,
            sku_name VARCHAR,
            quantity INTEGER,
            amount DECIMAL(12,2),
            refund_status VARCHAR,
            refund_amount DECIMAL(12,2),
            actual_amount DECIMAL(12,2),
            province VARCHAR,
            city VARCHAR,
            influencer_name VARCHAR,
            influencer_id VARCHAR,
            live_room_id VARCHAR,
            video_id VARCHAR,
            traffic_source VARCHAR,
            traffic_type VARCHAR,
            seller_note VARCHAR,
            year INTEGER,
            month INTEGER,
            is_member BOOLEAN,
            spu_category VARCHAR,
            spu_type VARCHAR,
            spu_tier VARCHAR,
            spu_product_class VARCHAR,
            spu_product_subclass VARCHAR,
            spu_cosmetic VARCHAR,
            spu_spec VARCHAR,
            spu_hash VARCHAR,
            channel VARCHAR,
            is_goujinjin BOOLEAN DEFAULT FALSE,
            is_refund BOOLEAN DEFAULT FALSE
        )
    """)


def _create_indexes(conn):
    """创建索引"""
    conn.execute("CREATE INDEX idx_orders_pay_time ON orders(pay_time)")
    conn.execute("CREATE INDEX idx_orders_user ON orders(user_id)")
    conn.execute("CREATE INDEX idx_orders_year_month ON orders(year, month)")
    conn.execute("CREATE INDEX idx_orders_product ON orders(product_id)")
    conn.execute("CREATE UNIQUE INDEX idx_orders_order_unique ON orders(order_id, sub_order_id)")
    # 人群看板复合索引（渠道×付款时间 + 渠道×会员）
    conn.execute("CREATE INDEX idx_orders_channel_pay_time ON orders(channel, pay_time)")
    conn.execute("CREATE INDEX idx_orders_channel_member ON orders(channel, is_member)")


def _create_orders_table_custom(conn, table_name="orders"):
    """创建订单表（支持自定义表名，用于 temp-table swap）"""
    conn.execute(f"""
        CREATE TABLE {table_name} (
            order_id VARCHAR,
            sub_order_id VARCHAR,
            user_id VARCHAR,
            user_nickname VARCHAR,
            order_time TIMESTAMP,
            pay_time TIMESTAMP,
            ship_time TIMESTAMP,
            order_type VARCHAR,
            order_status VARCHAR,
            product_id VARCHAR,
            merchant_code VARCHAR,
            product_title VARCHAR,
            sku_id VARCHAR,
            sku_code VARCHAR,
            sku_name VARCHAR,
            quantity INTEGER,
            amount DECIMAL(12,2),
            refund_status VARCHAR,
            refund_amount DECIMAL(12,2),
            actual_amount DECIMAL(12,2),
            province VARCHAR,
            city VARCHAR,
            influencer_name VARCHAR,
            influencer_id VARCHAR,
            live_room_id VARCHAR,
            video_id VARCHAR,
            traffic_source VARCHAR,
            traffic_type VARCHAR,
            seller_note VARCHAR,
            year INTEGER,
            month INTEGER,
            is_member BOOLEAN,
            spu_category VARCHAR,
            spu_type VARCHAR,
            spu_tier VARCHAR,
            spu_product_class VARCHAR,
            spu_product_subclass VARCHAR,
            spu_cosmetic VARCHAR,
            spu_spec VARCHAR,
            spu_hash VARCHAR,
            channel VARCHAR,
            is_goujinjin BOOLEAN DEFAULT FALSE,
            is_refund BOOLEAN DEFAULT FALSE
        )
    """)


def _create_indexes_custom(conn, table_name="orders"):
    """创建索引（支持自定义表名）"""
    conn.execute(f"CREATE INDEX idx_{table_name}_pay_time ON {table_name}(pay_time)")
    conn.execute(f"CREATE INDEX idx_{table_name}_user ON {table_name}(user_id)")
    conn.execute(f"CREATE INDEX idx_{table_name}_year_month ON {table_name}(\"year\", \"month\")")
    conn.execute(f"CREATE INDEX idx_{table_name}_product ON {table_name}(product_id)")
    conn.execute(f"CREATE UNIQUE INDEX idx_{table_name}_order_unique ON {table_name}(order_id, sub_order_id)")
    conn.execute(f"CREATE INDEX idx_{table_name}_channel_pay ON {table_name}(channel, pay_time)")
    conn.execute(f"CREATE INDEX idx_{table_name}_channel_member ON {table_name}(channel, is_member)")


def _create_metrics_tables(conn):
    """创建指标表"""
    conn.execute("""
        CREATE TABLE daily_metrics (
            date DATE PRIMARY KEY,
            gmv DECIMAL(14,2),
            gsv DECIMAL(14,2),
            order_count INTEGER,
            gsv_order_count INTEGER,
            new_user_count INTEGER,
            old_user_count INTEGER,
            member_gmv DECIMAL(14,2),
            member_gsv DECIMAL(14,2),
            member_count INTEGER,
            avg_order_value DECIMAL(10,2),
            new_user_gmv DECIMAL(14,2),
            old_user_gmv DECIMAL(14,2)
        )
    """)
    conn.execute("""
        CREATE TABLE monthly_metrics (
            year INTEGER,
            month INTEGER,
            gmv DECIMAL(12,2),
            gsv DECIMAL(12,2),
            order_count INTEGER,
            gsv_order_count INTEGER,
            new_user_count INTEGER,
            old_user_count INTEGER,
            member_gmv DECIMAL(12,2),
            member_gsv DECIMAL(12,2),
            avg_order_value DECIMAL(10,2),
            PRIMARY KEY (year, month)
        )
    """)


def filter_rolling_window(df, max_pay_time, window_days=30):
    """
    滑动窗口数据过滤（解决订单状态30天内滚动变化问题）：
      1. 全新订单：pay_time > max_pay_time → 追加 INSERT
      2. 窗口内刷新：pay_time >= 今天-window_days 且 <= max_pay_time → DELETE+INSERT

    返回: (new_df, refresh_df)
    """
    # QW4 埋点：filter_rolling_window 整体入口
    _frw_timer = PerfTimer("load_filter_rolling_window", input_rows=len(df), window_days=window_days)
    _frw_timer.__enter__()
    try:
        return _filter_rolling_window_body(df, max_pay_time, window_days, _frw_timer)
    finally:
        _frw_timer.__exit__(None, None, None)


def _filter_rolling_window_body(df, max_pay_time, window_days, _timer):
    """filter_rolling_window 实际实现（被外层 QW4 埋点包裹）"""
    if max_pay_time is None:
        return df.copy(), pd.DataFrame()

    if 'pay_time' in df.columns:
        if not pd.api.types.is_datetime64_any_dtype(df['pay_time']):
            df['pay_time'] = pd.to_datetime(df['pay_time'], errors='coerce')

    today = pd.Timestamp.now().normalize()
    window_start = today - pd.Timedelta(days=window_days)

    new_mask = df['pay_time'] > max_pay_time
    new_df = df[new_mask].copy()

    refresh_mask = (
        (df['pay_time'] >= window_start) &
        (df['pay_time'] <= max_pay_time)
    )
    refresh_df = df[refresh_mask].copy()

    stale_count = len(df) - new_mask.sum() - refresh_mask.sum()
    print(f"  滑动窗口过滤 (窗口={window_days}天):")
    print(f"    全新订单:     {len(new_df):,} 行")
    print(f"    窗口内刷新:   {len(refresh_df):,} 行 ({window_start.date()} ~ {max_pay_time.date()})")
    print(f"    剔除旧数据:   {stale_count:,} 行 (窗口外且已存在)")
    return new_df, refresh_df


def upsert_to_duckdb(df_new, df_refresh, mode='incremental', window_days=30):
    """
    写入 DuckDB（滑动窗口模式）：
      - 全量模式：重建表
      - 增量模式：全新订单追加 + 窗口内订单 DELETE+INSERT 刷新
    """
    total_new = len(df_new)
    total_refresh = len(df_refresh)
    print(f"\n写入 DuckDB: {total_new + total_refresh:,} 行 (全新:{total_new:,} 刷新:{total_refresh:,})")

    # QW4 埋点：upsert_to_duckdb 整体入口（手写 enter/exit 避免大段重缩进）
    _upsert_timer = PerfTimer(
        "load_upsert_to_duckdb",
        mode=mode, new_rows=total_new, refresh_rows=total_refresh,
    )
    _upsert_timer.__enter__()
    try:
        return _upsert_to_duckdb_body(df_new, df_refresh, mode, window_days,
                                      total_new, total_refresh, _upsert_timer)
    finally:
        _upsert_timer.__exit__(None, None, None)


def _upsert_to_duckdb_body(df_new, df_refresh, mode, window_days,
                            total_new, total_refresh, _timer):
    """upsert_to_duckdb 实际实现（被外层 QW4 埋点包裹）"""
    conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": DUCKDB_MEMORY_LIMIT})

    table_columns = [
        'order_id', 'sub_order_id', 'user_id', 'user_nickname',
        'order_time', 'pay_time', 'ship_time', 'order_type', 'order_status',
        'product_id', 'merchant_code', 'product_title', 'sku_id', 'sku_code',
        'sku_name', 'quantity', 'amount', 'refund_status', 'refund_amount',
        'actual_amount', 'province', 'city', 'influencer_name', 'influencer_id',
        'live_room_id', 'video_id', 'traffic_source', 'traffic_type',
        'seller_note', 'year', 'month', 'is_member', 'spu_category',
        'spu_type', 'spu_tier', 'spu_product_class', 'spu_product_subclass',
        'spu_cosmetic', 'spu_spec', 'spu_hash', 'channel',
        'is_goujinjin', 'is_refund'
    ]

    existing_cols = [c for c in table_columns if c in df_new.columns or c in df_refresh.columns]

    try:
        if mode == 'full':
            # 全量模式：temp-table swap（原子替换，避免 DROP 后 LOAD 失败导致数据丢失）
            all_df = pd.concat([df_new, df_refresh], ignore_index=True) if total_refresh > 0 else df_new
            df_insert = all_df[existing_cols].copy()
            parquet_path = os.path.join(tempfile.gettempdir(), 'orders_temp.parquet')
            df_insert.to_parquet(parquet_path, index=False)

            # Step 1: 用新表结构创建 orders_new
            conn.execute("DROP TABLE IF EXISTS orders_new")
            _create_orders_table_custom(conn, "orders_new")
            _create_indexes_custom(conn, "orders_new")
            cols_joined = ', '.join(existing_cols)
            conn.execute(f"COPY orders_new ({cols_joined}) FROM '{parquet_path}' (FORMAT PARQUET)")
            os.remove(parquet_path)

            # Step 2: 原子 swap（DuckDB 不支持事务性 DDL，但两步之间 crash 时 orders 仍完整）
            before_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            conn.execute("DROP TABLE IF EXISTS orders")
            conn.execute("ALTER TABLE orders_new RENAME TO orders")
            after_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            print(f"  ✅ 全量刷新: {before_count:,} → {after_count:,}")
        else:
            # ── 全新订单：追加（staging 表 + ON CONFLICT DO NOTHING）──
            if total_new > 0:
                df_insert = df_new[existing_cols].copy()
                for _col in ['order_id', 'sub_order_id']:
                    if _col in df_insert.columns:
                        df_insert[_col] = df_insert[_col].astype(str).replace('nan', '').replace('None', '')
                df_insert = df_insert.drop_duplicates(subset=['order_id', 'sub_order_id'], keep='last')
                copied = _copy_df_to_duckdb(df_insert, conn, existing_cols)
                print(f"  ✅ 全新订单: {copied:,} 行")

            # ── 窗口内订单：精确键值 DELETE + INSERT 刷新 ──
            if total_refresh > 0:
                import uuid as _uuid

                before_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]

                # 1. 将 df_refresh 的 order_id 写入临时表
                tmp_table = f"_refresh_ids_{_uuid.uuid4().hex[:8]}"
                refresh_ids = df_refresh[['order_id']].drop_duplicates()
                refresh_ids['order_id'] = refresh_ids['order_id'].astype(str).replace('nan', '').replace('None', '')
                ids_parquet = os.path.join(tempfile.gettempdir(), f'{tmp_table}.parquet')
                refresh_ids.to_parquet(ids_parquet, index=False)

                conn.execute(f"CREATE TEMP TABLE {tmp_table} (order_id VARCHAR)")
                conn.execute(f"COPY {tmp_table} FROM '{ids_parquet}' (FORMAT PARQUET)")
                os.remove(ids_parquet)

                # 2. tx1: DELETE + COMMIT (D-4 教训深二: DuckDB 1.5.2 UNIQUE INDEX 在同
                #    一 transaction 内 INSERT 时不感知本事务内未提交的 DELETE. 拆 2 tx 解决)
                conn.execute("BEGIN TRANSACTION")
                try:
                    conn.execute(f"""
                        DELETE FROM orders
                        WHERE order_id IN (SELECT order_id FROM {tmp_table})
                    """)
                    conn.execute("COMMIT")  # 立即 COMMIT, 让 UNIQUE INDEX 看到 DELETE
                except Exception:
                    conn.execute("ROLLBACK")
                    raise

                after_delete = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
                deleted = before_count - after_delete
                print(f"  🗑️  精确删除待刷新记录: {deleted:,} 行 ({len(refresh_ids):,} 个 order_id)")

                conn.execute(f"DROP TABLE IF EXISTS {tmp_table}")

                # 3. 去重：同一个 (order_id, sub_order_id) 保留最后一行
                # ID列统一转字符串后再去重，防止类型不一致（float vs string）导致去重失败
                for _col in ['order_id', 'sub_order_id']:
                    if _col in df_refresh.columns:
                        df_refresh[_col] = df_refresh[_col].astype(str).replace('nan', '').replace('None', '')
                df_refresh = df_refresh.drop_duplicates(
                    subset=['order_id', 'sub_order_id'], keep='last'
                )
                total_refresh_deduped = len(df_refresh)
                if total_refresh_deduped < total_refresh:
                    print(f"  ⚠️  去重: {total_refresh} → {total_refresh_deduped} 行")

                # 4. 插入刷新数据：staging 表（无 UNIQUE INDEX） + COPY 防主键冲突
                df_insert = df_refresh[existing_cols].copy()
                import uuid as _uuid_refresh
                tmp_stage = f"_stage_refresh_{_uuid_refresh.uuid4().hex[:8]}"
                parquet_path = os.path.join(tempfile.gettempdir(), 'orders_refresh.parquet')
                df_insert.to_parquet(parquet_path, index=False)
                cols_joined = ', '.join(existing_cols)

                # 5. tx2: 单独 tx 写 staging + INSERT NOT EXISTS
                #    (跟 tx1 DELETE+COMMIT 分开, UNIQUE INDEX 已看到 DELETE 提交)
                conn.execute("BEGIN TRANSACTION")
                try:
                    conn.execute(f"CREATE TEMP TABLE {tmp_stage} AS SELECT * FROM orders WHERE 1=0")
                    conn.execute(f"COPY {tmp_stage} ({cols_joined}) FROM '{parquet_path}' (FORMAT PARQUET)")
                    os.remove(parquet_path)
                    conn.execute(f"""
                        INSERT INTO orders ({cols_joined})
                        SELECT {cols_joined} FROM (
                            SELECT *, ROW_NUMBER() OVER (
                                PARTITION BY order_id, sub_order_id ORDER BY pay_time DESC
                            ) AS _rn FROM {tmp_stage}
                        ) t WHERE t._rn = 1
                        AND NOT EXISTS (
                            SELECT 1 FROM orders o
                            WHERE o.order_id = t.order_id AND o.sub_order_id = t.sub_order_id
                        )
                    """)
                    inserted = conn.execute(f"SELECT COUNT(*) FROM {tmp_stage}").fetchone()[0]
                    conn.execute(f"DROP TABLE IF EXISTS {tmp_stage}")
                    print(f"  ✅ 窗口刷新: {inserted:,} 行")

                    conn.execute("COMMIT")
                except Exception:
                    conn.execute("ROLLBACK")
                    raise

                # 4. 数据守恒断言：刷新不应导致总数净减少（允许少量因退款状态变化的合理差异）
                after_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
                net_change = after_count - before_count
                if net_change < -100:
                    raise AssertionError(
                        f"数据守恒异常: 刷新前 {before_count:,} → 刷新后 {after_count:,}，"
                        f"净减少 {abs(net_change):,} 行，超过阈值 100。可能有数据丢失！"
                    )
                print(f"  🔍 数据守恒: {before_count:,} → {after_count:,} (净变化 {net_change:+,})")

            count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            print(f"  当前订单总数: {count:,}")
    finally:
        conn.close()


def _copy_df_to_duckdb(df, conn, existing_cols):
    """通过Parquet中间文件将DataFrame追加写入DuckDB（不删除已有数据）。
    使用 INSERT ... ON CONFLICT DO NOTHING 跳过已存在的 (order_id, sub_order_id) 组合，
    彻底规避唯一约束冲突导致的崩溃。"""
    if df.empty:
        return 0
    df_insert = df[existing_cols].copy()
    # ID列统一转字符串，避免类型不一致导致字符串比较时 "1" != "1.0"
    for col in ['order_id', 'sub_order_id']:
        if col in df_insert.columns:
            df_insert[col] = df_insert[col].astype(str).replace('nan', '').replace('None', '')
    parquet_path = os.path.join(tempfile.gettempdir(), f'orders_{id(df)}.parquet')
    df_insert.to_parquet(parquet_path, index=False)

    # 使用临时表 + INSERT ... ON CONFLICT DO NOTHING（兼容 DuckDB 语法）
    import uuid
    tmp_table = f"_orders_stage_{uuid.uuid4().hex[:8]}"
    cols_joined = ', '.join(existing_cols)
    try:
        # 1. 创建临时 staging 表（无约束）
        conn.execute(f"CREATE TEMP TABLE {tmp_table} AS SELECT * FROM orders WHERE 1=0")
        # 2. COPY 数据到 staging 表
        conn.execute(f"COPY {tmp_table} ({cols_joined}) FROM '{parquet_path}' (FORMAT PARQUET)")
        # 3. 从 staging 表 INSERT 到 orders（已存在的行自动跳过）
        conn.execute(f"""
            INSERT INTO orders ({cols_joined})
            SELECT {cols_joined} FROM {tmp_table}
            ON CONFLICT (order_id, sub_order_id) DO NOTHING
        """)
        copied = conn.execute(f"SELECT COUNT(*) FROM {tmp_table}").fetchone()[0]
    finally:
        conn.execute(f"DROP TABLE IF EXISTS {tmp_table}")
        os.remove(parquet_path)
    return copied
