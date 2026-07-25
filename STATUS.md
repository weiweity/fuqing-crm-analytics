# 项目状态 (Project Status)

> **短表 SSOT**。编年：[`docs/history/STATUS-HISTORY.md`](docs/history/STATUS-HISTORY.md) · 债：`docs/TECH-DEBT.md` · 文档：`docs/README.md`

## 当前快照（2026-07-25 PR5 供应链分支）

| 项 | 值 |
|---|---|
| **VERSION** | 以根目录 `VERSION` 为准 |
| **main** | CI 假红闭环：#39 check_imports + #40 timeout 45min |
| **进行中分支** | `chore/security-supply-chain`（PR5：依赖/Docker/CI/治理文档；**未 push**） |
| **可合并 CI** | **lint + test + contract-filterbuilder-lint**；frontend build 建议 required；audit/docker-smoke soft；e2e 非 PR 门禁 |
| **定时 CI** | Nightly / Weekly 与 PR 同口径；timeout 45min |
| **供应链文档** | `docs/operating/supply-chain.md` · `github-governance-checklist.md` · `docker-ports-and-images.md` |
| **DuckDB 升级** | 仅 checklist：`docs/maintenance/duckdb-backup-upgrade-checklist.md`（**不**在 PR 执行） |
| **债** | [`docs/TECH-DEBT.md`](docs/TECH-DEBT.md) — 无未规划开放债；YOY unit 与 L4.81 契约漂移为触发型 |
| **运维脚本** | [`scripts/ops/`](scripts/ops/)（launchd 已指新路径） |
| **Admin Upload** | **已撤回**，无产品路由 |
| **生产数据** | `data/processed/fuqing_crm.duckdb` 本地，**不进 git** |
| **服务** | :5173 / :8000 以 `lsof` 为准；Compose 容器内 backend `:8001` |

## 阅读顺序

1. 本文件 → 2. TECH-DEBT → 3. `docs/README.md` → 4. `CLAUDE.md`（硬门禁）→ 5. `docs/rules/L4-permanent-rules.md`（按需）
