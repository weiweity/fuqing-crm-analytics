"""
芙清 CRM - ETL 脚本 v6
支持全量/增量/SPU重匹配模式：
  python run_etl.py                    # 自动检测：数据库空则全量，有数据则增量
  python run_etl.py --full             # 强制全量重建
  python run_etl.py --inc              # 强制增量
  python run_etl.py --update           # 一键增量更新（ETL+淘客+状态刷新）
  python run_etl.py --rescan-spu --product-ids 1008376905465 --dry-run
  python run_etl.py --rescan-spu --product-ids 1008376905465 --apply
"""

import gc
import sys
import os
import argparse
import functools
from pathlib import Path

# 添加项目根目录到 Python 路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import duckdb
import warnings
from backend.config import (
    DUCKDB_PATH, SHOP_DATA_SOURCE, MEMBER_DATA_SOURCE, SPU_MAPPING_SOURCE,
    PROCESSED_DATA_DIR, PARQUET_DATA_DIR
)

warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

# 列名映射：中文 -> 英文（匹配实际列名）
COLUMN_MAPPING = {
    '订单编号': 'order_id',
    '子订单号': 'sub_order_id',
    '用户ID': 'user_id',
    '买家昵称': 'user_nickname',
    '下单时间': 'order_time',
    '付款时间': 'pay_time',
    '发货时间': 'ship_time',
    '订单类型': 'order_type',
    '子订单状态': 'order_status',
    '商品ID': 'product_id',
    '商家编码': 'merchant_code',
    '商品标题': 'product_title',
    'SKUID': 'sku_id',
    'SKU编号': 'sku_code',
    'SKU名称': 'sku_name',
    '购买数量': 'quantity',
    '应付金额': 'amount',
    '退款状态': 'refund_status',
    '退款金额': 'refund_amount',
    '实付金额': 'actual_amount',
    '收货人省份': 'province',
    '收货人城市': 'city',
    '达人名称': 'influencer_name',
    '达人id': 'influencer_id',
    '直播间id': 'live_room_id',
    '视频id': 'video_id',
    '流量来源': 'traffic_source',
    '流量体裁': 'traffic_type',
    '卖家备注': 'seller_note'
}

# SPU 列名映射
# 原始 Excel 有合并单元格，pandas 读取 CSV 时 header 与 data 错位（从 col2 开始偏移 1 列）
# 正确映射：按 data 内容反推 → 直接用列位置重命名
#   col0 = 商品ID → product_id
#   col1 = 品类销售 → spu_category
#   col2 = "妆品销售/械品销售" → spu_category 二次映射（品类销售下钻）
#   col3 = "小样-U先/正装"    → spu_type（正装/小样）
#   col4 = "二梯队/核心品"   → spu_tier（商品梯队）
#   col5 = "胶原膜/..."     → spu_product_class（单品归类）
#   col6 = "胶原膜/..."     → spu_product_subclass（单品细分）
#   col7 = "械/妆"         → spu_cosmetic（妆/械）
#   col8 = "胶原膜*2片/..." → spu_spec（商品规格）
#   col9 = "2000/1/1"      → spu_start_date
#   col10 = "45368"        → spu_end_date（Excel serial，load_spu_mapping 中统一转日期）
SPU_COLUMNS = {
    '商品ID': 'product_id',
    '品类销售': 'spu_category',
    '正装/小样': 'spu_type',
    '商品梯队': 'spu_tier',
    '单品归类': 'spu_product_class',
    '单品细分': 'spu_product_subclass',
    '妆/械': 'spu_cosmetic',
    '商品规格': 'spu_spec',
    '开始时间': 'spu_start_date',
    '结束时间': 'spu_end_date'
}

# 渠道判定表路径
CHANNEL_RULES_SOURCE = Path(r"/Users/hutou/Desktop/fuqin date/芙清CRM数据库/芙清crm原始数据库/渠道判定.csv")

# 淘客数据库路径
TAOKE_DATA_SOURCE = Path(r"/Users/hutou/Desktop/fuqin date/芙清CRM数据库/芙清crm原始数据库/淘客数据库")
TAOKE_COL = "淘宝父订单编号"

# 淘客商品ID表路径（基于商品ID+时间范围补充淘客标记）
TAOKE_PRODUCT_SOURCE = Path(r"/Users/hutou/Desktop/fuqin date/芙清CRM数据库/芙清crm原始数据库/天猫_淘客数据商品ID_数据表.csv")

# 直播间数据源路径
LIVE_DATA_SOURCE = Path(r"/Users/hutou/Desktop/fuqin date/芙清CRM数据库/芙清crm原始数据库/直播间数据源")

# 淘客订单号全局缓存（进程生命周期内只读一次文件）
_TAOKE_ORDER_IDS_CACHE = None

# 直播订单号全局缓存（进程生命周期内只读一次文件）
_LIVE_ORDER_IDS_CACHE = None

# 淘客商品ID规则缓存（进程生命周期内只读一次文件）
# 格式: [(product_id_str, start_date, end_date), ...]
_TAOKE_PRODUCT_RULES_CACHE = None

# ETL 各数据源扫描统计（供结尾摘要表使用）
_ETL_SOURCE_STATS = {}


def _get_taoke_cache_path():
    """淘客文件级缓存路径（记录每个文件的 mtime + 订单ID列表）"""
    return PROCESSED_DATA_DIR / "taoke_file_cache.json"


def _load_taoke_cache():
    """加载淘客文件缓存。格式: {filename: {"mtime": float, "ids": [str, ...]}}"""
    path = _get_taoke_cache_path()
    if path.exists():
        import json
        with open(path, 'r') as f:
            return json.load(f)
    return {}


def _save_taoke_cache(cache):
    """保存淘客文件缓存"""
    import json
    path = _get_taoke_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(cache, f, indent=2, sort_keys=True)


def _get_live_cache_path():
    """直播文件级缓存路径（记录每个文件的 mtime + 订单ID列表）"""
    return PROCESSED_DATA_DIR / "live_file_cache.json"


def _load_live_cache():
    """加载直播文件缓存。格式: {filename: {"mtime": float, "ids": [str, ...]}}"""
    path = _get_live_cache_path()
    if path.exists():
        import json
        with open(path, 'r') as f:
            return json.load(f)
    return {}


def _save_live_cache(cache):
    """保存直播文件缓存"""
    import json
    path = _get_live_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(cache, f, indent=2, sort_keys=True)


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


def rename_columns(df):
    """重命名列名为英文"""
    rename_map = {}
    for cn, en in COLUMN_MAPPING.items():
        if cn in df.columns:
            rename_map[cn] = en
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def parse_date(date_str):
    """解析日期字符串"""
    if pd.isna(date_str):
        return None
    date_str = str(date_str).strip()
    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d']:
        try:
            return pd.to_datetime(date_str, format=fmt)
        except Exception:
            continue
    return None


def load_spu_mapping():
    """加载 SPU 匹配表（无 header 模式，手动按位置映射列名）

    原始 Excel 有合并单元格，pandas 读 CSV 时 header 与 data 错位 1 列（从 col2 起）。
    按 data 内容分析后的正确列位置：
      col0 → product_id   col1 → spu_category
      col2 → spu_category(二次)  col3 → spu_type  col4 → spu_tier
      col5 → spu_product_class  col6 → spu_product_subclass
      col7 → spu_cosmetic  col8 → spu_spec
      col9 → spu_start_date(str)  col10 → spu_end_date(Excel serial)
    """
    print("加载 SPU 匹配表...")
    spu_file = SPU_MAPPING_SOURCE
    if not spu_file.exists():
        print(f"  SPU文件不存在: {spu_file}")
        return None

    try:
        # 无 header 模式读取（避免合并单元格导致列名错位）
        for encoding in ['gbk', 'gb2312', 'utf-8']:
            try:
                df = pd.read_csv(spu_file, header=None, encoding=encoding)
                print(f"  使用编码: {encoding}")
                break
            except Exception:
                continue
        else:
            raise UnicodeDecodeError(
                'utf-8', b'', 0, 0,
                f"无法使用任何已知编码读取 SPU 文件: {spu_file}"
            )

        # 按位置指定列名（忽略原 CSV header 的错误映射）
        COL_NAMES = [
            'product_id',          # col0
            'spu_category',        # col1
            'spu_category_drill',  # col2: 品类下钻(妆/械品销售)
            'spu_type',            # col3: 正装/小样
            'spu_tier',            # col4: 商品梯队
            'spu_product_class',   # col5: 单品归类
            'spu_product_subclass',# col6: 单品细分
            'spu_cosmetic',        # col7: 妆/械
            'spu_spec',            # col8: 商品规格
            'spu_start_date',      # col9: 开始时间(str)
            'spu_end_date',        # col10: 结束时间(Excel serial)
            '_col11',              # col11: 修改人（不用）
            '_col12',              # col12: 父记录（不用）
        ]
        df.columns = COL_NAMES[:len(df.columns)]

        # 过滤掉残留的 header 行（如 '商品ID' 这种字符串 product_id）
        df = df[df['product_id'].astype(str).str.match(r'^\d+\.?\d*$', na=False)]

        # spu_start_date / spu_end_date: 优先解析为日期字符串，失败则尝试 Excel serial
        # Excel serial = 距离 1899-12-30 的天数
        # FIX(2026-04-26): start_date 之前漏了 Excel serial 回退，导致 1.8% 记录解析为 NaT
        def _parse_spu_date(val):
            if pd.isna(val):
                return pd.NaT
            s = str(val).strip()
            # 优先尝试标准日期格式（处理 "2024/3/17"、"2099/12/31" 等）
            for fmt in ['%Y/%m/%d', '%Y-%m-%d', '%Y.%m.%d']:
                try:
                    return pd.Timestamp(s)
                except Exception:
                    pass
            # 回退到 Excel serial（处理纯数字如 45368、46111）
            try:
                return pd.Timestamp('1899-12-30') + pd.Timedelta(days=int(float(s)))
            except Exception:
                return pd.NaT

        df['spu_start_date'] = df['spu_start_date'].apply(_parse_spu_date)
        df['spu_end_date'] = df['spu_end_date'].apply(_parse_spu_date)

        # 保留需要的列（排除中间列和不用列）
        keep_cols = ['product_id', 'spu_category', 'spu_type', 'spu_tier',
                     'spu_product_class', 'spu_product_subclass', 'spu_cosmetic',
                     'spu_spec', 'spu_start_date', 'spu_end_date']
        df = df[[c for c in keep_cols if c in df.columns]]

        print(f"  SPU匹配表: {len(df)} 条记录")
        print(f"  包含字段: {df.columns.tolist()}")
        return df
    except Exception as e:
        print(f"  加载SPU失败: {e}")
        return None


def load_channel_rules():
    """加载渠道判定规则"""
    print("\n加载渠道判定规则...")
    channel_file = CHANNEL_RULES_SOURCE
    if not channel_file.exists():
        print(f"  渠道判定文件不存在: {channel_file}")
        return None, None

    try:
        # 多编码尝试
        for enc in ['utf-8', 'gbk', 'gb2312']:
            try:
                df = pd.read_csv(channel_file, encoding=enc)
                print(f"  渠道判定编码: {enc}")
                break
            except:
                continue
        # 清理列名（按列名映射，而非按位置）
        col_map = {}
        for col in df.columns:
            col_lower = str(col).strip().lower()
            if '关键词' in col or 'keyword' in col_lower:
                col_map[col] = 'keyword'
            elif '渠道' in col and 'product' not in col_lower and 'channel' not in col_lower:
                col_map[col] = 'channel'
            elif '商品id' in col or 'product_id' in col_lower or '商品编号' in col:
                col_map[col] = 'product_id'
            elif 'channel' in col_lower and col not in col_map.values():
                col_map[col] = 'channel2'
        df = df.rename(columns=col_map)

        # 只有2列时（关键词+渠道），直接重命名
        if len(df.columns) == 2 and 'keyword' not in df.columns:
            df.columns = ['keyword', 'channel']

        # 提取关键词规则
        keyword_rules = []
        if 'keyword' in df.columns and 'channel' in df.columns:
            keyword_rules = df[['keyword', 'channel']].dropna().values.tolist()
        print(f"  关键词规则: {len(keyword_rules)} 条")
        if not keyword_rules:
            print("  ⚠️ 警告: keyword_rules 为空，P4 达播/微博关键词匹配将跳过")

        # 提取商品ID规则（仅当存在时才提取）
        id_rules = []
        if 'product_id' in df.columns and 'channel2' in df.columns:
            id_rules = df[['product_id', 'channel2']].dropna().values.tolist()
        print(f"  商品ID规则: {len(id_rules)} 条")

        return keyword_rules, id_rules
    except Exception as e:
        print(f"  加载渠道规则失败: {e}")
        return None, None


def _read_taoke_csv_robust(filepath):
    """
    使用 csv 模块读取淘客 CSV，兼容字段数不一致的行（不会跳过整行）。
    只提取 TAOKE_COL（淘宝父订单编号）列的数据。
    """
    import csv
    for enc in ('utf-8', 'gbk'):
        try:
            fh = open(filepath, 'r', encoding=enc, errors='replace', newline='')
            break
        except Exception:
            fh = None
    if fh is None:
        return pd.DataFrame()
    with fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if not header:
            return pd.DataFrame()
        try:
            col_idx = [h.strip() for h in header].index(TAOKE_COL)
        except ValueError:
            return pd.DataFrame()
        rows = []
        for row in reader:
            if len(row) > col_idx:
                rows.append(row[col_idx])
    return pd.DataFrame({TAOKE_COL: rows})


def load_taoke_order_ids():
    """
    读取淘客数据库所有文件，返回去重后的订单号集合。
    使用文件级缓存（mtime 检测）：未变化的文件直接跳过，只读新增/修改过的文件。
    """
    global _TAOKE_ORDER_IDS_CACHE, _ETL_SOURCE_STATS
    if _TAOKE_ORDER_IDS_CACHE is not None:
        return _TAOKE_ORDER_IDS_CACHE

    print("\n加载淘客数据库...")
    if not TAOKE_DATA_SOURCE.exists():
        print(f"  淘客数据库目录不存在: {TAOKE_DATA_SOURCE}")
        _TAOKE_ORDER_IDS_CACHE = set()
        return _TAOKE_ORDER_IDS_CACHE

    files = list(TAOKE_DATA_SOURCE.glob("*"))
    # 过滤出支持的文件类型
    files = [f for f in files if f.suffix.lower() in ('.csv', '.xlsx', '.xls')]
    print(f"  找到 {len(files)} 个文件")

    cache = _load_taoke_cache()  # {filename: {"mtime": float, "ids": [str]}}
    all_ids = set()
    reloaded = 0
    skipped = 0

    for f in files:
        key = f.name
        mtime = f.stat().st_mtime

        # 未变化：直接用缓存
        if key in cache and cache[key].get("mtime") == mtime:
            all_ids.update(cache[key].get("ids", []))
            skipped += 1
            continue

        # 新增或变化：重新读取
        try:
            if f.suffix.lower() == '.csv':
                df = _read_taoke_csv_robust(f)
                if df.empty:
                    df = pd.read_csv(f, dtype={TAOKE_COL: str}, low_memory=False, on_bad_lines='warn')
            else:
                df = pd.read_excel(f, dtype={TAOKE_COL: str})

            if TAOKE_COL not in df.columns:
                print(f"    跳过（无 {TAOKE_COL} 列）: {f.name}")
                continue

            # 清洗制表符、空格，并过滤空值
            col = df[TAOKE_COL].astype(str).str.strip().str.replace('\t', '', regex=False)
            col = col[col.notna() & (col != '') & (col != 'nan')]
            ids = col.tolist()
            all_ids.update(ids)
            cache[key] = {"mtime": mtime, "ids": ids}
            reloaded += 1
            print(f"    {f.name}: +{len(ids):,} 条")

        except Exception as e:
            print(f"    跳过（读取失败）: {f.name} -> {e}")
            continue

    # 清理已删除的文件缓存
    current_names = {f.name for f in files}
    removed = [k for k in cache if k not in current_names]
    for k in removed:
        del cache[k]

    _save_taoke_cache(cache)
    print(f"  淘客订单号合计（去重后）: {len(all_ids):,} 条")
    print(f"  [缓存] 重新读取: {reloaded} 个文件, 跳过: {skipped} 个文件, 清理: {len(removed)} 个")
    _TAOKE_ORDER_IDS_CACHE = all_ids
    _ETL_SOURCE_STATS['taoke'] = {
        'files': len(files),
        'reloaded': reloaded,
        'skipped': skipped,
        'total_ids': len(all_ids),
    }
    return all_ids


def load_live_order_ids():
    """
    读取直播间数据源所有 CSV/XLSX 文件，返回去重后的父订单号集合。
    文件级缓存：基于 mtime 检测变更，未变更文件直接复用缓存。
    匹配键：父订单id/父订单ID（去掉 ID_ 前缀得到纯数字，即 orders.order_id）
    """
    global _LIVE_ORDER_IDS_CACHE, _ETL_SOURCE_STATS
    if _LIVE_ORDER_IDS_CACHE is not None:
        return _LIVE_ORDER_IDS_CACHE

    print("\n加载直播间数据源...")
    if not LIVE_DATA_SOURCE.exists():
        print(f"  直播间数据源目录不存在: {LIVE_DATA_SOURCE}")
        _LIVE_ORDER_IDS_CACHE = set()
        _ETL_SOURCE_STATS['live'] = {'files': 0, 'reloaded': 0, 'skipped': 0, 'total_ids': 0}
        return _LIVE_ORDER_IDS_CACHE

    csv_files = list(LIVE_DATA_SOURCE.glob("*.csv"))
    xlsx_files = list(LIVE_DATA_SOURCE.glob("*.xlsx"))
    files = csv_files + xlsx_files
    print(f"  找到 {len(csv_files)} 个 CSV 文件, {len(xlsx_files)} 个 XLSX 文件")

    cache = _load_live_cache()  # {filename: {"mtime": float, "ids": [str]}}
    all_ids = set()
    reloaded = 0
    skipped = 0

    for f in files:
        key = f.name
        mtime = f.stat().st_mtime

        # 未变化：直接用缓存
        if key in cache and cache[key].get("mtime") == mtime:
            all_ids.update(cache[key].get("ids", []))
            skipped += 1
            continue

        # 新增或变化：重新读取
        try:
            if f.suffix.lower() == '.csv':
                df = pd.read_csv(f, dtype=str, low_memory=False, on_bad_lines='warn')
            else:
                df = pd.read_excel(f, dtype=str)

            # 兼容列名：父订单id / 父订单ID
            col_name = None
            for c in df.columns:
                if str(c).strip() in ('父订单id', '父订单ID'):
                    col_name = c
                    break
            if col_name is None:
                print(f"    跳过（无 父订单id/父订单ID 列）: {f.name}")
                continue

            # 清洗：去掉 ID_ 前缀、去空格、过滤空值/占位符
            ids = df[col_name].astype(str).str.replace('ID_', '', regex=False).str.strip()
            ids = ids[ids.notna() & (ids != '') & (ids != 'nan') & (ids != '-')]
            all_ids.update(ids.tolist())
            cache[key] = {"mtime": mtime, "ids": ids.tolist()}
            reloaded += 1
            print(f"    {f.name}: +{len(ids)} 条")

        except Exception as e:
            print(f"    跳过（读取失败）: {f.name} -> {e}")
            continue

    # 清理已删除的文件缓存
    current_names = {f.name for f in files}
    removed = [k for k in cache if k not in current_names]
    for k in removed:
        del cache[k]

    _save_live_cache(cache)
    print(f"  直播订单号合计（去重后）: {len(all_ids):,} 条")
    print(f"  [缓存] 重新读取: {reloaded} 个文件, 跳过: {skipped} 个文件, 清理: {len(removed)} 个")
    _LIVE_ORDER_IDS_CACHE = all_ids
    _ETL_SOURCE_STATS['live'] = {
        'files': len(files),
        'reloaded': reloaded,
        'skipped': skipped,
        'total_ids': len(all_ids),
    }
    return all_ids


def load_taoke_product_rules():
    """
    读取天猫_淘客数据商品ID_数据表.csv，返回商品ID→时间区间列表的映射。

    返回格式: Dict[str, List[Tuple[start_date, end_date]]]
    用于补充淘客标记：订单的 product_id + pay_time 匹配任意时间段 → 标记为淘客。
    """
    global _TAOKE_PRODUCT_RULES_CACHE, _ETL_SOURCE_STATS
    if _TAOKE_PRODUCT_RULES_CACHE is not None:
        return _TAOKE_PRODUCT_RULES_CACHE

    print("\n加载淘客商品ID表...")
    if not TAOKE_PRODUCT_SOURCE.exists():
        print(f"  淘客商品ID表不存在: {TAOKE_PRODUCT_SOURCE}")
        _TAOKE_PRODUCT_RULES_CACHE = {}
        _ETL_SOURCE_STATS['taoke_product'] = {'files': 0, 'total_rules': 0}
        return _TAOKE_PRODUCT_RULES_CACHE

    try:
        df = pd.read_csv(TAOKE_PRODUCT_SOURCE)
        # 解析日期
        df['start_date'] = pd.to_datetime(df['开始日期'], errors='coerce')
        df['end_date'] = pd.to_datetime(df['结束日期'], errors='coerce')
        # 过滤无效日期
        df = df.dropna(subset=['start_date', 'end_date'])
        # 按商品ID分组，收集所有时间段
        rules = {}
        for product_id, group in df.groupby('商品ID'):
            pid_str = str(int(product_id)) if pd.notna(product_id) else ''
            if not pid_str:
                continue
            intervals = list(zip(group['start_date'], group['end_date']))
            rules[pid_str] = intervals

        _TAOKE_PRODUCT_RULES_CACHE = rules
        total_intervals = sum(len(v) for v in rules.values())
        print(f"  淘客商品ID表: {len(rules)} 个商品，{total_intervals} 个时间段")
        _ETL_SOURCE_STATS['taoke_product'] = {
            'files': 1,
            'total_rules': total_intervals,
        }
        return rules
    except Exception as e:
        print(f"  加载淘客商品ID表失败: {e}")
        _TAOKE_PRODUCT_RULES_CACHE = {}
        _ETL_SOURCE_STATS['taoke_product'] = {'files': 0, 'total_rules': 0}
        return _TAOKE_PRODUCT_RULES_CACHE


def _get_processed_files_path(data_type):
    """获取已处理文件的追踪路径（新格式：path→mtime dict）"""
    return PROCESSED_DATA_DIR / f"processed_files_{data_type}.json"


def _load_processed_files(data_type):
    """加载已处理文件列表。
    新格式: {"path": mtime, ...}
    兼容旧格式(list): 自动转为 dict，mtime=0（下次会重新处理）
    """
    path = _get_processed_files_path(data_type)
    if path.exists():
        import json
        with open(path, 'r') as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        # 旧格式兼容：list/set → dict(mtime=0)
        return {str(p): 0 for p in data}
    return {}


def _save_processed_files(data_type, processed_dict):
    """保存已处理文件列表（dict 格式：path→mtime）"""
    import json
    path = _get_processed_files_path(data_type)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(processed_dict, f, indent=2, sort_keys=True)


def load_data_files(data_source, data_type='shop', run_mode='full'):
    """
    加载数据文件。优先读 Parquet 缓存，fallback 到 xlsx。

    data_type: 'shop' 或 'member'，决定查找哪个 Parquet 子目录
    run_mode: 'full' 加载全部 / 'incremental' 只加载新增文件
    """
    print(f"\n{'='*50}")
    print(f"加载数据: {data_source} (模式: {run_mode})")
    print(f"路径: {data_source}")

    if not data_source.exists():
        print(f"  目录不存在!")
        return pd.DataFrame()

    # 初始化变量（避免全量模式跳过Parquet时UnboundLocalError）
    pq_data = []
    combined_pq = None

    # ———— 优先：从 Parquet 读取 ————
    pq_dir = PARQUET_DATA_DIR / data_type
    # FIX(2026-04-26): 全量模式跳过Parquet，直接从xlsx读取
    # Parquet和xlsx是同源数据（Parquet只是格式转换缓存），同时加载会导致
    # 约3000万行冗余数据，内存耗尽崩溃。全量模式下xlsx是最新最完整的原始数据。
    if run_mode == 'full':
        print("  [Parquet 缓存] 全量模式: 跳过Parquet，直接从xlsx读取（避免内存冗余）")
        pq_files = []
    elif pq_dir.exists():
        pq_files = list(pq_dir.glob("*.parquet"))
    else:
        pq_files = []

    if pq_files:
        should_read_parquet = True
        # 增量模式：只加载新增或修改过的 Parquet 文件（对比 mtime）
        if run_mode == 'incremental':
            processed_files = _load_processed_files(data_type)
            new_files = []
            for f in pq_files:
                key = f.name
                mtime = f.stat().st_mtime
                if key not in processed_files or mtime > processed_files[key]:
                    new_files.append(f)
            if not new_files:
                print(f"  [Parquet 缓存] 无新增/变更 parquet 文件，继续检查 xlsx 原始文件")
                should_read_parquet = False
            else:
                # FIX(2026-04-29): 检查xlsx源是否有新文件，防止parquet缓存过期导致新xlsx被跳过
                xlsx_files = list(data_source.rglob("*.xlsx"))
                xlsx_new = []
                for xf in xlsx_files:
                    xkey = str(xf.relative_to(data_source))
                    xmtime = xf.stat().st_mtime
                    if xkey not in processed_files or xmtime > processed_files[xkey]:
                        xlsx_new.append(xf)
                if xlsx_new:
                    print(f"  [Parquet 缓存] 发现 {len(xlsx_new)} 个新xlsx文件，跳过parquet直接读xlsx（避免缓存过期）")
                    should_read_parquet = False
                else:
                    pq_files = new_files
                    print(f"  [Parquet 缓存] 增量模式: {len(pq_files)} 个新增/变更文件（已处理 {len(processed_files)} 个）")

        if should_read_parquet:
                if run_mode == 'full':
                    print(f"  [Parquet 缓存] 全量模式: 找到 {len(pq_files)} 个 parquet 文件")

                pq_data = []
                for i, f in enumerate(pq_files):
                    if (i + 1) % 20 == 0:
                        print(f"  进度: {i+1}/{len(pq_files)}")
                    try:
                        df = pd.read_parquet(f)
                        # Parquet 读取后自动完成列名清理和年份提取
                        df = rename_columns(df)
                        if 'order_time' in df.columns:
                            df['order_time'] = pd.to_datetime(df['order_time'], errors='coerce')
                            df['year'] = df['order_time'].dt.year
                            df['month'] = df['order_time'].dt.month
                        pq_data.append(df)
                        print(f"    {f.name}: {len(df):,} 行 [parquet]")
                    except Exception as e:
                        print(f"    跳过(parquet失败): {f.name} → {e}")
                        continue
                if pq_data:
                    combined_pq = pd.concat(pq_data, ignore_index=True)
                    # 增量模式：更新已处理文件列表（记录 mtime）
                    if run_mode == 'incremental':
                        processed_files = _load_processed_files(data_type)
                        for f in pq_files:
                            processed_files[f.name] = f.stat().st_mtime
                        _save_processed_files(data_type, processed_files)
                    print(f"  Parquet 数据合计: {len(combined_pq):,} 行")
                    if run_mode == 'incremental':
                        return combined_pq
                    # 全量模式：保留 parquet 数据，继续读 xlsx 补充
                # parquet 读取全部失败，或全量模式继续走 xlsx fallback

    # ———— Fallback：读 xlsx（支持文件级增量，含 mtime 检测）————
    print(f"  [xlsx fallback] 读取原始文件")
    files = list(data_source.rglob("*.xlsx"))
    print(f"  找到 {len(files)} 个文件")

    # 增量模式：只读新增或修改过的 xlsx 文件（对比 mtime）
    if run_mode == 'incremental':
        processed_files = _load_processed_files(data_type)
        new_files = []
        for f in files:
            key = str(f.relative_to(data_source))
            mtime = f.stat().st_mtime
            if key not in processed_files or mtime > processed_files[key]:
                new_files.append(f)
        if not new_files:
            # 找到目录中最新的文件，确认它确实在缓存中（避免误判）
            latest = max(files, key=lambda f: f.stat().st_mtime) if files else None
            latest_key = str(latest.relative_to(data_source)) if latest else ""
            if latest and latest_key in processed_files:
                latest_dt = pd.Timestamp(latest.stat().st_mtime, unit='s').strftime('%Y-%m-%d %H:%M')
                print(f"  [xlsx 增量] 所有 {len(files)} 个文件均已处理（最新: {latest.name} @ {latest_dt}），无需重新加载")
            else:
                print(f"  [xlsx 增量] 无新增/变更文件，跳过（已处理 {len(processed_files)} 个）")
            return pd.DataFrame()
        print(f"  [xlsx 增量] {len(new_files)} 个新增/变更文件（已处理 {len(processed_files)} 个）")
        files = new_files

    all_data = []
    # 全量模式：把 parquet 数据先放入 all_data，再补充 xlsx
    if run_mode == 'full' and pq_data:
        all_data.append(combined_pq)

    processed_new = {}
    for i, f in enumerate(files):
        if (i + 1) % 10 == 0:
            print(f"  进度: {i+1}/{len(files)}")

        try:
            # 读取 Excel，跳过可能的标题行
            df = pd.read_excel(f, engine='openpyxl', header=0)

            # 清理列名空格
            df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]

            # 重命名列
            df = rename_columns(df)

            # 基础字段检查
            if 'order_id' not in df.columns and '订单编号' not in df.columns:
                print(f"    跳过(无订单列): {f.name}")
                continue

            # 添加年份月份
            if 'order_time' in df.columns:
                df['order_time'] = pd.to_datetime(df['order_time'], errors='coerce')
                df['year'] = df['order_time'].dt.year
                df['month'] = df['order_time'].dt.month

            all_data.append(df)
            processed_new[str(f.relative_to(data_source))] = f.stat().st_mtime
            print(f"    {f.name}: {len(df)} 行")

        except Exception as e:
            print(f"    跳过({e}): {f.name}")
            continue

    # 增量模式：更新已处理文件列表（记录 mtime）
    if run_mode == 'incremental' and processed_new:
        existing_processed = _load_processed_files(data_type)
        for key, mtime in processed_new.items():
            existing_processed[key] = mtime
        _save_processed_files(data_type, existing_processed)
        print(f"  [xlsx 增量] 已更新处理记录: +{len(processed_new)} 个文件")

    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        print(f"  数据合计: {len(combined)} 行")
        return combined
    else:
        print(f"  无有效数据")
        return pd.DataFrame()


def match_channel(df, keyword_rules, id_rules, taoke_order_ids=None, live_order_ids=None, taoke_product_rules=None):
    """
    8层漏斗渠道判定（从高优先级到低优先级，高优先级永不被低优先级覆盖）。

    P1: U先派样      — spu_type 含 "小样-U先"（不区分大小写）OR product_title 含 "U先"（不区分大小写）OR product_title 含 "会员尝鲜"
    P2: 百补派样     — spu_type 含 "小样-百亿补贴" OR product_title 含 "by"（不区分大小写）
    P3: 赠品&0.01渠道 — spu_type 含 "小样"（排除P1/P2）OR product_title 含 "赠品"
    P4: 达播/微博    — keyword_rules / id_rules（仅对 channel='其他' 生效，含P4保护）
    P5: 直播         — order_id 匹配直播CSV的父订单号
    P6: 淘客(订单号) — order_id 在淘客数据库中
    P6-2: 淘客(关键词) — product_title 含 T1/T2/T4/TK（大小写不敏感，芙清淘客商品标识后缀）
    P7: 购物金       — product_title 含 "购物金"
    P8: 货架         — P1-P7未命中 且 spu_type 含 "正装"
    P9: 其他         — P1-P8未命中
    """
    # 默认值
    df['channel'] = '其他'

    spu_type = df['spu_type'].astype(str)
    product_title = df['product_title'].astype(str)

    # P1: U先派样
    # 修复：spu_type 实际值是"小样-U先"（大写U），需不区分大小写
    # 修复：product_title 包含"【U先】"和"【天猫U先】"，需匹配所有"U先"变体
    # 新增：product_title 含"会员尝鲜"也归入U先派样
    mask_u = (
        spu_type.str.contains('小样-u先', case=False, na=False) |
        product_title.str.contains('u先', case=False, na=False) |
        product_title.str.contains('会员尝鲜', case=False, na=False)
    )
    df.loc[mask_u, 'channel'] = 'U先派样'
    print(f"  P1 U先派样: {mask_u.sum():,}")

    # P2: 百补派样
    mask_b = spu_type.str.contains('小样-百亿补贴', na=False) | product_title.str.contains('by', case=False, na=False)
    df.loc[mask_b, 'channel'] = '百补派样'
    print(f"  P2 百补派样: {mask_b.sum():,}")

    # P3: 赠品&0.01渠道
    # 修复：移除 actual_amount < 4 的独立条件，避免覆盖P1/P2的分类结果
    mask_z = (
        (spu_type.str.contains('小样', na=False) & ~mask_u & ~mask_b) |
        product_title.str.contains('赠品', na=False)
    )
    df.loc[mask_z, 'channel'] = '赠品&0.01渠道'
    print(f"  P3 赠品&0.01渠道: {mask_z.sum():,}")

    # P4: 达播/微博（仅对未匹配订单生效，保护P1-P3）
    p4_count = 0
    if keyword_rules or id_rules:
        # 1. 商品ID精确匹配（仅对未匹配订单生效）
        if id_rules:
            id_map = {str(int(pid)): ch for pid, ch in id_rules
                      if pd.notna(pid) and pd.notna(ch)}
            if id_map:
                matched_ids = df['product_id'].astype(str).map(id_map)
                mask_unmatched = df['channel'] == '其他'
                df.loc[mask_unmatched & matched_ids.notna(), 'channel'] = matched_ids.dropna().values
                p4_count += (mask_unmatched & matched_ids.notna()).sum()

        # 2. 关键词模糊匹配（仅对未匹配订单生效，长词优先）
        if keyword_rules:
            kw_list = [(str(k).strip(), str(ch).strip())
                      for k, ch in keyword_rules if pd.notna(k) and pd.notna(ch)]
            if kw_list:
                kw_list.sort(key=lambda x: -len(x[0]))  # 长词优先
                titles = df['product_title'].astype(str)
                mask_unmatched = df['channel'] == '其他'
                for kw, ch in kw_list:
                    mask_kw = titles.str.contains(kw, case=False, na=False)
                    df.loc[mask_unmatched & mask_kw, 'channel'] = ch
                    p4_count += (mask_unmatched & mask_kw).sum()

        print(f"  P4 达播/微博: {p4_count:,}")

    # P5: 直播（仅对未匹配订单生效，order_id 在直播CSV父订单号集合中）
    if live_order_ids:
        mask_unmatched = df['channel'] == '其他'
        mask_live = mask_unmatched & df['order_id'].astype(str).isin(live_order_ids)
        df.loc[mask_live, 'channel'] = '直播'
        print(f"  P5 直播: {mask_live.sum():,}")

    # P6: 淘客（仅对未匹配订单生效）
    if taoke_order_ids:
        mask_unmatched = df['channel'] == '其他'
        mask_tk = mask_unmatched & df['order_id'].astype(str).isin(taoke_order_ids)
        df.loc[mask_tk, 'channel'] = '淘客'
        print(f"  P6 淘客: {mask_tk.sum():,}")

    # P6-2: 淘客补充（商品标题关键词匹配）
    # 芙清淘客商品标识后缀：T1/T2/T4/TK（大小写不敏感）
    # 例：...30支T1 / ...30支T2 / ...修复贴T4 / ...消械字TK
    mask_unmatched = df['channel'] == '其他'
    mask_tk_kw = product_title.str.contains(r'T[124K]', case=False, na=False)
    df.loc[mask_unmatched & mask_tk_kw, 'channel'] = '淘客'
    print(f"  P6-2 淘客关键词: {(mask_unmatched & mask_tk_kw).sum():,}")

    # P7: 购物金（product_title 含 "购物金"，仅对未匹配订单生效）
    mask_unmatched = df['channel'] == '其他'
    mask_card = product_title.str.contains('购物金', na=False)
    df.loc[mask_unmatched & mask_card, 'channel'] = '购物金'
    print(f"  P7 购物金: {(mask_unmatched & mask_card).sum():,}")

    # P8: 货架（P1-P7未命中 且 spu_type 含"正装"）
    mask_unmatched = df['channel'] == '其他'
    mask_zheng = spu_type.str.contains('正装', na=False)
    df.loc[mask_unmatched & mask_zheng, 'channel'] = '货架'
    print(f"  P8 货架: {(mask_unmatched & mask_zheng).sum():,}")

    # P9: 其他（P1-P8未命中）
    print(f"  P9 其他: {(df['channel'] == '其他').sum():,}")

    # 验证：检查高优先级渠道订单是否被错误覆盖为淘客
    if taoke_order_ids:
        wrong_taoke = (
            (df['channel'] == '淘客') &
            (
                spu_type.str.contains('小样', na=False) |
                product_title.str.contains('u先|赠品|购物金', case=False, na=False) |
                (df['actual_amount'] < 4)
            )
        )
        wrong_count = wrong_taoke.sum()
        if wrong_count > 0:
            print(f"  ⚠️ 警告: {wrong_count:,} 条订单疑似被错误标记为淘客（含小样/U先/赠品/<¥4）")

    channel_stats = df['channel'].value_counts()
    print(f"  渠道分布: {channel_stats.to_dict()}")
    return df


def clean_data(df, spu_df, keyword_rules, id_rules, taoke_order_ids=None, live_order_ids=None, taoke_product_rules=None):
    """清洗数据"""
    print(f"\n清洗数据: {len(df)} 行")

    # 日期字段处理（向量化）
    for col in ['order_time', 'pay_time', 'ship_time']:
        if col in df.columns:
            # 先直接尝试 pd.to_datetime（处理大部分标准格式）
            df[col] = pd.to_datetime(df[col], errors='coerce')
            # 对仍为空的用兼容解析（处理特殊格式）
            null_mask = df[col].isna()
            if null_mask.any():
                df.loc[null_mask, col] = pd.to_datetime(
                    df.loc[null_mask, col].astype(str).str.strip(),
                    format='%Y/%m/%d %H:%M:%S',
                    errors='coerce'
                )

    # 金额字段处理
    for col in ['amount', 'refund_amount', 'actual_amount']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 数量字段
    if 'quantity' in df.columns:
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(1)

    # ID字段强制转字符串（避免Parquet缓存与xlsx数据类型冲突，导致to_parquet时ArrowTypeError）
    for col in ['order_id', 'sub_order_id', 'user_id', 'product_id', 'sku_id', 'merchant_code']:
        if col in df.columns:
            df[col] = df[col].astype(str).replace('nan', '').replace('None', '')

    # SPU 匹配（向量化版本：用 pd.merge_asof 替代逐行循环）
    if spu_df is not None and 'product_id' in df.columns and 'order_time' in df.columns:
        print("  执行SPU时间范围匹配（向量化）...")

        spu_cols = ['product_id', 'spu_category', 'spu_type', 'spu_tier',
                     'spu_product_class', 'spu_product_subclass', 'spu_cosmetic',
                     'spu_spec', 'spu_start_date', 'spu_end_date']
        spu_cols = [c for c in spu_cols if c in spu_df.columns]
        spu_df_clean = spu_df[spu_cols].copy()

        # 准备订单数据：只保留需要匹配的列
        orders_match = df[['product_id', 'order_time']].copy()
        orders_match['order_idx'] = orders_match.index

        # 过滤无效行，并统一 product_id 类型为字符串（避免 merge 时类型冲突）
        orders_match = orders_match.dropna(subset=['product_id', 'order_time'])
        orders_match['product_id'] = orders_match['product_id'].astype(str)

        spu_valid = spu_df_clean.dropna(subset=['product_id', 'spu_start_date']).copy()
        # 去掉 float 的 .0 后缀，转换为整数字符串（如 744510508122.0 → "744510508122"）
        spu_valid['product_id'] = spu_valid['product_id'].apply(
            lambda x: str(int(x)) if pd.notna(x) else x
        )

        if len(orders_match) > 0 and len(spu_valid) > 0:
            spu_attr_cols = ['spu_category', 'spu_type', 'spu_tier',
                             'spu_product_class', 'spu_product_subclass',
                             'spu_cosmetic', 'spu_spec']
            spu_attr_cols = [c for c in spu_attr_cols if c in spu_valid.columns]

            # 步骤1：过滤出 product_id 在 SPU 表中的订单（避免 merge_asof 跨产品乱匹配）
            orders_in_spu = orders_match[orders_match['product_id'].isin(spu_valid['product_id'])].copy()
            print(f"  product_id 可匹配: {len(orders_in_spu):,} / {len(orders_match):,} ({len(orders_in_spu)/max(len(orders_match),1)*100:.1f}%)")

            if len(orders_in_spu) > 0:
                # 步骤2：常规 merge（product_id + 时间范围），产生候选行
                spu_merge = spu_valid[['product_id', 'spu_start_date', 'spu_end_date'] + spu_attr_cols].copy()
                merged = orders_in_spu.merge(spu_merge, on='product_id', how='left')

                # 步骤3：时间窗口过滤（订单时间在 SPU 有效期内的保留）
                # 条件：order_time >= spu_start_date（已生效）AND order_time <= spu_end_date（未过期）
                # FIX(2026-04-26): 用 normalize() 只比较日期部分，避免 end_date 被解析为
                # YYYY-MM-DD 00:00:00 时，过滤掉同一天后续时间的订单
                valid_mask = (
                    (merged['spu_start_date'].isna() | (merged['order_time'].dt.normalize() >= merged['spu_start_date'].dt.normalize())) &
                    (merged['spu_end_date'].isna() | (merged['spu_end_date'].dt.normalize() >= merged['order_time'].dt.normalize()))
                )
                merged_valid = merged[valid_mask].copy()

                # 步骤4：同一订单可能匹配到多个 SPU，按特异性排序取最优
                # 优先级：spu_product_class 非空 > spu_type 非空 > 更新的 spu_start_date
                # FIX(2026-04-26): spu_start_date 改为降序，确保时间范围更新的记录优先
                merged_valid['_spu_score'] = (
                    merged_valid['spu_product_class'].notna().astype(int) * 100 +
                    merged_valid['spu_type'].notna().astype(int) * 10 +
                    merged_valid['spu_start_date'].notna().astype(int)
                )
                merged_valid = merged_valid.sort_values(
                    ['_spu_score', 'spu_start_date'], ascending=[False, False]
                ).drop_duplicates(subset='order_idx', keep='first')

                matched_count = len(merged_valid)
                print(f"  SPU匹配: {matched_count} / {len(df)} ({matched_count/len(df)*100:.1f}%)")

                # 写回原 DataFrame（通过 order_idx 对齐）
                # 防御：如果 merged_valid 为空，确保 SPU 列初始化为 NaN（不覆盖已有数据）
                if len(merged_valid) > 0:
                    result = merged_valid.set_index('order_idx')[spu_attr_cols]
                    for col in spu_attr_cols:
                        if col in result.columns:
                            df[col] = result[col].reindex(df.index)
                else:
                    # SPU 匹配失败时初始化为空（避免旧数据残留）
                    for col in spu_attr_cols:
                        if col not in df.columns:
                            df[col] = pd.NA

        # SPU 数据验收门卫：在 load_spu_mapping 之后验证 end_date 解析结果
        if spu_df is not None and 'spu_end_date' in spu_df.columns:
            end_date_valid = spu_df['spu_end_date'].notna().mean()
            print(f"  SPU end_date 有效率: {end_date_valid:.1%}  (应为 >0，否则日期解析失败)")
            if end_date_valid < 0.01:
                print("  ⚠️ 警告: spu_end_date 几乎全为 NaT，请检查日期解析逻辑")

    # 渠道匹配（8层漏斗判定）
    print("  执行渠道匹配（8层漏斗）...")
    df = match_channel(df, keyword_rules, id_rules,
                       taoke_order_ids=taoke_order_ids, live_order_ids=live_order_ids,
                       taoke_product_rules=taoke_product_rules)

    # ============================================================
    # 人群看板清洗标记（P0-1, P0-3）
    # ============================================================

    # is_goujinjin：三个字段任意一个含"购物金"或"面值"即标记为购物金用户（剔除）
    mask_gj = (
        df['product_title'].astype(str).str.contains('购物金', na=False) |
        df['sku_name'].astype(str).str.contains('面值', na=False) |
        df['spu_product_class'].astype(str).str.contains('购物金', na=False)
    )
    df['is_goujinjin'] = mask_gj
    print(f"  is_goujinjin（购物金用户）: {mask_gj.sum():,} 行")

    # is_refund：三种情况任意一种即标记为退款（剔除）
    #   1. order_status 含"交易关闭"或"退款"
    #   2. refund_status 非空
    #   3. refund_amount > 0
    order_status_str = df['order_status'].astype(str)
    mask_refund = (
        order_status_str.str.contains('交易关闭', na=False) |
        order_status_str.str.contains('退款', na=False) |
        df['refund_status'].notna() & (df['refund_status'].astype(str).str.strip() != '') |
        (pd.to_numeric(df['refund_amount'], errors='coerce').fillna(0) > 0)
    )
    df['is_refund'] = mask_refund
    print(f"  is_refund（退款订单）: {mask_refund.sum():,} 行")

    print(f"  清洗后: {len(df)} 行")

    # ID字段去重（order_id + sub_order_id 联合唯一，防止Parquet/xlsx混读产生重复）
    before_dedup = len(df)
    df = df.drop_duplicates(subset=['order_id', 'sub_order_id'], keep='first')
    if len(df) < before_dedup:
        print(f"  去重: {before_dedup - len(df)} 行重复订单")

    # ========================================
    # 数据验收门卫（防止脏数据进入数据库）
    # ========================================
    refund_rate = df['is_refund'].mean()
    goujinjin_rate = df['is_goujinjin'].mean()
    print(f"\n  【数据验收】")
    print(f"    退款率:   {refund_rate:.1%}  （门卫: <25% → {'✅' if refund_rate < 0.25 else '❌ 异常!'}")
    print(f"    购物金率: {goujinjin_rate:.1%}  （门卫: <30% → {'✅' if goujinjin_rate < 0.3 else '❌ 异常!'}'")
    assert refund_rate < 0.25, f"退款率 {refund_rate:.1%} 异常（>25%），ETL 中止，请检查数据源"
    assert goujinjin_rate < 0.3, f"购物金率 {goujinjin_rate:.1%} 异常（>30%），ETL 中止，请检查数据源"
    return df


def init_database():
    """初始化数据库表结构"""
    print("初始化数据库...")

    conn = duckdb.connect(str(DUCKDB_PATH))

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

    conn = duckdb.connect(str(DUCKDB_PATH))

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
        'spu_cosmetic', 'spu_spec', 'channel',
        'is_goujinjin', 'is_refund'
    ]

    # 只保留存在的列，并按数据库表顺序排列
    existing_cols = [c for c in table_columns if c in df.columns]
    df_insert = df[existing_cols].copy()

    # 使用 DuckDB 的 COPY FROM parquet 方式
    # 先写入 parquet 文件，再 COPY 导入
    import tempfile
    import os

    parquet_path = os.path.join(tempfile.gettempdir(), 'orders_temp.parquet')
    df_insert.to_parquet(parquet_path, index=False)

    cols_joined = ', '.join(existing_cols)
    conn.execute(f"COPY orders ({cols_joined}) FROM '{parquet_path}' (FORMAT PARQUET)")

    os.remove(parquet_path)

    count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    print(f"  写入完成，当前订单总数: {count:,}")

    conn.close()


def calculate_daily_metrics():
    """预计算每日指标"""
    print("\n预计算每日指标...")

    conn = duckdb.connect(str(DUCKDB_PATH))
    conn.execute("DELETE FROM daily_metrics")

    # GMV: 全量实付; GSV: 剔除购物金且未退款（口径: is_goujinjin=FALSE AND is_refund=FALSE）
    # TODO: new_user_count 实为"当日去重用户数"，old_user_count/new_user_gmv/old_user_gmv 均硬编码0
    conn.execute("""
        INSERT INTO daily_metrics
        SELECT
            DATE(pay_time) as date,
            COALESCE(SUM(actual_amount), 0) as gmv,
            COALESCE(SUM(CASE WHEN (is_goujinjin = FALSE AND is_refund = FALSE) THEN actual_amount ELSE 0 END), 0) as gsv,
            COUNT(DISTINCT order_id) as order_count,
            COUNT(DISTINCT CASE WHEN (is_goujinjin = FALSE AND is_refund = FALSE) THEN order_id END) as gsv_order_count,
            -- ⚠️ 注意: new_user_count 语义为"当日去重用户数"，非真正新客数，待业务确认后重写
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


@functools.lru_cache(maxsize=1)
def get_db_max_pay_time():
    """
    获取数据库中已有订单的最大付款时间。
    结果缓存：进程内多次调用只查一次数据库。
    """
    if not DUCKDB_PATH.exists():
        return None
    try:
        conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)
        result = conn.execute("SELECT MAX(pay_time) FROM orders").fetchone()[0]
        conn.close()
        return result
    except Exception as e:
        print(f"  [警告] 读取数据库最大付款时间失败: {e}，将执行全量")
        return None


def ensure_database_schema():
    """确保数据库表结构存在（不删除数据）"""
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(DUCKDB_PATH))

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

    conn = duckdb.connect(str(DUCKDB_PATH))

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

    import tempfile
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
            # ── 全新订单：直接追加 ──
            if total_new > 0:
                df_insert = df_new[existing_cols].copy()
                parquet_path = os.path.join(tempfile.gettempdir(), 'orders_new.parquet')
                df_insert.to_parquet(parquet_path, index=False)
                cols_joined = ', '.join(existing_cols)
                conn.execute(f"COPY orders ({cols_joined}) FROM '{parquet_path}' (FORMAT PARQUET)")
                os.remove(parquet_path)
                print(f"  ✅ 全新订单: {total_new:,} 行")

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

                # 2. 显式事务：DELETE + INSERT 原子执行
                conn.execute("BEGIN TRANSACTION")
                try:
                    conn.execute(f"""
                        DELETE FROM orders
                        WHERE order_id IN (SELECT order_id FROM {tmp_table})
                    """)
                    after_delete = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
                    deleted = before_count - after_delete
                    print(f"  🗑️  精确删除待刷新记录: {deleted:,} 行 ({len(refresh_ids):,} 个 order_id)")

                    conn.execute(f"DROP TABLE IF EXISTS {tmp_table}")

                    # 3. 插入刷新数据
                    df_insert = df_refresh[existing_cols].copy()
                    parquet_path = os.path.join(tempfile.gettempdir(), 'orders_refresh.parquet')
                    df_insert.to_parquet(parquet_path, index=False)
                    cols_joined = ', '.join(existing_cols)
                    conn.execute(f"COPY orders ({cols_joined}) FROM '{parquet_path}' (FORMAT PARQUET)")
                    os.remove(parquet_path)
                    print(f"  ✅ 窗口刷新: {total_refresh:,} 行")

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
    import tempfile
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
        success = [r for r in results if r[3] > 0]
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
                               taoke_product_rules=taoke_product_rules)
        if len(refresh_df) > 0:
            refresh_df = clean_data(refresh_df, spu_df, keyword_rules, id_rules,
                                   taoke_order_ids=taoke_order_ids, live_order_ids=live_order_ids,
                                   taoke_product_rules=taoke_product_rules)

        # Step 4: 写入数据库（滑动窗口模式）
        upsert_to_duckdb(new_df, refresh_df, mode=run_mode, window_days=window_days)

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


if __name__ == '__main__':
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
        success = [r for r in results if r[3] > 0]
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

    run_full_etl(mode=mode, window_days=args.window_days)