# Sprint archive 索引

> **最后更新**: 2026-07-19 document-release  
> 本目录保留已 ship 的 handoff / 验证报告，供查证。**不作为日常阅读入口**。

## 保留策略

| 类型 | 策略 |
|---|---|
| 业务功能 handoff（RFM/Sampling/品类等） | 保留 |
| L4.42 立项实证报告 | 保留（防脑补复发） |
| wall_min / CI fix 验证 | 保留指针级 |
| **Admin Upload 产品路径** | **已删除树内文件**（产品撤回）；git 历史可恢复 |
| **L4.74 / Trino 中间 stage** | 删中间报告；保留 `SPRINT-L474-STAGE-5-GO-NO-GO-DECISION.md` + `docs/architecture/l4.74-*.md` + clickhouse memo |
| 根目录迁入 HANDOFF | `root-handoffs-*/README.md`（正文多 gitignore） |

## 正式决策（优先于 archive 过程文）

| 主题 | SSOT |
|---|---|
| ClickHouse / Trino | `docs/architecture/clickhouse-poc-decision-memo.md` |
| PostgreSQL 16 / L4.74 | `docs/architecture/l4.74-duckdb-postgresql16-decision-memo.md` + `SPRINT-L474-STAGE-5-GO-NO-GO-DECISION.md` |
| Excel 导出 | `docs/architecture/l4_91_excel_export_ssot.md` |
| 开放债 | `docs/TECH-DEBT.md` |

## 列目录

```bash
ls docs/sprints/archive/*.md | wc -l
```
