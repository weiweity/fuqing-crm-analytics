"""
数据库连接管理 — 请求级 read-only 路由 + 兼容旧全局写单例

生命周期规则：
- HTTP 看板请求由 QueryRouterMiddleware 绑定 read-only 请求连接
- 非 HTTP / 维护脚本保留历史 write-capable 单例
- 禁止调用 conn.close() — 连接由 close_connection() / middleware 统一释放
- DuckDB 同一个连接不是线程安全的：execute / fetch 必须串行化，包装器已自动处理
"""
from __future__ import annotations

import logging
import threading
import duckdb
from backend.config import DUCKDB_PATH, DUCKDB_MEMORY_LIMIT, DUCKDB_THREADS

logger = logging.getLogger(__name__)

_conn: duckdb.DuckDBPyConnection | None = None
_lock = threading.Lock()
_query_lock = threading.RLock()


class ThreadSafeCursor:
    """线程安全游标：结果在构造时预取到内存，后续 fetch 不触碰连接。

    DuckDB 没有真正的独立 cursor — execute() 的结果集绑定在连接上。
    如果 execute() 和 fetchone() 之间锁被释放，另一个线程的 execute()
    会覆盖结果集，导致读到错误数据。因此必须在构造时（锁内）预取全部结果。
    """

    def __init__(self, cursor, lock: threading.RLock):
        self._cursor = cursor
        # 在锁内一次性把结果从底层 cursor 读到内存
        with lock:
            self._rows = cursor.fetchall()
            self._description = cursor.description
        self._idx = 0

    def fetchone(self):
        if self._idx >= len(self._rows):
            return None
        row = self._rows[self._idx]
        self._idx += 1
        return row

    def fetchall(self):
        rows = self._rows[self._idx:]
        self._idx = len(self._rows)
        return rows

    def fetchdf(self):
        import pandas as pd

        if not self._rows:
            return pd.DataFrame()
        columns = [desc[0] for desc in self._description] if self._description else []
        df = pd.DataFrame(self._rows[self._idx:], columns=columns)
        self._idx = len(self._rows)
        return df

    def __iter__(self):
        return iter(self._rows)

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class ThreadSafeConnection:
    """线程安全连接包装器：execute 自动获取全局查询锁并预取结果"""

    def __init__(
        self,
        conn: duckdb.DuckDBPyConnection,
        lock: threading.RLock | None = None,
        *,
        pooled: bool = False,
    ):
        self._conn = conn
        self._lock = lock or _query_lock
        self._pooled = pooled

    def execute(self, *args, **kwargs):
        with self._lock:
            cursor = self._conn.execute(*args, **kwargs)
            return ThreadSafeCursor(cursor, self._lock)

    def cursor(self):
        with self._lock:
            c = self._conn.cursor()
            return ThreadSafeCursor(c, self._lock)

    def close(self):
        # Request-scoped pooled connections are owned by query_router / dual_conn.
        # Closing them here would recycle or destroy a connection another request
        # may still hold after this handler returns.
        if self._pooled:
            logger.debug("skip close of request-pooled DuckDB connection")
            return None
        with self._lock:
            return self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_duckdb_config(**overrides) -> dict:
    """获取 DuckDB 连接配置（含 memory_limit + threads）.

    使用 config.py 的统一启动预算，显式 overrides 优先。
    HTTP 连接继续走 dual_conn 的 runtime SET，以保留连接兼容性；
    不向同一数据库的现有连接引入不同 connect(config=...) fingerprint。
    """
    cfg = {"memory_limit": DUCKDB_MEMORY_LIMIT, "threads": str(DUCKDB_THREADS)}
    cfg.update(overrides)
    return cfg


def get_connection() -> ThreadSafeConnection:
    """获取 DuckDB 连接。

    HTTP read 请求优先使用 middleware 绑定的 read-only 连接；其他场景保留
    历史 write-capable 单例，避免 ETL / 维护脚本被本次改造破坏。
    """
    from backend.services import dual_conn

    request_conn = dual_conn.get_request_connection()
    if request_conn is not None:
        return ThreadSafeConnection(request_conn.conn, request_conn.lock, pooled=True)

    global _conn
    if _conn is not None:
        return ThreadSafeConnection(_conn)
    with _lock:
        if _conn is not None:
            return ThreadSafeConnection(_conn)
        _conn = dual_conn.get_write_connection()
        logger.info("DuckDB 单例连接已创建: %s (memory_limit=%s)", DUCKDB_PATH, DUCKDB_MEMORY_LIMIT)
        return ThreadSafeConnection(_conn)


def close_connection() -> None:
    """关闭全局 DuckDB 写单例（应用关闭时调用）。

    请求仍占用池连接时不得 drain 共享 read pool，避免关掉他人 owner 的连接。
    """
    global _conn
    from backend.services import dual_conn

    if dual_conn.get_request_connection() is not None:
        logger.debug("request still owns a pooled connection; skip process-wide close")
        return
    with _lock:
        if _conn is not None:
            try:
                _conn.close()
                logger.info("DuckDB 连接已关闭")
            except Exception as e:
                logger.debug("关闭 DuckDB 连接时出错: %s", e)
            _conn = None
    try:
        dual_conn.close_all_connections()
    except Exception as e:  # noqa: BLE001
        logger.debug("关闭 dual DuckDB 连接池时出错: %s", e)
