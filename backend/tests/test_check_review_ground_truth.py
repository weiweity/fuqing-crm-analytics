"""
Sprint 3 P1-3: pre-commit 钩子 check_review_ground_truth 单元测试

D-4 教训 (2026-06-06): 飞书架构 7 份刷出现 4 个 ground truth 错误, agent 凭
memory / stale 文档下结论, 没跑 git log 实证。本测试套件覆盖:
  - Red team: 故意构造无 evidence 的 trigger → 应被拦
  - Regression: 真实 commit 模式 (有 evidence) → 应通过

测试策略: 不实际跑 git 命令, 而是直接调 check_file (传入合成 diff) + 调
is_review_file / find_triggers / find_evidence_nearby 等纯函数。
"""
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parent.parent.parent
SCRIPT = ROOT / ".githooks" / "check_review_ground_truth.py"

# 把 .githooks/ 加到 sys.path 以便 import
sys.path.insert(0, str(ROOT / ".githooks"))
import check_review_ground_truth as crgt  # noqa: E402


# ---------------------------------------------------------------------------
# 纯函数单元测试
# ---------------------------------------------------------------------------

class TestIsReviewFile:
    """scope 检查: 只扫 docs/ 下的 .md, 排除元数据文件."""

    def test_docs_md_is_review(self):
        assert crgt.is_review_file("docs/飞书版架构文档/00-系统总览.md")
        assert crgt.is_review_file("docs/validation-reports/w4-t7.md")
        # docs/ 下任意 .md (非元数据) 都是 review 范围
        assert crgt.is_review_file("docs/产品设计/foo.md")
        assert crgt.is_review_file("docs/DEPLOY-WINDOWS.md")

    def test_changelog_excluded(self):
        """CHANGELOG.md / reference.md / DOCUMENT-INDEX.md 是元数据, 跳过."""
        assert not crgt.is_review_file("CHANGELOG.md")
        assert not crgt.is_review_file("docs/reference.md")
        assert not crgt.is_review_file("docs/DOCUMENT-INDEX.md")
        assert not crgt.is_review_file("docs/README.md")

    def test_code_files_excluded(self):
        """backend/ frontend-vue3/ scripts/ scraper/ — code comments 正常, 不扫."""
        assert not crgt.is_review_file("backend/main.py")
        assert not crgt.is_review_file("backend/services/pipeline.py")
        assert not crgt.is_review_file("frontend-vue3/src/views/Home.vue")
        assert not crgt.is_review_file("scripts/etl/cli.py")
        assert not crgt.is_review_file("scraper/fetch.py")

    def test_non_md_excluded(self):
        """docs/ 下 .py / .yml / .json 都不算 review (虽然少见)."""
        assert not crgt.is_review_file("docs/foo.py")
        assert not crgt.is_review_file("docs/build.yml")
        assert not crgt.is_review_file("docs/data.json")

    def test_windows_path_normalized(self):
        """Windows 反斜杠路径也能识别 (兼容 CI)."""
        assert crgt.is_review_file("docs\\飞书版架构文档\\00-系统总览.md")


class TestTriggerDetection:
    """触发词检测: 中英文 + 单词边界."""

    def test_chinese_triggers(self):
        for word in ["未集成", "不存在", "占位", "缺失", "待集成", "还没接"]:
            added = [(1, f"这个模块 {word} 需要修复")]
            triggers = crgt.find_triggers(added)
            assert len(triggers) == 1, f"应检测到 '{word}'"
            assert triggers[0][1] == word

    def test_english_triggers(self):
        for word in ["TODO", "FIXME", "placeholder", "missing", "not integrated"]:
            added = [(1, f"# {word} in this section")]
            triggers = crgt.find_triggers(added)
            assert len(triggers) >= 1, f"应检测到 '{word}'"

    def test_word_boundary_english(self):
        """英文触发词必须 \b 边界, 避免 'PENDING' 误匹配 'TODO' 等."""
        # 'TODO' 在 'TODOS' 中应不算 (单复数 区别)
        # 但 'TODOs' 中 'TODO' 仍是独立词, 会匹配 — 这是设计选择
        # 关键验证: 'MyTODOApp' 不会匹配 (没有 \b 边界)
        added2 = [(1, "MyTODOApp is a library")]
        assert crgt.find_triggers(added2) == [], (
            "MyTODOApp 不应匹配 TODO (无 \\b 边界)"
        )

    def test_no_trigger_in_clean_text(self):
        added = [(1, "W2 manifest 原子切换 ✅ (v0.4.8)")]
        assert crgt.find_triggers(added) == []

    def test_multiple_triggers_in_line(self):
        added = [(1, "X 未集成, Y 不存在, 都是占位")]
        triggers = crgt.find_triggers(added)
        # 至少 3 个 trigger (3 中文触发词: 未集成/不存在/占位)
        assert len(triggers) >= 3, f"应至少 3 个 trigger, got {len(triggers)}: {triggers}"


class TestEvidenceDetection:
    """evidence 检测: git log / SHA / 已验证 标记."""

    def test_git_log_is_evidence(self):
        """附近有 'git log' 命令 → 有 evidence."""
        added = [
            (10, "Step 7b 状态: 未集成"),
            (11, ""),
            (12, "验证:"),
            (13, "```bash"),
            (14, "$ git log --all -- backend/services/pipeline.py"),
            (15, "a1b2c3d feat(etl): W3 step 8.5"),
            (16, "```"),
        ]
        assert crgt.find_evidence_nearby(added, trigger_idx=0) is True

    def test_commit_sha_is_evidence(self):
        """7-40 位 hex SHA → 有 evidence."""
        added = [
            (5, "X 未集成"),
            (6, "相关 commit: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"),
        ]
        assert crgt.find_evidence_nearby(added, trigger_idx=0) is True

    def test_chinese_verified_marker(self):
        """'已集成' / '已验证' / '已落地' 等白名单词 → 有 evidence."""
        for marker in ["已验证", "已确认", "已核对", "已落地", "已合入", "已集成", "已实现", "已存在"]:
            added = [
                (3, f"功能 X — {marker} (commit a1b2c3d)"),
            ]
            assert crgt.find_evidence_nearby(added, trigger_idx=0) is True, (
                f"marker '{marker}' 应被识别为 evidence"
            )

    def test_no_evidence_nearby(self):
        """trigger 附近没有任何 evidence → 缺 evidence."""
        added = [
            (1, "X 未集成"),
            (2, "Y 是占位"),
            (3, "Z 不存在"),
        ]
        assert crgt.find_evidence_nearby(added, trigger_idx=0) is False

    def test_evidence_outside_window(self):
        """evidence 在 window 之外 (例如 trigger 行 + 100 行) → 不算."""
        added = [(i, "其他内容") for i in range(100)]
        added[0] = (1, "X 未集成")
        added[50] = (51, "git log 输出")
        # window=30, trigger 在 idx=0, 50 > 30, 不在范围内
        assert crgt.find_evidence_nearby(added, trigger_idx=0, window=30) is False


class TestParseAddedLines:
    """unified diff 解析: 只取 + 行."""

    def test_simple_added(self):
        diff = (
            "@@ -1,2 +1,3 @@\n"
            " line1\n"
            "-old\n"
            "+new1\n"
            "+new2\n"
            " line2\n"
        )
        added = crgt.parse_added_lines(diff)
        # line1 (ctx) 占 line 1, new1 = line 2, new2 = line 3
        assert added == [(2, "new1"), (3, "new2")]

    def test_hunk_header_tracking(self):
        """line number 在 hunk 之间正确递增."""
        diff = (
            "@@ -1,2 +1,2 @@\n"
            " ctx\n"
            "+a\n"
            "@@ -10,3 +10,3 @@\n"
            " ctx\n"
            "+b\n"
        )
        added = crgt.parse_added_lines(diff)
        # hunk1: ctx (line 1) + +a (line 2)
        # hunk2: +10,3 → ctx (line 10) + +b (line 11)
        assert added == [(2, "a"), (11, "b")]

    def test_file_header_excluded(self):
        """--- a/foo +++ b/foo 是文件头, 不算 added."""
        diff = (
            "--- a/foo.md\n"
            "+++ b/foo.md\n"
            "@@ -1 +1 @@\n"
            "+new line\n"
        )
        added = crgt.parse_added_lines(diff)
        assert added == [(1, "new line")]

    def test_empty_diff(self):
        assert crgt.parse_added_lines("") == []


# ---------------------------------------------------------------------------
# check_file 集成测试
# ---------------------------------------------------------------------------

class TestCheckFile:
    """check_file 端到端测试."""

    def test_blocks_trigger_without_evidence(self):
        diff = (
            "@@ -1,2 +1,3 @@\n"
            " # 架构\n"
            "+Step 7b 未集成\n"
            "+下一步: 集成\n"
        )
        with patch.object(crgt, "get_staged_diff", return_value=diff):
            violations = crgt.check_file("docs/飞书版架构文档/00-系统总览.md")
        assert len(violations) == 1
        lineno, trigger, reason = violations[0]
        assert trigger == "未集成"
        assert reason == "no_evidence"

    def test_passes_trigger_with_git_log(self):
        diff = (
            "@@ -1,2 +1,5 @@\n"
            " # 架构\n"
            "+Step 7b 未集成\n"
            "+但已验证:\n"
            "+\\`\\`\\`\n"
            "+\\$ git log --all -- backend/services/pipeline.py | head -3\n"
            "+\\`\\`\\`\n"
        )
        with patch.object(crgt, "get_staged_diff", return_value=diff):
            violations = crgt.check_file("docs/飞书版架构文档/00-系统总览.md")
        assert violations == [], f"有 git log evidence 应通过, got {violations}"

    def test_passes_trigger_with_commit_sha(self):
        diff = (
            "@@ -1,2 +1,3 @@\n"
            " # 架构\n"
            "+W3 step 7b 未集成 (commit a1b2c3d4 待 fix)\n"
        )
        with patch.object(crgt, "get_staged_diff", return_value=diff):
            violations = crgt.check_file("docs/飞书版架构文档/00-系统总览.md")
        assert violations == [], f"有 SHA evidence 应通过, got {violations}"

    def test_passes_trigger_with_verified_marker(self):
        diff = (
            "@@ -1,2 +1,3 @@\n"
            " # 架构\n"
            "+W3 step 7b 已集成 (v0.4.10)\n"
        )
        with patch.object(crgt, "get_staged_diff", return_value=diff):
            violations = crgt.check_file("docs/飞书版架构文档/00-系统总览.md")
        # '已集成' 是 evidence marker, 不应被拦
        # 但 '集成' 之前 '已' 是 evidence → 通过
        assert violations == [], f"'已集成' 是 evidence marker 应通过, got {violations}"

    def test_removed_line_not_counted(self):
        """删除行 (以 - 开头) 中的 trigger 不算 violation (历史已有)."""
        diff = (
            "@@ -1,2 +1,2 @@\n"
            " # 架构\n"
            "-旧: Step 7b 未集成 (此条已删)\n"
            "+新: Step 7b 已集成 ✅\n"
        )
        with patch.object(crgt, "get_staged_diff", return_value=diff):
            violations = crgt.check_file("docs/飞书版架构文档/00-系统总览.md")
        # '已集成' 是 evidence, 不会触发
        # 删除行的 '未集成' 也不应被算
        assert violations == [], f"删除行不应被算, got {violations}"

    def test_empty_diff_passes(self):
        with patch.object(crgt, "get_staged_diff", return_value=""):
            violations = crgt.check_file("docs/飞书版架构文档/00-系统总览.md")
        assert violations == []


# ---------------------------------------------------------------------------
# main() 端到端测试 (red team + regression)
# ---------------------------------------------------------------------------

class TestMainEndToEnd:
    """端到端测试: 模拟 staged files, 验证 main() 的 exit code 和 stdout."""

    def _run_main(self, files: list[str], diffs: dict[str, str], env_skip: str | None = None) -> tuple[int, str]:
        """Helper: mock get_staged_files + get_staged_diff, run main()."""
        from io import StringIO
        ctx_managers = [
            patch.object(crgt, "get_staged_files", return_value=files),
            patch.object(crgt, "get_staged_diff", side_effect=lambda p: diffs.get(p, "")),
        ]
        if env_skip is not None:
            ctx_managers.append(patch.dict(os.environ, {"FQA_GROUND_TRUTH_SKIP": env_skip}))
        # 串行 enter / exit (Python 不支持 with *)
        entered = []
        for cm in ctx_managers:
            entered.append(cm.__enter__())
        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            rc = crgt.main([])
        finally:
            sys.stdout = old_stdout
            for cm in reversed(ctx_managers):
                cm.__exit__(None, None, None)
        return rc, captured.getvalue()

    # ---- Red team: 故意无 evidence 的 trigger 必须被拦 ----

    def test_red_team_fake_wei_jicheng_blocked(self):
        """D-4 同型攻击: 写一句 'X 未集成' 进 docs/, 应被拦."""
        files = ["docs/飞书版架构文档/00-系统总览.md"]
        diffs = {
            files[0]: (
                "@@ -1,2 +1,3 @@\n"
                " # 系统总览\n"
                "+W3 step 7b 仍未集成, 后续 sprint 接入\n"
            ),
        }
        rc, output = self._run_main(files, diffs)
        assert rc == 1, f"red team 未集成 应被拦, got rc={rc}, output={output}"
        assert "未集成" in output, "violation 输出应包含触发词"
        assert "[block]" in output, "应输出 [block] 标记"

    def test_red_team_fake_bucunzai_blocked(self):
        """'X 不存在' 应被拦."""
        files = ["docs/validation-reports/w4-t7.md"]
        diffs = {
            files[0]: (
                "@@ -1,2 +1,3 @@\n"
                " # W4 T-7 验证\n"
                "+scripts/etl/foo.py 不存在\n"
            ),
        }
        rc, output = self._run_main(files, diffs)
        assert rc == 1, f"'不存在' 应被拦, got rc={rc}"
        assert "不存在" in output

    def test_red_team_fake_placeholder_blocked(self):
        """'X 是占位' 应被拦."""
        files = ["docs/validation-reports/w4-t7.md"]
        diffs = {
            files[0]: (
                "@@ -1,2 +1,3 @@\n"
                " # W4\n"
                "+test_X.py 是占位测试, 没真跑\n"
            ),
        }
        rc, output = self._run_main(files, diffs)
        assert rc == 1, f"'占位' 应被拦, got rc={rc}"

    def test_red_team_todo_english_blocked(self):
        """英文 TODO 也应被拦 (如果是 review 文件)."""
        files = ["docs/validation-reports/w4-t7.md"]
        diffs = {
            files[0]: (
                "@@ -1,2 +1,3 @@\n"
                " # W4\n"
                "+TODO: 真跑 T-7 验证\n"
            ),
        }
        rc, output = self._run_main(files, diffs)
        assert rc == 1, f"英文 TODO 在 review 文件中应被拦, got rc={rc}"

    def test_red_team_multiple_violations_all_reported(self):
        """多个 violation 应全部上报."""
        files = ["docs/validation-reports/w4-t7.md"]
        diffs = {
            files[0]: (
                "@@ -1,2 +1,4 @@\n"
                " # W4\n"
                "+Step 7b 未集成\n"
                "+foo.py 不存在\n"
                "+bar.py 是占位\n"
            ),
        }
        rc, output = self._run_main(files, diffs)
        assert rc == 1
        # 至少 3 个 violation
        violation_count = output.count("(reason: no_evidence)")
        assert violation_count >= 3, f"应至少 3 个 violation, got {violation_count}"

    # ---- Regression: 真实 commit 模式应通过 ----

    def test_regression_clean_diff_passes(self):
        """clean diff (无 trigger) → 通过."""
        files = ["docs/validation-reports/w4-t7.md"]
        diffs = {
            files[0]: (
                "@@ -1,2 +1,3 @@\n"
                " # W4\n"
                "+W4 T-7 跑批 540 组合 ✅\n"
                "+耗时 32min (目标 < 35min)\n"
            ),
        }
        rc, output = self._run_main(files, diffs)
        assert rc == 0, f"clean diff 应通过, got rc={rc}, output={output}"
        assert "[ok]" in output

    def test_regression_with_git_log_evidence_passes(self):
        """trigger + 同段 git log 实证 → 通过."""
        files = ["docs/validation-reports/w4-t7.md"]
        diffs = {
            files[0]: (
                "@@ -1,2 +1,8 @@\n"
                " # W4\n"
                "+Step 7b 状态: 未集成\n"
                "+\n"
                "+验证:\n"
                "+\\`\\`\\`bash\n"
                "+\\$ git log --oneline -- backend/services/pipeline.py | head -3\n"
                "+097a63e feat(etl): W3/W4 pipeline 集成 — step 7b/8 补 skip flag\n"
                "+\\`\\`\\`\n"
            ),
        }
        rc, output = self._run_main(files, diffs)
        assert rc == 0, f"有 git log evidence 应通过, got rc={rc}, output={output}"

    def test_regression_with_commit_sha_passes(self):
        """trigger + commit SHA → 通过."""
        files = ["docs/validation-reports/w4-t7.md"]
        diffs = {
            files[0]: (
                "@@ -1,2 +1,3 @@\n"
                " # W4\n"
                "+Step 7b 未集成 (待 a1b2c3d4 集成后 fix)\n"
            ),
        }
        rc, output = self._run_main(files, diffs)
        assert rc == 0, f"有 SHA 应通过, got rc={rc}"

    def test_regression_with_verified_marker_passes(self):
        """trigger 行同段有 '已验证/已集成' 标记 → 通过."""
        files = ["docs/validation-reports/w4-t7.md"]
        diffs = {
            files[0]: (
                "@@ -1,2 +1,3 @@\n"
                " # W4\n"
                "+Step 7b 已集成 (commit a1b2c3d)\n"
            ),
        }
        rc, output = self._run_main(files, diffs)
        assert rc == 0, f"'已集成' 应是 evidence, got rc={rc}"

    def test_regression_changelog_with_trigger_passes(self):
        """CHANGELOG.md 不在 scope, 触发词应被忽略."""
        files = ["CHANGELOG.md"]
        diffs = {
            files[0]: (
                "@@ -1,2 +1,3 @@\n"
                " ## v0.5.0\n"
                "+TODO: 等 v0.5.1 集成 W5\n"
            ),
        }
        rc, output = self._run_main(files, diffs)
        assert rc == 0, f"CHANGELOG.md 不应在 scope, got rc={rc}"

    def test_regression_code_file_with_trigger_passes(self):
        """backend/ 下的 .py 触发词应被忽略 (code comment 正常)."""
        files = ["backend/services/pipeline.py"]
        diffs = {
            files[0]: (
                "@@ -1,2 +1,3 @@\n"
                " def step_7b():\n"
                "     # TODO: implement\n"
                "     pass\n"
            ),
        }
        rc, output = self._run_main(files, diffs)
        assert rc == 0, f"backend/ .py 触发词应被忽略, got rc={rc}"

    def test_regression_frontend_with_trigger_passes(self):
        """frontend-vue3/ 下的 .vue 触发词应被忽略."""
        files = ["frontend-vue3/src/components/Foo.vue"]
        diffs = {
            files[0]: (
                "@@ -1,2 +1,3 @@\n"
                " <template>\n"
                "   <!-- FIXME: 改样式 -->\n"
                " </template>\n"
            ),
        }
        rc, output = self._run_main(files, diffs)
        assert rc == 0, f"frontend-vue3/ 触发词应被忽略, got rc={rc}"

    def test_regression_no_staged_files_passes(self):
        """无 staged 文件 → 通过 (no-op)."""
        rc, output = self._run_main([], {})
        assert rc == 0, f"无 staged 文件应通过, got rc={rc}"
        assert "[ok]" in output

    def test_regression_only_non_review_staged_passes(self):
        """只 staged 了 code 文件 → 通过 (无 review 文件)."""
        files = ["backend/main.py", "frontend-vue3/src/foo.vue"]
        diffs = {
            files[0]: "+# FIXME: fix later\n",
            files[1]: "+<!-- TODO: change style -->\n",
        }
        rc, output = self._run_main(files, diffs)
        assert rc == 0, f"无 review 文件应通过, got rc={rc}"

    def test_skip_env_var_bypasses_check(self):
        """FQA_GROUND_TRUTH_SKIP=1 应绕过 (救火用)."""
        files = ["docs/validation-reports/w4-t7.md"]
        diffs = {
            files[0]: (
                "@@ -1,2 +1,3 @@\n"
                " # W4\n"
                "+未集成, 不存在, 占位\n"
            ),
        }
        rc, output = self._run_main(files, diffs, env_skip="1")
        assert rc == 0, f"FQA_GROUND_TRUTH_SKIP=1 应 bypass, got rc={rc}"
        assert "[skip]" in output


# ---------------------------------------------------------------------------
# CLI integration: 真实 git 命令 (--files 路径, 不依赖 staged)
# ---------------------------------------------------------------------------

class TestCLIRun:
    """真跑脚本: 验证 argparse / --files / --verbose."""

    def test_script_imports(self):
        """脚本本身能被 import, 没有 syntax error."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"--help 应成功, stderr={result.stderr}"
        assert "Check staged review files" in result.stdout

    def test_no_staged_files_passes(self):
        """空 staged 列表 → rc=0."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--files"],
            capture_output=True,
            text=True,
            check=False,
        )
        # --files 接空 list, argparse 会报 unrecognized args
        # 但 pre-commit 实际不会这样调, 这里只确认脚本不崩
        # 真无 staged 场景已由 test_regression_no_staged_files_passes 覆盖
        assert result.returncode in (0, 2), f"脚本不崩即可, got rc={result.returncode}"

    def test_fqa_skip_env_bypasses(self):
        """env 变量真生效."""
        env = os.environ.copy()
        env["FQA_GROUND_TRUTH_SKIP"] = "1"
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        # 跳过模式下, 即使有 staged 文件 (CI 环境可能没有) 也 rc=0
        assert result.returncode == 0
        assert "[skip]" in result.stdout


# ---------------------------------------------------------------------------
# Sanity: 脚本能真在 test git repo 里跑通
# ---------------------------------------------------------------------------

class TestScriptInGitRepo:
    """在 tmp git repo 里真跑: 模拟真 git 场景."""

    @pytest.fixture
    def tmp_git_repo(self, tmp_path):
        """Create a tmp git repo with a docs/ file."""
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
        docs = tmp_path / "docs" / "飞书版架构文档"
        docs.mkdir(parents=True)
        f = docs / "00-系统总览.md"
        f.write_text("# 系统总览\n\n初始内容\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-m", "init", "-q"], cwd=tmp_path, check=True)
        return tmp_path

    def test_real_git_red_team_blocked(self, tmp_git_repo):
        """在真 git repo 里写 '未集成' 进 docs/ 并 stage, 跑脚本应 rc=1."""
        f = tmp_git_repo / "docs" / "飞书版架构文档" / "00-系统总览.md"
        f.write_text(
            "# 系统总览\n\n初始内容\n\nW3 step 7b 仍未集成\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "."], cwd=tmp_git_repo, check=True)
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
            cwd=tmp_git_repo,
        )
        assert result.returncode == 1, (
            f"真 git red team 应被拦, got rc={result.returncode}, "
            f"stdout={result.stdout}, stderr={result.stderr}"
        )
        assert "未集成" in result.stdout

    def test_real_git_with_evidence_passes(self, tmp_git_repo):
        """在真 git repo 里写 '未集成' + git log evidence, 跑脚本应 rc=0."""
        f = tmp_git_repo / "docs" / "飞书版架构文档" / "00-系统总览.md"
        f.write_text(
            "# 系统总览\n\n初始内容\n\n"
            "W3 step 7b 仍未集成 (待 a1b2c3d 集成)\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "."], cwd=tmp_git_repo, check=True)
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
            cwd=tmp_git_repo,
        )
        assert result.returncode == 0, (
            f"有 SHA evidence 应通过, got rc={result.returncode}, "
            f"stdout={result.stdout}, stderr={result.stderr}"
        )

    def test_real_git_changelog_passes(self, tmp_git_repo):
        """CHANGELOG.md 不在 scope, 写 trigger 不应被拦."""
        cl = tmp_git_repo / "CHANGELOG.md"
        cl.write_text(
            "## v0.5.0\n\n- TODO: 集成 W5\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "."], cwd=tmp_git_repo, check=True)
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
            cwd=tmp_git_repo,
        )
        assert result.returncode == 0, (
            f"CHANGELOG.md 不应在 scope, got rc={result.returncode}, "
            f"stdout={result.stdout}"
        )
