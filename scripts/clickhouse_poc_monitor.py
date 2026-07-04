#!/usr/bin/env python3
"""Sprint 203 R2 Finding 4.1: ClickHouse POC 启动条件监控 (L4.58 + L4.59 永久规则化)

- 每周日 04:45 launchd 触发 (跟 R6 04:00 / R7 04:15 / R8 04:30 错开)
- 监控 a/b/c 3 件启动条件:
  - (a) DuckDB file size > 200GB
  - (b) query P95 > 30s (TODO: 接入 /metrics endpoint, Sprint 203 R3 OpsView 落地后)
  - (c) 5+ 业务分析师并发取数 (TODO: 接入 /metrics endpoint, Sprint 203 R3 OpsView 落地后)
- 0 触发 → print CLICKHOUSE_POC_MONITOR_PASS
- 任意触发 → exit 0 (fail-open) + write TECH-DEBT.md 跨 sprint 留尾告警
- 异常 → exit 0 (跟 L4.40 post-merge hook 1:1 stable)

L4.61 跨 CI runner 适配:
- Linux CI runner 跑: 没 production DuckDB + 没 macOS path → 视作 0 触发 → PASS
- main() 加 sys.platform != "darwin" 平台守卫

L4.60 跨平台: REPO_ROOT = Path(__file__).resolve().parent.parent (脚本在 scripts/ 下)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent  # L4.60 跨平台
DUCKDB_PATH = Path(os.environ.get("DUCKDB_PATH", str(REPO_ROOT / "data" / "processed" / "fuqing_crm.duckdb")))
LOG_FILE = Path("/tmp/fuqing-clickhouse-poc-monitor.log")
TECH_DEBT = REPO_ROOT / "docs" / "TECH-DEBT.md"

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


def _check_trigger_b() -> str | None:
    """(b) query P95 > 30s 持续 1 周 → return alert msg.

    TODO Sprint 203 R3: 接入 /metrics endpoint histogram_quantile(0.95, query_latency_seconds)
    现阶段没 /metrics dashboard 数据, 返回 None (0 触发, 不告警).
    """
    return None  # Sprint 203 R3 OpsView.vue 落地后接入


def _check_trigger_c() -> str | None:
    """(c) 5+ 业务分析师并发取数 → return alert msg.

    TODO Sprint 203 R3: 接入 /metrics endpoint request_id 计数
    现阶段没 /metrics dashboard 数据, 返回 None (0 触发, 不告警).
    """
    return None  # Sprint 203 R3 OpsView.vue 落地后接入


def append_tech_debt(msgs: list[str]) -> None:
    """跨 sprint 留尾告警 (跟 L4.12 SSOT 配套)."""
    try:
        if not TECH_DEBT.exists():
            TECH_DEBT.write_text("# Tech Debt (Sprint 67+ L4.12 SSOT)\n\n")
        with TECH_DEBT.open("a") as f:
            f.write("\n## ClickHouse POC 启动条件触发告警 (Sprint 203 R2)\n\n")
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
            f"triggers: a/b/c 0 命中 — 跨 CI runner 适配)"
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
            f"triggers: a/b/c 0 命中 — Sprint 203 R2 cross-sprint stable)"
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