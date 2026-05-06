<script setup lang="ts">
import { computed, h, ref, toValue } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NTooltip, NSelect } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useFilterStore } from '@/stores/filterStore'
import { fetchMarketBasket } from '@/api/category'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import DataTablePro from '@/components/DataTablePro.vue'

const props = defineProps<{
  dataQualityNote?: string
  /** 品类列表（从 distributionData 获取，按GSV降序） */
  categoryOptions?: string[]
}>()

const filterStore = useFilterStore()
import { LOW_PRICE_CHANNELS } from '@/constants/channels'

// 目标品类选择
const targetCategory = ref<string | null>(null)

const initCategory = computed(() => {
  if (targetCategory.value) return targetCategory.value
  return props.categoryOptions?.[0] || 'B5面膜'
})

const selectOptions = computed(() => {
  const fromProps = props.categoryOptions || []
  return fromProps.map(c => ({ label: c, value: c }))
})

const queryParams = computed(() => ({
  start_date: filterStore.dateRange[0],
  end_date: filterStore.dateRange[1],
  level: 'class',
  target_category: initCategory.value,
  channel: filterStore.channel === '全店' ? undefined : filterStore.channel,
  exclude_channels: filterStore.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined,
}))

const {
  data,
  isLoading,
  error,
  refetch,
} = useQuery({
  queryKey: computed(() => ['market-basket', { ...toValue(queryParams) }]),
  queryFn: () => fetchMarketBasket(toValue(queryParams)),
  staleTime: 60_000,
})

// ─── 表格列 ──────────────────────────────────────────────────────
const tableColumns = computed<DataTableColumns<any>>(() => [
  {
    title: '关联品类',
    key: 'category_name',
    width: 140,
    fixed: 'left',
  },
  {
    title: '关联订单数',
    key: 'co_order_count',
    align: 'right',
    render: (row: any) => row.current.co_order_count.toLocaleString(),
  },
  {
    title: 'Confidence',
    key: 'confidence',
    align: 'right',
    render: (row: any) => (row.current.confidence * 100).toFixed(1) + '%',
  },
  {
    title: 'Lift',
    key: 'lift',
    align: 'right',
    render: (row: any) => row.current.lift.toFixed(2),
  },
  {
    title: '去年同期 Confidence',
    key: 'prev_confidence',
    align: 'right',
    render: (row: any) => {
      if (!row.previous) return '—'
      return (row.previous.confidence * 100).toFixed(1) + '%'
    },
  },
  {
    title: '去年同期 Lift',
    key: 'prev_lift',
    align: 'right',
    render: (row: any) => {
      if (!row.previous) return '—'
      return row.previous.lift.toFixed(2)
    },
  },
  {
    title: 'Confidence变化',
    key: 'confidence_change',
    align: 'right',
    render: (row: any) => {
      if (row.confidence_change == null) return '—'
      const v = row.confidence_change * 100
      const color = v > 0 ? 'text-red-500' : v < 0 ? 'text-green-500' : 'text-slate-500'
      const sign = v > 0 ? '+' : ''
      return h('span', { class: color }, `${sign}${v.toFixed(1)}pp`)
    },
  },
  {
    title: '排名变化',
    key: 'rank_change',
    align: 'right',
    render: (row: any) => {
      if (row.rank_change == null) return '—'
      const v = row.rank_change
      const color = v < 0 ? 'text-red-500' : v > 0 ? 'text-green-500' : 'text-slate-500'
      const sign = v > 0 ? '+' : ''
      return h('span', { class: color }, `${sign}${v}`)
    },
  },
])

const tableData = computed(() => data.value?.items ?? [])

// 指标说明
const METRIC_TIPS = {
  confidence: '买目标品类的人中，同时买该品类的比例',
  lift: '关联强度 >1 表示正相关，<1 表示负相关',
}
</script>

<template>
  <div class="space-y-5">
    <!-- Data Quality Hint -->
    <div class="flex items-center justify-end gap-2">
      <n-tooltip trigger="hover" v-if="dataQualityNote || data?.data_quality_note">
        <template #trigger>
          <span class="inline-flex items-center justify-center w-4 h-4 rounded-full bg-slate-200 text-slate-500 text-[10px] font-bold cursor-help">i</span>
        </template>
        <span class="text-xs">{{ data?.data_quality_note || dataQualityNote }}</span>
      </n-tooltip>
    </div>

    <ErrorState v-if="error" :message="(error as Error).message" @retry="refetch()" />
    <LoadingState v-else-if="isLoading" />

    <template v-else-if="data">
      <!-- 目标品类选择 + 指标卡 -->
      <div class="bi-card p-4">
        <div class="flex items-center justify-between mb-4">
          <div>
          <h3 class="text-sm font-semibold text-slate-800 mb-0.5">购物篮分析</h3>
          <p class="text-[11px] text-slate-500">分析购买目标品类的用户，同单还购买了哪些品类</p>
          <p class="text-[11px] text-slate-400 mt-0.5">同一笔订单里的品类组合——指导组合装设计、关联推荐和满减门槛设置</p>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-xs text-slate-500">目标品类:</span>
            <n-select
              v-model:value="targetCategory"
              :options="selectOptions"
              size="small"
              clearable
              filterable
              tag
              placeholder="输入或选择品类"
              style="width: 200px"
            />
          </div>
        </div>

        <!-- 指标卡 -->
        <div class="grid grid-cols-4 gap-3 mb-4">
          <div class="bi-card p-3 text-center">
            <div class="text-[11px] text-slate-500 mb-1">目标品类订单数</div>
            <div class="text-[22px] font-semibold text-slate-900 tracking-tight tabular-nums">{{ data.target_order_count.toLocaleString() }}</div>
          </div>
          <div class="bi-card p-3 text-center">
            <div class="text-[11px] text-slate-500 mb-1">总订单数</div>
            <div class="text-[22px] font-semibold text-slate-900 tracking-tight tabular-nums">{{ data.total_orders.toLocaleString() }}</div>
          </div>
          <div class="bi-card p-3 text-center">
            <div class="text-[11px] text-slate-500 mb-1">当期</div>
            <div class="text-sm font-semibold text-slate-700 mt-1.5">{{ data.period_label }}</div>
          </div>
          <div class="bi-card p-3 text-center">
            <div class="text-[11px] text-slate-500 mb-1">去年同期</div>
            <div class="text-sm font-semibold text-slate-700 mt-1.5">{{ data.yoy_period_label || '—' }}</div>
          </div>
        </div>

        <!-- 指标说明 -->
        <div class="flex gap-4 text-[11px] text-slate-500 mb-3">
          <span>
            <span class="font-medium">Confidence:</span> {{ METRIC_TIPS.confidence }}
          </span>
          <span>
            <span class="font-medium">Lift:</span> {{ METRIC_TIPS.lift }}
          </span>
        </div>
      </div>

      <!-- 关联品类表格 -->
      <div class="bi-card p-4">
        <h3 class="text-sm font-semibold text-slate-800 mb-0.5">关联品类 Top N</h3>
        <p class="text-[11px] text-slate-500 mb-1">按关联订单数排序，展示当期与去年同期对比</p>
        <p class="text-[11px] text-slate-400 mb-3">Confidence=买目标品类的人中同时买该品类的比例；Lift>1表示正相关，<1表示负相关</p>
        <DataTablePro
          :columns="tableColumns"
          :data="tableData"
          :pagination="{ pageSize: 15 }"
          :scroll-x="900"
        />
      </div>
    </template>

    <EmptyState v-else description="暂无数据" />
  </div>
</template>
