# 交接说明（短表）

> **最后更新**: 2026-09-16。VERSION **0.9.0.0** 本机正式候选，loopback，不上公网。见 [LOCAL-RELEASE-2026-09-16](docs/hackathon/LOCAL-RELEASE-2026-09-16.md)。
> 细节以代码与下列 SSOT 为准，**不要**在本文件堆 sprint 日记。

## 立刻要看

| 问题 | 文档 |
|---|---|
| Agent 规则 | [`AGENTS.md`](AGENTS.md)（`CLAUDE.md` 只是兼容入口） |
| 系统能不能用？版本？端口？ | [`STATUS.md`](STATUS.md) |
| 还欠什么？（M1 任务卡） | [`docs/hackathon/TODOS.md`](docs/hackathon/TODOS.md#m1-核心交付) |
| 还欠什么？（运维债） | [`docs/TECH-DEBT.md`](docs/TECH-DEBT.md) |
| 文档地图 | [`docs/README.md`](docs/README.md) |
| 怎么合 PR | [`.agents/skills/ship-pr/SKILL.md`](.agents/skills/ship-pr/SKILL.md) |
| 整洁规范 | [`docs/operating/project-hygiene.md`](docs/operating/project-hygiene.md) |

## 技术栈（摘要）

- 后端 FastAPI · 前端 Vue3 · 分析库 DuckDB（`data/processed/fuqing_crm.duckdb`，本地大文件，**不进 git**）
- 版本号：根目录 `VERSION` + `CHANGELOG.md`
- 服务（以 `lsof` 为准）：DSH `:6677` · 合成 HTTP `:18082` · 比赛看板前端 `:15173` · 比赛看板 API `:8000`。通用 Vite 5173 不是比赛看板入口。

## 启动（开发机）

```bash
cd "/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/fuqing-crm-analytics"
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
