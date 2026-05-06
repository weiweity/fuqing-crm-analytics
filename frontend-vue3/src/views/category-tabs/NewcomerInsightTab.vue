<script setup lang="ts">
import { computed, toValue } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NTooltip } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useFilterStore } from '@/stores/filterStore'
import { fetchCategoryNewcomerInsight } from '@/api/category'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import DataTablePro from '@/components/DataTablePro.vue'
import { CHART_COLORS } from '@/composables/useChartTheme'

const props = defineProps<{
  dataQualityNote?: string
}>()

const filterStore = useFilterStore()
import { LOW_PRICE_CHANNELS } from '@/constants/channels'

const queryParams = computed(() => ({
  start_date: filterStore.dateRange[0],
  end_date: filterStore.dateRange[1],
  level: 'class',
  channel: filterStore.channel === '全店' ? undefined : filterStore.channel,
  exclude_channels: filterStore.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined,
}))

const {
  data,
  isLoading,
  error,
  refetch,
} = useQuery({
  queryKey: computed(() => ['category-newcomer-insight', { ...toValue(queryParams) }]),
  queryFn: () => fetchCategoryNewcomerInsight(toValue(queryParams)),
  staleTime: 60_000,
})

// ─── Bar Chart: Top10 首购品类柱状图 ──────────────────────────────
const barChartOption = computed(() => {
  if (!data.value?.bars?.length) return {}
  const bars = data.value.bars  // 后端已截断TOP10，前端不再重复截断
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      padding: [10, 14],
      textStyle: { color: '#0f172a', fontSize: 12 },
      extraCssText: 'box-shadow: 0 4px 12px -2px rgba(0,0,0,0.08); border-radius: 4px;',
      formatter: (params: any[]) => {
        const item = params[0]
        const barItem = bars[item.dataIndex]
        return `${item.name}<br/>新客人数: ${item.value.toLocaleString()}<br/>新客GMV: ¥${(barItem.new_gmv / 10000).toFixed(1)}万`
      },
    },
    grid: { left: 12, right: 24, top: 20, bottom: 8, outerBounds: true },
    xAxis: {
      type: 'category',
      data: bars.map((b: { category_name: string }) => b.category_name),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 10, margin: 8, rotate: 30 },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 11 },
      splitLine: { lineStyle: { color: '#e5edf5', type: [4, 4] } },
    },
    series: [
      {
        name: '新客人数',
        type: 'bar',
        data: bars.map((b: { new_user_count: number }) => b.new_user_count),
        itemStyle: {
          color: CHART_COLORS[0],
          borderRadius: [3, 3, 0, 0],
        },
        barMaxWidth: 48,
      },
    ],
  }
})

// ─── Graph Diagram: 复购路径（ECharts 5 不支持 chord，用 graph 替代）────
const chordChartOption = computed(() => {
  if (!data.value?.chord_data?.nodes?.length) return {}
  const { nodes, links, source_nodes, target_nodes } = data.value.chord_data
  if (nodes.length < 2 || links.length === 0) return {}

  // 后端已区分 source_nodes（首购品类=左侧）和 target_nodes（复购品类=右侧）
  // fallback：老数据没有这两个字段时用原有切分逻辑
  const leftNodes = source_nodes ?? nodes.slice(0, Math.ceil(nodes.length / 2))
  const rightNodes = target_nodes ?? nodes.slice(Math.ceil(nodes.length / 2))

  const graphNodes = [
    ...leftNodes.map((n: string, i: number) => ({
      name: `首购:${n}`,
      x: 100,
      y: 80 + i * 60,
      symbolSize: 28,
      itemStyle: { color: CHART_COLORS[0] },
      label: { show: true, fontSize: 10, color: '#334155', formatter: `{b}` },
      displayName: n,
    })),
    ...rightNodes.map((n: string, i: number) => ({
      name: `复购:${n}`,
      x: 400,
      y: 80 + i * 60,
      symbolSize: 28,
      itemStyle: { color: CHART_COLORS[4] },
      label: { show: true, fontSize: 10, color: '#334155', formatter: `{b}` },
      displayName: n,
    })),
  ]

  const graphLinks = links.map((l: { source: string; target: string; value: number }) => ({
    source: `首购:${l.source}`,
    target: `复购:${l.target}`,
    value: l.value,
    lineStyle: { curveness: 0.2, opacity: 0.6, width: Math.max(1, Math.sqrt(l.value || 1)) },
  }))

  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      padding: [10, 14],
      textStyle: { color: '#0f172a', fontSize: 12 },
      extraCssText: 'box-shadow: 0 4px 12px -2px rgba(0,0,0,0.08); border-radius: 4px;',
      formatter: (params: any) => {
        if (params.dataType === 'edge') {
          const src = params.data.source.replace(/^首购:/, '')
          const tgt = params.data.target.replace(/^复购:/, '')
          return `${src} → ${tgt}`
        }
        return params.data?.displayName ?? params.name.replace(/^(首购|复购):/, '')
      },
    },
    animationDurationUpdate: 1500,
    animationEasingUpdate: 'quinticInOut' as any,
    series: [
      {
        type: 'graph',
        layout: 'none',
        symbol: 'circle',
        roam: false,
        label: { show: true, fontSize: 10 },
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: [4, 8],
        data: graphNodes,
        links: graphLinks,
        lineStyle: { color: '#c4b5fd', curveness: 0.2, opacity: 0.6 },
      },
    ],
  }
})

// ─── Table ───────────────────────────────────────────────────────
const tableColumns = computed<DataTableColumns<any>>(() => [
  {
    title: '首购品类',
    key: 'category_name',
    width: 130,
    fixed: 'left',
    align: 'center',
  },
  {
    title: '新客人数',
    key: 'new_user_count',
    width: 100,
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => row.new_user_count?.toLocaleString() ?? '—',
  },
  {
    title: '新客GMV',
    key: 'new_gmv',
    width: 100,
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => `¥${((row.new_gmv || 0) / 10000).toFixed(1)}万`,
  },
  {
    title: '品类内复购率',
    key: 'intra_repurchase_rate',
    width: 110,
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => `${((row.intra_repurchase_rate || 0) * 100).toFixed(1)}%`,
  },
  {
    title: '跨品类复购率',
    key: 'cross_repurchase_rate',
    width: 110,
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => `${((row.cross_repurchase_rate || 0) * 100).toFixed(1)}%`,
  },
  {
    title: '复购首选品类',
    key: 'top_repurchase_category',
    width: 120,
    align: 'center',
    render: (row) => row.top_repurchase_category || '—',
  },
  {
    title: '老客占比',
    key: 'old_user_ratio',
    width: 90,
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => `${((row.old_user_ratio || 0) * 100).toFixed(1)}%`,
  },
  {
    title: '老客AUS',
    key: 'old_aus',
    width: 90,
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => row.old_aus != null ? `¥${row.old_aus.toFixed(0)}` : '—',
  },
])

const tableData = computed(() => data.value?.table ?? [])

const suggestionRows = computed(() => data.value?.operation_suggestions ?? [])
</script>

<template>
  <div class="space-y-5">
    <!-- Data Quality Hint -->
    <div class="flex items-center justify-end gap-1">
      <n-tooltip trigger="hover" v-if="dataQualityNote || data?.data_quality_note">
        <template #trigger>
          <span class="inline-flex items-center justify-center w-4 h-4 rounded-full bg-slate-200 text-slate-500 text-[10px] font-bold cursor-help">i</span>
        </template>
        <span class="text-xs">{{ data?.data_quality_note || dataQualityNote }}</span>
      </n-tooltip>
    </div>

    <ErrorState v-if="error" :message="(error as Error).message" @retry="refetch()" />
    <LoadingState v-else-if="isLoading" />

    <template v-else-if="data">
      <!-- 上行: 柱状图(60%) + 和弦图(40%) -->
      <div class="grid grid-cols-5 gap-5">
        <div class="col-span-3 bi-card p-4">
          <h3 class="text-sm font-semibold text-slate-800 mb-0.5">新客首购品类TOP10</h3>
          <p class="text-[11px] text-slate-500 mb-3">首购该品类的新客人数，hover查看新客GMV</p>
          <EChartsWrapper :option="barChartOption" height="280px" />
        </div>
        <div class="col-span-2 bi-card p-4">
          <h3 class="text-sm font-semibold text-slate-800 mb-0.5">复购路径和弦图</h3>
          <p class="text-[11px] text-slate-500 mb-3">左侧首购TOP5 → 右侧复购品类，宽度∝复购人数</p>
          <EChartsWrapper :option="chordChartOption" height="280px" />
        </div>
      </div>

      <!-- 下行: 明细表 -->
      <div class="bi-card p-4">
        <h3 class="text-sm font-semibold text-slate-800 mb-0.5">首购品类明细表</h3>
        <p class="text-[11px] text-slate-500 mb-3">
          品类内复购率=30天内再次购买同一品类的用户占比；跨品类复购率=30天内购买其他品类的用户占比
        </p>
        <DataTablePro
          :columns="tableColumns"
          :data="tableData"
          :pagination="{ pageSize: 10 }"
          :scroll-x="900"
        />
      </div>

      <!-- 运营建议 -->
      <div v-if="suggestionRows.length" class="bi-card p-4 bg-amber-50 border-amber-200">
        <h3 class="text-sm font-semibold text-amber-800 mb-1.5">运营建议</h3>
        <ul class="space-y-1">
          <li v-for="(s, i) in suggestionRows" :key="i" class="text-xs text-amber-700 flex items-start gap-2">
            <span class="mt-0.5 text-amber-500 flex-shrink-0">•</span>
            {{ s }}
          </li>
        </ul>
      </div>
    </template>

    <EmptyState v-else description="暂无数据" />
  </div>
</template>
