<script setup lang="ts">
import { encodeHtml } from '@/utils/encodeHtml'
import { computed, h, toValue } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NTooltip } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useFilterStore } from '@/stores/filterStore'
import { fetchCategoryChurn } from '@/api/category'
import { categoryDisplayName, destColor, destDisplayName, maskCategoryTokensInText, maskDestsInText } from '@/utils/maskCategoryName'
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

// ─── 流失风险散点图 ──────────────────────────────────────────
// X = 本期用户数(对数), Y = 平均 hazard, 气泡 = 高风险人数
const scatterOption = computed(() => {
  if (!data.value?.scatter_data?.length) return {}
  const points = data.value.scatter_data
  const xData = points.map((p) => ({
    value: [Math.log10(p.current_users + 1), p.mean_hazard * 100, p.high_risk_users],
    name: categoryDisplayName(p),
    ...p,
  }))

  const maxChurn = Math.max(...points.map((p) => p.high_risk_users), 1)

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
        return `<b>${encodeHtml(categoryDisplayName(p))}</b><br/>本期用户: ${p.current_users.toLocaleString()}<br/>平均风险: ${(p.mean_hazard * 100).toFixed(1)}%<br/>高风险人数: ${p.high_risk_users.toLocaleString()}`
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
      name: '平均流失风险(%)',
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
          return 14 + ratio * 46
        },
        data: xData,
        itemStyle: {
          color: (param: any) => {
            const p = param.data
            const isLargeScale = Math.log10(p.current_users + 1) > 4
            const isHighRisk = p.mean_hazard >= 0.5
            if (isLargeScale && isHighRisk) return '#ef4444'
            if (p.mean_hazard < 0.3) return '#10b981'
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
            formatter: (param: any) => encodeHtml(categoryDisplayName(param.data)),
          },
        },
      },
    ],
    markLine: {
      silent: true,
      symbol: 'none',
      lineStyle: { color: '#cbd5e1', type: 'dashed', width: 1 },
      data: [{ yAxis: 50 }],
    },
  }
})

// ─── 平均流失风险柱状图 ────────────────────────────────────────────────
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
        return `${encodeHtml(categoryDisplayName(row))}<br/>本期: ${row.current_users.toLocaleString()}<br/>上期: ${row.previous_users.toLocaleString()}<br/>平均风险: ${(row.mean_hazard * 100).toFixed(1)}%`
      },
    },
    grid: { left: 56, right: 24, top: 16, bottom: 64, containLabel: false },
    xAxis: {
      type: 'category',
      data: rows.map((r) => categoryDisplayName(r)),
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
        name: '平均流失风险',
        type: 'bar',
        data: rows.map((r) => ({
          value: parseFloat((r.mean_hazard * 100).toFixed(2)),
          itemStyle: {
            color: r.mean_hazard >= 0.5 ? '#ef4444' : '#10b981',
            borderRadius: [3, 3, 0, 0],
          },
        })),
        barMaxWidth: 40,
      },
    ],
  }
})

// ─── Table ───────────────────────────────────────────────────────
const tableColumns = computed<DataTableColumns<any>>(() => [
  {
    title: '品类',
    key: 'category_name',
    width: 110,
    fixed: 'left',
    align: 'center',
    render: (row) => categoryDisplayName(row),
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
    title: '平均风险',
    key: 'mean_hazard',
    width: 90,
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => {
      const v = row.mean_hazard || 0
      const cls = v >= 0.5 ? 'text-red-500' : 'text-emerald-600'
      return h('span', { class: cls }, `${(v * 100).toFixed(1)}%`)
    },
  },
  {
    title: '高风险人数',
    key: 'high_risk_users',
    width: 100,
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => row.high_risk_users?.toLocaleString() ?? '—',
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
      const color = destColor(dest)
      return h('span', {
        class: 'inline-flex items-center gap-1',
        style: { color },
      }, destDisplayName(dest))
    },
  },
  {
    title: 'TOP1占比',
    key: 'top_churn_dest1_ratio',
    width: 75,
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => row.top_churn_dest1_ratio != null ? `${((row.top_churn_dest1_ratio || 0) * 100).toFixed(0)}%` : '—',
  },
  {
    title: '流失去向TOP2',
    key: 'top_churn_dest2',
    width: 110,
    align: 'center',
    render: (row) => {
      const dest = row.top_churn_dest2
      if (!dest) return '—'
      const color = destColor(dest)
      return h('span', { style: { color } }, destDisplayName(dest))
    },
  },
  {
    title: '挽回建议',
    key: '挽回建议',
    width: 140,
    align: 'left',
    ellipsis: true,
    render: (row) => maskDestsInText(row.挽回建议, [row.top_churn_dest1, row.top_churn_dest2]),
  },
])

const tableData = computed(() => data.value?.table ?? [])
const suggestionRows = computed(() =>
  (data.value?.operation_suggestions ?? []).map((s) => maskCategoryTokensInText(s)),
)

// ── Sprint 174 XLSX 导出 (Q3) ──
const churnTableXlsxColumns = computed<XlsxColumn[]>(() => [
  { header: '品类', key: 'display_name', width: 14 },
  { header: '本期用户', key: 'current_users', width: 12, numFmt: '#,##0' },
  { header: '上期用户', key: 'previous_users', width: 12, numFmt: '#,##0' },
  { header: '平均风险', key: 'mean_hazard', width: 12, numFmt: '0.0%' },
  { header: '高风险人数', key: 'high_risk_users', width: 12, numFmt: '#,##0' },
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
          <h3 class="text-sm font-semibold text-slate-800 mb-0.5">流失风险散点图</h3>
          <p class="text-[11px] text-slate-500 mb-1">X=规模(log)，Y=平均流失风险，气泡=高风险人数，红=规模大且风险≥50%</p>
          <p class="text-[11px] text-slate-400 mb-3">风险来自距上次购买相对品类回购周期的生存 hazard，RFM 挽留象限加权</p>
          <EChartsWrapper :option="scatterOption" height="300px" />
        </div>
        <div class="col-span-2 bi-card p-4">
          <h3 class="text-sm font-semibold text-slate-800 mb-0.5">各品类平均流失风险</h3>
          <p class="text-[11px] text-slate-500 mb-3">绿色=&lt;50%，红色=≥50%</p>
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
          平均风险=上期购买用户距上次购买相对回购周期的 hazard；高风险=hazard≥0.50；沉默=上期买A本期无订单
        </p>
        <p class="text-[11px] text-slate-400 mb-3">
          品类迁移去向只说明还在买别的东西，判定流失看风险分。迁移细节见流转 Tab。
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
