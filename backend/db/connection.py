"""
数据库连接管理 — 全局单例 + threading.Lock 双重检查锁定

生命周期规则：
- 连接在首次 get_connection() 时创建，进程生命周期内复用
- 禁止调用 conn.close() — 单例连接由 close_connection() 在应用关闭时统一释放
- 所有 service 函数通过 get_connection() 获取连接，不要自行创建
- DuckDB 连接不是线程安全的：execute / fetch 必须串行化，包装器已自动处理
"""
import logging
import os
import threading
import duckdb
from backend.config import DUCKDB_PATH

logger = logging.getLogger(__name__)

_conn: duckdb.DuckDBPyConnection | None = None
_lock = threading.Lock()
_query_lock = threading.Lock()


class ThreadSafeCursor:
    """线程安全游标：fetch 操作自动获取全局查询锁"""

    def __init__(self, cursor, lock: threading.Lock):
        self._cursor = cursor
        self._lock = lock

    def fetchone(self):
        with self._lock:
            return self._cursor.fetchone()

    def fetchall(self):
        with self._lock:
            return self._cursor.fetchall()

    def fetchdf(self):
        with self._lock:
            return self._cursor.fetchdf()

    def __iter__(self):
        return iter(self._cursor)

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class ThreadSafeConnection:
    """线程安全连接包装器：execute 自动获取全局查询锁"""

    def __init__(self, conn: duckdb.DuckDBPyConnection):
        self._conn = conn

    def execute(self, *args, **kwargs):
        with _query_lock:
            cursor = self._conn.execute(*args, **kwargs)
        return ThreadSafeCursor(cursor, _query_lock)

    def cursor(self):
        with _query_lock:
            c = self._conn.cursor()
        return ThreadSafeCursor(c, _query_lock)

    def close(self):
        with _query_lock:
            return self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_connection() -> ThreadSafeConnection:
    """获取全局共享的 DuckDB 连接（线程安全单例）"""
    global _conn
    if _conn is not None:
        return ThreadSafeConnection(_conn)
    with _lock:
        if _conn is not None:
            return ThreadSafeConnection(_conn)
        db_password = os.environ.get("DUCKDB_PASSWORD")
        if db_password:
            _conn = duckdb.connect(str(DUCKDB_PATH), config={"password": db_password})
        else:
            _conn = duckdb.connect(str(DUCKDB_PATH))
        logger.info("DuckDB 单例连接已创建: %s", DUCKDB_PATH)
        return ThreadSafeConnection(_conn)


def close_connection() -> None:
    """关闭全局 DuckDB 连接（应用关闭时调用）"""
    global _conn
    with _lock:
        if _conn is not None:
            try:
                _conn.close()
                logger.info("DuckDB 连接已关闭")
            except Exception as e:
                logger.debug("关闭 DuckDB 连接时出错: %s", e)
            _conn = None
