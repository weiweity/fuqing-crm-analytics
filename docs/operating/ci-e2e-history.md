# CI e2e 实战 fix 历史 (Sprint 32.1 → Sprint 58 #4)

> 目的：把 Sprint 41 的 12 follow-up、Sprint 55 的 4 follow-up、Sprint 57 的 advisory 沉淀成单一历史入口，供后续 sprint 直接复用。
>
> 只引用可长期复用的证据链：`docs/operating/ci-defense-playbook.md`、`docs/development/LESSONS_LEARNED.md`、`docs/architecture/TEST_INFRASTRUCTURE.md`。
>
> 明确禁止把“本地可跑”误判成“CI 可跑”，也禁止把一次性修复误判成系统性闭环。

## 总览

| 阶段 | 主题 | 结果 | 复用结论 |
|---|---|---|---|
| Sprint 32.1 | 首次尝试把 e2e 拉进 CI | 进入 follow-up 周期 | 先验证 runner 差异，再谈 blocking |
| Sprint 41 | 12 follow-up 仍 fail | 改 advisory | CI e2e 先保留证据链，不强行治本 |
| Sprint 55 | 4 follow-up 收口 | 3/4 job pass, e2e advisory | 复杂 CI 任务要按小步最小 diff 走 |
| Sprint 57 | 持续沉淀 docs / lessons | 把经验固化为 SSOT | 让后续 sprint 直接查文档，不翻旧 commit |
| Sprint 58 #4 | 持久化 + auto-recovery | 新增 script + workflow + history | 把实战 fix 变成可调用流程 |

## §1 Sprint 41 12 follow-up (CI 0→1 实战 fix, 2026-06-17)

Sprint 41 的主线不是“写一个 e2e job”，而是“把本地 11/11 pass 的 spec 拉到 GH Actions 上验证后，承认 runner 差异并记录每个 follow-up 的失败原因”。

| Follow-up | Commit | 症状 | 根因 | 修复模式 | 跨 sprint 复用价值 |
|---|---|---|---|---|---|
| 41.1 | `d44804b` | disk check 先炸 | runner 14GB disk 触发 ETL 阈值 | `ETL_MIN_DISK_GB=0` | 测试只验证 marker 时要跳过无关资源门槛 |
| 41.2 | `ee8a655` | `npm ci` 失败 | `openapi-typescript` peer dep 与 TS 版本冲突 | `--legacy-peer-deps` | 依赖冲突先保 CI 可运行，再考虑回收 |
| 41.3 | `b374f36` | `vue-tsc` strict 报错 | readonly string[] 类型与组件签名不一致 | 显式 type cast | 真实类型问题优先修，不用 build 假绿掩盖 |
| 41.4 | `ae68c6c` | API 返回 401 | CI runner 没 backend 服务 | e2e job 启 uvicorn | CI 里必须把依赖服务也当作被测系统的一部分 |
| 41.5 | `7df0c84` | `page.request` 仍 401 | request 没带 session token | 补 Authorization header | 浏览器态 token 不等于 request 态 token |
| 41.6 | `342e2f3` | sampling spec 断言失败 | backend 字段名 typo + 并行抢资源 | 修 typo + 关 fullyParallel | spec 的业务断言和并发设置都要显式审查 |
| 41.7 | `d2a8534` | 渲染超时 | runner 上 headless Chromium 更慢 | CI timeout 30s | 超时要按环境校准，不要照搬本地值 |
| 41.8 | `da9cd2b` | spec 内 hardcode timeout 仍失败 | `playwright.config.ts` 没覆盖 hardcode | 批量改 spec timeout | 配置层和用例层都要清理，不能只改一层 |
| 41.9 | `9770cfa` | beforeEach / test body 仍超时 | CI 需要更宽松的全局 timeout | 60s | timeout 策略要分层，不可混用 |
| 41.10 | `e3729a5` | uvicorn 启动不稳定 | 启动失败被吞错 + 等待窗口不足 | `set -e` + redirect log + 60s wait | 错误可见性比优雅失败更重要 |
| 41.11 | `e3729a5` | 同上 | `|| true` 把真错藏掉 | 显式 fail-fast | 任何 CI wrapper 都不能吞掉启动错误 |
| 41.12 | `e9020a1` | 仍然 fail | runner 与本地差异过大 | 改 non-blocking advisory | 当治本成本过高时，先让 CI 保持有信号 |

### Sprint 41 的结论

- 12 follow-up 证明了“CI e2e 不是单点 bug，而是环境、依赖、服务启动、超时和数据门槛的组合问题”。
- `docs/operating/ci-defense-playbook.md` 把这次经验抽象成 Q1-Q4 决策树。
- `docs/development/LESSONS_LEARNED.md` 的 Pattern 6 说明了 follow-up 不是失败，而是复杂系统修复的正常形态。

## §2 Sprint 55 4 follow-up (CI 实战 fix, 2026-06-19)

Sprint 55 的主线是把 CI 从“被动红灯”修到“可解释的 3/4 pass”，再把剩余 e2e 失败保留为 advisory。这里的关键不是 commit 数量，而是每个 follow-up 都有独立症状、独立根因、独立验证。

| Follow-up | Commit | 症状 | 根因 | 修复模式 | 跨 sprint 复用价值 |
|---|---|---|---|---|---|
| 55.0 | `af146b2` | backend smoke 因 env 缺失炸掉 | `HEALTH_API_KEY` 在 CI 没注入 | 注入 fake CI key | 任何启动型 job 都要显式补齐必需 env |
| 55.1 | `b697535` | ruff / lint 仍报 F401 | 测试和 service 里残留 unused import | 清理 8 个 F401 | 小而散的 lint 报错要一次性收口 |
| 55.2 | `d00ab3c` | 本地看不出 CI 真错 | stderr 没被抓到 | capture stderr | 先把证据打印出来，再谈修复 |
| 55.3 | `351adfd` | subprocess `getpath` crash | absolute path + cwd 处理触发 Python 3.14 问题 | 显式 `cwd=str(repo_root)` | subprocess 路径要显式，不要依赖隐式解析 |

### Sprint 55 的结论

- 这 4 次修复证明：CI 任务可以收口，但前提是每次都保留最小 diff 和独立验证。
- `CHANGELOG.md` 的 Sprint 55 段已经把 4 次修复和 3/4 pass 结果记录为可追溯事实。
- `docs/development/LESSONS_LEARNED.md` Pattern 6 里对 Sprint 55 的引用，正是为了后续 sprint 不再重复从零摸索。

## §3 Sprint 57 实战 fix (e2e CI advisory 持续)

Sprint 57 没有把 e2e 从 advisory 再次拉回 blocking，而是继续坚持“runner 差异大于局部代码问题时，先保留信号，再做持久化沉淀”。

- 当前 CI 结构沿用 4 jobs 视角：`lint` + `ground-truth-lint` + `pytest` + `e2e`。
- `docs/operating/ci-defense-playbook.md` 里已经明确：当 `N follow-up` 继续增长但 ROI 不再成立时，改 advisory 是务实选择。
- `docs/architecture/TEST_INFRASTRUCTURE.md` 也把 GH Actions CI 的 e2e 状态写成 `3/4 pass`，说明它不是主阻断面，而是持续观察面。

### Sprint 57 的教训

- e2e 不是“做了就该 blocking”，而是“先能解释，再决定是否阻断”。
- 失败证据必须保留，不然下一 sprint 会把同一个坑重新踩一遍。
- 只要 runner 约束不变，继续 follow-up 不一定比 advisory 更有效。

## §4 Sprint 58 持久化模式 (本 sprint)

本 sprint 的目标不是再发明一套新流程，而是把 Sprint 41 + Sprint 55 + Sprint 57 的结论固化为可复用资产。

### 这次固化了什么

- `docs/operating/ci-e2e-history.md`：作为 e2e CI 的 SSOT 历史入口，集中承载 12 follow-up、4 follow-up、advisory 和复用结论。
- `scripts/ci/auto_recover_ci.sh`：把“失败后清缓存再重跑一次”的操作从口头经验变成可调用脚本。
- `.github/workflows/e2e.yml`：把 auto-recovery 串进 workflow，但不改变现有 11 spec 的执行方式。

### 为什么这样做

- 避免 Sprint 60+ 再次出现“同类失败已经在旧 commit 里修过，但新流程没人记得”的复发。
- 把“查历史”变成“查一个文件”，减少 review 时的上下文切换成本。
- 让 Stage 3 review 可以直接验证：文档、脚本、workflow 三者是否一致。

## §5 auto_recover_ci.sh 设计

auto_recover_ci.sh 的目标只有一个：在不改测试逻辑的前提下，给 CI 一次轻量自愈机会。

### 设计原则

1. 只允许 1 次 retry，避免把 transient error 伪装成稳定通过。
2. 只做 cache cleanup，不碰生产数据、不改测试逻辑。
3. 用数组参数执行命令，避免 `eval` 的字符串拼接脆弱性。
4. 失败时保留日志，方便 Stage 3 和后续 sprint 复盘。

### 清理范围

- `.pytest_cache`
- `backend/tests/.pytest_cache`
- `frontend-vue3/node_modules/.cache`
- `/tmp` 下符合条件的 `playwright_*` 临时目录

### 预期行为

- `bash scripts/ci/auto_recover_ci.sh true` 应直接通过。
- `bash scripts/ci/auto_recover_ci.sh false` 应在第 2 次尝试后放弃，并留下 `/tmp/auto_recover_ci.log`。
- 这个脚本的价值在于“把人工 recovery 变成一致动作”，不是提高测试本身的正确率。

## §6 跨 sprint 复用价值

- Sprint 41 的 12 follow-up 提供了“runner 差异、超时、依赖、服务启动”的完整失败谱。
- Sprint 55 的 4 follow-up 提供了“env、lint、stderr、cwd/path”这类常见 CI 失败模式。
- Sprint 57 把 advisory 作为持续观察面的策略固定下来。
- Sprint 58 把这些经验串成一个可调用的最小闭环。

### 复用优先级

1. 先查 `docs/operating/ci-e2e-history.md`。
2. 再查 `docs/operating/ci-defense-playbook.md`。
3. 再查 `docs/development/LESSONS_LEARNED.md` 的 Pattern 6。
4. 最后再看 `CHANGELOG.md` / `TECH-DEBT.md` 中的 commit 证据。

### 结论

- 复杂 CI 任务不靠一次性聪明修复，而靠可重复的证据链。
- 只要 follow-up 还在增长，就说明系统性问题还没收口。
- 一旦决策为 advisory，就要把理由写进历史文档，而不是留在个人记忆里。

## Stage 2 完成 — Sprint 58 #4 (CI e2e 持久化)

- **完成时间**: 2026-06-21
- **改动**:
  - `docs/operating/ci-e2e-history.md`: 扩写为 6 个章节的 SSOT 历史入口
  - `scripts/ci/auto_recover_ci.sh`: 新建数组参数版 recovery 脚本
  - `.github/workflows/e2e.yml`: 新建 auto-recovery workflow
- **Stage 3 等待**: 请核对文档、脚本和 workflow 的一致性
