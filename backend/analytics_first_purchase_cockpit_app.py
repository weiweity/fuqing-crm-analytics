"""Opt-in first-purchase cockpit HTTP. No application at import.

Reads/writes do not start runs, workers or models. OpenAPI generation opens no DB.
Preview never writes. Add binds FirstPurchaseSavedAnalysisStore.get, never caller facts.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi

from backend.analytics_app import KEY_HEADER, _BodyLimit, _error_response, _single_header
from backend.contracts.analytics import AnalyticsErrorResponse
from backend.contracts.analytics_first_purchase_cockpit import (
    DASHBOARD_SCHEMA,
    FirstPurchaseCockpitCreateRequest,
    FirstPurchaseCockpitOp,
    FirstPurchaseDashboard,
    FirstPurchaseDashboardList,
    FirstPurchaseDashboardListItem,
    HTTP_API_CONNECTED,
)
from backend.contracts.analytics_first_purchase_run import FIRST_PURCHASE_HTTP_PREFIX
from backend.services.analytics.access import AnalyticsError, B0IdentityRegistry
from backend.services.analytics.first_purchase.asset_state import validate_key
from backend.services.analytics.first_purchase.cockpit import FirstPurchaseCockpitRecord, FirstPurchaseCockpitStore
from backend.services.analytics.first_purchase.cockpit_source import authorize_http_op, project_dashboard
from backend.services.analytics.first_purchase.saved import FirstPurchaseSavedAnalysisStore

PREFIX = FIRST_PURCHASE_HTTP_PREFIX + "/dashboards"
VERSION_HEADER = {
    "name": "If-Match", "in": "header", "required": True,
    "schema": {"type": "string", "pattern": "^[1-9][0-9]{0,15}$"},
}


def _if_match(request: Request) -> str:
    raw = _single_header(request, "if-match")
    if raw is None:
        raise AnalyticsError(428, "IF_MATCH_REQUIRED", "预览和保存需要最近一次 GET 返回的版本号。")
    if not re.fullmatch(r"[1-9][0-9]{0,15}", raw):
        raise AnalyticsError(400, "INVALID_VERSION", "If-Match 必须是正整数字符串。")
    return raw


def http_dashboard(
    record: FirstPurchaseCockpitRecord, analysis_store: FirstPurchaseSavedAnalysisStore, actor, *,
    base_version: int,
) -> FirstPurchaseDashboard:
    payload = project_dashboard(analysis_store, actor, record.as_dict(), base_version=base_version)
    payload["http_api"] = HTTP_API_CONNECTED
    return FirstPurchaseDashboard.model_validate(payload)


def http_list_item(item: dict) -> FirstPurchaseDashboardListItem:
    payload = dict(item)
    payload["http_api"] = HTTP_API_CONNECTED
    return FirstPurchaseDashboardListItem.model_validate(payload)


def create_first_purchase_cockpit_app(
    analysis_store: FirstPurchaseSavedAnalysisStore | None = None,
    cockpit_store: FirstPurchaseCockpitStore | None = None,
    identities: B0IdentityRegistry | None = None,
    *,
    runtime_ready: Callable[[], bool] | None = None,
) -> FastAPI:
    app = FastAPI(title="Shine Mage First-Purchase Cockpit", version=DASHBOARD_SCHEMA,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(_BodyLimit)
    registry = identities or B0IdentityRegistry()

    def principal(request: Request):
        return registry.resolve(_single_header(request, "authorization"))

    def analyses() -> FirstPurchaseSavedAnalysisStore:
        if analysis_store is None:
            raise AnalyticsError(503, "ANALYSIS_NOT_CONFIGURED", "分析资产库尚未显式配置。")
        return analysis_store

    def boards() -> FirstPurchaseCockpitStore:
        if cockpit_store is None:
            raise AnalyticsError(503, "COCKPIT_NOT_CONFIGURED", "驾驶舱资产库尚未显式配置。")
        return cockpit_store

    def patch_for(actor, payload: FirstPurchaseCockpitOp, dashboard_id: str, if_match: str) -> dict:
        return authorize_http_op(analyses(), boards(), actor, dashboard_id, payload, if_match)

    @app.exception_handler(AnalyticsError)
    async def analytics_error(request: Request, error: AnalyticsError):
        return _error_response(error, request.state.analytics_request_id)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, _error: RequestValidationError):
        return _error_response(
            AnalyticsError(422, "INVALID_REQUEST", "请求与当前驾驶舱合同不匹配，请检查版本、字段和取值。"),
            request.state.analytics_request_id,
        )

    @app.exception_handler(sqlite3.DatabaseError)
    async def state_error(request: Request, _error: sqlite3.DatabaseError):
        return _error_response(
            AnalyticsError(503, "STATE_UNAVAILABLE", "驾驶舱状态暂不可用，请使用原请求标识查询或重试。", retryable=True),
            request.state.analytics_request_id,
        )

    errors = {code: {"model": AnalyticsErrorResponse} for code in (400, 401, 403, 404, 409, 410, 413, 422, 428, 429, 503)}
    created = {
        200: {"model": FirstPurchaseDashboard, "description": "Owner already has a private dashboard."},
        201: {"model": FirstPurchaseDashboard, "description": "Created the owner's private dashboard."},
    }

    @app.post(PREFIX, response_model=FirstPurchaseDashboard,
              operation_id="analytics_first_purchase_dashboard_create", responses={**created, **errors},
              openapi_extra={"parameters": [KEY_HEADER]})
    def create_dashboard(payload: FirstPurchaseCockpitCreateRequest, request: Request, response: Response):
        actor = principal(request)
        body = {} if payload.title is None else {"title": payload.title}
        record, status = boards().acquire(actor, validate_key(_single_header(request, "idempotency-key")), body)
        document = http_dashboard(record, analyses(), actor, base_version=record.version)
        response.status_code = status
        response.headers.update({
            "cache-control": "no-store",
            "etag": str(document.version),
            "location": f"{PREFIX}/{document.dashboard_id}",
        })
        return document

    @app.get(PREFIX, response_model=FirstPurchaseDashboardList,
             operation_id="analytics_first_purchase_dashboard_list", responses=errors)
    def list_dashboards(request: Request, response: Response):
        actor = principal(request)
        items = [http_list_item(row) for row in boards().list(actor)]
        response.headers["cache-control"] = "no-store"
        return FirstPurchaseDashboardList(items=items)

    @app.get(PREFIX + "/{dashboard_id}", response_model=FirstPurchaseDashboard,
             operation_id="analytics_first_purchase_dashboard_get", responses=errors)
    def get_dashboard(dashboard_id: str, request: Request, response: Response):
        actor = principal(request)
        record = boards().get(actor, dashboard_id)
        document = http_dashboard(record, analyses(), actor, base_version=record.version)
        response.headers.update({"cache-control": "no-store", "etag": str(document.version)})
        return document

    @app.post(PREFIX + "/{dashboard_id}/preview", response_model=FirstPurchaseDashboard,
              operation_id="analytics_first_purchase_dashboard_preview", responses=errors,
              openapi_extra={"parameters": [VERSION_HEADER]})
    def preview_dashboard(dashboard_id: str, payload: FirstPurchaseCockpitOp, request: Request, response: Response):
        actor = principal(request)
        match = _if_match(request)
        record = boards().preview(actor, dashboard_id, patch_for(actor, payload, dashboard_id, match), if_match=match)
        document = http_dashboard(record, analyses(), actor, base_version=int(match))
        response.headers.update({"cache-control": "no-store", "etag": str(record.version)})
        return document

    @app.post(PREFIX + "/{dashboard_id}/versions", status_code=201, response_model=FirstPurchaseDashboard,
              operation_id="analytics_first_purchase_dashboard_apply", responses=errors,
              openapi_extra={"parameters": [KEY_HEADER, VERSION_HEADER]})
    def apply_dashboard(dashboard_id: str, payload: FirstPurchaseCockpitOp, request: Request, response: Response):
        actor = principal(request)
        match = _if_match(request)
        record = boards().apply(
            actor, validate_key(_single_header(request, "idempotency-key")),
            dashboard_id, match, patch_for(actor, payload, dashboard_id, match),
        )
        document = http_dashboard(record, analyses(), actor, base_version=int(match))
        response.headers.update({"cache-control": "no-store", "etag": str(document.version)})
        return document

    def openapi():
        if app.openapi_schema is None:
            schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
            schema.setdefault("components", {}).setdefault("securitySchemes", {})["CockpitBearer"] = {
                "type": "http", "scheme": "bearer",
                "description": "Explicit local first-purchase cockpit identity; not CRM auth.",
            }
            schema["security"] = [{"CockpitBearer": []}]
            schema["x-cockpit-http"] = True
            schema["x-first-purchase-cockpit-http"] = True
            schema["x-not-b0-run-kernel"] = True
            schema["x-query-session-fence"] = False
            schema["x-saved-analysis-http"] = False
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi
    app.state.runtime_ready = runtime_ready
    return app
