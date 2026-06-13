"""芙清 CRM - Pydantic 契约模型"""
from __future__ import annotations
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field
from .types import RatioField, PpField  # Sprint 17 B2 全量 audit

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

class ProductClassRepurchase(BaseModel):
    """品类复购指标（含同比）"""
    product_class: str = Field(..., description="品类名称")
    total_buyers: int = Field(..., description="购买人数")
    repurchase_users: int = Field(..., description="复购人数")
    # Sprint 17 B2 全量 audit: 6 个 ratio/yoy 字段补标
    # repurchase_rate 0-1 decimal, ly 同期值, yoy pp 差 (cur-ly *100 后 0-1 → 0-100pp)
    repurchase_rate: "RatioField" = Field(..., description="复购率 0-1 decimal")
    median_days: int = Field(..., description="中位复购天数")
    p25_days: int = Field(..., description="P25复购天数")
    p75_days: int = Field(..., description="P75复购天数")
    avg_days: Optional[float] = Field(None, description="平均复购天数")
    avg_order_value: float = Field(..., description="客单价（含首购）")
    gsv: float = Field(..., description="GSV（含首购）")
    repurchase_order_value: float = Field(..., description="复购客单价（仅复购订单）")
    repurchase_gsv: float = Field(..., description="复购GSV（仅复购订单）")
    # 同比
    ly_repurchase_rate: Optional["RatioField"] = Field(None, description="去年同期复购率 0-1 decimal")
    ly_median_days: Optional[int] = Field(None, description="去年同期中位天数")
    ly_avg_days: Optional[float] = Field(None, description="去年同期平均天数")
    ly_gsv: Optional[float] = Field(None, description="去年同期GSV")
    # YOY: repurchase_rate_yoy 是 pp 差 (cur-ly *100), gsv_yoy 是 0-1 ratio
    # median_days_yoy / avg_days_yoy 是原始天数差 (cur-ly), 不约束
    repurchase_rate_yoy: Optional["PpField"] = Field(None, description="复购率同比(pp 差 -100~+100)")
    median_days_yoy: Optional[float] = Field(None, description="中位天数同比（原始天数差 cur-ly）")
    avg_days_yoy: Optional[float] = Field(None, description="平均天数YOY（原始天数差 cur-ly）")
    # gsv_yoy 是 (cur-ly)/ly 变化率 0-1 decimal, 可负可超 1 (新品类从 0 涨起万倍)
    gsv_yoy: Optional[float] = Field(None, description="GSV同比 0-1 decimal (cur-ly)/ly, 可负可超 1")

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
    # 采集质量标识：legacy(历史) / verified(已核对) / likely-wrong(疑似脏数据)。
    # 默认 legacy 保证向前兼容。前端默认隐藏 likely-wrong 行。
    quality_flag: str = "legacy"
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

