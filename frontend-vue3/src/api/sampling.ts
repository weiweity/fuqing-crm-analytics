import client from './index'

// ── 渠道汇总 ──

export interface SamplingChannelSummary {
  channel: string
  sample_users: number
  // Sprint 140: 统一窗口字段（任意 window_days）
  repurchase_users: number
  repurchase_rate: number
  repurchase_gsv: number
  repurchase_aus: number
  // Sprint 139 保留: 正装/非正装 split
  full_repurchase_users: number
  full_repurchase_rate: number
  full_repurchase_gsv: number
  full_repurchase_aus: number
  nonfull_repurchase_users: number
  nonfull_repurchase_gsv: number
  nonfull_repurchase_aus: number
  repurchase_users_yoy_pct?: number | null
  repurchase_gsv_yoy_pct?: number | null
  repurchase_rate_yoy_pp?: number | null
  full_repurchase_users_yoy_pct?: number | null
  full_repurchase_gsv_yoy_pct?: number | null
  full_repurchase_rate_yoy_pp?: number | null
  repurchase_aus_yoy_pct?: number | null
  full_repurchase_aus_yoy_pct?: number | null
  nonfull_repurchase_gsv_yoy_pct?: number | null
  repurchase_users_mom_pct?: number | null
  repurchase_gsv_mom_pct?: number | null
  repurchase_rate_mom_pp?: number | null
  full_repurchase_users_mom_pct?: number | null
  full_repurchase_gsv_mom_pct?: number | null
  full_repurchase_rate_mom_pp?: number | null
  repurchase_aus_mom_pct?: number | null
  full_repurchase_aus_mom_pct?: number | null
  nonfull_repurchase_gsv_mom_pct?: number | null
}

// ── level 二级聚合 ──

export interface SamplingLevelSummary {
  channel: string
  level: string
  level_value: string
  sample_users: number
  repurchase_users: number
  repurchase_rate: number
  repurchase_gsv: number
  repurchase_aus: number
  full_repurchase_users: number
  full_repurchase_rate: number
  full_repurchase_gsv: number
  full_repurchase_aus: number
  nonfull_repurchase_users: number
  nonfull_repurchase_gsv: number
  nonfull_repurchase_aus: number
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
  full_repurchase_users: number
  full_repurchase_rate: number
  full_repurchase_gsv: number
  full_repurchase_aus: number
  nonfull_repurchase_users: number
  nonfull_repurchase_gsv: number
  nonfull_repurchase_aus: number
  // Sprint 175 Q5: YOY/MOM 同比字段 (backend service 已 fetch, frontend 暴露)
  repurchase_users_yoy_pct?: number | null
  repurchase_gsv_yoy_pct?: number | null
  repurchase_rate_yoy_pp?: number | null
  full_repurchase_users_yoy_pct?: number | null
  full_repurchase_gsv_yoy_pct?: number | null
  full_repurchase_rate_yoy_pp?: number | null
  repurchase_aus_yoy_pct?: number | null
  full_repurchase_aus_yoy_pct?: number | null
  nonfull_repurchase_gsv_yoy_pct?: number | null
}

// ── 时间范围 ──

export interface SamplingROITimeRange {
  start: string
  end: string
  window_days: number
}

// ── 回购周期分布 / DQM ──

export interface PeriodDistribution {
  bucket_1_3d: number
  bucket_4_7d: number
  bucket_8_30d: number
  bucket_31_60d: number
  bucket_61_90d: number
  full_bucket_1_3d: number
  full_bucket_4_7d: number
  full_bucket_8_30d: number
  full_bucket_31_60d: number
  full_bucket_61_90d: number
}

export interface QualityFlag {
  code: string
  severity: string
  message: string
  posize_ratio?: number | null
  total_posize_gsv?: number | null
  total_gsv?: number | null
}

export interface SamplingRepurchaseBucket {
  bucket: string
  users: number
  gsv: number
  aus: number
}

export interface SamplingRepurchaseDistribution {
  buckets: SamplingRepurchaseBucket[]
  window_days: number
}

// ── ROI 响应 ──

export interface SamplingROIResponse {
  summary: {
    channels: SamplingChannelSummary[]
  }
  category_breakdown: SamplingCategoryRow[]
  time_range: SamplingROITimeRange
  period_distribution: PeriodDistribution
  quality_flags: QualityFlag[]
  summary_by_level: Record<string, SamplingLevelSummary[]>
}

// ── API 函数 ──

export function fetchSamplingROI(params: {
  start_date: string
  end_date: string
  window_days?: number
  level?: string
  channel?: string
  compare_date_range?: [string, string] | null
  exclude_low_price?: boolean
}): Promise<SamplingROIResponse> {
  return client.get('/v1/sampling/roi', { params })
}

export function fetchSamplingRepurchaseDistribution(params: {
  start_date: string
  end_date: string
  window_days?: number
  channel?: string
}): Promise<SamplingRepurchaseDistribution> {
  return client.get('/v1/sampling/repurchase-distribution', { params })
}

// ── 回购周期跟踪 (3 年对比, Sprint 169) ──

export interface SamplingRepurchaseTrackingBucket {
  bucket: string
  year_label: string
  rate: number
  year_range_start: string
  year_range_end: string
}

export interface SamplingRepurchaseTrackingResponse {
  buckets: SamplingRepurchaseTrackingBucket[]
  year_labels: string[]
  time_range: SamplingROITimeRange
  window_days: number
}

export function fetchSamplingRepurchaseTracking(params: {
  start_date: string
  end_date: string
  window_days?: number
  channel?: string
}): Promise<SamplingRepurchaseTrackingResponse> {
  return client.get('/v1/sampling/repurchase-tracking', { params })
}

// ── LTV ──

export interface LifetimeValueSummary {
  cohort_date: string
  user_count: number
  ltv_90d_avg: number
  ltv_180d_avg: number
  ltv_365d_avg: number
  ltv_90d_median: number
  ltv_180d_median: number
  ltv_365d_median: number
  ltv_90d_yoy_pct: number
  ltv_180d_yoy_pct: number
  ltv_365d_yoy_pct: number
}

export function fetchLifetimeValue(params: {
  cohort_date: string
  channel?: string
}): Promise<LifetimeValueSummary> {
  return client.get('/v1/lifetime-value/cohort', { params })
}
