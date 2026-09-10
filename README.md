# 伸美 AI 增长董事会

> AI 黑客松作品 · 多渠道客户资产诊断 · 受控自由问数与人群决策

> **价值定稿（2026-09-05）**：已确认让老板拍板一个有边界的天猫内部跨渠道客户增长试点，主线是“渠道 × 首购商品 × 后续购买”。见 [CEO 价值与首版决策方案](./docs/hackathon/CEO-VALUE-PLAN.md)（用户已批准定稿，APPROVED）。统一分析工作台方向保留；用户已确认保留 DSH 原生 UI，详见 [DSH 交互设计](./docs/hackathon/DSH-UI-INTERACTION-SPEC.md)。原生 UI 的集成、运行时与模型仍待验证，公网部署继续暂缓。

> **当前交付（2026-09-10）**：competition 集成 #112 和 7 项审查修复 #114 已合入 main `788b5b1`；PR 与合并后的主线 CI 均通过。独立合成浏览器已验证连续成板、失败重试、保存布局重开及行动草稿 v2，见 [修复 QA](./docs/hackathon/COMPETITION-REPAIR-QA-2026-09-10.md)。当前按 [产品验收与发布准备账本](./docs/hackathon/PRODUCT-READINESS-2026-09-10.md) 推进；T13 已有真实 DeepSeek 有界实测，T15 待本人验收，T16 仅合成单用户基线，T17 PARTIAL，整产品仍 PARTIAL。约千万行、10 人使用仍是规划输入，公网尚未部署。

> **候选追加**：#115 `d482bd6` CI SUCCESS，已切换 4325/18083；原生主题、实际 AntD、BAR 重开及五库恢复有本轮证据。快速 canary 仍有既有 B0 404，整产品 PARTIAL。见[当前候选切换](./docs/hackathon/PRODUCT-CANDIDATE-SWITCH-2026-09-10.md)。

---

## 项目简介

本仓库源自多渠道 CRM 分析系统。目标是把既有分析能力组织成 CEO 决策产品：AI 准备机会、证据和行动草案，老板决定优先级、资源和继续/停止条件。第一版围绕可观察的首购与后续购买，不宣称完整生命周期或已验证增长。

当前保留的 Mission 演示基线使用合成数据，支持受控问数与审批后的合成人群草稿；它不等于新版多轮工作台和驾驶舱已交付。真实业务数据库不进入公开演示链。

### 核心价值与边界

- 看清不同渠道和首购商品的客户后续买了什么，形成可验证的经营机会，不只给渠道排名。
- 老板拍板试点方向、负责人、资源上限和退出条件；人群核对与具体执行属于运营职责。
- 目标工作台以可信追问、证据和分析复用支持决策，不把“每天唯一 Mission”作为新版强制入口。
- 稳定 `user_id` 关联的是可观察订单旅程，不是因果获客归因；缺少成本与干预证据时不判断利润最优。
- 现有审批后仅生成合成 `DRAFT_EXPORT`，演示 holdout 比例不是通用实验设计，不自动触达真实用户。
- 公开演示使用代码生成的合成数据与 manifest；流程演示不证明真实业务收益。

---

## 快速开始

新 DSH 开发入口见 [dsh-dev 使用说明](./scripts/dsh-dev/README.md)，比赛 HTTP 包络与隔离约定见 [competition-http](./docs/operating/competition-http.md)，验证按 [当前验证入口](./docs/operating/verification.md) 选择范围。以下是**既有演示/私有分析的历史入口**，不作为新工作台的默认启动或验证命令；不要继承私人数据库配置。

### 1. 启动本地演示

```bash
./scripts/ops/start-stack.sh
```

- 后端 API: http://localhost:8000
- 前端界面: http://localhost:5173
- API 文档（无需登录）: http://localhost:8000/docs

演示结束后恢复冷存：

```bash
./scripts/ops/stop-stack.sh
```

Mission 的合成数据和环境配置见 [`docs/hackathon/README.md`](./docs/hackathon/README.md)。

### 2. ETL 增量更新（仅既有私有分析环境）

```bash
PYTHONPATH="$(pwd)" /Users/yourname/homebrew/bin/python3 scripts/run_etl.py --update
```

### 3. 即席查询 CLI（`/ad-hoc-query` skill, Sprint 171 v2.0）

```bash
# 9 个子命令: daily-gsv / yoy-battle / channel-slice /
#   two-year-overview / new-old-customer / rfm-repurchase /
#   top-n / export-excel / dq-report / ask NL 路由
PYTHONPATH="$(pwd)" python3 scripts/ad_hoc_query.py <cmd> [args]
# 详: .claude/skills/ad-hoc-query/SKILL.md
```

### 4. 测试

```bash
PYTHONPATH="$(pwd)" pytest backend/tests/ -v              # 后端单测
cd frontend-vue3 && npx playwright test                   # E2E
```

---

## 状态 SSOT

> **短表入口** — 详细历史在 `docs/history/`，不要在 STATUS 堆编年。

| 维度 | 入口 |
|---|---|
| **当前能不能用 / 债指针 / 服务端口** | [`STATUS.md`](./STATUS.md)（短表） |
| **开放技术债** | [`docs/TECH-DEBT.md`](./docs/TECH-DEBT.md) |
| **文档总索引** | [`docs/README.md`](./docs/README.md) |
| **版本变更** | [`CHANGELOG.md`](./CHANGELOG.md) · 老条目 `docs/history/CHANGELOG_HISTORY.md` |
| **AI 行为规则** | [`AGENTS.md`](./AGENTS.md)（唯一正文；CLAUDE 仅导入）；旧 CRM L4 细则按主题查阅 |
| **协作 / 整洁** | [`docs/operating/team-workflow-v1.md`](./docs/operating/team-workflow-v1.md) · [`project-hygiene.md`](./docs/operating/project-hygiene.md) |
| **AI 增长董事会** | [`docs/hackathon/README.md`](./docs/hackathon/README.md) · [`MISSION-API.md`](./docs/hackathon/MISSION-API.md) |
| **视觉与交互基线** | [`DESIGN.md`](./DESIGN.md) |

---

## 文档导航

完整文档索引 + 跨文档一致性见 [`docs/README.md`](./docs/README.md)。速查：

| 文档 | 说明 |
|---|---|
| [`AGENTS.md`](./AGENTS.md) | **AI 行为规则 / 授权 / 架构 / 分级验证** |
| [`docs/operating/ship.md`](./docs/operating/ship.md) | 历史交付记录；当前 Git 动作按 AGENTS.md |
| [`docs/operating/automation.md`](./docs/operating/automation.md) | 当前本地 hooks/Skills 边界与历史自动化记录 |
| [`docs/operating/ci-defense-playbook.md`](./docs/operating/ci-defense-playbook.md) | CI 失败排查决策树 |
| [`docs/architecture/AI_SAFETY_NET.md`](./docs/architecture/AI_SAFETY_NET.md) | L1 lint + L2 AST + L3 FilterBuilder 3 层防线 |
| [`docs/architecture/DATA_PIPELINE.md`](./docs/architecture/DATA_PIPELINE.md) | ETL 4 阶段: W1-W4 |
| [`docs/business/RFM_DEFINITIONS.md`](./docs/business/RFM_DEFINITIONS.md) | RFM 阈值/口径定义 SSOT |
| [`docs/data/data-layout.md`](./docs/data/data-layout.md) | data/cache exports parquet processed raw 5 区用途+清理 |
| [`docs/history/SPRINT_INDEX.md`](./docs/history/SPRINT_INDEX.md) | Sprint 1-150+ 索引 |
| [`docs/maintenance/BOOTSTRAP.md`](./docs/maintenance/BOOTSTRAP.md) | 新开发者 clone 后必读 |
| [`docs/development/testing.md`](./docs/development/testing.md) | test 怎么写 + mock + race flake 模式 |
| [`docs/development/services.md`](./docs/development/services.md) | 新增 service 的 pattern + FilterBuilder 强制 |
| [`docs/development/LESSONS_LEARNED.md`](./docs/development/LESSONS_LEARNED.md) | 9 项实战 fix pattern 沉淀 |
| [`docs/development/ratio-convention.md`](./docs/development/ratio-convention.md) | B1+B2 ratio/pct/ppt/rate 命名规范 |
| [`docs/development/AUDIT-WORDING.md`](./docs/development/AUDIT-WORDING.md) | audit 措辞 SOP |

---

## 架构原则

本节订单/退款规则属于既有私有CRM，不自动套用于新synthetic分析。新渠道路径的净支付有效单、同刻排序和N日成熟窗口采用 [版本化拟定合同](./docs/hackathon/ANALYTICS-CONTRACTS-DRAFT.md#7-v1-指标与合成金标准约定拟定)，须独立金标准验证，不能混用分母。

1. **语义层唯一真实数据源**：口径只定义一次，禁止在 Service 中硬编码 SQL
2. **双保险过滤**：`is_refund=FALSE` 且 `order_status!='交易关闭'`
3. **契约层外置**：所有 Pydantic 模型统一从 `backend/contracts/schemas.py` 导入
4. **前端只做展示**：禁止前端计算 YOY/占比等业务指标
5. **连接零泄漏**：DuckDB 连接必须 try/finally 关闭

详细项目结构见 `docs/README.md`。

---

## 运维安全 / 磁盘治理

6 层防护详情见 `docs/operating/ship.md` 跟 Sprint 6 P0-3 落地说明。

紧急清理:

```bash
PYTHONPATH="$(pwd)" python3 scripts/etl/cli.py --cleanup-tmp
```

---

## 核心技术栈

| 层级 | 技术 |
|---|---|
| 数据处理 | Python + Pandas + DuckDB |
| 后端 API | FastAPI + Pydantic |
| 前端界面 | Vue3 + Vite + ECharts 6 + Tailwind + naive-ui |
| 状态管理 | Pinia + TanStack Query |
| 语义层 | `backend/semantic/`（口径唯一真实数据源） |
| 契约层 | `backend/contracts/schemas.py`（Pydantic → OpenAPI → TypeScript） |

---

## core 数据指标

| 指标 | 口径 |
|---|---|
| GSV | 剔除购物金 + 退款的有效订单金额 |
| GMV | 剔除购物金，含退款的订单金额 |
| 新老客 | cutoff = 查询起始日 - 1 天，此前有购买 = 老客 |
| RFM | R=最近购买天数, F=购买频次, M=消费金额 |
