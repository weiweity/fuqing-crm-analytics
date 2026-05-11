<script setup lang="ts">
import { computed, ref, toValue } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NTooltip, NSelect } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useFilterStore } from '@/stores/filterStore'
import { fetchCategoryFlow } from '@/api/category'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import DataTablePro from '@/components/DataTablePro.vue'
import { CHART_COLORS } from '@/composables/useChartTheme'

const props = defineProps<{
  dataQualityNote?: string
}>()

const filterStore = useFilterStore()

// 品类流转tab默认排除的渠道（避免赠品&0.01、其他渠道污染流转数据）
const CATEGORY_FLOW_EXCLUDED_CHANNELS = ['赠品&0.01', '其他']

const windowDays = ref<number>(90)
const targetCategory = ref<string | null>(null)

// 流转矩阵显示模式：百分比(默认) / 数值
const matrixDisplayMode = ref<'percentage' | 'value'>('percentage')

const targetCategoryOptions = computed(() => {
  if (!data.value?.sankey_data?.nodes) return []
  const { nodes, links } = data.value.sankey_data
  // 按节点总流量（流入+流出）降序，高流量优先展示
  const nodeFlow: Record<string, number> = {}
  for (const l of links) {
    nodeFlow[l.source] = (nodeFlow[l.source] || 0) + l.value
    nodeFlow[l.target] = (nodeFlow[l.target] || 0) + l.value
  }
  return nodes
    .map((n) => ({ label: n.name, value: n.name, flow: nodeFlow[n.name] || 0 }))
    .sort((a, b) => b.flow - a.flow)
})

const queryParams = computed(() => ({
  start_date: filterStore.dateRange[0],
  end_date: filterStore.dateRange[1],
  level: 'class',
  window_days: windowDays.value,
  channel: filterStore.channel === '全店' ? undefined : filterStore.channel,
  exclude_channels: CATEGORY_FLOW_EXCLUDED_CHANNELS,
  target_category: targetCategory.value || undefined,
}))

const {
  data,
  isLoading,
  error,
  refetch,
} = useQuery({
  queryKey: computed(() => ['category-flow', { ...toValue(queryParams) }]),
  queryFn: () => fetchCategoryFlow(toValue(queryParams)),
  staleTime: 60_000,
})

const WINDOW_OPTIONS = [
  { label: '30天', value: 30 },
  { label: '90天', value: 90 },
  { label: '180天', value: 180 },
  { label: '365天', value: 365 },
]

// ─── 检测并打破有向环（桑基图要求DAG）─────────────────────────────
function breakCycles(links: { source: string; target: string; value: number }[]) {
  const result = [...links]
  while (true) {
    const adj = new Map<string, string[]>()
    const linkMap = new Map<string, { source: string; target: string; value: number }>()
    for (const link of result) {
      if (!adj.has(link.source)) adj.set(link.source, [])
      adj.get(link.source)!.push(link.target)
      linkMap.set(`${link.source}->${link.target}`, link)
    }
    const visited = new Set<string>()
    let linkToRemove: { source: string; target: string; value: number } | null = null

    function dfs(node: string, path: string[], rec: Set<string>): typeof linkToRemove {
      visited.add(node)
      rec.add(node)
      path.push(node)
      for (const neighbor of adj.get(node) || []) {
        if (!visited.has(neighbor)) {
          const found = dfs(neighbor, path, rec)
          if (found) return found
        } else if (rec.has(neighbor)) {
          const cycleStart = path.indexOf(neighbor)
          const cycleNodes = path.slice(cycleStart)
          let minLink: typeof linkToRemove = null
          let minValue = Infinity
          for (let i = 0; i < cycleNodes.length; i++) {
            const src = cycleNodes[i]
            const tgt = cycleNodes[(i + 1) % cycleNodes.length]
            const link = linkMap.get(`${src}->${tgt}`)
            if (link && link.value < minValue) {
              minValue = link.value
              minLink = link
            }
          }
          return minLink
        }
      }
      path.pop()
      rec.delete(node)
      return null
    }

    for (const node of adj.keys()) {
      if (!visited.has(node)) {
        linkToRemove = dfs(node, [], new Set())
        if (linkToRemove) break
      }
    }
    if (!linkToRemove) break
    const idx = result.findIndex((l) => l === linkToRemove)
    if (idx >= 0) result.splice(idx, 1)
  }
  return result
}

// ─── Sankey Chart ────────────────────────────────────────────────
const sankeyOption = computed(() => {
  if (!data.value?.sankey_data?.nodes?.length) return {}
  const { nodes, links } = data.value.sankey_data

  // 打破环，确保DAG
  const acyclicLinks = breakCycles(links)

  // 过滤弱连接：只保留 value >= 5 且 >= 最大值的2% 的link，避免线太细太密
  const maxValue = Math.max(...acyclicLinks.map((l) => l.value), 1)
  const threshold = Math.max(5, maxValue * 0.02)
  const filteredLinks = acyclicLinks.filter((l) => l.value >= threshold)

  // 用 index 映射解决节点名称重复问题
  const nodeNames = nodes.map((n) => n.name)
  const nodeNameIdx: Record<string, number> = {}
  nodeNames.forEach((name, i) => { nodeNameIdx[name] = i })

  const sankeyLinks = filteredLinks.map((l) => ({
    source: nodeNameIdx[l.source] ?? l.source,
    target: nodeNameIdx[l.target] ?? l.target,
    value: l.value,
  }))

  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      padding: [10, 14],
      textStyle: { color: '#0f172a', fontSize: 12 },
      extraCssText: 'box-shadow: 0 4px 12px -2px rgba(0,0,0,0.08); border-radius: 4px;',
      formatter: (params: any) => {
        if (params.dataType === 'edge') {
          const srcName = nodes[params.data.source]?.name ?? params.data.source
          const tgtName = nodes[params.data.target]?.name ?? params.data.target
          return `${srcName} → ${tgtName}<br/>流转人数: ${params.data.value.toLocaleString()}`
        }
        return params.name
      },
    },
    grid: { left: 8, right: 8, top: 8, bottom: 8 },
    series: [
      {
        type: 'sankey',
        nodeGap: 20,
        nodeWidth: 24,
        nodeAlign: 'justify',
        emphasis: { focus: 'adjacency' },
        lineStyle: {
          color: 'gradient',
          curveness: 0.4,
          opacity: 0.6,
        },
        itemStyle: { borderWidth: 1, borderColor: '#fff', borderRadius: 4 },
        label: {
          fontSize: 11,
          color: '#334155',
          formatter: (p: any) => {
            const name = p.name as string
            return name.length > 8 ? name.slice(0, 7) + '…' : name
          },
        },
        data: nodes.map((n) => ({
          name: n.name,
          itemStyle: {
            color: n.name === '流失'
              ? '#ef4444'
              : n.name === '其他'
                ? '#94a3b8'
                : CHART_COLORS[nodeNameIdx[n.name] % CHART_COLORS.length],
          },
        })),
        links: sankeyLinks,
        animation: false,
      },
    ],
  }
})

// ─── Flow Matrix Table ────────────────────────────────────────────
const matrixColumns = computed<DataTableColumns<any>>(() => {
  if (!data.value?.matrix) return []
  const { targets } = data.value.matrix

  const cols: DataTableColumns<any> = [
    {
      title: '来源↓ / 目标→',
      key: 'source',
      width: 140,
      fixed: 'left',
      align: 'center',
    },
  ]

  targets.forEach((t, i) => {
    cols.push({
      title: t,
      key: `t_${i}`,
      width: 90,
      align: 'right',
      className: 'bi-cell-number',
      render: (row: any) => {
        const val = row[`t_${i}`]
        if (val == null || val === 0) return '—'
        if (matrixDisplayMode.value === 'percentage') {
          return val + '%'
        }
        return val.toLocaleString()
      },
    })
  })

  return cols
})

const matrixData = computed(() => {
  if (!data.value?.matrix) return []
  const { sources, targets, matrix, row_totals } = data.value.matrix

  return sources.map((src, si) => {
    const row: Record<string, any> = { source: src }
    const rowTotal = row_totals?.[si] ?? 0

    targets.forEach((_, ti) => {
      const rawVal = matrix[si]?.[ti] ?? 0
      if (matrixDisplayMode.value === 'percentage' && rowTotal > 0) {
        // 行百分比，保留1位小数
        row[`t_${ti}`] = rawVal === 0 ? 0 : Math.round((rawVal / rowTotal) * 1000) / 10
      } else {
        row[`t_${ti}`] = rawVal
      }
    })
    return row
  })
})

// ─── Temporal Association ─────────────────────────────────────────
const ASSOC_COLS: DataTableColumns<any> = [
  { title: '品类', key: 'category_name', width: 140, fixed: 'left' },
  {
    title: '关联人数',
    key: 'user_count',
    align: 'right',
    render: (r) => r.user_count.toLocaleString(),
  },
  {
    title: '订单数',
    key: 'order_count',
    align: 'right',
    render: (r) => r.order_count.toLocaleString(),
  },
  {
    title: '关联GMV',
    key: 'gsv',
    align: 'right',
    render: (r) => (r.gsv / 10000).toFixed(1) + '万',
  },
  {
    title: '占目标用户比例',
    key: 'ratio',
    align: 'right',
    render: (r) => (r.ratio * 100).toFixed(1) + '%',
  },
  {
    title: '平均间隔天数',
    key: 'avg_days_gap',
    align: 'right',
    render: (r) => r.avg_days_gap.toFixed(1) + '天',
  },
]
</script>

<template>
  <div class="space-y-5">
    <!-- Data Quality Hint + Stale Warning -->
    <div class="flex items-center justify-end gap-2">
      <span
        v-if="data?.data_stale"
        class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-amber-100 text-amber-700"
      >
        ⚠ 数据更新中
      </span>
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
      <!-- 时间窗口选择 + 桑基图 -->
      <div class="bi-card p-4">
        <div class="flex items-center justify-between mb-3">
          <div>
            <h3 class="text-sm font-semibold text-slate-800 mb-0.5">品类流转桑基图</h3>
            <p class="text-[11px] text-slate-500">首购品类 → 次购品类的用户流转，宽度∝流转人数</p>
            <p class="text-[11px] text-slate-400 mt-0.5">用户首单买了A品类后，下一单流向了B还是C？线条越宽=流转人数越多，帮你发现品类间的引流和承接关系</p>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-xs text-slate-500">目标品类:</span>
            <n-select
              v-model:value="targetCategory"
              :options="targetCategoryOptions"
              size="small"
              clearable
              filterable
              placeholder="选择品类查看前后置关联"
              style="width: 180px"
            />
            <span class="text-xs text-slate-500">窗口:</span>
            <n-select
              v-model:value="windowDays"
              :options="WINDOW_OPTIONS"
              size="small"
              style="width: 100px"
            />
          </div>
        </div>
        <EmptyState
          v-if="!data.sankey_data?.nodes?.length"
          description="当前条件下无流转数据"
        />
        <EChartsWrapper v-else :option="sankeyOption" height="480px" />
      </div>

      <!-- 时序关联分析 -->
      <template v-if="data?.target_category">
        <div class="bi-card p-4">
          <h3 class="text-sm font-semibold text-slate-800 mb-0.5">
            买 {{ data.target_category }} 之前买了什么
          </h3>
          <p class="text-[11px] text-slate-500 mb-1">购买目标品类之前，该品类用户的购买品类分布</p>
          <p class="text-[11px] text-slate-400 mb-3">谁是引流品类？——如果买B5面膜的人之前大量买了洗面奶，说明洗面奶是面膜的流量入口</p>
          <DataTablePro
            :columns="ASSOC_COLS"
            :data="data.pre_purchase ?? []"
            :pagination="{ pageSize: 10 }"
            :scroll-x="800"
          />
        </div>
        <div class="bi-card p-4">
          <h3 class="text-sm font-semibold text-slate-800 mb-0.5">
            买 {{ data.target_category }} 之后买了什么
          </h3>
          <p class="text-[11px] text-slate-500 mb-1">购买目标品类之后，该品类用户的购买品类分布</p>
          <p class="text-[11px] text-slate-400 mb-3">谁是承接品类？——如果买B5面膜之后大量流向精华，说明精华是面膜的自然延伸，可做关联推荐</p>
          <DataTablePro
            :columns="ASSOC_COLS"
            :data="data.post_purchase ?? []"
            :pagination="{ pageSize: 10 }"
            :scroll-x="800"
          />
        </div>
      </template>

      <!-- 流转矩阵 -->
      <div class="bi-card p-4">
        <div class="flex items-center justify-between mb-3">
          <div>
            <h3 class="text-sm font-semibold text-slate-800 mb-0.5">流转矩阵</h3>
            <p class="text-[11px] text-slate-500 mb-1">
              行=来源品类，列=目标品类，{{ matrixDisplayMode === 'percentage' ? '值=行百分比（从来源流向目标的占比）' : '值=流转人数' }}
            </p>
            <p class="text-[11px] text-slate-400">
              {{ matrixDisplayMode === 'percentage' ? '百分比模式：快速发现核心流转路径' : '数值模式：精确读取流转人数' }}
            </p>
          </div>
          <div class="flex items-center bg-slate-100 rounded-lg p-0.5">
            <button
              class="px-3 py-1 text-xs rounded-md transition-colors"
              :class="matrixDisplayMode === 'percentage' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
              @click="matrixDisplayMode = 'percentage'"
            >
              百分比
            </button>
            <button
              class="px-3 py-1 text-xs rounded-md transition-colors"
              :class="matrixDisplayMode === 'value' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
              @click="matrixDisplayMode = 'value'"
            >
              数值
            </button>
          </div>
        </div>
        <DataTablePro
          :columns="matrixColumns"
          :data="matrixData"
          :pagination="false"
          :scroll-x="2000"
          :max-height="520"
        />
      </div>
    </template>

    <EmptyState v-else description="暂无数据" />
  </div>
</template>
