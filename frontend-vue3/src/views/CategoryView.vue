<script setup lang="ts">
import { computed, toValue, h, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NGrid, NGi, NTabs, NTabPane } from 'naive-ui'
import BaseStyleButton from '@/components/BaseStyleButton.vue'
import type { DataTableColumns } from 'naive-ui'
import { useFilterStore } from '@/stores/filterStore'
import {
  fetchCategoryOverview,
  fetchCategoryDistribution,
  type CategoryOverviewItem,
  type CategoryDistributionItem,
} from '@/api/category'
import MetricCard from '@/components/MetricCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import YOYGuard from '@/components/YOYGuard.vue'
import RatioConventionBanner from '@/components/RatioConventionBanner.vue'
import DataTablePro from '@/components/DataTablePro.vue'
import ExportToolbar from '@/components/ExportToolbar.vue'
import type { XlsxColumn } from '@/utils/exportXlsx'
import { CHART_COLORS } from '@/composables/useChartTheme'
import ValueTierTab from './category-tabs/ValueTierTab.vue'
import CategoryFlowTab from './category-tabs/CategoryFlowTab.vue'
import MarketBasketTab from './category-tabs/MarketBasketTab.vue'
import ChurnWarningTab from './category-tabs/ChurnWarningTab.vue'
import CategoryRepurchaseTab from './category-tabs/CategoryRepurchaseTab.vue'
import ProductClassRepurchaseTab from './category-tabs/ProductClassRepurchaseTab.vue'
import { useRouteHashTab } from '@/composables/useRouteHashTab'

const filterStore = useFilterStore()
const activeTab = ref('overview')
useRouteHashTab(activeTab, ['overview', 'association', 'product-repurchase', 'repurchase', 'flow', 'wool', 'risk'])

import { LOW_PRICE_CHANNELS } from '@/constants/channels'

const queryParams = computed(() => ({
  start_date: filterStore.dateRange[0],
  end_date: filterStore.dateRange[1],
  level: 'class',
  metric_type: 'GSV',
  channel: filterStore.channel === '全店' ? undefined : filterStore.channel,
  exclude_channels: filterStore.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined,
}))

const {
  data: overviewData,
  isLoading: overviewLoading,
  error: overviewError,
  refetch: overviewRefetch,
} = useQuery({
  queryKey: computed(() => ['category-overview', { ...toValue(queryParams) }, filterStore.compareParams]),
  queryFn: () => {
    const p = toValue(queryParams)
    const comp = filterStore.compareParams
    return fetchCategoryOverview({
      start_date: p.start_date,
      end_date: p.end_date,
      level: p.level,
      metric_type: p.metric_type,
      channel: p.channel,
      exclude_channels: p.exclude_channels,
      compare_start_date: comp ? comp[0] : undefined,
      compare_end_date: comp ? comp[1] : undefined,
    })
  },
  staleTime: 60_000,
})

const distributionParams = computed(() => {
  const start = new Date(filterStore.dateRange[0])
  const end = new Date(filterStore.dateRange[1])
  const lookback_days = Math.round((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24))
  return {
    date: filterStore.dateRange[1],
    lookback_days,
    level: 'class',
    channel: filterStore.channel === '全店' ? undefined : filterStore.channel,
    exclude_channels: filterStore.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined,
  }
})

const {
  data: distributionData,
  isLoading: distributionLoading,
  error: distributionError,
  refetch: distributionRefetch,
} = useQuery({
  queryKey: computed(() => ['category-distribution', { ...toValue(distributionParams) }]),
  queryFn: () => {
    const p = toValue(distributionParams)
    return fetchCategoryDistribution({ date: p.date, lookback_days: p.lookback_days, level: p.level, channel: p.channel, exclude_channels: p.exclude_channels })
  },
  staleTime: 60_000,
})

// 品类列表（用于回购分析下拉框）
const categoryOptions = computed(() => {
  if (!distributionData.value?.distribution) return []
  return distributionData.value.distribution.map((d) => d.name)
})


// ─── 品类运营视角 KPI ──────────────────────────────────────────
const newCustomerGsvRatio = computed(() => {
  const ttl = overviewData.value?.all_ttl
  if (!ttl || !ttl.gsv) return '—'
  return `${(ttl.new_gsv / ttl.gsv * 100).toFixed(1)}%`
})

const top3GsvRatio = computed(() => {
  if (!sortedDistribution.value.length) return '—'
  const top3 = sortedDistribution.value.slice(0, 3)
  const top3Gsv = top3.reduce((sum, d) => sum + d.gmv, 0)
  return `${(top3Gsv / distributionData.value!.total_gmv * 100).toFixed(1)}%`
})

const topPenetration = computed(() => {
  const items = distributionData.value?.distribution
  if (!items?.length) return '—'
  const top = [...items].sort((a, b) => b.penetration_rate - a.penetration_rate)[0]
  return `${top.name} ${(top.penetration_rate * 100).toFixed(1)}%`
})

const topGsvCategory = computed(() => {
  const items = sortedDistribution.value
  if (!items?.length) return '—'
  const top = items[0]
  return `${top.name} ¥${(top.gmv / 10000).toFixed(1)}万`
})

// 按GSV降序排序的品类分布（饼图和表格统一使用）
const sortedDistribution = computed(() => {
  if (!distributionData.value?.distribution) return []
  return [...distributionData.value.distribution].sort((a, b) => b.gmv - a.gmv)
})

const top1GsvPct = computed(() => {
  const items = sortedDistribution.value
  if (!items?.length || !distributionData.value?.total_gmv) return '—'
  return `${(items[0].gmv / distributionData.value.total_gmv * 100).toFixed(1)}%`
})

const pieChartOption = computed(() => {
  if (!distributionData.value) return {}
  const items = sortedDistribution.value.slice(0, 10)
  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      padding: [10, 12],
      textStyle: { color: '#0f172a', fontSize: 12 },
      extraCssText: 'box-shadow: 0 4px 12px -2px rgba(0,0,0,0.08); border-radius: 4px;',
      formatter: (params: { name: string; value: number; percent: number }) => {
        return `${params.name}<br/>GSV: ¥${(params.value / 10000).toFixed(1)}万 (${params.percent}%)`
      },
    },
    legend: {
      type: 'scroll',
      orient: 'vertical',
      right: 10,
      top: 20,
      bottom: 20,
      icon: 'circle',
      itemGap: 10,
      textStyle: { color: '#64748b', fontSize: 11 },
    },
    color: CHART_COLORS,
    series: [
      {
        name: '品类GSV',
        type: 'pie',
        radius: ['40%', '65%'],
        center: ['35%', '50%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
        label: {
          show: true,
          position: 'outside',
          formatter: (params: any) => `${params.name}\n${params.percent}%`,
          fontSize: 10,
          color: '#64748b',
          lineHeight: 14,
        },
        emphasis: {
          label: { show: true, fontSize: 12, fontWeight: 'bold', color: '#0f172a' },
        },
        labelLine: { show: true, length: 10, length2: 8, lineStyle: { color: '#cbd5e1' } },
        data: items.map((item: CategoryDistributionItem) => ({ name: item.name, value: item.gmv })),
      },
    ],
  }
})

// ─── 表格列定义 ──────────────────────────────────────────────────
type SubCol = { title: string; key: string; width: number; align: 'left' | 'center' | 'right'; className?: string; sorter?: any; render?: any }

function gsvChildren(valKey: string, yoyKey: string): SubCol[] {
  return [
    {
      title: 'GSV',
      key: valKey,
      width: 105,
      align: 'center',
      className: 'bi-cell-number',
      sorter: (a: any, b: any) => (a[valKey] ?? 0) - (b[valKey] ?? 0),
      render: (row: any) => `¥${((row[valKey] || 0) / 10000).toFixed(1)}万`,
    },
    {
      title: 'YOY',
      key: yoyKey,
      width: 85,
      align: 'center',
      sorter: (a: any, b: any) => (a[yoyKey] ?? 0) - (b[yoyKey] ?? 0),
      render: (row: any) => h(YOYGuard, { value: row[yoyKey], styled: true}),
    },
  ]
}

function usersChildren(valKey: string, yoyKey: string): SubCol[] {
  return [
    {
      title: '人数',
      key: valKey,
      width: 90,
      align: 'center',
      className: 'bi-cell-number',
      sorter: (a: any, b: any) => (a[valKey] ?? 0) - (b[valKey] ?? 0),
      render: (row: any) => ((row[valKey] || 0)).toLocaleString(),
    },
    {
      title: 'YOY',
      key: yoyKey,
      width: 85,
      align: 'center',
      sorter: (a: any, b: any) => (a[yoyKey] ?? 0) - (b[yoyKey] ?? 0),
      render: (row: any) => h(YOYGuard, { value: row[yoyKey], styled: true}),
    },
  ]
}

function ausChildren(valKey: string, yoyKey: string): SubCol[] {
  return [
    {
      title: 'AUS',
      key: valKey,
      width: 85,
      align: 'center',
      className: 'bi-cell-number',
      sorter: (a: any, b: any) => (a[valKey] ?? 0) - (b[valKey] ?? 0),
      render: (row: any) => `¥${((row[valKey] || 0)).toFixed(1)}`,
    },
    {
      title: 'YOY',
      key: yoyKey,
      width: 85,
      align: 'center',
      sorter: (a: any, b: any) => (a[yoyKey] ?? 0) - (b[yoyKey] ?? 0),
      render: (row: any) => h(YOYGuard, { value: row[yoyKey], styled: true}),
    },
  ]
}

function ratioChildren(valKey: string, yoyKey: string): SubCol[] {
  return [
    {
      title: '占比',
      key: valKey,
      width: 80,
      align: 'center',
      className: 'bi-cell-number',
      sorter: (a: any, b: any) => (a[valKey] ?? 0) - (b[valKey] ?? 0),
      render: (row: any) => `${(((row[valKey] || 0)) * 100).toFixed(1)}%`,
    },
    {
      title: 'YOY',
      key: yoyKey,
      width: 85,
      align: 'center',
      sorter: (a: any, b: any) => (a[yoyKey] ?? 0) - (b[yoyKey] ?? 0),
      render: (row: any) => h(YOYGuard, { value: row[yoyKey], unit: 'pp', styled: true}),
    },
  ]
}

/** 给一组列的第一个 child 加 group-sep 分隔线类名 */
function addGroupSep(cols: SubCol[]): SubCol[] {
  return cols.map((col, i) =>
    i === 0 ? { ...col, className: [col.className || '', 'group-sep'].join(' ') } : col
  )
}

// ─── 单品概览列模式切换（各自独立）──────────────────────────────────
const showDetailAll = ref(false)
const showDetailMember = ref(false)

// 精简列：产品分类 + 全店GSV/YOY + 老客GSV/YOY/占比 + 新客GSV/YOY/占比
const compactColumns: DataTableColumns<CategoryOverviewItem> = [
  {
    title: '产品分类',
    key: 'name',
    width: 120,
    fixed: 'left',
    align: 'center',
    sorter: 'default',
  },
  {
    title: '全店',
    key: 'all_group',
    align: 'center',
    children: [
      ...gsvChildren('gsv', 'gsv_yoy'),
    ],
  },
  {
    title: '老客',
    key: 'old_group',
    align: 'center',
    children: [
      ...addGroupSep(gsvChildren('old_gsv', 'old_gsv_yoy')),
      ...ratioChildren('old_ratio', 'old_ratio_yoy'),
    ],
  },
  {
    title: '新客',
    key: 'new_group',
    align: 'center',
    children: [
      ...addGroupSep(gsvChildren('new_gsv', 'new_gsv_yoy')),
      ...ratioChildren('new_ratio', 'new_ratio_yoy'),
    ],
  },
]

// 精简列（会员）
const compactMemberColumns: DataTableColumns<CategoryOverviewItem> = [
  {
    title: '产品分类',
    key: 'name',
    width: 120,
    fixed: 'left',
    align: 'center',
    sorter: 'default',
  },
  {
    title: '全店',
    key: 'all_group',
    align: 'center',
    children: [
      ...gsvChildren('gsv', 'gsv_yoy'),
      {
        title: '会员占比',
        key: 'member_ratio',
        width: 80,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: any, b: any) => (a['member_ratio'] ?? 0) - (b['member_ratio'] ?? 0),
        render: (row: any) => `${(((row['member_ratio'] || 0)) * 100).toFixed(1)}%`,
      },
      {
        title: 'YOY',
        key: 'member_ratio_yoy',
        width: 85,
        align: 'center',
        sorter: (a: any, b: any) => (a['member_ratio_yoy'] ?? 0) - (b['member_ratio_yoy'] ?? 0),
        render: (row: any) => h(YOYGuard, { value: row['member_ratio_yoy'], unit: 'pp', styled: true}),
      },
    ],
  },
  {
    title: '老客',
    key: 'old_group',
    align: 'center',
    children: [
      ...addGroupSep(gsvChildren('old_gsv', 'old_gsv_yoy')),
      ...ratioChildren('old_ratio', 'old_ratio_yoy'),
    ],
  },
  {
    title: '新客',
    key: 'new_group',
    align: 'center',
    children: [
      ...addGroupSep(gsvChildren('new_gsv', 'new_gsv_yoy')),
      ...ratioChildren('new_ratio', 'new_ratio_yoy'),
    ],
  },
]

const allColumns: DataTableColumns<CategoryOverviewItem> = [
  {
    title: '产品分类',
    key: 'name',
    width: 130,
    fixed: 'left',
    align: 'center',
    sorter: 'default',
  },
  {
    title: '全店',
    key: 'all_group',
    align: 'center',
    children: [
      ...gsvChildren('gsv', 'gsv_yoy'),
      {
        title: '会员占比',
        key: 'member_ratio',
        width: 80,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: any, b: any) => (a['member_ratio'] ?? 0) - (b['member_ratio'] ?? 0),
        render: (row: any) => `${(((row['member_ratio'] || 0)) * 100).toFixed(1)}%`,
      },
      {
        title: 'YOY',
        key: 'member_ratio_yoy',
        width: 85,
        align: 'center',
        sorter: (a: any, b: any) => (a['member_ratio_yoy'] ?? 0) - (b['member_ratio_yoy'] ?? 0),
        render: (row: any) => h(YOYGuard, { value: row['member_ratio_yoy'], unit: 'pp', styled: true}),
      },
      ...usersChildren('users', 'users_yoy'),
      ...ausChildren('aus', 'aus_yoy'),
    ],
  },
  {
    title: '老客',
    key: 'old_group',
    align: 'center',
    children: [
      ...addGroupSep(gsvChildren('old_gsv', 'old_gsv_yoy')),
      ...ratioChildren('old_ratio', 'old_ratio_yoy'),
      ...usersChildren('old_users', 'old_users_yoy'),
      ...ausChildren('old_aus', 'old_aus_yoy'),
    ],
  },
  {
    title: '新客',
    key: 'new_group',
    align: 'center',
    children: [
      ...addGroupSep(gsvChildren('new_gsv', 'new_gsv_yoy')),
      ...ratioChildren('new_ratio', 'new_ratio_yoy'),
      ...usersChildren('new_users', 'new_users_yoy'),
      ...ausChildren('new_aus', 'new_aus_yoy'),
    ],
  },
]

const memberColumns: DataTableColumns<CategoryOverviewItem> = [
  {
    title: '产品分类',
    key: 'name',
    width: 130,
    fixed: 'left',
    align: 'center',
    sorter: 'default',
  },
  {
    title: '全店',
    key: 'all_group',
    align: 'center',
    children: [
      ...gsvChildren('gsv', 'gsv_yoy'),
      // 会员占比列：自定义标题为"会员占比"
      {
        title: '会员占比',
        key: 'member_ratio',
        width: 80,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: any, b: any) => (a['member_ratio'] ?? 0) - (b['member_ratio'] ?? 0),
        render: (row: any) => `${(((row['member_ratio'] || 0)) * 100).toFixed(1)}%`,
      },
      {
        title: 'YOY',
        key: 'member_ratio_yoy',
        width: 85,
        align: 'center',
        sorter: (a: any, b: any) => (a['member_ratio_yoy'] ?? 0) - (b['member_ratio_yoy'] ?? 0),
        render: (row: any) => h(YOYGuard, { value: row['member_ratio_yoy'], unit: 'pp', styled: true}),
      },
      ...usersChildren('users', 'users_yoy'),
      ...ausChildren('aus', 'aus_yoy'),
    ],
  },
  {
    title: '老客',
    key: 'old_group',
    align: 'center',
    children: [
      ...addGroupSep(gsvChildren('old_gsv', 'old_gsv_yoy')),
      ...ratioChildren('old_ratio', 'old_ratio_yoy'),
      ...usersChildren('old_users', 'old_users_yoy'),
      ...ausChildren('old_aus', 'old_aus_yoy'),
    ],
  },
  {
    title: '新客',
    key: 'new_group',
    align: 'center',
    children: [
      ...addGroupSep(gsvChildren('new_gsv', 'new_gsv_yoy')),
      ...ratioChildren('new_ratio', 'new_ratio_yoy'),
      ...usersChildren('new_users', 'new_users_yoy'),
      ...ausChildren('new_aus', 'new_aus_yoy'),
    ],
  },
]

const allTtl = computed<CategoryOverviewItem | null>(() => overviewData.value?.all_ttl || null)
const memberTtl = computed<CategoryOverviewItem | null>(() => overviewData.value?.member_ttl || null)

// ── Sprint 174 ad-hoc 14 sheet 导出 (Q3) ──
// 5 张 DataTablePro 各对应一套 XlsxColumn + ExportToolbar.
// 注意: 子表 (gsv/users/aus) 跨多列 (去年/差值/YOY) → flatten 成 Excel 多列.
const categoryDistributionXlsxColumns = computed<XlsxColumn[]>(() => [
  { header: '品类名称', key: 'name', width: 18 },
  { header: 'GSV (元)', key: 'gmv', width: 14, numFmt: '¥#,##0' },
  { header: '用户数', key: 'user_count', width: 12, numFmt: '#,##0' },
  { header: '会员占比', key: 'member_ratio', width: 12, numFmt: '0.0%' },
  { header: '渗透率', key: 'penetration_rate', width: 12, numFmt: '0.0%' },
])

// L4.79 + L4.80 WYSIWYG 25 列扩列 (跟 frontend allColumns 1:1 stable, 全店+老客+新客 groups + 会员占比 + 会员渗透率)
// 1 + 9 (全店) + 8 (老客) + 8 (新客) = 26 列. 全店 group 多 1 列 会员占比 YOY, 跟 frontend allColumns (line 395-453) 1:1 stable 沿用
const allCompactXlsxColumns = computed<XlsxColumn[]>(() => [
  { header: '产品分类', key: 'name', width: 14 },
  // 全店 group (9 columns: GSV/YOY/会员占比/YOY/用户数/YOY/AUS/YOY)
  { header: '全店-GSV (元)', key: 'gsv', width: 16, numFmt: '¥#,##0' },
  { header: '全店-GSV YOY%', key: 'gsv_yoy', width: 12, numFmt: '0.00' },
  { header: '全店-会员占比', key: 'member_ratio', width: 12, numFmt: '0.0%' },
  { header: '全店-会员占比 YOY%', key: 'member_ratio_yoy', width: 12, numFmt: '0.00' },
  { header: '全店-用户数', key: 'users', width: 12, numFmt: '#,##0' },
  { header: '全店-用户数 YOY%', key: 'users_yoy', width: 12, numFmt: '0.00' },
  { header: '全店-AUS', key: 'aus', width: 12, numFmt: '¥#,##0' },
  { header: '全店-AUS YOY%', key: 'aus_yoy', width: 12, numFmt: '0.00' },
  { header: '全店-会员渗透率', key: 'member_penetration', width: 12, numFmt: '0.0%' },
  // 老客 group (8 columns: GSV/YOY/占比/YOY/用户数/YOY/AUS/YOY)
  { header: '老客-GSV (元)', key: 'old_gsv', width: 16, numFmt: '¥#,##0' },
  { header: '老客-GSV YOY%', key: 'old_gsv_yoy', width: 12, numFmt: '0.00' },
  { header: '老客-占比', key: 'old_ratio', width: 12, numFmt: '0.0%' },
  { header: '老客-占比 YOY%', key: 'old_ratio_yoy', width: 12, numFmt: '0.00' },
  { header: '老客-用户数', key: 'old_users', width: 12, numFmt: '#,##0' },
  { header: '老客-用户数 YOY%', key: 'old_users_yoy', width: 12, numFmt: '0.00' },
  { header: '老客-AUS', key: 'old_aus', width: 12, numFmt: '¥#,##0' },
  { header: '老客-AUS YOY%', key: 'old_aus_yoy', width: 12, numFmt: '0.00' },
  // 新客 group (8 columns: GSV/YOY/占比/YOY/用户数/YOY/AUS/YOY)
  { header: '新客-GSV (元)', key: 'new_gsv', width: 16, numFmt: '¥#,##0' },
  { header: '新客-GSV YOY%', key: 'new_gsv_yoy', width: 12, numFmt: '0.00' },
  { header: '新客-占比', key: 'new_ratio', width: 12, numFmt: '0.0%' },
  { header: '新客-占比 YOY%', key: 'new_ratio_yoy', width: 12, numFmt: '0.00' },
  { header: '新客-用户数', key: 'new_users', width: 12, numFmt: '#,##0' },
  { header: '新客-用户数 YOY%', key: 'new_users_yoy', width: 12, numFmt: '0.00' },
  { header: '新客-AUS', key: 'new_aus', width: 12, numFmt: '¥#,##0' },
  { header: '新客-AUS YOY%', key: 'new_aus_yoy', width: 12, numFmt: '0.00' },
])

// 会员 view 同样 26 列 WYSIWYG (跟 frontend memberColumns 1:1 stable 沿用, 老客/新客 改用 member_data 子字典)
const memberCompactXlsxColumns = computed<XlsxColumn[]>(() => [
  { header: '产品分类', key: 'name', width: 14 },
  // 全店 group (9 columns, 会员口径)
  { header: '全店-GSV (元)', key: 'gsv', width: 16, numFmt: '¥#,##0' },
  { header: '全店-GSV YOY%', key: 'gsv_yoy', width: 12, numFmt: '0.00' },
  { header: '全店-会员占比', key: 'member_ratio', width: 12, numFmt: '0.0%' },
  { header: '全店-会员占比 YOY%', key: 'member_ratio_yoy', width: 12, numFmt: '0.00' },
  { header: '全店-用户数', key: 'users', width: 12, numFmt: '#,##0' },
  { header: '全店-用户数 YOY%', key: 'users_yoy', width: 12, numFmt: '0.00' },
  { header: '全店-AUS', key: 'aus', width: 12, numFmt: '¥#,##0' },
  { header: '全店-AUS YOY%', key: 'aus_yoy', width: 12, numFmt: '0.00' },
  { header: '全店-会员渗透率', key: 'member_penetration', width: 12, numFmt: '0.0%' },
  // 老客 group (8 columns, 会员口径)
  { header: '老客-GSV (元)', key: 'old_gsv', width: 16, numFmt: '¥#,##0' },
  { header: '老客-GSV YOY%', key: 'old_gsv_yoy', width: 12, numFmt: '0.00' },
  { header: '老客-占比', key: 'old_ratio', width: 12, numFmt: '0.0%' },
  { header: '老客-占比 YOY%', key: 'old_ratio_yoy', width: 12, numFmt: '0.00' },
  { header: '老客-用户数', key: 'old_users', width: 12, numFmt: '#,##0' },
  { header: '老客-用户数 YOY%', key: 'old_users_yoy', width: 12, numFmt: '0.00' },
  { header: '老客-AUS', key: 'old_aus', width: 12, numFmt: '¥#,##0' },
  { header: '老客-AUS YOY%', key: 'old_aus_yoy', width: 12, numFmt: '0.00' },
  // 新客 group (8 columns, 会员口径)
  { header: '新客-GSV (元)', key: 'new_gsv', width: 16, numFmt: '¥#,##0' },
  { header: '新客-GSV YOY%', key: 'new_gsv_yoy', width: 12, numFmt: '0.00' },
  { header: '新客-占比', key: 'new_ratio', width: 12, numFmt: '0.0%' },
  { header: '新客-占比 YOY%', key: 'new_ratio_yoy', width: 12, numFmt: '0.00' },
  { header: '新客-用户数', key: 'new_users', width: 12, numFmt: '#,##0' },
  { header: '新客-用户数 YOY%', key: 'new_users_yoy', width: 12, numFmt: '0.00' },
  { header: '新客-AUS', key: 'new_aus', width: 12, numFmt: '¥#,##0' },
  { header: '新客-AUS YOY%', key: 'new_aus_yoy', width: 12, numFmt: '0.00' },
])

// 详细 (all_columns) 复用 same 模式, 内容行更多 (Sprint 174 先统一导出 compact 版, 详细版后续 sprint)
const exportFilenamePrefix = computed(() => `品类分析_${filterStore.dateRange[0]}_${filterStore.dateRange[1]}`)

// L4.79 + L4.80 flatten compactXlsxColumns 26 列到行: 从 CategoryOverviewItem 提取 (全店 + 老客 + 新客 + 会员占比 + 会员渗透率)
function flattenOverviewRow(row: Record<string, any>, includeMember: boolean): Record<string, any> {
  const base: Record<string, any> = {
    name: row.name,
    // 全店 group
    gsv: row.gsv,
    gsv_yoy: row.gsv_yoy,
    member_ratio: row.member_ratio,
    member_ratio_yoy: row.member_ratio_yoy,
    users: row.users,
    users_yoy: row.users_yoy,
    aus: row.aus,
    aus_yoy: row.aus_yoy,
    // 老客 group
    old_gsv: row.old_gsv,
    old_gsv_yoy: row.old_gsv_yoy,
    old_ratio: row.old_ratio,
    old_ratio_yoy: row.old_ratio_yoy,
    old_users: row.old_users,
    old_users_yoy: row.old_users_yoy,
    old_aus: row.old_aus,
    old_aus_yoy: row.old_aus_yoy,
    // 新客 group
    new_gsv: row.new_gsv,
    new_gsv_yoy: row.new_gsv_yoy,
    new_ratio: row.new_ratio,
    new_ratio_yoy: row.new_ratio_yoy,
    new_users: row.new_users,
    new_users_yoy: row.new_users_yoy,
    new_aus: row.new_aus,
    new_aus_yoy: row.new_aus_yoy,
  }
  if (includeMember) {
    base.member_gsv = row.member_gsv
    base.member_gsv_yoy = row.member_gsv_yoy
    base.member_users = row.member_users
    base.member_users_yoy = row.member_users_yoy
    base.member_aus = row.member_aus
    base.member_aus_yoy = row.member_aus_yoy
    base.member_penetration = row.member_penetration
  }
  return base
}
const allCompactXlsxData = computed(() =>
  (overviewData.value?.all_rows ?? []).map((r: any) => flattenOverviewRow(r, true))
)
const memberCompactXlsxData = computed(() =>
  (overviewData.value?.member_rows ?? []).map((r: any) => flattenOverviewRow(r, true))
)
const distributionXlsxData = computed(() =>
  sortedDistribution.value.map((r: any) => ({
    name: r.name,
    gmv: r.gmv,
    user_count: r.user_count,
    member_ratio: r.member_ratio,
    penetration_rate: r.penetration_rate,
  }))
)

</script>

<template>
  <div class="space-y-5">
    <PageHeader title="品类看板" subtitle="品类分布与人群交叉分析" />

    <RatioConventionBanner />

    <!-- 6-Tab 主体 -->
    <div class="p-4" style="background-color: #f8fafc; border-radius: 6px; border: 1px solid #e2e8f0;">
      <n-tabs v-model:value="activeTab" type="line" animated class="mb-1">
        <!-- ═══ Tab 1: 现状概览 ═══ -->
        <n-tab-pane name="overview" tab="现状概览">
          <p class="text-[11px] text-slate-400 mb-3 pt-1">
            解决问题：品类整体长啥样？哪些品类是主力、哪些在增长？——看清品类规模、集中度和单品明细
          </p>
          <div class="space-y-5">
            <!-- 全局 KPI（品类运营视角） -->
            <n-grid :cols="4" :x-gap="12" :y-gap="12" responsive="screen" :item-responsive="true">
              <n-gi :span="1">
                <MetricCard
                  title="新客GSV占比"
                  :value="newCustomerGsvRatio"
                  :loading="overviewLoading"
                  subtitle="新客贡献越高，增长越依赖拉新投入"
                  formula="新客GSV / 全店GSV"
                />
              </n-gi>
              <n-gi :span="1">
                <MetricCard
                  title="TOP3品类GSV占比"
                  :value="top3GsvRatio"
                  :loading="distributionLoading"
                  subtitle="集中度>70%需警惕品类依赖风险"
                  formula="TOP3品类GSV之和 / 全店总GSV"
                />
              </n-gi>
              <n-gi :span="1">
                <MetricCard
                  title="渗透率TOP1"
                  :value="topPenetration"
                  :loading="distributionLoading"
                  subtitle="覆盖用户最广的品类，具备扩圈潜力"
                  formula="该品类购买人数 / 总购买人数"
                />
              </n-gi>
              <n-gi :span="1">
                <MetricCard
                  title="GSV贡献TOP1"
                  :value="topGsvCategory"
                  :loading="distributionLoading"
                  subtitle="当前收入贡献最大的品类，资源倾斜参考"
                  formula="GSV最高的品类名称 + 金额"
                />
              </n-gi>
            </n-grid>

            <!-- 品类GSV分布 -->
            <div class="bi-card p-4">
              <ErrorState
                v-if="distributionError"
                :message="(distributionError as Error).message"
                @retry="distributionRefetch()"
              />
              <LoadingState v-else-if="distributionLoading" />
              <template v-else-if="distributionData?.distribution.length">
                <div class="flex flex-col lg:flex-row gap-5">
                  <div class="w-full lg:w-1/2">
                    <h3 class="text-sm font-semibold text-slate-800 mb-0.5">品类GSV分布</h3>
                    <p class="text-[11px] text-slate-500 mb-1">TOP10品类GSV占比</p>
                    <p class="text-[11px] text-slate-400 mb-3">
                      TOP1占比：<span class="font-semibold text-slate-600">{{ top1GsvPct }}</span>
                    </p>
                    <EChartsWrapper :option="pieChartOption" height="320px" />
                  </div>
                  <div class="w-full lg:w-1/2">
                    <div class="flex items-center justify-between mb-0.5">
                      <h3 class="text-sm font-semibold text-slate-800">品类明细</h3>
                      <ExportToolbar
                        :filename="`${exportFilenamePrefix}_品类明细`"
                        :columns="categoryDistributionXlsxColumns"
                        :data="distributionXlsxData"
                        sheet-name="品类明细"
                      />
                    </div>
                    <p class="text-[11px] text-slate-500 mb-3">各品类GSV与用户规模（按GSV降序）</p>
                    <DataTablePro
                      :columns="[
                        { title: '品类名称', key: 'name', width: 180, fixed: 'left', align: 'center', sorter: 'default' },
                        { title: 'GSV', key: 'gmv', width: 130, align: 'center', className: 'bi-cell-number', sorter: (a: any, b: any) => (a.gmv ?? 0) - (b.gmv ?? 0), render: (row: any) => `¥${(row.gmv / 10000).toFixed(1)}万` },
                        { title: '用户数', key: 'user_count', width: 100, align: 'center', className: 'bi-cell-number', sorter: (a: any, b: any) => (a.user_count ?? 0) - (b.user_count ?? 0) },
                        { title: '会员占比', key: 'member_ratio', width: 100, align: 'center', className: 'bi-cell-number', sorter: (a: any, b: any) => (a.member_ratio ?? 0) - (b.member_ratio ?? 0), render: (row: any) => `${((row.member_ratio || 0) * 100).toFixed(1)}%` },
                        { title: '渗透率', key: 'penetration_rate', width: 100, align: 'center', className: 'bi-cell-number', sorter: (a: any, b: any) => (a.penetration_rate ?? 0) - (b.penetration_rate ?? 0), render: (row: any) => `${((row.penetration_rate || 0) * 100).toFixed(1)}%` },
                      ]"
                      :data="sortedDistribution"
                      :pagination="false"
                      :max-height="400"
                    />
                  </div>
                </div>
              </template>
              <EmptyState v-else description="当前条件下无数据" />
            </div>

            <!-- 单品概览 — 全店 -->
            <div class="bi-card p-4">
              <div class="flex items-center justify-between mb-0.5">
                <h3 class="text-sm font-semibold text-slate-800">单品概览 — 全店</h3>
                <div class="flex items-center gap-2">
                  <BaseStyleButton
                    :mode="showDetailAll ? 'collapse' : 'expand'"
                    @click="showDetailAll = !showDetailAll"
                  >
                    {{ showDetailAll ? '收起详情' : '显示详情' }}
                  </BaseStyleButton>
                  <ExportToolbar
                    :filename="`${exportFilenamePrefix}_单品概览全店`"
                    :columns="allCompactXlsxColumns"
                    :data="allCompactXlsxData"
                    sheet-name="单品概览全店"
                  />
                </div>
              </div>
              <p class="text-[11px] text-slate-500 mb-3">
                {{ showDetailAll ? '全量指标：GSV / 人数 / AUS / 占比 及同比' : '核心指标：GSV 及新老客占比（点击"显示详情"展开全部列）' }}
              </p>
              <ErrorState v-if="overviewError" :message="(overviewError as Error).message" @retry="overviewRefetch()" />
              <LoadingState v-else-if="overviewLoading" />
              <EmptyState v-else-if="!overviewData?.all_rows.length" description="暂无数据" />
              <template v-else>
                <DataTablePro
                  v-if="!showDetailAll"
                  :columns="compactColumns"
                  :data="overviewData.all_rows"
                  :total-row="allTtl"
                  :pagination="false"
                  :max-height="400"
                  striped
                />
                <DataTablePro
                  v-else
                  :columns="allColumns"
                  :data="overviewData.all_rows"
                  :total-row="allTtl"
                  :pagination="false"
                  :max-height="400"
                  :scroll-x="2500"
                  striped
                />
              </template>
            </div>

            <!-- 单品概览 — 会员 -->
            <div class="bi-card p-4">
              <div class="flex items-center justify-between mb-0.5">
                <h3 class="text-sm font-semibold text-slate-800">单品概览 — 会员</h3>
                <div class="flex items-center gap-2">
                  <BaseStyleButton
                    :mode="showDetailMember ? 'collapse' : 'expand'"
                    @click="showDetailMember = !showDetailMember"
                  >
                    {{ showDetailMember ? '收起详情' : '显示详情' }}
                  </BaseStyleButton>
                  <ExportToolbar
                    :filename="`${exportFilenamePrefix}_单品概览会员`"
                    :columns="memberCompactXlsxColumns"
                    :data="memberCompactXlsxData"
                    sheet-name="单品概览会员"
                  />
                </div>
              </div>
              <p class="text-[11px] text-slate-500 mb-3">
                {{ showDetailMember ? '全量指标：GSV / 会员占比 / 人数 / AUS 及同比' : '核心指标：GSV 及新老客占比（点击"显示详情"展开全部列）' }}
              </p>
              <ErrorState v-if="overviewError" :message="(overviewError as Error).message" @retry="overviewRefetch()" />
              <LoadingState v-else-if="overviewLoading" />
              <EmptyState v-else-if="!overviewData?.member_rows.length" description="暂无数据" />
              <template v-else>
                <DataTablePro
                  v-if="!showDetailMember"
                  :columns="compactMemberColumns"
                  :data="overviewData.member_rows"
                  :total-row="memberTtl"
                  :pagination="false"
                  :max-height="400"
                  striped
                />
                <DataTablePro
                  v-else
                  :columns="memberColumns"
                  :data="overviewData.member_rows"
                  :total-row="memberTtl"
                  :pagination="false"
                  :max-height="400"
                  :scroll-x="2500"
                  striped
                />
              </template>
            </div>
          </div>
        </n-tab-pane>

        <!-- ═══ Tab 2: 连带分析 ═══ -->
        <n-tab-pane name="association" tab="连带分析">
          <p class="text-[11px] text-slate-400 mb-3 pt-1">
            解决问题：同一笔订单里哪些品类经常一起被买？——指导组合装设计、关联推荐和满减门槛设置
          </p>
          <div class="space-y-5">
            <MarketBasketTab :category-options="categoryOptions" />
          </div>
        </n-tab-pane>

        <!-- ═══ Tab 3: 品类复购周期 ═══ -->
        <n-tab-pane name="product-repurchase" tab="品类复购周期">
          <p class="text-[11px] text-slate-400 mb-3 pt-1">
            解决问题：各品类的复购周期多长？同品类复购 vs 跨品类回购的表现差异？——识别高黏性品类和引流型品类
          </p>
          <div class="space-y-5">
            <ProductClassRepurchaseTab />
          </div>
        </n-tab-pane>

        <!-- ═══ Tab 4: 品类回购分析 ═══ -->
        <n-tab-pane name="repurchase" tab="品类回购分析">
          <p class="text-[11px] text-slate-400 mb-3 pt-1">
            解决问题：买了某品类的老客，多久回来？回来买了同品还是其他品类？——识别品类复购周期和品类间的承接关系
          </p>
          <div class="space-y-5">
            <CategoryRepurchaseTab :category-options="categoryOptions" />
          </div>
        </n-tab-pane>

        <!-- ═══ Tab 5: 品类流转 ═══ -->
        <n-tab-pane name="flow" tab="品类流转">
          <p class="text-[11px] text-slate-400 mb-3 pt-1">
            解决问题：用户买了A品类之后流向了哪个品类？——看清品类间的承接关系，指导关联推荐和品类组合策略
          </p>
          <div class="space-y-5">
            <CategoryFlowTab :category-options="categoryOptions" />
          </div>
        </n-tab-pane>

        <!-- ═══ Tab 6: 羊毛党分析 ═══ -->
        <n-tab-pane name="wool" tab="羊毛党分析">
          <p class="text-[11px] text-slate-400 mb-3 pt-1">
            解决问题：哪些品类用户质量高（高价值多）、哪些品类薅羊毛严重？——指导品类人群健康度评估和资源投放优先级
          </p>
          <div class="space-y-5">
            <ValueTierTab />
          </div>
        </n-tab-pane>

        <!-- ═══ Tab 7: 风险预警 ═══ -->
        <n-tab-pane name="risk" tab="风险预警">
          <p class="text-[11px] text-slate-400 mb-3 pt-1">
            解决问题：哪些品类在流失用户、流失去了哪里？——识别下滑品类并给出挽回方向
          </p>
          <div class="space-y-5">
            <ChurnWarningTab />
          </div>
        </n-tab-pane>
      </n-tabs>
    </div>
  </div>
</template>

<style scoped>
/* 详情模式下确保横向滚动条可见 */
:deep(.n-data-table .n-data-table-base-table-body) {
  overflow-x: auto;
}

:deep(.n-data-table .n-data-table-base-table-body::-webkit-scrollbar-thumb) {
  background: #94a3b8;
  border-radius: 4px;
}

:deep(.n-data-table .n-data-table-base-table-body::-webkit-scrollbar-track) {
  background: #e2e8f0;
}

/* 组分隔线：老客/新客组首列左边加竖线，防止看岔行 */
:deep(.n-data-table td.group-sep),
:deep(.n-data-table th.group-sep) {
  border-left: 2px solid #cbd5e1;
}

/* 隔行变色增强可读性 */
:deep(.n-data-table .n-data-table-td--striped) {
  background: #f8fafc !important;
}
</style>
