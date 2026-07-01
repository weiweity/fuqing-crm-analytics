#!/usr/bin/env python3
"""session_start_check.py — Sprint 178+ SessionStart hook

Claude Code session 启动时自动检查:
1. MEMORY.md 大小 vs 24.4KB L4.13 limit
2. main HEAD 跟 origin/main drift
3. .githooks 是否激活
4. 当前分支未提交修改

不阻塞 session, 仅提示 (跟 Sprint 67 UserPromptSubmit hook 模式 stable).
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return 1, str(e)


def main() -> int:
    print("\n=== Sprint 178 SessionStart 检查 ===")

    # 1. MEMORY.md 大小
    mem_path = Path.home() / ".claude" / "projects" / "-Users-hutou" / "memory" / "MEMORY.md"
    if mem_path.exists():
        size = mem_path.stat().st_size
        limit = 24_576  # 24.4KB L4.13
        pct = size / limit * 100
        marker = "🚨" if size > limit else ("⚠️" if size > 17_100 else "✅")
        print(f"  {marker} MEMORY.md: {size} bytes ({pct:.1f}% of 24.4KB L4.13 limit)")
        if size > limit:
            print(f"     → 跑 Sprint 178 dedupe SOP: 删旧 sprint 指针")
    else:
        print("  ⚠️  MEMORY.md not found")

    # 2. main drift
    rc, out = run(["git", "rev-parse", "--verify", "main"])
    if rc == 0:
        local_main = out.strip()
    else:
        local_main = "?"
    rc2, out2 = run(["git", "rev-parse", "--verify", "origin/main"])
    if rc2 == 0:
        remote_main = out2.strip()
    else:
        remote_main = "?"
    if local_main == remote_main and local_main != "?":
        print(f"  ✅ main HEAD = origin/main = {local_main[:7]} (0 drift)")
    elif local_main != "?" and remote_main != "?":
        print(f"  ⚠️  main drift: local {local_main[:7]} vs origin {remote_main[:7]}")

    # 3. .githooks 激活
    rc, out = run(["git", "config", "core.hooksPath"])
    hooks_path = out.strip() if rc == 0 else ""
    expected = ".githooks"  # git config 存的是相对 git toplevel 的相对路径
    # 兼容绝对路径 (老版本可能存绝对)
    if hooks_path in (expected, str(REPO_ROOT / ".githooks")):
        print(f"  ✅ core.hooksPath = {hooks_path}")
    elif "/pytest-of-" in hooks_path or hooks_path.endswith("/.git/hooks"):
        print(f"  🚨 core.hooksPath 被污染: {hooks_path}")
        print(f"     → 自动恢复: git config core.hooksPath .githooks")
        run(["git", "config", "--unset", "core.hooksPath"])
        run(["git", "config", "core.hooksPath", ".githooks"])
    else:
        print(f"  ⚠️  core.hooksPath 异常: {hooks_path}")
        print(f"     → 期望: {expected}")

    # 4. 当前分支未提交
    rc, out = run(["git", "status", "--porcelain"])
    if rc == 0 and out.strip():
        lines = out.strip().split("\n")
        print(f"  ⚠️  {len(lines)} 个 uncommitted 改动 (CLAUDE.md §0 强制: main 上禁止 commit)")
    else:
        print("  ✅ 无未提交改动")

    print("=== SessionStart 完成 ===\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())