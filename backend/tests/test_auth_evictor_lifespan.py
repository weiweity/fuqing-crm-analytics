"""Auth evictor lifespan regression tests that do not require production DuckDB."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import main as main_module
from backend.db import connection as connection_module
from backend.db import memory_monitor as memory_monitor_module
from backend.services import auth_token_evictor as evictor_module
from backend.services.rfm import cache as cache_module


class _FakeRfmQueryCache:
    def ensure_table(self) -> None:
        return None


async def _wait_for_stop(stop_event) -> None:
    await stop_event.wait()


def test_concurrent_lifespans_await_their_own_evictor_task() -> None:
    """Concurrent TestClient lifespans must not await a task from another loop."""
    rendezvous = threading.Barrier(2)
    isolated_app = FastAPI(lifespan=main_module.lifespan)

    with (
        patch.object(main_module, "validate_startup_db", lambda: None),
        patch.object(
            memory_monitor_module,
            "start_memory_watchdog",
            lambda **_kwargs: None,
        ),
        patch.object(memory_monitor_module, "check_memory", lambda **_kwargs: None),
        patch.object(memory_monitor_module, "stop_memory_watchdog", lambda: None),
        patch.object(connection_module, "close_connection", lambda: None),
        patch.object(cache_module, "RfmQueryCache", _FakeRfmQueryCache),
        patch.object(cache_module, "check_manifest_version_and_invalidate", lambda: None),
        patch.object(evictor_module, "evict_idle_tokens_periodically", _wait_for_stop),
    ):
        def open_and_close_client(_: int) -> str:
            with TestClient(isolated_app):
                rendezvous.wait(timeout=3)
            return "closed"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = sorted(executor.map(open_and_close_client, range(2)))

    assert results == ["closed", "closed"]
