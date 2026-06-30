<script setup lang="ts">
import { computed, h, toValue, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NTooltip, NTabs } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useFilterStore } from '@/stores/filterStore'
import { fetchCategoryValueTier } from '@/api/category'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import DataTablePro from '@/components/DataTablePro.vue'
import ExportToolbar from '@/components/ExportToolbar.vue'
import type { XlsxColumn } from '@/utils/exportXlsx'

const WINDOW_LABELS: Record<string, string> = {
  default: '当前周期',
  '30d': '近30天',
  '90d': '近90天',
  all: '全部历史',
}

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
  queryKey: computed(() => ['category-value-tier', { ...toValue(queryParams) }]),
  queryFn: () => fetchCategoryValueTier(toValue(queryParams)),
  staleTime: 60_000,
})

// ─── 双轴折线图: 羊毛党占比 + 高价值占比 ───────────────────────
const dualAxisOption = computed(() => {
  if (!data.value?.dual_axis_line) return {}
  const { categories, wool_party_ratios, high_value_ratios } = data.value.dual_axis_line
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line' },
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      padding: [10, 14],
      textStyle: { color: '#0f172a', fontSize: 12 },
      extraCssText: 'box-shadow: 0 4px 12px -2px rgba(0,0,0,0.08); border-radius: 4px;',
      formatter: (params: any[]) => {
        return params.map((p) => `${p.marker} ${p.seriesName}: ${(p.value * 100).toFixed(1)}%`).join('<br/>')
      },
    },
    legend: {
      data: ['羊毛党占比', '高价值占比'],
      bottom: 0,
      icon: 'circle',
      itemGap: 16,
      textStyle: { color: '#64748b', fontSize: 11 },
    },
    grid: { left: 48, right: 48, top: 16, bottom: 80 },
    xAxis: {
      type: 'category',
      data: categories,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 10, margin: 12, rotate: 40, interval: 0 },
    },
    yAxis: [
      {
        type: 'value',
        name: '羊毛党占比',
        nameTextStyle: { color: '#64748b', fontSize: 10 },
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: '#ef4444', fontSize: 11, formatter: (v: number) => `${v.toFixed(0)}%` },
        splitLine: { lineStyle: { color: '#e5edf5', type: [4, 4] } },
      },
      {
        type: 'value',
        name: '高价值占比',
        nameTextStyle: { color: '#64748b', fontSize: 10 },
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: '#533afd', fontSize: 11, formatter: (v: number) => `${v.toFixed(0)}%` },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '羊毛党占比',
        type: 'line',
        yAxisIndex: 0,
        data: wool_party_ratios.map((v) => parseFloat((v * 100).toFixed(2))),
        itemStyle: { color: '#ef4444' },
        lineStyle: { color: '#ef4444', width: 2 },
        smooth: false,
        symbol: 'circle',
        symbolSize: 5,
      },
      {
        name: '高价值占比',
        type: 'line',
        yAxisIndex: 1,
        data: high_value_ratios.map((v) => parseFloat((v * 100).toFixed(2))),
        itemStyle: { color: '#533afd' },
        lineStyle: { color: '#533afd', width: 2 },
        smooth: false,
        symbol: 'circle',
        symbolSize: 5,
      },
    ],
  }
})

// ─── Table ───────────────────────────────────────────────────────
const GRADE_COLORS: Record<string, string> = {
  A: 'text-emerald-600 font-bold',
  B: 'text-blue-600 font-semibold',
  C: 'text-amber-600 font-semibold',
  D: 'text-orange-600',
  E: 'text-red-500',
  '样本不足': 'text-slate-400 text-[11px]',
}

const tableColumns = computed<DataTableColumns<any>>(() => [
  {
    title: '品类',
    key: 'category_name',
    width: 120,
    fixed: 'left',
    align: 'center',
  },
  {
    title: '总人数',
    key: 'total_users',
    width: 90,
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => row.total_users?.toLocaleString() ?? '—',
  },
  {
    title: '高价值人数',
    key: 'high_value_users',
    width: 100,
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => row.high_value_users?.toLocaleString() ?? '—',
  },
  {
    title: '高价值占比',
    key: 'high_value_ratio',
    width: 100,
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => `${((row.high_value_ratio || 0) * 100).toFixed(1)}%`,
  },
  {
    title: '羊毛党-T1',
    key: 'wool_type1',
    width: 100,
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => {
      const t1 = row.wool_party?.type1_count ?? 0
      const t1r = (row.wool_party?.type1_ratio || 0) * 100
      return `${t1.toLocaleString()} (${t1r.toFixed(1)}%)`
    },
  },
  {
    title: '羊毛党-T2',
    key: 'wool_type2',
    width: 100,
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => {
      const t2 = row.wool_party?.type2_count ?? 0
      const t2r = (row.wool_party?.type2_ratio || 0) * 100
      return `${t2.toLocaleString()} (${t2r.toFixed(1)}%)`
    },
  },
  {
    title: '会员占比',
    key: 'member_ratio',
    width: 90,
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => `${((row.member_ratio || 0) * 100).toFixed(1)}%`,
  },
  {
    title: '平均AUS',
    key: 'avg_aus',
    width: 90,
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => row.avg_aus != null ? `¥${row.avg_aus.toFixed(0)}` : '—',
  },
  {
    title: '价值评分',
    key: 'value_score',
    width: 90,
    align: 'center',
    className: 'bi-cell-number',
    render: (row) => row.value_grade === '样本不足' ? '—' : (row.value_score?.toFixed(1) ?? '—'),
  },
  {
    title: '等级',
    key: 'value_grade',
    width: 70,
    align: 'center',
    render: (row) => {
      const grade = row.value_grade || 'E'
      const display = grade === '样本不足' ? '—' : grade
      return h('span', { class: GRADE_COLORS[grade] || 'text-slate-500' }, display)
    },
  },
])

const activeWindow = ref<string>('default')

const windowOptions = computed(() => {
  const keys = data.value?.wool_party_by_window ? Object.keys(data.value.wool_party_by_window) : []
  return keys.map(k => ({ label: WINDOW_LABELS[k] || k, value: k }))
})

const tableData = computed(() => data.value?.table ?? [])

// 多窗口羊毛党表格数据
const windowTableData = computed(() => {
  if (!data.value?.wool_party_by_window) return []
  return data.value.wool_party_by_window[activeWindow.value] ?? []
})

// ── Sprint 174 XLSX 导出 (Q3, 2 张表共用 columns) ──
const valueTierXlsxColumns = computed<XlsxColumn[]>(() => [
  { header: '品类', key: 'category_name', width: 14 },
  { header: '总人数', key: 'total_users', width: 12, numFmt: '#,##0' },
  { header: '高价值人数', key: 'high_value_users', width: 14, numFmt: '#,##0' },
  { header: '高价值占比', key: 'high_value_ratio', width: 14, numFmt: '0.0%' },
  { header: '羊毛党-T1', key: 'wool_type1_count', width: 14, numFmt: '#,##0' },
  { header: '羊毛党-T1率', key: 'wool_type1_ratio', width: 14, numFmt: '0.0%' },
  { header: '羊毛党-T2', key: 'wool_type2_count', width: 14, numFmt: '#,##0' },
  { header: '羊毛党-T2率', key: 'wool_type2_ratio', width: 14, numFmt: '0.0%' },
  { header: '会员占比', key: 'member_ratio', width: 12, numFmt: '0.0%' },
  { header: '平均AUS', key: 'avg_aus', width: 12, numFmt: '¥#,##0' },
  { header: '价值评分', key: 'value_score', width: 12, numFmt: '0.0' },
  { header: '等级', key: 'value_grade', width: 8 },
])
function flattenValueTierRow(row: any): any {
  return {
    category_name: row.category_name,
    total_users: row.total_users,
    high_value_users: row.high_value_users,
    high_value_ratio: row.high_value_ratio,
    wool_type1_count: row.wool_party?.type1_count,
    wool_type1_ratio: row.wool_party?.type1_ratio,
    wool_type2_count: row.wool_party?.type2_count,
    wool_type2_ratio: row.wool_party?.type2_ratio,
    member_ratio: row.member_ratio,
    avg_aus: row.avg_aus,
    value_score: row.value_score,
    value_grade: row.value_grade,
  }
}
const valueTierXlsxData = computed(() => tableData.value.map(flattenValueTierRow))
const windowValueTierXlsxData = computed(() => windowTableData.value.map(flattenValueTierRow))
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
      <!-- 双轴折线图: 羊毛党 vs 高价值占比 -->
      <div class="bi-card p-4">
        <h3 class="text-sm font-semibold text-slate-800 mb-0.5">羊毛党占比 vs 高价值占比</h3>
        <p class="text-[11px] text-slate-500 mb-1">红色系=羊毛党占比(T1+T2)，蓝色系=高价值占比(Champions+Loyal)</p>
        <p class="text-[11px] text-slate-400 mb-3">一眼看出哪些品类用户质量高、哪些品类薅羊毛严重——红高蓝低的品类需警惕</p>
        <EChartsWrapper :option="dualAxisOption" height="300px" />
      </div>

      <!-- 价值评分表 -->
      <div class="bi-card p-4">
        <div class="flex items-center justify-between mb-0.5">
          <h3 class="text-sm font-semibold text-slate-800">价值评分表</h3>
          <ExportToolbar
            :filename="`价值评分表_${filterStore.dateRange[0]}_${filterStore.dateRange[1]}`"
            :columns="valueTierXlsxColumns"
            :data="valueTierXlsxData as any[]"
            sheet-name="价值评分"
          />
        </div>
        <p class="text-[11px] text-slate-500 mb-1">
          各品类用户质量综合评估：高价值占比越高越好，羊毛党占比越低越好
        </p>
        <p class="text-[11px] text-slate-400 mb-3">
          A档品类值得加大资源投入，E档品类需要优化人群结构——评分 = 高价值排名×0.4 + (100-羊毛党排名)×0.3 + 会员占比排名×0.2 + AUS排名×0.1
        </p>
        <DataTablePro
          :columns="tableColumns"
          :data="tableData"
          :pagination="{ pageSize: 10 }"
          :scroll-x="1000"
        />
        <!-- 指标定义 -->
        <div class="mt-3 pt-3 border-t border-slate-100">
          <p class="text-[11px] text-slate-400 leading-relaxed">
            <span class="font-medium text-slate-500">指标定义：</span>
            高价值占比 = RFM Champions(最近购买+高频+高金额) + Loyal(较远购买+高频+高金额) 的用户数占比  |
            羊毛党-T1 = 历史上买过正装、窗口期内100%买小样的用户数  |
            羊毛党-T2 = 历史上从未买正装、窗口期内100%买小样的用户数  |
            价值评分 = 高价值排名×0.4 + (100-羊毛党排名)×0.3 + 会员占比排名×0.2 + AUS排名×0.1
          </p>
          <p class="text-[11px] text-slate-400 leading-relaxed mt-1">
            <span class="text-amber-500">⚠️</span>
            羊毛党统计基于渠道分类(U先派样/百补派样/赠品&0.01=小样)，<span class="font-medium text-slate-500">不受"剔除低价"筛选影响</span>。
            用户数&lt;100的品类标记为"样本不足"，不参与评分排名。
          </p>
        </div>
      </div>

      <!-- 多窗口羊毛党对比 -->
      <div v-if="data?.wool_party_by_window" class="bi-card p-4">
        <div class="flex items-center justify-between mb-3">
          <div>
            <h3 class="text-sm font-semibold text-slate-800 mb-0.5">羊毛党多窗口对比</h3>
            <p class="text-[11px] text-slate-500">切换时间窗口查看羊毛党变化趋势</p>
            <p class="text-[11px] text-slate-400 mt-0.5">30天vs90天vs全部历史——如果近30天羊毛党占比明显高于长期均值，说明近期低价渠道引入了过多低质量用户</p>
          </div>
          <div class="flex items-center gap-2">
            <n-tabs
              v-model:value="activeWindow"
              type="segment"
              size="small"
              :options="windowOptions"
              style="width: 280px"
            />
            <ExportToolbar
              :filename="`羊毛党多窗口_${activeWindow}_${filterStore.dateRange[0]}_${filterStore.dateRange[1]}`"
              :columns="valueTierXlsxColumns"
              :data="windowValueTierXlsxData as any[]"
              sheet-name="羊毛党多窗口"
            />
          </div>
        </div>
        <DataTablePro
          :columns="tableColumns"
          :data="windowTableData"
          :pagination="{ pageSize: 10 }"
          :scroll-x="1000"
        />
      </div>
    </template>

    <EmptyState v-else description="暂无数据" />
  </div>
</template>
