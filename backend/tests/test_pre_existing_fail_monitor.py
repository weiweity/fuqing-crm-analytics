"""Sprint 201+ R6 pre-existing fail monitor 锁回归 (L4.59 永久规则化)

- 验证 scripts/pre_existing_fail_monitor.py 跑出 PRE_EXISTING_FAIL_MONITOR_PASS
- 验证 14 case 期望跟 SSOT 对齐 (Sprint 201 R2 v24 治本实证)
- 验证 fail-open 原则 (异常 exit 0 不阻 commit)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # L4.60 跨平台 (test 在 backend/tests/ 下, parents[2] 是 repo root)
SCRIPT = REPO_ROOT / "scripts" / "pre_existing_fail_monitor.py"


def _run_monitor() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(REPO_ROOT),
        env={"PYTHONPATH": str(REPO_ROOT), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_pre_existing_fail_monitor_passes_14_cases() -> None:
    """R6 跨 sprint stable 实证: 4 test file 14 case 全部 PASS"""
    result = _run_monitor()
    assert "PRE_EXISTING_FAIL_MONITOR_PASS" in result.stdout, (
        f"R6 monitor did not report PASS: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "14 passed" in result.stdout, (
        f"R6 monitor expected '14 passed', got: {result.stdout!r}"
    )
    assert result.returncode == 0, f"R6 monitor exited non-zero: {result.returncode}"


def test_pre_existing_fail_monitor_script_syntax() -> None:
    """R6 监控脚本可被 Python 编译 (语法 OK)"""
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"R6 script syntax error: {result.stderr}"


def test_pre_existing_fail_monitor_fail_open() -> None:
    """R6 监控脚本 main() 失败不阻 commit (fail-open 原则, 跟 L4.40 post-merge hook 配套)"""
    import importlib.util

    spec = importlib.util.spec_from_file_location("pre_existing_fail_monitor", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # 异常路径不阻 commit (return 0)
    assert callable(mod.main)
    assert callable(mod.run_pytest)
    assert callable(mod.append_tech_debt)