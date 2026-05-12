import client from './index'

// ── 渠道汇总 ──

export interface SamplingChannelSummary {
  channel: string
  sample_users: number
  repurchase_users_7d: number
  repurchase_users_30d: number
  repurchase_users_60d: number
  repurchase_rate_7d: number
  repurchase_rate_30d: number
  repurchase_rate_60d: number
  repurchase_gsv_7d: number
  repurchase_gsv_30d: number
  repurchase_gsv_60d: number
  repurchase_aus_7d: number
  repurchase_aus_30d: number
  repurchase_aus_60d: number
}

// ── 品类明细 ──

export interface SamplingCategoryRow {
  channel: string
  category: string
  sample_users: number
  repurchase_users: number
  repurchase_rate: number
  repurchase_gsv: number
  repurchase_aus: number
  same_category_repurchase: number
  same_category_rate: number
}

// ── 时间范围 ──

export interface SamplingROITimeRange {
  start: string
  end: string
  window_days: number
}

// ── ROI 响应 ──

export interface SamplingROIResponse {
  summary: {
    channels: SamplingChannelSummary[]
  }
  category_breakdown: SamplingCategoryRow[]
  time_range: SamplingROITimeRange
}

// ── 锁权活动信息 ──

export interface SamplingLockCampaignInfo {
  year: number
  campaign_name: string
  conversion_start: string | null
  conversion_end: string | null
  lock_start: string | null
  lock_end: string | null
  error?: string
}

// ── 锁权单年数据 ──

export interface SamplingLockYearData {
  total_uv: number
  locked_users: number
  lock_rate: number
  converted_users: number
  conversion_rate: number
  lock_gsv: number
  lock_aus: number
  new_locked_users: number
  new_locked_ratio: number
  new_converted_users: number
  new_conversion_rate: number
  new_lock_gsv: number
  new_lock_aus: number
}

// ── 锁权YoY ──

export interface SamplingLockYOY {
  total_uv: number | null
  locked_users: number | null
  lock_rate: number | null
  converted_users: number | null
  conversion_rate: number | null
  lock_gsv: number | null
  lock_aus: number | null
  new_locked_users: number | null
  new_locked_ratio: number | null
  new_converted_users: number | null
  new_conversion_rate: number | null
  new_lock_gsv: number | null
  new_lock_aus: number | null
}

// ── 锁权分析响应 ──

export interface SamplingLockAnalysisResponse {
  campaign_info: SamplingLockCampaignInfo
  current_year: SamplingLockYearData
  last_year: SamplingLockYearData
  yoy: SamplingLockYOY
}

// ── API 函数 ──

export function fetchSamplingROI(params: {
  start_date: string
  end_date: string
  window_days?: number
  level?: string
  channel?: string
}): Promise<SamplingROIResponse> {
  return client.get('/v1/sampling/roi', { params })
}

export function fetchSamplingLockAnalysis(params: {
  campaign_name: string
  year: number
}): Promise<SamplingLockAnalysisResponse> {
  return client.get('/v1/sampling/lock-analysis', { params })
}

// ── 0.01派样滚动同期对比 ──

export interface RollingYearMetrics {
  phase: string
  total_uv: number
  locked_users: number
  lock_rate: number
  new_locked_users: number
  new_locked_ratio: number
  old_locked_users: number
  old_locked_ratio: number
  converted_users: number
  conversion_rate: number
  conv_gsv: number
  conv_aus: number
  new_converted_users: number
  new_conversion_rate: number
  new_conv_gsv: number
  new_conv_aus: number
  old_converted_users: number
  old_conversion_rate: number
}

export interface RollingYOY {
  total_uv: number | null
  locked_users: number | null
  lock_rate: number | null
  new_locked_users: number | null
  new_locked_ratio: number | null
  converted_users: number | null
  conversion_rate: number | null
  conv_gsv: number | null
  conv_aus: number | null
  new_converted_users: number | null
  new_conversion_rate: number | null
  new_conv_gsv: number | null
  new_conv_aus: number | null
}

export interface RollingTimeline {
  year_a_sample_start: string
  year_a_sample_end: string
  year_a_conv_start: string
  year_b_sample_start: string
  year_b_sample_end: string
  year_b_conv_start: string
  rolling_end: string
  year_b_equiv_end: string
  T: number
  T_sample_a: number
  T_sample_b: number
  T_conv: number
}

export interface RollingComparisonResponse {
  year_a: RollingYearMetrics
  year_b: RollingYearMetrics
  yoy: RollingYOY
  timeline: RollingTimeline
}

export function fetchRollingComparison(params: {
  year_a_sample_start: string
  year_a_sample_end: string
  year_a_conv_start: string
  year_b_sample_start: string
  year_b_sample_end: string
  year_b_conv_start: string
  rolling_end: string
}): Promise<RollingComparisonResponse> {
  return client.get('/v1/sampling/rolling-comparison', { params })
}
