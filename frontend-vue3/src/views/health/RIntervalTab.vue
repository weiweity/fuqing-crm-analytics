<script setup lang="ts">
import { computed, toValue, h, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NButton } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useFilterStore } from '@/stores/filterStore'
import {
  fetchRFMRFlow,
  type RFMRFlowRow,
  type RFMRFlowResponse,
} from '@/api/flow'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import DataTablePro from '@/components/DataTablePro.vue'
import YOYGuard from '@/components/YOYGuard.vue'
import ExportToolbar from '@/components/ExportToolbar.vue'
import { BRAND_PRIMARY } from '@/composables/useChartTheme'
import type { EChartTooltipParam, EChartLabelParam } from '@/types/echarts'
import type { XlsxColumn } from '@/utils/exportXlsx'

const filterStore = useFilterStore()
import { LOW_PRICE_CHANNELS } from '@/constants/channels'
const rChartRef = ref<InstanceType<typeof EChartsWrapper> | null>(null)

const rFlowQueryParams = computed(() => ({
  start_date: filterStore.dateRange[0],
  end_date: filterStore.dateRange[1],
  channel: filterStore.channel === '全店' ? undefined : filterStore.channel,
  metric_type: 'GSV' as const,
  exclude_channels: filterStore.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined,
}))

// 对比参数：auto_yoy 不传（后端原生 Y-1），auto_mom / custom 传计算后的日期
const compareQueryParams = computed(() => {
  if (filterStore.compareMode === 'auto_yoy') return {}
  const comp = filterStore.compareParams
  if (!comp) return {}
  return { compare_start_date: comp[0], compare_end_date: comp[1] }
})

// ⚠️ queryKey 必须 computed(() => [..., {...}]) 展开，否则 ComputedRef 嵌套导致 channel 变化不触发请求
const rFlowQueryKey = computed(() => ['rfm-r-flow', { ...toValue(rFlowQueryParams) }, toValue(compareQueryParams)])

// L4.75.2: 默认不自动 fetch, 用户手动点击按钮触发
const rFlowAutoFetch = ref(false)
function onRFlowQueryClick() {
  rFlowAutoFetch.value = true
  rFlowRefetch()
}

const { data: rFlowData, isLoading: rFlowLoading, error: rFlowError, refetch: rFlowRefetch } = useQuery({
  queryKey: rFlowQueryKey,
  queryFn: () => fetchRFMRFlow({ ...toValue(rFlowQueryParams), ...toValue(compareQueryParams) }),
  enabled: rFlowAutoFetch,
  staleTime: 60_000,
})

// ── 回购率柱状图 ──
const repurchaseRateChartOption = computed(() => {
  if (!rFlowData.value) return {}
  const data = rFlowData.value as RFMRFlowResponse
  const rows = data.rows.filter((r) => r.r_segment !== '已购客TTL')
  const segments = rows.map((r) => r.r_segment)

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
            <span class="font-medium text-slate-800">${(Number(p.value) * 100).toFixed(2)}%</span>
          </div>`
        })
        return html
      },
    },
    legend: {
      data: [`${data.year_label}年`, `${data.comp_year_label}年`, `${data.prev2_year_label}年`],
      top: 0,
      icon: 'circle',
      itemGap: 16,
      textStyle: { color: '#64748b', fontSize: 11 },
    },
    grid: { left: 12, right: 12, top: 40, bottom: 8 },
    xAxis: {
      type: 'category',
      data: segments,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 11, interval: 0 },
    },
    yAxis: {
      type: 'value',
      name: '回购率',
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
        name: `${data.year_label}年`,
        type: 'bar',
        data: rows.map((r) => r.repurchase_rate_current),
        itemStyle: { color: BRAND_PRIMARY, borderRadius: [3, 3, 0, 0] },
        barGap: '20%',
        label: { show: true, position: 'top', formatter: (p: EChartLabelParam) => `${(p.value as number * 100).toFixed(1)}%`, fontSize: 10, color: BRAND_PRIMARY },
      },
      {
        name: `${data.comp_year_label}年`,
        type: 'bar',
        data: rows.map((r) => r.repurchase_rate_comp),
        itemStyle: { color: '#60a5fa', borderRadius: [3, 3, 0, 0] },
        label: { show: true, position: 'top', formatter: (p: EChartLabelParam) => `${(p.value as number * 100).toFixed(1)}%`, fontSize: 10, color: '#60a5fa' },
      },
      {
        name: `${data.prev2_year_label}年`,
        type: 'bar',
        data: rows.map((r) => r.repurchase_rate_prev2),
        itemStyle: { color: '#94a3b8', borderRadius: [3, 3, 0, 0] },
        label: { show: true, position: 'top', formatter: (p: EChartLabelParam) => `${(p.value as number * 100).toFixed(1)}%`, fontSize: 10, color: '#94a3b8' },
      },
    ],
  }
})

// ── 辅助函数 ──
function formatSlashDate(d: Date) {
  return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`
}

function addDays(d: Date, days: number) {
  const nd = new Date(d)
  nd.setDate(nd.getDate() + days)
  return nd
}

const segmentMeta = computed<Record<string, { label: string; range: string }>>(() => {
  const start = filterStore.dateRange[0]
  const cutoff = addDays(new Date(start + 'T00:00:00'), -1)
  const r0 = formatSlashDate(addDays(cutoff, -30))
  const r1 = formatSlashDate(cutoff)
  const r2 = formatSlashDate(addDays(cutoff, -90))
  const r3 = formatSlashDate(addDays(cutoff, -31))
  const r4 = formatSlashDate(addDays(cutoff, -180))
  const r5 = formatSlashDate(addDays(cutoff, -91))
  const r6 = formatSlashDate(addDays(cutoff, -365))
  const r7 = formatSlashDate(addDays(cutoff, -181))
  const r8 = formatSlashDate(addDays(cutoff, -730))
  const r9 = formatSlashDate(addDays(cutoff, -366))
  const r10 = formatSlashDate(addDays(cutoff, -730))
  return {
    '近1个月已购客': { label: '近1个月已购客', range: `${r0}-${r1}` },
    '近2-3个月已购客': { label: '近2-3个月已购客', range: `${r2}-${r3}` },
    '近4-6月已购客': { label: '近4-6月已购客', range: `${r4}-${r5}` },
    '近7-12个月已购客': { label: '近7-12个月已购客', range: `${r6}-${r7}` },
    '近13个月-近24个月已购客': { label: '近13个月-近24个月已购客', range: `${r8}-${r9}` },
    '2年外已购客': { label: '2年外已购客', range: `<${r10}` },
    '已购客TTL': { label: '已购客TTL', range: '全部' },
  }
})

// ── 表格列定义 ──
const rFlowColumns = computed<DataTableColumns<RFMRFlowRow>>(() => {
  const yr = rFlowData.value?.year_label || String(new Date().getFullYear())
  const yr2 = rFlowData.value?.comp_year_label || String(new Date().getFullYear() - 1)
  const yr3 = rFlowData.value?.prev2_year_label || String(new Date().getFullYear() - 2)

  return [
    {
      title: 'R 区间',
      key: 'r_segment',
      width: 160,
      fixed: 'left',
      align: 'center',
      render: (row: RFMRFlowRow) => {
        const meta = segmentMeta.value[row.r_segment] || { label: row.r_segment, range: '' }
        return h('div', { class: 'flex flex-col items-center justify-center leading-tight py-0.5' }, [
          h('div', { class: 'text-[13px] font-medium text-slate-800' }, meta.label),
          h('div', { class: 'text-[11px] text-slate-400 mt-0.5' }, meta.range),
        ])
      },
    },
    { title: `${yr}历史人数`, key: 'hist_users_current', width: 90, align: 'right', render: (r) => r.hist_users_current.toLocaleString() },
    { title: `${yr}回购人数`, key: 'repurchase_users_current', width: 90, align: 'right', render: (r) => r.repurchase_users_current.toLocaleString() },
    {
      title: `${yr}回购率`,
      key: 'repurchase_rate_current',
      width: 80,
      align: 'right',
      render: (r) => h('span', { class: 'font-medium text-slate-800' }, `${(r.repurchase_rate_current * 100).toFixed(2)}%`),
    },
    { title: `${yr}回购GSV`, key: 'repurchase_gsv_current', width: 90, align: 'right', render: (r) => r.repurchase_gsv_current >= 10000 ? `${(r.repurchase_gsv_current / 10000).toFixed(1)}万` : r.repurchase_gsv_current.toLocaleString() },
    {
      title: `${yr}回购GSV占比`,
      key: 'repurchase_gsv_ratio_current',
      width: 90,
      align: 'right',
      render: (r) => `${(r.repurchase_gsv_ratio_current * 100).toFixed(2)}%`,
    },
    {
      title: `${yr}年同比历史人数`,
      key: 'yoy_hist_users',
      width: 110,
      align: 'center',
      render: (r: RFMRFlowRow) => h(YOYGuard, { value: r.yoy_hist_users, styled: true}),
    },
    {
      title: `${yr}年同比人数`,
      key: 'yoy_repurchase_users',
      width: 110,
      align: 'center',
      render: (r: RFMRFlowRow) => h(YOYGuard, { value: r.yoy_repurchase_users, styled: true}),
    },
    {
      title: `${yr}同比回购率`,
      key: 'yoy_repurchase_rate',
      width: 110,
      align: 'center',
      render: (r: RFMRFlowRow) => h(YOYGuard, { value: r.yoy_repurchase_rate, unit: 'pp', styled: true}),
    },
    {
      title: `${yr}同比回购GSV`,
      key: 'yoy_repurchase_gsv',
      width: 110,
      align: 'center',
      render: (r: RFMRFlowRow) => h(YOYGuard, { value: r.yoy_repurchase_gsv, styled: true}),
    },
    {
      title: `${yr}同比回购GSV占比`,
      key: 'yoy_repurchase_gsv_ratio_ppt',
      width: 110,
      align: 'center',
      render: (r: RFMRFlowRow) => h(YOYGuard, { value: r.yoy_repurchase_gsv_ratio_ppt, unit: 'pp', styled: true}),
    },
    { title: `${yr2}历史人数`, key: 'hist_users_comp', width: 90, align: 'right', render: (r) => r.hist_users_comp.toLocaleString() },
    {
      title: `${yr2}回购率`,
      key: 'repurchase_rate_comp',
      width: 80,
      align: 'right',
      render: (r) => `${(r.repurchase_rate_comp * 100).toFixed(2)}%`,
    },
    { title: `${yr3}历史人数`, key: 'hist_users_prev2', width: 90, align: 'right', render: (r) => r.hist_users_prev2.toLocaleString() },
    {
      title: `${yr3}回购率`,
      key: 'repurchase_rate_prev2',
      width: 80,
      align: 'right',
      render: (r) => `${(r.repurchase_rate_prev2 * 100).toFixed(2)}%`,
    },
  ]
})

// ── R 区间 Excel 导出列定义 ──
const rFlowXlsxColumns = computed<XlsxColumn[]>(() => {
  const yr = rFlowData.value?.year_label || String(new Date().getFullYear())
  const yr2 = rFlowData.value?.comp_year_label || String(new Date().getFullYear() - 1)
  const yr3 = rFlowData.value?.prev2_year_label || String(new Date().getFullYear() - 2)
  return [
    { header: 'R区间', key: 'r_segment', width: 20 },
    { header: `${yr}历史人数`, key: 'hist_users_current', width: 12, numFmt: '#,##0' },
    { header: `${yr}回购人数`, key: 'repurchase_users_current', width: 12, numFmt: '#,##0' },
    { header: `${yr}回购率`, key: 'repurchase_rate_current', width: 10, numFmt: '0.00%' },
    { header: `${yr}回购GSV`, key: 'repurchase_gsv_current', width: 14, numFmt: '¥#,##0' },
    { header: `${yr}回购GSV占比`, key: 'repurchase_gsv_ratio_current', width: 12, numFmt: '0.00%' },
    { header: `${yr}同比历史人数`, key: 'yoy_hist_users', width: 12, numFmt: '0.0%' },
    { header: `${yr}同比回购人数`, key: 'yoy_repurchase_users', width: 12, numFmt: '0.0%' },
    { header: `${yr}同比回购率`, key: 'yoy_repurchase_rate', width: 12, numFmt: '0.0%' },
    { header: `${yr}同比回购GSV`, key: 'yoy_repurchase_gsv', width: 12, numFmt: '0.0%' },
    { header: `${yr}同比回购GSV占比`, key: 'yoy_repurchase_gsv_ratio_ppt', width: 14, numFmt: '0.0%' },
    { header: `${yr2}历史人数`, key: 'hist_users_comp', width: 12, numFmt: '#,##0' },
    { header: `${yr2}回购率`, key: 'repurchase_rate_comp', width: 10, numFmt: '0.00%' },
    { header: `${yr3}历史人数`, key: 'hist_users_prev2', width: 12, numFmt: '#,##0' },
    { header: `${yr3}回购率`, key: 'repurchase_rate_prev2', width: 10, numFmt: '0.00%' },
  ]
})

// ── 导出订单明细 ── Sprint 175 Q2: 整块删除 (用户拍板功能不需要)
</script>

<template>
  <div class="r-interval-tab">
    <!-- 图表 -->
    <div class="bi-card p-4 mb-4">
      <div class="flex items-center justify-between mb-0.5">
        <div>
          <h3 class="text-sm font-semibold text-slate-800">回购率 3 年对比</h3>
          <p class="text-[11px] text-slate-500">各 R 区间老客唤醒效率变化</p>
        </div>
        <ExportToolbar
          :filename="`老客分析_R区间回购率_${filterStore.dateRange[0]}_${filterStore.dateRange[1]}`"
          :chart-ref="rChartRef"
        />
      </div>
      <ErrorState v-if="rFlowError" :message="(rFlowError as Error).message" @retry="rFlowRefetch()" />
      <LoadingState v-else-if="rFlowLoading" />
      <div v-else-if="!rFlowAutoFetch" class="manual-query-guide">
        <NButton type="primary" size="large" @click="onRFlowQueryClick">🔍 点击查询 R 区间数据</NButton>
        <p class="hint">说明: 本次结果计算量较大, 请点击按钮手动触发查询。</p>
      </div>
      <EmptyState v-else-if="!rFlowData?.rows?.length" description="当前条件下无数据" />
      <EChartsWrapper v-else ref="rChartRef" :option="repurchaseRateChartOption" height="260px" />
    </div>

    <!-- 表格：全店 -->
    <div class="bi-card p-4 mb-4">
      <div class="flex items-center justify-between mb-0.5">
        <div>
          <h3 class="text-sm font-semibold text-slate-800">R 区间流转详情</h3>
          <p class="text-[11px] text-slate-500">老客分区回购表现 — 3 年同比</p>
        </div>
        <div class="flex items-center gap-2">
          <ExportToolbar
            :filename="`老客分析_R区间全店_${filterStore.dateRange[0]}_${filterStore.dateRange[1]}`"
            :columns="rFlowXlsxColumns"
            :data="rFlowData?.rows ?? []"
            sheet-name="R区间全店"
          />
        </div>
      </div>
      <ErrorState v-if="rFlowError" :message="(rFlowError as Error).message" @retry="rFlowRefetch()" />
      <LoadingState v-else-if="rFlowLoading" />
      <EmptyState v-else-if="!rFlowData?.rows?.length" description="当前条件下无数据" />
      <DataTablePro
        v-else
        :columns="rFlowColumns"
        :data="rFlowData.rows"
        :pagination="{ pageSize: 12 }"
        :scroll-x="2100"
      />
    </div>

    <!-- 表格：会员 -->
    <div class="bi-card p-4 mb-4">
      <div class="flex items-center justify-between mb-0.5">
        <div>
          <h3 class="text-sm font-semibold text-slate-800">R 区间流转详情 — 会员</h3>
          <p class="text-[11px] text-slate-500">会员老客分区回购表现 — 3 年同比</p>
        </div>
        <ExportToolbar
          :filename="`老客分析_R区间会员_${filterStore.dateRange[0]}_${filterStore.dateRange[1]}`"
          :columns="rFlowXlsxColumns"
          :data="rFlowData?.member_rows ?? []"
          sheet-name="R区间会员"
        />
      </div>
      <ErrorState v-if="rFlowError" :message="(rFlowError as Error).message" @retry="rFlowRefetch()" />
      <LoadingState v-else-if="rFlowLoading" />
      <EmptyState v-else-if="!rFlowData?.member_rows?.length" description="当前条件下无数据" />
      <DataTablePro
        v-else
        :columns="rFlowColumns"
        :data="rFlowData.member_rows"
        :pagination="{ pageSize: 12 }"
        :scroll-x="2100"
      />
    </div>

    <!-- 表格：本渠道（仅当选择了渠道时显示） -->
    <template v-if="filterStore.channel !== '全店' && !rFlowLoading && rFlowData?.same_channel_rows?.length">
      <div class="bi-card p-4 mb-4">
        <h3 class="text-sm font-semibold text-slate-800 mb-0.5">R 区间流转详情 — 本渠道</h3>
        <p class="text-[11px] text-slate-500 mb-3">本渠道老客在本渠道回购表现 — 3 年同比</p>
        <DataTablePro
          :columns="rFlowColumns"
          :data="rFlowData.same_channel_rows"
          :pagination="{ pageSize: 12 }"
          :scroll-x="2100"
        />
      </div>
      <div class="bi-card p-4 mb-4">
        <h3 class="text-sm font-semibold text-slate-800 mb-0.5">R 区间流转详情 — 会员本渠道</h3>
        <p class="text-[11px] text-slate-500 mb-3">会员本渠道老客在本渠道回购表现 — 3 年同比</p>
        <DataTablePro
          :columns="rFlowColumns"
          :data="rFlowData.member_same_channel_rows"
          :pagination="{ pageSize: 12 }"
          :scroll-x="2100"
        />
      </div>
    </template>
  </div>
</template>

<style scoped>
.r-interval-tab {
  padding-top: 8px;
}
</style>
