<script setup lang="ts">
import { computed, toValue, h, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NGrid, NGi, NTabs, NTabPane, NAlert, NButton } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useFilterStore } from '@/stores/filterStore'
import {
  fetchFlowMatrix,
  fetchFlowSankey,
  fetchRFMRFlow,
  type FlowMatrixResponse,
  type FlowSankeyResponse,
  type RFMRFlowRow,
  type RFMRFlowResponse,
} from '@/api/flow'
import MetricCard from '@/components/MetricCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import RfmVersionBanner from '@/components/RfmVersionBanner.vue'
import RatioConventionBanner from '@/components/RatioConventionBanner.vue'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import { BRAND_PRIMARY } from '@/composables/useChartTheme'
import EmptyState from '@/components/EmptyState.vue'
import DataTablePro from '@/components/DataTablePro.vue'
import YOYGuard from '@/components/YOYGuard.vue'

const filterStore = useFilterStore()
const activeTab = ref('r-flow')
const showLogicExplain = ref(true)

// ─────────────────────────────────────────────────────────────
// 参数定义
// ─────────────────────────────────────────────────────────────
import { LOW_PRICE_CHANNELS } from '@/constants/channels'

const queryParams = computed(() => ({
  from_date: filterStore.dateRange[0],
  to_date: filterStore.dateRange[1],
  lookback_days: 90,
  metric_type: 'GMV' as const,
  exclude_channels: filterStore.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined,
}))

const rFlowQueryParams = computed(() => ({
  start_date: filterStore.dateRange[0],
  end_date: filterStore.dateRange[1],
  channel: filterStore.channel === '全店' ? undefined : filterStore.channel,
  metric_type: 'GSV' as const,
  exclude_channels: filterStore.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined,
}))

// ─────────────────────────────────────────────────────────────
// Tab 按需加载：sankey / r-flow 延迟加载；matrix 始终加载（顶部卡片依赖）
// ─────────────────────────────────────────────────────────────
// ─────────────────────────────────────────────────────────────
// ⚠️ queryKey 必须用 computed(() => [..., {...spreadedValue}]) 展开
// 否则 TanStack Vue Query 无法追踪 ComputedRef 内的嵌套 reactive 值变化
// 表现：filterStore.channel 变化后请求不触发（"点了没反应"）
// ─────────────────────────────────────────────────────────────
const matrixQueryKey = computed(() => ['flow-matrix', { ...toValue(queryParams) }])
const sankeyQueryKey = computed(() => ['flow-sankey', { ...toValue(queryParams) }])
const rFlowQueryKey = computed(() => ['rfm-r-flow', { ...toValue(rFlowQueryParams) }])

const { data: matrixData, isLoading: matrixLoading, error: matrixError, refetch: matrixRefetch } = useQuery({
  queryKey: matrixQueryKey,
  queryFn: () => {
    const p = toValue(queryParams)
    return fetchFlowMatrix({
      from_date: p.from_date,
      to_date: p.to_date,
      lookback_days: p.lookback_days,
      metric_type: p.metric_type,
      exclude_channels: p.exclude_channels,
    })
  },
  staleTime: 60_000,
})

const { data: sankeyData, isLoading: sankeyLoading, error: sankeyError, refetch: sankeyRefetch } = useQuery({
  queryKey: sankeyQueryKey,
  queryFn: () => {
    const p = toValue(queryParams)
    return fetchFlowSankey({
      from_date: p.from_date,
      to_date: p.to_date,
      lookback_days: p.lookback_days,
      metric_type: p.metric_type,
      exclude_channels: p.exclude_channels,
    })
  },
  staleTime: 60_000,
  enabled: computed(() => activeTab.value === 'sankey'),
})

const { data: rFlowData, isLoading: rFlowLoading, error: rFlowError, refetch: rFlowRefetch } = useQuery({
  queryKey: rFlowQueryKey,
  queryFn: () => {
    const p = toValue(rFlowQueryParams)
    return fetchRFMRFlow(p)
  },
  staleTime: 60_000,
  enabled: computed(() => activeTab.value === 'r-flow'),
})

// ─────────────────────────────────────────────────────────────
// 格式化辅助
// ─────────────────────────────────────────────────────────────
function formatKPI(value: number, type: 'currency' | 'number' | 'percent') {
  if (type === 'percent') return `${(value * 100).toFixed(1)}%`
  return value.toLocaleString()
}

// ─────────────────────────────────────────────────────────────
// 3年回购率汇总（来自 R区间流转加权平均）
// ─────────────────────────────────────────────────────────────
const repurchase3YData = computed(() => {
  const data = rFlowData.value as RFMRFlowResponse | undefined
  if (!data?.rows?.length) return null
  // 排除 "已购客TTL" 只算各分段
  const validRows = data.rows.filter((r) => r.r_segment !== '已购客TTL')
  const totalHist = validRows.reduce((s, r) => s + r.hist_users_current, 0)
  const totalRep = validRows.reduce((s, r) => s + r.repurchase_users_current, 0)
  const curRate = totalHist > 0 ? totalRep / totalHist : 0

  const totalHistComp = validRows.reduce((s, r) => s + r.hist_users_comp, 0)
  const totalRepComp = validRows.reduce((s, r) => s + r.repurchase_users_comp, 0)
  const compRate = totalHistComp > 0 ? totalRepComp / totalHistComp : 0

  const totalHistPrev2 = validRows.reduce((s, r) => s + r.hist_users_prev2, 0)
  const totalRepPrev2 = validRows.reduce((s, r) => s + r.repurchase_users_prev2, 0)
  const prev2Rate = totalHistPrev2 > 0 ? totalRepPrev2 / totalHistPrev2 : 0

  const yoy = compRate > 0 ? (curRate - compRate) / compRate * 100 : null
  return {
    cur: curRate,
    comp: compRate,
    prev2: prev2Rate,
    yoy,
    yr: data.year_label,
    yr2: data.comp_year_label,
    yr3: data.prev2_year_label,
  }
})

// ─────────────────────────────────────────────────────────────
// 桑基图
// ─────────────────────────────────────────────────────────────
const segmentColors: Record<string, string> = {
  '钻石会员': '#2563eb',
  '潜力新贵': '#10b981',
  '忠实金主': '#ef4444',
  '频次买家': '#f59e0b',
  '豪气新客': '#0891b2',
  '清新路人': '#64748b',
  '沉睡土豪': '#8b5cf6',
  '流失用户': '#94a3b8',
  '其他': '#cbd5e1',
}

const sankeyOption = computed(() => {
  if (!sankeyData.value) return {}
  const data = sankeyData.value as FlowSankeyResponse
  return {
    tooltip: {
      trigger: 'item',
      triggerOn: 'mousemove',
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      textStyle: { color: '#0f172a', fontSize: 12 },
      extraCssText: 'box-shadow: 0 4px 12px -2px rgba(0,0,0,0.08); border-radius: 4px;',
    },
    series: [
      {
        type: 'sankey',
        layout: 'none',
        emphasis: { focus: 'adjacency' },
        nodeAlign: 'left',
        data: data.nodes.map((n) => ({
          name: n.name,
          itemStyle: { color: segmentColors[n.name] || '#2563eb' },
        })),
        links: data.links.map((l) => ({
          source: data.nodes.find((n) => n.id === l.source)?.name || String(l.source),
          target: data.nodes.find((n) => n.id === l.target)?.name || String(l.target),
          value: l.value,
        })),
        lineStyle: { color: 'gradient', curveness: 0.5, opacity: 0.3 },
        label: { color: '#0f172a', fontSize: 11 },
      },
    ],
  }
})

// ─────────────────────────────────────────────────────────────
// 流转矩阵表格
// ─────────────────────────────────────────────────────────────
function getHeatColor(value: number, max: number) {
  if (!max || value <= 0) return 'transparent'
  const ratio = value / max
  const alpha = Math.max(0.05, ratio * 0.55)
  return `rgba(37, 99, 235, ${alpha})`
}

const matrixTable = computed(() => {
  const data = matrixData.value as FlowMatrixResponse | undefined
  if (!data) return { columns: [], data: [] }
  const segments = data.segments.map((s) => s.name)
  const maxCount = Math.max(1, ...data.flow_matrix.map((f) => f.count))

  const pivot: Record<string, Record<string, number>> = {}
  segments.forEach((s) => (pivot[s] = {}))
  data.flow_matrix.forEach((f) => {
    pivot[f.from_segment][f.to_segment] = f.count
  })

  const columns: DataTableColumns<any> = [
    { title: 'From \\ To', key: 'from', width: 120, fixed: 'left' },
    ...segments.map((s) => ({
      title: s,
      key: s,
      width: 90,
      align: 'right' as const,
      render: (row: any) => {
        const val = row[s] as number | undefined
        const display = val && val > 0 ? val.toLocaleString() : '—'
        return h(
          'div',
          {
            style: {
              backgroundColor: getHeatColor(val || 0, maxCount),
              padding: '2px 6px',
              borderRadius: '3px',
              fontWeight: val && val > 0 ? 500 : 400,
              color: val && val > maxCount * 0.5 ? '#fff' : '#0f172a',
              fontSize: '12px',
              textAlign: 'right',
            },
          },
          display
        )
      },
    })),
    {
      title: '合计',
      key: 'total',
      width: 90,
      fixed: 'right',
      align: 'right' as const,
      className: 'bi-cell-number',
      render: (row: any) => h('span', { class: 'font-semibold text-slate-900' }, row.total.toLocaleString()),
    },
  ]

  const tableData = segments.map((fromSeg) => {
    const row: Record<string, any> = { from: fromSeg, total: 0 }
    segments.forEach((toSeg) => {
      const val = pivot[fromSeg]?.[toSeg] || 0
      row[toSeg] = val
      row.total += val
    })
    return row
  })

  const totalRow: Record<string, any> = { from: '合计', total: 0 }
  segments.forEach((toSeg) => {
    let colTotal = 0
    segments.forEach((fromSeg) => {
      colTotal += pivot[fromSeg]?.[toSeg] || 0
    })
    totalRow[toSeg] = colTotal
    totalRow.total += colTotal
  })
  tableData.push(totalRow)

  return { columns, data: tableData }
})

// ─────────────────────────────────────────────────────────────
// R 区间流转 - 回购率柱状图
// ─────────────────────────────────────────────────────────────
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
      formatter: (params: any[]) => {
        let html = `<div class="font-semibold mb-1">${params[0].name}</div>`
        params.forEach((p) => {
          html += `<div class="flex items-center gap-2 text-xs">
            <span class="w-2 h-2 rounded-full" style="background:${p.color}"></span>
            <span class="text-slate-500">${p.seriesName}:</span>
            <span class="font-medium text-slate-800">${(p.value * 100).toFixed(2)}%</span>
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
      },
      {
        name: `${data.comp_year_label}年`,
        type: 'bar',
        data: rows.map((r) => r.repurchase_rate_comp),
        itemStyle: { color: '#60a5fa', borderRadius: [3, 3, 0, 0] },
      },
      {
        name: `${data.prev2_year_label}年`,
        type: 'bar',
        data: rows.map((r) => r.repurchase_rate_prev2),
        itemStyle: { color: '#94a3b8', borderRadius: [3, 3, 0, 0] },
      },
    ],
  }
})

// ─────────────────────────────────────────────────────────────
// R 区间流转 - 表格
// ─────────────────────────────────────────────────────────────
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

const rFlowColumns = computed<DataTableColumns<RFMRFlowRow>>(() => {
  const yr = rFlowData.value?.year_label || String(new Date().getFullYear())
  const yr2 = rFlowData.value?.comp_year_label || String(new Date().getFullYear() - 1)

  return [
    {
      title: 'R 区间',
      key: 'r_segment',
      width: 160,
      fixed: 'left',
      align: 'center',
      render: (row) => {
        const meta = segmentMeta.value[row.r_segment] || { label: row.r_segment, range: '' }
        return h('div', { class: 'flex flex-col items-center justify-center leading-tight py-0.5' }, [
          h('div', { class: 'text-[13px] font-medium text-slate-800' }, meta.label),
          h('div', { class: 'text-[11px] text-slate-400 mt-0.5' }, meta.range),
        ])
      },
    },
    {
      title: `${yr}年`,
      key: 'current_year',
      align: 'center',
      children: [
        {
          title: '历史人群量级',
          key: 'hist_users_current',
          width: 110,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => row.hist_users_current.toLocaleString(),
        },
        {
          title: '回购人数',
          key: 'repurchase_users_current',
          width: 100,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => row.repurchase_users_current.toLocaleString(),
        },
        {
          title: '回购率',
          key: 'repurchase_rate_current',
          width: 90,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => `${(row.repurchase_rate_current * 100).toFixed(1)}%`,
        },
        {
          title: '回购金额',
          key: 'repurchase_gsv_current',
          width: 110,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => `¥${(row.repurchase_gsv_current / 10000).toFixed(1)}万`,
        },
        {
          title: '占比',
          key: 'repurchase_gsv_ratio_current',
          width: 80,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => `${(row.repurchase_gsv_ratio_current * 100).toFixed(1)}%`,
        },
      ],
    },
    {
      title: 'YOY',
      key: 'yoy',
      align: 'center',
      children: [
        {
          title: '历史人群',
          key: 'yoy_hist_users',
          width: 100,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => h(YOYGuard, { value: row.yoy_hist_users, styled: true}),
        },
        {
          title: '回购人数',
          key: 'yoy_repurchase_users',
          width: 100,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => h(YOYGuard, { value: row.yoy_repurchase_users, styled: true}),
        },
        {
          title: '回购率',
          key: 'yoy_repurchase_rate',
          width: 90,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => h(YOYGuard, { value: row.yoy_repurchase_rate, unit: 'pp', styled: true}),
        },
        {
          title: '回购金额',
          key: 'yoy_repurchase_gsv',
          width: 100,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => h(YOYGuard, { value: row.yoy_repurchase_gsv, styled: true}),
        },
        {
          title: '占比',
          key: 'yoy_repurchase_gsv_ratio_ppt',
          width: 90,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => h(YOYGuard, { value: row.yoy_repurchase_gsv_ratio_ppt, unit: 'pp', styled: true}),
        },
      ],
    },
    {
      title: `${yr2}年`,
      key: 'comp_year',
      align: 'center',
      children: [
        {
          title: '历史人群量级',
          key: 'hist_users_comp',
          width: 110,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => row.hist_users_comp.toLocaleString(),
        },
        {
          title: '回购人数',
          key: 'repurchase_users_comp',
          width: 100,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => row.repurchase_users_comp.toLocaleString(),
        },
        {
          title: '回购率',
          key: 'repurchase_rate_comp',
          width: 90,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => `${(row.repurchase_rate_comp * 100).toFixed(1)}%`,
        },
        {
          title: '回购金额',
          key: 'repurchase_gsv_comp',
          width: 110,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => `¥${(row.repurchase_gsv_comp / 10000).toFixed(1)}万`,
        },
        {
          title: '占比',
          key: 'repurchase_gsv_ratio_comp',
          width: 80,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => `${(row.repurchase_gsv_ratio_comp * 100).toFixed(1)}%`,
        },
      ],
    },
  ]
})
</script>

<template>
  <div class="space-y-5">
    <PageHeader title="RFM分析" subtitle="人群流转与象限变迁洞察" />

    <RfmVersionBanner />

    <RatioConventionBanner />

    <n-grid :cols="4" :x-gap="12" :y-gap="12" responsive="screen" :item-responsive="true">
      <n-gi :span="1">
        <MetricCard
          title="分析期用户总数"
          :value="matrixData ? matrixData.from_total.toLocaleString() : '—'"
          :loading="matrixLoading && activeTab === 'matrix'"
        />
      </n-gi>
      <n-gi :span="1">
        <MetricCard
          title="回购率(3年)"
          :value="repurchase3YData ? formatKPI(repurchase3YData.cur, 'percent') : '—'"
          :change="repurchase3YData?.yoy != null ? repurchase3YData.yoy : undefined"
          :loading="rFlowLoading && activeTab === 'r-flow'"
        />
      </n-gi>
      <n-gi :span="1">
        <MetricCard
          title="升级率"
          :value="matrixData ? formatKPI(matrixData.summary.upgrade_rate, 'percent') : '—'"
          :loading="matrixLoading && activeTab === 'matrix'"
        />
      </n-gi>
      <n-gi :span="1">
        <MetricCard
          title="降级率"
          :value="matrixData ? formatKPI(matrixData.summary.downgrade_rate, 'percent') : '—'"
          :loading="matrixLoading && activeTab === 'matrix'"
        />
      </n-gi>
    </n-grid>

    <div class="bi-card p-4">
      <n-tabs v-model:value="activeTab" type="line" animated>
        <n-tab-pane name="r-flow" tab="R 区间流转">
          <div class="pt-2 space-y-5">
            <!-- 人群分层 & 评分逻辑说明 -->
            <NAlert type="info" :show-icon="false" class="logic-explainer">
              <template #header>
                <div class="flex items-center justify-between w-full">
                  <span class="text-[13px] font-semibold text-slate-700">老客人分层逻辑 & 评分规则</span>
                  <NButton text size="tiny" @click="showLogicExplain = !showLogicExplain">
                    {{ showLogicExplain ? '收起' : '展开详情' }}
                  </NButton>
                </div>
              </template>
              <div v-if="showLogicExplain" class="mt-3 space-y-4 text-[12px] text-slate-600 leading-relaxed">
                <!-- 人群分层逻辑 -->
                <div>
                  <p class="font-semibold text-slate-700 mb-1.5">一、人群分层逻辑（R 区间）</p>
                  <p class="mb-1">基于用户最近一次购买距分析基准日的天数，将老客划分为 6 个 R 区间：</p>
                  <table class="w-full text-[11px] border border-slate-200 rounded">
                    <thead>
                      <tr class="bg-slate-50 text-slate-500">
                        <th class="text-left px-3 py-1.5 font-medium">区间名称</th>
                        <th class="text-left px-3 py-1.5 font-medium">时间范围</th>
                        <th class="text-left px-3 py-1.5 font-medium">含义</th>
                      </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-100">
                      <tr><td class="px-3 py-1.5 font-medium text-purple-600">近1个月已购客</td><td class="px-3 py-1.5">T-30 ~ T-1 天</td><td class="px-3 py-1.5">高度活跃，需持续激活</td></tr>
                      <tr><td class="px-3 py-1.5 font-medium text-purple-600">近2-3个月已购客</td><td class="px-3 py-1.5">T-90 ~ T-31 天</td><td class="px-3 py-1.5">中度活跃，回购窗口期</td></tr>
                      <tr><td class="px-3 py-1.5 font-medium text-purple-600">近4-6月已购客</td><td class="px-3 py-1.5">T-180 ~ T-91 天</td><td class="px-3 py-1.5">沉默用户，需重点唤醒</td></tr>
                      <tr><td class="px-3 py-1.5 font-medium text-purple-600">近7-12个月已购客</td><td class="px-3 py-1.5">T-365 ~ T-181 天</td><td class="px-3 py-1.5">半休眠状态，唤醒难度大</td></tr>
                      <tr><td class="px-3 py-1.5 font-medium text-purple-600">近13个月-近24个月已购客</td><td class="px-3 py-1.5">T-730 ~ T-366 天</td><td class="px-3 py-1.5">休眠用户，极难唤醒</td></tr>
                      <tr><td class="px-3 py-1.5 font-medium text-slate-500">2年外已购客</td><td class="px-3 py-1.5">&lt; T-730 天</td><td class="px-3 py-1.5">几乎流失，价值极低</td></tr>
                    </tbody>
                  </table>
                  <p class="mt-1.5 text-[11px] text-slate-400">T 为分析截止日期（dateRange 结束日）；新客（无历史购买）不计入 R 区间。</p>
                </div>
                <!-- 评分逻辑 -->
                <div>
                  <p class="font-semibold text-slate-700 mb-1.5">二、老客健康评分逻辑</p>
                  <p class="mb-1">健康评分基于 5 个维度综合计算，各维度独立评分后加权求和：</p>
                  <table class="w-full text-[11px] border border-slate-200 rounded">
                    <thead>
                      <tr class="bg-slate-50 text-slate-500">
                        <th class="text-left px-3 py-1.5 font-medium">维度</th>
                        <th class="text-left px-3 py-1.5 font-medium">含义</th>
                        <th class="text-left px-3 py-1.5 font-medium">目标值来源</th>
                        <th class="text-left px-3 py-1.5 font-medium">评分公式</th>
                      </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-100">
                      <tr><td class="px-3 py-1.5 font-medium text-purple-600">全店复购率</td><td class="px-3 py-1.5">分析期内有复购的老客占比</td><td class="px-3 py-1.5">去年同期实际值</td><td class="px-3 py-1.5">软封顶公式（见下方）</td></tr>
                      <tr><td class="px-3 py-1.5 font-medium text-purple-600">本品复购率</td><td class="px-3 py-1.5">复购同品类订单的老客占比</td><td class="px-3 py-1.5">去年同期实际值</td><td class="px-3 py-1.5">软封顶公式（见下方）</td></tr>
                      <tr><td class="px-3 py-1.5 font-medium text-purple-600">老客占比</td><td class="px-3 py-1.5">老客 GSV / 全店 GSV</td><td class="px-3 py-1.5">去年同期实际值</td><td class="px-3 py-1.5">软封顶公式（见下方）</td></tr>
                      <tr><td class="px-3 py-1.5 font-medium text-purple-600">老客 AUS</td><td class="px-3 py-1.5">老客平均客单价</td><td class="px-3 py-1.5">去年同期实际值</td><td class="px-3 py-1.5">软封顶公式（见下方）</td></tr>
                      <tr><td class="px-3 py-1.5 font-medium text-purple-600">周均复购人数</td><td class="px-3 py-1.5">周期内复购总人数 / 天数 × 7</td><td class="px-3 py-1.5">固定 300 人/周</td><td class="px-3 py-1.5">软封顶公式（见下方）</td></tr>
                    </tbody>
                  </table>
                  <div class="mt-2 p-2.5 bg-slate-50 border border-slate-200 rounded text-[11px]">
                    <p class="font-semibold text-slate-600 mb-1">软封顶公式（softCap）：</p>
                    <p>当 实际值 ≤ 目标值时，评分 = 实际值 / 目标值（线性，0~1）</p>
                    <p>当 实际值 &gt; 目标值时，评分 = 1 + 0.2 × ln(1 + 超出比例) / ln(4)</p>
                    <p class="mt-1 text-slate-400">超出目标最多可获得 0.2 的额外加分，上限约 1.2；目的是在追赶阶段给予更大动力。</p>
                  </div>
                </div>
                <!-- 回购率计算说明 -->
                <div>
                  <p class="font-semibold text-slate-700 mb-1.5">三、回购率计算规则</p>
                  <p>回购率 = 回购人数 / 历史人群量级（该 R 区间内的老客基数）</p>
                  <p>回购人数：在分析期内（T+1 一年内）有第 2 次购买的用户数</p>
                  <p class="mt-1 text-[11px] text-slate-400">回购金额占比 = 该区间回购 GSV / 全店回购 GSV，反映各区间对整体回购的贡献度。</p>
                </div>
              </div>
            </NAlert>

            <!-- 图表 -->
            <div>
              <h3 class="text-sm font-semibold text-slate-800 mb-0.5">回购率 3 年对比</h3>
              <p class="text-[11px] text-slate-500 mb-3">各 R 区间老客唤醒效率变化</p>
              <ErrorState v-if="rFlowError" :message="(rFlowError as Error).message" @retry="rFlowRefetch()" />
              <LoadingState v-else-if="rFlowLoading" />
              <EmptyState v-else-if="!rFlowData?.rows?.length" description="当前条件下无数据" />
              <EChartsWrapper v-else :option="repurchaseRateChartOption" height="260px" />
            </div>

            <!-- 表格：全店 -->
            <div>
              <h3 class="text-sm font-semibold text-slate-800 mb-0.5">R 区间流转详情</h3>
              <p class="text-[11px] text-slate-500 mb-3">老客分区回购表现 — 3 年同比</p>
              <ErrorState v-if="rFlowError" :message="(rFlowError as Error).message" @retry="rFlowRefetch()" />
              <LoadingState v-else-if="rFlowLoading" />
              <EmptyState v-else-if="!rFlowData?.rows?.length" description="当前条件下无数据" />
              <DataTablePro
                v-else
                :columns="rFlowColumns"
                :data="rFlowData.rows"
                :pagination="{ pageSize: 12 }"
                :scroll-x="1600"
              />
            </div>

            <!-- 表格：会员 -->
            <div>
              <h3 class="text-sm font-semibold text-slate-800 mb-0.5">R 区间流转详情 - 会员</h3>
              <p class="text-[11px] text-slate-500 mb-3">会员老客分区回购表现 — 3 年同比</p>
              <ErrorState v-if="rFlowError" :message="(rFlowError as Error).message" @retry="rFlowRefetch()" />
              <LoadingState v-else-if="rFlowLoading" />
              <EmptyState v-else-if="!rFlowData?.member_rows?.length" description="当前条件下无数据" />
              <DataTablePro
                v-else
                :columns="rFlowColumns"
                :data="rFlowData.member_rows"
                :pagination="{ pageSize: 12 }"
                :scroll-x="1600"
              />
            </div>

            <!-- 表格：本渠道回购本渠道 -->
            <div v-if="filterStore.channel !== '全店' && !rFlowLoading && rFlowData?.same_channel_rows?.length">
              <h3 class="text-sm font-semibold text-slate-800 mb-0.5">R 区间流转详情 - 本渠道</h3>
              <p class="text-[11px] text-slate-500 mb-3">本渠道老客在本渠道回购表现 — 3 年同比</p>
              <DataTablePro
                :columns="rFlowColumns"
                :data="rFlowData.same_channel_rows"
                :pagination="{ pageSize: 12 }"
                :scroll-x="1600"
              />
            </div>

            <!-- 表格：会员本渠道 -->
            <div v-if="filterStore.channel !== '全店' && !rFlowLoading && rFlowData?.member_same_channel_rows?.length">
              <h3 class="text-sm font-semibold text-slate-800 mb-0.5">R 区间流转详情 - 会员本渠道</h3>
              <p class="text-[11px] text-slate-500 mb-3">会员本渠道老客在本渠道回购表现 — 3 年同比</p>
              <DataTablePro
                :columns="rFlowColumns"
                :data="rFlowData.member_same_channel_rows"
                :pagination="{ pageSize: 12 }"
                :scroll-x="1600"
              />
            </div>
          </div>
        </n-tab-pane>

        <n-tab-pane name="matrix" tab="流转矩阵">
          <div class="pt-2">
            <h3 class="text-sm font-semibold text-slate-800 mb-0.5">人群流转矩阵</h3>
            <p class="text-[11px] text-slate-500 mb-3">行 = 起始象限，列 = 结束象限，颜色深浅表示流转人数</p>
            <ErrorState v-if="matrixError" :message="(matrixError as Error).message" @retry="matrixRefetch()" />
            <LoadingState v-else-if="matrixLoading" />
            <EmptyState v-else-if="!matrixData" description="当前条件下无数据" />
            <DataTablePro
              v-else
              :columns="matrixTable.columns"
              :data="matrixTable.data"
              :pagination="false"
              :scroll-x="900"
            />
          </div>
        </n-tab-pane>

        <n-tab-pane name="sankey" tab="桑基图">
          <div class="pt-2">
            <h3 class="text-sm font-semibold text-slate-800 mb-0.5">人群流转桑基图</h3>
            <p class="text-[11px] text-slate-500 mb-3">可视化人群在不同象限间的流动路径</p>
            <ErrorState v-if="sankeyError" :message="(sankeyError as Error).message" @retry="sankeyRefetch()" />
            <LoadingState v-else-if="sankeyLoading" />
            <EmptyState v-else-if="!sankeyData" description="当前条件下无数据" />
            <EChartsWrapper v-else :option="sankeyOption" height="440px" />
          </div>
        </n-tab-pane>
      </n-tabs>
    </div>
  </div>
</template>

<style scoped>
.logic-explainer {
  border-radius: 8px;
  font-size: 13px;
}
.logic-explainer :deep(.n-alert-header) {
  padding-bottom: 0;
}
.logic-explainer :deep(.n-alert-body) {
  padding-top: 8px;
}
</style>
