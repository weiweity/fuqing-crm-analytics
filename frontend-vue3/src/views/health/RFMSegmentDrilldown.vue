<template>
  <div class="drilldown-card">
    <div class="drilldown-header">
      <div class="header-left">
        <span class="segment-badge">{{ props.rfmSegment }}</span>
        <span class="header-title">— 品类回购拆解</span>
      </div>
      <n-button quaternary circle size="small" @click="emit('close')">
        <template #icon><Close /></template>
      </n-button>
    </div>

    <div v-if="loading" class="loading-wrap">
      <n-spin size="small" />
    </div>

    <template v-else-if="data">
      <div class="driver-row">
        <div class="driver-card kpi-card">
          <div class="driver-name">象限用户数</div>
          <div class="driver-rate kpi-rate">{{ data.summary.segment_user_count?.toLocaleString() ?? '-' }}</div>
        </div>
        <div class="driver-card kpi-card">
          <div class="driver-name">整体回购率</div>
          <div class="driver-rate kpi-rate">{{ fmtPct(data.summary.overall_repurchase_rate) }}</div>
        </div>
        <div class="driver-card kpi-card">
          <div class="driver-name">同比变化</div>
          <div class="driver-rate kpi-rate" :class="yoyClass(data.summary.overall_repurchase_rate_yoy)">
            {{ fmtYoY(data.summary.overall_repurchase_rate_yoy) }}
          </div>
        </div>
      </div>
      <div class="kpi-hint">口径：当期有复购行为的去重用户数 ÷ 象限总用户数（不限品类，与柱状图一致）</div>

      <div v-if="data.summary.top_drivers?.length" class="driver-row">
        <div
          v-for="d in data.summary.top_drivers"
          :key="d.category_name"
          class="driver-card"
          :class="(d.yoy_repurchase_rate ?? 0) >= 0 ? 'up' : 'down'"
        >
          <div class="driver-name">{{ d.category_name }}</div>
          <div class="driver-rate">同品类复购率：{{ fmtPct(d.repurchase_rate_current) }}</div>
          <div class="driver-yoy">{{ fmtYoY(d.yoy_repurchase_rate) }}</div>
          <div class="driver-base">{{ d.hist_users_current?.toLocaleString() }} 基数</div>
        </div>
      </div>

      <div class="chart-wrap" style="cursor: pointer">
        <EChartsWrapper ref="chartRef" :option="chartOption" style="height: 240px" @chart-click="onChartClick" />
        <div v-if="selectedCategory" class="selected-hint">当前选中：{{ selectedCategory }}</div>
      </div>

      <div class="table-wrap">
        <div class="table-scroll-wrap">
          <DataTablePro :columns="tableColumns" :data="displayRows" :pagination="false" :scroll-x="780" />
        </div>
        <div class="table-hint">口径说明：历史人数 = 历史买过该品类的人；同品类复购 = 买过A又买了A；同一用户买过多品类会重复计入</div>
      </div>

      <div v-if="memberRows.length > 0" class="member-wrap">
        <div class="member-header">
          <span class="member-title">会员品类明细</span>
          <span class="member-hint">鼠标滚动查看</span>
        </div>
        <DataTablePro
          :columns="tableColumns"
          :data="memberRows"
          :pagination="false"
          :scroll-x="780"
          :max-height="300"
        />
      </div>

    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, h, markRaw } from 'vue'
import { NButton, NSpin } from 'naive-ui'
import { Close } from '@vicons/ionicons5'
import EChartsWrapper from '@/components/EChartsWrapper.vue'

// 用于空白区域点击：获取 ECharts 实例进行坐标转换
const chartRef = ref<InstanceType<typeof EChartsWrapper> | null>(null)
import DataTablePro from '@/components/DataTablePro.vue'
import { fetchRFMCategoryDrilldown, type RFMCategoryDrilldownResponse } from '@/api/health'
import { useFilterStore } from '@/stores/filterStore'
import { LOW_PRICE_CHANNELS } from '@/constants/channels'
import { BRAND_PRIMARY } from '@/composables/useChartTheme'
import type { EChartsOption } from 'echarts'

const props = defineProps<{
  rfmSegment: string
  queryParams: {
    start_date: string
    end_date: string
    channel?: string
    exclude_channels?: string[]
    compare_start_date?: string
    compare_end_date?: string
  }
}>()
const emit = defineEmits<{ close: [] }>()

const filterStore = useFilterStore()
const loading = ref(false)
const data = ref<RFMCategoryDrilldownResponse | null>(null)
// TODO: 后续用于柱状图选中高亮
const selectedCategory = ref<string | null>(null)

const displayRows = computed(() => (data.value?.categories ?? []).slice(0, 10))
const memberRows = computed(() => (data.value?.member_categories ?? []).slice(0, 10))

// Bug 5: 合并 filterStore 的渠道和低价筛选状态
// 渠道：只有非"全店"时才覆盖（避免全店时把已有渠道冲掉）
const liveQueryParams = computed(() => {
  const base = { ...props.queryParams }
  if (filterStore.channel && filterStore.channel !== '全店') {
    base.channel = filterStore.channel
  }
  if (filterStore.excludeLowPrice) {
    base.exclude_channels = LOW_PRICE_CHANNELS
  } else {
    base.exclude_channels = undefined
  }
  return base
})

// 动态年份标签：支持同比/环比/自定义三种对比模式
const yearLabel = computed(() => data.value?.year_label ?? '当期')
const compYearLabel = computed(() => data.value?.comp_year_label ?? '对比期')

const tableColumns = computed(() => [
  { title: '品类', key: 'category_name', width: 130, align: 'center' as const, sorter: 'default' as any },
  {
    title: `历史人数(${yearLabel.value})`,
    key: 'hist_users_current',
    width: 110,
    align: 'center' as const,
    sorter: (a: any, b: any) => (a.hist_users_current ?? 0) - (b.hist_users_current ?? 0),
    defaultSortOrder: 'descend' as const,
    render: (r: any) => r.hist_users_current?.toLocaleString() ?? '-',
  },
  {
    title: `复购人数(${yearLabel.value})`,
    key: 'repurchase_users_current',
    width: 110,
    align: 'center' as const,
    sorter: (a: any, b: any) => (a.repurchase_users_current ?? 0) - (b.repurchase_users_current ?? 0),
    render: (r: any) => r.repurchase_users_current?.toLocaleString() ?? '-',
  },
  {
    title: `同品类复购率(${yearLabel.value})`,
    key: 'repurchase_rate_current',
    width: 100,
    align: 'center' as const,
    sorter: (a: any, b: any) => (a.repurchase_rate_current ?? 0) - (b.repurchase_rate_current ?? 0),
    render: (r: any) => fmtPct(r.repurchase_rate_current),
  },
  {
    title: `同比(${yearLabel.value} vs ${compYearLabel.value})`,
    key: 'yoy_repurchase_rate',
    width: 130,
    align: 'center' as const,
    sorter: (a: any, b: any) => (a.yoy_repurchase_rate ?? 0) - (b.yoy_repurchase_rate ?? 0),
    render: (r: any) => {
      const v = r.yoy_repurchase_rate
      if (v == null) return '-'
      const color = v >= 0 ? '#16a34a' : '#dc2626'
      const arrow = v >= 0 ? '↑' : '↓'
      return markRaw(h('span', { style: { color, fontWeight: 600 } }, `${arrow}${Math.abs(v * 100).toFixed(1)}pp`))
    },
  },
  {
    title: `回购GSV(${yearLabel.value})`,
    key: 'repurchase_gsv_current',
    width: 110,
    align: 'center' as const,
    sorter: (a: any, b: any) => (a.repurchase_gsv_current ?? 0) - (b.repurchase_gsv_current ?? 0),
    render: (r: any) => r.repurchase_gsv_current != null ? '¥' + (r.repurchase_gsv_current / 10000).toFixed(1) + '万' : '-',
  },
])


function fmtPct(v: number | null | undefined): string {
  if (v == null) return '-'
  return (v * 100).toFixed(1) + '%'
}
function fmtYoY(v: number | null | undefined): string {
  if (v == null) return '-'
  return (v >= 0 ? '+' : '') + (v * 100).toFixed(1) + 'pp'
}
function yoyClass(v: number | null | undefined): string {
  if (v == null) return ''
  return v >= 0 ? 'success' : 'danger'
}

// Bug 1: 柱状图点击处理（暴露到 window 供 tooltip onclick 调用）
// Issue 1: 柱状图点击（含空白区域）——空白处点击时用坐标换算最近柱体
function onChartClick(params: any) {
  const rows = (displayRows.value as any[]).slice(0, 15)
  // params.name 为空时（点击空白区域），尝试用坐标换算最近柱体
  if (!params.name && params.event?.offsetX != null) {
    const instance = chartRef.value?.getChartInstance?.()
    if (instance) {
      const converted = instance.convertFromPixel({ xAxisIndex: 0 }, params.event.offsetX)
      if (converted !== null && converted !== undefined && rows[converted] != null) {
        selectedCategory.value = rows[converted].category_name
        return
      }
    }
  }
  const name = params?.name
  if (!name) return
  selectedCategory.value = name
}

// Issue 4: 简化 tooltip，品类拆解面板本身不需要"点击下钻"交互
const chartOption = computed((): EChartsOption => {
  const rows = (displayRows.value as any[]).slice(0, 15)
  const yr = yearLabel.value
  const yr2 = compYearLabel.value
  return {
    color: [BRAND_PRIMARY, '#60a5fa'],  // 确保图例颜色与 series 一致（覆盖 baseTheme）
    tooltip: {
      trigger: 'axis' as const,
      backgroundColor: 'rgba(255,255,255,0.98)',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      textStyle: { color: '#0f172a', fontSize: 12 },
      formatter: (params: any) => {
        const arr = Array.isArray(params) ? params : [params]
        const rows = arr.map((p: any) =>
          `<div style="display:flex;align-items:center;gap:6px;margin:2px 0">
            <span style="width:8px;height:8px;border-radius:50%;background:${p.color};flex-shrink:0"></span>
            <span style="color:#64748b;font-size:12px">${p.seriesName}:</span>
            <span style="color:#1e293b;font-size:12px;font-weight:500">${(Number(p.value) * 100).toFixed(1)}%</span>
          </div>`
        ).join('')
        const catName = arr[0].name
        return `<div style="background:#f5f5f5;padding:8px 12px;border-radius:4px;line-height:1.8">
          <div style="font-weight:600;margin-bottom:4px;color:#1e293b">${catName}</div>
          ${rows}
        </div>`
      },
    },
    legend: { top: 0, data: [yr, yr2] },
    grid: { left: 80, right: 20, top: 36, bottom: 36 },
    xAxis: {
      type: 'category' as const,
      data: rows.map((r: any) => r.category_name),
      axisLabel: { rotate: 30, fontSize: 10 },
    },
    yAxis: { type: 'value' as const, name: '回购率', axisLabel: { formatter: (v: number) => (v * 100).toFixed(0) + '%' } },
    series: [
      {
        name: yr, type: 'bar' as const,
        data: rows.map((r: any) => ({ value: r.repurchase_rate_current, itemStyle: { color: BRAND_PRIMARY, borderRadius: [3, 3, 0, 0] } })),
        label: { show: true, position: 'top', formatter: (p: any) => `${(Number(p.value) * 100).toFixed(1)}%`, fontSize: 10, color: BRAND_PRIMARY, fontWeight: 'bold' },
      },
      {
        name: yr2, type: 'bar' as const,
        data: rows.map((r: any) => ({ value: r.repurchase_rate_comp, itemStyle: { color: '#60a5fa', borderRadius: [3, 3, 0, 0] } })),
        label: { show: true, position: 'top', formatter: (p: any) => `${(Number(p.value) * 100).toFixed(1)}%`, fontSize: 10, color: '#60a5fa', fontWeight: 'bold' },
      },
    ],
  }
})

// Issue 2: 将点击处理器暴露到 window，供 tooltip 区域 onclick 调用
onMounted(() => {
  ;(window as any).__rFMDrilldownClick = onChartClick
})

async function load() {
  loading.value = true
  try {
    data.value = await fetchRFMCategoryDrilldown({ rfm_segment: props.rfmSegment, ...liveQueryParams.value })
  } catch (e) {
    console.error('[RFMSegmentDrilldown] load failed', e)
  } finally {
    loading.value = false
  }
}

// 合并 watch：rfmSegment 变化时重新加载，filterStore 变化时也重新加载
watch([() => props.rfmSegment, liveQueryParams], load, { immediate: true })
</script>

<style scoped>
.drilldown-card { border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 12px 0; background: #fafafa; }
.drilldown-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.header-left { display: flex; align-items: center; gap: 8px; }
.segment-badge { background: #2563eb; color: white; padding: 2px 10px; border-radius: 12px; font-size: 13px; }
.header-title { font-weight: 600; font-size: 15px; }
.loading-wrap { display: flex; justify-content: center; padding: 32px; }
.kpi-card { background: #f8fafc; }
.kpi-rate { color: #1e293b !important; }
.kpi-rate.success { color: #16a34a !important; }
.kpi-rate.danger { color: #dc2626 !important; }
.kpi-hint { font-size: 11px; color: #94a3b8; margin: -10px 0 14px 4px; }
.chart-wrap, .table-wrap, .member-wrap { margin: 10px 0; }
.selected-hint { color: #533afd; font-size: 12px; margin-top: 2px; font-weight: 500; }
.table-scroll-wrap { overflow-x: auto; max-height: 400px; overflow-y: auto; }
.table-hint { font-size: 11px; color: #94a3b8; margin-top: 6px; }
.member-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.member-title { font-size: 13px; font-weight: 600; color: #334155; }
.member-hint { font-size: 11px; color: #94a3b8; background: #f1f5f9; padding: 1px 8px; border-radius: 10px; }
.driver-row { display: flex; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
.driver-card { border-radius: 6px; padding: 10px 14px; min-width: 120px; flex: 1; border: 1px solid #e2e8f0; }
.driver-card.up { background: #f0fdf4; border-color: #bbf7d0; }
.driver-card.down { background: #fef2f2; border-color: #fecaca; }
.driver-name { font-size: 13px; font-weight: 600; color: #1e293b; margin-bottom: 4px; }
.driver-rate { font-size: 16px; font-weight: 700; }
.driver-card.up .driver-rate { color: #16a34a; }
.driver-card.down .driver-rate { color: #dc2626; }
.driver-yoy { font-size: 12px; font-weight: 600; }
.driver-card.up .driver-yoy { color: #16a34a; }
.driver-card.down .driver-yoy { color: #dc2626; }
.driver-base { font-size: 11px; color: #64748b; margin-top: 2px; }
</style>
