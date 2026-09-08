# 项目状态 (Project Status)

> **短表 SSOT**。编年：[`docs/history/STATUS-HISTORY.md`](docs/history/STATUS-HISTORY.md) · 债：`docs/TECH-DEBT.md` · 文档：`docs/README.md`

## 当前快照（2026-09-08 overlay 测试）

| 项 | 值 |
|---|---|
| **VERSION** | `0.6.1.0`（本分支 `VERSION`；`origin/main` 仍为 `0.6.0.0`） |
| **main** | `1a785d1`（#101 docs closeout）。#100 查询资产驾驶舱及 #85–#99、#92 已合入。开放 PR **0** |
| **进行中分支** | `test/cockpit-overlay-gap`：overlay 撤销整板/加入/无板创建/409 编译后 DOM；尚无 PR |
| **黑客松主链** | 旧 Mission 演示仍是 `GET /today → 增长董事会 → 问数 → 审批 → DRAFT_EXPORT`（8000/5173）。B0 查询资产为 opt-in `--native-query-assets`（4315–4319），产品仍 PARTIAL |
| **可合并 CI** | required：`lint` `test` `ground-truth-lint` `contract-filterbuilder-lint` `frontend` `dependency-audit` `docker-smoke` `b0-contract-build` `merge-gate`。skip 不算失败。e2e 非 PR 门禁 |
| **定时 CI** | Nightly / Weekly 与 PR 同口径；timeout 45min |
| **供应链文档** | `docs/operating/supply-chain.md` · `github-governance-checklist.md` · `docker-ports-and-images.md` |
| **Actions 策略** | 仅 GitHub-owned Actions；workflow 动作为 40 位 commit SHA |
| **ruff** | 锁 `0.16.6`；`pyproject.toml` `lint.select = ["E4","E7","E9","F"]`（保持 0.15 默认 59 条，不启用 0.16 的 413 条） |
| **债** | [`docs/TECH-DEBT.md`](docs/TECH-DEBT.md)。本分支已补 overlay 撤销整板/加入/无板创建/409 编译后 DOM；产品仍 PARTIAL。公网提交、W4/W5 见 [总待办](docs/hackathon/PLAN-CLOSEOUT-2026-09-05.md) |
| **运维脚本** | [`scripts/ops/`](scripts/ops/)（launchd 已指新路径） |
| **Admin Upload** | **已撤回**，无产品路由 |
| **生产数据** | `data/processed/fuqing_crm.duckdb` 本地，**不进 git** |
| **服务** | 旧 CRM 演示 127.0.0.1:5173 / 8000；B0 隔离 4315–4319。不要停别人的 8000/5173 |
| **未完成** | 产品仍 PARTIAL；公网部署/网址提交仍暂缓；历史三次 supervisor 退出仍 UNKNOWN。本分支 overlay 测试尚未合入 `main` |

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
