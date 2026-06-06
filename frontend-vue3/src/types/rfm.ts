/**
 * RFM 相关类型定义
 *
 * - RfmVersionInfo: GET /api/v1/rfm/version 的响应
 *   用于 RFM Version Banner 组件展示当前 active manifest 信息,
 *   方便 PM / 分析师一眼确认"看到的是哪一批数据"。
 *
 * 字段来源: backend.services.rfm.loader.get_rfm_manifest_info
 * 暴露端点: backend.routers.rfm.get_rfm_manifest_version (W2 v0.4.8)
 */

export interface RfmVersionInfo {
  /** 当前 active view 名称,例如 "rfm_8_segments" / "rfm_default"。
   *  空字符串表示 ETL 还没跑过 (后端监控告警触发条件)。 */
  active_view: string
  /** manifest 版本号,整数,每次切 batch 递增 */
  version: number
  /** manifest 写入时间 (ISO 8601 字符串,例如 "2026-06-06T03:12:44Z") */
  ts: string
  /** manifest 文件绝对路径,鼠标悬停时完整展示 */
  path: string
}
