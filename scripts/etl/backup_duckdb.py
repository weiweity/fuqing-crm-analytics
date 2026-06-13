#!/usr/bin/env python3
"""
芙清 CRM - DuckDB 每日备份 (Sprint 4 P0-2, 2026-06-07)

SOP:
  1. umask 077 (客户数据 600 权限, 其他用户不可读)
  2. shutil.copy2 主 DuckDB → backups/sample_crm_YYYY-MM-DD.duckdb
  3. post-copy verify (duckdb connect 验证备份可打开, 防 APFS torn copy)
  4. zstd 压缩 (55GB → 目标 < 15GB)
  5. 失败清理: zstd 失败时删 uncompressed 中间产物 (防磁盘累积)
  6. log 走 plist stdout/stderr 重定向 (避免双写)
  7. 失败 loud-fail: 主动 sendmail + osascript 系统通知 (Sprint 10 B3)

调度: launchd com.fuqing.duckdb-backup.daily 03:30 daily
复用: cleanup_backups.sh 的 F18 POSIX lock 模式 + 已有 BACKUP_DIR
"""
import os
import sys
import subprocess
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import DUCKDB_PATH, PROCESSED_DATA_DIR  # noqa: E402

BACKUP_DIR = PROCESSED_DATA_DIR / "backups"
LOCK_DIR = Path("/tmp/fuqing-duckdb-backup.lock.d")
# Sprint 10 B3: 用 Beijing 时间 (UTC+8) 命名, 跟用户日历日期一致.
# 之前用 UTC 在 03:30 BJ 跑出来文件名是 6/7, 用户看像 6/7 没 6/8 backup.
# 改 BJ 时间后, 6/8 03:30 BJ 跑出来文件名是 2026-06-08, 跟用户预期一致.
BJ_TZ = timezone(timedelta(hours=8))
TODAY = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
ALERT_EMAIL = "hutou@fuqing.local"  # launchd 失败 loud-fail 收件人


def log(msg: str) -> None:
    # 每次调用算 TS (防 5-20min 跑批时间戳全一样). Sprint 10 B3 改用 BJ 时间戳.
    ts = datetime.now(BJ_TZ).strftime("%Y-%m-%dT%H:%M:%S%z")
    print(f"[{ts}] {msg}", flush=True)


def loud_fail(reason: str) -> None:
    """Sprint 10 B3: launchd 失败 loud-fail.

    主动 sendmail + macOS 系统通知 (osascript display notification), 防止 launchd
    StandardErrorPath 静默失败. exit code 1 让 launchd 也检测到失败.
    """
    log(f"FATAL: {reason}")
    # 1. macOS 系统通知 (桌面弹窗)
    try:
        subprocess.run(
            ["osascript", "-e",
             f'display notification "DuckDB 备份失败: {reason[:80]}" '
             f'with title "芙清 CRM 备份 FAILED" subtitle "{TODAY}"'],
            check=False, timeout=5,
        )
    except Exception as e:
        log(f"osascript 通知失败: {e}")
    # 2. mail 发到 ALERT_EMAIL
    try:
        subprocess.run(
            ["/usr/bin/mail", "-s", f"[FATAL] 芙清 DuckDB 备份失败 {TODAY}", ALERT_EMAIL],
            input=f"backup_duckdb.py 失败\n\n时间: {datetime.now(BJ_TZ).isoformat()}\n原因: {reason}\n日志: /tmp/fuqing-duckdb-backup.log\n",
            text=True, check=False, timeout=10,
        )
    except Exception as e:
        log(f"mail 发送失败: {e}")


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
        backup_path = BACKUP_DIR / f"sample_crm_{TODAY}.duckdb"
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
        # Sprint 10 B3: 加 size > 0 硬验证 (防 zstd 0 字节输出假成功)
        compressed_bytes = compressed_path.stat().st_size
        if compressed_bytes <= 0:
            raise AssertionError(
                f"compressed zst file size is {compressed_bytes} bytes (expected > 0)"
            )
        compressed_mb = compressed_bytes / 1024 / 1024
        log(f"DONE: {compressed_path} ({compressed_mb:.1f} MB, {compressed_bytes} bytes)")
        return 0

    except Exception as e:
        # Sprint 10 B3: loud_fail 主动通知 (osascript + mail) + 仍返回 1 让 launchd 检测
        loud_fail(str(e))
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
