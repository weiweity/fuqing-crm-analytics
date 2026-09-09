# Grok 并行开发任务包

日期：2026-09-09。状态：`BATCH1_DISPATCHED / C0_PENDING`。这是[总计划§12](../PLAN-CLOSEOUT-2026-09-05.md)的任务拆分，不新增第二套产品范围。G0 已建第一批工作树并派发 A1/A4/A2（只读口径）/A9（反例设计）；C0 未冻结，A3/A5/A6/A7/A8 未派发。登记见 [g0/REGISTRY.md](./g0/REGISTRY.md)。任务清单见 [tasks.json](./tasks.json)。

## 推荐组织

**Grok作为总控/集成人，8个开发角色A1–A8，1个独立验收角色A9。默认最多4个子Agent同时运行。** 9个角色可复用会话分批调度，不要求9个进程同时常驻；CPU/内存吃紧时先减少重型测试，不取消功能。若宿主没有独立工作树能力，则只能并发只读分析，代码改动按写入范围串行，不让多个Agent覆盖同一文件。

| Agent | 任务卡 | 负责交付 | 主要依赖 |
|---|---|---|---|
| A1 | [共享合同](./A1.md) | 统一条件/结果/看板/人群/错误、能力目录、生成类型 | 首先冻结C0；持续处理变更 |
| A2 | [业务计算](./A2.md) | 日期、GSV、新老、小样、RFM、共享特征 | C0；可提前只读核验/手算夹具 |
| A3 | [API与资源治理](./A3.md) | 参数暴露、认证错误、连接准入、完整MCP/HTTP、文档 | C0；真实计算接A2 |
| A4 | [DSH与品牌壳](./A4.md) | 原生能力保留、启动认证、统一主题和比赛品牌 | 可立即开始；给A6导出主题接口 |
| A5 | [资产与看板后端](./A5.md) | 批量创建、版本/预览/撤销/幂等与持久编辑目标 | C0 |
| A6 | [看板与行动前端](./A6.md) | 拖拽缩放/聊天编辑UI、候选和草稿UI | C0+A4导出；先fixture后A5/A8 |
| A7 | [诊断Skill与工具](./A7.md) | 自由问数诊断链、工具调用、受控AI patch、eval | C0；真接线需A2/A3/A5/A8 |
| A8 | [候选与行动后端](./A8.md) | 固定去年cohort、本期回购、候选与草稿服务 | C0；先手算夹具后A2特征 |
| A9 | [独立验收](./A9.md) | 17组跨层验收、故障、模型、原生和容量证据 | 提前设计反例，集成后实测 |

## 批次与依赖

```text
G0：Grok记录基线/未提交规划快照/工作树/路径owner/资源登记
  ↓
第一批（最多4个）：A1合同 + A4基座/品牌 + A2只读口径核验 + A9独立反例
  ↓ C0字段/fixture/支持矩阵冻结；A4主题导出明确
第二批（最多4个）：A2计算 + A3接口治理 + A5看板后端 + A8人群后端
  ↓ 有槽位即调入（不必等第二批全部结束）
第三批：A4品牌完善 + A6交互UI + A7工具/Skill + A9局部验收
  ↓ Grok先集成合同/公共入口，再接模块
集成全链：A2→A3→A7；A5↔A6；A8↔A6/A7；A4包住原生功能与业务UI
  ↓
A9按同一集成快照验收 → owner定点返修 → 仅重验影响范围
```

A6/A7可以在C0 fixture上先做实现，不必等待真实接口全部完成；但必须通过实际服务接线才能标闭环完成。A8可以先用固定10人金标准验证候选，不必等聊天UI完成。A4原生全量未验不阻塞A2计算开发，仍阻断“全部功能已保留通过”的声明。

关键路径：**C0 → A2/A3可信数据 → A7真实问数 → A5/A6成板编辑 + A8候选草稿 → A9整链**。整个仓库ETL改型、真实营销发送和公网不隐含进入并发队列。

## G0：总控开工动作

1. 核实当前仓库cwd/分支/HEAD/dirty状态，不沿用任务卡里的历史SHA当新事实。当前规划含未提交修改，**新worktree只取HEAD会漏掉最新方案**。先保存精确规划文件副本/hash，再分发到子工作树；不自动commit/stash/reset。当前已有4个无关未跟踪文件不纳入本次交付。
2. 规划快照只白名单包含：DESIGN.md、docs/hackathon/PLAN-CLOSEOUT-2026-09-05.md、TODOS.md、DSH-UI-INTERACTION-SPEC.md、README.md、AUTOPLAN-COMPETITION-REVIEW-2026-09-09.md、COMPETITION-TEST-PLAN-2026-09-09.md及本任务包。上述docs相对路径均以docs/hackathon为前缀。不要复制整个dirty工作区、.context、上游依赖、真实DuckDB或数据目录。
3. 为每个正在实施的轨分配独立工作树和分支、实际绝对cwd；记录分配表。避免自动LFS拉取真实大资产；不复制node_modules或固定上游树。按既有工具链允许方式只读复用固定上游，业务状态/运行目录各轨隔离。
4. tasks.json中的worktree/base_sha/contract_hash是待总控填的真实值，**填完再派发**，不能让子Agent自行猜目录。补充规划快照hash和可写文件清单。不开第二个Grok总控，不允许子Agent自行再分派。
5. 建资源表：轨、端口、runtime目录、PID owner、测试预算。用户现有4327演示及其他进程先核实归属，不停止/复用；临时端口先检查后分配。最多一个重型backend/B0全套或容量测试同时运行，轻量独立单测可并行；共享固定上游仅只读，不并发安装/重建同一产物。

## C0：合同冻结门（A1产出，Grok验收）

这是一次小范围同步点，不是等待所有业务开发完成。

| 合同族（概念名，真实代码名由A1映射） | 必须明确 |
|---|---|
| Condition | GSV；两段日期/对比方式/时区/cutoff/as_of；销售与历史scope；派样排除模式；版本/可支持范围 |
| ResultRef | 完整性/分页、实际执行条件、数据/规则版本、来源时态、授权scope；空/不足/不支持/失败不同 |
| BoardSpec/Patch | 沿现有analytics_cockpit演进；稳定ID、base_version、允许操作/图表、持久目标、批次/逐板键与指纹 |
| Audience/Action | 固定入组快照/观察窗、AND/OR去重、三种未回购、会员未知、草稿过期/复核、无自动发送 |
| Error/Capabilities | code/param/retryable/retry_after/request_id/doc_ref；actor过滤能力目录，后端仍鉴权 |
| Frontend ports | A4主题/壳插槽、A6挂载/dispose、A7选中编辑事件、A5/A8 transport签名 |

每族至少成功、空结果、参数错误和权限失败fixture；编辑另有409与部分成功。manifest包含文件清单、hash、版本和接口支持状态；Python/TS生成类型一致。**模型推理的自由度来自组合已核验能力，不来自绕过合同。**

业务偏好尚未确认的推荐默认不变成隐藏假设：当前推荐“剔除小样只过滤本期销售、历史重算显式选择”和“一组认可分析一板多块、可选批量分板”。先实现显式模式/选择能力；默认值集中可配置并保留待确认标记，不让每轨各决定一个默认。

C0后改字段走CR：提出者→A1标影响消费者/兼容/fixture→Grok决定版本→A1更新→受影响轨接入同一hash。只暂停依赖该字段的工作，其他任务继续；不静默改schema让其他轨猜。

## 共享文件只允许一个写入者

| 文件/区域 | 唯一owner | 其他轨如何协作 |
|---|---|---|
| backend/contracts、OpenAPI、generated类型、离线合同生成器 | A1 | 提交CR与负例，禁止手改生成文件 |
| 旧CRM人群/RFM/共享特征计算 | A2 | A3/A8通过函数接口调用，禁止复制计算 |
| 旧路由、连接准入、旧MCP | A3 | A2给签名，A1给合同；禁止掺入其他轨业务实现 |
| scripts/dsh-dev、全局styles与品牌壳 | A4 | A6用主题exports和局部样式 |
| 分析资产/看板service | A5 | A6/A7调用，禁止自建版本账本 |
| 看板/候选/行动UI | A6 | A4提供主题；A7提供工具接口，均不直接改UI |
| 新诊断编排/业务Skill/AI工具模块 | A7 | 由总控注册进原生入口 |
| 候选family/候选草稿新service | A8 | A2供特征，A5供结果引用，A6供展示 |
| 独立验收测试和报告 | A9 | 产品修复返回owner，不改测试使之通过 |
| backend/main.py、backend/analytics*_app.py，analytics公共jobs/runtime/access/worker/catalog/queries/query_codecs及注册入口 | **Grok** | 各轨交精确接线diff；总控串行组装，保留现有单一任务账本 |
| 插件src/index.ts、client/index.tsx、bridge/runtime公共入口、asset-http公共transport、pack-skills与skill锁 | **Grok** | 消费方交exports/事件/路由说明，总控统一装配 |
| package.json、依赖锁、toolchain、CI/共享runner/conftest、当前状态/主计划文档 | **Grok** | 子轨提交依赖/验证需求；只在隔离候选固定版本后加入 |

任务卡列的是允许写入的最大边界；同目录内共享文件以本表为准。遇到未归属文件先分配owner再写。每轨自己的测试文件命名含competition与轨模块；共享fixture由A1提供合同样例，A9独立手算预期，不能两个来源互相复制而声称独立验证。

## 总控集成出口与验收顺序

- **G1 合同集成**：A1生成产物及manifest先进入集成工作树；A2/A3确认真实旧服务可表达范围，客户端fixture通过。缺口回C0，不假注册SUPPORTED。
- **G2 服务集成**：Grok接A2/A3入口、任务预算/身份/发布权限；接A5资产、A8候选草稿。避免同时改同一jobs/worker/runtime。T01–T08、T14先验，权限不是拖到最后才做。
- **G3 原生产品集成**：装配A4/A6/A7；Skill打包/类型/构建同源；运行诊断→认可→批量成板→局部编辑→候选→草稿。旧标准preset、会话、工具、文件、压缩、权限与设置保持可达并分别验收。
- **G4 独立验收**：A9在固定集成快照跑相应pipeline、HTTP、编译后DOM、浏览器、真实模型与容量；各层独立状态。其他Agent不能边改集成树边让A9记录验收；返修后记录新快照并重验受影响层。
- **G5 交接**：Grok交实际完成表、未完成/阻断、风险、变更文件、contract hash、验证产物和运行实例。合成演示/真实模型/目标容量/业务UAT/公开URL分列。未授权不自动commit/push/PR/merge/部署；交可审查的本地补丁即可。

补丁交接必须有base SHA和源文件摘要；未提交开发可用白名单文本patch与明确新增文件清单，不要求子轨commit。总控应用前核验基线/路径，不用全目录覆盖；冲突时由唯一owner解释和重做。后续如用户授权Git发布，再走仓库对应检查点，不从旧Goal继承自动发布流程。

## 所有Agent统一交付格式

```json
{
  "task_id": "A2",
  "status": "COMPLETE|PARTIAL|BLOCKED",
  "worktree": "实际绝对路径",
  "base_sha": "实际基线",
  "plan_snapshot_hash": "实际规划快照hash",
  "contract_hash": "实际C0版本hash",
  "changed_files": [],
  "patch_artifacts": [],
  "validation": [{"command": "实际命令", "exit_code": 0, "evidence": "实际日志路径"}],
  "integration_requests": [],
  "not_run": [],
  "risks": [],
  "owned_processes": []
}
```

这是格式示例，不能照抄COMPLETE/exit_code=0；填写实际结果。BLOCKED必须指出依赖哪个接口/owner及仍可独立推进的工作。计划、任务卡不作为已执行证据。

## 给 Grok 的总控提示词（可直接复制）

```text
你是本项目的并行开发总控和唯一集成人。请执行以下任务包，按依赖调度多个Agent，不要让他们在同一目录并发改代码：
/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/fuqing-crm-analytics/docs/hackathon/parallel-competition-2026-09-09/README.md

先读仓库AGENTS.md、最新总计划§12、本任务包及tasks.json。当前规划有未提交改动，新worktree不能只取HEAD丢掉这些文档；按G0白名单生成规划快照并分发，保留用户原有改动。

由你负责G0–G5、公共注册/任务账本/依赖锁/文档状态；A1–A8负责各自开发，A9独立验收。默认最多4个子Agent同时工作，最多1个重型测试/容量任务同时运行。每轨独立worktree，派发前填实绝对cwd、base SHA、规划hash与C0 hash；不允许子Agent再次分派。

第一批启动A1、A4、A2只读口径核验、A9反例设计。C0冻结后按依赖推进A2/A3/A5/A8；有槽位就调入A6/A7，允许使用冻结fixture开发，不允许自行发明字段。业务范围保持完整：自由分析、认可后批量成板、拖拽缩放与AI局部编辑、自有比赛UI、召回候选与行动草稿；保留DSH所有原有功能。真实数据/外部营销/公网另行处理。

每个Agent读取自己的A1.md至A9.md任务卡并按统一格式交付。公共文件和合同仅唯一owner写入，其他轨提交CR/接线请求；你串行集成，A9固定快照验收。复用现有计算/资产/工具链，不新增第二Agent运行时或平行数据权威。

不复制真实DuckDB/原始数据/依赖树，不读取输出凭据，不关闭认证，不停用户现有演示。不得继承历史自动commit/push/merge/部署流程；本次先交本地实现、必要验证和可审查补丁。遇到确需核心上游补丁或缺真实数据/模型条件，报告具体边界，继续不依赖它的任务，未验不得称通过。
```
