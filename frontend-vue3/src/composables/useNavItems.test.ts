import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useNavItems } from './useNavItems'
import { NAV_ITEMS } from '@/config/navigations'
import { useAuthStore } from '@/stores/auth'

describe('useNavItems (Admin Upload withdrawn)', () => {
  it('local demo only offers the synthetic growth board', () => {
    setActivePinia(createPinia())
    useAuthStore().localDemoNoLogin = true
    expect(useNavItems().value.map((item) => item.key)).toEqual(['/growth-board'])
  })
  beforeEach(() => {
    sessionStorage.clear()
    setActivePinia(createPinia())
  })

  it('admin=true does not inject /admin/upload (product withdrawn)', () => {
    const authStore = useAuthStore()
    authStore.setSession('token-admin', 'admin', true)

    const navItems = useNavItems()
    const keys = navItems.value.map((item) => item.key)

    expect(keys).not.toContain('/admin/upload')
    expect(navItems.value.map((item) => item.key)).not.toContain('/growth-board')
    expect(navItems.value.map((item) => item.key)).not.toContain('/market-focus')
    expect(NAV_ITEMS.some((item) => item.key === '/market-focus' && item.hidden)).toBe(true)
  })

  it('admin=false hides growth-board and market-focus', () => {
    const authStore = useAuthStore()
    authStore.setSession('token-user', 'fqsw', false)

    const navItems = useNavItems()
    expect(navItems.value.map((item) => item.key)).not.toContain('/growth-board')
    expect(navItems.value.map((item) => item.key)).not.toContain('/market-focus')
    expect(NAV_ITEMS.some((item) => item.key === '/market-focus' && item.hidden)).toBe(true)
    expect(navItems.value.map((i) => i.key)).not.toContain('/admin/upload')
  })

  it('does not mutate the shared NAV_ITEMS array', () => {
    const originalLength = NAV_ITEMS.length
    const authStore = useAuthStore()
    authStore.setSession('token-admin', 'admin', true)

    const navItems = useNavItems()
    expect(navItems.value.length).toBe(NAV_ITEMS.filter((item) => !item.hidden).length)
    expect(NAV_ITEMS.length).toBe(originalLength)
    expect(NAV_ITEMS.some((item) => item.hidden)).toBe(true)
  })
})
