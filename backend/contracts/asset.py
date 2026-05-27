"""芙清 CRM - Pydantic 契约模型"""
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field

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

