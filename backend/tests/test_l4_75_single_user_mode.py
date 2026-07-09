"""L4.75 single-user mode regression tests."""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.middleware import single_user_mode as mode


def _request(path: str, token: str = "alice-token", method: str = "GET") -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": [(b"authorization", f"Bearer {token}".encode())],
            "client": ("127.0.0.1", 12345),
            "scheme": "http",
            "server": ("testserver", 80),
        }
    )


async def _ok_call_next(request: Request) -> Response:
    return JSONResponse({"ok": True, "path": request.url.path})


def _run(coro: Awaitable[Response]) -> Response:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def reset_single_user_mode(monkeypatch):
    mode.ACTIVE_USERS.clear()
    monkeypatch.setenv("FQ_SINGLE_USER_LOCK_TIMEOUT_SECONDS", "300")
    monkeypatch.setattr(
        mode,
        "_verify_bearer_token",
        lambda token: {"alice-token": "alice", "bob-token": "bob"}.get(token),
    )
    yield
    mode.ACTIVE_USERS.clear()


def test_first_rfm_user_acquires_lock() -> None:
    response = _run(mode.single_user_mode_middleware(_request(mode.RFM_SINGLE_USER_PATH), _ok_call_next))

    assert response.status_code == 200
    assert response.headers["X-Limited-Mode"] == "single-user"
    assert mode.active_user_count() == 1
    assert "alice" in mode.ACTIVE_USERS


def test_same_user_refreshes_existing_lock() -> None:
    mode.ACTIVE_USERS["alice"] = time.monotonic() - 60
    before = mode.ACTIVE_USERS["alice"]

    response = _run(mode.single_user_mode_middleware(_request(mode.RFM_SINGLE_USER_PATH), _ok_call_next))

    assert response.status_code == 200
    assert mode.ACTIVE_USERS["alice"] > before


def test_second_user_gets_friendly_503_with_headers() -> None:
    mode.ACTIVE_USERS["alice"] = time.monotonic()

    response = _run(
        mode.single_user_mode_middleware(
            _request(mode.RFM_SINGLE_USER_PATH, token="bob-token"),
            _ok_call_next,
        )
    )

    body = json.loads(response.body)
    assert response.status_code == 503
    assert response.headers["Retry-After"].isdigit()
    assert response.headers["X-Limited-Mode"] == "single-user"
    assert response.headers["X-Lock-Timeout-Seconds"] == "300"
    assert body["limited_mode"] == "single-user"
    assert body["active_user_count"] == 1
    assert "bob" not in mode.ACTIVE_USERS


def test_expired_lock_is_evicted_and_new_user_can_enter(monkeypatch) -> None:
    monkeypatch.setenv("FQ_SINGLE_USER_LOCK_TIMEOUT_SECONDS", "5")
    mode.ACTIVE_USERS["alice"] = time.monotonic() - 6

    response = _run(
        mode.single_user_mode_middleware(
            _request(mode.RFM_SINGLE_USER_PATH, token="bob-token"),
            _ok_call_next,
        )
    )

    assert response.status_code == 200
    assert "alice" not in mode.ACTIVE_USERS
    assert "bob" in mode.ACTIVE_USERS


def test_non_rfm_endpoint_bypasses_lock() -> None:
    response = _run(mode.single_user_mode_middleware(_request("/api/v1/auth/me"), _ok_call_next))

    assert response.status_code == 200
    assert mode.ACTIVE_USERS == {}


def test_release_user_lock_is_idempotent() -> None:
    mode.ACTIVE_USERS["alice"] = time.monotonic()

    assert mode.release_user_lock("alice") is True
    assert mode.release_user_lock("alice") is False
    assert mode.ACTIVE_USERS == {}
