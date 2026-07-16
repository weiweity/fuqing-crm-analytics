import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useNavItems } from './useNavItems'
import { NAV_ITEMS } from '@/config/navigations'
import { useAuthStore } from '@/stores/auth'

describe('useNavItems admin gating', () => {
  beforeEach(() => {
    sessionStorage.clear()
    setActivePinia(createPinia())
  })

  it('admin=true shows /admin/upload located right after /sampling', () => {
    const authStore = useAuthStore()
    authStore.setSession('token-admin', 'admin', true)

    const navItems = useNavItems()
    const keys = navItems.value.map((item) => item.key)

    expect(keys).toContain('/admin/upload')
    const samplingIdx = keys.indexOf('/sampling')
    const uploadIdx = keys.indexOf('/admin/upload')
    expect(samplingIdx).toBeGreaterThanOrEqual(0)
    // /admin/upload 紧跟在 /sampling 后
    expect(uploadIdx).toBe(samplingIdx + 1)

    // admin item 结构正确
    const uploadItem = navItems.value[uploadIdx]
    expect(uploadItem.label).toBe('数据上传')
    expect(uploadItem.tabs.map((t) => t.key)).toEqual(['#upload', '#history'])
  })

  it('admin=false does not show /admin/upload and returns NAV_ITEMS unchanged', () => {
    const authStore = useAuthStore()
    authStore.setSession('token-user', 'fqsw', false)

    const navItems = useNavItems()
    const keys = navItems.value.map((item) => item.key)

    expect(keys).not.toContain('/admin/upload')
    expect(navItems.value).toEqual(NAV_ITEMS)
  })

  it('does not mutate the shared NAV_ITEMS array when admin', () => {
    const originalLength = NAV_ITEMS.length
    const authStore = useAuthStore()
    authStore.setSession('token-admin', 'admin', true)

    const navItems = useNavItems()
    // 触发 computed 求值
    expect(navItems.value.length).toBe(originalLength + 1)
    // NAV_ITEMS 本身未被 push 污染
    expect(NAV_ITEMS.length).toBe(originalLength)
    expect(NAV_ITEMS.map((i) => i.key)).not.toContain('/admin/upload')
  })
})
