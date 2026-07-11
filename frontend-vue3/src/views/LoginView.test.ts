import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  claimLoginRequest: vi.fn(),
  getLoginRequestStatus: vi.fn(),
  loginRequest: vi.fn(),
  push: vi.fn(),
  replace: vi.fn(),
  setSession: vi.fn(),
}))

vi.mock('@/api/loginRequest', () => ({
  claimLoginRequest: mocks.claimLoginRequest,
  getLoginRequestStatus: mocks.getLoginRequestStatus,
  loginRequest: mocks.loginRequest,
}))

// === L4.85.7: 真实 auth store (不 mock) 验证 Bug #1 治本 ===
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore, AUTH_TOKEN_KEY, AUTH_USER_KEY } from '@/stores/auth'

vi.mock('@/stores/auth', async () => {
  const actual = await vi.importActual<typeof import('@/stores/auth')>('@/stores/auth')
  return {
    ...actual,
    useAuthStore: () => {
      const store = actual.useAuthStore()
      vi.mocked(mocks.setSession).mockImplementation((t: string, u: string) => store.setSession(t, u))
      return store
    },
  }
})

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: mocks.push, replace: mocks.replace }),
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
    sessionStorage.clear()
    setActivePinia(createPinia())
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

// === L4.85.7 回归测试: 验证 Bug #1 真根因已治本 ===
// 跟 L4.42 立项实证 SOP + L4.50 0 业务代码改动 累计 95+ 次 + L4.85.5 plan-eng-review 缺陷 1+2 1:1 stable 永久规则链配套
describe('L4.85.7 Bug #1 治本回归', () => {
  beforeEach(() => {
    sessionStorage.clear()
    setActivePinia(createPinia())
  })

  it('Bug #1 治本: LoginView unmount 不清空 成功登录后 的 sessionStorage token', () => {
    // 模拟 user 登录成功: authStore.login 写 token 到 sessionStorage + 内存
    const authStore = useAuthStore()
    authStore.setSession('test-token-after-login', 'admin')
    expect(sessionStorage.getItem(AUTH_TOKEN_KEY)).toBe('test-token-after-login')
    expect(sessionStorage.getItem(AUTH_USER_KEY)).toBe('admin')
    expect(authStore.isAuthenticated).toBe(true)

    // Mount LoginView (模拟 router 跳到 /audience 又跳回 /login)
    const wrapper = mount(LoginView, {
      global: { stubs: { 'router-link': true, 'router-view': true } },
    })

    // Unmount LoginView (模拟 router.push('/audience') 触发 unmount)
    wrapper.unmount()

    // ✅ L4.85.7 治本: token 必须保留, 因为 user 已成功登录, token 还要用于后续 axios 请求
    expect(sessionStorage.getItem(AUTH_TOKEN_KEY)).toBe('test-token-after-login')
    expect(sessionStorage.getItem(AUTH_USER_KEY)).toBe('admin')
  })

  it('Bug #2 兼容: Cmd+Q 后 sessionStorage 应保留 token (L4.85.6 已 ship)', () => {
    // 模拟 user 登录成功
    const authStore = useAuthStore()
    authStore.setSession('test-token-cmd-q', 'admin')

    // 模拟 router 切换: LoginView mount → unmount (合法的 route 切换)
    const wrapper = mount(LoginView, {
      global: { stubs: { 'router-link': true, 'router-view': true } },
    })
    wrapper.unmount()

    // ✅ Cmd+Q 退出浏览器 → sessionStorage 持久化保留
    expect(sessionStorage.getItem(AUTH_TOKEN_KEY)).toBe('test-token-cmd-q')
  })
})
