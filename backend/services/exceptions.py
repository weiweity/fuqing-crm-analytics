"""
芙清 CRM - Service 层统一异常定义

所有 Service 抛出的业务异常应使用以下类型，禁止使用裸 except。
异常被 main.py 中的全局处理器捕获，返回统一的 JSON 错误响应。
"""

from fastapi import HTTPException

# HTTP status code numeric literals (avoids deprecation warnings from fastapi.status)
_HTTP_422 = 422  # Unprocessable Content (formerly Unprocessable Entity)


class ServiceError(HTTPException):
    """Service 层基础异常（自动映射到 HTTP 500）"""
    def __init__(self, detail: str, error_code: str = "SERVICE_ERROR"):
        super().__init__(
            status_code=500,
            detail={"error": error_code, "message": detail}
        )


class ValidationError(HTTPException):
    """参数校验失败（自动映射到 HTTP 422）"""
    def __init__(self, detail: str):
        super().__init__(
            status_code=_HTTP_422,
            detail={"error": "VALIDATION_ERROR", "message": detail}
        )


class NotFoundError(HTTPException):
    """资源不存在（自动映射到 HTTP 404）"""
    def __init__(self, detail: str):
        super().__init__(
            status_code=404,
            detail={"error": "NOT_FOUND", "message": detail}
        )


class DataSourceError(ServiceError):
    """数据源/数据库错误"""
    def __init__(self, detail: str):
        super().__init__(detail, error_code="DATA_SOURCE_ERROR")


class ComputationError(ServiceError):
    """计算/聚合错误"""
    def __init__(self, detail: str):
        super().__init__(detail, error_code="COMPUTATION_ERROR")
