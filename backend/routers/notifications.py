"""L4.75.3 通知弹窗 endpoints (跟 L4.4 middleware 通知接口 1:1 stable 永久规则链配套).

设计:
- POST /api/v1/notifications/notify  B 同事 通知 A 同事
- GET  /api/v1/notifications/list     A 同事 查询未读通知
- POST /api/v1/notifications/release  A 同事 主动 release 锁 (跟 DELETE /api/v1/session 同位)

跟 L4.75 single_user_mode middleware 1:1 stable 永久规则化永久规则链配套, 共用 ACTIVE_USERS 数据结构.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.middleware.single_user_mode import (
    ACTIVE_USERS,
    extract_user_id_from_request,
    release_user_lock,
)

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


class NotifyRequest(BaseModel):
    target_ip: str
    message: str = "请让一下, 我需要查询老客 RFM 数据"


class NotifyResponse(BaseModel):
    delivered: bool
    target_ip: str
    notification_id: str


class Notification(BaseModel):
    notification_id: str
    from_user: str
    message: str
    timestamp: float
    read: bool


def _get_notifications_for_lock(lock_key: str) -> List[Dict[str, Any]]:
    """L4.75.3 helper: 跟 L4.75 单人模式 ACTIVE_USERS 兼容 (旧结构是 float, 新结构是 dict)."""
    info = ACTIVE_USERS.get(lock_key)
    if isinstance(info, dict):
        return info.setdefault("notifications", [])
    return []


def _set_notifications_for_lock(lock_key: str, notifications: List[Dict[str, Any]]) -> None:
    """L4.75.3 helper: 升级 ACTIVE_USERS[lock_key] 从 float 到 dict (跟 L4.75 兼容 1:1 stable 永久规则链配套)."""
    last_active = ACTIVE_USERS.get(lock_key)
    if last_active is None:
        last_active = time.monotonic()
    if isinstance(last_active, dict):
        last_active["notifications"] = notifications
    else:
        ACTIVE_USERS[lock_key] = {
            "last_active": float(last_active) if isinstance(last_active, (int, float)) else time.monotonic(),
            "notifications": notifications,
        }


@router.post("/notify", response_model=NotifyResponse)
def notify_user(request: Request, body: NotifyRequest) -> NotifyResponse:
    """L4.75.3 B 同事 通知 A 同事 (跟 L4.4 SSE 实时推送 1:1 stable 永久规则链配套)."""
    user_id = extract_user_id_from_request(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="登录已过期")

    target_lock = body.target_ip if body.target_ip.startswith("ip:") else f"ip:{body.target_ip}"
    if target_lock not in ACTIVE_USERS:
        raise HTTPException(status_code=404, detail=f"目标用户 {target_lock} 已离线或锁已释放")

    notification_id = f"notif_{int(time.time() * 1000)}"
    notif = {
        "notification_id": notification_id,
        "from_user": user_id,
        "message": body.message,
        "timestamp": time.time(),
        "read": False,
    }
    notifs = _get_notifications_for_lock(target_lock)
    notifs.append(notif)
    _set_notifications_for_lock(target_lock, notifs)
    _logger.info("L4.75.3 notify: %s -> %s: %s", user_id, target_lock, body.message)
    return NotifyResponse(delivered=True, target_ip=body.target_ip, notification_id=notification_id)


@router.get("/list", response_model=List[Notification])
def list_notifications(request: Request) -> List[Notification]:
    """L4.75.3 A 同事 查询未读通知 (跟 user 'B 同事进入后, 就显示重试、通知对方, 然后 A 同事可以收到信息' 1:1 stable 永久规则链配套)."""
    user_id = extract_user_id_from_request(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="登录已过期")
    notifs = _get_notifications_for_lock(user_id)
    return [Notification(**n) for n in notifs]


@router.post("/release")
def release_lock_self(request: Request) -> dict[str, Any]:
    """L4.75.3 A 同事 主动 release 锁 (跟 user '然后 A 同事可以收到信息, 然后可以主动退出账号' 1:1 stable 永久规则链配套)."""
    user_id = extract_user_id_from_request(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="登录已过期")
    released = release_user_lock(user_id)
    return {"released": released, "user_id": user_id}
