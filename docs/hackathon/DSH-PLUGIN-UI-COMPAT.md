# DSH 插件 UI 兼容（本轨）

> 下文保留并行候选交接时点；集成后的修复与实际验收以 [Codex 集成记录](./DSH-COMPAT-INTEGRATION-2026-09-09.md) 为准。

日期：2026-09-09。分支：`codex/dsh-plugin-ui-compat`。工作树：`.worktrees/dsh-plugin-ui-compat`。基线：`f818fca`（#110）。固定上游：`d347e703908d0406b7a7ef80e3a0e594d86b2215`。状态：`LOCAL_CANDIDATE / NATIVE_STACK_NOT_REHOSTED`。

本文件记录业务插件与固定 DSH 原生壳的 UI 关系、一致性矩阵、本轨修复与未关闭项。不修改 DESIGN.md 品牌基准，不把源码未改、插件可加载或单项测试通过写成完整兼容通过。

## 原生壳与业务入口

固定上游插槽树（`docs/subsystems/slots.md` @ d347e70）与本插件实际登记：

| 原生表面 | 插槽 | 基数 | 本插件 | 覆盖风险 |
|---|---|---|---|---|
| 侧栏品牌标 | `sidebar.brand.mark` | single | `priority: -10` 伸美帽子 | 替换官方 FishLogo，DESIGN 要求保留原 Logo |
| 侧栏品牌名 | `sidebar.brand.name` | single | `priority: -10`「伸美 · B0」 | 替换官方词标 |
| 工作区/会话列表 | `sidebar.workspaces` | — | 不登记 | 原生保留 |
| 新会话 / 折叠 | SidebarRoot 自有按钮 | — | 不登记 | 原生保留 |
| 设置 | `sidebar.settings` 及子槽 | — | 不登记 | 原生保留；启用/停用未在本轨原生 Settings 验证 |
| 侧栏底入口 | `sidebar.footer.action` | list | `id=shine-mage.analytics-b0.footer` | 增量，不替换 Settings |
| 聊天 / 输入器 / hero preset | `conversation*` | — | 只加 `conversation.input.dock` 任务状态 | 不另造聊天界面 |
| 工具卡 | `tool.call.toolview` | keyed | 仅 `analytics_b0_query` / `analytics_channel_followup_query` / `analytics_first_purchase_query` | 不占用 `bash`/`skill` 等原生 key |
| 右侧详情 | `details` / `conversation.details.tool` | single | 不替换 | 原生保留 |
| 业务弹层 | `shell.overlay` | list | `id=shine-mage.analytics-b0.overlay` | 增量；宽驾驶舱继续用 `<dialog>`，不用 380px 原生 Modal |
| 问数 / 保存 / 驾驶舱 | overlay 内面板 + 查询卡动作 | — | HTTP overlay 或 finite mock | 不新增 Vue 页面 |

原生消息流、发送/停止、模型选择、Session log、Trajectory 仍由 DSH 拥有。业务事实只经校验后的 run 快照渲染。

## UI 一致性矩阵

实测对象：1）现有 4318 只读壳与 HTTP overlay（修复前插件）；2）隔离 HTML 夹具（修复前/后 CSS）。DSH 正文 `font-size` 16px，Composer 14px/24px，Settings 行约 42px / 半径 12px，Button 原子 36px / 半径 18px，Modal 半径 24px / layer-2。

| 项 | 原生 DSH | 修复前插件 | 本轨 | 证据 |
|---|---|---|---|---|
| 字体 | `--dsw-font-family`，PingFang SC 回退 | `font:inherit`，查询卡写死 16px | 查询卡 `--dsw-font-base-16`，控件 `--dsw-font-s-14` | 夹具 after；`plugin-ui-native-chrome` |
| 颜色 | `--dsw-alias-*` | 部分 `line-primary` / `currentColor` | layer-2、mask-1、border-l3、error-primary | 深浅夹具截图 |
| 间距/圆角 | Button 18px 胶囊，Modal 24px | 按钮 8px、弹层 16px、min-height 44px | 按钮 36×18，弹层 24px | before 44px vs after 36px |
| 主题 | ThemePresenter + `data-ds-dark-theme` | 跟随 token，backdrop 40% 无 blur | mask-1 + `--dsw-mask-blur` | after dark 1440 |
| 响应式 | 390/768/1440 | 480px 才缩 padding | 保留 480；夹具 390/768/1440 无横向溢出 | after 三档 |
| 键盘焦点 | 原生 outline / Input focus 品牌色 | `outline:2px currentColor` | `--dsw-alias-brand-primary` 2px | after focus-close，outline `rgb(15,17,21) solid 2px` |
| 弹层关闭/返回 | Modal Escape；overlay 自管 | mock overlay 有 Tab 陷阱；HTTP overlay 无 | 两者共用 `trapDialogTab`；关闭归还入口焦点 | `asset-overlay` 源码断言 |
| 滚动 | 原生列滚动 | dialog `overflow:auto` | 保留；max-height `100dvh-48px` | 夹具无 pageOverflow |
| 错误状态 | StateDot / 失败文案 | 错误卡无 grid 跨度，窄条 | `grid-column:1/-1` + error 色 | after 错误卡宽 1052px @1440 |
| 触控 44px | 原生 Button 36px | DESIGN/交互稿 44px | **跟随上游 36px**，冲突交 Codex | INTEGRATION.md |

DESIGN.md 的 Deep Plum / Outfit / 44px 不套到 DSH 壳。伸美 Logo 仍走品牌槽，249:45。

## 本轨修复

- 插件 chrome 改走 DSH token 与 Button/Input/Modal 几何，不引入 Vue 色板。
- HTTP overlay 补 Tab 陷阱；错误板块拉满栅格，避免挤成竖条。
- 驾驶舱/已保存分析视图标记 `data-dsh-native-chrome`。
- 未导入 `@deepseek-ai/dsh-client-ui-primitives` 运行时组件：CJS 测试种子与 CSS modules 会扩大公共接线；样式对齐先行。

## 生命周期（本轨能证明的）

| 项 | 结果 | 限制 |
|---|---|---|
| 登记 8 个槽；卸载 dispose 清空 | PASS，假 Cordis | 不是 Settings 开关 |
| 同一 ctx 二次 `apply` 得到 16 条登记 | PASS，说明 Host 不得双挂 | 真 Cordis 重复 list id 行为未跑 |
| 4316 Loader 启用/停用 | **NOT RUN** | 现网占用 4316，禁停 4315–4319 |
| Settings 插件页停用后原生工具卡 | **NOT RUN** | 需隔离 DSH + Codex 启动器端口 |
| 卸载后 SQLite 资产仍在 | **NOT RUN** 本轨 | 只读打开过 4318 overlay，未删库 |

## 业务回归（隔离）

| 项 | 结果 | 环境 |
|---|---|---|
| 查询卡 8 状态 + 渠道/首购卡 | PASS | 编译后 DOM |
| 保存分析 / 加入驾驶舱 / 409 只重试加入 | PASS | JSDOM mock HTTP |
| 驾驶舱预览/放弃/拖动/撤销 | PASS | JSDOM |
| 脱离会话可读 + 403 不泄漏 | PASS | `sessionless-view-dom` / cockpit-view |
| 真实 worker 查询 → 保存 → 驾驶舱 | **NOT RUN** | kernel/gateway 写死 4315–4318 |
| 真实模型 | **NOT RUN** | 授权禁止 |

## 需要 Codex / 隔离原生栈的项目

1. `serve.mjs` / `gateway.mjs` / `analytics_runtime.py` / 插件 kernel URL / Seatbelt 端口参数化到 4335–4339。
2. 在该栈上重跑 Settings 启用/停用、重复加载、卸载清理、问数→保存→驾驶舱、无会话重读。
3. 决定是否把 `<dialog>` 换成原生 `Modal`（默认 380px，需 className 加宽）。
4. DESIGN.md 44px 与上游 36px 的基准选择；不要由本轨改 DESIGN.md。
5. 测试种子若要真正 `import` Button，需 Codex 统一改 harness。
