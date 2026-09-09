# AI 增长董事会

本目录记录黑客松产品决策和本地演示基线，它不替代原有 CRM 分析文档。公网部署与网址提交仍是独立待办。

2026-09-10 核验主线为 `788b5b1`（#114），VERSION `0.7.0.0`。competition 集成 #112 和 7 项修复 #114 已合入，PR 及 main CI 均通过；[独立浏览器 QA](./COMPETITION-REPAIR-QA-2026-09-10.md) 覆盖合成成板、重试、布局和草稿重开。当前执行 [产品验收与发布准备七阶段账本](./PRODUCT-READINESS-2026-09-10.md)。T13 已有真实 DeepSeek 有界实测，T15 待本人验收，T16 仅合成单用户基线，T17 PARTIAL；完整产品仍 PARTIAL。开发入口见 [DSH-BASE-COMPAT](./DSH-BASE-COMPAT.md) 和 [dsh-dev](../../scripts/dsh-dev/README.md)。

2026-09-10 追加：#115 候选 `8c2e676` 的必需 CI 已通过，仍为 draft。数值增量已完成显式计算、可信快照与认可成板：完整合成后端 2315 passed / 77 skipped，B0 全流程 PASS；两条真实 DeepSeek 评测得到 410/305 和 400/300，后一结果成板后刷新仍一致。4325/18083 已更新，旧板和草稿保留。增量未提交，完整产品仍 PARTIAL；见[本轮交付与边界](DIAGNOSIS-INTEGRATION-DELIVERY-2026-09-10.md)和[工程计划](DIAGNOSIS-INTEGRATION-PLAN-2026-09-10.md)。

## 当前采用的目标方案（2026-09-09）

并行开发交接：[Grok总控与9个角色任务包](./parallel-competition-2026-09-09/README.md) 保留当时的任务拆分、所有权和验收合同；代码已由 #112 集成、#114 补修。任务包不是当前执行状态源，当前状态以顶部账本和证据为准。

本轮[总计划§12](./PLAN-CLOSEOUT-2026-09-05.md)更新首版为自由诊断 → 批量可编辑看板 → 召回候选与行动草稿；保留 DSH 全功能，前台采用自有比赛品牌/Ant Design。旧 CRM API-01–06 与口径、工具合同同步纳主线；三问是已实现基线，候选不再计划延期。[评审附件](./AUTOPLAN-COMPETITION-REVIEW-2026-09-09.md)与[验收计划](./COMPETITION-TEST-PLAN-2026-09-09.md)记录本次修改，未代表API修复/新UI实现。以下保留历史时点。

**首购发布历史（2026-09-09）**：v0.7.0.0 已经 [PR #108](https://github.com/weiweity/fuqing-crm-analytics/pull/108) 合入 `d95e504`，PR CI 必需检查通过。本机 DSH 合成演示已验证首购查询→保存分析→加入驾驶舱；使用本地 stub，真实模型和公网未验。见 [发布收尾](./RELEASE-0700-CLOSEOUT-2026-09-09.md)。以下各轮记录保留其历史时点。

**当前第二轮结果**：[候选复核与资产集成](./PARALLEL-ROUND2-REVIEW-2026-09-08.md) 保留历史阻断。2026-09-09 已在集成 worktree 接通首购原生持久绑定、在途协议、decoder/编译后卡片与查询→保存→驾驶舱合成闭环；候选人群仍未开放。原生浏览器 stub 合成查询→总结→保存→驾驶舱→脱离会话重读已补验通过；真实模型仍 NOT RUN。交接见 [HANDOFF](./FIRST-PURCHASE-NATIVE-HANDOFF-2026-09-09.md)，交付记录见 [闭环](./FIRST-PURCHASE-NATIVE-LOOP-2026-09-09.md)。

**上一轮本地工作**：[首购查询 / W4 并行集成清单](./PARALLEL-QUERY-W4-INTEGRATION-2026-09-08.md)。两个候选已收到，Codex 已完成共享内核、物理 worker、独立 HTTP 和 W4 最小层集成；本轮 pipeline 405 项 Python 测试通过，W1–W3 另跑 27 项通过。详见 [集成结果](./PARALLEL-INTEGRATION-RESULT-2026-09-08.md) 与 [HTTP 使用说明](./FIRST-PURCHASE-SHARED-HTTP.md)。当时尚未提交、首购 native UI 未验收；已由 #108 的合成原生闭环证据更新。

开发入口：[唯一 Agent 规则](../../AGENTS.md)；[2026-09-06 规则统一与项目盘查](./AGENT-RULES-AUDIT-2026-09-06.md)记录 Astra 工作方式适配、旧自动化停用及未删除候选，不改变 B0 业务验收结论。

**Git 收口（2026-09-08）**：本次核验基线 `origin/main` = `3ec1c86`（#107）。#100 v0.6.0.0 查询资产驾驶舱、#102 v0.6.1.0 overlay 编译后 DOM、#103 v0.6.2.0 加入重试/不串板、#104 v0.6.3.0 首购离线金标准、#105–#107 hackathon README 收口已 squash 合入；#85–#99 依赖与 ruff 0.16.6（`lint.select` 仍为 0.15 的 `E4/E7/E9/F`）已合入。公网部署仍暂缓。产品仍 PARTIAL。

**并行 gstack Goal（2026-09-08，已结束交付）**：双轨已串行 `/ship` + `/land-and-deploy`。[#103](https://github.com/weiweity/fuqing-crm-analytics/pull/103) v0.6.2.0 overlay：保存成功后 join 4xx/409 只重试加入；两 CONNECTED overlay 不串板；切分析面板不把卸载控件当 hang。[#104](https://github.com/weiweity/fuqing-crm-analytics/pull/104) v0.6.3.0 首购离线金标准：JSON snapshot 变换，缺商品角色整查询拒绝且不输出转化率。该历史版本 catalog / HTTP / worker 当时仍 DEFERRED；后续 #108 的 worker/HTTP/合成 native 已通过，首购 catalog 为 SUPPORTED_CONTRACT；候选人群仍 DEFERRED。计划原稿仍是本地未跟踪文件，不代表仓库已收录。

**8 小时 Goal 当时口径（2026-09-07，已结束交付）**：[Goal 计划](./GOAL-8H-CODEX-GROK-2026-09-07.md) 做过本地 synthetic G0–G5。它承接历史 B0 PARTIAL，不是重跑 T01–T09，也不是 B1–B4 完整产品。当时 Git 是 `PR_DELIVERY`（分支/commit/push/小 PR）；**之后**已获 merge 授权并把队列合进 `main`。不要把「未授权 merge」当成现在的指令。G0 文档单元当时未跑业务测试。T09 `bd6d8fe` / [PR #69](https://github.com/weiweity/fuqing-crm-analytics/pull/69)；G1 `857d2ce` / [PR #70](https://github.com/weiweity/fuqing-crm-analytics/pull/70)。G2a–G4b 报告仍是当时证据。G4a 浏览器当时 **NOT RUN**。G4b 核心 native PASS（`runtime-zPbEKI`）。交接快照见 [Goal 结果](./GOAL-8H-RESULT-2026-09-07.md)。v0.6.0.0 opt-in `--native-query-assets`：SUCCEEDED 查询保存为 SNAPSHOT，「我的驾驶舱」HTTP overlay 查看/加入/复制/预览/撤销；默认查询入口不带资产。见 [CHANGELOG](../../CHANGELOG.md) 与 [插件 README](../../dsh-plugins/analytics-workbench/README.md)。

2026-09-06 的工作流治理见 [治理实施记录](./WORKFLOW-GOVERNANCE-2026-09-06.md)；阶段 Git 见 [阶段 Git 与 QA](./PHASE-GIT-QA-2026-09-06.md)，日常命令见 [验证入口](../operating/verification.md)。第 1、2 项当时由 [PR #67](https://github.com/weiweity/fuqing-crm-analytics/pull/67) 合入 `ee66469`（**不是**现在的 `origin/main`）。T09 见 [原生故障与监督器](./B0-NATIVE-FAULT-2026-09-07.md)。整体 B0 仍 PARTIAL。G2a/G3a 合同与离线计算见上表。

阶段 Git 检查与开放项见[草稿提交检查](./PHASE-DRAFT-REVIEW-2026-09-06.md)。该记录区分局部测试、推送检查和完整产品验收，不以 Draft PR 代替合并或部署许可。

当前任务顺序与状态统一看[方案收口与总待办](./PLAN-CLOSEOUT-2026-09-05.md)：保留原 11 工作包，补齐架构、数仓/ETL 和多人验证依赖。10 人使用、峰值 5 人分析、约千万行、T+1、多品牌/店铺隔离是规划输入，不是已测容量。2026-09-06 已从方案收口进入 B0 最小任务内核实施，不等于整包验收通过。

增量审核：[D1–D4 已确认](./ENGINEERING-INCREMENTAL-REVIEW-2026-09-05.md)。T01–T08 保留既有方法/compaction、权限、七问和组件 8 状态证据；最新 [T09 原生故障与监督器验证](./B0-NATIVE-FAULT-2026-09-07.md)补齐真实 worker 故障到原生失败卡、Skill 与分析卡同轮共存、刷新恢复，并修复已复现的 stderr EPIPE 退出及运行中夹具漂移漏记失败。T09 当时本地检查为 167 Python / 138 源 Node / 14 编译与装配；本 Goal 已提交并经 PR #69 CI 对 `bd6d8fe` 成功，原生 `runtime-eDvn6c` PASS。G0 文档单元当时未跑业务测试。G1 已提交 `857d2ce` / PR #70：独立 pipeline 178/143/14，F3 后 7 Node smoke PASS，最终 pre-push 178/145/14；原生四问 `runtime-SNWYss` PASS，第一次 `hkeo4K` F3 失败保留。P1 CI 不是 G1 CI；G1 CI 对 `857d2ce` PASS（34052132760 / 34052132799）。历史三次退出缺少原始原因证据，整体 B0 仍 PARTIAL。

最新开工约束：[视觉、Git/gstack、架构图与技术栈基线](./ENGINEERING-BASELINE-2026-09-05.md)。保持 DSH 单运行时、独立插件和业务服务；视觉以新版 DESIGN.md 的比赛品牌方向为准；B1–B4 完整产品、真实模型、业务 UAT 与公开发布不在本 Goal 范围。本次原生通过项不扩大为全部状态、全部工具或长期稳定性通过。

执行历史：[B0本地DSH验证](./B0-DSH-VALIDATION-2026-09-05.md)、[worker/故障](./B0-WORKER-FAULT-VALIDATION-2026-09-06.md)与[监督器复查](./B0-SUPERVISOR-RECHECK-2026-09-06.md)保留各轮证据与失败。当前分层结果结合 T01–T08 历史与 T09 增量读取；T09 收尾时 B0 临时服务已停止（4315–4319 无监听），这不描述用户另行保留的旧 Mission 演示 8000/5173。G0 文档修订记录时点未启动 B0 服务；禁止把 G0 文档修订声称为新运行或原生四问验证。此前“实施未授权”为静态审查时记录；B0 队列随后获本地实施授权；PR #67 另获合并授权；当前 Goal 另获 synthetic G0–G5 与 scoped Git 授权。均不代表完整实现、付费模型或公网已授权。

商业逻辑已收口：**让老板批准一个有边界的天猫内部跨渠道客户增长试点，优先验证“渠道 × 首购商品 × 后续购买”的客户承接路径。** CEO 拍板经营优先级、资源、负责人和继续/停止条件；名单导出是运营执行环节，不代表已批准真实营销。

“统一分析工作台”方向保留：问数＋画布、分析保存、驾驶舱和标准 BI 复用。专家与自动化不单独扩成平台。单一在线 Agent 主运行时原则保留；用户已确认新 UI 采用 DSH 原生 Web，现进入最小业务插件交互设计。运行时、安全和模型仍待工程验证，不把 UI 选择当作集成通过，也不叠加 Hermes/StaffDeck。**商业逻辑与 UI 方向已确认；新版底座集成与新功能尚未验收。**

最新确认的目标：**板块插件化、驾驶舱配置化、AI局部编辑**，以及“先登记业务任务，再交DSH”。老板可自主组合、预览/保存/撤销，通过固定入口每天查看；已有资产可无会话/无模型刷新，历史/审批快照不漂移。工程静态复审已收口，B0只实现一个静态合成板块和标题编辑承载，不是上述完整功能；未创建日更/推送任务。

- [CEO 价值与首版决策方案](./CEO-VALUE-PLAN.md)：最新商业口径主源；用户已批准定稿，状态为 APPROVED；不代表工程或业务效果验收。
- [DSH 原生 UI 交互设计](./DSH-UI-INTERACTION-SPEC.md)：当前设计主源；S0–S6流程、真实插槽、分析资产弹层与验证卡；B0小样部分验证，完整交互未验收。
- [产品与实施计划 v2.3](./UNIFIED-ANALYTICS-PLAN.md)：保留历史autoplan及工程复审；B0内核片段已实施，完整合同/金标准→纵向闭环→本地验收仍待完成。
- [8 小时 Goal 计划](./GOAL-8H-CODEX-GROK-2026-09-07.md)：当前 synthetic G0–G5 执行入口；启动账本不在本文重复计时。
- [T09 原生故障与监督器](./B0-NATIVE-FAULT-2026-09-07.md)：历史 B0 最新本地验收与开放项；
- [G1 原生 running / 非法结果拒绝](./B0-NATIVE-STATE-2026-09-07.md)：本范围原生四问 PASS（`runtime-SNWYss`）；第一次 `hkeo4K` F3 失败保留；源码已提交 `857d2ce` / PR #70；
- [渠道首次观察队列合同与金标准](./CHANNEL-FOLLOWUP-CONTRACT-2026-09-07.md)：G2a `analytics-channel-followup/v1` 独立合同与手算金标准；
- [渠道首次观察队列离线计算](./CHANNEL-FOLLOWUP-COMPUTE-2026-09-07.md)：G3a 从 G2 输入计算 G2 结果；worker/HTTP/native 未实现；
- [渠道首次观察队列受信 run 绑定](./CHANNEL-FOLLOWUP-RUN-BINDING-2026-09-07.md)：G3b1 单族 RunStore / 独立 query-run 合同；store-only 基线；
- [渠道首次观察队列共享 worker](./CHANNEL-FOLLOWUP-WORKER-2026-09-07.md)：G3b2 backend 共享 worker 合成查询；HTTP/native 当时 **NOT RUN**；
- [渠道首次观察队列 native 接通（G4a）](./CHANNEL-FOLLOWUP-NATIVE-G4A-2026-09-07.md)：ASGI/真实 worker/真实 Cordis loader PASS；浏览器/Gateway/卡片 **NOT RUN**，G4 未完成；
- [渠道首次观察队列双会话原生查询（G4b）](./CHANNEL-FOLLOWUP-NATIVE-G4B-2026-09-07.md)：核心 native PASS（fresh `runtime-zPbEKI`）；初始 FAIL 与手工 verify-existing 层级保留；
- [查询资产 HTTP overlay（v0.6.0.0；v0.6.1.0 补编译后 DOM）](../../CHANGELOG.md)：opt-in `--native-query-assets`；独立 `/b0/analyses` 与 `/b0/dashboards`；默认查询入口不带资产；overlay 撤销整板/加入/无板创建/409 重读有 mock 编译后 DOM；产品仍 PARTIAL；
- [8 小时 Goal 交接（G5）](./GOAL-8H-RESULT-2026-09-07.md)：当时提交前快照。2026-09-08 起相关 PR 已合入 `main`（见上文 Git 收口）；
- [B0 工具卡 DOM 增量](./B0-TOOL-CARD-DOM-2026-09-06.md) / [T01–T09 清单](./B0-EXECUTION-CHECKLIST-2026-09-06.md)：历史 B0 当轮入口；[T01–T07 收口](./B0-LOCAL-CLOSEOUT-2026-09-06.md)保留既有分层验收、开放风险和服务收尾。
- [B0 方法与上下文](./B0-METHOD-CONTROL-VALIDATION-2026-09-06.md) / [当前控制面清单](./B0-CONTROL-MANIFEST-2026-09-06.md)：整包、原生组件压缩及持续权限修复的红/绿证据。
- [B0 监督器复查与工程阶段](./B0-SUPERVISOR-RECHECK-2026-09-06.md)：历史专项入口；七问单次 PASS，历史退出根因仍未解。
- [B0 worker 与故障验证](./B0-WORKER-FAULT-VALIDATION-2026-09-06.md)：物理只读 worker、进程/提交故障、资源负测、151/92 项本地测试及上一轮失败证据。
- [B0 原生接线与固定构建](./B0-DSH-KERNEL-INTEGRATION-2026-09-06.md)：上一单元的原生五问与构建证据，不替代本轮扩展旅程结果。
- [首个 B0 任务内核代码与验证](./B0-RUN-KERNEL-2026-09-06.md)：首单元历史，局部接口、落盘/权限/预算测试与离线类型；其未接 DSH 状态已由后续报告更新。
- [AI工程复审报告](./AI-ENGINEERING-REVIEW-2026-09-05.md)：Harness/MCP/Skill/上下文/记忆/多Agent/长任务与驾驶舱；13项发现、复用边界、故障/测试地图及独立来源；静态收口不是运行通过。
- [autoplan 评审记录](./AUTOPLAN-REVIEW-2026-09-05.md)：前提已批准，方案审查完成；Claude实际路由为MiniMax、视觉未渲染，降级已注明，不是实现通过报告。
- [11项实施检查表](./AUTOPLAN-IMPLEMENTATION-TASKS-2026-09-05.md)：C-T1承载验证部分完成，其余正式工作包待实施。
- [分阶段评审依据](./AUTOPLAN-PHASES-2026-09-05.md) / [测试地图](./AUTOPLAN-TEST-PLAN-2026-09-05.md) / [延后TODO](./TODOS.md)：保留论证、失败路径、人工fixture及后续工作。
- [D3 最小任务故障测试地图](./ENGINEERING-RUN-TEST-PLAN-2026-09-06.md)：保留全地图；落盘/受控进程与部分固定 DSH 原生接线已有证据，不能据此勾选整图通过。
- [接口与数据对象草案](./ANALYTICS-CONTRACTS-DRAFT.md)：完整产品 API 仍 DRAFT；B0 `analytics-run-b0/v1` 子集已实现并已接原生 DSH，固定 fixture 不是三类业务查询。G2a 另有独立查询合同子集，见上条。
- [底座与业务闭环验收](./RUNTIME-VALIDATION-PLAN.md)：B0–B4验证顺序；B0小样证据另表记录，完整用例矩阵仍未通过。
- [商业战略与采用记录](./STRATEGY-DECISIONS-2026-09-05.md)：跨渠道价值账、经营动作比较与本轮方向确认。
- [本地 RFM 证据收尾](./RFM-LOCAL-EVIDENCE-2026-09-05.md)：PC2 已移出范围；源码事实、隔离验证与后续性能门分开记录。
- [分析性能首轮实现与数据面路线](./ANALYTICS-PERFORMANCE-2026-09-05.md)：统一资源预算、派样聚合优化、整数键合成对照；已完成首轮局部验证，千万行 RFM 与多人重分析未验收。
- [ETL 诊断与证据留存](./ETL-DIAGNOSIS-2026-09-05.md)：重复读入/预计算、中间结果和增量正确性；上一轮隔离复现与静态推断分开，未执行真实 ETL 或重构。

当前只推进本地环境，PC2 不纳入；用户后续已认可把 RFM/派样/ETL 一起纳入优化规划，具体为总清单 W1–W5/V1–V4，替代此前“留到以后再讨论”的排期。它们不要求先迁移真实大库，也不阻止小合成 B0 验证；实际接入与容量声明仍须通过正确性、资源隔离和权限测试，不能用旧 Mission 通过代替，也不扩大现有 synthetic Mission 免登录范围。

以下内容继续作为**现有 Mission 演示基线与历史验证记录**，本轮没有重新运行应用。新方案取代其“唯一 Mission 为默认入口”的目标编排，不修改现有路由/API。CEO 话术与报名文案已同步最新价值逻辑，但新版交付声明仍须在提交前按实际验收结果确认；本地完成不等于网址已提交。

## 文档索引

- [CEO 口语话术与演示脚本](./CEO-PITCH.md)
- [黑客松报名与作品文案](./SUBMISSION-COPY.md)
- [AI 调用 Mission API 指南](./AI-TOOL-CALLING.md)
- [Mission HTTP 契约](./MISSION-API.md)
- [架构、质量证据与提交收口审计](./ARCHITECTURE-AND-RELEASE-AUDIT.md)
- [Mission 阶段路线与历史验证快照](./ROADMAP.md)
- [CEO 价值与行业验证底稿](./research/report-source.md)
- [伸美视觉与交互基线](../../DESIGN.md)
- [Figma 可编辑稿同步清单](./FIGMA-SYNC.md)

## 当前 Mission 演示主链

```text
Mission GET /today
  → CEO 增长董事会首屏
  → 受控自由问数
  → CEO 审批
  → DRAFT_EXPORT_READY
  → WAITING_MEASUREMENT
```

该旧演示固定展示一个合成情景：直播首次观察到的付费用户更多，货架客户的二单率和 180 天价值更高，并据此准备“直播首购·待补货”人群草案。这不是公司真实渠道排名，不是因果归因，也不是新版工作台必须生成的唯一建议。

## 评委演示

1. 本地启用免登录模式后，直接打开 `/` 或 `/login` 均进入 `/growth-board`；公网部署暂缓。
2. 先讲“直播规模第一、货架质量第一”的经营冲突，再点三个建议问题之一验证证据链。
3. 点击“审批并生成 DRAFT_EXPORT”，明确系统只生成 90/10 合成人群草稿，不自动发送短信。
4. 下载 CSV，展示同一 `synthetic_user_id` 可跨渠道关联；刷新页面后下载入口仍会保留。
5. 本地需要重复演示时点击“重置演示”；免登录演示身份或普通模式的管理员可用，仍受独立环境开关控制，公网默认不出现。

演示前需按 [`scripts/synthetic/README.md`](../../scripts/synthetic/README.md) 生成数据，并在部署环境显式配置 `.env.example` 中的四个 `FQ_MISSION_*` 变量。

### 本地免登录（2026-09-05）

在已有 synthetic 数据和 Mission 环境配置上额外设置 `FQ_LOCAL_DEMO_NO_LOGIN=1`，通过 `./scripts/ops/start-stack.sh` 启动；服务仍只监听 `127.0.0.1`。环境变量变更需要先用 `stop-stack.sh` 停止本工作树服务，再按原有配置启动，不是前端热更新即可生效。

- `GET /api/v1/missions/access` 返回不缓存的服务端能力；前端不存假 token、不内置账号密码，也不把演示身份升级为管理员。
- 只有本地请求的 synthetic Mission 链路免登录，界面只保留增长董事会入口；真实 CRM 与运维接口仍需认证。
- 免登录模式启动仅校验合成数据，跳过旧 CRM 数据库启动校验、缓存预热与后台任务。
- 审批记录使用 `LOCAL_SYNTHETIC_DEMO`，不代表真实 CEO 身份。版本、幂等、审批前不得导出、90/10 分组和 synthetic manifest 校验不变。
- 禁止把本地服务经公网隧道转发；公网模式必须显式设置 `FQ_LOCAL_DEMO_NO_LOGIN=0` 并恢复正式访问控制。Host、来源和代理头检查是额外防线，不替代部署边界。
- 恢复登录：设置 `FQ_LOCAL_DEMO_NO_LOGIN=0` 并重启服务、刷新页面。所有普通账号/密码配置无需改动。

本地验证（2026-09-05）：前端 23 文件 / 201 项单测通过，类型检查与构建通过；后端 `test_local_demo_access`、`test_missions_api`、`test_security_p0_auth`、`test_admin_auth` 共 49 项通过。独立 Chromium 实测 `/login` → `/growth-board`，`hasToken=false`，无密码框；真实 `/api/v1/core/summary` 无认证返回 401。标签页引用 `/shine-mage-mark.svg`，独立渲染确认仅有原紫色帽子。浏览器控制插件会暂时覆盖 favicon，应用原始 HTML 与独立浏览器结果用于区分插件覆盖和应用缺陷。

## 边界

- 公网演示仅使用 `data_profile=synthetic` 且 `contains_real_data=false` 的数据集。
- `FQ_MISSION_DEMO_ENABLED` 默认关闭；Mission 不会回退到真实 `DUCKDB_PATH`。
- `FQ_MISSION_DEMO_RESET_ENABLED` 默认关闭；只在受控本地演示临时开启。
- 问数只调用已测试的语义视图，不执行模型生成的任意 SQL。
- 未审批不生成名单；草稿名单只包含合成用户 ID、Mission ID 和实验分组。
- `DRAFT_EXPORT_READY` 不等于短信已发送，也不等于已对接 CRM。

接口、幂等与状态转换见 [MISSION-API.md](./MISSION-API.md)，合成数据生成见 [`scripts/synthetic/README.md`](../../scripts/synthetic/README.md)。

诊断取消增量：见[交付与边界](DIAGNOSIS-CANCELLATION-2026-09-10.md)，实际 transport/HTTP/SQLite 通过，完整后端 2320 passed / 77 skipped、B0 PASS；浏览器原生取消全路径仍独立记录。
