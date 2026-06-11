"""芙清 CRM - Pydantic 契约模型"""
from __future__ import annotations
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field
from .asset import ProductClassRepurchase
from .types import RatioField, PercentageField, PpField  # Sprint 14 A.3
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
    all_store_repurchase_rate: "RatioField" = Field(..., description="全店复购率 0-1 decimal")
    same_product_repurchase_rate: "RatioField" = Field(..., description="本品复购率 0-1 decimal")
    period_repurchase_users: int = Field(..., description="周期复购人数（同分析周期）")

    # 老客指标
    old_gsv: float = Field(..., description="老客GSV")
    old_users: int = Field(..., description="老客人数")
    old_customer_gsv_ratio: "RatioField" = Field(..., description="老客GSV占比 0-1 decimal")
    old_customer_aus: float = Field(..., description="老客AUS")

    # 会员老客指标
    member_old_gsv: float = Field(..., description="会员老客GSV")
    member_old_users: int = Field(..., description="会员老客人数")
    member_old_customer_gsv_ratio: "RatioField" = Field(..., description="会员老客GSV占比 0-1 decimal")
    member_old_customer_aus: float = Field(..., description="会员老客AUS")

    # 健康评分（归一化后加权 0-100）
    health_score: float = Field(..., description="健康评分 0-100")
    health_level: str = Field(..., description="healthy | warning | critical")
    ly_health_score: Optional[float] = Field(None, description="去年同期健康评分")
    health_score_yoy: Optional["PpField"] = Field(None, description="健康评分同比（百分点差）")

    # 去年同期原始值（用于雷达图两年对比）
    ly_all_store_repurchase_rate: Optional["RatioField"] = Field(None, description="去年同期全店复购率 0-1 decimal")
    ly_same_product_repurchase_rate: Optional["RatioField"] = Field(None, description="去年同期本品复购率 0-1 decimal")
    ly_old_customer_gsv_ratio: Optional["RatioField"] = Field(None, description="去年同期老客GSV占比 0-1 decimal")
    ly_old_customer_aus: Optional[float] = Field(None, description="去年同期老客AUS")
    ly_period_repurchase_users: Optional[int] = Field(None, description="去年同期周期复购人数")

    # 同比（vs去年同期同周期）
    yoy_all_store_repurchase_rate: Optional["PpField"] = Field(None, description="全店复购率同比 (pp 差)")
    yoy_same_product_repurchase_rate: Optional["PpField"] = Field(None, description="本品复购率同比 (pp 差)")
    yoy_old_customer_gsv_ratio: Optional["PpField"] = Field(None, description="老客占比同比 (pp 差)")
    yoy_old_customer_aus: Optional["PercentageField"] = Field(None, description="老客AUS同比 (percentage)")
    yoy_period_repurchase_users: Optional["PercentageField"] = Field(None, description="周期复购人数同比 (percentage)")
    yoy_old_gsv: Optional["PercentageField"] = Field(None, description="老客GSV同比 (percentage)")
    yoy_old_users: Optional["PercentageField"] = Field(None, description="老客人数同比 (percentage)")
    yoy_member_old_gsv: Optional["PercentageField"] = Field(None, description="会员老客GSV同比 (percentage)")
    yoy_member_old_users: Optional["PercentageField"] = Field(None, description="会员老客人数同比 (percentage)")
    yoy_member_old_customer_gsv_ratio: Optional["PpField"] = Field(None, description="会员老客GSV占比同比 (pp 差)")
    yoy_member_old_customer_aus: Optional["PercentageField"] = Field(None, description="会员老客AUS同比 (percentage)")

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
    user_ratio: "RatioField" = Field(..., description="占复购人群比例 0-1 decimal")
    # 去年同期
    ly_user_count: Optional[int] = Field(None, description="去年同期该桶人数")
    ly_user_ratio: Optional["RatioField"] = Field(None, description="去年同期占比 0-1 decimal")
    # 前年同期
    prev2_user_count: Optional[int] = Field(None, description="前年同期该桶人数")
    prev2_user_ratio: Optional["RatioField"] = Field(None, description="前年同期占比 0-1 decimal")
    # YOY
    user_count_yoy: Optional["PercentageField"] = Field(None, description="人数同比（percentage 已 *100）")
    user_ratio_yoy: Optional["PpField"] = Field(None, description="占比同比 (pp 差)")


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
    # Sprint 16.5 B2 试点治根: 2 个 ratio/金额 字段补标注 (跟 audience.py B1 模式一致)
    # 修法: gsv_ratio 0-1 decimal 越界 (e.g. service 返 1.2 错值) 在 API 入口 422
    gsv_ratio: "RatioField" = Field(..., description="占全店GSV比例 0-1 decimal")


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
    # Sprint 16.5 B2 试点治根: 第 3 个 mark — gsv_ratio 补 RatioField 标注
    # 修法: 0-1 decimal 越界 (e.g. service 返 1.5 错值) 在 API 入口 422, 不再 500
    gsv_ratio: "RatioField" = Field(..., description="GSV占比 0-1 decimal")
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
    # Sprint 16.5 B2 试点治根: 1 个 ratio 字段补 RatioField 标注 (跟 audience.py B1 模式一致)
    # 修法: repurchase_gsv_ratio 0-1 decimal 越界在 API 入口 422
    repurchase_gsv_ratio_current: "RatioField" = Field(default=0.0, description="回购GSV占全店GSV比例 0-1 decimal")
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
