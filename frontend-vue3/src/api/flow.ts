import client from './index'

// ============================================================
// RFM - R区间流转看板
// ============================================================

export interface RFMRFlowParams {
  start_date: string
  end_date: string
  channel?: string
  metric_type?: 'GSV' | 'GMV'
  exclude_channels?: string[]
  compare_start_date?: string
  compare_end_date?: string
}

export interface RFMRFlowRow {
  r_segment: string
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
  yoy_repurchase_gsv_ratio_ppt: number | null
}

export interface RFMRFlowResponse {
  year_label: string
  comp_year_label: string
  prev2_year_label: string
  metric_type: string
  rows: RFMRFlowRow[]
  same_channel_rows: RFMRFlowRow[]
  member_rows: RFMRFlowRow[]
  member_same_channel_rows: RFMRFlowRow[]
}

export function fetchRFMRFlow(params: RFMRFlowParams, signal?: AbortSignal): Promise<RFMRFlowResponse> {
  return client.get('/v1/rfm/r-flow', { params, signal })
}

// F 区间流转（与 R 结构完全一致，仅字段名不同）
export type RFMFRFlowRow = Omit<RFMRFlowRow, 'r_segment'> & { f_segment: string }
export type RFMFRFlowResponse = Omit<RFMRFlowResponse, 'rows' | 'same_channel_rows' | 'member_rows' | 'member_same_channel_rows'> & {
  rows: RFMFRFlowRow[]
  same_channel_rows: RFMFRFlowRow[]
  member_rows: RFMFRFlowRow[]
  member_same_channel_rows: RFMFRFlowRow[]
}

export function fetchRFMFRFlow(params: RFMRFlowParams, signal?: AbortSignal): Promise<RFMFRFlowResponse> {
  return client.get('/v1/rfm/f-flow', { params, signal })
}

// M 区间流转（与 R 结构完全一致，仅字段名不同）
export type RFMMFlowRow = Omit<RFMRFlowRow, 'r_segment'> & { m_segment: string }
export type RFMMFlowResponse = Omit<RFMRFlowResponse, 'rows' | 'same_channel_rows' | 'member_rows' | 'member_same_channel_rows'> & {
  rows: RFMMFlowRow[]
  same_channel_rows: RFMMFlowRow[]
  member_rows: RFMMFlowRow[]
  member_same_channel_rows: RFMMFlowRow[]
}

export function fetchRFMMFlow(params: RFMRFlowParams, signal?: AbortSignal): Promise<RFMMFlowResponse> {
  return client.get('/v1/rfm/m-flow', { params, signal })
}

// Sprint 175 Q2: 接口整段删除 (用户拍板)
