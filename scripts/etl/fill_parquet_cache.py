#!/usr/bin/env python3
"""Parquet 缓存填充脚本
遍历所有 xlsx 文件，逐个读取后存为 Parquet 缓存。

用法:
    PYTHONPATH="$(pwd)" /Users/hutou/homebrew/bin/python3 scripts/etl/fill_parquet_cache.py
    PYTHONPATH="$(pwd)" /Users/hutou/homebrew/bin/python3 scripts/etl/fill_parquet_cache.py --data-type shop
    PYTHONPATH="$(pwd)" /Users/hutou/homebrew/bin/python3 scripts/etl/fill_parquet_cache.py --force
"""
import os
import sys
import gc
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.etl.config import (
    SHOP_DATA_SOURCE, MEMBER_DATA_SOURCE, PARQUET_DATA_DIR,
    _load_processed_files, _save_processed_files, _get_file_hash,
)
from scripts.etl.ingest import rename_columns

import pandas as pd


def fill_parquet_cache(data_source, data_type, force=False):
    """遍历 xlsx 文件，转换为 Parquet 缓存。"""
    xlsx_files = list(data_source.rglob("*.xlsx"))
    print(f"[{data_type}] 找到 {len(xlsx_files)} 个 xlsx 文件")

    pq_dir = PARQUET_DATA_DIR / data_type
    pq_dir.mkdir(parents=True, exist_ok=True)

    # 清理残留的 .parquet.tmp 文件（上次中断可能留下）
    tmp_cleaned = 0
    for tmp in pq_dir.glob("*.parquet.tmp"):
        tmp.unlink()
        tmp_cleaned += 1
    if tmp_cleaned:
        print(f"  清理残留临时文件: {tmp_cleaned} 个")

    # 加载 processed_files 用于增量检测（与 ingest.py 逻辑一致）
    processed_files = _load_processed_files(data_type) if not force else {}

    converted = 0
    skipped = 0
    errors = 0
    processed_updates = {}

    for i, f in enumerate(xlsx_files):
        pq_path = pq_dir / f"{f.stem}.parquet"
        key = str(f.relative_to(data_source))

        # 增量检测：mtime + hash（与 ingest.py _file_changed() 逻辑一致）
        if not force and pq_path.exists():
            mtime = f.stat().st_mtime
            if key in processed_files:
                rec = processed_files[key]
                old_mtime = rec.get('mtime', 0) if isinstance(rec, dict) else rec
                if mtime <= old_mtime:
                    skipped += 1
                    continue
                # mtime 变了，算 hash 确认内容是否真的变了
                old_hash = rec.get('hash', '') if isinstance(rec, dict) else ''
                if old_hash and _get_file_hash(f) == old_hash:
                    skipped += 1
                    continue

        try:
            # 读取 + 预处理（与 ingest.py 第 180-200 行一致）
            df = pd.read_excel(f, engine='openpyxl', header=0)
            df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]
            df = rename_columns(df)

            if 'order_id' not in df.columns and '订单编号' not in df.columns:
                print(f"  跳过(无订单列): {f.name}")
                errors += 1
                continue

            # 强制 datetime 解析（确保 order_time 列类型一致）
            if 'order_time' in df.columns:
                df['order_time'] = pd.to_datetime(df['order_time'], errors='coerce')
                df['year'] = df['order_time'].dt.year
                df['month'] = df['order_time'].dt.month

            # 原子写入（先写临时文件，再 rename）
            tmp_path = pq_dir / f"{f.stem}.parquet.tmp"
            df.to_parquet(tmp_path, index=False)
            os.rename(tmp_path, pq_path)

            # 记录 processed_files 更新（与 ingest.py 行为一致）
            processed_updates[key] = {
                'mtime': f.stat().st_mtime,
                'hash': _get_file_hash(f)
            }

            converted += 1
            print(f"  [{i+1}/{len(xlsx_files)}] {f.name}: {len(df):,} 行")
            del df
            gc.collect()  # 强制释放内存

        except Exception as e:
            print(f"  跳过({e}): {f.name}")
            errors += 1
            continue

    # 保存 processed_files（与 ingest.py 事务化逻辑一致：写入成功后才标记）
    if processed_updates:
        _save_processed_files(data_type, processed_updates)
        print(f"  更新 processed_files: {len(processed_updates)} 个文件")

    print(f"\n[{data_type}] 完成: 转换 {converted}, 跳过 {skipped}, 错误 {errors}")
    return converted, skipped, errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parquet 缓存填充脚本")
    parser.add_argument("--data-type", choices=["shop", "member", "all"], default="all")
    parser.add_argument("--force", action="store_true", help="忽略 mtime，强制重新转换")
    args = parser.parse_args()

    total_converted = 0
    total_skipped = 0
    total_errors = 0

    if args.data_type in ("shop", "all"):
        c, s, e = fill_parquet_cache(SHOP_DATA_SOURCE, "shop", args.force)
        total_converted += c
        total_skipped += s
        total_errors += e

    if args.data_type in ("member", "all"):
        c, s, e = fill_parquet_cache(MEMBER_DATA_SOURCE, "member", args.force)
        total_converted += c
        total_skipped += s
        total_errors += e

    print(f"\n{'='*50}")
    print(f"总计: 转换 {total_converted}, 跳过 {total_skipped}, 错误 {total_errors}")
