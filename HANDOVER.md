# 交接说明（短表）

> **最后更新**: 2026-07-19  
> 细节以代码与下列 SSOT 为准，**不要**在本文件堆 sprint 日记。

## 立刻要看

| 问题 | 文档 |
|---|---|
| 系统能不能用？版本？端口？ | [`STATUS.md`](STATUS.md) |
| 还欠什么？ | [`docs/TECH-DEBT.md`](docs/TECH-DEBT.md) |
| 文档地图 | [`docs/README.md`](docs/README.md) |
| AI / 协作硬规则 | [`CLAUDE.md`](CLAUDE.md) · L4 全文 [`docs/rules/L4-permanent-rules.md`](docs/rules/L4-permanent-rules.md) |
| 怎么合 PR | [`docs/operating/team-workflow-v1.md`](docs/operating/team-workflow-v1.md) |
| 整洁规范 | [`docs/operating/project-hygiene.md`](docs/operating/project-hygiene.md) |
| 父工作区地图 | [`../README.md`](../README.md)（`fuqin-date`，非 monorepo） |
| 运营日常（PC2） | 父目录 `README-OPERATIONS.md`（含密钥的交接另见父目录 `HANDOVER.md`，**勿 commit 真密码**） |

## 技术栈（摘要）

- 后端 FastAPI · 前端 Vue3 · 分析库 DuckDB（`data/processed/fuqing_crm.duckdb`，本地大文件，**不进 git**）
- 版本号：根目录 `VERSION` + `CHANGELOG.md`
- 服务：后端 `:8000` · 前端 `:5173`（以 `lsof` 为准）

## 启动（开发机）

```bash
cd "/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics"
git checkout main && git pull origin main --ff-only
# 后端 / 前端按 README.md；hooks: bash scripts/setup-hooks.sh
```

## 禁止

1. 在 main 直接改业务代码（先 feature 分支）  
2. 提交 `data/**` / `.env` / duckdb  
3. 默认重开 Admin Upload 或 L4.74 PG（见 TECH-DEBT）  
4. 无 user 拍板就 `git push`（L4.15）

## 历史

长编年与旧 handoff 已归档或删除出树；需要时用 `git log -- docs/` / `docs/history/`。
