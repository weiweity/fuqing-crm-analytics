#!/usr/bin/env python3
"""session_close_check.py — Sprint 178+ Stop hook

Claude Code session 结束前自动检查 (sprint close 必备):
1. 是否在 main 分支且有未 commit 修改 → 提醒 12 步流程
2. .ship-audit.log 是否已追加本次 sprint
3. MEMORY.md 是否需要 dedupe (接近 24.4KB limit)
4. L4.8 删分支 (检查本地/远程是否有已合并分支)
5. CHANGELOG.md 是否需要更新

不阻塞 session, 仅提醒 (silent skip on error).
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SHIP_LOG = REPO_ROOT / ".ship-audit.log"


def run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return 1, str(e)


def main() -> int:
    print("\n=== Sprint 178 Stop 检查 ===")

    # 1. main 分支 + 未 commit
    rc, branch = run(["git", "branch", "--show-current"])
    branch = branch.strip()
    rc, status = run(["git", "status", "--porcelain"])
    uncommitted = status.strip().split("\n") if status.strip() else []

    if branch == "main" and uncommitted:
        print(f"  🚨 main 分支有 {len(uncommitted)} 个未提交改动")
        print(f"     → CLAUDE.md §0 强制: 切 feature branch 才能 commit")
    elif branch != "main" and uncommitted:
        print(f"  💡 {branch} 分支有 {len(uncommitted)} 个未提交改动 (考虑 commit)")

    # 2. .ship-audit.log
    if SHIP_LOG.exists():
        with open(SHIP_LOG) as f:
            lines = [l for l in f.readlines() if l.strip()]
        if lines:
            last_line = lines[-1].strip()
            print(f"  ✅ .ship-audit.log 最新: {last_line[:80]}...")
        else:
            print(f"  ⚠️  .ship-audit.log 空")
    else:
        print(f"  ⚠️  .ship-audit.log 不存在 (新项目/未 ship 过)")

    # 3. MEMORY.md 大小
    mem_path = Path.home() / ".claude" / "projects" / "-Users-hutou" / "memory" / "MEMORY.md"
    if mem_path.exists():
        size = mem_path.stat().st_size
        limit = 24_576
        pct = size / limit * 100
        if size > limit:
            print(f"  🚨 MEMORY.md {size} bytes ({pct:.1f}%) 超 24.4KB L4.13 limit → 必 dedupe")
        elif size > 17_100:
            print(f"  ⚠️  MEMORY.md {size} bytes ({pct:.1f}%) 接近 limit (建议下次 sprint 收口 dedupe)")

    # 4. L4.8 删分支 (检查本地已 merge 但未删)
    rc, out = run(["git", "branch", "--format=%(refname:short)"])
    if rc == 0:
        branches = [b.strip() for b in out.split("\n") if b.strip() and b.strip() != "main"]
        merged_branches = []
        for b in branches:
            rc2, _ = run(["git", "merge-base", "--is-ancestor", b, "main"])
            if rc2 == 0:
                merged_branches.append(b)
        if merged_branches:
            print(f"  🚨 {len(merged_branches)} 个已 merge main 本地分支未删:")
            for b in merged_branches[:5]:
                print(f"     - {b}")
            if len(merged_branches) > 5:
                print(f"     ... + {len(merged_branches) - 5} 更多")
            print(f"     → 跑 python3 scripts/branch_cleanup.py 清理")

    # 5. CHANGELOG.md 提醒 (如果有 staged .py 但 CHANGELOG 没改)
    rc, staged = run(["git", "diff", "--cached", "--name-only"])
    if rc == 0 and staged.strip():
        staged_files = staged.strip().split("\n")
        has_py = any(f.endswith(".py") for f in staged_files)
        has_changelog = any("CHANGELOG.md" in f for f in staged_files)
        if has_py and not has_changelog:
            print(f"  💡 改 .py 但未改 CHANGELOG.md (建议同步, sprint 178+ L4.x 配套)")

    print("=== Stop 检查完成 ===\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())