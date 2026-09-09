# 项目状态 (Project Status)

> **短表 SSOT**。编年：[`docs/history/STATUS-HISTORY.md`](docs/history/STATUS-HISTORY.md) · 债：`docs/TECH-DEBT.md` · 文档：`docs/README.md`

## 当前快照（2026-09-09 本地原生闭环）

| 项 | 值 |
|---|---|
| **VERSION** | `0.7.0.0`（#108 已合并） |
| **main** | `d95e504`（#108）；首购原生与 W4 最小层已合入 |
| **进行中分支** | `codex/parallel-query-w4-integration`：已随 #108 合并，保留分支与交接证据；本机 DSH 合成演示运行中 |
| **黑客松主链** | 旧 Mission 演示仍是 `GET /today → 增长董事会 → 问数 → 审批 → DRAFT_EXPORT`（8000/5173）。B0 查询资产为 opt-in `--native-query-assets`；首购原生为 `--native-first-purchase`（4315–4319），产品仍 PARTIAL |
| **可合并 CI** | required：`lint` `test` `ground-truth-lint` `contract-filterbuilder-lint` `frontend` `dependency-audit` `docker-smoke` `b0-contract-build` `merge-gate`。skip 不算失败。e2e 非 PR 门禁 |
| **定时 CI** | Nightly / Weekly 与 PR 同口径；timeout 45min |
| **供应链文档** | `docs/operating/supply-chain.md` · `github-governance-checklist.md` · `docker-ports-and-images.md` |
| **Actions 策略** | 仅 GitHub-owned Actions；workflow 动作为 40 位 commit SHA |
| **ruff** | 锁 `0.16.6`；`pyproject.toml` `lint.select = ["E4","E7","E9","F"]`（保持 0.15 默认 59 条，不启用 0.16 的 413 条） |
| **债** | 产品仍 PARTIAL；首购 catalog 已按合成 native/HTTP/合同证据升为 SUPPORTED_CONTRACT；候选人群仍 DEFERRED。W4 基础特征共享读取、W5 特征产物原子发布已实现，发布状态以本轮 PR 为准；完整 W4/整仓发布、真实模型与完整业务验收未完成 |
| **运维脚本** | [`scripts/ops/`](scripts/ops/)（launchd 已指新路径） |
| **Admin Upload** | **已撤回**，无产品路由 |
| **生产数据** | `data/processed/fuqing_crm.duckdb` 本地，**不进 git** |
| **服务** | 核验时 PID 36717/36727 仍监听 8000/5173，cwd 指向已删除的旧演示目录；不是当前主线运行证据。本轮未停止或重启 |
| **未完成** | 真实模型原生浏览器、整仓发布、多人/容量/业务 UAT、公网仍未完成；历史三次 supervisor 退出 UNKNOWN |

发布 CI：#108 的 `34310344976` 必需检查通过，按路径规则跳过项不算运行通过；已合并为 `d95e504`。完整业务验收仍开放。本轮本地统一 pipeline：428 项 Python、223 项源 Node、类型检查、编译后 49 项（含干净重建）通过。OCR Medium 与浏览器发现的终态总结上下文修复后已串行重跑通过。原生 DSH 浏览器 stub 合成闭环已通过（查询→总结→保存→加入驾驶舱→脱离会话重读）；补修成功后总结上下文，不代表真实模型或业务 UAT。见 [首购原生闭环](docs/hackathon/FIRST-PURCHASE-NATIVE-LOOP-2026-09-09.md)、[交接](docs/hackathon/FIRST-PURCHASE-NATIVE-HANDOFF-2026-09-09.md) 与 [并行集成清单](docs/hackathon/PARALLEL-QUERY-W4-INTEGRATION-2026-09-08.md)。本地证据在 `.context/parallel-round2-review/evidence-2026-09-09/`。
本轮 W4/W5 本地接缝与分支核对见 [实施记录](docs/hackathon/W4-W5-LOCAL-2026-09-09.md)；临停本轮 DSH 后 Loader 与干净重建通过，历史端口冲突证据保留。

## 历史人工运维门禁（待重新核验，不自动执行）

下表保留历史记录，不将旧版本、运行环境或备份状况当成今日已核实事实。

| 优先级 | 动作 | 当前门禁 |
|---|---|---|
| **P0** | 轮换曾出现在公开 PR 历史中的管理员口令 | 需 owner 决定新口令并安排 backend 重启；只清当前 PR 正文不能撤销历史泄漏 |
| **P0** | 建立 DuckDB 可恢复备份 | 旧 `copy2 + zstd` 执行路径已硬停用，但当前仍无已验证恢复点；需 ≥2× 库体积空间、停写窗口、原生一致性副本与异机恢复演练 |
| **P1** | 同步生产 venv / 重启服务 | 仅在代码合并、`git pull --ff-only`、依赖审计和发布抽检后执行 |
| **P1** | DuckDB 1.5.5 升级 | 必须排在备份恢复演练之后，独立 PR/维护窗口 |
| **P2** | 退役 1.5.4 release checker | 先核对已安装 LaunchAgent，再人工 unload/remove；不得从仓库模板重新安装 |

阅读顺序：1. 本文件 → 2. TECH-DEBT → 3. `docs/README.md` → 4. `AGENTS.md`（行为规则）→ 5. `docs/rules/L4-permanent-rules.md`（按需）；第二轮历史结果：资产后端接线完成，pipeline 418 项 Python、215 项源 Node 测试及类型/构建/干净重建通过。当时原生候选未导入，见 [第二轮复核](docs/hackathon/PARALLEL-ROUND2-REVIEW-2026-09-08.md)。再上一轮 405 项 Python 见 [集成结果](docs/hackathon/PARALLEL-INTEGRATION-RESULT-2026-09-08.md)，均不代表远端 CI 或 native UI 新验收。
