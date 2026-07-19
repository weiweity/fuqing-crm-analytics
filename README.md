# 天猫CRM 客户分析系统

> 内部运营中台 · 数据驱动的客户洞察 · 每日 9 点自动推送

---

## 项目简介

天猫CRM 客户分析系统是为天猫电商运营团队打造的内部数据中台，处理 **1030 万订单 / 410 万用户**（2020-2026）的数据规模，提供实时的客户洞察能力。

### 核心价值

- ⏰ 每日 9 点自动推送运营洞察
- 📊 口径唯一可信，改一处全局生效
- 🔍 多维度分析：老客健康 / 市场对焦 / 品类 / 人群 / 地域
- 📤 一键导出复盘数据

---

## 快速开始

### 1. 一次性激活 githooks

```bash
bash scripts/setup-hooks.sh   # 激活 pre-commit / pre-push (一次性, session 保持)
```

### 2. 启动服务

```bash
cd "/Users/yourname/Desktop/fuqin date/fuqing-crm-analytics"
export HEALTH_API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
PYTHONPATH="$(pwd)" nohup python3 -m uvicorn backend.main:app \
  --host 0.0.0.0 --port 8000 --reload --reload-dir backend \
  >> /tmp/fuqing-crm-backend.log 2>&1 &
cd frontend-vue3 && npm run dev
```

- 后端 API: http://localhost:8000
- 前端界面: http://localhost:5173
- API 文档（无需登录）: http://localhost:8000/docs

### 3. ETL 增量更新

```bash
PYTHONPATH="$(pwd)" /Users/yourname/homebrew/bin/python3 scripts/run_etl.py --update
```

### 4. 即席查询 CLI（`/ad-hoc-query` skill, Sprint 171 v2.0）

```bash
# 9 个子命令: daily-gsv / yoy-battle / channel-slice /
#   two-year-overview / new-old-customer / rfm-repurchase /
#   top-n / export-excel / dq-report / ask NL 路由
PYTHONPATH="$(pwd)" python3 scripts/ad_hoc_query.py <cmd> [args]
# 详: .claude/skills/ad-hoc-query/SKILL.md
```

### 5. 测试

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
| **AI 行为规则** | [`CLAUDE.md`](./CLAUDE.md) · L4 细则 [`docs/rules/L4-permanent-rules.md`](./docs/rules/L4-permanent-rules.md) |
| **协作 / 整洁** | [`docs/operating/team-workflow-v1.md`](./docs/operating/team-workflow-v1.md) · [`project-hygiene.md`](./docs/operating/project-hygiene.md) |
| **父工作区地图** | [`../README.md`](../README.md)（`fuqin-date`，非 git monorepo） |

---

## 文档导航

完整文档索引 + 跨文档一致性见 [`docs/README.md`](./docs/README.md)。速查：

| 文档 | 说明 |
|---|---|
| [`CLAUDE.md`](./CLAUDE.md) | **AI 行为规则 / Git 工作流 / 架构 / AI 检查点** |
| [`docs/operating/ship.md`](./docs/operating/ship.md) | /ship skill 使用文档（12 步流程） |
| [`docs/operating/automation.md`](./docs/operating/automation.md) | Claude Code 自动化配置 |
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
