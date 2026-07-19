# 项目状态 (Project Status)

> **单一 source of truth（短表）**。长编年见 `docs/history/STATUS-HISTORY.md` / `CHANGELOG.md`。  
> 整洁与协作规范：`docs/operating/project-hygiene.md` · `docs/operating/team-workflow-v1.md`

## 当前快照（2026-07-19 backlog workflow）

| 项 | 值 |
|---|---|
| **VERSION** | `0.4.14.51`（以根目录 `VERSION` 文件为准） |
| **main** | 以 `git rev-parse origin/main` 为准（#30–#34 + STATUS 截断 + e2e soft） |
| **分支** | 目标仅 `main`；feature 合完即删 |
| **可合并 CI** | lint + test 必绿；e2e `continue-on-error`（见 team-workflow-v1） |
| **债** | `docs/TECH-DEBT.md`（短表）；历史 `TECH-DEBT + STATUS history 见 docs/history/` |
| **生产数据** | `data/` 本地、不进 git |
| **服务** | 前端 5173 / 后端 8000 以本机 `lsof` 为准 |

> 历史编年已迁至 [`docs/history/STATUS-HISTORY.md`](docs/history/STATUS-HISTORY.md)。

