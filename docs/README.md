# Docs 索引

> 按 lifecycle 分层，新人约 5 分钟找到入口。  
> **最后更新**: 2026-07-19（工作区扫描 + STATUS/TECH-DEBT 短表 + sprints 只留索引）

## 一图流

```
fuqing-crm-analytics/docs/
├── README.md                          ← 你在这里
├── TECH-DEBT.md                       开放债短表（唯一）
├── DISASTER-RECOVERY.md               DuckDB 备份恢复
├── WINDOWS-DEPLOY-KNOWN-ISSUES.md     Windows / L4.64
├── user-prompt-template-ad-hoc-query.md
│
├── architecture/                      为什么这样设计
│   ├── AI_SAFETY_NET.md
│   ├── DATA_PIPELINE.md
│   ├── TEST_INFRASTRUCTURE.md
│   ├── clickhouse-poc-decision-memo.md
│   ├── l4.74-duckdb-postgresql16-decision-memo.md
│   └── l4_91_excel_export_ssot.md
│
├── business/                          业务口径 SSOT
│   └── RFM_DEFINITIONS.md
│
├── data/                              data/ 布局
│   └── data-layout.md
│
├── operating/                         怎么运维 / 协作
│   ├── team-workflow-v1.md            可合并定义 · 角色
│   ├── project-hygiene.md             根目录 / 文档整洁
│   ├── ship.md · linting.md · hooks-* · launchd-uvicorn.md
│   └── ci-*.md
│
├── development/                       怎么改代码
│   ├── testing.md · services.md · ratio-convention.md
│   └── LESSONS_LEARNED.md · AUDIT-WORDING.md
│
├── rules/                             L4 细则全文
│   └── L4-permanent-rules.md
│
├── history/                           长编年归档
│   ├── STATUS-HISTORY.md
│   ├── TECH-DEBT-HISTORY.md
│   ├── CHANGELOG_HISTORY.md
│   └── SPRINT_INDEX.md
│
├── maintenance/
│   └── BOOTSTRAP.md
│
└── sprints/                           仅进行中 + archive
    ├── README.md
    ├── _sprint-close-index.md
    └── archive/                       已 ship handoff（80+）
```

## 仓库根（docs 之外）

| 文件 | 职责 |
|---|---|
| `README.md` | 人读项目简介 |
| `STATUS.md` | **短状态表**（勿再堆编年） |
| `VERSION` / `CHANGELOG.md` | 版本与近窗变更 |
| `CLAUDE.md` | AI 硬规则 + 指针；L4 细则在 `docs/rules/` |
| `HANDOVER.md` | 交接（gitignore 敏感信息） |
| 工作区父目录 | `../README.md`（`fuqin-date` 地图） |

## 何时用哪个

| 你想… | 看 |
|---|---|
| 项目能不能用 / 债指针 | 根 `STATUS.md` + `TECH-DEBT.md` |
| 团队怎么合 PR | `operating/team-workflow-v1.md` |
| 根目录该不该堆文件 | `operating/project-hygiene.md` |
| 加 service / 写 SQL | `development/services.md` + `architecture/AI_SAFETY_NET.md` |
| 写测试 | `development/testing.md` |
| RFM 口径 | `business/RFM_DEFINITIONS.md` |
| Excel 导出 | `architecture/l4_91_excel_export_ssot.md` |
| ClickHouse / PG 留尾 | architecture 两份 decision-memo + TECH-DEBT（0 默认重开） |
| 即席查询 | `/ad-hoc-query` skill · 18 tool |
| 历史 sprint | `history/SPRINT_INDEX.md` + `sprints/archive/` |
| 新 clone | `maintenance/BOOTSTRAP.md` |
| Windows 部署 | `WINDOWS-DEPLOY-KNOWN-ISSUES.md` |
| DuckDB 炸了 | `DISASTER-RECOVERY.md` |

## 文档维护（Sprint 收口）

1. `CHANGELOG.md` 加 entry（老条目进 `history/CHANGELOG_HISTORY.md`）
2. `TECH-DEBT.md` 只改**开放行**
3. `STATUS.md` 只改短表
4. 已 ship 的 `docs/sprints/HANDOFF-*` → `sprints/archive/`
5. 根目录不新增长期 `HANDOFF-TO-CODEX-*`（ignore + 放 archive）

## 2026-07-19 整理摘要

| 动作 | 结果 |
|---|---|
| STATUS / TECH-DEBT 短表 | 编年在 `history/` |
| sprints 顶层 | 仅 `_sprint-close-index` + README + archive |
| 根 HANDOFF 8 份 | `archive/root-handoffs-2026-07-19/` |
| PR #35 | e2e soft + SSOT lint 对齐 history |
| 开放债 | C7 deselect · e2e 严跑 · CLAUDE L4 瘦身 · scripts-ops · preflight-env |

---

**协作契约**: lint + test 必绿；e2e 默认不挡合（`team-workflow-v1`）。本地即生产，改 data 路径先问人。
