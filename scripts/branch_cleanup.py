#!/usr/bin/env python3
"""branch_cleanup.py — Sprint 177+ L4.8 自动化: 删本地+远程已 merge main 的分支

触发方式 (Claude Code hook):
- PostToolUse matcher=Bash
- 检测 Bash command 包含 "git push origin main" 模式
- 自动检测本地 + 远程已 merge main 的分支, 一键删除

用法 (manual):
    python3 scripts/branch_cleanup.py [--dry-run] [--keep-protected]

保护分支 (永不删):
    main / master / HEAD
    sprint175/main-multi-fix (历史 metadata 分支, Sprint 176 close 已迁)
    feature/*-sprint172|173|174|175 (Sprint 172-175 已合并保留作为历史)
    fix/sprint173-month-week-window-fallback (Sprint 173 已合并)

排除规则 (跨 sprint 实战 fix):
- 当前分支永远不删
- main / master / HEAD / develop
- origin/main HEAD

Sprint 177 实战 fix 模式 #61:
- push main 后 hook 自动扫
- "✅ 删除 X 个本地分支" / "✅ 删除 Y 个远程分支" / 跟 L4.8 永久规则配套
- 网络超时 silent skip (跟 Sprint 176.1 hot reload retry 模式 stable)
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from typing import List, Tuple

PROTECTED = {
    "main",
    "master",
    "HEAD",
    "develop",
    # Sprint 172-175 已合并分支, 作为历史保留 (用户拍板)
    "feature/export-btn-styles-sprint172",
    "feature/sprint174-export-excel-cleanup",
    "fix/sprint173-month-week-window-fallback",
    "sprint175/health-rm-decode",
    "sprint175/market-focus",
    "sprint175/sampling-ui",
    "sprint175/main-multi-fix",
}


def run(cmd: List[str], timeout: int = 30) -> Tuple[int, str]:
    """Run subprocess, return (returncode, output). Silent on network timeout."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, ""  # 跟 git 124 timeout exit code 一致
    except Exception as e:
        return 1, str(e)


def get_local_merged() -> List[str]:
    """列出本地已 merge main 的分支 (排除 PROTECTED + 当前分支)."""
    rc, out = run(["git", "branch", "--format=%(refname:short)"])
    if rc != 0:
        return []
    branches = [b.strip() for b in out.split("\n") if b.strip()]
    # 当前分支不删
    rc_cur, cur = run(["git", "branch", "--show-current"])
    current = cur.strip() if rc_cur == 0 else ""
    return [b for b in branches if b and b not in PROTECTED and b != current and not b.startswith("origin/")]


def get_remote_merged() -> List[str]:
    """列出远程已 merge origin/main 的分支 (排除 PROTECTED)."""
    rc, out = run(["git", "branch", "-r", "--format=%(refname:short)"])
    if rc != 0:
        return []
    branches = [b.strip() for b in out.split("\n") if b.strip()]
    # 排除 origin (HEAD 拆解) + origin/main + PROTECTED
    return [
        b for b in branches
        if b
        and b != "origin"  # origin/HEAD 拆解的占位
        and not b.endswith("/HEAD")
        and not b.endswith("/main")
        and b not in PROTECTED
    ]


def is_merged(branch: str, base: str = "main") -> bool:
    """检查 branch 是否已 merge 进 base."""
    rc, _ = run(["git", "merge-base", "--is-ancestor", branch, base])
    return rc == 0


def delete_local(branch: str, dry_run: bool = False) -> bool:
    """删本地分支 (已 merge 走 -d, 未 merge 走 -D 防御)."""
    if dry_run:
        print(f"  [dry-run] would delete local: {branch}")
        return True
    rc, out = run(["git", "branch", "-d", branch])
    if rc != 0:
        # Unmerged 走 -D (防御误删)
        rc2, out2 = run(["git", "branch", "-D", branch])
        if rc2 == 0:
            print(f"  [force -D] local: {branch}")
            return True
        print(f"  ✗ failed delete local {branch}: {out2}")
        return False
    print(f"  ✅ local: {branch}")
    return True


def delete_remote(branch: str, dry_run: bool = False) -> bool:
    """删远程分支 (silent skip on network timeout)."""
    if dry_run:
        print(f"  [dry-run] would delete remote: {branch}")
        return True
    rc, out = run(["git", "push", "origin", "--delete", branch], timeout=60)
    if rc == 0:
        print(f"  ✅ remote: {branch}")
        return True
    if rc == 124:
        print(f"  ⏭ silent skip remote (network timeout): {branch}")
        return False
    print(f"  ✗ failed delete remote {branch}: {out[:100]}")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Sprint 177+ L4.8 自动化: 删已 merge main 的分支")
    parser.add_argument("--dry-run", action="store_true", help="只看, 不真删")
    parser.add_argument("--keep-protected", action="store_true", default=True, help="保留 PROTECTED 列表分支")
    args = parser.parse_args()

    print("=== L4.8 自动化: branch cleanup ===")
    print(f"  dry-run: {args.dry_run}")

    # 1. 本地分支
    local_merged = []
    for b in get_local_merged():
        if is_merged(b, "main"):
            local_merged.append(b)
    print(f"\n[本地] 已 merge main 的分支 ({len(local_merged)} 个):")
    local_deleted = 0
    for b in local_merged:
        if delete_local(b, args.dry_run):
            local_deleted += 1

    # 2. 远程分支
    remote_merged = []
    for b in get_remote_merged():
        if is_merged(b, "origin/main"):
            remote_merged.append(b)
    print(f"\n[远程] 已 merge origin/main 的分支 ({len(remote_merged)} 个):")
    remote_deleted = 0
    for b in remote_merged:
        if delete_remote(b, args.dry_run):
            remote_deleted += 1

    print(f"\n=== Summary: {local_deleted} local + {remote_deleted} remote deleted ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())