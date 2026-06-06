"""
芙清 CRM 客户分析系统 - FastAPI 后端

本文件仅负责：
- app 初始化
- CORS 配置
- 全局中间件（访问日志、认证）
- 全局异常处理器
- 路由注册

所有业务 API 端点已拆分到 backend/routers/ 下的独立模块。
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime
import time
import logging

from backend.services.exceptions import ServiceError, ValidationError, NotFoundError

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 应用生命周期
# ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(application: FastAPI):
    # 启动时启动内存监控守护线程
    from backend.db.memory_monitor import start_memory_watchdog, check_memory
    start_memory_watchdog(interval=60)
    check_memory(label="应用启动")
    # W5 v0.4.13: 初始化 RFM cache 表 + 同步 manifest version
    # (后续每次 cache.get() 内部 _ManifestTracker 还会做变化检测)
    try:
        from backend.services.rfm.cache import RfmQueryCache
        RfmQueryCache().ensure_table()
        logger.info("W5 RFM cache 表已就绪")
    except Exception as e:  # noqa: BLE001
        logger.warning("W5 RFM cache 启动失败 (不阻塞服务): %s", e)
    yield
    # 关闭时停止内存监控并释放全局 DuckDB 连接
    from backend.db.memory_monitor import stop_memory_watchdog
    from backend.db.connection import close_connection
    stop_memory_watchdog()
    close_connection()


# ─────────────────────────────────────────────────────────────
# App 初始化
# ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="芙清 CRM 客户分析系统 API",
    description="提供核心指标、RFM、人群流转等数据 API",
    version="1.0.0",
    lifespan=lifespan,
)

# ─────────────────────────────────────────────────────────────
# CORS 配置
# ─────────────────────────────────────────────────────────────
import os
_DEFAULT_ORIGINS = "http://localhost:5173"
_CORS_ORIGINS = os.environ.get("CORS_ORIGINS", _DEFAULT_ORIGINS).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _CORS_ORIGINS if o.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# ─────────────────────────────────────────────────────────────
# 安全响应头中间件
# ─────────────────────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response

# ─────────────────────────────────────────────────────────────
# 结构化访问日志中间件
# ─────────────────────────────────────────────────────────────
_access_logger = logging.getLogger("access")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000
    _access_logger.info(
        "API request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "client_ip": request.client.host if request.client else "unknown",
        }
    )
    return response


# ─────────────────────────────────────────────────────────────
# 全局认证中间件（除认证路由和健康检查外，所有 API 需 Bearer token）
# ─────────────────────────────────────────────────────────────
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if (
        path.startswith("/api/v1/auth/")
        or path == "/api/v1/health"
        or path.startswith("/docs")
        or path.startswith("/redoc")
        or path == "/openapi.json"
    ):
        return await call_next(request)
    if request.method == "OPTIONS":
        return await call_next(request)

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "未提供认证令牌"})

    token = auth[7:]
    # 延迟导入避免循环依赖
    from backend.routers.auth import _verify_token
    if _verify_token(token) is None:
        return JSONResponse(status_code=401, content={"detail": "登录已过期，请重新登录"})

    return await call_next(request)


# ─────────────────────────────────────────────────────────────
# 全局异常处理器
# ─────────────────────────────────────────────────────────────
def _future_date_warning_for_request(request: Request) -> str | None:
    """
    检查请求中的日期参数，如果存在未来日期则返回警告消息（ASCII安全）。

    用于在 service 抛异常时，仍能告知调用方日期参数有问题。
    AI-开发者友好：未来日期静默全0 会对运营决策造成误导。
    """
    try:
        from datetime import date as _date
        from datetime import datetime as _dt
        _date_params = ["analysis_date", "start_date", "end_date", "compare_start_date", "compare_end_date"]
        for _param in _date_params:
            _val = request.query_params.get(_param)
            if not _val:
                continue
            try:
                _input_date = _dt.strptime(_val, "%Y-%m-%d").date()
                if _input_date > _date.today():
                    # 返回 URL 编码的英文消息（HTTP header 只支持 latin-1/ASCII）
                    from urllib.parse import quote
                    return quote(
                        f"date {_val} is in the future, data will be all-zero. "
                        "Use a date <= today for analysis."
                    )
            except ValueError:
                pass
        return None
    except Exception:
        return None


def _add_future_date_warning(request: Request, json_response: JSONResponse) -> JSONResponse:
    if warning := _future_date_warning_for_request(request):
        json_response.headers["X-Data-Warning"] = warning
    return json_response


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError):
    resp = JSONResponse(status_code=exc.status_code, content=exc.detail)
    return _add_future_date_warning(request, resp)


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    resp = JSONResponse(status_code=exc.status_code, content=exc.detail)
    return _add_future_date_warning(request, resp)


@app.exception_handler(NotFoundError)
async def not_found_error_handler(request: Request, exc: NotFoundError):
    resp = JSONResponse(status_code=exc.status_code, content=exc.detail)
    return _add_future_date_warning(request, resp)


@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    """未捕获的异常返回 500，避免堆栈信息暴露"""
    import traceback
    print(f"[500 ERROR] {request.method} {request.url.path}: {type(exc).__name__}: {exc}")
    traceback.print_exc()
    resp = JSONResponse(
        status_code=500,
        content={"error": "INTERNAL_ERROR", "message": "服务器内部错误，请稍后重试"}
    )
    return _add_future_date_warning(request, resp)


# ─────────────────────────────────────────────────────────────
# 健康检查（保留在 main.py，避免循环依赖）
# ─────────────────────────────────────────────────────────────
@app.get("/api/v1/health")
def health_check():
    """系统健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
    }


# ─────────────────────────────────────────────────────────────
# 路由注册
# ─────────────────────────────────────────────────────────────
from backend.routers import (
    auth_router,
    health_router,
    metrics_router,
    flow_router,
    churn_router,
    asset_router,
    geo_router,
    category_router,
    audience_router,
    rfm_router,
    breakdown_router,
    sampling_router,
    market_focus_router,
    visitor_router,
    export_router,
    report_router,
)

app.include_router(auth_router)
app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(flow_router)
app.include_router(churn_router)
app.include_router(asset_router)
app.include_router(geo_router)
app.include_router(category_router)
app.include_router(audience_router)
app.include_router(rfm_router)
app.include_router(breakdown_router)
app.include_router(sampling_router)
app.include_router(market_focus_router)
app.include_router(visitor_router)
app.include_router(export_router)
app.include_router(report_router)


if __name__ == "__main__":
    import uvicorn
    from pathlib import Path
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(Path(__file__).parent)],
    )
