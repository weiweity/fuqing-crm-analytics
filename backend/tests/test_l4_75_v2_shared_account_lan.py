"""L4.75 v2 shared-account LAN queue regression tests."""
from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Awaitable

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.middleware import single_user_mode as mode
from backend.routers import session as session_router


def _request(
    path: str = mode.RFM_SINGLE_USER_PATH,
    *,
    client_ip: str = "10.0.0.1",
    method: str = "GET",
    session_id: str | None = None,
) -> Request:
    headers: list[tuple[bytes, bytes]] = [(b"authorization", b"Bearer test-token")]
    if session_id:
        headers.append((b"x-session-id", session_id.encode()))
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": headers,
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
def reset_v2_state(monkeypatch: pytest.MonkeyPatch):
    mode.ACTIVE_USERS.clear()
    mode._reset_v2_state()
    monkeypatch.setenv("FQ_SINGLE_USER_V2", "1")
    monkeypatch.setenv("FQ_SINGLE_USER_LOCK_TIMEOUT_SECONDS", "300")
    yield
    mode.ACTIVE_USERS.clear()
    mode._reset_v2_state()


def test_l4_75_v2_ip_basic_acquire_release() -> None:
    acquired = mode.acquire_or_queue("10.0.0.1", now=10)
    assert acquired["status"] == "active"
    assert acquired["ip"] == "10.0.0.1"

    released = mode.release_v2("10.0.0.1", now=20)
    assert released == {
        "released": True,
        "user_id": "ip:10.0.0.1",
        "promoted_ip": None,
        "promoted_queue_position": None,
        "release_pending": False,
    }
    assert mode.get_session_status("10.0.0.1", now=20)["status"] == "none"
    assert mode.acquire_or_queue("10.0.0.1", now=21)["status"] == "active"


def test_l4_75_v2_ip_queue_2nd_ip() -> None:
    first = mode.acquire_or_queue("10.0.0.1", now=10)
    second = mode.acquire_or_queue("10.0.0.2", now=11)

    assert first["status"] == "active"
    assert second["status"] == "queued"
    assert second["position"] == 1
    assert second["queue_length"] == 1
    assert second["current_ip"] == "10.0.0.1"
    assert second["estimated_wait_seconds"] == 299


def test_l4_75_v2_5min_idle_auto_release() -> None:
    mode.acquire_or_queue("10.0.0.1", now=0)
    mode.acquire_or_queue("10.0.0.2", now=10)

    promoted = mode.get_session_status("10.0.0.2", now=300)

    assert promoted["status"] == "active"
    assert "10.0.0.1" not in mode.ACTIVE_SESSIONS
    assert list(mode.QUEUE) == []


def test_l4_75_v2_heartbeat_reset_idle() -> None:
    mode.acquire_or_queue("10.0.0.1", now=0)

    heartbeat = mode.heartbeat_session("10.0.0.1", now=250)
    still_active = mode.get_session_status("10.0.0.1", now=549)
    expired = mode.get_session_status("10.0.0.1", now=550)

    assert heartbeat["status"] == "active"
    assert still_active["status"] == "active"
    assert expired["status"] == "none"


def test_l4_75_v2_same_ip_multi_session_ok() -> None:
    first_id = "11111111-1111-4111-8111-111111111111"
    second_id = "22222222-2222-4222-8222-222222222222"

    first = mode.acquire_or_queue("10.0.0.1", first_id, now=10)
    second = mode.acquire_or_queue("10.0.0.1", second_id, now=20)

    assert first["status"] == second["status"] == "active"
    assert first["session_id"] == second["session_id"] == first_id
    assert len(mode.ACTIVE_SESSIONS) == 1
    assert len(mode.QUEUE) == 0


def test_l4_75_v2_queue_promotion_on_idle() -> None:
    mode.acquire_or_queue("10.0.0.1", now=0)
    mode.acquire_or_queue("10.0.0.2", now=10)
    mode.acquire_or_queue("10.0.0.3", now=20)

    second = mode.get_session_status("10.0.0.2", now=300)
    third = mode.get_session_status("10.0.0.3", now=300)

    assert second["status"] == "active"
    assert third["status"] == "queued"
    assert third["position"] == 1
    assert third["current_ip"] == "10.0.0.2"


@pytest.mark.parametrize(
    ("client_ip", "allowed"),
    [
        ("10.42.0.9", True),
        ("172.16.0.1", True),
        ("172.31.255.254", True),
        ("192.168.10.8", True),
        ("127.0.0.1", True),
        ("::1", True),
        ("fd00::1", True),
        ("8.8.8.8", False),
        ("172.32.0.1", False),
        ("169.254.1.1", False),
        ("192.0.2.1", False),
        ("not-an-ip", False),
    ],
)
def test_l4_75_v2_lan_subnet_filter(client_ip: str, allowed: bool) -> None:
    assert mode.is_lan_ip(client_ip) is allowed


def test_l4_75_v2_no_uvicorn_impact() -> None:
    mode.acquire_or_queue("10.0.0.1")
    queued_call_next_ran = False

    async def queued_call_next(request: Request) -> Response:
        nonlocal queued_call_next_ran
        queued_call_next_ran = True
        return await _ok_call_next(request)

    async def scenario() -> tuple[Response, Response]:
        queued = await asyncio.wait_for(
            mode.single_user_mode_middleware(
                _request(client_ip="10.0.0.2"),
                queued_call_next,
            ),
            timeout=0.5,
        )
        health = await asyncio.wait_for(
            mode.single_user_mode_middleware(
                _request("/api/v1/health", client_ip="10.0.0.2"),
                _ok_call_next,
            ),
            timeout=0.5,
        )
        return queued, health

    queued_response, health_response = asyncio.run(scenario())
    assert queued_response.status_code == 503
    assert queued_response.headers["X-Limited-Mode"] == "single-user-queued"
    assert queued_call_next_ran is False
    assert health_response.status_code == 200


def test_l4_75_v2_v1_compat_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FQ_SINGLE_USER_V2", "0")

    first = _run(mode.single_user_mode_middleware(_request(client_ip="10.0.0.1"), _ok_call_next))
    second = _run(mode.single_user_mode_middleware(_request(client_ip="10.0.0.2"), _ok_call_next))

    assert first.status_code == second.status_code == 200
    assert mode.ACTIVE_USERS.keys() == {"ip:10.0.0.1", "ip:10.0.0.2"}
    assert mode.ACTIVE_SESSIONS == {}
    assert list(mode.QUEUE) == []


def test_l4_75_v2_session_id_uniqueness() -> None:
    first = mode.acquire_or_queue("10.0.0.1", now=10)
    second = mode.acquire_or_queue("10.0.0.2", now=20)
    first_id = str(first["session_id"])
    second_id = str(second["session_id"])

    assert uuid.UUID(first_id)
    assert uuid.UUID(second_id)
    assert first_id != second_id

    mode.release_v2("10.0.0.1", now=30)
    promoted = mode.get_session_status("10.0.0.2", now=30)
    assert promoted["status"] == "active"
    assert promoted["session_id"] == second_id


def test_l4_75_v2_status_does_not_acquire() -> None:
    status = mode.get_session_status("10.0.0.9", now=10)

    assert status["status"] == "none"
    assert mode.ACTIVE_SESSIONS == {}
    assert list(mode.QUEUE) == []


def test_l4_75_v2_stale_queue_entry_is_evicted() -> None:
    mode.acquire_or_queue("10.0.0.1", now=0)
    mode.acquire_or_queue("10.0.0.2", now=1)
    mode.heartbeat_session("10.0.0.1", now=250)

    stale = mode.get_session_status("10.0.0.2", now=301)

    assert stale["status"] == "none"
    assert mode.get_session_status("10.0.0.1", now=301)["status"] == "active"


def test_l4_75_v2_non_lan_rfm_is_rejected() -> None:
    call_next_ran = False

    async def call_next(request: Request) -> Response:
        nonlocal call_next_ran
        call_next_ran = True
        return await _ok_call_next(request)

    response = _run(
        mode.single_user_mode_middleware(
            _request(client_ip="8.8.8.8"),
            call_next,
        )
    )
    body = json.loads(response.body)

    assert response.status_code == 403
    assert response.headers["X-Limited-Mode"] == "single-user-lan-denied"
    assert body["limited_mode"] == "single-user-lan-denied"
    assert call_next_ran is False


def test_l4_75_v2_release_queued_ip_keeps_active_ip() -> None:
    mode.acquire_or_queue("10.0.0.1", now=10)
    mode.acquire_or_queue("10.0.0.2", now=20)

    result = mode.release_v2("10.0.0.2", now=30)

    assert result["released"] is True
    assert result["promoted_ip"] is None
    assert mode.get_session_status("10.0.0.1", now=30)["status"] == "active"
    assert mode.get_session_status("10.0.0.2", now=30)["status"] == "none"


def test_l4_75_v2_session_router_status_and_heartbeat() -> None:
    mode.acquire_or_queue("10.0.0.1")
    request = _request("/api/v1/session/status", client_ip="10.0.0.1")

    status = asyncio.run(session_router.session_status(request))
    heartbeat = asyncio.run(session_router.session_heartbeat(request))

    assert status["status"] == "active"
    assert heartbeat["status"] == "active"


def test_l4_75_v2_queued_response_contains_coordination_fields() -> None:
    mode.acquire_or_queue("10.0.0.1")

    response = _run(
        mode.single_user_mode_middleware(
            _request(client_ip="10.0.0.2"),
            _ok_call_next,
        )
    )
    body = json.loads(response.body)

    assert response.status_code == 503
    assert body["position"] == 1
    assert body["queue_length"] == 1
    assert body["current_ip"] == "10.0.0.1"
    assert "10.0.0.1" in body["detail"]


def test_l4_75_v2_invalid_session_header_is_not_reflected() -> None:
    response = _run(
        mode.single_user_mode_middleware(
            _request(client_ip="10.0.0.1", session_id="not-a-uuid\r\nX-Injected: yes"),
            _ok_call_next,
        )
    )

    assert response.status_code == 200
    assert response.headers["X-Session-Id"] != "not-a-uuid\r\nX-Injected: yes"
    assert uuid.UUID(response.headers["X-Session-Id"])
