# 品类回购分析前端实现 — 全面代码探索报告

**项目路径**: `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3`  
**探索日期**: 2026-05-10  
**技术栈**: Vue 3 + TypeScript + Vite + naive-ui + TanStack Vue Query + Apache ECharts + Pinia + SheetJS (xlsx)

---

## 一、架构总览

### 1.1 模块划分

品类分析模块位于 `src/views/` 与 `src/views/category-tabs/` 下，由以下层级构成：

| 层级 | 文件/目录 | 职责 |
|------|-----------|------|
| **路由入口** | `src/router/index.ts` | `/category` → CategoryView；`/category-detail/:categoryId` → CategoryDetailView |
| **父视图** | `src/views/CategoryView.vue` | 7-Tab 容器，承载 KPI 卡片、饼图、概览表格及 5 个子 Tab 组件 |
| **子视图** | `src/views/category-tabs/*.vue` | 7 个独立分析子模块（详见下文） |
| **详情页** | `src/views/CategoryDetailView.vue` | 单品类下钻页：日趋势、RFM 分布、用户明细、CSV 导出 |
| **API 层** | `src/api/category.ts` | 12+ 个接口定义及 TypeScript 类型 |
| **共享组件** | `src/components/*.vue` | DataTablePro、EChartsWrapper、YOYBadge、ExportToolbar、MetricCard 等 |
| **状态管理** | `src/stores/filterStore.ts` | 全局筛选：日期范围、渠道、低价剔除、对比模式 |

### 1.2 数据流架构

```
AppFilterBar (UI) ──► filterStore (Pinia) ──► computed queryParams ──► useQuery (TanStack)
                                                              │
                                                              ▼
                                                    src/api/category.ts (axios client)
                                                              │
                                                              ▼
                                                    Backend API (/v1/category/*)
                                                              │
                                                              ▼
                                               Vue Component (charts + tables + badges)
```

**核心模式**: 所有数据获取均通过 `useQuery` + `computed(() => ['key', { ...toValue(params) }])` 实现响应式缓存。`toValue` 解包 + 对象展开运算符是强制写法，否则嵌套对象变更不会触发重新请求（代码中有多处显式注释警告此 bug）。

---

## 二、品类看板父视图：CategoryView.vue

**文件**: `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/views/CategoryView.vue`

### 2.1 结构

采用 `n-tabs` 7-Tab 布局：

1. **现状概览** (`name="overview"`) — 内置在 CategoryView 中
2. **连带分析** (`name="association"`) — `<MarketBasketTab />`
3. **品类复购周期** (`name="product-repurchase"`) — `<ProductClassRepurchaseTab />`
4. **品类回购分析** (`name="repurchase"`) — `<CategoryRepurchaseTab :category-options="categoryOptions" />`
5. **品类流转** (`name="flow"`) — `<CategoryFlowTab />`
6. **羊毛党分析** (`name="wool"`) — `<ValueTierTab />`
7. **风险预警** (`name="risk"`) — `<ChurnWarningTab />`

### 2.2 数据获取

- **`fetchCategoryOverview`**：全店 vs 会员的 GSV / 人数 / AUS / 新老客占比及同比，用于"单品概览"表格。
- **`fetchCategoryDistribution`**：品类分布（按 GSV 降序），用于饼图 + 品类明细表格，同时产出 `categoryOptions`（品类名称列表）透传给 `CategoryRepurchaseTab` 和 `MarketBasketTab` 作为下拉框选项。

### 2.3 表格列工厂函数

为了支撑"全店 / 会员"两张几乎结构相同的表格，以及"精简 / 详情"两种列模式，视图内定义了 4 个工厂函数：

```ts
gsvChildren(valKey, yoyKey)   // GSV 列 + YOY 列
usersChildren(valKey, yoyKey) // 人数列 + YOY 列
ausChildren(valKey, yoyKey)   // AUS 列 + YOY 列
ratioChildren(valKey, yoyKey) // 占比列 + YOY 列
```

以及 `addGroupSep()` 给每组的第一个子列添加 `group-sep` CSS 类名，实现组间竖线分隔（`:deep(.n-data-table td.group-sep)`）。

### 2.4 列模式切换

- `showDetailAll` / `showDetailMember` 两个 ref 控制"精简列"（compactColumns / compactMemberColumns）与"完整列"（allColumns / memberColumns）的切换。
- 完整列启用 `:scroll-x="2500"` 以支持横向滚动。

---

## 三、品类回购分析 Tab：CategoryRepurchaseTab.vue

**文件**: `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/views/category-tabs/CategoryRepurchaseTab.vue`

### 3.1 业务目标

回答："买了某品类的老客，多久回来？回来买了同品还是其他品类？" —— 识别品类复购周期和品类间的承接关系。

### 3.2 Props

```ts
defineProps<{
  categoryOptions?: string[]   // 从 CategoryView.distributionData 传入的品类列表
}>()
```

### 3.3 核心状态

| 状态 | 类型 | 说明 |
|------|------|------|
| `targetCategory` | `string` | 当前选中的目标品类（默认取 `categoryOptions[0]`） |
| `activeTable` | `'same' \| 'cross' \| 'member_same' \| 'member_cross'` | 4 张表格的视图切换 |

### 3.4 API 调用

**`fetchCategoryRepurchaseFlow`**（endpoint: `GET /v1/category/repurchase-flow`）

参数：
```ts
{
  start_date, end_date, category: targetCategory.value,
  level: 'class', metric_type: 'GSV',
  channel, exclude_channels
}
```

返回数据结构（3 年对比）：
```ts
interface CategoryRepurchaseFlowResponse {
  year_label: string
  comp_year_label: string
  prev2_year_label: string
  target_category: string
  same_category_rows: CategoryRepurchaseFlowRow[]
  cross_category_rows: CategoryRepurchaseFlowRow[]
  member_same_category_rows: CategoryRepurchaseFlowRow[]
  member_cross_category_rows: CategoryRepurchaseFlowRow[]
}
```

每行数据字段（以 `same_category_rows` 为例）：
```ts
interface CategoryRepurchaseFlowRow {
  r_segment: string              // R 区间标签（T-30, T-90, T-180, T-365, T-730, 沉睡）
  hist_users_current: number     // 当期历史购买人数
  repurchase_users_current: number
  repurchase_rate_current: number
  repurchase_gsv_current: number
  repurchase_gsv_ratio_current: number
  hist_users_comp: number        // 去年同期（Y-1）
  repurchase_rate_comp: number
  hist_users_prev2: number       // 前年（Y-2）
  repurchase_rate_prev2: number
  yoy_hist_users: number | null  // 同比变化
  yoy_repurchase_users: number | null
  yoy_repurchase_rate: number | null
  yoy_repurchase_gsv: number | null
  yoy_repurchase_gsv_ratio: number | null
}
```

### 3.5 表格列定义（关键模式）

采用 **分组表头（Grouped Headers）** 组织 3 年数据：

```
产品分类 | 当期(current_year) | 同比(yoy) | 去年同期(comp_year) | 前年(prev2_year)
         | 人数 | 回购率 | GSV | ...
```

实现方式：

```ts
const sameCategoryColumns = computed(() => [
  { title: 'R区间', key: 'r_segment', fixed: 'left', width: 110 },
  {
    title: yearLabel.value,        // e.g. "2025"
    key: 'current_year',
    align: 'center',
    children: [
      { title: '人数', key: 'hist_users_current', render: ... },
      { title: '回购率', key: 'repurchase_rate_current', render: ... },
      { title: '回购GSV', key: 'repurchase_gsv_current', render: ... },
      { title: 'GSV占比', key: 'repurchase_gsv_ratio_current', render: ... },
    ]
  },
  {
    title: '同比', key: 'yoy',
    align: 'center',
    children: [
      { title: '人数', key: 'yoy_hist_users', render: (row) => h(YOYBadge, { value: row.yoy_hist_users }) },
      { title: '回购率', key: 'yoy_repurchase_rate', render: ... },
      // ... 所有同比列均使用 YOYBadge 渲染
    ]
  },
  {
    title: compYearLabel.value,    // e.g. "2024"
    key: 'comp_year',
    align: 'center',
    children: [
      { title: '人数', key: 'hist_users_comp', render: ... },
      { title: '回购率', key: 'repurchase_rate_comp', render: ... },
    ]
  },
  {
    title: prev2YearLabel.value,   // e.g. "2023"
    key: 'prev2_year',
    align: 'center',
    children: [
      { title: '人数', key: 'hist_users_prev2', render: ... },
      { title: '回购率', key: 'repurchase_rate_prev2', render: ... },
    ]
  },
])
```

**4 张表格复用同一套列定义逻辑**：`sameCategoryColumns` 与 `crossCategoryColumns` 结构相同，只是数据行来源不同（`same_category_rows` vs `cross_category_rows`）。会员版本（`member_same_category_rows` / `member_cross_category_rows`）同理。

### 3.6 3 年柱状图

```ts
const repurchaseRateChartOption = computed(() => {
  // 使用 ECharts 多 series bar 图
  // series[0]: 当期回购率
  // series[1]: 去年同期回购率
  // series[2]: 前年回购率
})
```

图表展示同品类回购率与跨品类回购率在各 R 区间的对比，直观呈现"同品复购 vs 跨品迁移"差异。

### 3.7 业务注释

组件模板中包含大量业务说明文案，如：

> "同品类回购 = 买了B5面膜的人，下次回来又买了B5面膜；跨品类回购 = 买了B5面膜的人，下次回来买了其他品类。同品回购率高说明品类黏性高，跨品回购率高说明该品类适合作为引流品。"

---

## 四、品类复购周期 Tab：ProductClassRepurchaseTab.vue

**文件**: `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/views/category-tabs/ProductClassRepurchaseTab.vue`

### 4.1 业务目标

回答："各品类的复购周期多长？同品类复购 vs 跨品类回购的表现差异？" —— 识别高黏性品类和引流型品类。

### 4.2 核心状态

| 状态 | 类型 | 说明 |
|------|------|------|
| `activeView` | `'same' \| 'cross'` | 同品类 / 跨品类视图切换 |

### 4.3 API 调用

复用了 **health 模块**的 API：

```ts
import { fetchRepurchaseCycle } from '@/api/health'
```

endpoint: `GET /v1/health/repurchase-cycle`（注意：虽然是品类分析，但后端接口归类在 health 下）

参数与 health 模块一致：
```ts
{ start_date, end_date, metric_type: 'ALL', channel, exclude_channels }
```

### 4.4 表格列模式

此组件引入了**可展开列（expandable columns）**模式：

```ts
const simpleColumns = computed(() => [
  { title: '产品分类', key: 'name', fixed: 'left' },
  { title: '复购周期(中位数)', key: 'repurchase_cycle_median', render: ... },
  { title: '复购周期(平均)', key: 'repurchase_cycle_mean', render: ... },
  { title: '同品类复购率', key: 'same_category_repurchase_rate', render: ... },
  { title: '跨品类复购率', key: 'cross_category_repurchase_rate', render: ... },
])

const expandedColumns = computed(() => [
  // 在 simpleColumns 基础上增加：
  // 30天/90天/180天/365天回购人数、回购率、GSV、GSV占比
  // 以及 DaysChangeBadge（展示与上期相比的天数变化）
])
```

通过 `showExpanded.value` 切换精简/完整视图。

### 4.5 自定义渲染：DaysChangeBadge

```ts
function renderDaysChange(row: RepurchaseCycleRow, key: 'same_category_days_change' | 'cross_category_days_change') {
  const v = row[key]
  if (v == null) return '—'
  const color = v < 0 ? 'text-emerald-600' : v > 0 ? 'text-red-500' : 'text-slate-500'
  const sign = v > 0 ? '+' : ''
  const icon = v < 0 ? '↓' : v > 0 ? '↑' : '→'
  return h('span', { class: color }, `${sign}${v.toFixed(0)}天 ${icon}`)
}
```

天数减少（负数）为绿色（周期缩短，变好），天数增加为正红色（周期拉长，变差）。

---

## 五、其他 category-tabs 概览

### 5.1 CategoryFlowTab.vue（品类流转）

**文件**: `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/views/category-tabs/CategoryFlowTab.vue`

- **桑基图**：展示"首购品类 → 次购品类"的用户流转，使用 ECharts `sankey` 类型。
- **DAG 保障**：后端数据可能存在有向环（如 A→B→A），前端通过 `breakCycles()` 函数（DFS 检测 + 移除最小流量边）打破环路，确保桑基图可渲染。
- **弱连接过滤**：只保留 `value >= 5 && >= maxValue * 0.02` 的 link，避免线条过密。
- **流转矩阵**：行=来源品类，列=目标品类，值=流转人数。
- **时序关联**：选择目标品类后，展示"买 X 之前买了什么"和"买 X 之后买了什么"两张表。

### 5.2 MarketBasketTab.vue（连带分析）

**文件**: `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/views/category-tabs/MarketBasketTab.vue`

- **购物篮分析**：分析同一订单中目标品类与关联品类的共现关系。
- **核心指标**：支持度（support）、置信度（confidence）、提升度（lift）、连带人均消费（co_aus）、消费提升（gsv_lift）。
- **两种 GSV 口径**：
  - `co_gsv`（整单）：跨品类重复计算，用于评估连带订单规模。
  - `co_own_gsv`（自身）：可加总不重复，用于评估实际营收贡献。
- **交互功能**：目标品类选择、排序（关联订单数/置信度/提升度/人均消费/消费提升）、最小支持度过滤、精简/详情列切换、Excel 导出。
- **Lift 业务化解读**：`liftInterpret()` 函数将数值翻译为业务语言（强关联 / 中等关联 / 弱关联 / 无关联 / 负关联）。

### 5.3 ValueTierTab.vue（羊毛党分析）

**文件**: `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/views/category-tabs/ValueTierTab.vue`

- **双轴折线图**：红色轴=羊毛党占比，蓝色轴=高价值占比，一眼识别"红高蓝低"的危险品类。
- **价值评分表**：综合评分 = 高价值排名×0.4 + (100-羊毛党排名)×0.3 + 会员占比排名×0.2 + AUS排名×0.1，等级 A-E。
- **多窗口羊毛党对比**：支持"当前周期 / 近30天 / 近90天 / 全部历史"切换，识别近期低价渠道是否引入过多低质量用户。

### 5.4 ChurnWarningTab.vue（风险预警）

**文件**: `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/views/category-tabs/ChurnWarningTab.vue`

- **流失严重度散点图**：X=本期用户数(log)，Y=MoM变化率，气泡大小=流失人数。左下红区=规模大+下滑快，优先关注。
- **MoM 柱状图**：绿色=增长，红色=下滑。
- **流失明细表**：区分"品类间流失"（用户转向其他品类）与"沉默流失"（用户彻底无订单），并给出流失去向 TOP2 及挽回建议。

### 5.5 NewcomerInsightTab.vue（新客洞察 — 内置在 CategoryView 的 overview Tab 中，但独立文件）

**文件**: `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/views/category-tabs/NewcomerInsightTab.vue`

- **新客首购品类 TOP10 柱状图**
- **复购路径和弦图（Graph 替代）**：ECharts 5 不支持 chord，使用固定坐标的 `graph` 类型，左侧=首购品类，右侧=复购品类，连线宽度∝复购人数。
- **首购品类明细表**：品类内复购率、跨品类复购率、复购首选品类、老客占比、老客 AUS。

---

## 六、品类详情页：CategoryDetailView.vue

**文件**: `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/views/CategoryDetailView.vue`

### 6.1 路由参数

```ts
const categoryId = computed(() => String(route.params.categoryId))
```

### 6.2 数据获取

- **`fetchCategoryDailyTrend`**：日/周/月趋势（根据日期跨度自动选择粒度：>90天→monthly，>30天→weekly，否则 daily）。返回 GMV、用户数、AUS、新客占比时间序列。
- **`fetchCategoryUserList`**：TOP100 用户明细，包含用户ID、昵称、订单数、累计GMV、首购/最近购买日期、RFM 象限、会员/羊毛党标记。

### 6.3 可视化

- **多轴趋势图**：柱状图（GMV）+ 折线图（用户数、AUS、新客占比），使用双 Y 轴。
- **RFM 分布饼图**：8 象限颜色固定映射（Champions=#533afd, Loyal=#8b5cf6, ...）。
- **新老客转化漏斗**：纯前端静态参考值（首购→30天复购→90天复购→忠诚用户）。

### 6.4 CSV 导出

原生浏览器 Blob + URL.createObjectURL 实现，导出字段：用户ID、昵称、订单数、累计GMV、首购日期、最近购买、象限、会员、羊毛党。

---

## 七、API 层：src/api/category.ts

**文件**: `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/api/category.ts`

### 7.1 接口清单

| 函数 | Endpoint | 用途 |
|------|----------|------|
| `fetchCategoryDistribution` | `GET /v1/category/distribution` | 品类分布（饼图、明细表） |
| `fetchCategoryOverview` | `GET /v1/category/overview` | 单品概览（全店/会员） |
| `fetchCategorySegmentMatrix` | `GET /v1/category/segment` | 品类 × RFM 象限矩阵 |
| `fetchCategoryUserProfile` | `GET /v1/category/user-profile` | 品类用户画像 |
| `fetchCategoryValueTier` | `GET /v1/category/value-tier` | 羊毛党 vs 高价值分析 |
| `fetchCategoryFlow` | `GET /v1/category/flow` | 品类流转桑基图 + 矩阵 |
| `fetchMarketBasket` | `GET /v1/category/basket` | 购物篮连带分析 |
| `fetchCategoryChurn` | `GET /v1/category/churn` | 流失预警 |
| `fetchCategoryRepurchaseFlow` | `GET /v1/category/repurchase-flow` | **品类回购分析核心接口** |
| `fetchCategoryDailyTrend` | `GET /v1/category/detail/daily-trend` | 品类日趋势 |
| `fetchCategoryUserList` | `GET /v1/category/detail/user-list` | 品类用户明细 |
| `fetchCategoryNewcomerInsight` | `GET /v1/category/newcomer-insight` | 新客洞察 |

### 7.2 类型设计特点

- 所有响应接口均包含 `data_quality_note?: string` 字段，用于前端展示数据质量提示。
- 购物篮分析使用嵌套结构：`MarketBasketYoYItem` 包含 `current: MarketBasketItem` 和 `previous?: MarketBasketItem`，支持同比变化计算。
- 品类回购分析使用扁平化 3 年字段：`*_current` / `*_comp` / `*_prev2` + `yoy_*`。

---

## 八、共享组件深度解析

### 8.1 YOYBadge.vue

**文件**: `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/components/YOYBadge.vue`

```vue
<script setup lang="ts">
defineProps<{
  value: number | null | undefined
  unit?: '%' | 'pp'   // 默认 '%'
}>()
</script>
```

- 正数 → 绿色 `+X% ↑`
- 负数 → 红色 `X% ↓`
- null / undefined → `—`
- 被大量使用在表格的 `render` 函数中：`render: (row) => h(YOYBadge, { value: row.gsv_yoy })`

### 8.2 ExportToolbar.vue

**文件**: `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/components/ExportToolbar.vue`

支持两种导出：
1. **图表导出**：传入 `chart-ref`（EChartsWrapper 实例），调用 `getDataURL()` 下载 PNG。
2. **Excel 导出**：传入 `columns`（XlsxColumn[]）、`data`、`sheet-name`，调用 `exportSheetToXlsx()`。

### 8.3 DataTablePro.vue

**文件**: `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/components/DataTablePro.vue`

对 `naive-ui` `NDataTable` 的薄封装，标准化：
- 默认 `size="small"`
- 默认 `bordered`
- 默认 `pagination={{ pageSize: 10 }}`
- 支持 `striped`（隔行变色，配合 `:deep(.n-data-table-td--striped)`）
- 支持 `maxHeight`、`scrollX`
- 统一 `rowKey` 处理

### 8.4 EChartsWrapper.vue

**文件**: `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/components/EChartsWrapper.vue`

- 封装 `vue-echarts`（或原生 ECharts init），统一主题、tooltip 样式、resize 监听。
- 提供 `getDataURL()` 方法供 ExportToolbar 调用。
- 所有图表 option 均为 `computed`，数据变更自动重绘。

### 8.5 MetricCard.vue

**文件**: `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/components/MetricCard.vue`

KPI 卡片组件，支持：
- `title`、`value`、`subtitle`（业务含义）
- `formula`（计算公式）
- `loading` 状态骨架屏
- 格式化：`number` / `currency` / `percent`

### 8.6 AppFilterBar.vue

**文件**: `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/components/AppFilterBar.vue`

全局筛选栏，两行布局：
- **第一行**：当前日期（daterange）、维度（periodType）、渠道（channel）、低价筛选（excludeLowPrice switch）
- **第二行**：对比日期（daterange，始终可编辑）、对比模式（auto_yoy / auto_mom / custom）

**关键交互逻辑**：
- 选择 periodType（非 custom）→ 自动计算日期范围并赋值给 filterStore。
- 手动修改当前日期 → 自动切为 custom periodType。
- 点击对比日期选择器 → 自动切为 custom 对比模式，并保留当前自动计算的日期作为起点。
- 对比日期修改 → 自动切为 custom 模式（通过 `isProgrammaticUpdate` flag 防止循环）。

---

## 九、状态管理：filterStore.ts

**文件**: `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/stores/filterStore.ts`

### 9.1 State

```ts
const dateRange = ref<[string, string]>(getPeriodDateRange('MTD')!)
const channel = ref<string>('全店')
const dimension = ref<string>('channel')
const dimensionValue = ref<string>('')
const periodType = ref<PeriodType>('MTD')
const excludeLowPrice = ref<boolean>(false)
const compareMode = ref<CompareMode>('auto_yoy')
const compareDateRange = ref<[string, string] | null>(null)
```

### 9.2 Computed

- **`computedCompareDateRange`**：始终返回有效的对比日期范围（auto_yoy → 去年同期的计算结果）。
- **`compareParams`**：传给后端的对比参数：
  - `auto_yoy` → `null`（后端原生三列对比，不需要覆盖）
  - `auto_mom` → 自动计算的环比日期
  - `custom` → 用户自选的对比日期
- **`compareLabel`**：表头显示用（YOY / 环比 / 对比）。

### 9.3 Watch 联动

```ts
// 切到 custom 对比模式时，自动填充默认对比日期（同比）
watch(compareMode, ...)

// 手动修改对比日期 → 自动切为 custom
watch(compareDateRange, ...)

// 当前日期变化 → custom 模式下重新填入同比日期
watch(dateRange, ...)

// 切换维度 → 清空维度值
watch(dimension, ...)
```

---

## 十、关键技术模式与最佳实践

### 10.1 QueryKey 展开模式（强制）

```ts
// ✅ 正确 — 使用对象展开，确保嵌套属性变更触发新请求
queryKey: computed(() => ['category-flow', { ...toValue(queryParams) }]),

// ❌ 错误 — 直接传入对象引用，channel 变更不会触发请求
queryKey: computed(() => ['category-flow', toValue(queryParams)]),
```

此模式在代码库中被反复强调，几乎每个 `useQuery` 调用都遵循这一写法。

### 10.2 3 年对比数据模型

后端返回的数据普遍采用以下字段命名约定：

| 后缀 | 含义 | 示例 |
|------|------|------|
| `*_current` | 当期（当前选择的日期范围） | `hist_users_current` |
| `*_comp` | 对比期（Y-1，去年同期） | `hist_users_comp` |
| `*_prev2` | 前二期（Y-2，前年同期） | `hist_users_prev2` |
| `yoy_*` | 同比变化（pp 或百分比） | `yoy_hist_users` |

### 10.3 渠道参数处理

```ts
channel: filterStore.channel === '全店' ? undefined : filterStore.channel
```

"全店"作为 UI 上的默认选项，传给后端时需转为 `undefined`，避免后端将其作为具体渠道过滤。

### 10.4 低价渠道剔除

```ts
import { LOW_PRICE_CHANNELS } from '@/constants/channels'
// LOW_PRICE_CHANNELS = ['U先派样', '百补派样', '赠品&0.01', '其他']

exclude_channels: filterStore.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined
```

通过 `exclude_channels` 参数传给后端，实现统一过滤。

### 10.5 表格列工厂与复用

CategoryView 中通过 `gsvChildren`、`usersChildren`、`ausChildren`、`ratioChildren` 四个工厂函数生成重复的"值+YOY"子列组合，避免手写 50+ 列定义。`addGroupSep()` 给每组的第一个子列添加分隔线类名。

### 10.6 图表 Option 的 computed 模式

所有 ECharts option 均为 `computed(() => { ... })`，内部先判断 `if (!data.value) return {}`，确保无数据时渲染空图表而非报错。tooltip、legend、grid 等样式在每个组件中重复定义，保持视觉一致性。

### 10.7 数据质量提示

几乎每个 Tab 组件的模板顶部都包含：

```vue
<div class="flex items-center justify-end gap-2">
  <span v-if="data?.data_stale" class="...">⚠ 数据更新中</span>
  <n-tooltip v-if="data?.data_quality_note">
    <template #trigger>
      <span class="...">i</span>
    </template>
    <span>{{ data.data_quality_note }}</span>
  </n-tooltip>
</div>
```

---

## 十一、文件清单（绝对路径）

### 核心视图

- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/views/CategoryView.vue`
- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/views/CategoryDetailView.vue`
- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/views/RFMView.vue`
- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/views/CustomerHealthView.vue`

### category-tabs

- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/views/category-tabs/CategoryRepurchaseTab.vue`
- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/views/category-tabs/ProductClassRepurchaseTab.vue`
- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/views/category-tabs/CategoryFlowTab.vue`
- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/views/category-tabs/MarketBasketTab.vue`
- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/views/category-tabs/ValueTierTab.vue`
- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/views/category-tabs/ChurnWarningTab.vue`
- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/views/category-tabs/NewcomerInsightTab.vue`

### API 层

- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/api/category.ts`
- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/api/health.ts`
- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/api/flow.ts`
- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/api/types.ts`

### 共享组件

- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/components/YOYBadge.vue`
- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/components/ExportToolbar.vue`
- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/components/DataTablePro.vue`
- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/components/EChartsWrapper.vue`
- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/components/MetricCard.vue`
- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/components/AppFilterBar.vue`
- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/components/LoadingState.vue`
- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/components/ErrorState.vue`
- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/components/EmptyState.vue`

### 状态与工具

- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/stores/filterStore.ts`
- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/constants/channels.ts`
- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/utils/exportXlsx.ts`
- `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3/src/router/index.ts`

---

## 十二、可扩展性观察

1. **新增品类分析 Tab**：在 `CategoryView.vue` 的 `<n-tabs>` 中新增 `<n-tab-pane>`，引入新的子组件即可。子组件遵循相同模式：接收 `filterStore` → 定义 `queryParams` computed → `useQuery` 获取数据 → `computed` 生成 chart option / table columns → 模板渲染。

2. **新增表格列**：使用 `hColTip()` 辅助函数（如 MarketBasketTab 所示）可快速添加带 tooltip 的表头。

3. **新增 API 接口**：在 `src/api/category.ts` 中定义接口类型 + 函数，然后在组件中导入使用。axios client 已统一封装在 `src/api/index.ts`。

4. **统一主题色**：所有图表通过 `CHART_COLORS`（来自 `src/composables/useChartTheme`）保持一致配色，修改主题只需改一处。

---

*报告结束*
