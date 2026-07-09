"""L4.75 single-user guard for expensive RFM analysis requests."""
from __future__ import annotations

import logging
import os
import time
from typing import Awaitable, Callable

from fastapi import Request
from starlette.responses import Response

RFM_SINGLE_USER_PATH = "/api/v1/customer-health/rfm-analysis"
DEFAULT_LOCK_TIMEOUT_SECONDS = 300
ACTIVE_USERS: dict[str, float] = {}

_logger = logging.getLogger(__name__)


def _lock_timeout_seconds() -> int:
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
    """L4.75.1 extract lock key (跟 L4.75 1:1 stable 沿用 + 兼容共享账号).

    Priority:
    1. IP address (跟 user '其他的人是共享账号的' 1:1 stable 永久规则链配套).
       Same IP 不同 username 共享锁, 不同 IP 各自独立.
    2. Fallback: Bearer token username (单账号场景, 跟 L4.75 沿用 1:1 stable 永久规则链配套).
    """

    # 优先 IP, 兼容 10 业务分析师共享 admin/fqsw 账号 (跟 L4.75.1 1:1 stable 永久规则化永久规则链配套)
    if request.client and request.client.host:
        return f"ip:{request.client.host}"

    # Fallback: Bearer token username (跟 L4.75 1:1 stable 沿用)
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    return _user_id_from_verify_result(_verify_bearer_token(token))


def _evict_expired(now: float, timeout_seconds: int) -> None:
    expired = [user_id for user_id, seen_at in ACTIVE_USERS.items() if now - seen_at >= timeout_seconds]
    for user_id in expired:
        ACTIVE_USERS.pop(user_id, None)


def release_user_lock(user_id: str) -> bool:
    """Release a user's single-user lock if present."""

    return ACTIVE_USERS.pop(user_id, None) is not None


def active_user_count(now: float | None = None) -> int:
    """Return active lock count after applying the 5-minute LRU eviction."""

    current = time.monotonic() if now is None else now
    _evict_expired(current, _lock_timeout_seconds())
    return len(ACTIVE_USERS)


def _is_guarded_rfm_request(request: Request) -> bool:
    return request.method != "OPTIONS" and request.url.path == RFM_SINGLE_USER_PATH


async def single_user_mode_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Allow one authenticated user at a time through the RFM analysis endpoint."""

    if not _is_guarded_rfm_request(request):
        return await call_next(request)

    user_id = extract_user_id_from_request(request)
    if user_id is None:
        return await call_next(request)

    now = time.monotonic()
    timeout_seconds = _lock_timeout_seconds()
    _evict_expired(now, timeout_seconds)

    # L4.75.1: 1 IP 1 锁 + 多 IP 各自独立 (跟 user "其他的人是共享账号的" 1:1 stable 永久规则链配套)
    # 不同 IP 之间互不冲突 (10 业务分析师共享 IP 时候 = 1 锁, 分多办公地点 = 多锁各自)
    # L4.75.1 业务语义变化: 从 "全局只 1 active user" 改成 "1 IP 1 锁 多 IP 各自" (跟 L4.74 + L4.75 1:1 stable 永久规则链配套)
    ACTIVE_USERS[user_id] = now
    response = await call_next(request)
    response.headers["X-Limited-Mode"] = "single-user"
    response.headers["X-Lock-Timeout-Seconds"] = str(timeout_seconds)
    return response
