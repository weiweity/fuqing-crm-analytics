# 芙清 CRM — 前端架构文档

**版本**: v3.2（2026-06-07 同步 v0.4.14.11 — Sprint 4+5 真闭环: RFM Version Banner + 痛点 1 端到端 < 35 min）
**对应目录**: `frontend-vue3/`
**⚠️ 注意**: Streamlit 版本已废弃，不要再使用 `frontend/app.py`。

---

## 1. 技术栈

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| 框架 | Vue3 + Composition API | `<script setup>` 语法 |
| 构建 | Vite 8.x | 端口 5173 |
| 语言 | TypeScript | 类型从 OpenAPI 自动生成，禁止手写 |
| 样式 | Tailwind CSS + Stripe Design System | 配色/阴影/圆角 |
| 状态 | Pinia（filterStore 等） | 全局状态管理 |
| 数据 | TanStack Query（Vue Query） | 服务端状态缓存 |
| UI组件 | Naive UI | n-date-picker / n-select 等 |
| 图表 | ECharts 5 | 地图/柱状图/饼图/桑基图 |
| 类型 | openapi-typescript | 从 `/openapi.json` 自动生成 |

---

## 2. 项目结构

```
frontend-vue3/
├── src/
│   ├── main.ts
│   ├── App.vue
│   ├── api/
│   │   ├── client.ts           # Axios 实例 + 拦截器
│   │   ├── types.ts            # ⚠️ 自动生成，禁止手写（1786行）
│   │   └── endpoints/          # API 端点分组
│   │       ├── metrics.ts      # /api/v1/metrics/*
│   │       ├── audience.ts      # /api/v1/audience/*
│   │       ├── geo.ts          # /api/v1/geo/*
│   │       ├── rfm.ts          # /api/v1/rfm/*
│   │       ├── churn.ts        # /api/v1/churn/*
│   │       └── category.ts      # /api/v1/category/*
│   ├── stores/
│   │   └── filterStore.ts      # 全局筛选状态（时间/渠道/人群）
│   ├── views/                  # 6 个页面 View
│   │   ├── GeoView.vue         # 地域分析
│   │   ├── CategoryView.vue    # 品类分析
│   │   ├── RFMView.vue         # RFM 象限
│   │   ├── ChurnView.vue       # 流失分析
│   │   ├── ProductTierView.vue # 产品梯队
│   │   └── AudienceView.vue    # 人群看板（复杂：含6个Tab）
│   ├── components/
│   │   ├── charts/             # ECharts 封装
│   │   ├── ui/                 # Naive UI 二次封装
│   │   └── layout/             # 布局组件
│   └── utils/
│       ├── formatters.ts       # 金额/日期格式化
│       └── constants.ts         # 象限颜色/渠道列表等
├── package.json
├── vite.config.ts
├── tailwind.config.js
└── tsconfig.json
```

---

## 3. 7 个页面 View

### 3.1 页面总览

| View | 路由 | 核心功能 |
|------|------|---------|
| `GeoView.vue` | `/geo` | 地域分布（省份 TOP10 + 城市 TOP10）+ 人群交叉 |
| `CategoryView.vue` | `/category` | 品类分布（product_class/subclass）+ 人群交叉 |
| `RFMView.vue` | `/rfm` | 8 象限散点图 + 分布柱状图 + 人群明细表 |
| `ChurnView.vue` | `/churn` | 流失分布（动态阈值）+ 流失率趋势 |
| `ProductTierView.vue` | `/product-tier` | 核心品/趋势新品/普通品/长尾品梯队分析 |
| `AudienceView.vue` | `/audience` | 6 个 Tab：概览/日趋势/30指标/渠道/地域/象限 |
| `CustomerHealthView.vue` | `/customer-health` | 老客健康分析独立页面（6 Tab + 配置面板 + CSV导出） |

### 3.2 AudienceView — 6 个 Tab

| Tab | 内容 | API |
|-----|------|-----|
| KPI概览 | GSV/订单数/人数/客单价 | `/api/v1/metrics/overview` |
| 日趋势 | GSV/订单数趋势（折线图） | `/api/v1/metrics/trend` |
| 30日指标 | 近30天关键指标 | `/api/v1/audience/table` |
| 渠道概览 | 各渠道 GSV + **会员占比**（v2.0 新增列） | `/api/v1/audience/table` |
| 地域TOP10 | 省份/城市 GSV 排行 | `/api/v1/geo/distribution` |
| 象限分布 | 11 象限 GSV + 人数 | `/api/v1/rfm/segments` |

---

## 4. 筛选器设计

### 4.1 全局筛选状态（filterStore）

```typescript
// stores/filterStore.ts
interface FilterState {
  periodType: 'wtd' | 'mtd' | 'last_month' | 'custom'  // 默认 WTD
  startDate: string    // YYYY-MM-DD
  endDate: string      // YYYY-MM-DD
  channels: string[]   // [] = 全渠道
  segmentIds: number[] // [] = 全象限
  memberOnly: boolean  // false
}
```

### 4.2 周期默认值（v2.0）

| 周期 | 说明 | 前端行为 |
|------|------|---------|
| **WTD**（默认） | 当周至今 | 自动调取本周一 ~ 今天 |
| MTD | 当月至今 | 自动调取当月1号 ~ 今天 |
| 上月 | 上月同期 | 环比计算 |
| 自定义 | 用户选择 | — |

> ⚠️ WTD prev2 之前存在日期倒置 Bug（2026-04-17 已修复）。

---

## 5. 象限颜色系统（Stripe Design System）

```typescript
// 全局统一象限配色（v4.0，经典 8 象限）
export const SEGMENT_COLORS: Record<number, string> = {
  1: '#FF6B6B',   // 重要价值 - 红
  2: '#4ECDC4',   // 重要保持 - 青
  3: '#45B7D1',   // 重要发展 - 蓝
  4: '#96CEB4',   // 重要挽留 - 绿
  5: '#DDA0DD',   // 一般价值 - 紫
  6: '#98D8C8',   // 一般保持 - 浅绿
  7: '#F7DC6F',   // 一般发展 - 黄
  8: '#BDC3C7',   // 一般挽留 - 灰
};
```

---

## 6. TypeScript 类型生成

### 6.1 生成命令

```bash
# 后端必须运行在 localhost:8000
cd /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/frontend-vue3
npx openapi-typescript http://localhost:8000/openapi.json -o src/api/types.ts
```

### 6.2 生成的类型表示例

```typescript
// src/api/types.ts（自动生成，禁止手写）
export interface OverviewMetrics {
  gsv: number;
  gsv_order_count: number;
  gmv: number;
  order_count: number;
  total_users: number;
  new_users: number;
  old_users: number;
  // ...
}

export interface RFMSegmentResponse {
  segments: SegmentStats[];
  total_users: number;
  avg_r_score: number;
  avg_f_score: number;
  avg_m_score: number;
}
```

---

## 7. 启动与构建

```bash
# 开发模式（热重载）
cd /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/frontend-vue3
npm run dev

# 生产构建
npm run build
# 输出: dist/（0 error）

# 类型检查
npm run type-check
```

---

## 8. 已知问题与修复（v3.0）

| 问题 | 修复 | 日期 |
|------|------|------|
| CustomerHealthView 全量/剔除低价联动异常 | 缓存TTL机制修复 | 2026-04-20 |
| 健康分析配置历史/回滚/审计缺失 | P1-P4 扩展功能完成 | 2026-04-19 |
| TanStack Query ComputedRef queryKey 不追踪 | 改用 `computed(() => ['key', {...}])` 显式展开 | 2026-04-19 |
| 渠道名大小写不一致（u先派样/U先派样） | DB迁移108万条，统一大写U | 2026-04-20 |
| YoYBadge 显示颜色错误 | 修复条件判断 | 2026-04-16 |
| WTD prev2 日期倒置 | 修复 date 计算逻辑 | 2026-04-17 |
| 渠道筛选与概览不联动 | ChannelAPI 支持 period 参数 | 2026-04-16 |
| 会员溢价数值异常 | 修复 is_member LEFT JOIN 逻辑 | 2026-04-16 |
| AUS 显示为 0 | 修复 NULLIF 分母为 0 的情况 | 2026-04-16 |
| 16项 AudienceView Bug | 逐项修复（YoY颜色/日期/day cutoff/TTL/列宽/AUS） | 2026-04-16 |

---

## 9. v0.4.10 同步 — W2/W3/W4 + CI 6 件套前端落地

> 本节记录 v0.4.10 release 中前端侧需要落地/已落地的变更。

### 9.1 RFM Version Banner（W2 配套, v0.4.8+）

后端提供 `GET /api/v1/rfm/version` 后，前端在 RFM 页面顶部加 version banner：

```vue
<!-- src/views/RFMView.vue -->
<template>
  <div class="rfm-page">
    <div v-if="rfmVersion" class="version-banner">
      RFM snapshot: <strong>{{ rfmVersion.active_view }}</strong>
      (manifest version: {{ rfmVersion.version }})
    </div>
    <!-- 8 象限散点图 + 分布柱状图 + 人群明细表 -->
  </div>
</template>

<script setup>
import { useQuery } from '@tanstack/vue-query'
import { getRFMVersion } from '@/api/endpoints/rfm'

const { data: rfmVersion } = useQuery({
  queryKey: ['rfm-version'],
  queryFn: getRFMVersion,
  staleTime: 30 * 1000,  // 30s
})
</script>
```

> ⚠️ `/api/v1/rfm/version` 当前 main 上**没有** `manifest_version` / `fact_rfm_long_rows` / `is_healthy` 字段 — 返回的是 `{active_view, version, ts, path}`（见 03-契约层.md §6）。

- **缓存策略**：30s staleTime，比 manifest 切换频繁度（每天 1 次）短，确保用户能感知到新版本
- **强制刷新**：`version`（整数）变化时清空 TanStack Query 缓存

### 9.2 manifest_version cache invalidation

```typescript
// src/stores/filterStore.ts（伪代码）
watch(rfmVersion, (newVer, oldVer) => {
  if (newVer?.version !== oldVer?.version) {
    // 强制刷新所有 RFM 相关 query
    queryClient.invalidateQueries({ queryKey: ['rfm'] })
  }
})
```

### 9.3 CustomerHealthView 配置面板 W3 状态

- 健康分析页面的"配置变更"按钮触发 PUT /api/v1/customer-health/config
- W3 DQ 跑批失败时，**前端不需要改动**（告警走 lark 通道，运维收到后处理）
- 但建议：在 "AuditLog" tab 加一个"近期 DQ 警告"行（v0.4.11 跟进）

### 9.4 4 个 RFM 端点的前端对接（W5 配套）

> ⚠️ W5 (`feat/wo5-cache` 分支) 未合 main。main 上无 `GET /api/v1/rfm/distribution` / `GET /api/v1/rfm/fact/{dim}`，实际 router 端点为 `r-flow` / `f-flow` / `m-flow` / `segment-orders`。

| 端点 | 前端位置 | 缓存策略 |
|------|---------|---------|
| GET /api/v1/rfm/r-flow | RFMView.vue R 桶分布 | staleTime 5min |
| GET /api/v1/rfm/f-flow | RFMView.vue F 桶分布 | staleTime 5min |
| GET /api/v1/rfm/m-flow | RFMView.vue M 桶分布 | staleTime 5min |
| GET /api/v1/rfm/segment-orders | RFMView.vue 明细表 | staleTime 5min |
| GET /api/v1/rfm/version | RFMView.vue 顶部 banner | staleTime 30s |
| GET /api/v1/rfm/distribution | （W5 规划，**未合 main**） | staleTime 1h |
| GET /api/v1/rfm/segments | （W5 规划，**未合 main**） | staleTime 1h |
| GET /api/v1/rfm/fact/{dim} | （W5 规划，**未合 main**） | staleTime 1h |

### 9.5 CI 6 件套前端相关

| CI 闸 | 前端是否受影响 |
|------|---------------|
| B2 pre-commit import | 否（前端走 vue-tsc） |
| B3 nightly | 否 |
| B4 requirements-lock | 否 |
| B5 test-order | 弱相关（前端 Vitest 可加 random order） |
| B6 weekly report | 否 |
| B1 pytest random | 否 |

### 9.6 自动化测试

```bash
# 前端类型检查（CI 必跑）
cd frontend-vue3 && npm run type-check

# 前端单元测试
cd frontend-vue3 && npm run test:unit

# 前端 lint
cd frontend-vue3 && npm run lint
```
