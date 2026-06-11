"""芙清 CRM - Pydantic 契约模型"""
from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field
from .types import RatioField, PercentageField, PpField  # Sprint 14 A.3

class RFMRFlowRow(BaseModel):
    r_segment: str

    hist_users_current: int = 0
    repurchase_users_current: int = 0
    repurchase_rate_current: "RatioField" = 0.0
    repurchase_gsv_current: float = 0.0
    # Sprint 14.5 P1.1 (Codex audit): TTL 段 ratio 必 > 1.0 越界 RatioField 0-1,
    # 改 Optional 让 None 通过. Service 端 _parse_flow_rows 给 TTL 段写 None
    # (语义: 不参与 R/F/M 桶占比), 前端 RFMView 已 .filter 过滤此段显示.
    repurchase_gsv_ratio_current: Optional["RatioField"] = None

    hist_users_comp: int = 0
    repurchase_users_comp: int = 0
    repurchase_rate_comp: "RatioField" = 0.0
    repurchase_gsv_comp: float = 0.0
    repurchase_gsv_ratio_comp: Optional["RatioField"] = None

    hist_users_prev2: int = 0
    repurchase_users_prev2: int = 0
    repurchase_rate_prev2: "RatioField" = 0.0
    repurchase_gsv_prev2: float = 0.0
    repurchase_gsv_ratio_prev2: Optional["RatioField"] = None

    yoy_hist_users: Optional["PercentageField"] = None
    yoy_repurchase_users: Optional["PercentageField"] = None
    # Sprint 13 修: 字段名带 _rate 但语义是 pp 差, 加 unit='pp' caller 端, 契约层是 PpField
    yoy_repurchase_rate: Optional["PpField"] = None
    yoy_repurchase_gsv: Optional["PercentageField"] = None
    yoy_repurchase_gsv_ratio: Optional["PpField"] = None


class RFMRFlowResponse(BaseModel):
    year_label: str = "2026"
    comp_year_label: str = "2025"
    prev2_year_label: str = "2024"
    metric_type: str
    rows: List[RFMRFlowRow]
    same_channel_rows: List[RFMRFlowRow] = Field(default_factory=list, description="本渠道回购本渠道数据")
    member_rows: List[RFMRFlowRow] = Field(default_factory=list, description="会员-本渠道唤醒贡献")
    member_same_channel_rows: List[RFMRFlowRow] = Field(default_factory=list, description="会员-本渠道回购本渠道")

class RFMFRFlowRow(BaseModel):
    f_segment: str

    hist_users_current: int = 0
    repurchase_users_current: int = 0
    repurchase_rate_current: "RatioField" = 0.0
    repurchase_gsv_current: float = 0.0
    # Sprint 14.5 P1.1: TTL 段 ratio 改 Optional (见 RFMRFlowRow 注释)
    repurchase_gsv_ratio_current: Optional["RatioField"] = None

    hist_users_comp: int = 0
    repurchase_users_comp: int = 0
    repurchase_rate_comp: "RatioField" = 0.0
    repurchase_gsv_comp: float = 0.0
    repurchase_gsv_ratio_comp: Optional["RatioField"] = None

    hist_users_prev2: int = 0
    repurchase_users_prev2: int = 0
    repurchase_rate_prev2: "RatioField" = 0.0
    repurchase_gsv_prev2: float = 0.0
    repurchase_gsv_ratio_prev2: Optional["RatioField"] = None

    yoy_hist_users: Optional["PercentageField"] = None
    yoy_repurchase_users: Optional["PercentageField"] = None
    yoy_repurchase_rate: Optional["PpField"] = None
    yoy_repurchase_gsv: Optional["PercentageField"] = None
    yoy_repurchase_gsv_ratio: Optional["PpField"] = None


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
    repurchase_rate_current: "RatioField" = 0.0
    repurchase_gsv_current: float = 0.0
    # Sprint 14.5 P1.1: TTL 段 ratio 改 Optional (见 RFMRFlowRow 注释)
    repurchase_gsv_ratio_current: Optional["RatioField"] = None

    hist_users_comp: int = 0
    repurchase_users_comp: int = 0
    repurchase_rate_comp: "RatioField" = 0.0
    repurchase_gsv_comp: float = 0.0
    repurchase_gsv_ratio_comp: Optional["RatioField"] = None

    hist_users_prev2: int = 0
    repurchase_users_prev2: int = 0
    repurchase_rate_prev2: "RatioField" = 0.0
    repurchase_gsv_prev2: float = 0.0
    repurchase_gsv_ratio_prev2: Optional["RatioField"] = None

    yoy_hist_users: Optional["PercentageField"] = None
    yoy_repurchase_users: Optional["PercentageField"] = None
    yoy_repurchase_rate: Optional["PpField"] = None
    yoy_repurchase_gsv: Optional["PercentageField"] = None
    yoy_repurchase_gsv_ratio: Optional["PpField"] = None


class RFMMFlowResponse(BaseModel):
    year_label: str = "2026"
    comp_year_label: str = "2025"
    prev2_year_label: str = "2024"
    metric_type: str
    rows: List[RFMMFlowRow]
    same_channel_rows: List[RFMMFlowRow] = Field(default_factory=list)
    member_rows: List[RFMMFlowRow] = Field(default_factory=list)
    member_same_channel_rows: List[RFMMFlowRow] = Field(default_factory=list)

class RFMAnalysisRow(BaseModel):
    """RFM 8象限分析单行数据"""
    rfm_segment: str = Field(..., description="人群标签，如 重要价值客户")
    hist_users_current: int = Field(default=0)
    repurchase_users_current: int = Field(default=0)
    repurchase_rate_current: "RatioField" = Field(default=0.0)
    repurchase_gsv_current: float = Field(default=0.0)
    repurchase_gsv_ratio_current: "RatioField" = Field(default=0.0)
    hist_users_comp: int = Field(default=0)
    repurchase_users_comp: int = Field(default=0)
    repurchase_rate_comp: "RatioField" = Field(default=0.0)
    repurchase_gsv_comp: float = Field(default=0.0)
    repurchase_gsv_ratio_comp: "RatioField" = Field(default=0.0)
    hist_users_prev2: int = Field(default=0)
    repurchase_users_prev2: int = Field(default=0)
    repurchase_rate_prev2: "RatioField" = Field(default=0.0)
    repurchase_gsv_prev2: float = Field(default=0.0)
    repurchase_gsv_ratio_prev2: "RatioField" = Field(default=0.0)
    yoy_hist_users: Optional["PercentageField"] = Field(None)
    yoy_repurchase_users: Optional["PercentageField"] = Field(None)
    yoy_repurchase_rate: Optional["PpField"] = Field(None)
    yoy_repurchase_gsv: Optional["PercentageField"] = Field(None)
    yoy_repurchase_gsv_ratio: Optional["PpField"] = Field(None)


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


# ============================================================
# RFM 品类下钻 (RFM Category Drilldown)
# ============================================================

class DecliningCategoryItem(BaseModel):
    """下滑品类项"""
    name: str = Field(..., description="品类名称")
    # Sprint 17 B2 全量 audit: yoy_repurchase_rate 是 pp 差, 补 PpField 标注
    yoy_repurchase_rate: "PpField" = Field(..., description="回购率 YOY（pp 差 -100~+100）")


class ImprovingCategoryItem(BaseModel):
    """上升品类项"""
    name: str = Field(..., description="品类名称")
    # Sprint 17 B2 全量 audit: yoy_repurchase_rate 是 pp 差, 补 PpField 标注
    yoy_repurchase_rate: "PpField" = Field(..., description="回购率 YOY（pp 差 -100~+100）")


class RFMCategoryDrilldownRow(BaseModel):
    """RFM 品类下钻单行数据"""
    category_name: str = Field(..., description="品类名称")

    # 当前期
    hist_users_current: int = Field(default=0)
    repurchase_users_current: int = Field(default=0)
    # Sprint 17 B2 全量 audit: 0-1 decimal ratio 字段补 RatioField 标注
    repurchase_rate_current: "RatioField" = Field(default=0.0)
    repurchase_gsv_current: float = Field(default=0.0)
    repurchase_gsv_ratio_current: "RatioField" = Field(default=0.0)

    # 对比期
    hist_users_comp: int = Field(default=0)
    repurchase_users_comp: int = Field(default=0)
    # Sprint 17 B2 全量 audit: 0-1 decimal ratio 字段补 RatioField 标注
    repurchase_rate_comp: "RatioField" = Field(default=0.0)
    repurchase_gsv_comp: float = Field(default=0.0)
    repurchase_gsv_ratio_comp: "RatioField" = Field(default=0.0)

    # 前年期
    hist_users_prev2: int = Field(default=0)
    repurchase_users_prev2: int = Field(default=0)
    # Sprint 17 B2 全量 audit: 0-1 decimal ratio 字段补 RatioField 标注
    repurchase_rate_prev2: "RatioField" = Field(default=0.0)
    repurchase_gsv_prev2: float = Field(default=0.0)
    repurchase_gsv_ratio_prev2: "RatioField" = Field(default=0.0)

    # YOY（当前 vs 对比）
    # *_gsv/*_users → yoy_absolute 返 percentage, *_rate/*_ratio → yoy_repurchase_rate 返 pp
    yoy_hist_users: Optional["PercentageField"] = Field(None)
    yoy_repurchase_users: Optional["PercentageField"] = Field(None)
    yoy_repurchase_rate: Optional["PpField"] = Field(None)
    yoy_repurchase_gsv: Optional["PercentageField"] = Field(None)
    yoy_repurchase_gsv_ratio: Optional["PpField"] = Field(None)


class TopDriverItem(BaseModel):
    """影响因子 TOP 品类"""
    category_name: str
    # Sprint 17 B2 全量 audit: 0-1 decimal ratio 字段补 RatioField 标注
    repurchase_rate_current: "RatioField" = Field(default=0.0)
    yoy_repurchase_rate: Optional["PpField"] = Field(None)
    hist_users_current: int = Field(default=0)


class RFMCategoryDrilldownSummary(BaseModel):
    """RFM 品类下钻汇总"""
    total_hist_users: int = Field(default=0)
    total_repurchase_users: int = Field(default=0)
    # Sprint 17 B2 全量 audit: 0-1 decimal ratio 字段补 RatioField 标注
    overall_repurchase_rate: "RatioField" = Field(default=0.0)
    overall_repurchase_rate_comp: "RatioField" = Field(default=0.0)
    # yoy 是 pp 差
    overall_repurchase_rate_yoy: "PpField" = Field(default=0.0)
    segment_user_count: int = Field(default=0, description="象限内去重用户数")
    top_drivers: List[TopDriverItem] = Field(default_factory=list, description="影响因子 TOP 品类")
    declining_categories: List[DecliningCategoryItem] = Field(default_factory=list)
    improving_categories: List[ImprovingCategoryItem] = Field(default_factory=list)


class RFMCategoryDrilldownResponse(BaseModel):
    """RFM 品类下钻完整响应"""
    rfm_segment: str = Field(..., description="RFM 象限名称")
    year_label: str = Field(..., description="当前年份标签")
    comp_year_label: str = Field(..., description="对比年份标签")
    prev2_year_label: str = Field(..., description="前年年份标签")
    metric_type: str = Field(default="GSV")
    categories: List[RFMCategoryDrilldownRow] = Field(default_factory=list, description="全店品类明细")
    member_categories: List[RFMCategoryDrilldownRow] = Field(default_factory=list, description="会员品类明细")
    summary: RFMCategoryDrilldownSummary = Field(..., description="汇总数据")

