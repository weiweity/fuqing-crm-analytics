"""
Sample CRM 客户分析系统 - FastAPI 后端

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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import time
import logging

from backend.services.exceptions import ServiceError, ValidationError, NotFoundError

logger = logging.getLogger(__name__)


def validate_startup_db() -> None:
    """Sprint 61 P2 治本: 启动时校验 DuckDB 数据可用性 (fail-fast).

    根因: uvicorn PID 29564 接错 798KB 空 schema DB, 健康检查绿 + 200 OK + 全 0 数据
    ("静默失真" 模式, 跟 Sprint 60+ 4 个 500 error 同类).

    校验项:
    - DB 文件存在
    - orders 表存在
    - orders 行数 > 0
    - max(pay_time) 新鲜度 (默认 30 天)

    模式 (FQ_DB_MODE):
    - production (默认): 任一校验失败 → raise RuntimeError 拒绝启动
    - schema_test: 跳过数据量检查, 只 WARN log (CI e2e / schema_test 用)
    - 其他值: 默认 production 行为
    """
    from backend.config import DUCKDB_PATH, DB_MODE, DB_FRESHNESS_DAYS
    import duckdb

    db_realpath = Path(DUCKDB_PATH).resolve()
    db_size_bytes = db_realpath.stat().st_size if db_realpath.exists() else 0
    db_size_gb = db_size_bytes / (1024 ** 3)

    logger.info(
        "[Sprint 61 startup-check] DB realpath=%s size=%.3f GB (%d bytes) mode=%s freshness_days=%d",
        db_realpath, db_size_gb, db_size_bytes, DB_MODE, DB_FRESHNESS_DAYS,
    )

    # 文件不存在 → 直接拒绝 (任何模式都拒绝, 跟读不到表同根因)
    if not db_realpath.exists():
        msg = f"Startup validation failed: DuckDB file not found at {db_realpath}"
        logger.error("[Sprint 61 startup-check] %s", msg)
        raise RuntimeError(msg)

    # 用临时 read_only 连接校验 (避免污染全局单例的 memory_limit/config)
    try:
        conn = duckdb.connect(str(db_realpath), read_only=True)
    except Exception as e:  # noqa: BLE001
        msg = f"Startup validation failed: cannot open DuckDB at {db_realpath}: {e}"
        logger.error("[Sprint 61 startup-check] %s", msg)
        raise RuntimeError(msg) from e

    try:
        # orders 表存在性
        try:
            orders_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        except duckdb.CatalogException as e:
            orders_count = 0
            logger.warning("[Sprint 61 startup-check] orders 表不存在: %s", e)

        # max(pay_time) 新鲜度 (pay_time 字段缺失时容错)
        max_pay_time = None
        try:
            row = conn.execute("SELECT MAX(pay_time) FROM orders").fetchone()
            if row and row[0] is not None:
                max_pay_time = row[0]
        except duckdb.Error as e:
            logger.warning("[Sprint 61 startup-check] pay_time 字段查询失败: %s", e)

        logger.info(
            "[Sprint 61 startup-check] orders.count=%s max_pay_time=%s",
            orders_count, max_pay_time,
        )

        # schema_test 模式: 跳过数据量 + 新鲜度校验, 只 WARN
        if DB_MODE == "schema_test":
            logger.warning(
                "[Sprint 61 startup-check] schema_test mode → 跳过数据量/新鲜度校验 "
                "(orders.count=%s max_pay_time=%s)",
                orders_count, max_pay_time,
            )
            return

        # production 模式 (含未知 mode 默认): fail-fast
        if orders_count == 0:
            msg = (
                f"Startup validation failed: orders 表为空 (count=0) at {db_realpath}. "
                f"可能是 DUCKDB_PATH 接错空 schema DB. Set FQ_DB_MODE=schema_test for CI e2e."
            )
            logger.error("[Sprint 61 startup-check] %s", msg)
            raise RuntimeError(msg)

        if max_pay_time is None:
            msg = (
                f"Startup validation failed: orders.max(pay_time) 为 NULL at {db_realpath}. "
                f"可能是 DUCKDB_PATH 接错空 schema DB. Set FQ_DB_MODE=schema_test for CI e2e."
            )
            logger.error("[Sprint 61 startup-check] %s", msg)
            raise RuntimeError(msg)

        # 新鲜度: max(pay_time) 距今超过 DB_FRESHNESS_DAYS 天 → 拒绝启动
        now = datetime.now()
        # max_pay_time 可能是 datetime / date / str, 统一转 datetime 比较
        if isinstance(max_pay_time, datetime):
            mpt = max_pay_time
        elif hasattr(max_pay_time, "to_pydatetime"):  # pandas Timestamp
            mpt = max_pay_time.to_pydatetime()
        elif hasattr(max_pay_time, "year"):  # date
            mpt = datetime(max_pay_time.year, max_pay_time.month, max_pay_time.day)
        else:
            logger.warning("[Sprint 61 startup-check] max_pay_time 类型未知: %s, 跳过新鲜度校验", type(max_pay_time))
            return

        age = now - mpt
        if age > timedelta(days=DB_FRESHNESS_DAYS):
            msg = (
                f"Startup validation failed: orders.max(pay_time)={mpt} 距今 {age.days} 天 "
                f"> {DB_FRESHNESS_DAYS} 天阈值. 可能是 DUCKDB_PATH 接错过期 DB. "
                f"Set FQ_DB_MODE=schema_test for CI e2e."
            )
            logger.error("[Sprint 61 startup-check] %s", msg)
            raise RuntimeError(msg)
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


# ─────────────────────────────────────────────────────────────
# 应用生命周期
# ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(application: FastAPI):
    # Sprint 61 P2 治本: 启动校验 (fail-fast, 阻断 DUCKDB_PATH 接错空/过期 DB)
    validate_startup_db()
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
    # Sprint 18 #123: 启动 hook — 跨进程 manifest version 对齐
    # 改 ratio/契约后, 重启 uvicorn 自动 invalidate W5 cache, 不再需要手动
    try:
        from backend.services.rfm.cache import check_manifest_version_and_invalidate
        check_manifest_version_and_invalidate()
    except Exception as e:  # noqa: BLE001
        logger.warning("W5 startup hook 启动失败 (不阻塞服务): %s", e)
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
    title="Sample CRM 客户分析系统 API",
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
# Rate Limit 中间件 (Sprint 200 R1 v2.1, 跟 L4.36 友好错误 1:1)
#
# 真因: 业务组持续取数 → uvicorn 一直处于下线状态 (Sprint 184 L4.38 DuckDB flock 锁死)
# 治本: 每用户每分钟 60 req 限流, 超限返 429 + Retry-After 头. 跟 L4.36 graceful retry 3 次配套.
# 配套: Codex consult 6 补强 (AST allowlist + DuckDB 安全配置 + query worker) 后续 sprint 实施.
# ─────────────────────────────────────────────────────────────
_RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60"))
_RATE_LIMIT_WINDOW = 60  # seconds
_rate_limit_buckets: dict[str, list[float]] = {}  # {user_id: [timestamp, ...]}


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # 只 bypass 登录接口 (防止登录失败重试触发 429), 其他 auth/me / auth/refresh / auth/logout 都要限流
    path = request.url.path
    if (
        path == "/api/v1/health"
        or path == "/api/v1/auth/login"
        or path == "/api/v1/auth/refresh"
        or path.startswith("/docs")
        or path.startswith("/redoc")
        or path == "/openapi.json"
    ):
        return await call_next(request)
    if request.method == "OPTIONS":
        return await call_next(request)

    # 提取 user_id (从 Authorization bearer token 推, 简化为 client_ip fallback)
    user_id = _extract_user_id_from_request(request)
    if user_id is None:
        user_id = f"ip:{request.client.host if request.client else 'unknown'}"

    # 滑动窗口 rate limit
    now = time.time()
    bucket = _rate_limit_buckets.setdefault(user_id, [])
    # 清除窗口外的请求
    bucket[:] = [t for t in bucket if now - t < _RATE_LIMIT_WINDOW]

    if len(bucket) >= _RATE_LIMIT_PER_MINUTE:
        # L4.36 友好错误: 返 429 + Retry-After 头
        response = JSONResponse(
            status_code=429,
            content={
                "detail": f"Rate limit exceeded ({_RATE_LIMIT_PER_MINUTE} req/min). "
                          "Retry in 60s. (L4.36 graceful retry, Sprint 200 R1 v2.1)",
                "retry_after_seconds": _RATE_LIMIT_WINDOW,
                "user_id": user_id,
            },
        )
        response.headers["Retry-After"] = str(_RATE_LIMIT_WINDOW)
        response.headers["X-RateLimit-Limit"] = str(_RATE_LIMIT_PER_MINUTE)
        response.headers["X-RateLimit-Remaining"] = "0"
        _access_logger.warning(
            "Rate limit triggered",
            extra={
                "user_id": user_id,
                "path": path,
                "method": request.method,
                "current_count": len(bucket),
                "limit": _RATE_LIMIT_PER_MINUTE,
            },
        )
        return response

    bucket.append(now)
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(_RATE_LIMIT_PER_MINUTE)
    response.headers["X-RateLimit-Remaining"] = str(_RATE_LIMIT_PER_MINUTE - len(bucket))
    return response


def _extract_user_id_from_request(request: Request) -> Optional[str]:
    """
    从 Authorization Bearer token 提取 user_id (跟 auth_middleware._verify_token 1:1 stable).
    Bearer admin:123456 → "admin"
    Bearer fqsw:fqsw888 → "fqsw"
    失败返 None (rate limit fallback to client_ip)

    跟 auth_middleware 1:1: 用 _verify_token 校验 token 有效性, 有效再解析 user_id.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    # 延迟导入避免循环依赖 (跟 auth_middleware 1:1)
    from backend.routers.auth import _verify_token
    user_info = _verify_token(token)
    if user_info is None:
        return None
    # user_info 是 dict {"username": ..., "role": ...} 或 str (跟 Sprint 195 R1 兼容)
    if isinstance(user_info, dict):
        return user_info.get("username", "unknown")
    if isinstance(user_info, tuple):
        return user_info[0] if user_info else "unknown"
    return str(user_info)

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
    asset_router,
    geo_router,
    category_router,
    audience_router,
    rfm_router,
    sampling_router,
    lifetime_value_router,
    cohort_retention_router,
    market_focus_router,
    visitor_router,
    export_router,
    report_router,
    ad_hoc_query_router,  # Sprint 188: 即席查询 HTTP API 入口
)

app.include_router(auth_router)
app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(flow_router)
app.include_router(asset_router)
app.include_router(geo_router)
app.include_router(category_router)
app.include_router(audience_router)
app.include_router(rfm_router)
app.include_router(sampling_router)
app.include_router(lifetime_value_router)
app.include_router(cohort_retention_router)
app.include_router(market_focus_router)
app.include_router(visitor_router)
app.include_router(export_router)
app.include_router(report_router)
app.include_router(ad_hoc_query_router)  # Sprint 188


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
