# 工程开工基线：视觉、工作流、架构与技术栈

初版日期：2026-09-05；D4 与审核收尾：2026-09-06。状态：`UI_REFERENCE_CONFIRMED / STACK_RECOMMENDED / PLAN_REVIEW_COMPLETE / B0_PARTIAL`。

初版只留存方案和架构图。用户确认：**StaffDeck 为数字员工主参考，融入 DSH 视觉**；整体优先保留成熟设计，后续再创新。技术选型中的新增组件是工程推荐，不冒充安装、集成或性能验收。

收口更新：跨计划执行顺序、最新 10 人/5 分析/约千万行/T+1/多品牌店铺需求及数仓/ETL 待办见[总清单](./PLAN-CLOSEOUT-2026-09-05.md)。下表与现图保留本地 B0 profile；多人 PostgreSQL 应用状态与 ETL 发布架构仍需核定和补图，不将其写成已部署。本基线四节静态审核已完成，D1–D4 均已确认；尚未实现/运行验收，不代表 B0 或完整首版通过。

增量工程审核 D1 已确认：**将最小 FastAPI 任务内核前置到 B0**，覆盖任务登记、派发、状态查询、取消与重启恢复；Node 网关只保留协议转发。此为复用既定后端的顺序调整，不引入新平台。其余正式指标、资产、驾驶舱和营销功能仍待原关卡；不授权付费模型、真实数据、公网或 Git 发布。审核进度见[增量记录](./ENGINEERING-INCREMENTAL-REVIEW-2026-09-05.md)。

## 1. UI/UX：一个视觉体系，两个参考层次

| 区域 | 采用方式 | 不做什么 |
|---|---|---|
| 工作台、聊天、输入、导航、详情 | 保留 DSH 原生 UI，通过受支持的插件插槽补业务 | 不重造 Chat，不全局覆盖上游 CSS |
| 数字员工 | StaffDeck 的“员工 → 任务 → 成果”组织方式，使用 DSH 字体、间距、色彩和交互组件 | 不复制整个平台，不引入 StaffDeck 或 Hermes 第二运行时 |
| 分析卡与驾驶舱 | 同一业务插件、同一图表规范；图表颜色/背景/提示框跟随 DSH 主题 | 不拼贴多个 UI 套件，不让模型执行任意组件代码 |
| 现有固定 BI | 保留 Vue 页面与既有图表；新适配入口携带已验证条件 | 不为视觉统一先重写旧 BI，不声称旧 BI 已接受新条件 |

Hermes 仅为辅助参考。第一版仍是一个增长分析师、三个查询族、一个可组合的私人驾驶舱。员工不是“一个接口一个进程”。界面可以体现任务与成果，不新增员工市场、专家组队或工作流编辑器。

统一分两层：**新工作台视觉统一到 DSH；跨新旧系统统一指标口径、图表语义、品牌和筛选条件**。旧 Vue 全面换肤不列为开工前置。参考项目后续须固定设计参考版本并做页面对照；本次不是 StaffDeck 像素级复刻验收。

## 2. 技术栈与复用边界

| 层 | 推荐选择 | 当前证据与待办 |
|---|---|---|
| AI 主底座 | DeepSeek Harness，固定上游 SHA `d347e703908d0406b7a7ef80e3a0e594d86b2215` | B0 部分验证；保留单一 Agent 运行时，业务取消/恢复门未闭合 |
| 新前端 | DSH 宿主 React 18 / TypeScript；Node 24，pnpm 11.7.0 | 复用宿主 React 和原生组件；不另装一套 React 或 Vue 壳 |
| 数字员工 | DSH preset + 受控 Skills/tools + 本业务插件 | StaffDeck 提供产品组织参考，不是额外技术底座 |
| 图表 | ECharts，优先复用旧项目已锁定的 6.1.0 | 引擎复用；DSH 的 React 生命周期、按需加载、resize/dispose、主题与资源回收尚需验证 |
| 驾驶舱布局 | React-Grid-Layout v2 为首选候选 | 尚未安装；需验证 React 18、DSH 插件打包/加载、响应式、拖拽与图表 resize；精确版本小样通过后锁定 |
| 业务后端 | 现有 Python 3.14 / FastAPI / Pydantic 2 | 唯一业务权威；沿用依赖锁与环境，不在本轮升级 |
| 接口 | FastAPI OpenAPI → 生成 TypeScript 类型 | 复用现有 openapi-typescript 工具链；业务状态、错误码、幂等和版本协议仍需实现验证 |
| 应用状态 | 本地 SQLite，由 FastAPI 独占业务访问入口 | 保存任务、分析资产、驾驶舱配置、审批；不是分析数仓，也不是多机直接共享数据库文件 |
| 分析数据 | 合成 DuckDB 只读 + manifest；受限进程 worker | 不动归档真库；重查询不在 HTTP 请求进程内执行，不用模型生成任意 SQL |
| 旧 BI | Vue 3 / Naive UI / ECharts，现有 npm 锁文件 | 原样保留；新 DSH pnpm 与旧 npm 边界分开，不统一迁移包管理器 |
| 验证 | pytest + Node/Vitest + Playwright | 复用现有工具，补新业务合同、金标准、隔离和原生 UI 验证，不以旧页面通过代替 |

布局候选的通过标准：保存/恢复版本化布局；只改目标 card_id；失败不覆盖原配置；预览/保存/撤销；只读查看不调用模型；拖拽有键盘按钮等价操作。不能把库支持拖拽当作已满足键盘可访问性。若候选不适配，先用 CSS Grid + 显式移动/尺寸控制完成已确认组合能力；换库不改变业务合同，明显改变交互时回到用户确认。

后续多人共享部署可将**应用状态**迁至 PostgreSQL；这不是把 DuckDB 换名为 PostgreSQL，也不保证 RFM 自动变快。当前不新增 Redis/Celery、通用工作流引擎或第二 Agent 编排框架。MCP 是可选工具协议；本地 typed tools 足够时不为形式再套一层。模型供应商与成本门独立，stub 通过不等于真实模型通过。

## 3. 目标架构与边界

架构图是**目标状态，不是已部署拓扑**。业务状态与权限留在 FastAPI，DSH 负责会话和 Agent 执行，插件负责展示；可替换底座不等于重复建设业务后端。

![目标架构，尚未完整实现](../../diagrams/analytics-target-architecture.png)

源文件：[Mermaid](../../diagrams/analytics-target-architecture.mmd)；可编辑稿：[Excalidraw](../../diagrams/analytics-target-architecture.excalidraw)；高清：[SVG](../../diagrams/analytics-target-architecture.svg) / [PNG](../../diagrams/analytics-target-architecture.png)。维护方式见[架构图说明](../../diagrams/README.md)。

关键约束：

- 新提问先由 FastAPI 持久记录 run、条件 hash、dispatch intent 和原始 202 响应，再派发 DSH。`accepted` 不等于分析成功；取消、重试和恢复绑定业务 run。
- DSH 仅通过白名单类型化工具调用业务 API。权限、查询预算、数据范围、审计、导出审批由后端执行，不依赖提示词自律。
- 确定性 worker 读取合成分析库；同一业务任务管理器约束并发、超时、取消与结果回收。图中 worker 不是新增自主 Agent。
- 已保存分析与驾驶舱直接读取授权资产，不依赖模型在线。显式数据刷新走确定性任务；历史/审批快照固定，不能悄悄替换。
- AI 局部编辑产生可校验配置差异，经过预览/版本校验再保存。允许的图表为指标、表格、柱线图、证据文本，不执行模型 HTML/JS/任意 ECharts options。
- 同条件 BI 跳转需独立适配、服务端校验和往返测试。营销只到人类审批后的合成 `DRAFT_EXPORT`，不自动短信或真实 CRM 写入。

## 4. Git 与 gstack 开发流程

### Git：一仓协作，小步评审

当前配置的远端是 `git@github.com:weiweity/fuqing-crm-analytics.git`。本次只读取配置，**没有核验远端 PR、分支保护或 required checks 当前状态**。

建立基线时的 `codex/shine-mage-figma-refinement` 工作树包含旧 Vue/登录/Mission 改动、方案和 B0 小样，不能直接整体提交。最新续接分支见[总清单 Git 记录](./PLAN-CLOSEOUT-2026-09-05.md)；沿当前进度建分支不等于这些改动已提交。下一次工程开工先按 diff 核对归属与依赖，再确定分支/PR 边界。保留全部未提交内容，不自动 stash/reset、搬迁或清理分支。

建议提交单元为：方案与基线 → B0 底座适配 → 合同与金标准 → 纵向业务闭环；共享文件指定负责人，依赖关系写入 PR。新任务在获准时从已核验的主分支创建短分支/隔离 worktree，不把既有未提交改动丢掉。代码和合成 fixture 进软件仓，真实数据、密钥、模型凭据不进仓。

**检查缺口**：现有 `lint.yml` 的 PR 事件会触发，但检查内容主要覆盖旧后端/Vue，main push 路径过滤也没有覆盖 DSH 插件；`e2e-smoke.yml` 是定时/手动可选的旧登录冒烟，不是新工作台 PR 必过门。后续须补 DSH 插件、合同及合成纵向链 CI，并单独核验远端分支保护，不能用旧 CI 绿灯代替。

commit、push、创建 PR、merge、部署分别遵守已有明确授权范围。gstack 自动化不能绕过这些边界，本次不执行任何这些动作。

### D2：插件交付单位（已确认，待实施）

用户确认 **同仓插件源码＋固定 DSH 版本＋统一构建与 CI，暂不发布独立 npm 包**。沿用现有 DSH SHA / Node / pnpm 版本及上游依赖锁，复用官方 bundle/profile 装配，不提交整份上游克隆，不新增安装平台；旧 Vue/npm 独立保留。

统一入口须显式准备并校验上游，按锁文件安装、构建、加载插件；不能依赖预先存在的本机 `.context` 工具链，也不能分发写死作者路径的 `lib/`。CI 覆盖插件、适配脚本、版本/依赖锁、共享合同及 workflow，包含类型检查、单元/编译合同、真实 Loader 和干净环境验证。验证使用 stub/合成数据，不含真实模型费用；Mac 与 CI 平台证据分列，不跨平台推定 sandbox 通过。

完整依据、验收条件及延后范围见[增量审核 D2](./ENGINEERING-INCREMENTAL-REVIEW-2026-09-05.md#d2同仓插件源码固定底座与统一构建已确认)。当前尚未改构建/CI、安装依赖或验证新机器；该决定不改变 B0 PARTIAL，也不授权修改远端 required checks。

### D3：故障测试承载（已确认，待实施）

最小 FastAPI 任务内核与测试同批交付：单元/合同＋真实落盘小 SQLite/独立连接/受控子进程集成＋少量固定 DSH 与 stub 原生端到端。外部服务可替换，正式仓储、事务、授权和取消链不能全被 mock；不导入旧 CRM lifespan 或访问真实库。

提交前后崩溃、丢响应、取消竞争、未知执行、旧 attempt、重连与第二问均须有明确断言和独立证据。流程、故障夹具、拟测试路径与交付门见 [D3 测试地图](./ENGINEERING-RUN-TEST-PLAN-2026-09-06.md)。新增测试均 `PLANNED / NOT_IMPLEMENTED / NOT_RUN`；预算配置落点按 D4 已确认方案实施，不据此宣称 B0 通过。

### D4：独立 B0 资源配置（已确认，待实施）

新 B0 由最小 FastAPI app 显式装配一份经过校验的资源配置，统一执行全局/调用者额度、排队、截止、取消与退出回收。只复用无数据库副作用的工具函数，不回退旧 BI 的内存、线程、真实路径或连接初始化；旧 BI 配置保持不变，不新增第二业务服务。

沿用[测试地图首轮资源假设](./AUTOPLAN-TEST-PLAN-2026-09-05.md)：active worker=1、queue<=8、同调用者在途<=3、单查询30秒、含排队的run总截止120秒/最多8步、DuckDB512MiB/2线程/临时盘512MiB、worker RSS观测1GiB。统一调度不能按用户或 HTTP 进程复制 worker 配额；截止/取消后确认实际退出才释放。配置缺失/非法不借旧默认值继续执行，持久预算不因重启复位。

完整来源、治理落点、性能四项核查与实施检查点见[增量审核 D4](./ENGINEERING-INCREMENTAL-REVIEW-2026-09-05.md)。这些数值是待验证起点，RSS不是瞬时硬限额；基础状态/事件限制在前置内核运行前固化。多人共机/千万行测试仍为 V1/V2，B0 不控制旧 BI、ETL 或其他进程。

### gstack：沿用已定稿结论，增量审核变化

`office-hours / CEO 价值定稿 → autoplan / 工程评审历史 → 本次四项基线 → 增量设计与工程复核 → 补齐 B0 → 合同/金标准 → 纵向实现 → review + QA + 相关视觉验收 → 获授权的 ship → 单独获授权的合并/部署`。

这里是执行约定，不代表本轮重新运行了这些技能。实际执行时读取对应 SKILL.md；既有降级评审如实保留。gstack 管评审与交付组织，CI 管可重复检查，人工验收管业务效果，三者不能互相替代。只因参考风格收敛，不重开已收口的商业路线。

## 5. 开工门与下一步

1. 已确认：DSH 视觉优先、StaffDeck 为员工主参考、插件化私人驾驶舱；本次保存可编辑架构与技术推荐。
2. 四节静态审核完成：按 D1–D4 的原工作包映射交付最小任务内核、同仓可复现装配、故障测试和独立资源配置；具体 schema 与实现/测试同批冻结，布局兼容性仍须小样；只有改变既定范围/交互的选择再询问。
3. 恢复 B0 时先闭合业务 run 受理、连续提问、取消/恢复及原生状态映射，再验证 BI 往返和主题/品牌；原报告仍为 `PARTIAL`。
4. B0 未通过前不宣称底座可承载全链。经 D1 确认，允许前置 E-T1/E-T2/X-T1 中的最小任务合同和内核；不代表 B1–B4 完整开工或已通过。本次审核只更新计划，不启动服务、不改应用、不安装依赖、不操作真实库、不对外发布。

## 6. 依据与交叉核验

访问/核验日期：2026-09-05。项目事实来自本地锁文件和固定 DSH 源码；以下外部文档证明组件能力，不替代本项目验收。设计组织和组合选型是基于这些证据的工程判断，不声称是唯一最佳方案。

- **保留 UI、借鉴员工组织、不叠加运行时**：DSH 固定源码中的宿主 React 与插件插槽、[DSH 官方仓库](https://github.com/deepseek-ai/deepseek-harness)，与 [StaffDeck 官方 Core Workflows](https://github.com/OpenBMB/StaffDeck) 的员工/能力/会话/任务组织交叉参照。StaffDeck 是独立平台，借鉴其组织方式不要求引入其后端；[Hermes 官方仓库](https://github.com/NousResearch/hermes-agent) 作为辅助参考。
- **图表引擎与布局分离**：[ECharts 官方按需引入说明](https://echarts.apache.org/handbook/en/basics/import/) 支持独立实例与模块选择；[React-Grid-Layout 官方仓库](https://github.com/react-grid-layout/react-grid-layout) 说明 v2 的 React 18+、响应式拖拽缩放与布局序列化。另核验旧 `frontend-vue3/package-lock.json` 的 ECharts 6.1.0；两库能力互补，但 DSH 集成尚待小样。
- **应用状态与分析分离**：[SQLite 官方适用场景](https://www.sqlite.org/whentouse.html) 说明本地应用与写并发边界；[DuckDB 官方并发说明](https://duckdb.org/docs/current/connect/concurrency) 用于核验只读访问模式。二者与现有归档边界共同支持“本地状态库 + 只读合成分析”，不支持未经测试的高并发承诺。
- **合同优先**：[FastAPI 官方 Features](https://fastapi.tiangolo.com/features/) 的 OpenAPI/JSON Schema 能力，与现有前端 openapi-typescript 依赖交叉核对；唯一 schema 和生成类型不免除行为/权限测试。
- **分支评审与工程流程**：[GitHub Flow 官方说明](https://docs.github.com/en/get-started/using-github/github-flow)、[gstack 官方仓库](https://github.com/garrytan/gstack) 与本地 `.github/workflows/lint.yml`、`e2e-smoke.yml` 对照。推荐流程不等于远端保护规则已配置。
