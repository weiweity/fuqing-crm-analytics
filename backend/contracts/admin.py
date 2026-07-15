"""Sprint 205+ Admin Upload: Pydantic 契约模型（v5 prompt）。

6 个模型:
- UploadSourcePublic: 客户端可见的数据源配置（不暴露 target_path/staged_path）
- UploadConfigResponse: GET /upload-config 响应
- UploadValidationResult: preflight 校验结果
- UploadRecordOut: 单条 upload 记录
- UploadResponse: POST /upload 响应
- UploadListResponse: GET /uploads 响应

契约约束:
- 不暴露 staged_path / target_path / 用户 home 路径 / 项目绝对路径
- mode 限定 append|single
- status 限定 staged（sprint 1 只 staged，sprint 2 才进入 queued/running/promoted）
- 所有时间用 UTC ISO-8601
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class UploadSourcePublic(BaseModel):
    """客户端可见的 single 数据源配置（GET /upload-config 元素）。

    服务端 allowlist 的子集：禁暴露 target_path / staging_path / 项目绝对路径 / 用户 home。
    """

    business_type: str = Field(..., description="业务类型: shop/member/status-refresh/taoke/live/visitor/spu-mapping/taoke-product/channel-rules/campaign-schedule")
    display_name: str = Field(..., description="运营可读的中文名")
    allowed_extensions: List[str] = Field(..., description="允许的扩展名（如 .csv / .xlsx / .zip）")
    mode: Literal["append", "single"] = Field(..., description="append 累积 / single 单文件替换")
    max_size_bytes: int = Field(..., description="单文件最大字节数")
    future_post_actions: List[str] = Field(
        default_factory=list,
        description="Sprint 2+ 才会执行的后置动作（如 rescan-spu / refresh-campaign-schedule）",
    )
    replacement_warning: Optional[str] = Field(
        default=None,
        description="UI 替换提示文案（仅 mode=single 才有值）",
    )


class UploadConfigResponse(BaseModel):
    """GET /upload-config 响应：恰好 10 种数据源 + 全局大小限制。"""

    sources: List[UploadSourcePublic] = Field(..., min_length=10, max_length=10)
    max_upload_bytes: int = Field(..., description="服务端硬上限（当前 100MB）")


class UploadValidationResult(BaseModel):
    """preflight 校验结果（解析失败返 422，业务校验失败也返 422）。"""

    validator: str = Field(..., description="校验器名称：csv-utf8/xlsx-pandas/zip-safe/business-<type>")
    valid: bool = Field(..., description="校验通过与否")
    detected_format: str = Field(..., description="检测到的格式（编码/sheet/zip layout）")
    row_sample_count: Optional[int] = Field(default=None, description="样本行数（CSV/XLSX）")
    warnings: List[str] = Field(default_factory=list, description="warning 列表（不阻断）")


class UploadRecordOut(BaseModel):
    """单条 upload 记录（registry entry 的对外视图）。"""

    upload_id: str = Field(..., description="UUID4 hex")
    business_type: str = Field(...)
    original_filename: str = Field(...)
    extension: str = Field(..., description="含点的扩展名，如 .csv")
    size_bytes: int = Field(..., ge=0)
    sha256: str = Field(..., description="64 字符 hex")
    uploaded_by: str = Field(...)
    uploaded_at: datetime = Field(..., description="UTC ISO-8601")
    status: Literal["staged"] = Field(default="staged")
    validation: UploadValidationResult
    future_post_actions: List[str] = Field(default_factory=list)


class UploadResponse(BaseModel):
    """POST /upload 响应。"""

    upload: UploadRecordOut
    duplicate: bool = Field(default=False, description="True 表示命中 idempotency key 复用已有记录（HTTP 200）；False 表示新 staged（HTTP 201）")


class UploadListResponse(BaseModel):
    """GET /uploads 响应。"""

    items: List[UploadRecordOut]
    total: int = Field(..., ge=0)
    limit: int = Field(..., ge=1, le=100)
    offset: int = Field(..., ge=0)