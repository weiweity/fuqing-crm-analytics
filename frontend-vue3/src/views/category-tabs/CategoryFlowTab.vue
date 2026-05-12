<script setup lang="ts">
import { computed, ref, toValue, watch } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NTooltip, NSelect } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useFilterStore } from '@/stores/filterStore'
import { fetchCategoryFlowAssoc, fetchCategoryFlowMatrix } from '@/api/category'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import DataTablePro from '@/components/DataTablePro.vue'
import { CHART_COLORS } from '@/composables/useChartTheme'

const props = defineProps<{
  dataQualityNote?: string
  /** 品类列表（从 distributionData 获取，按GSV降序） */
  categoryOptions?: string[]
}>()

const filterStore = useFilterStore()

// 品类流转tab默认排除的渠道（避免赠品&0.01、其他渠道污染流转数据）
const CATEGORY_FLOW_EXCLUDED_CHANNELS = ['赠品&0.01', '其他']

const windowDays = ref<number>(90)
const targetCategory = ref<string | null>(null)
const anchorMode = ref<'first' | 'last' | 'every'>('last')
const pathDepth = ref<'1'>('1')

const ANCHOR_MODE_OPTIONS = [
  { label: '首次购买', value: 'first' },
  { label: '末次购买', value: 'last' },
  { label: '每次购买', value: 'every' },
]

const PATH_DEPTH_OPTIONS = [
  { label: '1步', value: '1' },
]

// 流转矩阵折叠状态（默认折叠，降级为辅助参考）
const matrixExpanded = ref(false)

// 流转矩阵显示模式：百分比(默认) / 数值
const matrixDisplayMode = ref<'percentage' | 'value'>('percentage')

// 前后置分析视图模式：桑基图 / 双向条形图
const temporalViewMode = ref<'sankey' | 'bar'>('sankey')

const targetCategoryOptions = computed(() => {
  // 优先使用父组件传入的品类列表（与连带分析保持一致）
  const fromProps = props.categoryOptions || []
  if (fromProps.length > 0) {
    return fromProps.map((c) => ({ label: c, value: c }))
  }
  // fallback: 从桑基图节点动态计算（选项较少）
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

const queryParams = computed(() => {
  const endDate = filterStore.dateRange[1]
  const startDate = filterStore.dateRange[0]
  // 分析截止日为导航栏最后一日，追溯窗口为 windowDays
  // 时序关联分析在后端用 [end_date - window_days, end_date]
  // 全局流转矩阵仍用导航栏原始日期范围
  return {
    start_date: startDate,
    end_date: endDate,
    level: 'class',
    window_days: windowDays.value,
    channel: filterStore.channel === '全店' ? undefined : filterStore.channel,
    exclude_channels: CATEGORY_FLOW_EXCLUDED_CHANNELS,
    target_category: targetCategory.value || '',
    anchor_mode: anchorMode.value,
    path_depth: pathDepth.value,
  }
})

// 矩阵专用参数（不含 target_category 等时序关联参数）
const matrixParams = computed(() => {
  const endDate = filterStore.dateRange[1]
  const startDate = filterStore.dateRange[0]
  return {
    start_date: startDate,
    end_date: endDate,
    level: 'class',
    top_n: 10,
    window_days: windowDays.value,
    channel: filterStore.channel === '全店' ? undefined : filterStore.channel,
    exclude_channels: CATEGORY_FLOW_EXCLUDED_CHANNELS,
  }
})

// 主请求：时序关联分析（始终请求）
const {
  data: assocData,
  isLoading: assocLoading,
  error: assocError,
  refetch: refetchAssoc,
} = useQuery({
  queryKey: computed(() => ['category-flow-assoc', { ...toValue(queryParams) }]),
  queryFn: () => fetchCategoryFlowAssoc(toValue(queryParams)),
  staleTime: 60_000,
})

// 矩阵请求：懒加载（展开时才请求）
const matrixEnabled = computed(() => matrixExpanded.value)
const {
  data: matrixData,
  isLoading: matrixLoading,
  error: matrixError,
  refetch: refetchMatrix,
} = useQuery({
  queryKey: computed(() => ['category-flow-matrix', { ...toValue(matrixParams) }]),
  queryFn: () => fetchCategoryFlowMatrix(toValue(matrixParams)),
  enabled: matrixEnabled,
  staleTime: 60_000,
})

// 合并数据，保持模板兼容
const data = computed(() => {
  if (!assocData.value) return null
  return {
    target_category: assocData.value.target_category,
    post_purchase: assocData.value.post_purchase,
    pre_purchase: assocData.value.pre_purchase,
    post_sankey: assocData.value.post_sankey,
    pre_sankey: assocData.value.pre_sankey,
    // 矩阵数据来自独立接口（可能尚未加载）
    sankey_data: matrixData.value?.sankey_data ?? { nodes: [], links: [] },
    matrix: matrixData.value?.matrix ?? { sources: [], targets: [], matrix: [], row_totals: [], concentration_warnings: [] },
    data_stale: matrixData.value?.data_stale ?? false,
    data_quality_note: assocData.value.data_quality_note || matrixData.value?.data_quality_note || '',
  }
})

const isLoading = computed(() => assocLoading.value)
const error = computed(() => assocError.value || matrixError.value)
const refetch = () => {
  refetchAssoc()
  if (matrixEnabled.value) refetchMatrix()
}

// 默认选中「经典膜」（如果品类列表中存在）
watch(targetCategoryOptions, (options) => {
  if (!targetCategory.value && options.some((o) => o.value === '经典膜')) {
    targetCategory.value = '经典膜'
  }
}, { immediate: true })

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
  const focusTarget = targetCategory.value

  // ═══════════════════════════════════════════════════════════════
  // 模式A：有目标品类 → 合并 pre_sankey + post_sankey 成「前置→目标→后置」图
  // ═══════════════════════════════════════════════════════════════
  if (focusTarget && data.value?.pre_sankey?.nodes?.length && data.value?.post_sankey?.nodes?.length) {
    const pre = data.value.pre_sankey
    const post = data.value.post_sankey

    // 合并节点：前置节点 + 目标品类 + 后置节点（去重，排除"未购买其他"）
    const nodeMap = new Map<string, { name: string; category_name: string }>()
    for (const n of pre.nodes) {
      if (n.name !== focusTarget && n.name !== '未购买其他') nodeMap.set(n.name, n)
    }
    nodeMap.set(focusTarget, { name: focusTarget, category_name: focusTarget })
    for (const n of post.nodes) {
      if (n.name !== focusTarget && n.name !== '未购买其他') nodeMap.set(n.name, n)
    }
    const nodes = Array.from(nodeMap.values())

    // 合并链接（排除涉及"未购买其他"的）
    let links = [
      ...pre.links.filter((l) => l.source !== '未购买其他' && l.target !== '未购买其他'),
      ...post.links.filter((l) => l.source !== '未购买其他' && l.target !== '未购买其他'),
    ]

    // 打破环，确保DAG
    const acyclicLinks = breakCycles(links)

    // 过滤弱连接
    const maxValue = Math.max(...acyclicLinks.map((l) => l.value), 1)
    const threshold = Math.max(5, maxValue * 0.02)
    const filteredLinks = acyclicLinks.filter((l) => l.value >= threshold)

    // index 映射
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
            return `${srcName} → ${tgtName}<br/>关联人数: ${params.data.value.toLocaleString()}`
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
          lineStyle: { color: 'gradient', curveness: 0.4, opacity: 0.6 },
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
              color: n.name === focusTarget
                ? '#3b82f6'
                : CHART_COLORS[nodeNameIdx[n.name] % CHART_COLORS.length],
            },
          })),
          links: sankeyLinks,
          animation: false,
        },
      ],
      graphic: [
        {
          type: 'text',
          left: 'center',
          bottom: 4,
          style: {
            text: `左=买「${focusTarget}」之前买的品类  ·  右=买「${focusTarget}」之后买的品类  ·  线条宽度∝关联人数`,
            fontSize: 10,
            fill: '#94a3b8',
            textAlign: 'center',
          },
        },
      ],
    }
  }

  // ═══════════════════════════════════════════════════════════════
  // 模式B：无目标品类 → 全局首购→次购流转图（fallback）
  // ═══════════════════════════════════════════════════════════════
  if (!data.value?.sankey_data?.nodes?.length) return {}
  const { nodes: rawNodes, links: rawLinks } = data.value.sankey_data

  // 过滤"其他"节点和关联链接
  const EXCLUDED_SANKEY_NODES = ['其他']
  let nodes = rawNodes.filter((n) => !EXCLUDED_SANKEY_NODES.includes(n.name))
  let nodeNamesSet = new Set(nodes.map((n) => n.name))
  let links = rawLinks.filter((l) => nodeNamesSet.has(l.source) && nodeNamesSet.has(l.target))

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
        lineStyle: { color: 'gradient', curveness: 0.4, opacity: 0.6 },
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
              : CHART_COLORS[nodeNameIdx[n.name] % CHART_COLORS.length],
          },
        })),
        links: sankeyLinks,
        animation: false,
      },
    ],
    graphic: [
      {
        type: 'text',
        left: 'center',
        bottom: 4,
        style: {
          text: '左=首购品类  右=次购品类  线条宽度∝流转人数',
          fontSize: 10,
          fill: '#94a3b8',
          textAlign: 'center',
        },
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

const matrixTableData = computed(() => {
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

// ─── Temporal Sankey helpers ─────────────────────────────────────
function buildTemporalSankeyOption(
  sankeyData: { nodes: { name: string; category_name: string }[]; links: { source: string; target: string; value: number }[] } | undefined,
  targetName: string,
) {
  if (!sankeyData?.nodes?.length || !sankeyData?.links?.length) return {}

  // 过滤"其他"节点和关联链接
  const EXCLUDED_SANKEY_NODES = ['其他']
  const nodes = sankeyData.nodes.filter((n) => !EXCLUDED_SANKEY_NODES.includes(n.name))
  const nodeNamesSet = new Set(nodes.map((n) => n.name))
  const links = sankeyData.links.filter((l) => nodeNamesSet.has(l.source) && nodeNamesSet.has(l.target))

  // 打破环，确保DAG（2步路径可能产生环如 A→B→A）
  const acyclicLinks = breakCycles(links)

  const nodeNames = nodes.map((n) => n.name)
  const nodeNameIdx: Record<string, number> = {}
  nodeNames.forEach((name, i) => { nodeNameIdx[name] = i })

  const sankeyLinks = acyclicLinks.map((l) => ({
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
          return `${srcName} → ${tgtName}<br/>关联人数: ${params.data.value.toLocaleString()}`
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
            color: n.name === targetName
              ? '#3b82f6'
              : n.name === '未购买其他'
                ? '#94a3b8'
                : CHART_COLORS[nodeNameIdx[n.name] % CHART_COLORS.length],
          },
        })),
        links: sankeyLinks,
        animation: false,
      },
    ],
  }
}

const preSankeyOption = computed(() => {
  if (!data.value?.pre_sankey) return {}
  return buildTemporalSankeyOption(data.value.pre_sankey, data.value.target_category || '')
})

const postSankeyOption = computed(() => {
  if (!data.value?.post_sankey) return {}
  return buildTemporalSankeyOption(data.value.post_sankey, data.value.target_category || '')
})

// ─── 双向条形图（前置/后置对比）───────────────────────────────────
function buildBidirectionalBarOption(
  preData: { category_name: string; user_count: number }[] | undefined,
  postData: { category_name: string; user_count: number }[] | undefined,
  targetName: string,
) {
  const pre = (preData ?? []).slice(0, 8)
  const post = (postData ?? []).slice(0, 8)
  if (!pre.length && !post.length) return {}

  const preCats = pre.map((d) => d.category_name)
  const postCats = post.map((d) => d.category_name)
  const preValues = pre.map((d) => d.user_count)
  const postValues = post.map((d) => d.user_count)
  const maxVal = Math.max(...preValues, ...postValues, 1)

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      textStyle: { color: '#0f172a', fontSize: 12 },
      extraCssText: 'box-shadow: 0 4px 12px -2px rgba(0,0,0,0.08); border-radius: 4px;',
      formatter: (params: any) => {
        const p = Array.isArray(params) ? params[0] : params
        const val = Math.abs(p.value)
        const name = p.name
        const side = p.seriesName
        return `${side}<br/>${name}: ${val.toLocaleString()}人`
      },
    },
    grid: [
      { left: 10, right: '54%', top: 40, bottom: 20, containLabel: true },
      { left: '54%', right: 10, top: 40, bottom: 20, containLabel: true },
    ],
    xAxis: [
      {
        type: 'value',
        gridIndex: 0,
        inverse: true,
        max: maxVal * 1.1,
        axisLabel: { formatter: (v: number) => Math.abs(v).toLocaleString(), fontSize: 10, color: '#64748b' },
        splitLine: { lineStyle: { color: '#f1f5f9' } },
      },
      {
        type: 'value',
        gridIndex: 1,
        max: maxVal * 1.1,
        axisLabel: { formatter: (v: number) => v.toLocaleString(), fontSize: 10, color: '#64748b' },
        splitLine: { lineStyle: { color: '#f1f5f9' } },
      },
    ],
    yAxis: [
      {
        type: 'category',
        gridIndex: 0,
        data: preCats,
        axisLabel: { fontSize: 11, color: '#334155', width: 90, overflow: 'truncate' },
        axisTick: { show: false },
        axisLine: { show: false },
      },
      {
        type: 'category',
        gridIndex: 1,
        data: postCats,
        axisLabel: { fontSize: 11, color: '#334155', width: 90, overflow: 'truncate' },
        axisTick: { show: false },
        axisLine: { show: false },
      },
    ],
    series: [
      {
        name: '前置来源',
        type: 'bar',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: preValues.map((v) => -v),
        barWidth: 16,
        itemStyle: { color: '#60a5fa', borderRadius: [4, 0, 0, 4] },
        label: {
          show: true,
          position: 'left',
          fontSize: 10,
          color: '#475569',
          formatter: (p: any) => Math.abs(p.value).toLocaleString(),
        },
      },
      {
        name: '后置去向',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: postValues,
        barWidth: 16,
        itemStyle: { color: '#34d399', borderRadius: [0, 4, 4, 0] },
        label: {
          show: true,
          position: 'right',
          fontSize: 10,
          color: '#475569',
          formatter: (p: any) => p.value.toLocaleString(),
        },
      },
    ],
    graphic: [
      {
        type: 'text',
        left: 'center',
        top: 12,
        style: {
          text: targetName,
          fontSize: 14,
          fontWeight: 'bold',
          fill: '#3b82f6',
          textAlign: 'center',
        },
      },
      {
        type: 'text',
        left: 'center',
        top: 30,
        style: {
          text: '目标品类',
          fontSize: 10,
          fill: '#94a3b8',
          textAlign: 'center',
        },
      },
    ],
  }
}

const bidirectionalBarOption = computed(() => {
  if (!data.value?.target_category) return {}
  return buildBidirectionalBarOption(
    data.value.pre_purchase ?? [],
    data.value.post_purchase ?? [],
    data.value.target_category,
  )
})
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
      <!-- 目标品类前后关联桑基图 -->
      <div class="bi-card p-4">
        <div class="flex items-center justify-between mb-3">
          <div>
            <h3 class="text-sm font-semibold text-slate-800 mb-0.5">
              {{ targetCategory ? `「${targetCategory}」前后关联分析` : '品类流转桑基图' }}
            </h3>
            <p v-if="targetCategory" class="text-[11px] text-slate-400 mt-0.5">
              截止 {{ filterStore.dateRange[1] }} 往前追溯 {{ windowDays }} 天 · 锚点={{ anchorMode === 'first' ? '首次' : anchorMode === 'last' ? '末次' : '每次' }}购买 · 左=买之前 · 右=买之后 · 线条越宽=关联人数越多
            </p>
            <p v-else class="text-[11px] text-slate-400 mt-0.5">
              全局模式：找从左到右的粗线条 → 发现哪个品类在给哪个品类引流
            </p>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-xs text-slate-500">目标品类:</span>
            <n-select
              v-model:value="targetCategory"
              :options="targetCategoryOptions"
              size="small"
              clearable
              filterable
              placeholder="选择品类"
              style="width: 160px"
            />
            <span class="text-xs text-slate-500">锚点:</span>
            <n-select
              v-model:value="anchorMode"
              :options="ANCHOR_MODE_OPTIONS"
              size="small"
              style="width: 100px"
            />
            <span class="text-xs text-slate-500">窗口:</span>
            <n-select
              v-model:value="windowDays"
              :options="WINDOW_OPTIONS"
              size="small"
              style="width: 90px"
            />
          </div>
        </div>
        <EmptyState
          v-if="targetCategory ? !(data.pre_sankey?.nodes?.length || data.post_sankey?.nodes?.length) : !data.sankey_data?.nodes?.length"
          description="当前条件下无关联数据"
        />
        <EChartsWrapper v-else :option="sankeyOption" height="480px" />
      </div>

      <!-- 前后置关联明细表格 -->
      <template v-if="data?.target_category">
        <div class="bi-card p-4">
          <h3 class="text-sm font-semibold text-slate-800 mb-3">
            「{{ data.target_category }}」前后置关联明细
          </h3>
          <p class="text-[11px] text-slate-400 mb-3">
            截止 {{ filterStore.dateRange[1] }} 往前追溯 {{ windowDays }} 天 · {{ anchorMode === 'first' ? '首次' : anchorMode === 'last' ? '末次' : '每次' }}购买「{{ data.target_category }}」的用户，前后 {{ windowDays }} 天内还买了什么
          </p>

          <div class="border-t border-slate-100 pt-4">
            <h4 class="text-xs font-semibold text-slate-700 mb-2">买「{{ data.target_category }}」之前还买了什么</h4>
            <DataTablePro
              :columns="ASSOC_COLS"
              :data="data.pre_purchase ?? []"
              :pagination="{ pageSize: 10 }"
              :scroll-x="800"
              class="mb-4"
            />
            <h4 class="text-xs font-semibold text-slate-700 mb-2">买「{{ data.target_category }}」之后还买了什么</h4>
            <DataTablePro
              :columns="ASSOC_COLS"
              :data="data.post_purchase ?? []"
              :pagination="{ pageSize: 10 }"
              :scroll-x="800"
            />
          </div>
        </div>
      </template>

      <!-- 流转矩阵（默认折叠，全局首购→次购鸟瞰） -->
      <div class="bi-card">
        <div
          class="flex items-center justify-between p-4 cursor-pointer hover:bg-slate-50/50 transition-colors"
          @click="matrixExpanded = !matrixExpanded"
        >
          <div>
            <h3 class="text-sm font-semibold text-slate-800">流转矩阵</h3>
            <p class="text-[11px] text-slate-400 mt-0.5">
              全局首购→次购鸟瞰 · {{ matrixExpanded ? '点击折叠' : '点击展开' }}
            </p>
          </div>
          <span class="text-slate-400 text-xs">{{ matrixExpanded ? '▼' : '▶' }}</span>
        </div>
        <div v-show="matrixExpanded" class="px-4 pb-4">
          <div class="flex items-center justify-between mb-3">
            <p class="text-[11px] text-slate-500">
              行=来源品类，列=目标品类，{{ matrixDisplayMode === 'percentage' ? '值=行百分比' : '值=流转人数' }}
            </p>
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
            :data="matrixTableData"
            :pagination="false"
            :scroll-x="2000"
            :max-height="520"
          />
        </div>
      </div>
    </template>

    <EmptyState v-else description="暂无数据" />
  </div>
</template>
