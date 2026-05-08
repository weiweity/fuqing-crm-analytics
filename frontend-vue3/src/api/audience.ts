import client from './index'

export interface AudienceTableParams {
  date_start: string
  date_end: string
  channel?: string
  dimension?: string
  dim_value?: string
  exclude_channels?: string[]
  compare_start_date?: string
  compare_end_date?: string
}

export interface AudienceTableRow {
  dimension_value: string
  gsv: number
  user_count: number
  new_user_count: number
  new_user_ratio: number
  avg_order_amount: number
}

export interface ChannelSummary {
  channel: string
  gsv: number
  gsv_ratio: number
  order_count: number
  user_count: number
}

export interface DailyTrendPoint {
  date: string
  gsv: number
  member_ratio: number
  ly_gsv: number
  ly_member_ratio: number
}

export interface KPIMetrics {
  gsv: number
  gsv_yoy: number
  order_count: number
  order_count_yoy: number
  user_count: number
  user_count_yoy: number
  new_user_count: number
  new_user_ratio: number
  refund_rate: number
  refund_yoy: number
  avg_order_amount: number
  avg_order_yoy: number
  // v2.1 人群 GSV 及占比（YoY）
  old_gsv: number
  old_gsv_yoy: number
  new_gsv: number
  new_gsv_yoy: number
  member_gsv: number
  member_gsv_yoy: number
  old_gsv_ratio: number
  old_gsv_ratio_yoy: number
  new_gsv_ratio: number
  new_gsv_ratio_yoy: number
  member_gsv_ratio: number
  member_gsv_ratio_yoy: number
  // 会员溢价
  member_avg_order_amount: number
  member_premium: number
  member_premium_yoy: number
  // MoM（环比）
  gsv_mom: number
  order_count_mom: number
  user_count_mom: number
  old_gsv_mom: number
  new_gsv_mom: number
  member_gsv_mom: number
  old_gsv_ratio_mom: number
  new_gsv_ratio_mom: number
  member_gsv_ratio_mom: number
  member_premium_mom: number
}

export function fetchAudienceTable(params: AudienceTableParams): Promise<AudienceTableRow[]> {
  const backendParams: Record<string, any> = {
    dimension: params.dimension || 'channel',
    mode: 'free',
    start_date: params.date_start,
    end_date: params.date_end,
    metric_type: 'GMV',
  }
  if (params.channel) {
    backendParams.channels = params.channel
  }
  if (params.exclude_channels?.length) {
    backendParams.exclude_channels = params.exclude_channels
  }
  if (params.compare_start_date) backendParams.compare_start_date = params.compare_start_date
  if (params.compare_end_date) backendParams.compare_end_date = params.compare_end_date
  return client.get('/v1/audience/table', { params: backendParams }).then((res: any) => {
    return res.rows.map((row: any) => ({
      dimension_value: row.dimension,
      gsv: row.gsv,
      user_count: row.gsv_users,
      new_user_count: row.new_users,
      new_user_ratio: row.new_users_ratio,
      avg_order_amount: row.aus,
    }))
  })
}

export function fetchChannelSummary(params: Omit<AudienceTableParams, 'dimension' | 'dim_value'>): Promise<ChannelSummary[]> {
  const backendParams: Record<string, any> = { start_date: params.date_start, end_date: params.date_end, metric_type: 'GSV' }
  if (params.compare_start_date) backendParams.compare_start_date = params.compare_start_date
  if (params.compare_end_date) backendParams.compare_end_date = params.compare_end_date
  return client.get('/v1/metrics/overview', { params: backendParams }).then((res: any) => {
    return [{
      channel: '全店',
      gsv: res.amount,
      gsv_ratio: 1,
      order_count: res.order_count,
      user_count: res.new_users + res.old_users,
    }]
  })
}

export function fetchDailyTrend(params: Omit<AudienceTableParams, 'dimension' | 'dim_value'>): Promise<DailyTrendPoint[]> {
  const backendParams: Record<string, any> = {
    start_date: params.date_start,
    end_date: params.date_end,
    metric_type: 'GSV',
  }
  if (params.channel) backendParams.channel = params.channel
  if (params.exclude_channels?.length) backendParams.exclude_channels = params.exclude_channels
  if (params.compare_start_date) backendParams.compare_start_date = params.compare_start_date
  if (params.compare_end_date) backendParams.compare_end_date = params.compare_end_date
  return client.get('/v1/metrics/trend', { params: backendParams }).then((res: any) => {
    const dates = res.dates || []
    const amounts = res.amounts || []
    const member_ratios = res.member_ratios || []
    const ly_amounts = res.ly_amounts || []
    const ly_member_ratios = res.ly_member_ratios || []
    return dates.map((date: string, i: number) => ({
      date,
      gsv: amounts[i] || 0,
      member_ratio: member_ratios[i] ?? 0,
      ly_gsv: ly_amounts[i] || 0,
      ly_member_ratio: ly_member_ratios[i] ?? 0,
    }))
  })
}

export function fetchKPIMetrics(params: Omit<AudienceTableParams, 'dimension' | 'dim_value'>): Promise<KPIMetrics> {
  const backendParams: Record<string, any> = {
    start_date: params.date_start,
    end_date: params.date_end,
    metric_type: 'GSV',
  }
  if (params.channel) backendParams.channel = params.channel
  if (params.exclude_channels?.length) backendParams.exclude_channels = params.exclude_channels
  if (params.compare_start_date) backendParams.compare_start_date = params.compare_start_date
  if (params.compare_end_date) backendParams.compare_end_date = params.compare_end_date
  return client.get('/v1/metrics/overview', { params: backendParams }).then((res: any) => {
    const totalUsers = res.new_users + res.old_users
    return {
      gsv: res.amount,
      gsv_yoy: res.yoy_change?.amount_pct ?? 0,
      order_count: res.order_count,
      order_count_yoy: res.yoy_change?.order_count_pct ?? 0,
      user_count: totalUsers,
      user_count_yoy: 0,
      new_user_count: res.new_users,
      new_user_ratio: totalUsers > 0 ? res.new_users / totalUsers : 0,
      refund_rate: 0,
      refund_yoy: 0,
      avg_order_amount: res.avg_order_value,
      avg_order_yoy: res.yoy_change?.avg_order_value_pct ?? 0,
      // v2.1 人群 GSV 及占比（YoY）
      old_gsv: res.old_user_amount ?? 0,
      old_gsv_yoy: res.yoy_change?.old_user_amount_pct ?? 0,
      new_gsv: res.new_user_amount ?? 0,
      new_gsv_yoy: res.yoy_change?.new_user_amount_pct ?? 0,
      member_gsv: res.member_amount ?? 0,
      member_gsv_yoy: res.yoy_change?.member_amount_pct ?? 0,
      old_gsv_ratio: res.old_user_ratio ?? 0,
      old_gsv_ratio_yoy: res.yoy_change?.old_user_ratio_ppt ?? 0,
      new_gsv_ratio: res.new_user_ratio ?? 0,
      new_gsv_ratio_yoy: res.yoy_change?.new_user_ratio_ppt ?? 0,
      member_gsv_ratio: res.member_ratio ?? 0,
      member_gsv_ratio_yoy: res.yoy_change?.member_ratio_ppt ?? 0,
      // 会员溢价（member_premium 已是 % 数值，直接 fmtRatio 展示）
      member_avg_order_amount: res.member_avg_order_value ?? 0,
      member_premium: res.member_premium ?? 0,
      member_premium_yoy: res.yoy_change?.member_premium_ppt ?? 0,
      // MoM（环比）
      gsv_mom: res.mom_change?.amount_pct ?? 0,
      order_count_mom: res.mom_change?.order_count_pct ?? 0,
      user_count_mom: 0,
      old_gsv_mom: res.mom_change?.old_user_amount_pct ?? 0,
      new_gsv_mom: res.mom_change?.new_user_amount_pct ?? 0,
      member_gsv_mom: res.mom_change?.member_amount_pct ?? 0,
      old_gsv_ratio_mom: res.mom_change?.old_user_ratio_ppt ?? 0,
      new_gsv_ratio_mom: res.mom_change?.new_user_ratio_ppt ?? 0,
      member_gsv_ratio_mom: res.mom_change?.member_ratio_ppt ?? 0,
      member_premium_mom: res.mom_change?.member_premium_ppt ?? 0,
    }
  })
}

// ============================================================
// 三面板新增（30指标对比 + 渠道概览）
// ============================================================

export interface IndicatorRow {
  field: string
  value_2026: number | null
  value_2025: number | null
  value_2024: number | null
  yoy: number | null
  kind?: 'ratio' | 'count' | 'aus' | 'gsv'
}

export interface ChannelGSVRow {
  channel: string
  gsv_2026: number
  gsv_2025: number
  yoy: number | null
  ratio_2026: number
  ratio_2025: number
  ratio_yoy: number | null
  // 人数（Panel B=全店人数, Panel C=会员人数）
  users_2026?: number
  users_2025?: number
  users_yoy?: number | null
  // AUS（Panel B=全店AUS, Panel C=会员AUS）
  aus_2026?: number
  aus_2025?: number
  aus_yoy?: number | null
  // 全店新增：新客 GSV 及占比
  new_gsv_2026?: number
  new_gsv_2025?: number
  new_gsv_yoy?: number | null
  new_gsv_ratio_2026?: number
  new_gsv_ratio_2025?: number
  new_gsv_ratio_yoy?: number | null
  // 全店新增：老客 GSV 及占比
  old_gsv_2026?: number
  old_gsv_2025?: number
  old_gsv_yoy?: number | null
  old_gsv_ratio_2026?: number
  old_gsv_ratio_2025?: number
  old_gsv_ratio_yoy?: number | null
  // 新客人数（Panel B=全店新客人数, Panel C=会员新客人数）
  new_users_2026?: number
  new_users_2025?: number
  new_users_yoy?: number | null
  // 新客AUS（Panel B=全店新客AUS, Panel C=会员新客AUS）
  new_aus_2026?: number
  new_aus_2025?: number
  new_aus_yoy?: number | null
  // 老客人数（Panel B=全店老客人数, Panel C=会员老客人数）
  old_users_2026?: number
  old_users_2025?: number
  old_users_yoy?: number | null
  // 老客AUS（Panel B=全店老客AUS, Panel C=会员老客AUS）
  old_aus_2026?: number
  old_aus_2025?: number
  old_aus_yoy?: number | null
  // 会员新增：会员 GSV 占全店 GSV 比例（已有）
  member_ratio_2026?: number
  member_ratio_2025?: number
  member_ratio_yoy?: number | null
  // 会员新增：会员新客 GSV 及占比
  member_new_gsv_2026?: number
  member_new_gsv_2025?: number
  member_new_gsv_yoy?: number | null
  member_new_gsv_ratio_2026?: number
  member_new_gsv_ratio_2025?: number
  member_new_gsv_ratio_yoy?: number | null
  // 会员新增：会员老客 GSV 及占比
  member_old_gsv_2026?: number
  member_old_gsv_2025?: number
  member_old_gsv_yoy?: number | null
  member_old_gsv_ratio_2026?: number
  member_old_gsv_ratio_2025?: number
  member_old_gsv_ratio_yoy?: number | null
  // 交叉指标：会员新客GSV / 全店新客GSV
  member_new_vs_all_new_2026?: number
  member_new_vs_all_new_2025?: number
  member_new_vs_all_new_yoy?: number | null
  // 交叉指标：会员老客GSV / 全店老客GSV
  member_old_vs_all_old_2026?: number
  member_old_vs_all_old_2025?: number
  member_old_vs_all_old_yoy?: number | null
}

export interface AudienceSummary {
  year_label: string
  comp_year_label: string
  prev2_year_label: string
  metric_type: string
  indicators: IndicatorRow[]
  channel_all: ChannelGSVRow[]
  channel_member: ChannelGSVRow[]
}

export function fetchAudienceSummary(params: {
  year?: number
  start_date?: string
  end_date?: string
  channel?: string
  metric_type?: string
  exclude_channels?: string[]
  compare_start_date?: string
  compare_end_date?: string
} = {}): Promise<AudienceSummary> {
  return client.get('/v1/audience/summary', { params })
}

// ============================================================
// 访客入会率 (Visitor Member Join Rate)
// ============================================================

export interface VisitorSummary {
  start_date: string
  end_date: string
  visitors: number
  new_members: number
  member_join_rate: number
  ly_visitors: number
  ly_new_members: number
  ly_member_join_rate: number
  visitors_yoy: number | null
  new_members_yoy: number | null
  member_join_rate_yoy: number | null
  // 环比
  visitors_mom: number | null
  new_members_mom: number | null
  member_join_rate_mom: number | null
}

export interface VisitorDailyTrendItem {
  date: string
  visitors: number
  new_members: number
  member_join_rate: number
  ly_visitors: number
  ly_new_members: number
  ly_member_join_rate: number
}

export interface VisitorDailyTrend {
  start_date: string
  end_date: string
  data: VisitorDailyTrendItem[]
}

export function fetchVisitorSummary(params: {
  start_date: string
  end_date: string
  compare_start_date?: string
  compare_end_date?: string
}): Promise<VisitorSummary> {
  return client.get('/v1/visitor/summary', { params })
}

export function fetchVisitorDailyTrend(params: {
  start_date: string
  end_date: string
  compare_start_date?: string
  compare_end_date?: string
}): Promise<VisitorDailyTrend> {
  return client.get('/v1/visitor/daily-trend', { params })
}
