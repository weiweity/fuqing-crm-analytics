"""数据库连接管理 — 全局单例 + threading.Lock 双重检查锁定"""
import os
import threading
import duckdb
from backend.config import DUCKDB_PATH

_conn: duckdb.DuckDBPyConnection | None = None
_lock = threading.Lock()


def get_connection() -> duckdb.DuckDBPyConnection:
    """获取全局共享的 DuckDB 连接（线程安全单例）"""
    global _conn
    if _conn is not None:
        return _conn
    with _lock:
        if _conn is not None:
            return _conn
        db_password = os.environ.get("DUCKDB_PASSWORD")
        if db_password:
            _conn = duckdb.connect(str(DUCKDB_PATH), config={"password": db_password})
        else:
            _conn = duckdb.connect(str(DUCKDB_PATH))
        return _conn


def close_connection() -> None:
    """关闭全局 DuckDB 连接（应用关闭时调用）"""
    global _conn
    with _lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None
