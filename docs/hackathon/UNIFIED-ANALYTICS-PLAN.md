<!-- /autoplan restore point: /Users/hutou/.gstack/projects/weiweity-fuqing-crm-analytics/codex-shine-mage-figma-refinement-autoplan-restore-20260905-112331.md -->
# 伸美统一分析工作台：实施计划 v2.3
日期：2026-09-05。Status: REVIEWED_WITH_DEGRADATIONS / UI_DIRECTION_CONFIRMED / B0_PARTIAL。

当前收口入口：[总待办](./PLAN-CLOSEOUT-2026-09-05.md)。本文保留产品范围与历史评审；最新架构/数据排期以总待办为准：10 人使用、峰值 5 人分析、约千万行、T+1、多品牌/店铺隔离已作为规划输入，RFM/派样/ETL 纳入共享数据线。下文“旧 RFM 暂后置”是当时排期，不再解释为无需规划；真实库/PC2/公网仍排除，本地 SQLite B0 不代表多人方案已验收。后续[工程基线增量审核](./ENGINEERING-INCREMENTAL-REVIEW-2026-09-05.md) D1–D4 已确认、四节静态审核完成，不覆盖本文件历史模型/视觉降级。

执行更新：用户已授权仅B0安装、最小代码及临时合成/stub运行；[两轮证据](./B0-DSH-VALIDATION-2026-09-05.md)已留存且临时服务停止。UI承载/隔离部分通过，业务run取消与恢复硬门仍开放；B1–B4正式实施尚未开始。以下工程复审的未实施表述保留其时点，不覆盖此更新。

2026-09-06 实施续接：[首个 B0 任务内核单元](./B0-RUN-KERNEL-2026-09-06.md)已完成隔离 FastAPI 合同、持久状态/预算、离线生成类型与局部故障验证。DSH adapter、原生取消/恢复、固定构建/CI 和资源实测仍未完成，A2 与 C-T1 不勾选全通过。后续按小代码单元“实施→测试→/review”，涉及新 UI 再做视觉/交互 QA，不重跑已收口的商业 plan。

本次增量：用户确认可组装驾驶舱及A1“先登记业务任务，再交给DSH”；常规工程细化授权继续推进，仅产品取舍、费用/权限、重大范围改变需停下确认。已完成[AI工程静态复审](./AI-ENGINEERING-REVIEW-2026-09-05.md)四节、独立复核及任务/测试映射。当前交互主源为[DSH原生UI设计](./DSH-UI-INTERACTION-SPEC.md)。未重跑全套autoplan，不改变历史评审等级；正式业务实现、真实模型和完整产品浏览器流程仍未验收。

商业主源仍为 [CEO 价值方案](./CEO-VALUE-PLAN.md)。本文件替代 v1 的执行顺序；原草案已保存恢复副本。四阶段进度见 [评审审计](./AUTOPLAN-REVIEW-2026-09-05.md)，逐节论证、错误登记、失败模式、外部意见见 [分阶段审查依据](./AUTOPLAN-PHASES-2026-09-05.md)，它们是本计划的评审附录。

## 1. 拍板目标与交付边界

增量工程 D1–D4 已确认：将 E-T1/E-T2/X-T1 的最小 FastAPI 任务合同与内核前置到 B0（登记、派发、查询、取消、重启恢复），Node 仅协议转发；插件固定构建、落盘/进程测试与独立资源配置同批交付。此更新优先于下文“B0 后才实施”的绝对顺序；完整金标准、资产、驾驶舱与营销仍按原关卡。内核、DSH 接线与只读 worker 已有局部实测，扩展七问取得单次 PASS；历史监督器退出未定位，B0 PARTIAL 不变，见[最新复查与工程阶段](./B0-SUPERVISOR-RECHECK-2026-09-06.md)和[增量审核记录](./ENGINEERING-INCREMENTAL-REVIEW-2026-09-05.md)。

让老板看清哪条“渠道 × 首购商品 × 后续购买”的客户路径值得验证，并决定是否准备有资源上限、负责人和停止条件的增长试点。AI 负责研究和准备材料，人决定是否行动。

首版必须证明一条完整链：

```text
受控连续追问 → 同口径分析证据 → 保存 → 驾驶舱复用
                                   ├ 支持条件的标准看板
                                   └ 绑定人群的试点草案 → 人类审批 → 合成 DRAFT_EXPORT
```

保留商业方案七项验收。人群绑定没通过时，可独立展示旧 Mission，但必须写“新闭环未完成”，不能把固定旧人群装成当前分析结果。既有 diagnose 只有 question、按关键词分派，不是新多轮 Agent；这些旧实现不作为新功能通过证据。

首版限一个业务专家、三类受控查询、一个可组装的私人驾驶舱及一个 synthetic 标准看板适配；聊天中的自然语言可以变，数值口径和工具能力受控。板块可添加/复制/移除、拖动/缩放、调整展示与条件、预览/保存/撤销；AI只修改明确指定的板块或经确认的全局范围。用受控栅格及已登记板块类型，不搭任意网页代码编辑器、插件市场或第二套BI服务。固定驾驶舱入口不要求老板每天重新聊天；日常最新可用结果与历史证据快照分开。

延后：订阅调度/投递、专家协作与市场、自由工作流、妙搭生成新应用、共享认证分析、任意 SQL。保留后续扩展设计，但不因此先建所有 API/表。旧 RFM 改造、PC2、真库、CRM/短信、公网均不进入本轮实施前置或授权。

这是本地合成演示计划；9 月 10 日网址提交仍独立待完成。本地 PASS ≠ 作品已提交；9 月 8 日检查剩余发布依赖，未获部署授权则明确预警，不开隧道。

## 2. 核心设计与最小改动选择

公司自己持有 SavedAnalysis（分析定义）/ AnalysisRun / CohortBinding / DecisionDraft；不让这些对象只存在于某框架会话中。一个运行时负责 Agent 循环，一个业务后端负责权限、指标、计算、资产与审批。

| 候选 | 尽量复用 | 不可忽略的代价 | 决策规则 |
|---|---|---|---|
| DSH 原生 Web + 业务插件 + 旧 Vue BI | 用户已确认的 UI 设计基线；原生聊天、结果卡和资产弹层 | 两类前端身份/导航桥接、上游开发预览与安全裁剪 | B0验证已选 UI 是否满足硬门，尚未集成验收 |
| Vue/FastAPI + 单个运行时适配 | 当前主题、图表、测试、认证和部署结构 | 需要消息列表和事件呈现 | 仅在 DSH 硬门失败且用户重新确认后评估，不自动切换 |
| Hermes Web / Desktop | Web 配置监控或 Desktop transcript | Web 是 PTY；Desktop 不是可提交的网址；两套插件 SDK 不通用 | 不直接把 Desktop 当网页抄来；仅保留运行时候选 |

B0 为最多 6 个工作小时的验证盒，不是模型计费预算：固定合同/问题→DSH 工作区入口/插槽最小展示→原生发送/停止/重试绑定→权限与工具验证→记录是否满足承载条件。安全失败不靠增加适配代码掩盖。结束时最多一个在线运行时；不能两套都失败后自动发明第三套架构。

硬门：①业务结果与证据可按自有 ID 保存恢复；②多轮/事件/取消可适配；③关闭任意 Shell/文件/网络工具，隔离进程与私有目录；④身份由 FastAPI 决定，不用 runtime profile 授权；⑤原生插槽无需 fork 核心 UI 才能放分析/保存/草案；⑥不会破坏旧 Vue BI/品牌/匿名边界。UI方向已确认，B0部分实际运行，但尚未通过全部硬门；失败需报告，改变承载方案须重新确认。

## 3. 总体架构

```text
DSH 原生 Web ─ Chat / 业务结果卡 / 资产弹层 ──┐
原 Vue 标准 BI / 旧 Mission ─────────────────┤ 同源业务入口，旧私有 BI 保持鉴权
                                            v
                                  FastAPI / capability guard
                         ┌──────────────────┼─────────────────┐
                    Analytics service    Asset repository   Decision binding
                    query/metric catalog    SQLite(local)      Mission adapter
                         │                  runs/evidence       approval/export
                  bounded job manager
                         │
                  per-attempt worker ──只读── synthetic DuckDB + manifest
                         ^
                  one runtime adapter ── 获准的模型
                 不授予任意SQL/Shell/文件能力
```

新分析接口默认关闭，关闭时可回旧页面；不是把整个 CRM 匿名开放。DSH 如需额外进程，浏览器只经受控业务网关访问许可操作，不暴露上游通用控制 API。跨 UI 导航用不透明 run ID 与服务端权限，不把凭据塞 URL。

应用状态和分析仓物理分层：本地先独立 SQLite 记录事务状态；合成 DuckDB 只读供计算；不复制/读取 131G 归档真库。PostgreSQL 是多人协作版应用状态的候选，必须先测事务与并发，不把“换 PostgreSQL”当数据分析提速结论。

首版一个执行管理器，持久化 job/attempt、有限队列，每任务有独立可终止进程。HTTP 不做重计算。先同请求幂等与已完成结果缓存，不实现跨 run 的在途共享计算；因此取消只影响本 run，不需要跨人群等待者计数。更多调用者≠更多重查询同时运行，不限制单人登录代替资源管理。

用户确认A1：先在SQLite短事务落下业务run、请求hash、dispatch意图与原202，再调用DSH。受理、首次模型思考、查询步骤、最终化均有业务状态；DSH入inbox的accepted不代表成功。复用上游session/requestId去重，只在已验语义内同标识核对/重放；不确定UNKNOWN，不宣称跨系统exactly-once。只读资产不建run，已有资产显式刷新走同一管理器的QUERY派发，不需会话或模型。

DSH控制面按HTTP/WS mux/Fetch逐操作白名单与对象权限校验；MCP为可选工具桥，不是必须加的一层，新发现工具不自动获权。Skill仅装配固定获批整体包；聊天摘要、长期记忆与子Agent都不能替代FastAPI证据/权限。compaction及恢复从业务状态重组条件/证据/版本/剩余预算。首版不做长期记忆自动写入、自进化发布、多Agent或第二个loop；详见合同§5.1–5.2。

## 4. 业务合同（字段权威见接口草案）

共同绑定键：query/metric/data 版本 + 完整 resolved_filters + permission scope；结果增加不可变 run_id 与 evidence_digest。保存只引用 SUCCEEDED 且校验过的运行；刷新另开 run，不覆盖历史数字。

三类 v1 能力：
1. 渠道队列：首次观察到的有效付费渠道、成熟 N 日二单率/人数及后续跨渠道购买。
2. 首购商品路径：按首购商品集合/多品篮子组比较后续商品与购买间隔；支持小样→正装映射，但商品角色表也是 synthetic/版本化。
3. 候选承接人群：在明确截至日、首购条件、后续行为和排除规则下生成只读人群定义与摘要，提供“不新增营销/继续研究/准备试点”选项。

不叫“完整生命周期模型”；RFM 另行扩展。缺少真实成本只给未知项，不填 0 或生成利润/ROI。观察关联、情景假设、经营建议分开。

对话每次提交带 parent_run_id + 显式 condition patch；服务端回显完整条件与差异。并行追问从共同父 run 分支，不让后发响应覆盖另一分支。歧义产生 NEEDS_INPUT；澄清后新 run，不能把问题落入旧渠道兜底。

单run允许多工具步骤，每步冻结自己的query/metric/完整条件和证据；主结果由primary_result_ref明确，辅助结果分别标口径，必要步骤失败不得完整成功。草案额外固定source_result_ref，明确选哪个成功人群结果；顶层渠道主结果不冒充辅助人群的条件/摘要。

草案冻结来源 run、filter/metric/data/cohort/action 版本摘要；审批冻结同一 digest。改动条件/动作/人群或数据版本必须新草案/再审批。保存分析不审批营销。下载继续只含合成 ID 等许可列，不新增订单号/手机号或真实 CRM 兼容承诺。

## 5. CEO 阶段收口与取舍

CEO 主审完成 11 节，完整错误恢复、失败模式、三方案、复用与长期差距见 [Phase 1](./AUTOPLAN-PHASES-2026-09-05.md#phase-1--ceo--selective_expansion)。前提已批准；设计、工程、DX 已顺序补齐。本次用户进一步确认 DSH UI 方向；工程实施仍待授权，不重开已确认的商业定位。

双声音降级：Codex 完成 CEO 审查；Claude CLI 默认/opus 均返回 MiniMax，不视作 Claude。MiniMax 补充审查与 Codex 均指出范围/交付问题；正式 Claude–Codex 共识六维均 N/A。采纳有依据的问题，拒绝“两候选等于两在线”误读。

### Decision Audit Trail
原则：P1 完整闭环，P2 范围内修复，P3 务实，P4 复用，P5 显式约束，P6 可执行。

| ID | 阶段 / 类别 | 决定 | 理由 / 状态 |
|---|---|---|---|
| C01 | CEO / auto | 保留七项商业验收，一条客户路径先端到端 | P1；不重开已批准定位 |
| C02 | CEO / auto，后续补记 | 6 小时承载证明后确认唯一运行时集成候选 | UI 已由用户确认 DSH；原 CEO 决定的运行时硬门保留 |
| C03 | CEO / auto，后续限定 | 延后订阅/专家/自由工作流；旧“最小看板微调”由D08扩展 | 不删安全和人群绑定验收；用户已确认受控板块组合 |
| C04 | CEO / auto | 分析定义与运行证据自有，框架可替换 | P1/P5；降低未来迁移代价 |
| C05 | CEO / auto | 旧 RFM 不作前置，新渠道路径有自己金标准 | P2；执行用户最新范围 |
| C06 | CEO / auto | 人群绑定未过不得标新闭环完成 | P1/P5；独立旧 Mission 只是披露式降级 |
| C07 | CEO / auto | 六小时到点形成选择或失败记录 | P3/P6；不无限框架比较 |
| C08 | CEO / auto | 本地与网址交付分开，9/8 检查发布依赖 | P5；不新增部署权限 |
| C09 | CEO / auto | 本地 SQLite 状态 + 只读合成分析；PostgreSQL 后议 | P3/P4；不迁真库 |
| C10 | CEO / auto | 同请求幂等 + 成功缓存，不共享在途计算 | P3；避免首版取消协调复杂度 |
| C11 | CEO / auto | 条件差异、保存时证据、不营销选项纳入主链 | P1/P4；不建三个新门户 |
| D01 | Design / auto，后续限定 | 延用伸美品牌、原图；旧 Vue token 不覆盖 DSH 壳 | DSH 原生视觉按用户最新选择保留 |
| D02 | Design / auto，后续限定 | 就绪空会话三建议；结果先用自有工具卡 | 不强制重写 DSH 双列；见新增 D07 |
| D03 | Design / auto | 保存与加入驾驶舱分步，草案是另一明确动作 | P5；保存不等于审批 |
| D04 | Design / auto，后续限定 | 父/子run及历史快照仍独立；日常看板按D08读取兼容最新结果 | 不改写历史或已批准证据；数据日期和模式明确 |
| D05 | Design / auto | 全状态、窄屏页签、跳转焦点、图表表格替代 | P1；实施验收，不以草图代替 |
| D06 | Design / boundary | 不额外付费制图或开服务，视觉待测 | 尊重范围；不是 designer 不存在 |
| D07 | Design / user | 保留 DSH 原生 UI，开始业务交互设计 | 本轮明确选择；资产先用业务 overlay，运行时/渲染未验收 |
| D08 | Design / user | 板块插件化、AI局部编辑、个人组装、固定入口日常查看 | 用户明确“可以，就是这个逻辑，咱们继续”；§6和接口§3.4已完成工程静态复审，运行未验 |
| E01 | Eng / auto | 净支付有效单、先历史首单再入组、同刻有序后继、同N成熟分母 | P5；合成拟定口径，金标准冻结前标proposed |
| E02 | Eng / auto，后续限定 | parent_run/digest保留；SNAPSHOT固定pinned_run，LATEST_SUCCESS回传实际run/digest | D08区分配置与显示证据；完整证据不靠前端记忆 |
| E03 | Eng / auto | 三段式导出、短事务、固定人群摘要 | P1/P3；避免锁内重算及重选名单 |
| E04 | Eng / auto | 每attempt进程、fencing、CAS唯一终态 | P5；取消/失联不能仅改状态标签 |
| E05 | Eng / auto | 独立synthetic标准看板适配，不批量改旧筛选 | P2/P4；完整条件且私有CRM不开放 |
| E06 | Eng / auto | 单元/集成/E2E/eval/资源门齐备 | P1；零安全/数值错误，性能目标不是结果 |
| E07 | Eng / auto | 模块分工/单集成人，保留全部脏改动 | P2/P6；不自动开分支、提交或合并 |
| X01 | DX / auto | 新同事唯一synthetic起步路径；依赖齐5分钟为目标 | P3/P5；不把旧ETL全测当新手起步 |
| X02 | DX / auto | access/answer_mode/schema兼容矩阵显式化 | P5；stub、真实工具、模型链路分别计证据 |
| X03 | DX / auto | 同key找回丢失run；事件游标/410/diagnostics明确 | P1/P5；不盲重试/无限排队 |
| X04 | DX / auto | 旧版本只读、显式迁移，旧CRM退款规则不套新口径 | P5；不破坏历史或暗改业务定义 |
| X05 | DX / auto | OpenAPI/TS/样例离线同hash；HTTP先行不造SDK市场 | P3/P4；文档随功能交付 |
| X06 | DX / auto | 内部接手与排障实测；公共社区/自动升级延后 | P2；不造无关平台 |
| X07 | Final / auto | 入组窗、观察N日、截数快照分字段并纳入hash | P5；明确追问到底改变什么 |
| X08 | Final / auto | run.version、无响应同key恢复、草案GET导出状态补齐 | P1/P5；不增加新系统即可恢复任务 |
| X09 | Final / auto | 订阅从首版验收分母移除，未测试预览不得标已验证 | P5；延期不是通过 |
| E08 | Eng再审 / USER_CONFIRMED | A1先登记run/派发意图再调用DSH | 用户明确确认；复用上游去重与既定jobs，不另建队列平台 |
| E09 | Eng再审 / USER_DELEGATED | A2–A5、Q1–Q3、T1–T3、P1–P2工程细化纳入合同/测试 | 用户授权无产品取舍的工程项连续推进；不是逐条人审或新执行授权 |

## 6. 前端实施约束

最新承载以 [DSH 交互设计](./DSH-UI-INTERACTION-SPEC.md) 为准；[原设计状态表](./AUTOPLAN-PHASES-2026-09-05.md#phase-2--design) 的业务/安全要求继续保留，但旧双列尺寸和 Vue-only 令牌不覆盖 DSH 壳。问数用原生会话；分析库、私人驾驶舱与草案先用一组业务 overlay 视图。驾驶舱须有固定入口并能独立于活动会话读取已有资产，不假设 /ask、/library、/dashboards 已存在或可直接注册；B0核验入口接缝。原 /growth-board 保留独立旧情景。

- 问题建议在已绑定 synthetic 工作区的空白 session 中显示；冷首页默认进入方式需 B0 验证。原生消息、输入与详情布局不重写；自有工具 key 渲染分析卡，业务资产用弹层。新增控件响应、焦点与三档视口仍需实测。
- 分析卡固定读序：本次结论→完整条件/成熟样本/数据日期→主图及明细→证据局限→保存或草案。新追问只替换对应当前运行的区域，父证据可引用但不伪造同一 run。
- 保存成功后选择加入驾驶舱；同一DSH业务插件内登记可复用板块类型，驾驶舱保存实例组合，不按板块部署服务。AI与手动操作共用指定card_id的局部变更合同，可预览/保存/撤销；其他板块及共享分析定义不被覆盖。
- 新增、复制、移除、移动/缩放与展示修改按配置版本保存，窄屏/键盘有等效操作；改展示不重算，改条件只重算受影响板块。全局筛选与局部覆盖显式映射，错误不清空全板，仍不存任意SQL。
- 日常板块默认LATEST_SUCCESS，读取固定方法下最新兼容成功结果，显示实际数据日期、run/digest和过期状态；SNAPSHOT锁定历史引用。打开已有看板不触发Agent、调度或重计算；用户刷新复用既有有界执行，失败保留标注旧日期的结果，审批证据不随看板更新。
- 独立刷新通过POST /refresh-runs从获权资产解析条件，无会话/模型也能计算。card_id与有效数据定义hash共同防止旧刷新覆盖改条件/删除/撤销后的板块；纯标题/位置变化不使同条件数据失效。打开仍不自动查询，固定快照更新仍须确认。
- 只渲染白名单指标/表/柱/线/证据文本，禁止任意组件、HTML/JS formatter、外部 URL。空人群用“— + 原因”，不以 0% 冒充。
- 草案回显同一绑定摘要及负责人、资源/成本未知项和停止条件；只有人类确认且后端授权的动作可执行。审批通过不显示“短信已发”。
- 44px 触控、对比度、键盘、状态播报、表格文本替代与 reduced-motion 纳入后续浏览器验收。本轮评分是规范明确度 5.6→8.0，不是已运行页面的视觉评分。
## 7. 工程结构与协作

拟新增 backend/contracts/analytics.py；backend/services/analytics/ 下 catalog、queries、assets、jobs、runtime、decisions 模块；backend/routers/analytics.py。路径是实施目标，不是已有可调用代码。旧 Mission 抽取可复用的校验/幂等/导出规则时，必须以回归保护原API，不复制整个大service，也不直接让新路由调用旧固定人群方法。

结构化合同、数据语义、状态机以 [接口草案](./ANALYTICS-CONTRACTS-DRAFT.md) 为准，测试覆盖以 [测试地图](./AUTOPLAN-TEST-PLAN-2026-09-05.md) 为准。来源证据与工程4节见 [工程评审](./AUTOPLAN-PHASES-2026-09-05.md#phase-3--engineering--full-review)。新Schema/前端类型在B1冻结；新接口目前不可调用。

| 工作线 | 独占模块/文件 | 依赖与冲突控制 |
|---|---|---|
| A 合同/数据 | contracts/analytics、catalog/queries、人工fixture | B0后先冻结；schema与metrics只能一个负责人合入 |
| B 状态/执行 | assets/jobs/runtime、对应测试 | 等A冻结，stub可并行；不改query口径 |
| C 前端/文档 | DSH业务插件、生成类型消费；Vue只承接隔离看板适配 | 等A；与当前theme/nav/auth脏改动重叠需集成人逐项协调 |
| D 绑定/回归 | decisions adapter、权限、导出测试 | 等A/B；Mission原合同改动集中由集成人审查 |

一个远程仓协作，不把数据仓原始文件进Git；数据合同/合成生成器/manifest规则在软件仓，可分发布的数据版本不等于立刻拆仓。不同工作树/分支创建、commit/push/PR/merge另按授权执行；本计划没创建新Git状态。backend/main.py、router、theme、OpenAPI生成输出是共享冲突热点，只由集成人落最终接线。

并行度补充：A/B/D共享backend/services/analytics模块，冻结合同后仍按实现依赖顺序交接，不默认三人同时改同一模块；后端通道与C插件通道最多两条独立实施通道并行。4行责任分工不是4个无冲突工作树，最终接线由一个集成人完成。

错误明确分类：422不支持/非法参数，NEEDS_INPUT澄清，428缺写请求头，409版本/幂等/绑定冲突，429队列/配额，503来源或运行时不可用；401/403/404区别认证/能力/对象可见性。返回错误code、request_id、retryable和安全details；不暴露文件路径或供应方密钥。

导出实现需短事务认领→锁外固定集合生成/校验→短事务复核发布；READY才可下载。模型/SQL/文件IO不持SQLite写锁，旧attempt晚到不能提交。取消确认进程退出才释放槽位；成功结果缓存键和每次读权限均验证。初始资源阈值与新分支的具体映射见测试地图，不以本次静态检查宣称运行安全已验收。

预算按业务run持久保存绝对截止与实际调用/重试消耗；恢复、模型重试和上下文压缩不重置预算。除SQL进程外，还对板块、分页结果字节、事件、上下文与应用状态磁盘设门；dashboard GET返回配置/引用，不内联全量结果。候选数值是测试profile，在B1冻结，不是已实测SLA；模型费用仍须独立批准。

## 8. API调用与开发体验交付

完整对象、HTTP候选、权限、重试、事件和状态字段见 [接口草案](./ANALYTICS-CONTRACTS-DRAFT.md)，目前全新analytics仍不可调用。已有Mission继续按 [当前调用指南](./AI-TOOL-CALLING.md)。新入口/access必须显示模式和能力：STUB、确定性合成工具、获验Agent工具不可互相冒充；新匿名能力单独guard并默认关闭。

受理写请求在事务里保存稳定key与原202响应，丢失响应可同key重放获得同run；GET确认状态，不另发新任务。取消从GET获取version，409重读；UNKNOWN不盲重试。事件用Last-Event-ID/after恢复，过期410后读取快照。每个失败用request_id关联安全diagnostics，不暴露供应方密钥、思维链和私有路径。

开发交付顺序为schema→离线OpenAPI/TS→实现→相应测试→curl/Python成功与失败样例→操作文档；CI校验同schema hash与漂移。无需模型账号的synthetic/stub quickstart独立于旧ETL与全量CRM测试。依赖就绪首次有效结果目标5分钟，干净机器安装和模型真实接入另计。

详细9阶段旅程、三方参照、8pass与错误例见 [DX评审](./AUTOPLAN-PHASES-2026-09-05.md#phase-35--developer-experience--polish)。文档负责人随模块明确；旧query/metric不支持时历史只读、刷新明确拒绝，迁移另起版本。首版只做内部接手与API集成，不搭通用SDK/社区平台。

## 9. 实施顺序与退出关卡

以下是待最终批准后的计划窗口，不是已执行或按期保证；实际开工延迟需重算工作窗口，9/10提交期限不自动顺延。

| 关卡 | 目标窗口 | 交付与退出条件 | 失败处理 |
|---|---|---|---|
| B0 承载证明 | 9/5–9/6，最多6工作小时 | 验证已选DSH UI，确认唯一runtime集成候选；含工作区/原生操作绑定/权限/实际改动量 | 硬门失败停止集成并重新确认承载变更；stub不能当模型通过 |
| B1 数据与合同 | 9/6–9/7 | 三查询schema、8手工fixture、来源guard、run/资产/人群digest、offline OpenAPI/TS | 数值/隐私任一错误禁止生成经营结论 |
| B2 纵向闭环 | 9/7–9/8 | 连续追问→画布→保存→单驾驶舱/标准BI→绑定试点草案 | 绑定失败标“新闭环未完成”；不接旧固定人群蒙混 |
| B3 安全/模型/恢复 | 9/8–9/9 | 运行时L1、获准模型L2、全部首版P0数值/权限、事件/取消/短锁导出、浏览器与旧边界回归 | 失败留证据并修复；不能砍必要测试过关 |
| B4 本地演示冻结 | 9/9 | 七项验收回放、接手指南、实际能力文案、失败/离线说明 | 本地证据不等于业务收益或网址提交 |
| 独立发布关 | 最迟9/10网址提交；9/8先检查依赖 | 平台、访问控制、费用与部署授权独立确认；以后验证公开版本/访问边界 | 目前未授权、未部署、未提交；不自动公开免登录本机 |
| 后续 | 提交后至10月，赛期另确认 | 订阅、专家模板、CRM试点、干预评估按依赖推进 | 见延后TODO，不混入本版通过率 |

完整工作包见 [实施检查表](./AUTOPLAN-IMPLEMENTATION-TASKS-2026-09-05.md)：CEO2、Design2、Eng5、DX2，共11项；本轮13个评审发现映射为这些包内8组增量检查点，不是另加平台。D08及恢复/安全细化的旧估时不能直接作为新范围承诺，B0之后重估。多模块共享接线/契约，不能不经集成人审核就并行覆盖。先B0，不直接四路写代码。

## 10. 延后工作与已知限制

[TODO留存](./TODOS.md) 记录订阅、协作专家、实际平台接入、多人状态扩展与公开交付依赖。它们有前提/优先级，不作为本轮暗中新增授权。

已知未验证：运行时/模型是否适配、真实渲染与视觉效果、金标准及并发/恢复测试、多人业务权限、公网访问与提交。已知外部评审降级：Claude CLI实际返回MiniMax；四阶段有Codex审查，不能称Claude–Codex一致通过。本轮没有修复应用代码或验证产品功能。

## 11. 外部依据与交叉验证

核验日2026-09-05。不同组织算独立来源；同一厂商官网与GitHub不重复计数。以下支撑工程方向，不证明本公司收益、最佳框架、运行性能或集成成功。

| 结论 | 独立来源与依据 | 适用边界 |
|---|---|---|
| 聊天、可保存分析与看板复用是已有模式 | [Hex Threads](https://learn.hex.tech/docs/explore-data/threads) 的对话关联项目/保存；[Metabase](https://www.metabase.com/docs/latest/dashboards/introduction) 的saved questions与看板筛选 | 自有Definition/Run分离是结合本项目的架构推断，不宣称行业首创 |
| 可复用板块实例、布局和显式筛选组成个人看板 | [Grafana面板](https://grafana.com/developers/plugin-tools/tutorials/build-a-panel-plugin) 的data/options/尺寸；[Metabase筛选](https://www.metabase.com/docs/latest/dashboards/filters) 的全局/卡片作用域 | 采用配置组合，不安装另一套BI；AI局部变更、证据隔离是本项目设计，承载未实测 |
| 问数需业务语义，而非给模型直接猜原表 | [Snowflake语义问数](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst)、[WrenAI仓库](https://github.com/Canner/WrenAI) 的语义上下文 | 采用有版本的受控query/metric；不采购或复制其全部平台 |
| 先简单单Agent，复杂度需任务证据 | [Anthropic方法](https://www.anthropic.com/engineering/building-effective-agents)、[Microsoft架构模式](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns) | 前者原文发布于2024且提示工具变化；只作方法参照，不证明某运行时最佳 |
| 上游Agent不是完整业务隔离层 | [DSH安全说明](https://github.com/deepseek-ai/deepseek-harness/blob/d347e703908d0406b7a7ef80e3a0e594d86b2215/SAFETY.md)、[Hermes安全模型](https://github.com/NousResearch/hermes-agent/blob/79445a496c86a19332ad786494b8384d2167e2d0/SECURITY.md) | 两家均需外部隔离/业务授权；上游开源不等于生产安全已验收 |
| 计算超时/取消与HTTP后台任务不是同一事 | [FastAPI重计算说明](https://fastapi.tiangolo.com/tutorial/background-tasks/)、[Python Future取消语义](https://docs.python.org/3/library/concurrent.futures.html) | 前者提示更独立执行，后者运行中Future不可简单取消；本项目选择有界进程是推断，不必引Celery |
| 本地状态与分析文件职责不同 | [SQLite WAL](https://www.sqlite.org/wal.html) 单写入者；[DuckDB并发](https://duckdb.org/docs/lts/connect/concurrency) 多进程只读边界 | 支撑短事务/只读分层；不证明换PostgreSQL提速或企业吞吐 |

固定版本UI事实：DSH `d347e703908d0406b7a7ef80e3a0e594d86b2215` 的 [Web Client](https://github.com/deepseek-ai/deepseek-harness/blob/d347e703908d0406b7a7ef80e3a0e594d86b2215/docs/subsystems/web-client.md) 与 [slots](https://github.com/deepseek-ai/deepseek-harness/blob/d347e703908d0406b7a7ef80e3a0e594d86b2215/docs/subsystems/slots.md) 支持插件组装UI，仍为开发预览，未声明slot会失败，部分slot是替换点。Hermes `79445a496c86a19332ad786494b8384d2167e2d0` 的 [Web ChatPage](https://github.com/NousResearch/hermes-agent/blob/79445a496c86a19332ad786494b8384d2167e2d0/web/src/pages/ChatPage.tsx) 用xterm/PTy；[Desktop](https://github.com/NousResearch/hermes-agent/blob/79445a496c86a19332ad786494b8384d2167e2d0/apps/desktop/README.md) 是另一套Electron/React。只读官方源码，不是已运行视觉对比。这类“某仓库实现了什么”的事实只以该仓库为主源，不能用另一厂商伪凑双证。

两固定提交根许可证均MIT：[DSH LICENSE](https://github.com/deepseek-ai/deepseek-harness/blob/d347e703908d0406b7a7ef80e3a0e594d86b2215/LICENSE)、[Hermes LICENSE](https://github.com/NousResearch/hermes-agent/blob/79445a496c86a19332ad786494b8384d2167e2d0/LICENSE)。需保留许可声明，未完成依赖/商标审计，模型和托管费用另算。

本轮新增证据详见 [工程复审§8](./AI-ENGINEERING-REVIEW-2026-09-05.md#8-依据与独立交叉验证)：DSH固定源码分别与AWS/Azure重试与outbox、OWASP逐消息授权、MCP规范、Agent Skills规范、Anthropic上下文方法交叉检验。工程推荐是本项目推断；上游源码单点事实不伪凑两家实现证明。

## GSTACK REVIEW REPORT

2026-09-05本次工程复审完成。CEO/Design/DX行引用原autoplan文档审计，不伪造为本次运行日志；原审计原样保留。本次分支日志读取最初为NO_REVIEWS，新增工程行仅记录本次静态计划审查。旧设计分数不覆盖D08新增交互或真实渲染。

| Review | Trigger | Why | Runs | Status | Findings |
|---|---|---|---|---|---|
| CEO（历史文档） | /autoplan | 商业定位/范围 | 原主审1 + Codex1 + MiniMax补充1 | REVIEWED / Claude N/A；未重跑 | 七项商业验收与范围保留；不宣称正式双模型共识 |
| Design（历史文档） | /autoplan | 交互/状态 | 原主审1 + Codex1 | STATIC_REVIEWED；D08渲染NOT RUN | 当前DSH/D08有交互规范与工程静态复核，旧视觉评分不自动沿用 |
| Engineering（本次PLAN） | /plan-eng-review | AI架构/代码合同/测试/资源 | 主审1 + 同模型独立3路，合同追加复核 | STATIC_REVIEW_COMPLETE / issues_open | 5+3+3+2=13项已纳入；6类高风险有计划处理，运行NOT RUN；3个执行决策待确认 |
| DX（历史文档） | /autoplan | API/接手恢复 | 原8pass + Codex1 | REVIEWED / TTHW NOT MEASURED；未重跑 | 本次补刷新/来源/限额合同，仍不可调用；不称新手起步已实测 |
| Outside voice（本次） | 可选跨模型 | 独立意见 | 同模型3路；跨模型0 | SAME_MODEL_REVIEWED / CROSS_MODEL_NOT_RUN | 独立合同复核补明确人群结果引用；不伪称Claude–Codex一致通过 |

VERDICT: 工程静态计划已收口，13项均有契约/任务/测试去向；未处理的计划缺口为0，不等于实现或运行风险清零。整体仍REVIEWED_WITH_DEGRADATIONS；执行关issues_open，不是SHIP/部署CLEAR。B0若通过已定DSH硬门且实施已授权，普通工程项继续推进；失败需换壳/扩大范围时再请用户拍板。

**UNRESOLVED DECISIONS:**
- B0最小代码/安装/临时合成运行已获授权并部分验证；B1–B4正式实施权限仍独立，需在B0硬门收口后确认。
- 实际产品模型账号、允许模型、单run及整批eval费用上限；未批准只可在获准本地验证中用stub。
- 公网平台、访问控制、费用、部署与9/10网址提交另关；当前按用户要求暂缓，不公开免登录本机。
