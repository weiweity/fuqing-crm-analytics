import type { Ref } from 'vue'
import { watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

export function useRouteHashTab(activeTab: Ref<string>, tabNames: readonly string[]) {
  const route = useRoute()
  const router = useRouter()
  const validTabs = new Set(tabNames)

  function normalizeHash(hash: string) {
    return hash.startsWith('#') ? hash.slice(1) : hash
  }

  watch(
    () => route.hash,
    (hash) => {
      const tab = normalizeHash(hash)
      if (validTabs.has(tab) && activeTab.value !== tab) {
        activeTab.value = tab
      }
    },
    { immediate: true }
  )

  watch(activeTab, (tab) => {
    if (!validTabs.has(tab)) return

    const hash = `#${tab}`
    if (route.hash === hash) return

    router.replace({
      path: route.path,
      query: route.query,
      hash,
    })
  })
}
