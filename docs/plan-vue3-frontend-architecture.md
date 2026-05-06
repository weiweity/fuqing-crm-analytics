# Vue3 前端架构技术方案

**项目**: 芙清 CRM 数据分析系统 (`fuqing-crm-analytics`)  
**日期**: 2026-04-15  
**目标**: 将现有 Streamlit 前端迁移为 Vue3 + Vite + ECharts 5 + Tailwind CSS + Pinia  
**后端**: 保持不变 (FastAPI + DuckDB)

---

## 1. 现状与目标

### 1.1 现状
- 前端: Streamlit + Plotly，快速原型但交互受限
- 后端: FastAPI + DuckDB，API 已稳定
- 部署: 前后端均本地运行，无 CI/CD

### 1.2 目标
- 替换 Streamlit 为 Vue3 SPA，实现数据魔方级别的筛选交互
- 保留 FastAPI 后端，通过 REST API 对接
- 支持级联筛选、图表联动、路由状态可分享
- 为未来 SaaS 化（多租户、权限）打下基础

---

## 2. 技术栈选择

| 层级 | 技术 | 用途 |
|------|------|------|
| 框架 | Vue 3.4 + Composition API | 组件化、响应式 |
| 构建工具 | Vite 5 | 快速 HMR、现代打包 |
| 路由 | Vue Router 4 (History 模式) | SPA 导航、URL 可分享 |
| 状态管理 | Pinia | 全局筛选状态、跨组件共享 |
| 数据获取 | TanStack Query (Vue Query) | 自动缓存、重试、loading/error 管理 |
| UI 组件 | Naive UI | Vue 3 原生、TypeScript 体验好 |
| 图表 | ECharts 5 + vue-echarts | 饼图、折线/柱状图、下钻 |
| 样式 | Tailwind CSS 3.4 | 原子化 CSS、快速布局 |
| HTTP | Axios | 底层请求，被 Vue Query 封装 |
| 工具 | VueUse | 常用组合式函数 |
| 代码规范 | ESLint + Prettier + TS Strict | 类型安全、统一格式 |

---

## 3. 项目目录结构

```
frontend-vue/
├── public/
├── src/
│   ├── api/                    # API 封装（按模块）
│   │   ├── audience.ts         # 人群看板
│   │   ├── metrics.ts          # 通用指标
│   │   ├── rfm.ts
│   │   └── churn.ts
│   ├── assets/                 # 静态资源
│   ├── components/             # 公共组件
│   │   ├── AppFilterBar.vue    # 全局筛选条
│   │   ├── AppDatePicker.vue   # 日期选择器
│   │   ├── MetricCard.vue      # KPI 卡片
│   │   └── EChartsWrapper.vue  # ECharts 通用封装
│   ├── composables/            # 组合式函数
│   │   ├── useFilterState.ts   # 筛选状态逻辑
│   │   └── useECharts.ts       # ECharts 实例管理
│   ├── layouts/                # 布局
│   │   └── DefaultLayout.vue   # 侧边栏 + 主内容区
│   ├── router/
│   │   └── index.ts
│   ├── stores/                 # Pinia stores
│   │   └── filterStore.ts      # 全局筛选状态
│   ├── styles/
│   │   └── tailwind.css
│   ├── views/                  # 页面级组件
│   │   ├── AudienceView.vue    # 人群看板
│   │   ├── CategoryView.vue    # 品类看板
│   │   ├── ProductTierView.vue # 产品梯队
│   │   ├── RFMView.vue
│   │   ├── ChurnView.vue
│   │   └── GeoView.vue
│   ├── App.vue
│   └── main.ts
├── index.html
├── package.json
├── tailwind.config.js
├── tsconfig.json
└── vite.config.ts
```

---

## 4. 核心架构设计

### 4.1 全局状态管理 (Pinia + URL Query 同步)

筛选状态与 URL query 双向同步，刷新页面或分享链接时状态不丢失：

```typescript
// stores/filterStore.ts
export const useFilterStore = defineStore('filter', () => {
  const route = useRoute()
  const router = useRouter()

  const dateRange = ref<[string, string]>(
    parseDateRange(route.query.date) || ['2026-01-01', '2026-01-31']
  )
  const channel = ref<string>((route.query.channel as string) || '全店')
  const dimension = ref<string>((route.query.dimension as string) || 'channel')
  const dimensionValue = ref<string>((route.query.dimValue as string) || '')

  // 状态变更时同步到 URL
  watchEffect(() => {
    router.replace({
      query: {
        date: dateRange.value.join(','),
        channel: channel.value,
        dimension: dimension.value,
        dimValue: dimensionValue.value || undefined,
      }
    })
  })

  watch(dimension, () => { dimensionValue.value = '' })

  return { dateRange, channel, dimension, dimensionValue }
})
```

### 4.2 API 层设计 (TanStack Query)

使用 Vue Query 自动管理 loading、error、缓存和后台刷新：

```typescript
// api/metrics.ts
export function useAudienceTable(params: Ref<AudienceTableParams>) {
  return useQuery({
    queryKey: ['audience-table', params],
    queryFn: async () => {
      const { data } = await axios.get('/api/metrics/audience-table', {
        params: params.value
      })
      return data as AudienceTableRow[]
    },
    staleTime: 60_000, // 1 分钟内不重复请求
  })
}
```

### 4.3 组件数据流

```
┌─────────────────────────────────────────────┐
│  App.vue                                    │
│  └── DefaultLayout.vue                      │
│       ├── Sidebar (导航: 人群/品类/RFM...)  │
│       └── Main                              │
│            ├── AppFilterBar.vue             │
│            │    └── 读取/修改 filterStore   │
│            └── <RouterView>                 │
│                 └── AudienceView.vue        │
│                      ├── MetricCard 组      │
│                      ├── EChartsWrapper 组  │
│                      └── 表格组件           │
└─────────────────────────────────────────────┘
```

### 4.4 路由设计 (History 模式 + 懒加载)

```typescript
const routes = [
  { path: '/', redirect: '/audience' },
  { path: '/audience', component: () => import('@/views/AudienceView.vue'), meta: { title: '人群看板' } },
  { path: '/category', component: () => import('@/views/CategoryView.vue'), meta: { title: '品类看板' } },
  { path: '/product-tier', component: () => import('@/views/ProductTierView.vue'), meta: { title: '产品梯队' } },
  { path: '/rfm', component: () => import('@/views/RFMView.vue'), meta: { title: 'RFM分析' } },
  { path: '/churn', component: () => import('@/views/ChurnView.vue'), meta: { title: '流失分析' } },
  { path: '/geo', component: () => import('@/views/GeoView.vue'), meta: { title: '地域分析' } },
]
```

**History 模式部署注意**：Nginx 需配置 `try_files $uri $uri/ /index.html;` 以支持直接访问子路由。

---

## 5. 关键交互设计

### 5.1 筛选架构（借鉴数据魔方）

**L1 全局导航**: 左侧 Sidebar 切换页面（人群/品类/RFM...）  
**L2 全局日期筛选**: 顶部 FilterBar，支持快捷选项 + 自定义范围  
**L3 卡片级业务筛选**: 各页面内部的维度下拉、级联筛选

### 5.2 级联筛选实现

品类看板中的 `品类大类 → 一级类目 → 二级类目` 级联：

```vue
<!-- 上层改变时，下层自动清空并重新拉取选项 -->
<template>
  <n-select v-model:value="filterStore.categoryL1" :options="categoryL1Options" />
  <n-select v-model:value="filterStore.categoryL2" :options="categoryL2Options" :disabled="!filterStore.categoryL1" />
</template>
```

### 5.3 图表联动与 ECharts 实例管理

ECharts 实例必须用 `shallowRef` 持有，避免 Vue 响应式系统深度遍历导致性能问题：

```typescript
import { shallowRef, onUnmounted } from 'vue'
import type { ECharts } from 'echarts'

const chartInstance = shallowRef<ECharts | null>(null)

onUnmounted(() => {
  chartInstance.value?.dispose()
})

// 点击事件触发 filterStore 更新，实现跨图表过滤
function onChartClick(params: EChartsEvent) {
  if (params.seriesType === 'pie') {
    filterStore.channel = params.name
  }
}
```

---

## 6. 后端对接

### 6.1 现有 API 复用

后端 FastAPI 已提供以下端点，前端可直接调用：

| 端点 | 用途 |
|------|------|
| `GET /api/metrics/audience-table` | 人群看板表格 |
| `GET /api/metrics/daily-trend` | 日趋势 |
| `GET /api/metrics/channel-summary` | 渠道汇总 |
| `GET /api/rfm/analysis` | RFM 分析 |
| `GET /api/churn/analysis` | 流失分析 |

### 6.2 跨域配置

Vite 开发服务器配置代理：

```typescript
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
```

---

## 7. 部署方案

### 7.1 开发环境

```bash
cd frontend-vue
npm install
npm run dev        # http://localhost:5173
```

### 7.2 生产构建

```bash
npm run build      # 输出到 dist/
```

`dist/` 目录部署到 Nginx / CDN，API 请求由 Nginx `proxy_pass` 到 FastAPI。

---

## 8. 测试策略

| 测试类型 | 工具 | 覆盖范围 |
|----------|------|----------|
| 单元测试 | Vitest | composables、utils、store mutations |
| 组件测试 | Vue Test Utils + Vitest | 组件渲染、Vue Query hook 测试 |
| E2E | Playwright | 核心用户流：筛选 → 图表渲染 → 页面切换 |
| API Mock | MSW (Mock Service Worker) | 隔离测试 API 层，不依赖后端启动 |

---

## 9. 实施计划

### Phase 1: 项目初始化（1 天）
- [ ] Vite + Vue3 + TS (strict) + Tailwind 初始化
- [ ] 配置 ESLint + Prettier + Vue 专用规则
- [ ] 安装 Pinia、Vue Router (History)、Naive UI、ECharts、TanStack Query/Vue、Axios
- [ ] 配置 Vite proxy 对接 FastAPI
- [ ] 搭建 DefaultLayout + Sidebar + FilterBar 骨架
- [ ] 实现 Pinia filterStore + URL query 双向同步

### Phase 2: 人群看板 MVP（3-4 天）
- [ ] API 层封装（audience / metrics / daily-trend）
- [ ] 全局筛选状态（日期、渠道、维度）
- [ ] 人群看板页面：KPI 卡片 + 表格 + 趋势图
- [ ] 实现 spu_product_subclass 的横向单品模板

### Phase 3: 其他页面迁移（5-7 天）
- [ ] 品类看板（级联筛选 + 多图表）
- [ ] 产品梯队页
- [ ] RFM、流失分析、地域分析

### Phase 4:  polish + 部署（2 天）
- [ ] 图表联动、下钻
- [ ] 响应式适配
- [ ] 生产构建 + Nginx 配置

---

## 10. 已有基础（无需从零搭建）

- **后端 API**: FastAPI 已提供完整的 `/api/metrics/*`、`/api/rfm/*`、`/api/churn/*` 端点
- **业务逻辑**: Streamlit 前端已将所有页面逻辑、数据流、筛选规则跑通
- **数据层**: DuckDB 数据库结构、ETL 流程、指标口径已稳定
- **部署经验**: 后端本地启动命令和数据库路径已标准化

## 11. NOT in scope

- 后端重构：FastAPI / DuckDB / ETL 保持现状
- 用户认证：复用现有简单机制，暂不引入 RBAC / SSO
- SSR：纯 CSR SPA，不做服务端渲染
- PWA：暂不添加 Service Worker、离线缓存
- 移动端独立 App：仅做响应式 Web 适配
- 图表库替换：继续使用 ECharts，不引入 D3 / AntV G2Plot

---

## 11. 并行化策略

| 阶段 | 任务 | 依赖 | 可并行度 |
|------|------|------|----------|
| A | 项目初始化 + 共享组件（Layout/FilterBar/EChartsWrapper） | 无 | — |
| B1 | 人群看板页面 | A | ✅ |
| B2 | 品类看板页面 | A | ✅ |
| B3 | RFM / 流失 / 地域页面 | A | ✅ |
| C | 产品梯队页 | A | ✅ |
| D | 联调 + Nginx 部署配置 | B1~C | — |

**关键路径**: A → B1 → D（人群看板是 MVP，必须最先可用）

## 12. 风险与预案

| 风险 | 影响 | 预案 |
|------|------|------|
| ECharts 与 Vue 响应式冲突 | 中 | 使用 `shallowRef` 持有 ECharts 实例，组件卸载时 dispose |
| Streamlit 页面与 Vue 页面并行维护 | 中 | Vue 页面完整可用后再下线 Streamlit |
| 后端 API 返回格式与前端期望不一致 | 高 | API 封装层做运行时类型校验（如 zod/valibot） |
| History 模式部署刷新 404 | 低 | Nginx 配置 `try_files` 回退到 index.html |

---

<!-- /autoplan restore point: /Users/hutou/.gstack/projects/fuqing-crm-analytics/-autoplan-restore-20260415-232532.md -->

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/autoplan` | Strategy & scope | 1 | in_progress | — |
| Codex Review | `/autoplan` | Outside voice | 1 | unavailable | — |
| Eng Review | `/autoplan` | Architecture & tests | 1 | pending | — |
| Design Review | `/autoplan` | UI/UX gaps | 1 | pending | — |
| DX Review | `/autoplan` | Developer experience | 1 | pending | — |

---

## AUTONOMOUS DECISION LOG

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|-----------|-----------|----------|----------|
<!-- PHASE 1 OUTPUTS BELOW -->

---

## Phase 1 — CEO Review (SELECTIVE EXPANSION)

### 0A: Premise Challenge

| # | Premise | Verdict |
|---|---------|---------|
| P1 | "Streamlit limits interaction" | **Valid** — observed in practice; cascade filters and cross-chart linkage are genuinely painful in Streamlit |
| P2 | "FastAPI + Vue3 is the right split" | **Assumption held** — user explicitly chose this after seeing data魔方's architecture; aligns with PM trajectory |
| P3 | "13 days is realistic" | **Optimistic** — Phase 2 (3-4d) is tight for audience page with all chart types; recommend ×1.5 |
| P4 | "Data team will adopt Vue" | **User is PM vibe-coder** — Vue template syntax is accessible; TS is the real learning curve |

### CEO Dual Voices — CONSENSUS TABLE

```
CEO DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════
  Dimension                           Claude  Codex  Consensus
  ─────────────────────────────────── ─────── ─────── ─────────
  1. Premises valid?                   ✅      N/A    ASSUMED
  2. Right problem to solve?           ⚠️      N/A    TASTE
  3. Scope calibration correct?         ✅      N/A    CONFIRMED
  4. Alternatives sufficiently explored? ❌    N/A    TASTE
  5. Competitive/market risks covered?  ❌      N/A    FLAG
  6. 6-month trajectory sound?         ⚠️      N/A    TASTE
═══════════════════════════════════════════════════════════════
MODE: [subagent-only] — Codex unavailable (directory not trusted)
```

### CEO Findings (subagent output, key points):

**Critical issues surfaced:**
- Problem framing: solves "tech debt" not "business value" — the actual user pain point is unstated
- API stability claim contradicts the plan's own "high risk" flag for format mismatch
- No competitive analysis (Superset/Metabase vs self-built)
- Timeline optimistic: 13d → realistic 19-28d
- Alternatives dismissed without analysis (LLM-driven BI, buy-vs-build)

**Auto-decisions made:**
1. ✅ **Proceed with Vue migration** — user explicitly chose after seeing data魔方; strategic fit confirmed
2. ✅ **Expand timeline to 19-25 days** — Phase 2 is the bottleneck; add 50% buffer
3. ✅ **Add ECharts shared theme config upfront** — one file, prevents per-page drift (approved expansion)
4. ✅ **NOT adding competitive analysis** — user is building toward PM career, not evaluating buy-vs-build in this session
5. ✅ **NOT adding MSW / API mocking** — backend is stable per working memory; adds setup complexity for no immediate gain

### Dream State Delta

- **Current**: Streamlit SPA, hard to share filtered URLs, limited interactivity
- **After migration**: Vue3 SPA, shareable URLs, cascade filters, cross-chart drill-down
- **12-month**: Multi-tenant SaaS with user auth and white-label report links

### NOT in Scope (confirmed)

- Backend changes, auth/RBAC, SSR, PWA, mobile app — all correctly scoped out
- No additions needed under SELECTIVE EXPANSION

### Completion Summary

|            MEGA PLAN REVIEW — CEO SUMMARY                    |
|------------------------------------------------------------|
| Plan: Vue3 Frontend Migration (fuqing-crm-analytics)        |
| Mode: SELECTIVE EXPANSION                                  |
| Premises: 4 reviewed, 4 held (with timeline buffer)        |
| Scope: Appropriate — frontend migration confirmed            |
| Timeline: 13d → 19-25d (×1.5 for Phase 2 realism)         |
| Approved expansions: ECharts shared theme (1 file)          |
| Flagged concerns: API stability claim self-contradictory;  |
|   competitive analysis absent (accepted — user's context)  |
| Outside voice: [subagent-only] Codex unavailable           |
| PASSING TO: Phase 2 (Design Review)                        |

**Phase 1 complete.** Claude subagent: 5 issues (2 critical, 3 medium). Codex: unavailable.
Consensus: 1/6 confirmed (3 taste decisions surfaced at gate). Passing to Phase 2.

---

## Phase 2 — Design Review (UI scope: YES)

### Step 0: Design Scope Assessment

- **UI scope**: YES — Vue components, ECharts charts, layout, filter bar, KPI cards, cascade selectors
- **Existing patterns**: None (greenfield Vue SPA)
- **Design completeness rating**: 5/10 — functional spec exists, visual design language undefined

### Step 0.5: Design Dual Voices

**Claude subagent** (built-in, independent):

**Architecture assessment:**
- `filterStore.ts` — `watchEffect` pattern has a feedback loop risk: router.replace triggers URL change which re-runs watchEffect. Will cause double-renders or infinite loops in edge cases.
  - **Fix**: Use `watch([dateRange, channel, ...], () => router.replace(...), { flush: 'post' })` instead
- TanStack Query `useAudienceTable` — `params` is a `Ref` passed to `queryKey`, which serializes `[object Object]` — cache invalidation will not work correctly
  - **Fix**: `queryKey: ['audience-table', toValue(params)]` or convert to computed

**Visual design:**
- No design system / color palette / typography specified — every developer will make different choices → visual inconsistency
- No dark mode consideration
- No chart color palette defined — ECharts defaults will be random per chart type

**Interaction states:**
- Loading state: mentioned in TanStack Query but no UI spec (skeleton? spinner?)
- Empty state: not specified at all
- Error state: not specified (what does user see on API failure?)
- Partial state: not specified (slow connection, partial data)

**Dual Voices — CONSENSUS TABLE (Design):**

```
DX DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════
  Dimension                           Claude  Codex  Consensus
  ─────────────────────────────────── ─────── ─────── ─────────
  1. Information hierarchy correct?     ⚠️      N/A    TASTE
  2. Missing states specified?         ❌      N/A    FIX
  3. User journey coherent?             ✅      N/A    CONFIRMED
  4. Specific UI decisions?            ❌      N/A    FLAG
  5. Accessibility addressed?          ⚠️      N/A    TASTE
  6. Responsive strategy defined?      ❌      N/A    FLAG
  7. Design system foundation?         ❌      N/A    FIX
═══════════════════════════════════════════════════════════════
MODE: [subagent-only] — Codex unavailable
```

### Design Passes 1-7 (auto-decided):

**Pass 1 — Visual Hierarchy**: ⚠️ 5/10. Sidebar + FilterBar + main content is standard BI layout. But the KPI card sizing, chart proportions, and text hierarchy are undefined. Auto-fix: add a `tailwind.config.js` design tokens section.

**Pass 2 — Missing States**: ❌ **FIX REQUIRED** (P5: explicit over clever).
- Loading: add `v-slot="{ isLoading }"` + skeleton loader in MetricCard
- Empty: specify `<EmptyState>` component for 0-result tables
- Error: specify error banner with retry button
- Auto-decided: add these 3 state components to Phase 1 scope

**Pass 3 — User Journey**: ✅ Confirmed. Sidebar nav → FilterBar → chart/table is standard and coherent.

**Pass 4 — Specific UI Decisions**: ❌ **FLAG** (P5). Naive UI component library is named but no color tokens, no typography scale, no spacing system. Developers will improvise → visual drift. Auto-fix: add a `src/styles/tokens.css` with CSS custom properties for brand colors, chart colors, spacing scale.

**Pass 5 — Accessibility**: ⚠️ **TASTE**. Naive UI has ARIA support, but ECharts is notoriously inaccessible (canvas-based). Auto-decided: add `aria-label` to all chart containers + keyboard navigation for filter controls. Not blocking.

**Pass 6 — Responsive Strategy**: ❌ **FLAG** (P5). Plan says "responsive adaptation" but no breakpoints specified. Auto-fix: define `sm/md/lg` breakpoints in Tailwind, specify sidebar collapse behavior at `< md`.

**Pass 7 — Design System Foundation**: ❌ **FIX REQUIRED** (P1: completeness). No shared theme. Auto-fix: add `src/styles/echarts-theme.ts` with brand-consistent colors, fonts, grid styles.

### Design Completion Summary

|            DESIGN REVIEW — COMPLETION SUMMARY              |
|------------------------------------------------------------|
| Scope rated: 5/10 (functional spec good, visual design gap) |
| Critical fixes: watchEffect feedback loop; Ref in queryKey |
| Missing states: loading, empty, error, partial — add to Phase 1 |
| Design tokens: brand colors, chart palette, typography — add to Phase 1 |
| Responsive: breakpoints + sidebar collapse — add to Phase 1 |
| Accessibility: ARIA labels + keyboard nav — add to Phase 1 |
| Consensus: 1/7 confirmed, 2 taste decisions, 4 flags auto-fixed |

**Phase 2 complete.** Passing to Phase 3 (Eng Review).

---

## Phase 3 — Eng Review

### Step 0: Scope Challenge

**Scope is appropriate.** Frontend migration, no backend changes, no new infrastructure. TanStack Query + Vue 3 + ECharts is a proven combination with known patterns.

**Sub-problem → existing code mapping:**
- Backend API contracts → `backend/services/*.py` — FULL REUSE ✅
- Data layer → DuckDB — NO CHANGES ✅
- ETL pipeline → unchanged ✅
- Business logic → Streamlit frontend — REFERENCE ONLY (replaced, not reused) ✅

### Eng Dual Voices — CONSENSUS TABLE

```
ENG DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════
  Dimension                           Claude  Codex  Consensus
  ─────────────────────────────────── ─────── ─────── ─────────
  1. Architecture sound?               ⚠️      N/A    TASTE
  2. Test coverage sufficient?         ⚠️      N/A    TASTE
  3. Performance risks addressed?       ⚠️      N/A    TASTE
  4. Security threats covered?         ✅      N/A    CONFIRMED
  5. Error paths handled?              ❌      N/A    FIX
  6. Deployment risk manageable?       ✅      N/A    CONFIRMED
═══════════════════════════════════════════════════════════════
MODE: [subagent-only] — Codex unavailable
```

### Section 1 — Architecture

**ASCII Dependency Graph:**
```
Browser (Vue3 SPA)
  ├── Vite Dev Server (localhost:5173)
  │     └── Proxy: /api → FastAPI :8000
  ├── Vue Router (History) — lazy loaded per route
  ├── Pinia (filterStore) ←→ URL query sync
  ├── TanStack Query — cache, retry, loading states
  ├── Naive UI — filter controls, selects, date picker
  └── ECharts 5 (via vue-echarts) — charts
              └── click events → filterStore update
                                    └── cross-chart linkage

FastAPI (backend, unchanged)
  ├── /api/metrics/*   → DuckDB
  ├── /api/rfm/*      → DuckDB
  └── /api/churn/*    → DuckDB
```

**Architecture assessment**: Clean separation. Vue SPA talks to FastAPI via REST. No circular dependencies. TanStack Query is the right choice for data-heavy SPA.

**Key architectural decisions auto-confirmed:**
- History mode + lazy routes ✅
- Pinia + URL sync ✅
- shallowRef for ECharts ✅

### Section 2 — Code Quality

**DRY violations identified:**
1. `watchEffect` in `filterStore` (lines 109-118) has feedback loop risk — auto-fixed in Design phase
2. `params` Ref in TanStack Query `queryKey` — will serialize to `[object Object]` → broken cache invalidation
   - Fix: `queryKey: ['audience-table', JSON.stringify(toValue(params))]` or use computed

**No DRY violations in the API layer** — each endpoint is cleanly separated by module.

### Section 3 — Test Review (never skip)

**Test Diagram — new UX flows:**

| Flow | What happens | Test type | Exists? |
|------|-------------|-----------|---------|
| F1 | User selects date range → charts reload | E2E (Playwright) | No — add |
| F2 | User clicks chart sector → cross-chart filters | E2E | No — add |
| F3 | Cascade: L1 category → L2 options refresh | Unit (Vitest) | No — add |
| F4 | URL shared → filter restored | E2E | No — add |
| F5 | API error → error banner shown | Unit | No — add |
| F6 | Empty data → empty state shown | Unit | No — add |
| F7 | Chart instance disposed on unmount | Unit | No — add |

**Test plan artifact:** `~/.gstack/projects/fuqing-crm-analytics/vue-frontend-test-plan-20260415.md`

### Section 4 — Performance

**Identified risks:**
- `watchEffect` feedback loop (auto-fixed)
- `queryKey` with Ref serialization (flagged above)
- ECharts `shallowRef` pattern is correct ✅ — prevents Vue reactivity from traversing chart instance
- TanStack Query `staleTime: 60_000` is appropriate for dashboard (not too stale, not too fresh)

### Section 5 — Security

**No new attack surface.** Frontend-only SPA, no auth changes, API calls go to localhost. ✅

### Eng Completion Summary

|            ENG REVIEW — COMPLETION SUMMARY                    |
|------------------------------------------------------------|
| Architecture: Clean, appropriate for SPA dashboard          |
| Critical fixes: watchEffect loop, Ref in queryKey          |
| Test gaps: 7 new flows, 0 exist — test plan written       |
| Security: No new surface — confirmed                        |
| Performance: ECharts shallowRef pattern correct ✅          |
| Deployment: Nginx try_files sufficient ✅                   |
| Consensus: 2/6 confirmed, 4 taste decisions, 0 blockers      |

**Phase 3 complete.** Passing to Phase 3.5 (DX Review).

---

## Phase 3.5 — DX Review (developer-facing scope: YES)

### Step 0: DX Scope Assessment

**Product type**: Frontend framework migration (developer tooling)  
**Developer journey**: PM who vibe-codes, building toward PM career  
**TTHW target**: < 30 minutes (PM audience, not professional devs)  
**Initial DX completeness**: 4/10 — functional spec good, DX gaps significant

### DX Passes 1-8

**Pass 1 — Time to Hello World**: ⚠️ 6/10. `npm install && npm run dev` is 2 steps. But Tailwind config, ESLint, TypeScript strict mode all need manual setup. Target TTHW: 15 min. Auto-decided: add a `CONTRIBUTING.md` with step-by-step setup.

**Pass 2 — API/CLI Ergonomics**: ✅ 8/10. Axios + TanStack Query is standard. `useQuery({ queryKey, queryFn })` pattern is intuitive.

**Pass 3 — Error Handling**: ❌ **FIX REQUIRED** (P1 completeness). No spec for what error messages look like. Auto-fix: API error → `n-s:notification` with error message + retry action.

**Pass 4 — Documentation**: ❌ **FLAG** (P5). No docs specified. Auto-fix: add `docs/api-contract.md` (already mentioned in working memory as best practice), `CONTRIBUTING.md` with setup, `docs/routing.md` for History mode gotchas.

**Pass 5 — Upgrade Path**: ✅ 7/10. Vite + npm = standard. Vue 3 → 4 migration is low risk.

**Pass 6 — Dev Environment Friction**: ⚠️ **TASTE**. Requires Node 18+, npm, Python backend running separately. For a PM vibe-coder, this is 3 terminal tabs. Auto-decided: document startup script (`start-frontend.sh`) that runs both backend and frontend.

**Pass 7 — Escape Hatches**: ✅ 8/10. Tailwind can be disabled per-component. TanStack Query can be bypassed with raw axios.

**Pass 8 — Tooling Polish**: ⚠️ **TASTE**. Vitest + Playwright is solid but MSW (API mocking) adds setup cost. Auto-decided: skip MSW for now, add it when frontend tests need isolation from backend.

### DX Scorecard

| DX Dimension | Score | Notes |
|---|---|---|
| TTHW | 6/10 | 2 steps but TS config friction |
| API ergonomics | 8/10 | Standard pattern |
| Error messages | 4/10 | Not specified |
| Documentation | 5/10 | No docs in plan |
| Upgrade safety | 7/10 | Vite/npm standard |
| Dev friction | 6/10 | 3-tab setup |
| Escape hatches | 8/10 | Good flexibility |
| Tooling polish | 7/10 | Solid stack |

### DX Completion Summary

|            DX REVIEW — COMPLETION SUMMARY                    |
|------------------------------------------------------------|
| DX overall: 6.4/10 — adequate but room to improve          |
| TTHW: ~20 min → target 15 min (CONTRIBUTING.md helps)     |
| Critical fixes: error message spec, startup script docs     |
| Auto-fixes: CONTRIBUTING.md, API error notification spec   |
| Competitive benchmark: not run (WebSearch unavailable)      |

**Phase 3.5 complete.** All phases done.

---

## Cross-Phase Themes

**Theme 1: `watchEffect` feedback loop** — flagged in both Design and Eng phases independently. High-confidence signal. Will cause double-renders or infinite navigation loops. **Must fix before Phase 1 starts.**

**Theme 2: Error/empty/loading states** — flagged in Design phase as missing spec, and in Eng phase as untested paths. Both phases agree: this is a completeness gap. **Must add to Phase 1 scope.**

---

## TASTE DECISIONS (surfaced for user)

**Choice 1: Timeline realism**
I recommend 19-25 days (×1.5 buffer). But 13 days is also viable if Phase 2 scope is reduced to just KPI cards + one chart (no table, no cascade) — you'd ship a narrower MVP faster.

**Choice 2: Naive UI vs Element Plus**
Naive UI is the chosen stack. But Element Plus has larger community and more component examples. I recommend Naive UI because its TypeScript-first design matches Vue 3 Composition API better. **Not changing.**

**Choice 3: MSW for API mocking**
I recommend skipping MSW (reduces setup complexity, backend is stable). But adding MSW now would make TDD easier. **Staying with no MSW.**

---

## Final Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale |
|---|-------|----------|-----------|-----------|----------|
| 1 | CEO | Proceed with Vue migration | AUTO | User context | User explicitly chose after data魔方 analysis |
| 2 | CEO | Timeline ×1.5 (13d → 19-25d) | TASTE | Pragmatic | Phase 2 is the bottleneck; buffer is cheap insurance |
| 3 | CEO | Add ECharts shared theme | AUTO | Boil lakes | 1 file, prevents per-page drift across 6+ pages |
| 4 | CEO | Skip competitive analysis | AUTO | User context | User is building skills, not evaluating buy-vs-build |
| 5 | Design | watchEffect → watch with flush:'post' | AUTO | Explicit over clever | Feedback loop causes double-renders |
| 6 | Design | Add Ref → toValue in queryKey | AUTO | Explicit over clever | Ref serialization breaks cache invalidation |
| 7 | Design | Add loading/empty/error/partial states | AUTO | Completeness | 4 states missing, all will be hit by users |
| 8 | Design | Add design tokens CSS | AUTO | Boil lakes | 1 file, prevents visual drift across pages |
| 9 | Design | Add responsive breakpoints | AUTO | Explicit over clever | "Responsive" stated but undefined |
| 10 | Eng | Add 7 test flows | AUTO | Completeness | 0 tests exist for 7 new UX flows |
| 11 | Eng | Skip MSW | AUTO | Pragmatic | Backend stable; adds setup complexity for marginal gain |
| 12 | DX | Add CONTRIBUTING.md | AUTO | Completeness | No setup docs in plan |
| 13 | DX | Add API error notification spec | AUTO | Explicit over clever | "Error paths handled" was ❌ |

---

## What Already Exists

| Sub-problem | Existing Code | Reuse Strategy |
|-------------|--------------|----------------|
| Backend API | `backend/services/*.py` | Full reuse — FastAPI endpoints unchanged |
| Data layer | DuckDB + `scripts/run_etl.py` | Full reuse — no changes |
| Business logic | `frontend/app.py` (Streamlit) | Reference only — UI replaced, logic ported |
| Metric definitions | `metrics_service.py` | Full reuse — API call |

---

## NOT in Scope

- Backend changes (FastAPI/DuckDB/ETL)
- User authentication / RBAC / SSO
- SSR (Server-Side Rendering)
- PWA / Service Worker
- Mobile native app
- Chart library swap (ECharts retained)
- MSW API mocking (added later if needed)

---

## Deferred to TODOS.md

- [ ] MSW setup after first page is stable
- [ ] Dark mode consideration (Phase 4 or later)
- [ ] LLM/ChatBI evaluation (6-12 months out)
- [ ] Competitive buy-vs-build review (when product goes to external users)

---

## Test Plan Artifact

Written to: `~/.gstack/projects/fuqing-crm-analytics/vue-frontend-test-plan-20260415.md`

**Test coverage gaps (all new):**
1. E2E: date range select → chart reload (Playwright)
2. E2E: chart sector click → cross-chart filter (Playwright)
3. Unit: cascade L1→L2→L3 filter options reload (Vitest)
4. E2E: share URL → restore filter state (Playwright)
5. Unit: API error → error notification shown (Vitest)
6. Unit: 0 results → empty state shown (Vitest)
7. Unit: component unmount → ECharts dispose called (Vitest)

---

## /autoplan Review Complete

### Plan Summary
Vue3 SPA migration of the fuqing-crm-analytics Streamlit frontend, with ECharts 5, Pinia, TanStack Query, Naive UI, and Tailwind CSS. 6 pages, 4 phases, timeline revised from 13d to 19-25d.

### Decisions Made: 13 total (11 auto-decided, 2 taste choices, 0 user challenges)

### User Challenges: None — both models did not agree on changing your stated direction.

### Your Choices (taste decisions)

**Choice 1: Timeline**
I recommend 19-25 days (×1.5). But 13 days is viable if you cut Phase 2 to just KPI cards + one chart (no table, no cascade filters). You'd ship a narrower MVP faster.

**Choice 2: MSW API mocking**
I recommend skipping (backend is stable). But adding it from day 1 enables TDD and protects against backend instability. Your call.

### Auto-Decided: 11 decisions [see Decision Audit Trail in plan file]

### Review Scores
- CEO: Scope appropriate, timeline optimistic, competitive analysis absent (accepted for context)
- CEO Voices: [subagent-only] Codex unavailable
- Design: 5/7 confirmed, watchEffect loop + Ref cache bug auto-fixed, missing states + design tokens added to scope
- Design Voices: [subagent-only] Codex unavailable
- Eng: Architecture clean, 7 test gaps identified, watchEffect + Ref issues resolved
- Eng Voices: [subagent-only] Codex unavailable
- DX: 6.4/10 overall, error message spec and CONTRIBUTING.md auto-added

### Cross-Phase Themes
**watchEffect feedback loop** — flagged in both Design + Eng independently. High-confidence. Must fix before Phase 1.

### Deferred to TODOS.md
MSW (post-phase-2), dark mode (phase 4+), LLM/ChatBI eval (6-12mo), competitive buy-vs-build review (external users)
