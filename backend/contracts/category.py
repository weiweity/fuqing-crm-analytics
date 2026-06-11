"""芙清 CRM - Pydantic 契约模型"""
from __future__ import annotations
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field
from .common import WoolPartyBreakdown, DualAxisLineData
from .types import RatioField, PercentageField, PpField  # Sprint 14 A.3

class CategoryDistributionItem(BaseModel):
    name: str
    user_count: int
    member_count: int = 0
    gmv: float
    member_gsv: float = 0.0
    # Sprint 16.5 B2 试点治根: 3 个 ratio 字段补 RatioField 标注 (跟 audience.py B1 模式一致)
    # 修法: 0-1 decimal 越界 (e.g. service 返 1.5 错值) 在 API 入口 422, 不再 500
    pct: "RatioField"
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
# 品类看板 - 品类回购分析（同品/跨品类 RFM 8象限回购）
# ============================================================

class CategoryRepurchaseFlowRow(BaseModel):
    """品类回购分析单行数据（RFM 8象限分群）"""
    rfm_segment: str

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
