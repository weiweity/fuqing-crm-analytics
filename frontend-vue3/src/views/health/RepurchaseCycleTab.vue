<script setup lang="ts">
import { computed, toValue, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NGrid, NGi } from 'naive-ui'
import { useFilterStore } from '@/stores/filterStore'
import { fetchRepurchaseCycle, fetchCohortRetention } from '@/api/health'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import ExportToolbar from '@/components/ExportToolbar.vue'
import YOYBadge from '@/components/YOYBadge.vue'
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

interface HeatmapParam extends EChartLabelParam {
  data: [number, number, number]
}

const filterStore = useFilterStore()
import { LOW_PRICE_CHANNELS } from '@/constants/channels'
const bucketChartRef = ref<InstanceType<typeof EChartsWrapper> | null>(null)
const cohortChartRef = ref<InstanceType<typeof EChartsWrapper> | null>(null)

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

// L4.75.2: 默认不自动 fetch, 用户手动点击按钮触发
const repurchaseAutoFetch = ref(false)
function onRepurchaseQueryClick() {
  repurchaseAutoFetch.value = true
  refetch()
}

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
  enabled: repurchaseAutoFetch,
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

// ── Excel 导出列定义 ──
const bucketXlsxColumns: XlsxColumn[] = [
  { header: '复购间隔', key: 'bucket_label', width: 14 },
  { header: '人数', key: 'user_count', width: 10, numFmt: '#,##0' },
  { header: '占比', key: 'user_ratio', width: 10, numFmt: '0.0%' },
]

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
    <div v-else-if="!repurchaseAutoFetch" class="manual-query-guide">
      <NButton type="primary" size="large" @click="onRepurchaseQueryClick">🔍 点击查询复购周期数据</NButton>
      <p class="hint">说明: 本次结果计算量较大, 请点击按钮手动触发查询。</p>
    </div>

    <template v-else-if="data">
      <!-- 顶部统计 (Sprint 169: 5 列 grid, 加复购率卡 + 5 卡片 YOY) -->
      <NGrid :cols="5" :x-gap="12" responsive="screen" class="mb-4">
        <NGi>
          <div class="bi-card bi-card-hover px-3 py-3 text-center">
            <p class="text-xs text-slate-500">中位复购天数</p>
            <p class="text-2xl font-bold text-slate-900">{{ data.all_store_median_days }}天</p>
            <p class="text-[10px] text-slate-400 mt-1">50%的复购间隔 ≤ 该天数</p>
            <!-- Sprint 169: 天数 YOY (raw diff, 业务直觉"间隔缩/拉长") -->
            <p
              v-if="data.median_days_yoy != null"
              class="text-[10px] mt-0.5 font-medium"
              :class="data.median_days_yoy < 0 ? 'text-emerald-600' : data.median_days_yoy > 0 ? 'text-rose-600' : 'text-slate-400'"
            >
              vs {{ data.ly_all_store_median_days ?? '?' }}天 ({{ data.median_days_yoy > 0 ? '+' : '' }}{{ data.median_days_yoy }}天)
            </p>
          </div>
        </NGi>
        <NGi>
          <div class="bi-card bi-card-hover px-3 py-3 text-center">
            <p class="text-xs text-slate-500">P25复购天数</p>
            <p class="text-2xl font-bold text-slate-900">{{ data.all_store_p25_days }}天</p>
            <p class="text-[10px] text-slate-400 mt-1">25%的复购间隔 ≤ 该天数</p>
            <p
              v-if="data.p25_days_yoy != null"
              class="text-[10px] mt-0.5 font-medium"
              :class="data.p25_days_yoy < 0 ? 'text-emerald-600' : data.p25_days_yoy > 0 ? 'text-rose-600' : 'text-slate-400'"
            >
              vs {{ data.ly_all_store_p25_days ?? '?' }}天 ({{ data.p25_days_yoy > 0 ? '+' : '' }}{{ data.p25_days_yoy }}天)
            </p>
          </div>
        </NGi>
        <NGi>
          <div class="bi-card bi-card-hover px-3 py-3 text-center">
            <p class="text-xs text-slate-500">P75复购天数</p>
            <p class="text-2xl font-bold text-slate-900">{{ data.all_store_p75_days }}天</p>
            <p class="text-[10px] text-slate-400 mt-1">75%的复购间隔 ≤ 该天数</p>
            <p
              v-if="data.p75_days_yoy != null"
              class="text-[10px] mt-0.5 font-medium"
              :class="data.p75_days_yoy < 0 ? 'text-emerald-600' : data.p75_days_yoy > 0 ? 'text-rose-600' : 'text-slate-400'"
            >
              vs {{ data.ly_all_store_p75_days ?? '?' }}天 ({{ data.p75_days_yoy > 0 ? '+' : '' }}{{ data.p75_days_yoy }}天)
            </p>
          </div>
        </NGi>
        <NGi>
          <div class="bi-card bi-card-hover px-3 py-3 text-center">
            <p class="text-xs text-slate-500">平均复购天数</p>
            <p class="text-2xl font-bold text-slate-900">{{ data.all_store_avg_days }}天</p>
            <p class="text-[10px] text-slate-400 mt-1">复购周期内平均复购间隔</p>
            <p
              v-if="data.avg_days_yoy != null"
              class="text-[10px] mt-0.5 font-medium"
              :class="data.avg_days_yoy < 0 ? 'text-emerald-600' : data.avg_days_yoy > 0 ? 'text-rose-600' : 'text-slate-400'"
            >
              vs {{ data.ly_all_store_avg_days ?? '?' }}天 ({{ data.avg_days_yoy > 0 ? '+' : '' }}{{ data.avg_days_yoy }}天)
            </p>
          </div>
        </NGi>
        <NGi>
          <!-- Sprint 169: 新增复购率卡片 (next to 平均复购天数) -->
          <div class="bi-card bi-card-hover px-3 py-3 text-center">
            <p class="text-xs text-slate-500">复购率</p>
            <p class="text-2xl font-bold text-slate-900">{{ (data.all_store_repurchase_rate * 100).toFixed(1) }}%</p>
            <p class="text-[10px] text-slate-400 mt-1">2+订单人数 / 总购买人数</p>
            <div v-if="data.yoy_all_store_repurchase_rate != null" class="mt-0.5 flex justify-center">
              <span class="text-[10px] text-slate-500 mr-1">vs</span>
              <YOYBadge :value="data.yoy_all_store_repurchase_rate" unit="pp" />
            </div>
          </div>
        </NGi>
      </NGrid>
      <p class="text-[11px] text-slate-400 mb-4">统计口径：复购判定含当天多单（订单数 ≥ 2 即算复购），复购间隔按天去重后计算（当天多单合并为一天）</p>

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
    </template>
  </div>
</template>

<style scoped>
.repurchase-cycle-tab {
  padding-top: 8px;
}
</style>
