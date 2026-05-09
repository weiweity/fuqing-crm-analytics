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
import { parseDateRange, getPeriodDateRange, type PeriodType, type CompareMode } from '@/utils/date'

/** 合法的周期类型白名单 */
const VALID_PERIOD_TYPES: readonly PeriodType[] = [
  'WTD', 'MTD', 'YTD', 'Q1', 'Q2', 'Q3', 'Q4',
  'custom', 'yesterday', 'last180days', 'last365days',
]

function isValidPeriodType(v: string): v is PeriodType {
  return VALID_PERIOD_TYPES.includes(v as PeriodType)
}

export function useFilterSync() {
  const route = useRoute()
  const router = useRouter()
  const filterStore = useFilterStore()

  // ─────────────────────────────────────────────────────────────
  // URL → Pinia: Sync from URL query to Pinia store
  // Called on: initial load + every navigation
  // ─────────────────────────────────────────────────────────────
  const syncFromUrl = () => {
    const { date, channel, dimension, dimValue, periodType, compareMode, compareDateRange } = route.query

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
    const rawPeriod = (periodType as string) || ''
    if (rawPeriod && isValidPeriodType(rawPeriod)) {
      if (filterStore.periodType !== rawPeriod) {
        filterStore.periodType = rawPeriod
      }
    } else if (rawPeriod) {
      // 非法 periodType，回退到 custom（保留当前 dateRange）
      if (filterStore.periodType !== 'custom') {
        filterStore.periodType = 'custom'
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
    if (compareMode && filterStore.compareMode !== compareMode) {
      filterStore.compareMode = compareMode as CompareMode
    }
    if (compareDateRange) {
      const parsed = parseDateRange(compareDateRange as string)
      if (parsed && (!filterStore.compareDateRange || filterStore.compareDateRange[0] !== parsed[0] || filterStore.compareDateRange[1] !== parsed[1])) {
        filterStore.compareDateRange = parsed
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
      filterStore.compareMode,
      filterStore.compareDateRange,
    ],
    () => {
      router.replace({
        query: {
          date: filterStore.dateRange.join(','),
          channel: filterStore.channel,
          dimension: filterStore.dimension,
          dimValue: filterStore.dimensionValue || undefined,
          periodType: filterStore.periodType || undefined,
          compareMode: filterStore.compareMode || undefined,
          compareDateRange: filterStore.compareDateRange ? filterStore.compareDateRange.join(',') : undefined,
        },
      })
    },
    { flush: 'post', deep: true }
  )
}
