<script setup lang="ts">
import { computed, toValue, h, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import type { DataTableColumns } from 'naive-ui'
import { NSelect } from 'naive-ui'
import { useFilterStore } from '@/stores/filterStore'
import {
  fetchCategoryRepurchaseFlow,
  type CategoryRepurchaseFlowRow,
  type CategoryRepurchaseFlowResponse,
} from '@/api/category'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import DataTablePro from '@/components/DataTablePro.vue'
import YOYBadge from '@/components/YOYBadge.vue'
import { BRAND_PRIMARY } from '@/composables/useChartTheme'
import type { EChartTooltipParam, EChartLabelParam } from '@/types/echarts'
import { LOW_PRICE_CHANNELS } from '@/constants/channels'

const props = defineProps<{
  /** 品类列表（从 distributionData 获取） */
  categoryOptions: string[]
}>()

const filterStore = useFilterStore()

// 默认选中第一个品类
const targetCategory = ref<string | null>(null)

// 初始化默认品类
const initCategory = computed(() => {
  if (targetCategory.value) return targetCategory.value
  return props.categoryOptions[0] || 'B5面膜'
})

const categorySelectOptions = computed(() =>
  props.categoryOptions.map((c) => ({ label: c, value: c }))
)

const queryParams = computed(() => ({
  start_date: filterStore.dateRange[0],
  end_date: filterStore.dateRange[1],
  category: initCategory.value,
  level: 'class',
  metric_type: 'GSV',
  channel: filterStore.channel === '全店' ? undefined : filterStore.channel,
  exclude_channels: filterStore.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined,
}))

const {
  data,
  isLoading,
  error,
  refetch,
} = useQuery({
  queryKey: computed(() => ['category-repurchase-flow', { ...toValue(queryParams) }]),
  queryFn: () => fetchCategoryRepurchaseFlow(toValue(queryParams)),
  staleTime: 60_000,
})

// ── RFM象限分段元数据 ──
const segmentMeta = computed<Record<string, { label: string; range: string }>>(() => {
  return {
    '重要价值客户': { label: '重要价值客户', range: 'R高·F高·M高' },
    '重要保持客户': { label: '重要保持客户', range: 'R低·F高·M高' },
    '重要发展客户': { label: '重要发展客户', range: 'R高·F低·M高' },
    '重要挽留客户': { label: '重要挽留客户', range: 'R低·F低·M高' },
    '一般价值客户': { label: '一般价值客户', range: 'R高·F高·M低' },
    '一般保持客户': { label: '一般保持客户', range: 'R低·F高·M低' },
    '一般发展客户': { label: '一般发展客户', range: 'R高·F低·M低' },
    '一般挽留客户': { label: '一般挽留客户', range: 'R低·F低·M低' },
    '已购客TTL': { label: '已购客TTL', range: '全部' },
  }
})

// ── 柱状图: 回购率3年对比 ──
const repurchaseChartOption = computed(() => {
  if (!data.value) return {}
  const d = data.value as CategoryRepurchaseFlowResponse
  const rows = d.same_category_rows.filter((r) => r.rfm_segment !== '已购客TTL')
  const segments = rows.map((r) => r.rfm_segment)

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
      data: [`${d.year_label}年`, `${d.comp_year_label}年`, `${d.prev2_year_label}年`],
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
        name: `${d.year_label}年`,
        type: 'bar',
        data: rows.map((r) => r.repurchase_rate_current),
        itemStyle: { color: BRAND_PRIMARY, borderRadius: [3, 3, 0, 0] },
        barGap: '20%',
        label: { show: true, position: 'top', formatter: (p: EChartLabelParam) => `${(p.value as number * 100).toFixed(1)}%`, fontSize: 10, color: BRAND_PRIMARY },
      },
      {
        name: `${d.comp_year_label}年`,
        type: 'bar',
        data: rows.map((r) => r.repurchase_rate_comp),
        itemStyle: { color: '#60a5fa', borderRadius: [3, 3, 0, 0] },
        label: { show: true, position: 'top', formatter: (p: EChartLabelParam) => `${(p.value as number * 100).toFixed(1)}%`, fontSize: 10, color: '#60a5fa' },
      },
      {
        name: `${d.prev2_year_label}年`,
        type: 'bar',
        data: rows.map((r) => r.repurchase_rate_prev2),
        itemStyle: { color: '#94a3b8', borderRadius: [3, 3, 0, 0] },
        label: { show: true, position: 'top', formatter: (p: EChartLabelParam) => `${(p.value as number * 100).toFixed(1)}%`, fontSize: 10, color: '#94a3b8' },
      },
    ],
  }
})

// ── 表格列定义（复用 RIntervalTab 模式）──
const flowColumns = computed<DataTableColumns<CategoryRepurchaseFlowRow>>(() => {
  const yr = data.value?.year_label || String(new Date().getFullYear())
  const yr2 = data.value?.comp_year_label || String(new Date().getFullYear() - 1)
  const yr3 = data.value?.prev2_year_label || String(new Date().getFullYear() - 2)

  return [
    {
      title: 'RFM 象限',
      key: 'rfm_segment',
      width: 160,
      fixed: 'left',
      align: 'center',
      render: (row: CategoryRepurchaseFlowRow) => {
        const meta = segmentMeta.value[row.rfm_segment] || { label: row.rfm_segment, range: '' }
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
      title: `${yr}同比历史人数`,
      key: 'yoy_hist_users',
      width: 110,
      align: 'center',
      render: (r) => h(YOYBadge, { value: r.yoy_hist_users }),
    },
    {
      title: `${yr}同比回购人数`,
      key: 'yoy_repurchase_users',
      width: 110,
      align: 'center',
      render: (r) => h(YOYBadge, { value: r.yoy_repurchase_users }),
    },
    {
      title: `${yr}同比回购率`,
      key: 'yoy_repurchase_rate',
      width: 110,
      align: 'center',
      render: (r) => h(YOYBadge, { value: r.yoy_repurchase_rate }),
    },
    {
      title: `${yr}同比回购GSV`,
      key: 'yoy_repurchase_gsv',
      width: 110,
      align: 'center',
      render: (r) => h(YOYBadge, { value: r.yoy_repurchase_gsv }),
    },
    {
      title: `${yr}同比回购GSV占比`,
      key: 'yoy_repurchase_gsv_ratio',
      width: 120,
      align: 'center',
      render: (r) => h(YOYBadge, { value: r.yoy_repurchase_gsv_ratio }),
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
</script>

<template>
  <div class="space-y-5 pt-1">
    <!-- 品类选择器 + 说明 -->
    <div class="flex items-center justify-between">
      <div>
        <p class="text-[11px] text-slate-400">
          买了某品类的老客，多久回来？回来买了同品还是其他品类？——识别品类复购周期和承接关系
        </p>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-xs text-slate-500">目标品类:</span>
        <n-select
          v-model:value="targetCategory"
          :options="categorySelectOptions"
          size="small"
          clearable
          filterable
          tag
          placeholder="输入或选择品类"
          style="width: 200px"
        />
      </div>
    </div>

    <ErrorState v-if="error" :message="(error as Error).message" @retry="refetch()" />
    <LoadingState v-else-if="isLoading" />

    <template v-else-if="data">
      <!-- 回购率3年对比柱状图 -->
      <div class="bi-card p-4">
        <h3 class="text-sm font-semibold text-slate-800 mb-0.5">
          {{ data.target_category }} — 同品回购率 3 年对比
        </h3>
        <p class="text-[11px] text-slate-500 mb-3">各R区间老客对{{ data.target_category }}的复购率变化</p>
        <EmptyState
          v-if="!data.same_category_rows?.length"
          description="当前条件下无数据"
        />
        <EChartsWrapper v-else :option="repurchaseChartOption" height="260px" />
      </div>

      <!-- 同品回购明细 — 全店 -->
      <div class="bi-card p-4">
        <h3 class="text-sm font-semibold text-slate-800 mb-0.5">
          同品回购明细 — {{ data.target_category }}
        </h3>
        <p class="text-[11px] text-slate-500 mb-3">
          买了{{ data.target_category }}的老客，在分析期回来买同一品类的回购表现（3年同比）
        </p>
        <DataTablePro
          :columns="flowColumns"
          :data="data.same_category_rows"
          :pagination="{ pageSize: 12 }"
          :scroll-x="2100"
        />
      </div>

      <!-- 跨品类回购明细 — 全店 -->
      <div class="bi-card p-4">
        <h3 class="text-sm font-semibold text-slate-800 mb-0.5">
          跨品类回购明细 — {{ data.target_category }}
        </h3>
        <p class="text-[11px] text-slate-500 mb-3">
          买了{{ data.target_category }}的老客，在分析期回来买了其他品类的跨品类回购表现（3年同比）
        </p>
        <DataTablePro
          :columns="flowColumns"
          :data="data.cross_category_rows"
          :pagination="{ pageSize: 12 }"
          :scroll-x="2100"
        />
      </div>

      <!-- 会员 同品回购 -->
      <div class="bi-card p-4">
        <h3 class="text-sm font-semibold text-slate-800 mb-0.5">
          同品回购明细 — {{ data.target_category }} — 会员
        </h3>
        <p class="text-[11px] text-slate-500 mb-3">
          买了{{ data.target_category }}的会员老客，同品回购表现（3年同比）
        </p>
        <DataTablePro
          :columns="flowColumns"
          :data="data.member_same_category_rows"
          :pagination="{ pageSize: 12 }"
          :scroll-x="2100"
        />
      </div>

      <!-- 会员 跨品类回购 -->
      <div class="bi-card p-4">
        <h3 class="text-sm font-semibold text-slate-800 mb-0.5">
          跨品类回购明细 — {{ data.target_category }} — 会员
        </h3>
        <p class="text-[11px] text-slate-500 mb-3">
          买了{{ data.target_category }}的会员老客，跨品类回购表现（3年同比）
        </p>
        <DataTablePro
          :columns="flowColumns"
          :data="data.member_cross_category_rows"
          :pagination="{ pageSize: 12 }"
          :scroll-x="2100"
        />
      </div>
    </template>

    <EmptyState v-else description="暂无数据" />
  </div>
</template>
