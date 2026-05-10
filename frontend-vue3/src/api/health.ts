import client from './index'
import type { components } from './types'

// ── 类型导入（openapi-typescript 自动生成，禁止手写覆盖）──────────────────────
export type HealthOverviewMetrics = components['schemas']['HealthOverviewMetrics']
export type HealthAlertItem = components['schemas']['HealthAlertItem']
export type RepurchaseCycleOverview = components['schemas']['RepurchaseCycleOverview']
export type CohortRetentionResponse = components['schemas']['CohortRetentionResponse']
export type ValueTierResponse = components['schemas']['ValueTierResponse']
export type NewCustomerConversionResponse = components['schemas']['NewCustomerConversionResponse']
export type PromotionCalendarResponse = components['schemas']['PromotionCalendarResponse']
export type ChannelHealthScoreItem = components['schemas']['ChannelHealthScoreItem']
export type ChannelHealthScoresResponse = components['schemas']['ChannelHealthScoresResponse']
export type RFMConfigResponse = components['schemas']['RFMConfigResponse']
export type SegmentDefinitionItem = components['schemas']['SegmentDefinitionItem']
export type RFMThresholds = components['schemas']['RFMThresholds']

export interface HealthOverviewParams {
  analysis_date: string
  period_days?: number
  exclude_channels?: string[]
  channel?: string
  compare_start_date?: string
  compare_end_date?: string
}

export function fetchHealthOverview(params: HealthOverviewParams): Promise<HealthOverviewMetrics> {
  return client.get('/v1/customer-health/overview', { params })
}

// ── 渠道健康评分对比 ──
export interface ChannelHealthScoresParams {
  analysis_date: string
  period_days?: number
  exclude_channels?: string[]
}

export function fetchChannelHealthScores(params: ChannelHealthScoresParams): Promise<ChannelHealthScoresResponse> {
  return client.get('/v1/customer-health/channel-health-scores', { params })
}

export interface RepurchaseCycleParams {
  start_date: string
  end_date: string
  channel?: string
  exclude_channels?: string[]
  compare_start_date?: string
  compare_end_date?: string
}

export function fetchRepurchaseCycle(params: RepurchaseCycleParams): Promise<RepurchaseCycleOverview> {
  return client.get('/v1/customer-health/repurchase-cycle', { params })
}

export interface CohortRetentionParams {
  start_month: string
  end_month: string
  exclude_channels?: string[]
  channel?: string
}

export function fetchCohortRetention(params: CohortRetentionParams): Promise<CohortRetentionResponse> {
  return client.get('/v1/customer-health/cohort-retention', { params })
}

export interface ValueTiersParams {
  analysis_date: string
  lookback_days?: number
  exclude_channels?: string[]
  channel?: string
}

export function fetchValueTiers(params: ValueTiersParams): Promise<ValueTierResponse> {
  return client.get('/v1/customer-health/value-tiers', { params })
}

// ── 价值分层回购率流转（逻辑同R区间，分层维度为S/A/B/C×高/中/低频）──

export interface TierFlowRow {
  tier_segment: string
  hist_users_current: number
  repurchase_users_current: number
  repurchase_rate_current: number
  repurchase_gsv_current: number
  repurchase_gsv_ratio_current: number
  hist_users_comp: number
  repurchase_users_comp: number
  repurchase_rate_comp: number
  repurchase_gsv_comp: number
  repurchase_gsv_ratio_comp: number
  hist_users_prev2: number
  repurchase_users_prev2: number
  repurchase_rate_prev2: number
  repurchase_gsv_prev2: number
  repurchase_gsv_ratio_prev2: number
  yoy_hist_users: number | null
  yoy_repurchase_users: number | null
  yoy_repurchase_rate: number | null
  yoy_repurchase_gsv: number | null
  yoy_repurchase_gsv_ratio: number | null
}

export interface TierFlowResponse {
  year_label: string
  comp_year_label: string
  prev2_year_label: string
  metric_type: string
  rows: TierFlowRow[]
  same_channel_rows: TierFlowRow[]
  member_rows: TierFlowRow[]
  member_same_channel_rows: TierFlowRow[]
}

export interface TierFlowParams {
  start_date: string
  end_date: string
  metric_type?: 'GSV' | 'GMV'
  channel?: string
  exclude_channels?: string[]
  compare_start_date?: string
  compare_end_date?: string
}

export function fetchTierFlow(params: TierFlowParams): Promise<TierFlowResponse> {
  return client.get('/v1/customer-health/tier-flow', { params })
}

// ── RFM完整分析（8象限人群分群）──

export interface RFMAnalysisRow {
  rfm_segment: string
  hist_users_current: number
  repurchase_users_current: number
  repurchase_rate_current: number
  repurchase_gsv_current: number
  repurchase_gsv_ratio_current: number
  hist_users_comp: number
  repurchase_users_comp: number
  repurchase_rate_comp: number
  repurchase_gsv_comp: number
  repurchase_gsv_ratio_comp: number
  hist_users_prev2: number
  repurchase_users_prev2: number
  repurchase_rate_prev2: number
  repurchase_gsv_prev2: number
  repurchase_gsv_ratio_prev2: number
  yoy_hist_users: number | null
  yoy_repurchase_users: number | null
  yoy_repurchase_rate: number | null
  yoy_repurchase_gsv: number | null
  yoy_repurchase_gsv_ratio: number | null
}

export interface RFMAnalysisResponse {
  year_label: string
  comp_year_label: string
  prev2_year_label: string
  metric_type: string
  rows: RFMAnalysisRow[]
  same_channel_rows: RFMAnalysisRow[]
  member_rows: RFMAnalysisRow[]
  member_same_channel_rows: RFMAnalysisRow[]
}

export interface RFMAnalysisParams {
  start_date: string
  end_date: string
  metric_type?: 'GSV' | 'GMV'
  channel?: string
  exclude_channels?: string[]
  compare_start_date?: string
  compare_end_date?: string
}

export function fetchRFMAnalysis(params: RFMAnalysisParams): Promise<RFMAnalysisResponse> {
  return client.get('/v1/customer-health/rfm-analysis', { params })
}

export interface NewCustomerConversionParams {
  analysis_date: string
  lookback_months?: number
  exclude_channels?: string[]
}

export function fetchNewCustomerConversion(params: NewCustomerConversionParams): Promise<NewCustomerConversionResponse> {
  return client.get('/v1/customer-health/new-customer-conversion', { params })
}

export interface PromotionCalendarParams {
  year?: number
  exclude_channels?: string[]
}

export function fetchPromotionCalendar(params: PromotionCalendarParams): Promise<PromotionCalendarResponse> {
  return client.get('/v1/customer-health/promotion-calendar', { params })
}

// P1 fix: 配置写接口已移除（方案A）。配置修改请直接编辑后端 health_config.json 文件。
// 保留 GET 操作供前端只读展示。

// ── 配置管理（只读） ──
export interface HealthConfig {
  weights: Record<string, number>
  targets: Record<string, number>
  alert_thresholds: Record<string, number>
  health_level_bounds: Record<string, number>
  value_tier: Record<string, number>
  frequency_tier: Record<string, number>
  promotions: Array<{ name: string; start_date: string; end_date: string }>
}

export function fetchHealthConfig(): Promise<HealthConfig> {
  return client.get('/v1/customer-health/config')
}

// 审计 API 鉴权用（从 Vite 环境变量读取）
const _AUDIT_KEY = import.meta.env.VITE_HEALTH_API_KEY || ''

// ── 配置历史（只读） ──
export interface ConfigHistoryItem {
  backup_id: string
  action: string
  timestamp: string
  file_name: string
}

export interface ConfigHistoryResponse {
  history: ConfigHistoryItem[]
}

export function fetchConfigHistory(limit = 20): Promise<ConfigHistoryResponse> {
  return client.get('/v1/customer-health/config/history', { params: { limit, x_api_key: _AUDIT_KEY } })
}

// ── 审计日志 ──
export interface AuditLogItem {
  timestamp: string
  action: string
  details: Record<string, any>
}

export interface AuditLogResponse {
  logs: AuditLogItem[]
}

export function fetchAuditLog(limit = 50): Promise<AuditLogResponse> {
  return client.get('/v1/customer-health/config/audit-log', { params: { limit, x_api_key: _AUDIT_KEY } })
}

// ── 指标目标值查询 ──
export interface HealthTargetsResponse {
  analysis_date: string
  period_days: number
  channel?: string
  exclude_channels?: string[]
  all_store_repurchase_rate: number
  same_product_repurchase_rate: number
  old_customer_gsv_ratio: number
  old_customer_aus: number
  recent_7d_repurchase_users: number
}

export function fetchHealthTargets(params: {
  analysis_date: string
  period_days?: number
  exclude_channels?: string[]
  channel?: string
}): Promise<HealthTargetsResponse> {
  return client.get('/v1/customer-health/targets', { params })
}

// ── RFM 阈值配置（前后端同步唯一数据源） ──
export function fetchRFMConfig(): Promise<RFMConfigResponse> {
  return client.get('/v1/customer-health/config/rfm')
}

// ── RFM 品类下钻 ──
export interface RFMCategoryDrilldownRow {
  category_name: string
  hist_users_current: number
  repurchase_users_current: number
  repurchase_rate_current: number
  repurchase_gsv_current: number
  repurchase_gsv_ratio_current: number
  hist_users_comp: number; repurchase_users_comp: number; repurchase_rate_comp: number
  repurchase_gsv_comp: number; repurchase_gsv_ratio_comp: number
  hist_users_prev2: number; repurchase_users_prev2: number; repurchase_rate_prev2: number
  repurchase_gsv_prev2: number; repurchase_gsv_ratio_prev2: number
  yoy_hist_users: number | null; yoy_repurchase_users: number | null
  yoy_repurchase_rate: number | null; yoy_repurchase_gsv: number | null
  yoy_repurchase_gsv_ratio: number | null
}
export interface RFMCategoryDrilldownSummary {
  total_hist_users: number; total_repurchase_users: number
  overall_repurchase_rate: number; overall_repurchase_rate_comp: number; overall_repurchase_rate_yoy: number
  declining_categories: { name: string; yoy_repurchase_rate: number }[]
  improving_categories: { name: string; yoy_repurchase_rate: number }[]
}
export interface RFMCategoryDrilldownResponse {
  rfm_segment: string; year_label: string; comp_year_label: string; prev2_year_label: string; metric_type: string
  categories: RFMCategoryDrilldownRow[]; member_categories: RFMCategoryDrilldownRow[]; summary: RFMCategoryDrilldownSummary
}
export interface RFMCategoryDrilldownParams {
  rfm_segment: string; start_date: string; end_date: string
  metric_type?: 'GSV' | 'GMV'; channel?: string; exclude_channels?: string[]
  compare_start_date?: string; compare_end_date?: string
}
export function fetchRFMCategoryDrilldown(params: RFMCategoryDrilldownParams): Promise<RFMCategoryDrilldownResponse> {
  return client.get('/v1/customer-health/rfm-category-drilldown', { params })
}
