"""
数据库连接管理 — 全局单例 + threading.Lock 双重检查锁定

生命周期规则：
- 连接在首次 get_connection() 时创建，进程生命周期内复用
- 禁止调用 conn.close() — 单例连接由 close_connection() 在应用关闭时统一释放
- 所有 service 函数通过 get_connection() 获取连接，不要自行创建
"""
import logging
import os
import threading
import duckdb
from backend.config import DUCKDB_PATH

logger = logging.getLogger(__name__)

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
        logger.info("DuckDB 单例连接已创建: %s", DUCKDB_PATH)
        return _conn


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
