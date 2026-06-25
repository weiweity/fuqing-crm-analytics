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
  7. 失败 loud-fail: 主动 sendmail + osascript 系统通知 (Sprint 10 B3)

调度: launchd com.fuqing.duckdb-backup.daily 03:30 daily
复用: cleanup_backups.sh 的 F18 POSIX lock 模式 + 已有 BACKUP_DIR
"""
import os
import sys
import subprocess
import shutil
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Sprint 116 抽 _prune_lib 解耦 (修 #D8): backup_duckdb.py 从 _prune_lib import _prune_with_safety + BJ_TZ
# _prune_with_safety + MAGIC_CHECKS + BJ_TZ 都在 _prune_lib.py, 不在 backup_duckdb.py 重复定义.
from scripts.etl.common import _prune_lib  # noqa: E402

from backend.config import DUCKDB_PATH, PROCESSED_DATA_DIR  # noqa: E402

# Sprint 25: 复用 ETL 自己的 lark 通道 (替代 osascript 弹窗, 走 webhook 私聊)
# 失败 graceful degrade: 未配置 LARK_OPEN_ID 时 skip, 不影响主流程
from scripts.etl.common.lark import _send_lark_alert  # noqa: E402

BACKUP_DIR = PROCESSED_DATA_DIR / "backups"
LOCK_DIR = Path("/tmp/fuqing-duckdb-backup.lock.d")
# Sprint 10 B3: 用 Beijing 时间 (UTC+8) 命名, 跟用户日历日期一致.
# 之前用 UTC 在 03:30 BJ 跑出来文件名是 6/7, 用户看像 6/7 没 6/8 backup.
# 改 BJ 时间后, 6/8 03:30 BJ 跑出来文件名是 2026-06-08, 跟用户预期一致.
BJ_TZ = _prune_lib.BJ_TZ  # Sprint 116 抽到 _prune_lib (3 文件去重)
TODAY = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
ALERT_EMAIL = "hutou@fuqing.local"  # launchd 失败 loud-fail 收件人

# Sprint 62.5 治根: backup retention (Sprint 25 设计意图, 实施遗漏)
# 之前脚本只创建 .zst 不清理, 4 份累积到 169GB. 删前 8 项 safety check (lsof/sparse/magic/mtime).
# Sprint 111: 7 → 2 天滚动 (项目小, 2 天容灾足够). KEEP_MIN 1 → 2 保险 (连续 2 天失败仍有 2 份).
BACKUP_RETENTION_DAYS = int(os.environ.get("FQ_BACKUP_RETENTION_DAYS", "2"))
BACKUP_KEEP_MIN = 2  # Sprint 111: 1 → 2, 至少保留最新 2 份, 防单文件被误删

# Sprint 116 抽到 scripts/etl/common/_prune_lib.py (修 #D8 解耦):
# ZSTD_MAGIC, ZST_SUFFIX, BJ_TZ, MAGIC_CHECKS, _matches_magic, _prune_with_safety 全部移到 _prune_lib.
# backup_duckdb.py 现在只是 thin wrapper (_prune_old_backups) 调 _prune_lib._prune_with_safety.


def log(msg: str) -> None:
    # 每次调用算 TS (防 5-20min 跑批时间戳全一样). Sprint 10 B3 改用 BJ 时间戳.
    ts = datetime.now(BJ_TZ).strftime("%Y-%m-%dT%H:%M:%S%z")
    print(f"[{ts}] {msg}", flush=True)


def _prune_old_backups() -> int:
    """Sprint 62.5 治根: 删 > BACKUP_RETENTION_DAYS 天的 .zst.

    Sprint 116 修 #D8+#D9: thin wrapper 调 _prune_lib._prune_with_safety,
    返 int (deleted count) 通过拆 Tuple[int, list[str]] 拿 deleted.
    4 个 sister test (Sprint 62.5) 持续 PASS (assert deleted == N int).

    8 项 safety check (在 _prune_lib._prune_with_safety 实现, 这里是 wrapper):
      1. mtime age > retention (避免误删最新)
      2. 保留 BACKUP_KEEP_MIN 最新份 (防 cap=0 误删全部)
      3. 文件 > 0 字节 (防空文件假象)
      4. per-extension magic check (Sprint 116 修 #D7: PAR1 / DUCK / ZSTD_MAGIC)
      5. lsof 0 fd (无活跃 fd, Sprint 116 修 #D10: FileNotFoundError 保守放行)
      6. caller-side invariant (本次刚生成的 mtime 极新不会超 retention 阈值)
      7. sorted by mtime desc (最新优先保留)
      8. soft fail (删失败 log 不 raise)
    """
    deleted, _deleted_names = _prune_lib._prune_with_safety(  # noqa: deleted_names 丢弃 (wrapper 只返 count)
        backup_dir=BACKUP_DIR,
        glob_patterns=("fuqing_crm_*.duckdb.zst",),
        retention_days=BACKUP_RETENTION_DAYS,
        keep_min=BACKUP_KEEP_MIN,
        log_fn=log,
    )
    return deleted


def loud_fail(reason: str) -> None:
    """Sprint 10 B3 + Sprint 25: launchd 失败 loud-fail.

    Sprint 25 升级: 飞书 webhook 私聊告警 (复用 scripts.etl.common.lark) 走主通道,
    osascript 弹窗 + mail 保留作 fallback. 防止 launchd StandardErrorPath 静默失败.
    exit code 1 让 launchd 也检测到失败.

    治根 (2026-06-17): 原实现 osascript + mail 是无条件调用 (独立 try/except block),
    跟 lark 状态无关 → test 跑 loud_fail 触发 shutil.copy2 mock IOError 时,
    实际生产环境的 macOS 通知被 spam. 修复: osascript + mail 改为仅 lark 失败时
    调用 (lark = 主通道, osascript + mail = fallback 链).
    """
    log(f"FATAL: {reason}")
    lark_content = (
        f"[芙清 CRM 备份 FAILED] {TODAY}\n"
        f"原因: {reason}\n"
        f"时间: {datetime.now(BJ_TZ).isoformat()}\n"
        f"日志: /tmp/fuqing-duckdb-backup.log\n"
        f"机器: {os.uname().nodename if hasattr(os, 'uname') else '?'}"
    )
    # 1. 飞书 webhook 私聊告警 (主通道, Sprint 25 升级)
    lark_sent = False
    try:
        lark_sent, lark_reason = _send_lark_alert(lark_content, timeout=5.0)
        if lark_sent:
            log("lark 告警已发送: OK")
        else:
            log(f"lark 告警跳过/失败: {lark_reason} (走 osascript + mail fallback)")
    except Exception as e:
        log(f"lark 告警异常: {e} (走 osascript + mail fallback)")
    # 2 + 3. fallback 链仅在 lark 失败时触发 (治根: 避免 test 副作用 + 多通道 spam)
    if not lark_sent:
        # 2. macOS 系统通知
        try:
            subprocess.run(
                ["osascript", "-e",
                 f'display notification "DuckDB 备份失败: {reason[:80]}" '
                 f'with title "芙清 CRM 备份 FAILED" subtitle "{TODAY}"'],
                check=False, timeout=5,
            )
        except Exception as e:
            log(f"osascript 通知失败: {e}")
        # 3. mail 发到 ALERT_EMAIL
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

        # Sprint 29+#198 上游治根 (codex 推荐): --verify-only 模式跳过 shutil.copy2 +
        # zstd 压缩, 走 in-process duckdb.connect(read_only=True) verify, 不物理复制
        # 104GB+ DB. 之前 ETL 跑批验证 backup 111GB DB 到 /private/tmp/sprint28-verify/
        # 导致 disk full (FQ_TMP_PREFIXES 白名单不覆盖), 走 --verify-only 避免这种用法.
        if verify_only:
            log(f"verify-only mode (跳过 shutil.copy2 + zstd): {DUCKDB_PATH.name}")
            import duckdb  # noqa: PLC0415
            conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)
            try:
                # 跟 SOP post-copy verify 一致: 连接 + 简单 SELECT 验证
                row = conn.execute(
                    "SELECT COUNT(*), MAX(pay_time) FROM orders"
                ).fetchone()
                if row is None:
                    raise AssertionError("verify SELECT returned no row")
                log(
                    f"DONE (verify-only): orders count={row[0]:,}, max_pay_time={row[1]} "
                    f"(no file copied, 0 bytes disk usage)"
                )
            finally:
                conn.close()
            return 0

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        # Sprint 25: 文件名加 _{HHMM} 时间戳, 真滚动保留 7 天历史 (修复 cleanup_backups.sh 7 天清理伪命题)
        # 之前每天同名覆盖, 7 天滚动其实是 1 份文件
        hhmm = datetime.now(BJ_TZ).strftime("%H%M")
        backup_path = BACKUP_DIR / f"fuqing_crm_{TODAY}_{hhmm}.duckdb"
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

        # Sprint 62.5 治根: backup retention (7 天滚动)
        pruned = _prune_old_backups()
        if pruned:
            log(f"prune: removed {pruned} old backup(s) (> {BACKUP_RETENTION_DAYS}d)")
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
    import argparse
    parser = argparse.ArgumentParser(
        description="芙清 CRM DuckDB 每日备份 + Sprint 29+ verify-only 模式"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="跳过 shutil.copy2 + zstd 压缩, 走 in-process duckdb.connect(read_only=True) verify. "
             "0 字节磁盘占用. 适合 ETL 跑批前的 duckdb file sanity check "
             "(替代 backup 104GB+ DB 到 /private/tmp/sprint28-verify/ 的反模式).",
    )
    args = parser.parse_args()
    sys.exit(main(verify_only=args.verify_only))
