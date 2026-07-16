import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h } from 'vue'

// 路由 component 是懒加载 dynamic import；导航到目标路由时才解析。
// AdminUploadView.vue 要 Phase D 才创建，这里 stub 掉；顺带 stub 重定向目标视图避免加载重依赖。
const stub = (name: string) =>
  defineComponent({ name, render: () => h('div', name) })

vi.mock('@/views/AdminUploadView.vue', () => ({ default: stub('AdminUploadViewStub') }))
vi.mock('@/views/AudienceView.vue', () => ({ default: stub('AudienceViewStub') }))
vi.mock('@/views/LoginView.vue', () => ({ default: stub('LoginViewStub') }))

import router from './index'
import { useAuthStore } from '@/stores/auth'

describe('router /admin/upload admin guard', () => {
  beforeEach(async () => {
    sessionStorage.clear()
    setActivePinia(createPinia())
    await router.replace('/login').catch(() => {})
    await flushPromises()
  })

  it('unauthenticated user hitting /admin/upload is redirected to /login preserving redirect query', async () => {
    // 未登录（sessionStorage 已清空）
    await router.push('/admin/upload').catch(() => {})
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.redirect).toBe('/admin/upload')
  })

  it('authenticated non-admin hitting /admin/upload is redirected to /audience', async () => {
    const authStore = useAuthStore()
    authStore.setSession('token-user', 'fqsw', false)

    await router.push('/admin/upload').catch(() => {})
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/audience')
  })

  it('authenticated admin can access /admin/upload', async () => {
    const authStore = useAuthStore()
    authStore.setSession('token-admin', 'admin', true)

    await router.push('/admin/upload').catch(() => {})
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/admin/upload')
    expect(router.currentRoute.value.name).toBe('AdminUpload')
  })
})
