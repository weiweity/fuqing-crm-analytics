"""ETL 文件读取
列名映射、日期解析、数据文件加载（CSV/Excel）。
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.etl.config import (
    COLUMN_MAPPING, PARQUET_DATA_DIR,
    _load_processed_files, _get_file_hash,
)

import pandas as pd

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
        print("  目录不存在!")
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

    def _file_changed(f, processed_files):
        """v2 格式：mtime 变了才计算 hash，避免每次 ETL 都读文件内容"""
        key = str(f.relative_to(data_source)) if data_source in f.parents else f.name
        mtime = f.stat().st_mtime
        if key not in processed_files:
            return True
        rec = processed_files[key]
        old_mtime = rec.get('mtime', 0) if isinstance(rec, dict) else rec
        if mtime <= old_mtime:
            return False
        # mtime 变了，算 hash 确认内容是否真的变了
        old_hash = rec.get('hash', '') if isinstance(rec, dict) else ''
        if not old_hash:
            return True  # 无旧 hash，视为变更
        return _get_file_hash(f) != old_hash

    if pq_files:
        should_read_parquet = True
        # 增量模式：只加载新增或修改过的 Parquet 文件（hash 校验）
        if run_mode == 'incremental':
            processed_files = _load_processed_files(data_type)
            new_files = [f for f in pq_files if _file_changed(f, processed_files)]
            if not new_files:
                print("  [Parquet 缓存] 无新增/变更 parquet 文件，继续检查 xlsx 原始文件")
                should_read_parquet = False
            else:
                # FIX(2026-04-29): 检查xlsx源是否有新文件，防止parquet缓存过期导致新xlsx被跳过
                xlsx_files = list(data_source.rglob("*.xlsx"))
                xlsx_new = [f for f in xlsx_files if _file_changed(f, processed_files)]
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
                    # 增量模式：计算 hash，但不保存（事务化：写入成功后才标记已处理）
                    pq_updates = {}
                    if run_mode == 'incremental':
                        for f in pq_files:
                            pq_updates[f.name] = {
                                'mtime': f.stat().st_mtime,
                                'hash': _get_file_hash(f)
                            }
                        combined_pq.attrs['_etl_processed_updates'] = pq_updates
                    print(f"  Parquet 数据合计: {len(combined_pq):,} 行")
                    if run_mode == 'incremental':
                        return combined_pq
                    # 全量模式：保留 parquet 数据，继续读 xlsx 补充
                # parquet 读取全部失败，或全量模式继续走 xlsx fallback

    # ———— Fallback：读 xlsx（支持文件级增量，含 mtime 检测）————
    print("  [xlsx fallback] 读取原始文件")
    files = list(data_source.rglob("*.xlsx"))
    print(f"  找到 {len(files)} 个文件")

    # 增量模式：只读新增或修改过的 xlsx 文件（hash 校验，防 mtime 不变但内容变）
    if run_mode == 'incremental':
        processed_files = _load_processed_files(data_type)
        new_files = [f for f in files if _file_changed(f, processed_files)]
        if not new_files:
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

            # 写入 Parquet 缓存（下次 ETL 跳过 xlsx 解析）
            _save_parquet_cache(df, f, data_type)

            all_data.append(df)
            # v2 格式：记录 mtime + hash（但不保存，等 DuckDB 写入成功后再保存）
            processed_new[str(f.relative_to(data_source))] = {
                'mtime': f.stat().st_mtime,
                'hash': _get_file_hash(f)
            }
            print(f"    {f.name}: {len(df)} 行")

        except Exception as e:
            print(f"    跳过({e}): {f.name}")
            continue

    # 增量模式：收集更新但不保存（事务化：DuckDB 写入成功后才标记已处理）
    if run_mode == 'incremental' and processed_new:
        print(f"  [xlsx 增量] 待处理文件: {len(processed_new)} 个（DuckDB 写入成功后标记）")

    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        # 附加待保存的 processed_files 更新（供 pipeline.py 在写入成功后保存）
        if run_mode == 'incremental' and processed_new:
            # 合并 parquet 和 xlsx 的更新（如果之前 parquet 分支没 return）
            existing_updates = getattr(combined, 'attrs', {}).get('_etl_processed_updates', {})
            existing_updates.update(processed_new)
            combined.attrs['_etl_processed_updates'] = existing_updates
        print(f"  数据合计: {len(combined)} 行")
        return combined
    else:
        print("  无有效数据")
        return pd.DataFrame()


def _save_parquet_cache(df, xlsx_path, data_type):
    """将 xlsx 读取后的 DataFrame 存为 Parquet，下次 ETL 直接读 Parquet 跳过 openpyxl。

    写入到 PARQUET_DATA_DIR/<data_type>/<filename>.parquet。
    原子写入：先写 .tmp 再 rename，防止中断产生损坏文件。
    失败不阻塞 ETL，仅打印警告。
    """
    pq_dir = PARQUET_DATA_DIR / data_type
    pq_dir.mkdir(parents=True, exist_ok=True)
    pq_path = pq_dir / f"{xlsx_path.stem}.parquet"
    tmp_path = pq_dir / f"{xlsx_path.stem}.parquet.tmp"
    try:
        df.to_parquet(tmp_path, index=False)
        os.rename(tmp_path, pq_path)
        print(f"    [Parquet 写入] {pq_path.name} ({len(df):,} 行)")
    except Exception as e:
        # 清理临时文件
        if tmp_path.exists():
            tmp_path.unlink()
        print(f"    [Parquet 写入失败] {pq_path.name}: {e}")
