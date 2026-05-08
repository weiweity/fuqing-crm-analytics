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

  // ── 对比日期（新增） ──────────────────────────────
  const compareMode = ref<CompareMode>('auto_yoy')
  const compareDateRange = ref<[string, string] | null>(null)

  /**
   * 需要传递给后端的对比日期范围：
   * auto_yoy → null（后端原生三列对比，不需要覆盖）
   * auto_mom → 自动计算的环比日期
   * custom   → 用户自选的对比日期
   */
  const compareParams = computed<[string, string] | null>(() => {
    if (compareMode.value === 'auto_yoy') {
      // YOY 交给后端原生处理，不传 compare 参数
      return null
    }
    if (compareMode.value === 'custom') {
      return compareDateRange.value
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

  watch(dimension, () => {
    dimensionValue.value = ''
  })

  return {
    dateRange, channel, dimension, dimensionValue,
    periodType, excludeLowPrice,
    compareMode, compareDateRange, compareParams, compareLabel,
  }
})
