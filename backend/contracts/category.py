"""芙清 CRM - Pydantic 契约模型"""
from typing import Optional, List, Any, Dict
from enum import Enum
from pydantic import BaseModel, Field
from .common import SankeyNode, SankeyLink, SankeyGraphData, WoolPartyBreakdown, DualAxisLineData

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
# 品类看板 - 品类回购分析（同品/跨品类 RFM 8象限回购）
# ============================================================

class CategoryRepurchaseFlowRow(BaseModel):
    """品类回购分析单行数据（RFM 8象限分群）"""
    rfm_segment: str

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
    row_totals: List[int] = Field(default_factory=list, description="每行流转人数总和，用于前端计算行百分比")
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
    """品类流转 Tab 响应（兼容旧接口）"""
    sankey_data: SankeyGraphData
    matrix: FlowMatrix
    data_stale: bool = False
    data_quality_note: str
    # 时序关联分析(当传入 target_category 时填充)
    target_category: Optional[str] = None
    post_purchase: Optional[List[AssociationItem]] = None  # 买A之后买了什么
    pre_purchase: Optional[List[AssociationItem]] = None   # 买A之前买了什么
    # 前后置流转桑基图(当传入 target_category 时填充)
    pre_sankey: Optional[SankeyGraphData] = None   # 前置流转：其他品类 → 目标品类
    post_sankey: Optional[SankeyGraphData] = None  # 后置流转：目标品类 → 其他品类


class CategoryFlowAssociationResponse(BaseModel):
    """品类流转 - 时序关联分析响应"""
    target_category: str
    post_purchase: List[AssociationItem] = Field(default_factory=list)
    pre_purchase: List[AssociationItem] = Field(default_factory=list)
    post_sankey: SankeyGraphData = Field(default_factory=lambda: SankeyGraphData(nodes=[], links=[]))
    pre_sankey: SankeyGraphData = Field(default_factory=lambda: SankeyGraphData(nodes=[], links=[]))
    data_quality_note: str = ""


class CategoryFlowMatrixResponse(BaseModel):
    """品类流转 - 全局流转矩阵响应"""
    sankey_data: SankeyGraphData
    matrix: FlowMatrix
    data_stale: bool = False
    data_quality_note: str = ""


class AnchorMode(str, Enum):
    """锚点模式：以目标品类的哪次购买为分析锚点"""
    first = "first"   # 首次购买（分析期间内第一次买A）
    last = "last"     # 末次购买（分析期间内最后一次买A）
    every = "every"   # 每次购买（按购买事件统计，非按用户去重）


class PathDepth(str, Enum):
    """路径深度：时序关联分析的探索步数"""
    d1 = "1"   # 1步：直接前后置关联
    d2 = "2"   # 2步：再向外延伸一层（A→B→C）

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
