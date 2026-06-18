# Visitor Chain Ground-Truth Audit (Sprint 39.2)

**Audit date**: 2026-06-19
**Auditor**: Sprint 39.2 ground-truth audit (Sprint 36-1 留尾 #10)
**Sprint**: 39.2
**Audit goal**: 验证 backend visitor chain 是否真"完整可激活"还是"dead code 待清"

---

## TL;DR (Executive Summary)

**Visitor backend 100% 活跃** (5 文件 106 行,0 dead code):
- `backend/routers/visitor.py` (58 行) — /summary + /daily-trend endpoint
- `backend/contracts/visitor.py` (48 行) — Pydantic schema
- `backend/main.py:268` — `app.include_router(visitor_router)` 真注册
- `backend/contracts/schemas.py:13` — VisitorSummaryResponse / VisitorDailyTrendItem / VisitorDailyTrendResponse 在 __all__

**Frontend API client 100% 活跃** (1 文件 51 行):
- `frontend-vue3/src/api/audience.ts:354-368` — `fetchVisitorSummary()` + `fetchVisitorDailyTrend()` 函数
- `frontend-vue3/src/api/audience.ts:320-348` — TypeScript interfaces (VisitorSummary, VisitorDailyTrend, VisitorDailyTrendItem)
- `frontend-vue3/src/views/AudienceView.vue:11-12` — import 这 2 个函数
- `frontend-vue3/src/views/AudienceView.vue:194, 208` — **真在调** (从 AudienceView.vue line 194 `fetchVisitorSummary({...})` + line 208 `fetchVisitorDailyTrend({...})`)

**唯一缺**: frontend `router/index.ts` 没注册 `/visitor` 路由 (Sprint 33.2 留尾 — 写 10/10 view smoke spec 时 router 没这个路由,所以 spec 没覆盖)。

---

## 1. 实地调查 (Ground Truth)

### 1.1 Backend 文件清单

| 文件 | 行数 | 状态 | 证据 |
|---|---|---|---|
| `backend/routers/visitor.py` | 58 | **活跃** | `@router.get("/summary")` line 17 + `@router.get("/daily-trend")` line 38 |
| `backend/contracts/visitor.py` | 48 | **活跃** | `class VisitorSummaryResponse(BaseModel)` line 7 |
| `backend/main.py:268` | 1 | **活跃** | `app.include_router(visitor_router)` |
| `backend/contracts/schemas.py:13,53` | 2 | **活跃** | `VisitorSummaryResponse, VisitorDailyTrendItem, VisitorDailyTrendResponse` 在 __all__ |

### 1.2 Frontend API Client

`frontend-vue3/src/api/audience.ts`:

```typescript
// Line 320-348
export interface VisitorSummary {
  visitor_count: number;
  total_visitors: number;
  conversion_rate: number;
  // ... 完整 schema
}

export interface VisitorDailyTrendItem { ... }
export interface VisitorDailyTrend { data: VisitorDailyTrendItem[] }

// Line 354-368
export function fetchVisitorSummary(params: {...}): Promise<VisitorSummary> {
  return client.get('/v1/visitor/summary', { params })
}

export function fetchVisitorDailyTrend(params: {...}): Promise<VisitorDailyTrend> {
  return client.get('/v1/visitor/daily-trend', { params })
}
```

### 1.3 Frontend 调用方

`frontend-vue3/src/views/AudienceView.vue`:

```typescript
// Line 11-12 (import)
import {
  fetchVisitorSummary,
  fetchVisitorDailyTrend,
  ...
}

// Line 194 (useQuery callback)
return fetchVisitorSummary({...});

// Line 208 (useQuery callback)
return fetchVisitorDailyTrend({...});
```

**结论**: AudienceView.vue 通过 useQuery 模式真在调 visitor API。**visitor chain 0 dead code, 100% 活跃**。

### 1.4 Router 注册状态 (缺)

`frontend-vue3/src/router/index.ts`:

```typescript
const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/audience' },
  { path: '/login', ... },
  { path: '/audience', ... },
  { path: '/category', ... },
  { path: '/category-detail/:categoryId', ... },
  { path: '/customer-health', ... },
  { path: '/churn', ... },
  { path: '/geo', ... },
  { path: '/market-focus', ... },
  { path: '/sampling', ... },
  { path: '/breakdown', ... },
]
```

**10/10 router-registered routes, 没有 /visitor** (Sprint 33.2 view smoke 10/10 没覆盖 /visitor 因为它没注册)。

---

## 2. Sprint 36-1 plan-eng-review 报告校正

Sprint 36-1 plan-eng-review 报告建议说:
> "Sprint 36-1 A 范围保留 backend flow ghost endpoint, 留 Sprint 36.x 单独评估. Sprint 36-6 ground-truth audit: /v1/flow/sankey 前端 0 + 后端 0 业务消费 + 0 test"

**Sankey 评估对**: backend + frontend 都 0 调用,sankey 是真 ghost。

Sprint 36-1 plan-eng-review 报告同时建议:
> "新增 visitor spec (route /visitor 0 spec 全空白) 不做: 业务风险高, 需先 ground-truth audit `backend/routers/visitor.py` + frontend 路由注册状态"

**Visitor 评估错**: "0 spec 全空白" 是真的(因为 router 没注册,spec 跟着没写),但"业务风险高" 是错的 — **visitor backend 100% 活跃**,不是 dead code。Sprint 36-1 plan-eng-review 没做 ground-truth audit,所以评估错。

**本次 Sprint 39.2 audit 校正**: visitor 链不是 dead code 待清,是 **活跃 backend + 活跃 frontend API client + 缺前端路由注册 + 缺独立页面**。

---

## 3. 激活路径 (产品决策)

要"激活 /visitor 路由",需要 3 步:

### 选项 A: 注册路由 + 写最小 VisitorView.vue (1 天)

1. `frontend-vue3/src/router/index.ts` 加 `/visitor` 路由
2. 新建 `frontend-vue3/src/views/VisitorView.vue` (复用 AudienceView.vue 的 visitor API 部分, ~100-200 行)
3. `frontend-vue3/src/api/menu.ts` 加 `/visitor` 侧边栏菜单项
4. 写 `frontend-vue3/e2e/visitor.spec.ts` (复用 Sprint 33.2 模式)
5. 后端 visitor API 已在用,不动 backend

**ROI**: 用户能直接从侧边栏进 visitor 页面,不用 AudienceView 间接消费。半天-1 天,跟 Sprint 33.2 style 一致。

### 选项 B: 不注册路由,AudienceView 继续间接消费 (0 改动)

保持现状。visitor API 继续被 AudienceView 用,但没独立页面。**0 工作量, 0 价值**。

### 选项 C: 把 visitor 功能合并到 AudienceView, 删独立路由 (1-2 小时)

1. `backend/routers/visitor.py` 删,合并到 audience.py
2. `backend/contracts/visitor.py` 删,合并到 audience contracts
3. frontend AudienceView 保留
4. router 不注册 /visitor

**ROI**: 减 106 行 backend code + 0 frontend 改动。但合并 audience + visitor = audience router 变胖,可能需要拆 audience module。1-2 小时。

---

## 4. Sprint 39.2 决策

**本次 Sprint 39.2 = 写本 audit doc (本文件)**,0 代码改动。激活路径是产品决策,留给 user 拍板。

实际 Sprint 39.2 待办 = user 拍板:
- A: 注册 /visitor + VisitorView (1 天)
- B: 维持现状 (0 改动)
- C: visitor 功能合并到 audience (1-2 小时)

**Cross-sprint 教训**:
- Sprint 36-1 plan-eng-review 没做 ground-truth audit,误判 visitor 是"业务风险高"
- Sprint 39.2 audit = "任何留尾决策必须先 ground-truth audit 再决策"
- 跨 sprint 复用本 audit doc 模式: Sprint 40+ 留尾决策先跑 grep + Read 实查

---

## 5. Export/Report Chain (Sprint 36-1 留尾 #4)

| 文件 | 行数 | 状态 | 证据 |
|---|---|---|---|
| `backend/services/export_service.py` | 446 | **活跃** (backend) | `generate_ppt_report` line 304 + `get_available_templates` line 42 |
| `backend/services/report_service.py` | 201 | **活跃** (backend) | `get_report_summary` line 15 |
| `backend/routers/export.py` | 39 | **活跃** | router 真注册 + 用 generate_ppt_report line 22 |
| `backend/routers/report.py` | 25 | **活跃** | router 真注册 + 用 get_report_summary line 15 |
| frontend export/report API client | 0 | **0 调用** | `grep fetchExport\|fetchReport` frontend-vue3/src/api/ → 0 命中 |

**结论**:
- backend 100% 活跃 (5 文件 711 行)
- frontend 0 调用 (没 import 任何 export_service / report_service 包装函数)
- 这是 **"backend 完整, frontend 缺 UI"** 模式,跟 visitor 现状一致

Sprint 36-1 plan-eng-review 报告说"清 -810 行" 是错的:
- 实际 backend 在用 export_service + report_service
- 不能清 backend
- 能清的"dead code" 是 frontend 0 调用 → 但 frontend 0 export/report 代码,0 行可清

**真决策**:
- A: 加 frontend UI 接 backend export/report API (产品决策,半天-1 天)
- B: 删 backend export/report (frontend 0 UI 永远不做 → backend 也清,破坏后端导出功能,但前端 0 影响,1 天)
- C: 维持现状 (backend 在用 frontend 不用, 跟 visitor 现状一致)

---

## 6. 总结 (Sprint 39.2 收口)

**事实校正**:
1. Visitor chain 不是 dead code,backend 100% 活跃 + frontend API 100% 活跃 + AudienceView 真在消费
2. Export/Report chain backend 100% 活跃, frontend 0 调用

**Sprint 39.2 收口**:
- ✅ 本 audit doc 完成 (事实校正 + 3 选项激活路径)
- ⏸ Sprint 39.3 候选: 3 选项中 user 拍板 (A 激活 /visitor 半天-1 天, 或 B 维持 0 改动, 或 C 合并到 audience 1-2 小时)
- ⏸ Sprint 39.4 候选: Export/Report 链产品决策 (A 加 frontend UI / B 删 backend / C 维持)

**Cross-sprint 教训**:
- **plan-eng-review 必须 ground-truth audit 先**,不能只看 commit message + sprint memory。Sprint 36-1 留尾"visitor 业务风险高"评估错,因为没真查 backend 代码。
- Sprint 39.2 留本 audit doc = 跨 sprint 引用 truth source,任何未来 sprint 决策 visitor/export/report 都先读本文件。

---

## 关联 Memory / 文件

- `backend/routers/visitor.py` (58 行, 活跃)
- `backend/contracts/visitor.py` (48 行, 活跃)
- `frontend-vue3/src/api/audience.ts:320-368` (Visitor API client)
- `frontend-vue3/src/views/AudienceView.vue:11-12, 194, 208` (visitor API 真消费)
- `backend/services/export_service.py` (446 行, backend 活跃)
- `backend/services/report_service.py` (201 行, backend 活跃)
- Sprint 33.2 view smoke 留尾 (10/10 router-registered, 没 /visitor)
- Sprint 36-1 plan-eng-review 报告 (误判 "visitor 业务风险高",本次 audit 校正)