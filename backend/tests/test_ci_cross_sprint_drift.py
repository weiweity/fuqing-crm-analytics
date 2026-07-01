"""Sprint 188 B4: ci_cross_sprint_drift.py 锁回归.

目的: 验证 scripts/ci_cross_sprint_drift.py 能 import + 跑起来, 不验证具体 drift
结果 (那是手动跑脚本看的). 跟 scripts/ci/check_e2e_spec_drift.py
+ backend/tests/test_check_e2e_spec_drift.py 模式 stable.

设计:
- test_importable: 验证脚本能 import (无 syntax error / typo)
- test_get_recent_commits: 验证能取最近 1 个 commit (curl up L4.34 跨平台)
- test_check_drift_returns_zero: 验证 main 函数 exit 0 (advisory 模式)
- test_default_constants: 验证默认 N=10 commits + test path 是 test_subprocess_inherits_pythonpath
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# 跟 test_claude_hooks.py 一致: lock CWD to repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "ci_cross_sprint_drift.py"

# Sprint 181 模式: 跨 sprint 导入 scripts/ 时 sys.path 调整
sys.path.insert(0, str(REPO_ROOT / "scripts"))


def test_script_exists():
    """scripts/ci_cross_sprint_drift.py MUST exist (B4 脚手架入口)."""
    assert SCRIPT_PATH.exists(), (
        f"Sprint 188 B4: 期望 {SCRIPT_PATH} 存在 (跨 sprint drift 检测脚手架), "
        f"实际不存在; B4 实施未完成?"
    )


def test_script_importable():
    """scripts/ci_cross_sprint_drift.py MUST import without syntax error."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("ci_cross_sprint_drift", str(SCRIPT_PATH))
    if spec is None or spec.loader is None:
        pytest.fail(f"无法构造 import spec for {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except SyntaxError as exc:
        pytest.fail(f"ci_cross_sprint_drift.py syntax error: {exc}")
    # 期望暴露关键 entry: check_drift + main
    assert hasattr(module, "check_drift"), (
        "期望 ci_cross_sprint_drift module 暴露 'check_drift' 函数 (主入口)"
    )
    assert hasattr(module, "main"), (
        "期望 ci_cross_sprint_drift module 暴露 'main' 函数 (CLI entry)"
    )
    assert hasattr(module, "get_recent_commits"), (
        "期望 module 暴露 'get_recent_commits' 辅助函数"
    )


def test_default_constants():
    """Default N commits + test path MUST target test_subprocess_inherits_pythonpath.

    目的: 锁回归 Sprint 188 B4 范围 — 默认跑 Sprint 187 真因的那个 test, 防后续
    漂移到不相关 test path.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("ci_cross_sprint_drift", str(SCRIPT_PATH))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.DEFAULT_N_COMMITS == 10, (
        f"Sprint 188 B4 默认 N commits 应是 10, got {module.DEFAULT_N_COMMITS}"
    )
    assert "test_subprocess_inherits_pythonpath" in module.DEFAULT_TEST_PATH, (
        f"Sprint 188 B4 默认 test path 应是 test_subprocess_inherits_pythonpath "
        f"(Sprint 187 真因那个 test), got {module.DEFAULT_TEST_PATH}"
    )


def test_get_recent_commits_returns_at_least_one():
    """get_recent_commits(1) MUST return at least 1 commit on main."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("ci_cross_sprint_drift", str(SCRIPT_PATH))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    commits = module.get_recent_commits(1)
    assert isinstance(commits, list), f"期望 get_recent_commits 返 list, got {type(commits)}"
    assert len(commits) >= 1, f"期望至少 1 commit, got {len(commits)}"
    sha, message = commits[0]
    assert len(sha) == 40, f"SHA 应是 40 hex chars, got {sha!r}"
    assert all(c in "0123456789abcdef" for c in sha), f"SHA 不是 hex: {sha!r}"
    assert isinstance(message, str) and message, f"commit message 应是非空 str, got {message!r}"


def test_check_drift_runs_and_exits_zero():
    """check_drift(n=1) MUST run end-to-end and return 0 (advisory mode).

    目的: 验证脚本端到端能跑 — 真建 worktree, 真跑 pytest, 真清理. 这跟
    test_check_e2e_spec_drift.py::test_check_drift_runs_and_exits_zero 模式一致.

    注: 跑 1 commit 是 speed 测试 (单 commit ~1s, 10 commits ~10s). pytest 自己的
    subprocess.run + timeout + cleanup 套 L4.32 cwd lock 模式.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("ci_cross_sprint_drift", str(SCRIPT_PATH))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # 跑 1 commit 验证端到端, 不需要 drift 检测结果 (那是手动跑看的)
    result = module.check_drift(n_commits=1)
    assert result == 0, (
        f"期望 check_drift advisory mode 返 0, got {result}; "
        f"破坏 advisory 模式 = drift detection 阻塞 review skill"
    )


def test_cli_help_exits_zero():
    """`python3 scripts/ci_cross_sprint_drift.py --help` MUST exit 0."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help"],
        capture_output=True,
        text=True,
        timeout=15,
        cwd=str(REPO_ROOT),
        env={"PYTHONPATH": str(REPO_ROOT)},
    )
    assert result.returncode == 0, (
        f"--help 应 rc=0, got rc={result.returncode}, stderr={result.stderr[:300]}"
    )
    assert "跨 sprint CI drift" in result.stdout or "Sprint 188" in result.stdout, (
        f"--help stdout 应含脚本描述, got: {result.stdout[:300]}"
    )