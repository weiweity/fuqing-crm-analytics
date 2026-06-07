#!/usr/bin/env python3
"""
芙清 CRM - DuckDB 每日备份 (Sprint 4 P0-2, 2026-06-07)

SOP:
  1. umask 077 (客户数据 600 权限, 其他用户不可读)
  2. shutil.copy2 主 DuckDB → backups/fuqing_crm_YYYY-MM-DD.duckdb
  3. post-copy verify (duckdb connect 验证备份可打开, 防 APFS torn copy)
  4. zstd 压缩 (55GB → 目标 < 15GB)
  5. 失败清理: zstd 失败时删 uncompressed 中间产物 (防磁盘累积)
  6. log 走 plist stdout/stderr 重定向 (避免双写)

调度: launchd com.fuqing.duckdb-backup.daily 03:30 daily
复用: cleanup_backups.sh 的 F18 POSIX lock 模式 + 已有 BACKUP_DIR
"""
import os
import sys
import subprocess
import shutil
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import DUCKDB_PATH, PROCESSED_DATA_DIR  # noqa: E402

BACKUP_DIR = PROCESSED_DATA_DIR / "backups"
LOCK_DIR = Path("/tmp/fuqing-duckdb-backup.lock.d")
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def log(msg: str) -> None:
    # 每次调用算 TS (防 5-20min 跑批时间戳全一样)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] {msg}", flush=True)


def main() -> int:
    # 客户数据保护: 文件 600 权限 (其他用户不可读)
    os.umask(0o077)

    # F18 POSIX lock 防并发
    try:
        LOCK_DIR.mkdir(exist_ok=False)
    except FileExistsError:
        log(f"SKIP: another instance holds {LOCK_DIR}")
        return 0

    backup_path = None
    try:
        if not DUCKDB_PATH.exists():
            log(f"ERROR: {DUCKDB_PATH} not found")
            return 1

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup_path = BACKUP_DIR / f"fuqing_crm_{TODAY}.duckdb"
        compressed_path = backup_path.with_suffix(".duckdb.zst")

        # Step 1: os-level 复制 (不需 DuckDB lock)
        log(f"shutil.copy2 {DUCKDB_PATH.name} → {backup_path.name}")
        shutil.copy2(DUCKDB_PATH, backup_path)

        # Step 2: post-copy verify (防 APFS torn copy, 1-2s)
        log("post-copy verify (duckdb connect read_only)")
        import duckdb  # noqa: PLC0415
        conn = duckdb.connect(str(backup_path), read_only=True)
        conn.close()

        # Step 3: zstd 压缩 (绝对路径避免 launchd PATH 不含 homebrew)
        log(f"compressing → {compressed_path.name}")
        subprocess.run(
            ["/Users/hutou/homebrew/bin/zstd", "-q", "--rm", "-f",
             str(backup_path), "-o", str(compressed_path)],
            check=True,
        )
        compressed_mb = compressed_path.stat().st_size / 1024 / 1024
        log(f"DONE: {compressed_path} ({compressed_mb:.1f} MB)")
        return 0

    except Exception as e:
        log(f"ERROR: {e}")
        return 1
    finally:
        try:
            LOCK_DIR.rmdir()
        except OSError:
            pass
        # zstd 失败时清理 uncompressed 中间产物 (防磁盘累积)
        # 成功路径下 backup_path 已被 zstd --rm 删, unlink FileNotFoundError 被 try/except 吞掉
        if backup_path is not None:
            try:
                backup_path.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    sys.exit(main())
