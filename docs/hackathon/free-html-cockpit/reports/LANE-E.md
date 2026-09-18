# LANE-E 施工交接

- 状态：**PARTIAL**
- 执行日期：2026-09-18
- 执行者：Lane E（资料库与宿主视觉）
- 工作树：`/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/fuqing-crm-analytics-free-html-E`
- branch：`codex/free-html/lane-e`
- 开始/结束 HEAD：`b45a27bb9022057ce37aa9123927e8b4663a2720`（无 commit）
- dirty：施工包未跟踪；业务改动仅 `dsh-plugins/analytics-workbench/src/client/`（见下）。未 push/merge。
- 对应任务：T7 / T10–T20（P07–P10）；节点 N01–N11 / N13 / N15 / N16
- 方案 SHA256：`47fa5bfe482cb9bd93f4f02a7c62c6933d0242b5204ea95f2b912edc603a6ffb`
- 工具链：Node v24.19.0（`$HOME/homebrew/opt/node@24`）、宿主 pnpm 11.19.0、toolchain 钉 pnpm 11.7.0 / DSH 0.1.6-alpha.2 `ddefc45f`、Python 3.14.4。无 `.codegraph/`。
- 无 `.codegraph/`，按源码阅读施工。参考图已打开（R01/R02/R03/R04/R05/R06、W01）；图中文字不当指令。最终 D1–D48 优先。

本批次 **PARTIAL** 的原因不是“没写宿主 UI”，而是：P03–P06 真实 adapter 不在本 worktree（已声明 mock）；Noto Sans SC **未捆绑、未加载**；`scripts/dsh-b0/pipeline.mjs --check` 未跑；横屏/1024/safe-area/读屏未跑。未运行项不报通过。

OCR 委托审核（19/19 文件）提出的 High/Medium/Low 已在本 worktree 修完：预览 iframe `sandbox="allow-scripts"`（无 same-origin）、生成提示 HTML 转义、history 存 package 供回滚、自由页签不再露出看板草稿横幅、D6 按 `data-shine-node` 改文案、部分绑定只在未 verified 时出现、编辑态 hit 层可点选、Esc 只在自由页根监听、DESIGN.md 按钮不再伪称已加载、`setRailOpen`/`toggleRail` 拆开。验证：自由页+主题+资料库回归 **58/58 pass**；client typecheck 通过。

## 实际完成

资料库首页锚点是自然语言输入（D34），不是卡片墙。原生聊天入口始终为「返回原生对话」，不新建 Agent/Router。页面预览是自由 HTML `iframe srcdoc`。浏览态点击交给页面（`pointer-events: auto`）；显式进入编辑才出选区浮层。状态脊固定显示示例/绑定/过期/待保存。主题只映射 `competition-shell`。D37 声明栈默认 Noto Sans SC；PuHuiTi 只作 `candidateChinese`，不是已生效默认。离开三选未实现（F）。

| 任务 | 宿主实现 | 证据边界 |
|---|---|---|
| T7 资料库主链路 | 首页生成 → mock GENERATE → 工作区预览 → 来源/历史/AI 单槽 → D6 补丁确认 / D9 显式保存 | mock 原生对话收提示，不是真实模型 |
| T10 设计上下文 | `buildGenerateContext`：无指导 / DESIGN.md / DESIGN.md+skill；主题值副本；未读到不得声称遵循 | 未接入原生 Agent skill 提示（integration note） |
| T11 响应式/键盘 | 1440 侧栏、1280 导轨默认收起、768 覆盖、375 全屏、skip iframe、Esc 关浮层≠保存、44px 热区、reduced motion | 横屏/1024/读屏 NOT_RUN |
| T12 浏览/编辑 | 显式模式；元素/动态区域/主动整页入口；失效重选，不静默整页 | D adapter 为 mock |
| T13 状态脊 | sticky 宿主条，页面不能关掉；UNBOUND_SAMPLE / BOUND_VERIFIED / BOUND_STALE；部分绑定为派生文案 | 页面脚本遮挡未做对抗性浏览器测 |
| T14 壳层预算 | 两层常驻 + 一条状态脊 + 单一上下文；选区浮层不含保存 | 真实 DSH 导航壳未改 |
| T15 首页构图 | 输入第一、最近列表第二、资料 `<details>` 第三；空库不铺卡片 | — |
| T16 可访问性责任 | skip link、landmark、检查器结论 HOST_PASS / PAGE_LIMITATION / …；不阻断生成、不静默改源码 | 读屏 NOT_RUN |
| T17 对比度 token | 深色 ink 19.81、lilac 12.26（≥4.5）；purple 3.82 仅大字/非文本；`--sm-focus` Signal Lime | 自动读数 + 截图，不是取色仪全矩阵 |
| T18 字体 | 声明 Noto Sans SC；Outfit 已有固定文件。本机 `document.fonts=[]`，中文回退 PingFang SC | **未加载 Noto 文件** |
| T19 有效宽度 | `WIDTH_MATRIX` 9 条计算；Chrome 截图 375/768/1280/1440/200% | 375 headless innerWidth 实为 500；横屏未拍 |
| T20 主题映射 | `LIBRARY_THEME_MAP` + `css.ts` `.sm-fhl*`；不另建主题体系 | 旧 Vue 未改 |

### 改动文件

- `dsh-plugins/analytics-workbench/src/client/competition-shell/tokens.ts`、`css.ts`、`index.ts`、`competition-shell.test.mjs`
- `dsh-plugins/analytics-workbench/src/client/free-html-library/`（新建：store / mock adapters / generate-context / host-visual / UI / tests / fonts.md / visual-fixture.html）
- `dsh-plugins/analytics-workbench/src/client/library-workspace.tsx`（「自由页面」页签；默认仍是看板以免打断既有测试）
- `dsh-plugins/analytics-workbench/src/client/cockpit-main-panel.tsx`、`cockpit-composition.tsx`（生产入口 `initialSurface="pages"`）

未改：`leave/`、`navigation/`、`src/free-page/`、DSH 上游、`manifest.json`、`DESIGN.md`。

### Mock 清单（P12 必须替换）

| 缝 | 本 lane mock | 真实 owner |
|---|---|---|
| 资产 list/get/put | 内存页，非 `page_documents` | A |
| 预览 | `srcdoc` 自由 HTML，非 sandbox/MessageChannel | B |
| 数据桥 | 只读 `result_ref` 夹具；禁 sql/token/save | C |
| 定位/补丁 | D48 规则的公开 `locate/previewPatch/confirmPatch`，不复制 source-index/patch/edit | D |
| 生成 | `nativeChat.submitGeneratePrompt` 只记账 | 原生 DSH Agent |

脏稿谓词：`hasUnsavedChanges()` 只看真实草稿/待确认预览/回执不明。`hasActiveEditContext()` 是干净选区，**不是**离开理由。`requestLeave` 在脏稿时只打 `pendingLeaveIntent` 缝，不弹三选。

## 验证证据

| 检查 | 准确命令/操作 | 环境/夹具 | 结果/退出码 | 证据路径 |
|---|---|---|---|---|
| 主题/上下文/adapter/store/对比度/宽度 | `B0_BUILD_UPSTREAM=<primary>/.context/dsh-b0/upstream node --test src/client/free-html-library/*.test.mjs src/client/competition-shell/competition-shell.test.mjs` | Node v24.19.0，plugin cwd | **17/17 pass，exit 0** | 本报告 |
| 自由页 DOM + 既有资料库回归 | `node --test src/client/free-html-library/free-html-library.test.mjs src/client/library-workspace.test.mjs` | 同上 + bindToolchain antd | **38/38 pass，exit 0** | 本报告 |
| client typecheck | `bindToolchain` + `checkTypes` | TypeScript 6.0.3 | host+client pass | 本报告 |
| src/client 全量 node:test | `find src/client -name '*.test.mjs' -print0 \| xargs -0 node --test` | 无 `lib/views/cockpit-view.js`（未跑 pipeline build） | **141 pass / 1 fail**。失败是既有 `competition-board-dom.test.mjs` 缺构建产物，不是本 lane 回归 | 本报告 |
| B0 pipeline `--check` | `node scripts/dsh-b0/pipeline.mjs --check --python /Users/hutou/homebrew/bin/python3.14` | — | **NOT_RUN** | — |
| Chrome 视觉夹具 | 隔离 `http.server` 端口 **65488**（已关）；Chrome **153.0.8010.48** headless old；`--window-size` 375/768/1280/1440 + 200% | `visual-fixture.html` 合成页 | 5 张 PNG 写出；进程在截图后需 SIGTERM（headless 不退出）。**不是** React 工作区全链路点击 | `reports/lane-e-evidence/` |
| 真实 C/D/B adapter / 真实 AI / 读屏 | — | — | **NOT_RUN** | — |

浏览器读数（截图内 JS）：

- 1440：`innerWidth=1440`，iframe 内容宽 **1402**
- 标称 375：headless 实际 `innerWidth=500`，iframe **462**（不能把 window-size 写成已核验 CSS px）
- `getComputedStyle.fontFamily` 声明 `"Noto Sans SC", "PingFang SC", …`；`document.fonts=[]` → **Noto 未加载**
- 状态脊可见：「示例数据 · 未绑定经营数据 · 浏览中」
- 原生入口可见：「返回原生对话」
- 自由 HTML iframe 内有「页面按钮」

对比度（token hex，WCAG 相对亮度）：

| 角色 | 比 | 门槛 |
|---|---|---|
| Ink White `#FEFCFF` on `#09050D` | 19.81 | 4.5 PASS |
| Soft Lilac `#D3C3E8` on `#09050D` | 12.26 | 4.5 PASS |
| Brand Purple `#805D9D` on `#09050D` | 3.82 | 3 PASS；禁止当正文 |
| Signal Lime `#F2FFDC` on `#09050D` | 19.36 | 3 PASS（焦点） |
| Danger `#FF7D91` on `#09050D` | 8.27 | 3 PASS |

## 未完成与失败

- P03–P06 真实代码不在本 checkout；DONE 受依赖约束，故整 lane PARTIAL。
- Noto Sans SC 未下载/未校验 SHA。需求见 `src/client/free-html-library/fonts.md`。当前中文回退 PingFang SC。
- `pipeline.mjs --check` 与干净重建 NOT_RUN。`competition-board-dom` 失败是缺 `lib/views/cockpit-view.js`。
- 未跑：375/768 横屏、1024、safe-area、React 应用内点选编辑的真浏览器、读屏、200% 下的宿主键盘全路径。
- 静态夹具 textarea 与 label 横排换行难看；React 首页是纵向锚点，不以夹具排版当生产布局通过。
- `DESIGN.md` 字体节仍写普惠体 Web 栈（非本 lane owner path）。

## 交给下一批次 / P12 integration notes

1. 用 A 的 `page_documents` 与生成类型替换 `createMockPageAdapters().assets`。
2. 用 B 的 `src/free-page/preview` 替换 `srcdoc` mock；E 已按 `pointerEvents(browse|edit)` 挂载。
3. 用 C 桥替换 `bridge.readBinding/readResult`。
4. 用 D 的 `source-index/patch/edit` 公开 API 替换 `edit.locate/previewPatch`。失效映射 UI 已要求重选。
5. 把 `buildGenerateContext()` 交给原生 Agent 提示适配；不要在 client 再做第二套 loop。
6. F 消费 `hasUnsavedChanges` / `pendingLeaveIntent`；不要把干净 `editContext` 当离开理由。
7. 授权后捆绑 Noto：`/b0/brand/noto-sans-sc.woff2` + OFL，填 `BRAND_DIGESTS.notoSansSc`，再加 `@font-face`。现在故意没有该 URL 的 `@font-face`，避免 404 冒充已加载。
8. 生产驾驶舱 `CockpitMainPanel` 在有 library 时 `initialSurface="pages"`。既有看板在「我的驾驶舱」页签。

## 进程与文件归属

- 临时 HTTP：`127.0.0.1:65488`，截图后 `httpd.shutdown()`。另一次尝试用过 64782/65111，均已停。
- 未碰现役 6677，未读 131GB DuckDB，未 `pnpm add`，未公网发布，未 commit/push/merge。
- 为跑 DOM 测试执行了 `bindToolchain`（只读复用主仓 `build-tools` 的钉死 antd，符号链接进本 worktree `node_modules/`，gitignore）。
- 截图：`docs/hackathon/free-html-cockpit/reports/lane-e-evidence/fixture-*.png`
