# LANE-D · 源码定位与编辑

- 状态：**DONE**（本 lane owner 范围：确定性 fixture 覆盖 D48 六条守卫 + D6/D9 提交语义。真实 AI、真浏览器、A 持久化接缝未运行，不记通过）
- 执行日期：2026-09-18
- 执行者：Lane D 独立施工（Grok Build）
- 工作树：`/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/fuqing-crm-analytics-free-html-D`
- 分支：`codex/free-html/lane-d`
- 开始/结束 HEAD：`b45a27bb9022057ce37aa9123927e8b4663a2720`（未 commit）
- dirty：原未跟踪施工包 + 本 lane 新增 `src/free-page/{source-index,patch,edit}/` 与 `tests/free-page-edit.test.mjs`；无已跟踪文件 diff
- 任务：T6 / T29；节点 N08–N11 / N13（N08 可见模式接缝只暴露 API，UI 属 Lane E）
- approved-plan SHA256：`47fa5bfe482cb9bd93f4f02a7c62c6933d0242b5204ea95f2b912edc603a6ffb`（对本文件字节核验一致）
- 工具链：测试使用 `/Users/hutou/homebrew/opt/node@24/bin/node` **v24.19.0**（toolchain `node_major: 24`）。宿主默认 `node` 为 v25.8.2，未用来跑本 lane 测试。pnpm 宿主 11.19.0 / 钉 11.7.0，未升降级。无 `.codegraph/`。
- 现役 6677：未触碰。未 push / merge / commit。未改 DSH 上游、`manifest.json`、`library-board-client.mjs`、`html-sandbox.mjs`、`pipeline.mjs`。

## 实际完成

本 worktree 无 P03/P04 代码。按 PARALLEL-6 / COORDINATOR-KICKOFF 用 `fixtures/frozen-contract-v0.json` 与 `fixtures/d48-scope.fixture.json` 开工，A 的 `page_documents` 用内存 mock。

| 行为 | 位置 |
|---|---|
| 源码索引：`data-shine-node` 精确范围、`data-shine-region` 所属区域、重复/伪造/过期 token、禁止静默整页 | `src/free-page/source-index/index.mjs` |
| 补丁预览：影响分析、共享 CSS/JS → `SCOPE_REQUIRES_CONFIRMATION`、外源 HTML 拒绝、空包拒绝 | `src/free-page/patch/index.mjs` `impact.mjs` |
| D6 PATCH 确认 / D9 显式 SAVE；取消、关面板、退出编辑、清选区不落盘；过期/丢回执保留源码；幂等重复确认不第二版 | `src/free-page/edit/index.mjs` `patch/store.mjs` |
| Lane E 公开 adapter；干净 `edit_context` 不是 dirty（D42 输入，离开协调属 F） | `src/free-page/edit/adapter.mjs` |
| 原生 Agent 上下文 payload（`runtime: native-dsh`），无第二聊天 loop | `createEditController().agentContext()` |
| D48 七个 fixture 分支的确定性断言 | `src/free-page/edit/d48-scope.test.mjs` |
| 纳入当前 pipeline 已扫描目录 `tests/` 的入口（不改 `pipeline.mjs`） | `tests/free-page-edit.test.mjs` |

D6 与 D9 分开：PATCH 必须先有 `PENDING` 预览再用原 `idempotency_key` 确认；SAVE 只保存宿主内存草稿。同一次确认不会两条路径各写一版。

## 验证证据

| 检查 | 准确命令/操作 | 环境/夹具 | 结果/退出码 | 证据路径 |
|---|---|---|---|---|
| owner 单测 | `/Users/hutou/homebrew/opt/node@24/bin/node --test dsh-plugins/analytics-workbench/src/free-page/source-index/source-index.test.mjs dsh-plugins/analytics-workbench/src/free-page/patch/patch.test.mjs dsh-plugins/analytics-workbench/src/free-page/edit/edit.test.mjs dsh-plugins/analytics-workbench/src/free-page/edit/d48-scope.test.mjs` | Node v24.19.0；`frozen-contract-v0.json`；`d48-scope.fixture.json`；`createMemoryPageStore` | 34 pass / 0 fail；exit **0** | 本报告命令记录 |
| pipeline 可见入口 | `/Users/hutou/homebrew/opt/node@24/bin/node --test dsh-plugins/analytics-workbench/tests/free-page-edit.test.mjs` | 同上，再导出上述 34 项 | 34 pass / 0 fail；exit **0** | `tests/free-page-edit.test.mjs` |
| OCR delegate 审核后返修 | 无标记插入、区域 JS 整页、连续 mutate 偏移、D9 原键、kind 校验、`@media` CSS | 同上 | 已修并纳入 34 项；完整 pipeline 仍 **NOT_RUN** | 见下方「审核返修」 |
| 语法 | `node --check` 全部本 lane `.mjs` | Node v24.19.0 | exit **0** | — |
| 完整 `scripts/dsh-b0/pipeline.mjs --check` | 未执行 | 需 pinned upstream / Python 3.14 全套 | **NOT_RUN** | — |
| 真浏览器 iframe / 选区点击 | 未执行 | P12 | **NOT_RUN** | — |
| 三类真实 AI 样本 | 未执行 | P13 | **NOT_RUN** | — |
| Lane A `page_documents` 新连接/CAS | 未执行 | A 未在本树落地 | **NOT_RUN**（用内存 mock） | `patch/store.mjs` |
| 改 `manifest.json` | 禁止 | — | 未改 | — |

D48 覆盖（fixture id → 断言）：

| id | 结果 |
|---|---|
| static-precise | 只改 `n_title` 文本；canvas/js 字节不变；D6 后 version=2 |
| dynamic-region | 整区替换 canvas；`n_title`/`n_lede` 仍在 |
| mapping-stale | `MAPPING_STALE`；草稿保留；整页救场 proposed 不能提交 |
| forged-marker | 同 stale；`n_forged` 不进可信 `nodes` |
| user-whole-page | `user_switched: false` 拒绝；`switchWholePage()` 后才允许 |
| shared-css-expansion | 改 `h1{...}` 无确认 → `SCOPE_REQUIRES_CONFIRMATION`；匹配 `impact_hash` 后才 PENDING |
| cancel-expired-fail | 取消 / 过期 / 空包失败均 version=1，源码仍为「示例标题」 |

另测：重复 `data-shine-node`、过期 `mapping_token`、D6 幂等二次确认仍为 v2、D9 退出不保存、干净选区 `isDirty=false`。

## Mock / fixture 清单

- `docs/hackathon/free-html-cockpit/fixtures/frozen-contract-v0.json`（消费，未改语义）
- `docs/hackathon/free-html-cockpit/fixtures/d48-scope.fixture.json`（消费，未改语义）
- `src/free-page/source-index/page-fixture.mjs`：在冻结合同包之上补 `n_lede` / HTML 内伪造标记 / 共享 `h1` 规则，供 D48 分支
- `createMemoryPageStore`：替代未落地的 Lane A 存储（CAS、幂等、预览生命周期）
- 无 Lane B iframe/MessageChannel；无 Lane E 宿主 UI；无原生 DSH tool 注册

## 未完成与失败

无本 lane 单测失败。以下不是本 lane DONE 条件，但必须标明未运行：

- P12：真实 iframe 选择 → 补丁 → 确认 → 重开
- P13：真实模型三类样本
- A 正式 OpenAPI/类型替换 `frozen-contract-v0`
- `pipeline.mjs` 尚未扫描 `src/free-page/`（见 integration notes）
- N08 浏览/编辑可见切换、选区浮层 UI（Lane E / P08）

## 审核返修（OCR delegate，已修）

High：选区外无标记 HTML 插入拒绝；区域 JS 改成 `document.body.*` 走 `SCOPE_REQUIRES_CONFIRMATION`；本地连续编辑重绑 range；D9 丢回执复用原 `save_*` 键。  
Medium：`selection.kind` 必须等于节点 kind；`canvas_html_unchanged` 按 canvas 区域节点而非写死 `r_chart`；`open`/`applyLocalDraft` 捕获索引抛错；`@media` 等 at-rule 视为共享 CSS。

## 交给 P12 的 integration notes

1. **pipeline**：`scripts/dsh-b0/pipeline.mjs` 目前只递归 `src/board-spec`、`src/client`、`src/competition-agent`、`tests`。本 lane 把同一套测试再导出到 `tests/free-page-edit.test.mjs`，以便现有扫描能跑到。P12 应把 `src/free-page` 加入扫描，避免双份注册。
2. **存储**：把 `createMemoryPageStore` 换成 A 的 `page_documents`；保持 `GENERATE|PATCH|SAVE|ROLLBACK`、`PENDING|APPLIED|CANCELLED`、原幂等键、CAS。`INVALID_PAGE` 不要写成 `INVALID_BOARD`。
3. **Lane E**：只 import `src/free-page/edit/adapter.mjs`。不要把 `library-board-client.mjs` 的离开谓词拷到自由页。`hasActiveEditContext` ≠ dirty；dirty = 草稿≠已存 **或** 待确认 PATCH **或** `RECEIPT_UNCERTAIN`。
4. **原生 Agent**：`agentContext()` 只提供选区源码摘录与范围约束。N10 接现有 DSH session；不要新建 Router。工具名/注册不在本 lane owner 内。
5. **整页**：只能 `switchWholePage()` / `user_switched: true`。定位失败返回 `MAPPING_STALE` 且 `widen_to_whole_page: false`。共享 CSS/JS 用 `SCOPE_REQUIRES_CONFIRMATION` + 匹配 `impact_hash`，不能用整页重生成救场。
6. **合同**：未发明第二套绑定状态或操作集。模块内 `free-page-source-index/v1`、`free-page-edit-context/v1` 是定位/上下文实现 schema，不是资产 `free-page/v1` 的破坏性分叉。A 落地后改引用生成类型。
7. 不要改 `src/board-spec/html-sandbox.mjs`。

## 进程与文件归属

- 未启动临时服务或端口。
- 现役 6677 未变。
- 未安装依赖、未访问 131GB DuckDB、未写凭据。
- 无本地 commit 授权，未提交。
