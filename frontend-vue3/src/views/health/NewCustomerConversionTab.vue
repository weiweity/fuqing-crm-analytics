<script setup lang="ts">
import { computed, toValue, h } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NGrid, NGi, NDataTable, NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import ExportToolbar from '@/components/ExportToolbar.vue'
import type { XlsxColumn } from '@/utils/exportXlsx'
import { useFilterStore } from '@/stores/filterStore'
import { fetchNewCustomerConversion } from '@/api/health'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import EChartsWrapper from '@/components/EChartsWrapper.vue'

const filterStore = useFilterStore()
import { LOW_PRICE_CHANNELS } from '@/constants/channels'

const queryParams = computed(() => ({
  analysis_date: filterStore.dateRange[1],
  lookback_months: 12,
  exclude_channels: filterStore.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined,
}))

const { data, isLoading, error, refetch } = useQuery({
  queryKey: ['new-customer-conversion', queryParams],
  queryFn: () => {
    const p = toValue(queryParams)
    return fetchNewCustomerConversion({
      analysis_date: p.analysis_date,
      lookback_months: p.lookback_months,
      exclude_channels: p.exclude_channels,
    })
  },
  staleTime: 60_000,
})

const funnelOption = computed(() => {
  if (!data.value?.overall_funnel) return {}
  const f = data.value.overall_funnel
  return {
    title: { text: '新客转化漏斗', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'item', formatter: '{b}: {c}人 ({d}%)' },
    series: [{
      type: 'funnel',
      left: '10%', top: 40, bottom: 20, width: '80%',
      min: 0, max: f.total_first_purchase,
      label: { show: true, formatter: '{b}\n{c}人 ({d}%)' },
      data: [
        { value: f.total_first_purchase, name: '首购用户' },
        { value: f.day7_repurchase, name: '7日复购' },
        { value: f.day30_repurchase, name: '30日复购' },
        { value: f.day90_repurchase, name: '90日复购' },
      ],
    }],
  }
})

const channelColumns: DataTableColumns<any> = [
  { title: '渠道', key: 'channel' },
  { title: '首购人数', key: 'first_purchase_users', align: 'right' },
  { title: '首购客单价', key: 'first_purchase_aus', align: 'right',
    render: (row) => `¥${row.first_purchase_aus}`,
  },
  { title: '30日复购率', key: 'day30_repurchase_rate', align: 'right',
    render: (row) => `${(row.day30_repurchase_rate * 100).toFixed(1)}%`,
  },
  { title: '90日复购率', key: 'day90_repurchase_rate', align: 'right',
    render: (row) => `${(row.day90_repurchase_rate * 100).toFixed(1)}%`,
  },
  { title: '质量分', key: 'quality_score', align: 'right' },
  { title: '评级', key: 'quality_grade', align: 'center',
    render: (row) => {
      const colors: Record<string, string> = { A: 'success', B: 'info', C: 'warning', D: 'error' }
      return h(NTag, { type: colors[row.quality_grade] as any, size: 'small' }, { default: () => row.quality_grade })
    },
  },
]

// ── Sprint 174 XLSX 导出 (Q3, 替换旧 exportToCsv) ──
const newCustomerXlsxColumns = computed<XlsxColumn[]>(() => [
  { header: '渠道', key: 'channel', width: 14 },
  { header: '首购人数', key: 'first_purchase_users', width: 14, numFmt: '#,##0' },
  { header: '首购客单价', key: 'first_purchase_aus', width: 14, numFmt: '¥#,##0' },
  { header: '30日复购率', key: 'day30_repurchase_rate', width: 14, numFmt: '0.0%' },
  { header: '90日复购率', key: 'day90_repurchase_rate', width: 14, numFmt: '0.0%' },
  { header: '质量分', key: 'quality_score', width: 12, numFmt: '0.0' },
  { header: '评级', key: 'quality_grade', width: 10 },
])
</script>

<template>
  <div class="new-customer-tab">
    <LoadingState v-if="isLoading" />
    <ErrorState v-else-if="error" :message="error.message" @retry="refetch" />

    <template v-else-if="data">
      <!-- 漏斗图 + 渠道质量 -->
      <NGrid :cols="2" :x-gap="16" class="mb-4">
        <NGi>
          <div class="bi-card p-4">
            <EChartsWrapper :option="funnelOption" height="350px" />
          </div>
        </NGi>
        <NGi>
          <div class="bi-card p-4">
            <div class="flex items-center justify-between mb-3">
              <h3 class="text-sm font-semibold text-slate-700">分渠道新客质量</h3>
              <ExportToolbar
                :filename="`新客转化_${filterStore.dateRange[1]}`"
                :columns="newCustomerXlsxColumns"
                :data="(data?.channel_quality ?? []) as any[]"
                sheet-name="新客转化"
              />
            </div>
            <NDataTable
              :columns="channelColumns"
              :data="data.channel_quality"
              :pagination="false"
              size="small"
              striped
            />
          </div>
        </NGi>
      </NGrid>

      <!-- 月度转化趋势 -->
      <div v-if="data.monthly_trend?.length" class="bi-card p-4 mb-4">
        <h3 class="text-sm font-semibold text-slate-700 mb-3">月度转化趋势</h3>
        <NDataTable
          :columns="[
            { title: '首购月份', key: 'month' },
            { title: '7日复购率', key: 'day7_rate', align: 'right', render: (row: any) => `${(row.day7_rate * 100).toFixed(1)}%` },
            { title: '30日复购率', key: 'day30_rate', align: 'right', render: (row: any) => `${(row.day30_rate * 100).toFixed(1)}%` },
            { title: '90日复购率', key: 'day90_rate', align: 'right', render: (row: any) => `${(row.day90_rate * 100).toFixed(1)}%` },
          ]"
          :data="data.monthly_trend"
          :pagination="false"
          size="small"
          striped
        />
      </div>
    </template>
  </div>
</template>

<style scoped>
.new-customer-tab {
  padding-top: 8px;
}
</style>
