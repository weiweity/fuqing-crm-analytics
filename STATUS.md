# 项目状态 (Project Status)

> **单一 source of truth（短表）**。长编年见 `docs/history/STATUS-HISTORY.md` / `CHANGELOG.md`。  
> 整洁与协作规范：`docs/operating/project-hygiene.md` · `docs/operating/team-workflow-v1.md`

## 当前快照（2026-07-19）

| 项 | 值 |
|---|---|
| **VERSION** | `0.4.14.51`（以根目录 `VERSION` 为准） |
| **main** | `origin/main`（#30–#35 + document-release：L4→rules、CHANGELOG 滚动、archive 精简） |
| **分支** | 目标仅 `main`；feature 合完即删 |
| **可合并 CI** | lint + test 必绿；e2e `continue-on-error`（`team-workflow-v1`） |
| **债** | [`docs/TECH-DEBT.md`](docs/TECH-DEBT.md)（**#CLAUDE-L4-sink 已闭环**；余 P2 见台账） |
| **文档** | [`docs/README.md`](docs/README.md) · L4 全文 [`docs/rules/L4-permanent-rules.md`](docs/rules/L4-permanent-rules.md) · 工作区 `../README.md` |
| **生产数据** | `data/processed/fuqing_crm.duckdb` 本地 ~131GB，**不进 git** |
| **服务** | 前端 5173 / 后端 8000 以本机 `lsof` 为准 |

> 历史编年：[`docs/history/STATUS-HISTORY.md`](docs/history/STATUS-HISTORY.md)

