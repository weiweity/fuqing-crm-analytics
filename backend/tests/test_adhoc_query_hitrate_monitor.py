"""Sprint 201+ R8 ad-hoc-query hitrate monitor 锁回归 (L4.59 永久规则化)

- 验证 scripts/adhoc_query_hitrate_monitor.py 跑出 ADHOC_HITRATE_MONITOR + tools=14
- 验证 EXPECTED_TOOL_COUNT 跟 Sprint 198 治本一致 (14)
- 验证 fail-open 原则 (异常 exit 0 不阻 commit)
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path("/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics")
SCRIPT = REPO_ROOT / "scripts" / "adhoc_query_hitrate_monitor.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("adhoc_query_hitrate_monitor", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_adhoc_query_hitrate_monitor_basic() -> None:
    """R8 跨 sprint stable 实证: 14 tool 全部上 main"""
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "ADHOC_HITRATE_MONITOR" in result.stdout, (
        f"R8 monitor did not report: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "tools: 14" in result.stdout, (
        f"R8 monitor expected 14 tools, got: {result.stdout!r}"
    )
    assert result.returncode == 0, f"R8 monitor exited non-zero: {result.returncode}"


def test_adhoc_query_hitrate_monitor_log_grep() -> None:
    """R8 EXPECTED_TOOL_COUNT 跟 Sprint 198 治本一致 (14, ai-sandbox-execute)"""
    mod = _load_module()
    assert mod.EXPECTED_TOOL_COUNT == 14, (
        f"Sprint 198 ai-sandbox-execute 是第 14 tool, expected 14, got {mod.EXPECTED_TOOL_COUNT}"
    )
    assert mod.HITRATE_THRESHOLD == 0.70
    # L4.35 symlink 治本: SKILL_PATH_CLAUDE 期望在 ~/.claude/skills/ 下
    assert str(mod.SKILL_PATH_CLAUDE).endswith("ad-hoc-query/SKILL.md")
    assert str(mod.SKILL_PATH_WORKBUDDY).endswith("ad-hoc-query/SKILL.md")


def test_adhoc_query_hitrate_monitor_no_op() -> None:
    """R8 监控脚本可被 Python 编译 (语法 OK)"""
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"R8 script syntax error: {result.stderr}"