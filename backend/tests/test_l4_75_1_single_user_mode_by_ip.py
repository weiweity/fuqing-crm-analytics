"""L4.75.1 单人模式按 IP 限制 回归 test (跟 L4.42 + L4.50 + L4.75 1:1 stable 永久规则链配套)."""
import asyncio
import time

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse

from backend.middleware.single_user_mode import (
    ACTIVE_USERS, single_user_mode_middleware, release_user_lock,
    extract_user_id_from_request, RFM_SINGLE_USER_PATH,
)


def _make_request(path: str, client_ip: str, token: str | None = None) -> Request:
    """Build a minimal Request for the guard tests."""
    headers: list[tuple[bytes, bytes]] = []
    if token:
        headers.append((b"authorization", f"Bearer {token}".encode()))
    scope = {
        "type": "http",
        "path": path,
        "method": "GET",
        "headers": headers,
        "client": (client_ip, 12345),
    }
    return Request(scope)


def _ok_call_next(req):
    async def _call():
        return JSONResponse({"status": "ok"})
    return _call


def _make_ok_call_next():
    """L4.75.1 helper: middleware 期望 callable 返回 awaitable. 返回 async function."""
    async def _call_next(req):
        return JSONResponse({"status": "ok"})
    return _call_next


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


@pytest.fixture(autouse=True)
def _clear_active_users(monkeypatch):
    """每个 test 前后清空 ACTIVE_USERS (跟 L4.75 single-user middleware 1:1 stable 永久规则链配套)."""
    monkeypatch.setenv("FQ_SINGLE_USER_V2", "0")
    ACTIVE_USERS.clear()
    yield
    ACTIVE_USERS.clear()


def test_l4_75_1_extract_priority_ip_first():
    """L4.75.1 IP 优先 (跟 L4.75 1:1 stable 沿用, 兼容共享账号)."""
    request = _make_request("/api/v1/customer-health/rfm-analysis", client_ip="10.0.0.1", token="admin")
    user_id = extract_user_id_from_request(request)
    assert user_id == "ip:10.0.0.1"


def test_l4_75_1_release_user_lock_works_with_ip_prefix():
    """L4.75.1 release_user_lock 接受 ip: 前缀 (跟 L4.40 fail-open 1:1 stable 永久规则链配套)."""
    ACTIVE_USERS.clear()
    ACTIVE_USERS["ip:10.0.0.1"] = time.monotonic()
    released = release_user_lock("ip:10.0.0.1")
    assert released is True
    assert "ip:10.0.0.1" not in ACTIVE_USERS
    released = release_user_lock("ip:10.0.0.1")
    assert released is False


def test_l4_75_1_same_ip_different_user_share_lock():
    """L4.75.1 同一 IP 不同账号共享锁 (跟共享账号兼容 1:1 stable 永久规则链配套)."""
    ACTIVE_USERS.clear()
    req_admin = _make_request(RFM_SINGLE_USER_PATH, client_ip="10.0.0.1", token="admin-token-1")
    req_fqsw = _make_request(RFM_SINGLE_USER_PATH, client_ip="10.0.0.1", token="fqsw-token-2")
    resp1 = _run(single_user_mode_middleware(req_admin, _make_ok_call_next()))
    resp2 = _run(single_user_mode_middleware(req_fqsw, _make_ok_call_next()))
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert "ip:10.0.0.1" in ACTIVE_USERS


def test_l4_75_1_different_ip_independent_locks():
    """L4.75.1 不同 IP 各自拿锁 (跟 L4.75 + L4.51 1:1 stable 永久规则链配套)."""
    ACTIVE_USERS.clear()
    req1 = _make_request(RFM_SINGLE_USER_PATH, client_ip="10.0.0.1", token="t1")
    req2 = _make_request(RFM_SINGLE_USER_PATH, client_ip="10.0.0.2", token="t2")
    req3 = _make_request(RFM_SINGLE_USER_PATH, client_ip="10.0.0.3", token="t3")
    resp1 = _run(single_user_mode_middleware(req1, _make_ok_call_next()))
    resp2 = _run(single_user_mode_middleware(req2, _make_ok_call_next()))
    resp3 = _run(single_user_mode_middleware(req3, _make_ok_call_next()))
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp3.status_code == 200
    assert len(ACTIVE_USERS) == 3
    assert "ip:10.0.0.1" in ACTIVE_USERS
    assert "ip:10.0.0.2" in ACTIVE_USERS
    assert "ip:10.0.0.3" in ACTIVE_USERS
