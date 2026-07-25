"""lsof 副检 — /tmp 孤儿清理的最后一道防线 (PR3 fail-closed)

设计:
  - macOS / Linux lsof (项目不引 psutil 依赖)
  - **fail-closed**: lsof 缺失 / 超时 / 报错 → 视为「可能在用」, 跳过删除
    (false-positive = 多等下次; 禁止 false-negative 误删在用文件)
  - 超时 2s (lsof 默认 1s 太短, fork+exec 慢场景会假阴性)
  - 返回 (is_open, reason): is_open=True → 调用方必须跳过删除

复用: scripts/etl/cli.py (Layer 1 atexit) + scripts/etl/cleanup_subagent.py (Layer 6)
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

_LSOF_TIMEOUT_SEC = 2.0


def is_open_by_any_process(path: str | Path) -> tuple[bool, str]:
    """检查 path 当前是否被任何进程打开.

    Args:
        path: 绝对路径 (相对路径 lsof 行为不确定, 调用方传绝对路径)

    Returns:
        (is_open, reason) — is_open=True 表示有进程持有 fd **或** lsof 不可用
        (fail-closed), 调用方应跳过删除; is_open=False 表示确认无人打开, 可删.
    """
    p = str(path)
    lsof_bin = shutil.which("lsof")
    if not lsof_bin:
        # PR3: fail-closed — 无法确认则不删
        return (True, "lsof not found in PATH (fail-closed: skip delete)")

    try:
        result = subprocess.run(
            [lsof_bin, "--", p],
            capture_output=True,
            timeout=_LSOF_TIMEOUT_SEC,
            text=True,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return (True, f"lsof timeout after {_LSOF_TIMEOUT_SEC}s (fail-closed: skip delete)")
    except OSError as e:
        return (True, f"lsof exec error: {e} (fail-closed: skip delete)")

    # 非 0 且非「无 fd」常见退出码: lsof 对 missing file 常返 1 + 空/仅 header
    # 对权限错误等也 fail-closed
    if result.returncode not in (0, 1):
        return (
            True,
            f"lsof exit={result.returncode} (fail-closed: skip delete)",
        )

    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    if len(lines) <= 1:
        return (False, "lsof empty (no process holds fd)")
    return (True, f"lsof found {len(lines) - 1} fd(s)")


__all__ = ["is_open_by_any_process"]
