<script setup lang="ts">
import { computed, toValue, h, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import type { DataTableColumns } from 'naive-ui'
import { useFilterStore } from '@/stores/filterStore'
import {
  fetchRFMFRFlow,
  type RFMFRFlowRow,
  type RFMFRFlowResponse,
} from '@/api/flow'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import DataTablePro from '@/components/DataTablePro.vue'
import YOYBadge from '@/components/YOYBadge.vue'
import ExportToolbar from '@/components/ExportToolbar.vue'
import { BRAND_PRIMARY } from '@/composables/useChartTheme'
import type { EChartTooltipParam, EChartLabelParam } from '@/types/echarts'
import type { XlsxColumn } from '@/utils/exportXlsx'
import { downloadSegmentOrdersCSV } from '@/api/flow'
import { NButton, NSelect, NModal, NSpace, useMessage } from 'naive-ui'

const filterStore = useFilterStore()
import { LOW_PRICE_CHANNELS } from '@/constants/channels'
const fChartRef = ref<InstanceType<typeof EChartsWrapper> | null>(null)

const fFlowQueryParams = computed(() => ({
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
const fFlowQueryKey = computed(() => ['rfm-f-flow', { ...toValue(fFlowQueryParams) }, toValue(compareQueryParams)])

const { data: fFlowData, isLoading: fFlowLoading, error: fFlowError, refetch: fFlowRefetch } = useQuery({
  queryKey: fFlowQueryKey,
  queryFn: () => fetchRFMFRFlow({ ...toValue(fFlowQueryParams), ...toValue(compareQueryParams) }),
  staleTime: 60_000,
})

// ── 回购率柱状图 ──
const repurchaseRateChartOption = computed(() => {
  if (!fFlowData.value) return {}
  const data = fFlowData.value as RFMFRFlowResponse
  const rows = data.rows.filter((r) => r.f_segment !== '已购客TTL')
  const segments = rows.map((r) => r.f_segment)

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
        label: { show: true, position: 'top', formatter: (p: EChartLabelParam) => `${((p.value as number) * 100).toFixed(1)}%`, fontSize: 10, color: BRAND_PRIMARY },
      },
      {
        name: `${data.comp_year_label}年`,
        type: 'bar',
        data: rows.map((r) => r.repurchase_rate_comp),
        itemStyle: { color: '#60a5fa', borderRadius: [3, 3, 0, 0] },
        label: { show: true, position: 'top', formatter: (p: EChartLabelParam) => `${((p.value as number) * 100).toFixed(1)}%`, fontSize: 10, color: '#60a5fa' },
      },
      {
        name: `${data.prev2_year_label}年`,
        type: 'bar',
        data: rows.map((r) => r.repurchase_rate_prev2),
        itemStyle: { color: '#94a3b8', borderRadius: [3, 3, 0, 0] },
        label: { show: true, position: 'top', formatter: (p: EChartLabelParam) => `${((p.value as number) * 100).toFixed(1)}%`, fontSize: 10, color: '#94a3b8' },
      },
    ],
  }
})

// ── 表格列定义 ──
const fFlowColumns = computed<DataTableColumns<RFMFRFlowRow>>(() => {
  const yr = fFlowData.value?.year_label || String(new Date().getFullYear())
  const yr2 = fFlowData.value?.comp_year_label || String(new Date().getFullYear() - 1)
  const yr3 = fFlowData.value?.prev2_year_label || String(new Date().getFullYear() - 2)

  return [
    {
      title: 'F 区间',
      key: 'f_segment',
      width: 160,
      fixed: 'left',
      align: 'center',
      render: (row: RFMFRFlowRow) => {
        return h('div', { class: 'flex flex-col items-center justify-center leading-tight py-0.5' }, [
          h('div', { class: 'text-[13px] font-medium text-slate-800' }, row.f_segment),
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
      render: (r: RFMFRFlowRow) => h(YOYBadge, { value: r.yoy_hist_users }),
    },
    {
      title: `${yr}年同比人数`,
      key: 'yoy_repurchase_users',
      width: 110,
      align: 'center',
      render: (r: RFMFRFlowRow) => h(YOYBadge, { value: r.yoy_repurchase_users }),
    },
    {
      title: `${yr}同比回购率`,
      key: 'yoy_repurchase_rate',
      width: 110,
      align: 'center',
      render: (r: RFMFRFlowRow) => h(YOYBadge, { value: r.yoy_repurchase_rate, unit: 'pp' }),
    },
    {
      title: `${yr}同比回购GSV`,
      key: 'yoy_repurchase_gsv',
      width: 110,
      align: 'center',
      render: (r: RFMFRFlowRow) => h(YOYBadge, { value: r.yoy_repurchase_gsv }),
    },
    {
      title: `${yr}同比回购GSV占比`,
      key: 'yoy_repurchase_gsv_ratio',
      width: 110,
      align: 'center',
      render: (r: RFMFRFlowRow) => h(YOYBadge, { value: r.yoy_repurchase_gsv_ratio, unit: 'pp' }),
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

// ── F 区间 Excel 导出列定义 ──
const fFlowXlsxColumns = computed<XlsxColumn[]>(() => {
  const yr = fFlowData.value?.year_label || String(new Date().getFullYear())
  const yr2 = fFlowData.value?.comp_year_label || String(new Date().getFullYear() - 1)
  const yr3 = fFlowData.value?.prev2_year_label || String(new Date().getFullYear() - 2)
  return [
    { header: 'F区间', key: 'f_segment', width: 18 },
    { header: `${yr}历史人数`, key: 'hist_users_current', width: 12, numFmt: '#,##0' },
    { header: `${yr}回购人数`, key: 'repurchase_users_current', width: 12, numFmt: '#,##0' },
    { header: `${yr}回购率`, key: 'repurchase_rate_current', width: 10, numFmt: '0.00%' },
    { header: `${yr}回购GSV`, key: 'repurchase_gsv_current', width: 14, numFmt: '¥#,##0' },
    { header: `${yr}回购GSV占比`, key: 'repurchase_gsv_ratio_current', width: 12, numFmt: '0.00%' },
    { header: `${yr}同比历史人数`, key: 'yoy_hist_users', width: 12, numFmt: '0.0%' },
    { header: `${yr}同比回购人数`, key: 'yoy_repurchase_users', width: 12, numFmt: '0.0%' },
    { header: `${yr}同比回购率`, key: 'yoy_repurchase_rate', width: 12, numFmt: '0.0%' },
    { header: `${yr}同比回购GSV`, key: 'yoy_repurchase_gsv', width: 12, numFmt: '0.0%' },
    { header: `${yr}同比回购GSV占比`, key: 'yoy_repurchase_gsv_ratio', width: 14, numFmt: '0.0%' },
    { header: `${yr2}历史人数`, key: 'hist_users_comp', width: 12, numFmt: '#,##0' },
    { header: `${yr2}回购率`, key: 'repurchase_rate_comp', width: 10, numFmt: '0.00%' },
    { header: `${yr3}历史人数`, key: 'hist_users_prev2', width: 12, numFmt: '#,##0' },
    { header: `${yr3}回购率`, key: 'repurchase_rate_prev2', width: 10, numFmt: '0.00%' },
  ]
})

// ── 导出订单明细 ──
const message = useMessage()
const showExportModal = ref(false)
const exportSegment = ref<string | null>(null)
const exportLoading = ref(false)
const F_SEGMENTS = ['1次购买', '2次购买', '3次购买', '4次购买', '5次及以上']
const fSegmentOptions = F_SEGMENTS.map(s => ({ label: s, value: s }))

function openExportDialog() {
  exportSegment.value = null
  showExportModal.value = true
}

async function handleExportOrders() {
  if (!exportSegment.value) {
    message.warning('请选择要导出的区间')
    return
  }
  exportLoading.value = true
  try {
    await downloadSegmentOrdersCSV({
      dimension: 'f',
      segment: exportSegment.value,
      start_date: filterStore.dateRange[0],
      end_date: filterStore.dateRange[1],
      metric_type: 'GSV',
      channel: filterStore.channel === '全店' ? undefined : filterStore.channel,
      exclude_channels: filterStore.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined,
    })
    message.success('导出成功')
    showExportModal.value = false
  } catch (e: unknown) {
    message.error((e as Error).message || '导出失败')
  } finally {
    exportLoading.value = false
  }
}
</script>

<template>
  <div class="f-interval-tab">
    <!-- 图表 -->
    <div class="bi-card p-4 mb-4">
      <div class="flex items-center justify-between mb-0.5">
        <div>
          <h3 class="text-sm font-semibold text-slate-800">回购率 3 年对比</h3>
          <p class="text-[11px] text-slate-500">各 F 区间老客唤醒效率变化</p>
        </div>
        <ExportToolbar
          :filename="`老客分析_F区间回购率_${filterStore.dateRange[0]}_${filterStore.dateRange[1]}`"
          :chart-ref="fChartRef"
        />
      </div>
      <ErrorState v-if="fFlowError" :message="(fFlowError as Error).message" @retry="fFlowRefetch()" />
      <LoadingState v-else-if="fFlowLoading" />
      <EmptyState v-else-if="!fFlowData?.rows?.length" description="当前条件下无数据" />
      <EChartsWrapper v-else ref="fChartRef" :option="repurchaseRateChartOption" height="260px" />
    </div>

    <!-- 表格：全店 -->
    <div class="bi-card p-4 mb-4">
      <div class="flex items-center justify-between mb-0.5">
        <div>
          <h3 class="text-sm font-semibold text-slate-800">F 区间流转详情</h3>
          <p class="text-[11px] text-slate-500">老客按购买频次分区回购表现 — 3 年同比</p>
        </div>
        <div class="flex items-center gap-2">
          <ExportToolbar
            :filename="`老客分析_F区间全店_${filterStore.dateRange[0]}_${filterStore.dateRange[1]}`"
            :columns="fFlowXlsxColumns"
            :data="fFlowData?.rows ?? []"
            sheet-name="F区间全店"
          />
          <NButton size="tiny" quaternary type="primary" @click="openExportDialog">
            导出订单明细
          </NButton>
        </div>
      </div>
      <ErrorState v-if="fFlowError" :message="(fFlowError as Error).message" @retry="fFlowRefetch()" />
      <LoadingState v-else-if="fFlowLoading" />
      <EmptyState v-else-if="!fFlowData?.rows?.length" description="当前条件下无数据" />
      <DataTablePro
        v-else
        :columns="fFlowColumns"
        :data="fFlowData.rows"
        :pagination="{ pageSize: 12 }"
        :scroll-x="2100"
      />
    </div>

    <!-- 表格：会员 -->
    <div class="bi-card p-4 mb-4">
      <div class="flex items-center justify-between mb-0.5">
        <div>
          <h3 class="text-sm font-semibold text-slate-800">F 区间流转详情 — 会员</h3>
          <p class="text-[11px] text-slate-500">会员老客按购买频次分区回购表现 — 3 年同比</p>
        </div>
        <ExportToolbar
          :filename="`老客分析_F区间会员_${filterStore.dateRange[0]}_${filterStore.dateRange[1]}`"
          :columns="fFlowXlsxColumns"
          :data="fFlowData?.member_rows ?? []"
          sheet-name="F区间会员"
        />
      </div>
      <ErrorState v-if="fFlowError" :message="(fFlowError as Error).message" @retry="fFlowRefetch()" />
      <LoadingState v-else-if="fFlowLoading" />
      <EmptyState v-else-if="!fFlowData?.member_rows?.length" description="当前条件下无数据" />
      <DataTablePro
        v-else
        :columns="fFlowColumns"
        :data="fFlowData.member_rows"
        :pagination="{ pageSize: 12 }"
        :scroll-x="2100"
      />
    </div>

    <!-- 表格：本渠道（仅当选择了渠道时显示） -->
    <template v-if="filterStore.channel !== '全店' && !fFlowLoading && fFlowData?.same_channel_rows?.length">
      <div class="bi-card p-4 mb-4">
        <h3 class="text-sm font-semibold text-slate-800 mb-0.5">F 区间流转详情 — 本渠道</h3>
        <p class="text-[11px] text-slate-500 mb-3">本渠道老客在本渠道回购表现 — 3 年同比</p>
        <DataTablePro
          :columns="fFlowColumns"
          :data="fFlowData.same_channel_rows"
          :pagination="{ pageSize: 12 }"
          :scroll-x="2100"
        />
      </div>
      <div class="bi-card p-4 mb-4">
        <h3 class="text-sm font-semibold text-slate-800 mb-0.5">F 区间流转详情 — 会员本渠道</h3>
        <p class="text-[11px] text-slate-500 mb-3">会员本渠道老客在本渠道回购表现 — 3 年同比</p>
        <DataTablePro
          :columns="fFlowColumns"
          :data="fFlowData.member_same_channel_rows"
          :pagination="{ pageSize: 12 }"
          :scroll-x="2100"
        />
      </div>
    </template>

    <!-- 导出订单明细弹窗 -->
    <NModal v-model:show="showExportModal" preset="card" title="导出订单明细" style="width: 420px; max-width: 95vw;">
      <div class="mb-3">
        <p class="text-xs text-slate-500 mb-2">选择要导出订单明细的 F 区间：</p>
        <NSelect v-model:value="exportSegment" :options="fSegmentOptions" placeholder="请选择F区间" />
      </div>
      <NSpace justify="end">
        <NButton size="small" @click="showExportModal = false">取消</NButton>
        <NButton size="small" type="primary" :loading="exportLoading" :disabled="!exportSegment" @click="handleExportOrders">
          导出 CSV
        </NButton>
      </NSpace>
    </NModal>
  </div>
</template>

<style scoped>
.f-interval-tab {
  padding-top: 8px;
}
</style>
