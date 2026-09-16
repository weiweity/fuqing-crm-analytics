# S5 验收入口与 G6 交接（2026-09-15）

当前可访问入口。4325／18083 是 9 月 10 日历史候选，**不是**现在的 UAT。G6 齐套于 2026-09-16 交接确认；U1 已由用户本人反馈。

## 可用入口（loopback）

| 入口 | URL | 现在 | 说明 |
|---|---|---|---|
| 驾驶舱（DSH 原生壳） | http://127.0.0.1:6677/ | 听着；未带会话 cookie 为 401 | 已有 Chrome 会话可直接打开。侧栏「我的驾驶舱」，底栏「我的驾驶舱」「比赛看板」 |
| 比赛看板（独立 Vue） | http://127.0.0.1:15173/ | 200 | 新标签打开，独立登录，不内嵌。只作入口探活，**不是** T15 运营路径 |
| 旧 CRM API | http://127.0.0.1:8000/docs | 200 | 只给比赛看板 |
| 合成 BoardSpec HTTP | http://127.0.0.1:18082/ | 需业务 token | 驾驶舱写板用；无模型也能读已存板 |

合成范围：看板数字来自合成诊断结果，证据块标 SYNTHETIC。不是真实经营数据。归档 DuckDB（约 131GB）禁止打开／复制／改写／SQL。

## 当前已存板（只读核过）

| 板 | ID | 版本 | 块 |
|---|---|---|---|
| 说明板 | `board_6e9b59dfe3e845328ac0fcf0cd8d1acc` | v15 | TEXT + 两块 METRIC |
| 原板 | `board_f8b8d7d3926e47309e83da7a7f047c47` | v9 | METRIC×2、EVIDENCE、BAR、LINE、TABLE |
| G1 新板 | `board_a9bdb747bd6948708d7c152db7b5b9ab` | v9 | 六类；G2 后 G3 布局确认写入；METRIC 副标题仍含 G2-409-winner |

说明板与原板绑同一 `result_diag_13a0010…`。UAT 默认只读这两块，不含 G1 新板。要练确认保存，请生成**新板**。

## 本人 UAT（U1）— 请逐条回「通过」或卡住位置

1. **分析师**：6677 打开已有会话 → 侧栏／底栏进驾驶舱 → 说明板 v15 与原板 v9 能打开；BAR 文案里的 410／305 仍在；改图表类型若只预览再取消，版本不变。
2. **运营**：仍在 6677 驾驶舱 →「人群行动」。核对合成候选与草稿；自动发送不可用。本实例若没有旧 4325 草稿，只验入口可达和发送禁用，不编造草稿 ID。**不要用 15173 代替这条。**
3. **老板**：驾驶舱在无新对话、不靠模型时仍能读已存板；合成标记清楚，不把样例当本月 GSV。

15173 只确认：新标签打开、独立登录、DSH 不内嵌。它不是运营验收。

2026-09-16 用户对上列三条路径明确「通过」。Agent 不代签；T15／U1 按该口头确认记账。不是公网或真实经营验收。

## 公开属性与拒绝边界（G6）

目录 SSOT：`dsh-plugins/analytics-workbench/src/board-spec/component-catalog.json`，`board-components/v1`。细则见 [插件 README](../../dsh-plugins/analytics-workbench/README.md)。

- 六类可改表现属性；未知属性、脚本、facts、查询条件拒绝。TABLE **没有** `show_values`，提交该属性应为 `COMPONENT_PROPERTY`。
- 布局重叠预检 `COMPONENT_OVERLAP`，不自动改块、不授权 bash。
- 确认才写；取消不撤已应用版本；陈旧 `base_version` 为 409；幂等键重复确认不增版本。
- 模型没有确认写权限。无活动会话／模型不可用时仍须能读已授权已存板。

PROCESS／TIMELINE／WATERFALL／FUNNEL 有目录与隔离链，完整变体归 M2。

## 限制

- VERSION 0.8.0.1，非正式 release，无公网。
- 只绑 127.0.0.1。
- 6677 PID **14287**（G4 热插拔后），加载工作树 `m1-remainder` 已构建插件。不要用未核对的原仓 `lib/` 验收，不要 `--fresh`，不要用会编原仓插件的官方 `reload`。本机账本 `.context/checks/g6-20260916/` 不进 Git。
- 完整 T13 仍 PARTIAL（DuckDB cohort／运行中撤权／网络中断未做）。本候选 2026-09-16 有界真模型复测见 `.context/checks/t13-20260916/`。T16 合成 c1/c5 基线见 `.context/checks/t16-20260916/`，非正式通过。T17 本候选 1440/1024/390／设置／等价表见 `.context/checks/t17-20260916/`；触控／读屏／业务撤权未过。本候选 G1 真模型已跑。
- 85 历史跳转未定因。
- 人群行动入口已合 [#166](https://github.com/weiweity/fuqing-crm-analytics/pull/166)（`b78beffa`）；文档指针 [#167](https://github.com/weiweity/fuqing-crm-analytics/pull/167)（`04f16604`）。6677 已用 remainder `--plugin-path` 重启，不是官方 `reload`。

## 回退（不覆盖活库）

1. 用 `scripts/dsh-dev/cli.mjs status` 确认 6677 仍是当前 PID（现役 **14287**）。不要 `--fresh`。
2. 板状态在 `.context/checks/s2-c1/synth-state/`（`board-documents/board_documents.sqlite3` 等）。需要备份时用 SQLite `Connection.backup()` 拷到**新目录**，不要覆盖活文件、不要抄 WAL。
3. 回退代码：保留当前 runtime，把 `--plugin-path` 指回已验证构建后 stop/start，不要官方 `reload`、不要新 runtime 名。
4. 先核对未认证 401、已认证能打开、说明板仍 v15／原板仍 v9，再允许编辑。
5. 停止服务只停本次拥有的 supervisor／18082／15173／8000；不要杀无关进程。

历史 4325 回退说明留在 [PRODUCT-LOCAL-RELEASE-2026-09-10.md](PRODUCT-LOCAL-RELEASE-2026-09-10.md)，端口和 SHA 已过期。

## G6 齐套检查

| 项 | 状态 |
|---|---|
| 当前候选检查 | 热插拔后 PID **14287**、工作树插件 remainder、状态目录 s2-c1/synth-state。完整账本 `.context/checks/g6-20260916/` |
| 公开属性与拒绝边界 | 目录 TABLE 无 `show_values`；G2 现场 409／401；隔离非法属性／重叠仍以 S4 为准 |
| 可用入口 | 6677 401／已认证 200；15173 200；8000/docs 200；18082 板列表 401／200 |
| 合成范围 | 合成诊断结果；非真实经营数据 |
| 限制 | 上文（已按本候选改写） |
| 回退 | `Connection.backup()` 到新目录再 restore-sandbox；G3 后 heads 为 v15／新板 v9／原板 v9；未覆盖活库、未抄 WAL |
| UAT 清单 | 三条路径；2026-09-16 用户明确「通过」 |

G6 齐套已按上表交接确认。完整 T13 仍 PARTIAL（见 `.context/checks/t13-20260916/`）。T16／T17、M2、合入 main、正式发布另账。
