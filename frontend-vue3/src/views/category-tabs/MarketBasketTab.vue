<script setup lang="ts">
import { computed, h, ref, toValue, watch } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NTooltip, NSelect, NInputNumber, NButton } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useFilterStore } from '@/stores/filterStore'
import { fetchMarketBasket } from '@/api/category'
import { exportSheetToXlsx } from '@/utils/exportXlsx'
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

// 目标品类选择 —— 默认同步 props.categoryOptions[0]
const targetCategory = ref<string | null>(null)

// 当 categoryOptions 传入时，自动选中第一个作为默认值
watch(() => props.categoryOptions, (opts) => {
  if (opts && opts.length > 0 && !targetCategory.value) {
    targetCategory.value = opts[0]
  }
}, { immediate: true })

const initCategory = computed(() => {
  return targetCategory.value || props.categoryOptions?.[0] || 'B5面膜'
})

const selectOptions = computed(() => {
  const fromProps = props.categoryOptions || []
  return fromProps.map(c => ({ label: c, value: c }))
})

// ─── 排序与过滤 ──────────────────────────────────────────────────
const sortBy = ref<string>('co_order_count')
const sortOptions = [
  { label: '关联订单数', value: 'co_order_count' },
  { label: '置信度', value: 'confidence' },
  { label: '提升度', value: 'lift' },
  { label: '连带人均消费', value: 'co_aus' },
  { label: '消费提升', value: 'gsv_lift' },
]

// 最小支持度（百分比 0-100，内部转为 0-1 做过滤）
const minSupportPercent = ref<number>(0)

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

// ─── 表格列（全部居中，表头带公式 tooltip）──────────────────────────
const tableColumns = computed<DataTableColumns<any>>(() => [
  {
    title: () => hColTip('关联品类', '同单中与目标品类一起出现的其他品类'),
    key: 'category_name',
    width: 140,
    fixed: 'left',
    align: 'center',
  },
  {
    title: () => hColTip('关联订单数', '同时包含目标品类和该品类的订单数量'),
    key: 'co_order_count',
    align: 'center',
    render: (row: any) => row.current.co_order_count.toLocaleString(),
  },
  {
    title: () => hColTip('支持度', '公式：关联订单数÷总订单数\n作用：衡量组合出现的普遍程度，越高越常见'),
    key: 'support',
    align: 'center',
    render: (row: any) => (row.current.support * 100).toFixed(2) + '%',
  },
  {
    title: () => hColTip('置信度', '公式：关联订单数÷目标品类订单数\n作用：买目标品类的用户中，同时买该品类的比例'),
    key: 'confidence',
    align: 'center',
    render: (row: any) => (row.current.confidence * 100).toFixed(1) + '%',
  },
  {
    title: () => hColTip('提升度', '公式：置信度÷该品类独立购买概率\n作用：>1 正向关联，越高说明两个品类越应该搭着卖'),
    key: 'lift',
    align: 'center',
    render: (row: any) => {
      const lift = row.current.lift
      return h(NTooltip, { trigger: 'hover' }, {
        trigger: () => h('span', lift.toFixed(2)),
        default: () => h('span', { class: 'text-xs' }, liftInterpret(lift)),
      })
    },
  },
  {
    title: () => hColTip('连带人均消费', '公式：连带GSV÷连带购买人数\n即同时买这两个品类的人均消费金额'),
    key: 'co_aus',
    align: 'center',
    render: (row: any) => '¥' + row.current.co_aus.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  },
  {
    title: () => hColTip('消费提升', '公式：连带人均消费÷目标品类人均消费\n作用：>1 说明连带后人均消费更高，数字越大提升越明显'),
    key: 'gsv_lift',
    align: 'center',
    render: (row: any) => row.current.gsv_lift.toFixed(2) + 'x',
  },
  {
    title: () => hColTip('连带GSV', '同时包含目标品类和该品类的所有订单金额总和'),
    key: 'co_gsv',
    align: 'center',
    render: (row: any) => '¥' + row.current.co_gsv.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  },
  {
    title: '去年同期\n置信度',
    key: 'prev_confidence',
    align: 'center',
    render: (row: any) => {
      if (!row.previous) return '—'
      return (row.previous.confidence * 100).toFixed(1) + '%'
    },
  },
  {
    title: '去年同期\n提升度',
    key: 'prev_lift',
    align: 'center',
    render: (row: any) => {
      if (!row.previous) return '—'
      return row.previous.lift.toFixed(2)
    },
  },
  {
    title: '去年同期\n连带GSV',
    key: 'prev_co_gsv',
    align: 'center',
    render: (row: any) => {
      if (!row.previous) return '—'
      return '¥' + row.previous.co_gsv.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    },
  },
  {
    title: '置信度\n变化',
    key: 'confidence_change',
    align: 'center',
    render: (row: any) => {
      if (row.confidence_change == null) return '—'
      const v = row.confidence_change * 100
      const color = v > 0 ? 'text-red-500' : v < 0 ? 'text-green-500' : 'text-slate-500'
      const sign = v > 0 ? '+' : ''
      return h('span', { class: color }, `${sign}${v.toFixed(1)}pp`)
    },
  },
  {
    title: '提升度\n变化',
    key: 'lift_change',
    align: 'center',
    render: (row: any) => {
      if (row.lift_change == null) return '—'
      const v = row.lift_change
      const color = v > 0 ? 'text-red-500' : v < 0 ? 'text-green-500' : 'text-slate-500'
      const sign = v > 0 ? '+' : ''
      return h('span', { class: color }, `${sign}${v.toFixed(2)}`)
    },
  },
  {
    title: '连带GSV\n变化',
    key: 'gsv_change',
    align: 'center',
    render: (row: any) => {
      if (row.gsv_change == null) return '—'
      const v = row.gsv_change
      const color = v > 0 ? 'text-red-500' : v < 0 ? 'text-green-500' : 'text-slate-500'
      const sign = v > 0 ? '+' : ''
      return h('span', { class: color }, `${sign}¥${v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`)
    },
  },
  {
    title: '排名\n变化',
    key: 'rank_change',
    align: 'center',
    render: (row: any) => {
      if (row.rank_change == null) return '—'
      const v = row.rank_change
      const color = v < 0 ? 'text-green-500' : v > 0 ? 'text-red-500' : 'text-slate-500'
      const sign = v > 0 ? '+' : ''
      return h('span', { class: color }, `${sign}${v}`)
    },
  },
])

// 表头 tooltip 辅助函数
function hColTip(label: string, tip: string) {
  return h(NTooltip, { trigger: 'hover' }, {
    trigger: () => h('span', { style: 'cursor: help; border-bottom: 1px dashed #cbd5e1;' }, label),
    default: () => h('div', { class: 'text-xs max-w-[260px] whitespace-pre-line' }, tip),
  })
}

// ─── 排序与过滤后的数据 ──────────────────────────────────────────
const sortedTableData = computed(() => {
  let items = data.value?.items ?? []

  // 最小支持度过滤（百分比转小数）
  const minSupport = minSupportPercent.value / 100
  if (minSupport > 0) {
    items = items.filter((row: any) => row.current.support >= minSupport)
  }

  // 前端排序
  const sortKey = sortBy.value as string
  const sorted = [...items].sort((a: any, b: any) => {
    const av = a.current[sortKey] ?? 0
    const bv = b.current[sortKey] ?? 0
    return bv - av  // 降序
  })

  return sorted
})

// ─── Lift 业务化解读 ─────────────────────────────────────────────
function liftInterpret(lift: number): string {
  if (lift > 3) return `强关联：一起买的概率是单独购买的 ${lift.toFixed(1)} 倍`
  if (lift > 1.5) return `中等关联：一起买的概率是单独购买的 ${lift.toFixed(1)} 倍`
  if (lift > 1) return `弱关联：一起买的概率是单独购买的 ${lift.toFixed(1)} 倍`
  if (Math.abs(lift - 1) < 0.01) return '无关联：一起买和单独买的概率相同'
  return `负关联：一起买的概率比单独购买低 ${((1 - lift) * 100).toFixed(0)}%`
}

// ─── Excel 导出 ──────────────────────────────────────────────────
function handleExport() {
  const items = sortedTableData.value
  if (!items.length) return

  const rows = items.map((row: any) => ({
    category_name: row.category_name,
    co_order_count: row.current.co_order_count,
    support: row.current.support,
    confidence: row.current.confidence,
    lift: row.current.lift,
    co_aus: row.current.co_aus,
    gsv_lift: row.current.gsv_lift,
    co_gsv: row.current.co_gsv,
    prev_confidence: row.previous?.confidence ?? null,
    prev_lift: row.previous?.lift ?? null,
    prev_co_gsv: row.previous?.co_gsv ?? null,
    confidence_change: row.confidence_change,
    lift_change: row.lift_change,
    gsv_change: row.gsv_change,
    rank_change: row.rank_change,
  }))

  exportSheetToXlsx(
    `连带分析_${data.value?.target_category || '品类'}_${data.value?.period_label || ''}`,
    '关联品类',
    [
      { header: '关联品类', key: 'category_name', width: 16 },
      { header: '关联订单数', key: 'co_order_count', width: 12 },
      { header: '支持度', key: 'support', width: 10, numFmt: '0.00%' },
      { header: '置信度', key: 'confidence', width: 10, numFmt: '0.00%' },
      { header: '提升度', key: 'lift', width: 10 },
      { header: '连带人均消费', key: 'co_aus', width: 14, numFmt: '#,##0.00' },
      { header: '消费提升', key: 'gsv_lift', width: 12 },
      { header: '连带GSV', key: 'co_gsv', width: 14, numFmt: '#,##0.00' },
      { header: '去年同期置信度', key: 'prev_confidence', width: 14, numFmt: '0.00%' },
      { header: '去年同期提升度', key: 'prev_lift', width: 14 },
      { header: '去年同期连带GSV', key: 'prev_co_gsv', width: 16, numFmt: '#,##0.00' },
      { header: '置信度变化(pp)', key: 'confidence_change', width: 14 },
      { header: '提升度变化', key: 'lift_change', width: 12 },
      { header: '连带GSV变化', key: 'gsv_change', width: 14, numFmt: '#,##0.00' },
      { header: '排名变化', key: 'rank_change', width: 10 },
    ],
    rows,
  )
}

// 指标说明（通俗易懂版）
const METRIC_TIPS = {
  support: '关联订单数÷总订单数。越高说明这个组合越常见',
  confidence: '关联订单数÷目标品类订单数。越高说明买了目标品类的用户越可能同时买它',
  lift: '一起买的概率÷单独买的概率。>1 正向关联，越高越应该搭着卖',
  co_aus: '连带GSV÷连带购买人数。即同时买这两个品类的人均消费',
  gsv_lift: '连带人均消费÷目标品类人均消费。>1 说明连带后人均消费更高',
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
            <div class="text-[11px] text-slate-500 mb-1">目标品类人均消费</div>
            <div class="text-[22px] font-semibold text-slate-900 tracking-tight tabular-nums">
              ¥{{ (data.items[0]?.current.target_aus ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}
            </div>
          </div>
          <div class="bi-card p-3 text-center">
            <div class="text-[11px] text-slate-500 mb-1">当期</div>
            <div class="text-sm font-semibold text-slate-700 mt-1.5">{{ data.period_label }}</div>
          </div>
        </div>

        <!-- 指标说明 -->
        <div class="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-500 mb-3">
          <span>
            <span class="font-medium">支持度:</span> {{ METRIC_TIPS.support }}
          </span>
          <span>
            <span class="font-medium">置信度:</span> {{ METRIC_TIPS.confidence }}
          </span>
          <span>
            <span class="font-medium">提升度:</span> {{ METRIC_TIPS.lift }}
          </span>
          <span>
            <span class="font-medium">消费提升:</span> {{ METRIC_TIPS.gsv_lift }}
          </span>
        </div>
      </div>

      <!-- 关联品类表格 -->
      <div class="bi-card p-4">
        <div class="flex items-center justify-between mb-3">
          <div>
            <h3 class="text-sm font-semibold text-slate-800 mb-0.5">关联品类 Top N</h3>
            <p class="text-[11px] text-slate-500">支持排序切换和最小支持度过滤，展示当期与去年同期对比</p>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-xs text-slate-500">排序:</span>
            <n-select
              v-model:value="sortBy"
              :options="sortOptions"
              size="small"
              style="width: 130px"
            />
            <span class="text-xs text-slate-500 ml-2">最小支持度(%):</span>
            <n-input-number
              v-model:value="minSupportPercent"
              :min="0"
              :max="100"
              :step="0.1"
              size="small"
              style="width: 90px"
              placeholder="0"
            />
            <NButton size="tiny" @click="handleExport">📊 导出Excel</NButton>
          </div>
        </div>

        <p class="text-[11px] text-slate-400 mb-3">
          <span class="font-medium">支持度</span>=关联订单数÷总订单数，越高组合越常见；
          <span class="font-medium">置信度</span>=关联订单数÷目标品类订单数，越高连带概率越大；
          <span class="font-medium">提升度</span>=一起买的概率÷单独买的概率，&gt;1 正向关联；
          <span class="font-medium">消费提升</span>=连带人均消费÷目标品类人均消费，&gt;1 说明连带后人均消费更高
        </p>

        <DataTablePro
          :columns="tableColumns"
          :data="sortedTableData"
          :pagination="false"
          :scroll-x="1400"
          :max-height="520"
        />
      </div>
    </template>

    <EmptyState v-else description="暂无数据" />
  </div>
</template>
