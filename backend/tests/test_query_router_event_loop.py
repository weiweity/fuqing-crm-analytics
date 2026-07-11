"""Regression coverage for query-pool saturation and request cancellation."""
from __future__ import annotations

import asyncio
from pathlib import Path
import threading

import duckdb
import pytest

from backend.middleware.query_router import QueryRouterMiddleware
from backend.services import dual_conn


def test_async_read_context_keeps_event_loop_responsive(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    returned = threading.Event()
    dummy_conn = object()

    def slow_acquire():
        started.set()
        assert release.wait(timeout=2)
        return dummy_conn

    def fake_return(conn):
        assert conn is dummy_conn
        returned.set()

    monkeypatch.setattr(dual_conn, "get_read_connection", slow_acquire)
    monkeypatch.setattr(dual_conn, "return_read_connection", fake_return)

    async def scenario():
        async def borrow_once():
            async with dual_conn.async_read_request_context():
                return None

        task = asyncio.create_task(borrow_once())
        while not started.is_set():
            await asyncio.sleep(0.001)

        await asyncio.wait_for(asyncio.sleep(0.01), timeout=0.5)
        release.set()
        await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())
    assert returned.is_set()


def test_cancelled_read_app_waits_for_worker_before_connection_can_return():
    worker_started = threading.Event()
    release_worker = threading.Event()
    worker_finished = threading.Event()

    async def slow_app(scope, receive, send):
        def work():
            worker_started.set()
            assert release_worker.wait(timeout=2)
            worker_finished.set()

        await asyncio.to_thread(work)

    middleware = QueryRouterMiddleware(slow_app)

    async def scenario():
        task = asyncio.create_task(middleware._run_read_app({}, None, None))
        while not worker_started.is_set():
            await asyncio.sleep(0.001)
        task.cancel()
        await asyncio.sleep(0.01)
        assert not task.done()
        release_worker.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=1)
        assert worker_finished.is_set()

    asyncio.run(scenario())


def test_cancelled_read_app_preserves_cancellation_when_worker_fails():
    worker_started = threading.Event()
    release_worker = threading.Event()

    async def failing_app(scope, receive, send):
        def work():
            worker_started.set()
            assert release_worker.wait(timeout=2)
            raise RuntimeError("query failed after disconnect")

        await asyncio.to_thread(work)

    middleware = QueryRouterMiddleware(failing_app)

    async def scenario():
        task = asyncio.create_task(middleware._run_read_app({}, None, None))
        while not worker_started.is_set():
            await asyncio.sleep(0.001)
        task.cancel()
        release_worker.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())


def test_cancelled_acquire_preserves_cancelled_error_when_worker_fails(monkeypatch):
    started = threading.Event()
    release = threading.Event()

    def slow_failure():
        started.set()
        assert release.wait(timeout=2)
        raise dual_conn.ReadPoolTimeout("pool saturated")

    monkeypatch.setattr(dual_conn, "get_read_connection", slow_failure)

    async def scenario():
        async def borrow_once():
            async with dual_conn.async_read_request_context():
                return None

        task = asyncio.create_task(borrow_once())
        while not started.is_set():
            await asyncio.sleep(0.001)
        task.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())


def test_pool_health_endpoint_is_control_plane():
    middleware = QueryRouterMiddleware(lambda scope, receive, send: None)
    assert middleware.classify("/api/v1/health/pool", "GET") == "default"


def test_active_read_query_cap_never_exceeds_pool_size():
    limit = dual_conn.ACTIVE_READ_LIMIT
    acquired = 0
    try:
        for _ in range(limit):
            assert dual_conn._read_semaphore.acquire(blocking=False)
            acquired += 1
        assert not dual_conn._read_semaphore.acquire(blocking=False)
    finally:
        for _ in range(acquired):
            dual_conn._read_semaphore.release()


def test_duckdb_runtime_config_caps_threads_without_fingerprint_conflict(tmp_path):
    db_path = tmp_path / "runtime-settings.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        dual_conn._apply_runtime_settings(conn, "1GB")
        sibling = duckdb.connect(str(db_path))
        try:
            assert conn.execute("SELECT current_setting('threads')").fetchone()[0] == dual_conn.DUCKDB_THREADS
            assert sibling.execute("SELECT current_setting('threads')").fetchone()[0] == dual_conn.DUCKDB_THREADS
        finally:
            sibling.close()
    finally:
        conn.close()


def test_rfm_http_child_connection_uses_compatible_runtime_settings(tmp_path, monkeypatch):
    from backend.services.health.rfm_analysis import analysis

    db_path = tmp_path / "rfm-http-child.duckdb"
    seed = duckdb.connect(str(db_path))
    seed.execute("CREATE TABLE marker (value INTEGER)")
    seed.close()

    monkeypatch.setattr(analysis, "DUCKDB_PATH", db_path)
    context_token = dual_conn._set_request_connection(
        dual_conn.RequestConnection(
            conn=object(),  # type: ignore[arg-type]
            lock=threading.RLock(),
            query_type="read",
        )
    )
    try:
        conn = analysis._new_duckdb_conn()
        try:
            assert conn.execute("SELECT COUNT(*) FROM marker").fetchone() == (0,)
            assert conn.execute("SELECT current_setting('threads')").fetchone()[0] == dual_conn.DUCKDB_THREADS
        finally:
            conn.close()
    finally:
        dual_conn._reset_request_connection(context_token)


def test_mac_launch_profile_enables_bounded_single_user_mode():
    source = (Path(__file__).resolve().parents[2] / "scripts" / "uvicorn_launchd.py").read_text()
    assert "load_dotenv" in source
    assert 'os.environ["HEALTH_API_KEY"] =' not in source
    assert 'os.environ["FQ_CRM_PASSWORDS"] =' not in source
    assert "credentials loaded from .env" in source
    assert 'os.environ["DUCKDB_THREADS"] = "4"' in source
    assert 'os.environ["FQ_READ_POOL_SIZE"] = "2"' in source
    assert 'os.environ["FQ_READ_CONCURRENCY_LIMIT"] = "2"' in source
    assert 'os.environ["FQ_READ_MEMORY_LIMIT"] = "3GB"' in source
    assert 'os.environ["FQ_SINGLE_USER_V2"] = "1"' in source
