"""First-purchase native routes over shared RunStore/dispatcher. No second ledger."""

from __future__ import annotations

from backend.services.analytics.runtime_ports import bridge_origin

import asyncio
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import Field
from starlette.concurrency import run_in_threadpool

from backend.analytics_app import _single_header
from backend.analytics_first_purchase_analysis_app import create_first_purchase_analysis_app
from backend.analytics_first_purchase_app import create_first_purchase_app
from backend.analytics_first_purchase_cockpit_app import create_first_purchase_cockpit_app
from backend.analytics_first_purchase_fixture import create_first_purchase_fixture
from backend.contracts.analytics import AnalyticsCancelRequest, AnalyticsModel, OpaqueId
from backend.contracts.analytics_first_purchase import FirstPurchaseQueryRequest
from backend.contracts.analytics_first_purchase_kernel import (
    FirstPurchaseConversationRequest,
    FirstPurchaseKernelRequest,
    FirstPurchaseNativePrompt,
)
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal, B0IdentityRegistry
from backend.services.analytics.first_purchase.cockpit import FirstPurchaseCockpitStore
from backend.services.analytics.first_purchase.runtime import FirstPurchaseRuntime
from backend.services.analytics.first_purchase.saved import FirstPurchaseSavedAnalysisStore
from backend.services.analytics.jobs import RunStore, validate_key
from backend.services.analytics.resource_profile import B0ResourceProfile, B0_SMALL_FIXTURE_PROFILE
from backend.services.analytics.runtime import HostBridge, RunDispatcher, execute_native_first_purchase
from backend.services.analytics.worker import WorkerManager

QUERY_CAPABILITIES = frozenset({"run:create", "run:read", "run:cancel"})
ASSET_CAPABILITIES = frozenset({
    "analysis:save", "analysis:read", "dashboard:read", "dashboard:update",
})


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


class FirstPurchaseNativeContextRequest(AnalyticsModel):
    session_id: OpaqueId
    request_id: OpaqueId
    unit_id: OpaqueId
    package_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    resource: Literal["SKILL.md", "references/evidence-policy.md", "assets/result-example.json"] | None = None


class FirstPurchaseNativeStep(AnalyticsModel):
    session_id: OpaqueId
    request_id: OpaqueId
    call_id: OpaqueId
    request: FirstPurchaseQueryRequest


def _first_purchase_capabilities(config) -> frozenset[str]:
    extra = config.get("asset_capabilities")
    if extra is None:
        return QUERY_CAPABILITIES
    if not isinstance(extra, list) or not extra or set(extra) - ASSET_CAPABILITIES:
        raise ValueError("asset_capabilities must be an explicit analysis/dashboard subset")
    return QUERY_CAPABILITIES | frozenset(extra)


def _attach_first_purchase_assets(app, config, run_store, registry) -> None:
    analysis_dir = config.get("analysis_dir")
    cockpit_dir = config.get("cockpit_dir")
    if not isinstance(analysis_dir, str) or not analysis_dir.strip() or not isinstance(cockpit_dir, str) or not cockpit_dir.strip():
        raise ValueError("asset_capabilities require analysis_dir and cockpit_dir")
    analysis_store = FirstPurchaseSavedAnalysisStore(Path(analysis_dir))
    cockpit_store = FirstPurchaseCockpitStore(Path(cockpit_dir))
    analysis_app = create_first_purchase_analysis_app(
        run_store, analysis_store, registry, runtime_ready=app.state.runtime_ready,
    )
    cockpit_app = create_first_purchase_cockpit_app(
        analysis_store, cockpit_store, registry, runtime_ready=app.state.runtime_ready,
    )
    app.router.routes.extend(analysis_app.router.routes)
    app.router.routes.extend(cockpit_app.router.routes)
    app.state.analysis_store = analysis_store
    app.state.cockpit_store = cockpit_store


def create_first_purchase_native_app(config, *, bridge=None):
    runtime_token, gateway_token = config["runtime_token"], config["gateway_token"]
    if len(runtime_token) < 32 or len(gateway_token) < 32 or runtime_token == gateway_token:
        raise ValueError("separate explicit local capabilities required")
    session_id = config["session_id"]
    snapshot = config.get("snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("first-purchase native requires a server-owned snapshot")
    method_digest = config.get("method_package_digest")
    if not isinstance(method_digest, str) or len(method_digest) != 64:
        raise ValueError("explicit method package digest required")
    state_dir = Path(config["state_dir"])
    registry = B0IdentityRegistry()
    actor = AnalyticsPrincipal(
        "synthetic-demo",
        _first_purchase_capabilities(config),
        frozenset({"first-purchase-fixture"}),
    )
    registry.grant(gateway_token, actor)

    def resolve_actor(owner):
        try:
            current = registry.resolve("Bearer " + gateway_token)
            return current if current.actor_id == owner else None
        except AnalyticsError:
            return None

    fixture = create_first_purchase_fixture(snapshot)
    store = RunStore(state_dir, B0ResourceProfile(**B0_SMALL_FIXTURE_PROFILE), family="first_purchase")
    conv = store.create_conversation(
        actor, "native-first-purchase", FirstPurchaseConversationRequest(),
        runtime_session_id=session_id,
    )
    descriptor = fixture.binding_descriptor()
    workers = WorkerManager(store, resolve_actor, fixture)
    dispatcher = RunDispatcher(
        store, resolve_actor, bridge or HostBridge(bridge_origin(config), runtime_token),
        workers=workers,
    )
    runtime = FirstPurchaseRuntime(store, fixture, resolve_actor)
    app = create_first_purchase_app(runtime, registry, runtime_ready=lambda: dispatcher.ready)
    _attach_lifecycle(app, dispatcher)
    app.state.dispatcher = dispatcher
    app.state.store = store
    app.state.registry = registry
    app.state.workers = workers
    app.state.runtime = runtime
    app.state.session_id = session_id

    def gateway_actor(request: Request):
        return registry.resolve(_single_header(request, "authorization"))

    def runtime_identity(request: Request, requested: str) -> None:
        credential = _single_header(request, "authorization")
        if not credential or not secrets.compare_digest(credential, "Bearer " + runtime_token):
            raise AnalyticsError(401, "UNAUTHENTICATED", "需要运行时能力。")
        if requested != session_id:
            raise AnalyticsError(404, "NOT_FOUND", "原生会话不存在或不可见。")

    @app.post("/internal/native/run-context", include_in_schema=False)
    def run_context(payload: FirstPurchaseNativeContextRequest, request: Request):
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
        state = store.rebuild_context(
            principal, work["intent"].run_id, work["intent"].attempt_id,
            package_digest=method_digest, unit_id=payload.unit_id, resource=payload.resource,
        )
        return {**state, "session_id": payload.session_id, "request_id": payload.request_id}

    @app.get("/internal/native/context", include_in_schema=False)
    def context(request: Request):
        principal = gateway_actor(request)
        return {
            "conversation": store.get_conversation(principal, conv.conversation_id).model_dump(mode="json"),
            "session_id": session_id,
            "ready": dispatcher.ready,
            "family": "first_purchase",
        }

    @app.post("/internal/native/prompt", status_code=202, include_in_schema=False)
    def prompt(payload: FirstPurchaseNativePrompt, request: Request):
        principal = gateway_actor(request)
        if payload.sessionId != session_id:
            raise AnalyticsError(404, "NOT_FOUND", "原生会话不存在或不可见。")
        run = FirstPurchaseKernelRequest(question=payload.content[0].text)
        return store.accept(
            principal, conv.conversation_id, payload.requestId, run,
            allow_new=dispatcher.ready, native_request=payload.model_dump(mode="json"),
            method_package_digest=method_digest, fixture_descriptor=descriptor,
        )

    @app.post("/internal/native/first-purchase", include_in_schema=False)
    def native_step(payload: FirstPurchaseNativeStep, request: Request):
        runtime_identity(request, payload.session_id)
        dumped = payload.model_dump(mode="json")
        for banned in ("owner", "permission_scope", "result", "facts", "actor_id"):
            if banned in dumped:
                raise AnalyticsError(422, "INVALID_REQUEST", "请求与当前查询合同不匹配，请检查版本、字段和取值。")
        status, receipt = execute_native_first_purchase(
            store, resolve_actor, payload.session_id, payload.request_id, payload.call_id,
            payload.request, workers=workers,
        )
        return JSONResponse(status_code=status, content=receipt)

    @app.post("/internal/native/first-purchase/cancel", include_in_schema=False)
    def native_cancel(payload: dict, request: Request):
        principal = gateway_actor(request)
        run_id = payload.get("run_id") if isinstance(payload, dict) else None
        request_id = payload.get("request_id") if isinstance(payload, dict) else None
        matches = []
        if isinstance(request_id, str) and request_id:
            matches = store.runtime_work(session_id=session_id, request_id=request_id)
        if isinstance(run_id, str) and run_id:
            owned = store.get_conversation(principal, conv.conversation_id).run_ids
            if run_id not in owned:
                raise AnalyticsError(404, "NOT_FOUND", "任务不存在或当前身份不可见。")
            current = runtime.get(principal, run_id)
        elif len(matches) == 1:
            current = runtime.get(principal, matches[0]["intent"].run_id)
        else:
            raise AnalyticsError(409, "NO_ACTIVE_RUN", "没有可取消的活动任务；未声明已停止。")
        if current.status in {"SUCCEEDED", "FAILED", "CANCELLED", "NEEDS_INPUT"} and current.diagnostics.execution_active:
            raise AnalyticsError(409, "WORKER_ACTIVE", "查询执行尚未确认退出，不能宣称为已停止。")
        if current.status not in {"QUEUED", "RUNNING", "CANCELLING"} and not current.diagnostics.execution_active:
            raise AnalyticsError(409, "NO_ACTIVE_RUN", "没有可取消的活动任务；未声明已停止。")
        return runtime.cancel(
            principal, current.run_id, validate_key(_single_header(request, "idempotency-key")),
            current.version, AnalyticsCancelRequest(),
        )

    if config.get("asset_capabilities") is not None:
        _attach_first_purchase_assets(app, config, store, registry)
    return app
