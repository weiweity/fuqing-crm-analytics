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
      <div class="kpi-row">
        <div class="kpi-item">
          <div class="kpi-label">总历史人数</div>
          <div class="kpi-value">{{ data.summary.total_hist_users?.toLocaleString() ?? '-' }}</div>
        </div>
        <div class="kpi-item">
          <div class="kpi-label">当期回购率</div>
          <div class="kpi-value">{{ fmtPct(data.summary.overall_repurchase_rate) }}</div>
        </div>
        <div class="kpi-item">
          <div class="kpi-label">同比变化</div>
          <div class="kpi-value" :class="yoyClass(data.summary.overall_repurchase_rate_yoy)">
            {{ fmtYoY(data.summary.overall_repurchase_rate_yoy) }}
          </div>
        </div>
        <div class="kpi-item">
          <div class="kpi-label">下降品类</div>
          <div class="kpi-value danger">{{ data.summary.declining_categories?.length ?? 0 }} 个</div>
        </div>
        <div class="kpi-item">
          <div class="kpi-label">上升品类</div>
          <div class="kpi-value success">{{ data.summary.improving_categories?.length ?? 0 }} 个</div>
        </div>
      </div>

      <div class="chart-wrap">
        <EChartsWrapper :option="chartOption" style="height: 240px" />
      </div>

      <div class="table-wrap">
        <n-data-table :columns="tableColumns" :data="displayRows" :pagination="{ pageSize: 8 }" size="small" />
      </div>

      <div v-if="memberRows.length > 0" class="member-wrap">
        <n-collapse>
          <n-collapse-item title="会员品类明细">
            <n-data-table :columns="tableColumns" :data="memberRows" :pagination="{ pageSize: 5 }" size="small" />
          </n-collapse-item>
        </n-collapse>
      </div>

      <div v-if="insights.length > 0" class="insight-wrap">
        <div class="insight-title">💡 运营洞察</div>
        <ul>
          <li v-for="(ins, i) in insights" :key="i">{{ ins }}</li>
        </ul>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { NButton, NDataTable, NCollapse, NCollapseItem, NSpin } from 'naive-ui'
import { Close } from '@vicons/ionicons5'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import { fetchRFMCategoryDrilldown, type RFMCategoryDrilldownResponse } from '@/api/health'

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

const loading = ref(false)
const data = ref<RFMCategoryDrilldownResponse | null>(null)

const displayRows = computed(() => data.value?.categories ?? [])
const memberRows = computed(() => data.value?.member_categories ?? [])

// 动态年份标签：支持同比/环比/自定义三种对比模式
const yearLabel = computed(() => data.value?.year_label ?? '当期')
const compYearLabel = computed(() => data.value?.comp_year_label ?? '对比期')

const tableColumns = computed(() => [
  { title: '品类', key: 'category_name', width: 130 },
  { title: `历史人数(${yearLabel.value})`, key: 'hist_users_current', render: (r: any) => r.hist_users_current?.toLocaleString() ?? '-' },
  { title: `回购人数(${yearLabel.value})`, key: 'repurchase_users_current', render: (r: any) => r.repurchase_users_current?.toLocaleString() ?? '-' },
  { title: `回购率(${yearLabel.value})`, key: 'repurchase_rate_current', render: (r: any) => fmtPct(r.repurchase_rate_current) },
  { title: `同比(${yearLabel.value} vs ${compYearLabel.value})`, key: 'yoy_repurchase_rate', render: (r: any) => fmtYoY(r.yoy_repurchase_rate) },
  { title: `回购GSV(${yearLabel.value})`, key: 'repurchase_gsv_current', render: (r: any) => r.repurchase_gsv_current != null ? '¥' + (r.repurchase_gsv_current / 10000).toFixed(1) + '万' : '-' },
])

const chartOption = computed(() => {
  const rows = (displayRows.value as any[]).slice(0, 15)
  const yr = yearLabel.value
  const yr2 = compYearLabel.value
  return {
    tooltip: { trigger: 'axis' as const },
    legend: { top: 0, data: [yr, yr2] },
    grid: { left: 80, right: 20, top: 36, bottom: 36 },
    xAxis: { type: 'category' as const, data: rows.map((r: any) => r.category_name), axisLabel: { rotate: 30, fontSize: 10 } },
    yAxis: { type: 'value' as const, name: '回购率', axisLabel: { formatter: (v: number) => (v * 100).toFixed(0) + '%' } },
    series: [
      { name: yr, type: 'bar' as const, data: rows.map((r: any) => ({ value: r.repurchase_rate_current, itemStyle: { color: '#2563eb' } })) },
      { name: yr2, type: 'bar' as const, data: rows.map((r: any) => ({ value: r.repurchase_rate_comp, itemStyle: { color: '#94a3b8' } })) },
    ],
  }
})

const insights = computed(() => {
  const msgs: string[] = []
  const dec = data.value?.summary.declining_categories ?? []
  const imp = data.value?.summary.improving_categories ?? []
  if (dec.length > 0) {
    msgs.push(`"${dec[0].name}" 回购率同比下降 ${(dec[0].yoy_repurchase_rate * 100).toFixed(1)}pp，为主要下滑因素`)
  }
  if (imp.length > 0) {
    msgs.push(`"${imp[0].name}" 回购率同比上升 ${(imp[0].yoy_repurchase_rate * 100).toFixed(1)}pp，表现良好`)
  }
  return msgs
})

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

async function load() {
  loading.value = true
  try {
    data.value = await fetchRFMCategoryDrilldown({ rfm_segment: props.rfmSegment, ...props.queryParams })
  } catch (e) {
    console.error('[RFMSegmentDrilldown] load failed', e)
  } finally {
    loading.value = false
  }
}

watch(() => props.rfmSegment, load, { immediate: true })
watch(() => props.queryParams, load, { deep: true })
</script>

<style scoped>
.drilldown-card { border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 12px 0; background: #fafafa; }
.drilldown-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.header-left { display: flex; align-items: center; gap: 8px; }
.segment-badge { background: #2563eb; color: white; padding: 2px 10px; border-radius: 12px; font-size: 13px; }
.header-title { font-weight: 600; font-size: 15px; }
.loading-wrap { display: flex; justify-content: center; padding: 32px; }
.kpi-row { display: flex; gap: 12px; margin-bottom: 14px; flex-wrap: wrap; }
.kpi-item { background: white; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px 14px; min-width: 90px; }
.kpi-label { font-size: 11px; color: #64748b; margin-bottom: 4px; }
.kpi-value { font-size: 18px; font-weight: 600; }
.kpi-value.success { color: #16a34a; }
.kpi-value.danger { color: #dc2626; }
.chart-wrap, .table-wrap, .member-wrap { margin: 10px 0; }
.insight-wrap { background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; padding: 10px 14px; margin-top: 10px; }
.insight-title { font-weight: 600; margin-bottom: 6px; font-size: 13px; }
.insight-wrap ul { margin: 0; padding-left: 18px; }
.insight-wrap li { font-size: 13px; margin: 3px 0; }
</style>
