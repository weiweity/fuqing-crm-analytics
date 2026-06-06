"""
W4 full v0.4.12 — fact_rfm_long 全量重算脚本 (运营手触发, 不在 ETL 流程)

设计 (docs/design/etl-phase4-architecture.md §W4 + §7.4):
- 用途: 运营手触发全历史 / 任意日期范围重算 (例如 RFM 阈值变更后全量重算)
- 不在 ETL 自动流程内 (pipeline.py 只调 incremental + merge_replace)
- 走 setup_async_memory() 临时 16GB override
- dbt-style snapshot: 同一天多次跑产生新 version, 历史 version 保留
- 默认 540 组合 (channel × item × segment_id), 走 backend.semantic.segments

用法:
    PYTHONPATH=. python3 scripts/etl/rfm_recompute_window.py \\
        --from 2024-01-01 --to 2026-06-04  # 一次性跑全历史
    PYTHONPATH=. python3 scripts/etl/rfm_recompute_window.py \\
        --from 2026-06-01 --to 2026-06-06  # 跑最近 6 天
    PYTHONPATH=. python3 scripts/etl/rfm_recompute_window.py \\
        --from 2026-06-01 --to 2026-06-06 --dry-run  # 演练, 不写入

CLAUDE.md 合规:
- ① 走 backend.semantic.segments (校验) + backend.semantic.filters (口径)
- ② ETL 脚本连接例外 (CLAUDE.md §ETL 例外): duckdb.connect + conn.close()
- ③ W7 配套: DUCKDB_MEMORY_LIMIT_OVERRIDE=16GB 临时调高, 跑完恢复
"""
import argparse
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

# 把项目根加到 path（与 scripts/etl/_timer.py 等一致）
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.etl.precompute_fact_rfm import (  # noqa: E402
    FACT_RFM_TABLE,
    W4_TOTAL_COMBOS,
    cleanup_async_memory,
    create_fact_rfm_table,
    enumerate_combos,
    merge_replace,
    setup_async_memory,
)
from scripts.etl.config import DUCKDB_PATH as _DUCKDB_PATH  # noqa: E402


def _parse_date_arg(s: str) -> date:
    """解析 YYYY-MM-DD 日期字符串."""
    return datetime.strptime(s, "%Y-%m-%d").date()


def recompute_window(
    conn,
    from_date: date,
    to_date: date,
    dry_run: bool = False,
    verbose: bool = True,
) -> dict:
    """W4 full 全量重算指定日期范围 (含 from + to).

    走 merge_replace(date) 逐日重算 (dbt-style snapshot, 历史 version 保留).

    Args:
        conn: duckdb.Connection
        from_date: 起始日期 (含)
        to_date: 结束日期 (含)
        dry_run: 演练模式, 只打印不写入
        verbose: 详细输出

    Returns:
        dict: {"days": N, "rows_inserted": M, "rows_per_day_avg": ..., "elapsed_sec": ...}
    """
    if from_date > to_date:
        raise ValueError(f"from_date ({from_date}) 必须 <= to_date ({to_date})")

    days = (to_date - from_date).days + 1
    combos = enumerate_combos(conn)
    combo_count = len(combos)
    if verbose:
        print(f"  日期范围: {from_date} ~ {to_date} ({days} 天)")
        print(f"  组合数: {combo_count} (expected {W4_TOTAL_COMBOS})")
        assert combo_count == W4_TOTAL_COMBOS, f"枚举组合数 {combo_count} != 540"

    if dry_run:
        print("  [DRY-RUN] 演练模式, 不写入 fact_rfm_long")
        return {"days": days, "rows_inserted": 0, "rows_per_day_avg": 0, "elapsed_sec": 0, "dry_run": True}

    total_inserted = 0
    start_ts = time.perf_counter()

    # 一次重算 540 组合 (跨所有 segment_id=0 聚合行)
    # 注意: dbt-style snapshot 走 merge_replace, 不删旧 version, 写新 version
    for i, d in enumerate((from_date + timedelta(days=n) for n in range(days))):
        n = merge_replace(conn, d, combos=combos)
        total_inserted += n
        if verbose and (i + 1) % 30 == 0:
            elapsed = time.perf_counter() - start_ts
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (days - i - 1) / rate if rate > 0 else 0
            print(f"    [{i+1}/{days}] {d} +{n} 行 (rate {rate:.1f} d/s, ETA {eta:.0f}s)")

    elapsed = time.perf_counter() - start_ts
    return {
        "days": days,
        "rows_inserted": total_inserted,
        "rows_per_day_avg": total_inserted / days if days > 0 else 0,
        "elapsed_sec": elapsed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="W4 fact_rfm_long 全量重算 (运营手触发, 不在 ETL 流程)",
    )
    parser.add_argument(
        "--from", dest="from_date", required=True,
        help="起始日期 (含) YYYY-MM-DD",
    )
    parser.add_argument(
        "--to", dest="to_date", required=True,
        help="结束日期 (含) YYYY-MM-DD",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="演练模式, 不写入 fact_rfm_long",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="静默模式, 只打印结果摘要",
    )
    args = parser.parse_args()

    from_date = _parse_date_arg(args.from_date)
    to_date = _parse_date_arg(args.to_date)

    print("=" * 60)
    print("W4 fact_rfm_long 全量重算 (v0.4.12 full)")
    print("=" * 60)
    print(f"  from: {from_date}")
    print(f"  to:   {to_date}")
    print(f"  dry-run: {args.dry_run}")
    print(f"  combo: {W4_TOTAL_COMBOS} (= 9 channels × 60 items)")

    import duckdb
    setup_async_memory()
    memory_limit = os.environ.get("DUCKDB_MEMORY_LIMIT_OVERRIDE", "16GB")
    conn = duckdb.connect(str(_DUCKDB_PATH), config={"memory_limit": memory_limit})
    try:
        # 建表 (幂等)
        if not args.dry_run:
            create_fact_rfm_table(conn)

        # 重算窗口
        result = recompute_window(
            conn,
            from_date=from_date,
            to_date=to_date,
            dry_run=args.dry_run,
            verbose=not args.quiet,
        )

        print()
        print("=" * 60)
        print("W4 全量重算完成")
        print("=" * 60)
        print(f"  days:   {result['days']}")
        print(f"  rows:   {result['rows_inserted']:,}")
        if not args.dry_run:
            print(f"  avg:    {result['rows_per_day_avg']:.1f} 行/天")
            print(f"  wall:   {result['elapsed_sec']:.1f}s")
        if not args.dry_run:
            # 统计 (date, dimension_key, version) 实际行数
            count = conn.execute(f"SELECT COUNT(*) FROM {FACT_RFM_TABLE}").fetchone()[0]
            print(f"  total in {FACT_RFM_TABLE}: {count:,} 行")
        return 0
    finally:
        conn.close()
        cleanup_async_memory()


if __name__ == "__main__":
    sys.exit(main())
