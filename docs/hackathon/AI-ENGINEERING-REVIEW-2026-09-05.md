# AI工程复审：单运行时、可信分析与可组装驾驶舱

日期：2026-09-05。状态：`STATIC_REVIEW_COMPLETE / IMPLEMENTATION_NOT_AUTHORIZED / RUNTIME_NOT_RUN`。

后续执行说明：以上为本静态评审的时点状态。用户随后只授权B0，现已取得[两轮部分运行证据](./B0-DSH-VALIDATION-2026-09-05.md)，临时服务已停止；不重写本报告为运行通过，也不代表B1–B4、公网或收费模型获准。

主计划：[v2.3](./UNIFIED-ANALYTICS-PLAN.md)；字段主源：[接口草案](./ANALYTICS-CONTRACTS-DRAFT.md)；交互主源：[DSH UI v1.2](./DSH-UI-INTERACTION-SPEC.md)。本报告是工程计划审查，不是代码修复、渲染评分、模型性能或生产安全验收。

## 1. 结论、范围与授权

保留一个DSH原生Web及业务插件、一个Agent运行时、FastAPI业务后端、SQLite应用状态和只读合成DuckDB。老板日常从固定入口看自己的驾驶舱，必要时连续问数、改一块、保存证据，再决定是否准备有边界的增长试点。没有新增Hermes/StaffDeck运行时，没有按一个API建一个员工。

用户已明确确认A1“先登记业务任务，再交给DSH”，并授权普通计划工程项一路推进。A1记为USER_CONFIRMED；其他12项记为USER_DELEGATED工程细化，不伪称逐条人审。执行Architecture → Code Quality → Tests → Performance四节；不再为字段/测试微调重复停顿。改变产品范围、运行底座、成本/权限或公开部署时仍须停下。

范围挑战结论：接受已确认的完整业务主链与D08增量，不缩成只能保存固定卡片的聊天演示，也不扩为通用BI/低代码平台。旧RFM/PC2不作前置；商业七项验收保留。9/10网址提交和10月后续赛程不等于本地实现已获发布授权；B0后按实际剩余时间重排，不把早前估时当新范围承诺。

静态代码基线：`codex/shine-mage-figma-refinement`，HEAD `de2d785f4e0c7abe7fcd8fbb39be7d8c5a0c9642`，含既有脏改动。只在现有规划工作树改文档，不改应用/测试代码、不操作真实数据、不启动服务、不提交推送。历史autoplan证据保留在 [原审计](./AUTOPLAN-REVIEW-2026-09-05.md)；当前分支review-log原先未发现记录，不能把文档里的历史评分伪造为本次运行日志。

最近5提交包含pre-landing文档收尾、视觉交付、设计token和既有后端回归记录，尚不是本轮analytics实现。其相关易冲突区是theme/路由/免登录/Mission，继续定向回归，不从提交名称推断新Agent链已验证。

## 2. Architecture：5项

| ID / 优先级 | 发现与采用方案A | 不采用的方案及原因 | 证据/验收 |
|---|---|---|---|
| A1 / P1 | 业务受理必须早于DSH首次模型调用；短事务保存run、hash、dispatch意图和原202，再派发固定session/requestId | B首次工具才创建run会漏掉前置失败；C新建队列平台扩大部署；复用上游去重，不宣称exactly-once | 合同§3.3；I2f/I2g，V24；用户确认 |
| A2 / P1 | 控制面不只有POST；HTTP、WS mux逻辑操作与Fetch逐项登记和授权，重连仍核当前权限 | B只隐藏按钮不是隔离；C直通整个上游API会超出业务能力；不假称原DSH完全没有Host/Origin保护 | 合同§5.1；A2/V25；上游connection + OWASP |
| A3 / P1 | MCP可选；装配固定server/tool/schema hash，初始化/变化/执行都检查；FastAPI严格schema独立保留 | B动态发现即授权不合适；C强制多加MCP服务器无首版收益；supported schema验证仍复用 | 合同§5.1；A3/V25；DSH mcp-client + MCP规范 |
| A4 / P1 | Skill加载会读当前文件；冻结整个获批包（正文/引用/资产）并隔离默认roots，运行中不热换方法 | B仅记录skill名称不能复现；C新建技能市场/自进化发布器不在本版 | 合同§5.2；A4/V26；DSH skill-filesystem + Agent Skills规范 |
| A5 / P1 | compaction/恢复后从业务状态重组问题、完整条件、证据引用、版本和预算；摘要/记忆不授予事实与权限 | B依靠长聊天记住指标易漂移；C再建向量库/长期记忆服务不必要；复用DSH原生压缩 | 合同§5.2；A5/V26；DSH compaction + Anthropic上下文方法 |

没有发现需要重开CEO定位或立即更换DSH的充分证据。DSH是否能无核心fork通过硬门仍需B0；本报告不把源码存在的接缝当成已集成成功。跨任务停止隔离若证明不了，只在B0声明对应queue/steer动作不可用，不用单账号登录限制遮掩资源问题。

### 能力边界一览

| 用户关心的主题 | 首版落实方式 | 明确不做 |
|---|---|---|
| Harness / 底座适配 | 一个固定DSH版本，原生UI+受控业务插件，adapter映射业务ID | 双运行时、核心fork默认方案 |
| API / MCP | 版本化HTTP合同和DSH typed tools；MCP按实际客户端需要再装 | 模型任意SQL/直读私库、动态工具自动扩权 |
| Skills开发 | 一个增长专家的获批方法包，职责/输入/条件/证据/失败规则明确 | 一个指标一个服务、运行时改SOP立即发布 |
| 上下文 | 原生compaction + 后端恢复包；引用代替大名单 | 以摘要中的旧数值或口头批准作事实 |
| 长期记忆 | 显式保存的分析和驾驶舱是业务资产；未来偏好信息另有归属/失效 | 自动跨会话写记忆、挂入Hermes个人MEMORY |
| Subagent / Multi-agent | 保留将来权限交集、同轮依赖和总预算约束 | 首版专家组队和自由工作流 |
| 自进化 | 后续反馈→候选→独立回归→人工发布→可回滚 | 本版自改口径/权限/营销动作 |
| 超长任务 | 本版有界任务、持久状态/预算、失联UNKNOWN；将来长任务沿用这些合同 | 无上限后台运行、重启即预算清零 |
| 看板插件 | 一个业务插件内注册类型，配置实例、稳定card_id与局部操作 | 任意JS/HTML/远端代码、另一套BI服务 |
| 营销 | 明确人群结果→草案→人类审批→合成DRAFT_EXPORT | 自动短信、真实订单名单或CRM已接通声明 |

## 3. Code Quality：3项

| ID / 优先级 | 发现与采用方案A | 不采用的方案及原因 | 交付与测试 |
|---|---|---|---|
| Q1 / P1 | 一run可多工具，但原顶层query/facts单一；以step独立结果+primary_result_ref投影主结果，辅助证据各自保留口径；草案额外冻结source_result_ref | B只允许一次查询削弱连续研究；C以最后工具结果覆盖会混分母/人群；不再建工作流服务 | 合同§3.3/§6；I1b/I5d，V27 |
| Q2 / P1 | 每天查看已脱离聊天，但刷新只有会话建run入口；增加一个POST /refresh-runs和ASSET_REFRESH来源联合，无模型直接QUERY派发 | B假造会话/自然语言问题造成不必要耦合；C单建刷新服务重复队列/状态/权限 | 合同§3.3/§4；I3d，V28 |
| Q3 / P1 | 稳定card_id不足以判断刷新是否还适用；受理冻结有效数据定义hash，结果提交/显示核对card存在、定义与快照；布局不入数据hash | B整板版本改变即丢所有数据会误伤标题修改；C按网络晚到覆盖会串条件；不取消历史证据留存 | 合同§3.4；I3e，V28 |

复用与职责：同一个执行管理器承接CHAT/QUERY dispatch；同一schema主源生成TS供DSH React与旧Vue适配消费。内部DSH工具必须绑定已有run，不能再次调用外部建run入口递归启动DSH。保存、展示配置、数据刷新、营销审批是不同命令，不能一个万能接口隐式触发全部动作。

独立复核发现Q1还需“同run多个候选人群”绑定到具体结果，已补source_result_ref及I5d；审批摘要覆盖该引用、实际条件和成员摘要。这是同一发现的闭环修正，不新增一个人群服务。

## 4. Tests：3类缺口

| ID | 原缺口 | 计划补齐 / 测试入口 |
|---|---|---|
| T1 | “部分结果”笼统描述不足以证明单Agent多工具链，后续多专家V20也不能替代 | I1b：A成功/B失败、依赖来源错误、重复工具、主结果非最后工具；I5d：同run两个候选人群只导出所选；required步骤失败不能SUCCEEDED |
| T2 | 原SQL取消和请求恢复没有完整覆盖受理/模型/派发/最终化间隙 | I2f/I2g：事务前后崩溃、回包丢失、首工具前模型失败、工具间隙取消、晚到代际、queue/steer归属；A2–A5覆盖新安全边界 |
| T3 | 已有局部PATCH/版本测试没有交叉覆盖预览、在途刷新与配置变更 | I3d/I3e及B1b：无会话刷新、标题/条件/复制/删除/撤销、预览后撤权/改版、结果逆序；不清空其他板块，不把旧日期标今日 |

所有用例为**PLANNED / NOT RUN**。可执行测试仍需实现；本轮仅检查文档映射，不把fixture推导、schema草案或测试文件名当作运行覆盖率。

```text
人工fixture期望 ─ U1/U2 ──────────────┐
CHAT → I2f事务受理 → A2/A4装配 → A5上下文 → DSH → I1b逐步证据
资产 → I3d事务受理 ─────────────────→ QUERY ────┤
                                                     ↓
                                     I2g取消/CAS → 主结果完整性
                                                     ↓
                        I3保存 → U3b配置 → I3e并发/刷新 → B1b日常重开
                           ├ I4/B2同条件合成BI
                           └ I5d所选结果 → I5a审批 → I5b/c导出 → B3
全链：A1–A5权限/来源；P2持久预算；P3资源；R1旧边界回归
```

测量层级：L0确定性合成数值 → L1真实runtime+stub合同 → L2获准模型 → L3产品浏览器 → L4外部试点（延后）。前一层不能冒充后一层。B0小样只证明接缝，完整状态库/资源/业务仍在B1–B3。新React插件测试接入目录在B0冻结；仓库现有Vitest是Vue/jsdom配置，不能声称DSH测试框架已搭好。pytest/Playwright等已有配置可复用，未因此安装或运行。

测试地图已覆盖新增分支；L2至少20题×3次是下限，不为维持60次删除D08及安全类别。模型账单cap未获准，不能运行收费eval。各次失败必须留存，金标准不从被测SQL生成；95%合法任务理解是小样本目标，不是生产可靠率。

## 5. Performance：2项

| ID | 风险与采用方案A | 排除方案 / 验证 |
|---|---|---|
| P1 | 步数/超时只写每次尝试会在恢复或多层重试后超额；受理持久绝对deadline，实际尝试/compaction用量共同记账，派发前原子保留预算 | 不使用每层独立无限重试；P2验证第8/9步、断线重启、实际重试与未知用量；120秒含排队，单查询30秒服从剩余总时限 |
| P2 | SQL有界不代表UI/JSON/事件/状态磁盘有界；配置只含引用，结果分页、事件合并/关键状态预留、上下文与磁盘准入门 | 不按卡片数无界并发，不截半事实冒充完整，不以24小时保留要求承诺无限磁盘；P3边界测试及P1/P1b控制请求p95实录 |

现有首轮资源profile保留worker=1、queue≤8、每调用者在途≤3，内存/临时盘限制继续测试。新增20卡、200行/页、1MiB结果、64KiB事件、4MiB/run持久事件是**待B1冻结的测试假设**，不是已达标容量。模型上下文/输出、用量、应用状态磁盘高水位在实际环境冻结；缺必要限额拒绝启动执行，磁盘到水位保留历史证据而拒新run，不自动删资产。

读已有证据、手动展示编辑、应用已生成局部提案不调用模型或SQL；AI理解自然语言改板块可调用模型，但不顺带重查经营数据。显式刷新只计算必要板块，结果缓存按完整版本/条件/权限复用。不会把SQL加索引/换PostgreSQL当成未经测量的性能结论。

## 6. 失败模式、状态和恢复

六类高风险：任务丢失/重复、控制面扩权、证据/人群串用、配置与刷新错配、取消后旧执行提交、预算/资源失控。下表均已有计划处理及测试；未处理的方案缺口为0，**实现验证全部待完成**，不是6类风险已被运行证明消除。

| 故障 | 计划处理 | 老板看到什么 | 测试 |
|---|---|---|---|
| 业务事务未提交即崩溃 | 无dispatch；同key重新受理 | 未受理/可重试，不伪造run | I2f |
| 已提交未派发、回202丢失 | 原意图恢复；同key返回原202/run | 同一个任务继续，不出现两份 | I2e/f |
| DSH回包丢失或模型第一次工具前失败 | 核原session/requestId；已知失败FAILED，不确定UNKNOWN | 真实phase、可核对请求号 | I2f |
| 原生WS或MCP工具变化越权 | 逐操作/当前权限/固定manifest拒绝 | 无权限/功能不可用，不泄其他对象 | A2/A3 |
| Skill变更或压缩摘要失真 | 固定包；重组后端证据，无法确认明确失败/补问 | 方法版本/条件可核对 | A4/A5 |
| 必要工具失败或人群候选串用 | 不完整成功；source_result_ref校验 | 部分证据不可保存为完整分析或批准 | I1b/I5d |
| 预览过期、在途刷新晚到 | 409/权限拒绝；数据hash与card检查 | 保留正确配置、旧结果明确STALE | I3e |
| 停止/崩溃后旧执行提交 | 确认退出、attempt fencing、终态CAS | CANCELLING/CANCELLED/UNKNOWN真实区分 | I2b/c/g |
| 重试/重启绕过总预算 | 绝对deadline与用量持久化 | 超时/额度原因，不无限转圈 | P2 |
| 结果/事件/磁盘超额 | 分页/引用、事件合并、准入拒绝、保留关键状态 | 明确限额/待刷新，旧资产可读 | P3 |
| 导出文件完成但状态未提交/撤权 | 固定attempt文件、短事务复核、READY才下载 | PENDING/FAILED/UNKNOWN，不假送达 | I5b/c |

## 7. 复用、非目标与并行实施

### What already exists

- [Mission合同](../../backend/contracts/mission.py)、[路由](../../backend/routers/missions.py)、[实现](../../backend/services/mission_service.py)：版本、幂等、摘要、批准/合成导出模式可复用。旧service的固定情景、锁内查询/写文件不整体拷贝；新链用隔离adapter和三段式导出。
- [Mission回归](../../backend/tests/test_missions_api.py)、[本地免登录guard](../../backend/services/local_demo_access.py)及其测试：保护既有能力；不能自动授予analytics匿名权限。
- [Vue路由](../../frontend-vue3/src/router/index.ts)、[筛选同步](../../frontend-vue3/src/composables/useFilterSync.ts)、[App挂载](../../frontend-vue3/src/App.vue)：旧BI保留，隔离一个synthetic适配；不把全局旧筛选直接套新条件。
- [pytest配置](../../pyproject.toml)、[Vitest](../../frontend-vue3/vitest.config.ts)、[Playwright](../../frontend-vue3/playwright.config.ts)：复用现有工具与定向回归，不启动旧CRM全量测试。Python服务/测试按归档规范的Homebrew 3.14+。
- DSH已核验的原生壳/插槽、会话prompt去重、事件、Skill与compaction：优先适配，不另写聊天或Agent循环；静态可复用不等于本机装配通过。

### NOT in scope

真实DuckDB/ETL/RFM/PC2；数据迁移；第二套运行时；任意SQL或HTML/JS代码看板；自动长期记忆/自进化发布；多Agent团队/市场/工作流；订阅调度/推送；真实营销、订单号/手机号导出；公网/账户发布；commit/push/merge；新增收费模型评审。

已查 [TODOS](./TODOS.md)，现有订阅、专家、多人状态、平台接入及公网项继续保留，本轮新增后续项目0项，不借工程术语扩大首版。自进化等仅写设计边界，未暗增实施TODO。历史autoplan中Claude CLI实际返回MiniMax的记录照留，本轮未重新付费调用或宣称正式双模型共识。

### 并行工作线与顺序

```text
顺序门 B0承载/安全 → B1单人冻结合同/金标准
                           ├ A语义/查询（合同owner）
                           ├ B状态/执行/runtime
                           └ C业务插件/资产UI
                      A+B完成 → D人群绑定/回归
                           → 集成人接线 → B3数值/模型/安全/恢复 → B4本地回放
```

4个责任工作线不等于4个无冲突工作树；A/B/D都触及backend/services/analytics，因此按依赖顺序，不默认三人同时改该模块。B1冻结后后端通道与C前端通道最多2条无共享模块的实施通道并行；最终接线与验收顺序执行。

| 工作线 | 模块 | 依赖 / 并行约束 |
|---|---|---|
| A 合同/指标 | backend/contracts、backend/services/analytics、合成fixture | B0；先冻结schema/金标准 |
| B 状态/执行 | backend/services/analytics、后端集成测试 | A；与A/D共享模块，顺序推进 |
| C 插件/驾驶舱 | dsh-plugins/analytics-workbench（目录待B0确认） | A；可与B并行，D-T1→D-T2同插件顺序 |
| D 绑定/回归 | backend/services/analytics、后端binding测试 | A+B；与C继续并行需只消费已冻结合同 |
| 集成人 | backend入口/路由、生成类型、旧Vue适配 | 接线仅单人；相关工作线完成后验证 |

路径与11工作包见 [实施检查表](./AUTOPLAN-IMPLEMENTATION-TASKS-2026-09-05.md)。contracts、backend/main.py、router、生成OpenAPI/TS、旧theme/nav/auth为共享热点，单一集成人负责最终落点；已有脏改动保留。本轮不创建新工作树/分支。实现时jobs模块附受理→派发→attempt/取消ASCII状态图，assets附配置版本→有效定义→候选证据选择图，decisions附三段式导出/批准摘要图；图注标不变量而非复制本报告全文。

本次派生8组增量任务：C-T1、D-T1、D-T2、E-T1、E-T2、E-T3、E-T5、X-T1，分别对应上文发现。C-T1原4–6小时验证盒保留，其余新增范围的人类/AI协作估时均待B0实证后重估，不累加旧数值承诺日历。机器JSONL保存的是增量映射，不替代原11个工作包或把待实施变为完成。

## 8. 依据与独立交叉验证

核验日2026-09-05；DSH固定提交`d347e703908d0406b7a7ef80e3a0e594d86b2215`。结论至少交叉检查不同组织的原始文档；同厂商官网+GitHub不算两家。具体“上游实现是什么”只以该固定源码为证，不能要求另一项目证明它的实现；下面将事实和本项目推断分开。

| 工程判断 | 直接证据 | 独立对照与适用边界 |
|---|---|---|
| 先持久受理/意图，再有限同标识派发 | [DSH commands](https://github.com/deepseek-ai/deepseek-harness/blob/d347e703908d0406b7a7ef80e3a0e594d86b2215/packages/api/session-controller/src/commands.ts#L305)检查inbox/已记录rpcId；[types](https://github.com/deepseek-ai/deepseek-harness/blob/d347e703908d0406b7a7ef80e3a0e594d86b2215/packages/api/session-controller/src/types.ts#L315)明确accepted是inbox回执 | [AWS幂等重试](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)与[Microsoft transactional outbox](https://learn.microsoft.com/en-us/azure/architecture/databases/guide/transactional-out-box-cosmos)支撑稳定请求与同事务意图；使用既有SQLite，不引入其云平台，也不承诺exactly-once |
| HTTP与长连接均需业务逐操作授权 | [DSH connection](https://github.com/deepseek-ai/deepseek-harness/blob/d347e703908d0406b7a7ef80e3a0e594d86b2215/packages/client/connection/README.md#L28)列HTTP POST、`/api/remote.mux`及Fetch；原cookie/Host/Origin保护存在 | [OWASP WebSocket](https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html#message-level-authorization)要求消息级授权；本项目manifest是业务隔离推断，不是宣称DSH漏洞已复现 |
| MCP发现/注解不是业务授权，输出仍要严格校验 | [DSH mcp-client](https://github.com/deepseek-ai/deepseek-harness/blob/d347e703908d0406b7a7ef80e3a0e594d86b2215/packages/mcp/mcp-client/README.md#L129)支持动态重同步，部分不支持的schema词汇回退宽松JsonValue | [MCP tools安全约束](https://modelcontextprotocol.io/specification/2025-06-18/server/tools#security-considerations)要求输入/输出验证、访问控制和超时；受支持schema会被DSH验证，不泛称它完全不校验 |
| 获批Skill应固定全包而非只记名称 | [DSH skill-filesystem](https://github.com/deepseek-ai/deepseek-harness/blob/d347e703908d0406b7a7ef80e3a0e594d86b2215/packages/skill/skill-filesystem/README.md#L40)每次load读现文件，默认含多类roots/watch，可关闭默认roots | [Agent Skills规范](https://agentskills.io/specification)允许引用scripts/references/assets；全包hash/只读装配是本场景可复现性选择，不是规范强制的全部实现 |
| 压缩后恢复依靠明确状态与证据引用 | [DSH compaction](https://github.com/deepseek-ai/deepseek-harness/blob/d347e703908d0406b7a7ef80e3a0e594d86b2215/docs/subsystems/compaction.md#L11)区分日志事件和模型消息投影，另有pruner | [Anthropic context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)讨论压缩、结构化笔记与按需上下文；后端恢复包是结合本项目的推断，不证明任意超长任务已经可靠 |
| 驾驶舱复用类型、实例配置和显式筛选 | [Grafana panel](https://grafana.com/developers/plugin-tools/tutorials/build-a-panel-plugin)提供数据/配置/尺寸契约 | [Metabase dashboard filters](https://www.metabase.com/docs/latest/dashboards/filters)明确筛选连接；借鉴模式，未安装它们、不直接运行Grafana插件 |
| 重试/资源应在总预算内协调 | [AWS重试](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)对重复副作用的约束 | [Microsoft Retry pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/retry)讨论重试策略；本地数值上限仍需测试，不用这些文档证明Mac的p95 |

“是否最佳实践”结论：这些模式已有成熟参照，创新不在重造聊天或员工框架，而在本公司渠道/首购/后续购买语义、可追溯证据和可批准的经营动作。不能仅靠资料评选唯一最佳底座；B0–B3同题验收才决定DSH组合是否适合本产品。

## 9. 独立审查与完成摘要

本轮3路同模型独立审阅：架构权限/上下文、合同质量、测试/资源；主审逐节整合。合同追加复核提出source_result_ref窄口，已纳入；最终复核确认指定范围无新增P1契约矛盾，仍仅静态结论。它们是独立任务审阅，**不是不同厂商模型的交叉共识**。可选跨模型outside voice本轮未运行；历史MiniMax降级不改写成Claude通过。未写全局学习/决策记忆或远端同步，仅留本地项目文档与评审元数据。

| 检查 | 结论 |
|---|---|
| Step 0范围 | 接受已确认范围，无新增平台或商业范围 |
| Architecture / Code Quality / Tests / Performance | 5 / 3 / 3 / 2，共13项，全部进入计划处理 |
| 关键失败类型 | 6类，均有状态/恢复/测试映射；实现与运行未验 |
| 测试图/复用/非目标/TODO | 已写；新增后续TODO 0项 |
| Outside voice | 3路同模型独立审查已做；可选跨模型未做 |
| 并行化 | 4责任工作线；A/B/D共享后端顺序，最多2条模块通道并行，最终接线顺序 |
| 完整性选择（Lake） | 13/13有范围内闭环方案；这是计划覆盖，不是实现通过率 |
| 交付状态 | 11原工作包内8组增量检查点；全部PLANNED / NOT STARTED |

## 10. 下一步与停止点

下一步是B0固定DSH版本的本地合成/stub承载证明，最多6个工作小时：按已查接缝验证默认工作区、原生发送/停止/重试、业务卡/固定资产入口、控制面与Skill隔离。先取得安装/代码/临时启动的准确范围，不能从本次“继续计划”自动扩成执行。模型不付费调用，真库/外部发送/公网继续禁止。

后续B0通过且相应实施已授权时，普通schema细化、类型/测试和模块实现按依赖继续；不再为每个小字段停下。若原生插槽或安全硬门不满足、需更换壳/增加运行时、删商业验收/明显超时超范围，拿证据回到用户决策。收费模型需要明确账号/模型/整批及单run预算；公网平台/身份/发布另关。

静态收尾：10份文档的Markdown围栏/冲突标记/行末空白、本地链接、主计划末节/决策状态、12个新增测试ID及V24–V30均检查无错误；首轮136个本地链接，追加以下2个产物入口后合计138。范围内git diff --check通过；未跟踪文档另由同一静态脚本检查，不能只靠git diff漏掉。任务JSONL用jq逐条序列化再写入，8条全部PLANNED_NOT_STARTED；测试快照与主源同内容，链接按原主源目录解析。

- [8组增量任务JSONL](/Users/hutou/.gstack/projects/weiweity-fuqing-crm-analytics/tasks-eng-review-20260905-155428.jsonl)：对应原11个工作包，不表示另有8个平台或已执行任务。
- [后续QA测试快照](/Users/hutou/.gstack/projects/weiweity-fuqing-crm-analytics/codex-shine-mage-figma-refinement-test-plan-20260905-155428.md)：全部NOT RUN，保留启动/模型/真库/公网授权边界。

未运行应用测试、浏览器、模型或真实查询。工程review-log记录issues_open：13个发现已进入计划、0个未指定处理的计划关键缺口、3个实施/模型/公网决策仍开；这不是运行CLEAR或发布许可。
