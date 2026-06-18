<script setup lang="ts">
import { ref, computed } from 'vue'
import { NTabs, NTabPane, NSelect, NDatePicker, NCard, NDataTable, NGrid, NGi, NStatistic, NDivider } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useQuery } from '@tanstack/vue-query'
import PageHeader from '@/components/PageHeader.vue'
import MetricCard from '@/components/MetricCard.vue'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import { fetchSamplingROI, fetchSamplingLockAnalysis, fetchRollingComparison } from '@/api/sampling'
import type { SamplingChannelSummary, SamplingCategoryRow } from '@/api/sampling'

const activeTab = ref('roi')

// ── Tab 1: 派样ROI ──
const roiDateRange = ref<[number, number] | null>(null)
const windowDays = ref(30)
const categoryLevel = ref('spu_category')

const windowOptions = [
  { label: '7天回购', value: 7 },
  { label: '30天回购', value: 30 },
  { label: '60天回购', value: 60 },
]

const levelOptions = [
  { label: '品类销售', value: 'spu_category' },
  { label: '商品梯队', value: 'spu_tier' },
  { label: '单品归类', value: 'spu_product_class' },
]

function fmtDate(ts: number): string {
  const d = new Date(ts)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// 默认日期：本月
const now = new Date()
const defaultStart = new Date(now.getFullYear(), now.getMonth(), 1)
const defaultEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0)
roiDateRange.value = [defaultStart.getTime(), defaultEnd.getTime()]

const roiParams = computed(() => {
  const [s, e] = roiDateRange.value ?? [defaultStart.getTime(), defaultEnd.getTime()]
  return {
    start_date: fmtDate(s),
    end_date: fmtDate(e),
    window_days: windowDays.value,
    level: categoryLevel.value,
  }
})

const { data: roiData, isLoading: roiLoading, error: roiError } = useQuery({
  queryKey: computed(() => ['sampling-roi', roiParams.value]),
  queryFn: () => fetchSamplingROI(roiParams.value),
  enabled: computed(() => activeTab.value === 'roi' && !!roiDateRange.value),
})

const windowField = computed(() => `repurchase_users_${windowDays.value}d` as keyof SamplingChannelSummary)
const gsvField = computed(() => `repurchase_gsv_${windowDays.value}d` as keyof SamplingChannelSummary)
const rateField = computed(() => `repurchase_rate_${windowDays.value}d` as keyof SamplingChannelSummary)
const ausField = computed(() => `repurchase_aus_${windowDays.value}d` as keyof SamplingChannelSummary)

// 安全取值：Vue 模板中不能用 TS 类型断言，用 Number() 转换
function numVal(ch: SamplingChannelSummary, field: keyof SamplingChannelSummary): number {
  return Number(ch[field] ?? 0)
}

// 品类明细表格列
const categoryCols: DataTableColumns<SamplingCategoryRow> = [
  { title: '渠道', key: 'channel', width: 100, fixed: 'left', align: 'center' },
  { title: '品类', key: 'category', width: 130, fixed: 'left' },
  { title: '派样人数', key: 'sample_users', width: 100, align: 'right', render: r => (r.sample_users ?? 0).toLocaleString() },
  { title: '回购人数', key: 'repurchase_users', width: 100, align: 'right', render: r => (r.repurchase_users ?? 0).toLocaleString() },
  { title: '回购率', key: 'repurchase_rate', width: 90, align: 'center', render: r => `${((r.repurchase_rate ?? 0) * 100).toFixed(1)}%` },
  { title: '回购GSV', key: 'repurchase_gsv', width: 120, align: 'right', render: r => `¥${((r.repurchase_gsv ?? 0) / 1e4).toFixed(1)}万` },
  { title: 'AUS', key: 'repurchase_aus', width: 90, align: 'right', render: r => `¥${(r.repurchase_aus ?? 0).toFixed(0)}` },
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
</script>

<template>
  <div class="sampling-view">
    <PageHeader title="派样看板" subtitle="U先/百补派样ROI / 0.01锁权转化分析" />

    <n-tabs v-model:value="activeTab" type="line" animated>
      <!-- Tab 1: 派样ROI分析 -->
      <n-tab-pane name="roi" tab="派样ROI分析">
        <div class="flex items-center gap-3 mb-4 flex-wrap">
          <n-date-picker
            v-model:value="roiDateRange"
            type="daterange"
            clearable
            style="width: 280px"
            size="small"
          />
          <n-select
            v-model:value="windowDays"
            :options="windowOptions"
            style="width: 120px"
            size="small"
          />
          <n-select
            v-model:value="categoryLevel"
            :options="levelOptions"
            style="width: 120px"
            size="small"
          />
        </div>

        <loading-state v-if="roiLoading" />
        <error-state v-else-if="roiError" :message="getErrorMessage(roiError)" />

        <template v-else-if="roiData">
          <!-- 渠道对比卡片 -->
          <n-grid :cols="2" :x-gap="16" :y-gap="16" class="mb-6" responsive="screen">
            <n-gi v-for="ch in roiData.summary.channels" :key="ch.channel">
              <n-card :bordered="false" segmented>
                <template #header>
                  <span class="text-base font-bold" :class="ch.channel === 'U先派样' ? 'text-rose-600' : 'text-orange-500'">
                    {{ ch.channel }}
                  </span>
                </template>

                <n-grid :cols="5" :x-gap="12">
                  <n-gi>
                    <n-statistic label="派样人数" :value="ch.sample_users" />
                  </n-gi>
                  <n-gi>
                    <n-statistic label="回购人数" :value="numVal(ch, windowField)" />
                  </n-gi>
                  <n-gi>
                    <n-statistic label="回购率">
                      <template #default>
                        <span class="text-indigo-600 font-bold">
                          {{ (numVal(ch, rateField) * 100).toFixed(1) }}%
                        </span>
                      </template>
                    </n-statistic>
                  </n-gi>
                  <n-gi>
                    <n-statistic label="贡献GSV">
                      <template #default>
                        <span class="text-emerald-600 font-bold">
                          ¥{{ (numVal(ch, gsvField) / 1e4).toFixed(1) }}万
                        </span>
                      </template>
                    </n-statistic>
                  </n-gi>
                  <n-gi>
                    <n-statistic label="AUS">
                      <template #default>
                        <span class="text-sky-600 font-bold">
                          ¥{{ numVal(ch, ausField).toFixed(0) }}
                        </span>
                      </template>
                    </n-statistic>
                  </n-gi>
                </n-grid>

                <!-- 三窗口对比 -->
                <n-divider />
                <div class="flex items-center gap-6 text-sm text-slate-500">
                  <span>7天回购: <b class="text-slate-700">{{ (ch.repurchase_users_7d ?? 0).toLocaleString() }}</b> 人 ({{ ((ch.repurchase_rate_7d ?? 0) * 100).toFixed(1) }}%)</span>
                  <span>30天回购: <b class="text-slate-700">{{ (ch.repurchase_users_30d ?? 0).toLocaleString() }}</b> 人 ({{ ((ch.repurchase_rate_30d ?? 0) * 100).toFixed(1) }}%)</span>
                  <span>60天回购: <b class="text-slate-700">{{ (ch.repurchase_users_60d ?? 0).toLocaleString() }}</b> 人 ({{ ((ch.repurchase_rate_60d ?? 0) * 100).toFixed(1) }}%)</span>
                </div>
              </n-card>
            </n-gi>
          </n-grid>

          <!-- 品类明细表格 -->
          <n-card :bordered="false" segmented>
            <template #header>
              <span class="text-sm font-semibold text-slate-700">品类回购明细</span>
            </template>
            <n-data-table
              :columns="categoryCols"
              :data="roiData.category_breakdown"
              :bordered="false"
              :single-line="false"
              :scroll-x="1100"
              size="small"
              striped
            />
          </n-card>
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

      <!-- Tab 3: 0.01派样滚动同期对比 -->
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
