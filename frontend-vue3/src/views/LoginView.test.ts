import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  claimLoginRequest: vi.fn(),
  getLoginRequestStatus: vi.fn(),
  loginRequest: vi.fn(),
  replace: vi.fn(),
  setSession: vi.fn(),
}))

vi.mock('@/api/loginRequest', () => ({
  claimLoginRequest: mocks.claimLoginRequest,
  getLoginRequestStatus: mocks.getLoginRequestStatus,
  loginRequest: mocks.loginRequest,
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    isLoading: false,
    login: vi.fn(),
    setSession: mocks.setSession,
  }),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: mocks.replace }),
}))

vi.mock('@rive-app/canvas', () => ({
  default: class MockRive {
    cleanup() {}
  },
}))

import LoginView from './LoginView.vue'


describe('LoginView request polling lifecycle', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    mocks.loginRequest.mockResolvedValue({
      request_id: 'request-1',
      claim_token: 'claim-1',
      status: 'pending',
      message: '等待批准',
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('does not revive polling or claim a session after unmount', async () => {
    let resolveStatus!: (value: { status: 'approved'; username: string }) => void
    mocks.getLoginRequestStatus.mockReturnValue(new Promise((resolve) => {
      resolveStatus = resolve
    }))

    const wrapper = mount(LoginView)
    await wrapper.get('input[type="text"]').setValue('admin')
    await wrapper.get('input[type="password"]').setValue('123456')
    await wrapper.get('.btn-apply').trigger('click')
    await flushPromises()

    await vi.advanceTimersByTimeAsync(5000)
    expect(mocks.getLoginRequestStatus).toHaveBeenCalledTimes(1)
    wrapper.unmount()

    resolveStatus({ status: 'approved', username: 'admin' })
    await flushPromises()

    expect(mocks.claimLoginRequest).not.toHaveBeenCalled()
    expect(mocks.setSession).not.toHaveBeenCalled()
    expect(mocks.replace).not.toHaveBeenCalled()
    expect(vi.getTimerCount()).toBe(0)
  })
})
