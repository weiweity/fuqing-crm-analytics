"""lsof 副检 — /tmp 孤儿清理的最后一道防线 (Sprint 26 F6 重构)

设计:
  - macOS / Linux /usr/sbin/lsof (项目不引 psutil 依赖,
    跟 Layer 7 cleanup_orphan_pytest.py:lsof -t 同模式)
  - 软失败: lsof 不可用 / 超时不阻塞 cleanup (返回 is_open=False,
    false-negative = 误删风险仍在, false-positive = 多等下次, 选 false-positive)
  - 超时 2s (lsof 默认 1s 太短, fork+exec 慢场景会假阴性)
  - 失败模式统一: (False, reason) — 调用方按 (False, ...) 跳过删除 = 永远不删

复用: scripts/etl/cli.py:143 (Layer 1 atexit) + scripts/etl/cleanup_subagent.py:243 (Layer 6 hourly)
参考: Sprint 25 backup_duckdb.py 复用 scripts/etl/common/lark.py 同模式
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

# lsof 默认超时太短, fork+exec 慢场景会假阴性
_LSOF_TIMEOUT_SEC = 2.0


def is_open_by_any_process(path: str | Path) -> tuple[bool, str]:
    """检查 path 当前是否被任何进程打开 (Sprint 26 F6 副检).

    Args:
        path: 绝对路径 (相对路径 lsof 行为不确定, 调用方传绝对路径)

    Returns:
        (is_open, reason) — is_open=True 表示有进程持有 fd,
        调用方应跳过删除; is_open=False 表示可以删 (或 lsof 不可用 / 超时,
        软失败保守放行). reason 给审计/调试用.

    设计权衡:
      - 不可用 / 超时 → (False, "..."), 不阻塞 cleanup (跟原 mtime 决策一致)
      - "找不到" → (False, "..."), 跟"没人打开" 同语义 (lsof 对 missing file
        通常 stdout 仅 header, 跟"没人打开"同效果, 验证过)
      - lsof -t 模式见 Layer 7 cleanup_orphan_pytest.py (找占锁 PID 用)
    """
    p = str(path)
    lsof_bin = shutil.which("lsof")
    if not lsof_bin:
        return (False, "lsof not found in PATH (保守放行)")

    try:
        result = subprocess.run(
            [lsof_bin, "--", p],
            capture_output=True,
            timeout=_LSOF_TIMEOUT_SEC,
            text=True,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return (False, f"lsof timeout after {_LSOF_TIMEOUT_SEC}s (保守放行)")
    except OSError as e:
        return (False, f"lsof exec error: {e} (保守放行)")

    # lsof 输出格式:
    #   - 首行: "COMMAND  PID  USER  FD  TYPE  DEVICE  SIZE/OFF  NODE  NAME" (header)
    #   - 后续行: 每个 fd 一行
    #   - 空 stdout 或仅 header = 没人打开
    #   - 非空 = 有进程打开
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    if len(lines) <= 1:
        return (False, "lsof empty (no process holds fd)")
    return (True, f"lsof found {len(lines) - 1} fd(s)")


__all__ = ["is_open_by_any_process"]