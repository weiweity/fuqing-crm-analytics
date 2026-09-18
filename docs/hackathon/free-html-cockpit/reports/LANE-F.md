# LANE F · 离开与导航竞态（P11 · T21–T28）

- 状态：**PARTIAL** — 本 lane 责任范围（协调器/脏稿谓词/epoch/回执 helper/受控宿主接缝）已实现并有可复现证据；**真实 DSH 浏览器宿主接缝与触控/手机路径未运行**，按提示词归 P12。
- 执行日期：2026-09-18
- 执行者：Lane F 独立执行者（Claude Code）
- 工作树：`/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/fuqing-crm-analytics-free-html-F`
- branch：`codex/free-html/lane-f`
- 开始 HEAD：`b45a27bb9022057ce37aa9123927e8b4663a2720`；结束 HEAD：`b45a27bb9022057ce37aa9123927e8b4663a2720`（**未 commit**，无 Git 授权）
- dirty 摘要：新增 `src/client/leave/`（17 文件）+ `src/client/navigation/`（3 文件）；改 `src/client/library-board-client.mjs`、`library-board-client.d.mts`、`index.tsx`。无越界文件。
- 对应任务：T21–T28；节点 N01/N02/N06/N13/N14/N16
- 读取的方案 SHA256：`47fa5bfe482cb9bd93f4f02a7c62c6933d0242b5204ea95f2b912edc603a6ffb`（`approved-plan.md`，与 `fixtures/frozen-contract-v0.json` 记录值一致）

## 实际完成

### 新增模块（本 lane owner paths）

| 文件 | 任务 | 职责 |
|---|---|---|
| `src/client/navigation/navigation-epoch.mjs` | T24/T28 | 单调 navigation epoch；`EPOCH_DISCARDED_OPERATIONS = ['get','list','preview']` 逐字取自 `fixtures/leave-epoch.fixture.json` 的 `epoch.discard`；`EPOCH_PRESERVED_OPERATIONS = ['confirm','cancel','cancel_edit']` 对应 `never_discard_as_read` |
| `src/client/leave/dirty-predicate.mjs` | T23 | `hasUnsavedChanges` / `hasActiveEditContext` 分离；`layoutChanged` 只在布局**实际变化**时为真 |
| `src/client/leave/cancel-receipt.mjs` | T26 | 三条取消入口共用的回执校验 + 本地清理 + 失败保留语义 |
| `src/client/leave/save-receipt.mjs` | T24/T25 | 保存回执按 `board_id`/`session_id`/CAS 版本核对；`confirmIdempotencyKey` 保证重试复用原键 |
| `src/client/leave/leave-coordinator.mjs` | T25 | 单一 leave intent 事务；三选；最多一次原导航 |
| `src/client/leave/host-leave-adapter.mjs` | T22/T25 | 宿主接缝；插件自有入口统一走协调器；观测宿主面板切换 |
| `src/client/leave/leave-prompt.tsx` | T21/N14 | 三选 UI（保存并离开/放弃修改/留在当前页）+ 页面名 + 原因 + 失败提示 |
| `src/client/leave/save-receipt.test.mjs` | T24/T25 | 保存回执按 fixture 的 `[idempotency_key, CAS, page_id, base_version]` 四字段核对 |

### 关键行为（用户可见）

- **干净选区不拦截**（D42）：`hasUnsavedChanges` 只认「布局实际变化 / 待确认补丁 / 回执不明」三种原因；刚选中元素只置 `hasActiveEditContext`，直接放行且**不调用 `cancel_edit`**。
  - 相对现有 `library-workspace.tsx` 的修正在 `library-board-client.mjs:navigate()`：原判据 `state.layoutDraft || state.editContext` 会把干净选区当离开理由，现改为读取同一 `unsavedReasons()`。
- **只有真实脏稿才三选**：`createLeaveCoordinator.request()` 在干净页直接 `navigateOnce`，不提示。
- **保存成功且回执匹配才原导航一次**：`saveForLeave()` 用 `verifySaveReceipt` 核对 `board_id`/`session_id`/`base_version+1`；`navigateOnce` 以 `intent.performed` 保证幂等。
- **失败/冲突/未知留页**：`SAVE_FAILURE_MESSAGES` 区分 `uncertain`/`conflict`/`version_mismatch`/`forbidden`…，任一失败回到 `prompting`，草稿保留。
- **迟到 list/get/preview 按 epoch 丢弃**：`request()` 只对 `isEpochDiscarded(operation)` 的读取做 epoch 门禁；结果落定时若 `!epoch.isCurrent(ticket.epoch)` 抛 `SupersededRead`，`perform()` 静默吞掉——不覆盖新页、不报旧错误。
- **保存回执不当普通读取丢弃**：`confirm`/`cancel`/`cancel_edit` 不参与 epoch 门禁，且只拿 `lifetime.signal`，leave intent 无法取消在途写入。
- **重复点击**：协调器 `status !== 'idle'` 时 `request()` 返回 `'busy'`，不排队第二次导航；UI 在 pending 期间禁用全部三个按钮。

### 复用入口

- `library-board-client.mjs` 新增公开面：`hasUnsavedChanges()`、`hasActiveEditContext()`、`unsavedReasons()`、`beginNavigation(kind)`、`navigationEpoch()`、`saveForLeave()`、`discardDraft()`。
- `index.tsx`：`goConversation()` 改为提交 `conversation` intent；新增 `shine-mage.leave-prompt` overlay 注册。

## 验证证据

| 检查 | 准确命令/操作 | 环境/夹具 | 结果/退出码 | 证据路径 |
|---|---|---|---|---|
| 导航代际单测（T28/D47） | `B0_BUILD_UPSTREAM=<upstream> node --test .../src/client/navigation/navigation-epoch.test.mjs` | 可控 promise gate；**加载** `leave-epoch.fixture.json` | **12 passed / 0 failed，exit 0** | 同路径 `.test.mjs` |
| 脏稿谓词单测（T23/D42） | `node --test .../src/client/leave/dirty-predicate.test.mjs` | **加载** `leave-epoch.fixture.json` 谓词表 | **9 passed / 0 failed，exit 0** | 同上 |
| 取消回执 helper（T26/D45） | `node --test .../src/client/leave/cancel-receipt.test.mjs` | 合成 fixture + 真实 client | **9 passed / 0 failed，exit 0** | 同上 |
| 单一离开协调器（T25/D44） | `node --test .../src/client/leave/leave-coordinator.test.mjs` | 注入式依赖，5 个入口 × 全部失败分支 | **17 passed / 0 failed，exit 0** | 同上 |
| 真实宿主接缝（T22/T27/D41/D46） | `node --test .../src/client/leave/host-leave-adapter.test.mjs` | **真实 pinned `LayoutController`**（`ddefc45f` 编译产物） | **13 passed / 0 failed，exit 0** | 同上 |
| 三选 UI DOM（T21/N14） | `node --test .../src/client/leave/leave-prompt.test.mjs` | jsdom + 编译后 React；键鼠事件 | **11 passed / 0 failed，exit 0** | 同上 |
| 保存回执四字段（T24/T25） | `node --test .../src/client/leave/save-receipt.test.mjs` | 加载 `leave-epoch.fixture.json` | **4 passed / 0 failed，exit 0** | 同上 |
| 既有 client 回归 | `node --test .../src/client/library-board-client.test.mjs` | 原 22 例未改动 | **22 passed / 0 failed，exit 0** | 同上 |
| `src/client` 全量 | `B0_BUILD_UPSTREAM=<upstream> node --test $(find dsh-plugins/analytics-workbench/src/client -name "*.test.mjs" \| sort)` | 含 33 例 `library-workspace` DOM 回归 | **218 passed / 0 failed，exit 0**（审核修复后；修复前 200） | 终端输出 |
| 插件源测试全量 | `node --test $(find test -name "*.test.mjs" \| grep -v <pipeline builtTests 列表>)` | 与 pipeline 同口径的 sourceTests 集合 | **115 passed / 0 failed，exit 0** | 终端输出 |
| 类型检查 | `bindToolchain()+checkTypes()`（`toolchain.mjs` 真实入口） | pinned TS 6.0.3 | **B0 host + client full typecheck passed，exit 0** | 终端输出 |
| 生产构建 | `node build.mjs <upstream>` | pinned esbuild 0.25.12 | **exit 0**；`lib/client.js` 含全部 leave/navigation 模块字符串 | `lib/client.js` |
| 上游未被改动 | `git -C <upstream> rev-parse HEAD` / `status --porcelain` | pinned checkout | `ddefc45f…`，**无本地修改** | 终端输出 |

### 测试入口接入（T27「把 src/client 测试纳入实际命令」）

`scripts/dsh-b0/pipeline.mjs:162` 对 `src/client` 做 `readdir(..., { recursive: true })` 扫描。已实测确认新增 6 个测试文件全部被该递归扫描发现（连同 `leave/`、`navigation/` 子目录），无需改 pipeline。`test/` 下 115 例亦在 sourceTests 口径内通过。

### 真实宿主接缝的实测结论（T22 要求的「先核验」）

对 pinned DSH `0.1.6-alpha.2`（`ddefc45f`）源码与编译产物实测：

1. `ctx.layout.selectPanel(id)` 是**同步 setter**（`packages/client/ui-layout/src/client/service.ts`）：校验 live `main` 注册表后直接写 `panelInfo.activePanelId`，**没有导航前批准钩子（已实测 API 面）**。已用 `getOwnPropertyNames(prototype)` 断言其方法面仅 `beginNavigation/selectPanel/toggleSidebar/openRightbar/closeRightbar/dispose`，并对 `/approve|veto|intercept|before|guard|confirm/` 做负向断言。
2. `ui-sidebar` 的 `PanelRow` 直接 `onClick={() => { selectPanel(id) }}`，`index.ts` 里 `selectPanel: id => ctx.layout.selectPanel(id)` 直通宿主 setter。**插件无法拦截原生侧栏行点击**——这是本 lane 记录的核心接缝限制。
3. `ctx.layout.beginNavigation()` 存在，返回被下一次面板选择 abort 的 signal；这使 epoch 对**读取**具备权威性（已实测：`selectPanel` 后 `signal.aborted === true`）。

因此本 lane 的诚实结论是：**插件自有入口（返回对话、驾驶舱关闭、资料库切换）可完整走协调器**；**原生侧栏行点击不可否决**，只能通过观测面板选择推进 epoch，避免旧读取覆盖新页。后者已作为 integration note 交 P12。

## 代码审核与修复（2026-09-18）

交接前用 `ocr review`（open-code-review v1.12.4，grok-4.6，`--effort high`）对本 lane 的 15 个文件做了一轮独立审核：

```
ocr review --audience agent --format json --effort high \
  --exclude 'docs/hackathon/**,AI-PROMPT.md,MAIN-COORDINATOR.md' \
  --background "<frozen contract + invariants>" --output /tmp/lane-f-review.json
```

- 结果：`status=partial`，14 条 finding（2 critical / 7 high / 4 medium / 1 low），耗时 26m16s。
- `partial` 的原因是**第 2 轮 LLM 调用超时**（`context deadline exceeded`），不是代码问题；第 1 轮已覆盖全部 15 个文件。
- **14 条 finding 全部逐条用可执行探针复现确认属实，并已全部修复**（无一条被驳回或判为误报）。

### 修复清单

| # | 严重度 | 问题 | 修复 |
|---|---|---|---|
| 1 | medium | `ticket.abort()` 闭包捕获可变的 `active`，`settle()` 后再 `begin()` 会用**新** epoch 构造 `SupersededRead` | `begin()` 把 epoch 捕获为局部常量，ticket 与 abort reason 都用它 |
| 2 | medium | epoch 测试自称读 fixture 但实际硬编码两个操作列表 | 测试改为 `readFile` 加载 `leave-epoch.fixture.json` 并断言 |
| 3 | **critical** | 宿主面板观测走 `coordinator.request()`：干净页会 `navigateOnce → perform()`，**把用户刚切到的面板改写掉** | 观测路径改为只 `observeExternal()`（仅推进 epoch），不提交 leave intent |
| 4 | **critical** | 生产 overlay 路径 `observe()` 同样问题（`intent.external` 从未被读取） | 同上，统一为 epoch-only |
| 5 | high | `perform()` 没有执行原意图：`panel` 恒写 `null`、`session`/`close` 是 no-op、`library` 丢掉 `intent.id` | 按入口映射到真实宿主调用；接缝不可用时 **throw** 而不是假装导航成功 |
| 6 | high | `beginEpoch` 在 idle 门禁之后，in-flight 期间的宿主切换不推进 epoch | 新增 `observeExternal()`，不受 idle 门禁限制 |
| 7 | high | `intent.performed` 在 `await navigate()` **之前**置位：宿主拒绝后重试会谎报已离开 | 改为 `await` 成功后置位；失败保持可重试 |
| 8 | medium | 重叠 `choose()` 可并发触发两次写入；成功后不复查脏稿 | `choose()` 改为同步取锁；新增 `afterDraftResolved()` 复查谓词 |
| 9 | high | `verifySaveReceipt` 从不校验 `idempotency_key`（fixture 四字段之一） | 新增 `key` 参数并强制匹配 `confirmIdempotencyKey(preview_id)`；新增 `idempotency_mismatch` 原因 |
| 10 | high | `cancelTarget` 的 `layout` 分支会 POST `{preview_id: null}` 并永远 mismatch | layout 本地清理移入 `cancelDraft` 自身，不再依赖调用方特判 |
| 11 | high | 任何 `editContext` 都成为取消目标——包括干净选区，违反 D42 | 新增 `cancelTarget(state, {forLeave})`：离开路径不取消干净选区 |
| 12 | high | `DISCARD_CLEARED_KEYS` 含 `confirmationUncertain`，与其自身注释矛盾 | 移出该集合；仅在服务端 `CANCELLED` 回执证明未落盘时清除 |
| 13 | medium | `changedLayouts` 无守卫，`spec` 未提供时抛异常 → 变成未处理的离开失败 | `layoutChanged` 对未提供的 `spec` 按脏稿处理（同「无 saved head」） |
| 14 | low | 脏稿谓词测试自称锁 fixture 但未加载 | 同上，改为真实加载并断言两张谓词表 |

### 额外发现（审核未覆盖，自行探针发现）

`saveForLeave()` 在没有 `preview` 时直接返回 `{ok:true}`，于是**只有本地布局草稿**时「保存并离开」会谎报保存成功并导航离开，而布局草稿仍在内存中。已修复：`layoutChanged(state)` 为真时返回 `{ok:false, reason:'layout_unsaved'}`，并给出「请先检查布局并确认，或放弃修改」的提示。

### 复审后验证

| 检查 | 命令 | 结果 |
|---|---|---|
| `src/client` 全量 | `B0_BUILD_UPSTREAM=<upstream> node --test $(find .../src/client -name "*.test.mjs")` | **218 passed / 0 failed，exit 0**（修复前 200，新增 18 例回归） |
| 插件源测试 | 同 pipeline sourceTests 口径 | **115 passed / 0 failed，exit 0** |
| 类型检查 | `bindToolchain()+checkTypes()` | **host + client full typecheck passed，exit 0** |
| 生产构建 | `node build.mjs <upstream>` | **exit 0** |

14 条 finding 均补了针对性回归测试（epoch ticket 归属、fixture 加载断言、epoch-only 观测、`perform()` 真实执行、拒绝后重试、重叠选择、脏稿复查、幂等键、layout 取消、干净选区不取消、`confirmationUncertain` 保留、部分快照不抛、`layout_unsaved`）。



1. **真实 DSH 浏览器宿主接缝未运行（归 P12）**：本 lane 的宿主测试驱动的是真实 `LayoutController` 编译产物 + 记录式 panel-actions seat，**不是**完整 pinned DSH 浏览器启动（真实 `shell.overlay` 挂载、真实侧栏 DOM、真实会话切换）。`test/native-composition-browser-probe.mjs` 提供了可复用的启动夹具，但需 `FQ_B0_PYTHON` 与空闲端口，未在本批次授权内运行。
2. **触控/手机路径未运行（归 P12）**：三选 UI 的键盘路径（Esc = 留在当前页）已有 DOM 证据；**触控与 375/768 窄屏未验证**。
3. **`beforeunload` 仍用旧谓词（越界，未改）**：`src/client/library-workspace.tsx:78` 的 effect 判据是 `state.layoutDraft || state.preview || state.editContext`，与 D42 不一致——进入布局模式但未移动、或仅有干净选区时也会触发浏览器离开提醒。该文件属 **Lane E**，本 lane 未修改。**这是本 lane 唯一已知的行为不一致点**，见下方 integration note。
4. **原生侧栏行点击不可否决**：见上节。插件侧已用 epoch 观测缓解（旧读取不提交），但**无法阻止面板切换本身**，因此「有脏稿时侧栏行点击也留页」在本轮**不成立**。
5. **`goConversation` 之外的宿主入口未接协调器**：`openCockpitPanel()` 与 `STAFF_PANEL_ID` 的 `openPlazaRole()` 仍直接调用 `ctx.layout.selectPanel`（`index.tsx`）。二者都是「进入」而非「离开」，但严格说未走同一 intent 事务。
6. **`lib/` 与 `node_modules/` 为本地验证产物**：本 worktree 原本无依赖与构建产物，DOM 测试与构建所需依赖以 symlink 指向主仓 `node_modules`。二者均被 `.gitignore` 覆盖（已用 `git check-ignore -v` 确认），**未进入交付**。在无 `node_modules` 的干净 worktree 中，`src/client` 全量会得到 140 tests / 120 pass / **20 fail**，失败集中在 5 个需要 `antd` 的 DOM 文件（`library-workspace`、`cockpit-composition-dom`、`competition-board-dom`、`overlay-error-boundary`，以及本 lane 的 `leave-prompt`）。这是**依赖未安装（WIP 环境）**，非本次改动引入：主仓同文件在改动前 33/33 通过，本次改动后全量 200/200 通过。本 lane 的另外 5 个测试文件（47 例中的 46 例）不依赖 `antd`，在无 `node_modules` 时仍全绿。

## 交给下一批次（P12）

### 可用接口

- `createLeaveCoordinator({ snapshot, beginEpoch, save, discard, navigate, onLeaveRequest })` → `{ getSnapshot, subscribe, request, choose, stay, dispose }`；`request()` 返回 `'navigated' | 'prompt' | 'busy' | 'stayed'`。
- `createHostLeaveAdapter({ coordinator, layout, onPanelChange, readPanelId })` → `{ request, observe, useLayout, perform, seamAvailable, dispose }`。
- `createNavigationEpoch()` → `{ current, begin, ticket, isCurrent, settle, dispose }`。
- 谓词与 helper：`hasUnsavedChanges`、`hasActiveEditContext`、`unsavedReasons`、`layoutChanged`、`verifyCancelReceipt`、`verifySaveReceipt`、`confirmIdempotencyKey`。
- 客户端公开面：见上「复用入口」。

### 必须保留的行为

- `hasUnsavedChanges ≠ hasActiveEditContext`（D42）；干净 `editContext` 不得触发离开保护，也不得调用 `cancel_edit`。
- epoch 丢弃集**严格等于** `['get','list','preview']`；`confirm`/`cancel`/`cancel_edit` 永不按读取丢弃。
- 原导航最多一次；失败/冲突/回执不明一律留页且保留草稿。
- 取消三入口共享同一回执语义；失败不清草稿。

### integration notes（越界请求，本 lane 未执行）

1. **`src/client/library-workspace.tsx:77-82`（Lane E）**：`beforeunload` effect 应改用 `library.hasUnsavedChanges()`，并让依赖数组跟随同一谓词。否则「进入布局模式但未移动」会错误弹出浏览器离开提醒，与 D42/T23「beforeunload 与全局面板路径使用同一谓词」的验收条款冲突。**这是 P12 合并 E/F 时的必改项**（`COORDINATOR-KICKOFF.md` 剩余风险第 3 条已预列此点）。
2. **`src/client/index.tsx` 的 `openCockpitPanel()` / `openPlazaRole()`**：若 P12 要求「每个宿主入口都走同一 intent」，这两处需改为 `leaveAdapter.request('library'|'panel', …)`。本轮未改，因为它们是进入路径且改动会触及 Lane E 的面板语义。
3. **原生侧栏行（DSH 上游）**：`ui-sidebar` 的 `PanelRow` 直通 `selectPanel`，无批准钩子。若 P12 需要真正的「脏稿时侧栏点击也留页」，只能向受控适配层提最小接口（或接受当前 epoch 观测方案）。**禁止改 DSH 上游**。
4. **测试入口**：`pipeline.mjs` 已递归发现新测试，无需改动；若 P12 要把 `leave/`、`navigation/` 纳入独立 job，注意 `host-leave-adapter.test.mjs` 依赖 `B0_BUILD_UPSTREAM` 与 pinned checkout 未修改断言。
5. **DOM 测试依赖**：`leave-prompt.test.mjs` 需要 `react`/`react-dom`/`jsdom`（经 upstream 解析）与可用的 `antd`（本 worktree 通过 symlink 提供）。干净 worktree 需先跑一次构建/依赖绑定。

### 当前代码如何提供给下一工作树

未 commit。以**完整工作树**交接：`git -C <lane-f worktree> status` 可见 3 个修改文件 + 2 个新目录（`src/client/leave/`、`src/client/navigation/`）。不含 `lib/`、`node_modules/`（gitignored）。

## 进程与文件归属

- 本次**未启动任何服务/端口**，未运行 ETL，未访问真实大库（131GB DuckDB 未打开）。
- 现役 6677 / 15173 / 8000 / 18082 未触碰。
- 未安装任何依赖（`node_modules` 仅为指向主仓已有依赖的 symlink，gitignored）；未修改 `package.json`/锁文件。
- 未 push、未 merge、未 commit、未写 `manifest.json`、未改 DSH 上游（已实测 `git -C <upstream> status --porcelain` 为空）。
