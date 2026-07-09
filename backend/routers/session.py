"""Session control endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from backend.middleware.single_user_mode import extract_user_id_from_request, release_user_lock

router = APIRouter(prefix="/api/v1/session", tags=["session"])


@router.delete("")
async def release_session(request: Request) -> dict[str, object]:
    """Release the caller's single-user RFM lock."""

    user_id = extract_user_id_from_request(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return {"released": release_user_lock(user_id), "user_id": user_id}
