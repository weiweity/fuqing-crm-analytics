"""Explicit B0 runner. Configuration arrives on stdin, never argv or dotenv.

Only this module's __main__ starts a local service. No legacy CRM import.
"""

import asyncio
import json
import secrets
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Request
from pydantic import Field, field_validator
from starlette.concurrency import run_in_threadpool

from backend.analytics_app import create_app, _single_header
from backend.analytics_fixture import SyntheticFixture
from backend.analytics_query_app import create_query_app
from backend.analytics_query_fixture import ChannelFollowupFixture
from backend.contracts.analytics import AnalyticsModel, AnalyticsRunRequest, AnalyticsConversationRequest, OpaqueId
from backend.contracts.analytics_query import ChannelFollowupQueryRequest
from backend.contracts.analytics_query_run import (
    QUERY_RUN_FAMILY, AnalyticsQueryConversationRequest, AnalyticsQueryNativePrompt,
    AnalyticsQueryRunRequest,
)
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal, B0IdentityRegistry
from backend.services.analytics.jobs import RunStore
from backend.services.analytics.resource_profile import B0ResourceProfile, B0_SMALL_FIXTURE_PROFILE
from backend.services.analytics.runtime import HostBridge, RunDispatcher, execute_native_fixture, execute_native_query
from backend.services.analytics.worker import WorkerManager


class NativeText(AnalyticsModel):
    type: Literal["text"]
    text: Annotated[str, Field(min_length=1, max_length=8000)]

    @field_validator("text")
    @classmethod
    def supported_text(cls, value):
        AnalyticsRunRequest(question=value)  # Keep the raw text for replay hashing.
        return value


class NativePrompt(AnalyticsModel):
    requestId: OpaqueId
    sessionId: OpaqueId
    mode: Literal["queue"]
    content: Annotated[list[NativeText], Field(min_length=1, max_length=1)]
    clientTimeZone: Literal["UTC", "Asia/Shanghai"] = "Asia/Shanghai"


class NativeStep(AnalyticsModel):
    session_id: OpaqueId
    request_id: OpaqueId
    call_id: OpaqueId
    query: Literal["channel_repeat_rate"]


class NativeContextRequest(AnalyticsModel):
    session_id: OpaqueId
    request_id: OpaqueId
    unit_id: OpaqueId
    package_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    resource: Literal["SKILL.md", "references/evidence-policy.md", "assets/result-example.json"] | None = None


class QueryNativeStep(AnalyticsModel):
    session_id: OpaqueId
    request_id: OpaqueId
    call_id: OpaqueId
    request: ChannelFollowupQueryRequest


def _attach_lifecycle(app, dispatcher):
    @asynccontextmanager
    async def lifecycle(_app):
        dispatcher.start()
        stopping = asyncio.Event()

        async def loop():
            while not stopping.is_set():
                await run_in_threadpool(dispatcher.tick)
                try:
                    await asyncio.wait_for(stopping.wait(), timeout=0.15)
                except TimeoutError:
                    pass

        task = asyncio.create_task(loop())
        try:
            yield
        finally:
            stopping.set()
            try:
                await task
            finally:
                dispatcher.close()

    app.router.lifespan_context = lifecycle


def _query_runtime_app(config, *, bridge=None):
    session_ids = config.get("session_ids")
    if (not isinstance(session_ids, list) or len(session_ids) != 2 or len(set(session_ids)) != 2
            or any(not isinstance(item, str) or not item for item in session_ids)):
        raise ValueError("query-mode requires exactly two registered sessions")
    runtime_token, gateway_token = config["runtime_token"], config["gateway_token"]
    if len(runtime_token) < 32 or len(gateway_token) < 32 or runtime_token == gateway_token:
        raise ValueError("separate explicit local capabilities required")
    method_digest = config.get("method_package_digest")
    if method_digest is None:
        raise ValueError("explicit fixed method package digest required")
    registry = B0IdentityRegistry()
    actor = AnalyticsPrincipal(
        "b0-synthetic-owner",
        frozenset({"run:create", "run:read", "run:cancel"}),
        frozenset({"channel-followup-fixture"}),
    )
    registry.grant(gateway_token, actor)

    def resolve_actor(owner):
        try:
            current = registry.resolve("Bearer " + gateway_token)
            return current if current.actor_id == owner else None
        except AnalyticsError:
            return None

    store = RunStore(Path(config["state_dir"]), B0ResourceProfile(**B0_SMALL_FIXTURE_PROFILE),
                     family=QUERY_RUN_FAMILY)
    conversations = {}
    for index, session_id in enumerate(session_ids):
        conversations[session_id] = store.create_conversation(
            actor, f"native-query-{index}", AnalyticsQueryConversationRequest(),
            runtime_session_id=session_id,
        )
    fixture = ChannelFollowupFixture(**config["fixture"])
    fixture.validate()
    descriptor = fixture.binding_descriptor()
    workers = WorkerManager(store, resolve_actor, fixture)
    dispatcher = RunDispatcher(store, resolve_actor, bridge or HostBridge("http://127.0.0.1:4316", runtime_token),
                               workers=workers)
    mapping = {session_id: conv.conversation_id for session_id, conv in conversations.items()}
    app = create_query_app(store, registry, runtime_ready=lambda: dispatcher.ready,
                           session_conversations=mapping)
    _attach_lifecycle(app, dispatcher)
    app.state.dispatcher, app.state.store, app.state.registry, app.state.workers = dispatcher, store, registry, workers
    app.state.session_ids = tuple(session_ids)

    def gateway_actor(request):
        return registry.resolve(_single_header(request, "authorization"))

    def runtime_identity(request, requested_session):
        credential = _single_header(request, "authorization")
        if not credential or not secrets.compare_digest(credential, "Bearer " + runtime_token):
            raise AnalyticsError(401, "UNAUTHENTICATED", "需要运行时能力。")
        if requested_session not in conversations:
            raise AnalyticsError(404, "NOT_FOUND", "原生会话不存在或不可见。")

    @app.post("/internal/native/run-context", include_in_schema=False)
    def run_context(payload: NativeContextRequest, request: Request):
        runtime_identity(request, payload.session_id)
        if payload.package_digest != method_digest:
            raise AnalyticsError(409, "METHOD_VERSION_MISMATCH", "方法包版本未绑定或发生变化。")
        matches = store.runtime_work(session_id=payload.session_id, request_id=payload.request_id)
        if len(matches) != 1:
            raise AnalyticsError(409, "UNBOUND_NATIVE_REQUEST", "当前原生请求没有已登记的任务绑定。")
        work = matches[0]
        principal = resolve_actor(work["owner"])
        if principal is None:
            raise AnalyticsError(403, "FORBIDDEN", "当前任务身份已失效。")
        state = store.rebuild_context(principal, work["intent"].run_id, work["intent"].attempt_id,
                                      package_digest=method_digest, unit_id=payload.unit_id, resource=payload.resource)
        return {**state, "session_id": payload.session_id, "request_id": payload.request_id}

    @app.get("/internal/native/context", include_in_schema=False)
    def context(request: Request):
        principal = gateway_actor(request)
        session_id = _single_header(request, "x-runtime-session-id")
        if session_id not in conversations:
            raise AnalyticsError(404, "NOT_FOUND", "原生会话不存在或不可见。")
        conv = conversations[session_id]
        return {"conversation": store.get_conversation(principal, conv.conversation_id).model_dump(mode="json"),
                "session_id": session_id, "registered_sessions": list(session_ids), "ready": dispatcher.ready}

    @app.post("/internal/native/prompt", status_code=202, include_in_schema=False)
    def prompt(payload: AnalyticsQueryNativePrompt, request: Request):
        principal = gateway_actor(request)
        if payload.sessionId not in conversations:
            raise AnalyticsError(404, "NOT_FOUND", "原生会话不存在或不可见。")
        conv = conversations[payload.sessionId]
        run = AnalyticsQueryRunRequest(question=payload.content[0].text)
        return store.accept(principal, conv.conversation_id, payload.requestId, run,
                            allow_new=dispatcher.ready, native_request=payload.model_dump(mode="json"),
                            method_package_digest=method_digest, fixture_descriptor=descriptor)

    @app.post("/internal/native/channel-followup", include_in_schema=False)
    def channel_followup(payload: QueryNativeStep, request: Request):
        runtime_identity(request, payload.session_id)
        return execute_native_query(store, resolve_actor, payload.session_id, payload.request_id, payload.call_id,
                                    payload.request, workers=workers)

    return app


def runtime_app(config, *, bridge=None):
    family = config.get("family", "b0")
    if family == QUERY_RUN_FAMILY:
        return _query_runtime_app(config, bridge=bridge)
    if family != "b0":
        raise ValueError("unsupported runtime family")
    session_id = config["session_id"]
    runtime_token, gateway_token = config["runtime_token"], config["gateway_token"]
    if len(runtime_token) < 32 or len(gateway_token) < 32 or runtime_token == gateway_token:
        raise ValueError("separate explicit local capabilities required")
    registry = B0IdentityRegistry()
    actor = AnalyticsPrincipal("b0-synthetic-owner", frozenset({"run:create", "run:read", "run:cancel"}), frozenset({"b0-fixture"}))
    registry.grant(gateway_token, actor)

    def resolve_actor(owner):
        try:
            current = registry.resolve("Bearer " + gateway_token)
            return current if current.actor_id == owner else None
        except AnalyticsError:
            return None

    store = RunStore(Path(config["state_dir"]), B0ResourceProfile(**B0_SMALL_FIXTURE_PROFILE))
    conv = store.create_conversation(actor, "native-primary", AnalyticsConversationRequest(), runtime_session_id=session_id)
    workers = WorkerManager(store, resolve_actor, SyntheticFixture(**config["fixture"]))
    dispatcher = RunDispatcher(store, resolve_actor, bridge or HostBridge("http://127.0.0.1:4316", runtime_token), workers=workers)
    app = create_app(store, registry, runtime_ready=lambda: dispatcher.ready, runtime_conversation_id=conv.conversation_id)

    @asynccontextmanager
    async def lifecycle(_app):
        dispatcher.start()
        stopping = asyncio.Event()

        async def loop():
            while not stopping.is_set():
                await run_in_threadpool(dispatcher.tick)
                try:
                    await asyncio.wait_for(stopping.wait(), timeout=0.15)
                except TimeoutError:
                    pass

        task = asyncio.create_task(loop())
        try:
            yield
        finally:
            stopping.set()
            try:
                await task
            finally:
                dispatcher.close()

    app.router.lifespan_context = lifecycle
    app.state.dispatcher, app.state.store, app.state.registry, app.state.workers = dispatcher, store, registry, workers

    def gateway_actor(request):
        return registry.resolve(_single_header(request, "authorization"))

    def runtime_identity(request, requested_session):
        credential = _single_header(request, "authorization")
        if not credential or not secrets.compare_digest(credential, "Bearer " + runtime_token):
            raise AnalyticsError(401, "UNAUTHENTICATED", "需要运行时能力。")
        if requested_session != session_id:
            raise AnalyticsError(404, "NOT_FOUND", "原生会话不存在或不可见。")

    @app.post("/internal/native/run-context", include_in_schema=False)
    def run_context(payload: NativeContextRequest, request: Request):
        runtime_identity(request, payload.session_id)
        expected = config.get("method_package_digest")
        if expected is None or payload.package_digest != expected:
            raise AnalyticsError(409, "METHOD_VERSION_MISMATCH", "方法包版本未绑定或发生变化。")
        matches = store.runtime_work(session_id=payload.session_id, request_id=payload.request_id)
        if len(matches) != 1:
            raise AnalyticsError(409, "UNBOUND_NATIVE_REQUEST", "当前原生请求没有已登记的任务绑定。")
        work = matches[0]
        principal = resolve_actor(work["owner"])
        if principal is None:
            raise AnalyticsError(403, "FORBIDDEN", "当前任务身份已失效。")
        state = store.rebuild_context(principal, work["intent"].run_id, work["intent"].attempt_id,
                                      package_digest=expected, unit_id=payload.unit_id, resource=payload.resource)
        return {**state, "session_id": payload.session_id, "request_id": payload.request_id}

    @app.get("/internal/native/context", include_in_schema=False)
    def context(request: Request):
        principal = gateway_actor(request)
        return {"conversation": store.get_conversation(principal, conv.conversation_id).model_dump(mode="json"),
                "session_id": session_id, "ready": dispatcher.ready}

    @app.post("/internal/native/prompt", status_code=202, include_in_schema=False)
    def prompt(payload: NativePrompt, request: Request):
        principal = gateway_actor(request)
        if payload.sessionId != session_id:
            raise AnalyticsError(404, "NOT_FOUND", "原生会话不存在或不可见。")
        run = AnalyticsRunRequest(question=payload.content[0].text)
        return store.accept(principal, conv.conversation_id, payload.requestId, run,
                            allow_new=dispatcher.ready, native_request=payload.model_dump(),
                            method_package_digest=config.get("method_package_digest"))

    @app.post("/internal/native/fixture", include_in_schema=False)
    def fixture(payload: NativeStep, request: Request):
        runtime_identity(request, payload.session_id)
        return execute_native_fixture(store, resolve_actor, payload.session_id, payload.request_id, payload.call_id, payload.query, workers=workers)

    return app


if __name__ == "__main__":
    if sys.version_info < (3, 14):
        raise SystemExit("B0 requires Python 3.14+")
    import uvicorn
    setup = json.loads(sys.stdin.readline(65537))
    uvicorn.run(runtime_app(setup), host="127.0.0.1", port=4315, access_log=False, log_level="warning",
                loop="asyncio", http="h11", ws="none")
