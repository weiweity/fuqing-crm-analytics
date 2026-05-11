# 品类流转Tab增量改造 — 系统架构设计

> 版本: v1.0
> 日期: 2026-05-11
> 负责人: architect
> 关联PRD: PRD-category-flow-incremental.md

---

## 1. 实现方案概述

### 1.1 前端改造要点

| 改造项 | 说明 |
|--------|------|
| 365天窗口 | `WINDOW_OPTIONS` 追加 `{ label: '365天', value: 365 }` |
| 默认渠道排除 | `queryParams.exclude_channels` 硬编码默认 `['赠品&0.01', '其他']`，不依赖 `filterStore.excludeLowPrice` |
| 流转矩阵全量展示 | 后端返回全部品类矩阵后，前端使用 `DataTablePro` 的 `maxHeight` + `scrollX` 实现固定高度内部滚动；首列 `fixed: 'left'` 冻结 |
| 百分比/数值切换 | 前端本地计算行百分比（cell / rowTotal），不重新请求API；增加 `NSwitch` 切换控件 |
| 前后置关联优化 | 保持现有 `_compute_temporal_association` 逻辑，仅优化展示布局 |

### 1.2 后端改造要点

| 改造项 | 说明 |
|--------|------|
| 矩阵全量返回 | `get_category_flow` 中，桑基图仍按 `top_n=10` + "其他" 归类；流转矩阵改为返回**全部品类**的完整矩阵 |
| SQL拆分 | 原 `flow_sql` 限制 `first_category IN top_cats OR second_category IN top_cats`，需拆分：先查全部flow_pairs用于矩阵，再查top_n相关用于桑基图；或一次查全量，分别构建 |
| 矩阵排序 | 全量矩阵按品类总流量（流出+流入）降序排列行列，保证高流量品类在前 |
| 缓存策略 | 全量矩阵数据量较大，缓存key去掉 `top{top_n}` 后缀（矩阵不再受top_n影响），保留 `level`、`window_days`、`channel`、`exclude_channels` |
| `top_n`参数语义 | `top_n` 仅控制桑基图TOP品类数，矩阵始终返回全量；API参数保留不变，向后兼容 |

### 1.3 API变更说明

- **接口地址**: `GET /api/v1/category/flow`（不变）
- **请求参数**: 不变，仍支持 `top_n`（仅影响桑基图）
- **响应结构**: `CategoryFlowResponse` 不变，但 `matrix.matrix` 维度从 `(top_n) × (top_n+1)` 扩展为 `(N) × (N)`，其中 N 为全部有效品类数
- **兼容性**: 前端 `FlowMatrix` TypeScript 接口无需字段变更，仅数据维度扩展

---

## 2. 文件列表及变更说明

| 序号 | 文件路径 | 变更类型 | 变更说明 |
|------|----------|----------|----------|
| 1 | `frontend-vue3/src/views/category-tabs/CategoryFlowTab.vue` | **修改** | 365天窗口、默认渠道排除、百分比切换、矩阵全量展示适配 |
| 2 | `frontend-vue3/src/api/category.ts` | **修改** | `FlowMatrix` 接口增加 JSDoc 注释说明全量矩阵；如需要可增加 `row_totals` 字段（见第3节） |
| 3 | `frontend-vue3/src/constants/channels.ts` | **修改** | 新增 `CATEGORY_FLOW_DEFAULT_EXCLUDE_CHANNELS` 常量 |
| 4 | `frontend-vue3/src/components/DataTablePro.vue` | **修改** | 确认已透传 `maxHeight`、`scrollX`；如未透传 `sticky` 相关需补充（评估见第8节） |
| 5 | `backend/services/category_service.py` | **修改** | `get_category_flow` 拆分为全量矩阵 + TOP桑基图；调整缓存key；`_compute_temporal_association` 无变更 |
| 6 | `backend/main.py` | **不变** | `/api/v1/category/flow` 路由无需修改，参数和响应模型不变 |
| 7 | `backend/contracts/schemas.py` | **可选修改** | `FlowMatrix` 可增加 `row_totals: List[int]` 辅助前端百分比计算（不增加也可前端自行汇总） |

---

## 3. 数据结构变更

### 3.1 后端 Pydantic 模型（schemas.py）

**`FlowMatrix` 模型（建议增强，向后兼容）:**

```python
class FlowMatrix(BaseModel):
    sources: List[str]          # 全部品类，按总流量降序
    targets: List[str]          # 与 sources 同序（矩阵行列一致）
    matrix: List[List[int]]     # N×N 整数矩阵，值为流转用户数
    concentration_warnings: List[str]
    # --- 新增可选字段 ---
    row_totals: Optional[List[int]] = None  # 每行流出总和，辅助前端百分比计算
```

> **决策**: `row_totals` 为可选增强。若后端不增加，前端通过 `matrix[si].reduce((a,b)=>a+b, 0)` 自行计算。

### 3.2 前端 TypeScript 接口（category.ts）

```typescript
export interface FlowMatrix {
  sources: string[]
  targets: string[]
  matrix: number[][]
  concentration_warnings: string[]
  row_totals?: number[]   // 新增可选，后端返回则直接用
}
```

### 3.3 新增/修改字段说明

| 字段 | 位置 | 类型 | 说明 |
|------|------|------|------|
| `row_totals` | `FlowMatrix` | `number[]` | 每行流出总和，减少前端重复计算 |
| `CATEGORY_FLOW_DEFAULT_EXCLUDE_CHANNELS` | `channels.ts` | `string[]` | 品类流转tab默认排除渠道 |

---

## 4. 程序调用流程

```
用户进入品类流转Tab
    │
    ▼
CategoryFlowTab.vue mounted
    │
    ├── 构建 queryParams（默认 exclude_channels = ['赠品&0.01', '其他']）
    │   level='class', top_n=10, window_days=90（或用户选择365）
    │
    ▼
useQuery 触发 fetchCategoryFlow(queryParams)
    │
    ▼
GET /api/v1/category/flow?...&exclude_channels=赠品&0.01&exclude_channels=其他
    │
    ▼
backend/main.py → get_category_flow_api()
    │
    ▼
category_service.get_category_flow()
    │
    ├── 1. 检查缓存（无target_category时）
    │   缓存key: flow_{start}_{end}_w{window_days}_{level}_{channel_hash}.json
    │   （注意：不再包含 top{top_n}）
    │
    ├── 2. SQL查询全部有效品类列表（按首购用户数降序）
    │
    ├── 3. SQL查询全部 flow_pairs（不限top_n）
    │   用于：构建完整流转矩阵
    │
    ├── 4. 按 top_n 归类非TOP为"其他"，构建桑基图数据
    │
    ├── 5. 按总流量排序全部品类，构建 N×N 流转矩阵
    │   计算 row_totals（每行流出总和）
    │
    ├── 6. 写入缓存（无target_category时）
    │
    └── 7. 若传了 target_category，调用 _compute_temporal_association()
            返回 post_purchase + pre_purchase
    │
    ▼
返回 CategoryFlowResponse
    │
    ▼
前端接收数据
    │
    ├── sankeyOption computed → EChartsWrapper 渲染桑基图
    │
    ├── matrixColumns + matrixData computed
    │   默认 showPercentage=true，render时计算 cell/rowTotal 百分比
    │   点击切换 → showPercentage=false，显示原始数值
    │   DataTablePro 渲染（max-height=600 + scroll-x + 首列fixed）
    │
    └── target_category 选择后 → refetch 并渲染前后置关联表格
```

---

## 5. 任务分解列表（按实现顺序）

```
Task A: 后端 — 改造 get_category_flow 全量矩阵逻辑
├── 文件: backend/services/category_service.py
├── 依赖: 无
├── 要点:
│   1. 保留 top_cat_sql 用于桑基图TOP N确定
│   2. 新增 all_flow_sql（去掉 IN top_cats 限制）查询全部 flow_pairs
│   3. 矩阵构建逻辑改为：收集全部品类 → 按总流量排序 → 构建 N×N 矩阵
│   4. 缓存key去掉 top_n 后缀
│   5. 可选：增加 row_totals 计算
└── 验收: 接口返回矩阵维度 > 10×10，且包含全部品类

Task B: 后端 — 更新 Pydantic 模型（可选）
├── 文件: backend/contracts/schemas.py
├── 依赖: Task A（可选同步进行）
├── 要点: FlowMatrix 增加 row_totals?: List[int]
└── 验收: 模型校验通过

Task C: 前端 — 更新常量与API类型
├── 文件: frontend-vue3/src/constants/channels.ts, src/api/category.ts
├── 依赖: Task B（如执行）
├── 要点:
│   1. channels.ts 增加 CATEGORY_FLOW_DEFAULT_EXCLUDE_CHANNELS
│   2. category.ts FlowMatrix 增加 row_totals?
└── 验收: TypeScript编译无错误

Task D: 前端 — 改造 CategoryFlowTab.vue 核心交互
├── 文件: frontend-vue3/src/views/category-tabs/CategoryFlowTab.vue
├── 依赖: Task A, Task C
├── 要点:
│   1. WINDOW_OPTIONS 追加 365天
│   2. queryParams.exclude_channels 硬编码默认排除常量
│   3. 增加 showPercentage ref + NSwitch 切换UI
│   4. matrixColumns render 逻辑：showPercentage ? 百分比 : 数值
│   5. 前端本地计算 rowTotal（或使用后端返回的 row_totals）
│   6. DataTablePro 增加 max-height 和首列 fixed
│   7. 百分比计算规则：cell / rowTotal * 100，保留1位小数；rowTotal=0 时显示 "—"
└── 验收: UI切换正常，百分比加总≈100%，表格可滚动

Task E: 集成测试与缓存验证
├── 文件: 涉及全部修改文件
├── 依赖: Task A ~ D 全部完成
├── 要点:
│   1. 验证365天窗口数据正常返回
│   2. 验证默认渠道排除生效（赠品&0.01、其他不在结果中）
│   3. 验证矩阵全量返回（维度 > 10）
│   4. 验证缓存命中/失效逻辑正确（切换window_days、日期范围时重新计算）
│   5. 验证百分比/数值切换无额外API请求
└── 验收: QA通过
```

---

## 6. 共享知识（跨文件约定）

### 6.1 渠道排除常量

```typescript
// frontend-vue3/src/constants/channels.ts
export const LOW_PRICE_CHANNELS = ['U先派样', '百补派样', '赠品&0.01', '其他']

// 新增：品类流转Tab默认排除（不依赖UI开关）
export const CATEGORY_FLOW_DEFAULT_EXCLUDE_CHANNELS = ['赠品&0.01', '其他']
```

> **约定**: 品类流转tab的 `queryParams.exclude_channels` 始终包含 `CATEGORY_FLOW_DEFAULT_EXCLUDE_CHANNELS`，与 `filterStore.excludeLowPrice` 无关。当用户开启"剔除低价"时，额外排除 `LOW_PRICE_CHANNELS` 中剩余项（U先派样、百补派样）。

### 6.2 百分比计算规则

- **定义**: 行百分比 = 该单元格流转人数 / 该行来源品类的流出总人数
- **公式**: `pct = (matrix[si][ti] / rowTotal) * 100`
- **精度**: 保留1位小数（如 `12.3%`）
- **边界**: `rowTotal === 0` 时显示 `"—"`；`cell === 0` 时显示 `"—"`
- **位置**: 前端本地计算，不请求API

### 6.3 矩阵排序规则

- **行排序**: 按来源品类总流量（流出总和 + 流入总和）降序
- **列排序**: 与行排序一致（行列品类顺序相同），保持矩阵对称性
- **后端实现**: `get_category_flow` 中构建矩阵时，先计算每个品类的 `total_flow = outflow + inflow`，再按此降序排列 `sources` 和 `targets`
- **桑基图排序**: 桑基图节点仍按原逻辑（按首购用户数 TOP N），与矩阵排序独立

---

## 7. 依赖包列表

| 包名 | 当前状态 | 是否需要 | 说明 |
|------|----------|----------|------|
| `naive-ui` | 已安装 | 否 | NDataTable 已支持 `max-height`、`scroll-x`、`fixed` |
| `vue` / `pinia` / `vue-query` | 已安装 | 否 | 无新增依赖 |
| `echarts` | 已安装 | 否 | 桑基图无变更 |

**结论**: 无新增 npm/pip 依赖。

---

## 8. 待明确事项

| 编号 | 问题 | 建议方案 | 决策人 |
|------|------|----------|--------|
| Q1 | `DataTablePro` 是否已完整透传 `max-height` 和 `fixed` 所需属性？ | 当前 `DataTablePro` 已透传 `maxHeight`、`scrollX`。NDataTable 的列 `fixed` 通过 `columns` 配置传入，不依赖组件封装。**评估结论：无需修改 DataTablePro，直接在 CategoryFlowTab 的 columns 配置中添加 `fixed: 'left'` 即可。** | architect（已确认） |
| Q2 | 后端是否增加 `row_totals` 字段？ | **建议增加**：减少前端重复计算，避免大矩阵每行reduce的性能开销。字段为 Optional，不影响现有缓存文件（旧缓存无此字段，前端降级为自行计算）。 | product-manager + team-lead |
| Q3 | 全量矩阵数据量过大时的性能边界？ | 当前 DuckDB 本地执行，N（品类数）一般在 20~50 之间，矩阵大小 20×20~50×50，JSON 约 10~50KB，无性能风险。若未来 N > 100 需考虑分页或懒加载。 | team-lead |
| Q4 | 缓存key去掉 `top_n` 后，旧缓存文件如何处理？ | 旧缓存文件自然过期（文件名含 `top{top_n}`，新请求不匹配），无需清理逻辑。 | architect（已确认） |
| Q5 | 百分比切换时，行百分比 vs 全局百分比？ | PRD明确要求**行百分比**（A→B / A流出总和）。若后续需要全局百分比（A→B / 全量流转总和），需新增切换选项。 | product-manager |
| Q6 | 365天窗口下，SQL的 `window_start` 会大幅提前，是否影响性能？ | `window_start = start_date - window_days`。365天窗口意味着查询跨度约为 `dateRange + 365` 天。若 dateRange 本身为90天，则总跨度约455天。DuckDB 本地文件性能应可承受，但建议上线后监控首屏加载时间。 | team-lead |

---

## 附录：关键代码片段参考

### A. 后端矩阵全量构建逻辑（伪代码）

```python
# 1. 查全量 flow_pairs（不限 top_n）
all_flow_result = conn.execute(all_flow_sql, params).fetchall()

# 2. 收集全部品类并计算总流量
flow_stats = {}  # category -> {outflow, inflow}
for row in all_flow_result:
    from_cat, to_cat, users = row[0], row[1], int(row[2] or 0)
    if from_cat not in flow_stats: flow_stats[from_cat] = {"out": 0, "in": 0}
    if to_cat not in flow_stats: flow_stats[to_cat] = {"out": 0, "in": 0}
    flow_stats[from_cat]["out"] += users
    flow_stats[to_cat]["in"] += users

# 3. 按总流量降序排序
sorted_cats = sorted(
    flow_stats.keys(),
    key=lambda c: flow_stats[c]["out"] + flow_stats[c]["in"],
    reverse=True
)

# 4. 构建 N×N 矩阵
N = len(sorted_cats)
matrix = [[0] * N for _ in range(N)]
for row in all_flow_result:
    from_cat, to_cat, users = row[0], row[1], int(row[2] or 0)
    si = sorted_cats.index(from_cat)
    ti = sorted_cats.index(to_cat)
    matrix[si][ti] = users

row_totals = [sum(matrix[si]) for si in range(N)]
```

### B. 前端百分比渲染逻辑（伪代码）

```typescript
const showPercentage = ref(true)

// 使用后端返回的 row_totals，或自行计算
const rowTotals = computed(() => {
  if (data.value?.matrix?.row_totals) return data.value.matrix.row_totals
  return data.value?.matrix?.matrix.map(row => row.reduce((a, b) => a + b, 0)) ?? []
})

const matrixColumns = computed(() => {
  // ... 首列固定
  targets.forEach((t, i) => {
    cols.push({
      title: t,
      key: `t_${i}`,
      align: 'right',
      render: (row: any, rowIndex: number) => {
        const val = row[`t_${i}`]
        if (!val) return '—'
        if (showPercentage.value) {
          const total = rowTotals.value[rowIndex]
          if (!total) return '—'
          return ((val / total) * 100).toFixed(1) + '%'
        }
        return val.toLocaleString()
      }
    })
  })
})
```
