#!/usr/bin/env python3
"""Sprint 111: cleanup_backups.py — L4.7 Python 端口 of cleanup_backups.sh.
Sprint 112: refactor 用 _prune_with_safety (8 项 safety check 复用).
Sprint 116: refactor 抽 _prune_lib 解耦 (修 #D8) + per-extension magic check (修 #D7) +
            Tuple[int, list[str]] 返值 (修 #D9 deleted_names observability).
Sprint 117: rename _prune_lib → prune_lib (修 #D11 PEP 8) + 4 项真治本
            (#D12 _matches_magic 返 tuple + #D13 case-insensitive + #D14 显式 sort longest-first).

L4.7 永久规则合规: launchd 首选 python3 不用 bash (/bin/bash macOS sandbox
deny Desktop 路径, Sprint 111 诊断日志 "Operation not permitted" 确认).
Sprint 62.5 N3 plist Status=126 失效的 L4.7 治根修复.

保留原 bash 脚本所有功能:
  - 清理 data/processed/backups/ 下 mtime > RETENTION_DAYS 天的
    .parquet / .duckdb / .duckdb.zst (Sprint 25 加 zst 模式)
  - 8 项 safety check (Sprint 116 抽 shared prune_lib, Sprint 117 rename 去 _):
    mtime age + keep_min + size>0 + per-extension magic (PAR1/DUCK/ZSTD_MAGIC) + lsof 0 fd + soft fail
  - 软失败: 单文件 unlink 失败只 log, 不阻塞
  - mkdir-based lock 防并发 (F18 修复, POSIX 兼容)
  - 输出 plain-text 到 /tmp/fuqing-backup-cleanup.log (launchd 仅看 exit code)

Sprint 111 改动 (跟 backup_duckdb.py 同步):
  - RETENTION_DAYS 7 → 2 (FQ_BACKUP_RETENTION_DAYS env override)
  - BACKUP_KEEP_MIN 1 → 2 (FQ_BACKUP_KEEP_MIN env override, 保险 1 份)
  - BJ_TZ 时区跟 backup_duckdb.py 一致 (跨 sprint launchd 跑批 03:30 BJ 同步)

Sprint 112 改动:
  - refactor: 8 项 safety check 抽到 _prune_with_safety (initially in backup_duckdb.py)
  - 0 代码重复, 1 真业务 sprint 触发的 留尾治理 sprint (#D5 闭环)

Sprint 116 改动:
  - 修 #D8: cleanup_backups.py 不再 `from scripts.etl import backup_duckdb`
    (避免拉起 backup_duckdb 模块 → 拉起 lark SDK).
    改 `from scripts.etl.common import _prune_lib` (干净 import, 不触发 lark 副作用).
  - 修 #D9: 接收 _prune_lib._prune_with_safety 返 Tuple[int, list[str]],
    拼回 '| files: ...' observability 字段 (跟 Sprint 111 一致).

Sprint 117 改动 (跟 Sprint 116 模式一致, 留尾治理 sprint 模式 stable):
  - 修 #D11: rename _prune_lib → prune_lib (PEP 8 public, 跨模块访问合法)
  - 修 #D12: _matches_magic 返 tuple[bool, str], log 完整 reason (offset + actual magic)
  - 修 #D13: case-insensitive 匹配 (macOS APFS case-preserving vs Linux HFS+ case-insensitive)
  - 修 #D14: 显式 sort longest-first (sorted(MAGIC_CHECKS, key=len, reverse=True)),
    不依赖 dict iteration order
"""
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

# 跟 backup_duckdb.py 同步: script mode 下 sys.path bootstrap
# (launchd 跑 `python3 scripts/etl/cleanup_backups.py` 时 sys.path[0] = scripts/etl/,
# 找不到 backend/ package. 这里显式 insert project root.)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # noqa: E402
sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import PROCESSED_DATA_DIR  # noqa: E402
from scripts.etl.common import prune_lib  # noqa: E402  # Sprint 117 rename _prune_lib → prune_lib (修 #D11)

BJ_TZ = prune_lib.BJ_TZ  # Sprint 116 抽 + Sprint 117 rename (3 文件 SSOT)
BACKUP_DIR = PROCESSED_DATA_DIR / "backups"
LOG_FILE = Path("/tmp/fuqing-backup-cleanup.log")
LOCK_DIR = Path("/tmp/fuqing-backup-cleanup.lock.d")
RETENTION_DAYS = int(os.environ.get("FQ_BACKUP_RETENTION_DAYS", "2"))  # Sprint 111: 7 → 2
BACKUP_KEEP_MIN = int(os.environ.get("FQ_BACKUP_KEEP_MIN", "2"))  # Sprint 111: 1 → 2
PATTERNS = ("*.parquet", "*.duckdb", "*.duckdb.zst")


def log(msg: str) -> None:
    ts = datetime.now(BJ_TZ).strftime("%Y-%m-%dT%H:%M:%S%z")
    line = f"[{ts}] {msg}\n"
    print(line, end="", flush=True)
    with LOG_FILE.open("a") as f:
        f.write(line)


def main() -> int:
    # mkdir-based lock (F18 修复, POSIX 兼容)
    try:
        LOCK_DIR.mkdir()
    except FileExistsError:
        log(f"SKIP: another instance holds {LOCK_DIR}")
        return 0

    try:
        if not BACKUP_DIR.exists():
            log(f"SKIP: {BACKUP_DIR} 不存在")
            return 0

        # 收集 before stats
        before_files: list[Path] = []
        for pat in PATTERNS:
            before_files.extend(BACKUP_DIR.glob(pat))
        before_count = len(before_files)
        before_bytes = sum(p.stat().st_size for p in before_files if p.exists())

        # Sprint 116 refactor: 调 _prune_lib._prune_with_safety (8 项 safety check, 修 #D7-#D10)
        # Sprint 117: rename → prune_lib._prune_with_safety (修 #D11)
        # 修 #D5+#D7+#D8+#D9+#D10 (Sprint 111/112 /review defer): cleanup_backups.py 现在有完整 8 safety check
        # 修 #D8: 不再 `from scripts.etl import backup_duckdb` (避免拉起 lark SDK)
        # 修 #D9: 接收 Tuple[int, list[str]] 返值, 拼回 '| files: ...' observability 字段
        # 修 #D11-#D14: prune_lib._matches_magic 返 tuple (case-insensitive + 显式 sort + 完整 reason)
        deleted, deleted_names = prune_lib._prune_with_safety(
            backup_dir=BACKUP_DIR,
            glob_patterns=PATTERNS,
            retention_days=RETENTION_DAYS,
            keep_min=BACKUP_KEEP_MIN,
            log_fn=log,
        )

        # 重新统计 after
        after_files: list[Path] = []
        for pat in PATTERNS:
            after_files.extend(BACKUP_DIR.glob(pat))
        after_count = len(after_files)
        after_bytes = sum(p.stat().st_size for p in after_files if p.exists())

        before_mb = before_bytes // (1024 * 1024)
        after_mb = after_bytes // (1024 * 1024)
        summary = (
            f"backups cleanup: before={before_count} files/{before_mb}MB → "
            f"after={after_count} files/{after_mb}MB, "
            f"deleted={deleted} files/{before_mb - after_mb}MB"
        )
        # Sprint 116 修 #D9: 拼回 '| files: ...' observability 字段 (跟 Sprint 111 一致)
        if deleted_names:
            summary += f" | files: {' '.join(deleted_names)}"
        log(summary)

        disk_free = shutil.disk_usage(BACKUP_DIR)
        log(
            f"disk_free_after_cleanup: total={disk_free.total // (1024**3)}GiB, "
            f"used={disk_free.used // (1024**3)}GiB, free={disk_free.free // (1024**3)}GiB | "
            f"backups_size_total={after_mb}MB"
        )
        return 0
    finally:
        try:
            LOCK_DIR.rmdir()
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
