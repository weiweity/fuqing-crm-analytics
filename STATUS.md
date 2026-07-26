# 项目状态 (Project Status)

> **短表 SSOT**。编年：[`docs/history/STATUS-HISTORY.md`](docs/history/STATUS-HISTORY.md) · 债：`docs/TECH-DEBT.md` · 文档：`docs/README.md`

## 当前快照（2026-07-26 合并后安全复核）

| 项 | 值 |
|---|---|
| **VERSION** | 以根目录 `VERSION` 为准 |
| **main** | `9bedd40`：#42–#48 安全修复已合并 |
| **进行中分支** | `fix/post-security-audit-residuals`（合并后残留复核，未 push） |
| **可合并 CI** | **lint + test + ground-truth-lint + contract-filterbuilder-lint + frontend + dependency-audit + docker-smoke** 全部 required；e2e 非 PR 门禁 |
| **定时 CI** | Nightly / Weekly 与 PR 同口径；timeout 45min |
| **供应链文档** | `docs/operating/supply-chain.md` · `github-governance-checklist.md` · `docker-ports-and-images.md` |
| **Actions 策略** | 仅 GitHub-owned Actions；所有 workflow 强制 40 位 commit SHA |
| **DuckDB 升级** | PyPI 已发布 1.5.5；仅 checklist，必须先有可恢复备份与恢复演练，**不**在本分支执行 |
| **债** | [`docs/TECH-DEBT.md`](docs/TECH-DEBT.md) — 凭据轮换、备份恢复、runtime 同步等已明确排期/门禁 |
| **运维脚本** | [`scripts/ops/`](scripts/ops/)（launchd 已指新路径） |
| **Admin Upload** | **已撤回**，无产品路由 |
| **生产数据** | `data/processed/fuqing_crm.duckdb` 本地，**不进 git** |
| **服务** | 127.0.0.1:5173 / 127.0.0.1:8000；当前进程尚未重启到本分支代码；Compose 容器内 backend `:8001` |

## 人工运维门禁（本分支不自动执行）

| 优先级 | 动作 | 当前门禁 |
|---|---|---|
| **P0** | 轮换曾出现在公开 PR 历史中的管理员口令 | 需 owner 决定新口令并安排 backend 重启；只清当前 PR 正文不能撤销历史泄漏 |
| **P0** | 建立 DuckDB 可恢复备份 | 旧 `copy2 + zstd` 执行路径已硬停用，但当前仍无已验证恢复点；需 ≥2× 库体积空间、停写窗口、原生一致性副本与异机恢复演练 |
| **P1** | 同步生产 venv / 重启服务 | 仅在代码合并、`git pull --ff-only`、依赖审计和发布抽检后执行 |
| **P1** | DuckDB 1.5.5 升级 | 必须排在备份恢复演练之后，独立 PR/维护窗口 |
| **P2** | 退役 1.5.4 release checker | 先核对已安装 LaunchAgent，再人工 unload/remove；不得从仓库模板重新安装 |

## 阅读顺序

1. 本文件 → 2. TECH-DEBT → 3. `docs/README.md` → 4. `CLAUDE.md`（硬门禁）→ 5. `docs/rules/L4-permanent-rules.md`（按需）
