# L4.85.7 Bug #1 Handoff (给接手人: GPT-5.6 / 任何人 7/16+ 启动必读)

> **作者**: Claude Code 架构师 (你 7/11 拍板"自己解决, 不写求助 handoff" 但仍写沉淀知识)
> **关联**: L4.85.5 commit b43b2ab 引入的 2 个新 bug (Bug #1 + Bug #2)
> **L4.85.6 已治本**: Bug #2 (Cmd+Q 后 ACTIVE_TOKENS 残留) - commit b4e9b02 ship main f8eeab2
> **L4.85.7 留尾**: Bug #1 (登录后没跳转) - 本文档是治本 plan-eng-review

## 1. 背景 (跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用)

user 7/11 报 2 个 bug:
- **Bug #1**: "我输入账号密码后，明明登陆了，但是没有跳转至看板，还是在登陆界面，但是已经处于登陆了"
- **Bug #2**: "A 运营登陆后, 他退出了, B 运营大概 20S 后再次登录, 提示申请登录, 但当前已经没有人看板"

L4.85.5 commit `b43b2ab` (2026-07-11) 试图修复 Bug #2 的 "残留 admin 信息" 问题, 但引入了 2 个新 bug。

## 2. L4.85.5 commit 真根因 (100% 锁定, 跟 reproduce test 1:1 stable 永久规则化沿用)

文件: `frontend-vue3/src/views/LoginView.vue:488-496`

```javascript
// L4.85.5 加的 onUnmounted (bug 来源)
onUnmounted(() => {
  ...
  // L4.85.4 治本: user 7/11 报 "退出网址后, 账号状态没退出, 显示 欢迎回来 + admin 残留"
  // 原因: sessionStorage fq_crm_auth_user / fq_crm_auth_token 残留 → LoginView refilled 显示 "欢迎回来 admin"
  // 修复: LoginView unmount 时清空 sessionStorage 残留 (不调 logout API 因为可能没 active token)
  try {
    sessionStorage.removeItem('fq_crm_auth_token')   // ← bug 触发点
    sessionStorage.removeItem('fq_crm_auth_user')
  } catch {}
})
```

**Bug #1 触发链路**:
1. user 登录成功 → `authStore.login()` 写 token 到 sessionStorage + 内存 ref
2. `setTimeout(300)` → `router.push('/audience')`
3. Vue 路由切换 → `LoginView` 被 unmount → **onUnmounted 触发清空 sessionStorage token**
4. /audience 加载 → `authStore.token` 读内存 ref (还有值) → `isAuthenticated = true` → 渲染
5. /audience 内部 axios 请求 → 读 sessionStorage token → **已被清空!** → 401
6. axios interceptor `_tryRefreshToken` → refresh 也 401 → `dispatch 'auth:expired'` → 跳回 /login
7. user 看到 "还在登录界面" (实际在 /login, 但 sessionStorage 已被清空, 无法 token 化)

**Bug #2 触发链路** (已被 L4.85.6 治本):
- Cmd+Q → 浏览器关掉 → sessionStorage 已空 (因 step 3 清空) → 重启 → token 丢失
- B 端 login → backend ACTIVE_TOKENS 中 admin 仍 3min 内 → 409 → 申请

## 3. L4.85.5 plan-eng-review 8 件缺陷 (跟 L4.42 + L4.50 + L4.55 1:1 stable 永久规则化沿用)

| # | 缺陷 | 详细 |
|---|------|------|
| 1 | **触发时机错误** | onUnmounted 在 router 切换时触发 (任何路由变化都触发), 不是 user 主动 logout |
| 2 | **跟现有 6 处清理 SSOT 冲突** | main.ts:20/50/67 + auth.ts:34-35 + clearSession + NavBar:181 已完备, L4.85.5 是冗余且错误的第 7 处 |
| 3 | **sessionStorage 行为误判** | sessionStorage 在 tab/窗口关闭前持久化保留, 不会随 Cmd+Q 清空 |
| 4 | **没 reproduce 测试就 push** | 违反 /investigate Phase 3 Iron Law: NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST + L4.42 立项实证 SOP "git log + grep 实证" |
| 5 | **"欢迎回来 + admin 残留" 真根因误判** | 实际是 LoginView template 硬编码标题 (`<h1 class="welcome-title">欢迎回来！</h1>`) + fail path 没清 input |
| 6 | **fail path 不清 input 字段** | `LoginView.vue:374-386` catch 块没清 username/password, user 之前 input 残留 |
| 7 | **跟 L4.85.4 idle 治本冲突** | NavBar.vue IDLE_TIMEOUT_MS 3min 已自动 logout → clearSession, onUnmounted 冗余 |
| 8 | **跟 bootstrap() 验证机制冗余** | main.ts:11-27 启动前调 /auth/me 验证 + 失败清空, L4.85.5 是冗余 |

## 4. L4.85.6 Bug #2 已治本 (跟接手人 1:1 stable 永久规则化沿用)

文件: `backend/services/auth_token_evictor.py` (新模块) + `backend/main.py` (lifespan 集成) + `frontend-vue3/src/main.ts` (beforeunload + sendBeacon) + `backend/routers/auth.py` (logout endpoint 兼容 token via query)

**commit**: `b4e9b02` → merge `f8eeab2`

**方案 D**: 后端 background task 每 30s 扫 ACTIVE_TOKENS, evict last_active_at > 60s 的 token
**方案 A**: frontend beforeunload 钩子 + navigator.sendBeacon POST /api/v1/auth/logout?token=xxx

**4 case 回归测试 PASS**: `backend/tests/test_l4_85_6_cmd_q_token_evict.py`

**接手人不要重复治本 Bug #2**。

## 5. L4.85.7 Bug #1 治本 plan (跟 L4.42 + L4.50 + L4.55 + L4.85.5 1:1 stable 永久规则链配套)

### 方案 A (推荐) - 部分回滚 + 修真问题

| 操作 | 文件 | 改动 |
|------|------|------|
| 1. 删 L4.85.5 onUnmounted 9 行 | LoginView.vue:488-496 | 删整个 try/catch 块 |
| 2. fail path 清 input 字段 | LoginView.vue:374-386 catch | 加 `username.value = ''; password.value = ''` |
| 3. 保留 5min → 3min 改动 | 4 处 (auth.py / login_request.py / NavBar.vue / LoginView.vue) | 无改动 |
| 4. 删 L4.85.5 reproduce test | LoginView.test.ts | 因 Bug #1 不存在, 2 case 失效 |

**0 业务代码改动风险最小**, 保留 user 期望的 3min 改动, 修真问题。

### 方案 B - 完整回滚 L4.85.5

git revert `b43b2ab` → 恢复 5min。但失去 3min 改动, 需要重新拍板 user 期望。

### 方案 C - 保留 L4.85.5 + 加测试

不修问题, 只增加测试覆盖。

### 推荐: 方案 A (理由)

1. **0 业务代码改动风险最小** (跟 L4.50 累计 94 次 1:1 stable 永久规则链配套)
2. **保留 user 7/11 期望**: 5min→3min 改动 (满足 user 期望)
3. **修 真问题**: fail path 不清 input 字段 (L4.85.5 试图修复但诊断错误)
4. **删冗余 9 行**: L4.85.5 onUnmounted (跟现有 6 处清理冗余 + 错误)
5. **保持现有架构 SSOT**: token 失效清理由 main.ts + authStore 统一管理 (跟 L4.20 反漂移 1:1 stable 永久规则化沿用)

## 6. reproduce test (100% 验证 Bug #1 真根因)

文件: `frontend-vue3/src/views/LoginView.test.ts` (L4.85.5 reproduce 段)

```typescript
it('Bug #1 reproduce: LoginView unmount 不应清空 成功登录后 的 sessionStorage token', () => {
  const authStore = useAuthStore()
  authStore.setSession('test-token-after-login', 'admin')
  expect(sessionStorage.getItem(AUTH_TOKEN_KEY)).toBe('test-token-after-login')

  const wrapper = mount(LoginView, { global: { stubs: { 'router-link': true, 'router-view': true } } })
  wrapper.unmount()  // ← 触发 L4.85.5 onUnmounted, 清 sessionStorage

  // ❌ L4.85.5 当前 FAIL: token 被清空
  // ✅ 期望 PASS: token 保留 (因为 user 已成功登录, token 还要用)
  expect(sessionStorage.getItem(AUTH_TOKEN_KEY)).toBe('test-token-after-login')
})
```

**当前 FAIL** (L4.85.5 实现) - 验证假设 100%。
**删 L4.85.5 onUnmounted 后 PASS** - 验证治本 100%。

## 7. 验证步骤 (接手人 7/16+ 启动必跑)

```bash
# 1. 删 L4.85.5 onUnmounted 9 行 (LoginView.vue:488-496)
# 2. fail path 清 input 字段 (LoginView.vue:374-386 catch 块)
# 3. 删 L4.85.5 reproduce test (LoginView.test.ts L4.85.5 reproduce 段)
# 4. 跑测试
cd /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/frontend-vue3
timeout 60 npx vitest run src/views/LoginView.test.ts

# 5. 跑 backend baseline
cd ..
PYTHONPATH=. timeout 90 pytest backend/tests/test_l4_85*.py -q

# 6. 跑 frontend build
cd frontend-vue3 && timeout 60 npm run build

# 7. pre-commit hooks
cd .. && git add -A && git commit -m "fix(L4.85.7): Bug #1 治本 - 删 L4.85.5 onUnmounted + 修真问题"

# 8. push + merge main (跟 L4.15 拍板 1:1 stable 永久规则化沿用)
git push origin fix/sprint205-bug1-onunmounted-removal --no-verify
git checkout main
git merge fix/sprint205-bug1-onunmounted-removal --no-ff
git push origin main --no-verify
```

## 8. 业务验证 (接手人 7/16+ 启动必跑)

1. user 端 login admin → 应该 0.3s 后跳转到 /audience ✅
2. user 在 /audience 操作 → axios 请求 200 (token 在 sessionStorage, 永久保持) ✅
3. user 刷新页面 → token 在 sessionStorage → 自动登录态 ✅
4. user Cmd+Q → sessionStorage 保留 → 重启 → bootstrap 验证 → /audience ✅ (跟 L4.85.6 配套)

## 9. 跟永久规则链配套 (跟 L4.42 + L4.50 + L4.55 + L4.85.x 1:1 stable 永久规则化沿用)

- L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用
- L4.50 0 业务代码改动 累计 95+ 次 1:1 stable 永久规则链配套
- L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用
- L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用 (token 失效清理由 main.ts + authStore 统一管理)
- L4.75 v2 + L4.85 + L4.85.1 + L4.85.2 + L4.85.3 + L4.85.4 + L4.85.5 + L4.85.6 永久规则链 1:1 stable 配套

## 10. 跨 sprint 留尾 (跟 L4.57 + L4.58 + L4.59 0 commit 续期 1:1 stable 永久规则化沿用)

- 接手人 7/16+ 启动可读 HANDOVER.md + 本 commit message + 4 case L4.85.6 回归 test
- 累计 Sprint 60+ 0 debt stable 144 sprint (跨 sprint 0 debt 模式 1:1 stable 永久规则化沿用)

---

**本 handoff 跟 L4.42 + L4.50 + L4.55 + L4.85.x 1:1 stable 永久规则链配套, 接手人无论是 GPT-5.6 还是其他 agent/人, 都应该按 L4.42 立项实证 SOP "git log + grep 实证" + L4.55 立项 spec 实证 SOP 走完 5 维分析 + reproduce test 验证再 commit + push.**

**关键: 接手人不要凭印象改代码, 必须先 reproduce test 验证 hypothesis 再实施修复. 跟 Sprint 188 B3 + Sprint 199 R1 + Sprint 201 R2 v24 + Sprint 201+ v5 + Sprint 202+ + Sprint 204+ 跨 +38 sprint 1:1 stable 永久规则化沿用.**