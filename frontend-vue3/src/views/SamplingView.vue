<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { NTabs, NTabPane, NSelect, NCard, NDataTable, NGrid, NGi, NStatistic, NDivider, NAlert, NSlider } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useQuery } from '@tanstack/vue-query'
import PageHeader from '@/components/PageHeader.vue'
import MetricCard from '@/components/MetricCard.vue'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import CohortRetentionMatrix from '@/components/cohort/CohortRetentionMatrix.vue'
import { fetchSamplingROI, fetchSamplingLockAnalysis, fetchRollingComparison, fetchSamplingRepurchaseDistribution } from '@/api/sampling'
import type { SamplingCategoryRow, SamplingChannelSummary, SamplingLevelSummary } from '@/api/sampling'
import { useFilterStore } from '@/stores/filterStore'
import { useFormat } from '@/composables/useFormat'

const { formatNumber, formatPercent, formatCurrency, formatDelta } = useFormat()

const activeTab = ref('roi')
const cohortStartMonth = ref('2025-01')
const cohortEndMonth = ref('2026-06')
const cohortChannel = ref('全店')
const filterStore = useFilterStore()

// ── Tab 1: 派样正装转化 ──
const windowDays = ref(30)
const categoryLevel = ref('spu_category')

const sliderMarks = { 7: '7d', 14: '14d', 30: '30d', 60: '60d', 90: '90d' } as Record<number, string>
const windowDaysDebounced = ref(windowDays.value)
let debounceTimer: ReturnType<typeof setTimeout> | null = null

watch(windowDays, (newVal) => {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    windowDaysDebounced.value = newVal
    debounceTimer = null
  }, 250)
})

const levelOptions = [
  { label: '品类销售', value: 'spu_category' },
  { label: '商品梯队', value: 'spu_tier' },
  { label: '单品归类', value: 'spu_product_class' },
  { label: '产品细分', value: 'spu_product_subclass' },
  { label: '功效属性', value: 'spu_cosmetic' },
]

const roiParams = computed(() => {
  return {
    start_date: filterStore.dateRange[0],
    end_date: filterStore.dateRange[1],
    window_days: windowDaysDebounced.value,
    level: categoryLevel.value,
    channel: filterStore.channel === '全店' ? undefined : filterStore.channel,
    compare_date_range: filterStore.compareParams,
    exclude_low_price: filterStore.excludeLowPrice,
  }
})

const { data: roiData, isLoading: roiLoading, isFetching: roiFetching, error: roiError, refetch: refetchRoi } = useQuery({
  queryKey: computed(() => ['sampling-roi', roiParams.value]),
  queryFn: () => fetchSamplingROI(roiParams.value),
  enabled: computed(() => activeTab.value === 'roi'),
  placeholderData: previousData => previousData,
})

const { data: repurchaseDistribution } = useQuery({
  queryKey: computed(() => ['sampling-repurchase-distribution', {
    start_date: roiParams.value.start_date,
    end_date: roiParams.value.end_date,
    window_days: 90,
    channel: roiParams.value.channel,
  }]),
  queryFn: () => fetchSamplingRepurchaseDistribution({
    start_date: roiParams.value.start_date,
    end_date: roiParams.value.end_date,
    window_days: 90,
    channel: roiParams.value.channel,
  }),
  enabled: computed(() => activeTab.value === 'roi'),
  placeholderData: previousData => previousData,
})

const levelLoadingStartedAt = ref<number>(0)
const alertTick = ref(0)
let alertTickInterval: ReturnType<typeof setInterval> | null = null

watch(roiFetching, (isFetching) => {
  if (isFetching) {
    levelLoadingStartedAt.value = Date.now()
    alertTick.value = Date.now()
    if (alertTickInterval) clearInterval(alertTickInterval)
    alertTickInterval = setInterval(() => {
      alertTick.value = Date.now()
    }, 100)
    return
  }
  if (alertTickInterval) {
    clearInterval(alertTickInterval)
    alertTickInterval = null
  }
  levelLoadingStartedAt.value = 0
})

function safeRatio(numerator: number, denominator: number): number {
  if (!denominator || denominator === 0) return 0
  return numerator / denominator
}

// Sprint 146 P1: 401 会话过期 → 跳 login 页 (CLAUDE.md §AI 执行检查点 认证)
function handleLoginRedirect() {
  window.location.href = '/login?redirect=' + encodeURIComponent(window.location.pathname)
}

const ttlSummary = computed<SamplingChannelSummary | null>(() => {
  return roiData.value?.summary.channels.find(c => c.channel === 'TTL派样')
    ?? roiData.value?.summary.channels[0]
    ?? null
})

// Sprint 147 P2.2: 渠道对比卡加辅助 icon (色盲友好, 颜色不再是唯一标识符)
function channelIcon(channel: string): string {
  if (channel === 'TTL派样') return '🎯'
  if (channel === 'U先派样') return '👤'
  if (channel === '百补派样') return '🛒'
  return '·'
}

function channelColorClass(channel: string): string {
  if (channel === 'TTL派样') return 'text-purple-600'
  if (channel === 'U先派样') return 'text-rose-600'
  if (channel === '百补派样') return 'text-orange-500'
  return 'text-slate-600'
}

function compareValue(channel: SamplingChannelSummary, baseKey: string, kind: 'pct' | 'pp'): number | null | undefined {
  const modeKey = filterStore.compareMode === 'auto_yoy' ? 'yoy' : 'mom'
  return channel[`${baseKey}_${modeKey}_${kind}` as keyof SamplingChannelSummary] as number | null | undefined
}

const levelLoadingText = computed(() => {
  void alertTick.value
  if (!roiFetching.value || !roiData.value || levelLoadingStartedAt.value === 0) return null
  if (Date.now() - levelLoadingStartedAt.value < 300) return null
  const levelLabel = levelOptions.find(o => o.value === categoryLevel.value)?.label ?? categoryLevel.value
  return `正在按 ${levelLabel} 重算...`
})

// Sprint 140: 顶部 KPI 跟随自由窗口
const totalSampleUsers = computed(() => {
  return ttlSummary.value?.sample_users ?? 0
})

const totalRepurchaseUsers = computed(() => {
  return ttlSummary.value?.repurchase_users ?? 0
})

const totalRepurchaseRate = computed(() => {
  return safeRatio(totalRepurchaseUsers.value, totalSampleUsers.value)
})

const totalFullRepurchaseUsers = computed(() => {
  return ttlSummary.value?.full_repurchase_users ?? 0
})

const totalFullRepurchaseRate = computed(() => {
  return safeRatio(totalFullRepurchaseUsers.value, totalSampleUsers.value)
})

const totalFullRepurchaseGsv = computed(() => {
  return ttlSummary.value?.full_repurchase_gsv ?? 0
})

const totalFullRepurchaseAus = computed(() => {
  return safeRatio(totalFullRepurchaseGsv.value, totalFullRepurchaseUsers.value)
})

const levelLabel = computed(() => {
  return levelOptions.find(o => o.value === categoryLevel.value)?.label ?? categoryLevel.value
})

const summaryByLevelEntries = computed<[string, SamplingLevelSummary[]][]>(() => {
  const grouped = roiData.value?.summary_by_level ?? {}
  return Object.entries(grouped).slice(0, 6) as [string, SamplingLevelSummary[]][]
})

const repurchaseBuckets = computed(() => {
  const buckets = repurchaseDistribution.value?.buckets ?? []
  const maxUsers = Math.max(...buckets.map(b => b.users), 1)
  return buckets.map(b => ({
    ...b,
    height: Math.max(6, (b.users / maxUsers) * 140),
  }))
})

// 品类明细表格列
const categoryCols: DataTableColumns<SamplingCategoryRow> = [
  { title: '渠道', key: 'channel', width: 100, fixed: 'left', align: 'center' },
  { title: '品类', key: 'category', width: 130, fixed: 'left' },
  { title: '派样人数', key: 'sample_users', width: 100, align: 'right', render: r => (r.sample_users ?? 0).toLocaleString() },
  { title: '回购人数', key: 'repurchase_users', width: 100, align: 'right', render: r => (r.repurchase_users ?? 0).toLocaleString() },
  { title: '回购率', key: 'repurchase_rate', width: 90, align: 'center', render: r => `${((r.repurchase_rate ?? 0) * 100).toFixed(1)}%` },
  { title: '回购GSV', key: 'repurchase_gsv', width: 120, align: 'right', render: r => `¥${((r.repurchase_gsv ?? 0) / 1e4).toFixed(1)}万` },
  { title: 'AUS', key: 'repurchase_aus', width: 90, align: 'right', render: r => `¥${(r.repurchase_aus ?? 0).toFixed(0)}` },
  { title: '正装回购人数', key: 'full_repurchase_users', width: 110, align: 'right', render: r => (r.full_repurchase_users ?? 0).toLocaleString() },
  { title: '正装回购率', key: 'full_repurchase_rate', width: 100, align: 'center', render: r => `${((r.full_repurchase_rate ?? 0) * 100).toFixed(1)}%` },
  { title: '正装回购GSV', key: 'full_repurchase_gsv', width: 120, align: 'right', render: r => `¥${((r.full_repurchase_gsv ?? 0) / 1e4).toFixed(1)}万` },
  { title: '正装AUS', key: 'full_repurchase_aus', width: 90, align: 'right', render: r => `¥${(r.full_repurchase_aus ?? 0).toFixed(0)}` },
  { title: '同品类回购', key: 'same_category_repurchase', width: 100, align: 'right', render: r => (r.same_category_repurchase ?? 0).toLocaleString() },
  { title: '同品类回购率', key: 'same_category_rate', width: 110, align: 'center', render: r => `${((r.same_category_rate ?? 0) * 100).toFixed(1)}%` },
]

// ── Tab 2: 0.01锁权分析 ──
const campaignName = ref('summer_sale')
const campaignYear = ref(2026)

const campaignOptions = [
  { label: 'summer_sale', value: 'summer_sale' },
  { label: 'double11', value: 'double11' },
  { label: 'spring_festival', value: 'spring_festival' },
]

const yearOptions = [
  { label: '2026', value: 2026 },
  { label: '2025', value: 2025 },
  { label: '2024', value: 2024 },
  { label: '2023', value: 2023 },
  { label: '2022', value: 2022 },
]

const { data: lockData, isLoading: lockLoading, error: lockError } = useQuery({
  queryKey: computed(() => ['sampling-lock', campaignName.value, campaignYear.value]),
  queryFn: () => fetchSamplingLockAnalysis({ campaign_name: campaignName.value, year: campaignYear.value }),
  enabled: computed(() => activeTab.value === 'lock'),
})

// 漏斗数据
const funnelSteps = computed(() => {
  if (!lockData.value) return []
  const d = lockData.value.current_year
  return [
    { label: '全店UV', value: d.total_uv, color: '#6366f1' },
    { label: '锁权人数', value: d.locked_users, color: '#8b5cf6' },
    { label: '转化人数', value: d.converted_users, color: '#a855f7' },
    { label: '贡献GSV', value: d.lock_gsv, color: '#d946ef', isGsv: true },
  ]
})

// YoY 对比表
interface LockMetricRow {
  metric: string
  current: string
  lastYear: string
  yoy: string
  yoyRaw: number | null
  isRate: boolean
}

const lockMetricRows = computed<LockMetricRow[]>(() => {
  if (!lockData.value) return []
  const c = lockData.value.current_year
  const l = lockData.value.last_year
  const y = lockData.value.yoy
  return [
    { metric: '全店UV', current: c.total_uv.toLocaleString(), lastYear: l.total_uv.toLocaleString(), yoy: fmtYoy(y.total_uv, false), yoyRaw: y.total_uv, isRate: false },
    { metric: '锁权人数', current: c.locked_users.toLocaleString(), lastYear: l.locked_users.toLocaleString(), yoy: fmtYoy(y.locked_users, false), yoyRaw: y.locked_users, isRate: false },
    { metric: '锁权率', current: `${(c.lock_rate * 100).toFixed(2)}%`, lastYear: `${(l.lock_rate * 100).toFixed(2)}%`, yoy: fmtYoy(y.lock_rate, true), yoyRaw: y.lock_rate, isRate: true },
    { metric: '转化人数', current: c.converted_users.toLocaleString(), lastYear: l.converted_users.toLocaleString(), yoy: fmtYoy(y.converted_users, false), yoyRaw: y.converted_users, isRate: false },
    { metric: '转化率', current: `${(c.conversion_rate * 100).toFixed(1)}%`, lastYear: `${(l.conversion_rate * 100).toFixed(1)}%`, yoy: fmtYoy(y.conversion_rate, true), yoyRaw: y.conversion_rate, isRate: true },
    { metric: '锁权GSV', current: fmtGsv(c.lock_gsv), lastYear: fmtGsv(l.lock_gsv), yoy: fmtYoy(y.lock_gsv, false), yoyRaw: y.lock_gsv, isRate: false },
    { metric: '锁权AUS', current: `¥${c.lock_aus.toFixed(0)}`, lastYear: `¥${l.lock_aus.toFixed(0)}`, yoy: fmtYoy(y.lock_aus, false), yoyRaw: y.lock_aus, isRate: false },
    { metric: '新客锁权人数', current: c.new_locked_users.toLocaleString(), lastYear: l.new_locked_users.toLocaleString(), yoy: fmtYoy(y.new_locked_users, false), yoyRaw: y.new_locked_users, isRate: false },
    { metric: '新客锁权占比', current: `${(c.new_locked_ratio * 100).toFixed(1)}%`, lastYear: `${(l.new_locked_ratio * 100).toFixed(1)}%`, yoy: fmtYoy(y.new_locked_ratio, true), yoyRaw: y.new_locked_ratio, isRate: true },
    { metric: '新客转化人数', current: c.new_converted_users.toLocaleString(), lastYear: l.new_converted_users.toLocaleString(), yoy: fmtYoy(y.new_converted_users, false), yoyRaw: y.new_converted_users, isRate: false },
    { metric: '新客转化率', current: `${(c.new_conversion_rate * 100).toFixed(1)}%`, lastYear: `${(l.new_conversion_rate * 100).toFixed(1)}%`, yoy: fmtYoy(y.new_conversion_rate, true), yoyRaw: y.new_conversion_rate, isRate: true },
    { metric: '新客锁权GSV', current: fmtGsv(c.new_lock_gsv), lastYear: fmtGsv(l.new_lock_gsv), yoy: fmtYoy(y.new_lock_gsv, false), yoyRaw: y.new_lock_gsv, isRate: false },
    { metric: '新客锁权AUS', current: `¥${c.new_lock_aus.toFixed(0)}`, lastYear: `¥${l.new_lock_aus.toFixed(0)}`, yoy: fmtYoy(y.new_lock_aus, false), yoyRaw: y.new_lock_aus, isRate: false },
  ]
})

const lockCols: DataTableColumns<LockMetricRow> = [
  { title: '指标', key: 'metric', width: 130, fixed: 'left', align: 'left' },
  { title: () => `${campaignYear.value}年`, key: 'current', width: 120, align: 'right' },
  { title: () => `${campaignYear.value - 1}年`, key: 'lastYear', width: 120, align: 'right' },
  { title: 'YoY', key: 'yoy', width: 100, align: 'center' },
]

// 格式化：NaN/Infinity 防护
function fmtGsv(v: number): string {
  if (!Number.isFinite(v) || Number.isNaN(v)) return '—'
  if (v >= 1e8) return `¥${(v / 1e8).toFixed(2)}亿`
  if (v >= 1e4) return `¥${(v / 1e4).toFixed(1)}万`
  return `¥${v.toFixed(0)}`
}

function fmtYoy(v: number | null, isRate: boolean): string {
  if (v === null || v === undefined) return '—'
  if (!Number.isFinite(v) || Number.isNaN(v)) return '—'
  if (isRate) {
    // 百分点差 (caller 已 *100 传 pp 数值, pass-through)
    return `${v >= 0 ? '+' : ''}${v.toFixed(1)}pp`
  }
  // 百分比 (caller 已 *100 传 percentage 数值, pass-through)
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`
}

// 安全格式化百分比（防 NaN）
function fmtPct(v: number | undefined | null, decimals = 1): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—'
  return `${(v * 100).toFixed(decimals)}%`
}

// 老客锁权人数：边界保护（防止负数）
const oldLockedUsers = computed(() => {
  if (!lockData.value) return 0
  const { locked_users, new_locked_users } = lockData.value.current_year
  return Math.max(0, locked_users - new_locked_users)
})

const oldLockedRatio = computed(() => {
  if (!lockData.value) return 0
  return Math.max(0, 1 - lockData.value.current_year.new_locked_ratio)
})

// 获取 error 的安全消息（error 类型为 unknown）
function getErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message
  if (typeof err === 'string') return err
  return '请求失败'
}

// ── Tab 2b: 0.01派样滚动同期对比 ──

// 默认日期（用户可修改）
const rollingY2026SampleStart = ref<number>(new Date(2026, 3, 27).getTime()) // 4/27
const rollingY2026SampleEnd   = ref<number>(new Date(2026, 4, 20).getTime()) // 5/20
const rollingY2026ConvStart   = ref<number>(new Date(2026, 4, 6).getTime())  // 5/6
const rollingY2025SampleStart = ref<number>(new Date(2025, 3, 28).getTime()) // 4/28
const rollingY2025SampleEnd   = ref<number>(new Date(2025, 4, 16).getTime()) // 5/16
const rollingY2025ConvStart   = ref<number>(new Date(2025, 4, 13).getTime()) // 5/13

// 滚动截止日
const rollingEndTs = ref<number>(new Date(2026, 5, 21).getTime()) // 6/21

const rollingMaxTs = new Date(2026, 5, 21).getTime() // 6/21

// 格式化日期显示
function fmtTs(ts: number): string {
  const d = new Date(ts)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// API 参数
const rollingParams = computed(() => ({
  year_a_sample_start: fmtTs(rollingY2026SampleStart.value),
  year_a_sample_end: fmtTs(rollingY2026SampleEnd.value),
  year_a_conv_start: fmtTs(rollingY2026ConvStart.value),
  year_b_sample_start: fmtTs(rollingY2025SampleStart.value),
  year_b_sample_end: fmtTs(rollingY2025SampleEnd.value),
  year_b_conv_start: fmtTs(rollingY2025ConvStart.value),
  rolling_end: fmtTs(rollingEndTs.value),
}))

const { data: rollingData, isLoading: rollingLoading, error: rollingError } = useQuery({
  queryKey: computed(() => ['sampling-rolling', rollingParams.value]),
  queryFn: () => fetchRollingComparison(rollingParams.value),
  enabled: computed(() => activeTab.value === 'rolling'),
})

// 滚动对比 YoY 指标表
interface RollingMetricRow {
  metric: string
  yearA: string
  yearB: string
  yoy: string
  yoyRaw: number | null
  isRate: boolean
}

const rollingMetricRows = computed<RollingMetricRow[]>(() => {
  if (!rollingData.value) return []
  const a = rollingData.value.year_a
  const b = rollingData.value.year_b
  const y = rollingData.value.yoy
  const isConv = a.phase === 'conversion'

  const rows: RollingMetricRow[] = [
    { metric: '全店UV', yearA: a.total_uv.toLocaleString(), yearB: b.total_uv.toLocaleString(), yoy: fmtYoy(y.total_uv, false), yoyRaw: y.total_uv, isRate: false },
    { metric: '锁权人数', yearA: a.locked_users.toLocaleString(), yearB: b.locked_users.toLocaleString(), yoy: fmtYoy(y.locked_users, false), yoyRaw: y.locked_users, isRate: false },
    { metric: '锁权率', yearA: fmtPct(a.lock_rate, 2), yearB: fmtPct(b.lock_rate, 2), yoy: fmtYoy(y.lock_rate, true), yoyRaw: y.lock_rate, isRate: true },
    { metric: '新客锁权人数', yearA: a.new_locked_users.toLocaleString(), yearB: b.new_locked_users.toLocaleString(), yoy: fmtYoy(y.new_locked_users, false), yoyRaw: y.new_locked_users, isRate: false },
    { metric: '新客锁权占比', yearA: fmtPct(a.new_locked_ratio), yearB: fmtPct(b.new_locked_ratio), yoy: fmtYoy(y.new_locked_ratio, true), yoyRaw: y.new_locked_ratio, isRate: true },
  ]

  if (isConv) {
    rows.push(
      { metric: '加赠转化人数', yearA: a.converted_users.toLocaleString(), yearB: b.converted_users.toLocaleString(), yoy: fmtYoy(y.converted_users, false), yoyRaw: y.converted_users, isRate: false },
      { metric: '转化率', yearA: fmtPct(a.conversion_rate), yearB: fmtPct(b.conversion_rate), yoy: fmtYoy(y.conversion_rate, true), yoyRaw: y.conversion_rate, isRate: true },
      { metric: '转化GSV', yearA: fmtGsv(a.conv_gsv), yearB: fmtGsv(b.conv_gsv), yoy: fmtYoy(y.conv_gsv, false), yoyRaw: y.conv_gsv, isRate: false },
      { metric: '转化AUS', yearA: `¥${a.conv_aus.toFixed(0)}`, yearB: `¥${b.conv_aus.toFixed(0)}`, yoy: fmtYoy(y.conv_aus, false), yoyRaw: y.conv_aus, isRate: false },
      { metric: '新客转化人数', yearA: a.new_converted_users.toLocaleString(), yearB: b.new_converted_users.toLocaleString(), yoy: fmtYoy(y.new_converted_users, false), yoyRaw: y.new_converted_users, isRate: false },
      { metric: '新客转化率', yearA: fmtPct(a.new_conversion_rate), yearB: fmtPct(b.new_conversion_rate), yoy: fmtYoy(y.new_conversion_rate, true), yoyRaw: y.new_conversion_rate, isRate: true },
    )
  }

  return rows
})

const rollingCols: DataTableColumns<RollingMetricRow> = [
  { title: '指标', key: 'metric', width: 140, fixed: 'left', align: 'left' },
  { title: '2026年', key: 'yearA', width: 130, align: 'right' },
  { title: '2025年(对齐)', key: 'yearB', width: 130, align: 'right' },
  { title: 'YoY', key: 'yoy', width: 100, align: 'center' },
]

onUnmounted(() => {
  if (alertTickInterval) {
    clearInterval(alertTickInterval)
    alertTickInterval = null
  }
  if (debounceTimer) {
    clearTimeout(debounceTimer)
    debounceTimer = null
  }
})
</script>

<template>
  <div class="sampling-view">
    <PageHeader title="派样看板" subtitle="U先/百补派样正装转化分析 / 0.01锁权转化分析" />

    <n-tabs v-model:value="activeTab" type="line" animated>
      <!-- Tab 1: 派样正装转化分析 -->
      <n-tab-pane name="roi" tab="派样正装转化分析">
        <div class="flex items-center gap-3 mb-4 flex-wrap">
          <div class="flex items-center gap-3" style="width: 300px">
            <n-slider
              v-model:value="windowDays"
              :min="1"
              :max="90"
              :step="1"
              :marks="sliderMarks"
              style="width: 240px"
            />
            <span class="text-sm text-slate-600 whitespace-nowrap">{{ windowDays }}天回购</span>
          </div>
          <n-select
            v-model:value="categoryLevel"
            :options="levelOptions"
            style="width: 120px"
            size="small"
          />
        </div>

        <loading-state v-if="roiLoading && !roiData" />
        <error-state
          v-else-if="roiError"
          :message="getErrorMessage(roiError)"
          :status="(roiError as any)?.response?.status ?? 0"
          @retry="refetchRoi"
          @login="handleLoginRedirect"
        />

        <template v-else-if="roiData">
          <n-alert
            v-if="levelLoadingText"
            type="info"
            :show-icon="false"
            class="mb-4"
          >
            <span class="text-sm">{{ levelLoadingText }}</span>
          </n-alert>

          <section :aria-labelledby="'sampling-section-overview'">
          <h2 id="sampling-section-overview" class="text-base font-semibold text-slate-800 mb-3"><span class="text-slate-400 font-normal mr-2">01</span>总览</h2>
          <n-grid :cols="4" :x-gap="16" :y-gap="16" class="mb-4" responsive="screen">
            <n-gi>
              <n-card :bordered="false" segmented>
                <div class="text-sm text-slate-500">派样人数</div>
                <div class="text-3xl font-bold tabular-nums text-slate-800 mt-2">
                  {{ formatNumber(totalSampleUsers) }}
                </div>
                <div class="text-xs text-slate-400 mt-1">TTL (U先 ∪ 百补, 去重)</div>
              </n-card>
            </n-gi>
            <n-gi>
              <n-card :bordered="false" segmented>
                <div class="text-sm text-slate-500">{{ windowDays }}天回购人数</div>
                <div class="text-3xl font-bold tabular-nums text-slate-800 mt-2">
                  {{ formatNumber(totalRepurchaseUsers) }}
                </div>
                <div class="text-xs text-slate-400 mt-1">回购率 {{ formatPercent(totalRepurchaseRate) }}</div>
              </n-card>
            </n-gi>
            <n-gi>
              <n-card :bordered="false" segmented>
                <div class="text-sm text-slate-500">{{ windowDays }}天正装回购人数</div>
                <div class="text-3xl font-bold tabular-nums text-rose-600 mt-2">
                  {{ formatNumber(totalFullRepurchaseUsers) }}
                </div>
                <div class="text-xs text-slate-400 mt-1">
                  正装转化率 {{ formatPercent(totalFullRepurchaseRate) }}
                </div>
              </n-card>
            </n-gi>
            <n-gi>
              <n-card :bordered="false" segmented>
                <div class="text-sm text-slate-500">{{ windowDays }}天正装 GSV</div>
                <div class="text-3xl font-bold tabular-nums text-emerald-600 mt-2">
                  {{ formatCurrency(totalFullRepurchaseGsv, 'wan') }}
                </div>
                <div class="text-xs text-slate-400 mt-1">
                  AUS ¥{{ totalFullRepurchaseAus.toFixed(0) }}
                </div>
              </n-card>
            </n-gi>
          </n-grid>
          </section>

          <n-alert
            v-if="roiData.quality_flags?.length"
            type="warning"
            :show-icon="true"
            class="mb-4"
          >
            <template #header>数据质量警告 ({{ roiData.quality_flags.length }})</template>
            <div v-for="flag in roiData.quality_flags" :key="flag.code" class="text-sm">
              {{ flag.message }}
            </div>
          </n-alert>

          <section
            v-if="summaryByLevelEntries.length"
            :aria-labelledby="'sampling-section-summary'"
            class="mb-6"
          >
            <div class="flex items-center justify-between mb-3">
              <h2 id="sampling-section-summary" class="text-base font-semibold text-slate-800"><span class="text-slate-400 font-normal mr-2">02</span>{{ levelLabel }}汇总</h2>
              <span class="text-xs text-slate-400">{{ windowDays }}天窗口</span>
            </div>
            <n-grid :cols="3" :x-gap="16" :y-gap="16" responsive="screen">
              <n-gi v-for="[levelValue, summaries] in summaryByLevelEntries" :key="levelValue">
                <n-card :bordered="false" segmented size="small">
                  <template #header>
                    <span class="text-sm font-semibold text-slate-700">{{ levelValue }}</span>
                  </template>
                  <div class="space-y-3">
                    <div
                      v-for="item in summaries"
                      :key="`${levelValue}-${item.channel}`"
                      class="rounded border border-slate-100 bg-slate-50 px-3 py-2"
                    >
                      <div class="flex items-center justify-between text-xs mb-2">
                        <span class="font-semibold text-slate-600">{{ item.channel }}</span>
                        <span class="text-indigo-600 font-bold">{{ fmtPct(item.repurchase_rate) }}</span>
                      </div>
                      <div class="grid grid-cols-3 gap-2 text-xs text-slate-500">
                        <div>
                          <div>派样</div>
                          <b class="text-slate-700">{{ item.sample_users.toLocaleString() }}</b>
                        </div>
                        <div>
                          <div>回购</div>
                          <b class="text-slate-700">{{ item.repurchase_users.toLocaleString() }}</b>
                        </div>
                        <div>
                          <div>GSV</div>
                          <b class="text-emerald-700">¥{{ (item.repurchase_gsv / 1e4).toFixed(1) }}万</b>
                        </div>
                      </div>
                    </div>
                  </div>
                </n-card>
              </n-gi>
            </n-grid>
          </section>

          <!-- 渠道对比卡片 -->
          <section :aria-labelledby="'sampling-section-channels'" class="mb-6">
          <h2 id="sampling-section-channels" class="text-base font-semibold text-slate-800 mb-3"><span class="text-slate-400 font-normal mr-2">03</span>各板块情况</h2>
          <n-grid :cols="3" :x-gap="16" :y-gap="16" class="mb-6" responsive="screen" item-responsive>
            <n-gi v-for="ch in roiData.summary.channels" :key="ch.channel" span="1 m:1 l:1">
              <n-card :bordered="false" segmented class="h-full">
                <template #header>
                  <div class="flex items-baseline gap-2">
                    <span class="text-base font-bold" :class="channelColorClass(ch.channel)" :aria-label="ch.channel">
                      <span aria-hidden="true" class="mr-1">{{ channelIcon(ch.channel) }}</span>
                      {{ ch.channel }}
                    </span>
                    <span v-if="ch.channel === 'TTL派样'" class="text-xs font-normal text-slate-400">
                      (全渠道汇总)
                    </span>
                  </div>
                </template>

                <n-grid :cols="5" :x-gap="12">
                  <n-gi>
                    <n-statistic label="派样人数" :value="ch.sample_users" />
                  </n-gi>
                  <n-gi>
                    <n-statistic label="回购人数">
                      <template #default>
                        <div class="flex items-baseline gap-1.5">
                          <span class="text-3xl font-bold tabular-nums text-slate-800">{{ formatNumber(ch.repurchase_users) }}</span>
                          <span
                            v-if="compareValue(ch, 'repurchase_users', 'pct') != null"
                            class="text-xs tabular-nums text-slate-400"
                            :aria-label="`同比 ${formatDelta(compareValue(ch, 'repurchase_users', 'pct'), '%')}`"
                          >
                            {{ formatDelta(compareValue(ch, 'repurchase_users', 'pct'), '%') }}
                          </span>
                        </div>
                      </template>
                    </n-statistic>
                  </n-gi>
                  <n-gi>
                    <n-statistic label="回购率">
                      <template #default>
                        <div class="flex items-baseline gap-1.5">
                          <span class="text-3xl font-bold tabular-nums text-indigo-600">
                            {{ formatPercent(ch.repurchase_rate) }}
                          </span>
                          <span
                            v-if="compareValue(ch, 'repurchase_rate', 'pp') != null"
                            class="text-xs tabular-nums text-slate-400"
                            :aria-label="`同比 ${formatDelta(compareValue(ch, 'repurchase_rate', 'pp'), 'pp')}`"
                          >
                            {{ formatDelta(compareValue(ch, 'repurchase_rate', 'pp'), 'pp') }}
                          </span>
                        </div>
                      </template>
                    </n-statistic>
                  </n-gi>
                  <n-gi>
                    <n-statistic label="贡献GSV">
                      <template #default>
                        <div class="flex items-baseline gap-1.5">
                          <span class="text-3xl font-bold tabular-nums text-emerald-600">
                            {{ formatCurrency(ch.repurchase_gsv, 'wan') }}
                          </span>
                          <span
                            v-if="compareValue(ch, 'repurchase_gsv', 'pct') != null"
                            class="text-xs tabular-nums text-slate-400"
                            :aria-label="`同比 ${formatDelta(compareValue(ch, 'repurchase_gsv', 'pct'), '%')}`"
                          >
                            {{ formatDelta(compareValue(ch, 'repurchase_gsv', 'pct'), '%') }}
                          </span>
                        </div>
                      </template>
                    </n-statistic>
                  </n-gi>
                  <n-gi>
                    <n-statistic label="AUS">
                      <template #default>
                        <div class="flex items-baseline gap-1.5">
                          <!-- Sprint 146: AUS 降级为次要指标 (text-slate-500 而非 sky-600) -->
                          <span class="text-2xl font-semibold tabular-nums text-slate-500">
                            {{ formatCurrency(ch.repurchase_aus, 'yuan', 0) }}
                          </span>
                          <span
                            v-if="compareValue(ch, 'repurchase_aus', 'pct') != null"
                            class="text-xs tabular-nums text-slate-400"
                            :aria-label="`同比 ${formatDelta(compareValue(ch, 'repurchase_aus', 'pct'), '%')}`"
                          >
                            {{ formatDelta(compareValue(ch, 'repurchase_aus', 'pct'), '%') }}
                          </span>
                        </div>
                      </template>
                    </n-statistic>
                  </n-gi>
                </n-grid>

                <!-- 当前窗口概览 -->
                <n-divider />
                <div class="flex items-center gap-6 text-sm text-slate-500">
                  <span>{{ windowDays }}天回购: <b class="text-slate-700">{{ formatNumber(ch.repurchase_users) }}</b> 人 ({{ formatPercent(ch.repurchase_rate) }})</span>
                  <span>贡献GSV: <b class="text-slate-700">{{ formatCurrency(ch.repurchase_gsv, 'wan') }}</b></span>
                  <span>AUS: <b class="text-slate-700">{{ formatCurrency(ch.repurchase_aus, 'yuan', 0) }}</b></span>
                </div>

                <n-divider />
                <div class="grid grid-cols-2 gap-4">
                  <div>
                    <div class="text-xs font-semibold text-rose-600 mb-1">{{ windowDays }}天正装回购</div>
                    <div class="text-sm text-slate-600">
                      人数: <b class="text-slate-800">{{ formatNumber(ch.full_repurchase_users) }}</b>
                      ({{ formatPercent(ch.full_repurchase_rate) }})
                    </div>
                    <div class="text-sm text-slate-600">
                      GSV: <b class="text-emerald-700">{{ formatCurrency(ch.full_repurchase_gsv, 'wan') }}</b>
                      · AUS {{ formatCurrency(ch.full_repurchase_aus, 'yuan', 0) }}
                    </div>
                  </div>
                  <div>
                    <div class="text-xs font-semibold text-slate-500 mb-1">非正装回购 (小样/赠品等)</div>
                    <div class="text-sm text-slate-600">
                      人数: <b class="text-slate-800">{{ formatNumber(ch.nonfull_repurchase_users) }}</b>
                    </div>
                    <div class="text-sm text-slate-600">
                      GSV: <b class="text-slate-700">{{ formatCurrency(ch.nonfull_repurchase_gsv, 'wan') }}</b>
                      · AUS {{ formatCurrency(ch.nonfull_repurchase_aus, 'yuan', 0) }}
                    </div>
                  </div>
                </div>
              </n-card>
            </n-gi>
          </n-grid>
          </section>

          <!-- 品类明细表格 -->
          <section :aria-labelledby="'sampling-section-detail'" class="mb-6">
          <h2 id="sampling-section-detail" class="text-base font-semibold text-slate-800 mb-3"><span class="text-slate-400 font-normal mr-2">04</span>派样明细</h2>
          <n-card :bordered="false" segmented>
            <template #header>
              <span class="text-sm font-semibold text-slate-700">按 {{ levelLabel }} 明细</span>
            </template>
            <n-data-table
              :columns="categoryCols"
              :data="roiData.category_breakdown"
              :bordered="false"
              :single-line="false"
              :scroll-x="1500"
              size="small"
              striped
            />
          </n-card>
          </section>

          <section
            v-if="repurchaseDistribution"
            :aria-labelledby="'sampling-section-buckets'"
            class="mt-6"
          >
            <h2 id="sampling-section-buckets" class="text-base font-semibold text-slate-800 mb-3"><span class="text-slate-400 font-normal mr-2">05</span>回购周期分布</h2>
            <n-card :bordered="false" segmented>
              <!-- Sprint 147 P2.1: 视觉柱状图 (decorative), 屏幕阅读器读下面的 sr-only table -->
              <div class="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4 items-end" style="min-height: 220px" aria-hidden="true">
                <div v-for="bucket in repurchaseBuckets" :key="bucket.bucket" class="text-center">
                  <div class="text-xs text-slate-500 mb-2">{{ bucket.bucket }}</div>
                  <div class="mx-auto flex items-end justify-center" style="height: 148px">
                    <div
                      class="rounded-t transition-all"
                      :style="{
                        backgroundColor: '#6366f1',
                        width: '32px',
                        height: bucket.height + 'px',
                        minHeight: '6px',
                      }"
                    ></div>
                  </div>
                  <div class="text-sm font-bold tabular-nums text-slate-800 mt-2">{{ formatNumber(bucket.users) }} 人</div>
                  <div class="text-xs tabular-nums text-slate-500">GSV {{ formatCurrency(bucket.gsv, 'wan') }}</div>
                  <div class="text-xs tabular-nums text-slate-400">AUS {{ formatCurrency(bucket.aus, 'yuan', 0) }}</div>
                </div>
              </div>
              <!-- Sprint 147 P2.1: screen reader 友好的真 table (视觉隐藏) -->
              <table class="sr-only">
                <caption>回购周期分布</caption>
                <thead>
                  <tr>
                    <th scope="col">回购周期</th>
                    <th scope="col">人数</th>
                    <th scope="col">贡献 GSV</th>
                    <th scope="col">客单价 (AUS)</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="bucket in repurchaseBuckets" :key="bucket.bucket">
                    <th scope="row">{{ bucket.bucket }}</th>
                    <td>{{ formatNumber(bucket.users) }} 人</td>
                    <td>{{ formatCurrency(bucket.gsv, 'wan') }}</td>
                    <td>{{ formatCurrency(bucket.aus, 'yuan', 0) }}</td>
                  </tr>
                </tbody>
              </table>
            </n-card>
          </section>
        </template>
      </n-tab-pane>

      <!-- Tab 2: 0.01派样分析 -->
      <n-tab-pane name="lock" tab="0.01派样分析">
        <div class="flex items-center gap-3 mb-4">
          <n-select
            v-model:value="campaignName"
            :options="campaignOptions"
            style="width: 120px"
            size="small"
          />
          <n-select
            v-model:value="campaignYear"
            :options="yearOptions"
            style="width: 100px"
            size="small"
          />
        </div>

        <loading-state v-if="lockLoading" />
        <error-state v-else-if="lockError" :message="getErrorMessage(lockError)" />

        <template v-else-if="lockData">
          <!-- 活动信息 -->
          <n-card :bordered="false" segmented class="mb-4">
            <div class="flex items-center gap-6 text-sm">
              <span class="text-slate-500">锁权期:
                <b class="text-slate-700">{{ lockData.campaign_info.lock_start || '—' }} ~ {{ lockData.campaign_info.lock_end || '—' }}</b>
              </span>
              <span class="text-slate-500">转化期:
                <b class="text-slate-700">{{ lockData.campaign_info.conversion_start || '—' }} ~ {{ lockData.campaign_info.conversion_end || '—' }}</b>
              </span>
            </div>
          </n-card>

          <!-- 漏斗指标卡片 -->
          <n-grid :cols="4" :x-gap="16" :y-gap="16" class="mb-6" responsive="screen">
            <n-gi>
              <metric-card title="全店UV" :value="(lockData.current_year.total_uv ?? 0).toLocaleString()" />
            </n-gi>
            <n-gi>
              <metric-card title="锁权人数" :value="(lockData.current_year.locked_users ?? 0).toLocaleString()" :subtitle="`锁权率 ${fmtPct(lockData.current_year.lock_rate, 2)}`" />
            </n-gi>
            <n-gi>
              <metric-card title="转化人数" :value="(lockData.current_year.converted_users ?? 0).toLocaleString()" :subtitle="`转化率 ${fmtPct(lockData.current_year.conversion_rate)}`" />
            </n-gi>
            <n-gi>
              <metric-card title="锁权GSV" :value="fmtGsv(lockData.current_year.lock_gsv ?? 0)" :subtitle="`AUS ¥${(lockData.current_year.lock_aus ?? 0).toFixed(0)}`" />
            </n-gi>
          </n-grid>

          <!-- 漏斗可视化 -->
          <n-card :bordered="false" segmented class="mb-6">
            <template #header>
              <span class="text-sm font-semibold text-slate-700">转化漏斗</span>
            </template>
            <div class="flex items-center justify-center gap-4 py-4">
              <template v-for="(step, idx) in funnelSteps" :key="idx">
                <div class="text-center">
                  <div
                    class="rounded-lg px-6 py-4 text-white font-bold text-lg shadow-md transition-all"
                    :style="{
                      backgroundColor: step.color,
                      minWidth: '140px',
                      opacity: idx === 0 ? 1 : Math.max(0.4, 1 - idx * 0.15)
                    }"
                  >
                    {{ step.isGsv ? `¥${((step.value ?? 0) / 1e4).toFixed(1)}万` : (step.value ?? 0).toLocaleString() }}
                  </div>
                  <div class="text-xs text-slate-500 mt-2 font-medium">{{ step.label }}</div>
                </div>
                <div v-if="idx < funnelSteps.length - 1" class="text-slate-300 text-2xl">→</div>
              </template>
            </div>
            <!-- 转化率标注 -->
            <div class="flex items-center justify-center gap-8 text-xs text-slate-400 mt-2">
              <span>锁权率: {{ fmtPct(lockData.current_year.lock_rate, 2) }}</span>
              <span>转化率: {{ fmtPct(lockData.current_year.conversion_rate) }}</span>
            </div>
          </n-card>

          <!-- YoY对比表 -->
          <n-card :bordered="false" segmented class="mb-6">
            <template #header>
              <span class="text-sm font-semibold text-slate-700">
                同期对比: {{ campaignYear }} vs {{ campaignYear - 1 }}
              </span>
            </template>
            <n-data-table
              :columns="lockCols"
              :data="lockMetricRows"
              :bordered="false"
              :single-line="false"
              :scroll-x="600"
              size="small"
              striped
            />
          </n-card>

          <!-- 新客拆分 -->
          <n-grid :cols="4" :x-gap="16" :y-gap="16" responsive="screen">
            <n-gi>
              <metric-card
                title="新客锁权人数"
                :value="(lockData.current_year.new_locked_users ?? 0).toLocaleString()"
                :subtitle="`占比 ${fmtPct(lockData.current_year.new_locked_ratio)}`"
              />
            </n-gi>
            <n-gi>
              <metric-card
                title="新客转化人数"
                :value="(lockData.current_year.new_converted_users ?? 0).toLocaleString()"
                :subtitle="`转化率 ${fmtPct(lockData.current_year.new_conversion_rate)}`"
              />
            </n-gi>
            <n-gi>
              <metric-card
                title="新客锁权GSV"
                :value="fmtGsv(lockData.current_year.new_lock_gsv ?? 0)"
                :subtitle="`AUS ¥${(lockData.current_year.new_lock_aus ?? 0).toFixed(0)}`"
              />
            </n-gi>
            <n-gi>
              <metric-card
                title="老客锁权人数"
                :value="oldLockedUsers.toLocaleString()"
                :subtitle="`占比 ${(oldLockedRatio * 100).toFixed(1)}%`"
              />
            </n-gi>
          </n-grid>
        </template>
      </n-tab-pane>

      <!-- Tab 3: Cohort 留存矩阵 -->
      <n-tab-pane name="cohort" tab="Cohort 留存矩阵">
        <CohortRetentionMatrix
          :start-month="cohortStartMonth"
          :end-month="cohortEndMonth"
          :channel="cohortChannel"
        />
      </n-tab-pane>

      <!-- Tab 4: 0.01派样滚动同期对比 -->
      <n-tab-pane name="rolling" tab="滚动同期对比">
        <!-- 参数配置区 -->
        <n-card :bordered="false" segmented class="mb-4">
          <template #header>
            <span class="text-sm font-semibold text-slate-700">对比参数配置</span>
          </template>
          <n-grid :cols="2" :x-gap="24" :y-gap="12">
            <!-- 2026年 -->
            <n-gi>
              <div class="text-xs font-bold text-indigo-600 mb-2">2026年（当年）</div>
              <div class="flex flex-col gap-2">
                <div class="flex items-center gap-2">
                  <span class="text-xs text-slate-500 w-16">派样期</span>
                  <n-date-picker v-model:value="rollingY2026SampleStart" type="date" size="small" style="width:150px" />
                  <span class="text-xs text-slate-400">→</span>
                  <n-date-picker v-model:value="rollingY2026SampleEnd" type="date" size="small" style="width:150px" />
                </div>
                <div class="flex items-center gap-2">
                  <span class="text-xs text-slate-500 w-16">转化期</span>
                  <n-date-picker v-model:value="rollingY2026ConvStart" type="date" size="small" style="width:150px" />
                </div>
              </div>
            </n-gi>
            <!-- 2025年 -->
            <n-gi>
              <div class="text-xs font-bold text-emerald-600 mb-2">2025年（对比年）</div>
              <div class="flex flex-col gap-2">
                <div class="flex items-center gap-2">
                  <span class="text-xs text-slate-500 w-16">派样期</span>
                  <n-date-picker v-model:value="rollingY2025SampleStart" type="date" size="small" style="width:150px" />
                  <span class="text-xs text-slate-400">→</span>
                  <n-date-picker v-model:value="rollingY2025SampleEnd" type="date" size="small" style="width:150px" />
                </div>
                <div class="flex items-center gap-2">
                  <span class="text-xs text-slate-500 w-16">转化期</span>
                  <n-date-picker v-model:value="rollingY2025ConvStart" type="date" size="small" style="width:150px" />
                </div>
              </div>
            </n-gi>
          </n-grid>
        </n-card>

        <!-- 滚动截止日滑块 -->
        <n-card :bordered="false" segmented class="mb-4">
          <div class="flex items-center gap-4">
            <span class="text-sm text-slate-500 whitespace-nowrap">滚动截止日:</span>
            <n-date-picker
              v-model:value="rollingEndTs"
              type="date"
              size="small"
              :is-date-disabled="(ts: number) => ts > rollingMaxTs"
              style="width: 150px"
            />
          </div>
          <div v-if="rollingData" class="mt-3 text-xs text-slate-400">
            T = {{ rollingData.timeline.T }}天
            | 2025等价截止: {{ rollingData.timeline.year_b_equiv_end }}
            | {{ rollingData.year_a.phase === 'conversion' ? '当前阶段：转化期' : '当前阶段：派样期' }}
          </div>
        </n-card>

        <loading-state v-if="rollingLoading" />
        <error-state v-else-if="rollingError" :message="getErrorMessage(rollingError)" />

        <template v-else-if="rollingData">
          <!-- 核心指标卡片 -->
          <n-grid :cols="4" :x-gap="16" :y-gap="16" class="mb-6" responsive="screen">
            <n-gi>
              <metric-card
                title="全店UV"
                :value="rollingData.year_a.total_uv.toLocaleString()"
                :subtitle="`YoY ${fmtYoy(rollingData.yoy.total_uv, false)}`"
              />
            </n-gi>
            <n-gi>
              <metric-card
                title="锁权人数"
                :value="rollingData.year_a.locked_users.toLocaleString()"
                :subtitle="`锁权率 ${fmtPct(rollingData.year_a.lock_rate, 2)}`"
              />
            </n-gi>
            <n-gi v-if="rollingData.year_a.phase === 'conversion'">
              <metric-card
                title="加赠转化人数"
                :value="rollingData.year_a.converted_users.toLocaleString()"
                :subtitle="`转化率 ${fmtPct(rollingData.year_a.conversion_rate)}`"
              />
            </n-gi>
            <n-gi v-if="rollingData.year_a.phase === 'conversion'">
              <metric-card
                title="转化GSV"
                :value="fmtGsv(rollingData.year_a.conv_gsv)"
                :subtitle="`AUS ¥${rollingData.year_a.conv_aus.toFixed(0)}`"
              />
            </n-gi>
            <n-gi v-if="rollingData.year_a.phase === 'sample'">
              <metric-card
                title="新客锁权人数"
                :value="rollingData.year_a.new_locked_users.toLocaleString()"
                :subtitle="`占比 ${fmtPct(rollingData.year_a.new_locked_ratio)}`"
              />
            </n-gi>
            <n-gi v-if="rollingData.year_a.phase === 'sample'">
              <metric-card
                title="老客锁权人数"
                :value="rollingData.year_a.old_locked_users.toLocaleString()"
                :subtitle="`占比 ${fmtPct(rollingData.year_a.old_locked_ratio)}`"
              />
            </n-gi>
          </n-grid>

          <!-- YoY 对比表 -->
          <n-card :bordered="false" segmented class="mb-6">
            <template #header>
              <span class="text-sm font-semibold text-slate-700">
                同期对比: 2026 vs 2025（自动对齐）
                <span class="ml-2 text-xs font-normal" :class="rollingData.year_a.phase === 'conversion' ? 'text-purple-500' : 'text-amber-500'">
                  {{ rollingData.year_a.phase === 'conversion' ? '▸ 转化期' : '▸ 派样期' }}
                </span>
              </span>
            </template>
            <n-data-table
              :columns="rollingCols"
              :data="rollingMetricRows"
              :bordered="false"
              :single-line="false"
              :scroll-x="600"
              size="small"
              striped
            />
          </n-card>

          <!-- 新客/老客拆分（转化期时展示） -->
          <n-grid v-if="rollingData.year_a.phase === 'conversion'" :cols="4" :x-gap="16" :y-gap="16" responsive="screen">
            <n-gi>
              <metric-card
                title="新客转化人数"
                :value="rollingData.year_a.new_converted_users.toLocaleString()"
                :subtitle="`转化率 ${fmtPct(rollingData.year_a.new_conversion_rate)}`"
              />
            </n-gi>
            <n-gi>
              <metric-card
                title="新客转化GSV"
                :value="fmtGsv(rollingData.year_a.new_conv_gsv)"
                :subtitle="`AUS ¥${rollingData.year_a.new_conv_aus.toFixed(0)}`"
              />
            </n-gi>
            <n-gi>
              <metric-card
                title="老客转化人数"
                :value="rollingData.year_a.old_converted_users.toLocaleString()"
                :subtitle="`转化率 ${fmtPct(rollingData.year_a.old_conversion_rate)}`"
              />
            </n-gi>
            <n-gi>
              <metric-card
                title="2025加赠转化"
                :value="rollingData.year_b.converted_users.toLocaleString()"
                :subtitle="`转化率 ${fmtPct(rollingData.year_b.conversion_rate)}`"
              />
            </n-gi>
          </n-grid>
        </template>
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<style scoped>
.sampling-view {
  max-width: 1200px;
}
</style>
