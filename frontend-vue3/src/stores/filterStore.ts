import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { getPeriodDateRange, type PeriodType } from '@/utils/date'

export const useFilterStore = defineStore('filter', () => {
  const dateRange = ref<[string, string]>(getPeriodDateRange('MTD')!)
  const channel = ref<string>('全店')
  const dimension = ref<string>('channel')
  const dimensionValue = ref<string>('')
  const periodType = ref<PeriodType>('MTD')
  const excludeLowPrice = ref<boolean>(false)

  watch(dimension, () => {
    dimensionValue.value = ''
  })

  return { dateRange, channel, dimension, dimensionValue, periodType, excludeLowPrice }
})
