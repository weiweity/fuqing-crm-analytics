<script setup lang="ts">
import { computed, toValue } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NAlert } from 'naive-ui'
import {
  fetchStoreAssets,
} from '@/api/marketFocus'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import LineChart from '@/components/LineChart.vue'

const props = defineProps<{ weeks: number }>()

// 日维度：折线图
const dailyQueryParams = computed(() => ({ weeks: props.weeks, days: props.weeks * 7 }))
const { data: dailyData } = useQuery({
  queryKey: computed(() => ['store-assets-daily', { ...toValue(dailyQueryParams) }]),
  queryFn: () => {
    const p = toValue(dailyQueryParams)
    return fetchStoreAssets(p.weeks, p.days)
  },
  staleTime: 5 * 60 * 1000,
})

// 周维度：表格
const weeklyQueryParams = computed(() => ({ weeks: props.weeks }))
const { data: weeklyData, isLoading, error, refetch } = useQuery({
  queryKey: computed(() => ['store-assets-weekly', { ...toValue(weeklyQueryParams) }]),
  queryFn: () => {
    const p = toValue(weeklyQueryParams)
    return fetchStoreAssets(p.weeks, 0)
  },
  staleTime: 5 * 60 * 1000,
})

// 折线图：各人群 by 日
const chartDayLabels = computed(() => dailyData.value?.weeks.map(w => w.week_label) ?? [])

const crowdSeries = computed(() => {
  const weeks = dailyData.value?.weeks
  if (!weeks?.length) return []
  const fields: { key: StoreField; label: string }[] = [
    { key: 'discover', label: '发现' },
    { key: 'engage', label: '种草' },
    { key: 'enthuse', label: '互动' },
    { key: 'perform', label: '行动' },
    { key: 'initial', label: '首购' },
    { key: 'numerous', label: '复购' },
    { key: 'keen', label: '至爱' },
  ]
  return fields.map(f => ({
    name: f.label,
    data: weeks.map(w => w[f.key]),
  }))
})

// 格式化
function fmtInt(v: number): string {
  return v.toLocaleString()
}

function fmtChange(v: number): string {
  const abs = Math.abs(v)
  const sign = v > 0 ? '+' : ''
  // 超过5位数（10000以上）显示万单位
  if (abs >= 10000) {
    return `${sign}${(abs / 10000).toFixed(1)}万`
  }
  return `${sign}${v.toLocaleString()}`
}

function changeClass(v: number): string {
  if (v > 0) return 'text-rose-500'
  if (v < 0) return 'text-emerald-500'
  return 'text-slate-400'
}

// 表头映射
const storeColumns = [
  { key: 'total', label: '资产总量' },
  { key: 'discover', label: '发现' },
  { key: 'engage', label: '种草' },
  { key: 'enthuse', label: '互动' },
  { key: 'perform', label: '行动' },
  { key: 'initial', label: '首购' },
  { key: 'numerous', label: '复购' },
  { key: 'keen', label: '至爱' },
] as const

type StoreField = typeof storeColumns[number]['key']

function rowBg(idx: number): string {
  return idx % 2 === 0 ? 'bg-white' : 'bg-slate-50/80'
}
</script>

<template>
  <div>
    <LoadingState v-if="isLoading" description="正在加载全店资产数据..." />
    <ErrorState v-else-if="error" :message="String(error)" @retry="refetch" />
    <EmptyState v-else-if="!weeklyData?.weeks?.length" description="暂无全店资产数据" />

    <template v-else>
      <!-- 折线图：各人群趋势（日维度） -->
      <div class="bi-card p-4 mb-6">
        <div class="mb-0.5">
          <h3 class="text-sm font-semibold text-slate-800">各人群资产趋势</h3>
          <p class="text-[11px] text-slate-500">DMP全店人群日度流转 — 发现/种草/互动/行动/首购/复购/至爱</p>
        </div>
        <LineChart
          :x-axis-data="chartDayLabels"
          :series="crowdSeries"
          :y-axis="{ name: '人数', formatter: (v: number) => v >= 10000 ? (v / 10000).toFixed(1) + '万' : String(v) }"
          height="280px"
        />
      </div>

      <!-- 变化行说明 -->
      <NAlert type="warning" :bordered="false" class="text-xs mb-2" size="small">
        注：本周对比为绝对值差（+N人），非百分比
      </NAlert>

      <!-- 数据表（周维度） -->
      <div class="overflow-x-auto rounded-lg border border-slate-200">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-slate-200 bg-slate-50">
              <th class="text-left py-3 px-3 text-slate-600 font-semibold sticky left-0 bg-slate-50 z-10 min-w-[100px]">时间</th>
              <th
                v-for="col in storeColumns"
                :key="col.key"
                class="text-right py-3 px-3 text-slate-600 font-semibold"
              >{{ col.label }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(week, idx) in weeklyData.weeks"
              :key="week.week_label"
              :class="['border-b border-slate-100', rowBg(idx)]"
            >
              <td class="py-2.5 px-3 text-slate-900 font-medium sticky left-0 z-10 min-w-[100px]"
                :class="rowBg(idx)"
              >{{ week.week_label }}</td>
              <td
                v-for="col in storeColumns"
                :key="col.key"
                class="py-2.5 px-3 text-right text-slate-900 tabular-nums"
              >{{ fmtInt(week[col.key as StoreField]) }}</td>
            </tr>
            <!-- 本周对比上周 -->
            <tr
              v-if="weeklyData.weeks.length >= 2"
              class="border-b border-slate-200 bg-violet-50/50"
            >
              <td class="py-2 px-3 text-slate-500 font-medium sticky left-0 bg-violet-50/50 z-10">本周对比上周</td>
              <td
                v-for="col in storeColumns"
                :key="col.key"
                class="py-2 px-3 text-right tabular-nums"
                :class="changeClass(weeklyData.weeks[weeklyData.weeks.length - 1][`${col.key}_change` as `${StoreField}_change`])"
              >
                {{ fmtChange(weeklyData.weeks[weeklyData.weeks.length - 1][`${col.key}_change` as `${StoreField}_change`]) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>
