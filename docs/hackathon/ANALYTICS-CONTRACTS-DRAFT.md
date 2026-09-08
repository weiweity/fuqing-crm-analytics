# 统一分析工作台：接口与数据对象草案

日期：2026-09-05。状态：`DRAFT`（完整产品 API 仍未实现）；B0 子集已有可装配合同与原生接线。G2a 另有独立 synthetic 查询合同子集，**不是**全部目标已 IMPLEMENTED。

2026-09-07 局部实现说明：本文件仍是完整产品的目标草案，不是所有接口已实现。前置 B0 的会话/任务/取消/事件子集已落为独立 `analytics-run-b0/v1`，并已接到原生 DSH Web（独立插件、单 Agent Loop、官方 mock）；[实际接口及边界](./B0-RUN-KERNEL-2026-09-06.md)、[T09 原生故障](./B0-NATIVE-FAULT-2026-09-07.md)、[G1 原生状态](./B0-NATIVE-STATE-2026-09-07.md)和[生成 OpenAPI](../../backend/contracts/analytics-run.openapi.json)为该小样的可装配合同。G1 源码已提交 `857d2ce`（[PR #70](https://github.com/weiweity/fuqing-crm-analytics/pull/70)，base [PR #69](https://github.com/weiweity/fuqing-crm-analytics/pull/69)）。G2a 新增独立 `analytics-channel-followup/v1` 查询输入/结果合同与手工金标准，见 [渠道后续购买合同](./CHANNEL-FOLLOWUP-CONTRACT-2026-09-07.md)；G3a 离线 SQL 见 [渠道后续购买计算](./CHANNEL-FOLLOWUP-COMPUTE-2026-09-07.md)。2026-09-08（v0.6.0.0）另接通独立 SNAPSHOT 保存/驾驶舱 HTTP：`analytics-saved-analysis/v1` 与 `analytics-cockpit/v1`，OpenAPI 见 [analysis](../../backend/contracts/analytics-analysis.openapi.json) 与 [cockpit](../../backend/contracts/analytics-cockpit.openapi.json)；浏览器经 `serve.mjs --native-query-assets` 只放行 `/b0/analyses` 与 `/b0/dashboards`，不带 backend bearer。仍 **无完整 B1**。不支持业务 condition patch、QUERY 刷新或完整三类查询产品 API；完整产品 API 仍为下文草案。B0 固定 fixture（含原生卡展示的 100 / 25 / 25%）不是渠道后续购买等三类业务实现，且本子集未改该 25%。隔离入口使用 4315–4319，不是公网地址。不得把 B0 固定 fixture 类型冒充三类完整分析结果。

autoplan v2 范围：§3.5 订阅、§3.6 专家台为后续设计，不实现首版调度/投递/多人专家 API。v1 以单个经营专家、三类受控查询、保存/驾驶舱与分析人群草案闭环为准；不再要求先改造旧 RFM。

本文是待实现的协议设计，不是当前可调用 API。第 1 节描述已核验代码；其余章节均为新方案约束，需在实现时落实为 Pydantic、OpenAPI、生成的 TypeScript 类型和契约测试。总体范围见 [实施方案](./UNIFIED-ANALYTICS-PLAN.md)，验收编号见 [底座与闭环验收](./RUNTIME-VALIDATION-PLAN.md)。

## 1. 当前可复用合同，不改变行为

静态核验基线：`de2d785f4e0c7abe7fcd8fbb39be7d8c5a0c9642` 加当前工作树未提交改动。本轮没有启动服务或运行接口测试。

来源：[Mission 路由](../../backend/routers/missions.py)、[Pydantic 合同](../../backend/contracts/mission.py)、[业务实现](../../backend/services/mission_service.py)、[现有链路测试](../../backend/tests/test_missions_api.py)。

| 项目 | 当前事实 |
|---|---|
| HTTP 前缀 | `/api/v1/missions`；完整使用说明见 [Mission API](./MISSION-API.md) |
| 已有 operationId | `mission_access`、`mission_get_today`、`mission_get`、`mission_diagnose`、`mission_approve`、`mission_create_draft_export`、`mission_download_draft_export`、`mission_reset_demo` |
| 问数输入 | `question`，字符串，2–300 字；没有会话 ID、筛选对象或流式事件 |
| 问数结果 | `answer_mode=DETERMINISTIC_TOOL`，三类受控意图；部分证据/来源字段仍为宽松字典 |
| 审批输入 | `decision=APPROVE`；`note` 可为空，最长 500 字 |
| 写请求头 | `If-Match` 为整数字符串；`Idempotency-Key` 必需，路由检查原始头长度不超过 200 字符 |
| 错误 | 缺头 428；格式错误 400；版本、状态、幂等冲突 409；不是 412 |
| 幂等 | 同 actor、同业务请求、同 key 重放返回首次结果；幂等检查早于当前版本检查；跨 actor 或变更 payload 冲突 |
| Mission 状态 | `AWAITING_APPROVAL → APPROVED → WAITING_MEASUREMENT` |
| 导出状态 | `DRAFT_EXPORT_READY` 属于导出物，不是 Mission 状态；不表示发送或测量已发生 |
| 导出列 | 只有 `synthetic_user_id,mission_id,experiment_arm`；没有订单号、手机号 |
| 实验分组 | ID 哈希稳定分桶，目标约 90/10；有限样本不保证精确比例 |
| 权限现状 | 审批、导出、下载使用普通认证身份；只有 reset 要求 admin。尚无老板专属审批权限 |
| 匿名例外 | 仅经来源检查和双开关验证的 loopback synthetic Mission；不能延伸为整个工作台匿名通行 |

既有 [AI 调用指南](./AI-TOOL-CALLING.md) 仍只约束 Mission 工具。新工具不直接复用旧 MCP 的真实数据默认配置。

## 2. 共同约束（拟定）

- 新 HTTP 前缀拟为 `/api/v1/analytics`，operationId 使用 `analytics_`。未进入实际 OpenAPI 前，客户端不得依赖这些名字。
- 公共 schema 放入 `backend/contracts/`，从现有 `schemas.py` 入口导出；前端消费生成类型，不再手写另一套结构。
- 新对象的输入拒绝未声明字段；未知枚举、任意 SQL、脚本、数据库路径和任意远端 URL 均拒绝。
- 身份、可见范围、可调用工具、模型路由由服务端确定。客户端提供的 owner、审批身份和 provider 凭据不得生效。
- ID 是服务端生成的不透明标识，不能当作权限凭据；所有列表、读取、事件订阅、修改与运行都要校验归属。
- 比例统一使用 0–1，金额带币种与明确精度；缺失和未知用 `null` 加原因，不把它们写成 0。
- 时间戳使用带时区 RFC 3339；观察日使用 ISO 日期；日期范围以业务时区解析，转换后的开始/结束边界必须回传。
- 本地匿名扩容必须有独立 synthetic 能力校验及回归测试；在该功能实现前，新接口仍要求认证。不得仅放宽现有 URL 前缀判断。

### 本地访问与兼容性（拟实现）

新增 GET /access（analytics_get_access），只返回enabled/profile/answer_modes/capabilities与schema版本；未授权不返回账号、对象或数据源路径。新功能开关 FQ_ANALYTICS_WORKSPACE_ENABLED 默认关闭。本地免登录另须 FQ_LOCAL_DEMO_NO_LOGIN、回环/来源检查以及新analytics合成manifest/hash独立校验；仅授予本演示的有限能力，不开放旧CRM。真实认证模式由服务端既有身份映射能力；生产分角色授权另验，不能把DEMO actor当CEO身份。

answer_mode 为 STUB / DETERMINISTIC_TOOL / AGENT_TOOL；STUB只表示合同流程，DETERMINISTIC_TOOL表示无模型真实合成计算，只有获验模型+受控工具链可标AGENT_TOOL。首次成功固定fixture+预期hash和这些标记一起呈现，不冒充完整产品验收。

GET /catalog 公开范围由当前能力校验，返回schema_version/query_versions/metric_versions/data_profile/supported_filters/功能开关状态，不曝光任意私有连接。离线OpenAPI与生成TS附同一schema内容hash；运行时/catalog版本不匹配时拒绝生成新请求并提示更新客户端，历史run仍可读。不支持的旧保存定义只读，刷新422 UNSUPPORTED_VERSION；迁移显式创建新版本，不能暗改历史口径。

## 3. 核心数据对象（拟定）

### 3.1 FilterSpec：完整分析条件

| 字段 | 类型/约束 |
|---|---|
| `schema_version` | 固定版本字符串；不兼容变更必须升级 |
| `cohort_window` | 首购入组窗口：FIXED带开始/结束日期（开始含、结束不含）或ROLLING带登记窗口ID；互斥；替代旧草案含混的time_window |
| `observation_days` | 30/60/90之一，代表首购后的精确N×24小时观察长度；“90改60”只修改此字段；catalog唯一映射query/metric版本，不暗改入组窗口 |
| `data_snapshot_ref` | 有权限的合成快照ID/版本；缺省选目录明确的当前发布版，不接受文件路径；选定后不可漂移 |
| `as_of`（仅resolved输出） | 服务端从快照解析的RFC3339精确截数时间，不由模型覆盖；仅有日期的旧manifest须在B1明确封板时点并发布带精确时间的新合成版本，不暗猜小时 |
| `timezone` | 合法 IANA 时区；默认 `Asia/Shanghai`，必须显式回显 |
| `channel_ids` | 登记过的渠道 ID 数组；空数组表示全部，不能继承上次页面状态 |
| `cohort_ref` | 可空；有值时包含人群定义 ID 和版本，不接收个人标识名单 |
| `product_ids` | 登记过的合成商品 ID 数组；空数组表示全部 |
| `exclude_low_price` | 显式布尔值；不支持此条件的查询应拒绝，不可忽略 |
| `comparison` | 无对比或登记过的对比方式；自定义对比必须带独立日期范围 |

服务端解析后生成 `resolved_filters` 与规范化 `filter_hash`，包含resolved_cohort_start/end、observation_days、data_snapshot_ref、as_of、timezone及全部业务条件。缓存、证据、人群绑定沿用这些字段/hash和query/metric版本。“换入组月份”“观察90改60”“换截数快照”是三种不同操作，各自回显差异。缺字段只按catalog显式默认解析，不读取此前Pinia状态；ROLLING先按as_of与业务时区解析成固定边界再计算。不能只保存自然语言或少一类时间边界。

### 3.2 SavedAnalysis：可复用分析定义

| 字段 | 类型/约束 |
|---|---|
| `analysis_id` / `version` | 不透明 ID / 从 1 开始的整数；已发布版本不可原地改写 |
| `title` | 1–120 字；纯文本 |
| `query_ref` | 登记过的查询 ID 与版本；不存模型生成的 SQL |
| `metric_refs` | 指标 ID 与口径版本数组；单位、分母、成熟窗口可查询 |
| `filters` | 完整 FilterSpec；窗口可滚动，口径不随滚动改变 |
| `visual_spec` | 受控图表配置，见 3.4 |
| `created_from_run_id` | 来源运行记录，服务端确认与定义一致 |
| `owner_id` / `visibility` | 服务端身份 / 初期固定 PRIVATE；共享功能另行实现权限 |
| `endorsement` | PERSONAL 或 VERIFIED；收藏不会变为 VERIFIED，认证需单独权限与审计 |

用户改标题、布局与修改指标口径是不同操作。修改共享分析定义产生新版本；既有驾驶舱不静默切换版本。

### 3.3 AnalysisRun：一次运行和证据

必需字段：`run_id`、`version`、`source_kind`、`source_ref`、`conversation_id`、`parent_run_id`（可空）、`status`、`phase`、`created_at`、`resolved_filters`、`filter_hash`、`query_ref`、`metric_refs`、`data_provenance`、`facts`、`evidence_refs`、`evidence_digest`、`limitations`、`runtime_trace_ref`（stub/offline 时可空并标 answer_mode）。source_kind=CHAT时conversation_id必填，source_ref绑定该会话；ASSET_REFRESH时conversation_id与parent_run_id为空，source_ref固定获权资产/版本，不伪造问题或会话。version从1起，每次持久化状态/取消意图/结果提交递增，event序列单独计，不为每token增加version；GET与创建受理响应均返回version。A1采用先受理后解析：ACCEPTED/PLANNING时query/metric/filters/provenance/facts/digest明确可空，不伪填指标；各查询执行前冻结自己的条件，SUCCEEDED强制主结果完整并通过对应query输出schema。phase是执行阶段，不代替业务status。

- `status`：QUEUED、RUNNING、NEEDS_INPUT、SUCCEEDED、FAILED、CANCELLING、CANCELLED、UNKNOWN。
- 新定义尚未保存时允许没有 `analysis_id`；保存时服务端绑定当前已验证定义，保留原运行。
- `facts` 由确定性工具产生，模型不能覆盖；可变结构由 query 对应的输出 schema 校验。
- `data_provenance` 延续 `synthetic`、`contains_real_data=false`、数据版本/内容哈希、观察日、指标版本，并补足本次运行的数据新鲜度信息。
- 模型的解释与 facts 分开存储；经营因果、情景假设和观察事实分开标识。证据只展示工具与查询依据，不公开内部思维链。
- 固定 `runtime`、运行时修订、模型提供方/模型 ID、提示与工具集版本。AGENT_TOOL记录实际provider/model；确定性刷新用QUERY_EXECUTOR及代码修订，provider/model为空，不继承最近聊天的模型或伪造模型trace。业务 run ID 不等于运行时 session、run、node 或 tool-call ID（包括 DSH / Hermes）；adapter 必须显式映射。
- 数据集变更后可产生新运行，但不得改写历史结果。缓存键包含数据内容、口径/查询版本、完整条件、身份权限范围。
- 取消请求不等于执行已退出；只有执行端确认结束才变为 CANCELLED。崩溃且无法确认时使用 UNKNOWN，禁止悄悄重做带副作用的步骤。

计算调度补充（待实现）：AnalysisRun 是业务运行记录，后台计算任务是执行记录，runtime run 则是 Agent 的运行记录，三者不混用。业务 run 映射计算任务及执行 attempt；受理、查询状态和读取已有结果不得占用重 SQL 的执行槽。重计算通过独立有界进程执行，不使用单账号/单 IP 登录限制代替资源调度。

首版取消在途共享计算设计：同一个身份/逻辑请求/key 只创建一个业务 run；不同请求分别记录执行，仅复用完整条件、query/metric/data 版本和权限域一致的已成功缓存。不同 run 不共享仍在运行的 worker，不需要实现跨 run 等待者计数。缓存命中也创建本次归属记录并附 cached_from_run_id，读取仍重新鉴权。显式取消只作用本 run；浏览器断开不自动取消，执行退出前不得释放槽位或标 CANCELLED。详见 [验收计划](./RUNTIME-VALIDATION-PLAN.md)。

会话输入新增 parent_run_id（可空）与显式 condition_patch；父 run 必须属于当前会话且可见。null/清空与缺省区分，服务端返回完整条件及差异。两个请求引用同一父 run 时形成分支；UI 按 run_id 归位，不用最后到达的网络响应覆盖另一个分支。NEEDS_INPUT 是一次运行的终态，澄清后新 run 引用它。

执行状态补充：QUEUED→RUNNING→SUCCEEDED/FAILED/NEEDS_INPUT；QUEUED 可直接 CANCELLED；RUNNING 取消先 CANCELLING，确认进程退出后 CANCELLED。成功提交与取消通过事务比较状态竞争，只允许一个终态；SUCCEEDED 后取消返回已经完成，不追溯抹除结果。失联为 UNKNOWN，恢复时核验 attempt/进程代际与持久记录，不能仅凭 PID 推定进程身份。attempt_id 为 fencing token，过时代际结果不能提交。

#### A1：先受理业务任务，再派发DSH（用户已确认）

用户确认“没问题，确认，下一项”。业务run与待派发意图在同一应用状态短事务提交，然后才进行runtime网络调用；复用既定jobs/runtime模块，不引入消息队列平台或第二个Agent循环。

```text
分析请求 → 鉴权/校验输入 → [run + 请求hash + dispatch意图 + 原202]同事务
                              ↓ 提交后
                         DSH(session, requestId=固定dispatch key)
                              ↓ 获权工具上下文绑定已有run
                         查询步骤/证据 → 校验主结果 → 唯一业务终态
```

- 受理固定调用者、原始请求、允许数据范围、runtime/tool/skill配置版本与预算。派发前再核当前权限/取消意图；未派发已取消的任务不得补发。dispatch记录固定session、requestId与payload hash；同key换内容拒绝。DSH的accepted只是入inbox，不是业务SUCCEEDED。
- 受理响应丢失沿用§4同key找回原run；已登记未派发时重启，从原意图恢复。派发回包丢失只核对原session/requestId，按已验协议有限同标识重放；无法确认则UNKNOWN，不换标识再问一遍。上游确有inbox/已记消息rpcId去重，本层复用而非宣称上游没有幂等；不会承诺跨系统exactly-once。
- 模型在第一次查询前失败也有业务记录：确定失败为FAILED；执行归属/派发不确定为UNKNOWN。阶段覆盖ACCEPTED、PLANNING、EXECUTING、FINALIZING；失败保留安全诊断、已完成步骤与剩余预算。取消覆盖模型生成、工具间隙、查询执行及最终提交，不仅取消SQL。
- session可有排队或steer输入，停止必须映射到明确run/dispatch/活动执行，不凭session ID误停其他请求。无法证明run级停止隔离时，B0不开放相应原生queue/steer动作并报告承载缺口，不暗中限制全站单人登录。取消和成功仍由既有状态CAS裁决，旧代际不能提交。
- 只读已有分析、驾驶舱读取以及手动展示编辑不创建分析run；局部配置保存走其PATCH/key/version。自然语言编辑可使用runtime生成受控提案，但提案不是查询成功，也不能凭聊天完成就改驾驶舱。

#### 多工具结果与主证据（A1的契约细化）

一个分析run允许预算内多次工具调用，不限制成只能查询一次。沿用执行管理器的步骤/attempt记录，不另造工作流服务：

- 受控查询步骤由后端生成step_id，绑定run、dispatch、受信调用标识与规范参数hash；CHAT使用adapter映射的runtime tool-call标识，ASSET_REFRESH使用执行器生成的固定标识。同调用同参恢复同一步，同调用改参拒绝，不能让模型伪造别人的step/run。目录读取、证据读取和纯推理不占重SQL槽，但计入相应调用预算。
- 每个实际查询步骤在入队前冻结query/metric版本、完整resolved_filters、数据快照与step_hash；后续步骤可显式改变筛选做对比，但不得修改已完成步骤或在未声明的情况下更换共同数据快照。依赖步骤读取本run明确的前序证据；失败、未完成或旧run结果不伪装成本轮上游。
- 最终固定primary_result_ref指向一个完整、合法的主查询结果；run顶层query_ref/filters/facts/digest是该主结果的投影，辅助结果以evidence_refs分别保留条件、分母、版本与局限。最终必须覆盖请求所要求的必要步骤；没有完整主结果或必要步骤失败时不得SUCCEEDED、保存完整分析或准备草案。部分证据可展示为未完成。
- 新追问仍新run；草案只能绑定其明确的成功人群结果，不从多工具混合文字提取人群或相加不同分母。最终提交再次验证工具输出schema、执行归属、当前权限、版本与取消意图。

#### 已有资产的确定性刷新

单一 `POST /refresh-runs` 创建ASSET_REFRESH运行。输入source为互斥联合：`{kind:ANALYSIS,analysis_id,analysis_version}` 或 `{kind:DASHBOARD_CARD,dashboard_id,dashboard_version,card_id}`；客户端不提供owner、query SQL、任意数据路径或“模拟提问”。服务端鉴权后从定义及登记的数据策略解析完整有效条件，在短事务内固定source_ref、effective_spec_hash、目标快照、run与dispatch意图，返回同一202/key恢复合同。资产版本已变返回409，不对新版本悄悄刷新；快照改变不改变已受理run。

派发类型为QUERY，直接走同一个有界执行管理器和受控查询函数，不调用DSH/模型，不创建第二个刷新服务。answer_mode=DETERMINISTIC_TOOL；状态、步骤证据、事件、取消、预算、成功校验与CHAT共用。整板刷新按明确受影响卡片创建有限个运行，逐卡反馈受理/排队/拒绝，不能绕过单调用者配额。成功后只得到候选证据；SNAPSHOT更新引用仍要用户确认，刷新不是另存分析、修改审批或启用订阅。

### 3.4 DashboardSpec：可组装驾驶舱与板块插件

2026-09-05 用户确认“板块插件化、驾驶舱配置化、AI 局部编辑、每天固定查看”。本节替代旧的“所有卡片固定快照、仅标题/顺序/列宽微调”约束；是获准的设计方向，字段仍需 B1 schema 验证，不代表已实现。

必需字段继续为 `dashboard_id`、`version`、`owner_id`、`title`、`cards`、`global_filters`。首版仍为一个私人驾驶舱；看板配置和运行证据由业务后端保存，不只存在于聊天记录或浏览器。

区分三层：开发者登记可复用的板块类型；老板/AI 创建并配置板块实例；驾驶舱保存这些实例的组合。`card_id` 就是板块实例的稳定 ID，不另造一套 panel ID。一个 DSH 业务插件可承载多个板块类型；不是一块一个服务，也不直接加载 Grafana 插件或旧 Vue 组件源码。

每张卡的候选字段为 `card_id`、`plugin_ref={type,version}`、`analysis_ref={id,version}`、`data_mode`、`layout`、`display_overrides`、`filter_mapping`、`local_filters`。展示响应必须带实际 `run_id`、`evidence_digest`、完整条件和新鲜度状态；AI 不能提交或修改这些事实字段。

- 已登记类型初期为指标、表格、柱形图、折线图、证据说明；新类型经过输出/配置 schema、权限与渲染测试后扩展。不允许任意 JS、HTML、组件导入、外部数据 URL 或模型在线改应用源码。业务模板组合已登记类型，不因此新增查询能力。
- `visual_spec` 只能引用结果中的字段、声明的单位/聚合和允许的展示参数；前后端各自校验。标题、图形、移动/缩放不修改分析定义或重算数据。手动编辑及应用已生成的配置变更不调用模型；AI理解自然语言编辑意图可以调用模型，但不得顺带重新分析经营数据。
- AI 和手动编辑使用同一受控变更合同：增添、复制、移动/缩放、改展示、改指定条件、移除、撤销。拟复用 `PATCH /dashboards/{id}`，每次明确目标 `card_id`、基准版本、操作及参数；不是任意 JSON 路径或整页代码覆盖。先显示受影响板块和预览，再由用户保存；保存要求稳定 key 和 If-Match。未指明整板操作时默认只改目标板块，目标不明确则澄清。
- 每次保存产生新配置版本；版本冲突返回409，不覆盖另一标签页的新改动。撤销是基于当前版本恢复选定配置的另一次修改，不能撤销数据库事实、营销批准或已生成的导出。复制分配新 card_id；修改副本不影响原件。
- 全局筛选通过 `filter_mapping` 显式连接到板块。局部筛选、继承/覆盖及不兼容项必须回显；改整板条件前预览受影响范围，不能静默忽略不支持项。指标/筛选改变只为受影响板块产生新分析运行；成功前保留旧证据并标原条件，不套新条件冒充新结果。其他引用同一 SavedAnalysis 的板块不自动改变定义。

日常查看与历史证据采用两种模式，首次添加时明确展示，可由用户选择。SavedAnalysis的已保存FilterSpec不原地改写；LATEST_SUCCESS仅按用户选择的最新数据策略展开目标快照/as_of与由其解析的ROLLING窗口，再叠加已保存的局部/全局条件形成完整目标resolved_filters。固定首购入组窗、观察N日、query/metric版本不随刷新改变；解析规则和数据发布范围在B1冻结。每次实际run仍固定一份精确快照，SNAPSHOT则始终使用其原完整条件：

- `LATEST_SUCCESS`（日常默认）：保持获批的分析定义版本和布局，按当前权限、完整有效条件与登记数据范围读取最新兼容的成功结果。最新是数据快照/截至日语义，不是网络最后返回或 run 创建最晚。若尚无符合当前目标快照/滚动窗的结果，展示待刷新；允许另列上次结果但必须标 STALE/实际日期。打开看板读取已有结果，不隐式启动 Agent、重计算或订阅任务；用户刷新复用已有有界执行机制，失败不把旧结果标为今日。显示数据截止日、成功计算时间及实际 run/digest；这一动态解析不改写保存定义和历史 run。
- `SNAPSHOT`：固定 `pinned_run_id` 与 digest。显式刷新产生候选 run，用户确认后才更新引用；历史分析链接、试点草案和审批仍锁定来源 run/digest，不因日常驾驶舱更新而变化。

跨板块比较显示各自条件与数据日期；日期/成熟窗不一致时提示不可直接比较，不拼成同口径汇总。板块独立加载与报错，错误不清空其他板块。布局/读取证据不占重计算槽，整板刷新也受现有队列与调用者配额约束，不能按板块数开启无界并发。每天固定看不意味着已有数据日更、调度器或外部消息；定时刷新/推送仍属§3.5后续范围。

刷新与配置并发：受理记录dashboard/card及effective_spec_hash（分析/指标版本、有效数据策略、映射和完整业务条件；不含标题、尺寸、位置）。返回的证据还带实际snapshot/filter_hash；后台候选选择和前端展示均核验当前card仍存在、有效定义兼容及新鲜度。更改条件、移除、撤销或旧响应晚到不能仅靠card_id相同就覆盖当前板块。旧run可以依法留存为自己的历史证据；纯标题/布局变更不使同条件数据失效。复制分配新card_id，不继承在途请求归属，仍可按权限和完整条件复用已成功缓存。AI预览保存也须复核当前配置版本/权限；预览后配置已变返回409，未保存不改资产。

### 3.5 SubscriptionSpec 与 DeliveryAttempt

订阅必需字段：`subscription_id`、`version`、`owner_id`、`analysis_ref`、`mode`、`schedule`、`condition`、`recipient_refs`、`execution_identity`、`status`。

- `mode=REFRESH`：重复执行已保存定义；`REDIAGNOSE`：重新研究并产生新草稿，不覆盖已认可分析。均为后续订阅阶段；本提交版不建调度器。
- `schedule` 显式时区；支持范围由实际调度适配器验证。不要把客户端自然语言直接当 cron。
- 创建默认为 DRAFT。启用前展示指标、条件、接收人和频率，校验调用方及接收人数据权限。
- 只有一个调度器负责一份订阅。运行身份权限被撤销、定义失效或数据不满足新鲜度规则时，停止执行并记录原因。
- 每次生成接收人内容、首次投递及重试前，重新校验订阅 owner、执行身份和每位接收人的当前数据/分析对象权限；已缓存结果不能绕过撤权。消息链接打开时再鉴权，已发出的正文不能靠链接撤权收回，因此正文遵循最小披露。
- 后续订阅的第一个可验版本使用 `delivery_mode=PREVIEW` 假投递器；不得出现“飞书已送达”。本首版至多文案说明预览，不创建订阅任务；外部投递另行授权与验收。
- 调度首先用 `(subscription_id, subscription_version, scheduled_occurrence)` 的数据库唯一约束原子认领逻辑执行，再创建其业务 run。occurrence 是计划中的时点，不是实际执行的当前时间；同一次触发的重试/并发/重启必须复用该逻辑执行 ID。认领后崩溃需恢复已有记录，不能创建另一个逻辑执行绕过去重。
- DeliveryAttempt 独立记录逻辑执行 ID、业务 run、订阅版本、计划时间、接收人、固定内容版本、幂等键和状态。投递唯一键基于“逻辑执行 ID＋接收人＋首次固定的内容版本”；重试不得换 ID 或悄悄变更内容。手动重跑是独立显式动作，有自己的幂等键，不伪装成原定时任务重试。
- PREVIEW_READY、PENDING、PROVIDER_ACCEPTED、DELIVERED、FAILED、UNKNOWN 分开。渠道没有送达证据时不能置 DELIVERED；UNKNOWN 不自动重发可能已发送的消息。
- 暂停只阻止新 tick；已在途消息显示真实状态，不伪装撤回成功。

### 3.6 ExpertDefinition 与专家台

专家定义保存 `expert_id`、业务职责、提示/方法版本、允许工具与输出 schema；使用者的权限与专家工具集取交集。v1 先提供经营分析专家，运营/财务协作作为模板扩展，不按指标开一个服务。

专家台保存专家引用与工作流版本；同一任务共享受控人群、数据版本和 run 关联。依赖步骤明确等待本轮上游结果，不拿上次缓存冒充本轮输入。财务信息不足必须输出 UNKNOWN，不能自动补成本。

## 4. 候选 HTTP 表面（全部待实现）

表中读操作也需要身份与对象范围检查。POST 不一定执行外部动作，但创建记录仍须可追踪。

| 方法与相对路径 | 候选 operationId | 用途 |
|---|---|---|
| `GET /catalog` | `analytics_get_catalog` | 支持的问题、指标、查询、专家、看板、条件与数据可用范围 |
| `POST /conversations` | `analytics_create_conversation` | 创建自有会话，不接受客户端指定 owner |
| `GET /conversations/{id}` | `analytics_get_conversation` | 读取会话、已持久化运行与分析引用 |
| `POST /conversations/{id}/runs` | `analytics_create_run` | 受控问题＋条件＋可选专家台；返回 202 和 run ID |
| `POST /refresh-runs` | `analytics_create_refresh_run` | 从指定已保存分析或驾驶舱板块创建确定性刷新run；无会话、无模型 |
| `GET /runs/{id}` | `analytics_get_run` | 查询状态、结果与证据 |
| `GET /runs/{id}/events` | `analytics_stream_run` | 服务端事件流；重连不重新执行工具 |
| `POST /runs/{id}/cancel` | `analytics_cancel_run` | 请求取消；返回当前状态，不承诺瞬时终止 |
| `POST /analyses` | `analytics_save_analysis` | 用户明确保存后，从验证过的 run 创建分析定义 |
| `GET /analyses` | `analytics_list_analyses` | 当前身份可见的已保存分析列表，用于DSH资产弹层 |
| `GET /analyses/{id}` | `analytics_get_analysis` | 读取权限范围内的定义与指定版本 |
| `POST /analyses/{id}/versions` | `analytics_version_analysis` | 从当前版本派生新定义 |
| `GET /dashboards` | `analytics_list_dashboards` | 当前身份的私人驾驶舱入口；v1至多一个或空列表 |
| `POST /dashboards` / `GET /dashboards/{id}` | `analytics_create_dashboard` / `analytics_get_dashboard` | 新建/读取驾驶舱 |
| `PATCH /dashboards/{id}` | `analytics_update_dashboard` | 布局、引用与条件更新，需当前版本 |
| `POST /board-links/resolve` | `analytics_resolve_board_link` | 返回受控相对地址、完整条件与不支持项，不执行页面点击 |
| `POST /subscriptions` / `GET /subscriptions/{id}` | `analytics_create_subscription` / `analytics_get_subscription` | 新建草稿/读取订阅 |
| `POST /subscriptions/{id}/activate` | `analytics_activate_subscription` | 人类确认后启用；PREVIEW 与外部发送分别授权 |
| `POST /subscriptions/{id}/pause` | `analytics_pause_subscription` | 暂停并保留已有运行记录 |

DSH UI设计补充：GET /analyses、GET /dashboards 只按服务端当前身份授权返回；列表拟返回 items/next_cursor，limit默认20、最大50，稳定排序和不透明游标在B1冻结。拒绝未声明的owner筛选，不接受前端指定归属；每次翻页重新鉴权。v1私人驾驶舱唯一性需服务端约束，重复创建按稳定key/既有资产恢复，不靠隐藏新建按钮。UI弹层只持有导航引用，不以本地浏览器缓存替代资产存储。

新合同在 B1 落实为可验证 schema 后冻结；未冻结前禁止作为正式外部 API 发布。subscriptions 全部路径延后；analyses/versions 的高级定义编辑、专家台、共享认证不属于首版必建路径。单专家从服务端能力目录选择，不接受任意专家/模型配置。

首版新增拟定表面：POST /decision-drafts（从 SUCCEEDED run 的受控人群定义创建），GET /decision-drafts/{id}，POST /decision-drafts/{id}/approve，POST /decision-drafts/{id}/exports，GET /decision-drafts/{id}/exports/{export_id}/download。operationId 分别以 analytics_create/get/approve_decision_draft、analytics_create/download_decision_export 表达，B1 生成 OpenAPI 时冻结。新路由调用隔离的 Mission adapter，不改变旧 /missions 请求含义。

### 写操作与并发规则

- 创建会话/run/资产/订阅，以及取消、启用、暂停，均要求稳定 `Idempotency-Key`。更新既有资源还要求 `If-Match`。
- 新资源幂等作用域拟定为“服务端身份＋操作＋目标资源＋key”；规范请求哈希覆盖实际业务参数。同逻辑重试不生成第二条执行。
- 对已经完成的同一幂等请求，先校验当前身份访问资格，再返回原结果；权限已撤销时不能借重放绕过权限。
- 拟沿用 428 缺头、409 冲突；401 未认证、403 无操作权限、404 不存在或不可见、422 参数不支持、429 配额限制、503 数据/运行时不可用。具体 OpenAPI 与测试是最终依据。
- 409 后读取新状态并要求确认变更影响，不静默覆盖。超时需查询已有 run；不能换 key 盲目再提交。

丢失创建响应：服务端须在同一短事务写入key/request_hash和accepted响应（含run_id、version与Location）。同key同规范请求重放，包括执行中/已完成时，均返回首次受理响应和同一run_id，调用方再GET状态；不要求它先知道丢失的ID。首版幂等记录随本地应用状态保留，不定时淘汰；以后显式归档仍保留key墓碑，退役请求410而非创建重复动作。未受理的参数验证错误不占执行记录，冲突仍409。

取消/资产更新的If-Match取最近GET返回version；竞争时409后重读，终态不能再次执行取消副作用。GET失败最多3次指数退避(1/2/4秒)且受总截止限制；429携带Retry-After。完全没收到HTTP响应的传输故障允许同key有限重放（最多3次），用于找回已受理ID；收到错误响应时，仅在retryable=true时同key有限重放。都不换key。权限/绑定/来源错误不重试；已获知业务UNKNOWN则先查询人工核对，不重新执行副作用。客户端库默认自动重试须显式配置以遵守此约束。

### 标准事件（拟定）

事件包包含 `event_id`、`run_id`、递增 `sequence`、`type`、`occurred_at` 和经过脱敏/校验的 `payload`。

事件类型：`run.started`、`tool.started`、`tool.completed`、`answer.delta`、`artifact.ready`、`run.needs_input`、`run.completed`、`run.failed`、`run.cancelled`。

运行时的已完成工具事件只用于展示，不能再次执行；DSH 原生发送/停止/重试也必须映射到业务 run、稳定 key 和取消合同。最终成功由持久化业务 run 决定，不由最后一个文本 token 决定。重连用事件游标；游标过期时返回明确恢复指示，客户端重新读取 run 快照。

SSE标准用Last-Event-ID恢复，无法设置头的浏览器实现可用受控after游标参数；两者都有但不同则422。每run sequence严格递增，事件保留至少24小时，run/证据另持久保存。游标过期返回410 EVENT_CURSOR_EXPIRED与当前可见run链接；客户端GET快照及last_sequence后继续，不重新提交问题。先鉴权再返回恢复信息。每个错误有request_id，GET /runs/{id}提供安全diagnostics：phase、attempt_id、queue_ms、tool_ms、runtime_status/可空trace_ref，不包含供应方私密原文或内部思维链。

## 5. 工具权限分层

| 能力 | 初期是否给模型 | 控制方式 |
|---|---|---|
| 查支持目录、执行受控查询、检索已保存分析 | 是 | 服务端工具白名单、参数/输出 schema、只读数据源 |
| 建议图表/看板、解释差异 | 是 | 只返回受约束草案；facts 不能被模型改写 |
| 保存分析、修改驾驶舱、建立订阅 | 人类明确请求后 | 后端验证身份、版本与幂等；不套用营销 Mission 审批 |
| 营销审批、生成名单 | 不给一般问数 Agent 自动权限 | 进入既有 Mission 子链，独立的人类确认与后端权限 |
| reset、任意 SQL、Shell、文件读取、真实 CRM/短信发送 | 否 | 本次工具目录不暴露；也不以隐藏子 Agent 绕过 |

新调用指南实现时另建工作台版本，不把旧 `mission_` 前缀限制机械放宽成全部后端可调用。

### 5.1 DSH控制面与可选MCP的装配边界

这些是既有最小权限原则的工程细化，不新增运行时或网关服务。B0对固定DSH提交建立 `control_surface_manifest`：HTTP method/path/operation、WS mux中的逻辑流/方法、精确Fetch路由分别登记所需业务能力、参数边界、对象归属和响应字段。未登记默认拒绝；禁止通配转发 `/api/*` 或把整个WebSocket直通上游。DSH原有cookie/Host/Origin保护保留，但不能代替业务RBAC和run/session归属检查。

原生必要的发现、会话、历史、事件操作逐项验证，工作区与preset由后端注入；用户不能指定宿主cwd、任意模型/插件/配置、上传/日志下载或打开本机文件。静态资源和获权业务数据路径分别列明。重连与每条操作重新验证当前权限，撤权后不得依赖已建立连接继续读取；超大消息按资源门拒绝。B0同时证明正常路径可用和绕过路径被拒绝，无fork无法满足时触发现有硬门，不以隐藏UI替代隔离。

首版优先DSH类型化工具直接调用同一业务服务/API；MCP是可选协议适配，不是另建必需平台。若接MCP，server identity、工具名、input/output schema hash和工具集版本进入获批装配清单，能力交集在初始化、重连/列表变化和实际调用时均验证。新发现或漂移工具不自动加入经营专家；description/annotations不是授权。不支持的schema或宽松JsonValue退化不得绕过FastAPI的严格业务输出校验；额外字段、非法快照/归属及错误输出拒绝。旧私有MCP配置保持不接入。

外部AI客户端未来经MCP调用创建业务run的API，与DSH运行内部已经绑定run的查询工具分开；内部工具不能递归调用“创建run”再启动一个DSH循环。两种入口都复用同一query/metric合同。

### 5.2 Skills、上下文与长期记忆

一个增长分析师复用DSH原生Skills发现/按需加载和compaction，不自建Agent循环或向量记忆服务。业务SOP只指导分析顺序、何时澄清和怎样解释；指标计算、权限、审批由代码合同决定。

- 本preset仅加载获批隔离包：关闭默认个人/项目根扫描（固定版本配置 `includeDefaultRoots:false`），显式审查custom/bundled根。整个允许内容包的SKILL.md及references/assets使用manifest/hash绑定版本，不只记Skill名称或关闭watch；运行中的任务始终读取同一获批内容。Agent不得写包；禁止符号链接/相对路径逃逸。引用文件由受控loader读取，不开放通用文件工具；脚本或allowed-tools声明不会自行获得执行权。
- 运行上下文由后端重建，包含请求/已解析条件、parent关系、选定快照与口径版本、已完成步骤/证据引用、待澄清项、Skill/工具版本和剩余预算。首次派发、压缩后或故障恢复时都重读业务状态；权限始终以当前后端为准。原生摘要只是会话辅助，不是facts/审批/权限来源。
- 使用轻量证据引用和必要的有界摘要，不把订单明细、大名单和完整工具输出反复塞进模型。模型引用某结论时必须能对应实际成功run/步骤；摘要旧数字、缺失证据或不同快照冲突时重读受控证据或明确不能确认，不能凭记忆补数。
- 长期偏好/经营背景仅作为未来可纠正的信息类型，要求归属、来源、更新时间和失效规则；不得静默改变已保存条件、口径和批准。首版不新增跨会话自动写记忆，也不把Hermes的MEMORY文件挂入DSH。老板个人驾驶舱属于明确保存的业务资产，不是自动长期记忆。
- 自进化只保留“反馈→方法候选→合成回归→人工批准→新版本/可回滚”的后续边界，首版使用固定获批SOP；不自动发布候选、不改指标/权限、不执行真实营销。Subagent和专家团队亦不进首版；将来要验证证据统一、权限交集和共享总预算，不能通过子Agent绕过边界。

## 6. 分析与营销动作的关联

当前 Mission 不消费新 FilterSpec 或 SavedAnalysis，不能把任意问数结果的“行动”直接指向今日固定 Mission。首版目标新增显式分析→人群→草案绑定，同时保留独立旧 Mission 入口。绑定未通过可演示旧链，但须标“新闭环未完成”，商业首版验收第6项不能算通过。不能直接调用旧 create_draft_export 重新挑选其固定人群。

拟定 CohortBinding 固定 source_run_id、source_result_ref（具体step/结果ID）、可选 analysis ID/版本、query/metric/data 版本、filter_hash、cohort_definition/version、cohort_count、cohort_digest、action_version 和 evidence_digest。source_result_ref必须属于指定SUCCEEDED run并通过人群输出schema，可明确选择主结果或辅助结果，不能凭最后工具/模型文字猜测；其query/filters/digest取该结果而不是盲取run主结果。后端从只读合成工具解析成员并冻结摘要，不信任客户端名单。审批页面回显选定结果的条件、人数和证据，服务端以 approval_digest 绑定草案全部语义（含source_result_ref）；导出重验身份、版本、状态和摘要。数据已更新时历史证据可读，但不能用新的成员集沿用旧批准；生成新草案并再审批。一般问数 Agent 无权自批、修改摘要或自动导出。

DecisionDraft 包含机会/依据/限制、候选动作与“不新增营销”比较、owner/资源上限/成本等待确认项、观察周期/停止条件、binding、version、状态。缺真实财务和负责人不妨碍合成草案演示，但必须显式标未知；真实试点另行审批。所有写操作、CSV 发布和重试沿用对象级权限、事务、幂等，不做 runtime 跨库事务。

导出状态采用三段式：短事务以 actor/key/digest 认领 PENDING attempt → 锁外读取固定合成快照并写 attempt 专属临时文件、fsync/hash → 短事务重验审批摘要/版本并 CAS 发布 READY。最终文件使用不可变 export/attempt 名；下载只认已提交的 READY，不按文件是否存在判断。文件落盘但未提交由同 key 恢复核对 hash/digest 后提交或记失败；不会自动重选人群或返回另一个文件。用户权限撤销/批准变化即禁止发布及下载。孤儿产物只登记待精确清理，不在本轮删除。

POST /decision-drafts/{id}/exports 受理返回202，固定export_id、attempt_id、status=PENDING和Location指向GET /decision-drafts/{id}。该GET包含exports摘要：export_id、status=PENDING/READY/FAILED/UNKNOWN、version、binding_digest、error_code、retryable及READY时的download_url。创建丢响应同key回原export_id；前端轮询草案GET可恢复，不凭下载404猜任务状态。未READY不返回下载链接；下载重验当前权限与批准摘要。

## 7. v1 指标与合成金标准约定（拟定）

- 先将订单行归并为唯一 (synthetic_user_id, order_id) 的订单事实；订单头金额不能因多商品行重复相加。缺订单身份/支付时间/渠道等关键字段进入质量失败或 UNKNOWN 桶，不能伪填。初期生成器的一订单一商品不能覆盖真实多行情况，需要额外手工 fixture。
- 有效订单：截至 as_of 已支付且未取消、净支付金额大于 0；全退款排除、部分退款保留且金额用净额。这是合成 v1 的 proposed net-positive-paid 口径，不冒充公司已批准会计口径。退款数据按同一 as_of 截止，发布后不原地改历史数据版本。
- 首次可观察购买：在该 data version 全可观察历史上找最早有效订单，再按首购时间筛选入组；不能先筛观察期再把老客当新客。排序 (paid_at, order_id)，同刻不同有效订单属于后续订单，可计二单，必须专门金标准验证。若业务希望合并同时支付，另起 metric version，不暗改。
- 首购渠道由首订单确定后固定；首购商品集合去重排序，多品首单单列，渠道总览每用户入组一次。先确定首次渠道再做 channel filter；后续跨渠道不会重分首次渠道。
- N=30/60/90 日时，成熟分母仅纳入 as_of >= first_paid_at + N 天的人；分子为该人群在 [first_paid_at, first_paid_at+N天] 且排序晚于首订单的另一有效订单人数。空分母为 null；未成熟人数单列。新增严格 v1 与旧草图 (0,N] 文字/旧视图并非默认等价。
- 后续跨渠道、后续商品、净支付观察值采用同一 N 日窗口和成熟分母；不能用全历史 cross_channel_rate 与 N 日二单率并排比较而不说明。无历史覆盖只称“首次观察到”，不是因果获客/终身 LTV。
- cohort_digest 由固定规范化、排序后的合成成员集合和绑定元数据计算，规范与 hash_version 一并存储；大名单不经模型。不可用净支付观察值宣称利润/增量，成本缺失为 null + reason。
- 2026-09-07 G2a/G3a 子集：渠道首次观察队列的独立合同、11 用户/22 订单手算金标准与离线 SQL 已落地，见 [渠道后续购买合同](./CHANNEL-FOLLOWUP-CONTRACT-2026-09-07.md) 与 [计算报告](./CHANNEL-FOLLOWUP-COMPUTE-2026-09-07.md)。后两族仍 DEFERRED；HTTP/worker 未实现。本节完整目标不因此改为 IMPLEMENTED。

## 8. 合同交付检查

- [ ] B1 生成 OpenAPI 与 TypeScript，并测试 schema 漂移。
- [ ] 所有对象与事件有合法、非法、额外字段和未知版本样例。
- [ ] 每个接口有权限、空结果、超时、重试、并发与范围限制测试。
- [ ] 首版FilterSpec在Chat、保存分析、驾驶舱、标准BI和人群草案之间一致；订阅一致性留到后续订阅验收，不计首版分母。
- [ ] 运行时 API 密钥、个人信息、原始数据路径和内部日志不出现在浏览器或文档。
- [ ] 旧 Mission 合同继续通过回归；新草案通过实现验收后才改为 IMPLEMENTED。
