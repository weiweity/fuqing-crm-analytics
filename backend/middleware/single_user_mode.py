"""L4.75 single-user guard for expensive RFM analysis requests.

V1 keeps the historical per-IP lease behavior. V2, enabled with
``FQ_SINGLE_USER_V2=1``, limits the process to one active LAN IP and keeps the
remaining IPs in a FIFO queue.
"""
from __future__ import annotations

import ipaddress
import logging
import os
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from typing import Awaitable, Callable

from fastapi import Request
from starlette.responses import JSONResponse, Response

RFM_SINGLE_USER_PATH = "/api/v1/customer-health/rfm-analysis"
DEFAULT_LOCK_TIMEOUT_SECONDS = 300
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 30
LAN_DENIED_DETAIL = "RFM analysis 仅限局域网访问 (10.x.x.x / 172.16-31.x.x / 192.168.x.x)"

# L4.75 v1 state. Keep the public name because existing tests and the session
# release endpoint depend on it.
ACTIVE_USERS: dict[str, float] = {}


@dataclass
class ActiveSession:
    """One LAN client's active or queued RFM lease."""

    ip: str
    session_id: str
    last_heartbeat: float
    in_flight: int = 0
    release_when_idle: bool = False


# L4.75 v2 state. The dict intentionally contains at most one item.
ACTIVE_SESSIONS: dict[str, ActiveSession] = {}
QUEUE: deque[ActiveSession] = deque()

_STATE_LOCK = threading.RLock()
_LAN_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    # Local development and direct health verification.
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    # IPv6 unique-local addresses are the IPv6 equivalent of RFC1918 LANs.
    ipaddress.ip_network("fc00::/7"),
)

_logger = logging.getLogger(__name__)


def single_user_v2_enabled() -> bool:
    return os.environ.get("FQ_SINGLE_USER_V2", "0") == "1"


def lock_timeout_seconds() -> int:
    raw = (
        os.environ.get("FQ_SINGLE_USER_LOCK_TIMEOUT_SECONDS")
        or os.environ.get("FQ_SINGLE_USER_TIMEOUT")
        or str(DEFAULT_LOCK_TIMEOUT_SECONDS)
    )
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_LOCK_TIMEOUT_SECONDS


def _verify_bearer_token(token: str) -> object:
    from backend.routers.auth import _verify_token

    return _verify_token(token)


def _user_id_from_verify_result(user_info: object) -> str | None:
    if user_info is None:
        return None
    if isinstance(user_info, dict):
        value = user_info.get("username") or user_info.get("user_id") or user_info.get("sub")
        return str(value) if value else None
    if isinstance(user_info, tuple):
        return str(user_info[0]) if user_info else None
    value = str(user_info)
    return value or None


def extract_user_id_from_request(request: Request) -> str | None:
    """Extract the v1 lock key, preferring the socket client IP."""

    if request.client and request.client.host:
        return f"ip:{request.client.host}"

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    return _user_id_from_verify_result(_verify_bearer_token(token))


def _evict_expired(now: float, timeout_seconds: int) -> None:
    """Apply the historical v1 per-IP lease timeout."""

    expired = [user_id for user_id, seen_at in ACTIVE_USERS.items() if now - seen_at >= timeout_seconds]
    for user_id in expired:
        ACTIVE_USERS.pop(user_id, None)


def release_user_lock(user_id: str) -> bool:
    """Release a v1 user's single-user lock if present."""

    return ACTIVE_USERS.pop(user_id, None) is not None


def active_user_count(now: float | None = None) -> int:
    """Return the v1 lock count after applying the five-minute eviction."""

    current = time.monotonic() if now is None else now
    _evict_expired(current, lock_timeout_seconds())
    return len(ACTIVE_USERS)


def is_lan_ip(ip: str) -> bool:
    """Return whether *ip* is an explicitly allowed LAN or loopback address."""

    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False

    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return any(address in network for network in _LAN_NETWORKS if address.version == network.version)


def _new_session_id(raw_session_id: str | None = None) -> str:
    """Accept only UUID session IDs so an untrusted header is never echoed."""

    if raw_session_id:
        try:
            return str(uuid.UUID(raw_session_id))
        except ValueError:
            pass
    return str(uuid.uuid4())


def _active_session_locked() -> ActiveSession | None:
    return next(iter(ACTIVE_SESSIONS.values()), None)


def _drop_expired_queue_locked(now: float, timeout_seconds: int) -> None:
    retained: deque[ActiveSession] = deque()
    for queued in QUEUE:
        if now - queued.last_heartbeat >= timeout_seconds:
            _logger.info(
                "L4.75 v2 evict idle queued session ip=%s, last_heartbeat=%.1fs ago",
                queued.ip,
                now - queued.last_heartbeat,
            )
        else:
            retained.append(queued)
    QUEUE.clear()
    QUEUE.extend(retained)


def _promote_next_locked(now: float) -> ActiveSession | None:
    if ACTIVE_SESSIONS or not QUEUE:
        return None
    promoted = QUEUE.popleft()
    promoted.last_heartbeat = now
    ACTIVE_SESSIONS[promoted.ip] = promoted
    _logger.info("L4.75 v2 promote queue head ip=%s", promoted.ip)
    return promoted


def _evict_and_promote_locked(now: float, timeout_seconds: int) -> ActiveSession | None:
    """Evict inactive v2 sessions and promote the first live queued IP."""

    _drop_expired_queue_locked(now, timeout_seconds)
    active = _active_session_locked()
    if active and active.in_flight == 0 and now - active.last_heartbeat >= timeout_seconds:
        ACTIVE_SESSIONS.pop(active.ip, None)
        _logger.info(
            "L4.75 v2 evict idle active session ip=%s, last_heartbeat=%.1fs ago",
            active.ip,
            now - active.last_heartbeat,
        )
    return _promote_next_locked(now)


def _estimated_wait_seconds_locked(position: int, now: float, timeout_seconds: int) -> int:
    active = _active_session_locked()
    if active is None:
        return 0
    active_remaining = max(0, timeout_seconds - int(now - active.last_heartbeat))
    return active_remaining + max(0, position - 1) * timeout_seconds


def _session_status_locked(ip: str, now: float, timeout_seconds: int) -> dict[str, object]:
    active = ACTIVE_SESSIONS.get(ip)
    if active is not None:
        return {
            "status": "active",
            "ip": ip,
            "session_id": active.session_id,
            "position": 0,
            "queue_length": len(QUEUE),
            "current_ip": ip,
            "estimated_wait_seconds": 0,
            "last_heartbeat_seconds_ago": round(max(0.0, now - active.last_heartbeat), 1),
            "lock_timeout_seconds": timeout_seconds,
            "heartbeat_interval_seconds": DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
            "query_in_flight": active.in_flight > 0,
        }

    for position, queued in enumerate(QUEUE, start=1):
        if queued.ip == ip:
            current = _active_session_locked()
            return {
                "status": "queued",
                "ip": ip,
                "session_id": queued.session_id,
                "position": position,
                "queue_length": len(QUEUE),
                "current_ip": current.ip if current else None,
                "estimated_wait_seconds": _estimated_wait_seconds_locked(position, now, timeout_seconds),
                "last_heartbeat_seconds_ago": round(max(0.0, now - queued.last_heartbeat), 1),
                "lock_timeout_seconds": timeout_seconds,
                "heartbeat_interval_seconds": DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
                "query_in_flight": False,
            }

    current = _active_session_locked()
    return {
        "status": "none",
        "ip": ip,
        "position": 0,
        "queue_length": len(QUEUE),
        "current_ip": current.ip if current else None,
        "estimated_wait_seconds": 0,
        "lock_timeout_seconds": timeout_seconds,
        "heartbeat_interval_seconds": DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
        "query_in_flight": False,
    }


def acquire_or_queue(
    ip: str,
    session_id: str | None = None,
    *,
    now: float | None = None,
) -> dict[str, object]:
    """Acquire the single v2 lease or join its FIFO queue."""

    current_time = time.monotonic() if now is None else now
    timeout_seconds = lock_timeout_seconds()
    with _STATE_LOCK:
        _evict_and_promote_locked(current_time, timeout_seconds)

        active = ACTIVE_SESSIONS.get(ip)
        if active is not None:
            active.last_heartbeat = current_time
            return _session_status_locked(ip, current_time, timeout_seconds)

        for queued in QUEUE:
            if queued.ip == ip:
                # An explicit retry is user activity and keeps this queue entry live.
                queued.last_heartbeat = current_time
                return _session_status_locked(ip, current_time, timeout_seconds)

        new_session = ActiveSession(
            ip=ip,
            session_id=_new_session_id(session_id),
            last_heartbeat=current_time,
        )
        if _active_session_locked() is None:
            ACTIVE_SESSIONS[ip] = new_session
        else:
            QUEUE.append(new_session)
        return _session_status_locked(ip, current_time, timeout_seconds)


def get_session_status(ip: str, *, now: float | None = None) -> dict[str, object]:
    """Observe current v2 state without acquiring or refreshing a lease."""

    current_time = time.monotonic() if now is None else now
    timeout_seconds = lock_timeout_seconds()
    with _STATE_LOCK:
        _evict_and_promote_locked(current_time, timeout_seconds)
        return _session_status_locked(ip, current_time, timeout_seconds)


def heartbeat_session(ip: str, *, now: float | None = None) -> dict[str, object]:
    """Refresh an active or queued v2 lease after real browser activity."""

    current_time = time.monotonic() if now is None else now
    timeout_seconds = lock_timeout_seconds()
    with _STATE_LOCK:
        _evict_and_promote_locked(current_time, timeout_seconds)
        active = ACTIVE_SESSIONS.get(ip)
        if active is not None:
            active.last_heartbeat = current_time
            return _session_status_locked(ip, current_time, timeout_seconds)
        for queued in QUEUE:
            if queued.ip == ip:
                queued.last_heartbeat = current_time
                return _session_status_locked(ip, current_time, timeout_seconds)
        return _session_status_locked(ip, current_time, timeout_seconds)


def _begin_query(ip: str) -> bool:
    """Atomically reserve the only heavy query slot for the active LAN IP."""

    with _STATE_LOCK:
        active = ACTIVE_SESSIONS.get(ip)
        if active is None or active.in_flight > 0:
            return False
        active.in_flight = 1
        return True


def _finish_query(
    ip: str,
    *,
    keep_lease: bool,
    now: float | None = None,
) -> dict[str, object]:
    """Finish one RFM request and atomically refresh or release its lease."""

    current_time = time.monotonic() if now is None else now
    timeout_seconds = lock_timeout_seconds()
    with _STATE_LOCK:
        active = ACTIVE_SESSIONS.get(ip)
        if active is not None:
            active.in_flight = max(0, active.in_flight - 1)
            if not keep_lease:
                active.release_when_idle = True
            if active.in_flight == 0:
                if active.release_when_idle:
                    ACTIVE_SESSIONS.pop(ip, None)
                    _promote_next_locked(current_time)
                else:
                    active.last_heartbeat = current_time
        _evict_and_promote_locked(current_time, timeout_seconds)
        return _session_status_locked(ip, current_time, timeout_seconds)


def release_v2(ip: str, *, now: float | None = None) -> dict[str, object]:
    """Release an active or queued v2 lease and promote the next live IP."""

    current_time = time.monotonic() if now is None else now
    timeout_seconds = lock_timeout_seconds()
    with _STATE_LOCK:
        _evict_and_promote_locked(current_time, timeout_seconds)
        active = ACTIVE_SESSIONS.get(ip)
        release_pending = bool(active and active.in_flight > 0)
        if release_pending:
            active.release_when_idle = True
            released = True
        else:
            released = ACTIVE_SESSIONS.pop(ip, None) is not None

        if not released:
            for position, queued in enumerate(QUEUE):
                if queued.ip == ip:
                    del QUEUE[position]
                    released = True
                    break

        promoted = _promote_next_locked(current_time) if released and not release_pending else None
        return {
            "released": released,
            "user_id": f"ip:{ip}",
            "promoted_ip": promoted.ip if promoted else None,
            "promoted_queue_position": 1 if promoted else None,
            "release_pending": release_pending,
        }


def _reset_v2_state() -> None:
    """Clear process-local v2 state for deterministic regression tests."""

    with _STATE_LOCK:
        ACTIVE_SESSIONS.clear()
        QUEUE.clear()


def _is_guarded_rfm_request(request: Request) -> bool:
    return request.method != "OPTIONS" and request.url.path == RFM_SINGLE_USER_PATH


def _lan_denied_response() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={
            "detail": LAN_DENIED_DETAIL,
            "limited_mode": "single-user-lan-denied",
        },
        headers={"X-Limited-Mode": "single-user-lan-denied"},
    )


def _queued_response(result: dict[str, object]) -> JSONResponse:
    position = int(result["position"])
    queue_length = int(result["queue_length"])
    current_ip = str(result.get("current_ip") or "未知")
    estimated_wait = int(result["estimated_wait_seconds"])
    detail = (
        f"RFM 查询排队中，当前位置 {position}/{queue_length}。"
        f"当前 IP {current_ip} 正在使用，请联系该同事协调或等待自动释放。"
    )
    return JSONResponse(
        status_code=503,
        content={
            "detail": detail,
            # Preserve the existing frontend's v1 single-user error detector.
            "limited_mode": "single-user",
            "session_status": "queued",
            "position": position,
            "queue_length": queue_length,
            "current_ip": current_ip,
            "estimated_wait_seconds": estimated_wait,
            "lock_timeout_seconds": int(result["lock_timeout_seconds"]),
            "heartbeat_interval_seconds": DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
        },
        headers={
            "Retry-After": str(DEFAULT_HEARTBEAT_INTERVAL_SECONDS),
            "X-Limited-Mode": "single-user-queued",
            "X-Queue-Position": str(position),
            "X-Queue-Length": str(queue_length),
            "X-Current-Ip": current_ip,
            "X-Estimated-Wait-Seconds": str(estimated_wait),
            "X-Lock-Timeout-Seconds": str(result["lock_timeout_seconds"]),
            "X-Session-Id": str(result["session_id"]),
        },
    )


def _busy_response(result: dict[str, object]) -> JSONResponse:
    """Reject a duplicate query from the active IP without running DuckDB twice."""

    ip = str(result.get("ip") or "当前 IP")
    return JSONResponse(
        status_code=503,
        content={
            "detail": f"{ip} 已有一条 RFM 查询正在执行，请等待该查询完成。",
            "limited_mode": "single-user",
            "session_status": "busy",
            "position": 0,
            "queue_length": int(result["queue_length"]),
            "current_ip": ip,
            "estimated_wait_seconds": DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
            "lock_timeout_seconds": int(result["lock_timeout_seconds"]),
            "heartbeat_interval_seconds": DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
        },
        headers={
            "Retry-After": str(DEFAULT_HEARTBEAT_INTERVAL_SECONDS),
            "X-Limited-Mode": "single-user-busy",
            "X-Session-Status": "busy",
            "X-Session-Id": str(result["session_id"]),
            "X-Lock-Timeout-Seconds": str(result["lock_timeout_seconds"]),
        },
    )


async def _legacy_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    user_id = extract_user_id_from_request(request)
    if user_id is None:
        return await call_next(request)

    now = time.monotonic()
    timeout_seconds = lock_timeout_seconds()
    _evict_expired(now, timeout_seconds)
    ACTIVE_USERS[user_id] = now
    response = await call_next(request)
    response.headers["X-Limited-Mode"] = "single-user"
    response.headers["X-Lock-Timeout-Seconds"] = str(timeout_seconds)
    return response


async def single_user_mode_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Guard RFM analysis while leaving every other uvicorn route responsive."""

    if not _is_guarded_rfm_request(request):
        return await call_next(request)
    if not single_user_v2_enabled():
        return await _legacy_middleware(request, call_next)

    ip = request.client.host if request.client else ""
    if not ip or not is_lan_ip(ip):
        return _lan_denied_response()

    result = acquire_or_queue(
        ip,
        request.headers.get("X-Session-Id"),
    )
    if result["status"] == "queued":
        return _queued_response(result)

    if not _begin_query(ip):
        # A same-IP tab/retry may already be running. A release can also race
        # this no-await boundary, so re-read once before deciding the response.
        current = acquire_or_queue(ip, request.headers.get("X-Session-Id"))
        if current["status"] == "queued":
            return _queued_response(current)
        if not _begin_query(ip):
            return _busy_response(current)

    try:
        response = await call_next(request)
    except BaseException:
        _finish_query(ip, keep_lease=False)
        raise

    final_status = _finish_query(ip, keep_lease=response.status_code < 400)
    if response.status_code >= 400:
        return response

    response.headers["X-Limited-Mode"] = "single-user"
    response.headers["X-Lock-Timeout-Seconds"] = str(result["lock_timeout_seconds"])
    response.headers["X-Session-Status"] = str(final_status["status"])
    response.headers["X-Session-Id"] = str(result["session_id"])
    return response
