"""Sample CRM - Pydantic 契约模型"""
from __future__ import annotations
from typing import Optional, List, Any, Dict, Annotated
from pydantic import BaseModel, Field
from .common import WoolPartyBreakdown, DualAxisLineData
from .types import RatioField, PercentageField, PpField  # Sprint 14 A.3

class CategoryDistributionItem(BaseModel):
    name: str
    user_count: int
    member_count: int = 0
    gmv: float
    member_gsv: float = 0.0
    # Sprint 16.5 B2 试点治根: pct 是 0-100 percentage, penetration_rate/member_ratio 是 0-1 decimal
    pct: "PercentageField"
    penetration_rate: "RatioField" = 0.0
    member_ratio: "RatioField" = 0.0


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
    gsv_yoy: Optional["PercentageField"] = None
    users: int
    users_yoy: Optional["PercentageField"] = None
    aus: float
    aus_yoy: Optional["PercentageField"] = None
    old_gsv: float
    old_gsv_yoy: Optional["PercentageField"] = None
    old_ratio: "RatioField"
    old_ratio_yoy: Optional["PpField"] = None
    old_users: int
    old_users_yoy: Optional["PercentageField"] = None
    old_aus: float
    old_aus_yoy: Optional["PercentageField"] = None
    new_gsv: float
    new_gsv_yoy: Optional["PercentageField"] = None
    new_ratio: "RatioField"
    new_ratio_yoy: Optional["PpField"] = None
    new_users: int
    new_users_yoy: Optional["PercentageField"] = None
    new_aus: float
    new_aus_yoy: Optional["PercentageField"] = None
    old_users_ratio: Optional["RatioField"] = None
    old_users_ratio_yoy: Optional["PpField"] = None
    new_users_ratio: Optional["RatioField"] = None
    new_users_ratio_yoy: Optional["PpField"] = None
    member_ratio: Optional["RatioField"] = None
    member_ratio_yoy: Optional["PpField"] = None


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
# 品类看板 - 品类回购分析（同品/跨品类 R 桶回购）
# ============================================================
# Sprint 170: 业务口径由 RFM 8 象限改为 R 6 桶（近1个月/2-3月/4-6月/7-12月/13-24月/2年外）
# + 1 TTL 汇总（"已购客TTL"），复用 semantic.segments.R_SEGMENT_ORDER 公共 SSOT (Sprint 60+ 沉淀)
# field r_bucket 替代 rfm_segment（L4.x 永久规则：SSOT 业务字段名实一致）


class CategoryRepurchaseFlowRow(BaseModel):
    """品类回购分析单行数据（R 桶分群，6 档 Recency + 1 TTL 汇总）"""
    r_bucket: str

    hist_users_current: int = 0
    repurchase_users_current: int = 0
    repurchase_rate_current: "RatioField" = 0.0
    repurchase_gsv_current: float = 0.0
    repurchase_gsv_ratio_current: "RatioField" = 0.0

    hist_users_comp: int = 0
    repurchase_rate_comp: "RatioField" = 0.0

    hist_users_prev2: int = 0
    repurchase_rate_prev2: "RatioField" = 0.0

    yoy_hist_users: Optional["PercentageField"] = None
    yoy_repurchase_users: Optional["PercentageField"] = None
    # Sprint 13 修: 字段名带 _rate 但语义是 pp 差, 加 unit='pp' caller 端, 契约层是 PercentageField
    yoy_repurchase_rate: Optional["PpField"] = None
    yoy_repurchase_gsv: Optional["PercentageField"] = None
    # Sprint 19 #2: 改命名 yoy_*_ratio → yoy_*_ratio_ppt, 实际语义是 pp 差 (PpField)
    yoy_repurchase_gsv_ratio_ppt: Optional["PpField"] = None


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
    high_value_ratio: "RatioField"
    wool_party: WoolPartyBreakdown
    member_ratio: "RatioField"
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


class MarketBasketItem(BaseModel):
    """购物篮关联项"""
    category_name: str
    co_order_count: int          # 同单关联订单数
    support: "RatioField"        # 支持度 = co_order_count / total_orders  (0-1 decimal)
    confidence: "RatioField"     # 置信度 = co_order_count / target_orders (0-1 decimal)
    lift: float                  # 提升度 = confidence / item_prob (倍数, 可超 1)
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


# ─────────────────────────────────────────────────────────────
# 品类流失预警 (B 类 — 跟 /churn 路由无关, 配套 category_service.churn)
# Sprint 130 Phase 2.2 实战 fix 模式: 原在 contracts/churn.py, 跟 A 类 schema 共用 file
# 误删整 file 导致 routers/category.py:21,23 + services/category_service/churn.py:163,361
# ImportError. 跟 Sprint 109 实战 fix 模式 cross-reference 教训同根因, 2 B 类 schema 移这里
# ─────────────────────────────────────────────────────────────

class CategoryChurnItem(BaseModel):
    """品类流失预警-散点/条形/表格通用字段"""
    category_name: str
    current_users: int
    previous_users: int = 0
    mom_change_rate: float = Field(..., description="环比变化率 0-1 decimal, 可负")
    inter_churn: int = 0         # 品类间流失
    silent_churn: int = 0        # 沉默流失
    top_churn_dest1: str = ""
    top_churn_dest1_ratio: "RatioField" = 0.0
    top_churn_dest2: str = ""
    top_churn_dest2_ratio: "RatioField" = 0.0
    挽回建议: str = ""


class CategoryChurnResponse(BaseModel):
    """品类流失预警 Tab 响应"""
    scatter_data: List[CategoryChurnItem]
    bar_data: List[CategoryChurnItem]
    table: List[CategoryChurnItem]
    operation_suggestions: List[str]
    data_quality_note: str


class CategoryDailyTrendResponse(BaseModel):
    """品类每日趋势响应"""
    category_id: str
    category_name: str
    granularity: str = "daily"
    dates: List[str]
    gmv: List[float]
    user_count: List[int]
    aus: List[float]
    # Sprint 17 B2 全量 audit: List[RatioField] 必须用 Annotated 才能触发 element-wise 约束
    # Sprint 18 #141: 字段名 _ratio 已被 linter 强制要求 RatioField 0-1 范围, 0-1 decimal
    new_customer_ratio: List[Annotated[float, Field(ge=0.0, le=1.0, description="0-1 decimal 新客占比")]]


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
