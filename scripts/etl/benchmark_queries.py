#!/usr/bin/env python3
"""
benchmark_queries.py — 10.6M vs 50M 查询性能对比基准测试

测试场景（每个跑 3 次取平均）：
  1. 全店复购率查询（overview.py 核心逻辑）
  2. RFM 分群查询（fact_rfm_long 表查询）
  3. 渠道占比查询（audience_summary.py Panel B 核心逻辑）
  4. 30 指标对比查询（audience_summary.py Panel A 核心逻辑）

用法：python3 scripts/etl/benchmark_queries.py
输出：性能对比表（10.6M vs 50M）

设计说明：
  - 50M 库只有 orders 表，user_first_purchase 用子查询内联计算
  - fact_rfm_long 表仅在 10.6M 库存在，50M 库无此表时跳过 RFM 场景
  - 所有 SQL 参考 backend/services/health/overview.py 和
    backend/services/metrics/audience_summary.py 的实际查询逻辑
  - 每个场景独立连接，避免缓存干扰
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional

# 项目根目录
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import duckdb

# ── 数据库路径 ────────────────────────────────────────────────────
DB_10M = ROOT / "data" / "processed" / "sample_crm.duckdb"
DB_50M = ROOT / "data" / "processed" / "sample_crm_50m.duckdb"

RUNS = 3  # 每个场景跑 3 次取平均

# ── 有效订单口径（来自 backend.semantic.filters.OrderFilters.valid_order）──
VALID_ORDER = "is_goujinjin = FALSE AND order_status != '交易关闭' AND is_refund = FALSE"


# ══════════════════════════════════════════════════════════════════
# 场景 1: 全店复购率查询
# 参考: backend/services/health/overview.py _compute_repurchase_rate()
# ══════════════════════════════════════════════════════════════════

def bench_repurchase_rate(conn, start_date: str, end_date: str) -> dict:
    """全店复购率: 2+有效订单人数 / 总购买人数"""
    row = conn.execute(f"""
        WITH user_orders AS (
            SELECT user_id, COUNT(DISTINCT order_id) as order_count
            FROM orders
            WHERE {VALID_ORDER}
              AND pay_time >= ?::TIMESTAMP AND pay_time <= ?::TIMESTAMP
            GROUP BY user_id
        )
        SELECT
            COUNT(DISTINCT CASE WHEN order_count >= 2 THEN user_id END) as repurchase_users,
            COUNT(DISTINCT user_id) as total_users
        FROM user_orders
    """, [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]).fetchone()
    return {"repurchase_users": int(row[0] or 0), "total_users": int(row[1] or 0)}


# ══════════════════════════════════════════════════════════════════
# 场景 2: RFM 分群查询
# 参考: backend/semantic/segments.py + fact_rfm_long 表
# ══════════════════════════════════════════════════════════════════

def bench_rfm_segment(conn, query_date: str) -> Optional[dict]:
    """RFM 分群查询: 从 fact_rfm_long 表读取 8 象限分布"""
    # 检查 fact_rfm_long 表是否存在
    tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
    if "fact_rfm_long" not in tables:
        return None

    rows = conn.execute("""
        SELECT
            dimension_key,
            segment_id,
            user_count,
            gmv,
            repurchase_count
        FROM fact_rfm_long
        WHERE date = ?::DATE
          AND segment_id > 0
        ORDER BY segment_id
    """, [query_date]).fetchall()

    return {"segments": len(rows), "total_users": sum(r[2] for r in rows)}


def bench_rfm_inline(conn, query_date: str) -> dict:
    """RFM 分群内联计算: 直接从 orders 表计算 RFM 评分和 8 象限分布"""
    cutoff = query_date
    row = conn.execute(f"""
        WITH user_rfm AS (
            SELECT
                user_id,
                DATEDIFF('day', MAX(DATE(pay_time)), ?::DATE) AS recency,
                COUNT(DISTINCT order_id) AS frequency,
                SUM(actual_amount) AS monetary
            FROM orders
            WHERE {VALID_ORDER}
              AND pay_time IS NOT NULL
              AND pay_time <= ?::TIMESTAMP
            GROUP BY user_id
        ),
        scored AS (
            SELECT
                user_id,
                recency, frequency, monetary,
                CASE WHEN recency <= 30 THEN 5
                     WHEN recency <= 90 THEN 4
                     WHEN recency <= 180 THEN 3
                     WHEN recency <= 365 THEN 2
                     ELSE 1 END AS r_score,
                CASE WHEN frequency >= 5 THEN 5
                     WHEN frequency >= 4 THEN 4
                     WHEN frequency >= 3 THEN 3
                     WHEN frequency >= 2 THEN 2
                     ELSE 1 END AS f_score,
                CASE WHEN monetary >= 1000 THEN 5
                     WHEN monetary >= 500 THEN 4
                     WHEN monetary >= 300 THEN 3
                     WHEN monetary >= 100 THEN 2
                     ELSE 1 END AS m_score
            FROM user_rfm
        ),
        segmented AS (
            SELECT
                user_id,
                r_score, f_score, m_score,
                CASE
                    WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 1
                    WHEN r_score >= 4 AND f_score >= 4 AND m_score < 4 THEN 2
                    WHEN r_score >= 4 AND f_score < 4 AND m_score >= 4 THEN 3
                    WHEN r_score >= 4 AND f_score < 4 AND m_score < 4 THEN 4
                    WHEN r_score < 4 AND f_score >= 4 AND m_score >= 4 THEN 5
                    WHEN r_score < 4 AND f_score >= 4 AND m_score < 4 THEN 6
                    WHEN r_score < 4 AND f_score < 4 AND m_score >= 4 THEN 7
                    WHEN r_score < 4 AND f_score < 4 AND m_score < 4 THEN 8
                END AS segment_id
            FROM scored
        )
        SELECT
            segment_id,
            COUNT(*) AS user_count
        FROM segmented
        GROUP BY segment_id
        ORDER BY segment_id
    """, [cutoff, f"{cutoff} 23:59:59"]).fetchall()

    return {"segments": len(row), "total_users": sum(r[1] for r in row)}


# ══════════════════════════════════════════════════════════════════
# 场景 3: 渠道占比查询
# 参考: backend/services/metrics/audience_summary.py _run_period_data()
# ══════════════════════════════════════════════════════════════════

def bench_channel_share(conn, start_dt: str, end_dt: str, cutoff: str) -> dict:
    """渠道占比: GROUPING SETS 按渠道汇总 GSV/人数/AUS + 老客指标"""
    sql = f"""
    WITH
    base AS (
        SELECT * FROM orders
        WHERE pay_time >= ?::TIMESTAMP AND pay_time <= ?::TIMESTAMP
          AND {VALID_ORDER}
    ),
    old_customers AS (
        SELECT DISTINCT user_id
        FROM (
            SELECT user_id, MIN(DATE(pay_time)) AS first_pay_date
            FROM orders
            WHERE pay_time IS NOT NULL AND {VALID_ORDER} AND user_id IS NOT NULL AND user_id != ''
            GROUP BY user_id
        ) u
        WHERE u.first_pay_date <= ?::DATE
    ),
    enriched AS (
        SELECT
            o.channel AS dim_key,
            o.user_id,
            o.actual_amount AS amount,
            o.is_member,
            CASE WHEN oc.user_id IS NOT NULL THEN 1 ELSE 0 END AS is_old
        FROM base o
        LEFT JOIN old_customers oc ON o.user_id = oc.user_id
    ),
    grouped AS (
        SELECT
            dim_key,
            COUNT(DISTINCT user_id) AS gsv_users,
            SUM(amount) AS gsv,
            SUM(amount) / NULLIF(COUNT(DISTINCT user_id), 0) AS aus,
            COUNT(DISTINCT CASE WHEN is_old = 1 THEN user_id END) AS old_users,
            SUM(amount * CASE WHEN is_old = 1 THEN 1 ELSE 0 END) AS old_gsv,
            GROUPING(dim_key) AS _grp
        FROM enriched
        GROUP BY GROUPING SETS ((dim_key), ())
    )
    SELECT
        CASE WHEN _grp = 1 THEN '__TOTAL__' ELSE dim_key END,
        gsv_users, gsv, aus, old_users, old_gsv
    FROM grouped
    ORDER BY _grp ASC, gsv DESC
    """
    rows = conn.execute(sql, [start_dt, end_dt, cutoff]).fetchall()
    return {"channels": len(rows), "total_gsv": sum(float(r[2] or 0) for r in rows)}


# ══════════════════════════════════════════════════════════════════
# 场景 4: 30 指标对比查询
# 参考: backend/services/metrics/audience_summary.py _run_period_data()
#          + 3 年同比对比（当前期 + 去年 + 前年）
# ══════════════════════════════════════════════════════════════════

def bench_30_indicators(conn, periods: list) -> dict:
    """30 指标对比: 3 个周期 x 10 个核心指标

    periods: [(start_dt, end_dt, cutoff), ...]  3 个周期
    """
    results = []
    for start_dt, end_dt, cutoff in periods:
        sql = f"""
        WITH
        base AS (
            SELECT * FROM orders
            WHERE pay_time >= ?::TIMESTAMP AND pay_time <= ?::TIMESTAMP
              AND {VALID_ORDER}
        ),
        old_customers AS (
            SELECT DISTINCT user_id
            FROM (
                SELECT user_id, MIN(DATE(pay_time)) AS first_pay_date
                FROM orders
                WHERE pay_time IS NOT NULL AND {VALID_ORDER} AND user_id IS NOT NULL AND user_id != ''
                GROUP BY user_id
            ) u
            WHERE u.first_pay_date <= ?::DATE
        ),
        enriched AS (
            SELECT
                o.user_id,
                o.actual_amount AS amount,
                o.is_member,
                CASE WHEN oc.user_id IS NOT NULL THEN 1 ELSE 0 END AS is_old
            FROM base o
            LEFT JOIN old_customers oc ON o.user_id = oc.user_id
        )
        SELECT
            COUNT(DISTINCT user_id) AS gsv_users,
            SUM(amount) AS gsv,
            SUM(amount) / NULLIF(COUNT(DISTINCT user_id), 0) AS aus,
            COUNT(DISTINCT CASE WHEN is_old = 1 THEN user_id END) AS old_users,
            SUM(amount * CASE WHEN is_old = 1 THEN 1 ELSE 0 END) AS old_gsv,
            SUM(amount * CASE WHEN is_old = 1 THEN 1 ELSE 0 END) /
                NULLIF(COUNT(DISTINCT CASE WHEN is_old = 1 THEN user_id END), 0) AS old_aus,
            COUNT(DISTINCT CASE WHEN is_member = TRUE THEN user_id END) AS member_users,
            SUM(amount * CASE WHEN is_member = TRUE THEN 1 ELSE 0 END) AS member_gsv,
            SUM(amount * CASE WHEN is_member = TRUE THEN 1 ELSE 0 END) /
                NULLIF(COUNT(DISTINCT CASE WHEN is_member = TRUE THEN user_id END), 0) AS member_aus,
            COUNT(DISTINCT CASE WHEN is_member = TRUE AND is_old = 1 THEN user_id END) AS member_old_users,
            SUM(amount * CASE WHEN is_member = TRUE AND is_old = 1 THEN 1 ELSE 0 END) AS member_old_gsv
        FROM enriched
        """
        row = conn.execute(sql, [start_dt, end_dt, cutoff]).fetchone()
        results.append(row)

    return {"periods": len(results), "indicators_per_period": 11}


# ══════════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════════

def run_benchmark(db_path: Path, label: str, runs: int = RUNS) -> Dict[str, Any]:
    """对单个数据库运行所有 benchmark 场景"""
    if not db_path.exists():
        print(f"  [跳过] 数据库不存在: {db_path}")
        return {}

    results = {}

    # ── 场景 1: 全店复购率 ──────────────────────────────────────
    times = []
    last_result = None
    for i in range(runs):
        conn = duckdb.connect(str(db_path), read_only=True, config={"memory_limit": "8GB"})
        t0 = time.perf_counter()
        last_result = bench_repurchase_rate(conn, "2026-01-01", "2026-05-31")
        elapsed = time.perf_counter() - t0
        conn.close()
        times.append(elapsed)
    results["全店复购率"] = {"times": times, "avg": sum(times) / len(times), "result": last_result}

    # ── 场景 2: RFM 分群 ────────────────────────────────────────
    # 先尝试 fact_rfm_long 表查询
    times_rfm_table = []
    rfm_table_result = None
    rfm_has_table = False
    for i in range(runs):
        conn = duckdb.connect(str(db_path), read_only=True, config={"memory_limit": "8GB"})
        t0 = time.perf_counter()
        rfm_table_result = bench_rfm_segment(conn, "2026-06-07")
        elapsed = time.perf_counter() - t0
        conn.close()
        if rfm_table_result is not None:
            rfm_has_table = True
            times_rfm_table.append(elapsed)

    # 内联 RFM 计算（两个库都能跑）
    times_rfm_inline = []
    rfm_inline_result = None
    for i in range(runs):
        conn = duckdb.connect(str(db_path), read_only=True, config={"memory_limit": "8GB"})
        t0 = time.perf_counter()
        rfm_inline_result = bench_rfm_inline(conn, "2026-06-07")
        elapsed = time.perf_counter() - t0
        conn.close()
        times_rfm_inline.append(elapsed)

    if rfm_has_table:
        results["RFM分群(预计算表)"] = {
            "times": times_rfm_table,
            "avg": sum(times_rfm_table) / len(times_rfm_table),
            "result": rfm_table_result,
        }
    results["RFM分群(实时计算)"] = {
        "times": times_rfm_inline,
        "avg": sum(times_rfm_inline) / len(times_rfm_inline),
        "result": rfm_inline_result,
    }

    # ── 场景 3: 渠道占比 ────────────────────────────────────────
    times = []
    last_result = None
    for i in range(runs):
        conn = duckdb.connect(str(db_path), read_only=True, config={"memory_limit": "8GB"})
        t0 = time.perf_counter()
        last_result = bench_channel_share(conn, "2026-01-01 00:00:00", "2026-05-31 23:59:59", "2025-12-31")
        elapsed = time.perf_counter() - t0
        conn.close()
        times.append(elapsed)
    results["渠道占比"] = {"times": times, "avg": sum(times) / len(times), "result": last_result}

    # ── 场景 4: 30 指标对比 ─────────────────────────────────────
    # 3 个周期: 2026 MTD, 2025 MTD, 2024 MTD
    periods = [
        ("2026-01-01 00:00:00", "2026-05-31 23:59:59", "2025-12-31"),
        ("2025-01-01 00:00:00", "2025-05-31 23:59:59", "2024-12-31"),
        ("2024-01-01 00:00:00", "2024-05-31 23:59:59", "2023-12-31"),
    ]
    times = []
    last_result = None
    for i in range(runs):
        conn = duckdb.connect(str(db_path), read_only=True, config={"memory_limit": "8GB"})
        t0 = time.perf_counter()
        last_result = bench_30_indicators(conn, periods)
        elapsed = time.perf_counter() - t0
        conn.close()
        times.append(elapsed)
    results["30指标对比"] = {"times": times, "avg": sum(times) / len(times), "result": last_result}

    return results


def print_comparison(r10: dict, r50: dict):
    """打印性能对比表"""
    print()
    print("=" * 80)
    print("  芙清 CRM 查询性能基准测试 — 10.6M vs 50M")
    print("=" * 80)
    print()

    # 表头
    header = f"{'场景':<22} {'10.6M 平均':>10} {'10.6M 详情':>24} {'50M 平均':>10} {'50M 详情':>24} {'倍率':>6}"
    print(header)
    print("-" * len(header))

    all_scenarios = list(r10.keys())
    for scenario in all_scenarios:
        d10 = r10.get(scenario)
        d50 = r50.get(scenario)

        avg10 = d10["avg"] if d10 else float("nan")
        avg50 = d50["avg"] if d50 else float("nan")

        times10 = ", ".join(f"{t:.3f}" for t in d10["times"]) if d10 else "N/A"
        times50 = ", ".join(f"{t:.3f}" for t in d50["times"]) if d50 else "N/A"

        ratio = avg50 / avg10 if avg10 > 0 and not (avg10 != avg10) else float("nan")
        ratio_str = f"{ratio:.2f}x" if ratio == ratio else "N/A"

        print(f"{scenario:<22} {avg10:>9.3f}s {times10:>24} {avg50:>9.3f}s {times50:>24} {ratio_str:>6}")

    print("-" * len(header))
    print()

    # 汇总统计
    valid_10 = [d["avg"] for d in r10.values() if d]
    valid_50 = [d["avg"] for d in r50.values() if d]
    if valid_10 and valid_50:
        print(f"  10.6M 总耗时 (所有场景平均之和): {sum(valid_10):.3f}s")
        print(f"  50M   总耗时 (所有场景平均之和): {sum(valid_50):.3f}s")
        overall_ratio = sum(valid_50) / sum(valid_10) if sum(valid_10) > 0 else float("nan")
        print(f"  整体倍率: {overall_ratio:.2f}x")
    print()

    # 详细结果（如有）
    for scenario in all_scenarios:
        d10 = r10.get(scenario)
        d50 = r50.get(scenario)
        r10_val = d10.get("result") if d10 else None
        r50_val = d50.get("result") if d50 else None
        if r10_val or r50_val:
            print(f"  [{scenario}] 结果:")
            if r10_val:
                print(f"    10.6M: {r10_val}")
            if r50_val:
                print(f"    50M:   {r50_val}")
            print()


# ══════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════

def main():
    print("芙清 CRM 查询性能基准测试")
    print(f"  10.6M 库: {DB_10M}")
    print(f"  50M   库: {DB_50M}")
    print(f"  每场景跑 {RUNS} 次取平均")
    print()

    # 检查文件存在
    for label, path in [("10.6M", DB_10M), ("50M", DB_50M)]:
        if path.exists():
            size_gb = path.stat().st_size / (1024 ** 3)
            print(f"  {label}: {path.name} ({size_gb:.1f} GB)")
        else:
            print(f"  {label}: [不存在] {path}")
    print()

    # 运行 benchmark
    print("运行 10.6M benchmark ...")
    r10 = run_benchmark(DB_10M, "10.6M")
    print("  完成。")

    print("运行 50M benchmark ...")
    r50 = run_benchmark(DB_50M, "50M")
    print("  完成。")

    # 输出对比表
    print_comparison(r10, r50)


if __name__ == "__main__":
    main()
