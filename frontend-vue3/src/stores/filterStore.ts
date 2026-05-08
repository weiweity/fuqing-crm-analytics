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
   * 有效对比日期范围：
   * auto_yoy / auto_mom → 自动计算
   * custom             → compareDateRange
   */
  const effectiveCompareRange = computed<[string, string] | null>(() => {
    if (compareMode.value === 'custom') {
      return compareDateRange.value
    }
    return computeCompareRange(dateRange.value, compareMode.value)
  })

  watch(dimension, () => {
    dimensionValue.value = ''
  })

  // 当主日期变化时，重置自定义对比期（避免脏数据）
  watch(dateRange, () => {
    if (compareMode.value === 'custom') {
      // custom 模式不自动清除，用户可以保留自己的选择
    }
  })

  return {
    dateRange, channel, dimension, dimensionValue,
    periodType, excludeLowPrice,
    compareMode, compareDateRange, effectiveCompareRange,
  }
})
