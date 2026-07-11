import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
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
