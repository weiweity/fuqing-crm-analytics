"""Sprint 205+ Admin Upload Sprint 1 router (v5 prompt §5).

3 endpoints (跟 v5 prompt 1:1 stable):
- GET  /upload-config
- POST /upload (multipart + Idempotency-Key)
- GET  /uploads (limit/offset/business_type/status)

显式禁止:
- 不实现 POST /etl-runs (Sprint 2)
- 不调 scripts/etl/admin_etl_runner.py (Sprint 2)
- 不调 ETL pipeline 触发真实计算
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from backend.routers.auth import is_admin_username
from backend.services import admin_upload as svc
from backend.contracts.admin import (
    UploadConfigResponse,
    UploadListResponse,
    UploadRecordOut,
    UploadResponse,
    UploadSourcePublic,
    UploadValidationResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin-upload"])


# ─────────────────────────────────────────────────────────────
# require_admin dependency (跟 v5 prompt §"admin 鉴权" 1:1 stable)
#
# 行为:
# - 公共路径 / 未登录 → 401
# - 非 admin → 403
# - admin → 返 username
# 用 getattr(request.state, "username", None) 安全读取 (跟 v5 prompt §"main.py
# auth_middleware" 1:1 stable 永久规则化沿用, 防 AttributeError).
# ─────────────────────────────────────────────────────────────
def require_admin(request: Request) -> str:
    username = getattr(request.state, "username", None)
    if not username:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHENTICATED", "message": "需要登录"},
        )
    if not is_admin_username(username):
        raise HTTPException(
            status_code=403,
            detail={"code": "ADMIN_REQUIRED", "message": "需要管理员权限"},
        )
    return username


# ─────────────────────────────────────────────────────────────
# GET /upload-config
# ─────────────────────────────────────────────────────────────
@router.get("/upload-config", response_model=UploadConfigResponse)
def get_upload_config(_: str = Depends(require_admin)):
    sources = svc.public_sources_for_response()
    return UploadConfigResponse(
        sources=[UploadSourcePublic(**s) for s in sources],
        max_upload_bytes=svc.MAX_UPLOAD_BYTES,
    )


# ─────────────────────────────────────────────────────────────
# POST /upload
#
# P1-3 修法: async def → def, 让 FastAPI 在线程池跑同步 100MB 文件 I/O +
# pandas/openpyxl/fsync/阻塞 flock, 不阻塞 event loop. 不动 UploadFile / service API /
# 错误码 / 幂等语义.
#
# P1-4 修法: 加 response_model=UploadResponse + status_code=201 (默认), responses
# 字典声明 200/400/401/403/409/413/422/500 完整状态码, 让 OpenAPI 跟实际行为对齐.
# ─────────────────────────────────────────────────────────────
@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=201,
    responses={
        200: {"model": UploadResponse, "description": "Idempotency-Key 命中, 返老记录 (duplicate=true)"},
        201: {"model": UploadResponse, "description": "新建 staged 记录成功"},
        400: {"description": "未知业务类型 / 文件名非法 / 空文件 / Idempotency-Key 非法 (空/whitespace/>128 字符)"},
        401: {"description": "未登录"},
        403: {"description": "非管理员"},
        409: {"description": "business_type + sha256 重复 (DUPLICATE_UPLOAD) 或 Idempotency-Key 冲突 (IDEMPOTENCY_CONFLICT)"},
        413: {"description": "payload 超过 100MB (PAYLOAD_TOO_LARGE)"},
        422: {"description": "扩展名非法 或 业务内容校验失败 (VALIDATION_FAILED)"},
        500: {"description": "registry 损坏不可恢复 (REGISTRY_CORRUPT)"},
    },
)
def post_upload(
    request: Request,
    business_type: str = Form(...),
    file: UploadFile = File(...),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    _: str = Depends(require_admin),
):
    # L1 修法: router 层 Idempotency-Key 长度 + whitespace 校验.
    # service 层有 defensive 兜底, 但 router 层 FastAPI 在依赖注入阶段就能 reject,
    # 不必走到 service.
    if idempotency_key is not None:
        if len(idempotency_key) > svc.IDEMPOTENCY_KEY_MAX_LENGTH:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "IDEMPOTENCY_KEY_INVALID",
                    "message": (
                        f"Idempotency-Key 长度 {len(idempotency_key)} 超过 "
                        f"{svc.IDEMPOTENCY_KEY_MAX_LENGTH}"
                    ),
                },
            )
        if not idempotency_key.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "IDEMPOTENCY_KEY_INVALID",
                    "message": "Idempotency-Key 不能为空或纯空白",
                },
            )
    username = request.state.username
    try:
        # multipart file 已经是 SpooledTemporaryFile, read() 流式 + 大小限制内
        result = svc.upload(
            business_type=business_type,
            file_obj=file.file,
            original_filename=file.filename or "",
            uploaded_by=username,
            idempotency_key=idempotency_key if idempotency_key else None,
        )
    except svc.AdminUploadError as exc:
        # 映射服务层异常 → HTTP (跟 L4.5 + L4.50 1:1 stable 永久规则化沿用)
        raise HTTPException(
            status_code=exc.http_status,
            detail={"code": exc.code, "message": str(exc)},
        )

    record = UploadRecordOut(
        upload_id=result.upload_id,
        business_type=result.business_type,
        original_filename=result.original_filename,
        extension=result.extension,
        size_bytes=result.size_bytes,
        sha256=result.sha256,
        uploaded_by=result.uploaded_by,
        uploaded_at=result.uploaded_at,
        status="staged",
        validation=UploadValidationResult(**(result.validation or {
            "validator": "unknown", "valid": True, "detected_format": "n/a", "row_sample_count": None, "warnings": [],
        })),
        future_post_actions=result.future_post_actions,
    )
    body = UploadResponse(upload=record, duplicate=result.idempotency_hit)
    if result.idempotency_hit:
        # 幂等命中必须明确返 200 (跟 OpenAPI responses 200 描述对齐)
        return JSONResponse(status_code=200, content=body.model_dump(mode="json"))
    return body


# ─────────────────────────────────────────────────────────────
# GET /uploads
# ─────────────────────────────────────────────────────────────
@router.get("/uploads", response_model=UploadListResponse)
def get_uploads(
    business_type: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: str = Depends(require_admin),
):
    items, total = svc.list_uploads(
        business_type=business_type,
        status=status,
        limit=limit,
        offset=offset,
    )
    return UploadListResponse(
        items=[
            UploadRecordOut(
                upload_id=it.upload_id,
                business_type=it.business_type,
                original_filename=it.original_filename,
                extension=it.extension,
                size_bytes=it.size_bytes,
                sha256=it.sha256,
                uploaded_by=it.uploaded_by,
                uploaded_at=it.uploaded_at,
                status="staged",
                validation=UploadValidationResult(**(it.validation or {
                    "validator": "unknown", "valid": True, "detected_format": "n/a", "row_sample_count": None, "warnings": [],
                })),
                future_post_actions=it.future_post_actions,
            )
            for it in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )