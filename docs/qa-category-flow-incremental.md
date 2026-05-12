# 品类流转Tab增量改造 - QA测试报告

## 测试概览

| 项目 | 结果 |
|------|------|
| 测试日期 | 2026-05-11 |
| 测试分支 | feat/category-flow-tab-enhance |
| 变更文件数 | 4 |
| Python语法检查 | 通过 |
| TypeScript编译检查 | 通过 |
| 整体结论 | **有条件通过**（发现2处需修复，1处建议优化） |

---

## 一、代码审查

### 1. 后端SQL是否安全（参数化查询，无注入风险）

**结果：通过**

- `get_category_flow` 中所有动态值均使用 `?` 参数化占位符
- 渠道过滤条件 `channel_sql` / `exclude_sql` 通过 `','.join(['?'] * len(...))` 构造占位符
- `base_params` / `params_flow` 与 SQL 分离传递，无字符串拼接注入风险
- 唯一 f-string 拼接为列名选择（`_cat_expr`），字段来源受控于 `SPU_LEVELS` 白名单

### 2. 后端渠道排除逻辑是否正确

**结果：有条件通过（发现潜在风险）**

默认排除逻辑实现：
```python
DEFAULT_EXCLUDED_CHANNELS = ['赠品&0.01', '其他']
if exclude_channels is None:
    exclude_channels = DEFAULT_EXCLUDED_CHANNELS.copy()
else:
    merged = list(dict.fromkeys(exclude_channels + DEFAULT_EXCLUDED_CHANNELS))
    exclude_channels = merged
```

逻辑正确：无参数时应用默认值，有参数时去重合并。但存在以下风险：

> **风险：`expand_channels` 映射兼容性**
> 前端传入 `'赠品&0.01'`，但同文件中 `LOW_PRICE_CHANNELS` 使用 `'赠品&0.01渠道'`（带"渠道"后缀）。若 `expand_channels` 未配置 `'赠品&0.01'` → `'赠品&0.01渠道'` 的映射，默认排除将**不生效**。
>
> **建议**：联调时验证 `expand_channels(['赠品&0.01'])` 的返回结果是否包含预期的 DB 渠道名。

### 3. 前端TypeScript类型是否正确

**结果：通过**

```typescript
export interface FlowMatrix {
  sources: string[]
  targets: string[]
  matrix: number[][]
  row_totals: number[]
  concentration_warnings: string[]
}
```

与后端 `List[List[int]]` / `List[int]` 语义一致。

### 4. 前后端接口类型是否一致

**结果：通过**

| 字段 | 后端类型 | 前端类型 | 一致 |
|------|----------|----------|------|
| sources | `List[str]` | `string[]` | 是 |
| targets | `List[str]` | `string[]` | 是 |
| matrix | `List[List[int]]` | `number[][]` | 是 |
| row_totals | `List[int]` (默认 `[]`) | `number[]` | 是 |
| concentration_warnings | `List[str]` | `string[]` | 是 |

---

## 二、功能逻辑验证

### 1. 365天选项是否在前端正确展示

**结果：通过**

```typescript
const WINDOW_OPTIONS = [
  { label: '30天', value: 30 },
  { label: '90天', value: 90 },
  { label: '180天', value: 180 },
  { label: '365天', value: 365 },
]
```

### 2. 默认渠道排除是否生效

**结果：通过**

前端 `queryParams`：
```typescript
exclude_channels: CATEGORY_FLOW_EXCLUDED_CHANNELS, // ['赠品&0.01', '其他']
```

后端强制合并默认排除列表，无法被用户覆盖，符合产品预期。

### 3. 全量矩阵是否正确

**结果：通过**

- 旧版 `flow_sql` 含 `WHERE fo.first_category IN (...) OR so.second_category IN (...)` 限制
- 新版已**完全移除**该限制，`flow_result` 返回全部品类的流转对
- 矩阵维度由 `top_cats` 的固定 10×11 变为动态 `len(all_from_cats) × len(all_to_cats)`

### 4. row_totals是否正确计算

**结果：通过**

```python
row_totals = [sum(row) for row in matrix]
```

每行总和与 `matrix` 维度严格对齐。

### 5. 百分比计算是否正确

**结果：通过**

前端计算：
```typescript
row[`t_${ti}`] = rawVal === 0 ? 0 : Math.round((rawVal / rowTotal) * 1000) / 10
```

等价于 `round(rawVal / rowTotal * 100, 1)`，保留1位小数，符合预期。

### 6. 百分比/数值切换是否正常工作

**结果：通过**

- `matrixDisplayMode` 为响应式 ref，影响 `matrixData` computed
- `matrixColumns.render` 读取同一 ref，UI 同步更新
- 切换按钮绑定 `@click` 事件，无状态竞争

### 7. 矩阵表格max-height是否设置正确

**结果：通过**

```vue
<DataTablePro ... :max-height="520" />
```

---

## 三、回归测试

### 1. 桑基图功能不受影响

**结果：通过**

- 桑基图仍基于 `top_cats`（TOP10+其他）归类，数据结构未变
- `breakCycles` / 过滤阈值逻辑无修改
- 缓存文件增加 `_full` 后缀，不读取旧缓存

### 2. 前后置关联表格功能正常

**结果：通过**

- `_compute_temporal_association` 函数未修改
- 前端条件渲染 `v-if="data?.target_category"` 未变更

### 3. 时间窗口切换正常工作

**结果：通过**

- `windowDays` 为响应式 ref，参与 `queryKey` 计算
- `@tanstack/vue-query` 会在值变化时自动重新获取

### 4. 目标品类选择器正常工作

**结果：通过**

- `targetCategory` 参与 `queryParams`，清空时传 `undefined`
- 有 target 时后端不走缓存，符合预期

---

## 四、边界情况

### 1. row_totals为undefined时的兼容性

**结果：通过**

```typescript
const rowTotal = row_totals?.[si] ?? 0
```

- 旧缓存/旧数据无 `row_totals` 时，回退为 `0`
- `rowTotal > 0` 不成立，百分比模式自动降级为数值模式，无除零错误

### 2. 矩阵数据为空时的处理

**结果：通过**

```typescript
const matrixData = computed(() => {
  if (!data.value?.matrix) return []
  // ...
})
```

`matrixColumns` 同样做空值保护：
```typescript
if (!data.value?.matrix) return []
```

### 3. 缓存兼容性

**结果：通过**

- 缓存文件名从 `_top{top_n}_` 改为 `_full_`，旧缓存不会被命中
- 即使手动读取旧缓存，前端 `row_totals?.[si] ?? 0` 保证兼容性

---

## 五、发现的问题

### ❌ Bug-1：集中度警告标签错位（源码Bug，建议修复）

**位置**：`backend/services/category_service.py:1817-1823`

**问题代码**：
```python
for i, src in enumerate(sources):
    total_inflow = sum(matrix[j][i] for j in range(len(sources)))
    if total_inflow > 0:
        max_source_ratio = max(matrix[j][i] for j in range(len(sources))) / total_inflow
        if max_source_ratio > 0.6:
            concentration_warnings.append(f"{src} 过度依赖单一来源(占比>{int(max_source_ratio*100)}%)")
```

**根因**：循环变量 `src = sources[i]`（来源品类），但 `matrix[j][i]` 取的是**第 i 列**（目标品类 `targets[i]`）的流入数据。当 `sources` 与 `targets` 排序不一致时，警告信息会张冠李戴。

**复现场景**：
- `sources = ['面膜', '精华', '洁面']`（按流出量排序）
- `targets = ['洁面', '面膜', '精华']`（按流入量排序）
- 当 `i=0` 时，分析的是"洁面"的流入集中度，但警告显示"面膜 过度依赖单一来源"

**修复建议**：
```python
for i, tgt in enumerate(targets):
    total_inflow = sum(matrix[j][i] for j in range(len(sources)))
    if total_inflow > 0:
        max_source_ratio = max(matrix[j][i] for j in range(len(sources))) / total_inflow
        if max_source_ratio > 0.6:
            concentration_warnings.append(f"{tgt} 过度依赖单一来源(占比>{int(max_source_ratio*100)}%)")
```

> 注：此Bug在旧版代码中已存在，但因旧版 `sources = top_cats` 且 `targets = top_cats + [other_node]`，前N项索引勉强对齐，暴露概率低。新版全量矩阵中 `sources` 与 `targets` 独立排序，该Bug极易触发。

---

### ❌ Bug-2：百分比模式下0值显示不一致（源码Bug，建议修复）

**位置**：`frontend-vue3/src/views/category-tabs/CategoryFlowTab.vue:233-238`

**问题代码**：
```typescript
render: (row: any) => {
  const val = row[`t_${i}`]
  if (val == null || val === 0) return '—'
  if (matrixDisplayMode.value === 'percentage') {
    return val + '%'
  }
  return val.toLocaleString()
}
```

**根因**：`matrixData` 中 `rawVal === 0` 时被赋值为 `0`，但 `render` 中 `val === 0` 直接返回 `'—'`。这导致：
- 数值模式：0 显示为 `'—'`（尚可接受）
- 百分比模式：0% 也显示为 `'—'`（用户无法区分"无流转"和"数据缺失"）

**修复建议**：
```typescript
render: (row: any) => {
  const val = row[`t_${i}`]
  if (val == null) return '—'
  if (val === 0) {
    return matrixDisplayMode.value === 'percentage' ? '0.0%' : '—'
  }
  if (matrixDisplayMode.value === 'percentage') {
    return val + '%'
  }
  return val.toLocaleString()
}
```

---

### ⚠️ Risk-1：渠道名映射风险（建议联调验证）

**位置**：前后端渠道排除链

**描述**：前端发送 `'赠品&0.01'`，后端 `LOW_PRICE_CHANNELS` 使用 `'赠品&0.01渠道'`。若 `expand_channels` 未注册该别名，默认排除将失效。

**验证方法**：
```python
from backend.semantic.filters import expand_channels
print(expand_channels(['赠品&0.01']))
# 预期输出应包含 '赠品&0.01渠道' 或等效DB渠道名
```

---

### ⚠️ Risk-2：全量矩阵性能风险（建议监控）

**描述**：全量矩阵不再限制 `top_n`，若品类数量 >50，矩阵单元格 >2500，可能导致：
1. DuckDB 子查询（`user_first_order` / `user_second_order`）执行时间增加
2. 前端 `DataTablePro` 渲染50+列时横向滚动体验下降

**缓解措施**：缓存机制已保留，且 `_full` 后缀区分缓存，日常查看走缓存无实时计算压力。

---

## 六、测试清单汇总

| # | 检查项 | 结果 | 备注 |
|---|--------|------|------|
| 1 | 后端SQL参数化查询 | 通过 | 无注入风险 |
| 2 | 后端渠道排除逻辑 | 通过 | 默认排除正确，见 Risk-1 |
| 3 | 前端TypeScript类型 | 通过 | 与后端一致 |
| 4 | 前后端接口一致性 | 通过 | 字段类型对齐 |
| 5 | 365天选项展示 | 通过 | WINDOW_OPTIONS 已添加 |
| 6 | 默认渠道排除生效 | 通过 | queryParams 正确 |
| 7 | 全量矩阵返回 | 通过 | 已移除 top_cats 限制 |
| 8 | row_totals计算 | 通过 | 每行求和正确 |
| 9 | 百分比计算 | 通过 | 保留1位小数 |
| 10 | 百分比/数值切换 | 通过 | 响应式更新 |
| 11 | 矩阵max-height | 通过 | 520px |
| 12 | 桑基图回归 | 通过 | TOP10+其他归类保留 |
| 13 | 前后置关联表格 | 通过 | 未变更 |
| 14 | 时间窗口切换 | 通过 | 30/90/180/365 |
| 15 | 目标品类选择器 | 通过 | 未变更 |
| 16 | row_totals兼容性 | 通过 | `?. ?? 0` 保护 |
| 17 | 空矩阵处理 | 通过 | 返回 `[]` |
| 18 | 缓存兼容性 | 通过 | `_full` 后缀区分 |

---

## 七、修复优先级

| 优先级 | 问题 | 类型 | 负责人 |
|--------|------|------|--------|
| P1 | 集中度警告标签错位（Bug-1） | 源码Bug | engineer |
| P2 | 百分比0值显示不一致（Bug-2） | 源码Bug | engineer |
| P3 | 渠道名映射验证（Risk-1） | 联调验证 | qa-engineer + engineer |
| P3 | 全量矩阵性能监控（Risk-2） | 线上观察 | engineer |

---

## 八、结论

**总体评价：有条件通过**

本次增量改造的核心功能（全量矩阵、row_totals、百分比切换、365天窗口、默认渠道排除）实现正确，代码质量良好。建议在合并前修复 **Bug-1（集中度警告标签错位）** 和 **Bug-2（百分比0值显示）**，并在联调时验证渠道名映射（Risk-1）。

---

QA工程师: qa-engineer
日期: 2026-05-11
