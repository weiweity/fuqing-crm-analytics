# Sprint archive（精简后）

> **2026-07-19**：过程 handoff / 重复验证报告已 `git rm`（blob 仍在 git 历史）。  
> 树内只保留**决策与索引**。

## 当前文件

| 文件 | 用途 |
|---|---|
| [`README.md`](README.md) | archive 目录说明 |
| [`SPRINT201-204_L442_VERIFICATION_INDEX.md`](SPRINT201-204_L442_VERIFICATION_INDEX.md) | L4.42 立项实证索引 |
| [`SPRINT202+_WALL_MIN_VERIFICATION_INDEX.md`](SPRINT202+_WALL_MIN_VERIFICATION_INDEX.md) | ETL wall_min 验证索引 |
| [`SPRINT-L474-STAGE-5-GO-NO-GO-DECISION.md`](SPRINT-L474-STAGE-5-GO-NO-GO-DECISION.md) | L4.74 收口决策 |
| [`SPRINT-N+5-GO-DECISION-2026-07-06.md`](SPRINT-N+5-GO-DECISION-2026-07-06.md) / [`NO-GO`](SPRINT-N+5-NO-GO-DECISION-2026-07-06.md) | ClickHouse 波次拍板 |
| [`root-handoffs-2026-07-19/README.md`](root-handoffs-2026-07-19/README.md) | 根 HANDOFF 清理说明 |

## 正式决策（优先）

| 主题 | 路径 |
|---|---|
| ClickHouse / Trino | `docs/architecture/clickhouse-poc-decision-memo.md` |
| PostgreSQL / L4.74 | `docs/architecture/l4.74-duckdb-postgresql16-decision-memo.md` |
| Excel 导出 | `docs/architecture/l4_91_excel_export_ssot.md` |
| 开放债 | `docs/TECH-DEBT.md` |

## 恢复已删过程文

```bash
git log --diff-filter=D --summary -- docs/sprints/archive/ | head
git show <commit>:docs/sprints/archive/<file>.md
```
