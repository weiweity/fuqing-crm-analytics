import client from './index'

export interface CategoryDistributionParams {
  date: string
  lookback_days?: number
  level?: string
  segment_id?: number
  channel?: string
}

export interface CategoryDistributionItem {
  name: string
  user_count: number
  member_count: number
  gmv: number
  member_gsv: number
  pct: number
  penetration_rate: number
  member_ratio: number
}

export interface CategoryDistributionResponse {
  date: string
  level: string
  total_users: number
  total_members: number
  total_gmv: number
  distribution: CategoryDistributionItem[]
}

export interface CategoryOverviewItem {
  name: string
  gsv: number
  gsv_yoy: number | null
  users: number
  users_yoy: number | null
  aus: number
  aus_yoy: number | null
  old_gsv: number
  old_gsv_yoy: number | null
  old_ratio: number
  old_ratio_yoy: number | null
  old_users: number
  old_users_yoy: number | null
  old_aus: number
  old_aus_yoy: number | null
  new_gsv: number
  new_gsv_yoy: number | null
  new_ratio: number
  new_ratio_yoy: number | null
  new_users: number
  new_users_yoy: number | null
  new_aus: number
  new_aus_yoy: number | null
  old_users_ratio?: number | null
  old_users_ratio_yoy?: number | null
  new_users_ratio?: number | null
  new_users_ratio_yoy?: number | null
  member_ratio?: number | null
  member_ratio_yoy?: number | null
}

export interface CategoryOverviewResponse {
  date_start: string
  date_end: string
  level: string
  channel: string | null
  metric_type: string
  all_rows: CategoryOverviewItem[]
  member_rows: CategoryOverviewItem[]
  all_ttl: CategoryOverviewItem
  member_ttl: CategoryOverviewItem
}

export interface CategorySegmentMatrixResponse {
  date: string
  level: string
  matrix: Record<string, { category: string; user_count: number; gmv: number }[]>
  segments: { id: number; name: string; en?: string; color?: string }[]
}

export interface CategoryUserProfileResponse {
  date: string
  category: string
  type?: string
  total_users: number
  total_gmv: number
  avg_order_value: number
  avg_frequency: number
  segment_distribution: { segment_id: number; name: string; user_count: number; ratio: number }[]
  province_distribution: { province: string; user_count: number }[]
  channel_distribution: { channel: string; user_count: number }[]
}

export function fetchCategoryDistribution(params: CategoryDistributionParams & { exclude_channels?: string[] }): Promise<CategoryDistributionResponse> {
  return client.get('/v1/category/distribution', { params })
}

export function fetchCategoryOverview(params: {
  start_date: string
  end_date: string
  level?: string
  metric_type?: string
  channel?: string
  exclude_channels?: string[]
  compare_start_date?: string
  compare_end_date?: string
}): Promise<CategoryOverviewResponse> {
  return client.get('/v1/category/overview', { params })
}

export function fetchCategorySegmentMatrix(params: Omit<CategoryDistributionParams, 'segment_id'> & { top_n?: number; exclude_channels?: string[] }): Promise<CategorySegmentMatrixResponse> {
  return client.get('/v1/category/segment', { params })
}

export function fetchCategoryUserProfile(params: { date: string; lookback_days?: number; category: string; type?: string }): Promise<CategoryUserProfileResponse> {
  return client.get('/v1/category/user-profile', { params })
}

// ============================================================
// ValueTierTab
// ============================================================

export interface WoolPartyBreakdown {
  type1_count: number  // 历史有正装，后续一直买小样
  type2_count: number  // 历史只买小样
  total_count: number
  type1_ratio: number
  type2_ratio: number
}

export interface DualAxisLineData {
  categories: string[]
  wool_party_ratios: number[]
  high_value_ratios: number[]
}

export interface ValueTierTableRow {
  category_name: string
  total_users: number
  high_value_users: number
  high_value_ratio: number
  wool_party: WoolPartyBreakdown
  member_ratio: number
  avg_aus: number
  value_score: number
  value_grade: string
}

export interface CategoryValueTierResponse {
  dual_axis_line: DualAxisLineData
  table: ValueTierTableRow[]
  operation_suggestions: string[]
  data_quality_note: string
  wool_party_by_window?: Record<string, ValueTierTableRow[]>
}

export function fetchCategoryValueTier(params: {
  start_date: string
  end_date: string
  level?: string
  channel?: string
  exclude_channels?: string[]
}): Promise<CategoryValueTierResponse> {
  return client.get('/v1/category/value-tier', { params })
}

// ============================================================
// CategoryFlowTab
// ============================================================

export interface SankeyNode {
  name: string
  category_name: string
}

export interface SankeyLink {
  source: string
  target: string
  value: number
}

export interface SankeyGraphData {
  nodes: SankeyNode[]
  links: SankeyLink[]
}

export interface FlowMatrix {
  sources: string[]
  targets: string[]
  matrix: number[][]
  concentration_warnings: string[]
}

export interface AssociationItem {
  category_name: string
  user_count: number
  order_count: number
  gsv: number
  ratio: number
  avg_days_gap: number
}

export interface CategoryFlowResponse {
  sankey_data: SankeyGraphData
  matrix: FlowMatrix
  data_stale: boolean
  data_quality_note: string
  target_category?: string
  post_purchase?: AssociationItem[]
  pre_purchase?: AssociationItem[]
}

export function fetchCategoryFlow(params: {
  start_date: string
  end_date: string
  level?: string
  top_n?: number
  window_days?: number
  channel?: string
  exclude_channels?: string[]
  target_category?: string
}): Promise<CategoryFlowResponse> {
  return client.get('/v1/category/flow', { params })
}

// ============================================================
// MarketBasketTab
// ============================================================

export interface MarketBasketItem {
  category_name: string
  co_order_count: number
  support: number
  confidence: number
  lift: number
  target_order_count: number
  co_gsv: number                // 连带订单GSV
  co_aus: number                // 连带人均消费(AUS)
  target_aus: number            // 目标品类人均消费(AUS baseline)
  gsv_lift: number              // 消费提升倍数
}

export interface MarketBasketYoYItem {
  category_name: string
  current: MarketBasketItem
  previous?: MarketBasketItem
  confidence_change?: number
  lift_change?: number
  rank_change?: number
  gsv_change?: number           // 连带GSV同比变化
}

export interface MarketBasketResponse {
  target_category: string
  total_orders: number
  target_order_count: number
  period_label: string
  yoy_period_label?: string
  items: MarketBasketYoYItem[]
  data_quality_note: string
}

export function fetchMarketBasket(params: {
  start_date: string
  end_date: string
  target_category: string
  level?: string
  channel?: string
  exclude_channels?: string[]
}): Promise<MarketBasketResponse> {
  return client.get('/v1/category/basket', { params })
}

// ============================================================
// ChurnWarningTab
// ============================================================

export interface ChurnScatterPoint {
  category_name: string
  current_users: number
  mom_change_rate: number
  churn_users: number
  inter_churn: number
  silent_churn: number
}

export interface ChurnBarData {
  category_name: string
  current_users: number
  previous_users: number
  mom_change_rate: number
}

export interface ChurnTableRow {
  category_name: string
  current_users: number
  previous_users: number
  mom_change_rate: number
  inter_churn: number
  silent_churn: number
  top_churn_dest1: string
  top_churn_dest1_ratio: number
  top_churn_dest2: string
  top_churn_dest2_ratio: number
  挽回建议: string
}

export interface CategoryChurnResponse {
  scatter_data: ChurnScatterPoint[]
  bar_data: ChurnBarData[]
  table: ChurnTableRow[]
  operation_suggestions: string[]
  data_quality_note: string
}

export function fetchCategoryChurn(params: {
  start_date: string
  end_date: string
  level?: string
  channel?: string
  exclude_channels?: string[]
}): Promise<CategoryChurnResponse> {
  return client.get('/v1/category/churn', { params })
}

// ============================================================
// CategoryRepurchaseTab (品类回购分析)
// ============================================================

export interface CategoryRepurchaseFlowRow {
  r_segment: string
  hist_users_current: number
  repurchase_users_current: number
  repurchase_rate_current: number
  repurchase_gsv_current: number
  repurchase_gsv_ratio_current: number
  hist_users_comp: number
  repurchase_rate_comp: number
  hist_users_prev2: number
  repurchase_rate_prev2: number
  yoy_hist_users: number | null
  yoy_repurchase_users: number | null
  yoy_repurchase_rate: number | null
  yoy_repurchase_gsv: number | null
  yoy_repurchase_gsv_ratio: number | null
}

export interface CategoryRepurchaseFlowResponse {
  year_label: string
  comp_year_label: string
  prev2_year_label: string
  target_category: string
  same_category_rows: CategoryRepurchaseFlowRow[]
  cross_category_rows: CategoryRepurchaseFlowRow[]
  member_same_category_rows: CategoryRepurchaseFlowRow[]
  member_cross_category_rows: CategoryRepurchaseFlowRow[]
}

export function fetchCategoryRepurchaseFlow(params: {
  start_date: string
  end_date: string
  category: string
  level?: string
  metric_type?: string
  channel?: string
  exclude_channels?: string[]
}): Promise<CategoryRepurchaseFlowResponse> {
  return client.get('/v1/category/repurchase-flow', { params })
}

// ============================================================
// 详情页 API
// ============================================================

export interface CategoryDailyTrendResponse {
  category_id: string
  category_name: string
  granularity: string
  dates: string[]
  gmv: number[]
  user_count: number[]
  aus: number[]
  new_customer_ratio: number[]
}

export interface UserDetail {
  user_id: string
  nickname: string
  order_count: number
  total_gmv: number
  first_order_date: string
  last_order_date: string
  segment_id: number
  segment_name: string
  is_member: boolean
  is_wool_party: boolean
}

export interface CategoryUserListResponse {
  category_id: string
  category_name: string
  total_users: number
  users: UserDetail[]
}

export function fetchCategoryDailyTrend(params: {
  category_id: string
  category_name: string
  start_date: string
  end_date: string
  granularity?: string
}): Promise<CategoryDailyTrendResponse> {
  return client.get('/v1/category/detail/daily-trend', { params })
}

export function fetchCategoryUserList(params: {
  category_id: string
  category_name: string
  start_date: string
  end_date: string
  limit?: number
}): Promise<CategoryUserListResponse> {
  return client.get('/v1/category/detail/user-list', { params })
}

// ============================================================
// NewcomerInsightTab
// ============================================================

export interface NewcomerBarItem {
  category_name: string
  new_user_count: number
  new_gmv: number
}

export interface ChordData {
  nodes: string[]
  links: { source: string; target: string; value: number }[]
  source_nodes?: string[]
  target_nodes?: string[]
}

export interface NewcomerTableRow {
  category_name: string
  new_user_count: number
  new_gmv: number
  intra_repurchase_rate: number
  cross_repurchase_rate: number
  top_repurchase_category: string | null
  old_user_ratio: number
  old_aus: number | null
}

export interface CategoryNewcomerInsightResponse {
  bars: NewcomerBarItem[]
  chord_data: ChordData
  table: NewcomerTableRow[]
  operation_suggestions: string[]
  data_quality_note?: string
}

export function fetchCategoryNewcomerInsight(params: {
  start_date: string
  end_date: string
  level?: string
  channel?: string
  exclude_channels?: string[]
}): Promise<CategoryNewcomerInsightResponse> {
  return client.get('/v1/category/newcomer-insight', { params })
}
