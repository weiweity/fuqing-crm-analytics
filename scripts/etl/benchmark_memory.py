#!/usr/bin/env python3
"""
benchmark_memory.py — DuckDB 查询内存 & 并发性能基准测试

测试场景：
  1. 查询时 RSS 峰值（用 psutil 采样 + resource 模块）
  2. 冷启动查询耗时（首次 vs 缓存/热查询）
  3. 并发查询性能（1 vs 4 workers）

数据库：
  - 10.6M: data/processed/fuqing_crm.duckdb
  - 50M:   data/processed/fuqing_crm_50m.duckdb

用法：python3 scripts/etl/benchmark_memory.py
"""

from __future__ import annotations

import gc
import os
import platform
import resource
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import duckdb
import psutil

# ── 路径 ────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
DB_10M = ROOT / "data" / "processed" / "fuqing_crm.duckdb"
DB_50M = ROOT / "data" / "processed" / "fuqing_crm_50m.duckdb"

# ── 测试查询（真实业务场景） ─────────────────────────────────────
QUERIES: dict[str, str] = {
    "count_all": "SELECT count(*) FROM orders",
    "groupby_channel": (
        "SELECT channel, count(*) as cnt, sum(amount) as total "
        "FROM orders GROUP BY channel ORDER BY cnt DESC"
    ),
    "agg_rfm": (
        "SELECT user_id, "
        "  count(*) as frequency, "
        "  sum(amount) as monetary, "
        "  max(pay_time) as last_pay "
        "FROM orders "
        "WHERE pay_time IS NOT NULL "
        "GROUP BY user_id "
        "ORDER BY monetary DESC "
        "LIMIT 10000"
    ),
    "filter_refund": (
        "SELECT channel, count(*) as refund_cnt, sum(refund_amount) as refund_total "
        "FROM orders "
        "WHERE is_refund = true "
        "GROUP BY channel "
        "ORDER BY refund_cnt DESC"
    ),
}


# ── 辅助函数 ────────────────────────────────────────────────────
def rss_mb() -> float:
    """当前进程 RSS（MB），用 psutil 实时采样"""
    return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)


def peak_rss_mb() -> float:
    """进程生命周期内 RSS 峰值（MB），用 resource 模块"""
    rusage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() == "Darwin":
        return rusage / (1024 * 1024)  # bytes -> MB
    return rusage / 1024  # KB -> MB


def fmt_mb(mb: float) -> str:
    return f"{mb:,.1f} MB"


def fmt_sec(sec: float) -> str:
    if sec < 1:
        return f"{sec * 1000:.1f} ms"
    return f"{sec:.2f} s"


def connect_db(db_path: Path, memory_limit: str = "4GB") -> duckdb.DuckDBPyConnection:
    """连接 DuckDB，read_only + 指定 memory_limit

    DuckDB 1.5.x 单 writer 限制：如果主库被后端进程锁住，
    以 read_only=True 连接仍可能失败（锁检查在 connect 阶段）。
    这里 catch 异常让调用方决定是否跳过。
    """
    return duckdb.connect(
        str(db_path),
        read_only=True,
        config={"memory_limit": memory_limit},
    )


# ── 测试 1: RSS 峰值 ──────────────────────────────────────────
def bench_rss_peak(db_path: Path, label: str) -> dict[str, Any]:
    """执行所有查询，记录每个查询的 RSS 峰值增量"""
    results: dict[str, Any] = {"label": label, "db": db_path.name}
    base_rss = rss_mb()
    results["base_rss_mb"] = round(base_rss, 1)

    con = connect_db(db_path)
    query_rss: dict[str, dict[str, float]] = {}

    for name, sql in QUERIES.items():
        gc.collect()
        before = rss_mb()
        t0 = time.perf_counter()
        con.execute(sql).fetchall()
        elapsed = time.perf_counter() - t0
        after = rss_mb()
        peak = peak_rss_mb()

        query_rss[name] = {
            "elapsed_sec": round(elapsed, 4),
            "rss_before_mb": round(before, 1),
            "rss_after_mb": round(after, 1),
            "rss_delta_mb": round(after - before, 1),
            "rss_peak_mb": round(peak, 1),
        }

    con.close()
    results["queries"] = query_rss
    results["rss_peak_overall_mb"] = round(peak_rss_mb(), 1)
    return results


# ── 测试 2: 冷启动 vs 热查询 ────────────────────────────────────
def bench_cold_vs_hot(db_path: Path, label: str) -> dict[str, Any]:
    """冷启动（drop cache 后首次）vs 热查询（第 2 次）耗时对比

    注意：macOS 无法像 Linux 那样 drop page cache，
    这里用"新连接首次查询"模拟冷启动，同一连接重复查询模拟热查询。
    """
    results: dict[str, Any] = {"label": label, "db": db_path.name}
    timings: dict[str, dict[str, float]] = {}

    for name, sql in QUERIES.items():
        # 冷启动：新建连接 + 首次查询
        con_cold = connect_db(db_path)
        gc.collect()
        t0 = time.perf_counter()
        con_cold.execute(sql).fetchall()
        cold_sec = time.perf_counter() - t0
        # 热查询：同一连接再跑一次
        t0 = time.perf_counter()
        con_cold.execute(sql).fetchall()
        hot_sec = time.perf_counter() - t0
        con_cold.close()

        speedup = cold_sec / hot_sec if hot_sec > 0 else float("inf")
        timings[name] = {
            "cold_sec": round(cold_sec, 4),
            "hot_sec": round(hot_sec, 4),
            "speedup": round(speedup, 2),
        }

    results["queries"] = timings
    return results


# ── 测试 3: 并发查询 ──────────────────────────────────────────
def _run_query(db_path: Path, sql: str) -> float:
    """在独立连接中执行查询，返回耗时（秒）"""
    con = connect_db(db_path, memory_limit="2GB")
    t0 = time.perf_counter()
    con.execute(sql).fetchall()
    elapsed = time.perf_counter() - t0
    con.close()
    return elapsed


def bench_concurrency(db_path: Path, label: str) -> dict[str, Any]:
    """1 worker vs 4 workers 并发执行所有查询"""
    results: dict[str, Any] = {"label": label, "db": db_path.name}
    concurrency_results: dict[str, dict[str, Any]] = {}

    sql_list = list(QUERIES.values())
    query_names = list(QUERIES.keys())

    for n_workers in (1, 4):
        gc.collect()
        t_start = time.perf_counter()
        per_query_times: dict[str, list[float]] = {name: [] for name in query_names}

        with ThreadPoolExecutor(max_workers=n_workers) as pool:
            # 每个查询提交 n_workers 次（模拟并发竞争）
            futures = {}
            for _i in range(n_workers):
                for qi, sql in enumerate(sql_list):
                    f = pool.submit(_run_query, db_path, sql)
                    futures[f] = query_names[qi]

            for f in as_completed(futures):
                qname = futures[f]
                try:
                    elapsed = f.result()
                    per_query_times[qname].append(elapsed)
                except Exception:
                    per_query_times[qname].append(-1.0)

        wall_total = time.perf_counter() - t_start

        # 汇总每个查询的 avg / max
        per_q_summary = {}
        for qname in query_names:
            times = [t for t in per_query_times[qname] if t > 0]
            if times:
                per_q_summary[qname] = {
                    "avg_sec": round(sum(times) / len(times), 4),
                    "max_sec": round(max(times), 4),
                    "min_sec": round(min(times), 4),
                    "runs": len(times),
                }
            else:
                per_q_summary[qname] = {"avg_sec": -1, "runs": 0}

        concurrency_results[f"workers_{n_workers}"] = {
            "wall_total_sec": round(wall_total, 4),
            "per_query": per_q_summary,
        }

    results["concurrency"] = concurrency_results
    return results


# ── 表格输出 ────────────────────────────────────────────────────
def print_rss_table(rss_results: list[dict[str, Any]]) -> None:
    """打印 RSS 峰值对比表"""
    print()
    print("=" * 80)
    print("  测试 1: 查询 RSS 峰值对比")
    print("=" * 80)

    # 收集所有查询名
    all_queries = list(QUERIES.keys())

    # 表头
    header = f"{'查询':<25}"
    for r in rss_results:
        header += f" | {r['label'] + ' RSS峰值':>20}"
    print(header)
    print("-" * len(header))

    for qname in all_queries:
        row = f"{qname:<25}"
        for r in rss_results:
            q = r["queries"].get(qname, {})
            peak = q.get("rss_peak_mb", 0)
            delta = q.get("rss_delta_mb", 0)
            row += f" | {fmt_mb(peak):>12} (+{fmt_mb(delta):>6})"
        print(row)

    # 汇总行
    print("-" * len(header))
    row = f"{'[整体峰值]':<25}"
    for r in rss_results:
        row += f" | {fmt_mb(r.get('rss_peak_overall_mb', 0)):>20}"
    print(row)
    print()


def print_cold_hot_table(cold_hot_results: list[dict[str, Any]]) -> None:
    """打印冷启动 vs 热查询对比表"""
    print()
    print("=" * 90)
    print("  测试 2: 冷启动 vs 热查询耗时对比")
    print("=" * 90)

    all_queries = list(QUERIES.keys())

    for r in cold_hot_results:
        print(f"\n  --- {r['label']} ({r['db']}) ---")
        header = f"  {'查询':<25} | {'冷启动':>12} | {'热查询':>12} | {'加速比':>8}"
        print(header)
        print("  " + "-" * (len(header) - 2))

        for qname in all_queries:
            q = r["queries"].get(qname, {})
            cold = q.get("cold_sec", 0)
            hot = q.get("hot_sec", 0)
            speedup = q.get("speedup", 0)
            print(f"  {qname:<25} | {fmt_sec(cold):>12} | {fmt_sec(hot):>12} | {speedup:>7.1f}x")

    print()


def print_concurrency_table(conc_results: list[dict[str, Any]]) -> None:
    """打印并发性能对比表"""
    print()
    print("=" * 100)
    print("  测试 3: 并发查询性能对比 (1 worker vs 4 workers)")
    print("=" * 100)

    all_queries = list(QUERIES.keys())

    for r in conc_results:
        print(f"\n  --- {r['label']} ({r['db']}) ---")

        conc = r["concurrency"]
        w1 = conc.get("workers_1", {})
        w4 = conc.get("workers_4", {})

        # 总 wall time
        print(f"  总 wall time:  1 worker = {fmt_sec(w1.get('wall_total_sec', 0))}"
              f"  |  4 workers = {fmt_sec(w4.get('wall_total_sec', 0))}", end="")
        w1t = w1.get("wall_total_sec", 0)
        w4t = w4.get("wall_total_sec", 0)
        if w1t > 0:
            ratio = w4t / w1t
            print(f"  |  比值 = {ratio:.2f}x")
        else:
            print()

        # per-query 表
        header = f"  {'查询':<25} | {'1w avg':>12} | {'1w max':>12} | {'4w avg':>12} | {'4w max':>12} | {'4w/1w avg':>10}"
        print(header)
        print("  " + "-" * (len(header) - 2))

        for qname in all_queries:
            q1 = w1.get("per_query", {}).get(qname, {})
            q4 = w4.get("per_query", {}).get(qname, {})
            avg1 = q1.get("avg_sec", 0)
            max1 = q1.get("max_sec", 0)
            avg4 = q4.get("avg_sec", 0)
            max4 = q4.get("max_sec", 0)
            ratio_str = f"{avg4 / avg1:.2f}x" if avg1 > 0 else "N/A"
            print(f"  {qname:<25} | {fmt_sec(avg1):>12} | {fmt_sec(max1):>12} | "
                  f"{fmt_sec(avg4):>12} | {fmt_sec(max4):>12} | {ratio_str:>10}")

    print()


# ── 主流程 ──────────────────────────────────────────────────────
def main() -> int:
    print("=" * 80)
    print("  DuckDB 查询内存 & 并发性能基准测试")
    print(f"  平台: {platform.platform()}")
    print(f"  Python: {platform.python_version()}")
    print(f"  DuckDB: {duckdb.__version__}")
    print(f"  CPU 核数: {os.cpu_count()}")
    print(f"  psutil RSS 初始值: {fmt_mb(rss_mb())}")
    print("=" * 80)

    # 检查数据库存在性 + 可连接性
    dbs: list[tuple[Path, str]] = []
    for db_path, label in [(DB_10M, "10.6M"), (DB_50M, "50M")]:
        if not db_path.exists():
            print(f"  [跳过] {label} 数据库不存在: {db_path}")
            continue
        # 试连接一次，验证锁不冲突
        try:
            test_con = connect_db(db_path)
            test_con.execute("SELECT 1").fetchall()
            test_con.close()
            dbs.append((db_path, label))
        except Exception as e:
            print(f"  [跳过] {label} 数据库连接失败（可能被其他进程锁定）: {e}")

    if not dbs:
        print("错误: 无可用数据库", file=sys.stderr)
        return 1

    # ── 测试 1: RSS 峰值 ──────────────────────────────────────
    rss_results = []
    for db_path, label in dbs:
        print(f"\n  [RSS 峰值] {label} ({db_path.name}) ...")
        r = bench_rss_peak(db_path, label)
        rss_results.append(r)
        print(f"    完成, 整体 RSS 峰值: {fmt_mb(r['rss_peak_overall_mb'])}")

    print_rss_table(rss_results)

    # ── 测试 2: 冷启动 vs 热查询 ──────────────────────────────
    cold_hot_results = []
    for db_path, label in dbs:
        print(f"\n  [冷/热查询] {label} ({db_path.name}) ...")
        r = bench_cold_vs_hot(db_path, label)
        cold_hot_results.append(r)
        print("    完成")

    print_cold_hot_table(cold_hot_results)

    # ── 测试 3: 并发查询 ──────────────────────────────────────
    conc_results = []
    for db_path, label in dbs:
        print(f"\n  [并发查询] {label} ({db_path.name}) ...")
        r = bench_concurrency(db_path, label)
        conc_results.append(r)
        print("    完成")

    print_concurrency_table(conc_results)

    # ── 最终汇总 ──────────────────────────────────────────────
    print("=" * 80)
    print("  基准测试完成")
    print(f"  进程 RSS 峰值: {fmt_mb(peak_rss_mb())}")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
