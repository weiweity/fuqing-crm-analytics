"""Opt-in query-family HTTP surface. No application is created at import time.

Public routes are GET conversation/run and versioned cancel only. Native prompt
and tool helpers are attached by the runtime factory, never as session CRUD.
"""

import sqlite3
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi

from backend.analytics_app import (
    KEY_HEADER, VERSION_HEADER, _BodyLimit, _error_response, _single_header, _version,
)
from backend.contracts.analytics import AnalyticsCancelRequest, AnalyticsErrorResponse
from backend.contracts.analytics_query_run import (
    QUERY_RUN_SCHEMA, AnalyticsQueryConversation, AnalyticsQueryRunSnapshot,
)
from backend.services.analytics.access import AnalyticsError, B0IdentityRegistry
from backend.services.analytics.jobs import RunStore, validate_key

PREFIX = "/api/v1/analytics-query"
SESSION_HEADER = {
    "name": "X-Runtime-Session-Id", "in": "header", "required": True,
    "schema": {"type": "string", "minLength": 1, "maxLength": 128},
}


def create_query_app(store: RunStore | None = None, identities: B0IdentityRegistry | None = None,
                     *, runtime_ready: Callable[[], bool] | None = None,
                     session_conversations: dict[str, str] | None = None) -> FastAPI:
    """Factory supports offline OpenAPI generation without opening any state."""
    app = FastAPI(title="Shine Mage Query Run Kernel", version=QUERY_RUN_SCHEMA,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(_BodyLimit)
    registry = identities or B0IdentityRegistry()
    mapping = dict(session_conversations or {})

    def principal(request: Request):
        return registry.resolve(_single_header(request, "authorization"))

    def state() -> RunStore:
        if store is None:
            raise AnalyticsError(503, "KERNEL_NOT_CONFIGURED", "查询任务内核尚未显式配置。")
        return store

    def registered_session(request: Request) -> str:
        session_id = _single_header(request, "x-runtime-session-id")
        if session_id is None:
            raise AnalyticsError(400, "SESSION_REQUIRED", "需要已登记的运行时会话。")
        if session_id not in mapping:
            raise AnalyticsError(404, "NOT_FOUND", "原生会话不存在或不可见。")
        return session_id

    def conversation_for(session_id: str) -> str:
        return mapping[session_id]

    def owned_snapshot(actor, session_id: str, run_id: str) -> AnalyticsQueryRunSnapshot:
        snapshot = state().get(actor, run_id)
        if snapshot.conversation_id != conversation_for(session_id):
            raise AnalyticsError(404, "NOT_FOUND", "任务不存在或当前身份不可见。")
        return snapshot

    @app.exception_handler(AnalyticsError)
    async def analytics_error(request: Request, error: AnalyticsError):
        return _error_response(error, request.state.analytics_request_id)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, _error: RequestValidationError):
        return _error_response(AnalyticsError(422, "INVALID_REQUEST", "请求与当前查询合同不匹配，请检查版本、字段和取值。"),
                               request.state.analytics_request_id)

    @app.exception_handler(sqlite3.DatabaseError)
    async def state_error(request: Request, _error: sqlite3.DatabaseError):
        return _error_response(AnalyticsError(503, "STATE_UNAVAILABLE", "任务状态暂不可用，请使用原标识重试。", retryable=True),
                               request.state.analytics_request_id)

    errors = {code: {"model": AnalyticsErrorResponse} for code in (400, 401, 403, 404, 409, 410, 413, 422, 428, 429, 503)}

    @app.get(PREFIX + "/conversations/{conversation_id}", response_model=AnalyticsQueryConversation,
             operation_id="analytics_query_get_conversation", responses=errors,
             openapi_extra={"parameters": [SESSION_HEADER]})
    def get_conversation(conversation_id: str, request: Request, response: Response):
        actor = principal(request)
        session_id = registered_session(request)
        if conversation_id != conversation_for(session_id):
            raise AnalyticsError(404, "NOT_FOUND", "会话不存在或当前身份不可见。")
        response.headers["cache-control"] = "no-store"
        return state().get_conversation(actor, conversation_id)

    @app.get(PREFIX + "/runs/{run_id}", response_model=AnalyticsQueryRunSnapshot,
             operation_id="analytics_query_get_run", responses=errors,
             openapi_extra={"parameters": [SESSION_HEADER]})
    def get_run(run_id: str, request: Request, response: Response):
        actor = principal(request)
        session_id = registered_session(request)
        result = owned_snapshot(actor, session_id, run_id)
        response.headers.update({"cache-control": "no-store", "etag": str(result.version)})
        return result

    @app.post(PREFIX + "/runs/{run_id}/cancel", response_model=AnalyticsQueryRunSnapshot,
              operation_id="analytics_query_cancel_run", responses=errors,
              openapi_extra={"parameters": [KEY_HEADER, VERSION_HEADER, SESSION_HEADER]})
    def cancel_run(run_id: str, payload: AnalyticsCancelRequest, request: Request, response: Response):
        actor = principal(request)
        session_id = registered_session(request)
        owned_snapshot(actor, session_id, run_id)
        result = state().cancel(actor, run_id, validate_key(_single_header(request, "idempotency-key")),
                                _version(request), payload)
        if result.conversation_id != conversation_for(session_id):
            raise AnalyticsError(404, "NOT_FOUND", "任务不存在或当前身份不可见。")
        response.headers.update({"cache-control": "no-store", "etag": str(result.version)})
        return result

    def openapi():
        if app.openapi_schema is None:
            schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
            schema.setdefault("components", {}).setdefault("securitySchemes", {})["QueryBearer"] = {
                "type": "http", "scheme": "bearer",
                "description": "Explicit local query identity only; no default identity, CRM auth or production SSO.",
            }
            schema["security"] = [{"QueryBearer": []}]
            schema["x-query-run-schema"] = QUERY_RUN_SCHEMA
            schema["x-not-b0-run-kernel"] = True
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi
    app.state.session_conversations = mapping
    app.state.runtime_ready = runtime_ready
    return app
