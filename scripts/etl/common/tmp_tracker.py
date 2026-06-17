"""Sprint 31.1 — /tmp/fuqing_*.duckdb tracker-database sidecar

设计目标:
  替代 cli.py:53 FQ_TMP_PREFIXES prefix-based whitelist 的机制错误根源.
  物理上不可能再发生 5 次复发模式 (103GB fuqing_sampling2.duckdb 等),
  路径不在 tracker = 不可见, 不可能被 cleanup 误删.

架构:
  - SQLite sidecar 文件 /private/tmp/fuqing-tmp-tracker.db (跟 ETL log 同目录)
  - ETL 写入 /tmp/fuqing_*.duckdb 前 register(path, size, pid)
  - cleanup 跑前 bootstrap_from_filesystem() 扫描 prefix 路径, 把未跟踪的
    外部副本 (workbuddy cache / subagent copy) INSERT OR IGNORE, create_at = mtime
  - 清理时 list_expired(24) 返 (path, size, age_h), 走原 F3 marker / cap / lsof 流程
  - 软失败: 任何 sqlite3 error 只 log 不 raise, cleanup 永不 crash

设计决策 (跟用户对齐过):
  1. Bootstrap create_at = 文件真实 mtime (不重置). 24h+ 外部副本 1 run 治根.
  2. 路径存 resolved realpath 形式 (/private/tmp/...). 处理 macOS /tmp 软链.
  3. FQ_TMP_TRACKER_DISABLED=1 紧急回切到 prefix-only 路径. 2 行代码逃生舱.

复用:
  - Layer 1 cli.py:_cleanup_fq_tmp_orphans 切换到 list_expired() 来源
  - Layer 6 cleanup_subagent.py 改用 is_tracked() 替代静态 prefix 白名单
  - Sprint 26 F6 is_open_by_any_process 仍是 deletion 最后防线
"""
from __future__ import annotations

import glob
import os
import sqlite3
import time
from pathlib import Path
from typing import Optional

# 路径常量: macOS /tmp 是 /private/tmp 的软链, 模块 import 时 resolve 一次,
# 后续所有 INSERT/SELECT/cleanup 用 resolved 形式, 避免 track miss.
TRACKER_DB_PATH = str(Path("/tmp/fuqing-tmp-tracker.db").resolve())

# 应急回切开关: 万一 Phase 1 出 bug (真生产 111GB DB 触发 lsof 误报等),
# 紧急 export FQ_TMP_TRACKER_DISABLED=1 立即回退到 prefix-only 路径,
# 无需 git revert.
DISABLED_ENV_VAR = "FQ_TMP_TRACKER_DISABLED"

# 持久日志 — 跟 cli.py:_safe_log 同 sink (/tmp/fuqing-tmp-cleanup.log),
# 运维审计一条线.
_LOG_PATH = "/tmp/fuqing-tmp-cleanup.log"

# 默认 bootstrap 路径 (跟 FQ_TMP_PREFIXES 一致, 避免引入新白名单)
_DEFAULT_BOOTSTRAP_PREFIXES = (
    "/private/tmp/fuqing_",
    "/private/tmp/_fq_ro",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tracker (
    path      TEXT PRIMARY KEY,
    create_at REAL NOT NULL,
    size      INTEGER NOT NULL,
    pid       INTEGER NOT NULL,
    last_seen REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tracker_create_at ON tracker(create_at);
"""


def _is_disabled() -> bool:
    """检查 FQ_TMP_TRACKER_DISABLED 环境变量."""
    return os.environ.get(DISABLED_ENV_VAR, "").strip() in ("1", "true", "yes")


def _log(msg: str) -> None:
    """软失败日志: 写 /tmp/fuqing-tmp-cleanup.log, 失败不 raise."""
    try:
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()
        with open(_LOG_PATH, "a") as f:
            f.write(f"[{ts}] {tmp_tracker_log_prefix()}{msg}\n")
    except OSError:
        pass


def tmp_tracker_log_prefix() -> str:
    """统一日志前缀, 便于 grep 区分 tracker 事件 vs 其它 cleanup 事件."""
    return "[tmp-tracker] "


def _resolve(path: str) -> str:
    """Resolve path 一次, 处理 macOS /tmp -> /private/tmp 软链.

    Raises:
        OSError: 如果 path 不存在 (os.path.realpath 不会 raise, 但保险起见)
    """
    return str(Path(path).resolve())


def _open_connection(db_path: str) -> sqlite3.Connection:
    """打开一个 SQLite 连接, 配 WAL mode + check_same_thread=False.

    Per-call connection (每次方法调用都开/关) — fork 安全 + 多线程不共享 fd.
    """
    conn = sqlite3.connect(db_path, timeout=5.0, check_same_thread=False)
    # WAL mode: 并发读不阻塞写, kill -9 残留更可恢复
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")  # WAL 配套, 不丢已 commit 数据
    return conn


def _init_db(db_path: str) -> bool:
    """初始化 DB schema. 损坏时自愈: rename .corrupt-<ts> + 重建.

    Returns:
        True if init succeeded, False otherwise (self-heal best-effort).
    """
    parent = os.path.dirname(db_path)
    try:
        os.makedirs(parent, exist_ok=True)
    except OSError as e:
        _log(f"init_db: mkdir failed {parent}: {e}")
        return False

    # 自愈: 检测坏 DB, rename 后重建
    if os.path.exists(db_path):
        try:
            # 试打开 + 跑简单 query, 失败就视为损坏
            test_conn = sqlite3.connect(db_path, timeout=2.0)
            test_conn.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1").fetchone()
            test_conn.close()
        except sqlite3.DatabaseError as e:
            # 损坏 — rename 走人, 重建
            corrupt_path = f"{db_path}.corrupt-{int(time.time())}"
            try:
                os.rename(db_path, corrupt_path)
                _log(f"init_db: corrupt DB renamed to {corrupt_path} (error: {e})")
            except OSError as rename_err:
                _log(f"init_db: corrupt DB detected but rename failed: {rename_err}")
                return False
        except sqlite3.OperationalError as e:
            # OperationalError (locked / busy) 跟 corruption 不同, 不 rename
            _log(f"init_db: operational error (not corruption): {e}")
            return False

    try:
        conn = _open_connection(db_path)
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        _log(f"init_db: schema init failed: {e}")
        return False
    return True


class TrackerDB:
    """SQLite sidecar tracker for /tmp/fuqing_*.duckdb files.

    Sprint 31.1 — 6-layer protection ultimate root-cause fix.
    Replaces prefix-based whitelist (FQ_TMP_PREFIXES) as the source of truth.

    Usage:
        tracker = TrackerDB()
        tracker.register("/private/tmp/fuqing_x.duckdb", size=1024, pid=os.getpid())
        for path, size, age_h in tracker.list_expired(age_hours=24):
            ...delete via cli._cleanup_fq_tmp_orphans flow...
            tracker.remove(path)
    """

    def __init__(
        self,
        db_path: str = TRACKER_DB_PATH,
    ) -> None:
        """构造 + 自愈. 失败不 raise — 调用方应检查 is_available()."""
        self.db_path = db_path
        self._available = False
        if _is_disabled():
            _log(f"disabled via {DISABLED_ENV_VAR}=1, all methods no-op")
            return
        self._available = _init_db(db_path)

    def is_available(self) -> bool:
        """Tracker DB 是否可用. 不可用时所有写方法都 no-op."""
        return self._available

    def register(self, path: str, size: int, pid: Optional[int] = None) -> None:
        """INSERT OR REPLACE a tracker row. 软失败.

        Args:
            path: 绝对路径. 自动 resolve 到 realpath 形式.
            size: 文件字节数. 0 = 文件不存在, list_expired 会跳过.
            pid: 写入进程 PID. 缺省 os.getpid().
        """
        if not self._available:
            return
        try:
            resolved = _resolve(path)
            now = time.time()
            actual_pid = pid if pid is not None else os.getpid()
            conn = _open_connection(self.db_path)
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO tracker "
                    "(path, create_at, size, pid, last_seen) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (resolved, now, size, actual_pid, now),
                )
                conn.commit()
            finally:
                conn.close()
        except (sqlite3.Error, OSError) as e:
            _log(f"register failed {path}: {e}")

    def remove(self, path: str) -> None:
        """DELETE FROM tracker. 软失败 + 幂等 (missing path = no-op)."""
        if not self._available:
            return
        try:
            resolved = _resolve(path)
            conn = _open_connection(self.db_path)
            try:
                conn.execute("DELETE FROM tracker WHERE path = ?", (resolved,))
                conn.commit()
            finally:
                conn.close()
        except (sqlite3.Error, OSError) as e:
            _log(f"remove failed {path}: {e}")

    def list_expired(
        self, age_hours: float = 24.0
    ) -> list[tuple[str, int, float]]:
        """SELECT expired, alive rows. 走 list_expired SQL.

        Returns:
            list of (path, size_bytes, age_hours) tuples, sorted by create_at ASC
            (oldest first, 跟 cli.py:_collect_fq_tmp_orphans 排序一致).

        注: 空 list 时调用方应 fallback 到原 glob 路径, 不要假设一定有数据.
        """
        if not self._available:
            return []
        try:
            cutoff = time.time() - age_hours * 3600
            conn = _open_connection(self.db_path)
            try:
                rows = conn.execute(
                    "SELECT path, size, "
                    "(CAST(? AS REAL) - create_at) / 3600.0 AS age_h "
                    "FROM tracker "
                    "WHERE size > 0 AND create_at < ? "
                    "ORDER BY create_at ASC",
                    (cutoff, cutoff),
                ).fetchall()
            finally:
                conn.close()
            return [(r[0], r[1], r[2]) for r in rows]
        except (sqlite3.Error, OSError) as e:
            _log(f"list_expired failed: {e}")
            return []

    def is_tracked(self, path: str) -> bool:
        """SELECT 1 FROM tracker WHERE path = ?. Used by Layer 6 cross-ref."""
        if not self._available:
            return False
        try:
            resolved = _resolve(path)
            conn = _open_connection(self.db_path)
            try:
                row = conn.execute(
                    "SELECT 1 FROM tracker WHERE path = ? LIMIT 1", (resolved,)
                ).fetchone()
            finally:
                conn.close()
            return row is not None
        except (sqlite3.Error, OSError) as e:
            _log(f"is_tracked failed {path}: {e}")
            return False

    def bootstrap_from_filesystem(
        self,
        prefixes: tuple[str, ...] = _DEFAULT_BOOTSTRAP_PREFIXES,
    ) -> int:
        """扫描 prefixes 下的 *.duckdb, 把未跟踪的 INSERT OR IGNORE.

        这是 103GB 外部副本治根入口: workbuddy cache / subagent 直接 cp
        进来的 fuqing_*.duckdb 第一次 cleanup run 会被发现 + 采用, 第二次
        run (24h 后) 被 list_expired 拾起删除.

        Args:
            prefixes: 扫描根路径前缀. 缺省 = FQ_TMP_PREFIXES (跟旧 prefix
                matching 行为一致, 避免引入新白名单).

        Returns:
            本次 adopted 数量 (不含已存在).

        设计决策:
            - create_at = os.path.getmtime(path) (真实 mtime, 不重置).
              24h+ 外部副本 1 run 治根; < 24h 等下个周期.
            - size = os.path.getsize(path). 0 size 由 list_expired 跳过.
            - 幂等: INSERT OR IGNORE on PK violation.
        """
        if not self._available:
            return 0
        adopted = 0
        now = time.time()
        for prefix in prefixes:
            for raw_path in glob.glob(f"{prefix}*.duckdb"):
                # 跳过 symlink (跟 cli.py F7 一致, 避免 resolve 后 size 跟 target 错)
                if os.path.islink(raw_path) is True:
                    continue
                try:
                    resolved = _resolve(raw_path)
                    # 跳过已经在 tracker 的 (避免 list 完再 filter)
                    if self.is_tracked(resolved):
                        continue
                    mtime = os.path.getmtime(raw_path)
                    size = os.path.getsize(raw_path)
                    conn = _open_connection(self.db_path)
                    try:
                        # INSERT OR IGNORE: 跟 is_tracked check 竞态也无害
                        cur = conn.execute(
                            "INSERT OR IGNORE INTO tracker "
                            "(path, create_at, size, pid, last_seen) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (resolved, mtime, size, os.getpid(), now),
                        )
                        conn.commit()
                        if cur.rowcount > 0:
                            adopted += 1
                    finally:
                        conn.close()
                except (sqlite3.Error, OSError) as e:
                    _log(f"bootstrap skip {raw_path}: {e}")
                    continue
        if adopted:
            _log(f"bootstrap adopted {adopted} file(s) from prefixes={prefixes}")
        return adopted


__all__ = ["TrackerDB", "TRACKER_DB_PATH", "DISABLED_ENV_VAR"]
