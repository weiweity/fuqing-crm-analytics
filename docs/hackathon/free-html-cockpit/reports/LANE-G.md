# LANE-G 施工交接

- 状态：**DONE**（本 lane 责任范围；P13 真模型三场景不在本 lane，未做也未声称）
- 执行日期：2026-09-18
- 执行者：Lane G（原生页面生成工具）
- 工作树：`/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/fuqing-crm-analytics-free-html-G`
- branch：`codex/free-html/lane-g`
- 开始/结束 HEAD：`d6b57452d8e44b57ca528d1fa74f99896d303345`（= origin/main，#209 已合；无 commit）
- dirty：施工包（PARALLEL-3.md / prompts/）未跟踪沿用基线；业务改动 4 个源文件 + 1 个新测试 + 2 个常量/类型对 + 3 个测试清单行，见下。未 push/merge。未授权未 commit。
- 对应任务：生产接缝「生成工具」（PARALLEL-3 G 列）；方案冻结快照 SHA256 `47fa5bfe482cb9bd93f4f02a7c62c6933d0242b5204ea95f2b912edc603a6ffb`
- 工具链：Node v24.19.0（`$HOME/homebrew/opt/node@24`）、pnpm 11.7.0（钉）、DSH 0.1.6-alpha.2 `ddefc45f`（`bindToolchain` 全链核验通过）、TypeScript 6.0.3。无 `.codegraph/`，按源码阅读施工。
- 未触碰 6677（未探测/未 reload/未 stop）；未读 131GB DuckDB；未装浮动依赖（`bindToolchain` 只读复用主仓 `build-tools` + 固定 upstream，符号链接进本 worktree `node_modules/`，gitignore）；未改 DSH 上游。

## 实际完成

生产 `generate()` 现在从原生 Agent 交付工具拿到 `{html,css,js,resources,node_map}`，不再回退 `samplePackage()`。链路：浏览器发提示（携带 page-gen 标识）→ 原生 Agent 调 `free_html_page_generate` 交付包 → host 工具执行器按 `free-page/v1` 合同校验 → `presentationMeta` 把回执带到浏览器工具卡 → 工具卡把包递给 waiter → 等待中的 `nativeGenerate` 恢复 → 既有隔离 HTTP `generateAndConfirm` 写保存库（Lane H 边界，未改其契约）。

| 件 | 实现 | 位置 |
|---|---|---|
| 交付工具合同 | `PAGE_GENERATE_TOOL_NAME='free_html_page_generate'`、`PAGE_TOOL_RESULT_SCHEMA='free-page-tool-result/v1'`、`PAGE_REQUEST_ID_PATTERN` | `src/competition-agent/page-family.mjs`（+.d.mts） |
| 工具执行器 | 参数=页面源码包+request_id；用 free-page 合同 SSOT `parsePagePackage` 校验（超限/未知字段/非法 node_map 全拒）；回执 `PACKAGE_RECEIVED`/`REFUSED`；无 SQL/token/外联/fetch/子进程；不保存不转发 | `src/competition-agent/page-tools.mjs`（+.d.mts） |
| 工具注册 | board pack 门内、board 工具之后注册 `free_html_page_generate`；`presentationMeta: (_args, value) => value`（回执 canonical 值进工具卡 meta，board 已验证模式） | `src/competition-agent/apply.ts:107-123` |
| 浏览器 intake | `createPagePackageWaiter()`：`deliver/wait/cancelAll/pendingCount`；支持 Error 拒收结果、AbortSignal 取消、超时（默认 180s，防止 busy 永挂）；`createNativePageGenerate` 在有 waiter 时铸造 `page-gen-<uuid>`、提交提示后等待交付 | `src/client/free-html-library/native-generate.mjs:41-117`（+.d.mts） |
| 工具卡 | 从 `block.meta`（`presentationMeta` 通道）验收 `free-page-tool-result/v1`：`PACKAGE_RECEIVED`→`extractPagePackage` 领包并 `deliver`；REFUSED→带拒收码报错 deliver；按 `callId` 幂等（一次交付）；不渲染源码、不保存 | `src/client/index.tsx` `PagePackageToolCard` |
| index.tsx 生成段 | `pagePackageWaiter` 创建+dispose 取消；`submitPrompt` 提示词改为指示 Agent 调用交付工具并逐字回填 request_id；toolview 注册新卡 | `src/client/index.tsx` |
| 未改 | `leave/`、`openCockpitPanel`、`dsh-dev`、DSH 上游、`library-workspace.tsx`、`live-adapters.mjs`、`store.mjs`、Lane H 的 `page-http.mjs` 契约 | — |

边界说明：

- **没有第二套运行时**。`store.generate` / `documents.generateAndConfirm` / free-page 合同全部复用 #209 已合代码；本 lane 只补「Agent→包→store」接缝。
- **无包不回退**。waiter 路径超时/取消/拒收一律抛 `NATIVE_GENERATE_UNAVAILABLE`，`store.generate` 失败路径保留输入（既有行为，p12-live-adapters 已测）。
- **禁止外联**。工具执行器无 fetch/child_process/COMPETITION_HTTP；`refuseLivePort` 继续由 `page-http.mjs` 守 documents/result HTTP（Lane H 边界，未触碰）。测试含源码负测断言。
- **request_id 威胁模型**：模型理论上可编造一个从未提交的 page-gen id 并自答（无等待者时 `deliver` 返回 false，无副作用；有等待者时包会被采信）。工具执行器无法区分「用户消息里的 id」和「模型编造的 id」——DSH 工具参数面拿不到同会话的用户消息原文，这是 host 侧既有限制（board 工具的 edit_context 同样靠服务端会话绑定缓解）。缓解：request_id 只是路由键，不授权任何数据；页面写入仍需用户在工作台检查保存。已在 integration notes 记录，P13 真模型验收时观察。

## 验证证据

所有命令在 `dsh-plugins/analytics-workbench/` 下执行；`B0_BUILD_UPSTREAM=/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/fuqing-crm-analytics/.context/dsh-b0/upstream`；`bindToolchain(..., 主仓build-tools)` 只读复用。

| 检查 | 准确命令 | 环境/夹具 | 结果/退出码 |
|---|---|---|---|
| Host+Client 全量 typecheck | `bindToolchain`+`checkTypes`（真实 toolchain.mjs 入口） | 钉 TS 6.0.3，strict | **PASS，exit 0** |
| 插件构建 | `node build.mjs $B0_BUILD_UPSTREAM 主仓/build-tools` | esbuild 0.25.12 | **PASS，exit 0**（client bundle 含 free_html_page_generate / free-page-tool-result/v1） |
| 本 lane 专项 | `node --test test/lane-g-delivery.test.mjs` | 隔离 fetch 夹具 + 编译产物 vm 加载 | **6/6 pass，exit 0，140ms** |
| src 全量回归 | `find src/client src/competition-agent -name '*.test.mjs' \| xargs node --test` | Node 24 | **285/285 pass** |
| test/ 全量回归 | `find test -name '*.test.mjs' \| xargs node --test` | 编译产物 | **193/193 pass** |
| 负测：pack off | vm 加载 `lib/client.js`，`__SHINE_BOARD__: false` | — | **page cards = 0，exit 0** |

专项测试覆盖（`test/lane-g-delivery.test.mjs`，任务书 3/4 条逐条对应）：

1. 有效包→`PACKAGE_RECEIVED` 回执，`published:false`，含「原生Agent标题」。
2. 空 html/缺 request_id/无会话→`REFUSED`；源码负测断言无 `fetch(`、`:6677`、`child_process`、`COMPETITION_HTTP`。
3. 假 Agent 路径：`store.generate` 挂起等 waiter → deliver `AGENT_PACKAGE`（与 SAMPLE_PACKAGE 不同，含「原生Agent标题」）→ 假 documents HTTP 写库成功，`binding_state=UNBOUND_SAMPLE`，「有包就能 generate」。
4. 拒收路径：`cancelAll`（模拟拒收）→ generate 失败、输入「保留我」保留、`current=null`。
5. 超时路径：丢失交付→20ms 超时→`NATIVE_GENERATE_UNAVAILABLE`。
6. 编译产物：工具卡注册在 `tool.call.toolview`、`inject().pagePackageWaiter` 接通、运行态文案、成功回执 deliver 后 `pendingCount=0`。

既有测试清单更新（新增 tool 是有意行为，非回归）：

- `test/plugin-ui-lifecycle.test.mjs`：toolview 5→6、key 列表 +`free_html_page_generate`
- `test/tool-card-dom.test.mjs`：key 列表同上
- `test/loader.test.mjs`：host 注册工具列表 +`free_html_page_generate`

## 未完成与失败

- **P13 真模型三场景**：按 lane 边界未做。真实模型是否稳定回填 request_id、是否一次调对工具，需真实额度观察（见上文威胁模型 integration note）。
- **6677 现场浏览器链路**：本 lane 未跑（PARALLEL-3 禁探测 6677）。端到端真实浏览器验证属 P12/协调者收口。
- `scripts/dsh-b0/pipeline.mjs --check`：NOT_RUN（Lane E/F 同口径；本 lane 未改构建配置与合同文件，构建已单独验证）。
- 起初一版测试因微任务时序断言失败（waiter 注册晚于 submitPrompt 同步返回），已修为 flush-until-pending；无生产代码改动。

## 交给下一批次 / integration notes

1. **Lane H**：成功路径已通到 `documents.generateAndConfirm`（本 lane 测试用 `createIsolatedFetch` 假 HTTP 测通）。你接隔离 HTTP 真配置时无需改本 lane 代码；`store.mjs` 的 `http_not_configured` 失败路径保持不变。
2. **Lane K**：waiter dispose 时 `cancelAll()` 已挂 `ctx.effect`；leave 事务与生成中页面的交互你侧现有 `hasUnsavedChanges` 谓词未受影响（生成中 store.busy=true，无脏稿）。
3. **协调者**：三 lane 合并时 index.tsx 冲突预期在 toolview 注册段与 pageStore 段；本 lane 改动已收窄到生成/tool 段，未动 leave/openCockpitPanel。toolview key 清单 3 个测试的更新行如与 H/K 冲突，以「+free_html_page_generate」为准。
4. **P13/P12**：真实模型验收时观察 request_id 回填；若模型频繁编造 id，可在提示词强化或升级为服务端会话绑定（需 DSH 工具面提供用户消息上下文，本钉版本无）。
5. 无 commit：以完整工作树交接；改动清单见 `git status --short`。

## 进程与文件归属

- 无临时服务/端口（测试全部进程内假 fetch + vm 编译产物加载）。
- 一次测试进程因泄漏 waiter 计时器挂 180s，已定位并修复测试时序（非生产代码问题）；无遗留进程。
- 现役 6677（PID 83542）未探测未触碰；15173/8000/18082 未动。
- `node_modules/` 内符号链接（bindToolchain）与 `lib/` 构建产物均为 gitignore 构建中间物，不属交付改动。
