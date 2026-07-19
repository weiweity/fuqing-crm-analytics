import { computed } from 'vue'
import { NAV_ITEMS, type NavItem } from '@/config/navigations'
import { useAuthStore } from '@/stores/auth'

/**
 * Navigation items for sidebar.
 * Admin Upload product path withdrawn (2026-07-19 governance) — no admin-only nav injection.
 * isAdmin remains for other features (login-request, single-user mode).
 */
export function useNavItems() {
  const authStore = useAuthStore()
  return computed<NavItem[]>(() => {
    void authStore.isAdmin  // keep reactive auth dependency for future admin-only items
    return NAV_ITEMS
  })
}
