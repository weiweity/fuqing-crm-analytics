<script setup lang="ts">
import { computed, toValue, h } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NGrid, NGi, NTabs, NTabPane } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useFilterStore } from '@/stores/filterStore'
import {
  fetchGeoDistribution,
  fetchGeoSegmentMatrix,
  fetchGeoTrend,
  type GeoDistributionItem,
} from '@/api/geo'
import MetricCard from '@/components/MetricCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import DataTablePro from '@/components/DataTablePro.vue'
import { BRAND_PRIMARY } from '@/composables/useChartTheme'

const filterStore = useFilterStore()

import { LOW_PRICE_CHANNELS } from '@/constants/channels'

const distributionParams = computed(() => ({
  date: filterStore.dateRange[1],
  lookback_days: 90,
  level: '省份',
  top_n: 15,
  exclude_channels: filterStore.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined,
}))

const segmentParams = computed(() => ({
  date: filterStore.dateRange[1],
  lookback_days: 90,
  top_n: 5,
  exclude_channels: filterStore.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined,
}))

const trendParams = computed(() => ({
  start_date: filterStore.dateRange[0],
  end_date: filterStore.dateRange[1],
  lookback_days: 90,
  top_n: 5,
  exclude_channels: filterStore.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined,
}))

const {
  data: distributionData,
  isLoading: distributionLoading,
  error: distributionError,
  refetch: distributionRefetch,
} = useQuery({
  queryKey: computed(() => ['geo-distribution', { ...toValue(distributionParams) }]),
  queryFn: () => fetchGeoDistribution(toValue(distributionParams)),
  staleTime: 60_000,
})

const {
  data: matrixData,
  isLoading: matrixLoading,
  error: matrixError,
  refetch: matrixRefetch,
} = useQuery({
  queryKey: computed(() => ['geo-segment-matrix', { ...toValue(segmentParams) }]),
  queryFn: () => fetchGeoSegmentMatrix(toValue(segmentParams)),
  staleTime: 60_000,
})

const {
  data: trendData,
  isLoading: trendLoading,
  error: trendError,
  refetch: trendRefetch,
} = useQuery({
  queryKey: computed(() => ['geo-trend', { ...toValue(trendParams) }]),
  queryFn: () => fetchGeoTrend(toValue(trendParams)),
  staleTime: 60_000,
})

const barChartOption = computed(() => {
  if (!distributionData.value) return {}
  const data = distributionData.value.distribution.slice().reverse()
  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      padding: [10, 12],
      textStyle: { color: '#0f172a', fontSize: 12 },
      extraCssText: 'box-shadow: 0 4px 12px -2px rgba(0,0,0,0.08); border-radius: 4px;',
      formatter: (params: any) => {
        const p = params[0]
        const item = data[p.dataIndex] as GeoDistributionItem
        return `<div class="font-medium text-slate-900">${p.name}</div>
                <div class="text-[11px] text-slate-500 mt-1">GMV: ¥${(item.gmv / 10000).toFixed(1)}万</div>
                <div class="text-[11px] text-slate-500">用户数: ${item.user_count.toLocaleString()}</div>
                <div class="text-[11px] text-slate-500">占比: ${(item.gmv_ratio * 100).toFixed(1)}%</div>`
      },
    },
    grid: { left: 12, right: 24, top: 12, bottom: 8 },
    xAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 11, formatter: (v: number) => `¥${(v / 10000).toFixed(0)}万` },
      splitLine: { lineStyle: { color: '#e2e8f0', type: [4, 4] } },
    },
    yAxis: {
      type: 'category',
      data: data.map((d) => d.name),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#0f172a', fontSize: 11, margin: 10 },
    },
    series: [
      {
        type: 'bar',
        data: data.map((d) => d.gmv),
        itemStyle: { color: BRAND_PRIMARY, borderRadius: [0, 3, 3, 0] },
        barMaxWidth: 16,
      },
    ],
  }
})

const trendChartOption = computed(() => {
  if (!trendData.value) return {}
  const data = trendData.value
  const colors = [BRAND_PRIMARY, '#10b981', '#ef4444', '#0f172a', '#64748b']
  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      padding: [10, 12],
      textStyle: { color: '#0f172a', fontSize: 12 },
      extraCssText: 'box-shadow: 0 4px 12px -2px rgba(0,0,0,0.08); border-radius: 4px;',
    },
    legend: {
      data: data.top_provinces,
      top: 0,
      icon: 'circle',
      itemGap: 20,
      textStyle: { color: '#64748b', fontSize: 11 },
    },
    grid: { left: 12, right: 12, top: 40, bottom: 8 },
    xAxis: {
      type: 'category',
      data: data.time_points,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 11, margin: 10 },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 11, formatter: (v: number) => `¥${(v / 10000).toFixed(0)}万` },
      splitLine: { lineStyle: { color: '#e2e8f0', type: [4, 4] } },
    },
    series: data.top_provinces.map((province, idx) => ({
      name: province,
      type: 'line',
      data: data.trends[province],
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2, color: colors[idx % colors.length] },
      itemStyle: { color: colors[idx % colors.length] },
    })),
  }
})

const distributionColumns: DataTableColumns<GeoDistributionItem> = [
  { title: '省份', key: 'name', width: 120, fixed: 'left' },
  {
    title: 'GMV',
    key: 'gmv',
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => `¥${(row.gmv / 10000).toFixed(1)}万`,
  },
  { title: '用户数', key: 'user_count', align: 'right', className: 'bi-cell-number' },
  {
    title: 'GMV占比',
    key: 'gmv_ratio',
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => `${(row.gmv_ratio * 100).toFixed(1)}%`,
  },
  {
    title: '用户占比',
    key: 'user_ratio',
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => `${(row.user_ratio * 100).toFixed(1)}%`,
  },
]

const matrixColumns = computed(() => {
  if (!matrixData.value) return []
  const firstSegmentData = Object.values(matrixData.value.matrix)[0] as { province: string; user_count: number; gmv: number }[] | undefined
  const provinces = firstSegmentData?.map((i) => i.province) || []
  const cols: DataTableColumns<any> = [
    { title: '人群象限', key: 'segment', width: 120, fixed: 'left' },
  ]
  provinces.forEach((province: string) => {
    cols.push({
      title: province,
      key: province,
      render: (row: any) => {
        const cell = row[province]
        if (!cell) return '—'
        return h('div', { class: 'space-y-0.5' }, [
          h('div', { class: 'text-xs text-slate-900 font-medium' }, `¥${(cell.gmv / 10000).toFixed(1)}万`),
          h('div', { class: 'text-[10px] text-slate-500' }, `${cell.user_count.toLocaleString()}人`),
        ])
      },
    })
  })
  return cols
})

const matrixTableData = computed(() => {
  if (!matrixData.value) return []
  const firstSegmentData = Object.values(matrixData.value.matrix)[0] as { province: string; user_count: number; gmv: number }[] | undefined
  const provinces = firstSegmentData?.map((i) => i.province) || []
  return matrixData.value.segments.map((seg) => {
    const row: Record<string, any> = { segment: seg.name }
    const segData = matrixData.value!.matrix[seg.id.toString()] || []
    provinces.forEach((province: string) => {
      const item = segData.find((d: any) => d.province === province)
      row[province] = item || null
    })
    return row
  })
})

function formatCurrency(value: number) {
  return `¥${(value / 10000).toFixed(1)}万`
}
</script>

<template>
  <div class="space-y-5 relative">
    <!-- 待优化更新遮罩 -->
    <div class="absolute inset-0 z-50 flex items-center justify-center bg-slate-50/80 backdrop-blur-sm rounded-lg" style="min-height: 600px;">
      <div class="text-center">
        <div class="text-4xl mb-2">🔧</div>
        <div class="text-lg font-semibold text-slate-600">待优化更新</div>
        <div class="text-sm text-slate-400 mt-1">该模块正在重构中，敬请期待</div>
      </div>
    </div>

    <PageHeader title="地域分析" subtitle="省份分布与地域-人群交叉洞察" />

    <n-grid :cols="4" :x-gap="12" :y-gap="12" responsive="screen" :item-responsive="true">
      <n-gi :span="1">
        <MetricCard
          title="总GMV"
          :value="distributionData ? formatCurrency(distributionData.total_gmv) : '—'"
          :loading="distributionLoading"
        />
      </n-gi>
      <n-gi :span="1">
        <MetricCard
          title="总用户数"
          :value="distributionData ? distributionData.total_users.toLocaleString() : '—'"
          :loading="distributionLoading"
        />
      </n-gi>
      <n-gi :span="1">
        <MetricCard
          title="TOP1省份"
          :value="distributionData?.distribution?.[0]?.name || '—'"
          :loading="distributionLoading"
        />
      </n-gi>
      <n-gi :span="1">
        <MetricCard
          title="省份数量"
          :value="distributionData ? distributionData.distribution.length.toLocaleString() : '—'"
          :loading="distributionLoading"
        />
      </n-gi>
    </n-grid>

    <div class="bi-card p-4">
      <n-tabs type="line" animated>
        <n-tab-pane name="distribution" tab="省份分布">
          <div class="space-y-5 mt-3">
            <ErrorState
              v-if="distributionError"
              :message="(distributionError as Error).message"
              @retry="distributionRefetch()"
            />
            <LoadingState v-else-if="distributionLoading" />
            <EmptyState v-else-if="!distributionData?.distribution?.length" />
            <template v-else>
              <EChartsWrapper :option="barChartOption" height="360px" />
              <DataTablePro
                :columns="distributionColumns"
                :data="distributionData.distribution"
                :pagination="{ pageSize: 20 }"
              />
            </template>
          </div>
        </n-tab-pane>

        <n-tab-pane name="matrix" tab="地域-象限矩阵">
          <div class="mt-3">
            <ErrorState
              v-if="matrixError"
              :message="(matrixError as Error).message"
              @retry="matrixRefetch()"
            />
            <LoadingState v-else-if="matrixLoading" />
            <EmptyState v-else-if="!matrixTableData.length" />
            <DataTablePro
              v-else
              :columns="matrixColumns"
              :data="matrixTableData"
              :pagination="false"
            />
          </div>
        </n-tab-pane>

        <n-tab-pane name="trend" tab="地域趋势">
          <div class="mt-3">
            <ErrorState
              v-if="trendError"
              :message="(trendError as Error).message"
              @retry="trendRefetch()"
            />
            <LoadingState v-else-if="trendLoading" />
            <EmptyState v-else-if="!trendData?.time_points?.length" />
            <EChartsWrapper v-else :option="trendChartOption" height="320px" />
          </div>
        </n-tab-pane>
      </n-tabs>
    </div>
  </div>
</template>
