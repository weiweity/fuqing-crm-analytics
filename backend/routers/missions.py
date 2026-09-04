"""Mission endpoints: evidence, controlled Q&A, approval, and draft export."""

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse

from backend.contracts.schemas import (
    ApprovalRequest,
    DiagnoseRequest,
    DiagnoseResponse,
    ExportResponse,
    MissionResponse,
)
from backend.routers.auth import get_current_username, require_admin
from backend.services.mission_service import MissionService, MissionServiceError


router = APIRouter(prefix="/api/v1/missions", tags=["AI Mission"])


def _service() -> MissionService:
    try:
        return MissionService.from_environment()
    except MissionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _call(operation):
    try:
        return operation()
    except MissionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _required_header(value: str | None, name: str) -> str:
    if value is None or not value.strip():
        raise HTTPException(status_code=428, detail=f"缺少必需请求头 {name}")
    if len(value) > 200:
        raise HTTPException(status_code=400, detail=f"{name} 过长")
    return value.strip()


@router.get(
    "/today",
    response_model=MissionResponse,
    operation_id="mission_get_today",
    summary="读取今日唯一 CEO Mission",
)
def get_today_mission(request: Request):
    get_current_username(request)
    return _call(lambda: _service().get_today())


@router.post(
    "/diagnose",
    response_model=DiagnoseResponse,
    operation_id="mission_diagnose",
    summary="使用受控语义层回答经营问题",
)
def diagnose_mission(request: Request, payload: DiagnoseRequest):
    get_current_username(request)
    return _call(lambda: _service().diagnose(payload.question))


@router.get(
    "/{mission_id}",
    response_model=MissionResponse,
    operation_id="mission_get",
    summary="按 ID 读取 Mission",
)
def get_mission(mission_id: str, request: Request):
    get_current_username(request)
    return _call(lambda: _service().get_mission(mission_id))


@router.post(
    "/{mission_id}/approve",
    response_model=MissionResponse,
    operation_id="mission_approve",
    summary="审批 Mission",
)
def approve_mission(
    mission_id: str,
    payload: ApprovalRequest,
    request: Request,
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    actor = get_current_username(request)
    version = _required_header(if_match, "If-Match")
    key = _required_header(idempotency_key, "Idempotency-Key")
    return _call(
        lambda: _service().approve(
            mission_id,
            actor,
            version,
            key,
            payload.model_dump(),
        )
    )


@router.post(
    "/{mission_id}/audience-export",
    response_model=ExportResponse,
    operation_id="mission_create_draft_export",
    summary="生成 90/10 合成人群草稿",
)
def create_audience_export(
    mission_id: str,
    request: Request,
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    actor = get_current_username(request)
    version = _required_header(if_match, "If-Match")
    key = _required_header(idempotency_key, "Idempotency-Key")
    return _call(lambda: _service().create_draft_export(mission_id, actor, version, key))


@router.post(
    "/{mission_id}/demo-reset",
    response_model=MissionResponse,
    operation_id="mission_reset_demo",
    summary="将本地演示恢复到审批前",
)
def reset_demo_mission(
    mission_id: str,
    request: Request,
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    actor = require_admin(request)
    version = _required_header(if_match, "If-Match")
    key = _required_header(idempotency_key, "Idempotency-Key")
    return _call(lambda: _service().reset_demo(mission_id, actor, version, key))


@router.get(
    "/{mission_id}/audience-exports/{export_id}/download",
    operation_id="mission_download_draft_export",
    summary="下载受保护的合成人群草稿",
)
def download_audience_export(mission_id: str, export_id: str, request: Request):
    get_current_username(request)
    path = _call(lambda: _service().resolve_export(mission_id, export_id))
    return FileResponse(
        path,
        media_type="text/csv; charset=utf-8",
        filename=path.name,
    )
