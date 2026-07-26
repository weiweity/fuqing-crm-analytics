# 技术债台账 (Technical Debt Ledger)

> **唯一开放债短表**。历史：[`history/TECH-DEBT-HISTORY.md`](history/TECH-DEBT-HISTORY.md)

**最后更新**: 2026-07-26 合并后安全复核
**main 基线**: `9bedd40`（本地残留修复分支未 push）

---

## 已触发、必须排期

| ID | 级 | 当前事实 / 风险 | 完成条件 | 门禁 / 依赖 |
|---|---|---|---|---|
| **#SEC-credential-rotate** | **P0** | 现用管理员口令曾出现在公开 PR 正文；当前正文已清理，但历史副本不能视为已撤销 | 轮换全部受影响口令，重启 backend，旧口令登录失败，新口令登录成功 | owner 选定口令与维护窗口；不得把新值写入 Git/PR |
| **#OPS-backup-recovery** | **P0** | 复核时备份目录无可用恢复点；旧 `shutil.copy2 + zstd` 路径已硬停用，但尚无替代的可恢复备份 | DuckDB 原生一致性副本完成、SHA/表级抽检通过、另一目录/机器恢复演练通过、RPO/RTO 有记录 | 需要 ≥2× 数据库体积 + 20% 空间、停写窗口和备份介质；旧 launchd 不得安装 |
| **#OPS-runtime-sync** | **P1** | 本机运行 venv 未与新 lock 同步，当前 uvicorn 仍是合并前进程 | 合并后 `git pull --ff-only`，按 lock 同步，`pip check`/health/登录/关键看板抽检通过 | 依赖代码 merge + owner 发布窗口 |
| **#DB-duckdb-1.5.5** | **P1** | lock 仍为 1.5.3；1.5.5 已是稳定版，存在升级价值但禁止无恢复点升级 | 独立 PR 更新 pins；副本兼容、全量测试、ETL 和 24h 观察通过 | **硬依赖 #OPS-backup-recovery 完成** |
| **#OPS-release-check-retire** | **P2** | 旧 checker 仍等待已过期的 1.5.4 目标，且历史 launchd 执行曾 exit 126 | 核对宿主已安装实例并人工 unload/remove；仓库模板保持 legacy 标识 | 删除/卸载是外部状态变更，需 owner 授权 |
| **#SUPPLY-dev-audit** | **P2** | `npm audit --omit=dev` 为 0；完整 audit 仍有 dev/build/test 链告警 | 在不破坏 Vite/OpenAPI/Vitest 的前提下升级或替换相关工具链；生产审计持续为 0 | 只按可利用路径和上游兼容性排期，不用 `--force` |

---

## 条件触发型延期项

| ID | 级 | 说明 | **触发条件**（未触发 = 不立项） |
|---|---|---|---|
| **#C7-deselect** | P2 | CI 仍 deselect C 类 7 条 | 业务改 W4/RFM 预计算口径，**或**交付「CI 合成 fixture」 |
| **#preflight-env** | P2 | 无独立预发 | 有预发机 **或** 抽样 DuckDB 方案获批 |
| **#L4.74-PG** | — | PG/分布式 0 commit 收口 | 启动条件 a/b/c 任一真触发（见 architecture memo） |

> 本节不是立即待办；上方“已触发、必须排期”才是当前维修队列。
> SSOT deselect：`scripts/ci/pytest_c_class_deselects.txt`

---

## 本目标已闭环

| ID | 结果 |
|---|---|
| **#STATUS-HISTORY** | STATUS 短表 + history |
| **#CLAUDE-L4-sink** | L4 → `docs/rules/` |
| **#scripts-ops** | monitors → `scripts/ops/` + launchd 路径同步 |
| **#Admin-Upload-WITHDRAWN** | 产品面删除（router/service/view/e2e/test）；**不重开** |
| **#e2e-data** | 夹具能力保留（`FQ_CRM_TEST_MODE` + seed）；**PR 门禁已撤回**（2026-07-19 分层：可选 `e2e-smoke.yml`） |

---

## 工作流契约

- **可合并**: **lint + test 必绿**（e2e **不**挡 PR merge；`docs/operating/team-workflow-v1.md`）
- **可选 UI smoke**: `.github/workflows/e2e-smoke.yml`（`workflow_dispatch` + 工作日 schedule；`requirements-e2e.txt` + login 壳层）
- **整洁**: `docs/operating/project-hygiene.md`
- **运维监控入口**: `scripts/ops/` + `scripts/launchd/`

## 维护

1. 新债必须有触发条件或立即排期；禁止「以后再清」空行  
2. 长编年只进 `history/`  
3. 撤回功能优先删代码，不留死路由  
