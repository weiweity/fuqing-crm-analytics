import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h } from 'vue'

// Stub lazy views to avoid heavy deps
const stub = (name: string) =>
  defineComponent({ name, render: () => h('div', name) })

vi.mock('@/views/AudienceView.vue', () => ({ default: stub('AudienceViewStub') }))
vi.mock('@/views/LoginView.vue', () => ({ default: stub('LoginViewStub') }))

import router from './index'
import { useAuthStore } from '@/stores/auth'

describe('router auth guard (Admin Upload route removed)', () => {
  beforeEach(async () => {
    sessionStorage.clear()
    setActivePinia(createPinia())
    await router.replace('/login').catch(() => {})
    await flushPromises()
  })

  it('unauthenticated user hitting protected /audience is redirected to /login', async () => {
    await router.push('/audience').catch(() => {})
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.redirect).toBe('/audience')
  })

  it('authenticated user can access /audience', async () => {
    const authStore = useAuthStore()
    authStore.setSession('token-user', 'fqsw', false)

    await router.push('/audience').catch(() => {})
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/audience')
  })

  it('/admin/upload is not a registered product route', async () => {
    const authStore = useAuthStore()
    authStore.setSession('token-admin', 'admin', true)

    await router.push('/admin/upload').catch(() => {})
    await flushPromises()

    // No matching route name AdminUpload; vue-router falls through without product view
    expect(router.currentRoute.value.name).not.toBe('AdminUpload')
    const matchedNames = router.getRoutes().map((r) => r.name).filter(Boolean)
    expect(matchedNames).not.toContain('AdminUpload')
  })
})
