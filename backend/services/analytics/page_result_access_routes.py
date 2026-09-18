"""Read-only authorized result-bridge HTTP. Not mounted unless explicitly configured."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.analytics_app import _single_header
from backend.contracts.analytics import AnalyticsErrorDetail, AnalyticsErrorResponse
from backend.services.analytics.access import AnalyticsError, B0IdentityRegistry
from backend.services.analytics.page_result_access import PageResultAccess

PREFIX = "/api/v1/analytics/page-result-access"


def _error(error: AnalyticsError, request_id: str) -> JSONResponse:
    body = AnalyticsErrorResponse(error=AnalyticsErrorDetail(
        code=error.code, message=error.message, retryable=error.retryable, request_id=request_id,
        recovery_url=error.recovery_url,
    ))
    headers = {"cache-control": "no-store", "x-request-id": request_id}
    return JSONResponse(body.model_dump(mode="json"), status_code=error.status, headers=headers)


def page_result_access_router(access, principal):
    router = APIRouter(prefix=PREFIX)

    def service():
        if access is None:
            raise AnalyticsError(503, "STATE_UNAVAILABLE", "授权结果桥尚未显式配置。", retryable=True)
        return access

    def actor(request, response):
        response.headers["Cache-Control"] = "no-store"
        return principal(request)

    @router.post("/read")
    def read(payload: dict[str, Any], request: Request, response: Response):
        body = payload if isinstance(payload, dict) else {}
        return service().read(actor(request, response), body.get("request") or {},
                              manifest=body.get("manifest"))

    @router.post("/cancel")
    def cancel(payload: dict[str, Any], request: Request, response: Response):
        body = payload if isinstance(payload, dict) else {}
        return service().cancel(actor(request, response), body.get("request") or body)

    @router.post("/binding-state")
    def binding_state(payload: dict[str, Any], request: Request, response: Response):
        body = payload if isinstance(payload, dict) else {}
        return service().binding_state(actor(request, response), body.get("manifest"))

    @router.post("/snapshots", status_code=201)
    def snapshots(payload: dict[str, Any], request: Request, response: Response):
        actor(request, response)
        snapshot = service().put_snapshot(payload if isinstance(payload, dict) else {})
        return {
            "result_ref": snapshot.result_ref,
            "result_version": snapshot.result_version,
            "owner": snapshot.owner,
        }

    return router


def create_result_access_app(
    identities: B0IdentityRegistry | None = None,
    *,
    access: PageResultAccess | None = None,
) -> FastAPI:
    app = FastAPI(title="Free Page Result Access", version="free-page/v1",
                  docs_url=None, redoc_url=None, openapi_url=None)
    registry = identities or B0IdentityRegistry()
    store = access if access is not None else PageResultAccess()

    def principal(request: Request):
        return registry.resolve(_single_header(request, "authorization"))

    app.include_router(page_result_access_router(store, principal))

    @app.exception_handler(AnalyticsError)
    async def analytics_error(request: Request, error: AnalyticsError):
        return _error(error, getattr(request.state, "analytics_request_id", uuid4().hex))

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError):
        rid = getattr(request.state, "analytics_request_id", uuid4().hex)
        return _error(AnalyticsError(422, "INVALID_PAGE", "页面绑定或读取请求不符合合同。"), rid)

    return app
