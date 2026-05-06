import client from './index'

export interface GeoDistributionParams {
  date: string
  lookback_days?: number
  level?: string
  top_n?: number
  segment_id?: number
}

export interface GeoDistributionItem {
  name: string
  user_count: number
  gmv: number
  // 后端返回的 "占比" 字段 = user_count / total_users * 100（百分比，非小数）
  gmv_ratio: number
  user_ratio: number
}

export interface GeoDistributionResponse {
  date: string
  level: string
  total_users: number
  total_gmv: number
  distribution: GeoDistributionItem[]
}

export interface GeoSegmentMatrixResponse {
  date: string
  matrix: Record<string, { province: string; user_count: number; gmv: number }[]>
  // color 来自后端 user_rfm 表的 segment_hex 字段
  segments: { id: number; name: string; color: string }[]
}

export interface GeoTrendResponse {
  time_points: string[]
  top_provinces: string[]
  trends: Record<string, number[]>
}

export function fetchGeoDistribution(params: GeoDistributionParams & { exclude_channels?: string[] }): Promise<GeoDistributionResponse> {
  return client.get('/v1/geo/distribution', { params })
}

export function fetchGeoSegmentMatrix(params: Omit<GeoDistributionParams, 'level' | 'top_n' | 'segment_id'> & { top_n?: number; exclude_channels?: string[] }): Promise<GeoSegmentMatrixResponse> {
  return client.get('/v1/geo/segment', { params })
}

export function fetchGeoTrend(params: { start_date: string; end_date: string; lookback_days?: number; top_n?: number; exclude_channels?: string[] }): Promise<GeoTrendResponse> {
  return client.get('/v1/geo/trend', { params })
}
