"""Query routing middleware for Sprint 201 R1 read/write splitting."""
from __future__ import annotations

import time

from starlette.types import ASGIApp, Receive, Scope, Send

from backend.services.dual_conn import read_request_context, reset_query_type, set_query_type
from backend.services.query_metrics import record_query


class QueryRouterMiddleware:
    """Bind dashboard requests to read-only connections and record query metrics."""

    READ_ENDPOINTS = {
        "/api/v1/audience/summary",
        "/api/v1/audience/table",
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
    READ_PREFIXES = (
        "/api/v1/audience/",
        "/api/v1/assets/",
        "/api/v1/category/",
        "/api/v1/cohort-retention/",
        "/api/v1/export/",
        "/api/v1/flow/",
        "/api/v1/geo/",
        "/api/v1/health/",
        "/api/v1/lifetime-value/",
        "/api/v1/market-focus/",
        "/api/v1/metrics/",
        "/api/v1/report/",
        "/api/v1/rfm/",
        "/api/v1/sampling/",
        "/api/v1/visitor/",
    )
    WORKER_ENDPOINTS = {
        "/api/v1/ad-hoc/ai-sandbox-execute",
    }
    CONTROL_ENDPOINTS = {
        "/api/v1/health",
        "/metrics",
        "/openapi.json",
    }
    CONTROL_PREFIXES = (
        "/api/v1/auth/",
        "/docs",
        "/redoc",
    )

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    def classify(self, path: str, method: str) -> str:
        """Classify a request as read, worker, or default."""

        if path in self.CONTROL_ENDPOINTS or path.startswith(self.CONTROL_PREFIXES):
            return "default"
        if path in self.WORKER_ENDPOINTS:
            return "worker"
        if path in self.READ_ENDPOINTS or path.startswith(self.READ_PREFIXES):
            return "read"
        if method == "GET" and path.startswith("/api/v1/") and not path.startswith("/api/v1/auth/"):
            return "read"
        return "default"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path", ""))
        method = str(scope.get("method", "GET"))
        query_type = self.classify(path, method)
        scope["query_type"] = query_type
        start = time.perf_counter()

        try:
            if query_type == "read":
                with read_request_context(query_type):
                    await self.app(scope, receive, send)
            else:
                token = set_query_type(query_type)
                try:
                    await self.app(scope, receive, send)
                finally:
                    reset_query_type(token)
        finally:
            if path != "/metrics":
                record_query(path, query_type, time.perf_counter() - start)
