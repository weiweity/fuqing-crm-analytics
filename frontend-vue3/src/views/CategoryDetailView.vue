<script setup lang="ts">
import { computed, h, toValue } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { NGrid, NGi, NButton } from 'naive-ui'
import ExportToolbar from '@/components/ExportToolbar.vue'
import type { XlsxColumn } from '@/utils/exportXlsx'
import type { DataTableColumns } from 'naive-ui'
import { useFilterStore } from '@/stores/filterStore'
import { fetchCategoryDailyTrend, fetchCategoryUserList } from '@/api/category'
import MetricCard from '@/components/MetricCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import DataTablePro from '@/components/DataTablePro.vue'
import { CHART_COLORS } from '@/composables/useChartTheme'

const route = useRoute()
const router = useRouter()
const filterStore = useFilterStore()

const categoryId = computed(() => String(route.params.categoryId))

// ─── API: Daily Trend ───────────────────────────────────────────
const trendParams = computed(() => {
  const start = filterStore.dateRange[0]
  const end = filterStore.dateRange[1]
  const days = Math.ceil((new Date(end).getTime() - new Date(start).getTime()) / (1000 * 60 * 60 * 24))
  let granularity = 'daily'
  if (days > 90) granularity = 'monthly'
  else if (days > 30) granularity = 'weekly'
  return {
    category_id: categoryId.value,
    category_name: categoryId.value, // 后端会根据ID查名称
    start_date: start,
    end_date: end,
    granularity,
  }
})

const {
  data: trendData,
  isLoading: trendLoading,
  error: trendError,
  refetch: trendRefetch,
} = useQuery({
  queryKey: computed(() => ['category-daily-trend', { ...toValue(trendParams) }]),
  queryFn: () => fetchCategoryDailyTrend(toValue(trendParams)),
  staleTime: 60_000,
})

// ─── API: User List ────────────────────────────────────────────
const userListParams = computed(() => ({
  category_id: categoryId.value,
  category_name: categoryId.value,
  start_date: filterStore.dateRange[0],
  end_date: filterStore.dateRange[1],
  limit: 100,
}))

const {
  data: userListData,
  isLoading: userListLoading,
  error: userListError,
  refetch: userListRefetch,
} = useQuery({
  queryKey: computed(() => ['category-user-list', { ...toValue(userListParams) }]),
  queryFn: () => fetchCategoryUserList(toValue(userListParams)),
  staleTime: 60_000,
})

// ─── KPI Cards ─────────────────────────────────────────────────
const kpiCards = computed(() => {
  const td = trendData.value
  const ud = userListData.value
  const lastIdx = (td?.gmv?.length ?? 1) - 1
  return [
    {
      title: '总用户数',
      value: ud?.total_users?.toLocaleString() ?? '—',
      format: 'number' as const,
    },
    {
      title: '累计GMV',
      value: td?.gmv
        ? `¥${(td.gmv.reduce((s, v) => s + v, 0) / 10000).toFixed(1)}万`
        : '—',
      format: 'currency' as const,
    },
    {
      title: '新客占比',
      value: td?.new_customer_ratio?.length
        ? `${((td.new_customer_ratio[lastIdx] || 0) * 100).toFixed(1)}%`
        : '—',
      format: 'number' as const,
    },
    {
      title: '平均AUS',
      value: td?.aus?.length ? `¥${(td.aus[lastIdx] || 0).toFixed(0)}` : '—',
      format: 'currency' as const,
    },
  ]
})

// ─── 日趋势图 ──────────────────────────────────────────────────
const trendOption = computed(() => {
  if (!trendData.value) return {}
  const { dates, gmv, user_count, aus, new_customer_ratio } = trendData.value
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      padding: [10, 14],
      textStyle: { color: '#0f172a', fontSize: 12 },
      extraCssText: 'box-shadow: 0 4px 12px -2px rgba(0,0,0,0.08); border-radius: 4px;',
    },
    legend: {
      data: ['GMV(万)', '用户数', 'AUS(元)', '新客占比'],
      bottom: 0,
      icon: 'circle',
      itemGap: 16,
      textStyle: { color: '#64748b', fontSize: 11 },
    },
    grid: { left: 48, right: 16, top: 16, bottom: 48 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 10, margin: 8 },
    },
    yAxis: [
      {
        type: 'value',
        name: 'GMV/用户数',
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: '#64748b', fontSize: 11 },
        splitLine: { lineStyle: { color: '#e5edf5', type: [4, 4] } },
      },
      {
        type: 'value',
        name: 'AUS',
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: '#64748b', fontSize: 11 },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: 'GMV(万)',
        type: 'bar',
        yAxisIndex: 0,
        data: gmv.map((v) => parseFloat((v / 10000).toFixed(2))),
        itemStyle: { color: CHART_COLORS[0], borderRadius: [2, 2, 0, 0] },
      },
      {
        name: '用户数',
        type: 'line',
        yAxisIndex: 0,
        data: user_count,
        itemStyle: { color: CHART_COLORS[1] },
        lineStyle: { width: 2 },
        smooth: false,
        symbol: 'circle',
        symbolSize: 4,
      },
      {
        name: 'AUS(元)',
        type: 'line',
        yAxisIndex: 1,
        data: aus.map((v) => parseFloat(v.toFixed(2))),
        itemStyle: { color: CHART_COLORS[2] },
        lineStyle: { width: 2, type: 'dashed' },
        smooth: false,
        symbol: 'circle',
        symbolSize: 4,
      },
      {
        name: '新客占比',
        type: 'line',
        yAxisIndex: 1,
        data: new_customer_ratio.map((v) => parseFloat((v * 100).toFixed(1))),
        itemStyle: { color: CHART_COLORS[4] },
        lineStyle: { width: 2 },
        smooth: false,
        symbol: 'circle',
        symbolSize: 4,
      },
    ],
  }
})

// ─── RFM分布饼图 ───────────────────────────────────────────────
const SEGMENT_NAMES = ['Champions', 'Loyal', 'Potential', 'New', 'At Risk', 'Need Attn', 'Promising', 'About to Sleep']
const SEGMENT_COLORS = ['#533afd', '#8b5cf6', '#a78bfa', '#c4b5fd', '#ef4444', '#f59e0b', '#10b981', '#94a3b8']

const rfmPieOption = computed(() => {
  const users = userListData.value?.users ?? []
  const segCount = new Array(8).fill(0)
  users.forEach((u) => {
    if (u.segment_id >= 1 && u.segment_id <= 8) {
      segCount[u.segment_id - 1]++
    }
  })
  const pieData = segCount
    .map((count, i) => ({ name: SEGMENT_NAMES[i], value: count }))
    .filter((d) => d.value > 0)

  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      padding: [10, 14],
      textStyle: { color: '#0f172a', fontSize: 12 },
      extraCssText: 'box-shadow: 0 4px 12px -2px rgba(0,0,0,0.08); border-radius: 4px;',
      formatter: (params: { name: string; value: number; percent: number }) =>
        `${params.name}<br/>用户: ${params.value.toLocaleString()}<br/>占比: ${params.percent}%`,
    },
    legend: {
      orient: 'vertical',
      right: 8,
      top: 'center',
      icon: 'circle',
      itemGap: 8,
      textStyle: { color: '#64748b', fontSize: 10 },
    },
    series: [
      {
        type: 'pie',
        radius: ['40%', '65%'],
        center: ['35%', '50%'],
        itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
        label: { show: false },
        emphasis: {
          label: { show: true, fontSize: 12, fontWeight: 'bold', color: '#0f172a' },
        },
        data: pieData.map((d, i) => ({
          name: d.name,
          value: d.value,
          itemStyle: { color: SEGMENT_COLORS[i] },
        })),
      },
    ],
  }
})

// ─── 用户明细表 ───────────────────────────────────────────────
const userColumns = computed<DataTableColumns<any>>(() => [
  {
    title: '用户ID',
    key: 'user_id',
    width: 120,
    fixed: 'left',
    align: 'center',
    render: (row) => String(row.user_id),
  },
  {
    title: '昵称',
    key: 'nickname',
    width: 100,
    ellipsis: true,
    render: (row) => row.nickname || '—',
  },
  {
    title: '订单数',
    key: 'order_count',
    width: 80,
    align: 'right',
    className: 'bi-cell-number',
  },
  {
    title: '累计GMV',
    key: 'total_gmv',
    width: 100,
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => `¥${((row.total_gmv || 0) / 10000).toFixed(1)}万`,
  },
  {
    title: '首购日期',
    key: 'first_order_date',
    width: 100,
    align: 'center',
  },
  {
    title: '最近购买',
    key: 'last_order_date',
    width: 100,
    align: 'center',
  },
  {
    title: '象限',
    key: 'segment_name',
    width: 100,
    align: 'center',
    render: (row) => {
      const segIdx = (row.segment_id || 1) - 1
      return h('span', { style: { color: SEGMENT_COLORS[segIdx] ?? '#64748b' } }, row.segment_name || '—')
    },
  },
  {
    title: '会员',
    key: 'is_member',
    width: 70,
    align: 'center',
    render: (row) => row.is_member ? '✓' : '—',
  },
  {
    title: '羊毛党',
    key: 'is_wool_party',
    width: 70,
    align: 'center',
    render: (row) => row.is_wool_party ? '⚠' : '—',
  },
])

// ─── Sprint 174 XLSX 导出 (Q3) ────────────────────────────────
const userListXlsxColumns = computed<XlsxColumn[]>(() => [
  { header: '用户ID', key: 'user_id', width: 14 },
  { header: '昵称', key: 'nickname', width: 16 },
  { header: '订单数', key: 'order_count', width: 10, numFmt: '#,##0' },
  { header: '累计GMV', key: 'total_gmv', width: 14, numFmt: '¥#,##0' },
  { header: '首购日期', key: 'first_order_date', width: 12 },
  { header: '最近购买', key: 'last_order_date', width: 12 },
  { header: '象限', key: 'segment_name', width: 10 },
  { header: '会员', key: 'is_member_text', width: 8 },
  { header: '羊毛党', key: 'is_wool_party_text', width: 8 },
])
const userListXlsxData = computed(() =>
  (userListData.value?.users ?? []).map((u: any) => ({
    user_id: u.user_id,
    nickname: u.nickname || '',
    order_count: u.order_count,
    total_gmv: u.total_gmv,
    first_order_date: u.first_order_date || '',
    last_order_date: u.last_order_date || '',
    segment_name: u.segment_name || '',
    is_member_text: u.is_member ? '是' : '否',
    is_wool_party_text: u.is_wool_party ? '是' : '否',
  }))
)

// ─── CSV导出 ───────────────────────────────────────────────────
function exportCSV() {
  const users = userListData.value?.users ?? []
  if (!users.length) return
  const header = ['用户ID', '昵称', '订单数', '累计GMV', '首购日期', '最近购买', '象限', '会员', '羊毛党']
  const rows = users.map((u) => [
    u.user_id,
    u.nickname || '',
    u.order_count,
    u.total_gmv,
    u.first_order_date || '',
    u.last_order_date || '',
    u.segment_name || '',
    u.is_member ? '是' : '否',
    u.is_wool_party ? '是' : '否',
  ])
  const csv = [header, ...rows].map((r) => r.join(',')).join('\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `品类用户_${categoryId.value}_${filterStore.dateRange[0]}_${filterStore.dateRange[1]}.csv`
  link.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="space-y-5">
    <!-- PageHeader with back button -->
    <div class="flex items-center justify-between">
      <PageHeader
        :title="trendData?.category_name || categoryId"
        :subtitle="`品类ID: ${categoryId}`"
      />
      <NButton size="small" @click="router.push('/category')">← 返回品类看板</NButton>
    </div>

    <!-- KPI Cards -->
    <n-grid :cols="4" :x-gap="12" :y-gap="12" responsive="screen" :item-responsive="true">
      <n-gi v-for="(card, i) in kpiCards" :key="i" :span="1">
        <MetricCard
          :title="card.title"
          :value="card.value"
          :loading="trendLoading || userListLoading"
          :format="card.format"
        />
      </n-gi>
    </n-grid>

    <!-- 日趋势图 -->
    <div class="bi-card p-4">
      <h3 class="text-sm font-semibold text-slate-800 mb-0.5">
        {{ trendData?.granularity === 'monthly' ? '月' : trendData?.granularity === 'weekly' ? '周' : '日' }}趋势
      </h3>
      <p class="text-[11px] text-slate-500 mb-3">
        {{ filterStore.dateRange[0] }} ~ {{ filterStore.dateRange[1] }}
      </p>
      <ErrorState v-if="trendError" :message="(trendError as Error).message" @retry="trendRefetch()" />
      <LoadingState v-else-if="trendLoading" />
      <EChartsWrapper v-else-if="trendData?.dates?.length" :option="trendOption" height="280px" />
      <EmptyState v-else description="暂无趋势数据" />
    </div>

    <div class="grid grid-cols-5 gap-5">
      <!-- RFM分布饼图 -->
      <div class="col-span-2 bi-card p-4">
        <h3 class="text-sm font-semibold text-slate-800 mb-0.5">RFM象限分布</h3>
        <p class="text-[11px] text-slate-500 mb-3">购买该品类的用户在8象限中的分布</p>
        <ErrorState v-if="userListError" :message="(userListError as Error).message" @retry="userListRefetch()" />
        <LoadingState v-else-if="userListLoading" />
        <EChartsWrapper v-else-if="userListData?.users?.length" :option="rfmPieOption" height="280px" />
        <EmptyState v-else description="暂无用户数据" />
      </div>

      <!-- 新老客转化漏斗 (简化展示) -->
      <div class="col-span-3 bi-card p-4">
        <h3 class="text-sm font-semibold text-slate-800 mb-0.5">新老客转化漏斗</h3>
        <p class="text-[11px] text-slate-500 mb-3">基于查询时间窗口的转化参考</p>
        <LoadingState v-if="userListLoading" />
        <div v-else class="space-y-3 pt-4">
          <div v-for="(stage, i) in ['首购用户', '30天复购', '90天复购', '忠诚用户']" :key="stage"
            class="flex items-center gap-3">
            <div
              class="h-8 rounded flex items-center justify-center text-white text-xs font-medium"
              :style="{
                width: `${100 - i * 15}%`,
                backgroundColor: CHART_COLORS[i],
                opacity: 1 - i * 0.15,
              }"
            >
              {{ stage }}
            </div>
            <span class="text-xs text-slate-500">{{ ['100%', '~35%', '~18%', '~8%'][i] }}</span>
          </div>
          <p class="text-[10px] text-slate-400 mt-2">注: 漏斗数据为参考值，基于整体均值估算</p>
        </div>
      </div>
    </div>

    <!-- 用户明细表 -->
    <div class="bi-card p-4">
      <div class="flex items-center justify-between mb-3">
        <div>
          <h3 class="text-sm font-semibold text-slate-800 mb-0.5">用户明细表</h3>
          <p class="text-[11px] text-slate-500">
            TOP100用户
            <span v-if="userListData?.total_users" class="ml-1">
              (共 {{ userListData.total_users.toLocaleString() }} 人)
            </span>
          </p>
        </div>
        <NButton size="tiny" @click="exportCSV" :disabled="!userListData?.users?.length">
          导出CSV
        </NButton>
        <ExportToolbar
          :filename="`${categoryId}_用户明细_${filterStore.dateRange[0]}_${filterStore.dateRange[1]}`"
          :columns="userListXlsxColumns"
          :data="userListXlsxData"
          sheet-name="用户明细"
        />
      </div>
      <ErrorState v-if="userListError" :message="(userListError as Error).message" @retry="userListRefetch()" />
      <LoadingState v-else-if="userListLoading" />
      <DataTablePro
        v-else-if="userListData?.users?.length"
        :columns="userColumns"
        :data="userListData.users"
        :pagination="{ pageSize: 20 }"
        :scroll-x="900"
      />
      <EmptyState v-else description="暂无用户数据" />
    </div>
  </div>
</template>
