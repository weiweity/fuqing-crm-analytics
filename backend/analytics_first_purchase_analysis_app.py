"""Opt-in first-purchase saved-analysis HTTP. No application at import.

Reads/writes do not start runs, workers or models. OpenAPI generation opens no DB.
Minimal save interface for a Claude query card: POST created_from_run_id + title.
Card buttons and plugin root registration are out of this track.
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
from backend.contracts.analytics_first_purchase_analysis import (
    ANALYSIS_SCHEMA,
    FirstPurchaseAnalysisCreateRequest,
    FirstPurchaseAnalysisTitleRequest,
    FirstPurchaseSavedAnalysis,
    FirstPurchaseSavedAnalysisList,
    FirstPurchaseSavedAnalysisListItem,
    HTTP_API_CONNECTED,
)
from backend.contracts.analytics_first_purchase_run import FIRST_PURCHASE_HTTP_PREFIX
from backend.services.analytics.access import AnalyticsError, B0IdentityRegistry
from backend.services.analytics.first_purchase.asset_state import validate_key
from backend.services.analytics.first_purchase.saved import (
    FirstPurchaseSavedAnalysisRecord,
    FirstPurchaseSavedAnalysisStore,
)
from backend.services.analytics.first_purchase.source import resolve_trusted_first_purchase_source
from backend.services.analytics.jobs import RunStore

PREFIX = FIRST_PURCHASE_HTTP_PREFIX + "/analyses"
VERSION_HEADER = {
    "name": "If-Match", "in": "header", "required": True,
    "schema": {"type": "string", "pattern": "^[1-9][0-9]{0,15}$"},
}


def _analysis_version(request: Request) -> int:
    raw = _single_header(request, "if-match")
    if raw is None:
        raise AnalyticsError(428, "IF_MATCH_REQUIRED", "改标题需要最近一次 GET 返回的版本号。")
    if not re.fullmatch(r"[1-9][0-9]{0,15}", raw):
        raise AnalyticsError(400, "INVALID_VERSION", "If-Match 必须是正整数字符串。")
    return int(raw)


def http_analysis_document(record: FirstPurchaseSavedAnalysisRecord) -> FirstPurchaseSavedAnalysis:
    payload = record.as_dict()
    payload["http_api"] = HTTP_API_CONNECTED
    return FirstPurchaseSavedAnalysis.model_validate(payload)


def http_list_item(item: dict) -> FirstPurchaseSavedAnalysisListItem:
    payload = dict(item)
    payload["http_api"] = HTTP_API_CONNECTED
    return FirstPurchaseSavedAnalysisListItem.model_validate(payload)


def create_first_purchase_analysis_app(
    run_store: RunStore | None = None,
    analysis_store: FirstPurchaseSavedAnalysisStore | None = None,
    identities: B0IdentityRegistry | None = None,
    *,
    runtime_ready: Callable[[], bool] | None = None,
) -> FastAPI:
    app = FastAPI(title="Shine Mage First-Purchase Saved Analysis", version=ANALYSIS_SCHEMA,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(_BodyLimit)
    registry = identities or B0IdentityRegistry()

    def principal(request: Request):
        return registry.resolve(_single_header(request, "authorization"))

    def runs() -> RunStore:
        if run_store is None:
            raise AnalyticsError(503, "KERNEL_NOT_CONFIGURED", "查询任务内核尚未显式配置。")
        return run_store

    def analyses() -> FirstPurchaseSavedAnalysisStore:
        if analysis_store is None:
            raise AnalyticsError(503, "ANALYSIS_NOT_CONFIGURED", "分析资产库尚未显式配置。")
        return analysis_store

    @app.exception_handler(AnalyticsError)
    async def analytics_error(request: Request, error: AnalyticsError):
        return _error_response(error, request.state.analytics_request_id)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, _error: RequestValidationError):
        return _error_response(
            AnalyticsError(422, "INVALID_REQUEST", "请求与当前分析合同不匹配，请检查版本、字段和取值。"),
            request.state.analytics_request_id,
        )

    @app.exception_handler(sqlite3.DatabaseError)
    async def state_error(request: Request, _error: sqlite3.DatabaseError):
        return _error_response(
            AnalyticsError(503, "STATE_UNAVAILABLE", "分析状态暂不可用，请使用原请求标识查询或重试。", retryable=True),
            request.state.analytics_request_id,
        )

    errors = {code: {"model": AnalyticsErrorResponse} for code in (400, 401, 403, 404, 409, 410, 413, 422, 428, 429, 503)}

    @app.post(PREFIX, status_code=201, response_model=FirstPurchaseSavedAnalysis,
              operation_id="analytics_first_purchase_analysis_create", responses=errors,
              openapi_extra={"parameters": [KEY_HEADER]})
    def create_analysis(payload: FirstPurchaseAnalysisCreateRequest, request: Request, response: Response):
        actor = principal(request)
        visual = None if payload.visual_spec is None else payload.visual_spec.model_dump(mode="json")
        trusted = resolve_trusted_first_purchase_source(runs(), actor, payload.created_from_run_id)
        record = analyses().save_from_trusted_source(
            actor, validate_key(_single_header(request, "idempotency-key")),
            title=payload.title, visual_spec=visual, trusted=trusted,
        )
        document = http_analysis_document(record)
        response.headers.update({
            "cache-control": "no-store",
            "etag": str(document.version),
            "location": f"{PREFIX}/{document.analysis_id}",
        })
        return document

    @app.get(PREFIX, response_model=FirstPurchaseSavedAnalysisList,
             operation_id="analytics_first_purchase_analysis_list", responses=errors)
    def list_analyses(request: Request, response: Response):
        actor = principal(request)
        items = [http_list_item(row) for row in analyses().list(actor)]
        response.headers["cache-control"] = "no-store"
        return FirstPurchaseSavedAnalysisList(items=items)

    @app.get(PREFIX + "/{analysis_id}", response_model=FirstPurchaseSavedAnalysis,
             operation_id="analytics_first_purchase_analysis_get", responses=errors)
    def get_analysis(analysis_id: str, request: Request, response: Response, version: int | None = None):
        actor = principal(request)
        record = analyses().get(actor, analysis_id, version)
        document = http_analysis_document(record)
        response.headers.update({"cache-control": "no-store", "etag": str(document.version)})
        return document

    @app.post(PREFIX + "/{analysis_id}/versions", status_code=201, response_model=FirstPurchaseSavedAnalysis,
              operation_id="analytics_first_purchase_analysis_publish_title", responses=errors,
              openapi_extra={"parameters": [KEY_HEADER, VERSION_HEADER]})
    def publish_title(analysis_id: str, payload: FirstPurchaseAnalysisTitleRequest, request: Request, response: Response):
        actor = principal(request)
        record = analyses().publish_version(
            actor, validate_key(_single_header(request, "idempotency-key")), analysis_id,
            base_version=_analysis_version(request), title=payload.title,
        )
        document = http_analysis_document(record)
        response.headers.update({"cache-control": "no-store", "etag": str(document.version)})
        return document

    def openapi():
        if app.openapi_schema is None:
            schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
            schema.setdefault("components", {}).setdefault("securitySchemes", {})["AnalysisBearer"] = {
                "type": "http", "scheme": "bearer",
                "description": "Explicit local first-purchase analysis identity; not CRM auth.",
            }
            schema["security"] = [{"AnalysisBearer": []}]
            schema["x-saved-analysis-http"] = True
            schema["x-first-purchase-saved-analysis-http"] = True
            schema["x-not-b0-run-kernel"] = True
            schema["x-query-session-fence"] = False
            schema["x-shared-succeeded-source"] = True
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi
    app.state.runtime_ready = runtime_ready
    return app
