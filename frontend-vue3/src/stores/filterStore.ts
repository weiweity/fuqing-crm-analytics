import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { getPeriodDateRange, computeCompareRange, type PeriodType, type CompareMode } from '@/utils/date'

export const useFilterStore = defineStore('filter', () => {
  const dateRange = ref<[string, string]>(getPeriodDateRange('MTD')!)
  const channel = ref<string>('全店')
  const dimension = ref<string>('channel')
  const dimensionValue = ref<string>('')
  const periodType = ref<PeriodType>('MTD')
  const excludeLowPrice = ref<boolean>(false)

  // ── 对比日期 ──────────────────────────────
  const compareMode = ref<CompareMode>('auto_yoy')
  const compareDateRange = ref<[string, string] | null>(null)

  /** 标记：是否由程序自动更新对比日期（防止触发 auto-switch-to-custom） */
  let isProgrammaticCompareUpdate = false

  /**
   * 对比日期范围（始终有值）：
   * auto_yoy → 自动计算去年同期
   * auto_mom → 自动计算上一等长周期
   * custom   → 用户自选的对比日期（若未选则默认同比）
   *
   * 用于导航栏展示 + 报表查询
   */
  const computedCompareDateRange = computed<[string, string]>(() => {
    if (compareMode.value === 'custom' && compareDateRange.value) {
      return compareDateRange.value
    }
    const computed = computeCompareRange(dateRange.value, compareMode.value === 'custom' ? 'auto_yoy' : compareMode.value)
    return computed ?? computeCompareRange(dateRange.value, 'auto_yoy')!
  })

  /**
   * 需要传递给后端的对比日期范围：
   * auto_yoy → null（后端原生三列对比，不需要覆盖）
   * auto_mom → 自动计算的环比日期
   * custom   → 用户自选的对比日期（若未选则用等长前期兜底）
   */
  const compareParams = computed<[string, string] | null>(() => {
    if (compareMode.value === 'auto_yoy') {
      // YOY 交给后端原生处理，不传 compare 参数
      return null
    }
    if (compareMode.value === 'custom') {
      // 优先用户自选，兜底用等长前期
      return compareDateRange.value ?? computedCompareDateRange.value
    }
    // auto_mom: 自动计算环比日期
    return computeCompareRange(dateRange.value, compareMode.value)
  })

  /**
   * 对比模式显示标签（用于表头等）
   */
  const compareLabel = computed<string>(() => {
    if (compareMode.value === 'auto_yoy') return 'YOY'
    if (compareMode.value === 'auto_mom') return '环比'
    return '对比'
  })

  /**
   * 对比日期是否只读（同比/环比时自动计算，不可编辑）
   */
  const isCompareDateReadonly = computed<boolean>(() => {
    return compareMode.value !== 'custom'
  })

  // ── 联动：切到自定义对比时，自动填充默认对比日期（同比）──
  watch(compareMode, (mode) => {
    if (mode === 'custom' && !compareDateRange.value) {
      isProgrammaticCompareUpdate = true
      const defaultRange = computeCompareRange(dateRange.value, 'auto_yoy')
      if (defaultRange) compareDateRange.value = defaultRange
      isProgrammaticCompareUpdate = false
    }
  })

  // ── 联动：手动修改对比日期 → 自动切为自定义对比 ──
  watch(compareDateRange, () => {
    if (isProgrammaticCompareUpdate) return
    if (compareMode.value !== 'custom' && compareDateRange.value !== null) {
      compareMode.value = 'custom'
    }
  })

  // ── 联动：当前日期变化 → 自定义模式下重新填入同比日期 ──
  watch(dateRange, () => {
    if (compareMode.value === 'custom') {
      isProgrammaticCompareUpdate = true
      const yoyRange = computeCompareRange(dateRange.value, 'auto_yoy')
      if (yoyRange) compareDateRange.value = yoyRange
      isProgrammaticCompareUpdate = false
    }
  })

  watch(dimension, () => {
    dimensionValue.value = ''
  })

  return {
    dateRange, channel, dimension, dimensionValue,
    periodType, excludeLowPrice,
    compareMode, compareDateRange, compareParams, compareLabel,
    computedCompareDateRange, isCompareDateReadonly,
  }
})
