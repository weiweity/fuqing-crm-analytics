"""
芙清 CRM - Pydantic 契约模型

本文件是前后端契约的唯一真实来源（Source of Truth）。
任何字段变更必须在此修改，并同步通知前端重新生成类型。
"""

from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field


# ============================================================
# 通用结构
# ============================================================

class DateRangeResponse(BaseModel):
    start: str
    end: str
    cutoff: Optional[str] = None


# ============================================================
# 核心指标
# ============================================================

class OverviewMetrics(BaseModel):
    metric_type: str
    date_range: DateRangeResponse
    amount: float = Field(..., description="GMV 或 GSV 金额")
    order_count: int
    avg_order_value: float
    new_users: int
    old_users: int
    new_user_amount: float
    old_user_amount: float
    member_amount: float
    member_count: int
    member_order_count: int
    old_user_ratio: float = Field(..., description="老客金额占比 %")
    new_user_ratio: float = Field(..., description="新客金额占比 %")
    member_ratio: float = Field(..., description="会员金额占比 %")
    member_avg_order_value: float = Field(default=0.0, description="会员客单价(AUS)")
    member_premium: float = Field(default=0.0, description="会员溢价 %（会员AUS/全店AUS）")
    mom_change: Dict[str, float]
    yoy_change: Dict[str, float]


class TrendData(BaseModel):
    metric_type: str
    dates: List[str]
    amounts: List[float]
    member_ratios: List[float] = Field(default_factory=list, description="今年会员占比 %")
    ly_amounts: List[float] = Field(default_factory=list, description="去年同周期金额")
    ly_member_ratios: List[float] = Field(default_factory=list, description="去年同周期会员占比 %")


# ============================================================
# 人群看板 (Audience)
# ============================================================

class AudienceTableRequest(BaseModel):
    dimension: str = Field(default="channel", description="维度：channel / spu_tier / spu_product_class / spu_product_subclass")
    mode: str = Field(default="mtd", description="mtd 或 free")
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    channels: Optional[List[str]] = None


class AudienceRow(BaseModel):
    dimension: str

    # 当年（current）
    gsv_users: int
    gsv: float
    aus: float
    old_users: int
    old_gsv: float
    old_aus: float
    old_gsv_ratio: float
    old_users_ratio: float
    new_users: int
    new_gsv: float
    new_aus: float
    new_gsv_ratio: float
    new_users_ratio: float
    member_users: int
    member_gsv: float
    member_aus: float
    member_gsv_ratio: float
    member_users_ratio: float
    member_old_users: int
    member_old_gsv: float
    member_old_aus: float
    member_old_gsv_ratio: float
    member_old_users_ratio: float
    member_new_users: int
    member_new_gsv: float
    member_new_aus: float
    member_new_gsv_ratio: float
    member_new_users_ratio: float

    # 去年（comparison）
    comp_gsv_users: int
    comp_gsv: float
    comp_aus: float
    comp_old_users: int
    comp_old_gsv: float
    comp_old_aus: float
    comp_old_gsv_ratio: float
    comp_old_users_ratio: float
    comp_new_users: int
    comp_new_gsv: float
    comp_new_aus: float
    comp_new_gsv_ratio: float
    comp_new_users_ratio: float
    comp_member_users: int
    comp_member_gsv: float
    comp_member_aus: float
    comp_member_gsv_ratio: float
    comp_member_users_ratio: float
    comp_member_old_users: int
    comp_member_old_gsv: float
    comp_member_old_aus: float
    comp_member_old_gsv_ratio: float
    comp_member_old_users_ratio: float
    comp_member_new_users: int
    comp_member_new_gsv: float
    comp_member_new_aus: float
    comp_member_new_gsv_ratio: float
    comp_member_new_users_ratio: float

    # 前年（prev2）
    prev2_gsv_users: int
    prev2_gsv: float
    prev2_aus: float
    prev2_old_users: int
    prev2_old_gsv: float
    prev2_old_aus: float
    prev2_old_gsv_ratio: float
    prev2_old_users_ratio: float
    prev2_new_users: int
    prev2_new_gsv: float
    prev2_new_aus: float
    prev2_new_gsv_ratio: float
    prev2_new_users_ratio: float
    prev2_member_users: int
    prev2_member_gsv: float
    prev2_member_aus: float
    prev2_member_gsv_ratio: float
    prev2_member_users_ratio: float
    prev2_member_old_users: int
    prev2_member_old_gsv: float
    prev2_member_old_aus: float
    prev2_member_old_gsv_ratio: float
    prev2_member_old_users_ratio: float
    prev2_member_new_users: int
    prev2_member_new_gsv: float
    prev2_member_new_aus: float
    prev2_member_new_gsv_ratio: float
    prev2_member_new_users_ratio: float

    # YoY（当年 vs 去年）
    yoy_gsv: Optional[float]
    yoy_gsv_users: Optional[float]
    yoy_old_gsv: Optional[float]
    yoy_old_users: Optional[float]
    yoy_new_gsv: Optional[float]
    yoy_new_users: Optional[float]
    yoy_member_gsv: Optional[float]
    yoy_member_users: Optional[float]
    yoy_member_old_gsv: Optional[float]
    yoy_member_old_users: Optional[float]
    yoy_member_new_gsv: Optional[float]
    yoy_member_new_users: Optional[float]
    yoy_aus: Optional[float]
    yoy_old_aus: Optional[float]
    yoy_new_aus: Optional[float]
    yoy_member_aus: Optional[float]
    yoy_member_old_aus: Optional[float]
    yoy_member_new_aus: Optional[float]
    yoy_old_gsv_ratio: Optional[float]
    yoy_old_users_ratio: Optional[float]
    yoy_new_gsv_ratio: Optional[float]
    yoy_new_users_ratio: Optional[float]
    yoy_member_gsv_ratio: Optional[float]
    yoy_member_users_ratio: Optional[float]
    yoy_member_old_gsv_ratio: Optional[float]
    yoy_member_old_users_ratio: Optional[float]
    yoy_member_new_gsv_ratio: Optional[float]
    yoy_member_new_users_ratio: Optional[float]


class AudienceTableResponse(BaseModel):
    dimension: str
    mode: str
    current_period: DateRangeResponse
    comparison_period: DateRangeResponse
    prev2_period: Optional[DateRangeResponse] = None
    rows: List[AudienceRow]


# ============================================================
# 人群流转 (Flow)
# ============================================================

class FlowMatrixResponse(BaseModel):
    flow_matrix: List[Dict[str, Any]]
    segments: List[Dict[str, Any]]
    from_date: str
    to_date: str
    from_total: int
    to_total: int
    summary: Dict[str, float]


class FlowSankeyResponse(BaseModel):
    nodes: List[Dict[str, Any]]
    links: List[Dict[str, Any]]
    from_date: str
    to_date: str


# ============================================================
# 流失预警 (Churn)
# ============================================================

class ChurnSegmentItem(BaseModel):
    name: str
    high: int
    medium: int
    low: int


class ChurnDistributionResponse(BaseModel):
    date: str
    churn_mode: str
    total_users: int
    high_risk: int
    medium_risk: int
    low_risk: int
    high_risk_rate: float
    by_segment: Dict[str, ChurnSegmentItem]


class ChurnUserItem(BaseModel):
    user_id: str
    segment_id: int
    segment_name: str
    risk_score: float
    risk_level: str
    last_order_days: int
    frequency: int
    monetary: float


class ChurnUsersResponse(BaseModel):
    date: str
    mode: str
    total_matched: int
    users: List[ChurnUserItem]


# ============================================================
# 资产分析 (Asset)
# ============================================================

class AssetSummaryResponse(BaseModel):
    date: str
    total_users: int
    total_gmv: float
    avg_gmv_per_user: float
    by_segment: Dict[str, Any]


class AssetTrendResponse(BaseModel):
    time_points: List[str]
    segments: List[Dict[str, Any]]
    gmv_trend: Dict[str, List[float]]
    user_trend: Dict[str, List[int]]


# ============================================================
# 地域分析 (Geo)
# ============================================================

class GeoDistributionItem(BaseModel):
    name: str
    user_count: int
    gmv: float
    user_ratio: float
    gmv_ratio: float


class GeoDistributionResponse(BaseModel):
    date: str
    level: str
    total_users: int
    total_gmv: float
    distribution: List[GeoDistributionItem]


class GeoSegmentMatrixResponse(BaseModel):
    date: str
    matrix: Dict[str, List[Dict[str, Any]]]
    segments: List[Dict[str, Any]]


class GeoTrendResponse(BaseModel):
    time_points: List[str]
    top_provinces: List[str]
    trends: Dict[str, Any]


# ============================================================
# 品类分析 (Category)
# ============================================================

class CategoryDistributionItem(BaseModel):
    name: str
    user_count: int
    member_count: int = 0
    gmv: float
    member_gsv: float = 0.0
    pct: float
    penetration_rate: float = 0.0
    member_ratio: float = 0.0


class CategoryDistributionResponse(BaseModel):
    date: str
    level: str
    total_users: int
    total_members: int = 0
    total_gmv: float
    distribution: List[CategoryDistributionItem]


class CategoryOverviewItem(BaseModel):
    name: str
    gsv: float
    gsv_yoy: Optional[float] = None
    users: int
    users_yoy: Optional[float] = None
    aus: float
    aus_yoy: Optional[float] = None
    old_gsv: float
    old_gsv_yoy: Optional[float] = None
    old_ratio: float
    old_ratio_yoy: Optional[float] = None
    old_users: int
    old_users_yoy: Optional[float] = None
    old_aus: float
    old_aus_yoy: Optional[float] = None
    new_gsv: float
    new_gsv_yoy: Optional[float] = None
    new_ratio: float
    new_ratio_yoy: Optional[float] = None
    new_users: int
    new_users_yoy: Optional[float] = None
    new_aus: float
    new_aus_yoy: Optional[float] = None
    old_users_ratio: Optional[float] = None
    old_users_ratio_yoy: Optional[float] = None
    new_users_ratio: Optional[float] = None
    new_users_ratio_yoy: Optional[float] = None
    member_ratio: Optional[float] = None
    member_ratio_yoy: Optional[float] = None


class CategoryOverviewResponse(BaseModel):
    date_start: str
    date_end: str
    level: str
    channel: Optional[str] = None
    metric_type: str
    all_rows: List[CategoryOverviewItem]
    member_rows: List[CategoryOverviewItem]
    all_ttl: Optional[CategoryOverviewItem] = None
    member_ttl: Optional[CategoryOverviewItem] = None


class CategorySegmentMatrixResponse(BaseModel):
    date: str
    level: str
    matrix: Dict[str, List[Dict[str, Any]]]
    segments: List[Dict[str, Any]]


class CategoryUserProfileResponse(BaseModel):
    date: str
    category: str
    type: Optional[str]
    total_users: int
    total_gmv: float
    avg_order_value: float
    avg_frequency: float
    segment_distribution: List[Dict[str, Any]]
    province_distribution: List[Dict[str, Any]]
    channel_distribution: List[Dict[str, Any]]


# ============================================================
# 品类看板 - 品类回购分析（同品/跨品类 R区间回购）
# ============================================================

class CategoryRepurchaseFlowRow(BaseModel):
    """品类回购分析单行数据（复用 RFMRFlowRow 结构）"""
    r_segment: str

    hist_users_current: int = 0
    repurchase_users_current: int = 0
    repurchase_rate_current: float = 0.0
    repurchase_gsv_current: float = 0.0
    repurchase_gsv_ratio_current: float = 0.0

    hist_users_comp: int = 0
    repurchase_rate_comp: float = 0.0

    hist_users_prev2: int = 0
    repurchase_rate_prev2: float = 0.0

    yoy_hist_users: Optional[float] = None
    yoy_repurchase_users: Optional[float] = None
    yoy_repurchase_rate: Optional[float] = None
    yoy_repurchase_gsv: Optional[float] = None
    yoy_repurchase_gsv_ratio: Optional[float] = None


class CategoryRepurchaseFlowResponse(BaseModel):
    """品类回购分析完整响应"""
    year_label: str = "2026"
    comp_year_label: str = "2025"
    prev2_year_label: str = "2024"
    target_category: str
    same_category_rows: List[CategoryRepurchaseFlowRow] = Field(default_factory=list, description="同品回购明细")
    cross_category_rows: List[CategoryRepurchaseFlowRow] = Field(default_factory=list, description="跨品类回购明细")
    member_same_category_rows: List[CategoryRepurchaseFlowRow] = Field(default_factory=list, description="会员同品回购明细")
    member_cross_category_rows: List[CategoryRepurchaseFlowRow] = Field(default_factory=list, description="会员跨品类回购明细")


# ============================================================
# 人群看板 - 汇总（30指标对比 + 渠道概览）
# ============================================================

class ChannelGSVRow(BaseModel):
    channel: str
    gsv_2026: float = 0.0
    gsv_2025: float = 0.0
    yoy: Optional[float] = None          # YOY增长率
    ratio_2026: Optional[float] = None   # 2026年占全店比例
    ratio_2025: Optional[float] = None   # 2025年占全店比例
    ratio_yoy: Optional[float] = None   # 占比YOY
    # 人数（Panel B=全店人数, Panel C=会员人数）
    users_2026: Optional[float] = None
    users_2025: Optional[float] = None
    users_yoy: Optional[float] = None
    # AUS（Panel B=全店AUS, Panel C=会员AUS）
    aus_2026: Optional[float] = None
    aus_2025: Optional[float] = None
    aus_yoy: Optional[float] = None
    # 新客GSV
    new_gsv_2026: Optional[float] = None
    new_gsv_2025: Optional[float] = None
    new_gsv_yoy: Optional[float] = None
    new_gsv_ratio_2026: Optional[float] = None
    new_gsv_ratio_2025: Optional[float] = None
    new_gsv_ratio_yoy: Optional[float] = None
    # 老客GSV
    old_gsv_2026: Optional[float] = None
    old_gsv_2025: Optional[float] = None
    old_gsv_yoy: Optional[float] = None
    old_gsv_ratio_2026: Optional[float] = None
    old_gsv_ratio_2025: Optional[float] = None
    old_gsv_ratio_yoy: Optional[float] = None
    # 新客人数（Panel B=全店新客人数, Panel C=会员新客人数）
    new_users_2026: Optional[float] = None
    new_users_2025: Optional[float] = None
    new_users_yoy: Optional[float] = None
    # 新客AUS（Panel B=全店新客AUS, Panel C=会员新客AUS）
    new_aus_2026: Optional[float] = None
    new_aus_2025: Optional[float] = None
    new_aus_yoy: Optional[float] = None
    # 老客人数（Panel B=全店老客人数, Panel C=会员老客人数）
    old_users_2026: Optional[float] = None
    old_users_2025: Optional[float] = None
    old_users_yoy: Optional[float] = None
    # 老客AUS（Panel B=全店老客AUS, Panel C=会员老客AUS）
    old_aus_2026: Optional[float] = None
    old_aus_2025: Optional[float] = None
    old_aus_yoy: Optional[float] = None
    # 会员占该渠道比例（Panel C 专用）
    member_ratio_2026: Optional[float] = None
    member_ratio_2025: Optional[float] = None
    member_ratio_yoy: Optional[float] = None
    # 会员视角新/老客GSV（供 channel_member 列扩展使用）
    member_new_gsv_2026: Optional[float] = None
    member_new_gsv_2025: Optional[float] = None
    member_new_gsv_yoy: Optional[float] = None
    member_new_gsv_ratio_2026: Optional[float] = None
    member_new_gsv_ratio_2025: Optional[float] = None
    member_new_gsv_ratio_yoy: Optional[float] = None
    member_old_gsv_2026: Optional[float] = None
    member_old_gsv_2025: Optional[float] = None
    member_old_gsv_yoy: Optional[float] = None
    member_old_gsv_ratio_2026: Optional[float] = None
    member_old_gsv_ratio_2025: Optional[float] = None
    member_old_gsv_ratio_yoy: Optional[float] = None
    # 交叉指标：会员新客/老客 GSV 占全店新客/老客 GSV 比例
    member_new_vs_all_new_2026: Optional[float] = None
    member_new_vs_all_new_2025: Optional[float] = None
    member_new_vs_all_new_yoy: Optional[float] = None
    member_old_vs_all_old_2026: Optional[float] = None
    member_old_vs_all_old_2025: Optional[float] = None
    member_old_vs_all_old_yoy: Optional[float] = None


class AudiencePeriodMetrics(BaseModel):
    """单个周期的30项指标"""
    # 全店
    gsv: float = 0.0
    users: int = 0
    aus: float = 0.0
    # 老客
    old_gsv: float = 0.0
    old_users: int = 0
    old_aus: float = 0.0
    old_gsv_ratio: float = 0.0
    old_users_ratio: float = 0.0
    # 新客
    new_gsv: float = 0.0
    new_users: int = 0
    new_aus: float = 0.0
    new_gsv_ratio: float = 0.0
    new_users_ratio: float = 0.0
    # 会员
    member_gsv: float = 0.0
    member_users: int = 0
    member_aus: float = 0.0
    member_penetration: float = 0.0   # 会员渗透率 = 会员人数/全店人数
    member_users_ratio: float = 0.0
    # 会员老客
    member_old_gsv: float = 0.0
    member_old_users: int = 0
    member_old_aus: float = 0.0
    member_old_gsv_ratio: float = 0.0
    member_old_users_ratio: float = 0.0
    # 会员新客
    member_new_gsv: float = 0.0
    member_new_users: int = 0
    member_new_aus: float = 0.0
    member_new_gsv_ratio: float = 0.0
    member_new_users_ratio: float = 0.0


class YearComparisonRow(BaseModel):
    """30指标对比表格的一行"""
    field: str
    kind: str = "money"           # 指标类型: money | ratio | count | aus
    value_2026: Optional[float] = None
    value_2025: Optional[float] = None
    value_2024: Optional[float] = None
    yoy: Optional[float] = None    # 相对2025的YOY


class AudienceSummaryRequest(BaseModel):
    year: int = Field(default=2026, description="对比基准年，如2026")
    metric_type: str = Field(default="GSV", description="GMV 或 GSV")


class AudienceSummaryResponse(BaseModel):
    year_label: str = "2026"        # 当期年份标签（支持自定义日期范围的年份）
    comp_year_label: str = "2025"   # 同比年份标签
    prev2_year_label: str = "2024"  # 前年年份标签
    metric_type: str
    # Panel A: 30指标对比
    indicators: List[YearComparisonRow]
    # Panel B: 渠道概览-全店
    channel_all: List[ChannelGSVRow]
    # Panel C: 渠道概览-会员
    channel_member: List[ChannelGSVRow]


# ============================================================
# RFM - R区间流转看板
# ============================================================

class RFMRFlowRow(BaseModel):
    r_segment: str

    hist_users_current: int = 0
    repurchase_users_current: int = 0
    repurchase_rate_current: float = 0.0
    repurchase_gsv_current: float = 0.0
    repurchase_gsv_ratio_current: float = 0.0

    hist_users_comp: int = 0
    repurchase_users_comp: int = 0
    repurchase_rate_comp: float = 0.0
    repurchase_gsv_comp: float = 0.0
    repurchase_gsv_ratio_comp: float = 0.0

    hist_users_prev2: int = 0
    repurchase_users_prev2: int = 0
    repurchase_rate_prev2: float = 0.0
    repurchase_gsv_prev2: float = 0.0
    repurchase_gsv_ratio_prev2: float = 0.0

    yoy_hist_users: Optional[float] = None
    yoy_repurchase_users: Optional[float] = None
    yoy_repurchase_rate: Optional[float] = None
    yoy_repurchase_gsv: Optional[float] = None
    yoy_repurchase_gsv_ratio: Optional[float] = None


class RFMRFlowResponse(BaseModel):
    year_label: str = "2026"
    comp_year_label: str = "2025"
    prev2_year_label: str = "2024"
    metric_type: str
    rows: List[RFMRFlowRow]
    same_channel_rows: List[RFMRFlowRow] = Field(default_factory=list, description="本渠道回购本渠道数据")
    member_rows: List[RFMRFlowRow] = Field(default_factory=list, description="会员-本渠道唤醒贡献")
    member_same_channel_rows: List[RFMRFlowRow] = Field(default_factory=list, description="会员-本渠道回购本渠道")


# ============================================================
# RFM - F区间流转看板
# ============================================================

class RFMFRFlowRow(BaseModel):
    f_segment: str

    hist_users_current: int = 0
    repurchase_users_current: int = 0
    repurchase_rate_current: float = 0.0
    repurchase_gsv_current: float = 0.0
    repurchase_gsv_ratio_current: float = 0.0

    hist_users_comp: int = 0
    repurchase_users_comp: int = 0
    repurchase_rate_comp: float = 0.0
    repurchase_gsv_comp: float = 0.0
    repurchase_gsv_ratio_comp: float = 0.0

    hist_users_prev2: int = 0
    repurchase_users_prev2: int = 0
    repurchase_rate_prev2: float = 0.0
    repurchase_gsv_prev2: float = 0.0
    repurchase_gsv_ratio_prev2: float = 0.0

    yoy_hist_users: Optional[float] = None
    yoy_repurchase_users: Optional[float] = None
    yoy_repurchase_rate: Optional[float] = None
    yoy_repurchase_gsv: Optional[float] = None
    yoy_repurchase_gsv_ratio: Optional[float] = None


class RFMFRFlowResponse(BaseModel):
    year_label: str = "2026"
    comp_year_label: str = "2025"
    prev2_year_label: str = "2024"
    metric_type: str
    rows: List[RFMFRFlowRow]
    same_channel_rows: List[RFMFRFlowRow] = Field(default_factory=list)
    member_rows: List[RFMFRFlowRow] = Field(default_factory=list)
    member_same_channel_rows: List[RFMFRFlowRow] = Field(default_factory=list)


# ============================================================
# RFM - M区间流转看板
# ============================================================

class RFMMFlowRow(BaseModel):
    m_segment: str

    hist_users_current: int = 0
    repurchase_users_current: int = 0
    repurchase_rate_current: float = 0.0
    repurchase_gsv_current: float = 0.0
    repurchase_gsv_ratio_current: float = 0.0

    hist_users_comp: int = 0
    repurchase_users_comp: int = 0
    repurchase_rate_comp: float = 0.0
    repurchase_gsv_comp: float = 0.0
    repurchase_gsv_ratio_comp: float = 0.0

    hist_users_prev2: int = 0
    repurchase_users_prev2: int = 0
    repurchase_rate_prev2: float = 0.0
    repurchase_gsv_prev2: float = 0.0
    repurchase_gsv_ratio_prev2: float = 0.0

    yoy_hist_users: Optional[float] = None
    yoy_repurchase_users: Optional[float] = None
    yoy_repurchase_rate: Optional[float] = None
    yoy_repurchase_gsv: Optional[float] = None
    yoy_repurchase_gsv_ratio: Optional[float] = None


class RFMMFlowResponse(BaseModel):
    year_label: str = "2026"
    comp_year_label: str = "2025"
    prev2_year_label: str = "2024"
    metric_type: str
    rows: List[RFMMFlowRow]
    same_channel_rows: List[RFMMFlowRow] = Field(default_factory=list)
    member_rows: List[RFMMFlowRow] = Field(default_factory=list)
    member_same_channel_rows: List[RFMMFlowRow] = Field(default_factory=list)


# ============================================================
# 导出 (Export)
# ============================================================

class ExportPPTRequest(BaseModel):
    report_type: str = "weekly"
    start_date: str = "2026-03-01"
    end_date: str = "2026-03-19"
    modules: List[str] = ["cover", "metrics", "segments", "geo", "category"]
    template: str = "default"


class ExportPPTResponse(BaseModel):
    report_id: Optional[str] = None
    file_name: Optional[str] = None
    download_url: Optional[str] = None
    error: Optional[str] = None


class TemplatesResponse(BaseModel):
    templates: List[Dict[str, Any]]
    modules: List[str]


# ============================================================
# 老客健康分析仪表盘 (Phase 1)
# ============================================================

class HealthAlertItem(BaseModel):
    """健康度告警项"""
    alert_type: str = Field(..., description="告警类型编码")
    alert_name: str = Field(..., description="告警名称")
    severity: str = Field(..., description="high | medium | low")
    current_value: float = Field(..., description="当前值")
    threshold_value: float = Field(..., description="阈值")
    comparison_basis: str = Field(..., description="yoy | mom | absolute")
    suggested_action: str = Field(..., description="建议行动")
    target_tab: str = Field(..., description="跳转目标Tab名")


class HealthOverviewMetrics(BaseModel):
    """现状概览指标 - 运营日报"""
    analysis_date: str = Field(..., description="分析日期 YYYY-MM-DD")
    period_days: int = Field(default=30, description="分析周期天数")

    # 核心指标（当期）
    all_store_repurchase_rate: float = Field(..., description="全店复购率")
    same_product_repurchase_rate: float = Field(..., description="本品复购率")
    period_repurchase_users: int = Field(..., description="周期复购人数（同分析周期）")

    # 老客指标
    old_gsv: float = Field(..., description="老客GSV")
    old_users: int = Field(..., description="老客人数")
    old_customer_gsv_ratio: float = Field(..., description="老客GSV占比")
    old_customer_aus: float = Field(..., description="老客AUS")

    # 会员老客指标
    member_old_gsv: float = Field(..., description="会员老客GSV")
    member_old_users: int = Field(..., description="会员老客人数")
    member_old_customer_gsv_ratio: float = Field(..., description="会员老客GSV占比")
    member_old_customer_aus: float = Field(..., description="会员老客AUS")

    # 健康评分（归一化后加权 0-100）
    health_score: float = Field(..., description="健康评分 0-100")
    health_level: str = Field(..., description="healthy | warning | critical")
    ly_health_score: Optional[float] = Field(None, description="去年同期健康评分")
    health_score_yoy: Optional[float] = Field(None, description="健康评分同比（百分点差）")

    # 去年同期原始值（用于雷达图两年对比）
    ly_all_store_repurchase_rate: Optional[float] = Field(None, description="去年同期全店复购率")
    ly_same_product_repurchase_rate: Optional[float] = Field(None, description="去年同期本品复购率")
    ly_old_customer_gsv_ratio: Optional[float] = Field(None, description="去年同期老客GSV占比")
    ly_old_customer_aus: Optional[float] = Field(None, description="去年同期老客AUS")
    ly_period_repurchase_users: Optional[int] = Field(None, description="去年同期周期复购人数")

    # 同比（vs去年同期同周期）
    yoy_all_store_repurchase_rate: Optional[float] = Field(None, description="全店复购率同比")
    yoy_same_product_repurchase_rate: Optional[float] = Field(None, description="本品复购率同比")
    yoy_old_customer_gsv_ratio: Optional[float] = Field(None, description="老客占比同比")
    yoy_old_customer_aus: Optional[float] = Field(None, description="老客AUS同比")
    yoy_period_repurchase_users: Optional[float] = Field(None, description="周期复购人数同比")
    yoy_old_gsv: Optional[float] = Field(None, description="老客GSV同比")
    yoy_old_users: Optional[float] = Field(None, description="老客人数同比")
    yoy_member_old_gsv: Optional[float] = Field(None, description="会员老客GSV同比")
    yoy_member_old_users: Optional[float] = Field(None, description="会员老客人数同比")
    yoy_member_old_customer_gsv_ratio: Optional[float] = Field(None, description="会员老客GSV占比同比")
    yoy_member_old_customer_aus: Optional[float] = Field(None, description="会员老客AUS同比")

    # 环比（vs上一个等长周期）
    mom_period_repurchase_users: Optional[float] = Field(None, description="周期复购人数环比")

    # 告警列表
    alerts: List[HealthAlertItem] = Field(default_factory=list, description="告警列表")


# ============================================================
# 老客健康分析仪表盘 (Phase 2)
# ============================================================

class RepurchaseBucket(BaseModel):
    """复购间隔桶（含去年同期对比）"""
    bucket_label: str = Field(..., description="桶标签 如'0-7天'")
    bucket_start: int = Field(..., description="桶起始天数")
    bucket_end: Optional[int] = Field(None, description="桶结束天数（None表示无上限）")
    user_count: int = Field(..., description="该桶人数")
    user_ratio: float = Field(..., description="占复购人群比例")
    # 去年同期
    ly_user_count: Optional[int] = Field(None, description="去年同期该桶人数")
    ly_user_ratio: Optional[float] = Field(None, description="去年同期占比")
    # 前年同期
    prev2_user_count: Optional[int] = Field(None, description="前年同期该桶人数")
    prev2_user_ratio: Optional[float] = Field(None, description="前年同期占比")
    # YOY
    user_count_yoy: Optional[float] = Field(None, description="人数同比（绝对值变化）")
    user_ratio_yoy: Optional[float] = Field(None, description="占比同比（pp变化）")


class ProductClassRepurchase(BaseModel):
    """品类复购指标（含同比）"""
    product_class: str = Field(..., description="品类名称")
    total_buyers: int = Field(..., description="购买人数")
    repurchase_users: int = Field(..., description="复购人数")
    repurchase_rate: float = Field(..., description="复购率")
    median_days: int = Field(..., description="中位复购天数")
    p25_days: int = Field(..., description="P25复购天数")
    p75_days: int = Field(..., description="P75复购天数")
    avg_days: Optional[float] = Field(None, description="平均复购天数")
    avg_order_value: float = Field(..., description="客单价（含首购）")
    gsv: float = Field(..., description="GSV（含首购）")
    repurchase_order_value: float = Field(..., description="复购客单价（仅复购订单）")
    repurchase_gsv: float = Field(..., description="复购GSV（仅复购订单）")
    # 同比
    ly_repurchase_rate: Optional[float] = Field(None, description="去年同期复购率")
    ly_median_days: Optional[int] = Field(None, description="去年同期中位天数")
    ly_avg_days: Optional[float] = Field(None, description="去年同期平均天数")
    ly_gsv: Optional[float] = Field(None, description="去年同期GSV")
    # YOY
    repurchase_rate_yoy: Optional[float] = Field(None, description="复购率同比(pp)")
    median_days_yoy: Optional[float] = Field(None, description="中位天数同比(pp)")
    avg_days_yoy: Optional[float] = Field(None, description="平均天数YOY")
    gsv_yoy: Optional[float] = Field(None, description="GSV同比")


class RepurchaseCycleOverview(BaseModel):
    """复购周期概览"""
    period_start: str = Field(..., description="开始日期")
    period_end: str = Field(..., description="结束日期")

    # 全店分布
    all_store_median_days: int = Field(..., description="中位复购天数")
    all_store_p25_days: int = Field(..., description="P25")
    all_store_p75_days: int = Field(..., description="P75")
    all_store_avg_days: float = Field(..., description="平均复购天数")

    # 分桶分布
    bucket_distribution: List[RepurchaseBucket] = Field(default_factory=list)

    # 分品类
    by_product_class: List[ProductClassRepurchase] = Field(default_factory=list)
    by_product_class_return: List[ProductClassRepurchase] = Field(
        default_factory=list,
        description="跨品类回购店铺指标（首购该品类后又买店铺任意品类）"
    )

    # 年份标签（供3年对比图表使用）
    year_label: str = Field(..., description="当前年份")
    comp_year_label: str = Field(..., description="对比年份（去年）")
    prev2_year_label: str = Field(..., description="前年")


class CohortRetentionResponse(BaseModel):
    """Cohort留存矩阵"""
    cohort_months: List[str] = Field(default_factory=list, description="首购月份列表")
    periods: List[str] = Field(default_factory=list, description="周期标签 M0/M1/M2...")
    matrix: List[List[Optional[float]]] = Field(default_factory=list, description="复购率矩阵")
    avg_by_period: List[Optional[float]] = Field(default_factory=list, description="各周期平均复购率")
    ly_matrix: List[List[Optional[float]]] = Field(default_factory=list, description="去年同期复购率矩阵")
    ly_avg_by_period: List[Optional[float]] = Field(default_factory=list, description="去年同期各周期平均复购率")


# ─────────────────────────────────────────────────────────────
# 价值分层
# ─────────────────────────────────────────────────────────────

class ValueTierDefinition(BaseModel):
    """价值分层定义（动态计算）"""
    tier_code: str = Field(..., description="S/A/B/C")
    tier_name: str = Field(..., description="层级名称")
    gsv_threshold_min: Optional[float] = Field(None, description="GSV下限")
    gsv_threshold_max: Optional[float] = Field(None, description="GSV上限")
    user_count: int = Field(..., description="人数")
    gsv: float = Field(..., description="GSV")
    gsv_ratio: float = Field(..., description="占全店GSV比例")


class FrequencyTierDefinition(BaseModel):
    """频次分层定义"""
    tier_code: str = Field(..., description="high/medium/low")
    tier_name: str = Field(..., description="频次名称")
    order_threshold_min: int = Field(..., description="订单数下限")
    order_threshold_max: Optional[int] = Field(None, description="订单数上限")
    user_count: int = Field(..., description="人数")


class CustomerSegmentItem(BaseModel):
    """运营分层项（价值×频次交叉）"""
    segment_code: str = Field(..., description="如 S-high")
    segment_name: str = Field(..., description="如 超级用户")
    value_tier: str = Field(..., description="价值层级")
    frequency_tier: str = Field(..., description="频次层级")
    user_count: int = Field(..., description="人数")
    gsv: float = Field(..., description="GSV")
    gsv_ratio: float = Field(..., description="GSV占比")
    avg_order_value: float = Field(..., description="客单价")
    avg_orders_per_user: float = Field(..., description="人均订单数")
    suggested_action: str = Field(..., description="建议运营动作")
    priority: int = Field(..., description="优先级 1-6")


class ValueTierResponse(BaseModel):
    """价值分层响应"""
    analysis_date: str = Field(..., description="分析日期")
    lookback_days: int = Field(default=365, description="回溯天数")
    value_tiers: List[ValueTierDefinition] = Field(default_factory=list)
    frequency_tiers: List[FrequencyTierDefinition] = Field(default_factory=list)
    segments: List[CustomerSegmentItem] = Field(default_factory=list)
    insights: List[str] = Field(default_factory=list, description="自动洞察")


# ─────────────────────────────────────────────────────────────
# 价值分层回购率流转（逻辑同R区间，分层维度替换为S/A/B/C×高/中/低频）
# ─────────────────────────────────────────────────────────────

class TierFlowRow(BaseModel):
    """价值分层回购率单行数据"""
    tier_segment: str = Field(..., description="分层标签，如 S-高频")
    hist_users_current: int = Field(default=0)
    repurchase_users_current: int = Field(default=0)
    repurchase_rate_current: float = Field(default=0.0)
    repurchase_gsv_current: float = Field(default=0.0)
    repurchase_gsv_ratio_current: float = Field(default=0.0)
    hist_users_comp: int = Field(default=0)
    repurchase_users_comp: int = Field(default=0)
    repurchase_rate_comp: float = Field(default=0.0)
    repurchase_gsv_comp: float = Field(default=0.0)
    repurchase_gsv_ratio_comp: float = Field(default=0.0)
    hist_users_prev2: int = Field(default=0)
    repurchase_users_prev2: int = Field(default=0)
    repurchase_rate_prev2: float = Field(default=0.0)
    repurchase_gsv_prev2: float = Field(default=0.0)
    repurchase_gsv_ratio_prev2: float = Field(default=0.0)
    yoy_hist_users: Optional[float] = Field(None)
    yoy_repurchase_users: Optional[float] = Field(None)
    yoy_repurchase_rate: Optional[float] = Field(None)
    yoy_repurchase_gsv: Optional[float] = Field(None)
    yoy_repurchase_gsv_ratio: Optional[float] = Field(None)


class TierFlowResponse(BaseModel):
    """价值分层回购率流转响应"""
    year_label: str = Field(..., description="当前年份")
    comp_year_label: str = Field(..., description="对比年份（去年）")
    prev2_year_label: str = Field(..., description="前年")
    metric_type: str = Field(default="GSV")
    rows: List[TierFlowRow] = Field(default_factory=list)
    same_channel_rows: List[TierFlowRow] = Field(default_factory=list)
    member_rows: List[TierFlowRow] = Field(default_factory=list)
    member_same_channel_rows: List[TierFlowRow] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────
# RFM完整分析（8象限人群分群）
# ─────────────────────────────────────────────────────────────

class RFMAnalysisRow(BaseModel):
    """RFM 8象限分析单行数据"""
    rfm_segment: str = Field(..., description="人群标签，如 重要价值客户")
    hist_users_current: int = Field(default=0)
    repurchase_users_current: int = Field(default=0)
    repurchase_rate_current: float = Field(default=0.0)
    repurchase_gsv_current: float = Field(default=0.0)
    repurchase_gsv_ratio_current: float = Field(default=0.0)
    hist_users_comp: int = Field(default=0)
    repurchase_users_comp: int = Field(default=0)
    repurchase_rate_comp: float = Field(default=0.0)
    repurchase_gsv_comp: float = Field(default=0.0)
    repurchase_gsv_ratio_comp: float = Field(default=0.0)
    hist_users_prev2: int = Field(default=0)
    repurchase_users_prev2: int = Field(default=0)
    repurchase_rate_prev2: float = Field(default=0.0)
    repurchase_gsv_prev2: float = Field(default=0.0)
    repurchase_gsv_ratio_prev2: float = Field(default=0.0)
    yoy_hist_users: Optional[float] = Field(None)
    yoy_repurchase_users: Optional[float] = Field(None)
    yoy_repurchase_rate: Optional[float] = Field(None)
    yoy_repurchase_gsv: Optional[float] = Field(None)
    yoy_repurchase_gsv_ratio: Optional[float] = Field(None)


class RFMAnalysisResponse(BaseModel):
    """RFM 8象限分析响应"""
    year_label: str = Field(..., description="当前年份")
    comp_year_label: str = Field(..., description="对比年份（去年）")
    prev2_year_label: str = Field(..., description="前年")
    metric_type: str = Field(default="GSV")
    rows: List[RFMAnalysisRow] = Field(default_factory=list)
    same_channel_rows: List[RFMAnalysisRow] = Field(default_factory=list)
    member_rows: List[RFMAnalysisRow] = Field(default_factory=list)
    member_same_channel_rows: List[RFMAnalysisRow] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────
# 新客转化
# ─────────────────────────────────────────────────────────────

class NewCustomerConversionFunnel(BaseModel):
    """新客转化漏斗"""
    cohort_date: str = Field(..., description="首购月份")
    total_first_purchase: int = Field(..., description="首购人数")
    day7_repurchase: int = Field(default=0)
    day7_rate: float = Field(default=0.0)
    day30_repurchase: int = Field(default=0)
    day30_rate: float = Field(default=0.0)
    day90_repurchase: int = Field(default=0)
    day90_rate: float = Field(default=0.0)
    year_repurchase: int = Field(default=0)
    year_rate: float = Field(default=0.0)
    day7_not_repurchased: int = Field(default=0)
    day30_not_repurchased: int = Field(default=0)
    day90_not_repurchased: int = Field(default=0)


class NewCustomerChannelQuality(BaseModel):
    """分渠道新客质量"""
    channel: str = Field(..., description="渠道")
    first_purchase_users: int = Field(..., description="首购人数")
    first_purchase_aus: float = Field(..., description="首购客单价")
    day30_repurchase_rate: float = Field(default=0.0)
    day90_repurchase_rate: float = Field(default=0.0)
    avg_days_to_repurchase: Optional[float] = Field(None)
    quality_score: float = Field(..., description="质量分 0-100")
    quality_grade: str = Field(..., description="A/B/C/D")


class NewCustomerConversionResponse(BaseModel):
    """新客转化追踪响应"""
    analysis_date: str = Field(..., description="分析日期")
    overall_funnel: NewCustomerConversionFunnel = Field(default_factory=lambda: NewCustomerConversionFunnel(cohort_date="", total_first_purchase=0))
    cohort_funnels: List[NewCustomerConversionFunnel] = Field(default_factory=list)
    channel_quality: List[NewCustomerChannelQuality] = Field(default_factory=list)
    monthly_trend: List[Dict[str, Any]] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────
# 大促日历
# ─────────────────────────────────────────────────────────────

class PromotionPeriod(BaseModel):
    """大促周期定义"""
    name: str = Field(..., description="活动名称")
    start_date: str = Field(...)
    end_date: str = Field(...)
    year: int = Field(...)


class PromotionVsDailyMetrics(BaseModel):
    """单个大促 vs 日常对比"""
    promotion: PromotionPeriod = Field(...)
    promo_old_customer_count: int = Field(default=0)
    promo_old_customer_gsv: float = Field(default=0.0)
    promo_old_customer_aus: float = Field(default=0.0)
    promo_repurchase_rate: float = Field(default=0.0)
    daily_old_customer_count: int = Field(default=0)
    daily_old_customer_gsv: float = Field(default=0.0)
    daily_old_customer_aus: float = Field(default=0.0)
    daily_repurchase_rate: float = Field(default=0.0)
    gsv_lift: Optional[float] = Field(None)
    aus_lift: Optional[float] = Field(None)
    repurchase_lift: Optional[float] = Field(None)


class PromotionCalendarResponse(BaseModel):
    """大促日历响应"""
    analysis_year: int = Field(...)
    promotions: List[PromotionVsDailyMetrics] = Field(default_factory=list)
    annual_promo_gsv_ratio: float = Field(default=0.0)
    annual_promo_user_ratio: float = Field(default=0.0)
    promo_dependency_score: float = Field(default=0.0)
    dependency_level: str = Field(default="low")


# ─────────────────────────────────────────────────────────────
# 渠道健康评分对比
# ─────────────────────────────────────────────────────────────

class ChannelHealthScoreItem(BaseModel):
    """单个渠道健康评分"""
    channel: str = Field(..., description="渠道UI名称")
    health_score: float = Field(..., description="当期健康评分")
    health_level: str = Field(..., description="healthy | warning | critical")
    ly_health_score: Optional[float] = Field(None, description="去年同期健康评分")
    health_score_yoy: Optional[float] = Field(None, description="健康评分同比（百分点差）")


class HealthTargetsResponse(BaseModel):
    """健康评分目标值（自动沿用去年同周期实际值）"""
    analysis_date: str = Field(..., description="分析日期 YYYY-MM-DD")
    period_days: int = Field(default=30, description="分析周期天数")
    channel: Optional[str] = Field(None, description="指定渠道")
    exclude_channels: Optional[List[str]] = Field(None, description="排除渠道")
    # 五项指标目标值（沿用去年同周期实际值）
    all_store_repurchase_rate: float = Field(..., description="全店复购率目标")
    same_product_repurchase_rate: float = Field(..., description="本品复购率目标")
    old_customer_gsv_ratio: float = Field(..., description="老客占比目标")
    old_customer_aus: float = Field(..., description="老客AUS目标")
    recent_7d_repurchase_users: int = Field(..., description="周均复购人数目标")


class ChannelHealthScoresResponse(BaseModel):
    """所有渠道健康评分对比"""
    analysis_date: str = Field(...)
    period_days: int = Field(default=30)
    exclude_channels: Optional[List[str]] = Field(None)
    scores: List[ChannelHealthScoreItem] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────
# 配置历史/回滚 + 审计日志
# ─────────────────────────────────────────────────────────────

class ConfigHistoryItem(BaseModel):
    """配置历史备份项"""
    backup_id: str = Field(..., description="备份ID")
    action: str = Field(..., description="触发动作 update | reset")
    timestamp: str = Field(..., description="备份时间 ISO8601")
    file_name: str = Field(..., description="备份文件名")


class ConfigHistoryResponse(BaseModel):
    """配置历史列表响应"""
    history: List[ConfigHistoryItem] = Field(default_factory=list)


class ConfigRestoreResponse(BaseModel):
    """配置恢复响应"""
    success: bool = Field(default=True)
    restored_backup_id: str = Field(..., description="恢复的备份ID")
    config: Dict[str, Any] = Field(default_factory=dict, description="恢复后的完整配置")


class AuditLogItem(BaseModel):
    """审计日志项"""
    timestamp: str = Field(..., description="操作时间 ISO8601")
    action: str = Field(..., description="动作 update | reset | restore")
    details: Dict[str, Any] = Field(default_factory=dict, description="操作详情")


class AuditLogResponse(BaseModel):
    """审计日志列表响应"""
    logs: List[AuditLogItem] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────
# RFM 阈值配置（前后端同步唯一数据源）
# ─────────────────────────────────────────────────────────────

class RFMThresholds(BaseModel):
    """RFM 评分阈值"""
    r: List[int] = Field(..., description="R阈值：[30,90,180,365] 对应 5/4/3/2/1 分")
    f: List[int] = Field(..., description="F阈值：[1,2,3,4] 对应 1/2/3/4/5 分")
    m: List[int] = Field(..., description="M阈值：[100,300,500,1000] 对应 1/2/3/4/5 分")


class SegmentDefinitionItem(BaseModel):
    """8象限人群定义项"""
    segment_id: int = Field(..., description="象限ID 1-8")
    name_cn: str = Field(..., description="中文名")
    name_en: str = Field(..., description="英文名")
    r_high: bool = Field(..., description="R是否高分（>=4）")
    f_high: bool = Field(..., description="F是否高分（>=4）")
    m_high: bool = Field(..., description="M是否高分（>=4）")
    description: str = Field(..., description="人群描述")
    color: str = Field(..., description="展示颜色")
    priority: int = Field(..., description="优先级 1-8")


class RFMConfigResponse(BaseModel):
    """RFM 配置响应（阈值 + 象限定义）"""
    thresholds: RFMThresholds = Field(..., description="R/F/M 评分阈值")
    segments: List[SegmentDefinitionItem] = Field(default_factory=list, description="8象限定义列表")


# ─────────────────────────────────────────────────────────────
# 品类看板 v2 - 价值分层 (ValueTierTab)
# ─────────────────────────────────────────────────────────────

class WoolPartyBreakdown(BaseModel):
    """羊毛党细分统计"""
    type1_count: int  # 历史有正装，后续一直买小样
    type2_count: int  # 历史只买小样
    total_count: int
    type1_ratio: float
    type2_ratio: float


class DualAxisLineData(BaseModel):
    """双轴折线图数据"""
    categories: List[str]
    wool_party_ratios: List[float]
    high_value_ratios: List[float]


class ValueTierTableRow(BaseModel):
    """价值分层-表格行"""
    category_name: str
    total_users: int
    high_value_users: int
    high_value_ratio: float
    wool_party: WoolPartyBreakdown
    member_ratio: float
    avg_aus: float
    value_score: float
    value_grade: str  # A/B/C/D/E


class CategoryValueTierResponse(BaseModel):
    """价值分层 Tab 响应"""
    dual_axis_line: DualAxisLineData
    table: List[ValueTierTableRow]
    operation_suggestions: List[str]
    data_quality_note: str
    # 多时间窗口羊毛党数据（30天/90天/全部历史）
    wool_party_by_window: Optional[Dict[str, List[ValueTierTableRow]]] = None


# ─────────────────────────────────────────────────────────────
# 品类看板 v2 - 品类流转 (CategoryFlowTab)
# ─────────────────────────────────────────────────────────────

class SankeyNode(BaseModel):
    """桑基图节点"""
    name: str
    category_name: str


class SankeyLink(BaseModel):
    """桑基图连线"""
    source: str
    target: str
    value: int


class SankeyGraphData(BaseModel):
    """桑基图数据"""
    nodes: List[SankeyNode]
    links: List[SankeyLink]


class FlowMatrixCell(BaseModel):
    """流转矩阵单元格"""
    source_category: str
    target_category: str
    user_count: int
    ratio: float
    concentration_risk: bool  # True if TOP1来源占比>60%


class FlowMatrix(BaseModel):
    """品类流转矩阵"""
    sources: List[str]
    targets: List[str]
    matrix: List[List[int]]
    concentration_warnings: List[str]


class AssociationItem(BaseModel):
    """关联品类项"""
    category_name: str
    user_count: int
    order_count: int
    gsv: float
    ratio: float  # 占该品类购买用户的比例
    avg_days_gap: float  # 与目标品类的平均购买间隔天数


class CategoryFlowResponse(BaseModel):
    """品类流转 Tab 响应"""
    sankey_data: SankeyGraphData
    matrix: FlowMatrix
    data_stale: bool = False
    data_quality_note: str
    # 时序关联分析(当传入 target_category 时填充)
    target_category: Optional[str] = None
    post_purchase: Optional[List[AssociationItem]] = None  # 买A之后买了什么
    pre_purchase: Optional[List[AssociationItem]] = None   # 买A之前买了什么


# ─────────────────────────────────────────────────────────────
# 品类看板 v2 - 购物篮分析 (MarketBasketTab)
# ─────────────────────────────────────────────────────────────

class MarketBasketItem(BaseModel):
    """购物篮关联项"""
    category_name: str
    co_order_count: int          # 同单关联订单数
    support: float               # 支持度 = co_order_count / total_orders
    confidence: float            # 置信度 = co_order_count / target_orders
    lift: float                  # 提升度 = confidence / item_prob
    target_order_count: int      # 目标品类订单数（分母）
    co_gsv: float                # 连带订单整单GSV = 同时含目标品类+关联品类的订单的actual_amount总和（跨品类可加总时会重复计算）
    co_own_gsv: float            # 关联品类自身GSV = 该品类在连带订单中的实际销售金额（可加总，不重复）
    co_aus: float                # 连带人均消费(AUS) = co_gsv / 连带购买人数
    target_aus: float            # 目标品类人均消费(AUS baseline)
    gsv_lift: float              # 消费提升倍数 = co_aus / target_aus


class MarketBasketYoYItem(BaseModel):
    """购物篮关联项（含同比）"""
    category_name: str
    current: MarketBasketItem    # 当期
    previous: Optional[MarketBasketItem] = None  # 去年同期
    confidence_change: Optional[float] = None    # 置信度变化(pp)
    lift_change: Optional[float] = None          # 提升度变化
    rank_change: Optional[int] = None            # 排名变化
    gsv_change: Optional[float] = None           # 连带GSV同比变化（元）


class MarketBasketResponse(BaseModel):
    """购物篮分析 Tab 响应"""
    target_category: str
    total_orders: int            # 周期内总订单数
    target_order_count: int      # 目标品类订单数
    period_label: str            # 如 "2026-04"
    yoy_period_label: Optional[str] = None  # 去年同期标签
    items: List[MarketBasketYoYItem]
    data_quality_note: str

class ChurnScatterPoint(BaseModel):
    """流失预警-散点数据"""
    category_name: str
    current_users: int
    mom_change_rate: float
    churn_users: int
    inter_churn: int     # 品类间流失
    silent_churn: int    # 沉默流失


class ChurnBarData(BaseModel):
    """流失预警-条形数据"""
    category_name: str
    current_users: int
    previous_users: int
    mom_change_rate: float


class ChurnTableRow(BaseModel):
    """流失预警-表格行"""
    category_name: str
    current_users: int
    previous_users: int
    mom_change_rate: float
    inter_churn: int
    silent_churn: int
    top_churn_dest1: str
    top_churn_dest1_ratio: float
    top_churn_dest2: str
    top_churn_dest2_ratio: float
    挽回建议: str


class CategoryChurnResponse(BaseModel):
    """流失预警 Tab 响应"""
    scatter_data: List[ChurnScatterPoint]
    bar_data: List[ChurnBarData]
    table: List[ChurnTableRow]
    operation_suggestions: List[str]
    data_quality_note: str


# ─────────────────────────────────────────────────────────────
# 品类看板 v2 - 详情页 API
# ─────────────────────────────────────────────────────────────

class CategoryDailyTrendResponse(BaseModel):
    """品类每日趋势响应"""
    category_id: str
    category_name: str
    granularity: str = "daily"
    dates: List[str]
    gmv: List[float]
    user_count: List[int]
    aus: List[float]
    new_customer_ratio: List[float]


class UserDetail(BaseModel):
    """用户详情"""
    user_id: str
    nickname: str
    order_count: int
    total_gmv: float
    first_order_date: str
    last_order_date: str
    segment_id: int
    segment_name: str
    is_member: bool
    is_wool_party: bool


class CategoryUserListResponse(BaseModel):
    """品类用户列表响应"""
    category_id: str
    category_name: str
    total_users: int
    users: List[UserDetail]


# ============================================================
# 市场对焦板块 (Market Focus)
# ============================================================

class StoreAssetWeek(BaseModel):
    """全店资产-单周数据"""
    week_label: str
    week_end_date: str
    total: int
    discover: int
    engage: int
    enthuse: int
    perform: int
    initial: int
    numerous: int
    keen: int
    # 本周对比上周绝对值变化
    total_change: int = 0
    discover_change: int = 0
    engage_change: int = 0
    enthuse_change: int = 0
    perform_change: int = 0
    initial_change: int = 0
    numerous_change: int = 0
    keen_change: int = 0
    # 本周对比去年同期（YOY）绝对值变化
    total_yoy: int = 0
    discover_yoy: int = 0
    engage_yoy: int = 0
    enthuse_yoy: int = 0
    perform_yoy: int = 0
    initial_yoy: int = 0
    numerous_yoy: int = 0
    keen_yoy: int = 0


class StoreAssetResponse(BaseModel):
    """全店资产响应"""
    weeks: List[StoreAssetWeek]
    latest_week: str


class ProductAssetWeek(BaseModel):
    """单品资产-单周数据"""
    week_label: str
    week_end_date: str
    total: int
    shallow_grass: int
    deep_grass: int
    initial: int
    repurchase: int
    lian_dai: int
    # 本周对比上周绝对值变化
    total_change: int = 0
    shallow_grass_change: int = 0
    deep_grass_change: int = 0
    initial_change: int = 0
    repurchase_change: int = 0
    lian_dai_change: int = 0
    # 本周对比去年同期（YOY）绝对值变化
    total_yoy: int = 0
    shallow_grass_yoy: int = 0
    deep_grass_yoy: int = 0
    initial_yoy: int = 0
    repurchase_yoy: int = 0
    lian_dai_yoy: int = 0


class ProductAssetItem(BaseModel):
    """单品资产-单个产品"""
    name: str
    spu_classes: List[str] = Field(default_factory=list, description="该产品对应的SPU类目名列表（需与前端CORE_PRODUCTS保持一致）")
    weeks: List[ProductAssetWeek]


class ProductAssetResponse(BaseModel):
    """单品资产响应"""
    products: List[ProductAssetItem]
    latest_week: str


# ============================================================
# 访客入会率 (Visitor -> Member Join Rate)
# ============================================================

class VisitorSummaryResponse(BaseModel):
    """访客入会率汇总响应"""
    start_date: str
    end_date: str
    visitors: int
    new_members: int
    member_join_rate: float
    ly_visitors: int
    ly_new_members: int
    ly_member_join_rate: float
    visitors_yoy: Optional[float] = None
    new_members_yoy: Optional[float] = None
    member_join_rate_yoy: Optional[float] = None
    # 环比
    visitors_mom: Optional[float] = None
    new_members_mom: Optional[float] = None
    member_join_rate_mom: Optional[float] = None


class VisitorDailyTrendItem(BaseModel):
    """访客入会率每日趋势项"""
    date: str
    visitors: int
    new_members: int
    member_join_rate: float
    ly_visitors: int
    ly_new_members: int
    ly_member_join_rate: float


class VisitorDailyTrendResponse(BaseModel):
    """访客入会率每日趋势响应"""
    start_date: str
    end_date: str
    data: List[VisitorDailyTrendItem]


# ============================================================
# 一键拆解 v2 (Breakdown) — GSV only, R区间+渠道漏斗分层
# ============================================================

class BreakdownRequest(BaseModel):
    """一键拆解请求 v2"""
    target_gmv: float = Field(..., description="全店GSV目标（元）")
    activity_start: str = Field(..., description="活动开始日期 YYYY-MM-DD")
    activity_end: str = Field(..., description="活动结束日期 YYYY-MM-DD")
    last_year_start: Optional[str] = Field(default=None, description="去年同期开始 YYYY-MM-DD（不传则自动推算）")
    last_year_end: Optional[str] = Field(default=None, description="去年同期结束 YYYY-MM-DD（不传则自动推算）")
    old_customer_ratio_target: Optional[float] = Field(default=0.6, description="老客占比目标（默认60%）")
    breakdown_mode: str = Field(default="forward", description="拆解模式：forward(顺拆) 或 reverse(倒拆)")


# ── 老客 R区间明细 ──

class BreakdownRIntervalRow(BaseModel):
    """老客R区间×F段拆解明细（顺拆）"""
    r_interval: str = Field(..., description="R区间标签")
    f_segment: str = Field(..., description="F段：F>1 或 F=1")
    user_count: int = Field(..., description="当前该区间用户数")
    ly_repurchase_rate: float = Field(..., description="去年同期该区间回购率")
    est_repurchase_rate: float = Field(..., description="预估回购率（经活动系数调整）")
    est_aus: float = Field(..., description="预估客单价")
    est_gmv: float = Field(..., description="预估GMV")
    ly_total_users: int = Field(default=0, description="去年同期该区间总人数")
    ly_repurchased_users: int = Field(default=0, description="去年同期该区间回购人数")


class BreakdownRIntervalReverseRow(BaseModel):
    """老客R区间×F段拆解明细（倒拆）"""
    r_interval: str = Field(..., description="R区间标签")
    f_segment: str = Field(..., description="F段：F>1 或 F=1")
    current_users: int = Field(..., description="当前该区间用户数")
    est_repurchase_rate: float = Field(..., description="预估回购率")
    est_aus: float = Field(..., description="预估客单价")
    interval_target_gmv: float = Field(..., description="该区间目标GMV")
    needed_users: int = Field(..., description="所需用户数")
    user_gap: int = Field(..., description="用户数缺口")
    ly_repurchase_rate: float = Field(default=0, description="去年回购率参考")
    ly_total_users: int = Field(default=0, description="去年该区间总人数")


class BreakdownOldCustomer(BaseModel):
    """老客拆解结果 v2"""
    old_users_total: int = Field(..., description="老客总人数")
    old_gmv_target: float = Field(..., description="老客目标GSV")
    old_gmv_estimate: Optional[float] = Field(default=None, description="老客预估GSV（顺拆有值，倒拆为None）")
    old_gmv_gap: Optional[float] = Field(default=None, description="老客gap（顺拆有值，倒拆为None）")
    r_interval_breakdown: List = Field(default_factory=list, description="R区间×F段拆解明细")


# ── 新客渠道明细 ──

class BreakdownChannelNewRow(BaseModel):
    """新客渠道拆解明细（顺拆）"""
    channel: str = Field(..., description="渠道名")
    ly_new_users: int = Field(..., description="去年同期新客人数")
    est_new_users: int = Field(..., description="预估新客人数")
    ly_new_aus: float = Field(..., description="去年同期新客客单价")
    est_new_aus: float = Field(..., description="预估新客客单价")
    est_new_gmv: float = Field(..., description="预估新客GSV")


class BreakdownChannelNewReverseRow(BaseModel):
    """新客渠道拆解明细（倒拆）"""
    channel: str = Field(..., description="渠道名")
    ly_new_users: int = Field(..., description="去年同期新客人数")
    ly_new_aus: float = Field(..., description="去年同期新客客单价")
    channel_target_gmv: float = Field(..., description="该渠道目标GSV")
    needed_users: int = Field(..., description="所需新客人数")
    user_gap: int = Field(..., description="新客人数缺口")


class BreakdownNewCustomer(BaseModel):
    """新客拆解结果 v2"""
    new_users_total: Optional[int] = Field(default=None, description="新客总人数（顺拆有值）")
    new_gmv_target: float = Field(..., description="新客目标GSV")
    new_gmv_estimate: Optional[float] = Field(default=None, description="新客预估GSV（顺拆有值）")
    new_gmv_gap: Optional[float] = Field(default=None, description="新客gap（顺拆有值）")
    channel_breakdown: List = Field(default_factory=list, description="新客渠道拆解明细")
    uv_reference: int = Field(default=0, description="参考UV")
    member_join_rate: float = Field(default=0.0, description="参考入会率")
    needed_uv: Optional[int] = Field(default=None, description="所需UV（倒拆）")
    uv_gap: Optional[int] = Field(default=None, description="UV缺口（倒拆）")


# ── 通用 ──

class BreakdownGapSuggestion(BaseModel):
    """补gap建议"""
    dimension: str = Field(..., description="维度：老客/新客/总店")
    gap_amount: Optional[float] = Field(default=None, description="gap金额（顺拆）")
    gap_users: Optional[int] = Field(default=None, description="gap人数（倒拆）")
    uv_gap: Optional[int] = Field(default=None, description="UV缺口（倒拆新客）")
    suggestions: List[str] = Field(default_factory=list, description="建议列表")
    priority: str = Field(default="P1", description="优先级 P0/P1/P2")


class BreakdownMeta(BaseModel):
    """拆解元数据"""
    activity_type: str = Field(..., description="活动类型")
    repurchase_adjustment: float = Field(..., description="回购率调整系数")
    metric_type: str = Field(default="GSV", description="指标类型（固定GSV）")


class BreakdownLogic(BaseModel):
    """拆解逻辑说明（前端展示公式和知识引用）"""
    old_customer_formula: str = Field(..., description="老客拆解公式")
    old_customer_source: str = Field(..., description="老客拆解知识来源")
    new_customer_formula: str = Field(..., description="新客拆解公式")
    new_customer_source: str = Field(..., description="新客拆解知识来源")


class BreakdownResponse(BaseModel):
    """一键拆解响应 v2"""
    mode: str = Field(..., description="拆解模式：forward 或 reverse")
    mode_label: str = Field(..., description="拆解模式中文标签")
    target_gmv: float = Field(..., description="目标GSV")
    total_estimate: Optional[float] = Field(default=None, description="总预估GSV（顺拆有值，倒拆为None）")
    total_gap: Optional[float] = Field(default=None, description="总gap（顺拆有值，倒拆为None）")
    gap_ratio: Optional[float] = Field(default=None, description="gap占比（顺拆有值）")
    old_customer: BreakdownOldCustomer
    new_customer: BreakdownNewCustomer
    suggestions: List[BreakdownGapSuggestion]
    activity_period: DateRangeResponse
    reference_period: DateRangeResponse
    meta: BreakdownMeta = Field(..., description="拆解元数据")
    breakdown_logic: BreakdownLogic = Field(..., description="拆解逻辑说明")


# ============================================================
# 派样看板 (Sampling Dashboard)
# ============================================================

class SamplingChannelSummary(BaseModel):
    """派样渠道汇总"""
    channel: str
    sample_users: int
    repurchase_users_7d: int
    repurchase_users_30d: int
    repurchase_users_60d: int
    repurchase_rate_7d: float
    repurchase_rate_30d: float
    repurchase_rate_60d: float
    repurchase_gsv_7d: float
    repurchase_gsv_30d: float
    repurchase_gsv_60d: float
    repurchase_aus_7d: float
    repurchase_aus_30d: float
    repurchase_aus_60d: float


class SamplingCategoryRow(BaseModel):
    """派样品类明细"""
    channel: str
    category: str
    sample_users: int
    repurchase_users: int
    repurchase_rate: float
    repurchase_gsv: float
    repurchase_aus: float
    same_category_repurchase: int
    same_category_rate: float


class SamplingROITimeRange(BaseModel):
    """派样ROI时间范围"""
    start: str
    end: str
    window_days: int


class SamplingROIResponse(BaseModel):
    """派样ROI分析响应"""
    summary: Dict[str, List[SamplingChannelSummary]]
    category_breakdown: List[SamplingCategoryRow]
    time_range: SamplingROITimeRange


class SamplingLockCampaignInfo(BaseModel):
    """锁权活动信息"""
    year: int
    campaign_name: str
    conversion_start: Optional[str] = None
    conversion_end: Optional[str] = None
    lock_start: Optional[str] = None
    lock_end: Optional[str] = None
    error: Optional[str] = None


class SamplingLockYearData(BaseModel):
    """锁权分析单年数据"""
    total_uv: int
    locked_users: int
    lock_rate: float
    converted_users: int
    conversion_rate: float
    lock_gsv: float
    lock_aus: float
    new_locked_users: int
    new_locked_ratio: float
    new_converted_users: int
    new_conversion_rate: float
    new_lock_gsv: float
    new_lock_aus: float


class SamplingLockYOY(BaseModel):
    """锁权分析同比数据"""
    total_uv: Optional[float] = None
    locked_users: Optional[float] = None
    lock_rate: Optional[float] = None
    converted_users: Optional[float] = None
    conversion_rate: Optional[float] = None
    lock_gsv: Optional[float] = None
    lock_aus: Optional[float] = None
    new_locked_users: Optional[float] = None
    new_locked_ratio: Optional[float] = None
    new_converted_users: Optional[float] = None
    new_conversion_rate: Optional[float] = None
    new_lock_gsv: Optional[float] = None
    new_lock_aus: Optional[float] = None


class SamplingLockAnalysisResponse(BaseModel):
    """0.01锁权分析响应"""
    campaign_info: SamplingLockCampaignInfo
    current_year: SamplingLockYearData
    last_year: SamplingLockYearData
    yoy: SamplingLockYOY


# ============================================================
# RFM - 区间订单明细导出
# ============================================================

class SegmentOrderRow(BaseModel):
    """区间订单明细单行"""
    order_id: str
    user_id: str
    pay_time: str
    actual_amount: float
    channel: str
    spu_product_class: Optional[str] = None


class SegmentOrdersResponse(BaseModel):
    """区间订单明细响应"""
    dimension: str
    segment: str
    mode: str
    total_orders: int
    rows: List[SegmentOrderRow]
