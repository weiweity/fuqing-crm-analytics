/**
 * useFilterSync - URL ↔ Pinia filter state synchronization
 *
 * Design: URL as single source of truth (Plan Approach A)
 * - URL → Pinia: via router.beforeEach guard (handles browser back/forward)
 * - Pinia → URL: via watch with flush:'post' (handles user filter changes)
 * - Feedback loop prevention: router.replace to same URL won't re-trigger guard
 */
import { watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useFilterStore } from '@/stores/filterStore'
import { parseDateRange, getPeriodDateRange, type PeriodType } from '@/utils/date'

export function useFilterSync() {
  const route = useRoute()
  const router = useRouter()
  const filterStore = useFilterStore()

  // ─────────────────────────────────────────────────────────────
  // URL → Pinia: Sync from URL query to Pinia store
  // Called on: initial load + every navigation
  // ─────────────────────────────────────────────────────────────
  const syncFromUrl = () => {
    const { date, channel, dimension, dimValue, periodType } = route.query

    if (date) {
      const parsed = parseDateRange(date as string)
      if (parsed) {
        const [s, e] = parsed
        if (filterStore.dateRange[0] !== s || filterStore.dateRange[1] !== e) {
          filterStore.dateRange = parsed
        }
      }
    }
    if (channel && filterStore.channel !== channel) {
      filterStore.channel = channel as string
    }
    if (dimension && filterStore.dimension !== dimension) {
      filterStore.dimension = dimension as string
    }
    if (dimValue !== undefined && filterStore.dimensionValue !== dimValue) {
      filterStore.dimensionValue = dimValue as string
    }
    const nextPeriod = (periodType as PeriodType) || ''
    if (nextPeriod) {
      if (filterStore.periodType !== nextPeriod) {
        filterStore.periodType = nextPeriod
      }
    } else {
      // URL 没有 periodType 时
      if (!date) {
        // 没有 date 也没有 periodType，默认 MTD
        const mtd = getPeriodDateRange('MTD')!
        if (filterStore.periodType !== 'MTD') filterStore.periodType = 'MTD'
        if (filterStore.dateRange[0] !== mtd[0] || filterStore.dateRange[1] !== mtd[1]) {
          filterStore.dateRange = mtd
        }
      } else {
        // 有 date 但没有 periodType，视为自由筛选
        if (filterStore.periodType !== 'custom') {
          filterStore.periodType = 'custom'
        }
      }
    }
  }

  // Watch route.query for external URL changes (browser back/forward, manual edits)
  watch(() => route.query, syncFromUrl, { immediate: true, deep: true })


  // ─────────────────────────────────────────────────────────────
  // Pinia → URL: Sync from Pinia store to URL query
  // Called on: user interactions changing filter state
  // ─────────────────────────────────────────────────────────────
  watch(
    () => [
      filterStore.dateRange,
      filterStore.channel,
      filterStore.dimension,
      filterStore.dimensionValue,
      filterStore.periodType,
    ],
    () => {
      router.replace({
        query: {
          date: filterStore.dateRange.join(','),
          channel: filterStore.channel,
          dimension: filterStore.dimension,
          dimValue: filterStore.dimensionValue || undefined,
          periodType: filterStore.periodType || undefined,
        },
      })
    },
    { flush: 'post', deep: true }
  )
}
