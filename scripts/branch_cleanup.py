#!/usr/bin/env python3
"""Explicit branch maintenance; default is a read-only preview.

Run from the reviewed repository. --apply requires exact --local branch names.
Remote deletion is deliberately outside this script: review fresh remote refs
and authorize the corresponding Git operation separately. No hook calls this.
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


def is_merged(branch: str, base: str = "main") -> bool:
    """检查 branch 是否已 merge 进 base."""
    rc, _ = run(["git", "merge-base", "--is-ancestor", branch, base])
    return rc == 0


def delete_local(branch: str, dry_run: bool = True) -> bool:
    """Delete only merged, unoccupied branches; never fall back to force."""
    if branch in PROTECTED or branch.startswith('-') or not is_merged(branch):
        return False
    if dry_run:
        print(f"  [dry-run] would delete local: {branch}")
        return True
    rc, out = run(["git", "branch", "-d", "--", branch])
    if rc:
        print(f"  refused local deletion: {branch}: {out}")
        return False
    print(f"  deleted local: {branch}")
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Preview merged local branches; apply exact authorized targets")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="read-only preview (default)")
    mode.add_argument("--apply", action="store_true", help="delete explicitly listed local branches")
    parser.add_argument("--local", action="append", default=[], metavar="BRANCH")
    # Kept for old manual callers; protection is unconditional.
    parser.add_argument("--keep-protected", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.apply and not args.local:
        parser.error("--apply requires exact --local BRANCH targets")
    rc, status = run(["git", "status", "--porcelain"])
    if rc or (args.apply and status):
        print("Cannot apply cleanup in an unavailable or dirty checkout", file=sys.stderr)
        return 1
    eligible = set(get_local_merged())
    targets = list(dict.fromkeys(args.local)) if args.local else sorted(eligible)
    candidates = []
    for branch in targets:
        if branch not in eligible or not is_merged(branch):
            if args.local:
                print(f"Refused protected/current/unmerged target: {branch}", file=sys.stderr)
                return 1
            continue
        candidates.append(branch)
    completed = sum(delete_local(branch, dry_run=not args.apply) for branch in candidates)
    action = "deleted" if args.apply else "eligible (preview only)"
    print(f"Summary: {completed} local {action}; remote deletion requires a separate reviewed action")
    return 0 if completed == len(candidates) else 1


if __name__ == "__main__":
    sys.exit(main())