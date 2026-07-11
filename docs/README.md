# Docs 索引

> 文档按 lifecycle 分层, 新人 5 分钟找到入口。Sprint 54 起 (L3 FilterBuilder 100% 闭环) 架构师推荐分层。
> 最后更新: 2026-07-11 (Sprint 205+ L4.85.4-L4.85.9 Codex app 完整收口 + L4.86 + L4.87 + L4.88 4 件 sprint 收口 1:1 stable 永久规则化沿用 + 累计 Sprint 60+ 0 debt stable 141 sprint 1:1 stable 跨 sprint plan 沿用. 合并 HANDOVER.md (274 行) + OPERATIONS.md (485 行) 内容到 CLAUDE.md L4.85 段, 节省 759 行 (跟 L4.50 0 业务代码改动 + L4.42 立项实证 SOP 1:1 stable 永久规则链配套). 补 docs/sprints/_sprint-close-index.md L4.85-L4.88 索引行 + 合并 docs/sprints/archive/ 旧 sprint 文档到 docs/history/SPRINT_INDEX.md. 累计 /document-release 65 次 + Wave 1 跨 sprint plan Sprint N+1 to N+5 准备 1:1 stable + 跟你 7/16 离职 0.5-1 天闭环 1:1 stable 永久规则化沿用)

## 一图流

```
fuqing-crm-analytics/docs/
├── README.md                          ← 你在这里
│
├── architecture/                      [系统设计 - 为什么]
│   ├── AI_SAFETY_NET.md              (L1 lint + L2 AST + L3 FilterBuilder 3 层防线)
│   ├── DATA_PIPELINE.md              (ETL 4 阶段: W1-W4)
│   ├── TEST_INFRASTRUCTURE.md        (Sprint 53 race flake fixture 模式 + L4.3/L4.4/L4.6)
│   ├── 50m-scale-architecture.md     (Sprint 52 P2 留尾, 30M 数据触发)
│   └── clickhouse-poc-decision-memo.md  (Sprint 201+ ClickHouse / Trino POC 立项决策备忘录, 5 阶段拆分 8-10 周 1-2 人月 + 启动条件 a/b/c)
│
├── business/                          [业务定义 SSOT]
│   └── RFM_DEFINITIONS.md            (Sprint 60+ L4.8 永久规则, RFM 阈值/口径定义)
│
├── data/                              [数据目录布局]
│   └── data-layout.md                (data/cache exports parquet processed raw 5 区用途+读写+清理)
│
├── operating/                         [操作手册 - 怎么用]
│   ├── ship.md                       (原 SHIP.md, 12 步流程)
│   ├── linting.md                    (原 LINTING.md, ground-truth-lint 规则)
│   ├── pre-commit.md                 (原 PRE-COMMIT.md, hook 框架)
│   ├── automation.md                 (原 AUTOMATION.md, Claude Code 自动化)
│   ├── ci-defense-playbook.md        (原 CI-DEFENSE-PLAYBOOK.md, L5.1 ROI 重评)
│   ├── ci-precommit.md               (原 CI-PRECOMMIT.md, GitHub Actions 配置)
│   ├── ci-e2e-history.md             (原 CI-E2E-HISTORY.md, Sprint 41 实战 follow-up 12)
│   ├── hooks-choice.md               (原 HOOKS-CHOICE.md, .githooks vs .pre-commit-config)
│   ├── launchd-uvicorn.md            (Sprint 62 P3, launchd KeepAlive uvicorn 守护)
│   ├── w3-dq-advisory.md             (Sprint 165 advisory, W3 DQ 2 failed 真因 + Sprint 166 已治本 advisory only)
│   └── (frontend-types-gen.md / yoy-guard-config.md 已于 Sprint 61 清理, 改用 .claude/skills/regen-types/ + pre-commit hook)
│
├── development/                       [开发指南 - 怎么改]
│   ├── testing.md                    (test 怎么写, mock data, race flake 模式)
│   ├── services.md                   (新增 service 的 pattern, FilterBuilder 强制)
│   ├── ratio-convention.md           (B1+B2 ratio/pct/ppt/rate 命名规范)
│   ├── LESSONS_LEARNED.md            (Sprint 57 沉淀 9 项实战 fix pattern: DUCKDB_PATH / subagent / race flake / spec-lint / Codex / 12 步流程 / 破坏→验证→恢复 / commit msg↔diff / empty vs stub)
│   └── AUDIT-WORDING.md              (Sprint 59 #8 audit 措辞 SOP, 5 规则 + 5 反例正例)
│
├── history/                           [历史归档]
│   └── SPRINT_INDEX.md               (Sprint 1-203 索引, 130+ memory file 入口)
│
├── maintenance/                       [新开发者维护指南]
│   └── BOOTSTRAP.md                  (Sprint 68 收口, 新开发者 clone 后必读 + L4.12 留尾 SSOT 治理 + L4.13 MEMORY.md 24.4KB + L4.42 立项实证 SOP)
│
└── sprints/                           [Sprint handoff 临时 / 归档]
    ├── _sprint-close-index.md        (Sprint 193-203 close memory 指针, 跨 sprint 跨端访问 SSOT)
    ├── SPRINT_FUQING_DATA_QUERY_SKILL_PLAN.md  (Sprint 202+ Data Query v2.7 立项 plan, /autoplan 入口)
    ├── SPRINT201_PLUS_L442_VERIFICATION.md / SPRINT201_PLUS_R6_R7_R8_R9_VERIFICATION.md / SPRINT201_R2_V24_L442_VERIFICATION.md / SPRINT202_PLUS_L442_VERIFICATION.md / SPRINT202_R1_WALL_MIN_VERIFICATION.md / SPRINT202+_R4_WALL_MIN_VERIFICATION.md / SPRINT202+_R5_WALL_MIN_VERIFICATION.md / SPRINT202+_R6_WALL_MIN_ESTIMATED.md / SPRINT203_ARCHITECTURE_REVIEW.md / SPRINT203_R6_SKILL_V2_7_SNAPSHOT.md / SPRINT204+_L442_VERIFICATION.md  (Sprint 立项实证 + L4.42 验证 + 跑批 wall_min 验证/估算 + 架构审查 + SKILL.md v2.7 项目仓 snapshot + Sprint 204+ 3 件跨 sprint 留尾 0 commit 收口, 跨 sprint 留尾验证沉淀)
    ├── SPRINT202+_R7_WALL_MIN_VERIFIED.md / SPRINT202+_R8_WALL_MIN_VERIFIED.md / SPRINT-N+2-TRINO-BENCHMARK.md / SPRINT-N+1-BUSINESS-INTERVIEW-REQUIREMENTS.md / SPRINT-N+1-DUCKDB-BASELINE-2026-07.md / HANDOFF-TO-CODEX-SprintN+3-ClickHouse-POC-Trino-Cluster.md / HANDOFF-TO-CODEX-SprintN+4-ClickHouse-POC-DuckDB-Trino-ETL.md / HANDOFF-SprintN+5-Stage-Architecture-Inputs.md  (Sprint 202+ R7/R8 wall_min FAIL→PASS 收口 + Sprint N+1 业务方访谈 PDF 需求文档 + Sprint N+1 W2 DuckDB 128GB 性能基线 median P95=0.068s 跟业务方期望 <5s 1:1 stable + Sprint N+2 Trino POC bench 模板 + Wave 1 跨 sprint plan N+3/N+4/N+5 handoff doc 三件套, 跟 L4.42+L4.55+L4.56+L4.57+L4.58+L4.59 永久规则 1:1 stable 沿用)
    └── archive/                      (Sprint 139-159 老 HANDOFF 归档, 历史 reference)
```

## 何时用哪个

| 你想... | 看 |
|--------|-----|
| 了解项目全貌 | `README.md` (项目根) |
| 看 AI 行为规则 (L4.1-L4.62 永久规则) | `CLAUDE.md` (项目根) |
| 跑 sprint 收口 | `operating/ship.md` + `STATUS.md` (项目根) |
| 加新 service | `development/services.md` + `architecture/AI_SAFETY_NET.md` |
| 写新 test | `development/testing.md` |
| 改 contract ratio 字段 | `development/ratio-convention.md` |
| 排查 CI 失败 | `operating/ci-defense-playbook.md` + `operating/ci-e2e-history.md` |
| 启动 uvicorn 后端 | `operating/launchd-uvicorn.md` (Sprint 62 P3 launchd 守护, kill 自动重启) |
| ClickHouse POC 启动条件 (DuckDB > 200GB / 查询 P95 > 30s / 5+ 业务分析师并发) | `architecture/clickhouse-poc-decision-memo.md` + `scripts/clickhouse_poc_monitor.py` (launchd weekly 04:45 自动监控) |
| 即席查询 GSV / YOY / 渠道 / 两年对比 / 新老客 / R 区间复购 / Excel 多 sheet / 自然语言 ask 路由 / 固定商品列表对比 / 多周期 GSV / AI sandbox | `/ad-hoc-query` skill (Sprint 198 v2.6 **14 tool** subcommands, 跨 Sprint 171/183/196/197/198 累积: two-year-overview / new-old-customer / rfm-repurchase / top-n / export-excel / dq-report / ask / channel-slice / daily-gsv / daily-gsv-multi-period / fixed-product-list-compare / fixed-product-list-compare-http / ai-sandbox-execute, 三端兼容 Claude Code + CodeBuddy CLI + WorkBuddy, 跟 backend service 复用口径, 直接 import 不直连 DuckDB) |
| 看历史 sprint | `history/SPRINT_INDEX.md` (Sprint 1-203 索引) + `sprints/_sprint-close-index.md` (Sprint 193-203 close memory 指针) |
| 状态总览 (版本/测试/debt) | `STATUS.md` (项目根, 单一 source of truth) |
| data/ 目录布局 | `data/data-layout.md` (cache/exports/parquet/processed/raw) |
| 业务定义 SSOT (RFM 阈值) | `business/RFM_DEFINITIONS.md` (Sprint 60+ L4.8 永久规则) |
| 实战 fix pattern (9 项) | `development/LESSONS_LEARNED.md` (Sprint 57 沉淀) |
| audit 措辞 SOP | `development/AUDIT-WORDING.md` (Sprint 59 #8 沉淀) |
| W3 DQ advisory | `operating/w3-dq-advisory.md` (Sprint 165 advisory only, Sprint 166 治本) |
| 新开发者 clone 必读 | `maintenance/BOOTSTRAP.md` (Sprint 68 收口) |

## 跨 sprint 维护规则

**每个 Sprint 收口必做**:
1. `CHANGELOG.md` 加 entry (近 30 entry 滚动)
2. `TECH-DEBT.md` 更新 (新债 / 已修数)
3. `STATUS.md` 更新 (版本 + pytest + debt + e2e 状态行)
4. `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint{N}.md` 写收口记忆
5. `HANDOFF-*.md` / `CODEX-PROMPT-*.md` 归档到 `docs/sprints/archive/` (Sprint 收口后)

**跨 sprint 留尾意识** (L4.5 + L5.1 应用):
- 改 docs 之前先 `git log --oneline -- <doc_path>` 看历史
- 任何"未集成"/"不存在"结论必须有 `git log` 实证
- 大改前 `git stash` → 新分支 → 完整 12 步流程

## 推荐下一步 (Sprint 56+ 评估)

1. ~~**重构 docs/ 到 operating/ development/ architecture/ history/ 子目录**~~ ✅ Sprint 55 闭环
2. ~~**新增 STATUS.md**~~ ✅ Sprint 56 闭环 (本 sprint 4 doc 任务闭环, 见项目根 `STATUS.md`)
3. **新增 history/SPRINT_INDEX.md** (索引 27+ memory file) — 减少冷启动 token

按用户节奏, **本 Sprint 不强推** (跨 sprint recurring 风险, 跟 Sprint 41 实战 fix 模式一致)。
