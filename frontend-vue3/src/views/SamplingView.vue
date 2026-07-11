<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { NTabs, NTabPane, NSelect, NCard, NGrid, NGi, NDivider, NAlert, NSlider } from 'naive-ui'
import { useQuery } from '@tanstack/vue-query'
import PageHeader from '@/components/PageHeader.vue'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import YOYGuard from '@/components/YOYGuard.vue'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import { fetchSamplingROI, fetchSamplingRepurchaseTracking } from '@/api/sampling'
import type { SamplingCategoryRow, SamplingChannelSummary } from '@/api/sampling'
import ExportToolbar from '@/components/ExportToolbar.vue'
import type { XlsxColumn } from '@/utils/exportXlsx'
import { useFilterStore } from '@/stores/filterStore'
import { useFormat } from '@/composables/useFormat'
import { useRouteHashTab } from '@/composables/useRouteHashTab'

const { formatNumber, formatPercent, formatCurrency } = useFormat()

const activeTab = ref('roi')
useRouteHashTab(activeTab, ['roi'])
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

// ── Sprint 169 02 板块"回购周期分布" 3 年对比柱状图 ──
// 02 板块"回购周期分布" 3 年对比 — 只跟顶部主导航当前日期联动
// 跟 top filterStore.dateRange 1:1 一致 (cur 期间 = top 选择区, ly/prev2 = -1y/-2y)
// 不跟 01/02 的 7-90 天滑块联动：固定 90 天回购窗口，保证 3 年同期间口径一致
const trackingParams = computed(() => ({
  start_date: filterStore.dateRange[0],
  end_date: filterStore.dateRange[1],
  window_days: 90,
  channel: filterStore.channel === '全店' ? undefined : filterStore.channel,
}))
const { data: trackingData, isLoading: trackingLoading, error: trackingError, refetch: refetchTracking } = useQuery({
  queryKey: computed(() => ['sampling-repurchase-tracking', trackingParams.value]),
  queryFn: () => fetchSamplingRepurchaseTracking(trackingParams.value),
  enabled: computed(() => activeTab.value === 'roi'),
  placeholderData: previousData => previousData,
})

// 3 系列配色（参考健康页 R 区间"回购率 3 年对比"）: 2026 紫 / 2025 蓝 / 2024 灰
const TRACKING_COLORS = ['#533afd', '#60a5fa', '#94a3b8'] as const
const TRACKING_BUCKETS = ['0-7d', '8-30d', '31-60d', '61-90d'] as const
const trackingChartOption = computed(() => {
  const data = trackingData.value
  if (!data) return {}
  const yearLabels = data.year_labels ?? ['2026年', '2025年', '2024年']
  // 按 year_label 索引化桶数据，方便快速查找
  // (schema_test 模式下 backend 不返回 buckets, null guard 防 TypeError: e.buckets is not iterable)
  const byYearBucket = new Map<string, number>()
  for (const b of (data.buckets ?? [])) byYearBucket.set(`${b.year_label}|${b.bucket}`, b.rate)
  return {
    color: [...TRACKING_COLORS],
    grid: { left: 50, right: 24, top: 36, bottom: 36, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any[]) => {
        const bucket = params[0]?.axisValueLabel ?? ''
        const lines = [`<div class="font-semibold mb-1">回购间隔 ${bucket}</div>`]
        for (const p of params) {
          const dot = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:6px"></span>`
          lines.push(`<div style="display:flex;align-items:center;gap:6px;font-size:12px">${dot}<span style="color:#64748b">${p.seriesName}:</span><span style="font-weight:500;color:#0f172a">${((p.value ?? 0) * 100).toFixed(2)}%</span></div>`)
        }
        return lines.join('')
      },
    },
    legend: {
      data: yearLabels,
      top: 6,
      right: 8,
      icon: 'circle',
      itemWidth: 8,
      itemHeight: 8,
      textStyle: { color: '#475569', fontSize: 12 },
    },
    xAxis: {
      type: 'category',
      data: [...TRACKING_BUCKETS],
      axisLine: { lineStyle: { color: '#cbd5e1' } },
      axisLabel: { color: '#475569', fontSize: 12 },
    },
    yAxis: {
      type: 'value',
      name: '分布率',
      nameTextStyle: { color: '#94a3b8', fontSize: 11 },
      axisLine: { show: false },
      axisLabel: { color: '#475569', fontSize: 11, formatter: (v: number) => `${(v * 100).toFixed(1)}%` },
      splitLine: { lineStyle: { color: '#f1f5f9' } },
    },
    series: yearLabels.map((yearLabel, idx) => ({
      name: yearLabel,
      type: 'bar',
      barWidth: '20%',
      itemStyle: { color: TRACKING_COLORS[idx] ?? TRACKING_COLORS[0]!, borderRadius: [4, 4, 0, 0] },
      data: TRACKING_BUCKETS.map((bucket) => byYearBucket.get(`${yearLabel}|${bucket}`) ?? 0),
    })),
  }
})
// Sprint 177 P1-5: 02 板块 XLSX 列定义 (拍平 4 桶 × 3 年 = 12 行)
const trackingColumnsXlsx = computed<XlsxColumn[]>(() => {
  const yearLabels = trackingData.value?.year_labels ?? ['2026年', '2025年', '2024年']
  const cols: XlsxColumn[] = [
    { header: '回购间隔', key: 'bucket', width: 12 },
  ]
  for (const yl of yearLabels) {
    cols.push({ header: yl, key: `${yl}_rate`, width: 12, numFmt: '0.00%' })
  }
  return cols
})

// Sprint 177 P1-5: 02 板块 XLSX 数据 (按桶 × 年份 拍平)
const trackingDataXlsx = computed(() => {
  const d = trackingData.value
  if (!d) return []
  const buckets = d.buckets ?? []
  const yearLabels = d.year_labels ?? []
  const byKey = new Map<string, number>()
  for (const b of buckets) byKey.set(`${b.year_label}|${b.bucket}`, b.rate)
  const bucketSet = new Set<string>()
  for (const b of buckets) bucketSet.add(b.bucket)
  const sortedBuckets = [...bucketSet].sort()
  return sortedBuckets.map(bucket => {
    const row: Record<string, any> = { bucket }
    for (const yl of yearLabels) {
      row[`${yl}_rate`] = byKey.get(`${yl}|${bucket}`) ?? 0
    }
    return row
  })
})

// Sprint 177 P0-2: 删 exportTrackingPng, 改用 ExportToolbar 统一入口
const trackingChartRef = ref<{ getChartInstance: () => any; exportAsPng: (name: string) => void } | null>(null)

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

// Sprint 155 ② 03 板块 3 卡横排对齐 — TTL 在前, U先 + 百补 紧随
const allChannels = computed<SamplingChannelSummary[]>(() => {
  const all = roiData.value?.summary.channels ?? []
  const ttl = all.find(c => c.channel === 'TTL派样')
  const subs = all.filter(c => c.channel !== 'TTL派样')
  return ttl ? [ttl, ...subs] : all
})

// Sprint 177 P0-3: 渠道对比卡去掉 emoji (Sprint 172 拍板), 改用文字首字符标 + 颜色块做色盲友好
function channelIcon(channel: string): string {
  if (channel === 'TTL派样') return 'T'
  if (channel === 'U先派样') return 'U'
  if (channel === '百补派样') return '百'
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

function totalCompareValue(baseKey: string, kind: 'pct' | 'pp'): number | null | undefined {
  return ttlSummary.value ? compareValue(ttlSummary.value, baseKey, kind) : null
}

function deltaToneClass(value: number | null | undefined): string {
  if (value == null) return 'sampling-delta-badge--empty'
  if (value > 0) return 'sampling-delta-badge--up'
  if (value < 0) return 'sampling-delta-badge--down'
  return 'sampling-delta-badge--flat'
}

const compareModeLabel = computed(() => filterStore.compareMode === 'auto_mom' ? '环比' : '同比')

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

// 品类明细表格 — Sprint 155 ③ 改 native table + manual rowspan 合并渠道 + 自定义 sort
type CategoryCol = { key: keyof SamplingCategoryRow; title: string; align: 'left' | 'right' | 'center'; format: (r: SamplingCategoryRow) => string; isString?: boolean }
const categoryColumns: CategoryCol[] = [
  { key: 'category', title: '品类', align: 'left', format: r => r.category ?? '—', isString: true },
  { key: 'sample_users', title: '派样人数', align: 'right', format: r => (r.sample_users ?? 0).toLocaleString() },
  { key: 'repurchase_users', title: '回购人数', align: 'right', format: r => (r.repurchase_users ?? 0).toLocaleString() },
  { key: 'repurchase_rate', title: '回购率', align: 'center', format: r => `${((r.repurchase_rate ?? 0) * 100).toFixed(1)}%` },
  { key: 'repurchase_gsv', title: '回购GSV', align: 'right', format: r => `¥${((r.repurchase_gsv ?? 0) / 1e4).toFixed(1)}万` },
  { key: 'repurchase_aus', title: 'AUS', align: 'right', format: r => `¥${(r.repurchase_aus ?? 0).toFixed(0)}` },
  { key: 'full_repurchase_users', title: '正装回购人数', align: 'right', format: r => (r.full_repurchase_users ?? 0).toLocaleString() },
  { key: 'full_repurchase_rate', title: '正装回购率', align: 'center', format: r => `${((r.full_repurchase_rate ?? 0) * 100).toFixed(1)}%` },
  { key: 'full_repurchase_gsv', title: '正装回购GSV', align: 'right', format: r => `¥${((r.full_repurchase_gsv ?? 0) / 1e4).toFixed(1)}万` },
  { key: 'full_repurchase_aus', title: '正装AUS', align: 'right', format: r => `¥${(r.full_repurchase_aus ?? 0).toFixed(0)}` },
  { key: 'same_category_repurchase', title: '同品类回购', align: 'right', format: r => (r.same_category_repurchase ?? 0).toLocaleString() },
  { key: 'same_category_rate', title: '同品类回购率', align: 'center', format: r => `${((r.same_category_rate ?? 0) * 100).toFixed(1)}%` },
]

// ── Sprint 175 Q4 XLSX 导出 (04 派样明细) — Sprint 177 P0-4 精度统一 (pp/pct 全部 2 位) ──
const categoryColumnsXlsx: XlsxColumn[] = [
  { header: '渠道', key: 'channel', width: 12 },
  { header: '品类', key: 'category', width: 16 },
  { header: '派样人数', key: 'sample_users', width: 12, numFmt: '#,##0' },
  { header: '回购人数', key: 'repurchase_users', width: 12, numFmt: '#,##0' },
  { header: '回购率', key: 'repurchase_rate', width: 12, numFmt: '0.00%' },
  { header: '回购GSV', key: 'repurchase_gsv', width: 14, numFmt: '¥#,##0' },
  { header: 'AUS', key: 'repurchase_aus', width: 12, numFmt: '¥#,##0' },
  { header: '正装回购人数', key: 'full_repurchase_users', width: 14, numFmt: '#,##0' },
  { header: '正装回购率', key: 'full_repurchase_rate', width: 12, numFmt: '0.00%' },
  { header: '正装回购GSV', key: 'full_repurchase_gsv', width: 14, numFmt: '¥#,##0' },
  { header: '正装AUS', key: 'full_repurchase_aus', width: 12, numFmt: '¥#,##0' },
  { header: '同品类回购', key: 'same_category_repurchase', width: 12, numFmt: '#,##0' },
  { header: '同品类回购率', key: 'same_category_rate', width: 12, numFmt: '0.00%' },
  // Sprint 175 Q5: YOY 列 (跨 sprint 复用 _add_compare_metrics 模式) — Sprint 177 P0-4 全部 2 位
  // L4.91 PR2 (2026-07-11) 治本: 加显式 kind enum (auto-detect suffix pattern 能匹配但 SSOT 要求显式声明)
  { header: '回购人数YoY', key: 'repurchase_users_yoy_pct', kind: 'yoy_pct', width: 12, numFmt: '+0.00%;-0.00%;0.00%' },
  { header: '回购GSV YoY', key: 'repurchase_gsv_yoy_pct', kind: 'yoy_pct', width: 12, numFmt: '+0.00%;-0.00%;0.00%' },
  { header: '回购率 YoY(pp)', key: 'repurchase_rate_yoy_pp', kind: 'yoy_pp', width: 12, numFmt: '+0.00;-0.00;0.00' },
  { header: '正装回购人数YoY', key: 'full_repurchase_users_yoy_pct', kind: 'yoy_pct', width: 14, numFmt: '+0.00%;-0.00%;0.00%' },
  { header: '正装回购GSV YoY', key: 'full_repurchase_gsv_yoy_pct', kind: 'yoy_pct', width: 14, numFmt: '+0.00%;-0.00%;0.00%' },
  { header: '正装回购率 YoY(pp)', key: 'full_repurchase_rate_yoy_pp', kind: 'yoy_pp', width: 14, numFmt: '+0.00;-0.00;0.00' },
  { header: 'AUS YoY', key: 'repurchase_aus_yoy_pct', kind: 'yoy_pct', width: 12, numFmt: '+0.00%;-0.00%;0.00%' },
  { header: '正装AUS YoY', key: 'full_repurchase_aus_yoy_pct', kind: 'yoy_pct', width: 12, numFmt: '+0.00%;-0.00%;0.00%' },
  { header: '非正装回购GSV YoY', key: 'nonfull_repurchase_gsv_yoy_pct', kind: 'yoy_pct', width: 16, numFmt: '+0.00%;-0.00%;0.00%' },
]

// 排序状态: 默认按 channel (维持原顺序) + 品类 (升序)
const detailSortKey = ref<keyof SamplingCategoryRow>('category')
const detailSortOrder = ref<'asc' | 'desc'>('asc')

function toggleSort(key: keyof SamplingCategoryRow) {
  if (detailSortKey.value === key) {
    detailSortOrder.value = detailSortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    detailSortKey.value = key
    detailSortOrder.value = 'asc'
  }
}

// 排序后行 (按 channel 维持原顺序, 同 channel 内按 sortKey 排序)
const sortedCategoryRows = computed<SamplingCategoryRow[]>(() => {
  const data = roiData.value?.category_breakdown ?? []
  const key = detailSortKey.value
  const order = detailSortOrder.value
  const col = categoryColumns.find(c => c.key === key)
  const sign = order === 'asc' ? 1 : -1
  return [...data].sort((a, b) => {
    // 1. 先按 channel 分组 (维持原顺序: TTL派样 → U先派样 → 百补派样)
    const channelOrder: Record<string, number> = { 'TTL派样': 0, 'U先派样': 1, '百补派样': 2 }
    const ca = channelOrder[a.channel ?? ''] ?? 99
    const cb = channelOrder[b.channel ?? ''] ?? 99
    if (ca !== cb) return ca - cb
    // 2. 同 channel 内按 sortKey 排序
    if (col?.isString) {
      return sign * ((a[key] as string ?? '').localeCompare((b[key] as string ?? '')))
    }
    return sign * (((a[key] as number) ?? 0) - ((b[key] as number) ?? 0))
  })
})

// channel rowspan map: { rowIdx → rowspan } 用于合并 channel 列
const channelRowspans = computed<Map<number, number>>(() => {
  const map = new Map<number, number>()
  const data = sortedCategoryRows.value
  let i = 0
  while (i < data.length) {
    const ch = data[i].channel
    let j = i
    while (j < data.length && data[j].channel === ch) j++
    map.set(i, j - i)  // 起始行 i, 跨 j-i 行
    i = j
  }
  return map
})

// 获取 error 的安全消息（error 类型为 unknown）
function getErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message
  if (typeof err === 'string') return err
  return '请求失败'
}

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
    <PageHeader title="派样看板" subtitle="U先/百补派样正装转化分析" />

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

          <section :aria-labelledby="'sampling-section-overview'" class="sampling-section">
          <h2 id="sampling-section-overview" class="section-title"><span class="section-num">01</span>总览</h2>
          <n-grid :cols="4" :x-gap="16" :y-gap="16" class="mb-4" responsive="screen">
            <n-gi class="min-w-0">
              <div class="sampling-overview-card">
                <div class="sampling-overview-head">
                  <span class="sampling-overview-label">派样人数</span>
                  <span class="sampling-delta-empty">暂无{{ compareModeLabel }}</span>
                </div>
                <div class="sampling-overview-value text-slate-800">
                  {{ formatNumber(totalSampleUsers) }}
                </div>
                <div class="sampling-overview-subrow">TTL (U先 ∪ 百补, 去重)</div>
              </div>
            </n-gi>
            <n-gi class="min-w-0">
              <div class="sampling-overview-card">
                <div class="sampling-overview-head">
                  <span class="sampling-overview-label">{{ windowDays }}天回购人数</span>
                  <span
                    v-if="totalCompareValue('repurchase_users', 'pct') != null"
                    class="sampling-delta-badge"
                    :class="deltaToneClass(totalCompareValue('repurchase_users', 'pct'))"
                  >
                    {{ (totalCompareValue('repurchase_users', 'pct') ?? 0) > 0 ? '↑' : (totalCompareValue('repurchase_users', 'pct') ?? 0) < 0 ? '↓' : '' }}
                    <YOYGuard :value="totalCompareValue('repurchase_users', 'pct')" unit="%" />
                  </span>
                </div>
                <div class="sampling-overview-value text-slate-800">
                  {{ formatNumber(totalRepurchaseUsers) }}
                </div>
                <div class="sampling-overview-subrow">
                  <span>回购率 {{ formatPercent(totalRepurchaseRate) }}</span>
                  <span
                    v-if="totalCompareValue('repurchase_rate', 'pp') != null"
                    class="sampling-delta-badge sampling-delta-badge--mini"
                    :class="deltaToneClass(totalCompareValue('repurchase_rate', 'pp'))"
                  >
                    {{ (totalCompareValue('repurchase_rate', 'pp') ?? 0) > 0 ? '↑' : (totalCompareValue('repurchase_rate', 'pp') ?? 0) < 0 ? '↓' : '' }}
                    <YOYGuard :value="totalCompareValue('repurchase_rate', 'pp')" unit="pp" />
                  </span>
                </div>
              </div>
            </n-gi>
            <n-gi class="min-w-0">
              <div class="sampling-overview-card">
                <div class="sampling-overview-head">
                  <span class="sampling-overview-label">{{ windowDays }}天正装回购人数</span>
                  <span
                    v-if="totalCompareValue('full_repurchase_users', 'pct') != null"
                    class="sampling-delta-badge"
                    :class="deltaToneClass(totalCompareValue('full_repurchase_users', 'pct'))"
                  >
                    {{ (totalCompareValue('full_repurchase_users', 'pct') ?? 0) > 0 ? '↑' : (totalCompareValue('full_repurchase_users', 'pct') ?? 0) < 0 ? '↓' : '' }}
                    <YOYGuard :value="totalCompareValue('full_repurchase_users', 'pct')" unit="%" />
                  </span>
                </div>
                <div class="sampling-overview-value text-rose-600">
                  {{ formatNumber(totalFullRepurchaseUsers) }}
                </div>
                <div class="sampling-overview-subrow">
                  <span>正装转化率 {{ formatPercent(totalFullRepurchaseRate) }}</span>
                  <span
                    v-if="totalCompareValue('full_repurchase_rate', 'pp') != null"
                    class="sampling-delta-badge sampling-delta-badge--mini"
                    :class="deltaToneClass(totalCompareValue('full_repurchase_rate', 'pp'))"
                  >
                    {{ (totalCompareValue('full_repurchase_rate', 'pp') ?? 0) > 0 ? '↑' : (totalCompareValue('full_repurchase_rate', 'pp') ?? 0) < 0 ? '↓' : '' }}
                    <YOYGuard :value="totalCompareValue('full_repurchase_rate', 'pp')" unit="pp" />
                  </span>
                </div>
              </div>
            </n-gi>
            <n-gi class="min-w-0">
              <div class="sampling-overview-card">
                <div class="sampling-overview-head">
                  <span class="sampling-overview-label">{{ windowDays }}天正装 GSV</span>
                  <span
                    v-if="totalCompareValue('full_repurchase_gsv', 'pct') != null"
                    class="sampling-delta-badge"
                    :class="deltaToneClass(totalCompareValue('full_repurchase_gsv', 'pct'))"
                  >
                    {{ (totalCompareValue('full_repurchase_gsv', 'pct') ?? 0) > 0 ? '↑' : (totalCompareValue('full_repurchase_gsv', 'pct') ?? 0) < 0 ? '↓' : '' }}
                    <YOYGuard :value="totalCompareValue('full_repurchase_gsv', 'pct')" unit="%" />
                  </span>
                </div>
                <div class="sampling-overview-value text-emerald-600">
                  {{ formatCurrency(totalFullRepurchaseGsv, 'wan') }}
                </div>
                <div class="sampling-overview-subrow">
                  <span>AUS ¥{{ totalFullRepurchaseAus.toFixed(0) }}</span>
                  <span
                    v-if="totalCompareValue('full_repurchase_aus', 'pct') != null"
                    class="sampling-delta-badge sampling-delta-badge--mini"
                    :class="deltaToneClass(totalCompareValue('full_repurchase_aus', 'pct'))"
                  >
                    {{ (totalCompareValue('full_repurchase_aus', 'pct') ?? 0) > 0 ? '↑' : (totalCompareValue('full_repurchase_aus', 'pct') ?? 0) < 0 ? '↓' : '' }}
                    <YOYGuard :value="totalCompareValue('full_repurchase_aus', 'pct')" unit="%" />
                  </span>
                </div>
              </div>
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

          <!-- 02 板块 — Sprint 169: 只保留 3 年对比柱状图，5 卡片移除 -->
          <section
            :aria-labelledby="'sampling-section-buckets'"
            class="sampling-section"
          >
            <h2 id="sampling-section-buckets" class="section-title"><span class="section-num">02</span>回购周期分布</h2>
            <div class="bi-card p-4 mb-4">
              <div class="flex items-center justify-between mb-0.5">
                <div>
                  <h3 class="text-sm font-semibold text-slate-800">回购周期分布率 — 3 年对比</h3>
                  <p class="text-[11px] text-slate-500">
                    只跟顶部当前日期联动: {{ filterStore.dateRange[0] }} ~ {{ filterStore.dateRange[1] }} vs 25/24 同期 (固定 90 天回购窗口, 4 桶分布率 = 派样回购正装人数 / 派样人数)
                  </p>
                </div>
                <!-- Sprint 177: 02 板块统一 ExportToolbar (P0-1+P0-2+P1-5), 跟 04 派样明细 + Lock + Rolling 3 view 一致 -->
                <ExportToolbar
                  filename="回购周期分布_3年对比"
                  sheet-name="回购周期分布"
                  :columns="trackingColumnsXlsx"
                  :data="trackingDataXlsx"
                  :chart-ref="trackingChartRef"
                />
              </div>
              <ErrorState v-if="trackingError" :message="(trackingError as Error).message" @retry="refetchTracking()" />
              <LoadingState v-else-if="trackingLoading && !trackingData" />
              <EChartsWrapper
                v-else
                ref="trackingChartRef"
                :option="trackingChartOption"
                height="260px"
              />
            </div>
          </section>

          <!-- 渠道对比卡片 — 5 个核心指标两行展示，YOY/MOM badge 下沉避免遮挡 -->
          <section :aria-labelledby="'sampling-section-channels'" class="sampling-section">
          <h2 id="sampling-section-channels" class="section-title"><span class="section-num">03</span>各板块情况</h2>
          <n-grid :cols="3" :x-gap="16" :y-gap="16" responsive="screen" item-responsive>
            <!-- 3 卡横排 (TTL + U先 + 百补) 等宽对齐，TTL 始终展开 -->
            <n-gi v-for="ch in allChannels" :key="ch.channel" span="1 m:1 l:1">
              <n-card :bordered="false" segmented class="h-full sampling-channel-card">
                <template #header>
                  <div class="flex items-center justify-between w-full">
                    <div class="flex items-baseline gap-2">
                      <span class="text-base font-bold" :class="channelColorClass(ch.channel)" :aria-label="ch.channel">
                        <span aria-hidden="true" class="mr-1">{{ channelIcon(ch.channel) }}</span>
                        {{ ch.channel }}
                      </span>
                      <span v-if="ch.channel === 'TTL派样'" class="text-xs font-normal text-slate-400">U先 ∪ 百补</span>
                    </div>
                  </div>
                </template>

                <div class="sampling-channel-metrics">
                  <div class="sampling-channel-metric">
                    <div class="sampling-channel-label">派样人数</div>
                    <div class="sampling-channel-value text-slate-800">{{ formatNumber(ch.sample_users) }}</div>
                    <div class="sampling-channel-delta sampling-channel-delta--empty">暂无{{ compareModeLabel }}</div>
                  </div>
                  <div class="sampling-channel-metric">
                    <div class="sampling-channel-label">回购人数</div>
                    <div class="sampling-channel-value text-slate-800">{{ formatNumber(ch.repurchase_users) }}</div>
                    <div class="sampling-channel-delta">
                      <span class="sampling-delta-label">{{ compareModeLabel }}</span>
                      <span
                        v-if="compareValue(ch, 'repurchase_users', 'pct') != null"
                        class="sampling-delta-badge sampling-delta-badge--mini"
                        :class="deltaToneClass(compareValue(ch, 'repurchase_users', 'pct'))"
                      >
                        {{ (compareValue(ch, 'repurchase_users', 'pct') ?? 0) > 0 ? '↑' : (compareValue(ch, 'repurchase_users', 'pct') ?? 0) < 0 ? '↓' : '' }}
                        <YOYGuard :value="compareValue(ch, 'repurchase_users', 'pct')" unit="%" />
                      </span>
                    </div>
                  </div>
                  <div class="sampling-channel-metric">
                    <div class="sampling-channel-label">回购率</div>
                    <div class="sampling-channel-value text-indigo-600">{{ formatPercent(ch.repurchase_rate) }}</div>
                    <div class="sampling-channel-delta">
                      <span class="sampling-delta-label">{{ compareModeLabel }}</span>
                      <span
                        v-if="compareValue(ch, 'repurchase_rate', 'pp') != null"
                        class="sampling-delta-badge sampling-delta-badge--mini"
                        :class="deltaToneClass(compareValue(ch, 'repurchase_rate', 'pp'))"
                      >
                        {{ (compareValue(ch, 'repurchase_rate', 'pp') ?? 0) > 0 ? '↑' : (compareValue(ch, 'repurchase_rate', 'pp') ?? 0) < 0 ? '↓' : '' }}
                        <YOYGuard :value="compareValue(ch, 'repurchase_rate', 'pp')" unit="pp" />
                      </span>
                    </div>
                  </div>
                  <div class="sampling-channel-metric">
                    <div class="sampling-channel-label">贡献GSV</div>
                    <div class="sampling-channel-value text-emerald-600">{{ formatCurrency(ch.repurchase_gsv, 'wan') }}</div>
                    <div class="sampling-channel-delta">
                      <span class="sampling-delta-label">{{ compareModeLabel }}</span>
                      <span
                        v-if="compareValue(ch, 'repurchase_gsv', 'pct') != null"
                        class="sampling-delta-badge sampling-delta-badge--mini"
                        :class="deltaToneClass(compareValue(ch, 'repurchase_gsv', 'pct'))"
                      >
                        {{ (compareValue(ch, 'repurchase_gsv', 'pct') ?? 0) > 0 ? '↑' : (compareValue(ch, 'repurchase_gsv', 'pct') ?? 0) < 0 ? '↓' : '' }}
                        <YOYGuard :value="compareValue(ch, 'repurchase_gsv', 'pct')" unit="%" />
                      </span>
                    </div>
                  </div>
                  <div class="sampling-channel-metric">
                    <div class="sampling-channel-label">AUS</div>
                    <div class="sampling-channel-value sampling-channel-value--small text-slate-600">{{ formatCurrency(ch.repurchase_aus, 'yuan', 0) }}</div>
                    <div class="sampling-channel-delta">
                      <span class="sampling-delta-label">{{ compareModeLabel }}</span>
                      <span
                        v-if="compareValue(ch, 'repurchase_aus', 'pct') != null"
                        class="sampling-delta-badge sampling-delta-badge--mini"
                        :class="deltaToneClass(compareValue(ch, 'repurchase_aus', 'pct'))"
                      >
                        {{ (compareValue(ch, 'repurchase_aus', 'pct') ?? 0) > 0 ? '↑' : (compareValue(ch, 'repurchase_aus', 'pct') ?? 0) < 0 ? '↓' : '' }}
                        <YOYGuard :value="compareValue(ch, 'repurchase_aus', 'pct')" unit="%" />
                      </span>
                    </div>
                  </div>
                </div>

                <n-divider />
                <div class="sampling-channel-detail-grid">
                  <div class="sampling-channel-detail">
                    <div class="sampling-channel-detail-title text-rose-600">{{ windowDays }}天正装回购</div>
                    <div class="sampling-channel-detail-line">
                      <span>人数: <b>{{ formatNumber(ch.full_repurchase_users) }}</b></span>
                      <span
                        v-if="compareValue(ch, 'full_repurchase_users', 'pct') != null"
                        class="sampling-delta-badge sampling-delta-badge--mini"
                        :class="deltaToneClass(compareValue(ch, 'full_repurchase_users', 'pct'))"
                      >
                        {{ (compareValue(ch, 'full_repurchase_users', 'pct') ?? 0) > 0 ? '↑' : (compareValue(ch, 'full_repurchase_users', 'pct') ?? 0) < 0 ? '↓' : '' }}
                        <YOYGuard :value="compareValue(ch, 'full_repurchase_users', 'pct')" unit="%" />
                      </span>
                    </div>
                    <div class="sampling-channel-detail-line">
                      <span>转化率: <b>{{ formatPercent(ch.full_repurchase_rate) }}</b></span>
                      <span
                        v-if="compareValue(ch, 'full_repurchase_rate', 'pp') != null"
                        class="sampling-delta-badge sampling-delta-badge--mini"
                        :class="deltaToneClass(compareValue(ch, 'full_repurchase_rate', 'pp'))"
                      >
                        {{ (compareValue(ch, 'full_repurchase_rate', 'pp') ?? 0) > 0 ? '↑' : (compareValue(ch, 'full_repurchase_rate', 'pp') ?? 0) < 0 ? '↓' : '' }}
                        <YOYGuard :value="compareValue(ch, 'full_repurchase_rate', 'pp')" unit="pp" />
                      </span>
                    </div>
                    <div class="sampling-channel-detail-line">
                      <span>GSV: <b class="text-emerald-700">{{ formatCurrency(ch.full_repurchase_gsv, 'wan') }}</b></span>
                      <span
                        v-if="compareValue(ch, 'full_repurchase_gsv', 'pct') != null"
                        class="sampling-delta-badge sampling-delta-badge--mini"
                        :class="deltaToneClass(compareValue(ch, 'full_repurchase_gsv', 'pct'))"
                      >
                        {{ (compareValue(ch, 'full_repurchase_gsv', 'pct') ?? 0) > 0 ? '↑' : (compareValue(ch, 'full_repurchase_gsv', 'pct') ?? 0) < 0 ? '↓' : '' }}
                        <YOYGuard :value="compareValue(ch, 'full_repurchase_gsv', 'pct')" unit="%" />
                      </span>
                    </div>
                    <div class="sampling-channel-detail-line">
                      <span>AUS <b>{{ formatCurrency(ch.full_repurchase_aus, 'yuan', 0) }}</b></span>
                      <span
                        v-if="compareValue(ch, 'full_repurchase_aus', 'pct') != null"
                        class="sampling-delta-badge sampling-delta-badge--mini"
                        :class="deltaToneClass(compareValue(ch, 'full_repurchase_aus', 'pct'))"
                      >
                        {{ (compareValue(ch, 'full_repurchase_aus', 'pct') ?? 0) > 0 ? '↑' : (compareValue(ch, 'full_repurchase_aus', 'pct') ?? 0) < 0 ? '↓' : '' }}
                        <YOYGuard :value="compareValue(ch, 'full_repurchase_aus', 'pct')" unit="%" />
                      </span>
                    </div>
                  </div>
                  <div class="sampling-channel-detail">
                    <div class="sampling-channel-detail-title text-slate-500">非正装回购</div>
                    <div class="sampling-channel-detail-line">
                      <span>人数: <b>{{ formatNumber(ch.nonfull_repurchase_users) }}</b></span>
                    </div>
                    <div class="sampling-channel-detail-line">
                      <span>GSV: <b class="text-slate-700">{{ formatCurrency(ch.nonfull_repurchase_gsv, 'wan') }}</b></span>
                      <span
                        v-if="compareValue(ch, 'nonfull_repurchase_gsv', 'pct') != null"
                        class="sampling-delta-badge sampling-delta-badge--mini"
                        :class="deltaToneClass(compareValue(ch, 'nonfull_repurchase_gsv', 'pct'))"
                      >
                        {{ (compareValue(ch, 'nonfull_repurchase_gsv', 'pct') ?? 0) > 0 ? '↑' : (compareValue(ch, 'nonfull_repurchase_gsv', 'pct') ?? 0) < 0 ? '↓' : '' }}
                        <YOYGuard :value="compareValue(ch, 'nonfull_repurchase_gsv', 'pct')" unit="%" />
                      </span>
                    </div>
                    <div class="sampling-channel-detail-line">
                      <span>AUS <b>{{ formatCurrency(ch.nonfull_repurchase_aus, 'yuan', 0) }}</b></span>
                    </div>
                  </div>
                </div>
              </n-card>
            </n-gi>
          </n-grid>
          </section>

          <!-- 品类明细表格 — Sprint 155 ③ native table + 渠道列手动 rowspan 合并 + 其他列点击 sort -->
          <section :aria-labelledby="'sampling-section-detail'" class="sampling-section">
          <h2 id="sampling-section-detail" class="section-title"><span class="section-num">04</span>派样明细</h2>
          <n-card :bordered="false" segmented>
            <template #header>
              <div class="flex items-center gap-3">
                <span class="card-title">按 {{ levelLabel }} 明细</span>
                <ExportToolbar
                  :filename="`派样明细_${levelLabel}`"
                  :columns="categoryColumnsXlsx"
                  :data="sortedCategoryRows as any[]"
                  sheet-name="派样明细"
                />
              </div>
            </template>
            <div class="overflow-x-auto">
              <table class="w-full text-sm border-collapse">
                <thead>
                  <tr class="bg-slate-50 border-b border-slate-200">
                    <th class="px-3 py-2 text-left font-semibold text-slate-700 w-[100px]">渠道</th>
                    <th
                      v-for="col in categoryColumns"
                      :key="col.key"
                      class="px-3 py-2 font-semibold text-slate-700 cursor-pointer hover:bg-slate-100 select-none"
                      :class="col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left'"
                      @click="toggleSort(col.key)"
                    >
                      {{ col.title }}
                      <span v-if="detailSortKey === col.key" class="text-indigo-500 ml-1">
                        {{ detailSortOrder === 'asc' ? '↑' : '↓' }}
                      </span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(row, rowIdx) in sortedCategoryRows"
                    :key="`${row.channel}-${row.category}-${rowIdx}`"
                    class="border-b border-slate-100 hover:bg-slate-50"
                  >
                    <td
                      v-if="channelRowspans.get(rowIdx) != null"
                      :rowspan="channelRowspans.get(rowIdx)"
                      class="px-3 py-2 font-semibold text-slate-700 align-middle text-center border-r border-slate-200"
                    >
                      <div class="flex items-center justify-center min-h-[2rem]">{{ row.channel }}</div>
                    </td>
                    <td
                      v-for="col in categoryColumns"
                      :key="col.key"
                      class="px-3 py-2 tabular-nums"
                      :class="col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left'"
                    >
                      {{ col.format(row) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </n-card>
          </section>
        </template>
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<style scoped>
/* Sprint 154 ① 全局 8pt 网格 + 呼吸感 + 标题层级 + 行宽
   Sprint 156: 删 max-width: 1200px — 让 .sampling-view 继承 DefaultLayout 全局 max-w-[1600px] 容器,
   跟 CategoryView / AudienceView 等其他 view 拉齐宽度 */
.sampling-view {
  padding: 0 24px;  /* 8 的倍数 (3 × 8) */
}

/* 文本行宽控制 — 75ch 是黄金阅读宽度 */
.sampling-view :deep(.prose-narrow) {
  max-width: 75ch;
}

/* 卡片内边距统一 24px (8 × 3) */
.sampling-view :deep(.n-card) {
  padding: 8px 0;  /* 卡片自身内 padding 由 n-card 默认控制, 加上 :deep section 调整 */
}

/* 标题层级 — H1 (PageHeader) → H2 (section) → H3 (card) → H4 (sub) */
.sampling-view :deep(h2.section-title) {
  font-size: 1.125rem;  /* 18px */
  font-weight: 600;
  color: rgb(30 41 59);  /* slate-800 */
  margin-bottom: 16px;  /* 8 × 2 */
  line-height: 1.5;
  letter-spacing: -0.01em;
}

.sampling-view :deep(h2.section-title .section-num) {
  color: rgb(148 163 184);  /* slate-400 */
  font-weight: 400;
  margin-right: 12px;  /* 8 + 4 */
  font-variant-numeric: tabular-nums;
}

.sampling-view :deep(h3.card-title) {
  font-size: 0.875rem;  /* 14px */
  font-weight: 600;
  color: rgb(51 65 85);  /* slate-700 */
  line-height: 1.5;
}

.sampling-view :deep(h4.sub-title) {
  font-size: 0.8125rem;  /* 13px */
  font-weight: 500;
  color: rgb(71 85 105);  /* slate-600 */
  line-height: 1.4;
}

/* Section 间隔 — 8 的倍数 */
.sampling-view :deep(.sampling-section) {
  margin-bottom: 32px;  /* 8 × 4 */
}

.sampling-view :deep(.sampling-section + .sampling-section) {
  margin-top: 0;
}

.sampling-overview-card {
  height: 100%;
  padding: 16px;
  border: 1px solid rgb(226 232 240);
  border-radius: 6px;
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
}

.sampling-overview-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  min-height: 24px;
}

.sampling-overview-label {
  color: rgb(100 116 139);
  font-size: 0.875rem;
  font-weight: 500;
}

.sampling-overview-value {
  margin-top: 8px;
  font-size: 1.875rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.15;
}

.sampling-overview-subrow {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  color: rgb(148 163 184);
  font-size: 0.75rem;
}

.sampling-delta-badge {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  line-height: 1.25;
  white-space: nowrap;
}

.sampling-delta-badge--mini {
  padding: 1px 5px;
  font-size: 10px;
}

.sampling-delta-badge--up {
  background-color: rgba(21, 190, 83, 0.08);
  color: #108c3d;
}

.sampling-delta-badge--down {
  background-color: rgba(234, 34, 97, 0.08);
  color: #c41d4e;
}

.sampling-delta-badge--flat {
  background-color: rgb(241 245 249);
  color: rgb(100 116 139);
}

.sampling-delta-badge--empty {
  background-color: rgb(248 250 252);
  color: rgb(148 163 184);
}

.sampling-delta-empty,
.sampling-channel-delta--empty {
  color: rgb(148 163 184);
  font-size: 10px;
  font-weight: 500;
  white-space: nowrap;
}

.sampling-delta-label {
  color: rgb(148 163 184);
  font-size: 10px;
  font-weight: 500;
}

.sampling-channel-card :deep(.n-card-header) {
  padding-bottom: 12px;
}

.sampling-channel-metrics {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.sampling-channel-metric {
  min-width: 0;
}

.sampling-channel-label {
  color: rgb(148 163 184);
  font-size: 0.75rem;
  font-weight: 600;
  line-height: 1.25;
  white-space: nowrap;
}

.sampling-channel-value {
  min-height: 28px;
  margin-top: 6px;
  overflow: hidden;
  font-size: 1.25rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.15;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sampling-channel-value--small {
  font-size: 1.0625rem;
}

.sampling-channel-delta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  min-height: 18px;
  margin-top: 5px;
}

.sampling-channel-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.sampling-channel-detail {
  min-width: 0;
}

.sampling-channel-detail-title {
  margin-bottom: 6px;
  font-size: 0.75rem;
  font-weight: 700;
}

.sampling-channel-detail-line {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  min-height: 21px;
  color: rgb(71 85 105);
  font-size: 0.75rem;
  line-height: 1.35;
}

.sampling-channel-detail-line b {
  color: rgb(30 41 59);
  font-weight: 700;
}

@media (max-width: 1280px) {
  .sampling-channel-metrics {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .sampling-channel-metrics,
  .sampling-channel-detail-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
