# 芙清CRM登录认证功能 — 交叉审查报告

**日期**：2026-05-07
**场景**：登录认证功能上线前交叉审查（产品 + 安全 + QA）
**参与成员**：product-reviewer（产品官）+ security-officer（安全卫士）+ qa-lead（质量门神）

---

## 📌 TL;DR（执行摘要）

- 整体结论：**🟡 有条件通过** — 当前实现满足"能登录、能拦截"的基础需求，但存在 6 项🔴阻塞级问题必须在上线前修复
- 🔴 阻塞级：6 项（无logout、token永不过期、明文密码、暴力破解、路由守卫不验证有效性、内存存储重启掉线）
- 🟠 严重级：8 项（401跳转体验差、XSS token窃取、内存DoS、Pinia不同步、无加载态、并发重定向等）
- 🟡 一般级：9 项（布局判断、跳转地址保留、RBAC缺失等）
- 🟢 建议级：4 项（加载动画、弹窗延迟、CORS配置、代码规范）
- **下一步**：优先修复前 6 项阻塞问题，再进行第二轮回归验证

---

## 🎯 核心结论卡片

| 项目 | 内容 |
|------|------|
| Go / No-Go | 🟡 条件 Go（修复 6 项阻塞级后可上线） |
| 严重度分布 | 🔴 6 / 🟠 8 / 🟡 9 / 🟢 4 |
| 关键行动项 | 10 条 |
| 建议负责人 | 后端：logout + TTL + 限速 + 密码哈希；前端：401路由跳转 + 加载态 + 校验同步 |

---

## 1. 各成员核心结论

### 🔍 产品官（产品评审）
- **核心判断**：前后端分离的 Bearer Token 方案架构合理，sessionStorage 按 tab 隔离适合内网 CRM 场景，但当前实现过度简化，缺少 token 生命周期管理（TTL/刷新/注销）
- **关键建议**：① 补 `/logout` 端点解决内存泄漏；② 路由守卫需与 bootstrap 校验结果打通，避免后端重启后闪进看板；③ 401 拦截器改用 `router.push` 保持 SPA 体验；④ 密码必须哈希存储

### 🛡️ 安全卫士（OWASP+STRIDE 审计）
- **核心判断**：内网场景下安全基线严重不足——明文密码、永久有效 token、无审计日志、无速率限制，任何一项被攻破均可导致全站数据泄露
- **关键建议**：① 密码迁移 bcrypt/Argon2；② token 加 TTL + logout；③ 部署登录限速（5次/分钟）；④ 补全认证审计日志；⑤ 考虑 httpOnly Cookie 替代 sessionStorage 防 XSS；⑥ 生产环境移除 localhost CORS

### ✅ 质量门神（QA测试审查）
- **核心判断**：当前实现"能跑"但"不经测"——6 项阻塞级缺陷中任意一项都可能导致上线后用户投诉或安全事件，回归测试清单中至少 5 项 P0 目前无法通过
- **关键建议**：① 服务端重启后必须自动跳转登录页；② 并发 401 需防抖避免多次重定向；③ 暴力破解必须有限速；④ Swagger/docs 等接口需确认已纳入保护；⑤ 登录成功后应保留原始跳转地址

---

## 2. 综合审查发现（去重合并后按严重度排序）

### 🔴 阻塞级（必须修复）

| # | 严重度 | 类别 | 位置 | 问题描述 | 建议 | 来源 |
|---|--------|------|------|---------|------|------|
| 1 | 🔴 | 安全 | `auth.py:8-11` | 明文硬编码密码（"123456"/"fqsw888"），源码泄露即凭据暴露 | 使用 `passlib` bcrypt/Argon2 哈希；凭证改为环境变量+哈希存储 | 安全+产品+QA |
| 2 | 🔴 | 安全 | `auth.py:30` | Token 永不过期，无 TTL/刷新/注销机制，被盗后永久有效 | 增加 token 签发时间戳，校验时检查（如 8h TTL）；实现 `POST /logout` 清理 ACTIVE_TOKENS | 安全+产品+QA |
| 3 | 🔴 | 代码 | `auth.py` | 无 `/logout` 端点，用户退出仅清前端 sessionStorage，后端 token 仍在内存有效 | 新增 `POST /logout` 从 ACTIVE_TOKENS 删除当前 token；前端调用后再清本地存储 | 产品+安全+QA |
| 4 | 🔴 | 安全 | `auth.py:22-30` | 登录接口无速率限制，2个硬编码账号+弱口令极易被暴力破解 | 增加 IP/账号级失败计数（内存或 Redis），5次失败锁定15分钟 | 安全+产品+QA |
| 5 | 🔴 | 体验 | `router/index.ts` | 路由守卫 `isAuthenticated` 仅检查 `!!token`，后端重启后 token 失效仍放行，闪进看板后 401 才踢出 | bootstrap 中 `/me` 校验失败后立即 `router.replace('/login')`；或增加全局 `isAuthReady` 标志阻塞路由 | 产品+QA |
| 6 | 🔴 | 可靠 | `auth.py:30` | ACTIVE_TOKENS 为进程内存字典，服务端重启后全员掉线 | 使用 Redis/文件数据库存储 token；或改用 JWT 无状态方案 | QA+安全 |

### 🟠 严重级（强烈建议修复）

| # | 严重度 | 类别 | 位置 | 问题描述 | 建议 | 来源 |
|---|--------|------|------|---------|------|------|
| 7 | 🟠 | 体验 | `api/index.ts` | 401 拦截器使用 `window.location.href = '/login'` 整页刷新，破坏 SPA 体验 | 改为 `router.replace('/login')`（需在 api 模块引入 router 或用事件总线） | 产品+QA |
| 8 | 🟠 | 代码 | `api/index.ts` | 401 时直接 `sessionStorage.removeItem`，未调用 `authStore.logout()`，Pinia 状态与存储不同步 | 统一走 `authStore.logout()` 清理，确保单一数据源 | 产品 |
| 9 | 🟠 | 安全 | `stores/auth.ts` + `api/index.ts` | token 存 sessionStorage，任何 XSS 均可通过 `sessionStorage.getItem` 窃取 | 短期：加 CSP 策略；长期：改用 `httpOnly` Cookie + `allow_credentials=True` + SameSite=Lax | 安全 |
| 10 | 🟠 | 安全 | `auth.py:30` | ACTIVE_TOKENS 无容量上限，攻击者可批量调用 `/login` 造成内存 DoS | 使用带 TTL 的外部存储（Redis）；或实现内存上限 + LRU 淘汰 | 安全 |
| 11 | 🟠 | 安全 | `main.py` | CORS 允许 `localhost:5173/3000`，内网生产环境存在被本地恶意页面利用风险 | 移除所有 localhost 来源，仅保留实际生产域名；按环境变量区分 | 安全 |
| 12 | 🟠 | 体验 | `stores/auth.ts` | `login()` 无 `isLoading` 状态，网络延迟时可重复提交，生成多个有效 token | 增加 `isLoggingIn` ref，请求期间禁用提交按钮 | 产品+QA |
| 13 | 🟠 | 可靠 | `main.ts` | bootstrap 中 token 校验失败仅清除存储，不执行页面跳转，用户看到空页面 | 校验失败后立即 `window.location.href = '/login'` 或 `router.replace('/login')` | QA |
| 14 | 🟠 | 体验 | `api/index.ts` | Token 失效后页面多个 API 并发 401，每个请求都触发重定向，浏览器竞争闪烁 | 增加全局跳转锁/防抖，确保仅一次重定向 | QA |

### 🟡 一般级（建议优化）

| # | 严重度 | 类别 | 位置 | 问题描述 | 建议 | 来源 |
|---|--------|------|------|---------|------|------|
| 15 | 🟡 | 代码 | `App.vue:68` | 按 `route.path === '/login'` 判断布局，query 参数或子路径会失效 | 使用 `route.meta.requiresAuth` 或 `route.meta.layout` 判断 | 产品 |
| 16 | 🟡 | 代码 | `api/index.ts` + `auth.ts` | `'fq_crm_auth_token'` 硬编码字符串字面量重复定义 | 提取到共享常量文件，统一引用 | 产品 |
| 17 | 🟡 | 体验 | `main.ts` | 网络异常时保留无效 token，后续请求 401 循环 | 标记为"待验证"，首个成功请求后确认；或 401 时仅清 token 不重定向 | 产品 |
| 18 | 🟡 | 代码 | `api/index.ts` | 响应拦截器返回 `response.data` 而非完整 `AxiosResponse`，丢失 status/headers | 返回完整 response，调用方解构 `.data`；或提供两个 client 实例 | 产品 |
| 19 | 🟡 | 安全 | 全局 | 无 RBAC 权限分离，admin 与 fqsw 权限完全对等 | 增加 role 字段；关键接口加 `@require_role("admin")` | 安全 |
| 20 | 🟡 | 安全 | 全局 | 内网 HTTP 明文传输，Bearer token 可被 ARP 欺骗/端口镜像截获 | 部署 TLS/HTTPS；短期在受控网络段隔离 | 安全 |
| 21 | 🟡 | 安全 | `router/index.ts` | 前端路由守卫可被绕过（已知限制），需确认后端中间件覆盖完整 | 审计所有路由，确保 Swagger `/docs`、OpenAPI JSON 等已保护或禁用 | 安全+QA |
| 22 | 🟡 | 体验 | `router/index.ts` | 登录后未保留原始跳转地址，一律回到 `/audience` | 路由守卫 `next('/login?redirect=' + to.path)`；登录成功后解析跳转 | QA |
| 23 | 🟡 | 代码 | `auth.py` + `main.py` | 401 响应格式不统一（`HTTPException` vs `JSONResponse`） | 统一封装 401 响应生成函数 | QA |

### 🟢 建议级（长期改进）

| # | 严重度 | 类别 | 位置 | 问题描述 | 建议 | 来源 |
|---|--------|------|------|---------|------|------|
| 24 | 🟢 | 体验 | `main.ts` | 应用初始化白屏，无加载指示 | `#app` 挂载前加静态 loading 动画 | 产品+QA |
| 25 | 🟢 | 体验 | `LoginView.vue` | 登录成功后强制等待 800ms 才跳转，体感拖沓 | 服务端已确认成功，可直接跳转 | 产品 |
| 26 | 🟢 | 代码 | `main.py` | CORS 硬编码内网 IP，变动后需改代码 | 通过环境变量配置，开发环境允许 `*` | 产品 |
| 27 | 🟢 | 安全 | 全局 | 无审计日志，无法追溯登录事件 | 记录所有认证事件（时间、IP、UA、账号、结果），写入只读存储 | 安全+QA |
| 28 | 🟢 | 体验 | 全局 | 无 Token 刷新机制，长时操作可能中途被踢出 | 实现双 Token（Access + Refresh）或滑动过期 | QA |

---

## ✅ 行动清单（按优先级排序）

| # | 行动 | 负责方 | 紧急度 | 期望完成 |
|---|------|--------|--------|---------|
| 1 | 新增 `POST /logout` 端点，清理 ACTIVE_TOKENS | 后端 | P0 | 本轮 |
| 2 | 为 token 增加 TTL（如 8h），`/me` 和中间件校验过期时间 | 后端 | P0 | 本轮 |
| 3 | 密码使用 bcrypt/Argon2 哈希存储，改为环境变量配置 | 后端 | P0 | 本轮 |
| 4 | 登录接口增加速率限制（5次/分钟/账号，失败5次锁定15分钟） | 后端 | P0 | 本轮 |
| 5 | bootstrap 校验失败后立即跳转登录页，路由守卫同步校验结果 | 前端 | P0 | 本轮 |
| 6 | 考虑 token 持久化存储（Redis）替代内存字典 | 后端 | P0 | 下轮 |
| 7 | 401 拦截器改用 `router.replace('/login')`，增加全局跳转锁防并发重定向 | 前端 | P1 | 本轮 |
| 8 | 401 时统一调用 `authStore.logout()` 同步 Pinia 状态 | 前端 | P1 | 本轮 |
| 9 | `login()` 增加 `isLoading` 状态，禁用重复提交 | 前端 | P1 | 本轮 |
| 10 | 生产环境 CORS 移除 localhost，仅保留实际域名 | 后端 | P1 | 本轮 |

---

## ⚠️ 待完善 / 已知局限

- 当前为内网系统，HTTPS 短期可能无法部署，需在网络层做好隔离
- 仅 2 个硬编码账号，无用户管理体系，未来扩展需接入企业 SSO/LDAP
- 内存 token 方案不适合多实例部署（如有负载均衡），上生产前必须迁移 Redis
- Rive 动画资源文件较大（.riv），首次加载需考虑弱网环境

---

## 📚 成员产出索引

- **product-reviewer（产品官）** 原始产出：16 项发现（P0×3 / P1×5 / P2×5 / P3×3）+ 架构评估
- **security-officer（安全卫士）** 原始产出：11 项发现（Critical×4 / High×3 / Medium×3 / Low×1）+ OWASP/STRIDE 分类
- **qa-lead（质量门神）** 原始产出：18 项发现（阻塞×5 / 严重×5 / 一般×4 / 建议×4）+ 回归测试清单

---

> 本报告由 GStack 工程团队 AI 协作生成，关键决策请由工程负责人复核。
