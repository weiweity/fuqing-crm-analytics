/* tslint:disable */
/* eslint-disable */
/**
/* This file was automatically generated from pydantic models by running pydantic2ts.
/* Do not modify it by hand - just update the pydantic models and then re-run the script
*/

/**
 * 审计日志项
 */
export interface AuditLogItem {
  /**
   * 操作时间 ISO8601
   */
  timestamp: string;
  /**
   * 动作 update | reset | restore
   */
  action: string;
  /**
   * 操作详情
   */
  details?: {
    [k: string]: unknown;
  };
}
/**
 * 审计日志列表响应
 */
export interface AuditLogResponse {
  logs?: AuditLogItem[];
}
/**
 * 单个渠道健康评分
 */
export interface ChannelHealthScoreItem {
  /**
   * 渠道UI名称
   */
  channel: string;
  /**
   * 当期健康评分
   */
  health_score: number;
  /**
   * healthy | warning | critical
   */
  health_level: string;
  /**
   * 去年同期健康评分
   */
  ly_health_score?: number | null;
  /**
   * 健康评分同比（百分点差）
   */
  health_score_yoy?: number | null;
}
/**
 * 所有渠道健康评分对比
 */
export interface ChannelHealthScoresResponse {
  analysis_date: string;
  period_days?: number;
  exclude_channels?: string[] | null;
  scores?: ChannelHealthScoreItem[];
}
/**
 * Cohort留存矩阵
 */
export interface CohortRetentionResponse {
  /**
   * 首购月份列表
   */
  cohort_months?: string[];
  /**
   * 周期标签 M0/M1/M2...
   */
  periods?: string[];
  /**
   * 复购率矩阵
   */
  matrix?: (number | null)[][];
  /**
   * 各周期平均复购率
   */
  avg_by_period?: (number | null)[];
  /**
   * 去年同期复购率矩阵
   */
  ly_matrix?: (number | null)[][];
  /**
   * 去年同期各周期平均复购率
   */
  ly_avg_by_period?: (number | null)[];
}
/**
 * 配置历史备份项
 */
export interface ConfigHistoryItem {
  /**
   * 备份ID
   */
  backup_id: string;
  /**
   * 触发动作 update | reset
   */
  action: string;
  /**
   * 备份时间 ISO8601
   */
  timestamp: string;
  /**
   * 备份文件名
   */
  file_name: string;
}
/**
 * 配置历史列表响应
 */
export interface ConfigHistoryResponse {
  history?: ConfigHistoryItem[];
}
/**
 * 配置恢复响应
 */
export interface ConfigRestoreResponse {
  success?: boolean;
  /**
   * 恢复的备份ID
   */
  restored_backup_id: string;
  /**
   * 恢复后的完整配置
   */
  config?: {
    [k: string]: unknown;
  };
}
/**
 * 运营分层项（价值×频次交叉）
 */
export interface CustomerSegmentItem {
  /**
   * 如 S-high
   */
  segment_code: string;
  /**
   * 如 超级用户
   */
  segment_name: string;
  /**
   * 价值层级
   */
  value_tier: string;
  /**
   * 频次层级
   */
  frequency_tier: string;
  /**
   * 人数
   */
  user_count: number;
  /**
   * GSV
   */
  gsv: number;
  /**
   * GSV占比 0-1 decimal
   */
  gsv_ratio: number;
  /**
   * 客单价
   */
  avg_order_value: number;
  /**
   * 人均订单数
   */
  avg_orders_per_user: number;
  /**
   * 建议运营动作
   */
  suggested_action: string;
  /**
   * 优先级 1-6
   */
  priority: number;
}
export interface ExportPPTRequest {
  report_type?: string;
  start_date?: string;
  end_date?: string;
  modules?: string[];
  template?: string;
}
export interface ExportPPTResponse {
  report_id?: string | null;
  file_name?: string | null;
  download_url?: string | null;
  error?: string | null;
}
/**
 * 频次分层定义
 */
export interface FrequencyTierDefinition {
  /**
   * high/medium/low
   */
  tier_code: string;
  /**
   * 频次名称
   */
  tier_name: string;
  /**
   * 订单数下限
   */
  order_threshold_min: number;
  /**
   * 订单数上限
   */
  order_threshold_max?: number | null;
  /**
   * 人数
   */
  user_count: number;
}
/**
 * 健康度告警项
 */
export interface HealthAlertItem {
  /**
   * 告警类型编码
   */
  alert_type: string;
  /**
   * 告警名称
   */
  alert_name: string;
  /**
   * high | medium | low
   */
  severity: string;
  /**
   * 当前值
   */
  current_value: number;
  /**
   * 阈值
   */
  threshold_value: number;
  /**
   * yoy | mom | absolute
   */
  comparison_basis: string;
  /**
   * 建议行动
   */
  suggested_action: string;
  /**
   * 跳转目标Tab名
   */
  target_tab: string;
}
/**
 * 现状概览指标 - 运营日报
 */
export interface HealthOverviewMetrics {
  /**
   * 分析日期 YYYY-MM-DD
   */
  analysis_date: string;
  /**
   * 分析周期天数
   */
  period_days?: number;
  /**
   * 全店复购率 0-1 decimal
   */
  all_store_repurchase_rate: number;
  /**
   * 本品复购率 0-1 decimal
   */
  same_product_repurchase_rate: number;
  /**
   * 周期复购人数（同分析周期）
   */
  period_repurchase_users: number;
  /**
   * 老客GSV
   */
  old_gsv: number;
  /**
   * 老客人数
   */
  old_users: number;
  /**
   * 老客GSV占比 0-1 decimal
   */
  old_customer_gsv_ratio: number;
  /**
   * 老客AUS
   */
  old_customer_aus: number;
  /**
   * 会员老客GSV
   */
  member_old_gsv: number;
  /**
   * 会员老客人数
   */
  member_old_users: number;
  /**
   * 会员老客GSV占比 0-1 decimal
   */
  member_old_customer_gsv_ratio: number;
  /**
   * 会员老客AUS
   */
  member_old_customer_aus: number;
  /**
   * 健康评分 0-100
   */
  health_score: number;
  /**
   * healthy | warning | critical
   */
  health_level: string;
  /**
   * 去年同期健康评分
   */
  ly_health_score?: number | null;
  /**
   * 健康评分同比（百分点差）
   */
  health_score_yoy?: number | null;
  /**
   * 去年同期全店复购率 0-1 decimal
   */
  ly_all_store_repurchase_rate?: number | null;
  /**
   * 去年同期本品复购率 0-1 decimal
   */
  ly_same_product_repurchase_rate?: number | null;
  /**
   * 去年同期老客GSV占比 0-1 decimal
   */
  ly_old_customer_gsv_ratio?: number | null;
  /**
   * 去年同期老客AUS
   */
  ly_old_customer_aus?: number | null;
  /**
   * 去年同期周期复购人数
   */
  ly_period_repurchase_users?: number | null;
  /**
   * 全店复购率同比 (pp 差)
   */
  yoy_all_store_repurchase_rate?: number | null;
  /**
   * 本品复购率同比 (pp 差)
   */
  yoy_same_product_repurchase_rate?: number | null;
  /**
   * 老客占比同比 (pp 差)
   */
  yoy_old_customer_gsv_ratio?: number | null;
  /**
   * 老客AUS同比 (percentage)
   */
  yoy_old_customer_aus?: number | null;
  /**
   * 周期复购人数同比 (percentage)
   */
  yoy_period_repurchase_users?: number | null;
  /**
   * 老客GSV同比 (percentage)
   */
  yoy_old_gsv?: number | null;
  /**
   * 老客人数同比 (percentage)
   */
  yoy_old_users?: number | null;
  /**
   * 会员老客GSV同比 (percentage)
   */
  yoy_member_old_gsv?: number | null;
  /**
   * 会员老客人数同比 (percentage)
   */
  yoy_member_old_users?: number | null;
  /**
   * 会员老客GSV占比同比 (pp 差)
   */
  yoy_member_old_customer_gsv_ratio?: number | null;
  /**
   * 会员老客AUS同比 (percentage)
   */
  yoy_member_old_customer_aus?: number | null;
  /**
   * 周期复购人数环比
   */
  mom_period_repurchase_users?: number | null;
  /**
   * 告警列表
   */
  alerts?: HealthAlertItem[];
}
/**
 * 健康评分目标值（自动沿用去年同周期实际值）
 */
export interface HealthTargetsResponse {
  /**
   * 分析日期 YYYY-MM-DD
   */
  analysis_date: string;
  /**
   * 分析周期天数
   */
  period_days?: number;
  /**
   * 指定渠道
   */
  channel?: string | null;
  /**
   * 排除渠道
   */
  exclude_channels?: string[] | null;
  /**
   * 全店复购率目标
   */
  all_store_repurchase_rate: number;
  /**
   * 本品复购率目标
   */
  same_product_repurchase_rate: number;
  /**
   * 老客占比目标 0-1 decimal
   */
  old_customer_gsv_ratio: number;
  /**
   * 老客AUS目标
   */
  old_customer_aus: number;
  /**
   * 周均复购人数目标
   */
  recent_7d_repurchase_users: number;
}
/**
 * 分渠道新客质量
 */
export interface NewCustomerChannelQuality {
  /**
   * 渠道
   */
  channel: string;
  /**
   * 首购人数
   */
  first_purchase_users: number;
  /**
   * 首购客单价
   */
  first_purchase_aus: number;
  day30_repurchase_rate?: number;
  day90_repurchase_rate?: number;
  avg_days_to_repurchase?: number | null;
  /**
   * 质量分 0-100
   */
  quality_score: number;
  /**
   * A/B/C/D
   */
  quality_grade: string;
}
/**
 * 新客转化漏斗
 */
export interface NewCustomerConversionFunnel {
  /**
   * 首购月份
   */
  cohort_date: string;
  /**
   * 首购人数
   */
  total_first_purchase: number;
  day7_repurchase?: number;
  day7_rate?: number;
  day30_repurchase?: number;
  day30_rate?: number;
  day90_repurchase?: number;
  day90_rate?: number;
  year_repurchase?: number;
  year_rate?: number;
  day7_not_repurchased?: number;
  day30_not_repurchased?: number;
  day90_not_repurchased?: number;
}
/**
 * 新客转化追踪响应
 */
export interface NewCustomerConversionResponse {
  /**
   * 分析日期
   */
  analysis_date: string;
  overall_funnel?: NewCustomerConversionFunnel;
  cohort_funnels?: NewCustomerConversionFunnel[];
  channel_quality?: NewCustomerChannelQuality[];
  monthly_trend?: {
    [k: string]: unknown;
  }[];
}
/**
 * 品类复购指标（含同比）
 */
export interface ProductClassRepurchase {
  /**
   * 品类名称
   */
  product_class: string;
  /**
   * 购买人数
   */
  total_buyers: number;
  /**
   * 复购人数
   */
  repurchase_users: number;
  /**
   * 复购率 0-1 decimal
   */
  repurchase_rate: number;
  /**
   * 中位复购天数
   */
  median_days: number;
  /**
   * P25复购天数
   */
  p25_days: number;
  /**
   * P75复购天数
   */
  p75_days: number;
  /**
   * 平均复购天数
   */
  avg_days?: number | null;
  /**
   * 客单价（含首购）
   */
  avg_order_value: number;
  /**
   * GSV（含首购）
   */
  gsv: number;
  /**
   * 复购客单价（仅复购订单）
   */
  repurchase_order_value: number;
  /**
   * 复购GSV（仅复购订单）
   */
  repurchase_gsv: number;
  /**
   * 去年同期复购率 0-1 decimal
   */
  ly_repurchase_rate?: number | null;
  /**
   * 去年同期中位天数
   */
  ly_median_days?: number | null;
  /**
   * 去年同期平均天数
   */
  ly_avg_days?: number | null;
  /**
   * 去年同期GSV
   */
  ly_gsv?: number | null;
  /**
   * 复购率同比(pp 差 -100~+100)
   */
  repurchase_rate_yoy?: number | null;
  /**
   * 中位天数同比（原始天数差 cur-ly）
   */
  median_days_yoy?: number | null;
  /**
   * 平均天数YOY（原始天数差 cur-ly）
   */
  avg_days_yoy?: number | null;
  /**
   * GSV同比 0-1 decimal (cur-ly)/ly
   */
  gsv_yoy?: number | null;
}
/**
 * 大促日历响应
 */
export interface PromotionCalendarResponse {
  analysis_year: number;
  promotions?: PromotionVsDailyMetrics[];
  /**
   * 全年大促GSV占比 0-1 decimal
   */
  annual_promo_gsv_ratio?: number;
  /**
   * 全年大促用户占比 0-1 decimal
   */
  annual_promo_user_ratio?: number;
  promo_dependency_score?: number;
  dependency_level?: string;
}
/**
 * 单个大促 vs 日常对比
 */
export interface PromotionVsDailyMetrics {
  promotion: PromotionPeriod;
  promo_old_customer_count?: number;
  promo_old_customer_gsv?: number;
  promo_old_customer_aus?: number;
  promo_repurchase_rate?: number;
  daily_old_customer_count?: number;
  daily_old_customer_gsv?: number;
  daily_old_customer_aus?: number;
  daily_repurchase_rate?: number;
  gsv_lift?: number | null;
  aus_lift?: number | null;
  repurchase_lift?: number | null;
}
/**
 * 大促周期定义
 */
export interface PromotionPeriod {
  /**
   * 活动名称
   */
  name: string;
  start_date: string;
  end_date: string;
  year: number;
}
/**
 * 复购间隔桶（含去年同期对比）
 */
export interface RepurchaseBucket {
  /**
   * 桶标签 如'0-7天'
   */
  bucket_label: string;
  /**
   * 桶起始天数
   */
  bucket_start: number;
  /**
   * 桶结束天数（None表示无上限）
   */
  bucket_end?: number | null;
  /**
   * 该桶人数
   */
  user_count: number;
  /**
   * 占复购人群比例 0-1 decimal
   */
  user_ratio: number;
  /**
   * 去年同期该桶人数
   */
  ly_user_count?: number | null;
  /**
   * 去年同期占比 0-1 decimal
   */
  ly_user_ratio?: number | null;
  /**
   * 前年同期该桶人数
   */
  prev2_user_count?: number | null;
  /**
   * 前年同期占比 0-1 decimal
   */
  prev2_user_ratio?: number | null;
  /**
   * 人数同比（percentage 已 *100）
   */
  user_count_yoy?: number | null;
  /**
   * 占比同比 (pp 差)
   */
  user_ratio_yoy?: number | null;
}
/**
 * 复购周期概览
 */
export interface RepurchaseCycleOverview {
  /**
   * 开始日期
   */
  period_start: string;
  /**
   * 结束日期
   */
  period_end: string;
  /**
   * 中位复购天数
   */
  all_store_median_days: number;
  /**
   * P25
   */
  all_store_p25_days: number;
  /**
   * P75
   */
  all_store_p75_days: number;
  /**
   * 平均复购天数
   */
  all_store_avg_days: number;
  /**
   * 全店复购率 0-1 decimal
   */
  all_store_repurchase_rate: number;
  /**
   * 去年同期中位复购天数
   */
  ly_all_store_median_days?: number | null;
  /**
   * 去年同期P25
   */
  ly_all_store_p25_days?: number | null;
  /**
   * 去年同期P75
   */
  ly_all_store_p75_days?: number | null;
  /**
   * 去年同期平均复购天数
   */
  ly_all_store_avg_days?: number | null;
  /**
   * 去年同期全店复购率 0-1 decimal
   */
  ly_all_store_repurchase_rate?: number | null;
  /**
   * 全店复购率同比 (pp 差)
   */
  yoy_all_store_repurchase_rate?: number | null;
  /**
   * 中位天数同比 (raw diff)
   */
  median_days_yoy?: number | null;
  /**
   * P25天数同比 (raw diff)
   */
  p25_days_yoy?: number | null;
  /**
   * P75天数同比 (raw diff)
   */
  p75_days_yoy?: number | null;
  /**
   * 平均天数同比 (raw diff)
   */
  avg_days_yoy?: number | null;
  bucket_distribution?: RepurchaseBucket[];
  by_product_class?: ProductClassRepurchase[];
  /**
   * 跨品类回购店铺指标（首购该品类后又买店铺任意品类）
   */
  by_product_class_return?: ProductClassRepurchase[];
  /**
   * 当前年份
   */
  year_label: string;
  /**
   * 对比年份（去年）
   */
  comp_year_label: string;
  /**
   * 前年
   */
  prev2_year_label: string;
}
export interface TemplatesResponse {
  templates: {
    [k: string]: unknown;
  }[];
  modules: string[];
}
/**
 * 价值分层回购率流转响应
 */
export interface TierFlowResponse {
  /**
   * 当前年份
   */
  year_label: string;
  /**
   * 对比年份（去年）
   */
  comp_year_label: string;
  /**
   * 前年
   */
  prev2_year_label: string;
  metric_type?: string;
  rows?: TierFlowRow[];
  same_channel_rows?: TierFlowRow[];
  member_rows?: TierFlowRow[];
  member_same_channel_rows?: TierFlowRow[];
}
/**
 * 价值分层回购率单行数据
 */
export interface TierFlowRow {
  /**
   * 分层标签，如 S-高频
   */
  tier_segment: string;
  hist_users_current?: number;
  repurchase_users_current?: number;
  repurchase_rate_current?: number;
  repurchase_gsv_current?: number;
  /**
   * 回购GSV占全店GSV比例 0-1 decimal
   */
  repurchase_gsv_ratio_current?: number;
  hist_users_comp?: number;
  repurchase_users_comp?: number;
  repurchase_rate_comp?: number;
  repurchase_gsv_comp?: number;
  repurchase_gsv_ratio_comp?: number;
  hist_users_prev2?: number;
  repurchase_users_prev2?: number;
  repurchase_rate_prev2?: number;
  repurchase_gsv_prev2?: number;
  repurchase_gsv_ratio_prev2?: number;
  yoy_hist_users?: number | null;
  yoy_repurchase_users?: number | null;
  yoy_repurchase_rate?: number | null;
  yoy_repurchase_gsv?: number | null;
  yoy_repurchase_gsv_ratio?: number | null;
}
/**
 * 价值分层定义（动态计算）
 */
export interface ValueTierDefinition {
  /**
   * S/A/B/C
   */
  tier_code: string;
  /**
   * 层级名称
   */
  tier_name: string;
  /**
   * GSV下限
   */
  gsv_threshold_min?: number | null;
  /**
   * GSV上限
   */
  gsv_threshold_max?: number | null;
  /**
   * 人数
   */
  user_count: number;
  /**
   * GSV
   */
  gsv: number;
  /**
   * 占全店GSV比例 0-1 decimal
   */
  gsv_ratio: number;
}
/**
 * 价值分层响应
 */
export interface ValueTierResponse {
  /**
   * 分析日期
   */
  analysis_date: string;
  /**
   * 回溯天数
   */
  lookback_days?: number;
  value_tiers?: ValueTierDefinition[];
  frequency_tiers?: FrequencyTierDefinition[];
  segments?: CustomerSegmentItem[];
  /**
   * 自动洞察
   */
  insights?: string[];
}
