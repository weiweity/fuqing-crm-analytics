import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import NavBar from './NavBar.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ path: '/category', hash: '' }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}))

describe('NavBar idle logout', () => {
  beforeEach(() => {
    sessionStorage.clear()
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('disables the frontend idle timer in source', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/components/NavBar.vue'), 'utf8')
    expect(source).toMatch(/const IDLE_TIMEOUT_MS = 0/)
    expect(source).toContain('if (IDLE_TIMEOUT_MS <= 0) return')
  })

  it('does not schedule a 3-minute logout while authenticated', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const authStore = useAuthStore()
    authStore.setSession('tok', 'admin', true)
    const logout = vi.spyOn(authStore, 'logout').mockResolvedValue()
    const setTimeoutSpy = vi.spyOn(window, 'setTimeout')
    const wrapper = mount(NavBar, {
      global: {
        plugins: [pinia],
        stubs: { RouterLink: true, BrandMark: true },
      },
    })
    document.dispatchEvent(new Event('pointerdown'))
    await vi.advanceTimersByTimeAsync(3 * 60 * 1000 + 1000)
    expect(setTimeoutSpy.mock.calls.some(([, ms]) => ms === 3 * 60 * 1000)).toBe(false)
    expect(logout).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
