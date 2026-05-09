<script setup lang="ts">
import { computed, toValue } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NGrid, NGi, NTabs, NTabPane } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useFilterStore } from '@/stores/filterStore'
import {
  fetchChurnDistribution,
  fetchChurnRiskUsers,
  type ChurnUser,
} from '@/api/churn'
import MetricCard from '@/components/MetricCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import DataTablePro from '@/components/DataTablePro.vue'

const filterStore = useFilterStore()

import { LOW_PRICE_CHANNELS } from '@/constants/channels'

const distributionParams = computed(() => ({
  date: filterStore.dateRange[1],
  churn_mode: 'dynamic' as const,
  fixed_threshold: 60,
  exclude_channels: filterStore.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined,
}))

const riskUsersParams = computed(() => ({
  date: filterStore.dateRange[1],
  risk_level: 'high',
  limit: 50,
  exclude_channels: filterStore.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined,
}))

const {
  data: distributionData,
  isLoading: distributionLoading,
  error: distributionError,
  refetch: distributionRefetch,
} = useQuery({
  queryKey: computed(() => ['churn-distribution', { ...toValue(distributionParams) }]),
  queryFn: () => fetchChurnDistribution(toValue(distributionParams)),
  staleTime: 60_000,
})

const {
  data: riskUsersData,
  isLoading: riskUsersLoading,
  error: riskUsersError,
  refetch: riskUsersRefetch,
} = useQuery({
  queryKey: computed(() => ['churn-risk-users', { ...toValue(riskUsersParams) }]),
  queryFn: () => fetchChurnRiskUsers(toValue(riskUsersParams)),
  staleTime: 60_000,
})

const segmentChartOption = computed(() => {
  if (!distributionData.value) return {}
  const bySegment = distributionData.value.by_segment
  const segments = Object.keys(bySegment)
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      padding: [10, 12],
      textStyle: { color: '#0f172a', fontSize: 12 },
      extraCssText: 'box-shadow: 0 4px 12px -2px rgba(0,0,0,0.08); border-radius: 4px;',
    },
    legend: {
      data: ['高风险', '中风险', '低风险'],
      top: 0,
      icon: 'circle',
      itemGap: 20,
      textStyle: { color: '#64748b', fontSize: 11 },
    },
    grid: { left: 12, right: 12, top: 40, bottom: 8 },
    xAxis: {
      type: 'category',
      data: segments,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 11, margin: 10 },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 11 },
      splitLine: { lineStyle: { color: '#e2e8f0', type: [4, 4] } },
    },
    series: [
      {
        name: '高风险',
        type: 'bar',
        stack: 'total',
        data: segments.map((s) => bySegment[s].high_risk),
        itemStyle: { color: '#ef4444', borderRadius: [0, 0, 0, 0] },
        barWidth: '36%',
      },
      {
        name: '中风险',
        type: 'bar',
        stack: 'total',
        data: segments.map((s) => bySegment[s].medium_risk),
        itemStyle: { color: '#f59e0b', borderRadius: [0, 0, 0, 0] },
        barWidth: '36%',
      },
      {
        name: '低风险',
        type: 'bar',
        stack: 'total',
        data: segments.map((s) => bySegment[s].low_risk),
        itemStyle: { color: '#10b981', borderRadius: [3, 3, 0, 0] },
        barWidth: '36%',
      },
    ],
  }
})

interface SegmentTableRow {
  segment: string
  total: number
  high_risk: number
  medium_risk: number
  low_risk: number
  high_risk_rate: number
}

const segmentColumns: DataTableColumns<SegmentTableRow> = [
  { title: '象限', key: 'segment', width: 140, fixed: 'left' },
  { title: '总人数', key: 'total', align: 'right', className: 'bi-cell-number' },
  { title: '高风险', key: 'high_risk', align: 'right', className: 'bi-cell-number' },
  { title: '中风险', key: 'medium_risk', align: 'right', className: 'bi-cell-number' },
  { title: '低风险', key: 'low_risk', align: 'right', className: 'bi-cell-number' },
  {
    title: '高风险率',
    key: 'high_risk_rate',
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => `${(row.high_risk_rate * 100).toFixed(1)}%`,
  },
]

const segmentTableData = computed<SegmentTableRow[]>(() => {
  if (!distributionData.value) return []
  const bySegment = distributionData.value.by_segment
  return Object.entries(bySegment).map(([segment, values]) => ({
    segment,
    total: values.total,
    high_risk: values.high_risk,
    medium_risk: values.medium_risk,
    low_risk: values.low_risk,
    high_risk_rate: values.total > 0 ? values.high_risk / values.total : 0,
  }))
})

const userColumns: DataTableColumns<ChurnUser> = [
  { title: '用户ID', key: 'user_id', width: 160, fixed: 'left' },
  { title: '昵称', key: 'nickname' },
  {
    title: '最后下单',
    key: 'last_order_date',
    render: (row) => row.last_order_date || '—',
  },
  { title: '距今天数', key: 'days_since_last_order', align: 'right', className: 'bi-cell-number' },
  { title: '总订单数', key: 'total_orders', align: 'right', className: 'bi-cell-number' },
  {
    title: '总GMV',
    key: 'total_gmv',
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => `¥${row.total_gmv.toFixed(1)}`,
  },
  {
    title: '客单价',
    key: 'avg_order_value',
    align: 'right',
    className: 'bi-cell-number',
    render: (row) => row.avg_order_value != null ? `¥${row.avg_order_value.toFixed(1)}` : '—',
  },
  { title: '所属象限', key: 'segment_name' },
]
</script>

<template>
  <div class="space-y-5 relative">
    <!-- 待优化更新遮罩 -->
    <div class="absolute inset-0 z-50 flex items-center justify-center bg-slate-50/80 backdrop-blur-sm rounded-lg" style="min-height: 600px;">
      <div class="text-center">
        <div class="text-4xl mb-2">🔧</div>
        <div class="text-lg font-semibold text-slate-600">待优化更新</div>
        <div class="text-sm text-slate-400 mt-1">该模块正在重构中，敬请期待</div>
      </div>
    </div>

    <PageHeader title="流失分析" subtitle="用户流失风险识别与高风险用户清单" />

    <n-grid :cols="4" :x-gap="12" :y-gap="12" responsive="screen" :item-responsive="true">
      <n-gi :span="1">
        <MetricCard
          title="分析用户总数"
          :value="distributionData ? distributionData.total_users.toLocaleString() : '—'"
          :loading="distributionLoading"
        />
      </n-gi>
      <n-gi :span="1">
        <MetricCard
          title="高风险人数"
          :value="distributionData ? distributionData.high_risk.toLocaleString() : '—'"
          :loading="distributionLoading"
        />
      </n-gi>
      <n-gi :span="1">
        <MetricCard
          title="高风险率"
          :value="distributionData ? `${(distributionData.high_risk_rate * 100).toFixed(1)}%` : '—'"
          :loading="distributionLoading"
        />
      </n-gi>
      <n-gi :span="1">
        <MetricCard
          title="中风险人数"
          :value="distributionData ? distributionData.medium_risk.toLocaleString() : '—'"
          :loading="distributionLoading"
        />
      </n-gi>
    </n-grid>

    <div class="bi-card p-4">
      <n-tabs type="line" animated>
        <n-tab-pane name="distribution" tab="风险分布">
          <div class="space-y-5 mt-3">
            <div>
              <h3 class="text-sm font-semibold text-slate-800 mb-0.5">象限风险分布</h3>
              <p class="text-[11px] text-slate-500 mb-4">各用户象限的高/中/低风险人数堆叠分布</p>
              <ErrorState
                v-if="distributionError"
                :message="(distributionError as Error).message"
                @retry="distributionRefetch()"
              />
              <LoadingState v-else-if="distributionLoading" />
              <EmptyState v-else-if="!Object.keys(distributionData?.by_segment || {}).length" />
              <EChartsWrapper v-else :option="segmentChartOption" height="280px" />
            </div>

            <div>
              <h3 class="text-sm font-semibold text-slate-800 mb-0.5">象限明细</h3>
              <p class="text-[11px] text-slate-500 mb-3">按象限聚合的流失风险统计数据</p>
              <ErrorState
                v-if="distributionError"
                :message="(distributionError as Error).message"
                @retry="distributionRefetch()"
              />
              <LoadingState v-else-if="distributionLoading" />
              <EmptyState v-else-if="!segmentTableData.length" description="当前条件下无数据" />
              <DataTablePro
                v-else
                :columns="segmentColumns"
                :data="segmentTableData"
                :pagination="{ pageSize: 20 }"
              />
            </div>
          </div>
        </n-tab-pane>

        <n-tab-pane name="users" tab="高风险用户">
          <div class="mt-3">
            <h3 class="text-sm font-semibold text-slate-800 mb-0.5">高风险用户清单</h3>
            <p class="text-[11px] text-slate-500 mb-3">按流失风险评分排序的前50名高风险用户</p>
            <ErrorState
              v-if="riskUsersError"
              :message="(riskUsersError as Error).message"
              @retry="riskUsersRefetch()"
            />
            <LoadingState v-else-if="riskUsersLoading" />
            <EmptyState v-else-if="!riskUsersData?.users.length" description="当前条件下无数据" />
            <DataTablePro
              v-else
              :columns="userColumns"
              :data="riskUsersData.users"
              :pagination="{ pageSize: 20 }"
            />
          </div>
        </n-tab-pane>
      </n-tabs>
    </div>
  </div>
</template>
