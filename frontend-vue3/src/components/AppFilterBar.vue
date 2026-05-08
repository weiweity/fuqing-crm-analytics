<script setup lang="ts">
import { computed, watch } from 'vue'
import { NDatePicker, NSelect, NSwitch } from 'naive-ui'
import { useFilterStore } from '@/stores/filterStore'
import { getPeriodDateRange, formatDate, type CompareMode } from '@/utils/date'

const filterStore = useFilterStore()

let isProgrammaticUpdate = false

const channelOptions = [
  { label: '全店', value: '全店' },
  { label: '纯派样', value: '纯派样' },
  { label: '货架', value: '货架' },
  { label: '达播', value: '达播' },
  { label: '直播', value: '直播' },
  { label: '淘客', value: '淘客' },
  { label: '微博', value: '微博' },
  { label: 'U先派样', value: 'U先派样' },
  { label: '百补派样', value: '百补派样' },
  { label: '赠品&0.01', value: '赠品&0.01' },
  { label: '其他', value: '其他' },
]

const periodTypeOptions = [
  { label: '周', value: 'WTD' },
  { label: '月', value: 'MTD' },
  { label: '年', value: 'YTD' },
  { label: '第一季度', value: 'Q1' },
  { label: '第二季度', value: 'Q2' },
  { label: '第三季度', value: 'Q3' },
  { label: '第四季度', value: 'Q4' },
  { label: '自定义', value: 'custom' },
]

const compareModeOptions = [
  { label: '同比(YOY)', value: 'auto_yoy' },
  { label: '环比(MOM)', value: 'auto_mom' },
  { label: '自定义对比', value: 'custom' },
]

const dateRangeModel = computed({
  get(): [number, number] {
    const [s, e] = filterStore.dateRange
    return [new Date(s + 'T00:00:00').getTime(), new Date(e + 'T00:00:00').getTime()]
  },
  set(val: [number, number]) {
    if (val) {
      filterStore.dateRange = [formatDate(new Date(val[0])), formatDate(new Date(val[1]))]
      if (!isProgrammaticUpdate) {
        filterStore.periodType = 'custom'
      }
    }
  },
})

const compareDateModel = computed({
  get(): [number, number] | null {
    const range = filterStore.compareDateRange
    if (!range) return null
    return [new Date(range[0] + 'T00:00:00').getTime(), new Date(range[1] + 'T00:00:00').getTime()]
  },
  set(val: [number, number] | null) {
    if (val) {
      filterStore.compareDateRange = [formatDate(new Date(val[0])), formatDate(new Date(val[1]))]
    } else {
      filterStore.compareDateRange = null
    }
  },
})

watch(() => filterStore.periodType, (type) => {
  if (type && type !== 'custom') {
    const range = getPeriodDateRange(type)
    if (range) {
      isProgrammaticUpdate = true
      filterStore.dateRange = range
      isProgrammaticUpdate = false
    }
  }
})
</script>

<template>
  <div class="flex flex-wrap items-center gap-4 px-5 py-3 bg-white border-b border-slate-200">
    <!-- 当前日期 -->
    <div class="flex items-center gap-2">
      <span class="text-xs font-semibold text-slate-500 uppercase tracking-wider">日期</span>
      <n-date-picker
        v-model:value="dateRangeModel"
        type="daterange"
        clearable
        size="small"
        class="!w-64"
      />
      <n-select
        v-model:value="filterStore.periodType"
        :options="periodTypeOptions"
        placeholder="周期"
        size="small"
        clearable
        class="!w-36"
      />
    </div>

    <div class="w-px h-5 bg-slate-200" />

    <!-- 对比日期（新增） -->
    <div class="flex items-center gap-2">
      <span class="text-xs font-semibold text-slate-500 uppercase tracking-wider">对比</span>
      <n-select
        v-model:value="filterStore.compareMode"
        :options="compareModeOptions"
        size="small"
        class="!w-36"
      />
      <n-date-picker
        v-if="filterStore.compareMode === 'custom'"
        v-model:value="compareDateModel"
        type="daterange"
        clearable
        size="small"
        class="!w-64"
      />
    </div>

    <div class="w-px h-5 bg-slate-200" />

    <!-- 渠道 -->
    <div class="flex items-center gap-2">
      <span class="text-xs font-semibold text-slate-500 uppercase tracking-wider">渠道</span>
      <n-select
        v-model:value="filterStore.channel"
        :options="channelOptions"
        size="small"
        class="!w-28"
        clearable
      />
    </div>

    <div class="w-px h-5 bg-slate-200" />

    <!-- 低价筛选 -->
    <div class="flex items-center justify-center gap-2">
      <span class="text-xs font-semibold text-slate-500 uppercase tracking-wider text-center">低价筛选</span>
      <n-switch v-model:value="filterStore.excludeLowPrice" size="small">
        <template #checked>剔除低价</template>
        <template #unchecked>全部</template>
      </n-switch>
    </div>
  </div>
</template>
