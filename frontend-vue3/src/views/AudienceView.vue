<script setup lang="ts">
import { computed, toValue, ref, h } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NGrid, NGi, NButton } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useFilterStore } from '@/stores/filterStore'
import {
  fetchDailyTrend,
  fetchKPIMetrics,
  fetchAudienceSummary,
  fetchVisitorSummary,
  fetchVisitorDailyTrend,
  type AudienceTableParams,
  type DailyTrendPoint,
  type IndicatorRow,
  type ChannelGSVRow,
  type KPIMetrics,
  type VisitorSummary,
} from '@/api/audience'
import MetricCard from '@/components/MetricCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import YOYBadge from '@/components/YOYBadge.vue'
import DataTablePro from '@/components/DataTablePro.vue'
import ExportToolbar from '@/components/ExportToolbar.vue'
import { BRAND_PRIMARY } from '@/composables/useChartTheme'
import { getCompareLabels } from '@/utils/date'

const filterStore = useFilterStore()

const trendChartRef = ref<InstanceType<typeof EChartsWrapper> | null>(null)
const visitorTrendChartRef = ref<InstanceType<typeof EChartsWrapper> | null>(null)

const CHANNEL_ORDER = [
  '货架', '达播', '直播', '淘客', '微博', 'U先派样', '百补派样', '赠品&0.01', '其他',
]

import { LOW_PRICE_CHANNELS } from '@/constants/channels'

const channelSortState = ref<{ columnKey: string; order: 'ascend' | 'descend' | false }>({
  columnKey: 'channel',
  order: 'ascend',
})

// ─── 渠道概览 compact/all 切换 ────────────────────────────────
const showDetailChannelAll = ref(false)
const showDetailChannelMember = ref(false)

/** TTL汇总行加特殊样式：底部加粗分隔线，字体加粗 */
function channelRowClassName(row: any): string {
  return row.channel === 'TTL' ? 'ttl-row' : ''
}

/** 给一组列的首个 child 加 group-sep 分隔线类名 */
function addChannelGroupSep(subs: any[]): any[] {
  return subs.map((col, i) =>
    i === 0 ? { ...col, className: [col.className || '', 'group-sep'].join(' ') } : col
  )
}

// TTL 行直接从后端返回的数据中提取（后端已计算好正确的 TTL 行）
const channelAllTtl = computed<ChannelGSVRow | null>(() => {
  if (!summaryData.value?.channel_all) return null
  return summaryData.value.channel_all.find((r: ChannelGSVRow) => r.channel === 'TTL') || null
})

const sortedChannelAll = computed(() => {
  if (!summaryData.value?.channel_all) return []
  // 排除 TTL 行，只对真实渠道数据排序
  const data = summaryData.value.channel_all.filter((r: ChannelGSVRow) => r.channel !== 'TTL')
  const { columnKey, order } = channelSortState.value
  if (!order || (columnKey === 'channel' && order === 'ascend')) {
    data.sort((a, b) => CHANNEL_ORDER.indexOf(a.channel) - CHANNEL_ORDER.indexOf(b.channel))
  } else {
    data.sort((a, b) => {
      const va = a[columnKey as keyof typeof a]
      const vb = b[columnKey as keyof typeof b]
      if (va == null) return 1
      if (vb == null) return -1
      if (typeof va === 'number' && typeof vb === 'number') {
        return order === 'ascend' ? va - vb : vb - va
      }
      const cmp = String(va).localeCompare(String(vb))
      return order === 'ascend' ? cmp : -cmp
    })
  }
  return data
})

// displayChannelAll = 排序后的渠道数据 + TTL 行（后端已计算好）
const displayChannelAll = computed(() => {
  if (!channelAllTtl.value) return sortedChannelAll.value
  return [...sortedChannelAll.value, channelAllTtl.value]
})

// TTL 行直接从后端返回的数据中提取
const channelMemberTtl = computed<ChannelGSVRow | null>(() => {
  if (!summaryData.value?.channel_member) return null
  return summaryData.value.channel_member.find((r: ChannelGSVRow) => r.channel === 'TTL') || null
})

const sortedChannelMember = computed(() => {
  if (!summaryData.value?.channel_member) return []
  // 排除 TTL 行，只对真实渠道数据排序
  const data = summaryData.value.channel_member.filter((r: ChannelGSVRow) => r.channel !== 'TTL')
  const { columnKey, order } = channelSortState.value
  if (!order || (columnKey === 'channel' && order === 'ascend')) {
    data.sort((a, b) => CHANNEL_ORDER.indexOf(a.channel) - CHANNEL_ORDER.indexOf(b.channel))
  } else {
    data.sort((a, b) => {
      const va = a[columnKey as keyof typeof a]
      const vb = b[columnKey as keyof typeof b]
      if (va == null) return 1
      if (vb == null) return -1
      if (typeof va === 'number' && typeof vb === 'number') {
        return order === 'ascend' ? va - vb : vb - va
      }
      const cmp = String(va).localeCompare(String(vb))
      return order === 'ascend' ? cmp : -cmp
    })
  }
  return data
})

// displayChannelMember = 排序后的渠道数据 + TTL 行
// 交叉指标（会员vs全店占比）已由后端计算并返回
const displayChannelMember = computed(() => {
  if (!summaryData.value?.channel_member) return []
  const data = sortedChannelMember.value
  if (!channelMemberTtl.value) return data
  return [...data, channelMemberTtl.value]
})

const queryParams = computed<AudienceTableParams>(() => ({
  date_start: filterStore.dateRange[0],
  date_end: filterStore.dateRange[1],
  channel: filterStore.channel === '全店' ? undefined : filterStore.channel,
  dimension: filterStore.dimension,
  dim_value: filterStore.dimensionValue || undefined,
  exclude_channels: filterStore.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined,
}))

// 对比参数：auto_yoy 不传（后端原生 Y-1），auto_mom / custom 传计算后的日期
const compareQueryParams = computed(() => {
  if (filterStore.compareMode === 'auto_yoy') return {}
  const comp = filterStore.compareParams
  if (!comp) return {}
  return { compare_start_date: comp[0], compare_end_date: comp[1] }
})

const { data: kpiData, isLoading: kpiLoading } = useQuery({
  queryKey: computed(() => ['kpi-metrics', { ...toValue(queryParams) }, toValue(compareQueryParams)]),
  queryFn: () => {
    const p = toValue(queryParams)
    const c = toValue(compareQueryParams)
    return fetchKPIMetrics({ date_start: p.date_start, date_end: p.date_end, channel: p.channel, exclude_channels: p.exclude_channels, ...c })
  },
  staleTime: 60_000,
})

const { data: trendData, isLoading: trendLoading, error: trendError, refetch: trendRefetch } = useQuery({
  queryKey: computed(() => ['daily-trend', { ...toValue(queryParams) }, toValue(compareQueryParams)]),
  queryFn: () => {
    const p = toValue(queryParams)
    const c = toValue(compareQueryParams)
    return fetchDailyTrend({ date_start: p.date_start, date_end: p.date_end, channel: p.channel, exclude_channels: p.exclude_channels, ...c })
  },
  staleTime: 60_000,
})

const { data: summaryData, isLoading: summaryLoading, error: summaryError, refetch: summaryRefetch } = useQuery({
  queryKey: computed(() => ['audience-summary', { ...toValue(queryParams) }, filterStore.compareParams]),
  queryFn: () => {
    const p = toValue(queryParams)
    const comp = filterStore.compareParams
    return fetchAudienceSummary({
      start_date: p.date_start,
      end_date: p.date_end,
      channel: p.channel,
      exclude_channels: p.exclude_channels,
      compare_start_date: comp ? comp[0] : undefined,
      compare_end_date: comp ? comp[1] : undefined,
    })
  },
  staleTime: 60_000,
})

// 访客入会率数据
const { data: visitorSummary, isLoading: visitorLoading } = useQuery({
  queryKey: computed(() => ['visitor-summary', { ...toValue(queryParams) }, toValue(compareQueryParams)]),
  queryFn: () => {
    const p = toValue(queryParams)
    const c = toValue(compareQueryParams)
    return fetchVisitorSummary({
      start_date: p.date_start,
      end_date: p.date_end,
      ...c,
    })
  },
  staleTime: 60_000,
})

const { data: visitorTrendData, isLoading: visitorTrendLoading, error: visitorTrendError, refetch: visitorTrendRefetch } = useQuery({
  queryKey: computed(() => ['visitor-daily-trend', { ...toValue(queryParams) }, toValue(compareQueryParams)]),
  queryFn: () => {
    const p = toValue(queryParams)
    const c = toValue(compareQueryParams)
    return fetchVisitorDailyTrend({
      start_date: p.date_start,
      end_date: p.date_end,
      ...c,
    })
  },
  staleTime: 60_000,
})

// ── 对比模式联动：KPI 卡片 change 值 & 图表标签 ──
const isMOM = computed(() => filterStore.compareMode === 'auto_mom')

/** KPI 卡片切换：auto_mom → mom_*，其余 → yoy_* */
function kpiChange(yoyField: keyof KPIMetrics, momField: keyof KPIMetrics): number | undefined {
  if (!kpiData.value) return undefined
  return isMOM.value ? ((kpiData.value as any)[momField] ?? 0) : ((kpiData.value as any)[yoyField] ?? 0)
}

/** 访客卡片切换：auto_mom → *_mom，其余 → *_yoy */
function visitorChange(yoyField: keyof VisitorSummary, momField: keyof VisitorSummary): number | undefined {
  if (!visitorSummary.value) return undefined
  return isMOM.value ? ((visitorSummary.value as any)[momField] ?? 0) : ((visitorSummary.value as any)[yoyField] ?? 0)
}

/** 动态对比标签（用于图表 legend / 说明文字） */
const compareLabelShort = computed(() => {
  if (filterStore.compareMode === 'auto_mom') return '上期'
  if (filterStore.compareMode === 'custom') return '对比期'
  return '去年同期'
})

const indicatorColumns = computed<DataTableColumns<IndicatorRow>>(() => {
  const mode = filterStore.compareMode
  const labels = getCompareLabels(mode, summaryData.value?.year_label, summaryData.value?.comp_year_label)

  // 通用值渲染函数（年份动态）
  const renderValue = (yearKey: string) => (row: IndicatorRow) => {
    const v = row.values_by_year?.[yearKey] ?? null
    if (v == null) return '—'
    if (row.kind === 'ratio') return `${(v * 100).toFixed(1)}%`
    if (row.kind === 'count') return v.toLocaleString()
    if (row.kind === 'aus') return `¥${v.toFixed(1)}`
    return `¥${(v / 10000).toFixed(1)}万`
  }

  const cols: DataTableColumns<IndicatorRow> = [
    { title: '指标', key: 'field', width: 160, fixed: 'left', align: 'center' },
    {
      title: mode === 'auto_yoy' ? `${labels.current}年` : labels.current,
      key: 'values_by_year',
      width: 120,
      align: 'center',
      className: 'bi-cell-number',
      render: renderValue('2026'),
    },
    {
      title: mode === 'auto_yoy' ? `${labels.compare}年` : labels.compare,
      key: 'values_by_year',
      width: 120,
      align: 'center',
      className: 'bi-cell-number',
      render: renderValue('2025'),
    },
  ]

  // 同比模式：展示第3年列（前前年）
  if (mode === 'auto_yoy') {
    const yr3 = summaryData.value?.prev2_year_label || String(new Date().getFullYear() - 2)
    const hasPrev2 = !!summaryData.value?.prev2_year_label
    if (hasPrev2) {
      cols.push({
        title: `${yr3}年`,
        key: 'values_by_year',
        width: 120,
        align: 'center',
        className: 'bi-cell-number',
        render: renderValue('2024'),
      })
    }
  }

  // 变化列
  cols.push({
    title: labels.change,
    key: 'yoy',
    width: 120,
    align: 'center',
    render: (row: IndicatorRow) => h(YOYBadge, { value: row.kind === 'ratio' ? (row.yoy ?? 0) * 100 : row.yoy, unit: row.kind === 'ratio' ? 'pp' : '%' }),
  })
  return cols
})

// 所有列禁用内置排序，排序全部在 sortedChannelAll/sortedChannelMember 中处理
const channelColumns = computed<DataTableColumns<ChannelGSVRow>>(() => {
  const labels = getCompareLabels(filterStore.compareMode, summaryData.value?.year_label, summaryData.value?.comp_year_label)
  const yr = labels.current
  const yr2 = labels.compare
  const yoyLabel = labels.change
  return [
  {
    title: '渠道',
    key: 'channel',
    width: 110,
    fixed: 'left',
    align: 'center',
    sorter: false,
  },
  {
    title: 'GSV',
    key: 'gsv_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'gsv_2026',
        width: 110,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a, b) => (a.gsv_2026 ?? 0) - (b.gsv_2026 ?? 0),
        render: (row: ChannelGSVRow) => `¥${(row.gsv_2026 / 10000).toFixed(1)}万`,
      },
      {
        title: yr2,
        key: 'gsv_2025',
        width: 110,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a, b) => (a.gsv_2025 ?? 0) - (b.gsv_2025 ?? 0),
        render: (row: ChannelGSVRow) => `¥${(row.gsv_2025 / 10000).toFixed(1)}万`,
      },
      {
        title: yoyLabel,
        key: 'yoy',
        width: 90,
        align: 'center',
        sorter: (a, b) => (a.yoy ?? 0) - (b.yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: row.yoy }),
      },
    ],
  },
  {
    title: '人数',
    key: 'users_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'users_2026',
        width: 100,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.users_2026 ?? 0) - (b.users_2026 ?? 0),
        render: (row: ChannelGSVRow) => ((row.users_2026 ?? 0)).toLocaleString(),
      },
      {
        title: yr2,
        key: 'users_2025',
        width: 100,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.users_2025 ?? 0) - (b.users_2025 ?? 0),
        render: (row: ChannelGSVRow) => ((row.users_2025 ?? 0)).toLocaleString(),
      },
      {
        title: yoyLabel,
        key: 'users_yoy',
        width: 90,
        align: 'center',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.users_yoy ?? 0) - (b.users_yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: row.users_yoy }),
      },
    ],
  },
  {
    title: 'AUS',
    key: 'aus_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'aus_2026',
        width: 100,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.aus_2026 ?? 0) - (b.aus_2026 ?? 0),
        render: (row: ChannelGSVRow) => `¥${(row.aus_2026 ?? 0).toFixed(0)}`,
      },
      {
        title: yr2,
        key: 'aus_2025',
        width: 100,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.aus_2025 ?? 0) - (b.aus_2025 ?? 0),
        render: (row: ChannelGSVRow) => `¥${(row.aus_2025 ?? 0).toFixed(0)}`,
      },
      {
        title: yoyLabel,
        key: 'aus_yoy',
        width: 90,
        align: 'center',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.aus_yoy ?? 0) - (b.aus_yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: row.aus_yoy }),
      },
    ],
  },
  {
    title: '新客GSV',
    key: 'new_gsv_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'new_gsv_2026',
        width: 110,
        align: 'center',
        className: 'bi-cell-number group-sep',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_gsv_2026 ?? 0) - (b.new_gsv_2026 ?? 0),
        render: (row: ChannelGSVRow) => `¥${((row.new_gsv_2026 ?? 0) / 10000).toFixed(1)}万`,
      },
      {
        title: yr2,
        key: 'new_gsv_2025',
        width: 110,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_gsv_2025 ?? 0) - (b.new_gsv_2025 ?? 0),
        render: (row: ChannelGSVRow) => `¥${((row.new_gsv_2025 ?? 0) / 10000).toFixed(1)}万`,
      },
      {
        title: yoyLabel,
        key: 'new_gsv_yoy',
        width: 90,
        align: 'center',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_gsv_yoy ?? 0) - (b.new_gsv_yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: row.new_gsv_yoy }),
      },
    ],
  },
  {
    title: '新客GSV占比',
    key: 'new_gsv_ratio_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'new_gsv_ratio_2026',
        width: 90,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_gsv_ratio_2026 ?? 0) - (b.new_gsv_ratio_2026 ?? 0),
        render: (row: ChannelGSVRow) => `${((row.new_gsv_ratio_2026 ?? 0) * 100).toFixed(1)}%`,
      },
      {
        title: yr2,
        key: 'new_gsv_ratio_2025',
        width: 90,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_gsv_ratio_2025 ?? 0) - (b.new_gsv_ratio_2025 ?? 0),
        render: (row: ChannelGSVRow) => `${((row.new_gsv_ratio_2025 ?? 0) * 100).toFixed(1)}%`,
      },
      {
        title: yoyLabel,
        key: 'new_gsv_ratio_yoy',
        width: 90,
        align: 'center',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_gsv_ratio_yoy ?? 0) - (b.new_gsv_ratio_yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: (row.new_gsv_ratio_yoy ?? 0) * 100, unit: 'pp' }),
      },
    ],
  },
  {
    title: '新客人数',
    key: 'new_users_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'new_users_2026',
        width: 100,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_users_2026 ?? 0) - (b.new_users_2026 ?? 0),
        render: (row: ChannelGSVRow) => ((row.new_users_2026 ?? 0)).toLocaleString(),
      },
      {
        title: yr2,
        key: 'new_users_2025',
        width: 100,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_users_2025 ?? 0) - (b.new_users_2025 ?? 0),
        render: (row: ChannelGSVRow) => ((row.new_users_2025 ?? 0)).toLocaleString(),
      },
      {
        title: yoyLabel,
        key: 'new_users_yoy',
        width: 90,
        align: 'center',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_users_yoy ?? 0) - (b.new_users_yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: row.new_users_yoy }),
      },
    ],
  },
  {
    title: '新客AUS',
    key: 'new_aus_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'new_aus_2026',
        width: 100,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_aus_2026 ?? 0) - (b.new_aus_2026 ?? 0),
        render: (row: ChannelGSVRow) => `¥${(row.new_aus_2026 ?? 0).toFixed(0)}`,
      },
      {
        title: yr2,
        key: 'new_aus_2025',
        width: 100,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_aus_2025 ?? 0) - (b.new_aus_2025 ?? 0),
        render: (row: ChannelGSVRow) => `¥${(row.new_aus_2025 ?? 0).toFixed(0)}`,
      },
      {
        title: yoyLabel,
        key: 'new_aus_yoy',
        width: 90,
        align: 'center',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_aus_yoy ?? 0) - (b.new_aus_yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: row.new_aus_yoy }),
      },
    ],
  },
  {
    title: '老客GSV',
    key: 'old_gsv_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'old_gsv_2026',
        width: 110,
        align: 'center',
        className: 'bi-cell-number group-sep',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_gsv_2026 ?? 0) - (b.old_gsv_2026 ?? 0),
        render: (row: ChannelGSVRow) => `¥${((row.old_gsv_2026 ?? 0) / 10000).toFixed(1)}万`,
      },
      {
        title: yr2,
        key: 'old_gsv_2025',
        width: 110,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_gsv_2025 ?? 0) - (b.old_gsv_2025 ?? 0),
        render: (row: ChannelGSVRow) => `¥${((row.old_gsv_2025 ?? 0) / 10000).toFixed(1)}万`,
      },
      {
        title: yoyLabel,
        key: 'old_gsv_yoy',
        width: 90,
        align: 'center',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_gsv_yoy ?? 0) - (b.old_gsv_yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: row.old_gsv_yoy }),
      },
    ],
  },
  {
    title: '老客GSV占比',
    key: 'old_gsv_ratio_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'old_gsv_ratio_2026',
        width: 90,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_gsv_ratio_2026 ?? 0) - (b.old_gsv_ratio_2026 ?? 0),
        render: (row: ChannelGSVRow) => `${((row.old_gsv_ratio_2026 ?? 0) * 100).toFixed(1)}%`,
      },
      {
        title: yr2,
        key: 'old_gsv_ratio_2025',
        width: 90,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_gsv_ratio_2025 ?? 0) - (b.old_gsv_ratio_2025 ?? 0),
        render: (row: ChannelGSVRow) => `${((row.old_gsv_ratio_2025 ?? 0) * 100).toFixed(1)}%`,
      },
      {
        title: yoyLabel,
        key: 'old_gsv_ratio_yoy',
        width: 90,
        align: 'center',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_gsv_ratio_yoy ?? 0) - (b.old_gsv_ratio_yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: (row.old_gsv_ratio_yoy ?? 0) * 100, unit: 'pp' }),
      },
    ],
  },
  {
    title: '老客人数',
    key: 'old_users_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'old_users_2026',
        width: 100,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_users_2026 ?? 0) - (b.old_users_2026 ?? 0),
        render: (row: ChannelGSVRow) => ((row.old_users_2026 ?? 0)).toLocaleString(),
      },
      {
        title: yr2,
        key: 'old_users_2025',
        width: 100,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_users_2025 ?? 0) - (b.old_users_2025 ?? 0),
        render: (row: ChannelGSVRow) => ((row.old_users_2025 ?? 0)).toLocaleString(),
      },
      {
        title: yoyLabel,
        key: 'old_users_yoy',
        width: 90,
        align: 'center',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_users_yoy ?? 0) - (b.old_users_yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: row.old_users_yoy }),
      },
    ],
  },
  {
    title: '老客AUS',
    key: 'old_aus_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'old_aus_2026',
        width: 100,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_aus_2026 ?? 0) - (b.old_aus_2026 ?? 0),
        render: (row: ChannelGSVRow) => `¥${(row.old_aus_2026 ?? 0).toFixed(0)}`,
      },
      {
        title: yr2,
        key: 'old_aus_2025',
        width: 100,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_aus_2025 ?? 0) - (b.old_aus_2025 ?? 0),
        render: (row: ChannelGSVRow) => `¥${(row.old_aus_2025 ?? 0).toFixed(0)}`,
      },
      {
        title: yoyLabel,
        key: 'old_aus_yoy',
        width: 90,
        align: 'center',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_aus_yoy ?? 0) - (b.old_aus_yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: row.old_aus_yoy }),
      },
    ],
  },
]})

const channelMemberColumns = computed<DataTableColumns<ChannelGSVRow>>(() => {
  const labels = getCompareLabels(filterStore.compareMode, summaryData.value?.year_label, summaryData.value?.comp_year_label)
  const yr = labels.current
  const yr2 = labels.compare
  const yoyLabel = labels.change
  return [
  {
    title: '渠道',
    key: 'channel',
    width: 110,
    fixed: 'left',
    align: 'center',
    sorter: false,
  },
  {
    title: 'GSV',
    key: 'gsv_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'gsv_2026',
        width: 110,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a, b) => (a.gsv_2026 ?? 0) - (b.gsv_2026 ?? 0),
        render: (row: ChannelGSVRow) => `¥${(row.gsv_2026 / 10000).toFixed(1)}万`,
      },
      {
        title: yr2,
        key: 'gsv_2025',
        width: 110,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a, b) => (a.gsv_2025 ?? 0) - (b.gsv_2025 ?? 0),
        render: (row: ChannelGSVRow) => `¥${(row.gsv_2025 / 10000).toFixed(1)}万`,
      },
      {
        title: yoyLabel,
        key: 'yoy',
        width: 90,
        align: 'center',
        sorter: (a, b) => (a.yoy ?? 0) - (b.yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: row.yoy }),
      },
    ],
  },
  {
    title: '人数',
    key: 'users_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'users_2026',
        width: 100,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.users_2026 ?? 0) - (b.users_2026 ?? 0),
        render: (row: ChannelGSVRow) => ((row.users_2026 ?? 0)).toLocaleString(),
      },
      {
        title: yr2,
        key: 'users_2025',
        width: 100,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.users_2025 ?? 0) - (b.users_2025 ?? 0),
        render: (row: ChannelGSVRow) => ((row.users_2025 ?? 0)).toLocaleString(),
      },
      {
        title: yoyLabel,
        key: 'users_yoy',
        width: 90,
        align: 'center',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.users_yoy ?? 0) - (b.users_yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: row.users_yoy }),
      },
    ],
  },
  {
    title: 'AUS',
    key: 'aus_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'aus_2026',
        width: 100,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.aus_2026 ?? 0) - (b.aus_2026 ?? 0),
        render: (row: ChannelGSVRow) => `¥${(row.aus_2026 ?? 0).toFixed(0)}`,
      },
      {
        title: yr2,
        key: 'aus_2025',
        width: 100,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.aus_2025 ?? 0) - (b.aus_2025 ?? 0),
        render: (row: ChannelGSVRow) => `¥${(row.aus_2025 ?? 0).toFixed(0)}`,
      },
      {
        title: yoyLabel,
        key: 'aus_yoy',
        width: 90,
        align: 'center',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.aus_yoy ?? 0) - (b.aus_yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: row.aus_yoy }),
      },
    ],
  },
  {
    title: '会员新客GSV',
    key: 'new_gsv_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'new_gsv_2026',
        width: 110,
        align: 'center',
        className: 'bi-cell-number group-sep',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_gsv_2026 ?? 0) - (b.new_gsv_2026 ?? 0),
        render: (row: ChannelGSVRow) => `¥${((row.new_gsv_2026 ?? 0) / 10000).toFixed(1)}万`,
      },
      {
        title: yr2,
        key: 'new_gsv_2025',
        width: 110,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_gsv_2025 ?? 0) - (b.new_gsv_2025 ?? 0),
        render: (row: ChannelGSVRow) => `¥${((row.new_gsv_2025 ?? 0) / 10000).toFixed(1)}万`,
      },
      {
        title: yoyLabel,
        key: 'new_gsv_yoy',
        width: 90,
        align: 'center',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_gsv_yoy ?? 0) - (b.new_gsv_yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: row.new_gsv_yoy }),
      },
    ],
  },
  {
    title: '会员新客GSV占比',
    key: 'new_gsv_ratio_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'new_gsv_ratio_2026',
        width: 90,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_gsv_ratio_2026 ?? 0) - (b.new_gsv_ratio_2026 ?? 0),
        render: (row: ChannelGSVRow) => `${((row.new_gsv_ratio_2026 ?? 0) * 100).toFixed(1)}%`,
      },
      {
        title: yr2,
        key: 'new_gsv_ratio_2025',
        width: 90,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_gsv_ratio_2025 ?? 0) - (b.new_gsv_ratio_2025 ?? 0),
        render: (row: ChannelGSVRow) => `${((row.new_gsv_ratio_2025 ?? 0) * 100).toFixed(1)}%`,
      },
      {
        title: yoyLabel,
        key: 'new_gsv_ratio_yoy',
        width: 90,
        align: 'center',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_gsv_ratio_yoy ?? 0) - (b.new_gsv_ratio_yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: (row.new_gsv_ratio_yoy ?? 0) * 100, unit: 'pp' }),
      },
    ],
  },
  {
    title: '会员新客人数',
    key: 'new_users_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'new_users_2026',
        width: 100,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_users_2026 ?? 0) - (b.new_users_2026 ?? 0),
        render: (row: ChannelGSVRow) => ((row.new_users_2026 ?? 0)).toLocaleString(),
      },
      {
        title: yr2,
        key: 'new_users_2025',
        width: 100,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_users_2025 ?? 0) - (b.new_users_2025 ?? 0),
        render: (row: ChannelGSVRow) => ((row.new_users_2025 ?? 0)).toLocaleString(),
      },
      {
        title: yoyLabel,
        key: 'new_users_yoy',
        width: 90,
        align: 'center',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_users_yoy ?? 0) - (b.new_users_yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: row.new_users_yoy }),
      },
    ],
  },
  {
    title: '会员新客AUS',
    key: 'new_aus_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'new_aus_2026',
        width: 100,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_aus_2026 ?? 0) - (b.new_aus_2026 ?? 0),
        render: (row: ChannelGSVRow) => `¥${(row.new_aus_2026 ?? 0).toFixed(0)}`,
      },
      {
        title: yr2,
        key: 'new_aus_2025',
        width: 100,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_aus_2025 ?? 0) - (b.new_aus_2025 ?? 0),
        render: (row: ChannelGSVRow) => `¥${(row.new_aus_2025 ?? 0).toFixed(0)}`,
      },
      {
        title: yoyLabel,
        key: 'new_aus_yoy',
        width: 90,
        align: 'center',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_aus_yoy ?? 0) - (b.new_aus_yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: row.new_aus_yoy }),
      },
    ],
  },
  {
    title: '会员老客GSV',
    key: 'old_gsv_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'old_gsv_2026',
        width: 110,
        align: 'center',
        className: 'bi-cell-number group-sep',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_gsv_2026 ?? 0) - (b.old_gsv_2026 ?? 0),
        render: (row: ChannelGSVRow) => `¥${((row.old_gsv_2026 ?? 0) / 10000).toFixed(1)}万`,
      },
      {
        title: yr2,
        key: 'old_gsv_2025',
        width: 110,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_gsv_2025 ?? 0) - (b.old_gsv_2025 ?? 0),
        render: (row: ChannelGSVRow) => `¥${((row.old_gsv_2025 ?? 0) / 10000).toFixed(1)}万`,
      },
      {
        title: yoyLabel,
        key: 'old_gsv_yoy',
        width: 90,
        align: 'center',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_gsv_yoy ?? 0) - (b.old_gsv_yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: row.old_gsv_yoy }),
      },
    ],
  },
  {
    title: '会员老客GSV占比',
    key: 'old_gsv_ratio_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'old_gsv_ratio_2026',
        width: 90,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_gsv_ratio_2026 ?? 0) - (b.old_gsv_ratio_2026 ?? 0),
        render: (row: ChannelGSVRow) => `${((row.old_gsv_ratio_2026 ?? 0) * 100).toFixed(1)}%`,
      },
      {
        title: yr2,
        key: 'old_gsv_ratio_2025',
        width: 90,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_gsv_ratio_2025 ?? 0) - (b.old_gsv_ratio_2025 ?? 0),
        render: (row: ChannelGSVRow) => `${((row.old_gsv_ratio_2025 ?? 0) * 100).toFixed(1)}%`,
      },
      {
        title: yoyLabel,
        key: 'old_gsv_ratio_yoy',
        width: 90,
        align: 'center',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_gsv_ratio_yoy ?? 0) - (b.old_gsv_ratio_yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: (row.old_gsv_ratio_yoy ?? 0) * 100, unit: 'pp' }),
      },
    ],
  },
  {
    title: '会员老客人数',
    key: 'old_users_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'old_users_2026',
        width: 100,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_users_2026 ?? 0) - (b.old_users_2026 ?? 0),
        render: (row: ChannelGSVRow) => ((row.old_users_2026 ?? 0)).toLocaleString(),
      },
      {
        title: yr2,
        key: 'old_users_2025',
        width: 100,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_users_2025 ?? 0) - (b.old_users_2025 ?? 0),
        render: (row: ChannelGSVRow) => ((row.old_users_2025 ?? 0)).toLocaleString(),
      },
      {
        title: yoyLabel,
        key: 'old_users_yoy',
        width: 90,
        align: 'center',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_users_yoy ?? 0) - (b.old_users_yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: row.old_users_yoy }),
      },
    ],
  },
  {
    title: '会员老客AUS',
    key: 'old_aus_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'old_aus_2026',
        width: 100,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_aus_2026 ?? 0) - (b.old_aus_2026 ?? 0),
        render: (row: ChannelGSVRow) => `¥${(row.old_aus_2026 ?? 0).toFixed(0)}`,
      },
      {
        title: yr2,
        key: 'old_aus_2025',
        width: 100,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_aus_2025 ?? 0) - (b.old_aus_2025 ?? 0),
        render: (row: ChannelGSVRow) => `¥${(row.old_aus_2025 ?? 0).toFixed(0)}`,
      },
      {
        title: yoyLabel,
        key: 'old_aus_yoy',
        width: 90,
        align: 'center',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_aus_yoy ?? 0) - (b.old_aus_yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: row.old_aus_yoy }),
      },
    ],
  },
  {
    title: '会员GSV占比',
    key: 'member_ratio_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'member_ratio_2026',
        width: 90,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.member_ratio_2026 ?? 0) - (b.member_ratio_2026 ?? 0),
        render: (row: ChannelGSVRow) => `${((row.member_ratio_2026 ?? 0) * 100).toFixed(1)}%`,
      },
      {
        title: yr2,
        key: 'member_ratio_2025',
        width: 90,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.member_ratio_2025 ?? 0) - (b.member_ratio_2025 ?? 0),
        render: (row: ChannelGSVRow) => `${((row.member_ratio_2025 ?? 0) * 100).toFixed(1)}%`,
      },
      {
        title: yoyLabel,
        key: 'member_ratio_yoy',
        width: 90,
        align: 'center',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.member_ratio_yoy ?? 0) - (b.member_ratio_yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: (row.member_ratio_yoy ?? 0) * 100, unit: 'pp' }),
      },
    ],
  },
  {
    title: '会员新客GSV\n占比全店新客GSV',
    key: 'member_new_vs_all_new_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'member_new_vs_all_new_2026',
        width: 90,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.member_new_vs_all_new_2026 ?? 0) - (b.member_new_vs_all_new_2026 ?? 0),
        render: (row: ChannelGSVRow) => {
          const v = row.member_new_vs_all_new_2026
          return v != null ? `${(v * 100).toFixed(1)}%` : '—'
        },
      },
      {
        title: yr2,
        key: 'member_new_vs_all_new_2025',
        width: 90,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.member_new_vs_all_new_2025 ?? 0) - (b.member_new_vs_all_new_2025 ?? 0),
        render: (row: ChannelGSVRow) => {
          const v = row.member_new_vs_all_new_2025
          return v != null ? `${(v * 100).toFixed(1)}%` : '—'
        },
      },
      {
        title: yoyLabel,
        key: 'member_new_vs_all_new_yoy',
        width: 90,
        align: 'center',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.member_new_vs_all_new_yoy ?? 0) - (b.member_new_vs_all_new_yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: (row.member_new_vs_all_new_yoy ?? 0) * 100, unit: 'pp' }),
      },
    ],
  },
  {
    title: '会员老客GSV\n占比全店老客GSV',
    key: 'member_old_vs_all_old_group',
    align: 'center',
    children: [
      {
        title: yr,
        key: 'member_old_vs_all_old_2026',
        width: 90,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.member_old_vs_all_old_2026 ?? 0) - (b.member_old_vs_all_old_2026 ?? 0),
        render: (row: ChannelGSVRow) => {
          const v = row.member_old_vs_all_old_2026
          return v != null ? `${(v * 100).toFixed(1)}%` : '—'
        },
      },
      {
        title: yr2,
        key: 'member_old_vs_all_old_2025',
        width: 90,
        align: 'center',
        className: 'bi-cell-number',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.member_old_vs_all_old_2025 ?? 0) - (b.member_old_vs_all_old_2025 ?? 0),
        render: (row: ChannelGSVRow) => {
          const v = row.member_old_vs_all_old_2025
          return v != null ? `${(v * 100).toFixed(1)}%` : '—'
        },
      },
      {
        title: yoyLabel,
        key: 'member_old_vs_all_old_yoy',
        width: 90,
        align: 'center',
        sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.member_old_vs_all_old_yoy ?? 0) - (b.member_old_vs_all_old_yoy ?? 0),
        render: (row: ChannelGSVRow) => h(YOYBadge, { value: (row.member_old_vs_all_old_yoy ?? 0) * 100, unit: 'pp' }),
      },
    ],
  },
]})

// ─── 渠道概览 — 全店 精简列（compact）──────────────────────────
// 渠道 + GSV组 + 新客组 + 老客组（核心指标 ~950px 无需横向滚动）
const compactChannelColumns = computed<DataTableColumns<ChannelGSVRow>>(() => {
  const labels = getCompareLabels(filterStore.compareMode, summaryData.value?.year_label, summaryData.value?.comp_year_label)
  const yr = labels.current
  const yr2 = labels.compare
  const yoyLabel = labels.change
  return [
    { title: '渠道', key: 'channel', width: 110, fixed: 'left', align: 'center', sorter: false },
    {
      title: '全店GSV', key: 'gsv_group', align: 'center',
      children: [
        { title: yr, key: 'gsv_2026', width: 110, align: 'center', className: 'bi-cell-number', sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.gsv_2026 ?? 0) - (b.gsv_2026 ?? 0), render: (row: ChannelGSVRow) => `¥${(row.gsv_2026 / 10000).toFixed(1)}万` },
        { title: yr2, key: 'gsv_2025', width: 110, align: 'center', className: 'bi-cell-number', sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.gsv_2025 ?? 0) - (b.gsv_2025 ?? 0), render: (row: ChannelGSVRow) => `¥${(row.gsv_2025 / 10000).toFixed(1)}万` },
        { title: yoyLabel, key: 'yoy', width: 90, align: 'center', sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.yoy ?? 0) - (b.yoy ?? 0), render: (row: ChannelGSVRow) => h(YOYBadge, { value: row.yoy }) },
      ],
    },
    {
      title: '新客', key: 'new_group', align: 'center',
      children: addChannelGroupSep([
        { title: 'GSV', key: 'new_gsv_2026', width: 110, align: 'center', className: 'bi-cell-number', sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_gsv_2026 ?? 0) - (b.new_gsv_2026 ?? 0), render: (row: ChannelGSVRow) => `¥${((row.new_gsv_2026 ?? 0) / 10000).toFixed(1)}万` },
        { title: yoyLabel, key: 'new_gsv_yoy', width: 90, align: 'center', sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_gsv_yoy ?? 0) - (b.new_gsv_yoy ?? 0), render: (row: ChannelGSVRow) => h(YOYBadge, { value: row.new_gsv_yoy }) },
        { title: '占比', key: 'new_gsv_ratio_2026', width: 85, align: 'center', className: 'bi-cell-number', sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_gsv_ratio_2026 ?? 0) - (b.new_gsv_ratio_2026 ?? 0), render: (row: ChannelGSVRow) => `${((row.new_gsv_ratio_2026 ?? 0) * 100).toFixed(1)}%` },
      ]),
    },
    {
      title: '老客', key: 'old_group', align: 'center',
      children: addChannelGroupSep([
        { title: 'GSV', key: 'old_gsv_2026', width: 110, align: 'center', className: 'bi-cell-number', sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_gsv_2026 ?? 0) - (b.old_gsv_2026 ?? 0), render: (row: ChannelGSVRow) => `¥${((row.old_gsv_2026 ?? 0) / 10000).toFixed(1)}万` },
        { title: yoyLabel, key: 'old_gsv_yoy', width: 90, align: 'center', sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_gsv_yoy ?? 0) - (b.old_gsv_yoy ?? 0), render: (row: ChannelGSVRow) => h(YOYBadge, { value: row.old_gsv_yoy }) },
        { title: '占比', key: 'old_gsv_ratio_2026', width: 85, align: 'center', className: 'bi-cell-number', sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_gsv_ratio_2026 ?? 0) - (b.old_gsv_ratio_2026 ?? 0), render: (row: ChannelGSVRow) => `${((row.old_gsv_ratio_2026 ?? 0) * 100).toFixed(1)}%` },
      ]),
    },
  ]
})

// ─── 渠道概览 — 会员 精简列（compact）─────────────────────────
// 渠道 + GSV组 + 会员新客组 + 会员老客组 + 会员占比（核心指标 ~1000px）
const compactMemberChannelColumns = computed<DataTableColumns<ChannelGSVRow>>(() => {
  const labels = getCompareLabels(filterStore.compareMode, summaryData.value?.year_label, summaryData.value?.comp_year_label)
  const yr = labels.current
  const yr2 = labels.compare
  const yoyLabel = labels.change
  return [
    { title: '渠道', key: 'channel', width: 110, fixed: 'left', align: 'center', sorter: false },
    {
      title: '会员GSV', key: 'gsv_group', align: 'center',
      children: [
        { title: yr, key: 'gsv_2026', width: 110, align: 'center', className: 'bi-cell-number', sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.gsv_2026 ?? 0) - (b.gsv_2026 ?? 0), render: (row: ChannelGSVRow) => `¥${(row.gsv_2026 / 10000).toFixed(1)}万` },
        { title: yr2, key: 'gsv_2025', width: 110, align: 'center', className: 'bi-cell-number', sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.gsv_2025 ?? 0) - (b.gsv_2025 ?? 0), render: (row: ChannelGSVRow) => `¥${(row.gsv_2025 / 10000).toFixed(1)}万` },
        { title: yoyLabel, key: 'yoy', width: 90, align: 'center', sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.yoy ?? 0) - (b.yoy ?? 0), render: (row: ChannelGSVRow) => h(YOYBadge, { value: row.yoy }) },
      ],
    },
    {
      title: '会员新客', key: 'new_group', align: 'center',
      children: addChannelGroupSep([
        { title: 'GSV', key: 'new_gsv_2026', width: 110, align: 'center', className: 'bi-cell-number', sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_gsv_2026 ?? 0) - (b.new_gsv_2026 ?? 0), render: (row: ChannelGSVRow) => `¥${((row.new_gsv_2026 ?? 0) / 10000).toFixed(1)}万` },
        { title: yoyLabel, key: 'new_gsv_yoy', width: 90, align: 'center', sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_gsv_yoy ?? 0) - (b.new_gsv_yoy ?? 0), render: (row: ChannelGSVRow) => h(YOYBadge, { value: row.new_gsv_yoy }) },
        { title: '占比', key: 'new_gsv_ratio_2026', width: 85, align: 'center', className: 'bi-cell-number', sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.new_gsv_ratio_2026 ?? 0) - (b.new_gsv_ratio_2026 ?? 0), render: (row: ChannelGSVRow) => `${((row.new_gsv_ratio_2026 ?? 0) * 100).toFixed(1)}%` },
      ]),
    },
    {
      title: '会员老客', key: 'old_group', align: 'center',
      children: addChannelGroupSep([
        { title: 'GSV', key: 'old_gsv_2026', width: 110, align: 'center', className: 'bi-cell-number', sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_gsv_2026 ?? 0) - (b.old_gsv_2026 ?? 0), render: (row: ChannelGSVRow) => `¥${((row.old_gsv_2026 ?? 0) / 10000).toFixed(1)}万` },
        { title: yoyLabel, key: 'old_gsv_yoy', width: 90, align: 'center', sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_gsv_yoy ?? 0) - (b.old_gsv_yoy ?? 0), render: (row: ChannelGSVRow) => h(YOYBadge, { value: row.old_gsv_yoy }) },
        { title: '占比', key: 'old_gsv_ratio_2026', width: 85, align: 'center', className: 'bi-cell-number', sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.old_gsv_ratio_2026 ?? 0) - (b.old_gsv_ratio_2026 ?? 0), render: (row: ChannelGSVRow) => `${((row.old_gsv_ratio_2026 ?? 0) * 100).toFixed(1)}%` },
      ]),
    },
    {
      title: '会员GSV占比', key: 'member_ratio_group', align: 'center',
      children: [
        { title: yr, key: 'member_ratio_2026', width: 90, align: 'center', className: 'bi-cell-number', sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.member_ratio_2026 ?? 0) - (b.member_ratio_2026 ?? 0), render: (row: ChannelGSVRow) => `${((row.member_ratio_2026 ?? 0) * 100).toFixed(1)}%` },
        { title: yr2, key: 'member_ratio_2025', width: 90, align: 'center', className: 'bi-cell-number', sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.member_ratio_2025 ?? 0) - (b.member_ratio_2025 ?? 0), render: (row: ChannelGSVRow) => `${((row.member_ratio_2025 ?? 0) * 100).toFixed(1)}%` },
        { title: yoyLabel, key: 'member_ratio_yoy', width: 90, align: 'center', sorter: (a: ChannelGSVRow, b: ChannelGSVRow) => (a.member_ratio_yoy ?? 0) - (b.member_ratio_yoy ?? 0), render: (row: ChannelGSVRow) => h(YOYBadge, { value: (row.member_ratio_yoy ?? 0) * 100, unit: 'pp' }) },
      ],
    },
  ]
})

// 创建计算属性，动态生成列定义，使TTL行不参与排序
const computedChannelColumns = computed<DataTableColumns<ChannelGSVRow>>(() => {
  // 递归处理列定义，为每个有sorter的列生成新的sorter函数
  const cloneColumnWithSorter = (col: any): any => {
    const newCol = { ...col }
    
    // 如果有sorter函数，生成新的sorter函数
    if (col.sorter && typeof col.sorter === 'function') {
      const originalSorter = col.sorter
      newCol.sorter = (a: ChannelGSVRow, b: ChannelGSVRow) => {
        // 检查是否为TTL行
        const aIsTtl = a.channel === 'TTL'
        const bIsTtl = b.channel === 'TTL'
        
        // 如果其中一个是TTL行，根据排序顺序返回固定值
        if (aIsTtl || bIsTtl) {
          const order = channelSortState.value.order
          if (!order) return 0
          // TTL行始终在底部
          if (order === 'ascend') {
            return aIsTtl ? 1 : -1
          } else {
            return aIsTtl ? -1 : 1
          }
        }
        
        // 非TTL行，调用原始排序函数
        return originalSorter(a, b)
      }
    }
    
    // 递归处理子列
    if (col.children) {
      newCol.children = col.children.map(cloneColumnWithSorter)
    }
    
    return newCol
  }
  
  return channelColumns.value.map(cloneColumnWithSorter)
})

const computedChannelMemberColumns = computed<DataTableColumns<ChannelGSVRow>>(() => {
  // 递归处理列定义，为每个有sorter的列生成新的sorter函数
  const cloneColumnWithSorter = (col: any): any => {
    const newCol = { ...col }
    
    // 如果有sorter函数，生成新的sorter函数
    if (col.sorter && typeof col.sorter === 'function') {
      const originalSorter = col.sorter
      newCol.sorter = (a: ChannelGSVRow, b: ChannelGSVRow) => {
        // 检查是否为TTL行
        const aIsTtl = a.channel === 'TTL'
        const bIsTtl = b.channel === 'TTL'
        
        // 如果其中一个是TTL行，根据排序顺序返回固定值
        if (aIsTtl || bIsTtl) {
          const order = channelSortState.value.order
          if (!order) return 0
          // TTL行始终在底部
          if (order === 'ascend') {
            return aIsTtl ? 1 : -1
          } else {
            return aIsTtl ? -1 : 1
          }
        }
        
        // 非TTL行，调用原始排序函数
        return originalSorter(a, b)
      }
    }
    
    // 递归处理子列
    if (col.children) {
      newCol.children = col.children.map(cloneColumnWithSorter)
    }
    
    return newCol
  }
  
  return channelMemberColumns.value.map(cloneColumnWithSorter)
})

// ─── 精简列 TTL排序包装 ──────────────────────────────────────
const computedCompactChannelColumns = computed<DataTableColumns<ChannelGSVRow>>(() => {
  const cloneColumnWithSorter = (col: any): any => {
    const newCol = { ...col }
    if (col.sorter && typeof col.sorter === 'function') {
      const originalSorter = col.sorter
      newCol.sorter = (a: ChannelGSVRow, b: ChannelGSVRow) => {
        const aIsTtl = a.channel === 'TTL'
        const bIsTtl = b.channel === 'TTL'
        if (aIsTtl || bIsTtl) {
          const order = channelSortState.value.order
          if (!order) return 0
          return order === 'ascend' ? (aIsTtl ? 1 : -1) : (aIsTtl ? -1 : 1)
        }
        return originalSorter(a, b)
      }
    }
    if (col.children) newCol.children = col.children.map(cloneColumnWithSorter)
    return newCol
  }
  return compactChannelColumns.value.map(cloneColumnWithSorter)
})

const computedCompactMemberChannelColumns = computed<DataTableColumns<ChannelGSVRow>>(() => {
  const cloneColumnWithSorter = (col: any): any => {
    const newCol = { ...col }
    if (col.sorter && typeof col.sorter === 'function') {
      const originalSorter = col.sorter
      newCol.sorter = (a: ChannelGSVRow, b: ChannelGSVRow) => {
        const aIsTtl = a.channel === 'TTL'
        const bIsTtl = b.channel === 'TTL'
        if (aIsTtl || bIsTtl) {
          const order = channelSortState.value.order
          if (!order) return 0
          return order === 'ascend' ? (aIsTtl ? 1 : -1) : (aIsTtl ? -1 : 1)
        }
        return originalSorter(a, b)
      }
    }
    if (col.children) newCol.children = col.children.map(cloneColumnWithSorter)
    return newCol
  }
  return compactMemberChannelColumns.value.map(cloneColumnWithSorter)
})

function handleChannelSort(sorter: any) {
  if (!sorter || sorter.columnKey === 'channel') {
    channelSortState.value = { columnKey: 'channel', order: 'ascend' }
  } else {
    channelSortState.value = { columnKey: sorter.columnKey, order: sorter.order }
  }
}

const trendChartOption = computed(() => {
  if (!trendData.value) return {}
  const data = trendData.value
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
        const arr = Array.isArray(params) ? params : [params]
        let html = `<div style="font-weight:600;margin-bottom:4px">${arr[0].axisValue}</div>`
        for (const p of arr) {
          const val = p.value
          const isRatio = p.seriesName.includes('占比')
          const displayVal = isRatio ? `${val.toFixed(1)}%` : `¥${(val / 10000).toFixed(1)}万`
          html += `<div style="display:flex;align-items:center;gap:6px;margin:2px 0">`
          html += `<span style="width:8px;height:8px;border-radius:50%;background:${p.color}"></span>`
          html += `<span style="flex:1">${p.seriesName}</span>`
          html += `<span style="font-weight:600">${displayVal}</span>`
          html += `</div>`
        }
        return html
      },
    },
    legend: {
      data: ['全店GSV', '会员GSV占比', `${compareLabelShort.value}GSV`, `${compareLabelShort.value}会员GSV占比`],
      top: 0,
      icon: 'circle',
      itemGap: 16,
      textStyle: { color: '#64748b', fontSize: 11 },
    },
    grid: { left: 12, right: 12, top: 40, bottom: 8 },
    xAxis: {
      type: 'category',
      data: data.map((d: DailyTrendPoint) => d.date),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 11, margin: 10 },
    },
    yAxis: [
      {
        type: 'value',
        name: 'GSV',
        position: 'left',
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: '#64748b',
          fontSize: 11,
          formatter: (v: number) => `¥${(v / 10000).toFixed(0)}万`,
        },
        splitLine: { lineStyle: { color: '#e2e8f0', type: [4, 4] } },
      },
      {
        type: 'value',
        name: '会员GSV占比',
        position: 'right',
        min: 0,
        max: 100,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: '#94a3b8',
          fontSize: 11,
          formatter: (v: number) => `${v.toFixed(0)}%`,
        },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '全店GSV',
        type: 'line',
        data: data.map((d: DailyTrendPoint) => d.gsv),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2.5, color: BRAND_PRIMARY },
        itemStyle: { color: BRAND_PRIMARY },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(83, 58, 253, 0.10)' },
              { offset: 1, color: 'rgba(83, 58, 253, 0)' },
            ],
          },
        },
        yAxisIndex: 0,
      },
      {
        name: '会员GSV占比',
        type: 'line',
        data: data.map((d: DailyTrendPoint) => d.member_ratio),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2.5, color: '#10b981' },
        itemStyle: { color: '#10b981' },
        yAxisIndex: 1,
      },
      {
        name: `${compareLabelShort.value}GSV`,
        type: 'line',
        data: data.map((d: DailyTrendPoint) => d.ly_gsv),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.5, color: '#93c5fd', type: 'dashed' },
        itemStyle: { color: '#93c5fd' },
        yAxisIndex: 0,
      },
      {
        name: `${compareLabelShort.value}会员GSV占比`,
        type: 'line',
        data: data.map((d: DailyTrendPoint) => d.ly_member_ratio),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.5, color: '#86efac', type: 'dashed' },
        itemStyle: { color: '#86efac' },
        yAxisIndex: 1,
      },
    ],
  }
})

// 访客入会率趋势图配置
const visitorTrendChartOption = computed(() => {
  if (!visitorTrendData.value?.data?.length) return {}
  const data = visitorTrendData.value.data
  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      padding: [10, 12],
      textStyle: { color: '#0f172a', fontSize: 12 },
      extraCssText: 'box-shadow: 0 4px 12px -2px rgba(0,0,0,0.08); border-radius: 4px;',
      formatter: (params: any[]) => {
        const date = params[0]?.axisValue
        let html = `<div style="font-weight:600;margin-bottom:6px">${date}</div>`
        params.forEach((p: any) => {
          const val = p.seriesName.includes('入会率') ? `${p.value}%` : p.value.toLocaleString()
          html += `<div style="display:flex;align-items:center;gap:6px;margin:3px 0">
            <span style="width:8px;height:8px;border-radius:50%;background:${p.color}"></span>
            <span style="flex:1">${p.seriesName}</span>
            <span style="font-weight:600">${val}</span>
          </div>`
        })
        return html
      },
    },
    legend: {
      data: ['访客数', '新增会员数', '入会率', `${compareLabelShort.value}入会率`],
      top: 0,
      icon: 'circle',
      itemGap: 16,
      textStyle: { color: '#64748b', fontSize: 11 },
    },
    grid: { left: 12, right: 12, top: 40, bottom: 8 },
    xAxis: {
      type: 'category',
      data: data.map((d) => d.date),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 11, margin: 10 },
    },
    yAxis: [
      {
        type: 'value',
        name: '人数',
        position: 'left',
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: '#64748b',
          fontSize: 11,
          formatter: (v: number) => v >= 10000 ? `${(v / 10000).toFixed(0)}万` : v.toLocaleString(),
        },
        splitLine: { lineStyle: { color: '#e2e8f0', type: [4, 4] } },
      },
      {
        type: 'value',
        name: '入会率',
        position: 'right',
        min: 0,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: '#94a3b8',
          fontSize: 11,
          formatter: (v: number) => `${v.toFixed(2)}%`,
        },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '访客数',
        type: 'bar',
        data: data.map((d) => d.visitors),
        barWidth: '35%',
        itemStyle: { color: '#e0e7ff', borderRadius: [2, 2, 0, 0] },
        yAxisIndex: 0,
      },
      {
        name: '新增会员数',
        type: 'bar',
        data: data.map((d) => d.new_members),
        barWidth: '35%',
        itemStyle: { color: '#c7d2fe', borderRadius: [2, 2, 0, 0] },
        yAxisIndex: 0,
      },
      {
        name: '入会率',
        type: 'line',
        data: data.map((d) => d.member_join_rate),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2.5, color: '#f59e0b' },
        itemStyle: { color: '#f59e0b' },
        yAxisIndex: 1,
      },
      {
        name: `${compareLabelShort.value}入会率`,
        type: 'line',
        data: data.map((d) => d.ly_member_join_rate),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.5, color: '#d1d5db', type: 'dashed' },
        itemStyle: { color: '#d1d5db' },
        yAxisIndex: 1,
      },
    ],
  }
})

async function handleExportIndicators() {
  if (!summaryData.value?.indicators?.length) return
  const XLSX = await import('xlsx')
  try {
    const mode = filterStore.compareMode
  const labels = getCompareLabels(mode, summaryData.value?.year_label, summaryData.value?.comp_year_label)
  const yr3 = summaryData.value?.prev2_year_label || String(new Date().getFullYear() - 2)

  // 同比模式：3年+YOY；环比/自定义：2年+变化
  const headers = mode === 'auto_yoy'
    ? ['指标', `${labels.current}年`, `${labels.compare}年`, `${yr3}年`, labels.change]
    : ['指标', labels.current, labels.compare, labels.change]

  const aoa: any[][] = [headers]

  summaryData.value.indicators.forEach((row, idx) => {
    const excelRow = idx + 2
    const isRatio = row.kind === 'ratio'
    const yoyCell = isRatio
      ? { t: 'n', f: `=B${excelRow}-C${excelRow}` } as any
      : { t: 'n', f: `=(B${excelRow}-C${excelRow})/C${excelRow}` } as any

    if (mode === 'auto_yoy') {
      aoa.push([row.field, row.values_by_year?.['2026'] ?? 0, row.values_by_year?.['2025'] ?? 0, row.values_by_year?.['2024'] ?? 0, yoyCell])
    } else {
      aoa.push([row.field, row.values_by_year?.['2026'] ?? 0, row.values_by_year?.['2025'] ?? 0, yoyCell])
    }
  })

  const ws = XLSX.utils.aoa_to_sheet(aoa)
  ws['!cols'] = [
    { wch: 18 },
    { wch: 14 },
    { wch: 14 },
    { wch: 14 },
    { wch: 14 },
  ]

  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, '30指标对比')
  const fileName = `人群看板_30指标对比_${filterStore.dateRange[0]}_${filterStore.dateRange[1]}.xlsx`
  XLSX.writeFile(wb, fileName)
  } catch (err) {
    console.error('30指标导出失败:', err)
  }
}

function formatKPI(value: number, type: 'currency' | 'number' | 'percent') {
  if (type === 'currency') return `¥${(value / 10000).toFixed(1)}万`
  if (type === 'percent') return `${(value * 100).toFixed(1)}%`
  return value.toLocaleString()
}

// API ratio 字段已返回 % 格式（如 55.0 = 55%），直接展示
function fmtRatio(v: number | null | undefined): string {
  if (v == null) return '—'
  return `${v.toFixed(1)}%`
}

// ── 渠道 Excel 导出列定义 ──
const channelXlsxColumns = computed(() => {
  const labels = getCompareLabels(filterStore.compareMode, summaryData.value?.year_label, summaryData.value?.comp_year_label)
  const yr = labels.current
  const yr2 = labels.compare
  return [
    { header: '渠道', key: 'channel', width: 12 },
    { header: `${yr}GSV`, key: 'gsv_2026', width: 14, numFmt: '¥#,##0' },
    { header: `${yr2}GSV`, key: 'gsv_2025', width: 14, numFmt: '¥#,##0' },
    { header: 'GSV YOY', key: 'yoy', width: 12, numFmt: '0.0%' },
    { header: `${yr}人数`, key: 'users_2026', width: 12, numFmt: '#,##0' },
    { header: `${yr2}人数`, key: 'users_2025', width: 12, numFmt: '#,##0' },
    { header: '人数YOY', key: 'users_yoy', width: 12, numFmt: '0.0%' },
    { header: `${yr}AUS`, key: 'aus_2026', width: 12, numFmt: '¥#,##0' },
    { header: `${yr2}AUS`, key: 'aus_2025', width: 12, numFmt: '¥#,##0' },
    { header: 'AUS YOY', key: 'aus_yoy', width: 12, numFmt: '0.0%' },
    { header: `${yr}新客GSV`, key: 'new_gsv_2026', width: 14, numFmt: '¥#,##0' },
    { header: `${yr2}新客GSV`, key: 'new_gsv_2025', width: 14, numFmt: '¥#,##0' },
    { header: '新客GSV YOY', key: 'new_gsv_yoy', width: 12, numFmt: '0.0%' },
    { header: `${yr}老客GSV`, key: 'old_gsv_2026', width: 14, numFmt: '¥#,##0' },
    { header: `${yr2}老客GSV`, key: 'old_gsv_2025', width: 14, numFmt: '¥#,##0' },
    { header: '老客GSV YOY', key: 'old_gsv_yoy', width: 12, numFmt: '0.0%' },
    { header: `${yr}老客占比`, key: 'old_gsv_ratio_2026', width: 12, numFmt: '0.0%' },
    { header: `${yr2}老客占比`, key: 'old_gsv_ratio_2025', width: 12, numFmt: '0.0%' },
    { header: '老客占比YOY', key: 'old_gsv_ratio_yoy', width: 12, numFmt: '0.0%' },
    { header: `${yr}新客占比`, key: 'new_gsv_ratio_2026', width: 12, numFmt: '0.0%' },
    { header: `${yr2}新客占比`, key: 'new_gsv_ratio_2025', width: 12, numFmt: '0.0%' },
    { header: '新客占比YOY', key: 'new_gsv_ratio_yoy', width: 12, numFmt: '0.0%' },
    { header: `${yr}新客人数`, key: 'new_users_2026', width: 12, numFmt: '#,##0' },
    { header: `${yr2}新客人数`, key: 'new_users_2025', width: 12, numFmt: '#,##0' },
    { header: '新客人数YOY', key: 'new_users_yoy', width: 12, numFmt: '0.0%' },
    { header: `${yr}新客AUS`, key: 'new_aus_2026', width: 12, numFmt: '¥#,##0' },
    { header: `${yr2}新客AUS`, key: 'new_aus_2025', width: 12, numFmt: '¥#,##0' },
    { header: '新客AUS YOY', key: 'new_aus_yoy', width: 12, numFmt: '0.0%' },
    { header: `${yr}老客人数`, key: 'old_users_2026', width: 12, numFmt: '#,##0' },
    { header: `${yr2}老客人数`, key: 'old_users_2025', width: 12, numFmt: '#,##0' },
    { header: '老客人数YOY', key: 'old_users_yoy', width: 12, numFmt: '0.0%' },
    { header: `${yr}老客AUS`, key: 'old_aus_2026', width: 12, numFmt: '¥#,##0' },
    { header: `${yr2}老客AUS`, key: 'old_aus_2025', width: 12, numFmt: '¥#,##0' },
    { header: '老客AUS YOY', key: 'old_aus_yoy', width: 12, numFmt: '0.0%' },
  ]
})

// ── 渠道会员 Excel 导出列定义（与页面显示列一致）──
const channelMemberXlsxColumns = computed(() => {
  const labels = getCompareLabels(filterStore.compareMode, summaryData.value?.year_label, summaryData.value?.comp_year_label)
  const yr = labels.current
  const yr2 = labels.compare
  return [
    { header: '渠道', key: 'channel', width: 12 },
    // 会员GSV
    { header: `${yr}会员GSV`, key: 'gsv_2026', width: 14, numFmt: '¥#,##0' },
    { header: `${yr2}会员GSV`, key: 'gsv_2025', width: 14, numFmt: '¥#,##0' },
    { header: '会员GSV YOY', key: 'yoy', width: 12, numFmt: '0.0%' },
    // 会员人数
    { header: `${yr}会员人数`, key: 'users_2026', width: 12, numFmt: '#,##0' },
    { header: `${yr2}会员人数`, key: 'users_2025', width: 12, numFmt: '#,##0' },
    { header: '会员人数YOY', key: 'users_yoy', width: 12, numFmt: '0.0%' },
    // 会员AUS
    { header: `${yr}会员AUS`, key: 'aus_2026', width: 12, numFmt: '¥#,##0' },
    { header: `${yr2}会员AUS`, key: 'aus_2025', width: 12, numFmt: '¥#,##0' },
    { header: '会员AUS YOY', key: 'aus_yoy', width: 12, numFmt: '0.0%' },
    // 会员新客GSV
    { header: `${yr}会员新客GSV`, key: 'new_gsv_2026', width: 14, numFmt: '¥#,##0' },
    { header: `${yr2}会员新客GSV`, key: 'new_gsv_2025', width: 14, numFmt: '¥#,##0' },
    { header: '会员新客GSV YOY', key: 'new_gsv_yoy', width: 12, numFmt: '0.0%' },
    // 会员新客GSV占比
    { header: `${yr}会员新客GSV占比`, key: 'new_gsv_ratio_2026', width: 12, numFmt: '0.0%' },
    { header: `${yr2}会员新客GSV占比`, key: 'new_gsv_ratio_2025', width: 12, numFmt: '0.0%' },
    { header: '会员新客占比YOY', key: 'new_gsv_ratio_yoy', width: 12, numFmt: '0.0%' },
    { header: `${yr}会员新客人数`, key: 'new_users_2026', width: 12, numFmt: '#,##0' },
    { header: `${yr2}会员新客人数`, key: 'new_users_2025', width: 12, numFmt: '#,##0' },
    { header: '会员新客人数YOY', key: 'new_users_yoy', width: 12, numFmt: '0.0%' },
    { header: `${yr}会员新客AUS`, key: 'new_aus_2026', width: 12, numFmt: '¥#,##0' },
    { header: `${yr2}会员新客AUS`, key: 'new_aus_2025', width: 12, numFmt: '¥#,##0' },
    { header: '会员新客AUS YOY', key: 'new_aus_yoy', width: 12, numFmt: '0.0%' },
    // 会员老客GSV
    { header: `${yr}会员老客GSV`, key: 'old_gsv_2026', width: 14, numFmt: '¥#,##0' },
    { header: `${yr2}会员老客GSV`, key: 'old_gsv_2025', width: 14, numFmt: '¥#,##0' },
    { header: '会员老客GSV YOY', key: 'old_gsv_yoy', width: 12, numFmt: '0.0%' },
    // 会员老客GSV占比
    { header: `${yr}会员老客GSV占比`, key: 'old_gsv_ratio_2026', width: 12, numFmt: '0.0%' },
    { header: `${yr2}会员老客GSV占比`, key: 'old_gsv_ratio_2025', width: 12, numFmt: '0.0%' },
    { header: '会员老客占比YOY', key: 'old_gsv_ratio_yoy', width: 12, numFmt: '0.0%' },
    { header: `${yr}会员老客人数`, key: 'old_users_2026', width: 12, numFmt: '#,##0' },
    { header: `${yr2}会员老客人数`, key: 'old_users_2025', width: 12, numFmt: '#,##0' },
    { header: '会员老客人数YOY', key: 'old_users_yoy', width: 12, numFmt: '0.0%' },
    { header: `${yr}会员老客AUS`, key: 'old_aus_2026', width: 12, numFmt: '¥#,##0' },
    { header: `${yr2}会员老客AUS`, key: 'old_aus_2025', width: 12, numFmt: '¥#,##0' },
    { header: '会员老客AUS YOY', key: 'old_aus_yoy', width: 12, numFmt: '0.0%' },
    // 会员GSV占比（该渠道会员GSV / 该渠道全店GSV）
    { header: `${yr}会员GSV占比`, key: 'member_ratio_2026', width: 12, numFmt: '0.0%' },
    { header: `${yr2}会员GSV占比`, key: 'member_ratio_2025', width: 12, numFmt: '0.0%' },
    { header: '会员GSV占比YOY', key: 'member_ratio_yoy', width: 12, numFmt: '0.0%' },
    // 交叉指标: 会员新客GSV / 全店新客GSV
    { header: `${yr}会员新客vs全店新客GSV`, key: 'member_new_vs_all_new_2026', width: 14, numFmt: '0.0%' },
    { header: `${yr2}会员新客vs全店新客GSV`, key: 'member_new_vs_all_new_2025', width: 14, numFmt: '0.0%' },
    { header: '会员新客vs全店新客YOY', key: 'member_new_vs_all_new_yoy', width: 14, numFmt: '0.0%' },
    // 交叉指标: 会员老客GSV / 全店老客GSV
    { header: `${yr}会员老客vs全店老客GSV`, key: 'member_old_vs_all_old_2026', width: 14, numFmt: '0.0%' },
    { header: `${yr2}会员老客vs全店老客GSV`, key: 'member_old_vs_all_old_2025', width: 14, numFmt: '0.0%' },
    { header: '会员老客vs全店老客YOY', key: 'member_old_vs_all_old_yoy', width: 14, numFmt: '0.0%' },
  ]
})
</script>

<template>
  <div class="space-y-5">
    <PageHeader title="人群看板" subtitle="洞察用户结构与消费趋势" />

    <!-- KPI Cards 第一行：人群 GSV -->
    <n-grid :cols="4" :x-gap="12" :y-gap="12" responsive="screen" :item-responsive="true">
      <n-gi :span="1" class="h-full">
        <MetricCard
          title="全店GSV"
          :value="kpiData ? formatKPI(kpiData.gsv, 'currency') : '—'"
          :change="kpiChange('gsv_yoy', 'gsv_mom')"
          :loading="kpiLoading"
        />
      </n-gi>
      <n-gi :span="1" class="h-full">
        <MetricCard
          title="老客GSV"
          :value="kpiData ? formatKPI(kpiData.old_gsv, 'currency') : '—'"
          :change="kpiChange('old_gsv_yoy', 'old_gsv_mom')"
          :loading="kpiLoading"
        />
      </n-gi>
      <n-gi :span="1" class="h-full">
        <MetricCard
          title="新客GSV"
          :value="kpiData ? formatKPI(kpiData.new_gsv, 'currency') : '—'"
          :change="kpiChange('new_gsv_yoy', 'new_gsv_mom')"
          :loading="kpiLoading"
        />
      </n-gi>
      <n-gi :span="1" class="h-full">
        <MetricCard
          title="会员GSV"
          :value="kpiData ? formatKPI(kpiData.member_gsv, 'currency') : '—'"
          :change="kpiChange('member_gsv_yoy', 'member_gsv_mom')"
          :loading="kpiLoading"
        />
      </n-gi>
    </n-grid>

    <!-- KPI Cards 第二行：人群占比 + 会员溢价 -->
    <n-grid :cols="4" :x-gap="12" :y-gap="12" responsive="screen" :item-responsive="true">
      <n-gi :span="1" class="h-full">
        <MetricCard
          title="老客占比"
          :value="fmtRatio(kpiData?.old_gsv_ratio)"
          :change="kpiChange('old_gsv_ratio_yoy', 'old_gsv_ratio_mom')"
          :loading="kpiLoading"
          unit="pp"
        />
      </n-gi>
      <n-gi :span="1" class="h-full">
        <MetricCard
          title="新客占比"
          :value="fmtRatio(kpiData?.new_gsv_ratio)"
          :change="kpiChange('new_gsv_ratio_yoy', 'new_gsv_ratio_mom')"
          :loading="kpiLoading"
          unit="pp"
        />
      </n-gi>
      <n-gi :span="1" class="h-full">
        <MetricCard
          title="会员GSV占比"
          :value="fmtRatio(kpiData?.member_gsv_ratio)"
          :change="kpiChange('member_gsv_ratio_yoy', 'member_gsv_ratio_mom')"
          :loading="kpiLoading"
          unit="pp"
        />
      </n-gi>
      <n-gi :span="1" class="h-full">
        <MetricCard
          title="会员溢价"
          :value="kpiData ? Number(kpiData.member_premium).toFixed(2) : '—'"
          :change="kpiChange('member_premium_yoy', 'member_premium_mom')"
          :loading="kpiLoading"
          unit="%"
        />
      </n-gi>
    </n-grid>

    <!-- KPI Cards 第三行：访客入会率 -->
    <n-grid :cols="4" :x-gap="12" :y-gap="12" responsive="screen" :item-responsive="true">
      <n-gi :span="1" class="h-full">
        <MetricCard
          title="访客数"
          :value="visitorSummary ? Number(visitorSummary.visitors).toLocaleString() : '—'"
          :change="visitorChange('visitors_yoy', 'visitors_mom')"
          :loading="visitorLoading"
          unit="%"
        />
      </n-gi>
      <n-gi :span="1" class="h-full">
        <MetricCard
          title="新增会员数"
          :value="visitorSummary ? Number(visitorSummary.new_members).toLocaleString() : '—'"
          :change="visitorChange('new_members_yoy', 'new_members_mom')"
          :loading="visitorLoading"
          unit="%"
        />
      </n-gi>
      <n-gi :span="1" class="h-full">
        <MetricCard
          title="会员入会率"
          :value="visitorSummary ? `${visitorSummary.member_join_rate.toFixed(2)}%` : '—'"
          :change="visitorChange('member_join_rate_yoy', 'member_join_rate_mom')"
          :loading="visitorLoading"
          unit="pp"
        />
      </n-gi>
      <n-gi :span="1" class="h-full">
        <MetricCard
          :title="`${compareLabelShort}入会率`"
          :value="visitorSummary ? `${visitorSummary.ly_member_join_rate.toFixed(2)}%` : '—'"
          :loading="visitorLoading"
        />
      </n-gi>
    </n-grid>

    <!-- Trend Chart -->
    <div class="bi-card p-4">
      <div class="flex items-center justify-between mb-0.5">
        <div>
          <h3 class="text-sm font-semibold text-slate-800">日趋势</h3>
          <p class="text-[11px] text-slate-500">全店GSV 与会员占比 — 含{{ compareLabelShort }}对比</p>
        </div>
        <ExportToolbar
          :filename="`人群看板_日趋势_${filterStore.dateRange[0]}_${filterStore.dateRange[1]}`"
          :chart-ref="trendChartRef"
        />
      </div>
      <ErrorState v-if="trendError" :message="(trendError as Error).message" @retry="trendRefetch()" />
      <LoadingState v-else-if="trendLoading" />
      <EmptyState v-else-if="!trendData?.length" />
      <EChartsWrapper v-else ref="trendChartRef" :option="trendChartOption" height="280px" />
    </div>

    <!-- Visitor Join Rate Trend Chart -->
    <div class="bi-card p-4">
      <div class="flex items-center justify-between mb-0.5">
        <div>
          <h3 class="text-sm font-semibold text-slate-800">入会趋势</h3>
          <p class="text-[11px] text-slate-500">访客数、新增会员数与入会率 — 含{{ compareLabelShort }}入会率对比</p>
        </div>
        <ExportToolbar
          :filename="`人群看板_入会趋势_${filterStore.dateRange[0]}_${filterStore.dateRange[1]}`"
          :chart-ref="visitorTrendChartRef"
        />
      </div>
      <ErrorState v-if="visitorTrendError" :message="(visitorTrendError as Error).message" @retry="visitorTrendRefetch()" />
      <LoadingState v-else-if="visitorTrendLoading" />
      <EmptyState v-else-if="!visitorTrendData?.data?.length" description="暂无访客数据" />
      <EChartsWrapper v-else ref="visitorTrendChartRef" :option="visitorTrendChartOption" height="280px" />
    </div>

    <!-- Channel Overview -->
    <div class="flex flex-col gap-5">
      <!-- 全店 -->
      <div class="bi-card p-4">
        <div class="flex items-center justify-between mb-0.5">
          <div>
            <h3 class="text-sm font-semibold text-slate-800">渠道概览 — 全店</h3>
            <p class="text-[11px] text-slate-500">
              {{ showDetailChannelAll ? '全量指标：GSV / 人数 / AUS / 新老客 GSV 两年同比与占比' : '核心指标：GSV 及新老客占比（点击"显示详情"展开全部列）' }}
            </p>
          </div>
          <div class="flex items-center gap-2">
            <ExportToolbar
              :filename="`人群看板_渠道全店_${filterStore.dateRange[0]}_${filterStore.dateRange[1]}`"
              :columns="channelXlsxColumns"
              :data="displayChannelAll"
              sheet-name="渠道全店"
            />
            <button
              class="px-3 py-1.5 text-sm font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 hover:text-indigo-800 rounded-lg cursor-pointer select-none transition-colors"
              @click="showDetailChannelAll = !showDetailChannelAll"
            >
              {{ showDetailChannelAll ? '← 收起详情' : '显示详情 →' }}
            </button>
          </div>
        </div>
        <ErrorState v-if="summaryError" :message="(summaryError as Error).message" @retry="summaryRefetch()" />
        <LoadingState v-else-if="summaryLoading" />
        <EmptyState v-else-if="!sortedChannelAll.length" description="暂无数据" />
        <template v-else>
          <DataTablePro
            v-if="!showDetailChannelAll"
            :columns="computedCompactChannelColumns"
            :data="displayChannelAll"
            :pagination="false"
            striped
            :row-class-name="channelRowClassName"
            @update:sorter="handleChannelSort"
          />
          <DataTablePro
            v-else
            :columns="computedChannelColumns"
            :data="displayChannelAll"
            :pagination="false"
            :max-height="400"
            :scroll-x="2500"
            striped
            :row-class-name="channelRowClassName"
            @update:sorter="handleChannelSort"
          />
        </template>
      </div>

      <!-- 会员 -->
      <div class="bi-card p-4">
        <div class="flex items-center justify-between mb-0.5">
          <div>
            <h3 class="text-sm font-semibold text-slate-800">渠道概览 — 会员</h3>
            <p class="text-[11px] text-slate-500">
              {{ showDetailChannelMember ? '全量指标：会员 GSV / 人数 / AUS / 会员新老客 GSV 两年同比与占比' : '核心指标：会员GSV 及新老客占比（点击"显示详情"展开全部列）' }}
            </p>
          </div>
          <div class="flex items-center gap-2">
            <ExportToolbar
              :filename="`人群看板_渠道会员_${filterStore.dateRange[0]}_${filterStore.dateRange[1]}`"
              :columns="channelMemberXlsxColumns"
              :data="displayChannelMember"
              sheet-name="渠道会员"
            />
            <button
              class="px-3 py-1.5 text-sm font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 hover:text-indigo-800 rounded-lg cursor-pointer select-none transition-colors"
              @click="showDetailChannelMember = !showDetailChannelMember"
            >
              {{ showDetailChannelMember ? '← 收起详情' : '显示详情 →' }}
            </button>
          </div>
        </div>
        <ErrorState v-if="summaryError" :message="(summaryError as Error).message" @retry="summaryRefetch()" />
        <LoadingState v-else-if="summaryLoading" />
        <EmptyState v-else-if="!sortedChannelMember.length" description="暂无数据" />
        <template v-else>
          <DataTablePro
            v-if="!showDetailChannelMember"
            :columns="computedCompactMemberChannelColumns"
            :data="displayChannelMember"
            :pagination="false"
            striped
            :row-class-name="channelRowClassName"
            @update:sorter="handleChannelSort"
          />
          <DataTablePro
            v-else
            :columns="computedChannelMemberColumns"
            :data="displayChannelMember"
            :pagination="false"
            :max-height="400"
            :scroll-x="2500"
            striped
            :row-class-name="channelRowClassName"
            @update:sorter="handleChannelSort"
          />
        </template>
      </div>
    </div>

    <!-- 30 Indicators -->
    <div class="bi-card p-4">
      <div class="flex items-center justify-between mb-0.5">
        <div>
          <h3 class="text-sm font-semibold text-slate-800">30指标对比</h3>
          <p class="text-[11px] text-slate-500">全店 / 新老客 / 会员 / 会员新老客 — {{ filterStore.compareMode === 'auto_yoy' ? '3年同比' : filterStore.compareMode === 'auto_mom' ? '环比对比' : '自定义对比' }}</p>
        </div>
        <NButton size="tiny" @click="handleExportIndicators">📊 导出Excel</NButton>
      </div>
      <ErrorState v-if="summaryError" :message="(summaryError as Error).message" @retry="summaryRefetch()" />
      <LoadingState v-else-if="summaryLoading" />
      <EmptyState v-else-if="!summaryData?.indicators?.length" description="暂无数据" />
      <DataTablePro
        v-else
        :columns="indicatorColumns"
        :data="summaryData?.indicators ?? []"
        :pagination="false"
        :scroll-x="600"
        :max-height="520"
      />
    </div>

    <!-- 指标口径说明 -->
    <div class="text-xs text-slate-400 mt-3 px-1">
      <p>有效订单：剔除购物金及退款订单 | 新客：周期内首次购买 | 老客：周期开始前已有购买记录</p>
    </div>
  </div>
</template>

<style scoped>
/* TTL行样式 */
:deep(.ttl-row td) {
  font-weight: 600 !important;
  background: #f1f5f9 !important;
  border-top: 2px solid #94a3b8 !important;
}

/* 组分隔线：新客/老客组首列左边加竖线，防止看岔行 */
:deep(.n-data-table td.group-sep),
:deep(.n-data-table th.group-sep) {
  border-left: 2px solid #cbd5e1;
}

/* 隔行变色增强可读性 */
:deep(.n-data-table .n-data-table-td--striped) {
  background: #f8fafc !important;
}

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
</style>
