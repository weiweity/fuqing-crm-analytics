import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import axios, { CanceledError } from 'axios'
import client, { isCredentialAuthRequest } from './index'
import { AUTH_TOKEN_KEY } from '@/stores/auth'

function rejectWith(status: number, detail: string) {
  return async (config: any) => {
    throw {
      config,
      message: detail,
      response: {
        status,
        data: { detail },
        headers: {},
        config,
      },
    }
  }
}

describe('auth error routing', () => {
  beforeEach(() => {
    sessionStorage.clear()
    sessionStorage.setItem(AUTH_TOKEN_KEY, 'stale-token')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('matches only credential endpoints, not pending/approve/status endpoints', () => {
    expect(isCredentialAuthRequest('/v1/auth/login')).toBe(true)
    expect(isCredentialAuthRequest('/v1/auth/login-request')).toBe(true)
    expect(isCredentialAuthRequest('/v1/auth/login-requests/pending')).toBe(false)
    expect(isCredentialAuthRequest('/v1/auth/login-request/abc/approve')).toBe(false)
    expect(isCredentialAuthRequest('/v1/auth/login-request/abc/status')).toBe(false)
    expect(isCredentialAuthRequest('/v1/auth/login-request/abc/claim')).toBe(false)
  })

  it('turns a pending 401 into one global auth-expired event', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false })
    vi.stubGlobal('fetch', fetchMock)
    const expired = vi.fn()
    window.addEventListener('auth:expired', expired)

    try {
      await expect(client.get('/v1/auth/login-requests/pending', {
        adapter: rejectWith(401, '未登录或登录已过期'),
      })).rejects.toMatchObject({ status: 401 })
      expect(fetchMock).toHaveBeenCalledTimes(1)
      expect(expired).toHaveBeenCalledTimes(1)
    } finally {
      window.removeEventListener('auth:expired', expired)
    }
  })

  it('preserves the top-level status/data contract for credential failures', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const expired = vi.fn()
    window.addEventListener('auth:expired', expired)

    try {
      await expect(client.post('/v1/auth/login', {}, {
        adapter: rejectWith(401, '账号或密码错误'),
      })).rejects.toMatchObject({
        status: 401,
        data: { detail: '账号或密码错误' },
      })
      expect(fetchMock).not.toHaveBeenCalled()
      expect(expired).not.toHaveBeenCalled()
    } finally {
      window.removeEventListener('auth:expired', expired)
    }
  })
})

// === Codex Stage 3 review [P2-1]: Axios CanceledError pass-through ===
describe('axios CanceledError pass-through (per [P2-1])', () => {
  const originalAdapter = client.defaults.adapter

  afterEach(() => {
    client.defaults.adapter = originalAdapter
  })

  it('rejected CanceledError is NOT wrapped, axios.isCancel(err) === true, no auth:expired', async () => {
    // 替换 client.adapter: 所有请求 reject 一个 CanceledError (axios v1 signal.abort() 触发)
    client.defaults.adapter = vi.fn(() =>
      Promise.reject(new CanceledError('test canceled', undefined, undefined as any)),
    )
    const expired = vi.fn()
    window.addEventListener('auth:expired', expired)

    let caught: unknown
    try {
      await client.get('/v1/admin/upload-config')
    } catch (err) {
      caught = err
    }

    expect(caught).toBeDefined()
    expect(axios.isCancel(caught)).toBe(true)
    // 不能被 toApiError 包装 (包装后会变成普通 Error, name != 'CanceledError', code != 'ERR_CANCELED')
    expect((caught as any).name).toBe('CanceledError')
    expect((caught as any).code).toBe('ERR_CANCELED')

    // 不能走 401 流程触发 auth:expired
    expect(expired).not.toHaveBeenCalled()

    window.removeEventListener('auth:expired', expired)
  })

  it('non-cancel error is still wrapped by toApiError (control test)', async () => {
    // 控制组: 非 cancel error 应该被 toApiError 包装
    // 证明 interceptor 只豁免 CanceledError, 不影响其他错误
    client.defaults.adapter = vi.fn(() =>
      Promise.reject({
        config: { url: '/v1/admin/upload-config' },
        message: 'Network Error',
        response: undefined,
      }),
    )

    let caught: unknown
    try {
      await client.get('/v1/admin/upload-config')
    } catch (err) {
      caught = err
    }

    expect(axios.isCancel(caught)).toBe(false)
    // 被包装成 ApiError (status undefined 表示非 401 网络错误, 走 toApiError fallback)
    expect((caught as any).message).toBe('Network Error')
  })
})
