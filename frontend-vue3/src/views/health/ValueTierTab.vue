<script setup lang="ts">
import { computed, toValue, h, ref, onMounted, onUnmounted } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import type { DataTableColumns } from 'naive-ui'
import { NAlert, NButton } from 'naive-ui'
import { useFilterStore } from '@/stores/filterStore'
import {
  fetchRFMAnalysis,
  fetchRFMConfig,
  isSingleUserModeError,
  releaseSessionLock,
  type RFMAnalysisRow,
  type RFMAnalysisResponse,
  type SingleUserModeError,
  type SegmentDefinitionItem,
} from '@/api/health'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import RFMSegmentDrilldown from './RFMSegmentDrilldown.vue'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import DataTablePro from '@/components/DataTablePro.vue'
import YOYGuard from '@/components/YOYGuard.vue'
import ExportToolbar from '@/components/ExportToolbar.vue'
import { BRAND_PRIMARY } from '@/composables/useChartTheme'
import type { XlsxColumn } from '@/utils/exportXlsx'
import type { EChartTooltipParam } from '@/types/echarts'

const filterStore = useFilterStore()
const showLogicExplain = ref(false)
import { LOW_PRICE_CHANNELS } from '@/constants/channels'
const rfmChartRef = ref<InstanceType<typeof EChartsWrapper> | null>(null)
const selectedSegment = ref<string | null>(null)
const singleUserBlocked = ref(false)
const singleUserMessage = ref('')
let singleUserPingTimer: number | null = null

const drilldownQueryParams = computed(() => ({
  start_date: filterStore.dateRange[0],
  end_date: filterStore.dateRange[1],
  channel: filterStore.channel === '全店' ? undefined : filterStore.channel,
  ...compareQueryParams.value,
}))

function onRFMChartClick(params: any) {
  const rows = (rfmData.value?.rows ?? []).filter((r) => r.rfm_segment !== '已购客TTL')
  // ECharts 内置 click 事件：点击了柱体（params.name = 柱体名称）
  if (params.name) {
    selectedSegment.value = params.name
    return
  }
  // 原生 click 事件（params.name 为空）：用 convertFromPixel 换算最近柱体
  // 点击柱子上方空白区域也能选中对应柱子
  if (params.event?.offsetX != null) {
    const instance = rfmChartRef.value?.getChartInstance?.()
    if (instance) {
      const converted = instance.convertFromPixel({ xAxisIndex: 0 }, params.event.offsetX)
      if (converted !== null && converted !== undefined) {
        const idx = Math.round(converted)
        if (idx >= 0 && idx < rows.length) {
          selectedSegment.value = rows[idx].rfm_segment
          return
        }
      }
    }
  }
  // 真正的空白区域（图表外或无数据区域）→ 关闭下钻
  selectedSegment.value = null
}

// 暴露到 window，供 tooltip onclick 调用
onMounted(() => {
  ;(window as any).__rFMDrilldownClick = onRFMChartClick
})

onUnmounted(() => {
  stopSingleUserPing()
  void releaseSessionLock().catch(() => {})
})

const rfmQueryParams = computed(() => ({
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

const rfmQueryKey = computed(() => ['rfm-analysis', { ...toValue(rfmQueryParams) }, toValue(compareQueryParams)])

function startSingleUserPing() {
  if (singleUserPingTimer) return
  singleUserPingTimer = window.setInterval(() => {
    void rfmRefetch()
  }, 30_000)
}

function stopSingleUserPing() {
  if (!singleUserPingTimer) return
  window.clearInterval(singleUserPingTimer)
  singleUserPingTimer = null
}

async function fetchRFMAnalysisWithSingleUserGuard(): Promise<RFMAnalysisResponse | null> {
  try {
    const data = await fetchRFMAnalysis({ ...toValue(rfmQueryParams), ...toValue(compareQueryParams) })
    singleUserBlocked.value = false
    singleUserMessage.value = ''
    stopSingleUserPing()
    return data
  } catch (error) {
    if (isSingleUserModeError(error)) {
      const err = error as SingleUserModeError
      singleUserBlocked.value = true
      singleUserMessage.value = `${err.message} 系统会每 30 秒自动重试。`
      startSingleUserPing()
      return null
    }
    throw error
  }
}

const { data: rfmData, isLoading: rfmLoading, error: rfmError, refetch: rfmRefetch } = useQuery({
  queryKey: rfmQueryKey,
  queryFn: fetchRFMAnalysisWithSingleUserGuard,
  staleTime: 60_000,
  retry: false,
})

// ── RFM 阈值配置（前后端同步唯一数据源） ──
const { data: rfmConfig } = useQuery({
  queryKey: ['rfm-config'],
  queryFn: fetchRFMConfig,
  staleTime: 300_000,
})

// ── Hover 联动高亮状态 ──
const hoveredDim = ref<'r' | 'f' | 'm' | null>(null)
const hoveredSegmentId = ref<number | null>(null)

function onDimEnter(dim: 'r' | 'f' | 'm') {
  hoveredDim.value = dim
}
function onDimLeave() {
  hoveredDim.value = null
}
function onSegmentEnter(segmentId: number) {
  hoveredSegmentId.value = segmentId
}
function onSegmentLeave() {
  hoveredSegmentId.value = null
}

// ── 阈值格式化（人类可读） ──
function formatThreshold(dim: 'r' | 'f' | 'm', thresholds: number[]): string[] {
  if (dim === 'r') {
    return [
      `< ${thresholds[0]} 天`,
      `${thresholds[0]} ≤ 天 < ${thresholds[1]}`,
      `${thresholds[1]} ≤ 天 < ${thresholds[2]}`,
      `${thresholds[2]} ≤ 天 < ${thresholds[3]}`,
      `${thresholds[3]} 天以上`,
    ]
  }
  if (dim === 'f') {
    return [
      `≤ ${thresholds[0]} 次`,
      `${thresholds[1]} 次`,
      `${thresholds[2]} 次`,
      `${thresholds[3]} 次`,
      `≥ ${thresholds[3] + 1} 次`,
    ]
  }
  // m
  return [
    `< ¥${thresholds[0]}`,
    `¥${thresholds[0]} - ${thresholds[1] - 1}`,
    `¥${thresholds[1]} - ${thresholds[2] - 1}`,
    `¥${thresholds[2]} - ${thresholds[3] - 1}`,
    `≥ ¥${thresholds[3]}`,
  ]
}

// ── 象限颜色映射（从 API 动态获取） ──
const rfmColorMap = computed<Record<string, string>>(() => {
  const map: Record<string, string> = {}
  rfmConfig.value?.segments?.forEach((s) => {
    map[s.name_cn] = s.color
  })
  return map
})

function getRFMColor(segment: string): string {
  return rfmColorMap.value[segment] || '#94a3b8'
}

// ── 象限行是否应被高亮（根据 hover 的维度） ──
function isSegmentHighlighted(seg: SegmentDefinitionItem): boolean {
  if (!hoveredDim.value) return false
  if (hoveredDim.value === 'r') return seg.r_high
  if (hoveredDim.value === 'f') return seg.f_high
  if (hoveredDim.value === 'm') return seg.m_high
  return false
}

// ── 评分规则行是否应被高亮（根据 hover 的象限） ──
function isDimHighlighted(dim: 'r' | 'f' | 'm', seg: SegmentDefinitionItem | null): boolean {
  if (!seg) return false
  if (dim === 'r') return seg.r_high
  if (dim === 'f') return seg.f_high
  if (dim === 'm') return seg.m_high
  return false
}

// ── 回购率格式化（防御 null/undefined：缓存 / 老数据 / 中间态可能不含 prev2 字段） ──
function formatRate(v: number | null | undefined): string {
  return `${((v ?? 0) * 100).toFixed(2)}%`
}

// ── 回购率柱状图 ──
const repurchaseRateChartOption = computed(() => {
  if (!rfmData.value) return {}
  const data = rfmData.value as RFMAnalysisResponse
  const rows = data.rows.filter((r) => r.rfm_segment !== '已购客TTL')
  const segments = rows.map((r) => r.rfm_segment)

  return {
    // 显式设置色板顺序，确保图例颜色与 series 一致（覆盖 baseTheme.color）
    color: [BRAND_PRIMARY, '#60a5fa', '#94a3b8'],
    tooltip: {
      trigger: 'axis',
      enterable: true,
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      textStyle: { color: '#0f172a', fontSize: 12 },
      extraCssText: 'box-shadow: 0 4px 12px -2px rgba(0,0,0,0.08); border-radius: 4px;',
      formatter: (params: EChartTooltipParam[]) => {
        const segName = params[0].name
        // 显式颜色序列，不依赖 p.color（baseTheme.color 会干扰）
        const EXPLICIT_COLORS = [BRAND_PRIMARY, '#60a5fa', '#94a3b8']
        let html = `<div style="cursor:pointer;color:#533afd;font-weight:600;margin-bottom:4px" onclick="window.__rFMDrilldownClick({componentType:'series',seriesType:'bar',name:'${segName}'})">${segName} — 点击查看品类拆解</div>`
        params.forEach((p, idx) => {
          const color = EXPLICIT_COLORS[idx] ?? p.color
          const pct = (Number(p.value) * 100).toFixed(1)
          html += `<div style="display:flex;align-items:center;gap:6px;margin:2px 0">
            <span style="width:8px;height:8px;border-radius:50%;background:${color};flex-shrink:0"></span>
            <span style="color:#64748b;font-size:12px">${p.seriesName}:</span>
            <span style="color:#1e293b;font-size:12px;font-weight:500">${pct}%</span>
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
    grid: { left: 12, right: 12, top: 40, bottom: 32 },
    xAxis: {
      type: 'category',
      data: segments,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 10, interval: 0, rotate: 30 },
    },
    yAxis: {
      type: 'value',
      name: '回购率',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 11, formatter: (v: number) => `${(v * 100).toFixed(0)}%` },
      splitLine: { lineStyle: { color: '#e2e8f0', type: [4, 4] } },
    },
    series: [
      { name: `${data.year_label}年`, type: 'bar', data: rows.map((r) => r.repurchase_rate_current), itemStyle: { color: BRAND_PRIMARY, borderRadius: [3, 3, 0, 0] }, barGap: '20%', cursor: 'pointer', emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(37,99,235,0.3)' } }, label: { show: true, position: 'top', formatter: (p: EChartTooltipParam) => `${(Number(p.value) * 100).toFixed(1)}%`, fontSize: 9, color: BRAND_PRIMARY } },
      { name: `${data.comp_year_label}年`, type: 'bar', data: rows.map((r) => r.repurchase_rate_comp), itemStyle: { color: '#60a5fa', borderRadius: [3, 3, 0, 0] }, cursor: 'pointer', emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(96,165,250,0.3)' } }, label: { show: true, position: 'top', formatter: (p: EChartTooltipParam) => `${(Number(p.value) * 100).toFixed(1)}%`, fontSize: 9, color: '#60a5fa' } },
      { name: `${data.prev2_year_label}年`, type: 'bar', data: rows.map((r) => r.repurchase_rate_prev2), itemStyle: { color: '#94a3b8', borderRadius: [3, 3, 0, 0] }, cursor: 'pointer', emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(148,163,184,0.3)' } }, label: { show: true, position: 'top', formatter: (p: EChartTooltipParam) => `${(Number(p.value) * 100).toFixed(1)}%`, fontSize: 9, color: '#94a3b8' } },
    ],
  }
})



// ── 表格列定义 ──
const rfmColumns = computed<DataTableColumns<RFMAnalysisRow>>(() => {
  const yr = rfmData.value?.year_label || String(new Date().getFullYear())
  const yr2 = rfmData.value?.comp_year_label || String(new Date().getFullYear() - 1)
  const yr3 = rfmData.value?.prev2_year_label || String(new Date().getFullYear() - 2)

  return [
    {
      title: '人群分层',
      key: 'rfm_segment',
      width: 120,
      fixed: 'left',
      align: 'center',
      render: (row: RFMAnalysisRow) => {
        const color = getRFMColor(row.rfm_segment)
        return h('div', { class: 'flex items-center justify-center gap-1.5 py-0.5' }, [
          h('span', { class: 'w-2.5 h-2.5 rounded-full', style: `background:${color}` }),
          h('span', { class: 'text-[13px] font-medium text-slate-800' }, row.rfm_segment),
        ])
      },
    },
    { title: `${yr}历史人数`, key: 'hist_users_current', width: 90, align: 'right', render: (r) => r.hist_users_current.toLocaleString() },
    { title: `${yr}回购人数`, key: 'repurchase_users_current', width: 90, align: 'right', render: (r) => r.repurchase_users_current.toLocaleString() },
    { title: `${yr}回购率`, key: 'repurchase_rate_current', width: 80, align: 'right', render: (r) => h('span', { class: 'font-medium text-slate-800' }, formatRate(r.repurchase_rate_current)) },
    { title: `${yr}回购GSV`, key: 'repurchase_gsv_current', width: 90, align: 'right', render: (r) => r.repurchase_gsv_current >= 10000 ? `${(r.repurchase_gsv_current / 10000).toFixed(1)}万` : r.repurchase_gsv_current.toLocaleString() },
    { title: `${yr}回购GSV占比`, key: 'repurchase_gsv_ratio_current', width: 90, align: 'right', render: (r) => `${(r.repurchase_gsv_ratio_current * 100).toFixed(2)}%` },
    { title: `${yr}年同比历史人数`, key: 'yoy_hist_users', width: 110, align: 'center', render: (r: RFMAnalysisRow) => h(YOYGuard, { value: r.yoy_hist_users, styled: true}) },
    { title: `${yr}年同比人数`, key: 'yoy_repurchase_users', width: 110, align: 'center', render: (r: RFMAnalysisRow) => h(YOYGuard, { value: r.yoy_repurchase_users, styled: true}) },
    { title: `${yr}同比回购率`, key: 'yoy_repurchase_rate', width: 110, align: 'center', render: (r: RFMAnalysisRow) => h(YOYGuard, { value: r.yoy_repurchase_rate, unit: 'pp', styled: true}) },
    { title: `${yr}同比回购GSV`, key: 'yoy_repurchase_gsv', width: 110, align: 'center', render: (r: RFMAnalysisRow) => h(YOYGuard, { value: r.yoy_repurchase_gsv, styled: true}) },
    { title: `${yr}同比回购GSV占比`, key: 'yoy_repurchase_gsv_ratio_ppt', width: 110, align: 'center', render: (r: RFMAnalysisRow) => h(YOYGuard, { value: r.yoy_repurchase_gsv_ratio_ppt, unit: 'pp', styled: true}) },
    { title: `${yr2}历史人数`, key: 'hist_users_comp', width: 90, align: 'right', render: (r) => r.hist_users_comp.toLocaleString() },
    { title: `${yr2}回购率`, key: 'repurchase_rate_comp', width: 80, align: 'right', render: (r) => formatRate(r.repurchase_rate_comp) },
    { title: `${yr3}历史人数`, key: 'hist_users_prev2', width: 90, align: 'right', render: (r) => r.hist_users_prev2.toLocaleString() },
    { title: `${yr3}回购率`, key: 'repurchase_rate_prev2', width: 80, align: 'right', render: (r) => formatRate(r.repurchase_rate_prev2) },
  ]
})

// ── RFM Excel 导出列定义 ──
const rfmXlsxColumns = computed<XlsxColumn[]>(() => {
  const yr = rfmData.value?.year_label || String(new Date().getFullYear())
  const yr2 = rfmData.value?.comp_year_label || String(new Date().getFullYear() - 1)
  const yr3 = rfmData.value?.prev2_year_label || String(new Date().getFullYear() - 2)
  return [
    { header: '人群分层', key: 'rfm_segment', width: 14 },
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
</script>

<template>
  <div class="rfm-analysis-tab">
    <div v-if="singleUserBlocked" class="single-user-mask" role="status" aria-live="polite">
      <div class="single-user-mask-panel">
        <div>
          <h3>当前板块被占用</h3>
          <p>{{ singleUserMessage }}</p>
        </div>
        <NButton size="small" type="primary" ghost @click="rfmRefetch()">重试</NButton>
      </div>
    </div>

    <!-- 人群分层 & 评分逻辑说明 -->
    <NAlert type="info" :show-icon="false" class="logic-explainer mb-4">
      <template #header>
        <div class="flex items-center justify-between w-full">
          <span style="font-size: 13px; font-weight: 600; color: #334155;">RFM 人群分层逻辑 & 评分规则</span>
          <NButton text size="tiny" @click="showLogicExplain = !showLogicExplain">
            {{ showLogicExplain ? '收起' : '展开详情' }}
          </NButton>
        </div>
      </template>
      <div v-if="showLogicExplain" style="margin-top: 12px; font-size: 14px; color: #475569; line-height: 1.8;">
        <!-- RFM 分层逻辑 -->
        <div style="margin-bottom: 20px;">
          <p style="font-weight: 600; color: #334155; margin-bottom: 8px; font-size: 15px;">一、RFM 人群分层逻辑（8 象限）</p>
          <p style="margin-bottom: 8px;">基于 RFM 模型将用户按 R（最近购买时间）、F（购买频次）、M（消费金额）划分为 8 个象限：</p>
          <table style="width: 100%; font-size: 12px; border: 1px solid #e2e8f0; border-radius: 8px; border-collapse: collapse;">
            <thead>
              <tr style="background-color: #f8fafc; color: #64748b;">
                <th style="text-align: left; padding: 8px 14px; font-weight: 600;">象限名称</th>
                <th style="text-align: left; padding: 8px 14px; font-weight: 600;">R（活跃度）</th>
                <th style="text-align: left; padding: 8px 14px; font-weight: 600;">F（频次）</th>
                <th style="text-align: left; padding: 8px 14px; font-weight: 600;">M（金额）</th>
                <th style="text-align: left; padding: 8px 14px; font-weight: 600;">运营策略</th>
              </tr>
            </thead>
            <tbody style="border-top: 1px solid #f1f5f9;">
              <tr
                v-for="(seg, idx) in rfmConfig?.segments"
                :key="seg.segment_id"
                :class="{ 'rfm-highlight-row': isSegmentHighlighted(seg) || hoveredSegmentId === seg.segment_id }"
                :style="idx % 2 === 1 ? 'background-color: #fafafa;' : ''"
                @mouseenter="onSegmentEnter(seg.segment_id)"
                @mouseleave="onSegmentLeave"
              >
                <td style="padding: 8px 14px; font-weight: 600;" :style="`color: ${seg.color}`">{{ seg.name_cn }}</td>
                <td style="padding: 8px 14px;">{{ seg.r_high ? '高（近期购买）' : '低（较远）' }}</td>
                <td style="padding: 8px 14px;">{{ seg.f_high ? '高（多次）' : '低（少次）' }}</td>
                <td style="padding: 8px 14px;">{{ seg.m_high ? '高' : '低' }}</td>
                <td style="padding: 8px 14px;">{{ seg.description }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <!-- 回购率计算规则 -->
        <div style="margin-bottom: 20px;">
          <p style="font-weight: 600; color: #334155; margin-bottom: 8px; font-size: 15px;">二、回购率计算规则</p>
          <p style="margin-bottom: 4px;">回购率 = 分析期内复购人数 / 该象限历史人群基数</p>
          <p style="margin-bottom: 4px;">历史人群：截至分析基准日（dateRange 结束日）在该 RFM 象限中有购买记录的用户</p>
          <p>复购人数：在分析期（dateRange 范围内）发生第 2 次及以上有效购买的用户</p>
          <p style="margin-top: 6px; font-size: 13px; color: #94a3b8;">有效订单：剔除购物金及退款订单 | 回购 GSV 占比 = 该象限回购 GSV / 全店回购 GSV</p>
        </div>
        <!-- 3 年对比说明 -->
        <div style="margin-bottom: 20px;">
          <p style="font-weight: 600; color: #334155; margin-bottom: 8px; font-size: 15px;">三、3 年对比口径</p>
          <p style="margin-bottom: 4px;">当前年：按 dateRange 实际日期范围计算</p>
          <p style="margin-bottom: 4px;">去年同期：dateRange 整体向前平移 1 年（例如 2026/04/01-04/18 → 2025/04/01-04/18）</p>
          <p style="margin-bottom: 4px;">前年同期：dateRange 整体向前平移 2 年（例如 2026/04/01-04/18 → 2024/04/01-04/18）</p>
          <p style="margin-top: 6px; font-size: 13px; color: #94a3b8;">YOY 变化：百分比变化（人数/金额）或百分点差（比率/占比）</p>
        </div>
        <!-- RFM 评分标准 -->
        <div>
          <p style="font-weight: 600; color: #334155; margin-bottom: 8px; font-size: 15px;">四、RFM 评分标准（1-5 分）</p>
          <p style="margin-bottom: 8px;">R/F/M 各维度按固定阈值划分为 1-5 分，组合形成 8 个象限人群：</p>
          <table style="width: 100%; font-size: 12px; border: 1px solid #e2e8f0; border-radius: 8px; border-collapse: collapse; margin-bottom: 10px;">
            <thead>
              <tr style="background-color: #f8fafc; color: #64748b;">
                <th style="text-align: left; padding: 8px 12px; font-weight: 600;">维度</th>
                <th style="text-align: left; padding: 8px 12px; font-weight: 600;">5 分</th>
                <th style="text-align: left; padding: 8px 12px; font-weight: 600;">4 分</th>
                <th style="text-align: left; padding: 8px 12px; font-weight: 600;">3 分</th>
                <th style="text-align: left; padding: 8px 12px; font-weight: 600;">2 分</th>
                <th style="text-align: left; padding: 8px 12px; font-weight: 600;">1 分</th>
              </tr>
            </thead>
            <tbody style="border-top: 1px solid #f1f5f9;">
              <tr
                v-for="dim in (['r', 'f', 'm'] as const)"
                :key="dim"
                :class="{ 'rfm-highlight-row': isDimHighlighted(dim, rfmConfig?.segments?.find(s => s.segment_id === hoveredSegmentId) || null) }"
                :style="dim === 'f' ? 'background-color: #fafafa;' : ''"
                @mouseenter="onDimEnter(dim)"
                @mouseleave="onDimLeave"
              >
                <td style="padding: 8px 12px; font-weight: 600; color: #7c3aed;">
                  {{ dim === 'r' ? 'R 最近购买' : dim === 'f' ? 'F 购买频次' : 'M 累计金额' }}
                </td>
                <td
                  v-for="score in [0, 1, 2, 3, 4]"
                  :key="score"
                  style="padding: 8px 12px;"
                >
                  {{ formatThreshold(dim, rfmConfig?.thresholds?.[dim] || [])[score] || '—' }}
                </td>
              </tr>
            </tbody>
          </table>
          <p style="font-size: 13px; color: #94a3b8; margin-bottom: 4px;">★ 象限划分：R×F×M 各维度评分组合，划分为「重要价值 / 重要保持 / 重要发展 / 重要挽留 / 一般价值 / 一般保持 / 一般发展 / 一般挽留」8 类</p>
          <p style="font-size: 13px; color: #94a3b8;">★ 回购率分母：截至 dateRange 结束日仍处于该象限的历史用户（cutoff = T1-1 天）</p>
        </div>
      </div>
    </NAlert>

    <!-- 图表 -->
    <div class="bi-card p-4 mb-4">
      <div class="flex items-center justify-between mb-0.5">
        <div>
          <h3 class="text-sm font-semibold text-slate-800">回购率 3 年对比</h3>
          <p class="text-[11px] text-slate-500">RFM 8象限人群老客唤醒效率变化</p>
          <p class="text-[11px]" style="color: #7c3aed; font-size: 11px;">点击柱状图，可下钻品类拆解</p>
        </div>
        <ExportToolbar
          :filename="`老客分析_RFM回购率对比_${filterStore.dateRange[0]}_${filterStore.dateRange[1]}`"
          :chart-ref="rfmChartRef"
        />
      </div>
      <ErrorState v-if="rfmError && !singleUserBlocked" :message="(rfmError as Error).message" @retry="rfmRefetch()" />
      <LoadingState v-else-if="rfmLoading" />
      <EmptyState v-else-if="!rfmData?.rows?.length" description="当前条件下无数据" />
      <EChartsWrapper v-else ref="rfmChartRef" :option="repurchaseRateChartOption" height="300px" @chart-click="onRFMChartClick" />
    </div>

    <Transition name="slide-fade">
      <RFMSegmentDrilldown
        v-if="selectedSegment"
        :key="selectedSegment"
        :rfm-segment="selectedSegment"
        :query-params="drilldownQueryParams"
        @close="selectedSegment = null"
      />
    </Transition>

    <!-- 表格：全店 -->
    <div class="bi-card p-4 mb-4">
      <div class="flex items-center justify-between mb-0.5">
        <div>
          <h3 class="text-sm font-semibold text-slate-800">RFM 人群流转详情</h3>
          <p class="text-[11px] text-slate-500">8象限人群回购表现 — 3 年同比</p>
        </div>
        <ExportToolbar
          :filename="`老客分析_RFM全店_${filterStore.dateRange[0]}_${filterStore.dateRange[1]}`"
          :columns="rfmXlsxColumns"
          :data="rfmData?.rows ?? []"
          sheet-name="RFM全店"
        />
      </div>
      <ErrorState v-if="rfmError && !singleUserBlocked" :message="(rfmError as Error).message" @retry="rfmRefetch()" />
      <LoadingState v-else-if="rfmLoading" />
      <EmptyState v-else-if="!rfmData?.rows?.length" description="当前条件下无数据" />
      <DataTablePro
        v-else
        :columns="rfmColumns"
        :data="rfmData.rows"
        :pagination="{ pageSize: 9 }"
        :scroll-x="2100"
      />
    </div>

    <!-- 表格：会员 -->
    <div class="bi-card p-4 mb-4">
      <div class="flex items-center justify-between mb-0.5">
        <div>
          <h3 class="text-sm font-semibold text-slate-800">RFM 人群流转详情 — 会员</h3>
          <p class="text-[11px] text-slate-500">会员8象限人群回购表现 — 3 年同比</p>
        </div>
        <ExportToolbar
          :filename="`老客分析_RFM会员_${filterStore.dateRange[0]}_${filterStore.dateRange[1]}`"
          :columns="rfmXlsxColumns"
          :data="rfmData?.member_rows ?? []"
          sheet-name="RFM会员"
        />
      </div>
      <ErrorState v-if="rfmError && !singleUserBlocked" :message="(rfmError as Error).message" @retry="rfmRefetch()" />
      <LoadingState v-else-if="rfmLoading" />
      <EmptyState v-else-if="!rfmData?.member_rows?.length" description="当前条件下无数据" />
      <DataTablePro
        v-else
        :columns="rfmColumns"
        :data="rfmData.member_rows"
        :pagination="{ pageSize: 9 }"
        :scroll-x="2100"
      />
    </div>

    <!-- 表格：本渠道（仅当选择了渠道时显示） -->
    <template v-if="filterStore.channel !== '全店' && !rfmLoading && rfmData?.same_channel_rows?.length">
      <div class="bi-card p-4 mb-4">
        <h3 class="text-sm font-semibold text-slate-800 mb-0.5">RFM 人群流转详情 — 本渠道</h3>
        <p class="text-[11px] text-slate-500 mb-3">本渠道老客在本渠道回购表现 — 3 年同比</p>
        <DataTablePro
          :columns="rfmColumns"
          :data="rfmData.same_channel_rows"
          :pagination="{ pageSize: 9 }"
          :scroll-x="2100"
        />
      </div>
      <div class="bi-card p-4 mb-4">
        <h3 class="text-sm font-semibold text-slate-800 mb-0.5">RFM 人群流转详情 — 会员本渠道</h3>
        <p class="text-[11px] text-slate-500 mb-3">会员本渠道老客在本渠道回购表现 — 3 年同比</p>
        <DataTablePro
          :columns="rfmColumns"
          :data="rfmData.member_same_channel_rows"
          :pagination="{ pageSize: 9 }"
          :scroll-x="2100"
        />
      </div>
    </template>
  </div>
</template>

<style scoped>
.rfm-analysis-tab {
  padding-top: 8px;
  position: relative;
}
.rfm-highlight-row {
  background-color: #eff6ff !important;
  transition: background-color 0.15s ease;
}
.single-user-mask {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(248, 250, 252, 0.82);
  backdrop-filter: blur(5px);
}
.single-user-mask-panel {
  width: min(420px, 100%);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 20px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 16px 44px rgba(15, 23, 42, 0.14);
}
.single-user-mask-panel h3 {
  margin: 0 0 6px;
  font-size: 15px;
  font-weight: 650;
  color: #0f172a;
}
.single-user-mask-panel p {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  color: #475569;
}
@media (max-width: 640px) {
  .single-user-mask-panel {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
