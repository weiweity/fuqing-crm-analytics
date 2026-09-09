"""Query routing middleware for Sprint 201 R1 read/write splitting."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.services.dual_conn import (
    READ_ACQUIRE_TIMEOUT_SECONDS,
    async_read_request_context,
    reset_query_type,
    set_query_type,
)
from backend.services.query_metrics import record_query

logger = logging.getLogger(__name__)

DOC_T03 = "docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T03"
DOC_T06 = "docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T06"
DOC_T07 = "docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T07"
DOC_T08 = "docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T08"
ERROR_SCHEMA = "competition-error/v1"
ERROR_MAPS_TO = "backend.contracts.analytics.AnalyticsErrorDetail"


def new_request_id(explicit: str | None = None) -> str:
    """Return a C0 request_id (1–128 chars)."""

    if explicit and 1 <= len(explicit) <= 128:
        return explicit
    return f"req_{uuid.uuid4().hex}"


def request_id_from_scope(scope: Scope) -> str:
    for key, value in scope.get("headers") or []:
        if key == b"x-request-id":
            try:
                return new_request_id(value.decode("utf-8"))
            except UnicodeDecodeError:
                break
    return new_request_id()


def competition_error_body(
    *,
    http_status: int,
    code: str,
    message: str,
    request_id: str,
    retryable: bool,
    param: str | None = None,
    retry_after: int | None = None,
    doc_ref: str | None = None,
    recovery_url: str | None = None,
) -> dict[str, Any]:
    """Build a C0 CompetitionErrorResponse payload (not FastAPI `{detail: ...}`)."""

    payload = {
        "error": {
            "schema_version": ERROR_SCHEMA,
            "code": code[:64],
            "message": message[:500] or "request failed",
            "param": param,
            "retryable": retryable,
            "retry_after": retry_after,
            "request_id": request_id[:128],
            "doc_ref": doc_ref,
            "recovery_url": recovery_url,
            "http_status": http_status,
            "maps_to": ERROR_MAPS_TO,
        }
    }
    from backend.contracts.competition_c0 import CompetitionErrorResponse

    return CompetitionErrorResponse.model_validate(payload).model_dump(mode="json")


def competition_error_response(
    *,
    http_status: int,
    code: str,
    message: str,
    request_id: str,
    retryable: bool,
    param: str | None = None,
    retry_after: int | None = None,
    doc_ref: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    response_headers = dict(headers or {})
    if retry_after is not None:
        response_headers.setdefault("Retry-After", str(retry_after))
    return JSONResponse(
        status_code=http_status,
        content=competition_error_body(
            http_status=http_status,
            code=code,
            message=message,
            request_id=request_id,
            retryable=retryable,
            param=param,
            retry_after=retry_after,
            doc_ref=doc_ref,
        ),
        headers=response_headers,
    )


def overlay_live_capabilities(
    actor_capabilities: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Map C0 SUPPORT_MATRIX onto live HTTP binds. Actor filter does not skip backend checks."""

    from backend.contracts.competition_c0 import SUPPORT_MATRIX, SupportStatus

    overlays: dict[str, dict[str, Any]] = {
        "diag.gsv": {
            "http_mapping": "GET|POST /api/v1/audience/summary",
            "notes": (
                "Bind requires explicit GSV. GMV is 422, not computed as GSV. "
                "period is forwarded to calculate_audience_summary(period=)."
            ),
        },
        "diag.yoy": {
            "http_mapping": "GET|POST /api/v1/audience/summary compare_start_date/compare_end_date",
        },
        "diag.last_week_same_weekday": {
            "http_mapping": "GET|POST /api/v1/audience/summary period=WTD",
            "notes": (
                "period=WTD is passed through; cutoff is PeriodBuilder Monday-1, "
                "not custom month-start-1."
            ),
        },
        "diag.promo_dual_window": {
            "http_mapping": "GET|POST /api/v1/audience/summary compare_start_date/compare_end_date",
        },
        "diag.product": {
            "http_mapping": (
                "GET|POST /api/v1/audience/summary product_ids; "
                "/api/v1/audience/table dimension=spu_*"
            ),
            "notes": (
                "product_ids is forwarded to calculate_audience_summary. "
                "Unknown/unimplemented filters 422 rather than drop."
            ),
        },
        "diag.sample_exclude_current": {
            "http_mapping": "exclude_channels on /audience/summary and /audience/table",
            "notes": (
                "exclude_channels is forwarded. GET /sampling/roi exclude_low_price=true "
                "is 422 (service has no implementation). Do not guess sample channel set."
            ),
        },
        "catalog.http": {
            "support_status": SupportStatus.PARTIAL.value,
            "http_mapping": "GET /api/v1/audience/capabilities",
            "notes": (
                "Live catalog is on audience.capabilities. "
                "GET /api/v1/analytics/catalog still needs Grok wiring in main.py. "
                "Actor filter does not replace backend checks."
            ),
        },
    }
    items: list[dict[str, Any]] = []
    grants = actor_capabilities
    for cap in SUPPORT_MATRIX:
        data = cap.model_dump(mode="json")
        extra = overlays.get(cap.capability_id)
        if extra:
            data.update({k: v for k, v in extra.items() if v is not None})
        required = set(data.get("required_capabilities") or [])
        if grants is not None and required and not required.issubset(grants):
            continue
        items.append(data)
    return items


class QueryRouterMiddleware:
    """Bind dashboard requests to read-only connections and record query metrics."""

    READ_ENDPOINTS = {
        "/api/v1/audience/summary",
        "/api/v1/audience/table",
        "/api/v1/audience/capabilities",
        "/api/v1/analytics/catalog",
        "/api/v1/category/overview",
        "/api/v1/category/distribution",
        "/api/v1/dq-report",
        "/api/v1/export-excel",
        "/api/v1/new-old-customer",
        "/api/v1/yoy-battle",
        "/api/v1/two-year-overview",
        "/api/v1/top-n",
        "/api/v1/rfm-repurchase",
        "/api/v1/channel-slice",
        "/api/v1/metrics/overview",
        "/api/v1/metrics/trend",
    }
    # API-04: only these POSTs may borrow the read pool. Do not treat every POST as read.
    READ_ONLY_POST_ENDPOINTS = {
        "/api/v1/audience/summary",
        "/api/v1/two-year-overview",
        "/api/v1/new-old-customer",
        "/api/v1/ad-hoc/two-year-overview",
        "/api/v1/ad-hoc/new-old-customer",
    }
    READ_PREFIXES = (
        "/api/v1/audience/",
        "/api/v1/assets/",
        "/api/v1/category/",
        "/api/v1/customer-health/",  # L4.69: RFM 显式 read_only prefix (治本 RFM 雪崩)
        "/api/v1/export/",
        "/api/v1/flow/",
        "/api/v1/health/",
        "/api/v1/lifetime-value/",
        "/api/v1/market-focus/",
        "/api/v1/metrics/",
        "/api/v1/report/",
        "/api/v1/rfm/",
        "/api/v1/sampling/",
        "/api/v1/visitor/",
        # Sprint 203 R9: /api/v1/geo/ + /api/v1/cohort-retention/ prefix 删除 (前端解耦)
    )
    WORKER_ENDPOINTS = {
        "/api/v1/ad-hoc/ai-sandbox-execute",
    }
    CONTROL_ENDPOINTS = {
        "/api/v1/health",
        "/api/v1/health/pool",
        "/metrics",
        "/openapi.json",
    }
    CONTROL_PREFIXES = (
        "/api/v1/auth/",
        # Mission owns its synthetic reader and SQLite state; borrowing a
        # legacy CRM connection here couples the demo to archived assets.
        "/api/v1/missions/",
        "/docs",
        "/redoc",
    )

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    def classify(self, path: str, method: str) -> str:
        """Classify a request as read, worker, or default.

        GET dashboard paths use the read pool. POST is admitted only via the
        exact read-only allowlist (audience/summary, two-year-overview,
        new-old-customer). Other POSTs keep the write-capable path.
        """

        method_u = method.upper()
        if path in self.CONTROL_ENDPOINTS or path.startswith(self.CONTROL_PREFIXES):
            return "default"
        if path in self.WORKER_ENDPOINTS:
            return "worker"
        if method_u == "GET":
            if path in self.READ_ENDPOINTS or path.startswith(self.READ_PREFIXES):
                return "read"
            if path.startswith("/api/v1/") and not path.startswith("/api/v1/auth/"):
                return "read"
            return "default"
        if method_u == "POST" and path in self.READ_ONLY_POST_ENDPOINTS:
            return "read"
        return "default"

    async def _run_read_app(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Do not return a pooled connection while a sync route still runs.

        Starlette cannot stop a worker-thread DuckDB query when the outer ASGI
        task is cancelled. Waiting for that worker prevents the same connection
        from being returned to the pool and reused concurrently by a new request.
        """

        app_task = asyncio.create_task(self.app(scope, receive, send))
        try:
            await asyncio.shield(app_task)
        except asyncio.CancelledError as cancelled:
            try:
                await app_task
            except BaseException as exc:  # noqa: BLE001
                logger.debug("Read app finished with error after client cancellation: %s", exc)
            raise cancelled

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path", ""))
        method = str(scope.get("method", "GET"))
        query_type = self.classify(path, method)
        scope["query_type"] = query_type
        start = time.perf_counter()
        request_id = request_id_from_scope(scope)
        cancelled = False

        # L4.72.2 治本: 捕获 dual_conn.ReadPoolTimeout 618 大促 8 并发雪崩, 返回 503
        from backend.services.dual_conn import ReadPoolTimeout  # L4.72.2 新增异常类
        try:
            if query_type == "read":
                async with async_read_request_context(query_type):
                    await self._run_read_app(scope, receive, send)
            else:
                token = set_query_type(query_type)
                try:
                    await self.app(scope, receive, send)
                finally:
                    reset_query_type(token)
        except asyncio.CancelledError:
            cancelled = True
            raise
        except ReadPoolTimeout as e:
            # L4.72.2 治本: 618 大促 8 并发雪崩友好降级, 返回 503 而非 30s timeout
            logger.warning("L4.72.2 ReadPoolTimeout (618 大促 8 并发雪崩兜底): %s", e)
            retry_after = int(READ_ACQUIRE_TIMEOUT_SECONDS)
            response = JSONResponse(
                status_code=503,
                content=competition_error_body(
                    http_status=503,
                    code="STATE_UNAVAILABLE",
                    message=f"DuckDB read pool full, 请重试. {e}",
                    request_id=request_id,
                    retryable=True,
                    retry_after=retry_after,
                    doc_ref=DOC_T08,
                ),
                headers={"Retry-After": str(retry_after)},
            )
            await response(scope, receive, send)
        finally:
            duration = time.perf_counter() - start
            logger.info(
                "competition_query_event path=%s method=%s query_type=%s "
                "duration_ms=%.1f cancelled=%s request_id=%s",
                path,
                method,
                query_type,
                duration * 1000,
                cancelled,
                request_id,
            )
            if path != "/metrics":
                record_query(path, query_type, duration)
