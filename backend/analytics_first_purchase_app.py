"""Opt-in first-purchase HTTP over the shared RunStore/physical worker.

No native tool, catalog selection, model, or CRM service is enabled here.
The no-argument factory generates OpenAPI without opening state.
"""

from __future__ import annotations

import sqlite3
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi

from backend.analytics_app import KEY_HEADER, VERSION_HEADER, _BodyLimit, _error_response, _single_header, _version
from backend.contracts.analytics import AnalyticsCancelRequest, AnalyticsErrorResponse
from backend.contracts.analytics_first_purchase import FirstPurchaseQueryRequest
from backend.contracts.analytics_first_purchase_run import (
    FIRST_PURCHASE_HTTP_PREFIX,
    FIRST_PURCHASE_RUN_SCHEMA,
)
from backend.services.analytics.access import AnalyticsError, B0IdentityRegistry
from backend.services.analytics.first_purchase.runtime import FirstPurchaseRuntime
from backend.services.analytics.jobs import validate_key

from backend.contracts.analytics_first_purchase_kernel import FirstPurchaseKernelSnapshot

PREFIX = FIRST_PURCHASE_HTTP_PREFIX


def create_first_purchase_app(
    runtime: FirstPurchaseRuntime | None = None,
    identities: B0IdentityRegistry | None = None,
    *,
    runtime_ready: Callable[[], bool] | None = None,
) -> FastAPI:
    """Factory supports offline OpenAPI generation without opening any state."""
    app = FastAPI(
        title="Shine Mage First-Purchase Path Kernel",
        version=FIRST_PURCHASE_RUN_SCHEMA,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(_BodyLimit)
    registry = identities or B0IdentityRegistry()

    def principal(request: Request):
        return registry.resolve(_single_header(request, "authorization"))

    def state() -> FirstPurchaseRuntime:
        if runtime is None:
            raise AnalyticsError(503, "KERNEL_NOT_CONFIGURED", "查询任务内核尚未显式配置。")
        return runtime

    def ready() -> bool:
        return True if runtime_ready is None else bool(runtime_ready())

    @app.exception_handler(AnalyticsError)
    async def analytics_error(request: Request, error: AnalyticsError):
        return _error_response(error, request.state.analytics_request_id)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, _error: RequestValidationError):
        return _error_response(
            AnalyticsError(422, "INVALID_REQUEST", "请求与当前查询合同不匹配，请检查版本、字段和取值。"),
            request.state.analytics_request_id,
        )

    @app.exception_handler(sqlite3.DatabaseError)
    async def state_error(request: Request, _error: sqlite3.DatabaseError):
        return _error_response(
            AnalyticsError(503, "STATE_UNAVAILABLE", "任务状态暂不可用，请使用原标识重试。", retryable=True),
            request.state.analytics_request_id,
        )

    errors = {code: {"model": AnalyticsErrorResponse} for code in (400, 401, 403, 404, 409, 410, 413, 422, 428, 429, 503)}

    @app.post(
        PREFIX + "/runs",
        response_model=FirstPurchaseKernelSnapshot,
        operation_id="analytics_first_purchase_create_run",
        responses={**errors, 202: {"model": FirstPurchaseKernelSnapshot}},
        openapi_extra={"parameters": [KEY_HEADER]},
    )
    def create_run(payload: FirstPurchaseQueryRequest, request: Request, response: Response):
        actor = principal(request)
        if not ready():
            raise AnalyticsError(503, "KERNEL_NOT_READY", "查询任务内核尚未就绪。", retryable=True)
        result = state().submit_and_execute(actor, validate_key(_single_header(request, "idempotency-key")), payload)
        response.headers.update({"cache-control": "no-store", "etag": str(result.version)})
        response.headers["x-first-purchase-runtime"] = "shared-worker"
        if result.status not in {"SUCCEEDED", "FAILED", "CANCELLED", "NEEDS_INPUT"}:
            response.status_code = 202
        return result

    @app.get(
        PREFIX + "/runs/{run_id}",
        response_model=FirstPurchaseKernelSnapshot,
        operation_id="analytics_first_purchase_get_run",
        responses=errors,
    )
    def get_run(run_id: str, request: Request, response: Response):
        result = state().get(principal(request), run_id)
        response.headers.update({"cache-control": "no-store", "etag": str(result.version)})
        response.headers["x-first-purchase-runtime"] = "shared-worker"
        return result

    @app.post(
        PREFIX + "/runs/{run_id}/cancel",
        response_model=FirstPurchaseKernelSnapshot,
        operation_id="analytics_first_purchase_cancel_run",
        responses=errors,
        openapi_extra={"parameters": [KEY_HEADER, VERSION_HEADER]},
    )
    def cancel_run(run_id: str, payload: AnalyticsCancelRequest, request: Request, response: Response):
        result = state().cancel(
            principal(request),
            run_id,
            validate_key(_single_header(request, "idempotency-key")),
            _version(request),
            payload,
        )
        response.headers.update({"cache-control": "no-store", "etag": str(result.version)})
        response.headers["x-first-purchase-runtime"] = "shared-worker"
        return result

    def openapi():
        if app.openapi_schema is None:
            schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
            schema.setdefault("components", {}).setdefault("securitySchemes", {})["FirstPurchaseBearer"] = {
                "type": "http",
                "scheme": "bearer",
                "description": "Explicit local first-purchase identity only; no default identity, CRM auth or production SSO.",
            }
            schema["security"] = [{"FirstPurchaseBearer": []}]
            schema["x-first-purchase-run-schema"] = FIRST_PURCHASE_RUN_SCHEMA
            schema["x-shared-run-kernel"] = True
            schema["x-not-channel-followup"] = True
            schema["x-not-native-product"] = True
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi
    app.state.runtime_ready = runtime_ready
    app.state.runtime = runtime
    return app
