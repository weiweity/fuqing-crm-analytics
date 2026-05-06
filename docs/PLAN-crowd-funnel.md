# 人群漏斗 (Crowd Funnel) — 设计计划

## 1. 需求摘要

在市场对焦板块新增第 4 个 Tab「人群漏斗」，展示 DMP 人群在选定时间段内的流转情况。

**数据源**: `/Users/hutou/Desktop/work plat/DMP_test_package/core/data.csv`  
**设计参照**: 全店资产（StoreAssetsTab）— 上方图表 + 下方表格  
**核心运算**: 用户选择「开始日期」和「结束日期」，各指标值 = 结束日数值 − 开始日数值

---

## 2. 数据结构分析

### 2.1 CSV 格式
```
date, crowd, initial, zhuanfaxian, zhuanzhongcao, zhuanhudong, zhuanxingdong, zhuanshougou, zhuanfugou, zhuanzhiai
```

| 列名 | 含义 |
|------|------|
| `date` | 日期 `YYYY/M/D` |
| `crowd` | 人群层级：`faxian` 发现 → `zhongcao` 种草 → `hudong` 互动 → `xingdong` 行动 → `shougou` 首购 → `fugou` 复购 → `zhiai` 至爱，外加 `xinzeng` 新增 |
| `initial` | 该人群当日总人数 |
| `zhuanfaxian` | 流转到「发现」的人数 |
| `zhuanzhongcao` | 流转到「种草」的人数 |
| `zhuanhudong` | 流转到「互动」的人数 |
| `zhuanxingdong` | 流转到「行动」的人数 |
| `zhuanshougou` | 流转到「首购」的人数 |
| `zhuanfugou` | 流转到「复购」的人数 |
| `zhuanzhiai` | 流转到「至爱」的人数 |

### 2.2 数据特征
- **总行数**: 2008 行（约 251 天 × 8 人群）
- **日期范围**: 2025-08-19 至 2026-04-26
- **日维度**: 每日 8 条记录（7 个正人群 + 1 个新增）
- **数值格式**: 含千分位逗号（如 `"3,768,484"`）

### 2.3 运算逻辑定义

对于用户选择的日期区间 `[start_date, end_date]`：

```
flow_value = value_at(end_date) − value_at(start_date)
```

**示例**:
- 选择 2025/8/19 → 2025/8/22
- `faxian` 人群 `initial`: 3,768,484 → 3,823,949
- 流转人数 = 3,823,949 − 3,768,484 = **55,465**

**注意**: 这里的「流转」实际上是**期末减期初的净变化**，可能包含正向流入和负向流出，结果可正可负。

---

## 3. UI 设计

### 3.1 布局（参照全店资产）

```
┌─────────────────────────────────────────┐
│  [Tab: 人群漏斗]                        │
│                                         │
│  开始日期 [2025-08-19]  结束日期 [2025-08-26]  [查询]  │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │      漏斗图 / 桑基图            │   │
│  │   展示 8 个人群层级的流转       │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │      流转明细表格               │   │
│  │  人群 | 期初 | 期末 | 净流转 | 各去向... │
│  └─────────────────────────────────┘   │
│                                         │
└─────────────────────────────────────────┘
```

### 3.2 图表设计

**方案 A: 漏斗图**（推荐）
- 使用 ECharts `funnel` 系列
- 8 个层级：发现 → 种草 → 互动 → 行动 → 首购 → 复购 → 至爱
- 展示 `initial` 人数从发现到至爱的逐层衰减

**方案 B: 桑基图**
- 展示人群在各层级间的流转路径
- 数据量较大（8×8=64 条边），可能过于密集

**决策**: 先用**漏斗图**展示层级规模，表格展示详细流转矩阵。

### 3.3 表格设计

| 人群 | 期初人数 | 期末人数 | 净变化 | 发现 | 种草 | 互动 | 行动 | 首购 | 复购 | 至爱 |
|------|----------|----------|--------|------|------|------|------|------|------|------|
| 发现 | 3,768,484 | 3,823,949 | +55,465 | — | +145,279 | +120 | +524 | +206 | 0 | 0 |
| 种草 | 8,886,350 | 8,933,739 | +47,389 | 0 | — | +350 | +736 | +451 | 0 | 0 |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

**新增行**: `xinzeng`（新增人群）单独一行，展示从外部新增到各层级的人数。

---

## 4. 后端 API 设计

### 4.1 新增接口

```
GET /api/v1/market-focus/crowd-funnel?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```

### 4.2 Response Schema

```typescript
interface CrowdFunnelFlow {
  crowd: string           // 人群标识: faxian/zhongcao/...
  crowd_label: string     // 中文名: 发现/种草/...
  initial_start: number   // 期初人数
  initial_end: number     // 期末人数
  initial_delta: number   // 净变化 = end - start
  flows: {
    zhuanfaxian: number
    zhuanzhongcao: number
    zhuanhudong: number
    zhuanxingdong: number
    zhuanshougou: number
    zhuanfugou: number
    zhuanzhiai: number
  }
}

interface CrowdFunnelResponse {
  start_date: string      // "2025-08-19"
  end_date: string        // "2025-08-26"
  flows: CrowdFunnelFlow[]
}
```

### 4.3 实现方案

**数据加载**:
1. 读取 `data.csv`（路径可配置或硬编码，因为只在开发环境使用）
2. 解析日期列 `YYYY/M/D` → `datetime`
3. 去除千分位逗号，转为数值

**计算逻辑**:
1. 根据 `start_date` 和 `end_date` 筛选对应日期的 8 行数据
2. 对于每个 crowd，计算各列的差值：`end_value - start_value`
3. 组装响应

**缓存策略**:
- 同 `dmp_asset_service.py`，文件级缓存（按 mtime）
- 结果级缓存：key = `(start_date, end_date)`

---

## 5. 前端改造点

### 5.1 新增文件

| 文件 | 说明 |
|------|------|
| `views/market-focus/CrowdFunnelTab.vue` | 人群漏斗 Tab 组件 |
| `api/marketFocus.ts` 追加 | `fetchCrowdFunnel(start, end)` 接口定义 |

### 5.2 修改文件

| 文件 | 修改内容 |
|------|----------|
| `views/MarketFocusView.vue` | ① tabList 追加 `{name:'crowd-funnel', label:'人群漏斗'}` ② 引入 CrowdFunnelTab 组件 ③ 日期控件改为日期范围选择器（因为人群漏斗需要起止日期，而非近N周） |

### 5.3 日期控件设计

人群漏斗不使用「近N周」下拉框，而是使用**日期范围选择器**：
- 开始日期 picker（默认最早可用日期）
- 结束日期 picker（默认最新可用日期）
- 快捷选项：「最近7天」「最近30天」「最近90天」

**兼容性处理**: `MarketFocusView.vue` 的顶部控件需要根据当前 Tab 动态切换：
- Tab 1-3 显示「近N周」下拉框
- Tab 4 显示「日期范围」选择器

### 5.4 图表组件

使用 ECharts `funnel` 系列，展示 7 个核心人群（排除 xinzeng）的 `initial_end` 数值。

---

## 6. 关键决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 图表类型 | 漏斗图 | 直观展示人群逐层衰减，与「漏斗」命名一致 |
| 日期控件 | 双日期 picker | 运算逻辑要求自由选择起止日期 |
| 新增人群展示 | 表格单独一行 | xinzeng 是增量来源，非漏斗层级 |
| 负值处理 | 原样显示（红色） | 净流出用红色标识，符合认知 |
| 数值精度 | 整数（无小数） | 人数必须是整数 |

---

## 7. 实施顺序

1. **后端**: `services/dmp_crowd_funnel_service.py` + `main.py` 追加路由
2. **API 类型**: `api/marketFocus.ts` 追加接口定义
3. **前端组件**: `CrowdFunnelTab.vue`
4. **入口整合**: `MarketFocusView.vue` 追加 Tab 和日期控件适配
5. **联调验证**

---

## 8. 风险与注意事项

1. **数据文件路径**: `data.csv` 在当前开发环境路径下，生产部署时需要调整
2. **日期解析**: CSV 使用 `YYYY/M/D`（无补零），解析时需兼容
3. **千分位逗号**: 读取时需 strip 逗号再转 int
4. **日期控件状态**: MarketFocusView 中不同 Tab 的控件状态需要隔离
5. **xinzeng 行处理**: xinzeng 的 `initial` 代表当日新增总人数，在漏斗图中不展示，只在表格中展示
