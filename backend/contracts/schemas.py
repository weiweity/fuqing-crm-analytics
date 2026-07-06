"""Sample CRM - Pydantic 契约模型（统一导出）"""

from .common import DateRangeResponse, YearComparisonRow, DualAxisLineData, SankeyNode, SankeyLink, SankeyGraphData, WoolPartyBreakdown
from .metrics import OverviewMetrics, TrendData
from .audience import AudienceTableRequest, AudienceRow, AudienceTableResponse, ChannelGSVRow, AudiencePeriodMetrics, AudienceSummaryRequest, AudienceSummaryResponse
from .flow import FlowMatrixResponse, FlowMatrixCell, FlowMatrix, AssociationItem, CategoryFlowResponse, CategoryFlowAssociationResponse, CategoryFlowMatrixResponse, AnchorMode, PathDepth
from .asset import AssetSummaryResponse, AssetTrendResponse, ProductClassRepurchase, StoreAssetWeek, StoreAssetResponse, ProductAssetWeek, ProductAssetItem, ProductAssetResponse
# Sprint 203 R9: Geo contracts 删 (geo router + contract 删除; geo_service 保留供 report/export 用, 见 services/geo_service.py)
from .category import CategoryDistributionItem, CategoryDistributionResponse, CategoryOverviewItem, CategoryOverviewResponse, CategorySegmentMatrixResponse, CategoryUserProfileResponse, CategoryRepurchaseFlowRow, CategoryRepurchaseFlowResponse, ValueTierTableRow, CategoryValueTierResponse, MarketBasketItem, MarketBasketYoYItem, MarketBasketResponse, CategoryChurnItem, CategoryChurnResponse, CategoryDailyTrendResponse, UserDetail, CategoryUserListResponse
from .rfm import RFMRFlowRow, RFMRFlowResponse, RFMFRFlowRow, RFMFRFlowResponse, RFMMFlowRow, RFMMFlowResponse, RFMAnalysisRow, RFMAnalysisResponse, RFMThresholds, SegmentDefinitionItem, RFMConfigResponse, DecliningCategoryItem, ImprovingCategoryItem, RFMCategoryDrilldownRow, TopDriverItem, RFMCategoryDrilldownSummary, RFMCategoryDrilldownResponse
from .rfm_segments import LifecycleStage, ValueTier, PotentialTier, RFMSegmentExtended, RFMExtendedRequest, RFMExtendedResponse
from .health import HealthAlertItem, HealthOverviewMetrics, RepurchaseBucket, RepurchaseCycleOverview, CohortRetentionResponse, ValueTierDefinition, FrequencyTierDefinition, CustomerSegmentItem, ValueTierResponse, TierFlowRow, TierFlowResponse, PromotionPeriod, PromotionVsDailyMetrics, PromotionCalendarResponse, ChannelHealthScoreItem, HealthTargetsResponse, ChannelHealthScoresResponse, ConfigHistoryItem, ConfigHistoryResponse, ConfigRestoreResponse, AuditLogItem, AuditLogResponse, ExportPPTRequest, ExportPPTResponse, TemplatesResponse, NewCustomerConversionFunnel, NewCustomerChannelQuality, NewCustomerConversionResponse
from .visitor import VisitorSummaryResponse, VisitorDailyTrendItem, VisitorDailyTrendResponse
from .sampling import SamplingChannelSummary, SamplingLevelSummary, SamplingCategoryRow, SamplingROITimeRange, SamplingRepurchaseBucket, SamplingRepurchaseDistribution, SamplingRepurchaseTrackingBucket, SamplingRepurchaseTrackingResponse, SamplingROIResponse
# Sprint 203 R9: cohort_retention contracts 删 (前端 sampling 03-tab 解耦, cohort-retention/matrix API 移除)

__all__ = [
    "DateRangeResponse", "YearComparisonRow", "DualAxisLineData",
    "SankeyNode", "SankeyLink", "SankeyGraphData", "WoolPartyBreakdown",
    "OverviewMetrics", "TrendData",
    "AudienceTableRequest", "AudienceRow", "AudienceTableResponse",
    "ChannelGSVRow", "AudiencePeriodMetrics", "AudienceSummaryRequest", "AudienceSummaryResponse",
    "FlowMatrixResponse", "FlowMatrixCell", "FlowMatrix",
    "AssociationItem", "CategoryFlowResponse", "CategoryFlowAssociationResponse", "CategoryFlowMatrixResponse",
    "AnchorMode", "PathDepth",
    "AssetSummaryResponse", "AssetTrendResponse", "ProductClassRepurchase",
    "StoreAssetWeek", "StoreAssetResponse", "ProductAssetWeek", "ProductAssetItem", "ProductAssetResponse",
    # Sprint 203 R9: GeoDistributionItem/GeoDistributionResponse/GeoSegmentMatrixResponse/GeoTrendResponse 删
    "CategoryDistributionItem", "CategoryDistributionResponse",
    "CategoryOverviewItem", "CategoryOverviewResponse", "CategorySegmentMatrixResponse",
    "CategoryUserProfileResponse", "CategoryRepurchaseFlowRow", "CategoryRepurchaseFlowResponse",
    "ValueTierTableRow", "CategoryValueTierResponse",
    "MarketBasketItem", "MarketBasketYoYItem", "MarketBasketResponse",
    "CategoryChurnItem", "CategoryChurnResponse", "CategoryDailyTrendResponse", "UserDetail", "CategoryUserListResponse",
    "RFMRFlowRow", "RFMRFlowResponse", "RFMFRFlowRow", "RFMFRFlowResponse",
    "RFMMFlowRow", "RFMMFlowResponse", "RFMAnalysisRow", "RFMAnalysisResponse",
    "RFMThresholds", "SegmentDefinitionItem", "RFMConfigResponse",
    "LifecycleStage", "ValueTier", "PotentialTier", "RFMSegmentExtended",
    "RFMExtendedRequest", "RFMExtendedResponse",
    "DecliningCategoryItem", "ImprovingCategoryItem",
    "RFMCategoryDrilldownRow", "TopDriverItem", "RFMCategoryDrilldownSummary", "RFMCategoryDrilldownResponse",
    "HealthAlertItem", "HealthOverviewMetrics",
    "RepurchaseBucket", "RepurchaseCycleOverview", "CohortRetentionResponse",
    "ValueTierDefinition", "FrequencyTierDefinition", "CustomerSegmentItem", "ValueTierResponse",
    "TierFlowRow", "TierFlowResponse",
    "PromotionPeriod", "PromotionVsDailyMetrics", "PromotionCalendarResponse",
    "ChannelHealthScoreItem", "HealthTargetsResponse", "ChannelHealthScoresResponse",
    "ConfigHistoryItem", "ConfigHistoryResponse", "ConfigRestoreResponse",
    "AuditLogItem", "AuditLogResponse",
    "ExportPPTRequest", "ExportPPTResponse", "TemplatesResponse",
    "NewCustomerConversionFunnel", "NewCustomerChannelQuality", "NewCustomerConversionResponse",
    "VisitorSummaryResponse", "VisitorDailyTrendItem", "VisitorDailyTrendResponse",
    "SamplingChannelSummary", "SamplingLevelSummary", "SamplingCategoryRow", "SamplingROITimeRange",
    "SamplingRepurchaseBucket", "SamplingRepurchaseDistribution", "SamplingRepurchaseTrackingBucket", "SamplingRepurchaseTrackingResponse", "SamplingROIResponse",
    # Sprint 203 R9: SamplingLock*/Rolling*/CohortRetention 删
]  # noqa: E501
