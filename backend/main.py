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
from datetime import datetime
import time
import logging

from backend.services.exceptions import ServiceError, ValidationError, NotFoundError

# ─────────────────────────────────────────────────────────────
# App 初始化
# ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="芙清 CRM 客户分析系统 API",
    description="提供核心指标、RFM、人群流转等数据 API",
    version="1.0.0"
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
    if path.startswith("/api/v1/auth/") or path == "/api/v1/health":
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
@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError):
    return JSONResponse(status_code=exc.status_code, content=exc.detail)


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    return JSONResponse(status_code=exc.status_code, content=exc.detail)


@app.exception_handler(NotFoundError)
async def not_found_error_handler(request: Request, exc: NotFoundError):
    return JSONResponse(status_code=exc.status_code, content=exc.detail)


@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    """未捕获的异常返回 500，避免堆栈信息暴露"""
    return JSONResponse(
        status_code=500,
        content={"error": "INTERNAL_ERROR", "message": "服务器内部错误，请稍后重试"}
    )


# ─────────────────────────────────────────────────────────────
# 健康检查（保留在 main.py，避免循环依赖）
# ─────────────────────────────────────────────────────────────
@app.get("/api/v1/health")
def health_check():
    """系统健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": "duckdb"
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
