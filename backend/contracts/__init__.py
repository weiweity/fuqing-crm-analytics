"""
芙清 CRM - API 契约层 (Contracts)

统一管理所有 Pydantic Request/Response 模型。
规则:
1. 所有模型必须在此定义，禁止在 main.py 中内联定义 Response 模型
2. 字段命名必须与后端实际返回 100% 一致
3. 前端通过 openapi-typescript 从 /openapi.json 生成 TS 类型
"""

from .schemas import (
    # 通用
    DateRangeResponse,
    # 核心指标
    OverviewMetrics,
    TrendData,
    # 人群看板
    AudienceTableRequest,
    AudienceTableResponse,
    AudienceSummaryRequest,
    AudienceSummaryResponse,
    # RFM
    RFMRFlowResponse,
    # 流转
    FlowMatrixResponse,
    FlowSankeyResponse,
    # 流失
    ChurnDistributionResponse,
    ChurnUsersResponse,
    # 资产
    AssetSummaryResponse,
    AssetTrendResponse,
    # 地域
    GeoDistributionResponse,
    GeoSegmentMatrixResponse,
    GeoTrendResponse,
    # 品类
    CategoryDistributionResponse,
    CategoryOverviewResponse,
    CategorySegmentMatrixResponse,
    CategoryUserProfileResponse,
    # 导出
    ExportPPTRequest,
    ExportPPTResponse,
    TemplatesResponse,
)

__all__ = [
    "DateRangeResponse",
    "OverviewMetrics",
    "TrendData",
    "AudienceTableRequest",
    "AudienceTableResponse",
    "AudienceSummaryRequest",
    "AudienceSummaryResponse",
    "RFMRFlowResponse",
    "FlowMatrixResponse",
    "FlowSankeyResponse",
    "ChurnDistributionResponse",
    "ChurnUsersResponse",
    "AssetSummaryResponse",
    "AssetTrendResponse",
    "GeoDistributionResponse",
    "GeoSegmentMatrixResponse",
    "GeoTrendResponse",
    "CategoryDistributionResponse",
    "CategoryOverviewResponse",
    "CategorySegmentMatrixResponse",
    "CategoryUserProfileResponse",
    "ExportPPTRequest",
    "ExportPPTResponse",
    "TemplatesResponse",
]
