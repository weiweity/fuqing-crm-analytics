#!/usr/bin/env python3
"""
DuckDB 内存使用 + RFM 查询性能测量脚本

通过两种方式测量：
1. read-only 连接 DuckDB 做表统计和内存分析
2. HTTP API 测量实际 RFM 查询延迟（模拟前端真实体验）
"""

import sys
import time
import json
import tracemalloc
import urllib.request
from pathlib import Path
from datetime import date, timedelta, datetime

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import duckdb  # noqa: E402
from backend.config import DUCKDB_PATH, DUCKDB_MEMORY_LIMIT  # noqa: E402


def fmt_bytes(b: float) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(b) < 1024:
            return f"{b:.2f} {unit}"
        b /= 1024
    return f"{b:.2f} TB"


def fmt_duration(ms: float) -> str:
    if ms < 1000:
        return f"{ms:.1f} ms"
    return f"{ms / 1000:.2f} s"


def get_process_rss() -> int:
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except Exception:
        return 0


def measure_query(conn, sql, params=None, label=""):
    start = time.perf_counter()
    if params:
        rows = conn.execute(sql, params).fetchall()
    else:
        rows = conn.execute(sql).fetchall()
    elapsed = (time.perf_counter() - start) * 1000
    return rows, elapsed


def api_request(path, params=None, timeout=120):
    """调用本地后端 API，返回 (data, elapsed_ms)"""
    base = "http://127.0.0.1:8000"
    url = base + path
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url += "?" + query
    start = time.perf_counter()
    try:
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = json.loads(resp.read().decode())
        elapsed = (time.perf_counter() - start) * 1000
        return data, elapsed
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return {"error": str(e)}, elapsed


def main():
    print("=" * 70)
    print("芙清 CRM — DuckDB 内存与 RFM 查询性能测量")
    print(f"测量时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"DuckDB 路径: {DUCKDB_PATH}")
    print("=" * 70)

    # ────────────────────────────────────────────────────────
    # Part A: read-only 连接做表统计和内存分析
    # ────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("[Part A] DuckDB 文件与表统计（read-only）")
    print("=" * 70)

    file_size = DUCKDB_PATH.stat().st_size
    print(f"\n  数据库文件大小: {fmt_bytes(file_size)}")

    # 检查 WAL 和 temp 文件
    wal_path = DUCKDB_PATH.parent / (DUCKDB_PATH.name + ".wal")
    if wal_path.exists():
        print(f"  WAL 文件大小:   {fmt_bytes(wal_path.stat().st_size)}")

    conn_ro = duckdb.connect(str(DUCKDB_PATH), config={"access_mode": "READ_ONLY", "memory_limit": DUCKDB_MEMORY_LIMIT})

    # 表行数统计
    print("\n  各表行数:")
    tables = conn_ro.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='main' ORDER BY table_name"
    ).fetchall()
    table_stats = {}
    for (tbl,) in tables:
        try:
            count = conn_ro.execute(f'SELECT COUNT(*) FROM "{tbl}"').fetchone()[0]
            table_stats[tbl] = count
            marker = ""
            if tbl == "orders":
                marker = "  <-- 订单主表"
            elif tbl == "user_rfm":
                marker = "  <-- RFM 预计算"
            elif tbl == "rfm_analysis_cache":
                marker = "  <-- RFM 缓存"
            print(f"    {tbl:35s}  {count:>14,} 行{marker}")
        except Exception as e:
            print(f"    {tbl:35s}  ERROR: {e}")

    # user_rfm 分区分布
    print("\n  user_rfm 预计算表分区分布:")
    try:
        dist = conn_ro.execute("""
            SELECT analysis_date, metric_type, lookback_days, channel, COUNT(*)
            FROM user_rfm
            GROUP BY 1,2,3,4
            ORDER BY 1 DESC, 2, 3
        """).fetchall()
        print(f"    {'日期':12s} {'指标':6s} {'回看':8s} {'渠道':10s} {'行数':>10s}")
        print("    " + "-" * 56)
        for row in dist[:20]:
            print(f"    {str(row[0]):12s} {row[1]:6s} {row[2]:>6d}d  {row[3]:10s} {row[4]:>10,}")
        if len(dist) > 20:
            print(f"    ... 共 {len(dist)} 个分区")
    except Exception as e:
        print(f"    ERROR: {e}")

    # rfm_analysis_cache 缓存表
    print("\n  rfm_analysis_cache 缓存表:")
    try:
        cache_count = conn_ro.execute("SELECT COUNT(*) FROM rfm_analysis_cache").fetchone()[0]
        print(f"    缓存条目数: {cache_count}")
        if cache_count > 0:
            cache_info = conn_ro.execute("""
                SELECT period, start_date, end_date, metric_type,
                       LENGTH(result_json) as json_size, computed_at
                FROM rfm_analysis_cache
                ORDER BY computed_at DESC
                LIMIT 10
            """).fetchall()
            print(f"    {'周期':8s} {'开始':12s} {'结束':12s} {'指标':6s} {'JSON大小':>10s} {'计算时间'}")
            print("    " + "-" * 70)
            for r in cache_info:
                print(f"    {r[0] or '':8s} {r[1] or '':12s} {r[2] or '':12s} {r[3]:6s} {fmt_bytes(r[4]):>10s} {r[5]}")
    except Exception as e:
        print(f"    ERROR: {e}")

    # DuckDB 内存统计
    print("\n  DuckDB 内存分配器:")
    try:
        mem = conn_ro.execute("SELECT * FROM duckdb_memory()").fetchall()
        desc = conn_ro.execute("SELECT * FROM duckdb_memory()").description
        cols = [d[0] for d in desc]
        for row in mem:
            entry = dict(zip(cols, row))
            tag = entry.get("tag", "?")
            alloc = entry.get("allocator_memory_usage", 0)
            temp = entry.get("temporary_memory_usage", 0)
            print(f"    {tag:20s}  alloc={fmt_bytes(alloc):>12s}  temp={fmt_bytes(temp):>12s}")
    except Exception as e:
        print(f"    (查询失败: {e})")

    # DuckDB 配置
    print("\n  DuckDB 关键配置:")
    try:
        configs = [
            "memory_limit", "threads", "max_memory",
            "temp_directory", "enable_progress_bar"
        ]
        for cfg in configs:
            try:
                val = conn_ro.execute(f"SELECT current_setting('{cfg}')").fetchone()[0]
                print(f"    {cfg:25s} = {val}")
            except Exception:
                pass
    except Exception:
        pass

    conn_ro.close()

    # ────────────────────────────────────────────────────────
    # Part B: 通过 API 测量真实查询延迟
    # ────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("[Part B] RFM API 查询延迟测量（HTTP API）")
    print("=" * 70)

    # B1. 健康检查
    print("\n  B1. 后端健康检查:")
    data, t = api_request("/health")
    if "error" in data:
        print(f"    ERROR: {data['error']}")
        print("    （后端未运行，跳过 API 测量）")
    else:
        print(f"    状态: OK  ({fmt_duration(t)})")

    # B2. RFM 分析 API（全店 GSV，当月）
    print("\n  B2. RFM 分析 API（当月 MTD，全店 GSV）:")
    data, t = api_request("/api/v1/health/rfm-analysis", {
        "metric_type": "GSV",
        "period": "MTD"
    })
    if "error" in data:
        print(f"    ERROR: {data['error']}")
    else:
        rows = data.get("rows", [])
        year_label = data.get("year_label", "?")
        total_hist = sum(r.get("hist_users_current", 0) for r in rows)
        total_rep = sum(r.get("repurchase_users_current", 0) for r in rows)
        print(f"    年份标签: {year_label}")
        print(f"    耗时: {fmt_duration(t)}")
        print(f"    历史用户总计: {total_hist:,}")
        print(f"    购买用户总计: {total_rep:,}")
        if rows:
            print("    分群明细:")
            for r in rows:
                seg = r.get("rfm_segment", "?")
                hist = r.get("hist_users_current", 0)
                rep = r.get("repurchase_users_current", 0)
                rate = r.get("repurchase_rate_current", 0)
                print(f"      {seg:12s}  历史: {hist:>10,}  购买: {rep:>10,}  回购率: {rate:.2%}")

    # B3. RFM 分析 API（YTD）
    print("\n  B3. RFM 分析 API（YTD，全店 GSV）:")
    data, t = api_request("/api/v1/health/rfm-analysis", {
        "metric_type": "GSV",
        "period": "YTD"
    })
    if "error" in data:
        print(f"    ERROR: {data['error']}")
    else:
        rows = data.get("rows", [])
        total_hist = sum(r.get("hist_users_current", 0) for r in rows)
        print(f"    耗时: {fmt_duration(t)}")
        print(f"    历史用户总计: {total_hist:,}")

    # B4. RFM 分析 API（指定渠道）
    print("\n  B4. RFM 分析 API（YTD，自播渠道）:")
    data, t = api_request("/api/v1/health/rfm-analysis", {
        "metric_type": "GSV",
        "period": "YTD",
        "channel": "自播"
    })
    if "error" in data:
        print(f"    ERROR: {data['error']}")
    else:
        rows = data.get("rows", [])
        total_hist = sum(r.get("hist_users_current", 0) for r in rows)
        print(f"    耗时: {fmt_duration(t)}")
        print(f"    历史用户总计: {total_hist:,}")

    # B5. 连续调用测试（缓存命中情况）
    print("\n  B5. 缓存命中测试（连续 3 次相同请求 YTD GSV）:")
    times = []
    for i in range(3):
        data, t = api_request("/api/v1/health/rfm-analysis", {
            "metric_type": "GSV",
            "period": "YTD"
        })
        times.append(t)
        status = "OK" if "error" not in data else "ERROR"
        print(f"    第 {i+1} 次: {fmt_duration(t)} ({status})")
    if len(times) >= 2:
        print(f"    首次/后续比: {times[0]:.0f}ms / {times[1]:.0f}ms = {times[0]/times[1]:.1f}x")

    # ────────────────────────────────────────────────────────
    # Part C: 内存追踪
    # ────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("[Part C] Python 内存追踪")
    print("=" * 70)

    tracemalloc.start()
    conn_ro2 = duckdb.connect(str(DUCKDB_PATH), config={"access_mode": "READ_ONLY", "memory_limit": DUCKDB_MEMORY_LIMIT})
    snapshot1 = tracemalloc.take_snapshot()

    # 执行 user_rfm 聚合
    today_str = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    conn_ro2.execute("""
        SELECT rfm_tier, COUNT(*), SUM(monetary), AVG(recency_days)
        FROM user_rfm
        WHERE analysis_date = ? AND lookback_days = 90 AND metric_type = 'GSV' AND channel = '全店'
        GROUP BY rfm_tier
    """, [today_str]).fetchall()

    snapshot2 = tracemalloc.take_snapshot()
    stats = snapshot2.compare_to(snapshot1, "lineno")
    print("  Top 5 内存增量:")
    for s in stats[:5]:
        print(f"    {s}")

    current, peak = tracemalloc.get_traced_memory()
    print(f"\n  Python 当前内存: {fmt_bytes(current)}")
    print(f"  Python 峰值内存: {fmt_bytes(peak)}")
    tracemalloc.stop()
    conn_ro2.close()

    # 进程 RSS
    print(f"  进程 RSS (resource): {fmt_bytes(get_process_rss())}")

    # ────────────────────────────────────────────────────────
    # 汇总
    # ────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("汇总报告")
    print("=" * 70)
    print(f"  DuckDB 文件大小:     {fmt_bytes(file_size)}")
    print(f"  orders 表行数:       {table_stats.get('orders', 0):,}")
    print(f"  user_rfm 表行数:     {table_stats.get('user_rfm', 0):,}")
    print(f"  RFM 缓存条目数:      {table_stats.get('rfm_analysis_cache', 0):,}")
    print()


if __name__ == "__main__":
    main()
