# TODOS

施工顺序与禁区看仓库根 [STATUS.md](../../STATUS.md)。当前以本文件 **M1 核心交付**接续；Git 交付、产品验收与历史短 PR 分别记账，不另建平行 `todo.md`。七阶段历史账本：[产品验收与发布准备](./PRODUCT-READINESS-2026-09-10.md)。[总待办](./PLAN-CLOSEOUT-2026-09-05.md)和原 [11 工作包](./AUTOPLAN-IMPLEMENTATION-TASKS-2026-09-05.md)是规划编号，不代替当前任务卡。

## M1 核心交付

2026-09-13 用户确认“核心版本优先交付、扩库完善后置”。目标是问数后 AI 优先使用定制组件自由组板，板内按选定范围修改；首批六类不是最终上限。M1／产品仍 PARTIAL；原全量 App Goal 保持 PAUSED。本节承接原本地施工记录，不把旧冻结实现反推成最终需求。

### 当前停点与 Git 收尾

- [x] P1/#131：owned 启动器可靠性已合入。
- [x] P2/#132：13 文件计算事实包及 R4 数值接受规则已合入；不要重新提交原树中的旧 P2 快照。
- [x] #133：仓库专属 [ship-pr](../../.agents/skills/ship-pr/SKILL.md) 已纳管。
- [x] P3/P4 + AI-1/#134：107文件组合包已合入 `12a21de`，PR及该main CI均通过；含已复核的S1-A解释器便携性补丁，不重复发返修卡。不是M1／S2完成。
- [x] P5文档整理：按 document-release 更新当前入口、变更记录、未完成项，由独立文档PR交付；PR合并状态以实际Git回执为准。
- [x] S2-C1/#136：同会话 `saved_boards` 已合入 `b7dbc7b`。PR CI 通过；该 main CI 首次 `b0-contract-build` 失败后重跑通过，失败记录保留。有界合成措辞复验已做；本人 UAT 与合入后运行验收仍 NOT_RUN。不是 M1／S2 完成。
- [x] R-1/#153：生成配置预检已合入 `698278e`。有界真实模型 3 次＋Chrome 预览取消通过；TABLE `show_values` NOT_OBSERVED。不是 M1／S2 完成。
- [x] 侧栏比赛看板入口/#155：已合入 `27052fab`。[#157](https://github.com/weiweity/fuqing-crm-analytics/pull/157) 将默认前端口改为 `15173`（`fce2de83`）。Chrome 已见链接。不是 M1／S2 完成。
- [x] 本地清理：空闲树/已合分支已删；15173/8000 迁到 `main-runtime` 后拆 docs-155。原仓 `HANDOVER-CODEX.md` 保留。S4/S5 文档已写。G1–G6／U1 见下方验收门槛（G3 仍开）。
- [x] 驾驶舱人群行动入口/#166：已合入 `b78beffa`。PR CI 与该 main CI 均成功。合入不等于 6677 reload 或正式 release。不是 M1 完成。

S2-C1 代码已合。其余五类编辑、LINE 换数与当前模型板回退的**真实模型验收**已于 2026-09-14 在本机 6677 完成；9 月 15 日接续 S3 原型与正式壳验收，见 [首批记录](S3-ACCEPTANCE-2026-09-15.md) 与 [交叉补验](S3-CROSS-MATRIX-2026-09-15.md)。R-1 代码已合 #153；UAT 不在同一轮顺手扩修。

### 阶段接续

2026-09-15 当前增量：[R-1 生成配置错误恢复](R1-GENERATION-RECOVERY-2026-09-15.md)已合 [#153](https://github.com/weiweity/fuqing-crm-analytics/pull/153)（`698278e`）。历史“FUNNEL 422”定位为 LINE/TABLE 重叠。有界真实模型 3 次：问数通过；第一次生成因观察器把 `llm/retry` 当失败中止；重试命中 `COMPONENT_OVERLAP` 预检，FUNNEL 保留，未保存 6 块预览后 Chrome 取消。TABLE `show_values` NOT_OBSERVED。不据此关闭 S2/M1。

| 阶段 | 已有证据 | 尚需完成 |
|---|---|---|
| S0/S1 基线与装配 | Git／工具链／构建与同实例看板协议；已授权窗口的真实重载与模型连通 | 不重跑同题，不要求重新配置模型；下一次运行切换另核维护窗口 |
| S2 真实 AI 核心链 | 六类自由组板；METRIC 标题修改取消／确认 v2／刷新重开；生成快捷入口；S2-C1 已存板 catalog（#136）；2026-09-14 其余五类编辑、LINE 换数、当前模型板回退（预览→取消→重提→确认→重开）；R-1 重叠预检与 FUNNEL 保留（#153） | 不把本次运行写成 G1 勾选或 M1 DONE；TABLE `show_values` 现场未复现 |
| S3 设计与实现对齐 | 指定 Figma 矩阵通过；B3 核心分支双视口、12 次忙态恢复按钮实点已完成。窄屏覆盖导航／错误提示修复随本批代码交付，B0 完整检查与干净重建通过；真实 Chrome 通过窄屏开关、中文错误、只读拦截预检及桌面取消定点复验，当前仍 v15，未新增保存版本 | 85 历史跳转未定因，本轮未复现；取消拒绝新文案为状态回归，未重复真实落盘故障；整体 PARTIAL。详情见 [界面修复](S3-UI-REPAIR-2026-09-15.md)；不重跑完整 B3 矩阵 |
| S4 综合 QA | 候选钉死见 [S4](S4-QA-2026-09-15.md)。2026-09-16 本候选 G1–G6 现场／交接已补 | T16／触控另账。6677 未切到 main 构建 |
| S5 交接入口 | 6677／15173／8000／18082 本轮探活；回退、合成范围、拒绝边界与三条 UAT 路径见 [S5](S5-UAT-HANDOVER-2026-09-15.md)。U1 本人 2026-09-16「通过」。G6 2026-09-16 交接确认。人群行动入口已合 #166 `b78beffa` | 4325 历史入口不作当前交付。正式 release 与 6677 reload 另账 |

9 月 13 日真实模型证据：S2-A 为 3 prompt／9 step／7 工具，GSV 仅问数一次；S2-R2受控批次为 5 prompt／11 step／6 工具，0新增问数。另一次人工中止、无完整回执的轮次不计通过。两次 remote 注入失败保留为历史，现已修复。9 月 14 日 S2-C1 有界复验 5／6 次调用，见 #136。同日在已加载原仓插件的 6677 上完成 V-A1–A5／V-B1／V-B2；本机账本 `.context/checks/va-a1-a2-20260914/RESULT.md`（不进 Git）。终态原板 v8（ROLLBACK），说明板 v2。不代签 UAT。

### S2-C1 方案 B（已合 #136）

- [x] 只读定位：UI／SQLite原板为 APPLIED/v2，未覆盖；确认动作未进入原生会话，下一轮 catalog 不含已存板状态。模型把历史 PREVIEW_READY 当当前状态，不是存储丢失。
- [x] 在目录上下文增加**同权限、同会话**的 `saved_boards` 摘要（`board_id`/title/version）。当前 owner 最多扫描 500 个 head、返回 20 条；没有独立续页游标（`next_offset` 只分页问数结果）。状态为 complete／truncated／unavailable／unknown；不可用时省略 `saved_boards`。不返回整份 facts，不跨会话泄露。
- [x] 方法包与生成快捷入口明确“已保存不是草稿；GENERATE 是另一份未保存新板”。不自动 queue/steer，不加模型 confirm 工具，不改 GENERATE 新 board 的语义。
- [x] 隔离红→绿与有界真实复验：已存 v2 出现在 catalog；确认前预览不进已保存列表；新 GENERATE 不覆盖原板；取消后原板仍为 v2。权限／会话隔离与损坏 head=`unknown` 由合成测试覆盖。本人 UAT 不能代签；合入后的 6677 运行态未切到 `b7dbc7b`。

原定位正文位于本机 `.context/checks/ai-cockpit-goal/s2-c1-investigation-m3vN9c/RESULT.md`，不作为公共可访问证据。TABLE/FUNNEL 生成 422 与越界工具尝试不在本卡扩修。

### S2 其余真实模型用例（2026-09-14 已跑，文档收口）

每例覆盖预览→取消不变→重提→确认→重开。样式步问数回执增量为 0；换数核新 `result_id`。取消新数据提案不撤销已执行查询。本机证据不进 Git。

| 类型 | 结果 |
|---|---|
| LINE 图例 | [x] `show_legend` true→false；邻块不变；未再问数 |
| BAR 标签 | [x] `show_values` true→false；410/305 不变；未再问数 |
| TABLE 列 | [x] `columns=[]→["period"]`；未编造占比 |
| TEXT 正文 | [x] 本实例无 TEXT，先 GENERATE 说明板再改正文；`source_result_id` 仍 null；未覆盖原板 |
| EVIDENCE 摘要 | [x] 只改 `summary`；8 条 evidence items 深比较相等 |
| LINE 换数 | [x] 新结果 15 点／180；仅换 LINE 来源；取消后原板仍绑 31 日结果 |
| 当前模型板回退 | [x] 预览回退 v6→取消仍 v7→确认 v8 `ROLLBACK`；catalog 认已存 head |

METRIC 标题路径仍以 S2-R2 为准，不重复计新成功。R-1 代码已合；TABLE `show_values` 与 bash 越界本轮未复现。Figma 指定矩阵于 9 月 15 日通过，不能替代正式壳验收；[首批记录](S3-ACCEPTANCE-2026-09-15.md)保留注错未命中与白屏历史，[交叉补验](S3-CROSS-MATRIX-2026-09-15.md)记录核心分支与按钮实点、85 导航异常及 88 阻断未生效的设置失败；当前只读回读为同正文 v15，原板 v9。

### M1 验收门槛

- [x] G1 真实 AI：2026-09-16 本候选 6677／DeepSeek-V41-Flash High。自然语言六类组板新板 `board_a9bdb747bd6948708d7c152db7b5b9ab`；METRIC 标题 + TEXT 正文 + EVIDENCE 摘要 + BAR `show_values=false` + LINE `show_legend=false` + TABLE `columns=["period"]` 均预览后确认到 v7。说明板仍 v15、原板仍 v9。LINE 换数／回退未重跑，不挡本条。证据 `.context/checks/g1-20260916/`（不进 Git）。
- [x] G2 数据与范围：隔离链仍以 S4 为准。2026-09-16 现场 18082：同版两预览一胜一 409；无 token／假 token 401，现用身份仍可读；跨 session context 不列出本板，错误 session 提案 404。说明板 v15／原板 v9 未动，新板 v8。证据 `.context/checks/g2-20260916/`。未 revoke 现用 token。
- [ ] G3 保存恢复：确认才写、取消不变、幂等／未知核对、409保护、重开／回退，模型不可用仍可读已存板。
- [x] G4 原生体验：2026-09-16 6677 现场。分割条 ArrowLeft 调宽、收起／展开原生对话、折叠侧栏、布局方向键重叠拒绝后取消、换会话关闭驾驶舱；同一 runtime `--plugin off` 再 `on`（未 `--fresh`），伸美入口与已存板 v15/v7/v9 恢复。证据 `.context/checks/g4-20260916/`。不代替 G5。
- [x] G5 设计可用性：指定 Figma 矩阵仍以 S3 为准（不重跑 B3）。2026-09-16 本候选：六类目录 node-id 与 Figma 母组件五态存在；390 画布 334px 覆盖导航；长文／31 点折线／表分页可滚；Tab `:focus-visible`；loopback 打开 148ms。证据 `.context/checks/g5-20260916/`。不代替 T16 容量或触控／读屏。
- [x] G6 工程交接：2026-09-16 重核 PID 42237、工作树插件哈希、四入口、TABLE 无 show_values、401／409 拒绝、SQLite backup→restore-sandbox（未覆盖活库）。U1 已签。证据 `.context/checks/g6-20260916/`。不代替合入 main 或正式 release。
- [x] U1 用户本人 UAT：2026-09-16 用户对 S5 三条路径明确「通过」（分析师读说明板 v15／原板 v9，运营 6677「人群行动」且自动发送禁用，老板无新模型只读合成）。Agent 不代签；本条据用户当轮口头确认记账。

M1 DONE 要求 S0–S5、G1–G6具备对应证据；U1、Git交付、M2和原全量Goal分别记账。已知越权、错误数字、数据丢失或M1公开操作的焦点问题不能后置。

### M2 扩库完善

- [ ] PROCESS／TIMELINE／WATERFALL／FUNNEL已有目录、渲染与保存链，以及隔离浏览器分项；继续补完整属性、整板编辑、密集／长内容、Figma与真实模型验收，不删除实验成果。
- [ ] 其他公共样式变体、完整触控／读屏器、多层极端滚动及容量性能矩阵；不得用2000行边界测试代替性能结论。
- [ ] 已知 low UX：唯一已保存板仍需下拉选择；是否自动打开留后续小改，不混入收尾。

### 协作与接班

由用户人工转发有边界任务给 Grok Build，再贴回结果，主 Agent 核对基线／差异／测试后接收；不默认另起模型或递归子 Agent。任务卡须含 cwd／branch／base与文件指纹、可写范围、验收、禁区和证据位置；共享入口、合同与 Figma 母组件单写。主 Agent 唯一维护 STATUS/TODOS并整合结果，模型配置不随开发协作工具改变。

接班读 AGENTS → STATUS → 本节 → 当前任务及必要证据；涉及视觉再完整读 DESIGN。原本地长记录已私有备份，失败证据不回写，本文件仅维护当前接续。不提交 HANDOVER、不改 DSH 上游、不碰真实大库；任意脚本、飞书真操作与公网部署另定范围。

## 已合施工队列（历史短 PR）

- [x] #116 文档入口，对齐施工边界
- [x] #117 L4.91 R3 白名单：`member_join_rate` / `ly_member_join_rate` 展示 `*100`
- [x] #118 main DSH 钉升级到 0.1.5-rc.1；本地 0.1.3 checkout 已删
- [x] #119 访客入会率 API 0-1 raw，前端水平值 `*100`
- [x] #121 GSV SSOT：`calculations.GSV_PREDICATE`，filters/metrics 生产路径不再各写一份
- [x] #122 DQ 本地告警：断言与监控失败时发出可观测本地告警，不回接飞书
- [x] #124 聊天下「生成驾驶舱」：`conversation.input.dock` 打开 overlay 并落到认可成板
- [x] #125 T13 可重放离线 eval：`result_id ≠ run_id`、拒答文案、`money_unit`。不代替真实模型复测
- [x] #126 侧栏固定入口：`sidebar.panellist` / `main` key=`cockpit`
- [x] #127 dsh-dev 收进 main：6677 从 main 起；`--plugin on/off` 插拔伸美包。市场/IM 是另装的包，不是上游
- [x] #129 驾驶舱按 BoardSpec 生成：确认写入、`result_id` 绑数字、沙箱无脚本、侧栏样例板。合入 `main` `a729ff6`（v0.8.0.0）

## 当前验收缺口（开放，需对应证据）

- [ ] 首次启动保存反馈历史误报：3 次新运行时未复现，原根因仍待复现。
- [ ] 完整 T13：分项取证已有。2026-09-16 本候选 6677／DeepSeek-V41-Flash High：未接通重复调用即停、catalog 口径复测、等价问法、改期 EMPTY、GSV INHERIT、RFM+恶意备注拒执行、422 工具失败。证据 `.context/checks/t13-20260916/`（不进 Git）。运行中撤权／网络中断、真实 DuckDB cohort 仍开放。离线 eval 不代替真实模型复测。
- [x] T15：分析师 / 运营 / 老板 S5 三条路径，2026-09-16 用户本人「通过」。不要用 4325／15173 代替运营。不是公网或真实经营验收。
- [ ] T16：正式阈值与归档规模仍开放。2026-09-16 本候选合成基线：18082 GET 480/480，c1 与 c5 各 30 到达；多板 v15/v8/v9；results 分页；未重启故非冷启动。6677 1440 五次 reload FCP 中位 92ms。大候选 0 行未测。证据 `.context/checks/t16-20260916/`（不进 Git）。禁止先宣布性能通过。
- [ ] T17：完整视觉仍开放。2026-09-16 本候选 6677：1440/1024/390 无横向溢出、设置可达、Commands 含 compact（未执行）、LINE 31 条等价表、消费者壳无 DSH Local Build。键盘／热插拔沿用 G4。业务撤权、触控／读屏、本候选 Stop／compact 实跑仍开放。证据 `.context/checks/t17-20260916/`（不进 Git）。
- [ ] 明确发布版本/环境、状态备份与回退，完成部署后的关键路径验证。非正式 release。

历史局部通过项见 [维修 QA](./COMPETITION-REPAIR-QA-2026-09-10.md)。T13 本候选 2026-09-16 有界复测已记账，完整 T13 仍 PARTIAL。

## 已在 main 的证据（不要当成未完成任务）

- [x] #112 集成、#114 七项修复、#115 持久化诊断看板、**#116–#129**已合入 main；#166 人群行动入口已合 `b78beffa`（当前 HEAD 见 STATUS）。#129 为 BoardSpec 驾驶舱 v0.8.0.0。
- [x] 图表类型持久化与草稿恢复/放弃。
- [x] 原生浅/深色与业务主题、AntD 表单；完整 T17/视觉仍开放，见[视觉增量](PRODUCT-VISUAL-INTEGRATION-2026-09-10.md)。
- [x] GSV 数值诊断 → 保存 → 成板（合成源）；两条真实 DeepSeek 评测及刷新重开，见[本轮交付](DIAGNOSIS-INTEGRATION-DELIVERY-2026-09-10.md)。
- [x] 原生停止、文件权限/审批、目录与 preset、单位来源 v2、result_id/run_id 分项，见 PRODUCT-READINESS 及 COMPUTED-UNITS 文档。

自由诊断、认可后批量成板、拖拽缩放与聊天编辑、自有比赛品牌、召回候选预览及行动草稿已进入 [总计划§12](./PLAN-CLOSEOUT-2026-09-05.md)。真实人群、旧 CRM catalog 和 MCP 各按自身证据判断。

## 延期（独立授权，默认不做）

### 网址提交与访问控制

选择公网平台、访问控制并获得部署授权。用户已暂缓公网。未授权则报告阻碍，不公开免登录本机。

### 认可分析的定时刷新与投递预览

单调度器 REFRESH 与 fake delivery；真实飞书投递另批。本提交版不实现 subscriptions API。

### 财务与运营专家模板

先不做自由工作流编辑器。财务缺真实成本必须 UNKNOWN。

### 多人状态库 / PostgreSQL

规划输入约 10 人、峰值 5 人分析。本地 B0 仍为 SQLite + 只读合成 DuckDB。不把换库当提速结论。不读取/复制 131GB 归档真库。

### 妙搭能力核验与 CRM 试点

只延期真实触达、外部接口和回流。发送不等于有效增长。

## Completed

- [x] 视觉与状态恢复增量进入 4325/18083；五库新备份恢复及浏览器重开通过，[快速 canary DEGRADED](PRODUCT-CANDIDATE-SWITCH-2026-09-10.md)保留既有 B0 404。**Completed:** 2026-09-10
