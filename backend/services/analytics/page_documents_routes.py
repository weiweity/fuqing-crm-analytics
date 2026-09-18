"""Authenticated free-page asset routes. Independent of BoardSpec HTTP."""
from __future__ import annotations

from pathlib import Path
from typing import Callable
from uuid import uuid4

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from backend.analytics_app import _single_header
from backend.contracts.analytics import AnalyticsErrorDetail, AnalyticsErrorResponse
from backend.contracts.page_documents import (
    PACKAGE_MAX_BYTES, PageCancelResult, PageDraft, PageList, PagePatchPreview,
    PagePreview, PageRollbackPreview, PageSavePreview, PageSnapshot, PageRevision,
    SCHEMA_VERSION, is_package_too_large, page_documents_openapi,
)
from backend.services.analytics.access import AnalyticsError, B0IdentityRegistry
from backend.services.analytics.page_documents import PageDocumentStore, ResolvedPageBinding

PREFIX = "/api/v1/analytics/page-documents"


class _PageBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PATCH", "PUT"}:
            return await self.app(scope, receive, send)
        request_id = uuid4().hex
        scope.setdefault("state", {})["analytics_request_id"] = request_id
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > PACKAGE_MAX_BYTES:
                response = _error(AnalyticsError(413, "PACKAGE_TOO_LARGE", "页面源码包超过大小上限。"), request_id)
                return await response(scope, receive, send)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        return await self.app(scope, replay, send)


def _error(error: AnalyticsError, request_id: str) -> JSONResponse:
    body = AnalyticsErrorResponse(error=AnalyticsErrorDetail(
        code=error.code, message=error.message, retryable=error.retryable, request_id=request_id,
        recovery_url=error.recovery_url,
    ))
    headers = {"cache-control": "no-store", "x-request-id": request_id}
    return JSONResponse(body.model_dump(mode="json"), status_code=error.status, headers=headers)


def page_documents_router(store, principal):
    router = APIRouter(prefix=PREFIX)

    def service():
        if store is None:
            raise AnalyticsError(503, "STATE_UNAVAILABLE", "页面保存库尚未显式配置。", retryable=True)
        return store

    def actor(request, response):
        response.headers["Cache-Control"] = "no-store"
        return principal(request)

    @router.post("/previews", response_model=PagePreview, status_code=201)
    def generate(payload: PageDraft, request: Request, response: Response):
        return service().generate(actor(request, response), payload)

    @router.get("/previews/{preview_id}", response_model=PagePreview)
    def preview(preview_id: str, request: Request, response: Response):
        return service().preview(actor(request, response), preview_id)

    @router.post("/previews/{preview_id}/confirm", response_model=PageSnapshot)
    def confirm(preview_id: str, request: Request, response: Response):
        return service().confirm(actor(request, response), preview_id,
                                 _single_header(request, "idempotency-key"))

    @router.post("/previews/{preview_id}/cancel", response_model=PageCancelResult)
    def cancel(preview_id: str, request: Request, response: Response):
        return service().cancel(actor(request, response), preview_id)

    @router.get("/pages", response_model=PageList)
    def list_pages(request: Request, response: Response, limit: int = 100, offset: int = 0):
        return {"items": service().list(actor(request, response), limit=limit, offset=offset)}

    @router.get("/pages/{page_id}", response_model=PageSnapshot)
    def get_page(page_id: str, request: Request, response: Response, version: int | None = None):
        return service().get(actor(request, response), page_id, version)

    @router.get("/pages/{page_id}/versions", response_model=list[PageRevision])
    def history(page_id: str, request: Request, response: Response, limit: int = 100, offset: int = 0):
        return service().history(actor(request, response), page_id, limit=limit, offset=offset)

    @router.post("/pages/{page_id}/patch-preview", response_model=PagePreview, status_code=201)
    def patch(page_id: str, payload: PagePatchPreview, request: Request, response: Response):
        return service().patch(actor(request, response), page_id, payload)

    @router.post("/pages/{page_id}/save-preview", response_model=PagePreview, status_code=201)
    def save(page_id: str, payload: PageSavePreview, request: Request, response: Response):
        return service().save(actor(request, response), page_id, payload)

    @router.post("/pages/{page_id}/rollback-preview", response_model=PagePreview, status_code=201)
    def rollback(page_id: str, payload: PageRollbackPreview, request: Request, response: Response):
        return service().rollback(actor(request, response), page_id, payload)

    return router


def create_page_app(
    identities: B0IdentityRegistry | None = None,
    *,
    page_state_dir: Path | None = None,
    resolve_binding: Callable[..., ResolvedPageBinding] | None = None,
) -> FastAPI:
    app = FastAPI(title="Free Page Documents", version=SCHEMA_VERSION,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(_PageBodyLimit)
    registry = identities or B0IdentityRegistry()
    store = PageDocumentStore(page_state_dir, resolve_binding=resolve_binding) if page_state_dir is not None else None

    def principal(request: Request):
        return registry.resolve(_single_header(request, "authorization"))

    app.include_router(page_documents_router(store, principal))

    @app.exception_handler(AnalyticsError)
    async def analytics_error(request: Request, error: AnalyticsError):
        return _error(error, getattr(request.state, "analytics_request_id", uuid4().hex))

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError):
        rid = getattr(request.state, "analytics_request_id", uuid4().hex)
        if is_package_too_large(error):
            return _error(AnalyticsError(413, "PACKAGE_TOO_LARGE", "页面源码包超过大小上限。"), rid)
        return _error(AnalyticsError(422, "INVALID_PAGE", "页面源码包、绑定或字段不符合合同。"), rid)

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        offline = page_documents_openapi()
        for key in ("x-page-http", "x-free-page-schema", "x-b0-board-spec-untouched",
                    "x-page-operations", "x-binding-states", "x-bridge-protocol",
                    "x-bridge-forbidden-ops", "x-page-errors", "x-bridge-budget"):
            schema[key] = offline[key]
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
    return app
