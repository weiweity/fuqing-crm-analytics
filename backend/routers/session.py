"""Session control endpoints for the L4.75 RFM lease."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from backend.middleware.single_user_mode import (
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    LAN_DENIED_DETAIL,
    extract_user_id_from_request,
    get_session_status,
    heartbeat_session,
    is_lan_ip,
    lock_timeout_seconds,
    release_user_lock,
    release_v2,
    single_user_v2_enabled,
)

router = APIRouter(prefix="/api/v1/session", tags=["session"])


def _client_ip(request: Request) -> str:
    ip = request.client.host if request.client else ""
    if not ip:
        raise HTTPException(status_code=400, detail="无法识别 client IP")
    return ip


def _require_lan_ip(request: Request) -> str:
    ip = _client_ip(request)
    if not is_lan_ip(ip):
        raise HTTPException(status_code=403, detail=LAN_DENIED_DETAIL)
    return ip


@router.get("/status")
async def session_status(request: Request) -> dict[str, object]:
    """Observe the caller's v2 queue status without acquiring a lease."""

    if not single_user_v2_enabled():
        return {
            "status": "disabled",
            "v2_enabled": False,
            "lock_timeout_seconds": lock_timeout_seconds(),
            "heartbeat_interval_seconds": DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
        }
    return get_session_status(_require_lan_ip(request))


@router.post("/heartbeat")
async def session_heartbeat(request: Request) -> dict[str, object]:
    """Refresh an active or queued lease after browser user activity."""

    if not single_user_v2_enabled():
        return {
            "status": "disabled",
            "v2_enabled": False,
            "lock_timeout_seconds": lock_timeout_seconds(),
            "heartbeat_interval_seconds": DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
        }
    result = heartbeat_session(_require_lan_ip(request))
    if result["status"] == "none":
        # Authentication is still valid, so 401 would incorrectly trigger the
        # frontend's global logout/refresh path.
        raise HTTPException(status_code=409, detail="RFM session 不存在或已因超时释放")
    return result


@router.delete("")
async def release_session(request: Request) -> dict[str, object]:
    """Release the caller's single-user RFM lock."""

    user_id = extract_user_id_from_request(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    if single_user_v2_enabled():
        return release_v2(_require_lan_ip(request))
    return {"released": release_user_lock(user_id), "user_id": user_id}
