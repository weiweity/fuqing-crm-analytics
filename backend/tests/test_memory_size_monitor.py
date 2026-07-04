"""Sprint 201+ R7 MEMORY.md size monitor 锁回归 (L4.59 永久规则化)

- 验证 scripts/memory_size_monitor.py 跑出 MEMORY_SIZE_MONITOR_OK
- 验证 LIMIT_BYTES 跟 L4.13 永久规则一致 (24576)
- 验证 fail-open 原则 (异常 exit 0 不阻 commit)
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path("/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics")
SCRIPT = REPO_ROOT / "scripts" / "memory_size_monitor.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("memory_size_monitor", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_memory_size_monitor_basic() -> None:
    """R7 跨 sprint stable 实证: 当前 MEMORY.md size 在限制内"""
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "MEMORY_SIZE_MONITOR_OK" in result.stdout, (
        f"R7 monitor did not report OK: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert result.returncode == 0, f"R7 monitor exited non-zero: {result.returncode}"


def test_memory_size_monitor_no_op() -> None:
    """R7 监控脚本可被 Python 编译 (语法 OK)"""
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"R7 script syntax error: {result.stderr}"


def test_memory_size_monitor_below_limit() -> None:
    """R7 LIMIT_BYTES 跟 L4.13 永久规则一致 (24576)"""
    mod = _load_module()
    assert mod.LIMIT_BYTES == 24576, f"L4.13 limit must be 24576, got {mod.LIMIT_BYTES}"
    assert mod.MEMORY_PATH.name == "MEMORY.md"


def test_memory_size_monitor_above_limit(monkeypatch, tmp_path) -> None:
    """R7 超过 LIMIT_BYTES 触发告警 + 写 TECH-DEBT.md (mock MEMORY_PATH → 临时文件)"""
    mod = _load_module()
    fake_memory = tmp_path / "MEMORY.md"
    fake_memory.write_bytes(b"x" * (mod.LIMIT_BYTES + 1))
    monkeypatch.setattr(mod, "MEMORY_PATH", fake_memory)
    monkeypatch.setattr(mod, "TECH_DEBT", tmp_path / "TECH-DEBT.md")
    monkeypatch.setattr(mod, "LOG_FILE", tmp_path / "log.txt")
    rc = mod.main()
    assert rc == 0, f"R7 fail-open: even on over-limit must exit 0, got {rc}"
    content = (tmp_path / "TECH-DEBT.md").read_text()
    assert "MEMORY.md Size Alert" in content, (
        f"R7 over-limit must append alert header, got: {content!r}"
    )