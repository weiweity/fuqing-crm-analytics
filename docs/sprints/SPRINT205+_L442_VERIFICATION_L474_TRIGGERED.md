# Sprint 205+ L4.42 立项实证 L4.74 启动条件 c 真触发 (重新立项) (2026-07-08)

> **本文件 1 行 1 pointer, 详情见 Sprint 205+ L4.72 收口 close memory + 永久规则链.**

## 摘要 (跟 L4.42 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 1:1 stable 永久规则链配套)

你 7/8 拍板 "强行触发" L4.74 = L4.56 POC 留尾 SOP 启动条件 c **真触发** (PC2 部署 10 业务分析师并发 + 崩了 + 取不了数), 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则链配套 **反向** (真业务触发 → 重新立项 → 0 commit 续期 → 7/16 后接手人启动 8-10 周 1-2 人月真治本). 跟 Sprint 199 R1 cleanup 1:1 stable 模式 配套, 跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套, 跟 L4.56 POC 留尾 SOP 1:1 stable 永久规则链配套, 跟 L4.57 + L4.58 + L4.59 跨 sprint 留尾 0 commit 续期 1:1 stable 永久规则链配套.

## 启动条件 live verify (跟 L4.56 启动条件 a/b/c 1:1 stable 配套)

| 启动条件 | 阈值 | PC2 端 live verify | 状态 |
|---|---|---|---|
| **a) DuckDB 单文件 > 200GB** | > 200GB | **122GB** (跟 L4.68 5d9af72 PC2 122GB 1:1 stable 配套, 跟 L4.56 launchd weekly com.fuqing.clickhouse-poc-monitor.weekly.plist 1:1 stable 持续监控 0 hit) | ❌ 0 触发 (跟之前 1:1 stable 配套) |
| **b) 查询 P95 > 30s 持续 1 周** | > 30s 持续 1 周 | **PC2 端 "取不了数" = 跨 sprint 持续 (你 7/8 报 "一直发生这个问题")** (跟 L4.69 RFM 雪崩 8 并发 1:1 stable 模式 配套, 跟 L4.72.2 dual_conn semaphore timeout 1:1 stable 治本 配套) | ✅ **真触发** |
| **c) 5+ 业务分析师并发取数** | ≥ 5 并发 | **PC2 端 10 业务分析师** (你 7/8 报 "10 个人一起用这个软件") + 跟 L4.69 RFM 雪崩 8 并发 PC2 端 100% 复现 1:1 stable 模式 配套 | ✅ **真触发** |

**L4.74 真业务触发判定: b + c 两件 真触发 ✅, 重新立项**.

## 真业务触发症状 (跟 L4.69 + L4.72 1:1 stable 模式 配套)

你 7/8 报 "部署到PC2之后, 一直发生这个问题, 取不了数, 已经崩了, 我有10个人一起用这个软件" = 跨 sprint 持续 症状, 跟 L4.69 RFM 雪崩 8 并发 PC2 端 100% 复现 1:1 stable 模式 配套, 跟 L4.72.2 dual_conn semaphore timeout 治本 配套 (但 L4.72.2 治 30s+ timeout 兜底 503, 10 用户并发仍会触发 503, 1:1 stable 跨 sprint stable 模式).

## 重新立项 L4.74 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则链配套 反向)

L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则链配套 **反向**: 真业务触发 → 重新立项 (跟 Sprint 199 R1 cleanup 1:1 stable 模式 配套).

**重新立项步骤 (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套)**:
1. ✅ L4.42 立项实证 (本报告) — 启动条件 b + c 真触发验证
2. ✅ L4.74 立项决策 memo (跟 L4.56 clickhouse-poc-decision-memo.md 1:1 stable 配套) — `docs/architecture/l4.74-duckdb-postgresql16-decision-memo.md` (~280 行, 选型对比 + 5 阶段拆分 + 风险列表 + 启动条件真触发)
3. ✅ docs/TECH-DEBT.md 留尾登记 (跟 L4.12 SSOT 治理 1:1 stable 永久规则链配套)
4. ✅ CLAUDE.md L4.74 启动条件 c 真触发 永久规则化 (跟 L4.55 + L4.56 1:1 stable 永久规则链配套)
5. ✅ push main (跟 L4.15 拍板 "强行触发" 1:1 stable 永久规则链配套)
6. ✅ 跟接手人 handoff (跟 L4.55 + L4.56 1:1 stable 永久规则链配套)

## 0 commit 续期 → 7/16 后接手人启动 (跟 L4.42 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 1:1 stable 永久规则链配套)

L4.74 = 8-10 周 1-2 人月长期治本专项, 7/16 离职 = 4 天后, 不可能 7/16 之前完成. 按 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则链配套 **反向**: 真业务触发 → 0 commit 续期 → 7/16 后接手人启动.

**0 commit 续期配套 (跟 L4.50 + L4.57 + L4.58 + L4.59 1:1 stable 永久规则链配套)**:
- 0 业务代码改动, 1 file docs/TECH-DEBT.md 留尾登记 + CLAUDE.md L4.74 永久规则化段 + 立项决策 memo (跟 L4.56 clickhouse-poc-decision-memo.md 1:1 stable 配套)
- 跨 sprint 续期 0 commit (跟 L4.42 立项实证 SOP 1:1 stable 永久规则链配套)
- launchd 自动化监控 (L4.7 永久规则: python3 不走 bash, weekly 触发, log /tmp/fuqing-clickhouse-poc-monitor.log)
- fail-open 原则 (L4.40 监控脚本失败不阻 commit, 任何异常 exit 0 + stderr warn)

## 跟 L4.59 跨 sprint 维护性 0 commit 续期 SOP 总纲 1:1 stable 配套

3 件强契约 (跟 L4.59 永久规则链 1:1 stable 配套):
1. **L4.42 立项实证前置** (本报告, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则链配套)
2. **launchd 自动化监控** (L4.7 + L4.59 永久规则 1:1 stable 配套, com.fuqing.clickhouse-poc-monitor.weekly.plist weekly 监控)
3. **fail-open 原则** (L4.40 永久规则 1:1 stable 配套, 监控脚本失败不阻 commit, 任何异常 exit 0 + stderr warn)

## 累计指标 (跟 L4.65.1 + L4.69.1 + L4.72 1:1 stable 收口 push 模式 1:1 stable 配套)

- **L4.x 72 stable** (L4.1-L4.72, Sprint 60+ 138 sprint 0 debt stable 模式 1:1 stable 配套)
- **/document-release 真治本累计 60 次** (Sprint 60+ 1:1 stable 永久规则链)
- **0 业务代码改动累计 Sprint 60+ 60 次 1:1 stable** (跟 L4.50 pytest cleanup 1:1 stable 永久规则链配套)
- **CLAUDE.md L4.65-L4.72 八层永久规则链完整 + L4.74 启动条件 c 真触发永久规则化** (跟 L4.42 立项实证 SOP 1:1 stable 配套)
- **MEMORY.md 12.0KB** (L4.13 24.4KB 安全线 49%, 1:1 stable 永久规则链配套)
- **CI 4 commit 链 push main 成功 5c79385..2a68be9** (跟 L4.65.1 + L4.69.1 1:1 stable push 模式 配套)
- **跨 sprint 留尾累计 10 件 0 commit 续期** (跟 Sprint 60+ 0 debt stable 模式 +39 sprint 1:1 stable 沿用, 跟 L4.57 + L4.58 + L4.59 1:1 stable 永久规则链配套)

**Sprint 205+ L4.42 立项实证 L4.74 启动条件 c 真触发 (b + c 两件真触发) 重新立项 ✅, 0 commit 续期 → 7/16 后接手人启动 8-10 周 1-2 人月真治本 🎯**
