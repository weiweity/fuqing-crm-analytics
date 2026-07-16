/**
 * Sprint 3A Phase C: admin API client tests.
 *
 * 覆盖 (per prompt §十八 case 9-10 + §十五 + Comment 7):
 * - FormData 字段 (business_type + file)
 * - Idempotency-Key header
 * - 5 分钟 timeout 覆盖 (不改全局)
 * - onUploadProgress 计算 + clamp + total fallback
 * - getUploads 不发 undefined 参数
 * - getAdminErrorMessage 提取嵌套 detail.message 不产生 [object Object]
 * - getAdminErrorCode 提取 code
 * - AbortSignal 透传
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

const clientMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}))

vi.mock('./index', () => ({
  default: clientMock,
}))

import {
  ADMIN_UPLOAD_TIMEOUT_MS,
  getAdminErrorCode,
  getAdminErrorMessage,
  getUploadConfig,
  getUploads,
  uploadAdminFile,
} from './admin'

function makeFile(name: string, size: number, type = 'text/csv'): File {
  // 用 Uint8Array 构造指定 size，避免 jsdom 真实分配大内存
  const arr = new Uint8Array(size)
  return new File([arr], name, { type })
}

describe('admin API getUploadConfig', () => {
  beforeEach(() => {
    clientMock.get.mockReset()
  })

  it('calls GET /v1/admin/upload-config without AbortSignal', async () => {
    const cfg = {
      sources: [],
      max_upload_bytes: 100 * 1024 * 1024,
    } as any
    clientMock.get.mockResolvedValueOnce(cfg)
    const result = await getUploadConfig()
    expect(clientMock.get).toHaveBeenCalledWith('/v1/admin/upload-config', { signal: undefined })
    expect(result).toBe(cfg)
  })

  it('forwards AbortSignal to axios', async () => {
    clientMock.get.mockResolvedValueOnce({ sources: [], max_upload_bytes: 1 })
    const ac = new AbortController()
    await getUploadConfig(ac.signal)
    expect(clientMock.get).toHaveBeenCalledWith('/v1/admin/upload-config', { signal: ac.signal })
  })
})

describe('admin API uploadAdminFile', () => {
  beforeEach(() => {
    clientMock.post.mockReset()
  })

  it('appends business_type and file fields to FormData, sets Idempotency-Key header, overrides timeout', async () => {
    const file = makeFile('taoke.csv', 1024)
    const uploadResp = { upload: { upload_id: 'u1' }, duplicate: false } as any
    clientMock.post.mockResolvedValueOnce(uploadResp)

    const result = await uploadAdminFile({
      businessType: 'taoke',
      file,
      idempotencyKey: 'idem-123',
    })

    expect(clientMock.post).toHaveBeenCalledTimes(1)
    const [url, formData, config] = clientMock.post.mock.calls[0]
    expect(url).toBe('/v1/admin/upload')

    // FormData 字段验证
    expect(formData).toBeInstanceOf(FormData)
    expect(formData.get('business_type')).toBe('taoke')
    const appendedFile = formData.get('file') as File
    expect(appendedFile).toBeInstanceOf(File)
    expect(appendedFile.name).toBe('taoke.csv')
    expect(appendedFile.size).toBe(1024)

    // Header + timeout
    expect(config.headers['Idempotency-Key']).toBe('idem-123')
    expect(config.timeout).toBe(ADMIN_UPLOAD_TIMEOUT_MS)
    expect(ADMIN_UPLOAD_TIMEOUT_MS).toBe(5 * 60_000)

    // 禁止手工设 Content-Type
    expect(config.headers['Content-Type']).toBeUndefined()

    expect(result).toBe(uploadResp)
  })

  it('maps onUploadProgress to percent clamped 0-100 with total fallback to file.size', async () => {
    const file = makeFile('shop.xlsx', 2000)
    const onProgress = vi.fn()

    let capturedOnProgress: ((evt: any) => void) | undefined
    clientMock.post.mockImplementationOnce((_url: string, _body: any, config: any) => {
      capturedOnProgress = config.onUploadProgress
      return Promise.resolve({ upload: {}, duplicate: false })
    })

    await uploadAdminFile({ businessType: 'shop', file, idempotencyKey: 'k1', onProgress })

    expect(capturedOnProgress).toBeDefined()
    const cb = capturedOnProgress!

    // total 正常
    cb({ loaded: 500, total: 1000 })
    expect(onProgress).toHaveBeenLastCalledWith(500, 1000, 50)

    cb({ loaded: 1000, total: 1000 })
    expect(onProgress).toHaveBeenLastCalledWith(1000, 1000, 100)

    // total 缺失 → 回退 file.size
    cb({ loaded: 500, total: undefined })
    expect(onProgress).toHaveBeenLastCalledWith(500, 2000, 25)

    // loaded > total → clamp 100
    cb({ loaded: 2000, total: 1000 })
    expect(onProgress).toHaveBeenLastCalledWith(2000, 1000, 100)

    // loaded 为负 → clamp 0
    cb({ loaded: -10, total: 1000 })
    expect(onProgress).toHaveBeenLastCalledWith(-10, 1000, 0)
  })

  it('forwards AbortSignal to upload request', async () => {
    clientMock.post.mockResolvedValueOnce({ upload: {}, duplicate: false })
    const ac = new AbortController()
    const file = makeFile('x.csv', 10)
    await uploadAdminFile({ businessType: 'taoke', file, idempotencyKey: 'k', signal: ac.signal })
    const [, , config] = clientMock.post.mock.calls[0]
    expect(config.signal).toBe(ac.signal)
  })
})

describe('admin API getUploads', () => {
  beforeEach(() => {
    clientMock.get.mockReset()
  })

  it('calls GET /v1/admin/uploads with all 4 params', async () => {
    clientMock.get.mockResolvedValueOnce({ items: [], total: 0, limit: 20, offset: 0 })
    await getUploads({ business_type: 'taoke', status: 'staged', limit: 20, offset: 40 })
    expect(clientMock.get).toHaveBeenCalledWith(
      '/v1/admin/uploads',
      expect.objectContaining({
        params: { business_type: 'taoke', status: 'staged', limit: 20, offset: 40 },
      }),
    )
  })

  it('does not send undefined params (per prompt §15.6)', async () => {
    clientMock.get.mockResolvedValueOnce({ items: [], total: 0, limit: 20, offset: 0 })
    await getUploads({ business_type: undefined, status: undefined, limit: 20, offset: 0 })
    const [, config] = clientMock.get.mock.calls[0]
    expect(config.params).not.toHaveProperty('business_type')
    expect(config.params).not.toHaveProperty('status')
    expect(config.params.limit).toBe(20)
    expect(config.params.offset).toBe(0)
  })

  it('handles empty params (no params key)', async () => {
    clientMock.get.mockResolvedValueOnce({ items: [], total: 0, limit: 20, offset: 0 })
    await getUploads()
    const [, config] = clientMock.get.mock.calls[0]
    expect(config.params).toEqual({})
  })

  it('forwards AbortSignal', async () => {
    clientMock.get.mockResolvedValueOnce({ items: [], total: 0, limit: 20, offset: 0 })
    const ac = new AbortController()
    await getUploads({ signal: ac.signal })
    const [, config] = clientMock.get.mock.calls[0]
    expect(config.signal).toBe(ac.signal)
  })
})

describe('admin API getAdminErrorMessage', () => {
  it('extracts nested detail.message (Pydantic-style error)', () => {
    const err = {
      status: 422,
      data: { detail: { code: 'VALIDATION_FAILED', message: '缺少必填列: 淘宝父订单编号' } },
      message: '[object Object]',
    }
    expect(getAdminErrorMessage(err)).toBe('缺少必填列: 淘宝父订单编号')
  })

  it('falls back to plain string detail.message when not nested', () => {
    const err = {
      status: 400,
      data: { detail: 'plain message' },
      message: 'Request failed with status code 400',
    }
    expect(getAdminErrorMessage(err)).toBe('plain message')
  })

  it('does NOT produce "[object Object]"', () => {
    const err = {
      status: 500,
      data: { detail: { code: 'INTERNAL', message: 'registry write failed' } },
      message: '[object Object]',
    }
    const result = getAdminErrorMessage(err)
    expect(result).not.toBe('[object Object]')
    expect(result).toBe('registry write failed')
  })

  it('falls back to error.message when detail is missing', () => {
    const err = { message: 'Network Error' }
    expect(getAdminErrorMessage(err)).toBe('Network Error')
  })

  it('returns fallback when nothing usable exists', () => {
    expect(getAdminErrorMessage({}, '默认错误')).toBe('默认错误')
    expect(getAdminErrorMessage({ message: '[object Object]' }, '兜底文案')).toBe('兜底文案')
  })

  it('accepts custom fallback parameter', () => {
    expect(getAdminErrorMessage({}, '上传失败，请稍后重试')).toBe('上传失败，请稍后重试')
  })
})

describe('admin API getAdminErrorCode', () => {
  it('extracts nested detail.code', () => {
    const err = {
      data: { detail: { code: 'VALIDATION_FAILED', message: 'x' } },
    }
    expect(getAdminErrorCode(err)).toBe('VALIDATION_FAILED')
  })

  it('returns undefined when code missing', () => {
    expect(getAdminErrorCode({ data: { detail: { message: 'x' } } })).toBeUndefined()
    expect(getAdminErrorCode({})).toBeUndefined()
  })
})