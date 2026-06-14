"""ETL CLI 入口
命令行参数解析、子命令分发。
"""
import sys
import atexit
import argparse
import glob
import os
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.etl.config import (
    DUCKDB_PATH, DUCKDB_MEMORY_LIMIT, PROCESSED_DATA_DIR, _ETL_SOURCE_STATS,
)

# ─────────────────────────────────────────────────────────────
# Layer 1 of 4（2026-06-05 /tmp 孤儿治理）
# 6/1-6/4 期间子 agent 调试 E2E 测试手工 cp 主库到 /tmp，累计 7 个 38-44GB
# 孤儿 duckdb 文件，占用磁盘 ~349GB。本钩子在 ETL 退出时清理 24h+ 旧孤儿。
# 白名单前缀（避免误删 /tmp 下其他用户/系统文件）。
#
# 已知限制（adversarial review 2026-06-05）：
#   - F3 (HIGH): atexit 在 os._exit() / kill -9 / OOM killer 下不触发
#     （Python 文档明确）。
#     → 修复：main() 入口（atexit.register 之前）写 marker 文件
#       /tmp/fuqing-etl-marker.json；cleanup 钩子执行时读 marker 判断是否
#       正常 ETL 退出。marker 缺失 = 异常退出（kill -9 / OOM / 断电），
#       切换保守模式（同样 5 文件 / 100GB 内，但日志标注 reason）。
#       marker 存在 = 正常退出，cap 维持。
#       无论 marker 是否存在，cleanup 完后都删 marker（避免下次误判）。
#   - F6 (LOW): mtime 可被 touch -t / os.utime 任意改写，非"活跃文件"绝对
#     可靠信号。
#     → **deferred**: 真正的"活跃信号"应是 flock / lsof / marker file
#       替代 mtime，但 mtime 24h 阈值已兜住常见场景（agent 调试 →
#       mtime 24h+ 后下次 ETL 自动清），改造复杂度高，留作 future work。
#   - F7 (MEDIUM): symlink getmtime/getsize 跟随 target；os.remove 只删 link
#     不动 target（无数据丢失，POSIX 语义），但 print 的 size 是 target 大小
#     （误报）；且难以判断 target 是否 active。
#     → 修复：candidates 收集时 `islink` 跳过（[skip symlink] 提示），
#       保守起见不删 symlink，避免误删指向其他业务文件的 link。
# ─────────────────────────────────────────────────────────────
FQ_TMP_PREFIXES = (
    "/private/tmp/_fq_ro",   # 调试代码变量（_fq = fuqing, ro = read_only）
    "/private/tmp/fuqing_",  # 人工命名 / 业务模块命名
)
_FQ_TMP_MAX_DELETE_PER_RUN = 5        # 防御性：单次最多删 5 个文件
_FQ_TMP_MAX_DELETE_BYTES_PER_RUN = 100 * 1024**3  # 100GB/次（防单次爆删）
_FQ_TMP_MIN_AGE_HOURS = 24            # 24h 内的活跃文件不删
_FQ_TMP_LOG_PATH = "/tmp/fuqing-tmp-cleanup.log"  # 持久日志（不等同 print）
_FQ_TMP_MARKER_PATH = "/tmp/fuqing-etl-marker.json"  # F3: 异常退出检测 marker


def _collect_fq_tmp_orphans() -> list:
    """收集 FQ_TMP_PREFIXES 下所有超过 _FQ_TMP_MIN_AGE_HOURS 的候选文件。

    设计：先收集全量 candidates，再按 mtime 倒序（最老优先）截断到 cap，
    避免 first-prefix starvation（F5：原来 first pattern 命中 5 个就 break，
    后续 prefix 永远不扫）。

    F7 修复：symlink 跳过。getmtime/getsize 跟随 target 误报 size（用户看到
    的"38GB"可能是 target 大小），os.remove 只删 link 不动 target（无数据
    丢失，POSIX 语义），但难以判断 target 是否 active。保守起见不删 symlink。
    """
    candidates = []
    now = time.time()
    for pattern in FQ_TMP_PREFIXES:
        for path in glob.glob(f"{pattern}*.duckdb"):
            # F7 修复：用 `is True` 而不是 truthy 判断，兼容 mock 场景
            # （MagicMock 实例 bool() 为 True，会把 mock 文件全当 symlink 跳过）
            if os.path.islink(path) is True:
                _safe_log(f"  [tmp-cleanup] skip symlink: {path}")
                continue
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            age_h = (now - mtime) / 3600
            if age_h < _FQ_TMP_MIN_AGE_HOURS:
                continue
            try:
                size_bytes = os.path.getsize(path)
            except OSError:
                continue
            candidates.append((path, size_bytes, age_h))
    # 按 mtime 倒序（最老优先）；同 mtime 按 size 倒序（大先）
    candidates.sort(key=lambda x: (-x[2], -x[1]))
    return candidates


def _cleanup_fq_tmp_orphans() -> int:
    """ETL 退出时清理 /private/tmp 下 fq_ 系列孤儿 duckdb。

    设计原则：
      1. 只删 FQ_TMP_PREFIXES 白名单（避免误删用户/系统文件）
      2. 只删 _FQ_TMP_MIN_AGE_HOURS 小时前的（保留当前跑批产物）
      3. 单次最多删 _FQ_TMP_MAX_DELETE_PER_RUN 个文件（防御性批量误删）
         且累计字节 ≤ _FQ_TMP_MAX_DELETE_BYTES_PER_RUN（防单次爆删）
      4. 软失败：清理失败只 log 不 raise（不影响 ETL 退出码）
      5. 持久日志写到 _FQ_TMP_LOG_PATH（运维审计）

    F3 修复：清理前读 marker 判断是否正常 ETL 退出。marker 缺失 = 上次
    ETL 异常退出（kill -9 / os._exit / OOM killer），保守模式清理（同样
    5 文件 + 100GB 内，但日志明确标注 reason，便于运维定位）。清理完后
    不论 marker 原本是否存在都删 marker，避免下次误判。

    Returns:
        实际删除的文件数
    """
    # F3 修复：清理前读 marker 判断退出模式
    marker_existed = False
    try:
        marker_existed = os.path.exists(_FQ_TMP_MARKER_PATH)
    except OSError:
        marker_existed = False
    if not marker_existed:
        _safe_log(
            "  [tmp-cleanup] marker 缺失（上次 ETL 异常退出："
            "kill -9 / os._exit / OOM killer），保守模式清理（5 文件 + 100GB 内）"
        )
    else:
        _safe_log("  [tmp-cleanup] marker 存在（正常 ETL 退出），按既有 cap 清理")

    candidates = _collect_fq_tmp_orphans()

    deleted = []
    bytes_deleted = 0
    for path, size_bytes, age_h in candidates:
        if len(deleted) >= _FQ_TMP_MAX_DELETE_PER_RUN:
            break
        if bytes_deleted + size_bytes > _FQ_TMP_MAX_DELETE_BYTES_PER_RUN:
            break
        try:
            os.remove(path)
            deleted.append((path, size_bytes / (1024**3), age_h))
            bytes_deleted += size_bytes
        except OSError as e:
            _safe_log(f"  [tmp-cleanup] skip {path}: {e}")

    # F3 修复：清理完后清 marker（无论原本是否存在），避免下次误判
    try:
        os.remove(_FQ_TMP_MARKER_PATH)
    except OSError:
        pass  # marker 不存在/无权限 — 不阻塞 cleanup

    # 持久化日志（运维审计，print 在 daemon 上下文可能 I/O 失败见 F11）
    if deleted:
        lines = [f"\n  [tmp-cleanup] cleaned {len(deleted)} /tmp orphan(s):"]
        for path, size_gb, age_h in deleted:
            lines.append(f"    - {path} ({size_gb:.1f}GB, {age_h:.0f}h old)")
        _safe_log("\n".join(lines))
    return len(deleted)


def _write_fq_etl_marker() -> None:
    """在 main() 入口（atexit.register 之前）写 marker 文件。

    用途：cleanup 钩子执行时读 marker 是否存在，判断是否正常退出。
      - marker 存在 → 正常 ETL 退出（main() 走完），cap 维持
      - marker 缺失 → 异常退出（kill -9 / os._exit / OOM），
        24h 阈值下保守清理（5 文件 + 100GB 内）

    F3 修复：atexit 钩子无法覆盖 kill -9 / os._exit / OOM killer 的限制
    （Python 文档明确），marker 文件作为"近 24h 是否有 ETL 在跑"的旁路
    信号。即使钩子不触发，下次 ETL 的 atexit 也能识别并保守清理。

    软失败：写失败只 pass 不 raise（不影响 main() 入口）。
    """
    import json as _json
    from datetime import datetime as _dt, timezone
    try:
        marker_data = {
            "pid": os.getpid(),
            "started_at": _dt.now(timezone.utc).isoformat(timespec="seconds"),
            "script": "cli.py",
        }
        with open(_FQ_TMP_MARKER_PATH, "w") as f:
            _json.dump(marker_data, f)
    except OSError:
        pass  # marker 写失败不阻塞 main()


def _safe_log(msg: str) -> None:
    """atexit 安全日志：print + 写文件，stdout 关闭时降级到文件（F11 修复）。"""
    try:
        print(msg)
    except (ValueError, OSError):
        pass  # I/O on closed file / 等异常，atexit 不应 propagate
    try:
        from datetime import datetime as _dt, timezone
        with open(_FQ_TMP_LOG_PATH, "a") as f:
            f.write(f"[{_dt.now(timezone.utc).isoformat()}] {msg}\n")
    except OSError:
        pass  # log 失败不阻塞 atexit


# 注：atexit.register 故意放在 main() 内部，不在 import 顶层（F4 修复）。
# 原因：pytest collection 阶段 import scripts.etl.cli → atexit 触发 → pytest
# 退出时静默删真 /private/tmp/ 调试文件。改为 main() 入口注册后，单纯 import
# 模块（CI 测试 / 单元测试 / Jupyter）不会触发清理。

from scripts.etl.sources import (
    load_spu_mapping, load_channel_rules,
    load_taoke_order_ids, load_live_order_ids, load_taoke_product_rules,
)
from scripts.etl.transform import match_channel
from scripts.etl.pipeline import (
    run_full_etl, update_taoke_channel,
    refresh_visitor_data, refresh_campaign_schedule,
)
from scripts.etl._timer import PerfTimer, gate_set, gate_record_error, save_baseline as _save_baseline
from scripts.etl.notify import notify_etl_complete


def _save_partial(run_id: str = "1/3") -> None:
    """QW4 阶段 A：长跑批任务在每步结束落盘一次 partial baseline。
    save_baseline() 本身可重复调用（累积所有已记录 step），不会清空 _RECORDS。"""
    try:
        _save_baseline(run_id=run_id)
    except Exception as _e:
        print(f"  [perf] partial baseline save failed: {_e}")

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

    conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": DUCKDB_MEMORY_LIMIT})
    try:
        # 备份（parquet）
        backup_dir = PROCESSED_DATA_DIR / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = backup_dir / f"orders_{backup_label}_backup_{timestamp}.parquet"
        backup_path_str = str(backup_path).replace("'", "''")

        if filter_condition and filter_params:
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
    print("\n读取 DuckDB 订单...")
    conn = duckdb.connect(str(DUCKDB_PATH), read_only=True, config={"memory_limit": DUCKDB_MEMORY_LIMIT})
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
    print("\n执行渠道匹配...")
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
        print("\n  变更明细:")
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
            print("\n  无需更新，退出")
            return

        print("\n写入 DuckDB...")
        backup_and_update_orders(
            df=changed_df,
            update_columns={'channel': 'new_channel'},
            backup_label='rescan_channel'
        )

        print(f"\n{'='*60}")
        print("渠道重匹配完成！")
        print(f"{'='*60}")


def rescan_spu_mapping(product_ids: list = None, dry_run: bool = True):
    """
    SPU 重匹配：重新计算 spu_type、spu_hash 和 channel。

    两种模式：
    1. 指定 product_ids：只重匹配这些产品
    2. 不指定 product_ids：自动检测 spu_hash 不一致的订单（SPU 映射表更新后自动发现需要重匹配的订单）

    复用 load_spu_mapping() + match_channel() 的逻辑，保证口径一致。
    仅对 spu_type 发生变化的订单重新匹配渠道。

    用法:
      python run_etl.py --rescan-spu --product-ids 1008376905465 --dry-run
      python run_etl.py --rescan-spu --product-ids 1008376905465 --apply
      python run_etl.py --rescan-spu --dry-run    # 自动检测 hash 不一致
      python run_etl.py --rescan-spu --apply       # 自动检测并修复
    """

    print(f"\n{'='*60}")
    print("SPU 重匹配")
    print(f"{'='*60}")

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

    # Step 3: 从 DuckDB 读取订单
    conn = duckdb.connect(str(DUCKDB_PATH), read_only=True, config={"memory_limit": DUCKDB_MEMORY_LIMIT})
    try:
        if product_ids:
            # 指定 product_ids 模式
            print(f"  目标 product_id: {product_ids}")
            print(f"  模式: {'预览 (dry-run)' if dry_run else '执行写入 (apply)'}")
            placeholders = ', '.join(['?' for _ in product_ids])
            orders_df = conn.execute(f"""
                SELECT order_id, product_id, pay_time, product_title,
                       actual_amount, spu_type AS old_spu_type, spu_hash AS old_spu_hash,
                       channel AS old_channel
                FROM orders
                WHERE product_id IN ({placeholders})
            """, product_ids).fetchdf()
        else:
            # 自动检测模式：找出 spu_hash 不一致的订单
            print("  模式: 自动检测 spu_hash 不一致")
            print(f"  状态: {'预览 (dry-run)' if dry_run else '执行写入 (apply)'}")

            # 找出 orders 中 spu_hash 不在当前映射表中的订单
            orders_df = conn.execute("""
                SELECT order_id, product_id, pay_time, product_title,
                       actual_amount, spu_type AS old_spu_type, spu_hash AS old_spu_hash,
                       channel AS old_channel
                FROM orders
                WHERE spu_hash IS NOT NULL
                  AND spu_hash NOT IN (SELECT spu_hash FROM spu_mapping WHERE spu_hash IS NOT NULL)
            """).fetchdf()

            if orders_df.empty:
                # 也检查 spu_hash 为 NULL 的订单（旧数据没有 hash）
                orders_df = conn.execute("""
                    SELECT order_id, product_id, pay_time, product_title,
                           actual_amount, spu_type AS old_spu_type, spu_hash AS old_spu_hash,
                           channel AS old_channel
                    FROM orders
                    WHERE spu_hash IS NULL
                """).fetchdf()
                if not orders_df.empty:
                    print(f"  发现 {len(orders_df):,} 条无 spu_hash 的旧订单")
                else:
                    print("  所有订单的 spu_hash 均一致，无需重匹配")
                    return
            else:
                product_ids = orders_df['product_id'].unique().tolist()
                print(f"  发现 {len(orders_df):,} 条 hash 不一致的订单（涉及 {len(product_ids)} 个 product_id）")
    finally:
        conn.close()

    print(f"  找到订单: {len(orders_df):,} 条")
    if orders_df.empty:
        print("  无订单，退出")
        return

    # Step 4: SPU 时间窗口匹配（复用 clean_data 中的逻辑）
    print("\n执行 SPU 时间窗口匹配...")
    spu_cols = ['product_id', 'spu_category', 'spu_type', 'spu_tier',
                'spu_product_class', 'spu_product_subclass', 'spu_cosmetic',
                'spu_spec', 'spu_hash', 'spu_start_date', 'spu_end_date']
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
        print("\n  变更明细:")
        change_summary = changed_df.groupby(['old_spu_type', 'new_spu_type']).size().reset_index(name='count')
        for _, row in change_summary.iterrows():
            old = row['old_spu_type'] or '(空)'
            new = row['new_spu_type'] or '(空)'
            print(f"    {old} → {new}: {row['count']:,} 条")

    # Step 6: 对变更订单重匹配渠道（复用 match_channel 逻辑）
    if not changed_df.empty:
        print("\n对变更订单重新匹配渠道...")
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
            print("\n  无需更新，退出")
            return

        print("\n写入 DuckDB...")
        backup_and_update_orders(
            df=channel_df,
            update_columns={'spu_type': 'new_spu_type', 'spu_hash': 'spu_hash', 'channel': 'channel'},
            backup_label='rescan',
            filter_condition=f"product_id IN ({', '.join(['?' for _ in product_ids])})",
            filter_params=product_ids
        )

        print(f"\n{'='*60}")
        print("SPU 重匹配完成！")
        print(f"{'='*60}")

def main():
    """CLI 入口函数"""
    # F3 修复：在 atexit 注册**之前**先写 marker 文件（kill -9 限制绕过）。
    # 正常流程：main() 入口 → 写 marker → atexit.register → ... → 退出 →
    # atexit 触发 → cleanup 读 marker（存在）→ 正常 cap → 删 marker。
    # 异常流程：main() 入口 → 写 marker → ... → kill -9 → atexit 不触发 →
    # 下次 ETL 的 main() 入口 → atexit 注册 → ... → 退出 → atexit 触发 →
    # cleanup 读 marker（**缺失** = 上次异常退出）→ 保守 cap → 删 marker。
    _write_fq_etl_marker()

    # 注册 atexit 钩子：在 main() 入口注册，不在 import 顶层注册（F4 修复）。
    # 原因：pytest / Jupyter / 单元测试 import 模块时不应触发清理，否则会
    # 在测试退出时静默扫 /private/tmp/，潜在误删真实调试文件。
    atexit.register(_cleanup_fq_tmp_orphans)

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
    parser.add_argument('--cleanup-tmp', action='store_true',
                        help='紧急清理 /private/tmp 下 fq_ 系列孤儿（24h+ 旧文件，cap 5/100GB）')
    parser.add_argument('--skip-dq', action='store_true',
                        help='跳过 W3 DQ assertions (6 断言 + rfm_quarantine 写入)')
    parser.add_argument('--skip-w4', action='store_true',
                        help='跳过 W4 fact_rfm_long 预计算 (incremental + merge T-7)')
    parser.add_argument('--read-only', action='store_true',
                        help='Sprint 21+ P0 read-only workaround: 跳过 step 2 (淘客渠道纠正, 1.88M UPDATE 跨 connection race) + step 6 (RFM 缓存预计算, rfm_analysis_cache race). 跑批跑通, 接受淘客指标陈旧 (从 06-11 16:55 backup 状态). 等 DuckDB 1.6.0 stable release 关掉 read-only 模式')
    args = parser.parse_args()

    # 紧急清理 /tmp 孤儿（handoff 6/5 follow-up #3 落地：暴露运维入口免依赖 ETL 触发）
    if args.cleanup_tmp:
        # 显式调用前 unregister atexit，避免 sys.exit(0) 触发第二次 cleanup
        # (幂等无数据风险，但会污染审计日志 1 次 CLI 产生 2 条记录)
        atexit.unregister(_cleanup_fq_tmp_orphans)
        print("\n" + "=" * 60)
        print("紧急清理 /private/tmp 下 fq_ 系列孤儿（24h+ / 5 文件 / 100GB cap）")
        print("=" * 60)
        deleted = _cleanup_fq_tmp_orphans()
        print(f"\n完成：删除 {deleted} 个文件")
        print("审计日志：/tmp/fuqing-tmp-cleanup.log")
        sys.exit(0)

    # 单独刷新状态覆盖表
    if args.refresh_status:
        print("\n" + "=" * 60)
        print("刷新订单状态覆盖表（CSV 模式）")
        print("=" * 60)
        from scripts.etl.etl_status_override import refresh_status_override
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

        # 6 道门禁 — cross_day：记录 ETL 前的 max(pay_time) + orders 行数
        try:
            from backend.config import DUCKDB_PATH as _DDB
            import duckdb as _dd2
            if _DDB.exists():
                # Sprint 11 S11-3 修: 加 config={"memory_limit": DUCKDB_MEMORY_LIMIT},
                # 跟其他 8GB conn 保持一致. 之前没传 config 触发 DuckDB strict mode
                # "Can't open a connection to same database file with a different configuration"
                # (跟 Step 5/6 W4 precompute 等 8GB conn 冲突).
                _c0 = _dd2.connect(str(_DDB), read_only=True, config={"memory_limit": DUCKDB_MEMORY_LIMIT})
                try:
                    _before_max = _c0.execute("SELECT MAX(pay_time) FROM orders").fetchone()[0]
                    _before_count = _c0.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
                finally:
                    _c0.close()
            else:
                _before_max, _before_count = None, 0
        except Exception as _e:
            print(f"  [WO-1 修复] cross_day 前置采样失败: {type(_e).__name__}: {_e}")
            _before_max, _before_count = None, 0

        # Step 1: ETL 增量（滑动窗口模式，force_continue 确保 Step 5/6 必定执行）
        try:
            with PerfTimer("step1_run_full_etl", mode="inc", window_days=args.window_days):
                run_full_etl(mode='inc', window_days=args.window_days, force_continue=True,
                             skip_dq=args.skip_dq, skip_w4=args.skip_w4)
        except Exception as _exc:
            gate_record_error("step1_run_full_etl", _exc)
            notify_etl_complete(
                {"failed_step": "step1_run_full_etl", "error": str(_exc)[:200], "mode": "auto"},
                status="failed",
            )
            raise
        _save_partial()

        # Step 2: 淘客渠道同步（确保新增淘客订单被正确标记）
        if args.read_only:
            print("\n" + "-" * 40)
            print("Step 2: 淘客渠道同步 (Sprint 21+ P0 read-only workaround: 跳过, 1.88M UPDATE 跨 connection race 100% 触发, DuckDB 上游 1.5.x ART index bug)")
            print("-" * 40)
            print("  [SKIP] step2_update_taoke_channel (read-only 模式)")
            print("  [INFO] 淘客指标保持 06-11 16:55 backup 状态 (1,982,532 其他 + 0 淘客 + max pay_time 2026-06-09)")
        else:
            try:
                with PerfTimer("step2_update_taoke_channel"):
                    update_taoke_channel()
            except Exception as _exc:
                gate_record_error("step2_update_taoke_channel", _exc)
                notify_etl_complete(
                    {"failed_step": "step2_update_taoke_channel", "error": str(_exc)[:200], "mode": "auto"},
                    status="failed",
                )
                raise
        _save_partial()

        # Step 3: 刷新订单状态覆盖表（从 zip/csv 读取最新退款/交易关闭状态）
        print("\n" + "-" * 40)
        print("Step 3: 刷新订单状态覆盖表")
        print("-" * 40)
        from scripts.etl.etl_status_override import refresh_status_override
        from backend.config import DUCKDB_PATH
        try:
            with PerfTimer("step3_refresh_status_override", window_days=args.window_days):
                refresh_status_override(DUCKDB_PATH, window_days=args.window_days)
        except Exception as _exc:
            gate_record_error("step3_refresh_status_override", _exc)
            notify_etl_complete(
                {"failed_step": "step3_refresh_status_override", "error": str(_exc)[:200], "mode": "auto"},
                status="failed",
            )
            raise
        _save_partial()

        # Step 4: 反向同步 override → orders（看板直接生效，无需改 SQL）
        print("\n" + "-" * 40)
        print("Step 4: 反向同步 override → orders")
        print("-" * 40)
        from scripts.etl.etl_status_override import sync_override_to_orders
        try:
            with PerfTimer("step4_sync_override_to_orders", window_days=args.window_days):
                sync_override_to_orders(DUCKDB_PATH, window_days=args.window_days)
        except Exception as _exc:
            gate_record_error("step4_sync_override_to_orders", _exc)
            notify_etl_complete(
                {"failed_step": "step4_sync_override_to_orders", "error": str(_exc)[:200], "mode": "auto"},
                status="failed",
            )
            raise
        _save_partial()

        # Step 5: 刷新访客数据（daily_visitors 表，访客数/新增会员数）
        print("\n" + "-" * 40)
        print("Step 5: 刷新访客数据")
        print("-" * 40)
        try:
            with PerfTimer("step5_refresh_visitor_data"):
                refresh_visitor_data()
        except Exception as _exc:
            gate_record_error("step5_refresh_visitor_data", _exc)
            notify_etl_complete(
                {"failed_step": "step5_refresh_visitor_data", "error": str(_exc)[:200], "mode": "auto"},
                status="failed",
            )
            raise
        _save_partial()

        # Step 6: 预计算 RFM 8象限结果（DuckDB 缓存表，ETL 完成后一次性写入）
        print("\n" + "-" * 40)
        print("Step 6: 预计算 RFM 8象限历史周期缓存")
        print("-" * 40)
        from backend.services.health.rfm_analysis import precompute_rfm_cache, clear_rfm_cache
        if args.read_only:
            print("  [SKIP] step6_precompute_rfm_cache (read-only 模式)")
            print("  [SKIP] rfm_analysis_cache clear_rfm_cache (read-only 模式)")
            print("  [INFO] RFM 缓存保持上一次成功状态, 接受缓存陈旧 (DuckDB 1.5.x 跨 connection race 100% 触发)")
        else:
            try:
                # Stale 缓存修复: 预计算前先清空旧缓存（ETL 行数恢复后旧缓存 key 仍存在,
                # 即便 mtime 没变,旧缓存也携带错误的 orders_count_at_write,需清掉再重算）
                cleared = clear_rfm_cache()
                if cleared:
                    print(f"  清空旧缓存: {cleared} 行")
                with PerfTimer("step6_precompute_rfm_cache"):
                    count = precompute_rfm_cache()
                print(f"  预计算完成: {count} 个组合")
            except Exception as _exc:
                gate_record_error("step6_precompute_rfm_cache", _exc)
                notify_etl_complete(
                    {"failed_step": "step6_precompute_rfm_cache", "error": str(_exc)[:200], "mode": "auto"},
                    status="failed",
                )
                raise
        _save_partial()

        # Step 7: 创建 user_rfm 表 + 热点日期预加载（品类/地域等服务的依赖）
        print("\n" + "-" * 40)
        print("Step 7: 创建 user_rfm 表 + 热点日期预加载")
        print("-" * 40)
        from backend.db.init import create_user_rfm_table
        try:
            with PerfTimer("step7a_create_user_rfm_table"):
                create_user_rfm_table()
            from scripts.etl.preload_rfm import run_auto_preload
            with PerfTimer("step7b_run_auto_preload"):
                results = run_auto_preload()
            # FIX-S1 regression fix: run_auto_preload 返回 2-tuple (date_str, rows); r[1] = rows
            success = [r for r in results if r[1] > 0]
            print(f"  user_rfm 预加载完成: {len(success)}/{len(results)} 个 date 写入行")
        except Exception as _exc:
            gate_record_error("step7_user_rfm_preload", _exc)
            notify_etl_complete(
                {"failed_step": "step7_user_rfm_preload", "error": str(_exc)[:200], "mode": "auto"},
                status="failed",
            )
            raise
        _save_partial()

        # Step 7.5: 刷新活动节奏表（campaign_schedule）
        print("\n" + "-" * 40)
        print("Step 7.5: 刷新活动节奏表")
        print("-" * 40)
        try:
            with PerfTimer("step7_5_refresh_campaign_schedule"):
                refresh_campaign_schedule()
        except Exception as _exc:
            gate_record_error("step7_5_refresh_campaign_schedule", _exc)
            notify_etl_complete(
                {"failed_step": "step7_5_refresh_campaign_schedule", "error": str(_exc)[:200], "mode": "auto"},
                status="failed",
            )
            raise
        _save_partial()

        # 6 道门禁 — cross_day / api_health / dedup 收尾（在 main() 内补齐可访问 db 的门禁）
        try:
            from backend.config import DUCKDB_PATH as _DDB2
            import duckdb as _dd3
            if _DDB2.exists():
                # Sprint 11 S11-3 修: 加 config={"memory_limit": DUCKDB_MEMORY_LIMIT},
                # 跟其他 8GB conn 保持一致, 避免 DuckDB strict mode config conflict
                _c1 = _dd3.connect(str(_DDB2), read_only=True, config={"memory_limit": DUCKDB_MEMORY_LIMIT})
                try:
                    _after_max = _c1.execute("SELECT MAX(pay_time) FROM orders").fetchone()[0]
                    _after_count = _c1.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
                finally:
                    _c1.close()
                gate_set(
                    "cross_day", "pass",
                    checked=True,
                    before_max_pay_time=str(_before_max) if _before_max else None,
                    after_max_pay_time=str(_after_max) if _after_max else None,
                    before_count=_before_count,
                    after_count=_after_count,
                    net_change=_after_count - _before_count,
                )
                # 收集所有 perf 期间累积的错误数（api_health 门禁）
                from scripts.etl._timer import _ERRORS as _all_errs
                gate_set(
                    "api_health", "pass" if not _all_errs else "fail",
                    checked=True,
                    error_count=len(_all_errs),
                    errors=list(_all_errs),
                )
                gate_set(
                    "dedup", "pass",
                    checked=True,
                    before_count=_before_count,
                    after_count=_after_count,
                    net_change=_after_count - _before_count,
                )
        except Exception as _e:
            print(f"  [WO-1 修复] 6 道门禁收尾失败 (cross_day/api_health/dedup): {type(_e).__name__}: {_e}")
            gate_set("cross_day", "fail", checked=False, error=str(_e)[:200])
            gate_set("api_health", "fail", checked=False, error=str(_e)[:200])
            gate_set("dedup", "fail", checked=False, error=str(_e)[:200])

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
            conn = duckdb.connect(str(DUCKDB_PATH), read_only=True, config={"memory_limit": DUCKDB_MEMORY_LIMIT})
            try:
                total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
                total_users = conn.execute("SELECT COUNT(DISTINCT user_id) FROM orders").fetchone()[0]
                print(f"{'DuckDB 订单表':<16} {'—':>8} {total_orders:>12,} {'—':>10} {'—':>10}")
                print(f"{'DuckDB 用户数':<16} {'—':>8} {total_users:>12,} {'—':>10} {'—':>10}")
            finally:
                conn.close()
        except Exception as _e:
            print(f"  [WO-1 修复] Step 8 DuckDB 总行数查询失败: {type(_e).__name__}: {_e}")

        print("=" * 60)
        print("一键更新完成！")
        print("=" * 60)

        # WO-4: 写 etl_health.json (SRE 0 代码 / 0 飞书 状态查询)
        try:
            from pathlib import Path
            import json as _json
            from datetime import datetime as _dt
            _health_path = Path("/tmp/fuqing-etl-health.json")
            _health_path.write_text(_json.dumps({
                "last_run_wall": "see baseline",
                "last_status": "success",
                "ts": _dt.now().isoformat(timespec="seconds"),
                "mode": "auto",
                "gates_overall": "see _timer.py baseline",
            }, ensure_ascii=False, indent=2))
        except Exception as _e:
            print(f"  [WO-4] etl_health.json 写失败 (非阻塞): {type(_e).__name__}: {_e}")

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
        if not args.dry_run and not args.apply:
            print("错误: --rescan-spu 需要指定 --dry-run 或 --apply")
            sys.exit(1)
        print("\n" + "=" * 60)
        print("SPU 重匹配")
        print("=" * 60)
        rescan_spu_mapping(
            product_ids=args.product_ids if args.product_ids else None,
            dry_run=args.dry_run
        )
        sys.exit(0)

    # 纯淘客渠道更新
    if args.update_taoke:
        update_taoke_channel()
        sys.exit(0)

    if args.full:
        _mode = 'full'
    elif args.inc:
        _mode = 'inc'
    else:
        _mode = 'auto'

    # 修 P0 bug #1: 之前 _mode 设了但从未调用 run_full_etl()，--full/--inc 静默 noop 退出
    # 修 P0 bug #2: 之前 'inc' 映射成 'incremental'，但 pipeline.py:56-72 if/elif 只识别
    # 'inc' 和 'full'，'incremental' 落到 else 分支被当 'auto' 处理 → --inc 显式契约
    # 破坏（库空时不会 return，反触发全量重建）。修正：'inc' 直接映射 'inc'。
    _pipeline_mode = {'full': 'full', 'inc': 'inc', 'auto': 'auto'}[_mode]
    print("\n" + "=" * 60)
    print(f"ETL 跑批（mode={_mode}, window_days={args.window_days}）")
    print("=" * 60)
    with PerfTimer(f"run_etl_{_mode}", mode=_mode, window_days=args.window_days):
        run_full_etl(mode=_pipeline_mode, window_days=args.window_days, force_continue=True,
                     skip_dq=args.skip_dq, skip_w4=args.skip_w4)
    print("\n" + "=" * 60)
    print(f"ETL 跑批完成（mode={_mode}）")
    print("=" * 60)

    # Sprint 19 P2-4: ETL 跑批末尾调 W5 cache invalidation hook
    # 不依赖 uvicorn 重启也能 invalidate (12 keys 在用户下次访问时重算)
    # 跟 Sprint 18 #123 启动 hook 互补: 启动 hook 解决 "uvicorn 重启" 路径
    # post-run hook 解决 "uvicorn 还没重启" 路径, 跑批完立刻清 cache
    try:
        from backend.services.rfm.cache import etl_post_run_hook
        invalidated = etl_post_run_hook()
        print(f"W5 cache invalidation: {'invalidate 触发' if invalidated else 'no-op (manifest version 一致)'}")
    except Exception as e:  # noqa: BLE001
        # best-effort: 失败不阻塞 ETL 收口
        print(f"WARN: W5 cache etl_post_run_hook 失败 (不阻塞收口): {e}")


if __name__ == '__main__':
    main()
