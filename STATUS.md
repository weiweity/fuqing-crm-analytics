# 项目状态 (Project Status)
> 当前短表；编年与旧运维事项见 [STATUS-HISTORY.md](docs/history/STATUS-HISTORY.md)。

## 当前快照（2026-09-19）

| 项 | 状态 |
|---|---|
| VERSION / main | VERSION **0.9.0.9**（本分支候选）。origin/main **`22a0028f`**（#210）。loopback。**不上公网**。产品仍 PARTIAL。 |
| DSH 钉 | **0.1.6-alpha.2**（`ddefc45f`）。6677 PID **637** remainder 无 `--fresh`。隔离页库 `127.0.0.1:18091`（`--page-http on`）。 |
| 产品 | 仍 PARTIAL。自由 HTML 已合 #209+#210；P13 真模型样本未跑。Goal PAUSED。账本：[产品验收与发布准备](docs/hackathon/PRODUCT-READINESS-2026-09-10.md) |
| T13 | 本候选收口。有界复测、会话中途断网／401、小型 DuckDB 6 用户。`diag.fixed_cohort` 保持 UNSUPPORTED。131GB 只读元数据，禁止复制／改写／全表扫描 |
| T15 / T16 / T17 | T15 本人「通过」。T16 合成 c1/c5 基线已记，**不是 SLO 通过**。T17 缺口也算关 |
| 归档数据 | `data/processed/fuqing_crm.duckdb` 不进 Git；约 131GB。禁止复制、改写、全表扫描。未知金额 WATERFALL 仍 422 |
| 发布 | 本机正式候选 v0.9.0.0（loopback）。公网部署仍要独立授权 |

## 本轮施工计划（现行，不要只记在对话里）

### 自由 HTML 驾驶舱（Git 已合，现役已 reload）

[#209](https://github.com/weiweity/fuqing-crm-analytics/pull/209) 装配六路；[#210](https://github.com/weiweity/fuqing-crm-analytics/pull/210) `22a0028f` 接通生成工具、隔离 HTTP、驾驶舱离开。A–F/G/H/K/P12/SEAMS 工作树已删。入口：侧栏驾驶舱 → **自由页面**。保存打 18091，拒绝写 6677。剩余：P13 三场景、宿主壳接 DESIGN.md/Ant Design、侧栏 veto 已接受限制、`openPlazaRole`、Noto 字体。[施工包](docs/hackathon/free-html-cockpit/README.md) 仍本地未跟踪。产品仍 PARTIAL，不是 READY_FOR_SHIP。

### 已有产品与历史交付基线

S2-C1 代码已合 #136，[S3 界面修复](docs/hackathon/S3-UI-REPAIR-2026-09-15.md)已合 #152（`c734957`）。**[R-1 生成配置错误恢复](docs/hackathon/R1-GENERATION-RECOVERY-2026-09-15.md)** 已合 [#153](https://github.com/weiweity/fuqing-crm-analytics/pull/153)（`698278e`）：布局重叠预检与 FUNNEL 保留已有有界真实模型／Chrome 证据。TABLE `show_values` 现场未复现；bash 本轮未出现。人群行动入口已合 [#166](https://github.com/weiweity/fuqing-crm-analytics/pull/166)（`b78beffa`）。比赛看板品类脱敏已合 [#165](https://github.com/weiweity/fuqing-crm-analytics/pull/165)（`308180fd`）。6677 PID **14287** 加载工作树 `m1-remainder` 插件（同 runtime stop/start + `--plugin-path`，**不要**用会编原仓插件的官方 `reload`）。9 月 15 日指定 Figma 矩阵已通过；正式壳 B3 仍 PARTIAL，见 [首批记录](docs/hackathon/S3-ACCEPTANCE-2026-09-15.md) 与 [交叉补验](docs/hackathon/S3-CROSS-MATRIX-2026-09-15.md)。[S4 综合 QA](docs/hackathon/S4-QA-2026-09-15.md)为隔离 G2/G3 基线；2026-09-16 本候选 G1–G6 与 U1 已记账，其中 **G3 现场确认保存** 新板 v8→v9。产品接续看 [TODOS 的 M1 核心交付](docs/hackathon/TODOS.md#m1-核心交付)。交付按本仓 [ship-pr](.agents/skills/ship-pr/SKILL.md)，各动作授权分别核验。

产品方向：原生问数 → 复用结果、优先定制组件自由组板 → 预览 → 确认保存 → 指定组件 AI 修改／自由布局 → 重开／回退。六类是首批能力，不是六张固定模板或最终上限；旧交接的三操作、固定会话和主区互斥不是最终产品要求。
| 包 | Git 交付 | 适用范围 |
|---|---|---|
| P1 启动器 | [#131](https://github.com/weiweity/fuqing-crm-analytics/pull/131)，`c6e27d3` | owned 启动就绪、清理与取消；不把隔离竞态认作历史现场退出的确定原因 |
| P2 计算事实 | [#132](https://github.com/weiweity/fuqing-crm-analytics/pull/132)，`13bf175` | 逐日／渠道贡献／购买频次及 Python/JS 差额校验；原施工树旧快照不是最终 R4 |
| 工作流纳管 | [#133](https://github.com/weiweity/fuqing-crm-analytics/pull/133)，`a52309b` | 仓库专属 ship-pr；PR 与该 main CI 均成功 |
| P3/P4 + AI-1 | [#134](https://github.com/weiweity/fuqing-crm-analytics/pull/134)，`12a21de` | 104 文件业务包 + 3 文件取消修复，按组合验证交付；不宣称每个子包独立可发布 |
| S2-C1 已存板目录 | [#136](https://github.com/weiweity/fuqing-crm-analytics/pull/136)，`b7dbc7b` | 同会话 `saved_boards` 摘要；有界合成真实措辞复验。不宣称 S2/M1 完成 |
| S2 其余五类＋换数＋回退＋V-C 抽样 | [#138](https://github.com/weiweity/fuqing-crm-analytics/pull/138) | 2026-09-14 同一 6677／DeepSeek-V41-Flash High 真实模型全周期。不升版本、不代签 UAT、不勾 G1–G6 |
| R-1 生成配置错误恢复 | [#153](https://github.com/weiweity/fuqing-crm-analytics/pull/153)，`698278e` | 提交前预检指出非法属性／重叠块；有界真实模型 3 次＋Chrome 预览取消。TABLE `show_values` NOT_OBSERVED。不勾 G1–G6 |
| 侧栏比赛看板入口 | [#155](https://github.com/weiweity/fuqing-crm-analytics/pull/155) / [#157](https://github.com/weiweity/fuqing-crm-analytics/pull/157)，`fce2de83` | 新标签打开独立 15173；不内嵌。5173 留给其它 Vite |
| 驾驶舱人群行动入口 | [#166](https://github.com/weiweity/fuqing-crm-analytics/pull/166)，`b78beffa` | Library 页签打开既有 ActionsWorkbench；合入不等于 6677 reload 或正式 release |

CI 不替代完整真实模型、Figma、本人 UAT 或合入后的运行态验收。历史 run 见 [STATUS-HISTORY](docs/history/STATUS-HISTORY.md)。

### M1 接续与剩余事项

- S2 仍 **PARTIAL**。六类组板与换数／回退证据见历史；U1 已于 2026-09-16 记账。S3 Figma 矩阵已过，见 [首批记录](docs/hackathon/S3-ACCEPTANCE-2026-09-15.md)。R-1 已合 #153。
- **S4/S5** 账本 `.context/checks/g{1–6}-20260916/` 不进 Git。[S5 交接](docs/hackathon/S5-UAT-HANDOVER-2026-09-15.md) 齐套确认。Goal 仍 PAUSED。
- Git 合入不等于部署。现役 6677 PID **637**（`dsh-dev reload --page-http on`，无 `--fresh`）。比赛看板仍 15173，不进 DSH。
- `HANDOVER-CODEX.md` 不提交。公网另授权。shine-brand #205、FUNNEL #202、问数 #200、人群行动 #198、WATERFALL #196、品牌 #194。Q3 overlay 已灌；`fill_user_rfm=0`。

## 已合施工记录（#116–#129）

下表是上一轮短 PR 记录。9 月 5–10 日总待办／T01–T09也不是当前 M1 任务卡；不根据历史测试数重新认领已完成项。

| 顺序 | 刀 | 证据 | 状态 |
|---|---|---|---|
| 1 | 文档入口，对齐施工边界 | #116 | 已合 |
| 2 | L4.91 R3 白名单：入会率水平值允许展示 `*100` | #117 | 已合 |
| 3 | main DSH 钉升级到 0.1.5-rc.1 | #118 | 已合 |
| 4 | 访客入会率 API 0-1 raw，前端水平值 `*100` | #119 | 已合 |
| 5 | GSV 口径谓词 SSOT | #121 | 已合 |
| 6 | DQ 本地告警（不接飞书） | #122 | 已合 |
| 7 | 聊天下「生成驾驶舱」（`conversation.input.dock`） | #124 | 已合 |
| 8 | T13 可重放离线 eval | #125 | 已合 |
| 9 | 侧栏固定入口：`sidebar.panellist` / `main` key=`cockpit` | #126 | 已合 |
| 10 | dsh-dev 收进 main：6677 + 插件插拔 | #127 | 已合。日常改插件用 `reload`，固定 `.context/dsh-dev/runtime`，不要 `--fresh` |
| 11 | 驾驶舱按 BoardSpec 生成：确认写入、`result_id` 绑数字、沙箱无脚本 | #129 | 已合 |

## 当前施工边界（防乱）

遇到下列项就停，不要当顺手活：

- 不要把比赛工具接到通用 metric HTTP，也不要把 `ChannelFollowupQueryRequest` 泛化成新合同
- 不要给模型新增 SQL 工具，不要从 `FORBIDDEN_EXPANSIONS` 拿掉 `execute_sql`，不要把 `ai_sandbox` 接到比赛 Agent
- 不要改 DSH 上游源码。不要打开、复制、改写 131GB DuckDB，也不对其执行 SQL
- T3 备份、`cleanup_backups.sh` 的 `keep_min`、口令轮换、T15 本人验收、公网部署：要显式授权
- 自由任意组件、受控脚本、飞书真实操作另作范围确认；保留现有静态 HTML 沙箱及 LINK 占位，不接 token。不要把聊天下生成和侧栏查看混成一个入口

## 验证与历史入口

本地及 CI 按 [验证入口](docs/operating/verification.md)。skip 不算运行通过。B0 当轮 T01–T09 已收口。#108／W4/W5 见 [历史记录](docs/history/STATUS-HISTORY.md)。行为见 [AGENTS.md](AGENTS.md)，设计见 [DESIGN.md](DESIGN.md)，债见 [TECH-DEBT](docs/TECH-DEBT.md)，缺口见 [TODOS](docs/hackathon/TODOS.md)。
