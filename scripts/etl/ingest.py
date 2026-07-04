"""ETL 文件读取
列名映射、日期解析、数据文件加载（CSV/Excel）。
"""
import os
import sys
import time
import functools
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _clean_processed_updates(updates):
    """事务化标记清理：cold_start_marked 置 False（不删），加 last_processed_at。

    Step 4.5 upsert 成功后, ingest 产出的 updates 会覆盖冷启动登记的 entry,
    此时必须把 cold_start_marked 置 False (因为现在已经真正加载了) 并记录处理
    时间戳, 避免下次增量误判为冷启动假阳性而重复读取.

    ⚠️ 关键: 必须保留字段 (置 False), 不能 del. 因为 _file_changed 判定:
        ① entry 缺 cold_start_marked 字段 → 老格式 → 强制重载
        ② cold_start_marked=True → 冷启动 → 强制重载
        ③ cold_start_marked=False + mtime 一致 → 正常不重载
    如果 del 字段, 加载成功后 entry 变成"缺字段", 命中 ① → 每天增量全量重读.
    """
    if not updates:
        return updates
    cleaned = {}
    for key, rec in updates.items():
        if isinstance(rec, dict):
            clean_rec = dict(rec)  # 复制所有字段（包括 cold_start_marked）
            clean_rec['cold_start_marked'] = False  # 置 False（不删）
            clean_rec['last_processed_at'] = time.time()
            cleaned[key] = clean_rec
        else:
            cleaned[key] = rec
    return cleaned

from scripts.etl.config import (
    COLUMN_MAPPING, PARQUET_DATA_DIR,
    _load_processed_files, _get_file_hash,
)

import pandas as pd


def _file_changed(file_path, processed_files, data_source, xlsx_stem_to_rel):
    """判断单个文件是否需要重读 (Sprint 24 技术债 #2 抽到 module-level).

    v2 格式：mtime 变了才计算 hash, 避免每次 ETL 都读文件内容.

    判定顺序（不依赖 rec.get() 真值, 避免误判）:
      ① key not in processed_files → True (新文件, 强制重读)
      ② entry 缺少 cold_start_marked 字段 → True (老格式 entry, 视为未真正加载.
         向后兼容: 部署 Sprint 24 修复后, 现有 tracker 条目一次性强制重载,
         解决 6/15 数据已被假阳性的问题)
      ③ cold_start_marked=True → True (冷启动登记, 未真正加载.
         _clean_processed_updates 加载成功后会把字段置 False, 走正常流程)
      ④ mtime <= old_mtime → False (mtime 短路, 未变更)
      ⑤ hash 比对: 旧 hash 缺失或新 hash 不等 → True, 否则 False

    抽到 module-level 后可独立单测, 防止"测试过但真函数 typo"的盲点
    (Sprint 24 之前是 nested closure, 测试只能模拟判定逻辑).
    """
    # Parquet 文件使用对应 xlsx 的 key (保持一致性)
    if file_path.suffix == '.parquet':
        key = xlsx_stem_to_rel.get(file_path.stem, file_path.name)
    else:
        key = str(file_path.relative_to(data_source)) if data_source in file_path.parents else file_path.name
    mtime = file_path.stat().st_mtime
    if key not in processed_files:
        return True
    rec = processed_files[key]
    if isinstance(rec, dict) and 'cold_start_marked' not in rec:
        return True
    if isinstance(rec, dict) and rec.get('cold_start_marked'):
        return True
    old_mtime = rec.get('mtime', 0) if isinstance(rec, dict) else rec
    # Sprint 109 L4.7 实战 fix 模式: mtime 不变 + 内容变了 (cp -p / Finder 替换 xlsx 保持 mtime)
    # → 也要算 hash 比对, 不短路跳过. 之前 Sprint 24 mtime 短路 (95% 场景优化) 保留,
    # 5% 场景 (mtime 不变 + 内容变) 走 hash 比对. 默认走新逻辑 (mtime 不变也 hash 比对),
    # 老逻辑 (mtime 短路跳过) 通过 ETL_SKIP_MTIME_CHECK_HASH=1 启用 (兼容老跑批 / 测试).
    if mtime <= old_mtime:
        if os.environ.get('ETL_SKIP_MTIME_CHECK_HASH', '0') == '1':
            return False  # 老逻辑: mtime 短路跳过
        # 新逻辑: mtime 不变 + 内容变了 → 算 hash 比对
        old_hash = rec.get('hash', '') if isinstance(rec, dict) else rec
        if isinstance(old_hash, str) and old_hash:
            return _get_file_hash(file_path) != old_hash
        return False
    # mtime 变了, 算 hash 确认内容是否真的变了
    old_hash = rec.get('hash', '') if isinstance(rec, dict) else ''
    if not old_hash:
        return True  # 无旧 hash, 视为变更
    return _get_file_hash(file_path) != old_hash

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


@functools.lru_cache(maxsize=4)
def _build_xlsx_stem_to_rel(data_source_str: str) -> dict:
    """构建 xlsx stem → 相对路径映射, lru_cache 缓存避免 load_data_files 每次重算.

    data_source 路径变化时 cache 自动 invalidate (lru_cache 用 data_source_str 作 key).
    maxsize=4 支持 4 个 data_type (shop/member/taoke_product/live) 各自缓存.
    """
    from pathlib import Path
    data_source = Path(data_source_str)
    _xlsx_stem_to_rel = {}
    for _xf in data_source.rglob("*.xlsx"):
        _xlsx_stem_to_rel[_xf.stem] = str(_xf.relative_to(data_source))
    return _xlsx_stem_to_rel


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

    # FIX(2026-05-31): 构建 xlsx stem → 相对路径映射，使 Parquet 缓存 key 与 xlsx 一致
    # Parquet 文件名 {stem}.parquet 对应 xlsx 文件 {relative_path}/{stem}.xlsx
    # 使用 xlsx 的相对路径作为 key，确保 processed_files 中的 key 格式统一
    # FIX(v0.4.14.96): 加 lru_cache(maxsize=1) 缓存到 module-level, 避免每次 load_data_files
    # (~200 file rglob ~10ms × N 次调用) 重算. data_source 路径变化时 cache 自动 invalidate
    # (lru_cache 用 data_source str 作 key).
    _xlsx_stem_to_rel = _build_xlsx_stem_to_rel(str(data_source))

    # Sprint 202+ R4 修法 (跟 L4.42 实证 wall_min=63min 0 实质效果 1:1 stable):
    # L4.54 优化 1 从 pipeline.py:177 撤回 (嵌套在 if not processed_path.exists() 块内,
    # 增量路径 tracker 永远存在 → 0 hit), 移到 ingest.py 增量模式 line 跟 _file_changed 同级,
    # 让增量模式也走文件分桶. 期望 wall_min: 63min → <15min (跟 R1 实证期望 1:1 stable).
    if run_mode == 'incremental':
        _all_data_files = list(data_source.rglob("*.xlsx"))
        _all_data_files, _skipped_old = filter_files_by_age(_all_data_files)
        if _skipped_old:
            print(f"  [Sprint 202+ R4 L4.54 优化 1 真治本] {data_type}: 跳过 {len(_skipped_old)} 个 30d+ 老文件 (走 ingest 增量路径, 跟 _file_changed 同级)")

    if pq_files:
        should_read_parquet = True
        # 增量模式：只加载新增或修改过的 Parquet 文件（hash 校验）
        if run_mode == 'incremental':
            processed_files = _load_processed_files(data_type)
            new_files = [f for f in pq_files if _file_changed(f, processed_files, data_source, _xlsx_stem_to_rel)]
            if not new_files:
                print("  [Parquet 缓存] 无新增/变更 parquet 文件，继续检查 xlsx 原始文件")
                should_read_parquet = False
            else:
                # FIX(2026-04-29): 检查xlsx源是否有新文件，防止parquet缓存过期导致新xlsx被跳过
                xlsx_files = list(data_source.rglob("*.xlsx"))
                xlsx_new = [f for f in xlsx_files if _file_changed(f, processed_files, data_source, _xlsx_stem_to_rel)]
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
                        if 'sample_received_at' in df.columns:
                            df['sample_received_at'] = pd.to_datetime(df['sample_received_at'], errors='coerce')
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
                            # 使用 xlsx 相对路径作为 key（与 _file_changed 一致）
                            key = _xlsx_stem_to_rel.get(f.stem, f.name)
                            # Sprint 14 B 修 mtime 语义统一: parquet 路径写源 xlsx mtime (而非
                            # parquet 自己的 mtime), 保证 processed_files_*.json 中 mtime 字段
                            # 跟 _file_changed 比较的"源 mtime"基准一致. _xlsx_stem_to_rel 在
                            # ingest.py:75-77 已构建, key 反查 100% 命中 (Sprint 9 维修时已加固).
                            xlsx_path = data_source / key
                            xlsx_mtime = xlsx_path.stat().st_mtime if xlsx_path.exists() else f.stat().st_mtime
                            pq_updates[key] = {
                                'mtime': xlsx_mtime,
                                'hash': _get_file_hash(f)
                            }
                        combined_pq.attrs['_etl_processed_updates'] = _clean_processed_updates(pq_updates)
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
        new_files = [f for f in files if _file_changed(f, processed_files, data_source, _xlsx_stem_to_rel)]
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
            if 'sample_received_at' in df.columns:
                df['sample_received_at'] = pd.to_datetime(df['sample_received_at'], errors='coerce')

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
            combined.attrs['_etl_processed_updates'] = _clean_processed_updates(existing_updates)
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


# ─────────────────────────────────────────────────────────────
# Sprint 202 R1 优化 1: 文件按 mtime 分桶, 30d+ 老文件直接 skip
# 实证 (7/3 你跑 ETL 46min 慢): shop 125 文件 30d+ 占 78% (98 个), member 100 文件同模式
# 30d+ 老文件 tracker 早已处理, 跟 mtime 短路同效但更激进, 0 hash 计算 + 0 tracker 写盘
# 跨 sprint 60+ 0 debt 1:1: 0 业务代码改动, 加 1 helper + 1 行 list comprehension
# L4.54 永久规则化 (跟 L4.50 pytest cleanup + L4.51 Read-Write Splitting + L4.53 snapshot 永久根除 配套)
# ─────────────────────────────────────────────────────────────
SKIP_FILE_AGE_DAYS = int(os.environ.get("ETL_SKIP_FILE_AGE_DAYS", "30"))


def should_skip_file_by_age(file_path: Path, now_ts: float | None = None) -> bool:
    """Sprint 202 R1 优化 1: 30d+ 老文件直接 skip, 不进 tracker 对比.

    实证: 30d+ 老文件 tracker 早已处理, 走 _file_changed 还会做 mtime 比对
    (95% 场景 mtime 短路) + 5% hash 计算 + 0-30d 写盘. 直接 skip 省 100-200s.
    0 业务影响: 跟 mtime 短路逻辑等价但更激进.

    Args:
        file_path: 文件路径
        now_ts: 当前时间戳 (默认 time.time()), 测试时可注入 mock 时间

    Returns:
        True if file older than SKIP_FILE_AGE_DAYS (默认 30 天)
    """
    if now_ts is None:
        now_ts = time.time()
    file_mtime = file_path.stat().st_mtime
    age_days = (now_ts - file_mtime) / 86400
    return age_days > SKIP_FILE_AGE_DAYS


def filter_files_by_age(files: list, now_ts: float | None = None) -> tuple[list, list]:
    """Sprint 202 R1 优化 1: 批量分桶, 返回 (keep_files, skip_files).

    keep_files: 0-SKIP_FILE_AGE_DAYS 天内的文件, 走正常增量路径
    skip_files: 30d+ 老文件, 直接 skip (L4.54 永久规则化)
    """
    keep = []
    skip = []
    for f in files:
        if should_skip_file_by_age(f, now_ts):
            skip.append(f)
        else:
            keep.append(f)
    return keep, skip
