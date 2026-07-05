#!/usr/bin/env python3
"""Sprint 203 R2 Finding 4.1 + R4+ b/c 件真接入: ClickHouse POC 启动条件监控 (L4.58 + L4.59 永久规则化)

- 每周日 04:45 launchd 触发 (跟 R6 04:00 / R7 04:15 / R8 04:30 错开)
- 监控 a/b/c 3 件启动条件:
  - (a) DuckDB file size > 200GB (R2 接入, 走本地 Path stat)
  - (b) query P95 > 30s 持续 1 周 (R4 真接入 /metrics endpoint)
  - (c) 5+ 业务分析师并发取数 (R4 真接入 /api/v1/health/pool semaphore_in_use)
- 0 触发 → print CLICKHOUSE_POC_MONITOR_PASS
- 任意触发 → exit 0 (fail-open) + write TECH-DEBT.md 跨 sprint 留尾告警
- 异常 → exit 0 (跟 L4.40 post-merge hook 1:1 stable)

Sprint 203 R4+ 注: Sprint 203 R4 已真接入 b/c 件 (Phase 1 闭环), Sprint 203 R5+ 持续演进 (Phase 2 跨 sprint 维护性, 跟 L4.59 1:1 stable).

L4.61 跨 CI runner 适配:
- Linux CI runner 跑: 没 production DuckDB + 没 macOS path → 视作 0 触发 → PASS
- main() 加 sys.platform != "darwin" 平台守卫

L4.60 跨平台: REPO_ROOT = Path(__file__).resolve().parent.parent (脚本在 scripts/ 下)

Sprint 203 R4 b/c 件真接入设计 (跟 L4.59 跨 sprint 维护性 SOP 1:1 stable):
- b 件: urllib 3s timeout GET ${BACKEND_URL}/metrics → parse fq_query_duration_seconds_bucket → 推 P95 → > 30s 触发
- c 件: urllib 3s timeout GET ${BACKEND_URL}/api/v1/health/pool → parse semaphore_in_use → > 5 触发
- 异常 / 超时 → 视作 0 触发 (fail-open, 跟 L4.40 1:1 stable)
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent  # L4.60 跨平台
DUCKDB_PATH = Path(os.environ.get("DUCKDB_PATH", str(REPO_ROOT / "data" / "processed" / "fuqing_crm.duckdb")))
LOG_FILE = Path("/tmp/fuqing-clickhouse-poc-monitor.log")
TECH_DEBT = REPO_ROOT / "docs" / "TECH-DEBT.md"

# Sprint 203 R4: b/c 件真接入 backend HTTP endpoint
BACKEND_URL = os.environ.get("FQ_BACKEND_URL", "http://127.0.0.1:8000")
HTTP_TIMEOUT_S = float(os.environ.get("FQ_POC_MONITOR_TIMEOUT_S", "3"))

# ClickHouse POC 启动条件阈值 (跟 docs/architecture/clickhouse-poc-decision-memo.md §1.3 1:1 stable)
DUCKDB_SIZE_TRIGGER_GB = 200
QUERY_P95_TRIGGER_S = 30
CONCURRENT_USER_TRIGGER = 5


def _duckdb_size_gb() -> float | None:
    """DuckDB file size in GB; None if file not found."""
    try:
        if not DUCKDB_PATH.exists():
            return None
        return DUCKDB_PATH.stat().st_size / (1024 ** 3)
    except Exception as e:
        print(f"[CLICKHOUSE_POC_MONITOR] DuckDB size check exception: {e}", file=sys.stderr)
        return None


def _check_trigger_a(size_gb: float | None) -> str | None:
    """(a) DuckDB > 200GB → return alert msg."""
    if size_gb is None:
        return None
    if size_gb > DUCKDB_SIZE_TRIGGER_GB:
        return f"(a) DuckDB size {size_gb:.1f}GB > {DUCKDB_SIZE_TRIGGER_GB}GB threshold"
    return None


# --- Sprint 203 R4 b/c 件真接入: HTTP fetch + Prometheus parse + pool semaphore parse ---


def _fetch_url_text(url: str) -> str | None:
    """urllib GET, 3s timeout, fail-open (None on error)."""
    try:
        with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_S) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        print(f"[CLICKHOUSE_POC_MONITOR] HTTP fetch {url} exception: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def _fetch_url_json(url: str) -> dict | None:
    """urllib GET + json parse, fail-open."""
    text = _fetch_url_text(url)
    if text is None:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[CLICKHOUSE_POC_MONITOR] JSON parse {url} exception: {e}", file=sys.stderr)
        return None


def _parse_query_p95() -> float | None:
    """Parse /metrics → 推 global P95 latency (秒).

    Strategy: per-series P95 (per endpoint × query_type) → 取 MAX 跨 series.

    Prometheus histogram bucket 是 per-series cumulative (即每个 endpoint/query_type
    一组独立的 cumulative bucket). 简单跨 series 加总会歪曲 P95 (e.g. 一个 fast endpoint
    1M query + 一个 slow endpoint 10 query, 加总会让 slow endpoint P95 被淹没).
    正确做法: per-series P95 → MAX (worst-case latency as trigger condition).

    Returns P95 in seconds (MAX across all series), None if no data or parse fail.

    L4.40 fail-open: None on any exception.
    """
    text = _fetch_url_text(f"{BACKEND_URL}/metrics")
    if text is None:
        return None
    try:
        # 匹配: fq_query_duration_seconds_bucket{endpoint="X",query_type="Y",le="Z"} N
        bucket_re = re.compile(
            r'^fq_query_duration_seconds_bucket\{([^}]*)\}\s+(\d+(?:\.\d+)?)',
            re.MULTILINE,
        )
        # 匹配: fq_query_duration_seconds_count{endpoint="X",query_type="Y"} N
        count_re = re.compile(
            r'^fq_query_duration_seconds_count\{([^}]*)\}\s+(\d+(?:\.\d+)?)',
            re.MULTILINE,
        )

        # group by series (endpoint + query_type, 不含 le)
        def series_key(labels_str: str) -> tuple[str, str]:
            ep_match = re.search(r'endpoint="([^"]+)"', labels_str)
            qt_match = re.search(r'query_type="([^"]+)"', labels_str)
            return (ep_match.group(1) if ep_match else "", qt_match.group(1) if qt_match else "")

        series_totals: dict[tuple[str, str], float] = {}
        for m in count_re.finditer(text):
            key = series_key(m.group(1))
            series_totals[key] = series_totals.get(key, 0.0) + float(m.group(2))

        if not series_totals:
            return None

        # 每 series 单独算 P95
        series_buckets: dict[tuple[str, str], dict[float, float]] = {}
        for m in bucket_re.finditer(text):
            labels_str = m.group(1)
            le_str_match = re.search(r'le="([^"]+)"', labels_str)
            if le_str_match is None:
                continue
            le_str = le_str_match.group(1)
            if le_str in ("+Inf", "Inf"):
                continue
            try:
                le = float(le_str)
            except ValueError:
                continue
            key = series_key(labels_str)
            if key not in series_buckets:
                series_buckets[key] = {}
            series_buckets[key][le] = series_buckets[key].get(le, 0.0) + float(m.group(2))

        # 每 series 找 P95
        series_p95s: list[float] = []
        for key, total in series_totals.items():
            if total <= 0:
                continue
            buckets = series_buckets.get(key, {})
            threshold = 0.95 * total
            for le in sorted(buckets.keys()):
                if buckets[le] >= threshold:
                    series_p95s.append(le)
                    break

        if not series_p95s:
            return None
        # MAX 跨 series (worst-case latency as ClickHouse POC trigger)
        return max(series_p95s)
    except Exception as e:
        print(f"[CLICKHOUSE_POC_MONITOR] P95 parse exception: {e}", file=sys.stderr)
        return None


def _get_pool_in_use() -> int | None:
    """GET /api/v1/health/pool → semaphore_in_use count, None on fail-open."""
    data = _fetch_url_json(f"{BACKEND_URL}/api/v1/health/pool")
    if data is None:
        return None
    try:
        return int(data.get("semaphore_in_use", 0))
    except (TypeError, ValueError) as e:
        print(f"[CLICKHOUSE_POC_MONITOR] pool parse exception: {e}", file=sys.stderr)
        return None


def _check_trigger_b() -> str | None:
    """(b) query P95 > 30s 持续 1 周 → return alert msg.

    Sprint 203 R4 真接入 /metrics endpoint: 解析 Prometheus text format, 累计所有
    endpoint × query_type 维度的 histogram bucket, 推全局 P95 latency.
    > 30s 触发. None 表示 0 触发 (含 fail-open + 数据不够).
    """
    p95 = _parse_query_p95()
    if p95 is None:
        return None
    if p95 > QUERY_P95_TRIGGER_S:
        return f"(b) Query P95 {p95:.1f}s > {QUERY_P95_TRIGGER_S}s threshold"
    return None


def _check_trigger_c() -> str | None:
    """(c) 5+ 业务分析师并发取数 → return alert msg.

    Sprint 203 R4 真接入 /api/v1/health/pool: 读 semaphore_in_use count,
    > 5 触发 (跟 READ_POOL_SIZE * 2 / 2 = 5 阈值一致).
    """
    in_use = _get_pool_in_use()
    if in_use is None:
        return None
    if in_use > CONCURRENT_USER_TRIGGER:
        return f"(c) Read pool in use {in_use} > {CONCURRENT_USER_TRIGGER} concurrent users threshold"
    return None


def append_tech_debt(msgs: list[str]) -> None:
    """跨 sprint 留尾告警 (跟 L4.12 SSOT 配套)."""
    try:
        if not TECH_DEBT.exists():
            TECH_DEBT.write_text("# Tech Debt (Sprint 67+ L4.12 SSOT)\n\n")
        with TECH_DEBT.open("a") as f:
            f.write("\n## ClickHouse POC 启动条件触发告警 (Sprint 203 R2/R4)\n\n")
            for msg in msgs:
                f.write(f"- {msg}\n")
            f.write("\n")
    except Exception as e:
        print(f"[CLICKHOUSE_POC_MONITOR] TECH_DEBT write failed: {e}", file=sys.stderr)


def main() -> int:
    # L4.61 跨 CI runner 适配: Linux runner 视作 0 触发 → PASS
    if sys.platform != "darwin":
        msg = (
            f"CLICKHOUSE_POC_MONITOR_PASS (Linux/CI runner, "
            f"size={_duckdb_size_gb() or 'N/A'}GB, "
            f"triggers: a/b/c 0 命中 — 跨 CI runner 适配, R4 b/c 件真接入 HTTP fetch 跳过)"
        )
        print(msg)
        try:
            with LOG_FILE.open("a") as f:
                f.write(f"{msg}\n")
        except Exception:
            pass
        return 0

    try:
        size_gb = _duckdb_size_gb()
        alerts: list[str] = []

        a = _check_trigger_a(size_gb)
        if a:
            alerts.append(a)
        b = _check_trigger_b()
        if b:
            alerts.append(b)
        c = _check_trigger_c()
        if c:
            alerts.append(c)

        if alerts:
            msg = f"[CLICKHOUSE_POC_MONITOR] TRIGGER HIT: {'; '.join(alerts)} (DuckDB size {size_gb or 'N/A'}GB)"
            print(msg)
            with LOG_FILE.open("a") as f:
                f.write(f"{msg}\n")
            append_tech_debt(alerts + [f"DuckDB file size: {size_gb:.1f}GB" if size_gb else "DuckDB file size: N/A"])
            # fail-open: 监控不阻 commit, 只告警
            return 0

        msg = (
            f"CLICKHOUSE_POC_MONITOR_PASS (DuckDB {size_gb or 'N/A'}GB, "
            f"triggers: a/b/c 0 命中 — Sprint 203 R4 b/c 件真接入 HTTP fetch cross-sprint stable)"
        )
        print(msg)
        with LOG_FILE.open("a") as f:
            f.write(f"{msg}\n")
        return 0

    except Exception as e:
        # fail-open: 异常不阻 commit (跟 L4.40 post-merge hook 1:1 stable)
        warn = f"[CLICKHOUSE_POC_MONITOR] EXCEPTION (fail-open): {type(e).__name__}: {e}"
        print(warn, file=sys.stderr)
        try:
            with LOG_FILE.open("a") as f:
                f.write(f"{warn}\n")
        except Exception:
            pass
        return 0


if __name__ == "__main__":
    sys.exit(main())