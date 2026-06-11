"""芙清 CRM - Pydantic 契约模型"""
from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field
from .common import DateRangeResponse, YearComparisonRow
from .types import RatioField, PercentageField, PpField  # Sprint 14 A.1

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
    # Sprint 17 B2 全量 audit: ratio 字段补 RatioField 标注 (0-1 decimal)
    old_gsv_ratio: "RatioField"
    old_users_ratio: "RatioField"
    new_users: int
    new_gsv: float
    new_aus: float
    new_gsv_ratio: "RatioField"
    new_users_ratio: "RatioField"
    member_users: int
    member_gsv: float
    member_aus: float
    member_gsv_ratio: "RatioField"
    member_users_ratio: "RatioField"
    member_old_users: int
    member_old_gsv: float
    member_old_aus: float
    member_old_gsv_ratio: "RatioField"
    member_old_users_ratio: "RatioField"
    member_new_users: int
    member_new_gsv: float
    member_new_aus: float
    member_new_gsv_ratio: "RatioField"
    member_new_users_ratio: "RatioField"

    # 去年（comparison）
    comp_gsv_users: int
    comp_gsv: float
    comp_aus: float
    comp_old_users: int
    comp_old_gsv: float
    comp_old_aus: float
    comp_old_gsv_ratio: "RatioField"
    comp_old_users_ratio: "RatioField"
    comp_new_users: int
    comp_new_gsv: float
    comp_new_aus: float
    comp_new_gsv_ratio: "RatioField"
    comp_new_users_ratio: "RatioField"
    comp_member_users: int
    comp_member_gsv: float
    comp_member_aus: float
    comp_member_gsv_ratio: "RatioField"
    comp_member_users_ratio: "RatioField"
    comp_member_old_users: int
    comp_member_old_gsv: float
    comp_member_old_aus: float
    comp_member_old_gsv_ratio: "RatioField"
    comp_member_old_users_ratio: "RatioField"
    comp_member_new_users: int
    comp_member_new_gsv: float
    comp_member_new_aus: float
    comp_member_new_gsv_ratio: "RatioField"
    comp_member_new_users_ratio: "RatioField"

    # 前年（prev2）
    prev2_gsv_users: int
    prev2_gsv: float
    prev2_aus: float
    prev2_old_users: int
    prev2_old_gsv: float
    prev2_old_aus: float
    prev2_old_gsv_ratio: "RatioField"
    prev2_old_users_ratio: "RatioField"
    prev2_new_users: int
    prev2_new_gsv: float
    prev2_new_aus: float
    prev2_new_gsv_ratio: "RatioField"
    prev2_new_users_ratio: "RatioField"
    prev2_member_users: int
    prev2_member_gsv: float
    prev2_member_aus: float
    prev2_member_gsv_ratio: "RatioField"
    prev2_member_users_ratio: "RatioField"
    prev2_member_old_users: int
    prev2_member_old_gsv: float
    prev2_member_old_aus: float
    prev2_member_old_gsv_ratio: "RatioField"
    prev2_member_old_users_ratio: "RatioField"
    prev2_member_new_users: int
    prev2_member_new_gsv: float
    prev2_member_new_aus: float
    prev2_member_new_gsv_ratio: "RatioField"
    prev2_member_new_users_ratio: "RatioField"

    # YoY（当年 vs 去年）
    # *_gsv/*_users/*_aus → yoy_absolute 返 percentage (e.g. 25.0 = +25%)
    yoy_gsv: Optional["PercentageField"] = None
    yoy_gsv_users: Optional["PercentageField"] = None
    yoy_old_gsv: Optional["PercentageField"] = None
    yoy_old_users: Optional["PercentageField"] = None
    yoy_new_gsv: Optional["PercentageField"] = None
    yoy_new_users: Optional["PercentageField"] = None
    yoy_member_gsv: Optional["PercentageField"] = None
    yoy_member_users: Optional["PercentageField"] = None
    yoy_member_old_gsv: Optional["PercentageField"] = None
    yoy_member_old_users: Optional["PercentageField"] = None
    yoy_member_new_gsv: Optional["PercentageField"] = None
    yoy_member_new_users: Optional["PercentageField"] = None
    yoy_aus: Optional["PercentageField"] = None
    yoy_old_aus: Optional["PercentageField"] = None
    yoy_new_aus: Optional["PercentageField"] = None
    yoy_member_aus: Optional["PercentageField"] = None
    yoy_member_old_aus: Optional["PercentageField"] = None
    yoy_member_new_aus: Optional["PercentageField"] = None
    # *_ratio → yoy_ratio 返 pp 差 (e.g. 5.28 = +5.28pp)
    yoy_old_gsv_ratio: Optional["PpField"] = None
    yoy_old_users_ratio: Optional["PpField"] = None
    yoy_new_gsv_ratio: Optional["PpField"] = None
    yoy_new_users_ratio: Optional["PpField"] = None
    yoy_member_gsv_ratio: Optional["PpField"] = None
    yoy_member_users_ratio: Optional["PpField"] = None
    yoy_member_old_gsv_ratio: Optional["PpField"] = None
    yoy_member_old_users_ratio: Optional["PpField"] = None
    yoy_member_new_gsv_ratio: Optional["PpField"] = None
    yoy_member_new_users_ratio: Optional["PpField"] = None


class AudienceTableResponse(BaseModel):
    dimension: str
    mode: str
    current_period: DateRangeResponse
    comparison_period: DateRangeResponse
    prev2_period: Optional[DateRangeResponse] = None
    rows: List[AudienceRow]

class ChannelGSVRow(BaseModel):
    channel: str
    gsv_2026: float = 0.0
    gsv_2025: float = 0.0
    yoy: Optional["PercentageField"] = None          # YOY增长率 (已 *100 pp)
    ratio_2026: Optional["RatioField"] = None   # 2026年占全店比例 (0-1 decimal)
    ratio_2025: Optional["RatioField"] = None   # 2025年占全店比例 (0-1 decimal)
    ratio_yoy: Optional["PpField"] = None   # 占比YOY (pp 差)
    # 人数（Panel B=全店人数, Panel C=会员人数）
    users_2026: Optional[float] = None
    users_2025: Optional[float] = None
    users_yoy: Optional["PercentageField"] = None
    # AUS（Panel B=全店AUS, Panel C=会员AUS）
    aus_2026: Optional[float] = None
    aus_2025: Optional[float] = None
    aus_yoy: Optional["PercentageField"] = None
    # 新客GSV
    new_gsv_2026: Optional[float] = None
    new_gsv_2025: Optional[float] = None
    new_gsv_yoy: Optional["PercentageField"] = None
    new_gsv_ratio_2026: Optional["RatioField"] = None
    new_gsv_ratio_2025: Optional["RatioField"] = None
    new_gsv_ratio_yoy: Optional["PpField"] = None
    # 老客GSV
    old_gsv_2026: Optional[float] = None
    old_gsv_2025: Optional[float] = None
    old_gsv_yoy: Optional["PercentageField"] = None
    old_gsv_ratio_2026: Optional["RatioField"] = None
    old_gsv_ratio_2025: Optional["RatioField"] = None
    old_gsv_ratio_yoy: Optional["PpField"] = None
    # 新客人数（Panel B=全店新客人数, Panel C=会员新客人数）
    new_users_2026: Optional[float] = None
    new_users_2025: Optional[float] = None
    new_users_yoy: Optional["PercentageField"] = None
    # 新客AUS（Panel B=全店新客AUS, Panel C=会员新客AUS）
    new_aus_2026: Optional[float] = None
    new_aus_2025: Optional[float] = None
    new_aus_yoy: Optional["PercentageField"] = None
    # 老客人数（Panel B=全店老客人数, Panel C=会员老客人数）
    old_users_2026: Optional[float] = None
    old_users_2025: Optional[float] = None
    old_users_yoy: Optional["PercentageField"] = None
    # 老客AUS（Panel B=全店老客AUS, Panel C=会员老客AUS）
    old_aus_2026: Optional[float] = None
    old_aus_2025: Optional[float] = None
    old_aus_yoy: Optional["PercentageField"] = None
    # 会员占该渠道比例（Panel C 专用）
    member_ratio_2026: Optional["RatioField"] = None
    member_ratio_2025: Optional["RatioField"] = None
    member_ratio_yoy: Optional["PpField"] = None
    # 会员视角新/老客GSV（供 channel_member 列扩展使用）
    member_new_gsv_2026: Optional[float] = None
    member_new_gsv_2025: Optional[float] = None
    member_new_gsv_yoy: Optional["PercentageField"] = None
    member_new_gsv_ratio_2026: Optional["RatioField"] = None
    member_new_gsv_ratio_2025: Optional["RatioField"] = None
    member_new_gsv_ratio_yoy: Optional["PpField"] = None
    member_old_gsv_2026: Optional[float] = None
    member_old_gsv_2025: Optional[float] = None
    member_old_gsv_yoy: Optional["PercentageField"] = None
    member_old_gsv_ratio_2026: Optional["RatioField"] = None
    member_old_gsv_ratio_2025: Optional["RatioField"] = None
    member_old_gsv_ratio_yoy: Optional["PpField"] = None
    # 交叉指标：会员新客/老客 GSV 占全店新客/老客 GSV 比例
    member_new_vs_all_new_2026: Optional["RatioField"] = None
    member_new_vs_all_new_2025: Optional["RatioField"] = None
    member_new_vs_all_new_yoy: Optional["PpField"] = None
    member_old_vs_all_old_2026: Optional["RatioField"] = None
    member_old_vs_all_old_2025: Optional["RatioField"] = None
    member_old_vs_all_old_yoy: Optional["PpField"] = None

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
    # Sprint 17 B2 全量 audit: 9 个 ratio 字段补 RatioField 标注 (0-1 decimal)
    old_gsv_ratio: "RatioField" = 0.0
    old_users_ratio: "RatioField" = 0.0
    # 新客
    new_gsv: float = 0.0
    new_users: int = 0
    new_aus: float = 0.0
    new_gsv_ratio: "RatioField" = 0.0
    new_users_ratio: "RatioField" = 0.0
    # 会员
    member_gsv: float = 0.0
    member_users: int = 0
    member_aus: float = 0.0
    member_penetration: "RatioField" = 0.0   # 会员渗透率 = 会员人数/全店人数 (0-1 decimal)
    member_users_ratio: "RatioField" = 0.0
    # 会员老客
    member_old_gsv: float = 0.0
    member_old_users: int = 0
    member_old_aus: float = 0.0
    member_old_gsv_ratio: "RatioField" = 0.0
    member_old_users_ratio: "RatioField" = 0.0
    # 会员新客
    member_new_gsv: float = 0.0
    member_new_users: int = 0
    member_new_aus: float = 0.0
    member_new_gsv_ratio: "RatioField" = 0.0
    member_new_users_ratio: "RatioField" = 0.0


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

