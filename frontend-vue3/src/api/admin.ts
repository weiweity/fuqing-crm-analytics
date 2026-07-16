/**
 * Sprint 3A: admin upload API client.
 *
 * 仅覆盖 staging-only 范围（per Codex Sprint 3A 审计 prompt §十五 + §十六）：
 * - getUploadConfig()      GET  /v1/admin/upload-config
 * - uploadAdminFile()      POST /v1/admin/upload （multipart + Idempotency-Key + 5 min timeout + progress）
 * - getUploads()           GET  /v1/admin/uploads
 * - getAdminErrorMessage() 错误 helper（不产生 [object Object]）
 * - getAdminErrorCode()    错误 code 提取
 *
 * Sprint 2 才落地的接口（etl-runs / stale-warning / maintenance）**不在**本文件。
 */
import client from './index'
import type { ApiError } from './index'
import type { components } from './types'

// === 类型 re-export（不重复手写契约，跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用） ===
export type UploadConfigResponse = components['schemas']['UploadConfigResponse']
export type UploadSourcePublic = components['schemas']['UploadSourcePublic']
export type UploadResponse = components['schemas']['UploadResponse']
export type UploadListResponse = components['schemas']['UploadListResponse']
export type UploadRecordOut = components['schemas']['UploadRecordOut']

// === 常量 ===
/** 全局 axios timeout 是 30s；100MB 上传需要更长。仅 uploadAdminFile 覆盖，不动全局（per prompt §15.4）。 */
export const ADMIN_UPLOAD_TIMEOUT_MS = 5 * 60_000

// === API ===

/**
 * GET /v1/admin/upload-config
 * 服务端返回 10 种数据源 + max_upload_bytes 全局硬上限。
 */
export function getUploadConfig(signal?: AbortSignal): Promise<UploadConfigResponse> {
  return client.get<UploadConfigResponse>('/v1/admin/upload-config', { signal }) as unknown as Promise<UploadConfigResponse>
}

export interface UploadAdminFileParams {
  businessType: string
  file: File
  idempotencyKey: string
  signal?: AbortSignal
  onProgress?: (loaded: number, total: number, percent: number) => void
}

/**
 * POST /v1/admin/upload
 *
 * 重要约束（per prompt §15.3 + §15.4 + §15.5 + Comment 7）：
 * - FormData 字段名：business_type / file（后端 contract 用 snake_case）
 * - Header: Idempotency-Key
 * - **禁止**手工设 Content-Type（浏览器必须自己生成 multipart boundary）
 * - 仅本调用覆盖 timeout=5min，不动全局 axios
 * - progress 通过 onUploadProgress 回调；percent clamp 0-100；total 缺失回退 file.size
 */
export function uploadAdminFile(params: UploadAdminFileParams): Promise<UploadResponse> {
  const { businessType, file, idempotencyKey, signal, onProgress } = params

  const formData = new FormData()
  formData.append('business_type', businessType)
  formData.append('file', file, file.name)

  return client.post<UploadResponse>('/v1/admin/upload', formData, {
    signal,
    timeout: ADMIN_UPLOAD_TIMEOUT_MS,
    headers: {
      'Idempotency-Key': idempotencyKey,
    },
    onUploadProgress: (evt) => {
      if (!onProgress) return
      const loaded = evt.loaded ?? 0
      // Axios v1 typing: total 可能是 undefined（服务器未发 Content-Length）。
      // 回退到 file.size（prompt §15.5）。
      const total = typeof evt.total === 'number' && evt.total > 0 ? evt.total : file.size
      const rawPercent = total > 0 ? (loaded / total) * 100 : 0
      const percent = Math.max(0, Math.min(100, Math.round(rawPercent)))
      onProgress(loaded, total, percent)
    },
  }) as unknown as Promise<UploadResponse>
}

export interface GetUploadsParams {
  business_type?: string
  status?: string
  limit?: number
  offset?: number
  signal?: AbortSignal
}

/**
 * GET /v1/admin/uploads
 *
 * 重要约束（per prompt §15.6）：
 * - **不**发送值为 undefined 的参数（axios.paramsSerializer 已过滤 null，但显式过滤更稳）
 * - limit/offset 透传
 */
export function getUploads(params: GetUploadsParams = {}): Promise<UploadListResponse> {
  const query: Record<string, string | number> = {}
  if (params.business_type !== undefined) query.business_type = params.business_type
  if (params.status !== undefined) query.status = params.status
  if (params.limit !== undefined) query.limit = params.limit
  if (params.offset !== undefined) query.offset = params.offset

  return client.get<UploadListResponse>('/v1/admin/uploads', {
    params: query,
    signal: params.signal,
  }) as unknown as Promise<UploadListResponse>
}

// === 错误 helper（per prompt §15.7） ===

/**
 * 后端 admin 错误形态：
 * {
 *   "detail": {
 *     "code": "VALIDATION_FAILED",
 *     "message": "缺少必填列: 淘宝父订单编号"
 *   }
 * }
 *
 * 全局 ApiError.toString() 可能把 detail 对象显示成 "[object Object]"。
 * 本 helper 提取优先级：detail.message > error.message (排除 [object Object]) > fallback。
 */
export function getAdminErrorMessage(error: unknown, fallback = '请求失败'): string {
  const apiErr = error as ApiError | undefined
  const detail = apiErr?.data as { detail?: unknown } | undefined

  // 1) 提取嵌套 detail.message
  if (detail && typeof detail === 'object') {
    const d = detail.detail
    if (d && typeof d === 'object') {
      const msg = (d as { message?: unknown }).message
      if (typeof msg === 'string' && msg.length > 0) return msg
    }
    // detail 也可能直接是字符串
    if (typeof d === 'string' && d.length > 0) return d
  }

  // 2) error.message，排除 "[object Object]"
  const msg = apiErr?.message
  if (typeof msg === 'string' && msg.length > 0 && msg !== '[object Object]') {
    return msg
  }

  // 3) fallback
  return fallback
}

/** 提取后端 detail.code，没有则 undefined。 */
export function getAdminErrorCode(error: unknown): string | undefined {
  const apiErr = error as ApiError | undefined
  const detail = apiErr?.data as { detail?: unknown } | undefined

  if (detail && typeof detail === 'object') {
    const d = detail.detail
    if (d && typeof d === 'object') {
      const code = (d as { code?: unknown }).code
      if (typeof code === 'string' && code.length > 0) return code
    }
  }
  return undefined
}