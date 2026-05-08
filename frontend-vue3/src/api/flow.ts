import client from './index'

export interface FlowMatrixParams {
  from_date: string
  to_date: string
  lookback_days?: number
  metric_type?: string
  exclude_channels?: string[]
}

export interface FlowMatrixResponse {
  flow_matrix: { from_segment: string; to_segment: string; count: number; ratio: number }[]
  segments: { id: number; name: string; count: number }[]
  from_date: string
  to_date: string
  from_total: number
  to_total: number
  summary: { retention_rate: number; upgrade_rate: number; downgrade_rate: number }
}

export interface FlowSankeyResponse {
  nodes: { id: number; name: string; value: number }[]
  links: { source: number; target: number; value: number }[]
  from_date: string
  to_date: string
}

export function fetchFlowMatrix(params: FlowMatrixParams): Promise<FlowMatrixResponse> {
  return client.get('/v1/flow/matrix', { params })
}

export function fetchFlowSankey(params: FlowMatrixParams): Promise<FlowSankeyResponse> {
  return client.get('/v1/flow/sankey', { params })
}

// ============================================================
// RFM - R区间流转看板
// ============================================================

export interface RFMRFlowParams {
  start_date: string
  end_date: string
  channel?: string
  metric_type?: 'GSV' | 'GMV'
  exclude_channels?: string[]
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
  yoy_repurchase_gsv_ratio: number | null
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

export function fetchRFMRFlow(params: RFMRFlowParams): Promise<RFMRFlowResponse> {
  return client.get('/v1/rfm/r-flow', { params })
}

// F 区间流转（与 R 结构完全一致，仅字段名不同）
export type RFMFRFlowRow = Omit<RFMRFlowRow, 'r_segment'> & { f_segment: string }
export type RFMFRFlowResponse = Omit<RFMRFlowResponse, 'rows' | 'same_channel_rows' | 'member_rows' | 'member_same_channel_rows'> & {
  rows: RFMFRFlowRow[]
  same_channel_rows: RFMFRFlowRow[]
  member_rows: RFMFRFlowRow[]
  member_same_channel_rows: RFMFRFlowRow[]
}

export function fetchRFMFRFlow(params: RFMRFlowParams): Promise<RFMFRFlowResponse> {
  return client.get('/v1/rfm/f-flow', { params })
}

// M 区间流转（与 R 结构完全一致，仅字段名不同）
export type RFMMFlowRow = Omit<RFMRFlowRow, 'r_segment'> & { m_segment: string }
export type RFMMFlowResponse = Omit<RFMRFlowResponse, 'rows' | 'same_channel_rows' | 'member_rows' | 'member_same_channel_rows'> & {
  rows: RFMMFlowRow[]
  same_channel_rows: RFMMFlowRow[]
  member_rows: RFMMFlowRow[]
  member_same_channel_rows: RFMMFlowRow[]
}

export function fetchRFMMFlow(params: RFMRFlowParams): Promise<RFMMFlowResponse> {
  return client.get('/v1/rfm/m-flow', { params })
}

// ============================================================
// RFM 区间订单明细导出
// ============================================================

export interface SegmentOrdersParams {
  dimension: 'r' | 'f' | 'm'
  segment: string
  start_date: string
  end_date: string
  metric_type?: 'GSV' | 'GMV'
  mode?: 'all' | 'member' | 'same_channel' | 'member_same_channel'
  channel?: string
  exclude_channels?: string[]
}

export interface SegmentOrderRow {
  order_id: string
  user_id: string
  pay_time: string
  actual_amount: number
  channel: string
  spu_product_class: string | null
}

export interface SegmentOrdersResponse {
  dimension: string
  segment: string
  mode: string
  total_orders: number
  rows: SegmentOrderRow[]
}

export function fetchSegmentOrders(params: SegmentOrdersParams): Promise<SegmentOrdersResponse> {
  return client.get('/v1/rfm/segment-orders', { params })
}

export async function downloadSegmentOrdersCSV(params: SegmentOrdersParams): Promise<void> {
  const data = await fetchSegmentOrders(params)
  if (!data.rows.length) {
    throw new Error('该区间无订单数据')
  }
  const headers = ['订单号', '用户ID', '支付时间', '金额', '渠道', '品类']
  const csvRows = [headers.join(',')]
  for (const r of data.rows) {
    csvRows.push([
      r.order_id,
      r.user_id,
      r.pay_time,
      r.actual_amount.toFixed(2),
      r.channel,
      r.spu_product_class ?? '',
    ].map(v => `"${String(v).replace(/"/g, '""')}"`).join(','))
  }
  const BOM = '\uFEFF'
  const blob = new Blob([BOM + csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `订单明细_${params.dimension.toUpperCase()}区间_${params.segment}_${params.start_date}_${params.end_date}.csv`
  a.click()
  URL.revokeObjectURL(url)
}
