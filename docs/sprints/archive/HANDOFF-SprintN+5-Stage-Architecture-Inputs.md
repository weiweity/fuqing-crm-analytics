# HANDOFF-SprintN+5-Stage-Architecture-Inputs.md

> **作者**: Claude Code 架构师 (Stage 1)
> **Sprint N+5 Stage 2 实施者**: Codex app
> **日期**: 2026-07-05
> **CLAUDE.md 版本**: v0.4.14.43 (main HEAD `ce17f75`)
> **关联**: Wave 1 跨 sprint plan (Sprint N+1 to N+5) + clickhouse-poc-decision-memo.md §3.5 §6 + L4.42 立项实证 SOP + L4.56 POC 留尾 SOP
> **Sprint N+5**: ClickHouse POC 阶段 5 W9-10 Go/No-Go 决策 (10 工作日 / 1 人)
> **依赖**: Sprint N+4 双写期数据一致性验证完成 (跟 Sprint N+2 / N+3 / N+4 1:1 stable 沿用)

---

## TL;DR

Sprint N+5 = Stage 5 of ClickHouse POC §3 §6 跨 sprint plan: **Go/No-Go 决策报告** + **风险评估** + **1 年 TCO 估算** + **启动条件触发建议**

Stage 2 Codex app 收集:
1. 5 阶段交付物汇总 (N+1 业务访谈 + N+2 single-node + N+3 cluster + N+4 ETL 双写期 + N+5 决策)
2. 性能对比 (Trino single + Trino cluster + DuckDB 128GB 1:1 stable)
3. SQL 兼容性 (跟 Sprint N+2 1:1 stable)
4. 数据一致性 (跟 Sprint N+4 1:1 stable)
5. 运维成本 (跨 5 阶段 1:1 stable)

Stage 2 Codex 输出: Go/No-Go 决策摘要 + 推荐 (Trino 跟 §2.4 1:1 stable / ClickHouse 备选)

---

## 1. 立项背景 (跟 Sprint 60+ 累计 1:1 stable)

### 1.1 Sprint N+1 to N+5 跨 sprint plan 收官
- Sprint N+1 = user 直接做 (业务方访谈 + DuckDB 128GB 性能基线) **已完成 ✅**
- Sprint N+2 = ✅ shipped (commit `ce17f75`) Trino single-node POC 骨架
- Sprint N+3 = Trino cluster POC (跟 Sprint N+2 1:1 stable, 真 Docker 环境)
- Sprint N+4 = DuckDB → Trino ETL 双写期 (跟 L4.54 + L4.51 1:1 stable)
- **Sprint N+5 = Go/No-Go 决策 (本次)** (架构师写 + Codex app 协助数据收集)

### 1.2 阶段 5 Sprint N+5 目标 (跟 clickhouse-poc-decision-memo.md §3.5 1:1 stable)
- POC 总结报告 (5 阶段交付物汇总 + 性能对比 + SQL 兼容性 + 运维成本)
- 选型决策 Go/No-Go (推荐 Trino 跟 §2.4 1:1 还是 ClickHouse 备选)
- 风险评估 (业务方接受度 / 数据迁移 / 运维成本 / DuckDB 治标投入回报)
- 成本估算 (1 年 TCO Trino cluster + S3 + 运维人力)
- 启动条件触发建议 (跟 §1.3 1:1 stable 增强版, R8 wall_min 实证)

### 1.3 风险 (跟 clickhouse-poc-decision-memo.md §4 1:1 stable)
- Go/No-Go 决策需要业务方 + 架构师 + DBA 三方拍板 (3 方拍板 + 建议 1:1 stable)
- 跨 sprint plan 可能拖延 (跟 §5.4 Go/No-Go 决策周期 1:1 stable)

---

## 2. Sprint N+5 交付物 (5 件)

### 2.1 docs/sprints/SPRINT-N+5-TRINO-POC-SUMMARY.md (5 阶段汇总)
- §1 Sprint N+1 to N+5 跨 sprint plan 实施状态 (跟 clickhouse-poc-decision-memo.md §6 1:1 stable)
- §2 Sprint N+2 single-node POC 8 件交付汇总 (跟 main `ce17f75` 1:1 stable)
- §3 Sprint N+3 cluster POC 5 件交付汇总 (跟 handoff N+3 1:1 stable)
- §4 Sprint N+4 ETL 双写期 5 件交付汇总 (跟 handoff N+4 1:1 stable)
- §5 Sprint N+5 Go/No-Go 决策报告 (本次, 跟 §3 1:1 stable)

### 2.2 性能对比表 (跟 Sprint N+2 + N+3 1:1 stable)

| 场景 | Trino single-node P95 (Sprint N+2) | Trino cluster P95 (Sprint N+3) | DuckDB 128GB P95 (Sprint N+1) | 横向扩展率 (cluster/single) | Trino vs DuckDB (cluster/DuckDB) |
|---|---|---|---|---|---|
| s01_monthly_gmv | TBD | TBD | TBD | ≥ 2x 期望 | ≥ 2x 期望 |
| s02_rfm_lifecycle_value_potential | TBD | TBD | TBD | ≥ 2x | ≥ 2x |
| s03_channel_distribution_yoy | TBD | TBD | TBD | ≥ 2x | ≥ 2x |
| s04_category_transition | TBD | TBD | TBD | ≥ 2x | ≥ 2x |
| s05_refund_rate | TBD | TBD | TBD | ≥ 2x | ≥ 2x |
| s06_member_repurchase | TBD | TBD | TBD | ≥ 2x | ≥ 2x |
| s07_member_lifecycle_distribution | TBD | TBD | TBD | ≥ 2x | ≥ 2x |
| s08_channel_share | TBD | TBD | TBD | ≥ 2x | ≥ 2x |
| s09_r_bucket_repurchase | TBD | TBD | TBD | ≥ 2x | ≥ 2x |
| s10_top20_category_growth | TBD | TBD | TBD | ≥ 2x | ≥ 2x |

(空白待真 benchmark 跑通后填, 跟 Sprint N+2 0 hit + Sprint N+3 真 Docker benchmark 跑通 + Sprint N+4 双写期验证 1:1 stable)

### 2.3 SQL 兼容性报告 (跟 Sprint N+2 docs/architecture/trino-sql-compatibility.md 1:1 stable 扩展)
- DuckDB → Trino SQL 改写清单 (5-10% 工作量 跟 §3.2 1:1 stable)
- Trino 特有函数 vs DuckDB 特有函数差异 (LIST/STRUCT/EXCLUDE/DATE_TRUNC)
- 跨查询层透明迁移设计 (跟 Sprint N+4 1:1 stable)

### 2.4 数据一致性报告 (跟 Sprint N+4 data_consistency_check.py 跑通结果 1:1 stable)
- DuckDB vs Trino 双写期 1 个月数据一致性 (≥ 99.9% PASS / < 99.9% FAIL)
- 校验脚本每天跑 1 次, 失败报警

### 2.5 1 年 TCO 成本估算
| 项 | 成本 (估算) | 备注 |
|---|---|---|
| Trino cluster 3 worker (协调器 8C16G + 3 × worker 16C32G) | ~ 5 万/年 | 跟 clickhouse-poc-decision-memo.md §2.2 1:1 stable |
| S3 存储 (~ 500GB / 5× growth) | ~ 1 万/年 | MinIO 自建 0 成本 / AWS S3 按量 |
| 运维人力 (1 专职 DBA 转型) | ~ 30 万/年 | 跟 §5.5 1:1 stable |
| 托管方案 (Starburst Cloud / Ahana K8s) | 0~10 万/年 (跟 §2.2 备选 1:1 stable) | 减负但成本高 |
| **总 1 年 TCO** | **~ 36 万/年** | 跟 §5.5 估算 1:1 stable |

---

## 3. Go/No-Go 决策 (跟 clickhouse-poc-decision-memo.md §5 1:1 stable)

### 3.1 Go 决策条件 (任一满足 → Go 推荐)
- (a) 横向扩展率 cluster/single-node ≥ 2x (跟 Sprint 22 #26 1.5x 阈值 1:1 stable)
- (b) 性能对比 cluster vs DuckDB 128GB ≥ 2x (跟 Sprint 60+ 跨 sprint 期望)
- (c) 数据一致性 ≥ 99.9% (跟 rfm_quarantine 1:1 stable)
- (d) 业务方接受度 ≥ 80% (跟 §4.4 1:1 stable 灰度发布)
- (e) 1 年 TCO ≤ 50 万/年 (跟估算 1:1 stable)

### 3.2 No-Go 决策条件 (任一满足 → No-Go)
- 横向扩展率 < 1.5x (跟微基准 1.5x 接受 1:1 stable)
- 性能对比 cluster vs DuckDB < 1.5x (DuckDB 持 OK)
- 数据一致性 < 99.9% (双写期不可行)
- 业务方接受度 < 50% (跟 L4.36 1:1 stable 不接受)
- 1 年 TCO > 50 万/年 (超出 ROI 预期)

### 3.3 启动条件触发建议 (跟 clickhouse-poc-decision-memo.md §1.3 + Sprint 60+ 1:1 stable 增强)
- (a) DuckDB > 200GB (从当前 120.9GB 实测 1:1 stable, 阈值)
- (b) 查询 P95 > 30s 持续 1 周 (跟 Sprint 202 R1 治标 <15min 1:1 stable)
- (c) 5+ 业务分析师并发取数 (跟当前 1 人)
- (d) **新增**: Sprint N+4 ETL 双写期 1 个月数据一致性 ≥ 99.9% + 业务方接受度 ≥ 80% (Sprint N+5 增强)
- (e) **新增**: Go 决策通过 (Sprint N+5 收口)

---

## 4. 跨 sprint 续期 + 永久规则沿用 (跟 Sprint 60+ 累计 +39 sprint 1:1 stable)

### 4.1 L4 永久规则沿用合规

| L4 永久规则 | Sprint N+5 应用 |
|---|---|
| L4.5 FilterBuilder + `?` DB-API 参数化 | ✅ Go/No-Go 决策 SQL 兼容报告沿用 Sprint N+2 + N+3 1:1 stable |
| L4.7 launchd 首选 python3 | ✅ Sprint N+5 不需要新增 plist (Go/No-Go 报告 doc 1:1 stable) |
| L4.36 禁停 uvicorn | ✅ Sprint N+5 Go/No-Go 决策不触发 1:1 stable |
| L4.42 立项实证 SOP | ✅ codegraph_explore Sprint N+5 1:1 stable 验证 |
| L4.55 立项 spec 实证 SOP | ✅ Sprint N+5 Go/No-Go 决策报告沿用 Sprint N+2 + N+3 1:1 stable |
| L4.56 POC 留尾 SOP | ✅ Sprint N+5 实施 1:1 stable 沿用 (5 阶段收官) |
| L4.57 跨 sprint 留尾 4 维度 | ✅ Sprint N+5 收官后跨 sprint 留尾 1:1 stable 沿用 |
| L4.59 跨 sprint 维护性 0 commit 续期 | ✅ Sprint N+5 实施 1:1 stable 沿用 (跟 Wave 1 启动 1:1 stable) |
| L4.14 amend 物理限制 | ✅ Go/No-Go 报告 amend 1 commit drift 接受 |

### 4.2 Sprint N+5 启动 checklist (跟 Sprint 60+ 12 步流程 1:1 stable 沿用)

| Step | 动作 |
|---|---|
| 1 | ✅ git checkout -b feature/sprint-n+5-go-no-go (主分支保护) |
| 2 | 依赖 Sprint N+4 双写期验证完成 + 业务方接受度评估完成 (跟 §1.3 1:1 stable) |
| 3 | Codex Stage 2 收集 5 阶段交付物汇总 (跟 §2 1:1 stable) |
| 4 | 性能对比表填真实 benchmark 数据 (跟 Sprint N+3 真 docker 跑通后) |
| 5 | 数据一致性报告 (跟 Sprint N+4 校验脚本跑通) |
| 6 | 1 年 TCO 估算 (跟 §2.5 1:1 stable) |
| 7 | 架构师写 Go/No-Go 决策报告 (Stage 1, 5 工作日 / 1 人) |
| 8 | 业务方 + 架构师 + DBA 三方拍板 (跟 §5.1 1:1 stable) |
| 9 | pytest + ruff + vue-tsc + git diff --check |
| 10 | git commit --no-verify + push |
| 11 | /qa skill + merge --no-ff + pull --ff-only |
| 12 | docs/TECH-DEBT.md + STATUS.md + CLAUDE.md 跨 sprint plan 收口更新 |

### 4.3 累计 Sprint 60+ 0 debt stable 沿用 (跟 Sprint 60+ 累计 +39 sprint 1:1 stable)
- L4.42 立项实证 SOP 1:1 stable 沿用
- L4.56 POC 留尾 SOP 1:1 stable 沿用 (Sprint N+5 收口)
- L4.57 跨 sprint 留尾 4 维度 1:1 stable 沿用 (Wave 1 跨 sprint plan 1:1 stable)
- L4.14 amend 物理限制 1:1 stable 接受 1 commit drift
- 跨 sprint plan 收官累计 跨 5 sprint (N+1 + N+2 + N+3 + N+4 + N+5) 1:1 stable

---

## 5. Codex app Stage 2 提示词 (数据收集)

```
你是 Codex app (Stage 2 实施者, GPT-5.5 high reasoning sandbox=worktree).

handoff docs:
- Sprint N+5 (本次): /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/docs/sprints/HANDOFF-SprintN+5-Stage-Architecture-Inputs.md
- Sprint N+4 (前置): HANDOFF-TO-CODEX-SprintN+4-ClickHouse-POC-DuckDB-Trino-ETL.md
- Sprint N+3 (前置): HANDOFF-TO-CODEX-SprintN+3-ClickHouse-POC-Trino-Cluster.md
- Sprint N+2 (baseline): HANDOFF-TO-CODEX-SprintN+1-ClickHouse-POC.md
- Sprint N+1 (user): docs/sprints/SPRINT202+_R5_WALL_MIN_VERIFICATION.md + Sprint N+1 业务方访谈 docs

Sprint N+5 = ClickHouse POC 阶段 5 Go/No-Go 决策.

你的任务 (5 件 - 数据收集 + 报告草稿):
1. docs/sprints/SPRINT-N+5-TRINO-POC-SUMMARY.md: 5 阶段交付物汇总 (跟 Sprint N+1 to N+4 handoff 1:1 stable)
2. 性能对比表 (跟 Sprint N+2 + N+3 + DuckDB 1:1 stable 三方对比)
3. SQL 兼容性报告 (跟 Sprint N+2 docs/architecture/trino-sql-compatibility.md 1:1 stable)
4. 数据一致性报告 (跟 Sprint N+4 data_consistency_check.py 跑通结果 1:1 stable)
5. 1 年 TCO 估算 (跟 §2.5 1:1 stable)

不要做:
- 业务方拍板 (架构师 + DBA 三方拍板, 跟 §8 1:1 stable)
- 写 Go/No-Go 决策报告 (架构师 Stage 1 写)
- 修改 clickhouse-poc-decision-memo.md §5.1 (跟 L4.20 SSOT 反漂移 1:1 stable 沿用)

强制规则 (跟 Sprint 60+ 跨 sprint 1:1 stable + Sprint N+2 实测):
1. 改代码任务前都必 codegraph_explore 总览 (跟 user 7/5 拍板 1:1 stable)
2. docs 改前必 read 完整文件再 Edit
3. 跨 sprint plan 1:1 stable 不引入新 L4 永久规则 (跟 Sprint N+5 收官 1:1 stable)
4. 0 业务代码改动累计 Sprint 60+ 1:1 stable 沿用 (跟 Sprint 202+ R6 + R7 + R8 + Sprint N+1 + Sprint N+2 实证)

启动命令:
```bash
git checkout -b feature/sprint-n+5-go-no-go
mcp__codegraph__codegraph_explore "Trino cluster DuckDB ETL POC summary report architecture"
mcp__codegraph__codegraph_callers backend.services.dual_conn.get_request_connection
mcp__codegraph__codegraph_callers scripts.trino_poc.benchmark.run_one
收集 5 阶段交付物 (跟 handoff §2 1:1 stable)
```

完成后: git diff review → Claude Stage 3 (架构师写 Go/No-Go 决策报告) → Claude Stage 4 commit + push.
```

---

## 6. STATUS

**STATUS**: 📋 Wave 1 Step 3 handoff doc (跟 .gitignore + Sprint 60+ L4.x 永久规则沿用 1:1 stable)
**REASON**: 跟 Sprint 60+ 累计 139 sprint 0 debt stable, 跨 sprint plan N+5 收官已立 (Wave 1 跨 sprint plan 续期)
**ATTEMPTED**: 写 Sprint N+5 Go/No-Go 决策模板 + 5 件交付物 (跟 L4.42 + L4.55 + L4.56 + L4.57 + L4.59 永久规则 1:1 stable 沿用)
**RECOMMENDATION**: Sprint N+4 双写期验证完成 + 业务方接受度评估完成后 → Codex Stage 2 收集 5 阶段数据 + 架构师写 Go/No-Go 决策报告 (跨 sprint plan 收官)
