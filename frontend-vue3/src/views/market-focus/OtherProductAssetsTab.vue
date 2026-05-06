<script setup lang="ts">
import { computed, toValue } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { fetchOtherProductAssets } from '@/api/marketFocus'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import LineChart from '@/components/LineChart.vue'

const props = defineProps<{ weeks: number }>()

// 折线图：各产品资产总量 by 周
const chartWeekLabels = computed(() => data.value?.products[0]?.weeks.map(w => w.week_label) ?? [])

const productSeries = computed(() => {
  const products = data.value?.products
  if (!products?.length) return []
  return products.map(p => ({
    name: p.name,
    data: p.weeks.map(w => w.total),
  }))
})

const queryParams = computed(() => ({ weeks: props.weeks }))

const { data, isLoading, error, refetch } = useQuery({
  queryKey: computed(() => ['other-product-assets', { ...toValue(queryParams) }]),
  queryFn: () => {
    const p = toValue(queryParams)
    return fetchOtherProductAssets(p.weeks)
  },
  staleTime: 5 * 60 * 1000,
})

// ─────────────────────────────────────────────────────────────
// 宽表行类型
// ─────────────────────────────────────────────────────────────
type WideRow = {
  week_label: string
  isChangeRow?: boolean
} & Record<string, number | string | boolean | undefined>

const productSubColumns = [
  { key: 'total', label: '资产总量' },
  { key: 'shallow_grass', label: '浅种草' },
  { key: 'deep_grass', label: '深种草' },
  { key: 'initial', label: '首购资产' },
  { key: 'repurchase', label: '复购资产' },
  { key: 'lian_dai', label: '连带资产' },
] as const

type SubKey = typeof productSubColumns[number]['key']

/** 转换为「时间为行，产品为列」的宽格式 */
const wideTable = computed((): WideRow[] => {
  const products = data.value?.products
  if (!products?.length) return []

  const weekCount = products[0].weeks.length
  const rows: WideRow[] = []

  for (let i = 0; i < weekCount; i++) {
    const row: WideRow = {
      week_label: products[0].weeks[i].week_label,
    }
    for (const product of products) {
      const w = product.weeks[i]
      for (const col of productSubColumns) {
        row[`${product.name}_${col.key}`] = w[col.key as SubKey] as number
      }
    }
    rows.push(row)
  }

  // 本周对比上周
  const changeRow: WideRow = { week_label: '本周对比上周' }
  for (const product of products) {
    const latest = product.weeks[weekCount - 1]
    for (const col of productSubColumns) {
      changeRow[`${product.name}_${col.key}`] = latest[`${col.key}_change` as `${SubKey}_change`] as number
    }
  }
  changeRow.isChangeRow = true
  rows.push(changeRow)

  return rows
})

// 格式化
function fmtInt(v: number): string {
  return v.toLocaleString()
}

function fmtChange(v: number): string {
  const abs = Math.abs(v)
  const sign = v > 0 ? '+' : ''
  // 超过5位数（10000以上）显示万单位
  if (abs >= 10000) {
    return `${sign}${(abs / 10000).toFixed(1)}万`
  }
  return `${sign}${v.toLocaleString()}`
}

function changeClass(v: number): string {
  if (v > 0) return 'text-rose-500'
  if (v < 0) return 'text-emerald-500'
  return 'text-slate-400'
}

function rowBg(isChange: boolean, idx: number): string {
  if (isChange) return 'bg-violet-50/50'
  return idx % 2 === 0 ? 'bg-white' : 'bg-slate-50/80'
}
</script>

<template>
  <div>
    <LoadingState v-if="isLoading" description="正在加载单品资产-其他产品数据..." />
    <ErrorState v-else-if="error" :message="String(error)" @retry="refetch" />
    <EmptyState v-else-if="!data?.products?.length" description="暂无单品资产-其他产品数据" />

    <div v-else>
      <!-- 折线图：各产品资产总量趋势 -->
      <div class="bi-card p-4 mb-6">
        <div class="mb-0.5">
          <h3 class="text-sm font-semibold text-slate-800">各产品资产总量趋势</h3>
          <p class="text-[11px] text-slate-500">DMP单品人群周度流转 — 其他产品资产总量变化</p>
        </div>
        <LineChart
          :x-axis-data="chartWeekLabels"
          :series="productSeries"
          :y-axis="{ name: '人数', formatter: (v: number) => v >= 10000 ? (v / 10000).toFixed(1) + '万' : String(v) }"
          height="280px"
        />
      </div>

      <div class="overflow-x-auto rounded-lg border border-slate-200">
        <table class="w-full text-sm">
        <thead>
          <!-- 产品名表头 -->
          <tr class="border-b border-slate-200 bg-slate-50">
            <th class="text-left py-3 px-3 text-slate-600 font-semibold sticky left-0 bg-slate-50 z-10 min-w-[100px]">时间</th>
            <th
              v-for="product in data.products"
              :key="product.name"
              class="text-center py-3 px-2 text-slate-600 font-semibold"
              :colspan="6"
            >{{ product.name }}</th>
          </tr>
          <!-- 子列名表头 -->
          <tr class="border-b border-slate-200 bg-slate-50/80">
            <th class="text-left py-2 px-3 text-slate-400 font-medium sticky left-0 bg-slate-50/80 z-10"></th>
            <template v-for="product in data.products" :key="product.name">
              <th
                v-for="col in productSubColumns"
                :key="`${product.name}-${col.key}`"
                class="text-right py-2 px-2 text-slate-400 text-xs font-medium"
              >{{ col.label }}</th>
            </template>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, idx) in wideTable"
            :key="row.week_label"
            :class="['border-b border-slate-100', rowBg(!!row.isChangeRow, idx)]"
          >
            <td
              class="py-2.5 px-3 font-medium sticky left-0 z-10 min-w-[100px]"
              :class="row.isChangeRow ? 'text-slate-500 bg-violet-50/50' : `text-slate-900 ${rowBg(false, idx)}`"
            >{{ row.week_label }}</td>
            <template v-for="product in data.products" :key="product.name">
              <td
                v-for="col in productSubColumns"
                :key="`${product.name}-${col.key}`"
                class="py-2.5 px-2 text-right tabular-nums"
                :class="row.isChangeRow ? changeClass(row[`${product.name}_${col.key}`] as number) : 'text-slate-900'"
              >
                {{ row.isChangeRow ? fmtChange(row[`${product.name}_${col.key}`] as number) : fmtInt(row[`${product.name}_${col.key}`] as number) }}
              </td>
            </template>
          </tr>
        </tbody>
      </table>
      </div>
    </div>
  </div>
</template>
