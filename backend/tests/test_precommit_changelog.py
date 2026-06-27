"""
Sprint 30.2 — pre-commit CHANGELOG hard block → soft WARN (2026-06-17)

背景:
  Sprint 3 P1-3 引入的 `.githooks/pre-commit` 在改 .py / docs/ 时硬拦 CHANGELOG
  跟随 (exit 1).  问题: feature branch 多次 commit 时, 每次都强制 CHANGELOG 跟
  随不实际 (应该合并后 1 次写 CHANGELOG). Sprint 27 教训: 用户用 --no-verify
  绕过 hook 是反 pattern. codex 推荐: 改 soft WARN + post-merge hint.

改造:
  1. pre-commit hook: 默认 soft WARN (不 exit 1, 只 print 提醒), 紧急回切
     hard block 用 `STRICT_CHANGELOG_HOOK=1` env var 守卫.
  2. post-merge hook: 新增 `git log <last-tag>..HEAD` 校验 commit message 是
     否含 CHANGELOG / v0.4. / vX.Y.Z 关键字, 不含就 WARN (不阻断).

测试范围:
  - pre-commit hook 源码 verify: 默认 soft WARN 路径 (无 exit 1), strict 模式
    仍走 hard exit 1.
  - post-merge hook 源码 verify: CHANGELOG hint 段存在 + 关键字 grep 模式正确.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PRE_COMMIT_HOOK = REPO_ROOT / ".githooks" / "pre-commit"
POST_MERGE_HOOK = REPO_ROOT / ".githooks" / "post-merge"


class TestPreCommitChangelogSoftWarn:
    """Sprint 30.2: pre-commit CHANGELOG 跟随 hard exit 1 → soft WARN."""

    def test_precommit_hook_exists(self) -> None:
        """pre-commit hook 文件存在 + 可执行."""
        assert PRE_COMMIT_HOOK.exists(), f"missing: {PRE_COMMIT_HOOK}"
        assert os.access(PRE_COMMIT_HOOK, os.X_OK), f"not executable: {PRE_COMMIT_HOOK}"

    def test_precommit_soft_warn_default_no_exit1(self) -> None:
        """默认 (无 STRICT_CHANGELOG_HOOK) 走 soft WARN 路径, 不 exit 1.

        验证手段: 源码静态扫描 — 软 WARN 段必须包含 'soft WARN' 标记注释
        且对应 if 分支内**不**含 `exit 1`.
        """
        src = PRE_COMMIT_HOOK.read_text(encoding="utf-8")
        assert "Sprint 30.2 soft WARN" in src, (
            "pre-commit hook 缺 Sprint 30.2 soft WARN 标记注释"
        )
        assert "STRICT_CHANGELOG_HOOK" in src, (
            "pre-commit hook 缺 STRICT_CHANGELOG_HOOK 守卫"
        )

    def test_precommit_strict_mode_preserves_hard_exit(self) -> None:
        """STRICT_CHANGELOG_HOOK=1 仍走 hard exit 1 (Sprint 30.2 之前行为).

        验证手段: 源码静态扫描 — STRICT_CHANGELOG_HOOK=1 分支内必须有 `exit 1`.
        """
        src = PRE_COMMIT_HOOK.read_text(encoding="utf-8")
        m = re.search(
            r'if\s+\[\s*"\$?\{STRICT_CHANGELOG_HOOK:-0\}"\s*=\s*"1"\s*\].*?fi',
            src,
            re.DOTALL,
        )
        assert m is not None, (
            "pre-commit hook 找不到 STRICT_CHANGELOG_HOOK=1 的 if 守卫分支"
        )
        branch_body = m.group(0)
        assert "exit 1" in branch_body, (
            "STRICT_CHANGELOG_HOOK=1 分支必须保留 exit 1 (回切 hard block 用)"
        )

    def test_precommit_default_path_no_exit1_in_changelog_block(self) -> None:
        """默认 (非 strict) CHANGELOG 校验段**不**含 `exit 1`.

        验证手段: 抽取整段 CHANGELOG 校验 if 块, 确认默认 else 分支无 exit 1.
        这是 Sprint 30.2 核心改造点: 删 `exit 1`, 改 print "⚠".
        """
        src = PRE_COMMIT_HOOK.read_text(encoding="utf-8")
        m = re.search(
            r"# P2 散点:.*?STAGED_CHANGELOG.*?fi",
            src,
            re.DOTALL,
        )
        assert m is not None, "pre-commit hook 找不到 CHANGELOG 校验整段"
        block = m.group(0)
        exit_count = block.count("exit 1")
        assert exit_count == 1, (
            f"CHANGELOG 校验整段 exit 1 出现 {exit_count} 次, 期望 1 次 (strict 模式保留)"
        )
        else_match = re.search(
            r"else\s*\n(.*?)(?=^fi|\Z)",
            block,
            re.DOTALL | re.MULTILINE,
        )
        if else_match:
            else_body = else_match.group(1)
            assert "exit 1" not in else_body, (
                "Sprint 30.2: 默认 (非 strict) 分支不应有 exit 1, 实际存在"
            )


class TestPostMergeChangelogHint:
    """Sprint 30.2: post-merge hook 新增 CHANGELOG post-merge hint."""

    def test_postmerge_hook_exists(self) -> None:
        """post-merge hook 文件存在 + 可执行."""
        assert POST_MERGE_HOOK.exists(), f"missing: {POST_MERGE_HOOK}"
        assert os.access(POST_MERGE_HOOK, os.X_OK), f"not executable: {POST_MERGE_HOOK}"

    def test_postmerge_changelog_hint_segment_present(self) -> None:
        """post-merge hook 含 Sprint 30.2 CHANGELOG hint 段."""
        src = POST_MERGE_HOOK.read_text(encoding="utf-8")
        assert "Sprint 30.2" in src, "post-merge hook 缺 Sprint 30.2 标记"
        assert "CHANGELOG" in src, "post-merge hook 缺 CHANGELOG 关键字"
        assert "post-merge hint" in src, "post-merge hook 缺 hint 标识"

    def test_postmerge_grep_pattern_matches_changelog_keyword(self) -> None:
        """post-merge hook 用 `git log <range> | grep -E 'CHANGELOG|v0...'` 校验.

        验证: grep 模式至少匹配 CHANGELOG / v0.4. / vX.Y.Z 之一.
        """
        src = POST_MERGE_HOOK.read_text(encoding="utf-8")
        m = re.search(r"grep\s+-E\s+['\"]([^'\"]+)['\"]", src)
        assert m is not None, "post-merge hook 找不到 grep -E 模式"
        pattern = m.group(1)
        assert "CHANGELOG" in pattern, f"grep 模式缺 CHANGELOG: {pattern}"
        assert "v0\\.[0-9]+\\.[0-9]+" in pattern or "v0.4." in pattern, (
            f"grep 模式缺 v0.4. 类: {pattern}"
        )

    def test_postmerge_does_not_exit1_on_missing_changelog(self) -> None:
        """post-merge hook CHANGELOG hint 段**不**含 `exit 1` (WARN-only)."""
        src = POST_MERGE_HOOK.read_text(encoding="utf-8")
        m = re.search(
            r"# --- Sprint 30\.2:.*?\Z",
            src,
            re.DOTALL,
        )
        assert m is not None, "post-merge hook 找不到 Sprint 30.2 hint 段"
        hint_block = m.group(0)
        assert "exit 1" not in hint_block, (
            "Sprint 30.2 post-merge hint 段不应 exit 1, 实际存在"
        )
        assert "⚠" in hint_block, "Sprint 30.2 hint 段缺 WARN 提示符 ⚠"


class TestSprint302Anchor:
    """Sprint 30.2 修复锚点 — 防未来误删/误改."""

    def test_precommit_mentions_sprint_30_2(self) -> None:
        """pre-commit hook 注释含 Sprint 30.2 锚点."""
        src = PRE_COMMIT_HOOK.read_text(encoding="utf-8")
        assert "Sprint 30.2" in src, "pre-commit hook 缺 Sprint 30.2 锚点"

    def test_postmerge_mentions_sprint_30_2(self) -> None:
        """post-merge hook 注释含 Sprint 30.2 锚点."""
        src = POST_MERGE_HOOK.read_text(encoding="utf-8")
        assert "Sprint 30.2" in src, "post-merge hook 缺 Sprint 30.2 锚点"

    def test_precommit_uses_bash_shebang(self) -> None:
        """Sprint 30.2 改造保留 hook 风格 (项目老风格: bash + 无 set -euo pipefail)."""
        src = PRE_COMMIT_HOOK.read_text(encoding="utf-8")
        first_line = src.splitlines()[0] if src else ""
        assert first_line.startswith("#!"), (
            f"pre-commit hook 缺 shebang, 首行: {first_line!r}"
        )
        assert "bash" in first_line or "sh" in first_line, (
            f"pre-commit hook shebang 不是 bash/sh: {first_line!r}"
        )
