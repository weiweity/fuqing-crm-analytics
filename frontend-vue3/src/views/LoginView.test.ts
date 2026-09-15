import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { AUTH_TOKEN_KEY, AUTH_USER_KEY, useAuthStore } from '@/stores/auth'
import LoginView from './LoginView.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}))

describe('LoginView compact workspace access', () => {
  beforeEach(() => {
    sessionStorage.clear()
    setActivePinia(createPinia())
  })

  it('centers the form and drops the illustration and session takeover', () => {
    const wrapper = mount(LoginView)
    expect(wrapper.find('.illustration-section').exists()).toBe(false)
    expect(wrapper.find('.btn-apply').exists()).toBe(false)
    expect(wrapper.find('.form-section').exists()).toBe(true)
    expect(wrapper.get('.welcome-title').text()).toBe('进入增长董事会')
    wrapper.unmount()
  })

  it('keeps a successful session after unmount', () => {
    const authStore = useAuthStore()
    authStore.setSession('test-token-after-login', 'admin', true)
    const wrapper = mount(LoginView)
    wrapper.unmount()
    expect(sessionStorage.getItem(AUTH_TOKEN_KEY)).toBe('test-token-after-login')
    expect(sessionStorage.getItem(AUTH_USER_KEY)).toBe('admin')
  })
})
