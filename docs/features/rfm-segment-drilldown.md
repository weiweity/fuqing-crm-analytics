# RFM 象限品类回购下钻

> 点击回购率柱状图中的象限柱子 → 页面内展开该象限下各品类的回购率拆解

## 1. 业务背景

**问题**：老客分析 → RFM分析 → 回购率3年对比柱状图，能看到8个象限的整体回购率趋势，但当某个象限（如"重要价值客户"）回购率下滑时，无法知道**具体是哪个品类拖了后腿**。

**目标**：点击柱状图中的某个象限 → 展开详情 → 看到该象限下各品类的回购率，识别下滑品类，指导精准运营。

**核心用户故事**：
> 作为运营，我发现"重要价值客户"回购率同比下滑了3pp，我点击柱状图进入详情，
> 看到"B5面膜"品类该象限回购率同比下降了8pp，而"医用凝胶"品类反而上升了2pp，
> 于是我判断B5面膜品类的重点价值用户需要重点维护。

---

## 2. 交互设计

### 2.1 触发方式

在 `health/ValueTierTab.vue` 的"回购率 3 年对比"柱状图上，为每个柱子添加点击事件：

- 光标变为 `pointer`，hover 时柱子加深/加边框，提示可点击
- 点击任一象限的柱子（如"重要价值客户"），触发下钻展开

### 2.2 展开位置

**页面内展开（In-place Drilldown）**：在柱状图下方、RFM详情表格上方，原地展开详情卡片。

```
┌───────────────────────────────────────────────────────────┐
│ [柱状图] 回购率3年对比 ← 点击此处任一柱子                   │
│  ╔═══╗  ╔═══╗                                             │
│  ║重 ║  ║重 ║  ...  ← 点击后此处的柱子高亮选中态            │
│  ║要 ║  ║要 ║                                            │
│  ║价 ║  ║保 ║                                            │
│  ╚═══╝  ╚═══╝                                             │
├───────────────────────────────────────────────────────────┤
│ ▼ [详情卡片] 重要价值客户 — 品类回购拆解         [关闭 ×]   │
│                                                           │
│  [柱状图] 各品类回购率对比                                  │
│  [表格]   品类回购明细                                      │
│  [提示]   运营洞察                                          │
├───────────────────────────────────────────────────────────┤
│ [RFM详情表格] ← 始终可见，保持上下文                        │
└───────────────────────────────────────────────────────────┘
```

### 2.3 状态管理

```typescript
// 新增响应式状态
const selectedSegment = ref<string | null>(null)  // 当前选中的象限
```

- 点击柱子 → `selectedSegment = '重要价值客户'` → 详情卡片展开，触发 API 请求
- 点击"关闭"按钮 → `selectedSegment = null` → 详情卡片收起
- 点击不同柱子 → 切换到新象限的详情
- 切换全局筛选条件（日期/渠道/对比模式）→ 如果详情卡已展开，自动刷新数据

### 2.4 柱状图选中态

选中的柱子显示高亮效果（更粗的边框 / 更饱和的颜色），未选中的柱子降低透明度。

---

## 3. 数据架构

### 3.1 新增后端 API

**端点**：`GET /api/v1/customer-health/rfm-category-drilldown`

**参数**：

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| rfm_segment | string | ✅ | RFM象限名称，如"重要价值客户" |
| start_date | string | ✅ | 分析期开始日期 |
| end_date | string | ✅ | 分析期结束日期 |
| metric_type | string | | GSV（默认）/ GMV |
| channel | string | | 渠道筛选 |
| exclude_channels | string[] | | 排除的渠道 |
| compare_start_date | string | | 对比期开始（环比/自定义时传） |
| compare_end_date | string | | 对比期结束（环比/自定义时传） |

**对比模式支持**（与现有 `_resolve_date_ranges` 完全复用）：

| 对比模式 | 前端传参 | 后端行为 |
|---------|---------|---------|
| auto_yoy（同比） | 不传 compare_* | 自动计算去年同期 + 前年同期 |
| auto_mom（环比） | 传 compare_start_date/compare_end_date | 使用自定义对比期 + 前年同期（固定） |
| custom（自定义） | 传 compare_start_date/compare_end_date | 使用自定义对比期 + 前年同期（固定） |

**返回结构**：

```jsonc
{
  "rfm_segment": "重要价值客户",
  "year_label": "2026",
  "comp_year_label": "2025",
  "prev2_year_label": "2024",
  "metric_type": "GSV",
  "categories": [
    {
      "category_name": "B5面膜",
      // 当前期
      "hist_users_current": 12000,
      "repurchase_users_current": 3600,
      "repurchase_rate_current": 0.30,
      "repurchase_gsv_current": 540000,
      "repurchase_gsv_ratio_current": 0.25,
      // 对比期
      "hist_users_comp": 11000,
      "repurchase_users_comp": 3872,
      "repurchase_rate_comp": 0.352,
      "repurchase_gsv_comp": 520000,
      "repurchase_gsv_ratio_comp": 0.28,
      // 前年期
      "hist_users_prev2": 10000,
      "repurchase_users_prev2": 3200,
      "repurchase_rate_prev2": 0.32,
      "repurchase_gsv_prev2": 480000,
      "repurchase_gsv_ratio_prev2": 0.26,
      // YOY（当前 vs 对比）
      "yoy_hist_users": 0.0909,
      "yoy_repurchase_users": -0.0703,
      "yoy_repurchase_rate": -0.052,
      "yoy_repurchase_gsv": 0.0385,
      "yoy_repurchase_gsv_ratio": -0.03
    }
    // ... 其他品类
  ],
  "member_categories": [
    // 同结构，仅会员用户
  ],
  "summary": {
    "total_hist_users": 50000,
    "total_repurchase_users": 20000,
    "overall_repurchase_rate": 0.40,
    "overall_repurchase_rate_comp": 0.42,
    "overall_repurchase_rate_yoy": -0.02,
    "declining_categories": [
      { "name": "B5面膜", "yoy_repurchase_rate": -0.052 }
    ],
    "improving_categories": [
      { "name": "医用凝胶", "yoy_repurchase_rate": 0.021 }
    ]
  }
}
```

### 3.2 后端 SQL 核心逻辑

```sql
-- 伪代码（DuckDB SQL）
WITH
  -- Step 1: 复用 RFM 分群逻辑，但只计算目标象限的用户
  rfm_segmented_users AS (
    SELECT user_id
    FROM <RFM分群 CTE（与 rfm_analysis.py 相同）>
    WHERE rfm_segment = ?  -- 参数化目标象限
  ),

  -- Step 2: 这些用户在各品类的历史购买
  category_hist AS (
    SELECT
      COALESCE(o.spu_product_class, '未知') AS category,
      rsu.user_id
    FROM orders o
    INNER JOIN rfm_segmented_users rsu ON o.user_id = rsu.user_id
    WHERE o.pay_time <= cutoff  -- 历史截止
      AND o.is_goujinjin = FALSE
      AND o.order_status != '交易关闭'
      AND is_refund = FALSE       -- GSV 口径
  ),

  -- Step 3: 这些用户在分析期的各品类购买（回购）
  category_repurchase AS (
    SELECT
      COALESCE(o.spu_product_class, '未知') AS category,
      rsu.user_id,
      SUM(o.actual_amount) AS repurchase_gsv
    FROM orders o
    INNER JOIN rfm_segmented_users rsu ON o.user_id = rsu.user_id
    WHERE o.pay_time >= start_dt AND o.pay_time <= end_dt
      AND o.is_goujinjin = FALSE
      AND o.order_status != '交易关闭'
      AND is_refund = FALSE
    GROUP BY category, rsu.user_id
  ),

  -- Step 4: 按品类聚合
  category_stats AS (
    SELECT
      ch.category,
      COUNT(DISTINCT ch.user_id) AS hist_users,
      COUNT(DISTINCT cr.user_id) AS repurchase_users,
      COALESCE(SUM(cr.repurchase_gsv), 0) AS repurchase_gsv
    FROM (SELECT DISTINCT category, user_id FROM category_hist) ch
    LEFT JOIN category_repurchase cr ON ch.user_id = cr.user_id AND ch.category = cr.category
    GROUP BY ch.category
  )

  SELECT category, hist_users, repurchase_users, repurchase_gsv,
         CASE WHEN hist_users > 0 THEN repurchase_users::DOUBLE / hist_users ELSE 0 END AS repurchase_rate
  FROM category_stats
  WHERE hist_users >= 10  -- 过滤低基数品类，避免噪声
  ORDER BY repurchase_gsv DESC
```

**关键设计决策**：
- **品类维度**：使用 `spu_product_class`（产品类），如 B5面膜、医用凝胶
- **同品/跨品**：这里不区分同品/跨品，统计的是"该象限用户在各品类的回购情况"
- **低基数过滤**：`hist_users >= 10` 过滤掉极少用户的品类，避免回购率失真
- **会员拆分**：同现有模式，返回全店 + 会员两套数据

### 3.3 前端 API 层

```typescript
// api/health.ts 新增

export interface RFMCategoryDrilldownRow {
  category_name: string
  hist_users_current: number
  repurchase_users_current: number
  repurchase_rate_current: number
  repurchase_gsv_current: number
  repurchase_gsv_ratio_current: number
  hist_users_comp: number
  repurchase_rate_comp: number
  repurchase_gsv_comp: number
  repurchase_gsv_ratio_comp: number
  hist_users_prev2: number
  repurchase_rate_prev2: number
  repurchase_gsv_prev2: number
  repurchase_gsv_ratio_prev2: number
  yoy_hist_users: number | null
  yoy_repurchase_users: number | null
  yoy_repurchase_rate: number | null
  yoy_repurchase_gsv: number | null
  yoy_repurchase_gsv_ratio: number | null
}

export interface RFMCategoryDrilldownSummary {
  total_hist_users: number
  total_repurchase_users: number
  overall_repurchase_rate: number
  overall_repurchase_rate_comp: number
  overall_repurchase_rate_yoy: number
  declining_categories: { name: string; yoy_repurchase_rate: number }[]
  improving_categories: { name: string; yoy_repurchase_rate: number }[]
}

export interface RFMCategoryDrilldownResponse {
  rfm_segment: string
  year_label: string
  comp_year_label: string
  prev2_year_label: string
  metric_type: string
  categories: RFMCategoryDrilldownRow[]
  member_categories: RFMCategoryDrilldownRow[]
  summary: RFMCategoryDrilldownSummary
}

export interface RFMCategoryDrilldownParams {
  rfm_segment: string
  start_date: string
  end_date: string
  metric_type?: 'GSV' | 'GMV'
  channel?: string
  exclude_channels?: string[]
  compare_start_date?: string
  compare_end_date?: string
}

export function fetchRFMCategoryDrilldown(
  params: RFMCategoryDrilldownParams
): Promise<RFMCategoryDrilldownResponse> {
  return client.get('/v1/customer-health/rfm-category-drilldown', { params })
}
```

---

## 4. 前端组件设计

### 4.1 新增组件

**`health/RFMSegmentDrilldown.vue`**

职责：接收选中的象限名称，请求品类拆解数据并展示。

Props：
```typescript
const props = defineProps<{
  rfmSegment: string            // 选中的象限名称
  queryParams: {                // 继承父组件的全局筛选参数
    start_date: string
    end_date: string
    channel?: string
    exclude_channels?: string[]
    compare_start_date?: string
    compare_end_date?: string
  }
}>()

const emit = defineEmits<{
  close: []
}>()
```

布局：
```
┌─────────────────────────────────────────────────┐
│ 📌 {segment} — 品类回购拆解         [关闭 ×]    │
│                                                   │
│ [KPI 卡片行]                                      │
│ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐               │
│ │总回购 │ │同比  │ │下降  │ │上升  │               │
│ │率    │ │变化  │ │品类数│ │品类数│               │
│ └─────┘ └─────┘ └─────┘ └─────┘               │
│                                                   │
│ [柱状图] 各品类回购率对比（3年/2期）              │
│  X轴: 品类名称（按回购率降序）                     │
│  Y轴: 回购率                                      │
│  柱子: 当前期 vs 对比期（根据对比模式动态显示）     │
│  标记: 同比/环比 YOYBadge 标注在柱子顶部           │
│  高亮: 下滑品类标红边框，上升品类标绿边框           │
│                                                   │
│ [导出工具栏] ExportToolbar                         │
│                                                   │
│ [表格] 品类回购明细                                │
│  列: 品类 | 历史人数 | 回购人数 | 回购率 | YOY    │
│      | 回购GSV | 回购GSV占比                      │
│  排序: 默认按回购GSV降序                           │
│  表头: 根据 compareMode 动态显示年份/环比/对比     │
│                                                   │
│ [折叠面板] 会员品类明细（默认折叠）                │
│                                                   │
│ 💡 运营洞察                                       │
│  • "B5面膜"回购率同比下降 5.2pp，为主要下滑因素   │
│  • "医用凝胶"回购率同比上升 2.1pp，表现良好       │
└─────────────────────────────────────────────────┘
```

### 4.2 修改 `ValueTierTab.vue`

变更点：

1. **新增状态**：
```typescript
const selectedSegment = ref<string | null>(null)
```

2. **柱状图添加点击事件**：
```typescript
// 在 repurchaseRateChartOption 中添加
{
  // ... 现有配置
  series: [
    {
      // ... 现有配置
      cursor: 'pointer',
      emphasis: {
        itemStyle: {
          borderColor: '#2563eb',
          borderWidth: 2,
          shadowBlur: 8,
          shadowColor: 'rgba(37, 99, 235, 0.3)',
        }
      },
    }
  ]
}
```

3. **ECharts 事件绑定**：
```typescript
// 通过 EChartsWrapper 暴露的 getChartInstance() 绑定 click 事件
// 或新增 EChartsWrapper 的 onChartClick emit
const rfmChartRef = ref<InstanceType<typeof EChartsWrapper> | null>(null)

onMounted(() => {
  nextTick(() => {
    const instance = rfmChartRef.value?.getChartInstance()
    instance?.on('click', (params) => {
      if (params.componentType === 'series' && params.seriesType === 'bar') {
        selectedSegment.value = params.name  // 象限名称
      }
    })
  })
})
```

4. **模板中插入详情组件**：
```vue
<!-- 柱状图卡片之后、RFM详情表格之前 -->
<Transition name="slide-down">
  <RFMSegmentDrilldown
    v-if="selectedSegment"
    :rfm-segment="selectedSegment"
    :query-params="drilldownQueryParams"
    @close="selectedSegment = null"
  />
</Transition>
```

5. **drilldownQueryParams** 需要响应对比模式：
```typescript
const drilldownQueryParams = computed(() => ({
  start_date: filterStore.dateRange[0],
  end_date: filterStore.dateRange[1],
  channel: filterStore.channel === '全店' ? undefined : filterStore.channel,
  metric_type: 'GSV' as const,
  exclude_channels: filterStore.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined,
  ...compareQueryParams.value,  // 复用已有的对比参数逻辑
}))
```

### 4.3 EChartsWrapper 改造

需要支持 `click` 事件透传。两种方案：

**方案 A（推荐）**：`EChartsWrapper` 新增 `chartClick` emit

```typescript
// EChartsWrapper.vue
const emit = defineEmits<{
  chartClick: [params: any]
}>()

onMounted(() => {
  // ... 现有 initChart 逻辑
  chartInstance.on('click', (params) => {
    emit('chartClick', params)
  })
})
```

**方案 B**：父组件通过 `ref.getChartInstance()` 自行绑定

推荐方案 A，更符合 Vue 组件规范。

---

## 5. 对比模式适配

### 5.1 三种对比模式的表头/图表标签

| 对比模式 | 图表柱子 | 表格表头 | YOY 计算 |
|---------|---------|---------|---------|
| auto_yoy | 当前年 / 去年 / 前年 | `{yr}年` / `{yr2}年` / `{yr3}年` | 当前 vs 去年 |
| auto_mom | 当期 / 上期 / 前年同期 | `当期` / `上期` / `前年同期` | 当期 vs 上期 |
| custom | 当期 / 对比期 / 前年同期 | `当期` / `对比期` / `前年同期` | 当期 vs 对比期 |

**注意**：无论哪种对比模式，柱状图始终显示3组柱子（当前 + 对比 + 前年），但年份标签会变化。
在环比/自定义模式下，第2组柱子的 label 改为"上期"/"对比期"而非年份。

### 5.2 后端 `_resolve_date_ranges` 复用

新的 drilldown API 内部直接调用 `_resolve_date_ranges(period, start_date, end_date, compare_start_date, compare_end_date)`，与现有 RFM 分析完全一致，无需额外逻辑。

### 5.3 前端 `compareQueryParams` 复用

`ValueTierTab.vue` 已有 `compareQueryParams` computed（第39-44行），drilldown 参数直接展开：

```typescript
const drilldownQueryParams = computed(() => ({
  start_date: filterStore.dateRange[0],
  end_date: filterStore.dateRange[1],
  channel: filterStore.channel === '全店' ? undefined : filterStore.channel,
  metric_type: 'GSV' as const,
  exclude_channels: filterStore.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined,
  ...compareQueryParams.value,
}))
```

---

## 6. 后端实现要点

### 6.1 服务函数

新增 `backend/services/health/rfm_category_drilldown.py`：

```python
def get_rfm_category_drilldown(
    rfm_segment: str,
    period: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    metric_type: str = "GSV",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
    compare_start_date: Optional[str] = None,
    compare_end_date: Optional[str] = None,
) -> Dict[str, Any]:
```

### 6.2 复用策略

| 复用项 | 来源 | 说明 |
|-------|------|------|
| 日期范围解析 | `rfm_service._resolve_date_ranges()` | 当前期/对比期/前年期 |
| RFM 分群逻辑 | `rfm_analysis._run_rfm_period()` 中的 RFM SQL CTE | 8象限分群规则 |
| YoY 计算 | `semantic.calculations.yoy_absolute/yoy_repurchase_rate` | 统一 YoY 口径 |
| 缓存策略 | 参照 `rfm_analysis` 的 Plan C 文件缓存 | 历史周期缓存 |

### 6.3 RFM CTE 提取

`rfm_analysis.py` 中 `_run_rfm_period()` 的 RFM 分群 CTE 已经很大（~250行 SQL）。为避免代码重复，将 RFM 分群 CTE 提取为共享函数：

```python
# backend/services/health/rfm_crosstab.py（新增）

def build_rfm_ctes(
    cutoff_dt: str,
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> tuple[str, list]:
    """
    返回 RFM 分群 CTE SQL 片段 + 参数列表。
    生成的 CTE 名称为:
      user_stats → rfm_scored → segmented
    调用方可直接在 WITH 子句中拼接这些 CTE。
    """
```

`rfm_analysis._run_rfm_period()` 和 `rfm_category_drilldown.get_rfm_category_drilldown()` 都调用这个共享函数。

### 6.4 路由注册

在 `backend/routers/health.py` 新增端点：

```python
@router.get("/rfm-category-drilldown", response_model=RFMCategoryDrilldownResponse)
def rfm_category_drilldown(
    rfm_segment: str,
    start_date: str,
    end_date: str,
    metric_type: str = "GSV",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
    compare_start_date: Optional[str] = None,
    compare_end_date: Optional[str] = None,
):
```

### 6.5 Schema 定义

在 `backend/contracts/schemas.py` 新增 Pydantic 模型：

```python
class RFMCategoryDrilldownRow(BaseModel):
    category_name: str
    hist_users_current: int
    repurchase_users_current: int
    repurchase_rate_current: float
    repurchase_gsv_current: float
    repurchase_gsv_ratio_current: float
    # ... 对比期、前年期、YoY 字段

class RFMCategoryDrilldownSummary(BaseModel):
    total_hist_users: int
    total_repurchase_users: int
    overall_repurchase_rate: float
    overall_repurchase_rate_comp: float
    overall_repurchase_rate_yoy: float
    declining_categories: List[DecliningCategoryItem]
    improving_categories: List[ImprovingCategoryItem]

class RFMCategoryDrilldownResponse(BaseModel):
    rfm_segment: str
    year_label: str
    comp_year_label: str
    prev2_year_label: str
    metric_type: str
    categories: List[RFMCategoryDrilldownRow]
    member_categories: List[RFMCategoryDrilldownRow]
    summary: RFMCategoryDrilldownSummary
```

---

## 7. 缓存策略

| 场景 | 策略 | 说明 |
|------|------|------|
| 历史周期 + auto_yoy | Plan P1 DuckDB 预计算 | ETL 阶段预热 |
| 历史周期 + auto_mom/custom | Plan C 文件缓存 | 首次请求后缓存 |
| 当前周期（实时） | 不缓存 | 数据随时变化 |

缓存键格式：`{data_version}_{start}_{end}_{channel}_{metric}_{rfm_segment}_{compare_dates}.json`

---

## 8. 文件变更清单

### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/services/health/rfm_category_drilldown.py` | 品类下钻服务 |
| `backend/services/health/rfm_crosstab.py` | RFM 分群 CTE 共享模块 |
| `frontend-vue3/src/views/health/RFMSegmentDrilldown.vue` | 品类下钻详情组件 |
| `docs/features/rfm-segment-drilldown.md` | 本文档 |

### 修改文件

| 文件 | 变更内容 |
|------|---------|
| `frontend-vue3/src/views/health/ValueTierTab.vue` | 添加柱状图点击事件 + 下钻组件挂载 |
| `frontend-vue3/src/components/EChartsWrapper.vue` | 新增 `chartClick` emit |
| `frontend-vue3/src/api/health.ts` | 新增 drilldown API 函数和类型 |
| `frontend-vue3/src/api/types.ts` | 新增 OpenAPI schema 类型 |
| `backend/routers/health.py` | 新增路由端点 |
| `backend/contracts/schemas.py` | 新增 Pydantic 响应模型 |
| `backend/services/health/rfm_analysis.py` | 重构 RFM CTE 为共享模块调用 |

---

## 9. 开发分支与 Git 流程

```
main
 └── feature/rfm-category-drilldown
      ├── commit 1: docs: RFM品类下钻特性设计文档
      ├── commit 2: feat(backend): RFM CTE 提取 + 品类下钻 API
      ├── commit 3: feat(frontend): 柱状图点击 + 品类下钻组件
      ├── commit 4: feat(frontend): 对比模式适配 + 表头动态
      ├── commit 5: fix: QA 修复
      └── merge → main
```

---

## 10. 待确认事项

1. ~~品类层级~~ → 已确认：`spu_product_class`（产品类）
2. ~~交互方式~~ → 已确认：页面内展开
3. ~~对比模式~~ → 已确认：2年对比 + 环比 + 自定义
4. **会员拆分**：详情中是否需要显示会员品类明细？（默认建议：折叠面板，不默认展开）
5. **低基数品类**：`hist_users < 10` 的品类是否过滤？还是标记"样本不足"？
6. **品类排序**：按回购率降序 or 按回购GSV降序 or 按YoY变化幅度降序？
