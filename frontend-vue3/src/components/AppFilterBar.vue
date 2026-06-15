<script setup lang="ts">
import { computed, watch } from 'vue'
import { NDatePicker, NSelect, NSwitch } from 'naive-ui'
import { useFilterStore } from '@/stores/filterStore'
import { getPeriodDateRange, formatDate } from '@/utils/date'

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
  { label: '昨日', value: 'yesterday' },
  { label: '周', value: 'WTD' },
  { label: '月', value: 'MTD' },
  { label: '年', value: 'YTD' },
  { label: '近180天', value: 'last180days' },
  { label: '近365天', value: 'last365days' },
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

// ── 默认日期：月维度（MTD） ──
if (!filterStore.dateRange || filterStore.dateRange[0] === '') {
  const range = getPeriodDateRange('MTD')
  if (range) filterStore.dateRange = range
  filterStore.periodType = 'MTD'
}

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

// ── 对比日期 ──
// 始终可编辑：非custom模式时展示自动计算的日期，编辑时自动切为custom模式
const compareDateModel = computed({
  get(): [number, number] {
    const [s, e] = filterStore.computedCompareDateRange
    return [new Date(s + 'T00:00:00').getTime(), new Date(e + 'T00:00:00').getTime()]
  },
  set(val: [number, number]) {
    if (val) {
      filterStore.compareDateRange = [formatDate(new Date(val[0])), formatDate(new Date(val[1]))]
    }
  },
})

// 点击对比日期选择器时：保留当前自动计算的对比日期，切为自定义模式
function handleCompareDateFocus() {
  if (filterStore.compareMode !== 'custom') {
    // 保留当前显示值（同比/环比自动计算的日期）作为自定义起点
    const currentComputed = filterStore.computedCompareDateRange
    filterStore.compareDateRange = currentComputed
    filterStore.compareMode = 'custom'
  }
}

watch(() => filterStore.periodType, (type) => {
  // 清空选择器后自动切为自定义，避免状态不一致
  if (!type) {
    filterStore.periodType = 'custom'
    return
  }
  if (type !== 'custom') {
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
  <div class="bg-white border-b border-slate-200">
    <!-- 第一行：当前日期 | 维度 | 渠道 | 低价筛选 -->
    <div class="flex flex-wrap items-center gap-4 px-5 py-2.5">
      <!-- 当前日期 -->
      <div class="flex items-center gap-2">
        <span class="text-xs font-semibold text-slate-500 uppercase tracking-wider min-w-[3.5rem]">当前日期</span>
        <n-date-picker
          v-model:value="dateRangeModel"
          type="daterange"
          clearable
          size="small"
          class="!w-64"
        />
      </div>

      <div class="w-px h-5 bg-slate-200" />

      <!-- 维度 -->
      <div class="flex items-center gap-2">
        <span class="text-xs font-semibold text-slate-500 uppercase tracking-wider">维度</span>
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

    <!-- 第二行：对比日期 | 对比模式 -->
    <div class="flex flex-wrap items-center gap-4 px-5 py-2 bg-slate-50/70 border-t border-slate-100">
      <!-- 对比日期（始终可编辑） -->
      <div class="flex items-center gap-2">
        <span class="text-xs font-semibold text-slate-500 uppercase tracking-wider min-w-[3.5rem]">对比日期</span>
        <n-date-picker
          v-model:value="compareDateModel"
          type="daterange"
          size="small"
          class="!w-64"
          @focus="handleCompareDateFocus"
        />
      </div>

      <div class="w-px h-5 bg-slate-200" />

      <!-- 对比模式 -->
      <div class="flex items-center gap-2">
        <span class="text-xs font-semibold text-slate-500 uppercase tracking-wider">对比</span>
        <n-select
          v-model:value="filterStore.compareMode"
          :options="compareModeOptions"
          size="small"
          class="!w-36"
        />
      </div>
    </div>
  </div>
</template>
