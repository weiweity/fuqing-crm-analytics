<script setup lang="ts">
import { computed, h, toValue } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NTooltip } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useFilterStore } from '@/stores/filterStore'
import { fetchCategoryChurn } from '@/api/category'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import DataTablePro from '@/components/DataTablePro.vue'
import ExportToolbar from '@/components/ExportToolbar.vue'
import type { XlsxColumn } from '@/utils/exportXlsx'

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
  queryKey: computed(() => ['category-churn', { ...toValue(queryParams) }]),
  queryFn: () => fetchCategoryChurn(toValue(queryParams)),
  staleTime: 60_000,
})

// ─── 流失严重度散点图 ──────────────────────────────────────────
// X = 本期用户数(对数), Y = MoM变化率, 气泡大小 = 流失人数
// 第四象限(左下: 规模大+下滑快) 标红
const scatterOption = computed(() => {
  if (!data.value?.scatter_data?.length) return {}
  const points = data.value.scatter_data
  // 对数刻度 X 轴，取 log10
  const xData = points.map((p) => ({
    value: [Math.log10(p.current_users + 1), p.mom_change_rate * 100, p.churn_users],
    name: p.category_name,
    ...p,
  }))

  // 找最大流失人数用于气泡缩放
  const maxChurn = Math.max(...points.map((p) => p.churn_users))

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
        const p = params.data
        return `<b>${p.name}</b><br/>本期用户: ${p.current_users.toLocaleString()}<br/>MoM变化: ${(p.mom_change_rate * 100).toFixed(1)}%<br/>流失人数: ${p.churn_users.toLocaleString()}`
      },
    },
    grid: { left: 56, right: 24, top: 16, bottom: 40 },
    xAxis: {
      type: 'value',
      name: '本期用户数(log)',
      nameTextStyle: { color: '#64748b', fontSize: 10 },
      axisLine: { lineStyle: { color: '#e5edf5' } },
      axisTick: { show: false },
      axisLabel: {
        color: '#64748b',
        fontSize: 10,
        formatter: (v: number) => `${Math.pow(10, v).toLocaleString()}`,
      },
      splitLine: { lineStyle: { color: '#f0f4f8', type: [4, 4] } },
    },
    yAxis: {
      type: 'value',
      name: 'MoM变化率(%)',
      nameTextStyle: { color: '#64748b', fontSize: 10 },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 11, formatter: (v: number) => `${v.toFixed(0)}%` },
      splitLine: { lineStyle: { color: '#e5edf5', type: [4, 4] } },
    },
    series: [
      {
        type: 'scatter',
        symbolSize: (val: number[]) => {
          const ratio = val[2] / maxChurn
          return 14 + ratio * 46 // 14-60px
        },
        data: xData,
        itemStyle: {
          color: (param: any) => {
            const p = param.data
            const isLargeScale = Math.log10(p.current_users + 1) > 4 // 规模大(>1万)
            const isDeclining = p.mom_change_rate < 0 // MoM下滑
            if (isLargeScale && isDeclining) return '#ef4444' // 第四象限标红
            if (p.mom_change_rate > 0) return '#10b981'
            return '#94a3b8'
          },
          opacity: 0.8,
        },
        label: {
          show: false,
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 11,
            color: '#0f172a',
            fontWeight: 'bold',
            position: 'top',
            formatter: (param: any) => param.data.name,
          },
        },
      },
    ],
    // 参考线: Y=0
    markLine: {
      silent: true,
      symbol: 'none',
      lineStyle: { color: '#cbd5e1', type: 'dashed', width: 1 },
      data: [{ yAxis: 0 }],
    },
  }
})

// ─── MoM柱状图 ────────────────────────────────────────────────
const barOption = computed(() => {
  if (!data.value?.bar_data?.length) return {}
  const rows = data.value.bar_data
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
        const row = rows[params[0].dataIndex]
        return `${row.category_name}<br/>本期: ${row.current_users.toLocaleString()}<br/>上期: ${row.previous_users.toLocaleString()}<br/>MoM: ${(row.mom_change_rate * 100).toFixed(1)}%`
      },
    },
    grid: { left: 56, right: 24, top: 16, bottom: 64, containLabel: false },
    xAxis: {
      type: 'category',
      data: rows.map((r) => r.category_name),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 10, margin: 12, rotate: 40, interval: 0 },
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
        name: 'MoM变化',
        type: 'bar',
        data: rows.map((r) => ({
          value: parseFloat((r.mom_change_rate * 100).toFixed(2)),
          itemStyle: {
            color: r.mom_change_rate >= 0 ? '#10b981' : '#ef4444',
            borderRadius: r.mom_change_rate >= 0 ? [3, 3, 0, 0] : [0, 0, 3, 3],
          },
        })),
        barMaxWidth: 40,
      },
    ],
  }
})

// ─── Table ───────────────────────────────────────────────────────
const DEST_COLOR: Record<string, string> = {
  面膜: '#533afd',
  洁面: '#15be53',
  精华: '#8b5cf6',
  '医用凝胶': '#ea2261',
  面霜: '#f59e0b',
  防晒: '#10b981',
}

const tableColumns = computed<DataTableColumns<any>>(() => [
  {
    title: '品类',
    key: 'category_name',
    width: 110,
    fixed: 'left',
    align: 'center',
  },
  {
    title: '本期用户',
    key: 'current_users',
    width: 90,
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => row.current_users?.toLocaleString() ?? '—',
  },
  {
    title: '上期用户',
    key: 'previous_users',
    width: 90,
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => row.previous_users?.toLocaleString() ?? '—',
  },
  {
    title: 'MoM变化',
    key: 'mom_change_rate',
    width: 90,
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => {
      const v = row.mom_change_rate
      const cls = v >= 0 ? 'text-emerald-600' : 'text-red-500'
      return h('span', { class: cls }, `${v >= 0 ? '+' : ''}${(v * 100).toFixed(1)}%`)
    },
  },
  {
    title: '品类间流失',
    key: 'inter_churn',
    width: 90,
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => row.inter_churn?.toLocaleString() ?? '—',
  },
  {
    title: '沉默流失',
    key: 'silent_churn',
    width: 90,
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => row.silent_churn?.toLocaleString() ?? '—',
  },
  {
    title: '流失去向TOP1',
    key: 'top_churn_dest1',
    width: 110,
    align: 'center',
    render: (row) => {
      const dest = row.top_churn_dest1
      if (!dest) return '—'
      const color = DEST_COLOR[dest] || '#64748b'
      return h('span', {
        class: 'inline-flex items-center gap-1',
        style: { color },
      }, dest)
    },
  },
  {
    title: 'TOP1占比',
    key: 'top_churn_dest1_ratio',
    width: 75,
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => row.top_churn_dest1_ratio != null ? `${(row.top_churn_dest1_ratio * 100).toFixed(0)}%` : '—',
  },
  {
    title: '流失去向TOP2',
    key: 'top_churn_dest2',
    width: 110,
    align: 'center',
    render: (row) => {
      const dest = row.top_churn_dest2
      if (!dest) return '—'
      const color = DEST_COLOR[dest] || '#64748b'
      return h('span', { style: { color } }, dest)
    },
  },
  {
    title: '挽回建议',
    key: '挽回建议',
    width: 140,
    align: 'left',
    ellipsis: true,
    render: (row) => row.挽回建议 || '—',
  },
])

const tableData = computed(() => data.value?.table ?? [])
const suggestionRows = computed(() => data.value?.operation_suggestions ?? [])

// ── Sprint 174 XLSX 导出 (Q3) ──
const churnTableXlsxColumns = computed<XlsxColumn[]>(() => [
  { header: '品类', key: 'category_name', width: 14 },
  { header: '本期用户', key: 'current_users', width: 12, numFmt: '#,##0' },
  { header: '上期用户', key: 'previous_users', width: 12, numFmt: '#,##0' },
  { header: '流失人数', key: 'churn_users', width: 12, numFmt: '#,##0' },
  { header: 'MoM变化', key: 'mom_change_rate', width: 12, numFmt: '0.0%' },
])
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
      <!-- 上行: 散点图(60%) + 柱状图(40%) -->
      <div class="grid grid-cols-5 gap-5">
        <div class="col-span-3 bi-card p-4">
          <h3 class="text-sm font-semibold text-slate-800 mb-0.5">流失严重度散点图</h3>
          <p class="text-[11px] text-slate-500 mb-1">X=规模(log)，Y=MoM变化，气泡=流失人数，左下红区=规模大+下滑快</p>
          <p class="text-[11px] text-slate-400 mb-3">一眼识别最危险的品类：规模大且下滑快的品类在左下红区，需要优先关注</p>
          <EChartsWrapper :option="scatterOption" height="300px" />
        </div>
        <div class="col-span-2 bi-card p-4">
          <h3 class="text-sm font-semibold text-slate-800 mb-0.5">各品类MoM变化</h3>
          <p class="text-[11px] text-slate-500 mb-3">绿色=增长，红色=下滑</p>
          <EChartsWrapper :option="barOption" height="300px" />
        </div>
      </div>

      <!-- 下方表格 -->
      <div class="bi-card p-4">
        <div class="flex items-center justify-between mb-0.5">
          <h3 class="text-sm font-semibold text-slate-800">流失明细表</h3>
          <ExportToolbar
            :filename="`流失预警_${filterStore.dateRange[0]}_${filterStore.dateRange[1]}`"
            :columns="churnTableXlsxColumns"
            :data="tableData as any[]"
            sheet-name="流失明细"
          />
        </div>
        <p class="text-[11px] text-slate-500 mb-1">
          品类间流失=上期买A本期买B(B≠A)；沉默流失=上期买A本期无订单；跨品类迁移≠流失
        </p>
        <p class="text-[11px] text-slate-400 mb-3">
          品类间流失说明用户转向了竞品品类（看流失去向可追踪），沉默流失说明用户彻底沉默了——两种流失的挽回策略完全不同
        </p>
        <DataTablePro
          :columns="tableColumns"
          :data="tableData"
          :pagination="{ pageSize: 10 }"
          :scroll-x="1100"
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
