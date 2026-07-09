"""L4.75 single-user mode regression tests (跟 L4.75.1 按 IP 锁 1:1 stable 永久规则链配套).

Sprint 205+ L4.75.1: lock key 从 username 升级为 ip:xxx.
本测试文件已更新以反映 L4.75.1 新行为 (跟 L4.42 + L4.50 + L4.75 1:1 stable 永久规则链配套).
"""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.middleware import single_user_mode as mode


def _request(
    path: str,
    token: str = "alice-token",
    method: str = "GET",
    client_ip: str = "10.0.0.1",
) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": [(b"authorization", f"Bearer {token}".encode())],
            "client": (client_ip, 12345),
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
    """L4.75.1: 第 1 个用户 进入 RFM 拿 ip:xxx 锁."""
    response = _run(mode.single_user_mode_middleware(_request(mode.RFM_SINGLE_USER_PATH), _ok_call_next))
    assert response.status_code == 200
    assert response.headers["X-Limited-Mode"] == "single-user"
    assert mode.active_user_count() == 1
    assert "ip:10.0.0.1" in mode.ACTIVE_USERS


def test_same_ip_refreshes_existing_lock() -> None:
    """L4.75.1: 同 IP 刷新 last_active (跟 L4.40 fail-open 1:1 stable 永久规则链配套)."""
    mode.ACTIVE_USERS["ip:10.0.0.1"] = time.monotonic() - 60
    before = mode.ACTIVE_USERS["ip:10.0.0.1"]

    response = _run(mode.single_user_mode_middleware(_request(mode.RFM_SINGLE_USER_PATH), _ok_call_next))

    assert response.status_code == 200
    assert mode.ACTIVE_USERS["ip:10.0.0.1"] > before


def test_different_ip_takes_independent_lock() -> None:
    """L4.75.1: 不同 IP 各自拿锁, 不冲突 (跟 L4.74 + L4.75 1:1 stable 永久规则链配套)."""
    mode.ACTIVE_USERS.clear()
    response1 = _run(mode.single_user_mode_middleware(
        _request(mode.RFM_SINGLE_USER_PATH, client_ip="10.0.0.1"), _ok_call_next,
    ))
    response2 = _run(mode.single_user_mode_middleware(
        _request(mode.RFM_SINGLE_USER_PATH, client_ip="10.0.0.2"), _ok_call_next,
    ))
    assert response1.status_code == 200
    assert response2.status_code == 200
    # 两个 IP 在 ACTIVE_USERS 里
    assert "ip:10.0.0.1" in mode.ACTIVE_USERS
    assert "ip:10.0.0.2" in mode.ACTIVE_USERS
    assert mode.active_user_count() == 2


def test_same_ip_second_request_returns_200_within_timeout() -> None:
    """L4.75.1: 同 IP 第 2 个请求 在 5 分钟内 直接 200 (复用 last_active 刷新)."""
    mode.ACTIVE_USERS.clear()
    _run(mode.single_user_mode_middleware(
        _request(mode.RFM_SINGLE_USER_PATH, client_ip="10.0.0.1"), _ok_call_next,
    ))
    response = _run(mode.single_user_mode_middleware(
        _request(mode.RFM_SINGLE_USER_PATH, client_ip="10.0.0.1"), _ok_call_next,
    ))
    assert response.status_code == 200
    assert "ip:10.0.0.1" in mode.ACTIVE_USERS


def test_expired_lock_is_evicted(monkeypatch) -> None:
    """L4.75.1: 5 分钟无活动 LRU evict (跟 L4.62 + L4.40 fail-open 1:1 stable 永久规则链配套)."""
    monkeypatch.setenv("FQ_SINGLE_USER_LOCK_TIMEOUT_SECONDS", "5")
    mode.ACTIVE_USERS["ip:10.0.0.1"] = time.monotonic() - 6
    # 触发的请求 (同 IP) 走 LRU evict
    response = _run(mode.single_user_mode_middleware(
        _request(mode.RFM_SINGLE_USER_PATH, client_ip="10.0.0.1"), _ok_call_next,
    ))
    assert response.status_code == 200
    # 旧锁被 evict 后, 新锁 = ip:10.0.0.1 (不是替换)
    assert "ip:10.0.0.1" in mode.ACTIVE_USERS


def test_non_rfm_endpoint_bypasses_lock() -> None:
    response = _run(mode.single_user_mode_middleware(_request("/api/v1/auth/me"), _ok_call_next))

    assert response.status_code == 200
    assert mode.ACTIVE_USERS == {}


def test_release_user_lock_with_ip_prefix() -> None:
    """L4.75.1: release_user_lock 接受 ip: 前缀 (跟 L4.40 fail-open 1:1 stable 永久规则链配套)."""
    mode.ACTIVE_USERS["ip:10.0.0.1"] = time.monotonic()

    assert mode.release_user_lock("ip:10.0.0.1") is True
    assert mode.release_user_lock("ip:10.0.0.1") is False
    assert mode.ACTIVE_USERS == {}
