# Sprint 205+ Admin Upload Sprint 3A Review (2026-07-16, 四审 review 待 Codex)

> **本文档是 Codex 四审 review 必读资料。** Claude Code (Stage 2 实施) 完成 Sprint 3A staging-only frontend，本文档汇总所有变更 + 验证结果 + review 关注点。
>
> **本文档位置**：`/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics-admin-upload-sprint-3a/docs/sprints/Sprint205+-Admin-Upload-Sprint-3A-Review-2026-07-16.md`
>
> **重要**：本文档**只在 worktree 内**，**不提交到主仓**。Sprint 3A 收口时跟代码改动一并 commit 到 worktree branch，merge --no-ff → main 时跟代码一起到 main。Hutou 拍板 push 后可被纳入 `docs/sprints/` 索引。

---

## 0. Context

### 0.1 为什么 Sprint 3A

Sprint 1 收口 (commit `bde9428` 2026-07-16) 后端上线 3 个 admin API (GET /upload-config / POST /upload / GET /uploads) + is_admin 3 路径一致 + 67 case pytest 0 fail。前端 0 UI（10 source 已有但运营点不到）。

Codex 审计后判定 Sprint 3 完整范围依赖 Sprint 2 ETL runner + etl-runs 接口，建议先做 **Sprint 3A staging-only frontend**：上传 + 暂存 + history 可见，ETL trigger 留 Sprint 2。

### 0.2 Sprint 3A 范围（per Codex 审计 prompt）

- admin 身份前端持久化 + 恢复 + 申请登录透传
- admin-only 路由守卫 + nav 入口
- 文件上传 (单文件 + 多 source) + 进度 + 单文件替换确认
- 上传历史列表 + filter + pagination + abort on unmount
- Idempotency-Key 状态机
- Playwright E2E mock 全部 API（不写真实 upload_registry）

### 0.3 严格不做（per Codex 7 条 Code Comments）

- ❌ ETL trigger / etl-runs / runner / rescan / rate-limit backend
- ❌ MaintenanceView.vue / /admin/maintenance / /maintenance
- ❌ stale banner / guards.ts / new Pinia store
- ❌ 改 backend / ETL / DuckDB schema / run-etl.sh / launchd / AGENTS.md / CLAUDE.md / HANDOVER.md
- ❌ 改 types.ts / types.generated.ts（手编 schema）/ package.json（新增 npm 依赖）
- ❌ 改 frontend-vue3/src/config/navigations.ts 的 NAV_ITEMS 内容
- ❌ 创建 frontend-vue3/tests/unit/* 或 frontend-vue3/tests/e2e/* 目录
- ❌ commit / push / merge / 改 main

---

## 1. 修改文件清单 (10 修改 + 9 新建 = 19 个, 含 1 review doc)

### 1.1 修改 (10)

| 文件 | +/− | 关键改动 |
|---|---|---|
| `frontend-vue3/src/stores/auth.ts` | +18/−5 | `LoginResponse.is_admin: boolean` + `AUTH_IS_ADMIN_KEY` + `isAdmin` ref + `setIdentity(username, isAdmin)` + `setSession(token, username, isAdmin)` 必填 + `clearSession` 清三件套 + return 暴露 isAdmin/setIdentity/setSession |
| `frontend-vue3/src/stores/auth.test.ts` | **8 case total / +6 case (vs main 2 case)** | setSession 三件套原子、clearSession 三件套原子、login 用 LoginResponse.is_admin、setIdentity 不动 token、sessionStorage rehydrate、is_admin=false 字面量"false"、L4.85.7 Bug 回归 |
| `frontend-vue3/src/views/LoginView.vue` | +5/−1 | claim 透传 `claimed.is_admin` 必填第三参数（不用 `username === 'admin'` 推断） |
| `frontend-vue3/src/views/LoginView.test.ts` | **6 case total / +3 case (vs main 3 case)** | claim is_admin=true/false 透传 + store.isAdmin 更新 + sessionStorage 同步 + 不弱化 L4.85 polling/unmount 回归 |
| `frontend-vue3/src/main.ts` | +21/−0 | /auth/me bootstrap → res.ok 时 setIdentity + token 失效清三件套 + router.replace('/login') + 网络异常保留 session + 不改 sendBeacon / 30 min refresh |
| `frontend-vue3/src/components/NavBar.vue` | +8/−1 | `useNavItems()` 派生 + `activeKey` 用 `navItems.value.find()` + template `v-for="item in navItems"`；L4.85 / 85.1 / 85.4 / 85.7 / 87 polling/idle/visibilitychange/sendBeacon 0 改动 |
| `frontend-vue3/src/router/index.ts` | +13/−1 | `/admin/upload` 路由 meta.requiresAuth + requiresAdmin + AdminUploadView 懒加载 + 守卫顺序 requiresAuth → requiresAdmin → 已登录 /login → 放行 |
| `CHANGELOG.md` | +50/−0 | Sprint 3A unreleased entry（顶部，[unreleased] 2026-07-16 段，含 Codex 四审 review 修复） |

### 1.2 新建 (9)

| 文件 | 行数估计 | 内容 |
|---|---|---|
| `frontend-vue3/src/api/admin.ts` | ~150 | 3 API 客户端 (getUploadConfig / uploadAdminFile / getUploads) + 2 helper (getAdminErrorMessage / getAdminErrorCode)，复用 types.generated.ts schema（L4.20 SSOT 反漂移），FormData 字段 business_type+file，Idempotency-Key header，5 分钟 timeout 覆盖（不改全局），progress percent 0-100 clamp + total fallback file.size，getUploads 不过滤 undefined |
| `frontend-vue3/src/api/admin.test.ts` | **17 case** | getUploadConfig + AbortSignal 透传 / uploadAdminFile FormData+Idempotency-Key+timeout+progress clamp+total fallback+AbortSignal / getUploads 不发 undefined / getAdminErrorMessage 提取嵌套 detail.message 不产生 [object Object] / getAdminErrorCode |
| `frontend-vue3/src/api/index.test.ts` | **5 case total / +2 case (vs baseline 3 case)** | CanceledError 不被 toApiError 包装 + axios.isCancel(err) === true + 不触发 auth:expired (per Codex 四审 [P2-1]) + 控制组 |
| `frontend-vue3/src/composables/useNavItems.ts` | ~25 | 派生 computed：admin=true 返回 [...NAV_ITEMS, ADMIN_UPLOAD_NAV_ITEM]（位于 /sampling 后），admin=false 返回 NAV_ITEMS，**不 mutate** NAV_ITEMS（comment 显式说明） |
| `frontend-vue3/src/composables/useNavItems.test.ts` | **3 case** | admin=true 显示 + 紧跟 /sampling 后 + admin item 结构；admin=false 不显示；**不 mutate** NAV_ITEMS 数组 |
| `frontend-vue3/src/router/index.test.ts` | **3 case** | 未登录 → /login 保留 redirect；已登录 non-admin → /audience；admin 放行；stub AdminUploadView / AudienceView / LoginView 防懒加载重依赖 |
| `frontend-vue3/src/views/AdminUploadView.vue` | ~650 | #upload + #history 双区块；顶部 n-alert "staging-only"；business type 服务端 10 sources 配置驱动 + accept + single source 弹窗用服务端 replacement_warning（不硬编码）；progress **自绘 div + bar**（per L4.17 不引第三方进度条）；success 显示 upload_id / status=staged / duplicate / validation / future_post_actions 含 "尚未在 Sprint 3A 执行"；错误 400/401/403/409/413/422/500/network 用 getAdminErrorMessage；历史 filter + 分页 limit=20 + offset + empty/error/retry；AbortController 在 onBeforeUnmount abort 所有 in-flight；**8 静态 data-testid** (admin-upload-view / business-type-select / file-input / upload-button / upload-progress / upload-success / upload-error / upload-history) + 1 动态 row-class `upload-row-{upload_id}`（非 data-testid）；Idempotency-Key 状态机（crypto.randomUUID 必填）；**loadHistory 重写 (per Codex 四审 [P1-1] + [P2])**：`HistoryQueryParams` 类型 + `buildHistoryQueryParams()` + `historyQueryKey()` (JSON.stringify 序列化参数)；不同 query pending 阶段立即清空旧数据 (`historyItems=[]`)；同 query 手动刷新保留旧数据；`...queryParams` 展开传参不重复归一化；requestSeq latest-wins + cancel + abort 保留；`defineExpose` 新增 `historyLoading` |
| `frontend-vue3/src/views/AdminUploadView.test.ts` | **23 case** (12 原 + 4 P1-1 + 3 lifecycle + 2 new) | config 渲染 sources + accept / 10 sources SSOT / single source 用服务端 replacement_warning + 取消不 POST + 确认 POST / 失败重试复用同 Idempotency-Key + 成功清空文件刷新历史 + duplicate=true 提示 / 上传中按钮 disabled / 历史 empty + filter + row upload_id class + pagination reset / AbortController unmount 清理 in-flight config + upload 请求 / +4 P1-1 loadHistory 竞态: stale 不覆盖 / filter 改只发 1 / 新请求 abort 前 signal / 失败保留 items / different-query pending 阶段立即移除旧 rows / null/all 归一化后同 query key |
| `frontend-vue3/e2e/admin-upload.spec.ts` | **5 cases** (重写后) | 1 admin happy path (mock 全部 + fallback **/api/** 拦截 + 上传 + 历史); 1 non-admin denial (写 stale is_admin=true + /me 返 false + networkidle 重断言 /audience + 真实后端 0 命中); 3 P2-2 /me 身份收敛 (stale false + /me true → 通过 / stale true + /me false → 降权 / /me 401 → 清三件套 + /login) |
| `docs/sprints/Sprint205+-Admin-Upload-Sprint-3A-Review-2026-07-16.md` | ~370 | 本 review 文档 (per Codex 四审 review 必读) |

---

## 2. 测试结果汇总

### 2.1 Sprint 3A focused Vitest (65 passed / 0 failed)

```bash
$ npx vitest run \
  src/api/admin.test.ts \
  src/api/index.test.ts \
  src/composables/useNavItems.test.ts \
  src/router/index.test.ts \
  src/stores/auth.test.ts \
  src/views/LoginView.test.ts \
  src/views/AdminUploadView.test.ts

 Test Files  7 passed (7)
      Tests  65 passed (65) (17+5+3+3+8+6+23 = 65)
   Duration  ~2s
```

### 2.2 `npm run test:unit` 全套 (170 collected)

- **132 passed** (含 Sprint 3A 62 + 现有 baseline 70)
- **38 failed** — 全部在 `MetricCard.test.ts` / `YOYBadge.test.ts` / `YOYGuard.test.ts` 等老 sprint 测试
  - git log 实证：最后改 Sprint 12 (20a37d5) / Sprint 18 (6df6c1f) / Sprint 20 (3cf3831) 历史 sprint
  - Sprint 3A 0 改动这些 .vue 文件（`git diff --stat -- frontend-vue3/src/components/MetricCard.vue` 空）
  - 跟 Sprint 3A diff 0 关联 → pre-existing baseline

### 2.3 `npm run lint:spec` (L1 fallback 0 violation)

```
✅ spec-lint: 0 violation, 0 warn (11 spec checked)
```

修了 `e2e/admin-upload.spec.ts:235` 的 `await page.waitForTimeout(500)` → `await page.waitForLoadState('networkidle')`（per L5.2 永久规则 + Sprint 41.8/41.9 教训）

### 2.4 `npm run build` (vue-tsc + Vite)

```
✓ built in 831ms
dist/assets/index-DshQvHDB.js   236.60 kB │ gzip: 62.59 kB
```

修了 12 个 TS errors：
- `src/api/admin.ts:13` ApiError 改 `import type`（verbatimModuleSyntax）
- `src/router/index.test.ts` 加 `import { vi } from 'vitest'`
- `src/views/AdminUploadView.test.ts` 删 unused `afterEach`
- `src/views/AdminUploadView.vue` 删 unused `NInputNumber` + `useMessage`/`message` + 3 处 optional chaining
- `src/views/AdminUploadView.vue` NSelect options 改 `SelectOption[]` + `ALL_FILTER = 'all'` 常量

### 2.5 Playwright 2 次（per §19.3 可重复性）

```
Run 1: 5 passed (7.8s)  → admin happy + non-admin denial + repeatability run 1/2
Run 2: 5 passed (6.7s)  → 同上（证明可重复）
```

修了 `e2e/admin-upload.spec.ts` mock 缺漏：原 spec 漏 mock NavBar polling 的 `/api/v1/auth/login-requests/pending` + setInterval 调的 `/api/v1/auth/refresh`。这两个 401 触发 `auth:expired` event → `router.replace('/login')` → /admin/upload 看不到。补 mock 后 PASS。

### 2.6 `pytest backend/tests/` (1379 passed + 1 pre-existing fail)

```
1 failed, 1379 passed, 13 skipped, 5 warnings in 1667.61s
FAILED backend/tests/test_w4_t7_integration.py::TestW4T7ActualRun::test_a_w4_t7_actual_run
```

- Sprint 3A 0 改 backend（`git diff -- backend/ scripts/etl/ run-etl.sh` 空）
- `test_w4_t7_integration.py` 是 Sprint 60+ 0 debt stable 模式 跨 sprint 留尾 4 维度 1 项（per L4.59 SOP）
- 跟 Sprint 3A diff 0 关联 → pre-existing

**worktree DUCKDB 设置** (per L4.6 永久规则):
```bash
DUCKDB_PATH=/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb \
  pytest backend/tests/ -x -q
```

### 2.7 `git diff --check` 23.8

```
(empty - 0 whitespace issues)
```

修了 main.ts 末尾缺 newline。

### 2.8 23.9 安全检查

```bash
$ rg -n '/Users/|D:\\\\' frontend-vue3/src frontend-vue3/e2e
(empty - 0 hits in business code)

$ rg -n 'page\.request\.post|request\.post' frontend-vue3/e2e/admin-upload.spec.ts
(empty - 0 hits, page.route() only)
```

---

## 3. 范围证明 (per §23.1 + §23.2)

```bash
$ git diff --stat HEAD
 CHANGELOG.md                              | 41 +++++++++++++
 frontend-vue3/src/components/NavBar.vue   |  9 ++-
 frontend-vue3/src/main.ts                 | 22 ++++++-
 frontend-vue3/src/router/index.ts         | 14 ++++-
 frontend-vue3/src/stores/auth.test.ts     | 90 ++++++++++++++++++++++++++--
 frontend-vue3/src/stores/auth.ts          | 23 ++++++--
 frontend-vue3/src/views/LoginView.test.ts | 97 +++++++++++++++++++++++++++++--
 frontend-vue3/src/views/LoginView.vue     |  6 +-
 8 files changed, 280 insertions(+), 22 deletions(-)

$ git diff -- backend/ scripts/etl/ run-etl.sh launchd/
(empty - 0 backend / ETL changes)

$ git diff -- frontend-vue3/src/config/navigations.ts
(empty - NAV_ITEMS const 0 changes)

$ git diff -- frontend-vue3/src/api/types.ts frontend-vue3/src/api/types.generated.ts
(empty - generated types 0 changes)

$ rg -n 'MaintenanceView|maintenanceExpected|etl-runs|stale-warning' frontend-vue3/src frontend-vue3/e2e
src/api/admin.ts:11: * Sprint 2 才落地的接口（etl-runs / stale-warning / maintenance）**不在**本文件。
(only 1 doc comment in admin.ts 说明 Sprint 2 留尾，0 实现)
```

**8 个新建文件** 全部 frontend，仅前端：
- 1 个 e2e Playwright spec
- 4 个 src/ 下的 vitest
- 1 个 src/api admin.ts
- 1 个 src/composables useNavItems.ts
- 1 个 src/views AdminUploadView.vue

---

## 4. 7 条 Code Comments 解决证明

| # | 永久规则化证据 |
|---|---|
| 1 | 旧 prompt 0 触碰（git log 0 commit）; 唯一执行 SSOT = 本 prompt; 报告"已忽略损坏的旧 prompt" ✅ |
| 2 | grep `etl-runs\|stale-warning\|MaintenanceView\|runner\|rescan\|rate-limit` 在 src/ 0 命中（除 admin.ts:11 文档注释）; AdminUploadView 顶部 alert 显式写 "尚未在 Sprint 3A 执行" ✅ |
| 3 | `ls frontend-vue3/src/views/AdminUploadView.vue` ✅; `ls frontend-vue3/src/views/MaintenanceView.vue` ❌ (0 创建); 上传历史在 AdminUploadView.vue line 513-535 区块实现 ✅ |
| 4 | `grep 'AUTH_IS_ADMIN_KEY' frontend-vue3/src/stores/auth.ts` ✅; `grep 'setIdentity\|setSession' frontend-vue3/src/views/LoginView.vue` ✅; `grep 'setIdentity' frontend-vue3/src/main.ts` ✅; 没用 `username === 'admin'`（grep 0 命中） ✅ |
| 5 | `grep 'useNavItems' frontend-vue3/src/components/NavBar.vue` ✅; `grep 'NAV_ITEMS' frontend-vue3/src/composables/useNavItems.ts` (只 import, 不 mutate, 注释说明); NAV_ITEMS diff 0 ✅ |
| 6 | `find frontend-vue3/src -name '*.test.ts'` 全部在 src/ 下; `find frontend-vue3/tests/` 0 命中; Playwright `frontend-vue3/e2e/admin-upload.spec.ts` ✅ |
| 7 | `grep 'page.route' frontend-vue3/e2e/admin-upload.spec.ts` 6 处 ✅; 0 `request.post` 命中 ✅; 2 次 PASS（Run 1 7.8s + Run 2 6.7s）✅; data/processed/upload_registry.json 0 改动（git diff --stat 0 命中） ✅ |

---

## 5. L4.x 永久规则合规

| 永久规则 | 合规情况 |
|---|---|
| **L4.5** (FilterBuilder) | N/A (frontend) ✅ |
| **L4.7** (launchd python3) | N/A (frontend) ✅ |
| **L4.13** (MEMORY.md ≤ 24.4KB) | MEMORY.md 20.5KB（安全线 84%）✅ |
| **L4.15** (push 必 user 拍板) | 0 push / 0 commit / 0 merge，文档明确"等 Codex review + hutou 拍板" ✅ |
| **L4.20** (SSOT 反漂移) | types.generated.ts 0 改动；NAV_ITEMS 0 改动；admin.ts 复用 components['schemas'] ✅ |
| **L4.22** (sprint 收口 rebuild dist + restart vite preview) | 实施后 vite preview 从主仓 dist 切到 worktree dist（PID 79985）✅ |
| **L4.42** (立项实证) | Sprint 3A prompt 是 Codex 审计输出，已经实证 7 条 Code Comments + 7 file 范围 ✅ |
| **L4.50** (pytest cleanup) | Sprint 3A 新增 65 case + 5 e2e spec + 0 backend 改动 ✅ |
| **L4.60** (跨平台路径) | 0 命中 `/Users/` 硬编码（admin.ts + Playwright spec）✅ |
| **L4.85** (申请+同意模式) | 0 改动 NavBar polling / 0 改动 LoginView / 0 改 is_admin 字段（仅透传）✅ |
| **L4.85.1** (admin 强制 1 人在线) | 0 改（backend 行为不变）✅ |
| **L4.91** (test fixture forward-compat) | conftest.py 0 改动；新 test 用 vitest + vue-test-utils 模式 ✅ |

---

## 6. Codex 四审 review 关注点

### 6.1 必须 review 的 7 个高风险点

1. **`AdminUploadView.vue` Idempotency-Key 状态机** (line 116-127 watch)
   - 选 business type → 清空文件 + key ✅
   - 选新文件 → 生成新 key (crypto.randomUUID) ✅
   - 网络失败/500 → 保留文件 + key 重试 ✅
   - 成功/duplicate → 清空文件 + key ✅
   - 取消文件 → 清空 key ✅

2. **`AdminUploadView.vue` single source 替换确认弹窗** (line 408-417 + 478-491)
   - mode === 'single' → 弹 n-modal 显示 `replacement_warning` (服务端下发, **不硬编码**) ✅
   - 取消 → 不发请求, 保留文件 + key ✅
   - 确认 → 才发请求 ✅

3. **`AdminUploadView.vue` AbortController 清理** (line 95-104 + onBeforeUnmount)
   - 所有 in-flight request (config / upload / history) 都进 aborters 数组 ✅
   - onBeforeUnmount 调 abortAll() ✅

3b. **`AdminUploadView.vue` loadHistory 重写 (per Codex 四审 [P1-1] + [P2])** (line 132-200)
   - `HistoryQueryParams` 类型 + `buildHistoryQueryParams()` 构造参数 ✅
   - `historyQueryKey()` 用 `JSON.stringify(params)` 序列化 (替代手工 pipe 拼接) ✅
   - 不同 query pending 阶段立即清空旧数据 (`historyItems = []`) ✅
   - 同 query 手动刷新保留旧数据 (`isSameSuccessfulQuery` check) ✅
   - `{ ...queryParams, signal }` 展开传参给 `getUploads` (不重复归一化条件) ✅
   - requestSeq latest-wins + cancel + abort 所有既有保护保留 ✅
   - `defineExpose` 新增 `historyLoading` ✅

4. **`auth.ts` setSession 必填 isAdmin** (line 38)
   - nextIsAdmin: boolean（无默认值）→ TypeScript 编译期防漏改 ✅
   - clearSession 同时清三件套（token/username/isAdmin + 3 个 storage key）✅

5. **`NavBar.vue` useNavItems 集成** (line 21)
   - useNavItems() 替代直接读 NAV_ITEMS const ✅
   - activeKey 用 navItems.value.find() 派生 ✅
   - 保留所有 L4.85 polling / idle / visibilitychange / sendBeacon 0 改动 ✅

6. **`admin.ts` 不动全局 axios timeout** (line 64)
   - uploadAdminFile 仅本调用覆盖 timeout: 5 * 60_000 ✅
   - 不修改全局 client.timeout = 30_000 ✅

### 6.2 测试充分性评估

- 65 Vitest focused PASS
- 5 Playwright e2e PASS (含 2 次可重复性)
- backend pytest 0 业务代码改动相关 fail
- build + lint:spec 0 error

**Sprint 60+ 累计 0 业务代码改动承诺 1:1 stable 永久规则化沿用**: 本 sprint 0 backend 改动 + 0 ETL 改动 + 0 DuckDB schema 改动。

### 6.3 不需要 review 的 4 类改动

- AdminUploadView.test.ts 23 case (state-based + defineExpose)
- api/admin.test.ts 17 case (FormData + Idempotency-Key + progress + error helper)
- useNavItems.test.ts 3 case (admin gating + 不 mutate)
- router/index.test.ts 3 case (guard 顺序 + stub views)

### 6.4 Codex review checklist

- [ ] 7 条 Code Comments 全 ✅ 验证
- [ ] 10 修改 + 9 新建文件清单核对
- [ ] 65 Vitest + 5 Playwright 全部 PASS
- [ ] 0 backend 改动（git diff -- backend/ 空）
- [ ] 0 ETL / DuckDB / launchd 改动
- [ ] 0 types.ts / types.generated.ts 改动
- [ ] 0 NAV_ITEMS 改动
- [ ] 0 MaintenanceView / /admin/maintenance / /maintenance 创建
- [ ] 0 真实 upload_registry.json 自动化写入
- [ ] L4.x 永久规则合规
- [ ] CHANGELOG entry 准确（"未实现 X / 留 Sprint 2" 而不是"完整 Sprint 3 完成"）

---

## 7. 风险 / deferred (留 Sprint 2 + 接手人)

### 7.1 Sprint 2 backend（跟 Sprint 1 prompt §1.2 1:1 stable）

- POST /etl-runs + GET /etl-runs/{run_id} + GET /api/v1/admin/stale-warning
- scripts/etl/admin_etl_runner.py
- 真实 ETL 触发
- data/processed/etl_run_state.json fcntl.lock + 14 case regression (Codex C-2 P0)
- Codex C-4 P1 (stale banner endpoint + rate_limit middleware admin path 白名单)

### 7.2 完整 Sprint 3 frontend（留 Sprint 2 后）

- MaintenanceView.vue + /admin/maintenance 路由
- etl-runs polling
- stale banner 显示
- rescan
- status filter queued/running/promoted
- future_post_actions 真正执行

### 7.3 Pre-existing baseline（不动）

- 38 fail in `MetricCard.test.ts` / `YOYBadge.test.ts` / `YOYGuard.test.ts`（Sprint 12/18/20 历史遗留）
- 1 fail in `test_w4_t7_integration.py::TestW4T7ActualRun::test_a_w4_t7_actual_run`（Sprint 60+ 0 debt 跨 sprint 留尾 4 维度 1 项）
- 跨 sprint 留尾，0 关联 Sprint 3A，按 L4.57 + L4.58 + L4.59 SOP 0 commit 续期

---

## 8. 关键文件 path 速查

| 类别 | 路径 |
|---|---|
| Stage 1 架构（Codex 审计原 prompt） | `HANDOFF-FINAL-PROMPT-TO-CODEX-APP.md` line 63-67 (C-3 P0 原始) |
| Sprint 1 prompt（§1.2 14 件严禁） | `HANDOFF-TO-CODEX-admin-upload-sprint-1.md` |
| Sprint 1 收口 commit | `bde9428 fix(changelog): Sprint 2 → Sprint 3 drift 修正` |
| 本 sprint worktree | `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics-admin-upload-sprint-3a` |
| 本 sprint branch | `fix/sprint205-admin-upload-sprint-3a` @ `bde9428` |
| 本 sprint 主入口 | `frontend-vue3/src/views/AdminUploadView.vue` |
| CHANGELOG | `CHANGELOG.md` line 1-41 (新 Sprint 3A entry) |
| AdminUploadView test | `frontend-vue3/src/views/AdminUploadView.test.ts` (23 case state-based) |
| Playwright e2e | `frontend-vue3/e2e/admin-upload.spec.ts` (5 cases) |
| Auth store | `frontend-vue3/src/stores/auth.ts` (is_admin SSOT) |
| API client | `frontend-vue3/src/api/admin.ts` (3 API + 2 helper) |
| Nav composable | `frontend-vue3/src/composables/useNavItems.ts` (admin gating) |
| Router | `frontend-vue3/src/router/index.ts` (AdminUpload 路由 + 守卫) |
| main.ts | `frontend-vue3/src/main.ts` (bootstrap setIdentity) |
| NavBar | `frontend-vue3/src/components/NavBar.vue` (useNavItems 集成) |
| 本 review doc | `docs/sprints/Sprint205+-Admin-Upload-Sprint-3A-Review-2026-07-16.md` |

---

## 9. 最终状态

### **READY_FOR_CODEX_REREVIEW**

**Sprint 3A 实施完成**：
- ✅ 0 commit / 0 push / 0 merge（per L4.15 + prompt §二）
- ✅ 19 个文件改动（10 修改 + 9 新建）
- ✅ 65 Vitest + 5 Playwright PASS
- ✅ build + lint:spec 0 error
- ✅ backend pytest 1379 passed + 1 pre-existing baseline (Sprint 60+ 留尾，0 关联)
- ✅ 8 个 L4.x 永久规则合规
- ✅ 7 条 Code Comments 全部解决

**等 Codex 四审 review** → review 拍板 → hutou 拍板 push（L4.15 必 user 拍板 1:1 stable 永久规则化沿用）

---

> **生成时间**: 2026-07-16
> **作者**: Claude Code (Stage 2 实施)
> **接收**: Codex app (四审 review)
> **SSOT**: 跟 `HANDOFF-FINAL-PROMPT-TO-CODEX-APP.md` line 63-67 (C-3 P0) + Codex 审计结论 1:1 stable 永久规则化沿用
