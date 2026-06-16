<script setup lang="ts">
import { computed, toValue, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NAlert, NGrid, NGi, NEmpty, NButton } from 'naive-ui'
import type { EChartsOption } from 'echarts'
import { useFilterStore } from '@/stores/filterStore'
import { fetchHealthOverview, fetchChannelHealthScores, fetchHealthTargets } from '@/api/health'
import MetricCard from '@/components/MetricCard.vue'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import YOYGuard from '@/components/YOYGuard.vue'
import ExportToolbar from '@/components/ExportToolbar.vue'
import RatioConventionBanner from '@/components/RatioConventionBanner.vue'
import type { XlsxColumn } from '@/utils/exportXlsx'

const emit = defineEmits<{
  (e: 'navigate-tab', tabName: string): void
}>()

const filterStore = useFilterStore()
const radarChartRef = ref<InstanceType<typeof EChartsWrapper> | null>(null)

import { LOW_PRICE_CHANNELS, HEALTH_SCORE_CHANNELS } from '@/constants/channels'

// ── 渠道评分表格排序（仅显示全店/货架/达播/直播/淘客）──
const HEALTH_SCORE_CHANNEL_ORDER = HEALTH_SCORE_CHANNELS

// ── 渠道过滤：单渠道优先，排除低价渠道 ──
const queryParams = computed(() => {
  const channel = filterStore.channel !== '全店' ? filterStore.channel : undefined
  const excludeChannels = filterStore.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined
  // 动态计算 period_days：从日期范围计算实际天数
  const startMs = new Date(filterStore.dateRange[0] + 'T00:00:00').getTime()
  const endMs = new Date(filterStore.dateRange[1] + 'T00:00:00').getTime()
  const periodDays = Math.max(1, Math.round((endMs - startMs) / (1000 * 60 * 60 * 24)) + 1)
  const cmp = filterStore.compareParams
  return {
    analysis_date: filterStore.dateRange[1],
    period_days: periodDays,
    channel,
    exclude_channels: excludeChannels,
    compare_start_date: cmp?.[0],
    compare_end_date: cmp?.[1],
  }
})

const { data, isLoading, error, refetch } = useQuery({
  queryKey: computed(() => ['health-overview', { ...toValue(queryParams) }]),
  queryFn: () => {
    const p = toValue(queryParams)
    return fetchHealthOverview({
      analysis_date: p.analysis_date,
      period_days: p.period_days,
      channel: p.channel,
      exclude_channels: p.exclude_channels,
      compare_start_date: p.compare_start_date,
      compare_end_date: p.compare_end_date,
    })
  },
  staleTime: 60_000,
})

// ── 健康评分目标（自动沿用去年同周期实际值）──
const { data: targetsData } = useQuery({
  queryKey: computed(() => ['health-targets', { ...toValue(queryParams) }]),
  queryFn: () => {
    const p = toValue(queryParams)
    return fetchHealthTargets({
      analysis_date: p.analysis_date,
      period_days: p.period_days,
      channel: p.channel,
      exclude_channels: p.exclude_channels,
    })
  },
  staleTime: 60_000,
})

// ── 渠道评分对比（仅在全店视图下查询）──
const channelScoresParams = computed(() => {
  const p = toValue(queryParams)
  return {
    analysis_date: p.analysis_date,
    period_days: p.period_days,
    exclude_channels: p.exclude_channels,
  }
})

const isAllStore = computed(() => filterStore.channel === '全店')

// ── 渠道评分表格：过滤 + 排序 ──
const filteredChannelScores = computed(() => {
  const scores = channelScoresData.value?.scores ?? []
  return scores
    .filter(s => HEALTH_SCORE_CHANNEL_ORDER.includes(s.channel))
    .sort((a, b) => HEALTH_SCORE_CHANNEL_ORDER.indexOf(a.channel) - HEALTH_SCORE_CHANNEL_ORDER.indexOf(b.channel))
})

const { data: channelScoresData } = useQuery({
  queryKey: computed(() => ['channel-health-scores', { ...toValue(channelScoresParams) }]),
  queryFn: () => {
    const p = toValue(channelScoresParams)
    return fetchChannelHealthScores({
      analysis_date: p.analysis_date,
      period_days: p.period_days,
      exclude_channels: p.exclude_channels,
    })
  },
  staleTime: 60_000,
  enabled: isAllStore, // 仅全店视图下查询
})

// ── 健康评分颜色 ──
const healthColor = computed(() => {
  const level = data.value?.health_level
  if (level === 'healthy') return '#52c41a'
  if (level === 'warning') return '#faad14'
  return '#f5222d'
})

const healthLabel = computed(() => {
  const level = data.value?.health_level
  if (level === 'healthy') return '健康'
  if (level === 'warning') return '关注'
  return '预警'
})

// ── 格式化 ──
function fmtCurrency(v?: number | null): string {
  if (v == null) return '—'
  if (v >= 10_000) return `¥${(v / 10_000).toFixed(1)}万`
  if (v >= 1_000) return `¥${(v / 1_000).toFixed(0)}千`
  return `¥${v.toFixed(0)}`
}

function fmtPercent(v?: number | null): string {
  if (v == null) return '—'
  return `${(v * 100).toFixed(1)}%`
}

function fmtCount(v?: number | null): string {
  if (v == null) return '—'
  return v.toLocaleString()
}

// ── 五维雷达图配置 ──
const radarOption = computed((): EChartsOption => {
  if (!data.value) return {}
  const d = data.value
  // 目标值：优先使用去年同周期实际值（动态），无则降级为硬编码默认值
  const t = targetsData.value
  const targets = {
    repurchase: t?.all_store_repurchase_rate ?? 0.21,
    product: t?.same_product_repurchase_rate ?? 0.10,
    ratio: t?.old_customer_gsv_ratio ?? 0.38,
    aus: t?.old_customer_aus ?? 100,
    recent7d: t?.recent_7d_repurchase_users ?? 300,
  }

  const softCap = (v: number, t: number) => {
    const ratio = v / t
    if (ratio <= 1.0) return ratio
    const maxBonus = 0.2
    return 1.0 + maxBonus * Math.log(1.0 + ratio - 1.0) / Math.log(4.0)
  }

  // 周均复购人数（用于雷达图展示，目标恒定为300/周）
  const weeklyRepurchase = d.period_days > 0
    ? Math.round(d.period_repurchase_users / d.period_days * 7)
    : 0

  // 去年同期周均复购人数
  const lyWeeklyRepurchase = (d.ly_period_repurchase_users != null && d.period_days > 0)
    ? Math.round(d.ly_period_repurchase_users / d.period_days * 7)
    : 0

  // 是否有去年同期数据
  const hasLy = d.ly_all_store_repurchase_rate != null

  const rawValues = [
    { label: '全店复购率', value: `${(d.all_store_repurchase_rate * 100).toFixed(1)}%`, target: `${(targets.repurchase * 100).toFixed(0)}%` },
    { label: '本品复购率', value: `${(d.same_product_repurchase_rate * 100).toFixed(1)}%`, target: `${(targets.product * 100).toFixed(0)}%` },
    { label: '老客占比', value: `${(d.old_customer_gsv_ratio * 100).toFixed(1)}%`, target: `${(targets.ratio * 100).toFixed(0)}%` },
    { label: '老客AUS', value: `¥${d.old_customer_aus.toFixed(0)}`, target: `¥${targets.aus}` },
    { label: '周均复购', value: `${weeklyRepurchase}人/周`, target: `${targets.recent7d}人/周` },
  ]

  interface RadarSeriesItem {
    value: number[]
    name: string
    lineStyle?: { color: string; width: number; type?: 'solid' | 'dashed' | 'dotted' }
    areaStyle?: { color: string }
    itemStyle?: { color: string }
    symbol?: string
    symbolSize?: number
  }
  const seriesData: RadarSeriesItem[] = [{
    value: [
      softCap(d.all_store_repurchase_rate, targets.repurchase),
      softCap(d.same_product_repurchase_rate, targets.product),
      softCap(d.old_customer_gsv_ratio, targets.ratio),
      softCap(d.old_customer_aus, targets.aus),
      softCap(weeklyRepurchase, targets.recent7d),
    ],
    name: '当期',
    lineStyle: { color: '#6366f1', width: 2 },
    areaStyle: { color: 'rgba(99,102,241,0.25)' },
    itemStyle: { color: '#6366f1' },
    symbol: 'circle',
    symbolSize: 6,
  }]

  if (hasLy && d.ly_all_store_repurchase_rate != null) {
    seriesData.push({
      value: [
        softCap(d.ly_all_store_repurchase_rate, targets.repurchase),
        softCap(d.ly_same_product_repurchase_rate ?? 0, targets.product),
        softCap(d.ly_old_customer_gsv_ratio ?? 0, targets.ratio),
        softCap(d.ly_old_customer_aus ?? 0, targets.aus),
        softCap(lyWeeklyRepurchase, targets.recent7d),
      ],
      name: '去年同期',
      lineStyle: { color: '#fb923c', width: 2, type: 'dashed' },
      areaStyle: { color: 'rgba(251,146,60,0.12)' },
      itemStyle: { color: '#fb923c' },
      symbol: 'diamond',
      symbolSize: 6,
    })
  }

  return {
    backgroundColor: '#f8fafc',
    legend: {
      bottom: 0,
      data: hasLy ? ['当期', '去年同期'] : ['当期'],
      textStyle: { fontSize: 11, color: '#64748b' },
      itemWidth: 14,
      itemHeight: 8,
    },
    tooltip: {
      trigger: 'item',
      formatter: () => {
        const rows = rawValues.map(r => `<div style="display:flex;justify-content:space-between;gap:16px"><span>${r.label}</span><span><b>${r.value}</b> <span style="color:#94a3b8">(目标 ${r.target})</span></span></div>`).join('')
        return `<div style="font-size:12px;line-height:1.8">${rows}</div>`
      },
    },
    radar: {
      indicator: [
        {
          name: hasLy
            ? `全店复购率\n{a|${(d.all_store_repurchase_rate * 100).toFixed(1)}%}\n{b|去年同期 ${d.ly_all_store_repurchase_rate != null ? (d.ly_all_store_repurchase_rate * 100).toFixed(1) : '—'}%}`
            : `全店复购率\n{a|${(d.all_store_repurchase_rate * 100).toFixed(1)}%}`,
          max: 1.5
        },
        {
          name: hasLy
            ? `本品复购率\n{a|${(d.same_product_repurchase_rate * 100).toFixed(1)}%}\n{b|去年同期 ${d.ly_same_product_repurchase_rate != null ? (d.ly_same_product_repurchase_rate * 100).toFixed(1) : '—'}%}`
            : `本品复购率\n{a|${(d.same_product_repurchase_rate * 100).toFixed(1)}%}`,
          max: 1.5
        },
        {
          name: hasLy
            ? `老客占比\n{a|${(d.old_customer_gsv_ratio * 100).toFixed(1)}%}\n{b|去年同期 ${d.ly_old_customer_gsv_ratio != null ? (d.ly_old_customer_gsv_ratio * 100).toFixed(1) : '—'}%}`
            : `老客占比\n{a|${(d.old_customer_gsv_ratio * 100).toFixed(1)}%}`,
          max: 1.5
        },
        {
          name: hasLy
            ? `老客AUS\n{a|¥${d.old_customer_aus.toFixed(0)}}\n{b|去年同期 ¥${d.ly_old_customer_aus != null ? d.ly_old_customer_aus.toFixed(0) : '—'}}`
            : `老客AUS\n{a|¥${d.old_customer_aus.toFixed(0)}}`,
          max: 1.5
        },
        {
          name: hasLy
            ? `周均复购\n{a|${weeklyRepurchase}人}\n{b|去年同期 ${lyWeeklyRepurchase}人}`
            : `周均复购\n{a|${weeklyRepurchase}人}`,
          max: 1.5
        },
      ],
      shape: 'polygon',
      splitNumber: 3,
      axisName: {
        color: '#64748b',
        fontSize: 11,
        formatter: ((value: string) => value) as any,
        rich: {
          a: { fontSize: 11, color: '#64748b', lineHeight: 16 },
          b: { fontSize: 11, color: '#94a3b8', lineHeight: 16 },
        },
        overflow: 'break',
        width: 70,
      } as any,
      splitLine: { lineStyle: { color: '#cbd5e1' } },
      splitArea: { areaStyle: { color: ['#f8fafc', '#e2e8f0', '#cbd5e1'] } },
      axisLine: { lineStyle: { color: '#cbd5e1' } },
      radius: '58%',
      center: ['50%', '46%'],
      axisNameGap: 8,
    },
    series: [{
      type: 'radar',
      data: seriesData,
    }],
  }
})

// ── 告警 ──
const alerts = computed(() => data.value?.alerts || [])
const hasAlerts = computed(() => alerts.value.length > 0)
const highAlerts = computed(() => alerts.value.filter(a => a.severity === 'high'))
const mediumAlerts = computed(() => alerts.value.filter(a => a.severity === 'medium'))

const ALERT_TAB_MAP: Record<string, string> = {
  repurchase_rate_drop: 'repurchase',
  old_customer_ratio_low: 'tiers',
  aus_low: 'tiers',
}

function onAlertClick(alertType: string) {
  const tab = ALERT_TAB_MAP[alertType]
  if (tab) emit('navigate-tab', tab)
}

// ── 渠道评分 Excel 导出列 ──
const channelScoreXlsxColumns: XlsxColumn[] = [
  { header: '渠道', key: 'channel', width: 10 },
  { header: '当期评分', key: 'health_score', width: 12, numFmt: '0.0' },
  { header: '去年同期', key: 'ly_health_score', width: 12, numFmt: '0.0' },
  { header: '同比变化', key: 'health_score_yoy', width: 12, numFmt: '0.00' },
  { header: '同比变化 (pp)', key: 'health_score_yoy_label', width: 14 },
]
</script>

<template>
  <div class="health-overview-tab">
    <!-- 加载态 -->
    <LoadingState v-if="isLoading" />

    <!-- 错误态 -->
    <ErrorState v-else-if="error" :message="error.message" @retry="refetch" />

    <!-- 空数据 -->
    <NEmpty v-else-if="!data" description="暂无数据" />

    <!-- 正常展示 -->
    <template v-else>
      <!-- Sprint 13 比率口径 banner (3 天自动消失) -->
      <RatioConventionBanner class="mb-4" />

      <!-- 告警横幅 -->
      <div v-if="hasAlerts" class="alert-section mb-4">
        <NAlert
          v-for="alert in highAlerts"
          :key="alert.alert_type"
          type="error"
          :title="alert.alert_name"
          closable
          class="mb-2 cursor-pointer alert-hover"
          @click="onAlertClick(alert.alert_type)"
        >
          <div class="flex items-center justify-between">
            <span>{{ alert.suggested_action }}</span>
            <NButton
              v-if="ALERT_TAB_MAP[alert.alert_type]"
              text type="error" size="tiny"
              @click.stop="onAlertClick(alert.alert_type)"
            >查看详情 →</NButton>
          </div>
        </NAlert>
        <NAlert
          v-for="alert in mediumAlerts"
          :key="alert.alert_type"
          type="warning"
          :title="alert.alert_name"
          closable
          class="mb-2 cursor-pointer alert-hover"
          @click="onAlertClick(alert.alert_type)"
        >
          <div class="flex items-center justify-between">
            <span>{{ alert.suggested_action }}</span>
            <NButton
              v-if="ALERT_TAB_MAP[alert.alert_type]"
              text type="warning" size="tiny"
              @click.stop="onAlertClick(alert.alert_type)"
            >查看详情 →</NButton>
          </div>
        </NAlert>
      </div>

      <!-- 第一行：老客 -->
      <n-grid :cols="4" :x-gap="12" :y-gap="12" class="mb-3">
        <n-gi>
          <MetricCard
            title="老客GSV"
            :value="fmtCurrency(data.old_gsv)"
            :change="data.yoy_old_gsv"
          />
        </n-gi>
        <n-gi>
          <MetricCard
            title="老客人数"
            :value="fmtCount(data.old_users)"
            :change="data.yoy_old_users"
          />
        </n-gi>
        <n-gi>
          <MetricCard
            title="老客AUS"
            :value="fmtCurrency(data.old_customer_aus)"
            :change="data.yoy_old_customer_aus"
          />
        </n-gi>
        <n-gi>
          <MetricCard
            title="老客GSV占比"
            :value="fmtPercent(data.old_customer_gsv_ratio)"
            :change="data.yoy_old_customer_gsv_ratio_ppt"
            unit="pp"
          />
        </n-gi>
      </n-grid>

      <!-- 第二行：会员老客 -->
      <n-grid :cols="4" :x-gap="12" :y-gap="12" class="mb-3">
        <n-gi>
          <MetricCard
            title="会员老客GSV"
            :value="fmtCurrency(data.member_old_gsv)"
            :change="data.yoy_member_old_gsv"
          />
        </n-gi>
        <n-gi>
          <MetricCard
            title="会员老客人数"
            :value="fmtCount(data.member_old_users)"
            :change="data.yoy_member_old_users"
          />
        </n-gi>
        <n-gi>
          <MetricCard
            title="会员老客AUS"
            :value="fmtCurrency(data.member_old_customer_aus)"
            :change="data.yoy_member_old_customer_aus"
          />
        </n-gi>
        <n-gi>
          <MetricCard
            title="会员老客GSV占比"
            :value="fmtPercent(data.member_old_customer_gsv_ratio)"
            :change="data.yoy_member_old_customer_gsv_ratio_ppt"
            unit="pp"
          />
        </n-gi>
      </n-grid>

      <!-- 第三行：健康评分（五维图）+ 近7日复购 -->
      <n-grid :cols="4" :x-gap="12" :y-gap="12" class="mb-4">
        <!-- 健康评分大卡（占2列） -->
        <n-gi :span="2">
          <div class="bi-card p-4 h-full flex flex-col">
            <div class="flex items-center justify-between mb-2">
              <div>
                <p class="text-xs font-medium text-slate-500">健康评分</p>
                <ExportToolbar
                  :filename="`老客分析_五维雷达_${filterStore.dateRange[1]}`"
                  :chart-ref="radarChartRef"
                />
                <div class="flex items-baseline gap-2 mt-0.5">
                  <span class="text-3xl font-bold" :style="{ color: healthColor }">
                    {{ data.health_score }}
                  </span>
                  <span
                    class="px-2 py-0.5 rounded-full text-[11px] font-semibold text-white"
                    :style="{ backgroundColor: healthColor }"
                  >
                    {{ healthLabel }}
                  </span>
                </div>
                <!-- 去年同期 + YOY -->
                <div v-if="data.health_score_yoy != null" class="flex items-center gap-2 mt-1">
                  <span class="text-[11px] text-slate-400">
                    去年同期 {{ data.ly_health_score ?? '—' }}分
                  </span>
                  <YOYGuard :value="data.health_score_yoy" unit="pp" styled />
                </div>
              </div>
            </div>
            <!-- 五维雷达图 -->
            <div style="height: 380px">
              <EChartsWrapper ref="radarChartRef" :option="radarOption" height="380px" />
            </div>
          </div>
        </n-gi>

        <!-- 周期复购人数（占2列） -->
        <n-gi :span="2">
          <div class="bi-card p-4 h-full flex flex-col justify-center">
            <p class="text-xs font-medium text-slate-500">周期复购人数</p>
            <p class="text-3xl font-bold text-slate-900 mt-1 tabular-nums">
              {{ data.period_repurchase_users.toLocaleString() }}
            </p>
            <!-- 环比（先） -->
            <p v-if="data.mom_period_repurchase_users != null" class="text-xs mt-1">
              <span :class="data.mom_period_repurchase_users >= 0 ? 'text-emerald-600' : 'text-rose-600'">
                {{ data.mom_period_repurchase_users >= 0 ? '↑' : '↓' }}
                {{ data.mom_period_repurchase_users.toFixed(2) }}%
              </span>
              <span class="text-slate-400 ml-1">环比</span>
            </p>
            <!-- 同比（后） -->
            <p v-if="data.yoy_period_repurchase_users != null" class="text-xs mt-0.5">
              <span :class="data.yoy_period_repurchase_users >= 0 ? 'text-emerald-600' : 'text-rose-600'">
                {{ data.yoy_period_repurchase_users >= 0 ? '↑' : '↓' }}
                {{ data.yoy_period_repurchase_users.toFixed(2) }}%
              </span>
              <span class="text-slate-400 ml-1">同比</span>
            </p>
            <p class="text-[11px] text-slate-400 mt-2">
              分析周期：{{ data.period_days }}天
            </p>
          </div>
        </n-gi>
      </n-grid>

      <!-- 渠道健康评分对比（仅全店视图） -->
      <div v-if="isAllStore && filteredChannelScores.length" class="bi-card p-4 mt-4">
        <div class="flex items-center justify-between mb-3">
          <p class="text-sm font-semibold text-slate-700">各渠道健康评分对比</p>
          <ExportToolbar
            :filename="`老客分析_渠道评分_${filterStore.dateRange[1]}`"
            :columns="channelScoreXlsxColumns"
            :data="filteredChannelScores"
            sheet-name="渠道评分"
          />
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-slate-200">
                <th class="text-left py-2 px-3 text-xs font-medium text-slate-500">渠道</th>
                <th class="text-right py-2 px-3 text-xs font-medium text-slate-500">当期评分</th>
                <th class="text-right py-2 px-3 text-xs font-medium text-slate-500">去年同期</th>
                <th class="text-right py-2 px-3 text-xs font-medium text-slate-500">同比变化</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in filteredChannelScores"
                :key="item.channel"
                class="border-b border-slate-100 hover:bg-slate-50 transition-colors"
              >
                <td class="py-2.5 px-3 font-medium text-slate-700">{{ item.channel }}</td>
                <td class="py-2.5 px-3 text-right tabular-nums font-semibold" :style="{ color: item.health_level === 'healthy' ? '#52c41a' : item.health_level === 'warning' ? '#faad14' : '#f5222d' }">
                  {{ item.health_score.toFixed(1) }}
                </td>
                <td class="py-2.5 px-3 text-right tabular-nums text-slate-500">
                  {{ item.ly_health_score != null ? item.ly_health_score.toFixed(1) : '—' }}
                </td>
                <td class="py-2.5 px-3 text-right tabular-nums">
                  <YOYGuard v-if="item.health_score_yoy != null" :value="item.health_score_yoy" unit="pp" styled />
                  <span v-else class="text-slate-400">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 指标说明 -->
      <div class="text-xs text-slate-400 mt-2">
        <p>分析周期: {{ data.period_days }}天 | 分析日期: {{ data.analysis_date }}</p>
        <p class="mt-0.5">有效订单：剔除购物金及退款订单 | 复购：周期内2次及以上有效订单 | 老客：周期开始前已有购买记录</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.health-overview-tab {
  padding-top: 8px;
}
</style>
