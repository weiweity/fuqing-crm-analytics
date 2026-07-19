"""Query routing middleware for Sprint 201 R1 read/write splitting."""
from __future__ import annotations

import asyncio
import logging
import time

from starlette.types import ASGIApp, Receive, Scope, Send

from backend.services.dual_conn import (
    async_read_request_context,
    reset_query_type,
    set_query_type,
)
from backend.services.query_metrics import record_query

logger = logging.getLogger(__name__)


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
        # Admin upload/registry 走文件侧状态, 不读业务 DuckDB.
        # 若不排除, catch-all GET /api/v1/* → read 会在 CI (无 prod DuckDB)
        # 强开 read_only 连接 → "database does not exist" 500.
        "/api/v1/admin/",
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
        except ReadPoolTimeout as e:
            # L4.72.2 治本: 618 大促 8 并发雪崩友好降级, 返回 503 而非 30s timeout
            logger.warning(f"L4.72.2 ReadPoolTimeout (618 大促 8 并发雪崩兜底): {e}")
            from starlette.responses import JSONResponse
            response = JSONResponse(
                status_code=503,
                content={"detail": f"DuckDB read pool full, 请重试. {str(e)}"},
            )
            await response(scope, receive, send)
        finally:
            if path != "/metrics":
                record_query(path, query_type, time.perf_counter() - start)
