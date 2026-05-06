import client from './index'

export interface ChurnDistributionParams {
  date: string
  segment_id?: number
  churn_mode?: 'dynamic' | 'fixed'
  fixed_threshold?: number
}

export interface ChurnDistributionResponse {
  date: string
  churn_mode: string
  total_users: number
  high_risk: number
  medium_risk: number
  low_risk: number
  high_risk_rate: number
  by_segment: Record<string, { total: number; high_risk: number; medium_risk: number; low_risk: number }>
}

export interface ChurnUser {
  user_id: string
  nickname?: string
  last_order_date?: string
  total_orders: number
  total_gmv: number
  avg_order_value: number
  segment_name: string
  days_since_last_order: number
  risk_level: string
}

export interface ChurnUsersResponse {
  date: string
  mode: string
  total_matched: number
  users: ChurnUser[]
}

export function fetchChurnDistribution(params: ChurnDistributionParams & { exclude_channels?: string[] }): Promise<ChurnDistributionResponse> {
  return client.get('/v1/churn/distribution', { params })
}

export function fetchChurnRiskUsers(params: ChurnDistributionParams & { risk_level?: string; limit?: number; exclude_channels?: string[] }): Promise<ChurnUsersResponse> {
  return client.get('/v1/churn/risk', { params })
}
