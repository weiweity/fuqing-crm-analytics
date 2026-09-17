# 项目状态 (Project Status)
> 当前短表；编年与旧运维事项见 [STATUS-HISTORY.md](docs/history/STATUS-HISTORY.md)。

## 当前快照（2026-09-17）

| 项 | 状态 |
|---|---|
| VERSION / main | VERSION **0.9.0.6**（本候选）。origin/main **`6c2a2355`**（#199）。loopback。**不上公网**。产品仍 PARTIAL。 |
| DSH 钉 | **0.1.6-alpha.1**（`0a15e36e`）。6677 PID **35197** 已切（原仓 runtime + workbench + shine-brand + shine-waterfall + shine-crowd-action，未 `--fresh`，非官方 reload）。15173 PID **85899**。 |
| 产品 | 仍 PARTIAL。M2 其余缺口也算关（触控矩阵／下拉不是通过）。Goal 仍 PAUSED。验收账本：[产品验收与发布准备](docs/hackathon/PRODUCT-READINESS-2026-09-10.md) |
| T13 | 本候选收口。有界复测、会话中途断网／401、小型 DuckDB 6 用户。`diag.fixed_cohort` 保持 UNSUPPORTED。131GB 已只读打开元数据，禁止复制／改写／全表扫描 |
| T15 / T16 / T17 | T15 本人「通过」。T16 本候选收口：合成 c1/c5 基线已记（用户确认基线也算关），**不是 SLO 通过**。T17 缺口也算关 |
| 归档数据 | `data/processed/fuqing_crm.duckdb` 不进 Git；约 131GB。2026-09-17 只读打开元数据（19 表）。禁止复制、改写、全表扫描。未知金额 WATERFALL 仍 422 |
| 发布 | 本机正式候选 v0.9.0.0（loopback）。公网部署仍要独立授权 |

## 本轮施工计划（现行，不要只记在对话里）

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

#134 的合成检查与受控浏览器 QA 范围不变；[PR CI 34809535341](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34809535341)与该业务提交的[main CI 34810185362](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34810185362)均成功。#136 [PR CI 34844745522](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34844745522)成功。合入 SHA `b7dbc7b` 的 [main CI 34846189734](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34846189734) 首次 `b0-contract-build` 因 `first_purchase_native` 503/409 失败，`--failed` 重跑后含 `merge-gate` 成功；不把后一次绿灯写成从未失败。#153 [PR CI 34940883528](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34940883528)与合入 SHA `698278e` 的 [main CI 34950368840](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34950368840)均成功。#155 [PR CI 34957745433](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34957745433)与 `27052fab` 的 [main CI 34959522528](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34959522528)均成功。#157 [PR CI 34964763768](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34964763768)首次 test 因 DuckDB spill 失败、`--failed` 重跑后与 `fce2de83` 的 [main CI 34966517072](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34966517072)均成功。#158 与 `dbe5e6ed` 的 [main CI 34976252688](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34976252688)成功。#166 [PR CI 35057625458](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/35057625458)与合入 SHA `b78beffa` 的 [main CI 35058294392](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/35058294392)均成功。P2 后历史 main CI `34768344985` 失败不回写为成功。CI 不替代完整真实模型、Figma、本人 UAT 或合入后的运行态验收。

### M1 接续与剩余事项

- S0/S1已有基线与同实例装配证据；S2仍 **PARTIAL**。9 月 13 日真实模型已完成六类自由组板，以及 METRIC 只改标题的取消／确认 v2／重开和生成快捷入口。S2-C1 方案 B 已合 #136。9 月 14 日同一 6677（web PID 71492／18082 71160，原仓插件，未 `--fresh`）上，DeepSeek-V41-Flash High 完成其余五类编辑、LINE 换数与当前模型板回退；板 `board_f8b8d7d3926e47309e83da7a7f047c47` 终态 **v8**（v7 换数后 ROLLBACK 回 v6 内容）。本机证据 `.context/checks/va-a1-a2-20260914/RESULT.md`（`.context/` 不进 Git）。当时本人 UAT NOT_RUN；U1 已于 2026-09-16 记账。
- **下一产品缺口**不再是五类编辑／换数／回退实现。B3 核心恢复分支双视口和 12 次忙态恢复按钮实点已有证据。用户授权后已本地修复 390px 侧栏挤压、取消拒绝提示与英文连接错误，B0 完整检查／干净重建通过，详见 [S3 界面修复](docs/hackathon/S3-UI-REPAIR-2026-09-15.md)。窄屏覆盖导航与中文连接错误已由真实 Chrome 核验；取消拒绝新文案通过状态回归，未再次制造正式壳落盘故障。当前说明板 **v15**、原板 **v9**，修复验证没有新增保存版本。本批修复代码与证据一并交付；Git 合入以对应 PR 回执为准，整体 PARTIAL。
- S3 指定 Figma 矩阵已通过，示例金额不作 facts；历史证据见 [首批记录](docs/hackathon/S3-ACCEPTANCE-2026-09-15.md) 与 [交叉补验](docs/hackathon/S3-CROSS-MATRIX-2026-09-15.md)。85 历史意外返回对话仍未定因，88 设置失败导致的同正文 v15 保留。R-1 代码已合 #153；有界复验观察到布局重叠预检与 FUNNEL 保留，Chrome 取消未保存。TABLE `show_values` 与 bash 越界本轮未复现。
- **S4** 6677 现加载工作树插件。G2 现场：同 head 双预览一胜一 409；未授权 401；跨 session 不串板。G3 现场：新板布局取消仍 v8、确认 **v8→v9**、陈旧 layout-preview 409、未知属性 422、只读重开 v15／原板 v9。说明板仍 v15、原板仍 v9。G4 热插拔后 PID **14287**。G5 390／长内容已复核。G6 已交接确认。本机账本 `.context/checks/g{1–6}-20260916/` 不进 Git。
- **S5/G6** [交接](docs/hackathon/S5-UAT-HANDOVER-2026-09-15.md)：2026-09-16 齐套确认（候选／入口／拒绝边界／backup 演练／U1）。现役快照 PID 14287／新板 v9。证据 `.context/checks/g6-20260916/`。
- 开发协作沿用户人工转发 Grok Build 任务、主 Agent 复核的方式；不同 Agent 的共享入口与 Figma 母组件保持单写入者。原 App 全量 Goal 仍 PAUSED；本候选不恢复旧 Vue 全量 CRM，**不是 Goal 完成**。
- Git 合入不等于部署。6677 原仓 runtime PID **35197** 已 `plugin add` shine-brand + shine-waterfall + shine-crowd-action + workbench。15173 PID **85899**、8000 PID **85883**、18082 PID **83173** 未动。现役未 `--fresh`。不要用会编原仓插件的官方 `reload`。工作树已收口，只留 `main`。
- `HANDOVER-CODEX.md` 不提交。下一产品：FUNNEL／比赛看板另授权、公网另授权。问数／组板本候选已拆未合入／未 reload。人群行动已合 #198。WATERFALL 已合 #196。品牌已合 #194。#171 `5a8329c3`。Q3 overlay 已灌；`fill_user_rfm=0`。

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

本地及 CI 按 [验证入口](docs/operating/verification.md)。skip 不算运行通过。B0 当轮 T01–T09 已收口，清单是历史队列，不是当前任务卡。

#108 首购、W4/W5 和更早测试数已迁入 [历史记录](docs/history/STATUS-HISTORY.md)，不扩大为当前真实模型、容量或业务验收通过。

行为与数据边界见 [AGENTS.md](AGENTS.md)，设计合同见 [DESIGN.md](DESIGN.md)，开放债见 [TECH-DEBT](docs/TECH-DEBT.md)，验收缺口见 [TODOS](docs/hackathon/TODOS.md)。
