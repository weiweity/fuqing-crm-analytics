# TODOS

施工顺序与禁区看仓库根 [STATUS.md](../../STATUS.md)「本轮施工计划」。本文件分两块：**本轮施工队列**（短 PR，一次一刀）和 **验收缺口**（要证据，不是授权）。七阶段账本：[产品验收与发布准备](./PRODUCT-READINESS-2026-09-10.md)。[总待办](./PLAN-CLOSEOUT-2026-09-05.md)和原 [11 工作包](./AUTOPLAN-IMPLEMENTATION-TASKS-2026-09-05.md)是规划编号，默认不要当本轮任务卡。

## 本轮施工队列（一次一刀；下一刀仍要一句话开干）

- [x] #116 文档入口，对齐施工边界
- [x] #117 L4.91 R3 白名单：`member_join_rate` / `ly_member_join_rate` 展示 `*100`
- [x] #118 main DSH 钉升级到 0.1.5-rc.1；本地 0.1.3 checkout 已删
- [x] #119 访客入会率 API 0-1 raw，前端水平值 `*100`
- [x] #121 GSV SSOT：`calculations.GSV_PREDICATE`，filters/metrics 生产路径不再各写一份
- [x] #122 DQ 本地告警：断言与监控失败时发出可观测本地告警，不回接飞书
- [ ] **T13 可重放离线 eval**（下一刀，说「开 T13」）：`result_id ≠ run_id`、拒答文案、`money_unit`。不代替真实模型复测。代码在 `archive/2026-09-11-iron-rules-t4`，不要顺手捡驾驶舱
- [ ] 驾驶舱 UI 上 main：`sidebar.panellist` / `main` key=`cockpit` + TOOL_SPECS。代码在 `archive/2026-09-11-cockpit-t2`。钉已是 0.1.5，可以上 main，排在本队列最后

## 当前验收缺口（开放，需对应证据）

- [ ] 首次启动保存反馈历史误报：3 次新运行时未复现，原根因仍待复现。
- [ ] 完整 T13：分项取证已有（单位/标识、原生工具边界、A6/A7 HTTP、旧 MCP/截断、UNKNOWN）。其余鲁棒性、未接通能力的重复调用、真实 DuckDB cohort 仍开放。离线 eval 不代替真实模型复测。
- [ ] T15：分析师 / 运营 / 老板完整流程，须用户本人验收。
- [ ] T16：页面性能与数据量/并发/P95/RSS；现仅有单用户合成基线。
- [ ] T17：完整视觉及其余原生边界；已有局部 Stop/权限/目录/preset/压缩证据，不代替业务撤权与真实凭据可达。
- [ ] 明确发布版本/环境、状态备份与回退，完成部署后的关键路径验证。非正式 release。

历史局部通过项见 [维修 QA](./COMPETITION-REPAIR-QA-2026-09-10.md)。T13 已有有界真实 DeepSeek 调用，仍 PARTIAL。

## 已在 main 的证据（不要当成未完成任务）

- [x] #112 集成、#114 七项修复、#115 持久化诊断看板、**#116–#122 收口短 PR**已合入 main（当前 HEAD 见 STATUS）。
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
