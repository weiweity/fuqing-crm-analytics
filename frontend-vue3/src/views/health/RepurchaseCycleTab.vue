<script setup lang="ts">
import { computed, toValue, ref, h } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NGrid, NGi, NDataTable } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useFilterStore } from '@/stores/filterStore'
import { fetchRepurchaseCycle, fetchCohortRetention } from '@/api/health'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import YOYBadge from '@/components/YOYBadge.vue'
import ExportToolbar from '@/components/ExportToolbar.vue'
import { BRAND_PRIMARY } from '@/composables/useChartTheme'
import type { EChartTooltipParam, EChartLabelParam } from '@/types/echarts'
import type { XlsxColumn } from '@/utils/exportXlsx'

interface BucketItem {
  bucket_label: string
  user_count: number
  user_ratio: number
  ly_user_count?: number | null
  ly_user_ratio?: number | null
  prev2_user_count?: number | null
  prev2_user_ratio?: number | null
}

interface ProductItem {
  product_class: string
  total_buyers: number
  repurchase_users: number
  repurchase_rate: number
  ly_repurchase_rate?: number | null
  repurchase_rate_yoy?: number | null
  median_days: number
  ly_median_days?: number | null
  median_days_yoy?: number | null
  avg_days?: number | null
  ly_avg_days?: number | null
  avg_days_yoy?: number | null
  p25_days: number
  p75_days: number
  avg_order_value: number
  gsv: number
  ly_gsv?: number | null
  gsv_yoy?: number | null
}

interface HeatmapParam extends EChartLabelParam {
  data: [number, number, number]
}

const filterStore = useFilterStore()
import { LOW_PRICE_CHANNELS } from '@/constants/channels'
const bucketChartRef = ref<InstanceType<typeof EChartsWrapper> | null>(null)
const cohortChartRef = ref<InstanceType<typeof EChartsWrapper> | null>(null)

// 品类表格：简化/展开切换
const isExpanded = ref(false)

const queryParams = computed(() => ({
  start_date: filterStore.dateRange[0],
  end_date: filterStore.dateRange[1],
  channel: filterStore.channel !== '全店' ? filterStore.channel : undefined,
  exclude_channels: filterStore.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined,
}))

// 对比参数：auto_yoy 不传（后端原生 Y-1），auto_mom / custom 传计算后的日期
const compareQueryParams = computed(() => {
  if (filterStore.compareMode === 'auto_yoy') return {}
  const comp = filterStore.compareParams
  if (!comp) return {}
  return { compare_start_date: comp[0], compare_end_date: comp[1] }
})

const { data, isLoading, error, refetch } = useQuery({
  queryKey: computed(() => ['repurchase-cycle', { ...toValue(queryParams) }, toValue(compareQueryParams)]),
  queryFn: () => {
    const p = toValue(queryParams)
    const c = toValue(compareQueryParams)
    return fetchRepurchaseCycle({
      start_date: p.start_date,
      end_date: p.end_date,
      channel: p.channel,
      exclude_channels: p.exclude_channels,
      ...c,
    })
  },
  staleTime: 60_000,
})

// ── Cohort查询（默认最近12个月）─
const cohortParams = computed(() => {
  const end = filterStore.dateRange[1]
  const d = new Date(end)
  d.setMonth(d.getMonth() - 11)
  const start = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
  const endMonth = end.slice(0, 7)
  return {
    start_month: start,
    end_month: endMonth,
    channel: filterStore.channel !== '全店' ? filterStore.channel : undefined,
    exclude_channels: filterStore.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined,
  }
})

const { data: cohortData, isLoading: cohortLoading } = useQuery({
  queryKey: computed(() => ['cohort-retention', { ...cohortParams.value }]),
  queryFn: () => {
    const p = toValue(cohortParams)
    return fetchCohortRetention({
      start_month: p.start_month,
      end_month: p.end_month,
      channel: p.channel,
      exclude_channels: p.exclude_channels,
    })
  },
  staleTime: 60_000,
})

// ── 复购间隔分布：3年对比柱状图 ──
const bucketChartOption = computed(() => {
  if (!data.value?.bucket_distribution?.length) return {}
  const bd = data.value.bucket_distribution
  const yr = data.value.year_label || String(new Date().getFullYear())
  const yr2 = data.value.comp_year_label || String(new Date().getFullYear() - 1)
  const yr3 = data.value.prev2_year_label || String(new Date().getFullYear() - 2)
  const labels = bd.map((r: BucketItem) => r.bucket_label)

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      textStyle: { color: '#0f172a', fontSize: 12 },
      extraCssText: 'box-shadow: 0 4px 12px -2px rgba(0,0,0,0.08); border-radius: 4px;',
      formatter: (params: EChartTooltipParam[]) => {
        let html = `<div class="font-semibold mb-1">${params[0].name}</div>`
        params.forEach((p) => {
          html += `<div class="flex items-center gap-2 text-xs">
            <span class="w-2 h-2 rounded-full" style="background:${p.color}"></span>
            <span class="text-slate-500">${p.seriesName}:</span>
            <span class="font-medium text-slate-800">${(Number(p.value) * 100).toFixed(1)}%</span>
          </div>`
        })
        return html
      },
    },
    legend: {
      data: [`${yr}年`, `${yr2}年`, `${yr3}年`],
      top: 0,
      icon: 'circle',
      itemGap: 16,
      textStyle: { color: '#64748b', fontSize: 11 },
    },
    grid: { left: 12, right: 12, top: 40, bottom: 8 },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 11, interval: 0 },
    },
    yAxis: {
      type: 'value',
      name: '占比',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: '#64748b',
        fontSize: 11,
        formatter: (v: number) => `${(v * 100).toFixed(0)}%`,
      },
      splitLine: { lineStyle: { color: '#e2e8f0', type: [4, 4] } },
    },
    series: [
      {
        name: `${yr}年`,
        type: 'bar',
        data: bd.map((r: BucketItem) => r.user_ratio),
        itemStyle: { color: BRAND_PRIMARY, borderRadius: [3, 3, 0, 0] },
        barGap: '20%',
        label: { show: true, position: 'top', formatter: (p: EChartLabelParam) => `${((p.value as number) * 100).toFixed(1)}%`, fontSize: 10, color: BRAND_PRIMARY },
      },
      {
        name: `${yr2}年`,
        type: 'bar',
        data: bd.map((r: BucketItem) => r.ly_user_ratio),
        itemStyle: { color: '#60a5fa', borderRadius: [3, 3, 0, 0] },
        label: { show: true, position: 'top', formatter: (p: EChartLabelParam) => `${((p.value as number) * 100).toFixed(1)}%`, fontSize: 10, color: '#60a5fa' },
      },
      {
        name: `${yr3}年`,
        type: 'bar',
        data: bd.map((r: BucketItem) => r.prev2_user_ratio),
        itemStyle: { color: '#94a3b8', borderRadius: [3, 3, 0, 0] },
        label: { show: true, position: 'top', formatter: (p: EChartLabelParam) => `${((p.value as number) * 100).toFixed(1)}%`, fontSize: 10, color: '#94a3b8' },
      },
    ],
  }
})

/* ── 天数变化自定义徽章（不×100）── */
function DaysChangeBadge(props: { value: number | null }) {
  const { value } = props
  if (value == null) return h('span', { class: 'text-slate-400' }, '—')
  const sign = value >= 0 ? '+' : ''
  const cls = value >= 0
    ? 'inline-flex items-center px-1 py-0.5 rounded bg-emerald-50 text-emerald-600 text-[11px] font-semibold'
    : 'inline-flex items-center px-1 py-0.5 rounded bg-rose-50 text-rose-600 text-[11px] font-semibold'
  return h('span', { class: cls }, `${sign}${value}天`)
}

// ── Excel 导出列定义 ──
const bucketXlsxColumns: XlsxColumn[] = [
  { header: '复购间隔', key: 'bucket_label', width: 14 },
  { header: '人数', key: 'user_count', width: 10, numFmt: '#,##0' },
  { header: '占比', key: 'user_ratio', width: 10, numFmt: '0.0%' },
]

const productXlsxColumns: XlsxColumn[] = [
  { header: '品类', key: 'product_class', width: 12 },
  { header: '购买人数', key: 'total_buyers', width: 10, numFmt: '#,##0' },
  { header: '复购人数', key: 'repurchase_users', width: 10, numFmt: '#,##0' },
  { header: '复购率', key: 'repurchase_rate', width: 10, numFmt: '0.0%' },
  { header: '去年同期复购率', key: 'ly_repurchase_rate', width: 14, numFmt: '0.0%' },
  { header: '复购率YOY', key: 'repurchase_rate_yoy', width: 12, numFmt: '0.0%' },
  { header: '中位天数', key: 'median_days', width: 10 },
  { header: '去年同期中位天数', key: 'ly_median_days', width: 14 },
  { header: '中位天数YOY', key: 'median_days_yoy', width: 12 },
  { header: '平均天数', key: 'avg_days', width: 10 },
  { header: '去年同期平均天数', key: 'ly_avg_days', width: 14 },
  { header: '平均天数YOY', key: 'avg_days_yoy', width: 12 },
  { header: 'P25', key: 'p25_days', width: 8 },
  { header: 'P75', key: 'p75_days', width: 8 },
  { header: '客单价', key: 'avg_order_value', width: 10, numFmt: '¥#,##0' },
  { header: 'GSV', key: 'gsv', width: 12, numFmt: '¥#,##0' },
  { header: '去年同期GSV', key: 'ly_gsv', width: 14, numFmt: '¥#,##0' },
  { header: 'GSV YOY', key: 'gsv_yoy', width: 10, numFmt: '0.0%' },
]

// ── 简化版列：品类 + 核心指标（10列）──
const simpleColumns: DataTableColumns<ProductItem> = [
  { title: '品类', key: 'product_class', sorter: 'default', width: 130, fixed: 'left', align: 'center' },
  { title: '购买人数', key: 'total_buyers', align: 'center', sorter: 'default', width: 95 },
  { title: '复购人数', key: 'repurchase_users', align: 'center', sorter: 'default', width: 95 },
  {
    title: '复购率',
    key: 'repurchase_rate',
    align: 'center',
    sorter: 'default',
    width: 90,
    render: (row) => `${(row.repurchase_rate * 100).toFixed(1)}%`,
  },
  {
    title: '去年同期复购率',
    key: 'ly_repurchase_rate',
    align: 'center',
    sorter: 'default',
    width: 120,
    render: (row) => row.ly_repurchase_rate != null
      ? `${(row.ly_repurchase_rate * 100).toFixed(1)}%`
      : h('span', { class: 'text-slate-400' }, '—'),
  },
  {
    title: '复购率YOY',
    key: 'repurchase_rate_yoy',
    align: 'center',
    sorter: 'default',
    width: 100,
    render: (row) => h(YOYBadge, { value: row.repurchase_rate_yoy }),
  },
  { title: '中位天数', key: 'median_days', align: 'center', sorter: 'default', width: 95 },
  {
    title: '中位天数YOY',
    key: 'median_days_yoy',
    align: 'center',
    sorter: 'default',
    width: 105,
    render: (row) => h(DaysChangeBadge, { value: row.median_days_yoy ?? null }),
  },
  {
    title: '平均天数',
    key: 'avg_days',
    align: 'center',
    sorter: 'default',
    width: 95,
    render: (row) => row.avg_days != null
      ? `${row.avg_days}`
      : h('span', { class: 'text-slate-400' }, '—'),
  },
  {
    title: '平均天数YOY',
    key: 'avg_days_yoy',
    align: 'center',
    sorter: 'default',
    width: 105,
    render: (row) => h(DaysChangeBadge, { value: row.avg_days_yoy ?? null }),
  },
]

// ── 展开版列：全部指标（18列）──
const expandedColumns: DataTableColumns<ProductItem> = [
  { title: '品类', key: 'product_class', sorter: 'default', width: 120, fixed: 'left', align: 'center' },
  { title: '购买人数', key: 'total_buyers', align: 'center', sorter: 'default', width: 90 },
  { title: '复购人数', key: 'repurchase_users', align: 'center', sorter: 'default', width: 90 },
  {
    title: '复购率',
    key: 'repurchase_rate',
    align: 'center',
    sorter: 'default',
    width: 90,
    render: (row) => `${(row.repurchase_rate * 100).toFixed(1)}%`,
  },
  {
    title: '去年同期复购率',
    key: 'ly_repurchase_rate',
    align: 'center',
    sorter: 'default',
    width: 120,
    render: (row) => row.ly_repurchase_rate != null
      ? `${(row.ly_repurchase_rate * 100).toFixed(1)}%`
      : h('span', { class: 'text-slate-400' }, '—'),
  },
  {
    title: '复购率YOY',
    key: 'repurchase_rate_yoy',
    align: 'center',
    sorter: 'default',
    width: 100,
    render: (row) => h(YOYBadge, { value: row.repurchase_rate_yoy }),
  },
  { title: '中位天数', key: 'median_days', align: 'center', sorter: 'default', width: 95 },
  {
    title: '去年同期中位天数',
    key: 'ly_median_days',
    align: 'center',
    sorter: 'default',
    width: 135,
    render: (row) => row.ly_median_days != null
      ? `${row.ly_median_days}`
      : h('span', { class: 'text-slate-400' }, '—'),
  },
  {
    title: '中位天数YOY',
    key: 'median_days_yoy',
    align: 'center',
    sorter: 'default',
    width: 105,
    render: (row) => h(DaysChangeBadge, { value: row.median_days_yoy ?? null }),
  },
  {
    title: '平均天数',
    key: 'avg_days',
    align: 'center',
    sorter: 'default',
    width: 95,
    render: (row) => row.avg_days != null
      ? `${row.avg_days}`
      : h('span', { class: 'text-slate-400' }, '—'),
  },
  {
    title: '去年同期平均天数',
    key: 'ly_avg_days',
    align: 'center',
    sorter: 'default',
    width: 135,
    render: (row) => row.ly_avg_days != null
      ? `${row.ly_avg_days}`
      : h('span', { class: 'text-slate-400' }, '—'),
  },
  {
    title: '平均天数YOY',
    key: 'avg_days_yoy',
    align: 'center',
    sorter: 'default',
    width: 105,
    render: (row) => h(DaysChangeBadge, { value: row.avg_days_yoy ?? null }),
  },
  { title: 'P25', key: 'p25_days', align: 'center', sorter: 'default', width: 70 },
  { title: 'P75', key: 'p75_days', align: 'center', sorter: 'default', width: 70 },
  {
    title: '客单价',
    key: 'avg_order_value',
    align: 'center',
    sorter: 'default',
    width: 90,
    render: (row) => `¥${row.avg_order_value}`,
  },
  {
    title: 'GSV',
    key: 'gsv',
    align: 'center',
    sorter: 'default',
    width: 100,
    render: (row) => `¥${Math.round(row.gsv).toLocaleString()}`,
  },
  {
    title: '去年同期GSV',
    key: 'ly_gsv',
    align: 'center',
    sorter: 'default',
    width: 115,
    render: (row) => row.ly_gsv != null
      ? `¥${Math.round(row.ly_gsv).toLocaleString()}`
      : h('span', { class: 'text-slate-400' }, '—'),
  },
  {
    title: 'GSV YOY',
    key: 'gsv_yoy',
    align: 'center',
    sorter: 'default',
    width: 90,
    render: (row) => h(YOYBadge, { value: row.gsv_yoy }),
  },
]

// 当前显示的列（根据展开状态切换）
const productColumns = computed<DataTableColumns<ProductItem>>(() =>
  isExpanded.value ? expandedColumns : simpleColumns
)

// 全部品类按购买人数降序排列（TOP10 自然排在最前，其余可滚动查看）
const sortedProducts = computed<ProductItem[]>(() => {
  const list = data.value?.by_product_class ?? []
  return [...list].sort((a, b) => b.total_buyers - a.total_buyers)
})

// ── Cohort热力图配置 ──
const cohortChartOption = computed(() => {
  if (!cohortData.value?.matrix?.length) return {}
  const cd = cohortData.value
  const xData = cd.periods ?? []
  const yData = cd.cohort_months ?? []
  const lyMatrix = cd.ly_matrix || []
  const heatmapData: [number, number, number][] = []

  cd.matrix!.forEach((row, y) => {
    row.forEach((val, x) => {
      if (val != null) {
        heatmapData.push([x, y, val])
      }
    })
  })

  return {
    tooltip: {
      position: 'top',
      formatter: (p: HeatmapParam) => {
        const cohort = yData[p.data[1]] ?? ''
        const period = xData[p.data[0]] ?? ''
        const curRate = p.data[2]
        const lyRate = lyMatrix[p.data[1]]?.[p.data[0]]
        let yoyStr = ''
        if (lyRate != null) {
          const yoy = (curRate - lyRate) * 100
          const sign = yoy >= 0 ? '+' : ''
          const color = yoy >= 0 ? '#dc2626' : '#059669'
          const arrow = yoy >= 0 ? '↑' : '↓'
          yoyStr = `<br/><span style="color:${color}">同比: ${arrow}${sign}${yoy.toFixed(1)}pp</span>`
        }
        return `${cohort} ${period}<br/>留存率: ${(curRate * 100).toFixed(1)}%${yoyStr}`
      },
    },
    grid: { top: 20, right: 20, bottom: 60, left: 100 },
    xAxis: { type: 'category', data: xData, splitArea: { show: true }, name: '周期', nameLocation: 'end' },
    yAxis: {
      type: 'category',
      data: yData,
      splitArea: { show: true },
      name: '首购月份',
      nameLocation: 'end',
      axisLabel: {
        fontSize: 11,
        color: '#1e293b',
        fontWeight: 500,
      },
    },
    visualMap: {
      min: 0,
      max: 1,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 10,
      text: ['高', '低'],
      textStyle: { fontSize: 11, color: '#64748b' },
      inRange: { color: ['#dbeafe', '#93c5fd', '#3b82f6', '#1d4ed8', '#172554'] },
      outOfRange: { color: '#f8fafc' },
    },
    series: [{
      type: 'heatmap',
      data: heatmapData,
      label: {
        show: true,
        formatter: (p: HeatmapParam) => {
          const curRate = p.data[2]
          const lyRate = lyMatrix[p.data[1]]?.[p.data[0]]
          const pctStyle = curRate > 0.5 ? 'pctLight' : 'pctDark'
          const pctStr = `${(curRate * 100).toFixed(0)}%`
          if (lyRate == null) return `{${pctStyle}|${pctStr}}`
          const yoy = (curRate - lyRate) * 100
          const arrowStyle = yoy >= 0 ? 'up' : 'down'
          const arrow = yoy >= 0 ? '↑' : '↓'
          return `{${pctStyle}|${pctStr}} {${arrowStyle}|${arrow}${Math.abs(yoy).toFixed(0)}}`
        },
        rich: {
          pctLight: { fontSize: 10, color: '#fff' },
          pctDark: { fontSize: 10, color: '#334155' },
          up: { fontSize: 9, color: '#dc2626', fontWeight: 'bold' },
          down: { fontSize: 9, color: '#059669', fontWeight: 'bold' },
        },
      },
      emphasis: {
        itemStyle: { borderColor: '#0ea5e9', borderWidth: 2 },
      },
    }],
  }
})
</script>

<template>
  <div class="repurchase-cycle-tab">
    <LoadingState v-if="isLoading" />
    <ErrorState v-else-if="error" :message="error.message" @retry="refetch" />

    <template v-else-if="data">
      <!-- 顶部统计 -->
      <NGrid :cols="4" :x-gap="16" class="mb-4">
        <NGi>
          <div class="bi-card bi-card-hover px-4 py-3 text-center">
            <p class="text-xs text-slate-500">中位复购天数</p>
            <p class="text-2xl font-bold text-slate-900">{{ data.all_store_median_days }}天</p>
            <p class="text-[10px] text-slate-400 mt-1">50%的复购间隔 ≤ 该天数</p>
          </div>
        </NGi>
        <NGi>
          <div class="bi-card bi-card-hover px-4 py-3 text-center">
            <p class="text-xs text-slate-500">P25复购天数</p>
            <p class="text-2xl font-bold text-slate-900">{{ data.all_store_p25_days }}天</p>
            <p class="text-[10px] text-slate-400 mt-1">25%的复购间隔 ≤ 该天数</p>
          </div>
        </NGi>
        <NGi>
          <div class="bi-card bi-card-hover px-4 py-3 text-center">
            <p class="text-xs text-slate-500">P75复购天数</p>
            <p class="text-2xl font-bold text-slate-900">{{ data.all_store_p75_days }}天</p>
            <p class="text-[10px] text-slate-400 mt-1">75%的复购间隔 ≤ 该天数</p>
          </div>
        </NGi>
        <NGi>
          <div class="bi-card bi-card-hover px-4 py-3 text-center">
            <p class="text-xs text-slate-500">平均复购天数</p>
            <p class="text-2xl font-bold text-slate-900">{{ data.all_store_avg_days }}天</p>
            <p class="text-[10px] text-slate-400 mt-1">复购周期内平均复购间隔</p>
          </div>
        </NGi>
      </NGrid>
      <p class="text-[11px] text-slate-400 mb-4">统计口径：排除当天下多单的0天间隔，只计算间隔 ≥ 1天的真实复购</p>

      <!-- 数据区：上下两行， Cohort 有足够高度展示12个月Y轴 -->
      <!-- 第一行：复购间隔分布 -->
      <div class="bi-card p-4 mb-4">
        <div class="flex items-center justify-between mb-3">
          <div>
            <h3 class="text-sm font-semibold text-slate-800 mb-0.5">复购间隔分布</h3>
            <p class="text-[11px] text-slate-500">近几个月已购客，按复购间隔对比3年变化</p>
          </div>
          <ExportToolbar
            :filename="`老客分析_复购间隔分布_${filterStore.dateRange[1]}`"
            :chart-ref="bucketChartRef"
            :columns="bucketXlsxColumns"
            :data="data.bucket_distribution"
            sheet-name="复购间隔"
          />
        </div>
        <EChartsWrapper ref="bucketChartRef" :option="bucketChartOption" height="260px" />
      </div>

      <!-- 第二行：Cohort留存（全宽，给够高度展示12个月Y轴） -->
      <div class="bi-card p-4 mb-4">
        <div class="flex items-center justify-between mb-3">
          <div>
            <h3 class="text-sm font-semibold text-slate-700">Cohort留存</h3>
            <p class="text-[11px] text-slate-400">追踪近12个月首购Cohort在后续每月的复购留存率</p>
          </div>
          <ExportToolbar
            :filename="`老客分析_Cohort留存_${filterStore.dateRange[1]}`"
            :chart-ref="cohortChartRef"
          />
        </div>
        <EChartsWrapper ref="cohortChartRef" :option="cohortChartOption" height="420px" :loading="cohortLoading" />
        <div class="mt-2 text-[10px] text-slate-400 leading-relaxed">
          <span class="font-medium text-slate-500">含义：</span>固定人群（首购月份）的用户在后续每个月的复购比例<br/>
          目的：剔除"人群基数变化"造成的伪增长/伪下降，还原真实的复购黏性<br/>
          <span class="text-slate-300">说明：</span>当前追踪近12个月首购Cohort，X轴最长显示12个周期（M1~M12）；<span class="text-slate-300">举例：</span>2025-01月Cohort有1000人，2025-02月复购200人，则M1留存率=20%
        </div>
      </div>

      <!-- 品类表格 -->
      <div class="bi-card p-4">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2">
            <h3 class="text-sm font-semibold text-slate-700">分品类复购指标</h3>
            <span class="text-[11px] text-slate-400">
              {{ isExpanded ? '全部指标' : '核心指标' }}
            </span>
          </div>
          <div class="flex items-center gap-2">
            <ExportToolbar
              :filename="`老客分析_品类复购_${filterStore.dateRange[1]}`"
              :columns="productXlsxColumns"
              :data="data.by_product_class"
              sheet-name="品类复购"
            />
            <button
              class="px-3 py-1.5 text-sm font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 hover:text-indigo-800 rounded-lg cursor-pointer select-none transition-colors"
              @click="isExpanded = !isExpanded"
            >
              {{ isExpanded ? '收起 ←' : '显示详情 →' }}
            </button>
          </div>
        </div>
        <NDataTable
          :columns="productColumns"
          :data="sortedProducts"
          :pagination="false"
          size="small"
          striped
          :scroll-x="isExpanded ? 1900 : 1000"
          max-height="520"
        />
      </div>
    </template>
  </div>
</template>

<style scoped>
.repurchase-cycle-tab {
  padding-top: 8px;
}
</style>
