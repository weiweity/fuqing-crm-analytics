<script setup lang="ts">
import { computed, h, ref, toValue, watch } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NAlert, NDataTable } from 'naive-ui'
import type { DataTableColumns, DataTableColumn } from 'naive-ui'
import { fetchCategoryOverview } from '@/api/category'
import { fetchProductAssets } from '@/api/marketFocus'
import { useFilterStore } from '@/stores/filterStore'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import ExportToolbar from '@/components/ExportToolbar.vue'
import type { XlsxColumn } from '@/utils/exportXlsx'
import LineChart from '@/components/LineChart.vue'

const props = defineProps<{ weeks: number; channel?: string }>()
const filterStore = useFilterStore()

// 本Tab始终使用全店渠道数据，不展示渠道筛选

// 低价渠道列表
import { LOW_PRICE_CHANNELS } from '@/constants/channels'

// ─────────────────────────────────────────────────────────────
// 产品映射：从 Tab3（product-assets）获取 spu_classes，不再硬编码
// ─────────────────────────────────────────────────────────────
// 产品映射 ref，由 Tab3 数据初始化后填充
const productMapping = ref<{ name: string; spu_classes: string[] }[]>([])

// 监听 Tab3 数据，一旦加载完成就提取产品映射
const { data: productAssetsData } = useQuery({
  queryKey: ['product-assets', props.weeks],
  queryFn: () => fetchProductAssets(props.weeks),
  staleTime: 5 * 60 * 1000,
})

watch(productAssetsData, (data) => {
  if (data?.products) {
    productMapping.value = data.products.map(p => ({
      name: p.name,
      spu_classes: p.spu_classes,
    }))
  }
}, { immediate: true })

// ─────────────────────────────────────────────────────────────
// 日计算：最近 N 天（含今天）— 用于折线图
// ─────────────────────────────────────────────────────────────
function getDaysDateRange(days: number): string[] {
  const result: string[] = []
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today)
    d.setDate(today.getDate() - i)
    result.push(d.toISOString().split('T')[0])
  }
  return result
}

function getDayLabel(dateStr: string): string {
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

// ─────────────────────────────────────────────────────────────
// 周计算：自然周（周一~周日）— 用于表格
// ─────────────────────────────────────────────────────────────
function getWeeksDateRange(weeks: number) {
  const end = new Date()
  end.setHours(0, 0, 0, 0)
  const dayOfWeek = end.getDay()
  const daysSinceMonday = dayOfWeek === 0 ? 6 : dayOfWeek - 1
  end.setDate(end.getDate() - daysSinceMonday)

  const result: { start: string; end: string }[] = []
  for (let i = 0; i < weeks; i++) {
    const weekEnd = new Date(end)
    weekEnd.setDate(end.getDate() - i * 7)
    const weekStart = new Date(weekEnd)
    weekStart.setDate(weekEnd.getDate() - 6)
    result.unshift({
      start: weekStart.toISOString().split('T')[0],
      end: weekEnd.toISOString().split('T')[0],
    })
  }
  return result
}

function getWeekLabel(start: string, end: string): string {
  const s = new Date(start)
  const e = new Date(end)
  return `${s.getMonth() + 1}/${s.getDate()}-${e.getMonth() + 1}/${e.getDate()}`
}

// ─────────────────────────────────────────────────────────────
// 数据获取：日维度（折线图）+ 周维度（表格）
// ─────────────────────────────────────────────────────────────

const queryParams = computed(() => ({
  weeks: props.weeks,
  days: props.weeks * 7,
  channel: props.channel === '全店' || !props.channel ? undefined : props.channel,
  excludeLowPrice: filterStore.excludeLowPrice,
}))

// 日维度：折线图
const { data: dayResults } = useQuery({
  queryKey: computed(() => ['product-customer-daily', toValue(queryParams)]),
  queryFn: () => {
    const p = toValue(queryParams)
    const dates = getDaysDateRange(p.days)
    const excludeChannels = p.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined
    return Promise.all(
      dates.map(date =>
        fetchCategoryOverview({
          start_date: date,
          end_date: date,
          level: 'class',
          metric_type: 'GSV',
          channel: p.channel,
          exclude_channels: excludeChannels,
        }).then(res => ({ rows: res.all_rows, ttl: res.all_ttl, date }))
      )
    )
  },
  staleTime: 5 * 60 * 1000,
})

// 周维度：表格
const { data: weekResults, isLoading, error, refetch } = useQuery({
  queryKey: computed(() => ['product-customer-weekly', toValue(queryParams)]),
  queryFn: () => {
    const p = toValue(queryParams)
    const ranges = getWeeksDateRange(p.weeks)
    const excludeChannels = p.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined
    return Promise.all(
      ranges.map(range =>
        fetchCategoryOverview({
          start_date: range.start,
          end_date: range.end,
          level: 'class',
          metric_type: 'GSV',
          channel: p.channel,
          exclude_channels: excludeChannels,
        }).then(res => ({ rows: res.all_rows, ttl: res.all_ttl, range }))
      )
    )
  },
  staleTime: 5 * 60 * 1000,
})

// ─────────────────────────────────────────────────────────────
// 表格数据：每产品一组，包含多周数据 + 本周对比行
// ─────────────────────────────────────────────────────────────
interface TableRow {
  id: string
  product: string
  weekLabel: string
  weekIdx: number
  isChangeRow: boolean
  isYoyRow: boolean
  gsv: number
  new_gsv: number
  old_gsv: number
  users: number
  new_users: number
  old_users: number
  aus: number
  new_aus: number
  old_aus: number
  new_ratio_gsv: number
  old_ratio_gsv: number
  new_ratio_users: number
  old_ratio_users: number
}

// 分组后的数据（表格用周维度）
const groupedData = computed((): { name: string; rows: TableRow[] }[] => {
  const results = weekResults.value
  if (!results?.length) return []

  const allRows: TableRow[] = []
  const mapping = productMapping.value

  // 全店数据
  const storeRows: TableRow[] = results.map((r, weekIdx) => {
    const ttl = r!.ttl
    return {
      id: `store-${weekIdx}`,
      product: '全店',
      weekLabel: getWeekLabel(r!.range.start, r!.range.end),
      weekIdx,
      isChangeRow: false,
      isYoyRow: false,
      gsv: ttl.gsv,
      new_gsv: ttl.new_gsv,
      old_gsv: ttl.old_gsv,
      users: ttl.users,
      new_users: ttl.new_users || 0,
      old_users: ttl.old_users || 0,
      aus: ttl.users > 0 ? ttl.gsv / ttl.users : 0,
      new_aus: (ttl.new_users || 0) > 0 ? ttl.new_gsv / (ttl.new_users || 0) : 0,
      old_aus: (ttl.old_users || 0) > 0 ? ttl.old_gsv / (ttl.old_users || 0) : 0,
      new_ratio_gsv: ttl.gsv > 0 ? ttl.new_gsv / ttl.gsv : 0,
      old_ratio_gsv: ttl.gsv > 0 ? ttl.old_gsv / ttl.gsv : 0,
      new_ratio_users: ttl.users > 0 ? (ttl.new_users || 0) / ttl.users : 0,
      old_ratio_users: ttl.users > 0 ? (ttl.old_users || 0) / ttl.users : 0,
    }
  })
  allRows.push(...storeRows)

  // 各产品数据（使用 productMapping，不再硬编码）
  for (const product of mapping) {
    for (let weekIdx = 0; weekIdx < results.length; weekIdx++) {
      const r = results[weekIdx]!
      const matchingRows = r.rows.filter(row => product.spu_classes.includes(row.name))
      const gsv = matchingRows.reduce((s, r) => s + r.gsv, 0)
      const new_gsv = matchingRows.reduce((s, r) => s + r.new_gsv, 0)
      const old_gsv = matchingRows.reduce((s, r) => s + r.old_gsv, 0)
      const users = matchingRows.reduce((s, r) => s + r.users, 0)
      const new_users = matchingRows.reduce((s, r) => s + (r.new_users || 0), 0)
      const old_users = matchingRows.reduce((s, r) => s + (r.old_users || 0), 0)
      allRows.push({
        id: `${product.name}-${weekIdx}`,
        product: product.name,
        weekLabel: getWeekLabel(r.range.start, r.range.end),
        weekIdx,
        isChangeRow: false,
        isYoyRow: false,
        gsv,
        new_gsv,
        old_gsv,
        users,
        new_users,
        old_users,
        aus: users > 0 ? gsv / users : 0,
        new_aus: new_users > 0 ? new_gsv / new_users : 0,
        old_aus: old_users > 0 ? old_gsv / old_users : 0,
        new_ratio_gsv: gsv > 0 ? new_gsv / gsv : 0,
        old_ratio_gsv: gsv > 0 ? old_gsv / gsv : 0,
        new_ratio_users: users > 0 ? new_users / users : 0,
        old_ratio_users: users > 0 ? old_users / users : 0,
      })
    }
  }

  // 按产品分组
  const groups: Record<string, TableRow[]> = {}
  for (const row of allRows) {
    if (!groups[row.product]) groups[row.product] = []
    groups[row.product].push(row)
  }

    // 为每组添加本周对比上周行
    for (const name in groups) {
      const rows = groups[name]
      if (rows.length >= 2) {
        const latest = rows[rows.length - 1]
        const prev = rows[rows.length - 2]
        const changeRow: TableRow = {
          id: `change-${name}`,
          product: name,
          weekLabel: '本周对比上周',
          weekIdx: -1,
          isChangeRow: true,
          isYoyRow: false,
          // 绝对值指标：百分比变化
          gsv: prev.gsv > 0 ? (latest.gsv - prev.gsv) / prev.gsv : 0,
          new_gsv: prev.new_gsv > 0 ? (latest.new_gsv - prev.new_gsv) / prev.new_gsv : 0,
          old_gsv: prev.old_gsv > 0 ? (latest.old_gsv - prev.old_gsv) / prev.old_gsv : 0,
          users: prev.users > 0 ? (latest.users - prev.users) / prev.users : 0,
          new_users: prev.new_users > 0 ? (latest.new_users - prev.new_users) / prev.new_users : 0,
          old_users: prev.old_users > 0 ? (latest.old_users - prev.old_users) / prev.old_users : 0,
          aus: prev.aus > 0 ? (latest.aus - prev.aus) / prev.aus : 0,
          new_aus: prev.new_aus > 0 ? (latest.new_aus - prev.new_aus) / prev.new_aus : 0,
          old_aus: prev.old_aus > 0 ? (latest.old_aus - prev.old_aus) / prev.old_aus : 0,
          // 占比指标：百分点差（pp）
          new_ratio_gsv: latest.new_ratio_gsv - prev.new_ratio_gsv,
          old_ratio_gsv: latest.old_ratio_gsv - prev.old_ratio_gsv,
          new_ratio_users: latest.new_ratio_users - prev.new_ratio_users,
          old_ratio_users: latest.old_ratio_users - prev.old_ratio_users,
        }
        rows.push(changeRow)
      }

      // YOY同比行：全店用 ttl，产品行从 all_rows 聚合推导
      const lastWeekIdx = results.length - 1
      const lastResult = results[lastWeekIdx]!

      if (name === '全店') {
        const ttl = lastResult.ttl
        const yoyRow: TableRow = {
          id: `yoy-${name}`,
          product: name,
          weekLabel: '本周对比去年同期',
          weekIdx: -2,
          isChangeRow: false,
          isYoyRow: true,
          gsv: ttl.gsv_yoy ?? 0,
          new_gsv: ttl.new_gsv_yoy ?? 0,
          old_gsv: ttl.old_gsv_yoy ?? 0,
          users: ttl.users_yoy ?? 0,
          new_users: ttl.new_users_yoy ?? 0,
          old_users: ttl.old_users_yoy ?? 0,
          aus: ttl.aus_yoy ?? 0,
          new_aus: ttl.new_aus_yoy ?? 0,
          old_aus: ttl.old_aus_yoy ?? 0,
          new_ratio_gsv: ttl.new_ratio_yoy ?? 0,
          old_ratio_gsv: ttl.old_ratio_yoy ?? 0,
          new_ratio_users: ttl.new_users_ratio_yoy ?? 0,
          old_ratio_users: ttl.old_users_ratio_yoy ?? 0,
        }
        rows.push(yoyRow)
      } else {
        // 产品组：从 all_rows 聚合 YOY
        const product = mapping.find(p => p.name === name)
        if (product) {
          const matchingRows = lastResult.rows.filter(row => product.spu_classes.includes(row.name))
          if (matchingRows.length > 0) {
            // 从 yoy_absolute 的反函数推导去年同期绝对值: comp = cur / (1 + yoy)
            const deriveComp = (cur: number, yoy: number | null | undefined): number => {
              if (yoy == null || yoy === 0) return cur
              const denom = 1 + yoy
              return Math.abs(denom) > 1e-6 ? cur / denom : cur
            }
            // 聚合绝对值 YOY: sum(当前) / sum(去年同期) - 1
            const aggAbsYoy = (curSum: number, compSum: number): number => {
              return Math.abs(compSum) > 1e-6 ? (curSum - compSum) / compSum : 0
            }

            // 聚合当前 & 去年同期值
            const curGsv = matchingRows.reduce((s, r) => s + r.gsv, 0)
            const compGsv = matchingRows.reduce((s, r) => s + deriveComp(r.gsv, r.gsv_yoy), 0)
            const curNewGsv = matchingRows.reduce((s, r) => s + r.new_gsv, 0)
            const compNewGsv = matchingRows.reduce((s, r) => s + deriveComp(r.new_gsv, r.new_gsv_yoy), 0)
            const curOldGsv = matchingRows.reduce((s, r) => s + r.old_gsv, 0)
            const compOldGsv = matchingRows.reduce((s, r) => s + deriveComp(r.old_gsv, r.old_gsv_yoy), 0)
            const curUsers = matchingRows.reduce((s, r) => s + r.users, 0)
            const compUsers = matchingRows.reduce((s, r) => s + deriveComp(r.users, r.users_yoy), 0)
            const curNewUsers = matchingRows.reduce((s, r) => s + (r.new_users || 0), 0)
            const compNewUsers = matchingRows.reduce((s, r) => s + deriveComp(r.new_users || 0, r.new_users_yoy), 0)
            const curOldUsers = matchingRows.reduce((s, r) => s + (r.old_users || 0), 0)
            const compOldUsers = matchingRows.reduce((s, r) => s + deriveComp(r.old_users || 0, r.old_users_yoy), 0)

            // 客单价 = GSV / users，用聚合值
            const curAus = curUsers > 0 ? curGsv / curUsers : 0
            const compAus = compUsers > 0 ? compGsv / compUsers : 0
            const curNewAus = curNewUsers > 0 ? curNewGsv / curNewUsers : 0
            const compNewAus = compNewUsers > 0 ? compNewGsv / compNewUsers : 0
            const curOldAus = curOldUsers > 0 ? curOldGsv / curOldUsers : 0
            const compOldAus = compOldUsers > 0 ? compOldGsv / compOldUsers : 0

            // 占比 = 用聚合值算
            const curRatioNewGsv = curGsv > 0 ? curNewGsv / curGsv : 0
            const compRatioNewGsv = compGsv > 0 ? compNewGsv / compGsv : 0
            const curRatioOldGsv = curGsv > 0 ? curOldGsv / curGsv : 0
            const compRatioOldGsv = compGsv > 0 ? compOldGsv / compGsv : 0
            const curRatioNewUsers = curUsers > 0 ? curNewUsers / curUsers : 0
            const compRatioNewUsers = compUsers > 0 ? compNewUsers / compUsers : 0
            const curRatioOldUsers = curUsers > 0 ? curOldUsers / curUsers : 0
            const compRatioOldUsers = compUsers > 0 ? compOldUsers / compUsers : 0

            const yoyRow: TableRow = {
              id: `yoy-${name}`,
              product: name,
              weekLabel: '本周对比去年同期',
              weekIdx: -2,
              isChangeRow: false,
              isYoyRow: true,
              gsv: aggAbsYoy(curGsv, compGsv),
              new_gsv: aggAbsYoy(curNewGsv, compNewGsv),
              old_gsv: aggAbsYoy(curOldGsv, compOldGsv),
              users: aggAbsYoy(curUsers, compUsers),
              new_users: aggAbsYoy(curNewUsers, compNewUsers),
              old_users: aggAbsYoy(curOldUsers, compOldUsers),
              aus: aggAbsYoy(curAus, compAus),
              new_aus: aggAbsYoy(curNewAus, compNewAus),
              old_aus: aggAbsYoy(curOldAus, compOldAus),
              // 占比 YOY 用百分点差
              new_ratio_gsv: curRatioNewGsv - compRatioNewGsv,
              old_ratio_gsv: curRatioOldGsv - compRatioOldGsv,
              new_ratio_users: curRatioNewUsers - compRatioNewUsers,
              old_ratio_users: curRatioOldUsers - compRatioOldUsers,
            }
            rows.push(yoyRow)
          }
        }
      }
    }

  // 按最新周GSV排序
  const sortedProducts = Object.keys(groups).sort((a, b) => {
    if (a === '全店') return -1
    if (b === '全店') return 1
    const aLast = groups[a][groups[a].length - 2]?.gsv || 0
    const bLast = groups[b][groups[b].length - 2]?.gsv || 0
    return bLast - aLast
  })

  return sortedProducts.map(name => ({ name, rows: groups[name] }))
})

// 扁平化的表格数据
const tableData = computed((): TableRow[] => {
  return groupedData.value.flatMap(g => g.rows)
})

// ─────────────────────────────────────────────────────────────
// 折线图数据：各产品 by 日的新客/老客成交占比
// ─────────────────────────────────────────────────────────────
const chartDayLabels = computed(() => {
  const results = dayResults.value
  if (!results?.length) return []
  return results.map(r => getDayLabel(r!.date))
})

const newRatioSeries = computed(() => {
  const results = dayResults.value
  if (!results?.length) return []
  const mapping = productMapping.value
  const series: { name: string; data: number[] }[] = []
  // 全店
  series.push({
    name: '全店',
    data: results.map(r => {
      const ttl = r!.ttl
      return ttl.gsv > 0 ? +(ttl.new_gsv / ttl.gsv * 100).toFixed(1) : 0
    }),
  })
  // 各产品
  for (const product of mapping) {
    series.push({
      name: product.name,
      data: results.map(r => {
        const matchingRows = r!.rows.filter(row => product.spu_classes.includes(row.name))
        const gsv = matchingRows.reduce((s, r) => s + r.gsv, 0)
        const new_gsv = matchingRows.reduce((s, r) => s + r.new_gsv, 0)
        return gsv > 0 ? +(new_gsv / gsv * 100).toFixed(1) : 0
      }),
    })
  }
  return series
})

const oldRatioSeries = computed(() => {
  const results = dayResults.value
  if (!results?.length) return []
  const mapping = productMapping.value
  const series: { name: string; data: number[] }[] = []
  // 全店
  series.push({
    name: '全店',
    data: results.map(r => {
      const ttl = r!.ttl
      return ttl.gsv > 0 ? +(ttl.old_gsv / ttl.gsv * 100).toFixed(1) : 0
    }),
  })
  // 各产品
  for (const product of mapping) {
    series.push({
      name: product.name,
      data: results.map(r => {
        const matchingRows = r!.rows.filter(row => product.spu_classes.includes(row.name))
        const gsv = matchingRows.reduce((s, r) => s + r.gsv, 0)
        const old_gsv = matchingRows.reduce((s, r) => s + r.old_gsv, 0)
        return gsv > 0 ? +(old_gsv / gsv * 100).toFixed(1) : 0
      }),
    })
  }
  return series
})

// 行ID到分组信息的映射（用于span-method快速查找）
const rowSpanMap = computed(() => {
  const map = new Map<string, { firstIdx: number; span: number }>()
  let currentIdx = 0
  for (const group of groupedData.value) {
    for (let i = 0; i < group.rows.length; i++) {
      const row = group.rows[i]
      if (i === 0) {
        map.set(row.id, { firstIdx: currentIdx, span: group.rows.length })
      } else {
        map.set(row.id, { firstIdx: currentIdx, span: 0 })
      }
      currentIdx++
    }
  }
  return map
})

// span-method：合并产品列（Naive UI 正确签名）
function spanMethod(rowData: object, rowIndex: number, column: DataTableColumn & { key?: string }) {
  const row = rowData as TableRow
  if (column.key === 'product') {
    const info = rowSpanMap.value.get(row.id)
    if (info) {
      if (rowIndex === info.firstIdx) {
        return { rowspan: info.span, colspan: 1 }
      } else {
        return { rowspan: 0, colspan: 0 }
      }
    }
  }
  return { rowspan: 1, colspan: 1 }
}

// ─────────────────────────────────────────────────────────────
// 格式化工具函数（抽取公共逻辑）
// ─────────────────────────────────────────────────────────────
function fmtNumber(v: number, opts?: { minFractionDigits?: number; threshold?: number; suffix?: string }): string {
  const threshold = opts?.threshold ?? 10000
  const suffix = opts?.suffix ?? '万'
  const minFrac = opts?.minFractionDigits ?? 0
  const abs = Math.abs(v)
  if (abs >= threshold) {
    const sign = v < 0 ? '-' : ''
    return `${sign}${(abs / threshold).toFixed(1)}${suffix}`
  }
  return v.toLocaleString(undefined, { minimumFractionDigits: minFrac, maximumFractionDigits: minFrac })
}

function fmtMoney(v: number): string {
  return fmtNumber(v, { threshold: 10000, suffix: '万' })
}

function fmtAus(v: number): string {
  return fmtNumber(v, { threshold: 10000, suffix: '万', minFractionDigits: 1 })
}

function fmtInt(v: number): string {
  return v.toLocaleString()
}

function fmtPct(v: number): string {
  return `${(v * 100).toFixed(1)}%`
}

function fmtYoy(v: number): string {
  const sign = v > 0 ? '+' : ''
  // caller 已 *100 传 percentage 数值, pass-through
  return `${sign}${v.toFixed(1)}%`
}

function fmtPctChange(v: number): string {
  const sign = v > 0 ? '+' : ''
  // caller 已 *100 传 pp 数值, pass-through
  return `${sign}${v.toFixed(1)}pp`
}

function changeClass(v: number): string {
  if (v > 0) return 'text-rose-500'
  if (v < 0) return 'text-emerald-500'
  return 'text-slate-400'
}

// ─────────────────────────────────────────────────────────────
// 表格列定义（含变化行标注）
// ─────────────────────────────────────────────────────────────
type Row = TableRow

const columns: DataTableColumns<Row> = [
  {
    title: '产品',
    key: 'product',
    width: 100,
    fixed: 'left',
    align: 'center',
  },
  {
    title: '时间',
    key: 'weekLabel',
    width: 110,
    align: 'center',
  },
  {
    title: 'GSV\n(本周对比为%)',
    key: 'gsv',
    width: 95,
    align: 'right',
    render: (row) => row.isChangeRow || row.isYoyRow
      ? h('span', { class: changeClass(row.gsv) }, fmtYoy(row.gsv))
      : fmtMoney(row.gsv),
  },
  {
    title: '新客GSV\n(本周对比为%)',
    key: 'new_gsv',
    width: 95,
    align: 'right',
    render: (row) => row.isChangeRow || row.isYoyRow
      ? h('span', { class: changeClass(row.new_gsv) }, fmtYoy(row.new_gsv))
      : fmtMoney(row.new_gsv),
  },
  {
    title: '老客GSV\n(本周对比为%)',
    key: 'old_gsv',
    width: 95,
    align: 'right',
    render: (row) => row.isChangeRow || row.isYoyRow
      ? h('span', { class: changeClass(row.old_gsv) }, fmtYoy(row.old_gsv))
      : fmtMoney(row.old_gsv),
  },
  {
    title: '总客户数\n(本周对比为%)',
    key: 'users',
    width: 85,
    align: 'right',
    render: (row) => row.isChangeRow || row.isYoyRow
      ? h('span', { class: changeClass(row.users) }, fmtYoy(row.users))
      : fmtInt(row.users),
  },
  {
    title: '新客数\n(本周对比为%)',
    key: 'new_users',
    width: 75,
    align: 'right',
    render: (row) => row.isChangeRow || row.isYoyRow
      ? h('span', { class: changeClass(row.new_users) }, fmtYoy(row.new_users))
      : fmtInt(row.new_users),
  },
  {
    title: '老客数\n(本周对比为%)',
    key: 'old_users',
    width: 75,
    align: 'right',
    render: (row) => row.isChangeRow || row.isYoyRow
      ? h('span', { class: changeClass(row.old_users) }, fmtYoy(row.old_users))
      : fmtInt(row.old_users),
  },
  {
    title: '总客单价\n(本周对比为%)',
    key: 'aus',
    width: 85,
    align: 'right',
    render: (row) => row.isChangeRow || row.isYoyRow
      ? h('span', { class: changeClass(row.aus) }, fmtYoy(row.aus))
      : fmtAus(row.aus),
  },
  {
    title: '新客客单价\n(本周对比为%)',
    key: 'new_aus',
    width: 90,
    align: 'right',
    render: (row) => row.isChangeRow || row.isYoyRow
      ? h('span', { class: changeClass(row.new_aus) }, fmtYoy(row.new_aus))
      : fmtAus(row.new_aus),
  },
  {
    title: '老客客单价\n(本周对比为%)',
    key: 'old_aus',
    width: 90,
    align: 'right',
    render: (row) => row.isChangeRow || row.isYoyRow
      ? h('span', { class: changeClass(row.old_aus) }, fmtYoy(row.old_aus))
      : fmtAus(row.old_aus),
  },
  {
    title: '新客成交占比\n(本周对比为pp)',
    key: 'new_ratio_gsv',
    width: 100,
    align: 'right',
    render: (row) => row.isChangeRow || row.isYoyRow
      ? h('span', { class: changeClass(row.new_ratio_gsv) }, fmtPctChange(row.new_ratio_gsv))
      : fmtPct(row.new_ratio_gsv),
  },
  {
    title: '老客成交占比\n(本周对比为pp)',
    key: 'old_ratio_gsv',
    width: 100,
    align: 'right',
    render: (row) => row.isChangeRow || row.isYoyRow
      ? h('span', { class: changeClass(row.old_ratio_gsv) }, fmtPctChange(row.old_ratio_gsv))
      : fmtPct(row.old_ratio_gsv),
  },
  {
    title: '新客人数占比\n(本周对比为pp)',
    key: 'new_ratio_users',
    width: 100,
    align: 'right',
    render: (row) => row.isChangeRow || row.isYoyRow
      ? h('span', { class: changeClass(row.new_ratio_users) }, fmtPctChange(row.new_ratio_users))
      : fmtPct(row.new_ratio_users),
  },
  {
    title: '老客人数占比\n(本周对比为pp)',
    key: 'old_ratio_users',
    width: 100,
    align: 'right',
    render: (row) => row.isChangeRow || row.isYoyRow
      ? h('span', { class: changeClass(row.old_ratio_users) }, fmtPctChange(row.old_ratio_users))
      : fmtPct(row.old_ratio_users),
  },
]

// 行样式
function rowClassName(row: TableRow): string {
  if (row.isChangeRow) return 'bg-violet-50/50'
  if (row.isYoyRow) return 'bg-amber-50/50'
  return ''
}

// ── Sprint 174 XLSX 导出 (Q3) ──
const productCustomerXlsxColumns = computed<XlsxColumn[]>(() => [
  { header: '产品', key: 'product', width: 14 },
  { header: '时间', key: 'weekLabel', width: 14 },
  { header: 'GSV', key: 'gsv', width: 14, numFmt: '¥#,##0' },
  { header: 'GSV YOY', key: 'gsv_yoy', width: 14, numFmt: '+0.00%;-0.00%;0.00%' },
])
</script>

<template>
  <div>
    <!-- 数据来源说明 -->
    <div class="mb-4">
      <NAlert type="info" :bordered="false" class="text-xs">
        核心单品新老客数据来源: 订单表SQL聚合；全店资产/单品资产Tab数据来源: DMP PlatformDMP导出。两套口径的"用户"定义不同。
      </NAlert>
    </div>

    <LoadingState v-if="isLoading" description="正在加载各周品类数据..." />
    <ErrorState v-else-if="error" :message="String(error)" @retry="refetch" />
    <EmptyState v-else-if="!tableData.length" description="暂无品类数据" />

    <div v-else>
      <!-- 折线图：新客/老客成交占比趋势 -->
      <div class="grid grid-cols-1 xl:grid-cols-2 gap-4 mb-6">
        <div class="bi-card p-4">
          <div class="mb-0.5">
            <h3 class="text-sm font-semibold text-slate-800">新客成交占比趋势</h3>
            <p class="text-[11px] text-slate-500">各产品日度新客GSV占比变化</p>
          </div>
          <LineChart
            :x-axis-data="chartDayLabels"
            :series="newRatioSeries"
            :y-axis="{ name: '占比', formatter: (v: number) => v + '%' }"
            height="260px"
          />
        </div>
        <div class="bi-card p-4">
          <div class="mb-0.5">
            <h3 class="text-sm font-semibold text-slate-800">老客成交占比趋势</h3>
            <p class="text-[11px] text-slate-500">各产品日度老客GSV占比变化</p>
          </div>
          <LineChart
            :x-axis-data="chartDayLabels"
            :series="oldRatioSeries"
            :y-axis="{ name: '占比', formatter: (v: number) => v + '%' }"
            height="260px"
          />
        </div>
      </div>

      <div class="flex items-center justify-end mb-2">
        <ExportToolbar
          :filename="`产品_客群_滚动对比`"
          :columns="productCustomerXlsxColumns"
          :data="(tableData ?? []) as any[]"
          sheet-name="产品客群"
        />
      </div>
      <div class="overflow-x-auto rounded-lg border border-slate-200">
        <NDataTable
          :columns="columns"
          :data="tableData"
          :span-method="spanMethod"
          :pagination="false"
          :scroll-x="1800"
          :bordered="false"
          :single-line="false"
          :row-class-name="rowClassName"
          size="small"
        />
      </div>
    </div>
  </div>
</template>
