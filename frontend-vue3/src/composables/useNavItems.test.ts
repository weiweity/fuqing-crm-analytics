import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useNavItems } from './useNavItems'
import { NAV_ITEMS } from '@/config/navigations'
import { useAuthStore } from '@/stores/auth'

describe('useNavItems (Admin Upload withdrawn)', () => {
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
    expect(navItems.value).toEqual(NAV_ITEMS)
  })

  it('admin=false returns NAV_ITEMS unchanged', () => {
    const authStore = useAuthStore()
    authStore.setSession('token-user', 'fqsw', false)

    const navItems = useNavItems()
    expect(navItems.value).toEqual(NAV_ITEMS)
    expect(navItems.value.map((i) => i.key)).not.toContain('/admin/upload')
  })

  it('does not mutate the shared NAV_ITEMS array', () => {
    const originalLength = NAV_ITEMS.length
    const authStore = useAuthStore()
    authStore.setSession('token-admin', 'admin', true)

    const navItems = useNavItems()
    expect(navItems.value.length).toBe(originalLength)
    expect(NAV_ITEMS.length).toBe(originalLength)
  })
})
