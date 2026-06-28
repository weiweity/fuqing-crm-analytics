import client from './index'
import type { RfmVersionInfo } from '@/types/rfm'

/**
 * 获取当前 active RFM manifest 信息
 *
 * 后端: GET /api/v1/rfm/version → {active_view, version, ts, path}
 * 后端实现: backend/routers/rfm.py:get_rfm_manifest_version (W2 v0.4.8)
 * 数据源: backend/services/rfm/loader.py:get_rfm_manifest_info
 *
 * 用途: RFM Version Banner 顶栏展示 + ETL 切批后调试
 */
export function fetchRfmManifestVersion(): Promise<RfmVersionInfo> {
  return client.get('/v1/rfm/version')
}

export type LifecycleStage = '新客' | '活跃客' | '沉睡客' | '流失客'
export type ValueTier = '高价值' | '中价值' | '低价值'
export type PotentialTier = '高潜力' | '中潜力' | '低潜力'

export interface RFMSegmentExtended {
  user_id: string
  rfm_quadrant: string
  lifecycle_stage: LifecycleStage
  value_tier: ValueTier
  potential_tier: PotentialTier
}

export function fetchUserRFMExtended(params: {
  user_ids: string[]
  as_of_date?: string
}): Promise<{ segments: RFMSegmentExtended[] }> {
  return client.post('/v1/rfm/extended', params)
}
