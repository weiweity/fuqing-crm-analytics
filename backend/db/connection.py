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
from backend.config import DUCKDB_PATH, DUCKDB_MEMORY_LIMIT

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

    def __init__(self, cursor, lock: threading.Lock):
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


def get_duckdb_config(**overrides) -> dict:
    """获取 DuckDB 连接配置（含 memory_limit）。

    所有 duckdb.connect() 调用应使用此函数获取 config，确保内存限制统一生效。
    可通过 overrides 覆盖或追加配置项。
    """
    cfg = {"memory_limit": DUCKDB_MEMORY_LIMIT}
    cfg.update(overrides)
    return cfg


def get_connection(read_only: bool = True) -> ThreadSafeConnection:
    """获取全局共享的 DuckDB 连接（线程安全单例）

    Args:
        read_only: 是否只读连接（默认 True）。uvicorn 调用时必须为 True，
            避免 ETL 跑批时 uvicorn 跟 ETL 抢写锁导致 "Conflicting lock" 错误。
            ETL 端如果需要写 DuckDB，明确传 read_only=False。

    关键历史（QW2 工单）：
    之前 uvicorn 默认 read_write，ETL 跑批时 ETL 持写锁 → uvicorn
    报 "IO Error: Could not set lock on file .../fuqing_crm.duckdb:
    Conflicting lock" → API 500 → 前端空数据。
    修复：uvicorn 永远只读，ETL 写时用 read_only=False 单独 connect。
    """
    global _conn
    if _conn is not None:
        return ThreadSafeConnection(_conn)
    with _lock:
        if _conn is not None:
            return ThreadSafeConnection(_conn)
        cfg = get_duckdb_config()
        db_password = os.environ.get("DUCKDB_PASSWORD")
        if db_password:
            cfg["password"] = db_password
        if read_only:
            # read_only 模式强制 read_only=True（即使之前 _conn 是 read_write 也会重建）
            cfg["access_mode"] = "READ_ONLY"
        _conn = duckdb.connect(str(DUCKDB_PATH), config=cfg)
        logger.info(
            "DuckDB 单例连接已创建: %s (memory_limit=%s, read_only=%s)",
            DUCKDB_PATH, DUCKDB_MEMORY_LIMIT, read_only,
        )
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
