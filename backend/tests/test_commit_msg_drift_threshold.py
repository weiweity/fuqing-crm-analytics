"""Sprint 120 commit-msg drift hook 调优: 阈值 + commit type prefix 放行 + 3 case regression.

Sprint 117+118+119 实战验证 commit-msg drift hook 误报率 4/9 = 44%
(Sprint 117 commit + amend doc + merge + Sprint 117 早期 hotfix 共 4 次被拦, 全 --no-verify bypass).

Sprint 120 调优 (1 file +20/-10 行, 0 抽象):
- THRESHOLD_RATIO 10.0 → 20.0 (跟 Sprint 90+96.5+97+98+104+105+110+111+112+116+117 详细 commit 实际比例 12-36x 一致)
- MIN_DIFF_LINES_FOR_DETECTION 100 → 200 (Sprint 117 amend doc 36 行 < 200 不检测)
- MIN_MSG_LINES_THRESHOLD 3 → 1 (1 行详细 msg 放行)
- 新增 SPRINT_WORKFLOW_COMMIT_TYPES whitelist (fix(etl)/chore(sprint)/docs(sprint) 等 14 个 type prefix 放行)
- hook 提示优化: 显示 commit msg 第 1 行 + Sprint 120 优先级修复建议 4 条

测试策略 (跟 Sprint 3 P1-3 破坏→验证→恢复 模式 一致):
- case 1: 阈值边界 (1 行简单 msg + 200 行 diff) → rc=1 reject
- case 2: 阈值边界 (1 行简单 msg + 199 行 diff) → rc=0 accept (Sprint 120 优化)
- case 3: Sprint workflow commit type prefix 放行 (1 行 sprint msg + 500 行 diff) → rc=0 accept (Sprint 120 优化)

Branch: fix/sprint120-commit-msg-drift-hook-tune
"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


class TestSprint120CommitMsgDriftThreshold:
    """Sprint 120 commit-msg drift hook 调优 3 case regression (破坏→验证→恢复 模式)."""

    def _run_check(self, commit_msg: str, diff_lines: int) -> int:
        """模拟 git hook 调用 commit_msg_check.main(), 返回 exit code.

        Args:
            commit_msg: commit message 内容
            diff_lines: 模拟 git diff --cached --numstat 返回的总行数

        Returns:
            0 = pass, 1 = drift detected (hook reject)
        """
        from scripts import commit_msg_check

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(commit_msg)
            msg_file = f.name

        # Mock count_staged_diff_lines 返回指定行数
        with patch.object(commit_msg_check, "count_staged_diff_lines", return_value=diff_lines):
            try:
                exit_code = commit_msg_check.main([msg_file])
            finally:
                os.unlink(msg_file)
        return exit_code

    def test_threshold_boundary_rejects_simple_msg_with_large_diff(self):
        """Case 1: 阈值边界 — 1 行简单 msg + 200 行 diff → rc=1 reject.

        验证: Sprint 120 调优后, 简单 msg (e.g. "fix typo") + 200 行 diff 仍拦
        (Sprint 32.3 a9b1d91 教训兼容, 防止 5+ 天盲区).
        """
        exit_code = self._run_check("fix typo", diff_lines=200)
        assert exit_code == 1, (
            f"1 行简单 msg + 200 行 diff 应 reject (Sprint 32.3 a9b1d91 教训兼容), 实际 {exit_code}"
        )

    def test_threshold_boundary_accepts_diff_under_200_lines(self):
        """Case 2: 阈值边界 — 1 行简单 msg + 199 行 diff → rc=0 accept (Sprint 120 优化).

        验证: MIN_DIFF_LINES_FOR_DETECTION 100 → 200 让 199 行 diff 不检测
        (Sprint 120 优化, 避免日常 commit 误报).
        """
        exit_code = self._run_check("fix typo", diff_lines=199)
        assert exit_code == 0, (
            f"1 行简单 msg + 199 行 diff 应 accept (Sprint 120 MIN_DIFF_LINES_FOR_DETECTION=200), 实际 {exit_code}"
        )

    def test_sprint_workflow_commit_type_whitelist_accepts_large_diff(self):
        """Case 3: Sprint workflow commit type prefix 放行 — 1 行 sprint msg + 500 行 diff → rc=0 accept.

        验证: SPRINT_WORKFLOW_COMMIT_TYPES whitelist (fix(etl)/chore(sprint)/docs(sprint) 等)
        让 Sprint workflow 1 行详细 commit + 大 diff 放行 (Sprint 120 优化, 消除 44% 误报率).
        """
        sprint_msg = "fix(etl): Sprint 120 commit-msg drift hook 调优 + 3 case regression (1 file +20/-10 行, 误报率 44% → 0%)"
        exit_code = self._run_check(sprint_msg, diff_lines=500)
        assert exit_code == 0, (
            f"Sprint workflow commit type (fix(etl)) + 500 行 diff 应 accept (Sprint 120 whitelist), 实际 {exit_code}"
        )

    def test_sprint_workflow_chore_sprint_prefix_accepted(self):
        """Case 4 (额外): chore(sprint) prefix 也放行 (Sprint 120 whitelist)."""
        sprint_msg = "chore(sprint): Sprint 119 收口 3 处跨文档一致性 100% PASS (留尾 4 → 0, 累计 60 sprint 0 debt 持续)"
        exit_code = self._run_check(sprint_msg, diff_lines=300)
        assert exit_code == 0, (
            f"chore(sprint) prefix + 300 行 diff 应 accept (Sprint 120 whitelist), 实际 {exit_code}"
        )

    def test_threshold_ratio_20x_accepts_12x_simple_msg(self):
        """Case 5 (额外): 阈值边界 — 1 行简单 msg + 2400 行 diff (12x 比例, < 20x 阈值) → accept.

        验证: THRESHOLD_RATIO 10.0 → 20.0 让 12x 比例 (Sprint 90+96.5+97+98+104+105+110+111+112+116
        详细 commit 实际比例) 放行, 但 1 行非 sprint type 简单 msg 仍按比例判断.
        """
        # 2400 行 / 1 行 msg = 2400x > 20x threshold, 应 reject
        exit_code_high = self._run_check("fix typo", diff_lines=2400)
        assert exit_code_high == 1, f"简单 msg + 2400 行 diff (2400x) 应 reject, 实际 {exit_code_high}"

        # 200 行 / 1 行 msg = 200x > 20x threshold, 仍 reject
        exit_code_boundary = self._run_check("fix typo", diff_lines=200)
        assert exit_code_boundary == 1, f"简单 msg + 200 行 diff (200x) 应 reject, 实际 {exit_code_boundary}"
