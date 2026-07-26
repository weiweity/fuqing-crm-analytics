#!/usr/bin/env python3
"""
芙清 CRM - legacy DuckDB 备份入口（默认硬拒绝）。

2026-07-26 安全复核后，``shutil.copy2 + zstd`` 整库热拷贝已停用：
它会制造数据库同体积的磁盘尖峰，且没有一致性/恢复演练契约。当前脚本只保留
``--verify-only`` 零拷贝只读校验。正式备份必须按
``docs/maintenance/duckdb-backup-upgrade-checklist.md`` 另行实施 DuckDB 原生
``COPY FROM DATABASE`` 一致性副本。
"""
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Sprint 117 rename _prune_lib → prune_lib (修 #D11 PEP 8 private 跨模块访问)
# Sprint 116 解耦 (修 #D8) 持续: backup_duckdb.py 从 prune_lib import _prune_with_safety + BJ_TZ.
from scripts.etl.common import prune_lib  # noqa: E402

from backend.config import DUCKDB_PATH, PROCESSED_DATA_DIR  # noqa: E402

# Sprint 164: 飞书完整解耦, 删 lark 通道 (osascript + mail 替代, 跟 Sprint 25 fallback 链对齐)

BACKUP_DIR = PROCESSED_DATA_DIR / "backups"
LOCK_DIR = Path("/tmp/fuqing-duckdb-backup.lock.d")
# Sprint 10 B3: 用 Beijing 时间 (UTC+8) 命名, 跟用户日历日期一致.
# 之前用 UTC 在 03:30 BJ 跑出来文件名是 6/7, 用户看像 6/7 没 6/8 backup.
# 改 BJ 时间后, 6/8 03:30 BJ 跑出来文件名是 2026-06-08, 跟用户预期一致.
BJ_TZ = prune_lib.BJ_TZ  # Sprint 116 抽到 prune_lib (3 文件去重, Sprint 117 rename 去 _)
TODAY = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
ALERT_EMAIL = "hutou@fuqing.local"  # launchd 失败 loud-fail 收件人

# Sprint 62.5 治根: backup retention (Sprint 25 设计意图, 实施遗漏)
# 之前脚本只创建 .zst 不清理, 4 份累积到 169GB. 删前 8 项 safety check (lsof/sparse/magic/mtime).
# Sprint 111: 7 → 2 天滚动 (项目小, 2 天容灾足够). KEEP_MIN 1 → 2 保险 (连续 2 天失败仍有 2 份).
BACKUP_RETENTION_DAYS = int(os.environ.get("FQ_BACKUP_RETENTION_DAYS", "2"))
BACKUP_KEEP_MIN = 2  # Sprint 111: 1 → 2, 至少保留最新 2 份, 防单文件被误删

# Sprint 116 抽到 scripts/etl/common/_prune_lib.py (修 #D8 解耦), Sprint 117 rename → prune_lib (修 #D11):
# ZSTD_MAGIC, ZST_SUFFIX, BJ_TZ, MAGIC_CHECKS, _matches_magic, _prune_with_safety 全部移到 prune_lib.
# backup_duckdb.py 现在只是 thin wrapper (_prune_old_backups) 调 prune_lib._prune_with_safety.


def log(msg: str) -> None:
    # 每次调用算 TS (防 5-20min 跑批时间戳全一样). Sprint 10 B3 改用 BJ 时间戳.
    ts = datetime.now(BJ_TZ).strftime("%Y-%m-%dT%H:%M:%S%z")
    print(f"[{ts}] {msg}", flush=True)


def _prune_old_backups() -> int:
    """Sprint 62.5 治根: 删 > BACKUP_RETENTION_DAYS 天的 .zst.

    Sprint 116 修 #D8+#D9: thin wrapper 调 prune_lib._prune_with_safety,
    返 int (deleted count) 通过拆 Tuple[int, list[str]] 拿 deleted.
    4 个 sister test (Sprint 62.5) 持续 PASS (assert deleted == N int).

    8 项 safety check (在 prune_lib._prune_with_safety 实现, 这里是 wrapper):
      1. mtime age > retention (避免误删最新)
      2. 保留 BACKUP_KEEP_MIN 最新份 (防 cap=0 误删全部)
      3. 文件 > 0 字节 (防空文件假象)
      4. per-extension magic check (Sprint 116 修 #D7: PAR1 / DUCK / ZSTD_MAGIC;
         Sprint 117 修 #D12+#D13: tuple 返值 + case-insensitive)
      5. lsof 明确确认 0 fd (缺失、超时、权限拒绝或异常返回均 fail-closed)
      6. caller-side invariant (本次刚生成的 mtime 极新不会超 retention 阈值)
      7. sorted by mtime desc (最新优先保留)
      8. soft fail (删失败 log 不 raise)
    """
    # deleted_names 由 shared helper 写日志；这个兼容 wrapper 只公开 count。
    deleted, _deleted_names = prune_lib._prune_with_safety(
        backup_dir=BACKUP_DIR,
        glob_patterns=("fuqing_crm_*.duckdb.zst",),
        retention_days=BACKUP_RETENTION_DAYS,
        keep_min=BACKUP_KEEP_MIN,
        log_fn=log,
    )
    return deleted


def loud_fail(reason: str) -> None:
    """Sprint 10 B3 + Sprint 25 + Sprint 164: launchd 失败 loud-fail.

    Sprint 164: 飞书完整解耦, 删 lark 主通道, 走 osascript + mail 替代 (本地通知不依赖飞书).
    exit code 1 让 launchd 也检测到失败.
    """
    log(f"FATAL: {reason}")
    # 1. macOS 系统通知
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


def main(verify_only: bool = False) -> int:
    # 客户数据保护: 文件 600 权限 (其他用户不可读)
    os.umask(0o077)

    if not verify_only:
        log(
            "REFUSED: legacy shutil.copy2 + zstd backup is disabled; "
            "use --verify-only or the approved native backup runbook"
        )
        return 2

    # F18 POSIX lock 防并发
    try:
        LOCK_DIR.mkdir(exist_ok=False)
    except FileExistsError:
        log(
            f"ERROR: verify-only did not run because lock exists: {LOCK_DIR}; "
            "inspect the holder or stale lock before retrying"
        )
        return 1

    try:
        if not DUCKDB_PATH.exists():
            log(f"ERROR: {DUCKDB_PATH} not found")
            return 1

        log(f"verify-only mode (no file copy): {DUCKDB_PATH.name}")
        import duckdb  # noqa: PLC0415
        conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)
        try:
            row = conn.execute(
                "SELECT COUNT(*), MAX(pay_time) FROM orders"
            ).fetchone()
            if row is None or row[0] <= 0 or row[1] is None:
                raise AssertionError(
                    "orders sanity check failed: expected non-empty rows and "
                    "a non-null max pay_time"
                )
            log(
                f"DONE (verify-only): orders count={row[0]:,}, "
                f"max_pay_time={row[1]} (no file copied, 0 bytes disk usage)"
            )
        finally:
            conn.close()
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


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="芙清 CRM legacy backup guard + zero-copy verify-only"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="走 duckdb.connect(read_only=True) 文件 sanity check；0 字节复制。"
             "不带此参数会因 legacy backup 已停用而返回 2。",
    )
    args = parser.parse_args()
    sys.exit(main(verify_only=args.verify_only))
