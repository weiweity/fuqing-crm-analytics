"""芙清 CRM - Pydantic 契约模型（统一导出）"""

from .common import DateRangeResponse, YearComparisonRow, DualAxisLineData, SankeyNode, SankeyLink, SankeyGraphData, WoolPartyBreakdown
from .metrics import OverviewMetrics, TrendData
from .audience import AudienceTableRequest, AudienceRow, AudienceTableResponse, ChannelGSVRow, AudiencePeriodMetrics, AudienceSummaryRequest, AudienceSummaryResponse
from .flow import FlowMatrixResponse, FlowSankeyResponse, FlowMatrixCell, FlowMatrix, AssociationItem, CategoryFlowResponse, CategoryFlowAssociationResponse, CategoryFlowMatrixResponse, AnchorMode, PathDepth
from .churn import ChurnSegmentItem, ChurnDistributionResponse, ChurnUserItem, ChurnUsersResponse, ChurnScatterPoint, ChurnBarData, ChurnTableRow, CategoryChurnResponse, CategoryDailyTrendResponse, UserDetail, CategoryUserListResponse
from .asset import AssetSummaryResponse, AssetTrendResponse, ProductClassRepurchase, StoreAssetWeek, StoreAssetResponse, ProductAssetWeek, ProductAssetItem, ProductAssetResponse
from .geo import GeoDistributionItem, GeoDistributionResponse, GeoSegmentMatrixResponse, GeoTrendResponse
from .category import CategoryDistributionItem, CategoryDistributionResponse, CategoryOverviewItem, CategoryOverviewResponse, CategorySegmentMatrixResponse, CategoryUserProfileResponse, CategoryRepurchaseFlowRow, CategoryRepurchaseFlowResponse, ValueTierTableRow, CategoryValueTierResponse, MarketBasketItem, MarketBasketYoYItem, MarketBasketResponse
from .rfm import RFMRFlowRow, RFMRFlowResponse, RFMFRFlowRow, RFMFRFlowResponse, RFMMFlowRow, RFMMFlowResponse, RFMAnalysisRow, RFMAnalysisResponse, RFMThresholds, SegmentDefinitionItem, RFMConfigResponse, SegmentOrderRow, SegmentOrdersResponse, DecliningCategoryItem, ImprovingCategoryItem, RFMCategoryDrilldownRow, TopDriverItem, RFMCategoryDrilldownSummary, RFMCategoryDrilldownResponse
from .health import HealthAlertItem, HealthOverviewMetrics, RepurchaseBucket, RepurchaseCycleOverview, CohortRetentionResponse, ValueTierDefinition, FrequencyTierDefinition, CustomerSegmentItem, ValueTierResponse, TierFlowRow, TierFlowResponse, PromotionPeriod, PromotionVsDailyMetrics, PromotionCalendarResponse, ChannelHealthScoreItem, HealthTargetsResponse, ChannelHealthScoresResponse, ConfigHistoryItem, ConfigHistoryResponse, ConfigRestoreResponse, AuditLogItem, AuditLogResponse, ExportPPTRequest, ExportPPTResponse, TemplatesResponse, NewCustomerConversionFunnel, NewCustomerChannelQuality, NewCustomerConversionResponse
from .visitor import VisitorSummaryResponse, VisitorDailyTrendItem, VisitorDailyTrendResponse
from .breakdown import BreakdownRequest, BreakdownRIntervalRow, BreakdownRIntervalReverseRow, BreakdownOldCustomer, BreakdownChannelNewRow, BreakdownChannelNewReverseRow, BreakdownNewCustomer, BreakdownGapSuggestion, BreakdownMeta, BreakdownLogic, BreakdownResponse
from .sampling import SamplingChannelSummary, SamplingCategoryRow, SamplingROITimeRange, SamplingROIResponse, SamplingLockCampaignInfo, SamplingLockYearData, SamplingLockYOY, SamplingLockAnalysisResponse, RollingYearMetrics, RollingYOY, RollingTimeline, RollingComparisonResponse

__all__ = [
    "DateRangeResponse", "YearComparisonRow", "DualAxisLineData",
    "SankeyNode", "SankeyLink", "SankeyGraphData", "WoolPartyBreakdown",
    "OverviewMetrics", "TrendData",
    "AudienceTableRequest", "AudienceRow", "AudienceTableResponse",
    "ChannelGSVRow", "AudiencePeriodMetrics", "AudienceSummaryRequest", "AudienceSummaryResponse",
    "FlowMatrixResponse", "FlowSankeyResponse", "FlowMatrixCell", "FlowMatrix",
    "AssociationItem", "CategoryFlowResponse", "CategoryFlowAssociationResponse", "CategoryFlowMatrixResponse",
    "AnchorMode", "PathDepth",
    "ChurnSegmentItem", "ChurnDistributionResponse", "ChurnUserItem", "ChurnUsersResponse",
    "ChurnScatterPoint", "ChurnBarData", "ChurnTableRow",
    "CategoryChurnResponse", "CategoryDailyTrendResponse", "UserDetail", "CategoryUserListResponse",
    "AssetSummaryResponse", "AssetTrendResponse", "ProductClassRepurchase",
    "StoreAssetWeek", "StoreAssetResponse", "ProductAssetWeek", "ProductAssetItem", "ProductAssetResponse",
    "GeoDistributionItem", "GeoDistributionResponse", "GeoSegmentMatrixResponse", "GeoTrendResponse",
    "CategoryDistributionItem", "CategoryDistributionResponse",
    "CategoryOverviewItem", "CategoryOverviewResponse", "CategorySegmentMatrixResponse",
    "CategoryUserProfileResponse", "CategoryRepurchaseFlowRow", "CategoryRepurchaseFlowResponse",
    "ValueTierTableRow", "CategoryValueTierResponse",
    "MarketBasketItem", "MarketBasketYoYItem", "MarketBasketResponse",
    "RFMRFlowRow", "RFMRFlowResponse", "RFMFRFlowRow", "RFMFRFlowResponse",
    "RFMMFlowRow", "RFMMFlowResponse", "RFMAnalysisRow", "RFMAnalysisResponse",
    "RFMThresholds", "SegmentDefinitionItem", "RFMConfigResponse",
    "SegmentOrderRow", "SegmentOrdersResponse",
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
    "BreakdownRequest", "BreakdownRIntervalRow", "BreakdownRIntervalReverseRow",
    "BreakdownOldCustomer", "BreakdownChannelNewRow", "BreakdownChannelNewReverseRow",
    "BreakdownNewCustomer", "BreakdownGapSuggestion", "BreakdownMeta", "BreakdownLogic", "BreakdownResponse",
    "SamplingChannelSummary", "SamplingCategoryRow", "SamplingROITimeRange", "SamplingROIResponse",
    "SamplingLockCampaignInfo", "SamplingLockYearData", "SamplingLockYOY", "SamplingLockAnalysisResponse",
    "RollingYearMetrics", "RollingYOY", "RollingTimeline", "RollingComparisonResponse",
]
