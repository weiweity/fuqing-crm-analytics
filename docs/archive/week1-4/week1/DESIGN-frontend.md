# R 区间流转看板 — 前端设计文档

**版本**: v1.0  
**日期**: 2026-04-17  
**关联 PRD**: `docs/week1/PRD-rfm-r-flow.md`

---

## 1. 页面位置

嵌入 `RFMView.vue`，作为 `n-tabs` 的第 3 个 Tab：

```vue
<n-tabs type="line" animated>
  <n-tab-pane name="matrix" tab="流转矩阵">...</n-tab-pane>
  <n-tab-pane name="sankey" tab="桑基图">...</n-tab-pane>
  <n-tab-pane name="r-flow" tab="R 区间流转">
    <!-- 新增内容 -->
  </n-tab-pane>
</n-tabs>
```

---

## 2. 数据层设计

### 2.1 API 调用

```ts
// src/api/rfm.ts（在现有 flow.ts 同级新增或扩展）
export interface RFMRFlowParams {
  start_date: string
  end_date: string
  channel?: string
  metric_type?: 'GSV' | 'GMV'
}

export interface RFMRFlowRow {
  r_segment: string
  hist_users_current: number
  repurchase_users_current: number
  repurchase_rate_current: number
  repurchase_gsv_current: number
  repurchase_gsv_ratio_current: number
  hist_users_comp: number
  repurchase_users_comp: number
  repurchase_rate_comp: number
  repurchase_gsv_comp: number
  repurchase_gsv_ratio_comp: number
  hist_users_prev2: number
  repurchase_users_prev2: number
  repurchase_rate_prev2: number
  repurchase_gsv_prev2: number
  repurchase_gsv_ratio_prev2: number
  yoy_hist_users: number | null
  yoy_repurchase_users: number | null
  yoy_repurchase_rate: number | null
  yoy_repurchase_gsv: number | null
  yoy_repurchase_gsv_ratio: number | null
}

export interface RFMRFlowResponse {
  year_label: string
  comp_year_label: string
  prev2_year_label: string
  metric_type: string
  rows: RFMRFlowRow[]
}

export function fetchRFMRFlow(params: RFMRFlowParams): Promise<RFMRFlowResponse> {
  return client.get('/v1/rfm/r-flow', { params })
}
```

### 2.2 View 层查询

在 `RFMView.vue` 的 `script setup` 中新增：

```ts
const rFlowQueryParams = computed(() => ({
  start_date: filterStore.dateRange[0],
  end_date: filterStore.dateRange[1],
  channel: filterStore.channel === '全店' ? undefined : filterStore.channel,
  metric_type: 'GSV',
}))

const { data: rFlowData, isLoading: rFlowLoading, error: rFlowError, refetch: rFlowRefetch } = useQuery({
  queryKey: ['rfm-r-flow', rFlowQueryParams],
  queryFn: () => {
    const p = toValue(rFlowQueryParams)
    return fetchRFMRFlow(p)
  },
  staleTime: 60_000,
})
```

---

## 3. 可视化：回购率 3 年对比柱状图

### 3.1 ECharts Option

```ts
const repurchaseRateChartOption = computed(() => {
  if (!rFlowData.value) return {}
  const rows = rFlowData.value.rows.filter(r => r.r_segment !== '已购客TTL')
  const segments = rows.map(r => r.r_segment)

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      textStyle: { color: '#0f172a', fontSize: 12 },
      extraCssText: 'box-shadow: 0 4px 12px -2px rgba(0,0,0,0.08); border-radius: 4px;',
      formatter: (params: any[]) => {
        let html = `<div class="font-semibold mb-1">${params[0].name}</div>`
        params.forEach(p => {
          html += `<div class="flex items-center gap-2 text-xs">
            <span class="w-2 h-2 rounded-full" style="background:${p.color}"></span>
            <span class="text-slate-500">${p.seriesName}:</span>
            <span class="font-medium text-slate-800">${(p.value * 100).toFixed(2)}%</span>
          </div>`
        })
        return html
      },
    },
    legend: {
      data: [`${rFlowData.value.year_label}年`, `${rFlowData.value.comp_year_label}年`, `${rFlowData.value.prev2_year_label}年`],
      top: 0,
      icon: 'circle',
      itemGap: 16,
      textStyle: { color: '#64748b', fontSize: 11 },
    },
    grid: { left: 12, right: 12, top: 40, bottom: 8, containLabel: true },
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
        name: `${rFlowData.value.year_label}年`,
        type: 'bar',
        data: rows.map(r => r.repurchase_rate_current),
        itemStyle: { color: '#2563eb', borderRadius: [3, 3, 0, 0] },
        barGap: '20%',
      },
      {
        name: `${rFlowData.value.comp_year_label}年`,
        type: 'bar',
        data: rows.map(r => r.repurchase_rate_comp),
        itemStyle: { color: '#60a5fa', borderRadius: [3, 3, 0, 0] },
      },
      {
        name: `${rFlowData.value.prev2_year_label}年`,
        type: 'bar',
        data: rows.map(r => r.repurchase_rate_prev2),
        itemStyle: { color: '#94a3b8', borderRadius: [3, 3, 0, 0] },
      },
    ],
  }
})
```

### 3.2 图表容器

```vue
<div class="bi-card p-4 mb-5">
  <h3 class="text-sm font-semibold text-slate-800 mb-0.5">回购率 3 年对比</h3>
  <p class="text-[11px] text-slate-500 mb-3">各 R 区间老客唤醒效率变化</p>
  <EChartsWrapper :option="repurchaseRateChartOption" height="260px" />
</div>
```

---

## 4. 表格设计

### 4.1 Columns 定义

```ts
const rFlowColumns = computed<DataTableColumns<RFMRFlowRow>>(() => {
  const yr = rFlowData.value?.year_label || String(new Date().getFullYear())
  const yr2 = rFlowData.value?.comp_year_label || String(new Date().getFullYear() - 1)
  const yr3 = rFlowData.value?.prev2_year_label || String(new Date().getFullYear() - 2)

  return [
    {
      title: 'R 区间',
      key: 'r_segment',
      width: 140,
      fixed: 'left',
      align: 'center',
    },
    {
      title: `${yr}年`,
      key: 'current_year',
      align: 'center',
      children: [
        {
          title: '历史人群量级',
          key: 'hist_users_current',
          width: 110,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => row.hist_users_current.toLocaleString(),
        },
        {
          title: '回购人数',
          key: 'repurchase_users_current',
          width: 100,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => row.repurchase_users_current.toLocaleString(),
        },
        {
          title: '回购率',
          key: 'repurchase_rate_current',
          width: 90,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => `${(row.repurchase_rate_current * 100).toFixed(1)}%`,
        },
        {
          title: '回购金额',
          key: 'repurchase_gsv_current',
          width: 110,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => `¥${(row.repurchase_gsv_current / 10000).toFixed(1)}万`,
        },
        {
          title: '占比',
          key: 'repurchase_gsv_ratio_current',
          width: 80,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => `${(row.repurchase_gsv_ratio_current * 100).toFixed(1)}%`,
        },
      ],
    },
    {
      title: 'YOY',
      key: 'yoy',
      align: 'center',
      children: [
        {
          title: '历史人群',
          key: 'yoy_hist_users',
          width: 100,
          align: 'center',
          render: (row) => h(YOYBadge, { value: row.yoy_hist_users }),
        },
        {
          title: '回购人数',
          key: 'yoy_repurchase_users',
          width: 100,
          align: 'center',
          render: (row) => h(YOYBadge, { value: row.yoy_repurchase_users }),
        },
        {
          title: '回购率',
          key: 'yoy_repurchase_rate',
          width: 90,
          align: 'center',
          render: (row) => h(YOYBadge, { value: row.yoy_repurchase_rate }),
        },
        {
          title: '回购金额',
          key: 'yoy_repurchase_gsv',
          width: 100,
          align: 'center',
          render: (row) => h(YOYBadge, { value: row.yoy_repurchase_gsv }),
        },
        {
          title: '占比',
          key: 'yoy_repurchase_gsv_ratio',
          width: 90,
          align: 'center',
          render: (row) => h(YOYBadge, { value: row.yoy_repurchase_gsv_ratio }),
        },
      ],
    },
    {
      title: `${yr3}年`,
      key: 'prev2_year',
      align: 'center',
      children: [
        {
          title: '历史人群量级',
          key: 'hist_users_prev2',
          width: 110,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => row.hist_users_prev2.toLocaleString(),
        },
        {
          title: '回购人数',
          key: 'repurchase_users_prev2',
          width: 100,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => row.repurchase_users_prev2.toLocaleString(),
        },
        {
          title: '回购率',
          key: 'repurchase_rate_prev2',
          width: 90,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => `${(row.repurchase_rate_prev2 * 100).toFixed(1)}%`,
        },
        {
          title: '回购金额',
          key: 'repurchase_gsv_prev2',
          width: 110,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => `¥${(row.repurchase_gsv_prev2 / 10000).toFixed(1)}万`,
        },
        {
          title: '占比',
          key: 'repurchase_gsv_ratio_prev2',
          width: 80,
          align: 'center',
          className: 'bi-cell-number',
          render: (row) => `${(row.repurchase_gsv_ratio_prev2 * 100).toFixed(1)}%`,
        },
      ],
    },
  ]
})
```

### 4.2 表格容器

```vue
<div class="bi-card p-4">
  <h3 class="text-sm font-semibold text-slate-800 mb-0.5">R 区间流转详情</h3>
  <p class="text-[11px] text-slate-500 mb-3">老客分区回购表现 — 3 年同比</p>
  <ErrorState v-if="rFlowError" :message="(rFlowError as Error).message" @retry="rFlowRefetch()" />
  <LoadingState v-else-if="rFlowLoading" />
  <EmptyState v-else-if="!rFlowData?.rows?.length" description="暂无数据" />
  <DataTablePro
    v-else
    :columns="rFlowColumns"
    :data="rFlowData.rows"
    :pagination="{ pageSize: 12 }"
    :scroll-x="1100"
  />
</div>
```

---

## 5. 样式与交互规范

| 项 | 规范 |
|---|------|
| **TTL 行样式** | 后端返回数据中 `已购客TTL` 放在最后一行，DataTablePro 默认不处理加粗；如需加粗，可用 `:row-class-name` 匹配 `r_segment === '已购客TTL'` 加 `font-semibold` |
| **数值对齐** | 所有数值列 `align: 'center'`，使用 `bi-cell-number` 类统一字号和字色 |
| **YOY 颜色** | 复用 `YOYBadge` 组件，正数绿色、负数红色、0/null 灰色 |
| **金额单位** | 统一除以 10000 展示为「¥X.X 万」，人数用 `toLocaleString()` |
| **Loading/Error** | 严格遵循现有 4 状态模式：Error → Loading → Empty → Data |

---

## 6. 开发 checklist

- [ ] 在 `src/api/rfm.ts`（或 `flow.ts`）新增 `fetchRFMRFlow` 及类型
- [ ] 在 `RFMView.vue` 中新增「R 区间流转」Tab
- [ ] 接入 `useQuery` 获取数据
- [ ] 实现回购率柱状图 ECharts option
- [ ] 实现 DataTable columns（16 列分组表头）
- [ ] 后端实现 `/v1/rfm/r-flow` 接口并注册到 `main.py`
- [ ] 更新 `contracts/schemas.py` 新增 `RFMRFlowRequest/Response/Row`
- [ ] 跑通 `openapi-typescript` 自动生成前端类型
