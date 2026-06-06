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
