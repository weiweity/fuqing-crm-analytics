# 工程基线增量审核记录

初版日期：2026-09-05；D4 与四节收尾：2026-09-06。状态：`PLAN_REVIEW_COMPLETE / D1_D2_D3_D4_CONFIRMED / IMPLEMENTATION_NOT_VERIFIED`。

审核对象：[工程开工基线](./ENGINEERING-BASELINE-2026-09-05.md)。启动时分支 `codex/shine-mage-figma-refinement`，HEAD `de2d785`，存在历史未提交改动。此次不是全仓代码审计，不重开商业主线、DSH 视觉或 StaffDeck 主参考选择。采用 plan-eng-review，四节关键取舍均已逐项确认；本次只关闭这份基线的静态方案审核，不关闭 B0 运行、实现、业务或发布门。

后续整理记录：[总待办](./PLAN-CLOSEOUT-2026-09-05.md)已归并新增数仓/ETL/多人需求。当前续接分支为 `codex/architecture-warehouse-plan-closeout`，HEAD 仍为 `de2d785`；上句分支保留审核启动时点。用户已批准下述 D1–D4；下一步按同一工作包补齐 B0，不重做已确认项，不把决定留存记为实现通过。

## Step 0：范围与复用

- 已有：固定 DSH、原生 UI 插槽插件、同请求去重样板、控制面允许清单和脱敏工具。保留这些接缝，不重建聊天、运行时或 UI 平台。
- 已有 FastAPI/Pydantic 与现有 Mission 业务合同；新任务内核不复用旧 Mission 固定人群作为新查询结果，也不启动旧数据库初始化。
- 增量目标：核定任务内核前置、插件可复现构建、相应 CI、测试和恢复要求。ECharts/布局候选仍在后续小样中验证；不因选库提前铺开整个驾驶舱。
- 复杂度边界：完整首版原本跨多个工作包，不能当一个改动提交。最小任务片段先按合同、状态/适配、接口测试分步；不新增第二业务服务或通用工作流。
- 当时 TODOS 中公网、定时投递、多专家、PostgreSQL 和真实 CRM 保持延后。后续更新：多人权限/容量与共享数据层已转总清单，PostgreSQL 落地仍为候选，其他延后项不变。新 CI 属于当前工程基线，不挪成可以无期限忽略的后续事项。

## D1：最小任务内核前置（已确认）

用户答复：“可以，然后继续下一步”。接受将 E-T1/E-T2/X-T1 的最小任务部分提前到 C-T1/B0；其余工作包顺序不变。此决定替代“B0 完全结束后才开始任何可复用任务内核代码”的绝对顺序，不代表这些工作包整体已启动或完成。

已核对证据：

- `scripts/dsh-b0/gateway.mjs:38–40` 当前使用 Node SQLite 样板表与 `JSON.stringify` 请求 hash；`:104` 为 `scope.inFlight = true;`，`:116` 只更新到 `DSH_ACCEPTED` 或 `DISPATCH_FAILED`；`:117–118` 明确说明尚无完整业务终态观察/恢复。
- `scripts/dsh-b0/gateway-policy.mjs:81`：`if (scope.inFlight !== false) return deny('one-task-already-in-flight');`。结合[先前 B0 实测](./B0-DSH-VALIDATION-2026-09-05.md)，一次完成后第二次提问被拒绝是已知缺口，不是期望行为。置信度 10/10，未在此次启动服务重新复现。
- 固定 DSH `commands.ts:471`：`agent.cancel({ kind: 'user' }, { keepInbox: true })`；`:305` 已有 `hasPromptRequest` 去重，`:316` 将 requestId 写入 source.rpcId。不能把 cancel 回执或 session 最后一个 turn 当成业务 run 的完成证明。[官方 Core 文档](https://deepseek-harness.github.io/deepseek-harness/en/reference/subsystems/core)与本地固定源码相互核验，网站滚动版本不覆盖固定 SHA。
- 上一轮实际复跑现有 75 项插件/网关测试通过；它们不包含正式 FastAPI 任务恢复和完整状态观察，不作为本项通过证据。

已批准的执行边界：

```text
原生 UI → 协议转发 → FastAPI 最小任务合同
                         ├ 同事务：run / key / hash / dispatch intent / 原202
                         ├ 派发 DSH：绑定 session + requestId + attempt
                         ├ 独立观察：关联 inbox / turn / 合成结果证据
                         └ 状态查询 / 取消 / 重启核对

Node：协议与传输适配，不拥有另一份业务状态机
DSH：单一 Agent 运行时，不拥有公司审批或资产事实
```

实现仍遵守原合同：未知结果标 UNKNOWN，不重新生成请求标识盲目补发；取消前后核对对应执行，确认停止后才能释放槽位；结果提交与取消互斥，旧 attempt 不得写入新执行。这里是既有约束的前置，不增加新的状态系统。

任务登记/查询/取消接口使用同一 Pydantic 合同，HTTP 和原生桥接不能各自维护一套业务类型。D2/D3 已核定交付和测试要求，具体 schema 在前置内核实施时与生成类型、测试一起冻结；不把暂未存在的 API 写成可调用。

## D2：同仓插件源码、固定底座与统一构建（已确认）

用户对“同仓插件源码＋固定 DSH 版本＋统一构建与 CI，暂不发布独立 npm 包”的答复为：“可以”。本项是交付方式选择，不是降低测试覆盖率；不新增运行时、软件仓或插件安装平台，也不授权 Git 发布或安装依赖。

已核对证据：

- `[P1] (confidence: 10/10)` `dsh-plugins/analytics-workbench/build.mjs:7` 使用 `../../.context/dsh-b0/upstream` 默认目录，`:10–12` 借用该目录中已安装的 Vite/esbuild；`:27` 的 `path: pathToFileURL(toolsEntry).href, external: true` 将构建机器的绝对路径留在 Host 产物中。当前适合作为本机 B0 小样，不能直接复制 `lib/` 冒充跨机器交付；尚未执行新机器冷构建验证。
- `.github/workflows/lint.yml:9` 已有无路径限制的 `pull_request` 触发；问题不是 PR 完全不运行，而是现有 jobs 没有插件专属构建/测试，main push 的路径清单也不含 `dsh-plugins/**`。旧 CI 通过不证明新插件可交付。
- 固定 DSH 的[官方插件文档](https://github.com/deepseek-ai/deepseek-harness/blob/d347e703908d0406b7a7ef80e3a0e594d86b2215/docs/user/develop/basic/publish.md)已有 bundle/profile 和本地源码包安装方式；[pnpm 官方 frozen-lockfile](https://pnpm.io/cli/install#--frozen-lockfile)支持依赖清单与锁文件不一致时失败。两者来自独立项目，支持复用官方装配与锁定安装的工程判断，不构成本项目验收证据。

已批准的交付边界：

1. **一仓维护插件源码与测试**：沿用 `dsh-plugins/analytics-workbench/`，不提交整份上游克隆、`node_modules`、本机构建产物或私人配置；旧 Vue/npm 不迁移。
2. **继续固定底座**：DSH SHA `d347e703908d0406b7a7ef80e3a0e594d86b2215`、Node 24、pnpm 11.7.0 与依赖锁共同组成构建输入。只声明 SHA 不足以交付，需提供显式获取、校验和准备上游的入口；不能依赖作者预先准备的 `.context`。
3. **复用官方装配**：采用 DSH 原生 bundle/profile 组织业务插件；本地源码安装不要求发布公共 npm 包。具体 manifest、模块解析与 Loader 兼容在实施中验证，保留上游原生 UI 与宿主共享依赖。
4. **本地/CI 一个构建入口**：从明确版本准备上游、严格按锁文件安装、构建插件；产物不得携带作者机器专属路径。目标机器的本地路径由安装/构建入口生成，不当成可分发配置；环境不满足时给出明确失败，不能自动下载浮动最新版。
5. **CI 覆盖完整交付单位**：版本清单/依赖锁、插件源码/测试、适配脚本、共享接口合同和 workflow 改动均覆盖。包括类型检查、现有单元测试、编译后合同测试、实际插件加载及干净环境构建验证；编译成功不等于 TypeScript 检查或真实 Loader 通过。
6. **验证和授权分开**：只用 stub/合成 fixture、隔离状态目录，不需要真实业务库或模型密钥。Mac 本地与 CI 构建/加载证据分别记录，Linux CI 不冒充 macOS sandbox 验收；新增 required check 的远端保护配置待对应授权，不能只加 workflow 就声称受保护。

```text
软件仓：插件源码 + 版本/依赖锁 + 装配配置 + 测试
             |
             v
统一准备/构建入口 ---> 校验固定 DSH ---> 官方 bundle/profile
             |                              |
             +-- 类型/单元/编译合同 ----------+-- 实际加载验证
             |
             +-- 干净目录、无作者配置 ---> CI 与本地分别留证
```

交付验收：另一台机器/干净目录能从声明输入准备并加载同一插件；锁或 SHA 不符、缺依赖、模块加载失败均明确失败；不依赖原工作树绝对路径、全局缓存或真实数据。当前仅批准方案，这些检查均待实现/执行，B0 仍为 `PARTIAL`。

不在本项范围：独立 npm 发布、容器/安装器交付、Hermes 第二运行时、旧 Vue 换栈、生产保护规则修改、公网部署和真实模型测试。分别因当前交付单位不需要或须独立授权而保留延后。

任务映射：沿用 A4、C-T1、X-T2 及 E-T5 的构建/验证责任，不另造一套 autoplan 编号。构建接线由同一集成人顺序修改，避免插件与上游解析脚本同时分叉维护。

## D3：真实落盘与进程级故障测试（已确认）

用户对“隔离小 SQLite 真实落盘＋受控真实子进程，模型/外部服务替身，少量固定 DSH＋stub 端到端，与最小 FastAPI 内核同批交付”的答复为：“可以，开始”；随后要求继续。本项批准测试承载与证据层级，本轮仍为方案审核，不执行新测试或启动服务。

已核对证据：

- `[P1] (confidence: 10/10)` `dsh-plugins/analytics-workbench/test/model.test.mjs:49–55` 的取消用例先 `abort()` 再调用 fixture；只证明预先取消，不能证明运行中停止、退出后回收或重启恢复。已有 B0 原生取消小样另有部分证据，不能混称完全未测试。
- `scripts/dsh-b0/gateway.mjs:99–118` 仍是 Node 受理样板，缺少业务终态观察/恢复；现有权限/fixture/加载测试不覆盖尚待实现的 FastAPI 内核。原测试地图 I2a–I2g 已定义业务约束，缺的是与 D1 前置工作同批交付的故障承载和断言落点。
- [SQLite 官方说明](https://www.sqlite.org/inmemorydb.html)与 [FastAPI 官方依赖替换](https://fastapi.tiangolo.com/advanced/testing-dependencies/)支持使用隔离落盘状态、替换外部服务；外部组件能力不是本项目恢复验收。

已批准的执行边界：

1. 单元/合同验证 schema、状态/版本与边界；集成使用正式仓储、具名落盘 SQLite、独立连接和受控真实进程，不能用内存字典/`:memory:` 或 fake 仓储冒充恢复证据。
2. 覆盖提交前/后崩溃、202/DSH 回执丢失、各阶段取消与终态竞争、重启/孤儿/旧 attempt、SSE 恢复/撤权、连续第二问和持久预算；用明确屏障控制注入，不靠碰巧等待。
3. 少量固定 DSH＋stub＋真实插件/内核端到端核验 run 接线，其他故障先由可控替身确定性覆盖；模型质量与费用测试另设授权门。
4. 最小 app 不初始化旧 CRM，不触碰真实库，不安装守护；只操作测试夹具创建且确认归属的进程。两侧证据包括真实持久记录、协议受理记录和进程退出，不能只信内核自己的状态标签。
5. 用例沿用 I2a–I2g/A1–A2/B1/P2–P3；落点、流程图、用户恢复行为及交付门统一在 [D3 故障测试地图](./ENGINEERING-RUN-TEST-PLAN-2026-09-06.md)。不新增一套工作包编号，不把资产/驾驶舱/ETL 全部前置。

D3 决策已留存；新测试仍为 `PLANNED / NOT_IMPLEMENTED / NOT_RUN`。没有以测试数量或旧通过记录填补缺口，B0 仍 `PARTIAL`。

## D4：独立 B0 资源配置与统一预算执行（已确认）

用户对“采用独立 B0 资源配置，由 FastAPI 统一执行预算与排队约束，旧 BI 保持不变”的答复为：“同意”。这是新链配置归属和执行责任的决定，不是再次扩大并发、调高限额或启动性能测试。

已核对证据：

- `[P1] (confidence: 9/10)` 配置误用风险：`backend/resource_budget.py:48` 为 `return f"{max(1, min(8192, total // (2 * MIB)))}MiB"`；`backend/config.py:140` 为 `_DEFAULT_DUCKDB_MEMORY_LIMIT = default_memory_limit()`，`:134` 的默认数据路径仍为归档 `fuqing_crm.duckdb`。这套旧 BI 默认值不等于新 B0 的 512MiB 合成测试预算。新内核尚未实现，本项是已核对的默认值差异及未来耦合风险，不是实测 OOM，也不表示当前实际使用 8GiB。
- `backend/services/dual_conn.py:31` 的 `READ_MEMORY_LIMIT = os.environ.get("FQ_READ_MEMORY_LIMIT", "").strip() or DUCKDB_MEMORY_LIMIT` 证明既有连接会回退旧配置；不能因“复用后端”顺带复用真实路径或整套连接初始化。
- [DuckDB 官方内存说明](https://duckdb.org/docs/current/guides/performance/oom)指出部分分配不受 buffer manager 限额覆盖；[Python Future.cancel 官方说明](https://docs.python.org/3.14/library/concurrent.futures.html#concurrent.futures.Future.cancel)说明已运行调用不能靠该方法取消。两项独立来源支持分别验证实际内存和执行退出；不要求本项目采用 Future，也不替代本地验证。

已批准的执行边界：

1. **一份新 B0 配置**：由最小 FastAPI app 显式装配、校验并记录生效版本；插件、Node 和 worker 不各自推导一份预算。可复用无数据库副作用的硬件探测/校验函数，不调用旧默认预算作为 B0 fallback，不导入旧数据路径/连接/lifespan；旧 BI 配置不改。
2. **保留既有首轮数值**：计算 active worker=1、queued<=8、同调用者在途<=3；单查询<=30秒且不超过剩余 run 时限；run 从受理起含排队、模型、查询和最终化共120秒，最多8个工具步。DuckDB memory_limit=512MiB、threads=2、独立临时目录上限512MiB；worker RSS 观测阈值1GiB。它们是待验证起点，不是容量/SLA承诺，也不意味着允许每个 HTTP 进程各起一个 worker。
3. **单一调度权威**：新 B0 profile 只运行一个拥有派发权的 FastAPI 调度器；额度覆盖该 B0 的所有调用者、会话与计算 worker，不按用户/窗口/卡片复制配额。受理、排队、派发和工具调用前按原合同检查/保留预算；Node/DSH 不能绕过。同机旧 BI、ETL 和其他程序不受此配置管理，不宣称已限制整机资源；多人/共机容量仍走 V1/V2。
4. **持久预算不因重试重启复位**：run 固定原 deadline、计数/实际尝试及所用资源配置版本；进程重启、compaction、传输重连不能获得新的120秒或8步。到时先停止后续派发并请求停止活动执行；真实退出确认可能晚于截止，未确认时按合同保留 CANCELLING/UNKNOWN，不能先放槽再接新重计算。
5. **资源与错误分层**：DuckDB 限额、进程 RSS、临时盘、持久事件/证据分别记录。RSS 是观测阈值而非瞬时内核硬限制；超限终止只针对归属已确认的测试执行。拒绝未知/非法 profile；基础状态/事件必需限额未配置时拒绝新 run，不回退旧 BI，也不为腾空间删历史资产。前置内核运行前固化所需配置，B1 的驾驶舱/资产上限仍在 B1 冻结。
6. **复用 D3 做验证**：补配置缺失/非法、旧环境变量污染、额度边界、并发受理、重启预算、超时未退出、RSS/临时盘超限和第二问的断言。使用隔离小库、受控进程和 stub；未知计费按既有保守预留，真实模型费用 cap 仍须另批。

```text
独立 B0 profile → FastAPI 校验/单一调度权威 → 持久 run/预算
                              |                  |
                              +-- 排队/派发前检查-+
                              |                  |
                              v                  v
                       受控只读计算 worker    deadline/步骤/尝试
                              |
                超限/取消 → 停止请求 → 确认退出 → 回收额度

旧 BI 配置/连接与真实路径：不作为 fallback；本轮不改动
```

性能四个检查面已逐项核对：

| 检查面 | 已有计划的落点 / 本轮判断 |
|---|---|
| N+1 与重复读取 | 原测试 P1b 已要求日常 GET 不重算、不因每张卡触发模型/SQL；本地小样不是完整资产实现。保留调用次数断言，未测前不声称消除了所有 N+1 |
| 内存与并发 | D4 将旧 BI 默认值与 B0 分开，并把并发/截止交给同一内核；实际 CPU/RSS/spill 与状态请求延迟仍须记录 |
| 缓存 | I2a/A1 与 V3 已约定完整条件、权限、指标/数据版本及 as_of；缓存命中仍重新鉴权，只复用兼容成功结果，不共享另一 run 的在途执行；不加 Redis |
| 慢路径与复杂度 | W3/W4 已承担真增量、共享客户事实和减少全量扫描；千万行冷/热与多人基准归 V2，不将语言重写或真实 ETL 混入最小 B0 |

除已确认 D4 外，本节没有新增需要改变范围的取舍。上述“已有计划覆盖”不表示新实现或性能测试通过。

## What already exists：复用与不复用

- 固定 DSH、原生插槽、HTTP/WS 允许清单、脱敏和 stub：复用；Node 业务账本只是过渡样板，不长期保留第二权威。
- FastAPI/Pydantic、pytest、Node/Playwright、已有类型生成工具：复用；新 router 用最小 app，不借旧 CRM 初始化“顺便跑通”。
- 旧 BI 资源纯函数与既有分析/缓存经验：按边界复用；真实库默认路径、全应用配置和旧固定结果不进入 B0。
- D1–D4 与原 11 包、W/V 清单一一交叉引用；不建立新平台或另一份产品待办主源。

## NOT in scope

- B1–B4 全量产品实现、驾驶舱/图表兼容小样和完整品牌/BI 验收：保留原关卡，不因任务内核前置而整体提前。
- 真实模型、费用评测、真实业务数据/ETL、多人数据库迁移：各有独立预算、正确性和授权门；B0 合成证据不替代。
- 独立 npm 发布、安装器、Redis/Celery、第二 Agent 运行时：当前交付单位不需要，不为测试增加平台。
- commit/push/PR/merge、远端 required checks、公网部署、消息、目录迁移或清理：本轮只审查计划，无相应新授权。

## Implementation Tasks：映射原工作包

下列是 4 个增量检查点，不是新增 4 个产品工作包；每项源于 D1–D4。路径含拟新增项，命令/验收均为后续执行要求。本轮不执行。估时为未验证的拆分初估，包含重叠工作，不能相加为日期承诺。

- [ ] **D1 / E-T1＋E-T2＋X-T1 最小片段（P1，human: 2–4天 / AI协作: 6–12小时）**：实现唯一任务合同与持久受理/派发/查询/取消/重启恢复。
  - 来源：D1 的 Node inFlight/缺少业务终态观察。拟改 `backend/contracts/analytics.py`、`backend/routers/analytics.py`、`backend/services/analytics/{jobs,runtime}.py`，接线 `scripts/dsh-b0/gateway.mjs`。
  - 验证：拟新增合同/任务测试；先登记后派发、同 key 原202、UNKNOWN、CAS/fencing、原生连续第二问。内核中嵌入受理/派发与取消状态图，测试旁保留故障屏障图。
- [ ] **D2 / A4＋C-T1＋X-T2（P1，human: 1–2天 / AI协作: 3–6小时）**：交付同仓、固定版本、官方装配和本地/CI 同一构建入口。
  - 来源：D2 的本机工具链和产物绝对路径依赖。拟改 `dsh-plugins/analytics-workbench/`、`scripts/dsh-b0/` 及 `.github/workflows/` 的版本/依赖锁、准备、构建和检查接线。
  - 验证：严格锁文件、类型/单元/编译合同、真实 Loader、无作者配置的干净构建；Mac 与 CI 分列，不自动修改远端分支保护。
- [ ] **D3 / E-T5＋X-T1 前置测试（P1，human: 2–3天 / AI协作: 5–10小时）**：与内核同步交付[故障地图](./ENGINEERING-RUN-TEST-PLAN-2026-09-06.md)的落盘/进程证据。
  - 来源：D3 的预先取消测试不能证明全链恢复。拟改 `backend/tests/test_analytics_{contracts,jobs,access}.py`、插件现有测试及 `scripts/dsh-b0/{gateway-smoke,native-smoke}.mjs`。
  - 验证：13 组故障场景的真实状态、请求次数与退出记录；每层 PASS/FAIL/NOT_RUN 分开，全部必要新分支与实现同批，不延后测试。
- [ ] **D4 / A3＋E-T2＋E-T5 B0 子集（P1，human: 1–2天 / AI协作: 3–6小时）**：装配独立资源配置和单一调度预算，保持旧 BI 不变。
  - 来源：D4 的旧默认值/连接 fallback 风险。拟新增 `backend/services/analytics/resource_profile.py`，接入新 jobs/runtime，补 `backend/tests/test_analytics_run_budget.py`；不把现有旧 BI 资源测试改名冒充新链覆盖。
  - 验证：原测试 P1/P2/P3＋D3 故障注入，旧配置不影响 B0，缺失配置拒绝；超时/取消后确认退出、预算跨重启不复位、同调用者/全局额度边界均覆盖。

模块依赖与协作边界：

| 线 | 模块 | 顺序/依赖 |
|---|---|---|
| A：内核 | `backend/contracts/`、`backend/routers/`、`backend/services/analytics/`、`backend/tests/` | 合同 → D1＋D4 → D3 落盘/进程验证；测试随实现编写 |
| B：装配 | `dsh-plugins/analytics-workbench/`、`scripts/dsh-b0/`、`.github/workflows/` | D2 的版本准备可独立进行；业务桥接和原生端到端必须等待 A 的同源合同 |
| 汇合 | `scripts/dsh-b0/`、插件测试、`docs/hackathon/` | A/B 接线共同触及适配目录，由同一集成人顺序收敛，再运行原生证据门 |

仅版本准备部分具备并行条件；本次不创建 agent/worktree，默认单集成人顺序执行，避免两个任务同时改桥接。原 W1–W5 数据线不并入本表。

## 审核完成摘要与限制

- Step 0：增量范围已确认；未取消原首版能力，只有最小内核前置。
- Architecture / Code Quality / Test / Performance：各 1 项关键发现，共 4 项，D1–D4 均获用户批准并纳入计划。
- Test：已产出执行/用户流程图、13 组故障地图与 QA 入口；这是 1 项证据承载缺口的展开，不虚报源码覆盖率或 13 项已通过测试。
- Failure modes：地图中的处理/提示/测试要求已明确；本次范围内无仍未规定处理且静默失败的计划分支。实现层恢复/取消/权限门全部待验证，不能把计划层 critical gaps=0 解读成程序无缺陷。
- NOT in scope / What already exists / Implementation Tasks：已写明；任务记录保留原工作包映射。新增延后 TODO 为 0，现有 TODOS/W/V 已覆盖，不重复制造待办。
- Outside voice：按 Codex 宿主规则跳过嵌套 Codex；未调用其他模型或子 agent，无跨模型共识声明，不把跳过伪装为独立复核通过。
- Parallelization：2 个可划分的模块线，只有装配准备具备并行条件，默认顺序实施并由单集成人汇合。
- Lake Score：不对不同类型的方案伪造覆盖分数；4/4 决策已确认，未批准删减测试或业务验收的捷径。
- 近期 Git 历史 `de2d785` 为 Sprint 206 pre-landing 文档，前序包含视觉/旧回归记录；本轮不复用它们为新任务内核的通过证据，不修改其代码。
- 可复用的配置误用风险与持久化测试经验已留在 D3/D4；本轮无额外需要写入长期记忆的新发现，不做记忆/全局设置更新。

状态为 `DONE_WITH_CONCERNS`：四节静态方案审核完成，构建、内核、故障测试、资源实测及其余 B0 验收待实施。只读来源和文档检查不是运行证据；后续实施仍按实际授权推进。

留存适配：本次按方案文件 hash 记录评审和 4 项机器可读检查点；不运行会通过临时 index 将全部工作树写入 Git object 的指纹脚本，也不启动同步/遥测。记录只绑定本基线，不认证其他未提交代码；未执行 `gstack-review-log/read` 的整树脚本路径，不伪报该工具链全流程通过。

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|---|---|---|---|---|---|
| Eng 增量方案审核 | plan-eng-review | 当前基线的架构、交付、测试与性能 | 本次 1 轮，四节完成 | CLEAR (PLAN ONLY) | 4 项关键发现，D1–D4 均已确认并落入计划；实现/运行未验收 |
| Outside Voice | Codex 宿主检查 | 避免嵌套同宿主复核 | 0 | SKIPPED_UNDER_CODEX | 无独立模型意见，不声明跨模型共识 |
| B0 / 应用 / 发布验收 | 原验收关卡 | 与方案审查分开 | 本次 0 | PARTIAL / NOT_RUN | 不继承本表 PLAN CLEAR，原缺口继续有效 |

VERDICT: 本基线四节静态方案审核完成（DONE_WITH_CONCERNS）；D1–D4 无待用户决定项。可按已有授权推进前置 B0 实施，不代表应用测试、独立复核、B0 或发布通过。多人状态库/模型费用/公开交付保持其独立关卡，不由本表替代。

NO UNRESOLVED DECISIONS
