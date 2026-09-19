# DSH 插件 UI 兼容

现役对照 [STATUS](../../STATUS.md)：origin/main **`22a0028f`**（[#210](https://github.com/weiweity/fuqing-crm-analytics/pull/210)）。本分支 VERSION **0.9.0.9** 候选。DSH **0.1.6-alpha.2**（`ddefc45f`）。不改上游源码。不把插件可加载或单项测试写成整壳兼容通过、正式 release 或 6677 已 reload。

插槽登记以 `dsh-plugins/analytics-workbench/src/client/index.tsx` 与 `shine-brand` 为准；细节见 [workbench README](../../dsh-plugins/analytics-workbench/README.md)。

## 原生壳与业务入口（现役）

| 原生表面 | 插槽 | 基数 | 现役登记 | 覆盖风险 |
|---|---|---|---|---|
| 侧栏品牌标 | `sidebar.brand.mark` | single | workbench `priority: -10` | 盖官方标 |
| 侧栏品牌名 | `sidebar.brand.name` | single | shine-brand `priority: -10` | 盖官方词标 |
| 欢迎页品牌标 | `conversation.hero.brand.mark` | single | workbench `priority: -10` | 盖官方欢迎标 |
| 工作区/会话列表 | `sidebar.workspaces` | — | 不登记 | 原生保留 |
| 新会话 / 折叠 | SidebarRoot 自有按钮 | — | 不登记 | 原生保留 |
| 设置 | `sidebar.settings` | — | 不登记；账户菜单点原生触发钮 | 原生 overlay 必须 `position:fixed` 出侧栏，侧栏不得 `isolation` |
| 侧栏底入口 | `sidebar.footer.action` | list | `shine-mage.account.login` order=10；`shine-mage.account.theme` order=11 | 增量，不替换 Settings。收起后 `:has(.sm-login[data-wide="0"])` 把 footer 叠成 rail |
| 驾驶舱 / 数据员工 | `sidebar.panellist` + `main` | keyed | `cockpit` / `staff` | 增量面板 |
| 聊天输入器 | `conversation.input.dock` | list | `shine-mage.analytics-b0.run-status` | 任务状态；空会话不造聊天 |
| 生成驾驶舱 | `conversation.composer.dock` | list | `shine-mage.analytics-b0.generate-cockpit` | 仅 composer 变体挂载；空 hero 不出现 |
| 工具卡 | `tool.call.toolview` | keyed | 问数 / 渠道后续 / 首购 / 组板 generate+edit | 不占用 `bash`/`skill` |
| 右侧详情 | `details` / `conversation.details.tool` | single | 不替换 | 原生保留 |
| 业务弹层 | `shell.overlay` | list | `shine-mage.account.menu`；`shine-mage.analytics-b0.overlay`；可选 `shine-mage.cockpit-composition` | 增量。账户菜单含比赛看板外链与设置 |
| 问数 / 保存 / 驾驶舱 | overlay 内面板 + 查询卡 | — | HTTP overlay 或 finite mock | 不新增 Vue 页面 |

原生消息流、发送/停止、模型选择、Session log、Trajectory 仍由 DSH 拥有。alpha.2 会话用 `retain({ source: 'mainView' })`，没有 `ISessions.open` / `clear` / `SessionListState.current`。业务事实只经校验后的 run 快照渲染。

比赛看板不进 DSH：登录菜单 `http://127.0.0.1:15173/` 新标签打开独立前端。

## 现役 chrome 约定

- 侧栏灰玻璃、主聊天纯白；发送/停止统一品牌色（含「停止生成」）。
- 登录未登录显示「未登录」；本机 `localStorage` 写入显示名称后显示名字/飞书。不是飞书 OAuth。
- DESIGN.md 的 Deep Plum / Outfit / 44px 不套到 DSH 壳。按钮跟上游 36px。
- 侧栏驾驶舱 `main` 是独立二级页产物柜（本会话 HTML／看板／CSV）；页头「编辑」留在本页，侧轨调整布局／回退。HTML `[data-shine-node]` 悬停仅视觉。
- 证据：`plugin-ui-native-chrome`、`plugin-ui-lifecycle`、`account-identity`。不是浏览器 UAT、不是 Figma 过关。

## 2026-09-09 候选附录（不是现役）

当时分支 `codex/dsh-plugin-ui-compat`，基线 `f818fca`（#110），上游 `d347e70`。footer 还是 `shine-mage.analytics-b0.footer`，聊天只加 `conversation.input.dock`，状态 `LOCAL_CANDIDATE / NATIVE_STACK_NOT_REHOSTED`。集成交接见 [DSH-COMPAT-INTEGRATION-2026-09-09.md](./DSH-COMPAT-INTEGRATION-2026-09-09.md)。不要用下表改现在的插件。

| 当时表面 | 当时登记 |
|---|---|
| `sidebar.footer.action` | `shine-mage.analytics-b0.footer` |
| `conversation*` | 只加 `conversation.input.dock` 任务状态 |
| `shell.overlay` | `shine-mage.analytics-b0.overlay` |
| 工具卡 | 问数 / 渠道后续 / 首购 |

当时矩阵：查询卡走 `--dsw-font-base-16`，按钮 36×18，弹层 24px，跟随上游 36px 而不是 DESIGN 44px。生命周期假 Cordis PASS；Settings 停用、4316 Loader、真实 worker **当时 NOT RUN**。
