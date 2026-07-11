"""Read/write connection routing for Sprint 201 R1.

HTTP dashboard requests borrow short-lived read-only DuckDB connections from a
small pool. Non-HTTP code keeps the historical write-capable singleton path in
``backend.db.connection`` so ETL and maintenance scripts remain compatible.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
import logging
import os
import threading
from typing import AsyncIterator, Iterator

import duckdb

from backend.config import DUCKDB_MEMORY_LIMIT, DUCKDB_PATH, DUCKDB_THREADS

logger = logging.getLogger(__name__)

READ_POOL_SIZE = max(1, int(os.environ.get("FQ_READ_POOL_SIZE", "2")))  # L4.69: 5→2
READ_CONCURRENCY_LIMIT = max(
    1,
    int(os.environ.get("FQ_READ_CONCURRENCY_LIMIT", str(READ_POOL_SIZE))),
)
ACTIVE_READ_LIMIT = min(READ_POOL_SIZE, READ_CONCURRENCY_LIMIT)
READ_MEMORY_LIMIT = os.environ.get("FQ_READ_MEMORY_LIMIT", DUCKDB_MEMORY_LIMIT)
WRITE_MEMORY_LIMIT = os.environ.get("FQ_WRITE_MEMORY_LIMIT", DUCKDB_MEMORY_LIMIT)

_read_pool: list[duckdb.DuckDBPyConnection] = []
_read_lock = threading.Lock()
_write_lock = threading.Lock()
_WRITE_CONN: duckdb.DuckDBPyConnection | None = None
_cache_lock = threading.Lock()
# Sprint 205+ L4.67: RFM cache 库独立单例, 跟业务库 fingerprint 0 关联
_CACHE_CONN: duckdb.DuckDBPyConnection | None = None
# L4.85.4: active query cap must not exceed the configured pool.  The previous
# 2× multiplier admitted four heavy queries on a 16GB Mac and amplified memory
# pressure under repeated requests. The active-query cap now matches the pool.
_read_semaphore: threading.BoundedSemaphore = threading.BoundedSemaphore(
    ACTIVE_READ_LIMIT
)


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


def _db_config() -> dict[str, str]:
    """Return settings that must be supplied while opening the database."""
    cfg: dict[str, str] = {}
    db_password = os.environ.get("DUCKDB_PASSWORD")
    if db_password:
        cfg["password"] = db_password
    return cfg


def _apply_runtime_settings(
    conn: duckdb.DuckDBPyConnection,
    memory_limit: str,
) -> duckdb.DuckDBPyConnection:
    """Apply shared resource caps without changing DuckDB's file fingerprint.

    Passing ``memory_limit`` or ``threads`` via ``connect(config=...)`` makes a
    later plain connection to the same file fail with "different
    configuration". Runtime settings are inherited by sibling connections and
    keep legacy direct readers compatible with the bounded pool.
    """
    conn.execute("SET memory_limit = ?", [memory_limit])
    conn.execute("SET threads = ?", [DUCKDB_THREADS])
    return conn


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


class ReadPoolTimeout(Exception):
    """Read concurrency stayed saturated until the bounded wait expired."""
    pass


def get_read_connection(timeout: float = 5.0) -> duckdb.DuckDBPyConnection:
    """Borrow a read-only DuckDB connection for dashboard queries.

    Pool saturation waits at most five seconds, then degrades to HTTP 503.
    跟 L4.69 RFM 雪崩真治本 (ThreadPoolExecutor 串行) 1:1 stable 配套, 跟 L4.51
    Read-Write Splitting (read_only 池) 1:1 stable 永久规则链配套.
    """
    acquired = _read_semaphore.acquire(timeout=timeout)
    if not acquired:
        raise ReadPoolTimeout(
            f"DuckDB read concurrency limit {ACTIVE_READ_LIMIT} stayed full "
            f"for {timeout}s; retry after the active query finishes."
        )
    try:
        with _read_lock:
            while _read_pool:
                conn = _read_pool.pop()
                if _is_healthy(conn):
                    return conn

        conn = duckdb.connect(
            str(DUCKDB_PATH),
            config=_db_config(),
            read_only=True,
        )
        _apply_runtime_settings(conn, READ_MEMORY_LIMIT)
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


@asynccontextmanager
async def async_read_request_context(
    query_type: str = "read",
) -> AsyncIterator[RequestConnection]:
    """Borrow/return a read connection without blocking the ASGI event loop.

    ``threading.Semaphore.acquire(timeout=5)`` and ``duckdb.connect`` are both
    blocking calls. Running them directly inside async middleware freezes every
    route (including auth and health) when the pool is saturated.
    """

    acquire_task = asyncio.create_task(asyncio.to_thread(get_read_connection))
    try:
        conn = await asyncio.shield(acquire_task)
    except asyncio.CancelledError as cancelled:
        # A cancelled waiter must not leak a connection acquired by the worker
        # after the coroutine has gone away. Acquisition failures are cleanup
        # details and must not replace the caller's cancellation.
        conn = None
        try:
            conn = await acquire_task
        except BaseException as exc:  # noqa: BLE001
            logger.debug("DuckDB acquire finished with error after cancellation: %s", exc)
        if conn is not None:
            return_task = asyncio.create_task(asyncio.to_thread(return_read_connection, conn))
            try:
                await asyncio.shield(return_task)
            except asyncio.CancelledError:
                await return_task
            except BaseException as exc:  # noqa: BLE001
                logger.debug("DuckDB return failed during cancellation cleanup: %s", exc)
        raise cancelled

    ctx = RequestConnection(conn=conn, lock=threading.RLock(), query_type=query_type)
    query_token = set_query_type(query_type)
    conn_token = _set_request_connection(ctx)
    try:
        yield ctx
    finally:
        _reset_request_connection(conn_token)
        reset_query_type(query_token)
        return_task = asyncio.create_task(asyncio.to_thread(return_read_connection, conn))
        try:
            await asyncio.shield(return_task)
        except asyncio.CancelledError:
            await return_task
            raise


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
        _WRITE_CONN = _apply_runtime_settings(
            duckdb.connect(
                str(DUCKDB_PATH),
                config=_db_config(),
                read_only=False,
            ),
            READ_MEMORY_LIMIT,
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
        _CACHE_CONN = _apply_runtime_settings(
            duckdb.connect(
                CACHE_DUCKDB_PATH,
                config=_db_config(),
                read_only=False,
            ),
            DUCKDB_MEMORY_LIMIT,
        )
        logger.info("DuckDB cache singleton opened: %s", CACHE_DUCKDB_PATH)
        return _CACHE_CONN


def close_all_connections() -> None:
    """Close pooled read connections plus both write singletons."""

    global _CACHE_CONN, _WRITE_CONN
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

    with _cache_lock:
        if _CACHE_CONN is not None:
            try:
                _CACHE_CONN.close()
            except Exception as exc:  # noqa: BLE001
                logger.debug("关闭 DuckDB cache 连接时出错: %s", exc)
            _CACHE_CONN = None
