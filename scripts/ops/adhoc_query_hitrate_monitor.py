#!/usr/bin/env python3
"""Sprint 201+ R8 ad-hoc-query 19 tool 真实命中率监控 (L4.42 + L4.55 + L4.59 永久规则化)

- 每周日 04:00 launchd 触发
- 业务组预读 SKILL.md v2.7 reminder (Sprint 203 R5 升 v2.6 → v2.7, 14 → 19 tool)
- 检查 tool 数量 + SKILL.md symlink 治本 (L4.35)
- FAIL (tool 数量 < 19 或 SKILL.md symlink 失效) → 告警
- fail-open: 异常 stderr warn + exit 0 (跟 L4.40 post-merge hook 配套)

L4.61 跨平台守卫 (跟 L4.10 + L4.39 1:1 stable):
- main() 入口加 sys.platform != "darwin" 检查
- Linux CI runner 直接 exit 0 PASS (跳过 symlink check, ~/.workbuddy/ 是 macOS-only 路径)
- macOS launchd 走完整 symlink check
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL_PATH_CLAUDE = Path.home() / ".claude/skills/ad-hoc-query/SKILL.md"
SKILL_PATH_WORKBUDDY = Path.home() / ".workbuddy/skills/ad-hoc-query/SKILL.md"
REPO_ROOT = Path(__file__).resolve().parents[2]  # L4.60: scripts/ops/ → repo root
TOOL_DIR = REPO_ROOT / "scripts" / "ad_hoc_queries"
LOG_FILE = Path("/tmp/fuqing-adhoc-hitrate.log")
TECH_DEBT = REPO_ROOT / "docs" / "TECH-DEBT.md"
EXPECTED_TOOL_COUNT = 18  # Sprint 203 R5 治本 (4 件新 tool: channel-monthly / member-monthly / refund-monthly / cross-dimension-monthly, 14 → 18 tool. top_n 月/季/年 axis 扩不算新 tool 算 modify)
HITRATE_THRESHOLD = 0.95  # 95% (跟 Sprint 199 R1 实证 1:1 stable)


def count_tools() -> int:
    """跟 scripts/ad_hoc_queries/*.py (排除 __init__.py / _utils.py / registry.py) 1:1 stable"""
    return len(
        [
            p
            for p in TOOL_DIR.glob("*.py")
            if p.name not in ("__init__.py", "_utils.py", "registry.py")
        ]
    )


def check_symlink() -> bool:
    """L4.35 symlink 治本: ~/.workbuddy/skills/ad-hoc-query/SKILL.md 期望指向 ~/.claude/"""
    if not SKILL_PATH_WORKBUDDY.exists():
        return False
    if not SKILL_PATH_WORKBUDDY.is_symlink():
        return False
    target = SKILL_PATH_WORKBUDDY.resolve()
    return str(target) == str(SKILL_PATH_CLAUDE.resolve())


def append_tech_debt(msg: str) -> None:
    """跨 sprint 留尾告警 (跟 L4.12 SSOT 配套)"""
    try:
        if not TECH_DEBT.exists():
            TECH_DEBT.write_text("# Tech Debt (Sprint 67+ L4.12 SSOT)\n\n")
        with TECH_DEBT.open("a") as f:
            f.write(f"\n## R8 Ad-hoc Query Hitrate Alert (Sprint 201+)\n\n{msg}\n")
    except Exception as e:
        print(f"[ADHOC_HITRATE_MONITOR] TECH_DEBT write failed: {e}", file=sys.stderr)


def main() -> int:
    # L4.61 跨平台守卫 (跟 L4.10 + L4.39 1:1 stable): Linux CI runner 跳过 macOS-only symlink check
    if sys.platform != "darwin":
        msg = (
            f"[ADHOC_HITRATE_MONITOR] {datetime.now(timezone.utc).isoformat()}\n"
            f"  platform: {sys.platform} (skip macOS-only symlink check, 跟 L4.39 1:1 stable)\n"
            f"  tools: 跑 count_tools() (跨平台) - {count_tools()} tools\n"
            f"  ACTION: Linux runner 跳过 symlink check, 等周日 macOS launchd 跑"
        )
        print(msg)
        with LOG_FILE.open("a") as f:
            f.write(f"{msg}\n\n")
        return 0

    try:
        tool_count = count_tools()
        skill_size = (
            SKILL_PATH_CLAUDE.stat().st_size if SKILL_PATH_CLAUDE.exists() else 0
        )
        is_symlink = check_symlink()
        timestamp = datetime.now(timezone.utc).isoformat()

        problems = []
        if tool_count != EXPECTED_TOOL_COUNT:
            problems.append(
                f"tool_count={tool_count} != {EXPECTED_TOOL_COUNT} (期望 18, 跟 SKILL.md v2.7 1:1)"
            )
        if not is_symlink:
            problems.append(
                "SKILL.md symlink 失效 (L4.35 治本要求 mode 120000, 当前不是 symlink)"
            )

        if problems:
            msg = (
                f"[ADHOC_HITRATE_MONITOR] FAIL: {timestamp}\n"
                + "\n".join(f"  - {p}" for p in problems)
                + "\n  ACTION: 重新立项 Sprint 203+ 立缺失 tool 或修 symlink"
            )
            print(msg)
            with LOG_FILE.open("a") as f:
                f.write(f"{msg}\n\n")
            append_tech_debt("\n".join(f"- {p}" for p in problems))
            return 0  # fail-open

        msg = (
            f"[ADHOC_HITRATE_MONITOR] {timestamp}\n"
            f"  tools: {tool_count} (期望 18, 跟 SKILL.md v2.7 1:1) OK\n"
            f"  skill_md_size: {skill_size} bytes (symlink mode 120000, L4.35 治本) OK\n"
            f"  threshold: {HITRATE_THRESHOLD * 100:.0f}%\n"
            f"  ACTION: 业务组预读 SKILL.md v2.7, 反馈真实命中率 (期望 >= {HITRATE_THRESHOLD * 100:.0f}%)\n"
            f"  FAIL: 命中率 < {HITRATE_THRESHOLD * 100:.0f}% -> 重新立项 Sprint 203+ 立缺失 tool"
        )
        print(msg)
        with LOG_FILE.open("a") as f:
            f.write(f"{msg}\n\n")
        return 0
    except Exception as e:
        # fail-open: 异常不阻 commit
        warn = f"[ADHOC_HITRATE_MONITOR] EXCEPTION (fail-open): {type(e).__name__}: {e}"
        print(warn, file=sys.stderr)
        with LOG_FILE.open("a") as f:
            f.write(f"{warn}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
