#!/usr/bin/env python3
"""Sprint 201+ R7 MEMORY.md 24.4KB 维护监控 (L4.13 永久规则 + L4.59 永久规则化)

- 每周日 04:00 launchd 触发
- 检查 MEMORY.md 大小 > 24576 → 告警 (dedup 由 Claude 手动跑)
- 0 FAIL → print "MEMORY_SIZE_MONITOR_OK"
- fail-open: 异常 stderr warn + exit 0 (跟 L4.40 post-merge hook 配套)
"""
from __future__ import annotations

import sys
from pathlib import Path

MEMORY_PATH = Path.home() / ".claude/projects/-Users-hutou/memory/MEMORY.md"
LIMIT_BYTES = 24576  # L4.13 永久规则 (Claude Code 平台硬限制)
LOG_FILE = Path("/tmp/fuqing-memory-size.log")
TECH_DEBT = Path("/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/docs/TECH-DEBT.md")


def get_memory_size() -> int:
    return MEMORY_PATH.stat().st_size if MEMORY_PATH.exists() else 0


def append_tech_debt(msg: str) -> None:
    """跨 sprint 留尾告警 (跟 L4.12 SSOT 配套)"""
    try:
        if not TECH_DEBT.exists():
            TECH_DEBT.write_text("# Tech Debt (Sprint 67+ L4.12 SSOT)\n\n")
        with TECH_DEBT.open("a") as f:
            f.write(f"\n## R7 MEMORY.md Size Alert (Sprint 201+)\n\n{msg}\n")
    except Exception as e:
        print(f"[MEMORY_SIZE_MONITOR] TECH_DEBT write failed: {e}", file=sys.stderr)


def main() -> int:
    try:
        size = get_memory_size()
        pct = (size / LIMIT_BYTES) * 100

        if size > LIMIT_BYTES:
            msg = (
                f"[MEMORY_SIZE_MONITOR] OVER LIMIT: {size} bytes ({pct:.1f}%) > {LIMIT_BYTES}, "
                f"dedup SOP triggered (跟 Sprint 69 1:1 stable)"
            )
            print(msg)
            with LOG_FILE.open("a") as f:
                f.write(f"{msg}\n")
            append_tech_debt(
                f"- size={size} bytes ({pct:.1f}%) > {LIMIT_BYTES}\n"
                f"- ACTION: Claude 手动跑 dedup SOP (删 Sprint N 之前 close memory 索引行 → 1 行指针)"
            )
            # fail-open: 监控不阻 commit
            return 0

        msg = f"MEMORY_SIZE_MONITOR_OK {size} bytes ({pct:.1f}%) <= {LIMIT_BYTES}"
        print(msg)
        with LOG_FILE.open("a") as f:
            f.write(f"{msg}\n")
        return 0
    except Exception as e:
        # fail-open: 异常不阻 commit
        warn = f"[MEMORY_SIZE_MONITOR] EXCEPTION (fail-open): {type(e).__name__}: {e}"
        print(warn, file=sys.stderr)
        with LOG_FILE.open("a") as f:
            f.write(f"{warn}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())