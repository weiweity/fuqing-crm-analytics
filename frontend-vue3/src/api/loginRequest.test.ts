import { beforeEach, describe, expect, it, vi } from 'vitest'

const client = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))

vi.mock('./index', () => ({ default: client }))

import {
  claimLoginRequest,
  getLoginRequestStatus,
  loginRequest,
} from './loginRequest'


describe('login request claim contract', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('keeps the claim secret out of the status URL', async () => {
    const controller = new AbortController()
    client.get.mockResolvedValue({ status: 'pending' })

    await getLoginRequestStatus('request-1', 'claim-secret', controller.signal)

    expect(client.get).toHaveBeenCalledWith(
      '/v1/auth/login-request/request-1/status',
      {
        headers: { 'X-Login-Claim': 'claim-secret' },
        signal: controller.signal,
      },
    )
  })

  it('claims through an idempotent POST with the secret header', async () => {
    client.post.mockResolvedValue({ token: 'session-token', username: 'admin' })

    await claimLoginRequest('request-1', 'claim-secret')

    expect(client.post).toHaveBeenCalledWith(
      '/v1/auth/login-request/request-1/claim',
      undefined,
      {
        headers: { 'X-Login-Claim': 'claim-secret' },
        signal: undefined,
      },
    )
  })

  it('passes cancellation to request creation', async () => {
    const controller = new AbortController()
    client.post.mockResolvedValue({ request_id: 'request-1', claim_token: 'claim-secret' })

    await loginRequest('admin', 'password', controller.signal)

    expect(client.post).toHaveBeenCalledWith(
      '/v1/auth/login-request',
      { username: 'admin', password: 'password' },
      { signal: controller.signal },
    )
  })
})
