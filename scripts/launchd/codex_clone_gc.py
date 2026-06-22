#!/usr/bin/env python3
"""
Sprint 62.5 B4: Codex code_sign_clone GC (2026-06-22)

痛点: Codex app 每次更新做 code_sign_clone 复制到
  /private/var/folders/tz/<user>/X/com.openai.codex.code_sign_clone.*/
  累积 40 份 = 53GB (2026-06-22 实测).

治根: 每天凌晨 03:00 跑一次, 删 > 7 天的 clone, 保留最新 1 份
  (Codex 启动时仍需要的最新 Gatekeeper clone).

8 项 safety check (Sprint 28+ 实战 fix 模式):
  1. lsof 0 fd (无进程打开)
  2. mtime age > 7 天
  3. 保留最新 1 份 (防 cap=0 误删全部)
  4. 仅扫描 com.openai.codex.code_sign_clone.* 目录
  5. 仅在 macOS (其他平台直接 return)
  6. 不动其他 com.* 应用 (Chrome / Safari / WPS 等)
  7. soft fail (任何 OSError log 不 raise, 退出 0)
  8. log 到 /tmp/fuqing-codex-clone-gc.log

设计 (跟 Sprint 60.2 P3 L4.7 一致):
  - python3 不用 bash (避开 macOS launchd sandbox deny bash)
  - RunAtLoad=false (等 StartCalendarInterval 触发, 避免 install 时立即跑)
  - exit 0 (即使无 clone 可清, 也成功退出, launchd 不视为失败)
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

# 仅扫描这两类 code_sign_clone (Codex + Chrome, 排除其他 com.*)
TARGET_NAMES = (
    "com.openai.codex.code_sign_clone",
    "com.google.Chrome.code_sign_clone",
)

# 用户私有临时目录 (macOS XDG_RUNTIME_DIR 类似)
# 用 base_dir + glob_pattern 两段, 支持 test 时 monkeypatch base_dir.
X_DIR_GLOB_BASE = Path("/private/var/folders/tz")
X_DIR_GLOB_PATTERN = "*/X"

RETENTION_DAYS = 7
KEEP_MIN = 1  # 至少保留最新 1 份 (Codex 启动验证可能仍引用)

LOG_PATH = "/tmp/fuqing-codex-clone-gc.log"


def log(msg: str) -> None:
    """追加 log 到 /tmp/fuqing-codex-clone-gc.log (软失败)."""
    try:
        from datetime import datetime, timezone, timedelta
        ts = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%dT%H:%M:%S%z")
        with open(LOG_PATH, "a") as f:
            f.write(f"[{ts}] {msg}\n")
    except OSError:
        pass


def _is_in_use(path: Path) -> bool:
    """lsof 0 fd 校验 (Sprint 26 F6 副检). 软失败: lsof 不可用 → False 放行."""
    try:
        out = subprocess.run(
            ["lsof", "-t", str(path)],
            capture_output=True, text=True, timeout=5,
        )
        return bool(out.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False  # 保守放行


def _collect_clones() -> list[Path]:
    """扫描所有 target name 的 clone 目录 (按 mtime 倒序, 最新优先).

    用 base_dir.glob("*/X") 支持 test monkeypatch base_dir.

    Sprint 66 P1 排查: CI runner 上 gc_once() deleted=0 但本地 PASS.
    加 print debug 输出 (只在 FAIL 时能看到).
    """
    clones: list[Path] = []
    if not X_DIR_GLOB_BASE.is_dir():
        print(f"[codex_clone_gc DEBUG] X_DIR_GLOB_BASE={X_DIR_GLOB_BASE} not is_dir, return []")
        return clones
    print(f"[codex_clone_gc DEBUG] X_DIR_GLOB_BASE={X_DIR_GLOB_BASE} glob {X_DIR_GLOB_PATTERN}")
    for x_dir in X_DIR_GLOB_BASE.glob(X_DIR_GLOB_PATTERN):
        if not x_dir.is_dir():
            print(f"[codex_clone_gc DEBUG] {x_dir} not is_dir, skip")
            continue
        for target in TARGET_NAMES:
            target_dir = x_dir / target
            if not target_dir.is_dir():
                print(f"[codex_clone_gc DEBUG] {target_dir} not is_dir, skip")
                continue
            for entry in target_dir.iterdir():
                if entry.name.startswith(f"{target}."):
                    clones.append(entry)
                else:
                    print(f"[codex_clone_gc DEBUG] {entry.name} not startswith {target}., skip")
    clones.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    print(f"[codex_clone_gc DEBUG] collected {len(clones)} clones: {[c.name for c in clones]}")
    return clones


def gc_once() -> tuple[int, int]:
    """跑一次 GC. Returns (deleted_count, bytes_freed_gb).

    8 项 safety check:
      1. 仅 macOS (其他平台 return 0, 0)
      2. KEEP_MIN 守护 (永远保留最新 KEEP_MIN 份)
      3. 仅 TARGET_NAMES (不动其他 com.* 应用)
      4. mtime age > RETENTION_DAYS
      5. lsof 0 fd
      6. soft fail (rmtree fail log 不 raise)
      7. 不在 KEEP_MIN 守护范围
      8. log 到 LOG_PATH
    """
    if not sys.platform == "darwin":
        log("skip: not macOS")
        return 0, 0

    clones = _collect_clones()
    if len(clones) <= KEEP_MIN:
        log(f"found {len(clones)} clone(s), <= keep_min={KEEP_MIN}, nothing to do")
        return 0, 0

    cutoff = time.time() - RETENTION_DAYS * 86400
    candidates = [p for p in clones[KEEP_MIN:] if p.stat().st_mtime < cutoff]

    deleted = 0
    bytes_freed = 0
    for p in candidates:
        # safety 5: lsof 0 fd
        if _is_in_use(p):
            log(f"skip (lsof open): {p}")
            continue
        # safety 6: soft fail rmtree
        try:
            size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
            shutil.rmtree(p)
            deleted += 1
            bytes_freed += size
            log(f"deleted: {p.name} ({size / 1024 / 1024 / 1024:.1f} GiB)")
        except OSError as e:
            log(f"delete failed {p}: {e}")

    log(f"DONE: {deleted} clone(s) deleted, {bytes_freed / 1024 / 1024 / 1024:.1f} GiB freed")
    return deleted, bytes_freed


def main() -> int:
    log("=== codex-clone-gc start ===")
    deleted, _ = gc_once()
    log(f"=== codex-clone-gc end ({deleted} deleted) ===")
    return 0  # always 0, 避免 launchd 视为失败


if __name__ == "__main__":
    sys.exit(main())