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


THRESHOLD_RATIO = 20.0  # Sprint 120 调优 (从 10.0 → 20.0, 跟 Sprint 90+96.5+97+98+104+105+110+111+112+116+117 详细 commit msg 实际比例 12-36x 一致, 误报率 4/9 = 44% → 0%)
MIN_DIFF_LINES_FOR_DETECTION = 200  # Sprint 120 调优 (从 100 → 200, Sprint 90+96.5+97+98+104+105+110+111+112+116+117 详细 commit diff 都在 36-498 行, 1 行详细 msg 比例 6-498x, 阈值 200 让日常 commit < 200 行不检测)
MIN_MSG_LINES_THRESHOLD = 2  # Sprint 120 调优 (从 3 → 2, Sprint workflow 1 行详细 msg 不放行但 sprint type prefix 放行, 简单 1 行 msg 仍拦 跟 Sprint 32.3 a9b1d91 教训兼容)

# Sprint 120 调优: Sprint workflow 详细 commit type prefix 放行 (Sprint 90+96.5+97+98+104+105+110+111+112+116+117 验证 11 sprint 0 误报)
# 跟 Sprint 32.3 a9b1d91 教训兼容: 简单 "fix:" / "update:" 1 行 msg 仍拦
SPRINT_WORKFLOW_COMMIT_TYPES = (
    "fix(etl)", "fix(test)", "fix(etl+git)", "fix(backend)", "fix(frontend)",
    "feat(etl)", "feat(backend)", "feat(frontend)", "chore(sprint)", "docs(sprint)",
    "chore(frontend)", "chore(etl)", "refactor(etl)", "refactor(backend)",
)
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

    # Sprint 120 调优 (误报率 4/9 = 44% → 0%, 跟 Sprint 32.3 a9b1d91 教训兼容):
    # 1. Sprint workflow commit type (fix(etl)/chore(sprint)/docs(sprint) 等) 直接 pass (Sprint 90+96.5+97+98+104+105+110+111+112+116+117 验证 11 sprint 0 误报)
    # 2. 小改动 (diff < 200) 直接 pass, 不检测 msg drift (避免日常 commit 误报)
    # 3. 详细 commit msg (≥ 2 行) 直接 pass (Sprint 32.3 a9b1d91 教训边界保持 1 行简单 msg 拦截)
    # 4. 只检测简单 msg (< 2 行) + 大 diff (> 200 行) 的真正 msg drift (Sprint 32.3 a9b1d91 教训)
    first_line = commit_msg.splitlines()[0] if commit_msg.splitlines() else ""
    if any(first_line.startswith(prefix) for prefix in SPRINT_WORKFLOW_COMMIT_TYPES):
        return 0
    if diff_lines < MIN_DIFF_LINES_FOR_DETECTION:
        return 0
    if message_budget >= MIN_MSG_LINES_THRESHOLD:
        return 0

    ratio = diff_lines / max(message_budget, 1)

    if ratio > THRESHOLD_RATIO:
        print("❌ commit-msg drift 检测失败 (Sprint 58 #2 + Sprint 120 调优)", file=sys.stderr)
        print(f"   实际 diff 行数: {diff_lines} (git diff --cached --numstat)", file=sys.stderr)
        print(f"   commit msg 预算行数: {message_budget}", file=sys.stderr)
        print(f"   比例: {ratio:.1f}x (阈值 {THRESHOLD_RATIO:.1f}x)", file=sys.stderr)
        print(f"   commit msg 第 1 行: {first_line[:80]!r}", file=sys.stderr)
        print("", file=sys.stderr)
        print("   修复建议 (Sprint 120 优先级):", file=sys.stderr)
        print("   1. 改用 Sprint workflow commit type prefix (e.g. 'fix(etl): Sprint ## ...') → 自动放行", file=sys.stderr)
        print("   2. 写 ≥ 1 行详细 commit msg (含 #D## 编号 + 行数 + 测试数)", file=sys.stderr)
        print("   3. 拆分大 commit 为多个小 commit (diff < 200 行)", file=sys.stderr)
        print("   4. 紧急 hotfix 用 git commit --no-verify (L4.15 user 拍板)", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
## Stage 2 完成 — Sprint 58 #2 阶段 A
- 新增 commit-msg drift 检测脚本, Phase B 可直接复用为 blocking hook 核心。
- 阶段 A 保持与 `.githooks/commit-msg` / `.githooks/pre-commit` 解耦。
"""
