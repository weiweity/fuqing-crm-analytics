# 项目状态 (Project Status)

> **短表 SSOT**。编年：[`docs/history/STATUS-HISTORY.md`](docs/history/STATUS-HISTORY.md) · 债：`docs/TECH-DEBT.md` · 文档：`docs/README.md`

## 当前快照（2026-07-19 治理收口）

| 项 | 值 |
|---|---|
| **VERSION** | 以根目录 `VERSION` 为准 |
| **main** | 文档 release + Admin 撤回 + `scripts/ops` 监控分区 |
| **分支** | 目标仅 `main`；feature 合完即删 |
| **可合并 CI** | **lint + test + e2e 必绿**（2026-07-19 e2e 根治；team-workflow-v1） |
| **债** | [`docs/TECH-DEBT.md`](docs/TECH-DEBT.md) — **无未规划开放债**（仅触发型延期） |
| **运维脚本** | [`scripts/ops/`](scripts/ops/)（launchd 已指新路径） |
| **Admin Upload** | **已撤回**，无产品路由 |
| **生产数据** | `data/processed/fuqing_crm.duckdb` 本地，**不进 git** |
| **服务** | :5173 / :8000 以 `lsof` 为准 |

## 阅读顺序

1. 本文件 → 2. TECH-DEBT → 3. `docs/README.md` → 4. `CLAUDE.md`（硬门禁）→ 5. `docs/rules/L4-permanent-rules.md`（按需）
