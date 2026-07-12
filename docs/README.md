# Docs 索引

> 文档按 lifecycle 分层, 新人 5 分钟找到入口。
> **最后更新**: 2026-07-12 (Sprint 205+ L4.91 PR2 全部技术债闭环 + 7/16 离职前最终 doc cleanup: 13 件已 ship handoff/investigation → archive/ + 8 件 Codex prompt 纯 prompt 删除 + sprints/ 精简为 1 个索引文件 + archive 共 75 件. 累计节省 20+ 文件, 跟 L4.42 + L4.50 + L4.55 + L4.91 + L4.91.1 + L4.91.2 1:1 stable 永久规则链配套.)

## 一图流

```
fuqing-crm-analytics/docs/
├── README.md                          ← 你在这里
│
├── architecture/                      [系统设计 - 为什么]
│   ├── AI_SAFETY_NET.md              (L1 lint + L2 AST + L3 FilterBuilder 3 层防线)
│   ├── DATA_PIPELINE.md              (ETL 4 阶段: W1-W4)
│   ├── TEST_INFRASTRUCTURE.md        (Sprint 53 race flake fixture 模式 + L4.3/L4.4/L4.6)
│   ├── clickhouse-poc-decision-memo.md  (Sprint 201+ ClickHouse / Trino POC 立项决策备忘录, 5 阶段拆分 8-10 周 1-2 人月 + 启动条件 a/b/c)
│   ├── l4.74-duckdb-postgresql16-decision-memo.md  (L4.74 启动条件 b+c 真触发立项, 跟 L4.78 0 commit 收口 1:1 stable 永久规则化沿用)
│   └── l4_91_excel_export_ssot.md    (L4.91 8 件 bug 治本 + 24 视图审计 + 跨 sprint 留尾 SSOT)
│
├── business/                          [业务定义 SSOT]
│   └── RFM_DEFINITIONS.md            (Sprint 60+ L4.8 永久规则, RFM 阈值/口径定义)
│
├── data/                              [数据目录布局]
│   └── data-layout.md                (data/cache exports parquet processed raw 5 区用途+读写+清理)
│
├── operating/                         [操作手册 - 怎么用]
│   ├── ship.md                       (12 步流程)
│   ├── linting.md                    (ground-truth-lint 规则)
│   ├── pre-commit.md                 (hook 框架)
│   ├── automation.md                 (Claude Code 自动化)
│   ├── ci-defense-playbook.md        (L5.1 ROI 重评)
│   ├── ci-precommit.md               (GitHub Actions 配置)
│   ├── ci-e2e-history.md             (Sprint 41 实战 follow-up 12)
│   ├── hooks-choice.md               (.githooks vs .pre-commit-config)
│   ├── launchd-uvicorn.md            (Sprint 62 P3, launchd KeepAlive uvicorn 守护)
│   └── w3-dq-advisory.md             (Sprint 165 advisory, W3 DQ 2 failed 真因 + Sprint 166 已治本 advisory only)
│
├── development/                       [开发指南 - 怎么改]
│   ├── testing.md                    (test 怎么写, mock data, race flake 模式)
│   ├── services.md                   (新增 service 的 pattern, FilterBuilder 强制)
│   ├── ratio-convention.md           (B1+B2 ratio/pct/ppt/rate 命名规范)
│   ├── LESSONS_LEARNED.md            (Sprint 57 沉淀 9 项实战 fix pattern)
│   └── AUDIT-WORDING.md              (Sprint 59 #8 audit 措辞 SOP)
│
├── history/                           [历史归档]
│   └── SPRINT_INDEX.md               (Sprint 1-203 索引, 130+ memory file 入口)
│
├── maintenance/                       [新开发者维护指南]
│   └── BOOTSTRAP.md                  (Sprint 68 收口, 新开发者 clone 后必读 + L4.12 + L4.13 + L4.42)
│
├── sprints/                           [Sprint handoff 留尾 SSOT + 索引]
│   ├── _sprint-close-index.md        (Sprint 193-205+ close memory 指针)
│   └── archive/                      (75 件: Sprint 139-205+ 已 ship 全部 HANDOFF/CODEX/verification/handoff/investigate + L4.74 working docs + 8 件 Codex prompt 已删, 跨 sprint 历史 reference 留尾备查)
│
├── DISASTER-RECOVERY.md               (DUCKDB 备份恢复 SOP)
├── TECH-DEBT.md                       (技术债台账, P0/P1/P2 分级, 每债含触发场景+修复方案+估时)
├── WINDOWS-DEPLOY-KNOWN-ISSUES.md     (L4.64 Windows 11 部署 6 fix + Python 3.14.4 + npm legacy-peer-deps + NSSM 等)
└── user-prompt-template-ad-hoc-query.md  (Sprint 193 沉淀, 运营问数话术模板 5 模板 + 关键词必查表)
```

## 何时用哪个

| 你想... | 看 |
|--------|-----|
| 了解项目全貌 | `README.md` (项目根) |
| 看 AI 行为规则 (L4.1-L4.91 永久规则) | `CLAUDE.md` (项目根) |
| 跑 sprint 收口 | `operating/ship.md` + `STATUS.md` (项目根) |
| 加新 service | `development/services.md` + `architecture/AI_SAFETY_NET.md` |
| 写新 test | `development/testing.md` |
| 改 contract ratio 字段 | `development/ratio-convention.md` |
| 排查 CI 失败 | `operating/ci-defense-playbook.md` + `operating/ci-e2e-history.md` |
| 启动 uvicorn 后端 | `operating/launchd-uvicorn.md` (Sprint 62 P3 launchd 守护, kill 自动重启) |
| Excel 导出 bug | `architecture/l4_91_excel_export_ssot.md` (L4.91 SSOT) |
| ClickHouse POC 启动条件 (DuckDB > 200GB / 查询 P95 > 30s / 5+ 业务分析师并发) | `architecture/clickhouse-poc-decision-memo.md` + `scripts/clickhouse_poc_monitor.py` (launchd weekly 04:45 自动监控) |
| PostgreSQL 16 分布式启动条件 (查询 P95 > 30s + 5+ 业务分析师并发) | `architecture/l4.74-duckdb-postgresql16-decision-memo.md` + 5 commits 留尾分支 (跟 L4.78 0 commit 收口 1:1 stable 永久规则化沿用) |
| 即席查询 GSV / YOY / 渠道 / 两年对比 / 新老客 / R 区间复购 / Excel 多 sheet / 自然语言 ask 路由 / 固定商品列表对比 / 多周期 GSV / AI sandbox | `/ad-hoc-query` skill (Sprint 203 R5 v2.7 **18 tool** subcommands) |
| 看历史 sprint | `history/SPRINT_INDEX.md` (Sprint 1-203 索引) + `sprints/_sprint-close-index.md` (Sprint 193-205+ close memory 指针) |
| 状态总览 (版本/测试/debt) | `STATUS.md` (项目根, 单一 source of truth) |
| data/ 目录布局 | `data/data-layout.md` (cache/exports/parquet/processed/raw) |
| 业务定义 SSOT (RFM 阈值) | `business/RFM_DEFINITIONS.md` (Sprint 60+ L4.8 永久规则) |
| 实战 fix pattern (9 项) | `development/LESSONS_LEARNED.md` (Sprint 57 沉淀) |
| audit 措辞 SOP | `development/AUDIT-WORDING.md` (Sprint 59 #8 沉淀) |
| W3 DQ advisory | `operating/w3-dq-advisory.md` (Sprint 165 advisory only, Sprint 166 治本) |
| 新开发者 clone 必读 | `maintenance/BOOTSTRAP.md` (Sprint 68 收口) |
| Windows 11 部署 (跟 L4.64 1:1 stable) | `WINDOWS-DEPLOY-KNOWN-ISSUES.md` (Python 3.14.4 + npm legacy + NSSM 等 6 fix) |
| DUCKDB 备份恢复 | `DISASTER-RECOVERY.md` |
| 跨 sprint 留尾 (4 维度) | `TECH-DEBT.md` (跟 L4.12 SSOT 治理 1:1 stable) |
| Sprint 201-204 L4.42 立项实证 | `sprints/archive/SPRINT201-204_L442_VERIFICATION_INDEX.md` (5 件索引, archive 存原件) |
| Sprint 202+ wall_min 验证 R1-R8 | `sprints/archive/SPRINT202+_WALL_MIN_VERIFICATION_INDEX.md` (6 件索引) |
| Sprint 205+ Handoff/Prompt 留尾 | `sprints/archive/SPRINT205+_HANDOFF_PROMPT_INDEX.md` (留尾 4 件 + 已 ship 10 件索引) |
| 全部 sprint handoff 历史 | `sprints/archive/` (75 件, 含 L4.91 handoff/investigate 全部归档) |

## 跨 sprint 维护规则

**每个 Sprint 收口必做** (跟 Sprint 60+ 138 sprint 0 debt stable 模式 1:1 stable 永久规则化沿用):
1. `CHANGELOG.md` 加 entry (近 30 entry 滚动, 老 entry 自动 archive 到 `docs/history/CHANGELOG_HISTORY.md`)
2. `TECH-DEBT.md` 更新 (新债 / 已修数)
3. `STATUS.md` 更新 (版本 + pytest + debt + e2e 状态行)
4. `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint{N}.md` 写收口记忆
5. `HANDOFF-*.md` / `CODEX-PROMPT-*.md` / 已 ship sprint verification 归档到 `docs/sprints/archive/`
6. `docs/sprints/SPRINT{N}_*_INDEX.md` 加索引行 (跟 L4.57 0 commit 续期 1:1 stable 永久规则化沿用)
7. `MEMORY.md` size ≤ 24.4KB 验证 (跟 L4.13 永久规则 1:1 stable 永久规则化沿用)

**跨 sprint 留尾意识** (L4.5 + L5.1 + L4.42 + L4.57 + L4.58 + L4.59 1:1 stable 应用):
- 改 docs 之前先 `git log --oneline -- <doc_path>` 看历史 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)
- 任何"未集成"/"不存在"结论必须有 `git log` 实证
- 大改前 `git stash` → 新分支 → 完整 12 步流程
- 跨 sprint 续期 0 commit (跟 L4.57 0 commit 续期 SOP 1:1 stable 永久规则化沿用)
- 真业务触发再立 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)

## 跟 L4.x 永久规则链 1:1 stable 永久规则化沿用

- **L4.42 立项实证 SOP "git log + grep 实证"** 1:1 stable 永久规则化沿用 (跨 sprint 38 sprint stable)
- **L4.50 pytest cleanup 0 业务代码改动** 累计 92+ 次 1:1 stable 永久规则链配套
- **L4.55 立项 spec 实证 SOP** 1:1 stable 永久规则化沿用
- **L4.57 + L4.58 + L4.59** 跨 sprint 留尾 0 commit 续期 SOP 1:1 stable 永久规则化沿用
- **L4.78 L4.74 PG migration 0 commit 收口** 1:1 stable 永久规则化沿用 (5 commits 留尾分支备查)
- **L4.85.4 - L4.85.9 + L4.86 + L4.88** Codex app 完整收口 1:1 stable 永久规则化沿用
- **L4.91 Excel 导出 SSOT** 1:1 stable 永久规则化沿用 (8 件 bug + 24 视图审计 + 技术债 #1-#4 全部闭环)
- **L4.91.2 ProductAssetsTab + OtherProductAssetsTab formatValue + test_helpers** 1:1 stable 永久规则化沿用

---

**本索引跟 L4.42 + L4.50 + L4.55 + L4.57 + L4.58 + L4.59 + L4.78 + L4.85.4-L4.85.9 + L4.86 + L4.88 + L4.91 + L4.91.1 + L4.91.2 永久规则链 1:1 stable 永久规则化沿用, 7/16 离职前最终 doc cleanup, 接手人 7/16+ 启动必读.**