import client from './index'

// 与 backend/contracts/schemas.py 保持同步

export interface BreakdownRequest {
  target_gmv: number
  activity_start: string
  activity_end: string
  last_year_start?: string
  last_year_end?: string
  metric_type?: string
  old_customer_ratio_target?: number
  breakdown_mode?: 'forward' | 'reverse'
}

// ── 老客 R 区间明细 ──

export interface BreakdownRIntervalRow {
  r_interval: string
  f_segment: string
  user_count: number
  ly_repurchase_rate: number
  est_repurchase_rate: number
  est_aus: number
  est_gmv: number
  ly_total_users?: number
  ly_repurchased_users?: number
}

export interface BreakdownRIntervalReverseRow {
  r_interval: string
  f_segment: string
  current_users: number
  est_repurchase_rate: number
  est_aus: number
  interval_target_gmv: number
  needed_users: number
  user_gap: number
  ly_repurchase_rate?: number
  ly_total_users?: number
}

// ── 新客渠道明细 ──

export interface ChannelBreakdown {
  channel: string
  ly_new_users: number
  est_new_users: number
  ly_new_aus: number
  est_new_aus: number
  est_new_gmv: number
}

export interface BreakdownChannelNewReverseRow {
  channel: string
  ly_new_users: number
  ly_new_aus: number
  channel_target_gmv: number
  needed_users: number
  user_gap: number
}

// ── 老客/新客结果 ──

export interface BreakdownOldCustomer {
  old_users_total: number
  old_gmv_target: number
  old_gmv_estimate?: number | null
  old_gmv_gap?: number | null
  r_interval_breakdown?: (BreakdownRIntervalRow | BreakdownRIntervalReverseRow)[]
  repurchase_rate_reference?: Record<string, number>
}

export interface BreakdownNewCustomer {
  new_users_total?: number | null
  new_gmv_target: number
  new_gmv_estimate?: number | null
  new_gmv_gap?: number | null
  channel_breakdown: ChannelBreakdown[]
  uv_reference: number
  member_join_rate: number
  needed_uv?: number | null
  uv_gap?: number | null
}

// ── 建议 ──

export interface BreakdownGapSuggestion {
  dimension: string
  gap_amount?: number | null
  gap_users?: number | null
  uv_gap?: number | null
  suggestions: string[]
  priority: string
}

// ── 元数据 ──

export interface RFMTier {
  rfm_tier: string
  user_count: number
  avg_recency: number | null
  avg_frequency: number | null
  avg_monetary: number | null
}

export interface BreakdownMeta {
  activity_type: string
  repurchase_adjustment: number
  metric_type?: string
  rfm_tiers?: RFMTier[]
}

export interface DateRangeResponse {
  start: string
  end: string
  cutoff?: string
}

export interface BreakdownLogic {
  old_customer_formula: string
  old_customer_source: string
  new_customer_formula: string
  new_customer_source: string
}

// ── 响应 ──

export interface BreakdownResponse {
  mode: 'forward' | 'reverse'
  mode_label: string
  target_gmv: number
  total_estimate?: number | null
  total_gap?: number | null
  gap_ratio?: number | null
  old_customer: BreakdownOldCustomer
  new_customer: BreakdownNewCustomer
  suggestions: BreakdownGapSuggestion[]
  activity_period: DateRangeResponse
  reference_period: DateRangeResponse
  meta: BreakdownMeta
  breakdown_logic: BreakdownLogic
}

export function fetchBreakdownOneClick(payload: BreakdownRequest): Promise<BreakdownResponse> {
  return client.post('/v1/breakdown/one-click', payload)
}
