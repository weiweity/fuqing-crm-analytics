# LANE K · 离开与导航收口（生产接缝）

- 状态：**DONE**（本 lane 责任范围）；原生侧栏行为限制按提示词以 BLOCKED/接受限制方式记录，未假装可拦截
- 执行日期：2026-09-18
- 执行者：Lane K 独立执行者（Claude Code）
- 工作树：`/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/fuqing-crm-analytics-free-html-K`
- branch：`codex/free-html/lane-k`
- 开始 HEAD：`d6b57452`（origin/main，#209 已合）；结束 HEAD：`d6b57452`（**未 commit**，无 Git 授权）
- dirty 摘要：改 5 个已跟踪文件（`index.tsx`、`leave/leave-prompt.tsx`、`leave/leave-prompt.test.mjs`、`leave/dirty-predicate.d.mts`、`cockpit-main-panel.test.mjs`）+ 新增 `leave/cockpit-entry-seam.test.mjs`。无越界文件。
- 对应任务：T22/T25/T27 生产接缝（D44）；T18（字体，integration note，见文末）
- 读取的方案：`PARALLEL-3.md` 共同规则；approved-plan 冻结快照 SHA256 `47fa5bfe482cb9bd93f4f02a7c62c6933d0242b5204ea95f2b912edc603a6ffb`（在主树 `docs/hackathon/free-html-cockpit/approved-plan.md`，本树施工包未含该文件；本 lane 相关段落 D40–D47/T21–T28 逐字读取）

## 实际完成

### 1. `openCockpitPanel` 接上协调器（本 lane 核心）

改动位置：`dsh-plugins/analytics-workbench/src/client/index.tsx:456-487`（entry）、`:428-444`（navigate 回调）、`:533`（overlay 注入）。

- **脏页三选**：进入驾驶舱前读同一脏稿谓词（`hasUnsavedChanges({ ...library.getSnapshot(), htmlUnsaved: pageStore?.hasUnsavedChanges() })`，与协调器 snapshot 完全同源）。脏时提交 `panel` intent（`leaveAdapter.request('panel', { kind: 'panel', id: COCKPIT_PANEL_ID })`），由协调器弹三选（保存并离开 / 放弃修改 / 留在当前页），**任何选择落地前不切换**；保存/放弃成功才执行原导航，失败/冲突/回执不明留页（复用 Lane F 协调器的既有语义）。
- **净页直切**：干净页面保持原直切路径（组合模式 `composition.open` / 独立模式 `selectPanel('cockpit')`），**不提交 intent、不取 epoch**。原因（已实测确认）：工具卡手势是 `void library.openPreview(...)` 然后立即 `props.openCockpit?.()`（`library-workspace.tsx:218-221`）——`openPreview` 内部 `intend('preview', …)` 已推进 epoch 并开启预览读取；若 entry 再 `beginEpoch('panel')`，该预览读取会被 D43 规则按 `SupersededRead` 丢弃，用户点「打开预览，检查后确认」会看到空驾驶舱。净页直切是唯一不破坏既有手势链路的接法。
- **组合模式特判**：`navigate` 回调新增 `panel + cockpit` 分支——组合模式下驾驶舱不是宿主 main panel（`composition.open` 才是产品形态），回调里先 `composition.open(session_id)`；无组合时回落 `adapter.perform` 走宿主 setter。所有其它 intent 原样转 `perform`。
- **重复点击/忙态**：`'busy'` 由协调器兜底（在途 intent 不排队第二次）；entry 自身 `.catch` 兜底宿主拒绝。

### 2. 侧栏限制产品文案 + 状态脊提示

- `leave/leave-prompt.tsx`：三选提示新增固定说明（`data-testid="leave-sidebar-note"`）：**「侧栏的原生面板行由宿主直接切换，不会询问未保存的自由页面；请从页面内入口离开。」** 所有离开三选场景可见，用户在弹窗现场即知道哪些入口受保护、哪些不受。
- `LeavePromptOverlay` 接收 `pageStore`：脏自由页面时确认标题显示**自由页标题**（如「离开「大促复盘自由页」前…」）而非板标题；并订阅 pageStore 使标题随页面切换更新。

### 3. 原生侧栏行（BLOCKED/接受限制，不改 DSH 上游）

按提示词明确记录，不做假装实现：

- 接缝事实（Lane F 已实测并留有源码断言 `host-leave-adapter.test.mjs:284-300`，本轮复核引用）：pinned DSH `0.1.6-alpha.2`（`ddefc45f`）的 `ui-sidebar` PanelRow 在自身 `onClick` 直通 `ctx.layout.selectPanel(id)`；`selectPanel` 是同步 setter，无导航前批准钩子（方法面仅 `beginNavigation/selectPanel/toggleSidebar/openRightbar/closeRightbar/dispose`，对 `/approve|veto|intercept|before|guard|confirm/` 负向断言）。**插件无法在侧栏行点击上插入 veto**。
- 插件侧已有缓解（Lane F，保持不变）：`LeavePromptOverlay` 观测面板选择 → `observeExternal()` 仅推进 epoch，保证旧读取不覆盖新页。
- 本轮动作：限制写进产品文案（上节）+ 本报告。**未改 DSH 上游**（已复核 `git -C <upstream> status --porcelain --untracked-files=no` 为空）。

### 4. 类型契约补齐

`leave/dirty-predicate.d.mts`：`LeavePredicateState` 补 `htmlUnsaved?: boolean`。实现（`dirty-predicate.mjs:36`）自 #209 起就读该字段，但声明缺失——`index.tsx` 直接以完整谓词状态调用 `hasUnsavedChanges` 时 client typecheck 失败（TS2353）。声明对齐实现，未改行为。

## 验证证据

| 检查 | 准确命令/操作 | 环境/夹具 | 结果/退出码 | 证据路径 |
|---|---|---|---|---|
| 驾驶舱进入接缝（新增 4 例） | `B0_BUILD_UPSTREAM=<upstream> node --test dsh-plugins/analytics-workbench/src/client/leave/cockpit-entry-seam.test.mjs` | 真实 `createLibraryBoardClient` + `createLeaveCoordinator` + `createHostLeaveAdapter` 装配；覆盖净页不取 epoch/预览读取存活、脏页三选后单次进入、组合分支不推独立面板、保存失败留页 | **4 passed / 0 failed，exit 0** | 同路径 `.test.mjs` |
| 三选 UI DOM（含新增自由页页名+侧栏说明） | `B0_BUILD_UPSTREAM=<upstream> node --test .../src/client/leave/leave-prompt.test.mjs` | jsdom + 编译后 React；新增 1 例（`panel` intent 脏自由页命名自由页标题、断言侧栏说明 testid 与原因行） | **12 passed / 0 failed，exit 0** | 同路径 `.test.mjs` |
| index.tsx 装配源断言 | `node --test .../src/client/cockpit-main-panel.test.mjs` | 既有 indexSource 断言扩展：`request('panel', …)` 存在、脏检查先于直切（顺序断言）、`intent.id === COCKPIT_PANEL_ID` 组合分支存在、overlay 注入含 `pageStore` | **6 passed / 0 failed，exit 0** | 同路径 `.test.mjs` |
| leave 全目录 + 库客户端回归 | `node --test .../leave/*.test.mjs .../library-board-client.test.mjs .../cockpit-composition.test.mjs` | Lane F 既有 92 例 + 新增 | **96 passed / 0 failed，exit 0** | 终端输出 |
| free-html-library + workspace DOM 回归 | `node --test .../free-html-library.test.mjs .../library-workspace.test.mjs` | #209 集成后既有 43 例（含 beforeunload 已改用 `hasUnsavedChanges`） | **43 passed / 0 failed，exit 0** | 终端输出 |
| `src/client` 全量 | `B0_BUILD_UPSTREAM=<upstream> node --test $(find dsh-plugins/analytics-workbench/src/client -name "*.test.mjs" \| sort)` | Node 24.19.0；上游 `B0_BUILD_UPSTREAM` 只读复用主树 pinned checkout | **264 passed / 0 failed，exit 0** | 终端输出 |
| 插件 `test/` 全量 | `cd dsh-plugins/analytics-workbench && B0_BUILD_UPSTREAM=<upstream> node --test $(find test -maxdepth 1 -name "*.test.mjs")` | pipeline sourceTests 同口径 | **187 passed / 0 failed，exit 0** | 终端输出 |
| 类型检查 + 生产构建 | `cd dsh-plugins/analytics-workbench && B0_BUILD_UPSTREAM=<upstream> node build.mjs <upstream>` | pinned TS 6.0.3 / esbuild 0.25.12；**B0 host full typecheck passed** + client typecheck passed | **exit 0**；`lib/client.js` 含 `leave-sidebar-note`、`htmlUnsaved`、`sm-leave-prompt`（CJK 以 unicode 转义存在） | `lib/client.js`（gitignored 产物） |
| B0 pipeline 全量（`--check`） | `B0_BUILD_UPSTREAM=<upstream> node scripts/dsh-b0/pipeline.mjs --check --python /Users/hutou/homebrew/bin/python3.14` | 含 dsh-dev 测试、离线 kernel/analysis/cockpit 合同、`src/client`+`test` 全套、**干净重建** | **「B0 pipeline passed」，exit 0** | 终端输出 |
| 上游未被改动 | `git -C <upstream> rev-parse HEAD` / `status --porcelain --untracked-files=no` | pinned checkout | `ddefc45f…`，**无本地修改**，exit 0 | 终端输出 |
| 现役未触碰 | 全程未 stop/reload/HTTP 探测 6677；6677 全程 PID 83542 LISTEN 未变 | — | 未触碰 | 终端输出 |

### 环境缺口（WIP 树补齐，均 gitignored/就地 smudge，未进交付）

1. 本树无 `node_modules`：按 Lane F 同款方式 symlink 主树已有依赖（`dsh-plugins/analytics-workbench/node_modules/{@deepseek-ai,@types,antd,react,react-dom}` 与 `build-tools/node_modules`，均 `.gitignore` 覆盖）。未安装任何新依赖、未改 package.json/锁文件。
2. 本树 `frontend-vue3/src/assets/brand/shine-mage.png` 是未 smudge 的 LFS pointer（worktree 环境缺口，主树为真实文件），导致 `scripts/dsh-dev/diagnose.test.mjs` 1 例失败（`lfs_pointer ≠ ok`）。**该失败与本次改动无关**（主树同测试 3 passed）。处置：`git lfs checkout -- <file>` 就地恢复真实文件（共享主树 LFS 对象库，无网络下载），恢复后 diagnose 3 passed，pipeline 全绿。此 smudge 是把工作树文件恢复到 HEAD 声明的内容，非业务修改。其余 104 个 LFS pointer 全在 `docs/`/`diagrams/` 资产，无测试消费，未动。
3. 本树无 `.context/dsh-b0/upstream`：按验证入口用 `B0_BUILD_UPSTREAM` 只读复用主树 pinned checkout；测试内 pin/未修改断言全过。

## 未完成与失败

- **原生侧栏行脏稿拦截：BLOCKED（接受限制）**。pinned 宿主无 veto API（事实见上）。已交付：三选弹窗内固定说明文案 + 本报告记录；epoch 观测缓解（Lane F 既有）。未假装侧栏行点击能留页。若产品要真拦截，只能向 DSH 上游提最小接口或改插件注册方式——均超出本 lane 授权，留 P12 决策。
- **`openPlazaRole`（数据员工面板）未接协调器**：`index.tsx` staff 面板的 `openPlazaRole()` 仍直接 `sessions.create()` + `selectPanel(null)`。它在 Lane F 报告 integration note #2 中已被点名；本 prompt owner paths 为「index.tsx 的 leave / openCockpitPanel 段」，openPlazaRole 属数据员工入口且改动会触及该面板语义，**按范围未改**，维持 Lane F 的 integration note 原样交 P12。
- **P13 真模型样本**：不在本三路（PARALLEL-3 规则 7），未做。
- 无其它失败；未运行项无（上述表格全部实际运行，skip 不计通过）。

## 交给下一批次（P12 集成）

### 可用接口（全部既有，本轮未新增公共 API）

- `leaveAdapter.request('panel', { kind: 'panel', id: COCKPIT_PANEL_ID })` → 脏页三选、净页直通；`'navigated' | 'prompt' | 'busy' | 'stayed'`。
- `LeavePromptOverlay` 新增可选 prop `pageStore`；生产注入见 `index.tsx:533`。
- `LeavePredicateState.htmlUnsaved?: boolean`（声明补齐）。

### 必须保留的行为

- **净页进入驾驶舱不得取 epoch**：工具卡手势 `openPreview → openCockpit` 依赖预览读取在 entry 之后落定；改为无条件 intent 会回归成空驾驶舱（`cockpit-entry-seam.test.mjs` 第 1 例是防回归闸）。
- **组合模式下 `panel+cockpit` intent 必须走 `composition.open`**，不得推独立面板（第 3 例）。
- **三选弹窗必须保留侧栏说明文案**（`leave-sidebar-note`）——它是「侧栏不询问」限制的唯一产品内披露。
- 谓词同源：entry 的脏检查必须与协调器 snapshot 同一构造（`{ ...library.getSnapshot(), htmlUnsaved }`），两处判据漂移会出现「entry 直切但协调器弹窗」或反向的竞态。

### integration notes

1. **`openPlazaRole`**（Lane F note #2 原样）：如 P12 要求每个宿主入口走同一 intent，需单独设计——它是「创建会话 + 返回对话」复合动作，与 `OWNED_ENTRIES` 的 `session`/`conversation` 都不完全重合。
2. **字体（提示词可选项 3，T18）**：不改。捆绑 Noto Sans SC 需要「固定修订文件 + SHA-256 + 许可归档 + `BRAND_DIGESTS.notoSansSc` 置值 + `@font-face`」一整套授权动作（`fonts.md:14-26` 已写明流程），改动不小且越出 leave 收口范围；当前声明栈回退 PingFang SC 已在 fonts.md 如实记录。本 note 即提示词所说的 integration note。
3. **evidence 产物**：跑 pipeline 会在 `docs/hackathon/free-html-cockpit/reports/lane-b/` 写出 T0 探针证据（`isolation-probe.mjs:179` 默认路径，#209 行为）。该目录本轮以未跟踪状态留在本树，供集成者决定是否纳入提交；内容为本机 Chrome 153 headless 探针结果（明确 avoided 6677）。

### 当前代码如何提供给下一工作树

未 commit。以完整工作树交接：`git -C <K 树> status` 可见 5 个修改文件 + 1 个新测试文件。`lib/`、`node_modules/`、`.context/` 均 gitignored 不进交付；干净 worktree 需先按「环境缺口」一节补 symlink + LFS smudge 再复跑。

## 进程与文件归属

- 本次**未启动任何服务/端口**；未运行 ETL；131GB 真实 DuckDB 未打开。
- 现役 6677（PID 83542）/ 15173 / 8000 / 18082 全程未触碰；无 reload、无 HTTP 探测 6677。
- pipeline `--check` 的 T0 探针由 #209 既有代码启动 headless Chrome（端口 53466-53469，临时目录自动清理，进程已退出）；其探针目标明确避开 6677。另观察到**开工前**（13:37）既有的一组 `free-html-lane-b-chrome-87hJCf` Chrome 渲染进程残留（非本次运行产生），按「不终止无关进程」规则未动，仅记录。
- 未 push、未 merge、未 commit、未写 `manifest.json`、未改 DSH 上游（已实测 porcelain 为空）。
