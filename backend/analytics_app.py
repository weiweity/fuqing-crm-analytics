"""Opt-in, isolated B0 HTTP surface. No application is created at import time.

Do not import backend.routers here: its package initializer eagerly loads the
legacy CRM routers/configuration. The B0 app only mounts the run kernel below.
New runs are refused by default until an explicit runtime readiness callback is
supplied. This checkpoint does not start or claim to wire a DSH runtime.
"""

import asyncio
import re
import sqlite3
import time
from typing import Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from backend.contracts.analytics import (
    ANALYTICS_RUN_SCHEMA,
    AnalyticsCancelRequest,
    AnalyticsConversation,
    AnalyticsConversationRequest,
    AnalyticsErrorDetail,
    AnalyticsErrorResponse,
    AnalyticsRunAccepted,
    AnalyticsRunEvent,
    AnalyticsRunRequest,
    AnalyticsRunSnapshot,
)
from backend.services.analytics.access import AnalyticsError, B0IdentityRegistry, require
from backend.services.analytics.jobs import TERMINAL, RunStore, validate_key

PREFIX = "/api/v1/analytics"
MAX_BODY_BYTES = 65536
KEY_HEADER = {"name": "Idempotency-Key", "in": "header", "required": True,
              "schema": {"type": "string", "minLength": 1, "maxLength": 200}}
VERSION_HEADER = {"name": "If-Match", "in": "header", "required": True,
                  "schema": {"type": "string", "pattern": "^[1-9][0-9]{0,15}$"}}
CURSOR_HEADER = {"name": "Last-Event-ID", "in": "header", "required": False,
                 "schema": {"type": "string", "maxLength": 256},
                 "description": "Opaque event_id returned by this run; must agree with after when both are sent."}


def _error_response(error: AnalyticsError, request_id: str) -> JSONResponse:
    body = AnalyticsErrorResponse(error=AnalyticsErrorDetail(
        code=error.code, message=error.message, retryable=error.retryable,
        request_id=request_id, recovery_url=error.recovery_url,
    ))
    headers = {"cache-control": "no-store", "x-request-id": request_id}
    if error.status == 429:
        headers["retry-after"] = "1"
    return JSONResponse(body.model_dump(mode="json"), status_code=error.status, headers=headers)


class _BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = uuid4().hex
        scope.setdefault("state", {})["analytics_request_id"] = request_id
        if scope["method"] not in {"POST", "PATCH", "PUT"}:
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > MAX_BODY_BYTES:
                response = _error_response(AnalyticsError(413, "BODY_TOO_LARGE", "请求超过 B0 的大小上限。"), request_id)
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


def _single_header(request: Request, name: str) -> str | None:
    values = request.headers.getlist(name)
    if len(values) > 1:
        raise AnalyticsError(400, "DUPLICATE_HEADER", "请求包含重复的控制头。")
    return values[0] if values else None


def _version(request: Request) -> int:
    raw = _single_header(request, "if-match")
    if raw is None:
        raise AnalyticsError(428, "IF_MATCH_REQUIRED", "取消需要最近一次 GET 返回的版本号。")
    if not re.fullmatch(r"[1-9][0-9]{0,15}", raw):
        raise AnalyticsError(400, "INVALID_VERSION", "If-Match 必须是正整数字符串。")
    return int(raw)


def _cursor(run_id: str, header: str | None, query: str | None) -> int:
    if header is not None and query is not None and header != query:
        raise AnalyticsError(422, "EVENT_CURSOR_CONFLICT", "Last-Event-ID 与 after 不一致。")
    value = header if header is not None else query
    if value is None:
        return 0
    if len(value) > 256 or not value.startswith(run_id + ":"):
        raise AnalyticsError(422, "INVALID_EVENT_CURSOR", "事件游标不属于当前任务。")
    sequence = value[len(run_id) + 1:]
    if not re.fullmatch(r"0|[1-9][0-9]{0,15}", sequence):
        raise AnalyticsError(422, "INVALID_EVENT_CURSOR", "事件游标格式无效。")
    return int(sequence)


def create_app(store: RunStore | None = None, identities: B0IdentityRegistry | None = None,
               *, runtime_ready: Callable[[], bool] | None = None,
               runtime_conversation_id: str | None = None,
               stream_window_seconds: float = 10) -> FastAPI:
    """Factory supports offline OpenAPI generation without opening any state.

    A ready adapter is an injected server dependency, never a request field.
    The factory itself does not launch a scheduler, model, worker or web server.
    """
    if not 0 < stream_window_seconds <= 30:
        raise ValueError("SSE connection window must be in (0, 30] seconds")
    app = FastAPI(title="Shine Mage B0 Run Kernel", version=ANALYTICS_RUN_SCHEMA,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(_BodyLimit)
    registry = identities or B0IdentityRegistry()

    def principal(request: Request):
        return registry.resolve(_single_header(request, "authorization"))

    def state() -> RunStore:
        if store is None:
            raise AnalyticsError(503, "KERNEL_NOT_CONFIGURED", "B0 任务内核尚未显式配置。")
        return store

    @app.exception_handler(AnalyticsError)
    async def analytics_error(request: Request, error: AnalyticsError):
        return _error_response(error, request.state.analytics_request_id)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, _error: RequestValidationError):
        # Pydantic's raw error includes input values. Never reflect those.
        return _error_response(AnalyticsError(422, "INVALID_REQUEST", "请求与当前 B0 合同不匹配，请检查版本、字段和取值。"),
                               request.state.analytics_request_id)

    @app.exception_handler(sqlite3.DatabaseError)
    async def state_error(request: Request, _error: sqlite3.DatabaseError):
        return _error_response(AnalyticsError(503, "STATE_UNAVAILABLE", "任务状态暂不可用，请使用原标识重试。", retryable=True),
                               request.state.analytics_request_id)

    errors = {code: {"model": AnalyticsErrorResponse} for code in (400, 401, 403, 404, 409, 410, 413, 422, 428, 429, 503)}

    @app.post(PREFIX + "/conversations", status_code=201, response_model=AnalyticsConversation,
              operation_id="analytics_create_conversation", responses=errors,
              openapi_extra={"parameters": [KEY_HEADER]})
    def create_conversation(payload: AnalyticsConversationRequest, request: Request, response: Response):
        actor = principal(request)
        result = state().create_conversation(actor, validate_key(_single_header(request, "idempotency-key")), payload)
        response.headers["cache-control"] = "no-store"
        return result

    @app.get(PREFIX + "/conversations/{conversation_id}", response_model=AnalyticsConversation,
             operation_id="analytics_get_conversation", responses=errors)
    def get_conversation(conversation_id: str, request: Request, response: Response):
        actor = principal(request)
        response.headers["cache-control"] = "no-store"
        return state().get_conversation(actor, conversation_id)

    @app.post(PREFIX + "/conversations/{conversation_id}/runs", status_code=202,
              response_model=AnalyticsRunAccepted, operation_id="analytics_create_run", responses=errors,
              openapi_extra={"parameters": [KEY_HEADER]})
    def create_run(conversation_id: str, payload: AnalyticsRunRequest, request: Request, response: Response):
        actor = principal(request)
        ready = runtime_ready is not None and runtime_ready() is True
        ready = ready and (runtime_conversation_id is None or conversation_id == runtime_conversation_id)
        accepted = state().accept(actor, conversation_id, validate_key(_single_header(request, "idempotency-key")),
                                  payload, allow_new=ready)
        response.headers["location"] = accepted.location
        response.headers["cache-control"] = "no-store"
        return accepted

    @app.get(PREFIX + "/runs/{run_id}", response_model=AnalyticsRunSnapshot,
             operation_id="analytics_get_run", responses=errors)
    def get_run(run_id: str, request: Request, response: Response):
        actor = principal(request)
        result = state().get(actor, run_id)
        response.headers.update({"cache-control": "no-store", "etag": str(result.version)})
        return result

    @app.post(PREFIX + "/runs/{run_id}/cancel", response_model=AnalyticsRunSnapshot,
              operation_id="analytics_cancel_run", responses=errors,
              openapi_extra={"parameters": [KEY_HEADER, VERSION_HEADER]})
    def cancel_run(run_id: str, payload: AnalyticsCancelRequest, request: Request, response: Response):
        actor = principal(request)
        result = state().cancel(actor, run_id, validate_key(_single_header(request, "idempotency-key")), _version(request), payload)
        response.headers.update({"cache-control": "no-store", "etag": str(result.version)})
        return result

    @app.get(PREFIX + "/runs/{run_id}/events", operation_id="analytics_stream_run",
             response_class=StreamingResponse, openapi_extra={"parameters": [CURSOR_HEADER]}, responses={
        **errors, 200: {"content": {"text/event-stream": {"schema": {"type": "string"}}},
                       "description": "Bounded SSE connection. Reconnect using the last event_id; never resubmit a run."},
    })
    async def stream_run(run_id: str, request: Request, after: str | None = None):
        actor = principal(request)
        cursor = _cursor(run_id, _single_header(request, "last-event-id"), after)
        # Validate before sending HTTP 200; expired cursors must be real 410s.
        await run_in_threadpool(state().events, actor, run_id, cursor)

        def stream_principal():
            current = principal(request)
            require(current, "run:read")
            if current.actor_id != actor.actor_id:
                raise AnalyticsError(403, "FORBIDDEN", "流式连接的身份已变化，请重新鉴权。")
            return current

        async def stream():
            sequence = cursor
            until = time.monotonic() + stream_window_seconds
            while time.monotonic() < until:
                try:
                    current = stream_principal()  # revocation is checked on every read
                    events = await run_in_threadpool(state().events, current, run_id, sequence)
                    for event in events:
                        # Re-check directly before each disclosure, too.
                        stream_principal()
                        yield f"id: {event.event_id}\nevent: {event.type}\ndata: {event.model_dump_json()}\n\n"
                        sequence = event.sequence
                    snapshot = await run_in_threadpool(state().get, stream_principal(), run_id)
                    if snapshot.status in TERMINAL and sequence >= snapshot.last_sequence:
                        return
                except AnalyticsError as error:
                    yield f"event: error\ndata: {{\"code\":\"{error.code}\",\"request_id\":\"{request.state.analytics_request_id}\"}}\n\n"
                    return
                except sqlite3.DatabaseError:
                    yield f"event: error\ndata: {{\"code\":\"STATE_UNAVAILABLE\",\"request_id\":\"{request.state.analytics_request_id}\"}}\n\n"
                    return
                if await request.is_disconnected():
                    return
                await asyncio.sleep(0.05)
            yield ": reconnect with Last-Event-ID; do not resubmit\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"cache-control": "no-store"})

    def openapi():
        if app.openapi_schema is None:
            schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
            components = schema.setdefault("components", {})
            event = AnalyticsRunEvent.model_json_schema(ref_template="#/components/schemas/{model}")
            definitions = event.pop("$defs", {})
            components.setdefault("schemas", {}).update(definitions)
            components["schemas"]["AnalyticsRunEvent"] = event
            components["securitySchemes"] = {"B0Bearer": {"type": "http", "scheme": "bearer",
                "description": "Explicit local B0 identity only; no default identity, CRM auth or production SSO."}}
            schema["security"] = [{"B0Bearer": []}]
            schema["x-analytics-event-schema"] = {"$ref": "#/components/schemas/AnalyticsRunEvent"}
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi
    return app
