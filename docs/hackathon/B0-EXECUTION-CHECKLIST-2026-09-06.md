# B0 连续执行清单

日期：2026-09-06。总目标：完成已批准的 **隔离 synthetic B0 本地工程验收**，形成可核对的通过项、未通过项和后续交付清单，不把小样称作完整产品。

当前结论（更新于 2026-09-07）：**T01–T09 已执行，整体 B0 仍 PARTIAL**。最新 [T09 原生故障与监督器](./B0-NATIVE-FAULT-2026-09-07.md)已验证真实失败卡、多 key 卡片共存和刷新；确定的 EPIPE 故障模式已修复，历史三次退出无法归因。T09 已在本 Goal 提交 `bd6d8fe`（PR #69 base PR #68；CI runs 34049400372/34049400375 对该 SHA 成功；原生四问 `runtime-eDvn6c` PASS）。G1 [native-state](./B0-NATIVE-STATE-2026-09-07.md) **本范围原生补证 PASS**（`runtime-SNWYss` 四问；第一次 `hkeo4K` F3 失败保留）。独立 pipeline 178 Python / 143 源 Node / 14 built（F3 前口径）；F3 后 7 Node smoke PASS。G1 源码未提交，最终 full pipeline 待 Codex，P1 CI 不是 G1 CI。T01–T08 下表保留当轮证据。G0 文档单元当时未跑业务测试。该目录被 Git 忽略，不是未跟踪源码。

本清单是 **2026-09-06 B0 当轮队列（T01–T09）**，不是 2026-09-07 的 8 小时 Goal 任务卡。Goal 入口见 [8 小时计划](./GOAL-8H-CODEX-GROK-2026-09-07.md)：synthetic G0–G5 在本清单 PARTIAL 之上继续合同/金标准、首条合成查询和原生接线，**不重写下表 DONE/OPEN，也不把 G2–G4 记成 B1–B4 完整产品**。本轮 Goal 已授权 scoped Git（任务分支/commit/push/小 PR）；merge/部署/删分支/真实库/产品模型仍未授权。下文「工作位置与分支不变 / 不自动 commit」只约束当时 T01–T09 当轮，不是本 Goal 全局指令。G0 文档修订记录时点未启动 B0 服务，不断言其后 G1 是否启动。

本清单承接用户“罗列任务清单、整体走一个目标、逐步执行、不反复确认”的授权。日常实现、针对性测试和已批准的临时合成验证连续执行；只有超出授权、破坏性变更或触及原架构硬门时停下请求方向。当时要求既有 dirty 工作区保留、工作位置与分支不变；该约束已随 T09 记录，不阻止本轮 Goal 按授权创建新任务分支。

## 范围与完成规则

- 不重开已完成的架构选型；沿用 DSH 原生运行时及 UI、独立插件、FastAPI 状态与权限、SQLite B0 状态及只读合成 DuckDB。
- 当时 B0 队列不进入 B1–B4 完整产品开发；真实业务库、ETL、收费模型、跨会话自动记忆、子 agent、外部消息与部署不在该目标内。本轮 8h Goal 同样不把这些列为范围，但其 G2–G5 是同一 synthetic 线上的合同/首查/接线，不是「不得做任何 B0 之后的工作」。
- 当时清单不自动 commit / push / PR / merge / 发布，不清理已有分支或未提交改动。第 1、2 项已另获授权并由 PR #67 合并；本轮 Goal 对 T09/B0 收尾与 G0–G5 产物另有 scoped Git 授权（见上）。缺少当时 Git 授权不阻止本地任务——此句保留为当轮规则，不是当前禁止交付。
- 验证证据分为单元/合同、装配、原生运行/浏览器；只在实际覆盖的层级标 PASS，mock 不等于真实模型。
- 硬门失败须修复并复验，或明确报告未通过；不能通过删验收项、隐藏按钮或标记跳过让 B0 变绿。
- 临时验证结束后停止本次服务并核验归属；不安装常驻监督/监控。

## 任务队列

| ID | 任务与验收出口 | 当前状态 |
|---|---|---|
| T01 | 固定范围、当前代码/证据、任务队列；区分 B0 与后续产品阶段 | DONE：本清单及只读对齐 |
| T02 | Skill 整包 manifest/hash；SKILL.md、references/assets 全覆盖；默认 roots 隔离；符号链接/越界/漂移拒绝；原生发现与受控按需读取小样 | DONE：组件读取 PASS，新 preset 原生发现/七问通过；浏览器未调用方法工具 |
| T03 | 后端重建运行上下文；首派发、compaction 后和恢复重读条件/版本/证据/预算；旧摘要和记忆不可篡改事实、权限或批准 | DONE：真实组件压缩 PASS（HTTP fixture）；11 次 live mock 请求核对当前上下文/原截止；不冒充全链路压缩 |
| T04 | 固定控制面 manifest 对照当前原生 HTTP、WS mux、Fetch；正常与未登记/越权/撤权/过大参数路径实测 | DONE：持续权限修复复验，当前 51 项 live PASS；清单与原生七问齐备，MCP NOT ENABLED |
| T05 | UI-B04 固定入口、无会话/离线资产小样与局部预览恢复；UI-B06 旧 BI 隔离接缝与完整条件往返样例；UI-B07 原品牌/三档视口/键盘 | DONE（承载小样）：6 组资产/接缝、8 组主题/视口；非完整资产/同条件 BI 产品；UI-B02 全状态仍 PARTIAL |
| T06 | 将新增检查纳入统一 pipeline；相关回归、类型、真实 loader、干净构建与必要原生验证；临时服务收尾 | DONE：164 Python / 133 Node / 5 装配，干净构建和浏览器产物一致；4315–4319 无监听，测试页关闭 |
| T07 | 统一当前进度入口、B0 逐门结论和开放风险；整理 B1–B4 与 Git 交付清单（不执行未授权动作） | DONE：当前报告及主入口已同步，保留历史根因 OPEN，不执行后续阶段 |
| T08 | 补工具卡组件状态 DOM、桌面/窄屏展示及干净构建回归 | DONE（组件层）：8 状态、9 新测试、两档浏览器通过；最新 164 Python / 133 源 Node / 14 编译与装配，原生故障全链仍未实测 |

| T09 | 原生 worker 故障→工具失败卡、同轮 Skill/分析卡、刷新恢复与有界监督器退出根因验证 | DONE（本次限定链路）：四问 3 成功/1 TOOL_FAILED，5 次原生工具调用；EPIPE 因果对照与修复通过；167 Python / 138 Node / 14 编译装配；历史退出仍 OPEN |

## 已有基线，不冒充本轮重跑

来源：[监督器复查报告 §5](./B0-SUPERVISOR-RECHECK-2026-09-06.md)。2026-09-06T06:08:44Z 统一检查 151 Python / 100 Node、类型检查、真实 Cordis loader 和干净构建通过；随后原生七问通过。远端 CI 未运行。

历史监督器退出故障：**OPEN / NOT REPRODUCED**。历史原始退出证据不足，不能记为已修复；T09 另行复现并修复了 stderr EPIPE 模式，两者不混同。不无依据反复运行或新增常驻监控。

完成判据来源：[运行时验证计划 §5](./RUNTIME-VALIDATION-PLAN.md)、[Skills 与上下文合同 §5.2](./ANALYTICS-CONTRACTS-DRAFT.md)、[UI-B01–07](./DSH-UI-INTERACTION-SPEC.md)。如发现超出小型插件适配才能满足的承载缺口，报告硬门，不擅自 fork 上游或重建框架。

## 执行记录

- T01：已核验目标 worktree、分支 `codex/architecture-warehouse-plan-closeout` 及现有改动。开始时 42 个 tracked 修改、60 个 untracked 条目（目录条目不等于文件数）。不切换分支，不纳入无关修改。
- T02：现有启动配置禁用了 `skill-filesystem`，只有空隔离 Skill 目录；不能视为获批包装配通过。下一步沿用固定上游提供方与工具接口补受控包和针对性验证。
- T02–T04 执行更新：已实现固定包和后端上下文/预算小样，修复实证的网关持续权限缺口；详细证据及测试层级见[方法与权限报告](./B0-METHOD-CONTROL-VALIDATION-2026-09-06.md)。T02 上一条是执行前基线，不再代表当前实现。
- T02–T07 最终更新：当前 `runtime-qCzzrY` 七问与分层小样通过，最终干净构建为 `clean-build-DPNRQY`。本轮完成结果、未验证门及停止证据统一看[本地收口报告](./B0-LOCAL-CLOSEOUT-2026-09-06.md)，不以历史基线数量充当最新结果。
- T08 增量更新：仅测试/验证脚本及文档，未改业务组件；`clean-build-XiUowY` 和两档工具卡页面通过，编译客户端 hash 与 T01–T07 一致。详细层级、限制和清理见[增量报告](./B0-TOOL-CARD-DOM-2026-09-06.md)。

- T09：第 1、2 项 PR #67 合并后，在 `codex/b0-native-fault-validation` 完成本地修复与原生四问验证；当时第 3 项仅本地。本 Goal 已提交 T09 为 `bd6d8fe`，PR #69 base PR #68，CI 34049400372/34049400375 对该 SHA 成功；当前原生四问 `runtime-eDvn6c` PASS。证据见 [T09 报告](./B0-NATIVE-FAULT-2026-09-07.md)。P1 CI 不是 G1 CI。
- G1（2026-09-07）：native running / 未知版本与非法 facts 拒绝链已落地。F1 dump-only 非法 result；F2 真实工具卡 running；F3 等 native turn + Send message。`runtime-SNWYss` 四问 PASS（`G1-native-retry.log`）；第一次 `hkeo4K` 因 F3 失败保留。独立 pipeline 178/143/14；F3 后 7 Node PASS。G1 尚未 commit/push/CI，最终 full pipeline 待 Codex。报告 [B0 原生状态](./B0-NATIVE-STATE-2026-09-07.md)。不改写上表 T01–T09 DONE，也不闭合历史三次监督器退出。
