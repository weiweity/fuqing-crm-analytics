"""Resource defaults and connection ownership; only isolated temporary databases."""
from __future__ import annotations

import importlib
from pathlib import Path
import threading
from types import SimpleNamespace

import duckdb
import pytest

from backend import config
from backend import resource_budget as budget
from backend.services import dual_conn


def test_default_memory_has_one_source(monkeypatch):
    with monkeypatch.context() as patch:
        patch.delenv("DUCKDB_MEMORY_LIMIT", raising=False)
        patch.delenv("DUCKDB_MEMORY_LIMIT_OVERRIDE", raising=False)
        importlib.reload(config)
        try:
            assert config.get_duckdb_memory_limit() == config.DUCKDB_MEMORY_LIMIT
        finally:
            patch.undo()
            importlib.reload(config)


def test_cache_has_its_own_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DUCKDB_PATH", tmp_path / "cache.duckdb")
    monkeypatch.setattr(dual_conn, "_CACHE_CONN", None)
    monkeypatch.setattr(dual_conn, "CACHE_MEMORY_LIMIT", "192MB", raising=False)
    seen = []
    original = dual_conn._apply_runtime_settings

    def apply(conn, memory_limit):
        seen.append(memory_limit)
        return original(conn, memory_limit)

    monkeypatch.setattr(dual_conn, "_apply_runtime_settings", apply)
    try:
        conn = dual_conn.get_cache_connection()
        assert conn.execute("SELECT 42").fetchone() == (42,)
        assert seen == ["192MB"]
    finally:
        if dual_conn._CACHE_CONN is not None:
            dual_conn._CACHE_CONN.close()
            dual_conn._CACHE_CONN = None


@pytest.mark.parametrize("override", ["4GB", " 4GB "])
def test_explicit_offline_memory_override_is_preserved(monkeypatch, override):
    monkeypatch.setenv("DUCKDB_MEMORY_LIMIT", "2GB")
    monkeypatch.setenv("DUCKDB_MEMORY_LIMIT_OVERRIDE", override)
    assert config.get_duckdb_memory_limit() == "4GB"


@pytest.mark.parametrize(("ram_gib", "expected"), [
    (1, "512MiB"), (8, "4096MiB"), (16, "8192MiB"), (64, "8192MiB"),
])
def test_default_budget_leaves_headroom(ram_gib, expected):
    assert budget.default_memory_limit(ram_gib * budget.GIB) == expected


@pytest.mark.parametrize(("cpus", "expected"), [(1, 1), (2, 1), (8, 4), (10, 4), (64, 4)])
def test_default_threads_are_bounded(cpus, expected):
    assert budget.default_threads(cpus) == expected


def test_cache_default_is_small():
    assert budget.default_cache_memory_limit(16 * budget.GIB) == "256MiB"
    assert budget.default_cache_memory_limit(budget.GIB) == "32MiB"


def test_cgroup_memory_is_not_confused_with_host_ram(monkeypatch):
    monkeypatch.setattr(budget.sys, "platform", "linux")
    monkeypatch.setattr(budget.psutil, "virtual_memory", lambda: SimpleNamespace(total=64 * budget.GIB))
    monkeypatch.setattr(Path, "read_text", lambda self, **kwargs: (
        str(2 * budget.GIB) if self.name == "memory.max" else str(2 ** 63 - 4096)
    ))
    assert budget.effective_memory_bytes() == 2 * budget.GIB


def test_unlimited_cgroup_uses_host_ram(monkeypatch):
    monkeypatch.setattr(budget.sys, "platform", "linux")
    monkeypatch.setattr(budget.psutil, "virtual_memory", lambda: SimpleNamespace(total=8 * budget.GIB))
    monkeypatch.setattr(Path, "read_text", lambda self, **kwargs: "max")
    assert budget.effective_memory_bytes() == 8 * budget.GIB


def test_unknown_host_falls_back_conservatively(monkeypatch):
    monkeypatch.setattr(budget.sys, "platform", "darwin")

    def unavailable():
        raise OSError("synthetic unavailable host")

    monkeypatch.setattr(budget.psutil, "virtual_memory", unavailable)
    assert budget.default_memory_limit() == "2048MiB"


def test_cache_settings_do_not_change_business_database(tmp_path, monkeypatch):
    business_path = tmp_path / "business.duckdb"
    with duckdb.connect(str(business_path)) as seed:
        seed.execute("CREATE TABLE marker (value INTEGER)")
    monkeypatch.setattr(config, "CACHE_DUCKDB_PATH", tmp_path / "cache.duckdb")
    monkeypatch.setattr(dual_conn, "_CACHE_CONN", None)
    monkeypatch.setattr(dual_conn, "CACHE_MEMORY_LIMIT", "64MB")
    with duckdb.connect(str(business_path), read_only=True) as business:
        dual_conn._apply_runtime_settings(business, "128MB")
        before = business.execute("SELECT current_setting('memory_limit')").fetchone()
        try:
            cache = dual_conn.get_cache_connection()
            assert business.execute("SELECT current_setting('memory_limit')").fetchone() == before
            assert cache.execute("SELECT current_setting('memory_limit')").fetchone() != before
        finally:
            if dual_conn._CACHE_CONN is not None:
                dual_conn._CACHE_CONN.close()
                dual_conn._CACHE_CONN = None


def test_five_callers_share_two_native_read_slots(tmp_path, monkeypatch):
    """Real temporary DuckDB connections; this tests scheduling, not heavy-query SLA."""
    database = tmp_path / "pool.duckdb"
    with duckdb.connect(str(database)) as seed:
        seed.execute("CREATE TABLE marker AS SELECT 42 AS value")
    monkeypatch.setattr(dual_conn, "DUCKDB_PATH", database)
    monkeypatch.setattr(dual_conn, "READ_MEMORY_LIMIT", "64MB")
    monkeypatch.setattr(dual_conn, "DUCKDB_THREADS", 2)
    monkeypatch.setattr(dual_conn, "READ_POOL_SIZE", 2)
    monkeypatch.setattr(dual_conn, "ACTIVE_READ_LIMIT", 2)
    monkeypatch.setattr(dual_conn, "_read_pool", [])
    monkeypatch.setattr(dual_conn, "_read_semaphore", threading.BoundedSemaphore(2))
    start = threading.Barrier(6)
    two_active = threading.Event()
    release = threading.Event()
    state_lock = threading.Lock()
    active = peak = 0
    values, errors = [], []

    def caller():
        nonlocal active, peak
        conn = None
        counted = False
        try:
            start.wait(timeout=5)
            conn = dual_conn.get_read_connection(timeout=5)
            with state_lock:
                active += 1
                counted = True
                peak = max(peak, active)
                if active == 2:
                    two_active.set()
            assert release.wait(timeout=5)
            value = conn.execute("SELECT value FROM marker").fetchone()[0]
            with state_lock:
                values.append(value)
        except BaseException as exc:
            with state_lock:
                errors.append(exc)
        finally:
            if counted:
                with state_lock:
                    active -= 1
            if conn is not None:
                dual_conn.return_read_connection(conn)

    threads = [threading.Thread(target=caller) for _ in range(5)]
    for thread in threads:
        thread.start()
    try:
        start.wait(timeout=5)
        assert two_active.wait(timeout=5)
        with pytest.raises(dual_conn.ReadPoolTimeout):
            dual_conn.get_read_connection(timeout=0.01)
    finally:
        release.set()
        for thread in threads:
            thread.join(timeout=6)
        for conn in dual_conn._read_pool:
            conn.close()
        dual_conn._read_pool.clear()
    assert not any(thread.is_alive() for thread in threads)
    assert errors == []
    assert values == [42] * 5
    assert peak == 2
    assert dual_conn._read_semaphore.acquire(blocking=False)
    assert dual_conn._read_semaphore.acquire(blocking=False)
    assert not dual_conn._read_semaphore.acquire(blocking=False)
    dual_conn._read_semaphore.release()
    dual_conn._read_semaphore.release()
