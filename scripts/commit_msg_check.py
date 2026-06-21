#!/usr/bin/env python3
"""commit-msg drift 检测 (Sprint 58 #2 阶段 A).

Phase A 目标:
- 读取 commit message
- 估算 message 里表达的变更量
- 对比 staged diff 的实际行数
- 当实际变更明显大于 message 预算时阻断

这是一层低依赖的保护网, 供 Stage B 的 blocking hook 直接复用。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


THRESHOLD_RATIO = 3.0
MESSAGE_LINE_HINT_RE = re.compile(
    r"(?<!\d)(\d{1,6})(?!\d)\s*(?:lines?|line|行|行变更|changed lines?|modified lines?)",
    re.IGNORECASE,
)
TRAILER_RE = re.compile(
    r"^(?:Signed-off-by|Co-authored-by|Reviewed-by|Acked-by|Fixes|Refs?|Relates-to|Closes):",
    re.IGNORECASE,
)
MERGE_OR_REVERT_RE = re.compile(r"^(?:Merge\s+|Revert\s+)", re.IGNORECASE)


def count_staged_diff_lines() -> int:
    """统计 git diff --cached 的实际变更行数."""
    result = subprocess.run(
        [
            "git",
            "diff",
            "--cached",
            "--no-renames",
            "--numstat",
            "-z",
            "--diff-filter=ACMRD",
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(stderr or "git diff --cached failed")

    total = 0
    for raw_entry in result.stdout.split(b"\0"):
        if not raw_entry:
            continue
        parts = raw_entry.split(b"\t", 2)
        if len(parts) != 3 or parts[0] == b"-" or parts[1] == b"-":
            continue
        try:
            total += int(parts[0]) + int(parts[1])
        except ValueError:
            continue
    return total


def extract_message_line_budget(commit_msg: str) -> int:
    """从 commit message 里提取一个粗略的“变更量预算”.

    优先使用显式的数字+行数提示, 否则按有效行数粗估。
    """
    hints = [int(match) for match in MESSAGE_LINE_HINT_RE.findall(commit_msg)]
    if hints:
        return max(hints)

    budget = 0
    for line in commit_msg.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if TRAILER_RE.match(stripped):
            continue
        budget += 1
    return max(budget, 1)


def _read_commit_message(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) < 1:
        print("Usage: commit_msg_check.py <commit_msg_file>", file=sys.stderr)
        return 2

    commit_msg_file = Path(args[0])
    if not commit_msg_file.exists():
        print(f"Commit msg file not found: {commit_msg_file}", file=sys.stderr)
        return 2

    try:
        commit_msg = _read_commit_message(commit_msg_file)
    except OSError as exc:
        print(f"Failed to read commit msg file: {exc}", file=sys.stderr)
        return 2

    if MERGE_OR_REVERT_RE.match(commit_msg):
        return 0

    try:
        diff_lines = count_staged_diff_lines()
    except (OSError, RuntimeError) as exc:
        print(f"❌ commit-msg drift 检测失败: {exc}", file=sys.stderr)
        return 2

    if diff_lines == 0:
        return 0

    message_budget = extract_message_line_budget(commit_msg)
    ratio = diff_lines / max(message_budget, 1)

    if ratio > THRESHOLD_RATIO:
        print("❌ commit-msg drift 检测失败 (Sprint 58 #2)", file=sys.stderr)
        print(f"   实际 diff 行数: {diff_lines}", file=sys.stderr)
        print(f"   commit msg 预算行数: {message_budget}", file=sys.stderr)
        print(f"   比例: {ratio:.1f}x (阈值 {THRESHOLD_RATIO:.1f}x)", file=sys.stderr)
        print("   修复建议: 把 commit msg 写具体一点, 或在紧急 hotfix 时使用 git commit --no-verify", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
## Stage 2 完成 — Sprint 58 #2 阶段 A
- 新增 commit-msg drift 检测脚本, Phase B 可直接复用为 blocking hook 核心。
- 阶段 A 保持与 `.githooks/commit-msg` / `.githooks/pre-commit` 解耦。
"""
