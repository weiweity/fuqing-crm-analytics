# autoplan 评审记录 · 2026-09-05

Status: REVIEWED_WITH_DEGRADATIONS / AWAITING_FINAL_APPROVAL

时点说明（2026-09-06）：以上状态与下文“最终方案待批/未授权实现”是本次历史评审的启动快照，保留原模型/视觉降级，不作为当前开工阻断。后续已批准 B0 与 D1–D4，四节增量静态审核完成；当前状态见[总待办](./PLAN-CLOSEOUT-2026-09-05.md)，本地首个内核单元见[实现报告](./B0-RUN-KERNEL-2026-09-06.md)。本次没有重新执行本报告四阶段或据此批准整包/发布。

前提批准记录：2026-09-05，用户确认“没问题，先这样进行”。P1–P5 已通过；CEO→Design→Engineering→DX 已顺序完成方案审查，以下事实盘点保留为启动快照。最终方案仍待批准，未授权实现或发布。

用户明确调用 autoplan 并批准本轮前提。本文记录评审过程及降级，不是测试通过报告；执行主源是已重排的实施计划，商业定位继续沿用已批准方案。

## 1. 目标与基线

- 商业主源：[CEO 价值方案](./CEO-VALUE-PLAN.md)，APPROVED；不重新表决已确认的统一分析工作台和经营主线。
- 计划对象：[实施计划 v2](./UNIFIED-ANALYTICS-PLAN.md)，REVIEWED_WITH_DEGRADATIONS / AWAITING_APPROVAL。
- 工作树：`/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/.worktrees/hackathon-mission-mvp`。
- 分支：`codex/shine-mage-figma-refinement`；HEAD：`de2d785`。
- 当前分支没有匹配 PR；GitHub 仓库默认分支实查为 `main`。本地 `origin/main` 用于初步差异盘点，未 fetch，不声称它等于远端最新提交。
- 已阅读归档边界、工作树 AGENTS.md 和 DESIGN.md；未发现工作树 .codegraph 或 TODOS.md，不创建索引。
- 已有大量未提交/未跟踪改动，全部保留。基于本地 origin/main 的 tracked diff 为 59 文件，不含未跟踪方案和资产，不作本轮改动量或完成度。

原工程草案恢复副本：
[autoplan restore point](/Users/hutou/.gstack/projects/weiweity-fuqing-crm-analytics/codex-shine-mage-figma-refinement-autoplan-restore-20260905-112331.md)

原文 SHA-256：`2614efaff79238d307c0ee799f981014ed611521e11fb186d9bce4abbaa32798`。恢复副本是本轮任务产物，不更新长期记忆或全局学习记录。正文最后的 Original Plan State 保存评审启动前原文，恢复前仍须检查后续改动，禁止覆盖他人工作。

## 2. 已确认的本轮前提

| ID | 前提 | 依据与边界 |
|---|---|---|
| P1 | 首版证明“渠道 × 首购商品 × 后续购买”，帮助老板决定是否开展有边界的天猫内部客户增长试点 | 沿用已批准的商业方案；合成演示不能证明真实增量或因果获客 |
| P2 | 一个统一工作台承载问数、分析、保存和驾驶舱/标准 BI 复用，不新增独立员工平台 | 已有用户选择；动作草案不能用旧固定 Mission 人群冒充新分析结果 |
| P3 | 复用现有业务后端、确定性指标、Mission 和 BI；比较原生 Web UI 的最小改动承载，采用单一在线 Agent 主运行时 | Hermes / DeepSeek Harness 均未最终选定；如需改变用户已选方向，列为用户裁决，不能自行改成既定方案 |
| P4 | 本轮只做方案和评审；本地合成演示为首版目标，暂不处理 PC2、旧 RFM 性能改造、公网部署和真实 CRM/短信 | 不读取或修改归档真库，不启动服务、不实现代码、不提交/推送/部署；接入路径仍必须有自己的质量和安全验收 |
| P5 | 9 月 10 日的网址提交仍为独立待办；当前不能用本地完成代替提交 | 工程评审须按期限重新排优先级，但不擅自开公网隧道、启用外部发送或承诺未测功能 |

这些前提包含对已有决定的复用，不表示用户需要从头讨论商业定位。autoplan 的前提关卡已通过；各阶段完成仍需对应产物，不由前提批准代替。

## 3. 初步事实盘点（源码静态，不是验收）

独立子 agent 完成只读索引；主审复核了问数请求、关键词分派与前端状态。子 agent 与主审为同模型环境，不宣称跨模型共识。

| 当前资产 | 可定位的源码证据 | 不能据此推定 |
|---|---|---|
| Mission HTTP 链 | [missions.py](../../backend/routers/missions.py)，today / diagnose / approve / export / download | 新 analytics HTTP 路由已存在 |
| 代码生成合成数据 | [generate_hackathon_dataset.py](../../scripts/synthetic/generate_hackathon_dataset.py)，generate_dataset 与 _create_semantic_views | 当前服务已加载该数据；新增指标已通过独立金标准 |
| 数据来源和控制库隔离 | [mission_service.py](../../backend/services/mission_service.py)，manifest/哈希检查、只读分析连接、SQLite 控制状态 | 真实环境配置与新分析隔离已经验收 |
| 本地免登录保护 | [local_demo_access.py](../../backend/services/local_demo_access.py)，限定 Mission 路由、回环与代理头检查 | 可以匿名公开真实 CRM 或已经有生产 CEO 审批角色 |
| 问数请求与回答 | [mission.py](../../backend/contracts/mission.py) 的 DiagnoseRequest 只有 question；mission_service.diagnose 按三类关键词确定性分派 | 多轮上下文、自由问数、未知问题澄清已完成；当前其他问题会落入渠道兜底 |
| Vue 当前交互 | [GrowthBoardView.vue](../../frontend-vue3/src/views/GrowthBoardView.vue) 的 ask 替换单个 diagnosis | 已经有会话消息列表、SavedAnalysis 或分析画布合同 |
| 审批与导出 | mission_service.approve / create_draft_export，基于旧 Mission snapshot 与待补货人群 | 任意新分析都能生成对应人群；真实触达和效果回流已实现 |
| 筛选基础 | [useFilterSync.ts](../../frontend-vue3/src/composables/useFilterSync.ts) 与 filterStore | 跨看板完整条件、数据版本、口径版本已一致；旧 BI 已可匿名合成访问 |
| 回归资产 | [test_missions_api.py](../../backend/tests/test_missions_api.py)、[test_local_demo_access.py](../../backend/tests/test_local_demo_access.py)、[GrowthBoardView.test.ts](../../frontend-vue3/src/views/GrowthBoardView.test.ts) | 本轮测试已运行或新版能力已通过 |

子 agent 在 backend、frontend-vue3/src、scripts、mcp_servers 中定向搜索，未找到新版 SavedAnalysis、多轮上下文或 Hermes/DeepSeek runtime adapter 实现。这是当前搜索范围内的否定证据，不是对磁盘所有目录的穷尽证明。

## 4. 启动时登记的旧计划冲突（已在 v2 处理）

1. 旧 G1 仍要求先完成 RFM P01–P06。用户已明确先不处理旧 RFM；应在工程计划重排时移除这项前置，同时保留新接入分析路径必要的金标准、资源、权限验证。
2. 旧草案仍把 Hermes 优先和一个 Vue 前端写入架构。最新商业方案明确原生 Web UI 与运行时待验证，不能把任何候选写成已验收底座。
3. 旧问数的固定关键词和单结果状态，不覆盖新版连续追问、保存、复用。必须评估新增合同与真实交互，不只换文案或聊天皮肤。
4. 旧导出基于固定 Mission 人群。新分析到行动之间的条件/数据版本/人群绑定需要独立验收，失败时保留明确分开的旧演示。

处理结果：移除旧RFM前置、将承载/运行时改为B0硬门验证、新建分析合同和全状态、人群草案绑定单独验收。以下阶段记录与主计划为当前结论。

## 5. 四阶段结果与工具身份

| 阶段 | 审查结果 | 产物 |
|---|---|---|
| 0 准备/前提 | 完成；用户已确认 | 原文恢复点、规则/源码/品牌/商业基线、P1–P5 |
| 1 CEO | 完成方案审查；11节，Claude N/A | 3候选、复用/范围、错误恢复、安全/失败、长期差距、2轮文档复核 |
| 2 Design | 完成静态计划审查；渲染NOT RUN | 7维、状态表、litmus、布局/无障碍/品牌；规范明确度5.6→8.0 |
| 3 Engineering | 完成方案审查；测试NOT RUN | 4节、源码证据、订单fixture、状态/短锁导出、完整测试地图 |
| 3.5 DX | 完成8pass；首次成功时间未测 | persona/模拟旅程、9阶段、3方文档参照、接口恢复/兼容；规范明确度4.4→7.9 |
| 4 最终关卡 | AWAITING_FINAL_APPROVAL | 33项审计决定、11项聚合任务、TODO、来源矩阵 |

详细完整审查见 [分阶段依据](./AUTOPLAN-PHASES-2026-09-05.md)。评分只是主观的文档明确度，不是页面或产品验收分。

CLI实查：Codex 0.153.0、Claude Code 2.1.260。Codex预检往返OK，随后CEO/Design/Eng/DX各1次只读文档/源码输入审查，均返回成功。CEO调用Claude CLI默认返回实际模型MiniMax-M3[1m]，再用opus别名做最小探针仍为MiniMax-M3[1M]；因此没有经过验证的Anthropic Claude声音。MiniMax首次CEO意见保留为补充，不偷换标签。

外部审查按阶段串行，未并行跑四阶段；证据agent只辅助事实/fixture或文档一致性。CEO Codex提出3项、Design4项、Eng5项、DX4项，已逐条处理。正式Claude–Codex共识均N/A，不能称两模型一致通过。未变更模型登录/配置、未安装运行时、未调用产品的在线模型；本次发生的是评审CLI调用，不是产品链路验收。供应方返回的费用估计不是已核实账单，未把它当产品成本测量。

设计工具SSOT路径可执行但需要单独图像API；本轮不额外付费制图、不启动渲染服务，因此采用静态规范。既有灰度HTML是历史手工示意，没有改造成运行证明。视觉降级在最终门显式保留。

## 6. Decision Audit Trail

准备决定AP-000至AP-005沿用：只评审、商业主源优先、先留恢复点、用户批准前提、UI/DX适用、保留脏改动。详细33项本轮范围内决定C01–C11/D01–D06/E01–E07/X01–X09写在 [主计划审计表](./UNIFIED-ANALYTICS-PLAN.md#decision-audit-trail)，每项有理由和边界。

没有自动改变已批准商业方向；没有新增品牌口味选择。运行时/承载最终选择不是假定已通过，由B0限时实证决定；账号/费用与公网仍独立确认。用户最终批准的是整个修订方案，不由本轮“前提认可”替代。

## 7. 聚合、留存与验证

- 11项实施任务从4份任务JSONL实读聚合，过滤当前branch与最近5个本地commit、每阶段最新run，再按component/sorted(files)/title精确去重。重复风险与共享文件在 [检查表](./AUTOPLAN-IMPLEMENTATION-TASKS-2026-09-05.md) 明示。
- 机器任务产物：`/Users/hutou/.gstack/projects/weiweity-fuqing-crm-analytics/tasks-{ceo-review,design-review,eng-review,devex-review}-20260905-114500.jsonl`；它们是本任务产物，不是记忆或遥测。
- [测试地图](./AUTOPLAN-TEST-PLAN-2026-09-05.md) 包含8组人工期望、全分支/7业务项映射、模型60次初筛目标与资源阈值；全部NOT RUN。
- [延后TODO](./TODOS.md) 保留网址交付、订阅、专家模板、多人状态、实际平台/CRM；不默认执行。
- 末尾验证：11份本轮相关文档的116个本地链接目标全部存在，无尾部空白；主计划章节1–11顺序正确、33个审计ID唯一；git diff --check通过。原文恢复副本按真实标题边界提取后SHA与原记录一致。以上不包含浏览器、单元、集成、数据/模型产品链路验收。
- 现有大量代码/视觉/认证脏改动保留；本轮只写计划、合同/验收设计、审计、TODO和首页入口。无代码实现、启动、数据库读取/写入、Git提交/推送/合并、消息或公网部署。

成功review gate日志按autoplan留到用户最终批准后，不提前写clean状态。本次不修改gstack配置、长期记忆或全局学习/遥测。

最后跨文档审阅第二轮只复核5项修订，全部闭合，未发现这些项的剩余矛盾；该结果仅为文档一致性，不是实现通过。

## GSTACK REVIEW REPORT

VERDICT: REVIEWED_WITH_DEGRADATIONS / AWAITING_FINAL_APPROVAL
CEO / Design / Engineering / DX：方案审查完成，详细缺席/未测项已列。
UNRESOLVED：最终方案批准；B0承载实证选择；产品模型/费用；未来公网授权。
Implementation：NOT STARTED / NOT AUTHORIZED BY THIS REVIEW
