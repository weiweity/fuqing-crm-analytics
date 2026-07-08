"""Read/write connection routing for Sprint 201 R1.

HTTP dashboard requests borrow short-lived read-only DuckDB connections from a
small pool. Non-HTTP code keeps the historical write-capable singleton path in
``backend.db.connection`` so ETL and maintenance scripts remain compatible.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
import logging
import os
import threading
from typing import Iterator

import duckdb

from backend.config import DUCKDB_MEMORY_LIMIT, DUCKDB_PATH

logger = logging.getLogger(__name__)

READ_POOL_SIZE = int(os.environ.get("FQ_READ_POOL_SIZE", "2"))  # L4.69: 5→2 (大查询池小反快)
READ_MEMORY_LIMIT = os.environ.get("FQ_READ_MEMORY_LIMIT", DUCKDB_MEMORY_LIMIT)
WRITE_MEMORY_LIMIT = os.environ.get("FQ_WRITE_MEMORY_LIMIT", DUCKDB_MEMORY_LIMIT)

_read_pool: list[duckdb.DuckDBPyConnection] = []
_read_lock = threading.Lock()
_write_lock = threading.Lock()
_WRITE_CONN: duckdb.DuckDBPyConnection | None = None
_cache_lock = threading.Lock()
# Sprint 205+ L4.67: RFM cache 库独立单例, 跟业务库 fingerprint 0 关联
_CACHE_CONN: duckdb.DuckDBPyConnection | None = None
# Sprint 203 R2 Finding 2.2: Semaphore cap (2× pool size) prevents unbounded DuckDB connection
# growth under burst load. Over-cap requests block until a connection is returned.
_read_semaphore: threading.Semaphore = threading.Semaphore(READ_POOL_SIZE * 2)


@dataclass
class RequestConnection:
    """Connection bound to the current request context."""

    conn: duckdb.DuckDBPyConnection
    lock: threading.RLock
    query_type: str


_query_type_var: ContextVar[str] = ContextVar("fq_query_type", default="default")
_request_conn_var: ContextVar[RequestConnection | None] = ContextVar(
    "fq_request_connection",
    default=None,
)


def _db_config(memory_limit: str) -> dict[str, str]:
    cfg = {"memory_limit": memory_limit}
    db_password = os.environ.get("DUCKDB_PASSWORD")
    if db_password:
        cfg["password"] = db_password
    return cfg


def set_query_type(query_type: str) -> Token[str]:
    """Set the current request query type."""

    return _query_type_var.set(query_type)


def reset_query_type(token: Token[str]) -> None:
    """Reset the current request query type."""

    _query_type_var.reset(token)


def get_query_type() -> str:
    """Return the current request query type."""

    return _query_type_var.get()


def _set_request_connection(ctx: RequestConnection | None) -> Token[RequestConnection | None]:
    return _request_conn_var.set(ctx)


def _reset_request_connection(token: Token[RequestConnection | None]) -> None:
    _request_conn_var.reset(token)


def get_request_connection() -> RequestConnection | None:
    """Return the connection bound to this request, if any."""

    return _request_conn_var.get()


def _is_healthy(conn: duckdb.DuckDBPyConnection) -> bool:
    try:
        conn.execute("SELECT 1").fetchone()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("DuckDB pooled read connection failed health check: %s", exc)
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
        return False


def get_read_connection() -> duckdb.DuckDBPyConnection:
    """Borrow a read-only DuckDB connection for dashboard queries."""

    # Sprint 203 R2 Finding 2.2: Semaphore blocks over-cap requests; release in return_read_connection.
    _read_semaphore.acquire()
    try:
        with _read_lock:
            while _read_pool:
                conn = _read_pool.pop()
                if _is_healthy(conn):
                    return conn

        conn = duckdb.connect(
            str(DUCKDB_PATH),
            config=_db_config(READ_MEMORY_LIMIT),
            read_only=True,
        )
        logger.debug("DuckDB read-only connection borrowed: %s", DUCKDB_PATH)
        return conn
    except BaseException:
        _read_semaphore.release()
        raise


def return_read_connection(conn: duckdb.DuckDBPyConnection) -> None:
    """Return a read-only connection to the pool, closing extras."""

    try:
        with _read_lock:
            if len(_read_pool) < READ_POOL_SIZE and _is_healthy(conn):
                _read_pool.append(conn)
                return
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
    finally:
        _read_semaphore.release()


@contextmanager
def read_request_context(query_type: str = "read") -> Iterator[RequestConnection]:
    """Bind a borrowed read-only connection to the current request."""

    conn = get_read_connection()
    ctx = RequestConnection(conn=conn, lock=threading.RLock(), query_type=query_type)
    query_token = set_query_type(query_type)
    conn_token = _set_request_connection(ctx)
    try:
        yield ctx
    finally:
        _reset_request_connection(conn_token)
        reset_query_type(query_token)
        return_read_connection(conn)


def get_write_connection() -> duckdb.DuckDBPyConnection:
    """Return the historical write-capable singleton for non-HTTP jobs."""

    global _WRITE_CONN
    with _write_lock:
        if _WRITE_CONN is not None and _is_healthy(_WRITE_CONN):
            return _WRITE_CONN
        # Sprint 205+ PC2 RFM 500 真根因 (L4.66 永久规则化):
        # 写 conn 强制跟读 conn 用同一份 memory_limit + 显式 read_only=False
        # (让 DuckDB 1.5+ strict mode config dict 各项完全一致, 修复 RFM 雪崩)
        # 注: write 场景的 memory_limit 走 read 场景配置, 这是 DuckDB
        #     1.5+ strict mode 同一文件只能一种 config 的硬约束, 无解
        _WRITE_CONN = duckdb.connect(
            str(DUCKDB_PATH),
            config=_db_config(READ_MEMORY_LIMIT),
            read_only=False,
        )
        logger.info("DuckDB write-capable singleton opened: %s", DUCKDB_PATH)
        return _WRITE_CONN




def get_cache_connection() -> duckdb.DuckDBPyConnection:
    """RFM cache 库独立单例写 conn, 跟业务库 fingerprint 链完全解耦.
    
    L4.67 (Sprint 205+ 真业务触发: PC2 RFM 雪崩根因治本):
    - 业务库 (fuqing_crm.duckdb, 37GB) + middleware read_only conn 池化 (现状不动)
    - cache 库 (rfm_cache.duckdb, 新建独立文件) + 单例 write conn
    - DuckDB 1.5+ strict mode 按 同文件 fingerprint 比对, 跨文件 0 冲突
    - 5 轮串行业务读 + cache 写 0 错, 5 线程并发 0 错 (PC2 端 100% 验证)
    
    注意: 5 线程并发不是"5 个 read_only + 1 个 write", 而是 5 个业务库 read_only 
    + 5 个 cache 库 write (跨库独立 fingerprint, 互不阻塞).
    """
    global _CACHE_CONN
    with _cache_lock:
        if _CACHE_CONN is not None and _is_healthy(_CACHE_CONN):
            return _CACHE_CONN
        from backend.config import CACHE_DUCKDB_PATH
        os.makedirs(os.path.dirname(CACHE_DUCKDB_PATH), exist_ok=True)
        _CACHE_CONN = duckdb.connect(
            CACHE_DUCKDB_PATH,
            config=_db_config(DUCKDB_MEMORY_LIMIT),
            read_only=False,
        )
        logger.info("DuckDB cache singleton opened: %s", CACHE_DUCKDB_PATH)
        return _CACHE_CONN
def close_all_connections() -> None:
    """Close pooled read connections and the write singleton."""

    global _WRITE_CONN
    with _write_lock:
        if _WRITE_CONN is not None:
            try:
                _WRITE_CONN.close()
            except Exception as exc:  # noqa: BLE001
                logger.debug("关闭 DuckDB write 连接时出错: %s", exc)
            _WRITE_CONN = None

    with _read_lock:
        for conn in _read_pool:
            try:
                conn.close()
            except Exception as exc:  # noqa: BLE001
                logger.debug("关闭 DuckDB read 连接时出错: %s", exc)
        _read_pool.clear()
