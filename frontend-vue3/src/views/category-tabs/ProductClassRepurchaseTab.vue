<script setup lang="ts">
import { computed, toValue, ref, h } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NDataTable } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useFilterStore } from '@/stores/filterStore'
import { fetchRepurchaseCycle } from '@/api/health'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import YOYBadge from '@/components/YOYBadge.vue'
import ExportToolbar from '@/components/ExportToolbar.vue'
import type { XlsxColumn } from '@/utils/exportXlsx'
import { LOW_PRICE_CHANNELS } from '@/constants/channels'

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
  repurchase_order_value?: number
  repurchase_gsv?: number
}

const filterStore = useFilterStore()

// 品类表格：简化/展开切换
const isExpanded = ref(false)

// 品类视图切换：same = 同品类复购周期, cross = 品类买后又回购店铺
const activeView = ref<'same' | 'cross'>('same')

const queryParams = computed(() => ({
  start_date: filterStore.dateRange[0],
  end_date: filterStore.dateRange[1],
  channel: filterStore.channel !== '全店' ? filterStore.channel : undefined,
  exclude_channels: filterStore.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined,
}))

// 对比参数
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

// ── Excel 导出列定义（同品类） ──
const productXlsxColumnsSame: XlsxColumn[] = [
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
  { header: '客单价（含首购）', key: 'avg_order_value', width: 14, numFmt: '¥#,##0' },
  { header: 'GSV（含首购）', key: 'gsv', width: 14, numFmt: '¥#,##0' },
  { header: '去年同期GSV', key: 'ly_gsv', width: 14, numFmt: '¥#,##0' },
  { header: 'GSV YOY', key: 'gsv_yoy', width: 10, numFmt: '0.0%' },
  { header: '复购客单价', key: 'repurchase_order_value', width: 12, numFmt: '¥#,##0' },
  { header: '复购GSV', key: 'repurchase_gsv', width: 12, numFmt: '¥#,##0' },
]

// ── Excel 导出列定义（跨品类回购店铺） ──
const productXlsxColumnsCross: XlsxColumn[] = [
  { header: '品类', key: 'product_class', width: 12 },
  { header: '购买人数', key: 'total_buyers', width: 10, numFmt: '#,##0' },
  { header: '回购人数', key: 'repurchase_users', width: 10, numFmt: '#,##0' },
  { header: '回购率', key: 'repurchase_rate', width: 10, numFmt: '0.0%' },
  { header: '去年同期回购率', key: 'ly_repurchase_rate', width: 14, numFmt: '0.0%' },
  { header: '回购率YOY', key: 'repurchase_rate_yoy', width: 12, numFmt: '0.0%' },
  { header: '中位天数', key: 'median_days', width: 10 },
  { header: '去年同期中位天数', key: 'ly_median_days', width: 14 },
  { header: '中位天数YOY', key: 'median_days_yoy', width: 12 },
  { header: '平均天数', key: 'avg_days', width: 10 },
  { header: '去年同期平均天数', key: 'ly_avg_days', width: 14 },
  { header: '平均天数YOY', key: 'avg_days_yoy', width: 12 },
  { header: 'P25', key: 'p25_days', width: 8 },
  { header: 'P75', key: 'p75_days', width: 8 },
  { header: '入口客单价（首购）', key: 'avg_order_value', width: 16, numFmt: '¥#,##0' },
  { header: '入口GSV（首购）', key: 'gsv', width: 16, numFmt: '¥#,##0' },
  { header: '去年同期GSV', key: 'ly_gsv', width: 14, numFmt: '¥#,##0' },
  { header: 'GSV YOY', key: 'gsv_yoy', width: 10, numFmt: '0.0%' },
  { header: '回流客单价', key: 'repurchase_order_value', width: 14, numFmt: '¥#,##0' },
  { header: '回流GSV', key: 'repurchase_gsv', width: 14, numFmt: '¥#,##0' },
]

const productXlsxColumns = computed<XlsxColumn[]>(() =>
  activeView.value === 'same' ? productXlsxColumnsSame : productXlsxColumnsCross
)

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
    title: '客单价（含首购）',
    key: 'avg_order_value',
    align: 'center',
    sorter: 'default',
    width: 110,
    render: (row) => `¥${row.avg_order_value}`,
  },
  {
    title: 'GSV（含首购）',
    key: 'gsv',
    align: 'center',
    sorter: 'default',
    width: 110,
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
  {
    title: '复购客单价',
    key: 'repurchase_order_value',
    align: 'center',
    sorter: 'default',
    width: 100,
    render: (row) => `¥${row.repurchase_order_value ?? 0}`,
  },
  {
    title: '复购GSV',
    key: 'repurchase_gsv',
    align: 'center',
    sorter: 'default',
    width: 100,
    render: (row) => `¥${Math.round(row.repurchase_gsv ?? 0).toLocaleString()}`,
  },
]

// ── 展开版列：跨品类回购店铺（18列）──
const expandedColumnsCross: DataTableColumns<ProductItem> = [
  { title: '品类', key: 'product_class', sorter: 'default', width: 120, fixed: 'left', align: 'center' },
  { title: '购买人数', key: 'total_buyers', align: 'center', sorter: 'default', width: 90 },
  { title: '回购人数', key: 'repurchase_users', align: 'center', sorter: 'default', width: 90 },
  {
    title: '回购率',
    key: 'repurchase_rate',
    align: 'center',
    sorter: 'default',
    width: 90,
    render: (row) => `${(row.repurchase_rate * 100).toFixed(1)}%`,
  },
  {
    title: '去年同期回购率',
    key: 'ly_repurchase_rate',
    align: 'center',
    sorter: 'default',
    width: 120,
    render: (row) => row.ly_repurchase_rate != null
      ? `${(row.ly_repurchase_rate * 100).toFixed(1)}%`
      : h('span', { class: 'text-slate-400' }, '—'),
  },
  {
    title: '回购率YOY',
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
    title: '入口客单价（首购）',
    key: 'avg_order_value',
    align: 'center',
    sorter: 'default',
    width: 130,
    render: (row) => `¥${row.avg_order_value}`,
  },
  {
    title: '入口GSV（首购）',
    key: 'gsv',
    align: 'center',
    sorter: 'default',
    width: 130,
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
  {
    title: '回流客单价',
    key: 'repurchase_order_value',
    align: 'center',
    sorter: 'default',
    width: 110,
    render: (row) => `¥${row.repurchase_order_value ?? 0}`,
  },
  {
    title: '回流GSV',
    key: 'repurchase_gsv',
    align: 'center',
    sorter: 'default',
    width: 110,
    render: (row) => `¥${Math.round(row.repurchase_gsv ?? 0).toLocaleString()}`,
  },
]

// 当前显示的列（根据视图 + 展开状态切换）
const productColumns = computed<DataTableColumns<ProductItem>>(() => {
  if (activeView.value === 'cross') {
    return isExpanded.value ? expandedColumnsCross : simpleColumns
  }
  return isExpanded.value ? expandedColumns : simpleColumns
})

// 全部品类按购买人数降序排列
const sortedProducts = computed<ProductItem[]>(() => {
  const list = data.value?.by_product_class ?? []
  return [...list].sort((a, b) => b.total_buyers - a.total_buyers)
})

// 跨品类回购店铺数据
const sortedCrossProducts = computed<ProductItem[]>(() => {
  const list = (data.value as any)?.by_product_class_return ?? []
  return [...list].sort((a, b) => b.total_buyers - a.total_buyers)
})

// 当前视图数据
const currentProducts = computed<ProductItem[]>(() =>
  activeView.value === 'same' ? sortedProducts.value : sortedCrossProducts.value
)

const currentViewTitle = computed(() =>
  activeView.value === 'same' ? '同品类复购周期' : '品类买后又回购店铺'
)

const currentExportFilename = computed(() =>
  activeView.value === 'same'
    ? `品类看板_同品类复购_${filterStore.dateRange[1]}`
    : `品类看板_品类回购店铺_${filterStore.dateRange[1]}`
)

const currentSheetName = computed(() =>
  activeView.value === 'same' ? '同品类复购' : '品类回购店铺'
)
</script>

<template>
  <div>
    <LoadingState v-if="isLoading" />
    <ErrorState v-else-if="error" :message="error.message" @retry="refetch" />

    <template v-else-if="data">
      <div class="bi-card p-4">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2">
            <h3 class="text-sm font-semibold text-slate-700">{{ currentViewTitle }}</h3>
            <span class="text-[11px] text-slate-400">
              {{ isExpanded ? '全部指标' : '核心指标' }}
            </span>
          </div>
          <div class="flex items-center gap-2">
            <ExportToolbar
              :filename="currentExportFilename"
              :columns="productXlsxColumns"
              :data="activeView === 'same' ? data.by_product_class : (data as any).by_product_class_return"
              :sheet-name="currentSheetName"
            />
            <div class="flex items-center bg-slate-100 rounded-lg p-0.5">
              <button
                class="px-3 py-1.5 text-xs font-medium rounded-md cursor-pointer select-none transition-colors"
                :class="activeView === 'same' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
                @click="activeView = 'same'"
              >
                同品类复购
              </button>
              <button
                class="px-3 py-1.5 text-xs font-medium rounded-md cursor-pointer select-none transition-colors"
                :class="activeView === 'cross' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
                @click="activeView = 'cross'"
              >
                品类买后又回购店铺
              </button>
            </div>
          </div>
        </div>

        <!-- 数据逻辑备注（根据视图切换） -->
        <div class="mb-3 space-y-1">
          <template v-if="activeView === 'same'">
            <p class="text-[11px] text-slate-400 leading-relaxed">
              <span class="text-slate-300">*</span> 复购判定：该品类下订单数 ≥ 2 即算复购用户（当天多单去重），复购率 = 复购人数 / 购买人数
            </p>
            <p class="text-[11px] text-slate-400 leading-relaxed">
              <span class="text-slate-300">*</span> 复购间隔：按天去重后计算相邻购买间隔（当天多单合并为一天）
            </p>
            <p class="text-[11px] text-slate-400 leading-relaxed">
              <span class="text-slate-300">*</span> 客单价（含首购）= 该品类所有订单金额 / 所有订单数；复购客单价 = 复购订单金额 / 复购订单数（仅第2单及以后）
            </p>
            <p class="text-[11px] text-slate-400 leading-relaxed">
              <span class="text-slate-300">*</span> GSV（含首购）= 该品类所有订单金额汇总；复购GSV = 复购订单金额汇总
            </p>
          </template>
          <template v-else>
            <p class="text-[11px] text-slate-400 leading-relaxed">
              <span class="text-slate-300">*</span> 回购判定：首购该品类后，周期内有任意后续购买（含同品类/跨品类，不含当天）即算回购用户，回购率 = 回购人数 / 购买人数
            </p>
            <p class="text-[11px] text-slate-400 leading-relaxed">
              <span class="text-slate-300">*</span> 回购间隔：从首购该品类到下一次任意购买的间隔，按天去重后计算（当天多单合并为一天）
            </p>
            <p class="text-[11px] text-slate-400 leading-relaxed">
              <span class="text-slate-300">*</span> 客单价/GSV：该品类的入口价值（全部订单）；回流客单价/回流GSV = 首购后全店后续购买的均值/汇总
            </p>
          </template>
          <p class="text-[11px] text-slate-400 leading-relaxed">
            <span class="text-slate-300">*</span> 当筛选渠道时，上述全部逻辑在对应渠道范围内计算（含对比期）
          </p>
        </div>

        <div class="flex justify-end mb-2">
          <button
            class="px-3 py-1 text-xs font-medium text-slate-500 bg-slate-50 hover:bg-slate-100 hover:text-slate-700 rounded cursor-pointer select-none transition-colors"
            @click="isExpanded = !isExpanded"
          >
            {{ isExpanded ? '收起详情 ←' : '展开详情 →' }}
          </button>
        </div>
        <NDataTable
          :columns="productColumns"
          :data="currentProducts"
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
