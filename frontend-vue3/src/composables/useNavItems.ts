import { computed } from 'vue'
import { NAV_ITEMS, type NavItem } from '@/config/navigations'
import { useAuthStore } from '@/stores/auth'

// Sprint 3A: admin 专属"数据上传"导航项。仅当 authStore.isAdmin 时追加，位于 /sampling 后。
// 不 mutate NAV_ITEMS，不改 navigations.ts（SSOT 单源）。
const ADMIN_UPLOAD_NAV_ITEM: NavItem = {
  key: '/admin/upload',
  label: '数据上传',
  tabs: [
    { key: '#upload', label: '上传文件' },
    { key: '#history', label: '上传记录' },
  ],
}

export function useNavItems() {
  const authStore = useAuthStore()
  return computed<NavItem[]>(() => {
    if (!authStore.isAdmin) return NAV_ITEMS
    return [...NAV_ITEMS, ADMIN_UPLOAD_NAV_ITEM]
  })
}
