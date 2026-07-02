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

READ_POOL_SIZE = int(os.environ.get("FQ_READ_POOL_SIZE", "5"))
READ_MEMORY_LIMIT = os.environ.get("FQ_READ_MEMORY_LIMIT", DUCKDB_MEMORY_LIMIT)
WRITE_MEMORY_LIMIT = os.environ.get("FQ_WRITE_MEMORY_LIMIT", DUCKDB_MEMORY_LIMIT)

_read_pool: list[duckdb.DuckDBPyConnection] = []
_read_lock = threading.Lock()
_write_lock = threading.Lock()
_WRITE_CONN: duckdb.DuckDBPyConnection | None = None


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


def return_read_connection(conn: duckdb.DuckDBPyConnection) -> None:
    """Return a read-only connection to the pool, closing extras."""

    with _read_lock:
        if len(_read_pool) < READ_POOL_SIZE and _is_healthy(conn):
            _read_pool.append(conn)
            return
    try:
        conn.close()
    except Exception:  # noqa: BLE001
        pass


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
        _WRITE_CONN = duckdb.connect(
            str(DUCKDB_PATH),
            config=_db_config(WRITE_MEMORY_LIMIT),
        )
        logger.info("DuckDB write-capable singleton opened: %s", DUCKDB_PATH)
        return _WRITE_CONN


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
