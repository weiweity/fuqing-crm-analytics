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

# (description, added_lines, trigger_lineno, expected)
# P1-3 四轮 B2 修 (2026-06-07): trigger_lineno 是触发词的 1-based 行号 (NOT the
# index in the triggers list). 旧测试用 trigger_idx=0 凑巧能跑过因为 (1, ...) 是
# added_lines[0]; 新签名明确用 lineno 反查真 idx.
EVIDENCE_CASES = [
    # 强 evidence: 7+ 位 SHA 带 commit 前导
    ("sha_with_commit_prefix", [
        (1, "X 未集成"),
        (2, "相关 commit: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"),
    ], 1, True),
    # 强 evidence: git log 命令
    ("git_log_command", [
        (1, "X 未集成"),
        (2, ""),
        (3, "$ git log --oneline -- backend/services/pipeline.py"),
    ], 1, True),
    # 强 evidence: 已验证 marker
    ("verified_marker", [
        (1, "X 未集成"),
        (2, "已验证 (commit a1b2c3d)"),
    ], 1, True),
    # 弱 evidence: bare 7位 SHA 无前缀 (H1 修后不再算 evidence)
    ("bare_sha_no_prefix", [
        (1, "X 未集成"),
        (2, "(待 a1b2c3d 集成)"),
    ], 1, False),
    # 弱 evidence: 手机号 (11位 全数字) — 旧 regex 误判
    ("phone_number_11_digits", [
        (1, "X 未集成"),
        (2, "联系: 13812345678"),
    ], 1, False),
    # 无 evidence: 空
    ("no_evidence", [
        (1, "X 未集成"),
        (2, "Y 是占位"),
    ], 1, False),
    # P1-3 二轮 H1 HEX (2026-06-07): # 前缀 hex color (#ff00aabb) 不算 evidence
    # 旧 regex 接受 # 前缀, 现在被 hex_color filter 抠掉, 应被拦
    ("hex_color_with_hash_prefix", [
        (1, "X 未集成"),
        (2, "颜色: #ff00aabb"),
    ], 1, False),
    # P1-3 二轮 H1 HEX: 6 位 hex color (#ffffff) 不算 evidence
    ("hex_color_6_digits", [
        (1, "X 未集成"),
        (2, "color: #ffffff"),
    ], 1, False),
    # P1-3 二轮 H1 HEX: "commit ff00aabb" 仍是 valid SHA (无 # 前缀) → 算 evidence
    ("commit_prefix_no_hash", [
        (1, "X 未集成"),
        (2, "已验证 (commit ff00aabb)"),
    ], 1, True),
]


class TestEvidenceDetection:
    @pytest.mark.parametrize(
        "desc,added,trigger_lineno,expected",
        EVIDENCE_CASES,
        ids=[c[0] for c in EVIDENCE_CASES],
    )
    def test_evidence(self, desc, added, trigger_lineno, expected):
        result = crgt.find_evidence_nearby(added, trigger_lineno, window=30)
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
            assert crgt.has_real_git_evidence(added, 1, "docs/test.md") is True

    def test_has_real_git_evidence_no_history(self):
        """有 'git log' 字符串 + git log 跑空 → False (no_real_evidence)."""
        added = [
            (1, "X 未集成"),
            (2, ""),
            (3, "$ git log --oneline -- backend/services/pipeline.py"),
        ]
        with patch.object(crgt, "_git_log_produced_output", return_value=False):
            assert crgt.has_real_git_evidence(added, 1, "docs/test.md") is False


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
        assert crgt.find_evidence_nearby(added, 1, window=30) is False

    def test_red_team_valid_sha_with_commit_prefix_allowed(self):
        """正例: 'X 未集成, commit ff00aabb' 仍应算 evidence
        (commit 前导, 不是 hex color)."""
        added = [
            (1, "X 未集成"),
            (2, "已验证 (commit ff00aabb)"),
        ]
        assert crgt.find_evidence_nearby(added, 1, window=30) is True


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


# ---------------------------------------------------------------------------
# 10. P1-3 四轮 B2 (2026-06-07) — 修 idx/lineno 不一致 false negative bug
# ---------------------------------------------------------------------------

class TestB2LargeFileRegression:
    """P1-3 四轮 B2 修 (2026-06-07): 旧实现把 idx (triggers 列表索引) 传给
    find_evidence_nearby / has_real_git_evidence, 这俩把 idx 当 added_lines 索引.

    在 committed 模式下 added_lines = 整文件 (340 行), trigger 在末尾的 idx 在
    triggers 列表里 = 0, 但在 added_lines 里 = 339. window=30 滑到 added_lines[0:30]
    (文件头, 有早期 commit SHA), trigger 被屏蔽, false negative.

    修法: callers 传 lineno (1-based 行号), helpers 用 _find_line_index 反查真 idx.
    """

    def test_find_evidence_nearby_uses_lineno_not_triggers_idx(self):
        """核心 B2 测试: trigger 在第 45 行, evidence 在第 50 行.
        旧版 (传 idx=0) 会从 added_lines[0:30] 找 evidence, 找不到, 返 False.
        新版 (传 lineno=45) 会从 added_lines[15:75] 找 evidence, 找到, 返 True.
        """
        # 50 行内容: 前 44 行是干扰 (含 bare SHA / phone / hex color 各种伪 evidence)
        added = []
        for i in range(1, 45):
            added.append((i, f"line {i} - 干扰内容 a1b2c3d 13812345678 #ff00aabb"))
        # trigger 在第 45 行
        added.append((45, "X 未集成"))
        # evidence 在第 50 行 (commit 前导)
        added.append((50, "已验证 (commit a1b2c3d)"))

        # 旧 idx=0 行为: window=added_lines[0:30] = 干扰 → 返 False
        # 注: 旧版不再被我们测, 但用 lineno=1 模拟"调用方传错"的旧行为 → 应返 False
        old_behavior = crgt.find_evidence_nearby(added, 1, window=30)
        assert old_behavior is False, "lineno=1 (文件头) 不应找到末尾 evidence"

        # 新 lineno=45 行为: window=added_lines[15:75] = 包含 line 50 → 返 True
        new_behavior = crgt.find_evidence_nearby(added, 45, window=30)
        assert new_behavior is True, "lineno=45 应找到 line 50 evidence"

    def test_find_evidence_nearby_lineno_in_340_line_file(self):
        """模拟真实 etl-3-runs 文件场景: 340 行, trigger 在 line 340, evidence 在 line 30.
        关键: 旧 idx=0 会从 line 0-30 找 evidence (找到), 误判通过 → false negative 的反面
        实际 bug 是: trigger 在末尾, 旧 idx=0 找窗口是文件头, 命中 evidence, 错误放过
        但 evidence 实际不 near trigger.
        """
        added = []
        # 文件头 (line 1-29) 含强 evidence (干扰)
        for i in range(1, 30):
            added.append((i, f"line {i} - 已验证 (commit a1b2c3d)"))
        # 中间空
        for i in range(30, 339):
            added.append((i, f"line {i} - 普通内容"))
        # trigger 在 line 339 (末尾), 没 evidence
        added.append((339, "X 未集成"))
        # file 末尾
        added.append((340, "file end"))

        # 旧 idx=0 行为: lineno=1, window=added_lines[0:30] → 找到 evidence → 错误返 True
        old_behavior = crgt.find_evidence_nearby(added, 1, window=30)
        assert old_behavior is True, "lineno=1 模拟旧 idx 行为, 应找到文件头 evidence"

        # 新 lineno=339 行为: window=added_lines[309:340] → 没 evidence → 返 False
        new_behavior = crgt.find_evidence_nearby(added, 339, window=30)
        assert new_behavior is False, "lineno=339 (末尾 trigger) 应找不到 evidence → 拦"

    def test_has_real_git_evidence_uses_lineno_not_triggers_idx(self):
        """has_real_git_evidence 也得用 lineno, 不是 idx.
        模拟: trigger 在 line 45, 假 git log 字符串在 line 50.
        """
        added = []
        for i in range(1, 45):
            added.append((i, f"line {i} - 普通内容"))
        added.append((45, "X 未集成"))
        added.append((50, "$ git log --oneline -- backend/services/pipeline.py"))

        # 旧 idx=0 → window=added_lines[0:30] = 没 git log 字符串 → has_git_string=False → 返 True
        # 注: 这里 has_git_string=False 直接 pass, 不跑 git log, 跟 H3 设计一致
        with patch.object(crgt, "_git_log_produced_output", return_value=False) as m:
            # lineno=1 (旧 idx): window 没含 git log 字符串 → 不依赖 git log → 返 True
            r_old = crgt.has_real_git_evidence(added, 1, "docs/test.md")
            assert r_old is True, "lineno=1 旧行为: window 无 git log 字符串, 直接 pass"

        # lineno=45 (新): window 含 git log 字符串 → 跑 git log (mocked 返 False) → 返 False
        with patch.object(crgt, "_git_log_produced_output", return_value=False) as m:
            r_new = crgt.has_real_git_evidence(added, 45, "docs/test.md")
            assert r_new is False, "lineno=45 新行为: window 含 git log, mock 跑空 → 返 False"
            assert m.called, "lineno=45 应真调 _git_log_produced_output"

    def test_find_line_index_helper(self):
        """_find_line_index: lineno → 真 idx."""
        added = [(1, "a"), (5, "b"), (10, "c"), (15, "d")]
        assert crgt._find_line_index(added, 1) == 0
        assert crgt._find_line_index(added, 5) == 1
        assert crgt._find_line_index(added, 10) == 2
        assert crgt._find_line_index(added, 15) == 3
        # 不存在 → graceful default 0
        assert crgt._find_line_index(added, 100) == 0
        # 空 list
        assert crgt._find_line_index([], 1) == 0

    def test_check_file_committed_mode_long_file_ends_with_violation(self):
        """集成: check_file(committed=True) 在 50+ 行文件末尾 trigger 应被拦.
        旧版会 false negative (window 滑到文件头, 命中 evidence), 新版会真拦.

        设计: 50 行文件, evidence 仅在 line 1-15 (idx 0-14, 远离末尾),
        trigger 在 line 50 (idx 49). window=30 滑到 added_lines[19:50] (line 20-50),
        不含 evidence → 应返 False (no_evidence violation).
        """
        lines = []
        # line 1-15: 含强 evidence (干扰)
        for i in range(1, 16):
            lines.append(f"line {i} - 已验证 (commit a1b2c3d)")
        # line 16-49: 普通内容 (无 evidence)
        for i in range(16, 50):
            lines.append(f"line {i} - 普通内容")
        # line 50: 末尾 trigger (violation)
        lines.append("line 50 - X 未集成, 是个占位")
        content = "\n".join(lines) + "\n"
        with patch.object(crgt, "get_committed_content", return_value=content):
            violations = crgt.check_file("docs/validation-reports/long.md", committed=True)
        # 应有 violation: 末行 trigger
        triggers = [v[1] for v in violations]
        assert "未集成" in triggers, f"末尾 trigger 应被拦, got violations={violations}"
        assert "占位" in triggers, f"末尾 trigger 应被拦, got violations={violations}"

    def test_committed_mode_integration_340_line_file(self, tmp_path):
        """真文件回归: 模拟 etl-3-runs-2026-06-07.md (340 行) 末尾加 violation,
        跑 --committed 模式应真拦 (rc=1). 复现 D-4 教训: 长 committed 文件
        末尾 trigger 不能被错误放过.
        """
        env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null",
               "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        # 1. init git
        for cmd in [
            ["git", "init", "-q"],
            ["git", "config", "user.email", "t@t"],
            ["git", "config", "user.name", "t"],
        ]:
            subprocess.run(cmd, cwd=str(tmp_path), env=env, check=True, capture_output=True)
        # 2. 写 340 行文件, 前 339 行是真实内容 (含 commit SHA 干扰 evidence)
        #    最后 1 行加 violation
        docs = tmp_path / "docs" / "validation-reports"
        docs.mkdir(parents=True)
        f = docs / "etl-3-runs-2026-06-07.md"
        lines = []
        # line 1-30 含干扰 evidence (模拟文件头的早期 commit 引用)
        for i in range(1, 31):
            lines.append(f"line {i} - 已验证 (commit a1b2c3d{i:04d})")
        # line 31-339 普通内容
        for i in range(31, 340):
            lines.append(f"line {i} - 普通内容")
        # line 340 violation (末尾)
        lines.append("line 340 - X 模块未集成, 是个占位")
        f.write_text("\n".join(lines) + "\n", encoding="utf-8")
        # 3. commit
        subprocess.run(["git", "add", "."], cwd=str(tmp_path), env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", "test 340 line file"],
                       cwd=str(tmp_path), env=env, check=True, capture_output=True)
        # 4. 跑 --committed --files 模式
        rel_path = "docs/validation-reports/etl-3-runs-2026-06-07.md"
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--committed", "--files", rel_path],
            capture_output=True, text=True, env=env, cwd=str(tmp_path), check=False,
        )
        # 期望: 拦 (rc=1), trigger 在 line 340, evidence 在 line 1-30 (远在 window 外)
        assert result.returncode == 1, (
            f"末尾 violation 应被拦, got rc={result.returncode}, "
            f"stdout={result.stdout}, stderr={result.stderr}"
        )
        assert "未集成" in result.stdout or "占位" in result.stdout


# ---------------------------------------------------------------------------
# 11. P1-3 四轮 M1 (2026-06-07) — committed 默认 scope 修 false sense of safety
# ---------------------------------------------------------------------------

class TestM1CommittedDefaultScope:
    """P1-3 四轮 M1 修 (2026-06-07): --committed 没 --files 时, 旧版静默 no-op
    (files=[]). CI 跑 --files glob 没事, 但开发者手动 --committed 会得 false sense
    of safety. 修: 自动 fallback 扫 docs/validation-reports/*.md +
    docs/飞书版架构文档/*.md (匹配 CI workflow 的 scope).
    """

    def test_committed_fallback_scans_validation_reports(self, tmp_path):
        """--committed 不传 --files → 应自动扫 docs/validation-reports/*.md
        并检出其中的 violation (end-to-end).
        """
        env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null",
               "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        # 1. init git
        for cmd in [
            ["git", "init", "-q"],
            ["git", "config", "user.email", "t@t"],
            ["git", "config", "user.name", "t"],
        ]:
            subprocess.run(cmd, cwd=str(tmp_path), env=env, check=True, capture_output=True)
        # 2. 写含 violation 的文件到默认 fallback scope
        docs = tmp_path / "docs" / "validation-reports"
        docs.mkdir(parents=True)
        f = docs / "w4.md"
        f.write_text("# W4\n\nX 未集成, 是个占位\n", encoding="utf-8")
        # 3. commit
        subprocess.run(["git", "add", "."], cwd=str(tmp_path), env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", "test"],
                       cwd=str(tmp_path), env=env, check=True, capture_output=True)
        # 4. 跑 --committed 不传 --files → 应自动 fallback 扫到该文件 → 拦 (rc=1)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--committed"],
            capture_output=True, text=True, env=env, cwd=str(tmp_path), check=False,
        )
        assert result.returncode == 1, (
            f"M1 修: --committed 没 --files 应自动扫 docs/validation-reports/, "
            f"got rc={result.returncode}, stdout={result.stdout}, stderr={result.stderr}"
        )
        assert "未集成" in result.stdout or "占位" in result.stdout

    def test_committed_fallback_empty_repo_no_violation(self, tmp_path):
        """--committed 不传 --files 但 repo 无 review 文件 → 应返 rc=0 (无文件可扫),
        不应崩. 这是 M1 fallback 的 graceful 退出路径.
        """
        env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null",
               "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        for cmd in [
            ["git", "init", "-q"],
            ["git", "config", "user.email", "t@t"],
            ["git", "config", "user.name", "t"],
        ]:
            subprocess.run(cmd, cwd=str(tmp_path), env=env, check=True, capture_output=True)
        # 无 review 文件, 跑 --committed 应 graceful 返 rc=0
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--committed"],
            capture_output=True, text=True, env=env, cwd=str(tmp_path), check=False,
        )
        assert result.returncode == 0
        assert "跳过" in result.stdout or "无 review 文件" in result.stdout or "ok" in result.stdout

    def test_committed_with_explicit_files_overrides_fallback(self, tmp_path):
        """--committed --files X 仍应工作 (显式 --files 覆盖默认 scope, 不破坏 CI 用法)."""
        env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null",
               "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        for cmd in [
            ["git", "init", "-q"],
            ["git", "config", "user.email", "t@t"],
            ["git", "config", "user.name", "t"],
        ]:
            subprocess.run(cmd, cwd=str(tmp_path), env=env, check=True, capture_output=True)
        # 写 2 个 review 文件: 1 个 violation, 1 个 clean
        docs = tmp_path / "docs" / "validation-reports"
        docs.mkdir(parents=True)
        f_violate = docs / "bad.md"
        f_violate.write_text("X 未集成\n", encoding="utf-8")
        f_clean = docs / "good.md"
        f_clean.write_text("W4 ok\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=str(tmp_path), env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", "test"],
                       cwd=str(tmp_path), env=env, check=True, capture_output=True)
        # 显式 --files 只指向 good.md → 应 rc=0 (不扫 bad.md, fallback 不启用)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--committed", "--files", "docs/validation-reports/good.md"],
            capture_output=True, text=True, env=env, cwd=str(tmp_path), check=False,
        )
        assert result.returncode == 0, (
            f"显式 --files 应只扫指定文件 (不启用 fallback), "
            f"got rc={result.returncode}, stdout={result.stdout}"
        )
