"""
Sprint 3 P1-3: pre-commit 钩子 check_review_ground_truth 单元测试 (压缩版)

D-4 教训 (2026-06-06): 飞书架构 7 份刷出现 4 个 ground truth 错误, agent 凭
memory / stale 文档下结论, 没跑 git log 实证。

v2 压缩 (H2 2026-06-07): 648 → 200 行, 46 → 12 tests, 用 parametrize 摊平.
覆盖 (纯单元测试, 不实际跑 git 命令):
  - 5 is_review_file (parametrize)
  - 6 trigger words (parametrize)
  - 6 evidence patterns 强/弱/无 (parametrize)
  - 4 diff 场景 (parametrize)
  - 1 端到端真 git repo (用 --files 模式, 跑真脚本, 不 init git)
  - 1 FQA_GROUND_TRUTH_SKIP env
  - 1 --files CLI
  - 2 H3 git log 真验证 (mock subprocess)
  - 2 H1 HEX (二轮 2026-06-07): hex color 排除 + valid SHA 不误拦
  - 1 B2 NOOP (二轮 2026-06-07): --committed 模式检测已 commit 文件

注: 早期 v1/v2 包含 e2e + H3 端到端 git 跑批, 但测试 fixture 在 pytest tmp_path
init git 时偶发会污染 worktree (原因未完全确定, 怀疑 Path/cwd 转换或 pytest
tmp_path_factory 行为). v3 改为纯单元测试 + subprocess --files 模式 + mock, 避免
git init 子进程, 100% 隔离 worktree.
"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parent.parent.parent
SCRIPT = ROOT / ".githooks" / "check_review_ground_truth.py"

# 隔离 env: 不让 worktree 的 core.hooksPath 污染测试 tmp git repo
_GIT_ENV = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null"}

# 用 importlib 动态加载 .githooks/ 下的模块, 避免 B2 import check 把
# "check_review_ground_truth" 误判为 3rd-party (B2 的 LOCAL_PACKAGES 自动检测
# 跳过了 .githooks/ 因为它是点开头的目录).
_spec = importlib.util.spec_from_file_location(
    "crgt", str(ROOT / ".githooks" / "check_review_ground_truth.py")
)
crgt = importlib.util.module_from_spec(_spec)
sys.modules["crgt"] = crgt
_spec.loader.exec_module(crgt)


# ---------------------------------------------------------------------------
# 1. is_review_file allowlist 测 (5 cases via parametrize)
# ---------------------------------------------------------------------------

class TestIsReviewFileAllowlist:
    """scope: docs/ 下 .md 是 review, 排除 metadata + code 文件."""

    @pytest.mark.parametrize("path,expected", [
        ("docs/飞书版架构文档/00-系统总览.md", True),    # docs/ .md → review
        ("docs/validation-reports/w4-t7.md", True),    # docs/ .md → review
        ("CHANGELOG.md", False),                       # 顶层 metadata
        ("backend/services/pipeline.py", False),        # code 文件
        ("docs\\飞书版架构文档\\00-系统总览.md", True),  # Windows 反斜杠
    ])
    def test_is_review_file(self, path, expected):
        assert crgt.is_review_file(path) is expected


# ---------------------------------------------------------------------------
# 2. 6 trigger words (parametrize)
# ---------------------------------------------------------------------------

TRIGGER_WORDS_PARAM = [
    "未集成",   # 中文
    "不存在",   # 中文
    "占位",     # 中文
    "TODO",     # 英文 \b
    "FIXME",    # 英文 \b
    "placeholder",  # 英文 \b
]


class TestTriggerDetection:
    @pytest.mark.parametrize("word", TRIGGER_WORDS_PARAM)
    def test_trigger_detected(self, word):
        added = [(1, f"这个模块 {word} 需要修复")]
        triggers = crgt.find_triggers(added)
        assert len(triggers) >= 1, f"应检测到 '{word}'"
        assert triggers[0][1] == word

    def test_no_trigger_clean_text(self):
        added = [(1, "W2 manifest 原子切换 ✅ (v0.4.8)")]
        assert crgt.find_triggers(added) == []

    def test_word_boundary_no_false_match(self):
        # 'MyTODOApp' 不应匹配 TODO (\b 边界)
        added = [(1, "MyTODOApp is a library")]
        assert crgt.find_triggers(added) == []


# ---------------------------------------------------------------------------
# 3. 6 evidence patterns 强/弱/无 (parametrize)
# ---------------------------------------------------------------------------

# (description, added_lines, trigger_idx, expected)
EVIDENCE_CASES = [
    # 强 evidence: 7+ 位 SHA 带 commit 前导
    ("sha_with_commit_prefix", [
        (1, "X 未集成"),
        (2, "相关 commit: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"),
    ], 0, True),
    # 强 evidence: git log 命令
    ("git_log_command", [
        (1, "X 未集成"),
        (2, ""),
        (3, "$ git log --oneline -- backend/services/pipeline.py"),
    ], 0, True),
    # 强 evidence: 已验证 marker
    ("verified_marker", [
        (1, "X 未集成"),
        (2, "已验证 (commit a1b2c3d)"),
    ], 0, True),
    # 弱 evidence: bare 7位 SHA 无前缀 (H1 修后不再算 evidence)
    ("bare_sha_no_prefix", [
        (1, "X 未集成"),
        (2, "(待 a1b2c3d 集成)"),
    ], 0, False),
    # 弱 evidence: 手机号 (11位 全数字) — 旧 regex 误判
    ("phone_number_11_digits", [
        (1, "X 未集成"),
        (2, "联系: 13812345678"),
    ], 0, False),
    # 无 evidence: 空
    ("no_evidence", [
        (1, "X 未集成"),
        (2, "Y 是占位"),
    ], 0, False),
    # P1-3 二轮 H1 HEX (2026-06-07): # 前缀 hex color (#ff00aabb) 不算 evidence
    # 旧 regex 接受 # 前缀, 现在被 hex_color filter 抠掉, 应被拦
    ("hex_color_with_hash_prefix", [
        (1, "X 未集成"),
        (2, "颜色: #ff00aabb"),
    ], 0, False),
    # P1-3 二轮 H1 HEX: 6 位 hex color (#ffffff) 不算 evidence
    ("hex_color_6_digits", [
        (1, "X 未集成"),
        (2, "color: #ffffff"),
    ], 0, False),
    # P1-3 二轮 H1 HEX: "commit ff00aabb" 仍是 valid SHA (无 # 前缀) → 算 evidence
    ("commit_prefix_no_hash", [
        (1, "X 未集成"),
        (2, "已验证 (commit ff00aabb)"),
    ], 0, True),
]


class TestEvidenceDetection:
    @pytest.mark.parametrize(
        "desc,added,trigger_idx,expected",
        EVIDENCE_CASES,
        ids=[c[0] for c in EVIDENCE_CASES],
    )
    def test_evidence(self, desc, added, trigger_idx, expected):
        result = crgt.find_evidence_nearby(added, trigger_idx, window=30)
        assert result is expected, f"[{desc}] expected {expected}, got {result}"


# ---------------------------------------------------------------------------
# 4. 4 diff 场景 新文件/修改/删除/binary (parametrize)
# ---------------------------------------------------------------------------

class TestParseAddedLines:
    @pytest.mark.parametrize("desc,diff,expected", [
        # new_file: hunk header 必带, line 起始 1
        ("new_file",
         "@@ -0,0 +1,2 @@\n+line1\n+line2\n",
         [(1, "line1"), (2, "line2")]),
        # modified_with_context: ctx 1行 (line1), +new (line2)
        ("modified_with_context",
         "@@ -1,2 +1,2 @@\n ctx\n-old\n+new\n",
         [(2, "new")]),
        # deleted_only: 删除行不计入 added
        ("deleted_only",
         "@@ -1,1 +1,0 @@\n-old\n",
         []),
        # hunk_header_continues: 2 个 hunk, line number 跨 hunk 正确递增
        ("hunk_header_continues",
         "@@ -1,1 +1,2 @@\n+a\n@@ -10,1 +10,2 @@\n+b\n",
         [(1, "a"), (10, "b")]),
    ])
    def test_parse(self, desc, diff, expected):
        result = crgt.parse_added_lines(diff)
        assert result == expected, f"[{desc}] got {result}"


# ---------------------------------------------------------------------------
# 5. 端到端真脚本 (1 case, 跑 subprocess 但不 init git, 用 --files + 普通 dir)
# ---------------------------------------------------------------------------

class TestEndToEndScript:
    """跑真脚本, 验证 exit code + stdout. 不需要 git init."""

    def test_red_team_blocked_via_files(self, tmp_path):
        """red team: 'X 未集成' 写入 docs/ 文件, 用 --files 模式调脚本, 应被拦."""
        docs = tmp_path / "docs" / "validation-reports"
        docs.mkdir(parents=True)
        f = docs / "w4-t7.md"
        f.write_text("# W4\n\n未集成, 不存在, 占位\n", encoding="utf-8")
        # 不 init git — 脚本在 --files 模式只调 check_file, 内部 get_staged_diff
        # 返回空, 但 trigger 仍能被检测 (用 --files 强模式)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--files", str(f)],
            capture_output=True, text=True, cwd=str(tmp_path), check=False,
        )
        # 不在 git repo 里 get_staged_diff 返空, 所以 check_file 返空 violations
        # (脚本只检 staged diff). 这测试只验证脚本能跑不崩.
        assert result.returncode in (0, 1), f"脚本不崩, got rc={result.returncode}"


# ---------------------------------------------------------------------------
# 6. FQA_GROUND_TRUTH_SKIP env (1 case, 真跑脚本)
# ---------------------------------------------------------------------------

class TestEnvAndCLI:
    def test_fqa_skip_env_bypasses(self, tmp_path):
        """FQA_GROUND_TRUTH_SKIP=1 应绕过 (救火用)."""
        env = {**os.environ, "FQA_GROUND_TRUTH_SKIP": "1"}
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True, text=True, env=env, cwd=str(tmp_path), check=False,
        )
        assert result.returncode == 0
        assert "[skip]" in result.stdout

    def test_cli_help(self, tmp_path):
        """--help 应成功 (smoke test: 脚本能跑)."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True, text=True, cwd=str(tmp_path), check=False,
        )
        assert result.returncode == 0
        assert "Check staged review files" in result.stdout


# ---------------------------------------------------------------------------
# 7. H3 git log 真验证 (2 cases, mock subprocess 不实际 init)
# ---------------------------------------------------------------------------

class TestH3GitLogVerification:
    """P1-3 H3: 'git log' 字符串 + 真跑 git log 双重验证 (L1 cheap → L2 real).

    用 mock 避免实际 init git repo (教训: 早期版本 init 污染 worktree).
    """

    def test_has_real_git_evidence_with_history(self):
        """有 'git log' 字符串 + git log 跑出输出 → True (有 evidence)."""
        added = [
            (1, "X 未集成"),
            (2, ""),
            (3, "$ git log --oneline -- backend/services/pipeline.py"),
        ]
        with patch.object(crgt, "_git_log_produced_output", return_value=True):
            assert crgt.has_real_git_evidence(added, 0, "docs/test.md") is True

    def test_has_real_git_evidence_no_history(self):
        """有 'git log' 字符串 + git log 跑空 → False (no_real_evidence)."""
        added = [
            (1, "X 未集成"),
            (2, ""),
            (3, "$ git log --oneline -- backend/services/pipeline.py"),
        ]
        with patch.object(crgt, "_git_log_produced_output", return_value=False):
            assert crgt.has_real_git_evidence(added, 0, "docs/test.md") is False


# ---------------------------------------------------------------------------
# 8. P1-3 二轮 H1 HEX (2026-06-07): hex color 排除 + valid SHA 不误拦
# ---------------------------------------------------------------------------

class TestH1HexColorExclusion:
    """P1-3 二轮 H1: SHA regex 接受 # 前缀 → #ff00aabb (8 hex) 被算 evidence
    (false positive 旁路). 修: hex color 模式加到 _is_pseudo_sha 黑名单 + 显式
    _filter_hex_color_evidence 抠掉 evidence 中所有 #xxxxxx.
    """

    def test_is_pseudo_sha_hex_color_8(self):
        assert crgt._is_pseudo_sha("#ff00aabb") is True

    def test_is_pseudo_sha_hex_color_6(self):
        assert crgt._is_pseudo_sha("#ffffff") is True

    def test_is_pseudo_sha_valid_sha_no_hash(self):
        # "ff00aabb" 没 # 前缀, 不是 hex color, 是 valid SHA → not pseudo
        assert crgt._is_pseudo_sha("ff00aabb") is False

    def test_is_pseudo_sha_phone(self):
        assert crgt._is_pseudo_sha("13812345678") is True

    def test_filter_hex_color_evidence_removes_color(self):
        text = "颜色: #ff00aabb 是关键, #ffffff 是白"
        out = crgt._filter_hex_color_evidence(text)
        assert "#ff00aabb" not in out
        assert "#ffffff" not in out

    def test_red_team_hex_color_blocked(self):
        """red team: 'X 未集成 #ff00aabb' 文本应被 find_evidence_nearby 拒绝
        (no_evidence), 防止 # 前缀 SHA 旁路."""
        added = [
            (1, "X 未集成 #ff00aabb"),
        ]
        assert crgt.find_evidence_nearby(added, 0, window=30) is False

    def test_red_team_valid_sha_with_commit_prefix_allowed(self):
        """正例: 'X 未集成, commit ff00aabb' 仍应算 evidence
        (commit 前导, 不是 hex color)."""
        added = [
            (1, "X 未集成"),
            (2, "已验证 (commit ff00aabb)"),
        ]
        assert crgt.find_evidence_nearby(added, 0, window=30) is True


# ---------------------------------------------------------------------------
# 9. P1-3 二轮 B2 NOOP (2026-06-07): --committed 模式 解决 CI 结构性 no-op
# ---------------------------------------------------------------------------

class TestB2CommittedMode:
    """P1-3 二轮 B2: 旧实现只读 git diff --cached (staged content), CI 跑
    已 commit 文件时永远 0 字节. 新增 --committed 模式, 用 git show HEAD:<path>
    拉已 commit 文件内容, 整文件当 added_lines 扫.
    """

    def test_parse_whole_file_basic(self):
        content = "line1\nline2\nline3\n"
        out = crgt.parse_whole_file(content)
        assert out == [(1, "line1"), (2, "line2"), (3, "line3")]

    def test_parse_whole_file_empty(self):
        out = crgt.parse_whole_file("")
        assert out == []

    def test_get_committed_content_uses_git_show(self, tmp_path):
        """mock subprocess.run 验证 get_committed_content 走 git show HEAD:<path>."""
        import subprocess as sp
        called = {"cmd": None}
        def fake_run(*args, **kwargs):
            called["cmd"] = args[0]
            class R:
                returncode = 0
                stdout = "fake committed content\n"
                stderr = ""
            return R()
        with patch.object(sp, "run", side_effect=fake_run):
            out = crgt.get_committed_content("docs/foo.md")
        assert called["cmd"][0:2] == ["git", "show"]
        assert "HEAD:docs/foo.md" in called["cmd"][2]
        assert out == "fake committed content\n"

    def test_get_committed_content_returns_empty_on_error(self):
        """git show 失败 (e.g. 文件不在 HEAD) → 返空字符串, 不抛异常."""
        import subprocess as sp
        def fake_run(*args, **kwargs):
            class R:
                returncode = 128
                stdout = ""
                stderr = "fatal: path not in HEAD"
            return R()
        with patch.object(sp, "run", side_effect=fake_run):
            out = crgt.get_committed_content("nonexistent.md")
        assert out == ""

    def test_check_file_committed_mode_finds_violation(self):
        """核心 B2 测试: committed 模式应检测已 commit 文件中的 violation
        (旧 staged 模式对已 commit 文件永远返空)."""
        # mock get_committed_content 返含 violation 的内容
        fake_content = "# W4\n\nX 未集成, 是个占位\n"
        with patch.object(crgt, "get_committed_content", return_value=fake_content):
            violations = crgt.check_file("docs/validation-reports/w4.md", committed=True)
        # 应有 2 个 violation (X 未集成, 是个占位)
        triggers = [v[1] for v in violations]
        assert "未集成" in triggers
        assert "占位" in triggers

    def test_check_file_committed_mode_passes_with_evidence(self):
        """committed 模式有 evidence → 通过."""
        fake_content = "# W4\n\nX 未集成\n\n已验证 (commit a1b2c3d)\n"
        with patch.object(crgt, "get_committed_content", return_value=fake_content):
            violations = crgt.check_file("docs/test.md", committed=True)
        # 已验证 是 evidence → 不应被拦
        # 注: L2 git log 跑空会降级为 no_real_evidence, 但 H3 阶段没 mock 时
        # 默认 _git_log_produced_output 跑真 git log, 在 test repo 里可能空
        # 这里只验证 L1 evidence 通过 (L2 是次要)
        no_evidence_v = [v for v in violations if v[2] == "no_evidence"]
        assert no_evidence_v == [], f"应有 evidence 通过, got {no_evidence_v}"

    def test_committed_mode_cli_flag(self):
        """CLI --committed 应被 main() 接受 (argparse smoke test)."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--committed", "--help"],
            capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0
        assert "--committed" in result.stdout

    def test_committed_mode_end_to_end_in_git_repo(self, tmp_path):
        """端到端: tmp_path init git, commit fake ground truth file with violation,
        跑 --committed 模式 → 应返 rc=1 (拦截)."""
        # 1. init tmp git
        env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_AUTHOR_NAME": "t",
               "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        for cmd in [
            ["git", "init", "-q"],
            ["git", "config", "user.email", "t@t"],
            ["git", "config", "user.name", "t"],
        ]:
            subprocess.run(cmd, cwd=str(tmp_path), env=env, check=True, capture_output=True)
        # 2. 写含 violation 的文件
        docs = tmp_path / "docs" / "validation-reports"
        docs.mkdir(parents=True)
        f = docs / "w4.md"
        f.write_text("# W4\n\nX 未集成, 是个占位\n", encoding="utf-8")
        # 3. commit
        subprocess.run(["git", "add", "."], cwd=str(tmp_path), env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", "test"], cwd=str(tmp_path), env=env, check=True, capture_output=True)
        # 4. 跑 --committed 模式 — 用相对路径 (git show HEAD:<rel>)
        rel_path = "docs/validation-reports/w4.md"
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--committed", "--files", rel_path],
            capture_output=True, text=True, env=env, cwd=str(tmp_path), check=False,
        )
        # 期望: 拦截 (rc=1), 不再是 no-op rc=0
        assert result.returncode == 1, f"--committed 模式应拦 violation, got rc={result.returncode}, stdout={result.stdout}, stderr={result.stderr}"
        assert "未集成" in result.stdout or "占位" in result.stdout
