"""ETL 数据源加载
加载 SPU 映射、渠道规则、淘客订单号、直播订单号等外部数据源。
"""
import sys
import hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.etl.config import (
    SPU_MAPPING_SOURCE, CHANNEL_RULES_SOURCE,
    TAOKE_DATA_SOURCE, TAOKE_PRODUCT_SOURCE, LIVE_DATA_SOURCE,
    TAOKE_COL,
    _load_taoke_cache, _save_taoke_cache,
    _load_live_cache, _save_live_cache,
    _load_set_pickle, _save_set_pickle,
    _ETL_SOURCE_STATS,
)

import os
import pandas as pd


def _check_source(path, *, label=""):
    """检查 ETL 数据源路径是否存在，严格模式下抛错。

    默认严格模式：文件缺失 → raise FileNotFoundError。
    宽容模式（FQ_ETL_LENIENT_LOAD=1）：文件缺失 → 打印警告并返回 False。
    """
    lenient = os.environ.get("FQ_ETL_LENIENT_LOAD") == "1"
    if not path.exists():
        msg = f"ETL 数据源缺失{' (' + label + ')' if label else ''}: {path}"
        if lenient:
            print(f"  ⚠️ {msg}（宽容模式，继续）")
            return False
        raise FileNotFoundError(msg)
    return True


_TAOKE_ORDER_IDS_CACHE = None  # 全局缓存，避免重复加载
_LIVE_ORDER_IDS_CACHE = None
_TAOKE_PRODUCT_RULES_CACHE = None  # 需与 config.py 保持同步

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

        # 计算 spu_hash：每行 SPU 映射的版本指纹
        # 用于增量 ETL 时检测映射是否变化，自动触发重匹配
        hash_cols = ['product_id', 'spu_category', 'spu_type', 'spu_tier',
                     'spu_product_class', 'spu_product_subclass', 'spu_start_date', 'spu_end_date']
        def _row_hash(row):
            parts = []
            for c in hash_cols:
                v = row.get(c, '')
                parts.append(str(v) if pd.notna(v) else '')
            return hashlib.md5('|'.join(parts).encode()).hexdigest()[:16]

        df['spu_hash'] = df.apply(_row_hash, axis=1)
        print(f"  spu_hash 已计算（{df['spu_hash'].nunique()} 个唯一值）")

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
    if not _check_source(channel_file, label="渠道判定规则"):
        return [], []

    try:
        # 多编码尝试
        for enc in ['utf-8', 'gbk', 'gb2312']:
            try:
                df = pd.read_csv(channel_file, encoding=enc)
                print(f"  渠道判定编码: {enc}")
                break
            except Exception:
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
    增加 pickle 缓存：所有文件 mtime 未变时直接加载 pickle set，跳过 set 重建。
    """
    global _TAOKE_ORDER_IDS_CACHE, _ETL_SOURCE_STATS
    if _TAOKE_ORDER_IDS_CACHE is not None:
        return _TAOKE_ORDER_IDS_CACHE

    print("\n加载淘客数据库...")
    if not _check_source(TAOKE_DATA_SOURCE, label="淘客数据库"):
        _TAOKE_ORDER_IDS_CACHE = set()
        return _TAOKE_ORDER_IDS_CACHE

    files = list(TAOKE_DATA_SOURCE.glob("*"))
    # 过滤出支持的文件类型
    files = [f for f in files if f.suffix.lower() in ('.csv', '.xlsx', '.xls')]
    print(f"  找到 {len(files)} 个文件")

    # O1 优化: pickle 缓存 — 所有文件 mtime 未变时直接加载 set
    file_fingerprint = '|'.join(f"{f.name}:{f.stat().st_mtime}" for f in sorted(files, key=lambda x: x.name))
    cached_set, cached_fp = _load_set_pickle('taoke')
    if cached_set is not None and cached_fp == file_fingerprint:
        print(f"  [缓存] pickle 命中，直接加载 {len(cached_set):,} 条 (跳过 set 重建)")
        _TAOKE_ORDER_IDS_CACHE = cached_set
        _ETL_SOURCE_STATS['taoke'] = {
            'files': len(files), 'reloaded': 0, 'skipped': len(files),
            'total_ids': len(cached_set),
        }
        return cached_set

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

    # O1 优化: 保存 pickle 缓存（set 对象直接序列化，下次免重建）
    if all_ids:
        _save_set_pickle('taoke', all_ids, file_fingerprint)
        print(f"  [缓存] pickle 已保存 ({len(all_ids):,} 条)")

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
    增加 pickle 缓存：所有文件 mtime 未变时直接加载 pickle set，跳过 set 重建。
    """
    global _LIVE_ORDER_IDS_CACHE, _ETL_SOURCE_STATS
    if _LIVE_ORDER_IDS_CACHE is not None:
        return _LIVE_ORDER_IDS_CACHE

    print("\n加载直播间数据源...")
    if not _check_source(LIVE_DATA_SOURCE, label="直播间数据源"):
        _LIVE_ORDER_IDS_CACHE = set()
        _ETL_SOURCE_STATS['live'] = {'files': 0, 'reloaded': 0, 'skipped': 0, 'total_ids': 0}
        return _LIVE_ORDER_IDS_CACHE

    csv_files = list(LIVE_DATA_SOURCE.glob("*.csv"))
    xlsx_files = list(LIVE_DATA_SOURCE.glob("*.xlsx"))
    files = csv_files + xlsx_files
    print(f"  找到 {len(csv_files)} 个 CSV 文件, {len(xlsx_files)} 个 XLSX 文件")

    # O1 优化: pickle 缓存 — 所有文件 mtime 未变时直接加载 set
    file_fingerprint = '|'.join(f"{f.name}:{f.stat().st_mtime}" for f in sorted(files, key=lambda x: x.name))
    cached_set, cached_fp = _load_set_pickle('live')
    if cached_set is not None and cached_fp == file_fingerprint:
        print(f"  [缓存] pickle 命中，直接加载 {len(cached_set):,} 条 (跳过 set 重建)")
        _LIVE_ORDER_IDS_CACHE = cached_set
        _ETL_SOURCE_STATS['live'] = {
            'files': len(files), 'reloaded': 0, 'skipped': len(files),
            'total_ids': len(cached_set),
        }
        return cached_set

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

    # O1 优化: 保存 pickle 缓存（set 对象直接序列化，下次免重建）
    if all_ids:
        _save_set_pickle('live', all_ids, file_fingerprint)
        print(f"  [缓存] pickle 已保存 ({len(all_ids):,} 条)")

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
    if not _check_source(TAOKE_PRODUCT_SOURCE, label="淘客商品ID表"):
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
