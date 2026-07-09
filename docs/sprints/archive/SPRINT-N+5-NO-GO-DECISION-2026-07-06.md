# Sprint N+5 — Go/No-Go 拍板: **NO-GO** (System Locked Down + Handoff Advisory)

> **作者**: Claude Code 架构师 (Stage 1)
> **日期**: 2026-07-06
> **状态**: 🔴 **NO-GO** (跟 system locked down + handoff advisory 1:1 stable 沿用)
> **前置**: `docs/sprints/SPRINT-N+5-GO-DECISION-2026-07-06.md` (本次反转前 doc, 详见 §6 反转理由)
> **关联**:
> - docs/sprints/SPRINT-N+5-TRINO-POC-SUMMARY.md (Go 推荐条件 5 项 + TCO + 6 风险评估)
> - docs/sprints/SPRINT-N+1-DUCKDB-BASELINE-2026-07.md (W2 baseline median P95=0.068s)
> - docs/sprints/SPRINT-N+1-BUSINESS-INTERVIEW-REQUIREMENTS.md (21 答复 + 5 SCENARIOS 校准)
> - docs/architecture/clickhouse-poc-decision-memo.md (Sprint 201+ ClickHouse/Trino POC 立项决策)
> - docs/sprints/SPRINT-N-PLUS-WAVE1-CROSS-STABLE-2026-07-06.md (跨 sprint 留尾 4 维度续期)

---

## 1. 拍板结论: **NO-GO** (System Locked Down + Handoff Advisory)

跟 3 个新约束 1:1 stable 沿用,**反转 Sprint N+5 Go 拍板 → No-Go**:

| 新约束 | 反转理由 |
|---|---|
| **在职时间 < 8-10 周 1-2 人月 实施时间** | Sprint N+3+N+4 实施时间 远超 在职剩余时间, **实施不完 = 留烂摊子** |
| **系统写死 (system locked down)** | 不接受新功能, 不接受新风险, **跟 Go 迁移 哲学完全反** |
| **DuckDB 128GB 现状跑得好** | W2 baseline median P95=0.068s, 跟业务方期望 <2s 满足 **73x headroom**, **没有紧迫性** |

跟 Sprint 60+ L4.x 永久规则沿用 1:1 stable, **Boring by default** + **Reversibility preference** + **Essential vs accidental complexity** + **Two-week smell test** 4 大 cognitive pattern 1:1 stable 验证:
- ✅ Boring by default: 0 改动 = 0 新增风险
- ✅ Reversibility preference: No-Go 永远可由接手人 反转 → Go
- ✅ Essential vs accidental complexity: 当前 DuckDB 128GB working, 无 essential complexity 需修
- ✅ Two-week smell test: 任何 8-10 周 迁移 跟 smell test 不符

---

## 2. 反转理由 (跟 Go 拍板 5 项条件 1:1 stable 对比)

### 2.1 跟原 Go 推荐 5 项条件对比

| 原 Go 条件 | 现状 (跟 Go 1:1 stable) | 反转后决策 |
|---|---|---|
| (a) 性能: W2 P95=0.068s <2s 73x headroom | ✅ 满足 | 维持现状 DuckDB 128GB |
| (b) 业务方 Q20 接受 + Q19 灰度 + Q18 双写期 | ✅ 接受 | 业务方不急, 接手人决定 |
| (c) TCO ~36 万/年 ≤ 50 万/年 | ✅ 满足 | 但 8-10 周 1-2 人月 实施成本 ≠ TCO |
| (d) 数据一致性脚本 ready | ✅ ready | scripts 保留 接手人用 |
| (e) 6 风险评估可控 | ✅ 可控 | 但 新增 7/8 风险 (跟离职 + 写死 冲突) |

### 2.2 新增风险评估 (跟 Go 拍板 6 风险评估 + 2 件新风险 1:1 stable)

| 风险 | 等级 | 跟原评估对比 |
|---|---|---|
| (1) Trino SQL 兼容性 | 中 | (维持原) |
| (2) 数据一致性 | 中 | (维持原) |
| (3) 运维成本 | 中 → **高** | 接手人要从头学 Trino, 运维负担加重 |
| (4) 业务方接受度 | 低 | (维持原) |
| (5) ClickHouse POC 启动条件触发 | 低 | (维持原) |
| (6) Docker daemon 跟 macOS 网络 sandbox | 中 | (维持原) |
| **(7) 离职前发起 Trino 迁移 = 烂摊子** | (没考虑) → **致命** | 接手人继承 半完成迁移 = 0 working state |
| **(8) 跟"系统写死"哲学完全冲突** | (没考虑) → **致命** | 写死 = 不变, Go 迁移 = 巨变 |

**新增 2 件致命风险, 跟原 6 件风险 1:1 stable 累计 = 8 风险**, **远超过可控 6 风险评估 阈值**。

---

## 3. No-Go 决定 (跟 Wave 1 evidence 1:1 stable 沿用)

### 3.1 维持现状 DuckDB 128GB ✅

跟 W2 baseline + 21 业务方答复 + RFM_DEFINITIONS.md 业务 SSOT 1:1 stable 沿用:

| 维度 | 现状 | 业务方接受度 |
|---|---|---|
| DuckDB 128GB median P95=0.068s | ✅ <2s 满足 73x headroom | Q17 "我才满意" 满足 |
| top 频繁 s02 RFM P95=1.67s | ✅ <5s 接受 | Q12 "5s 内接受" 满足 |
| 频繁 s09 R 区间 P95=0.29s | ✅ <5s 接受 | RFM_DEFINITIONS.md SSOT 满足 |
| 10 场景全部 <2s | ✅ 全部满足 | Q17 <2s 满意 满足 |

**DuckDB 128GB 维持现状 = 0 改动 = 0 风险 = 离职前最干净状态**。

### 3.2 跨 sprint 留尾 4 维度 → Handoff Advisory

跟 L4.57 + L4.58 永久规则沿用 1:1 stable, 但 **状态从"跨 sprint 续期"改为"handoff advisory"**:

| 件 | 原状态 | 反转后状态 | 接手人路径 |
|---|---|---|---|
| Sprint N+3 cluster benchmark | ⏸ 跨 sprint 续期 | 📋 Handoff advisory | 接手人决定是否真实施 |
| Sprint N+4 ETL 双写期 | ⏸ 跨 sprint 续期 | 📋 Handoff advisory | 接手人决定是否真实施 |
| ClickHouse POC 启动条件监控 | ⏸ 0 触发续期 | ⏸ 0 触发续期 (维持) | launchd weekly 自动监控 |
| Stage D 灰度 + Stage E 全量切换 | ⏸ 跨 sprint 续期 | 📋 Handoff advisory | 接手人决定 |

跟 L4.57 + L4.58 永久规则沿用 1:1 stable, **状态保持 0 commit 续期**, 但 **类型从"积极推进"改成"advisory 给接手人"**。

---

## 4. Handoff Advisory 给接手人 (跟 Sprint 60+ 跨 sprint 维护性 SOP 1:1 stable)

### 4.1 接手人继承的 working state

跟 Sprint 60+ L4.x 永久规则沿用 1:1 stable, **接手人 0 改动继承**:

1. ✅ DuckDB 128GB working system (跟 W2 baseline median P95=0.068s 1:1 stable)
2. ✅ backend/services/ + scripts/etl/ + scripts/ad_hoc_queries/ (跟 L4.5 FilterBuilder + L4.19 channel alias + L4.51 Read-Write Splitting + L4.54 ETL 文件分桶 1:1 stable)
3. ✅ frontend-vue3/ (跟 L4.22 前端 sprint 收口 rebuild dist + kill 旧 vite preview 1:1 stable)
4. ✅ launchd plist (跟 L4.7 + L4.62 1:1 stable)
5. ✅ pytest baseline 1057/7/3 → 1079/7/0 (跟 Sprint 60+ 累计 60+ 次 0 业务代码改动 1:1 stable)
6. ✅ Wave 1 5/5 阶段 docs (跟 L4.20 SSOT 反漂移 1:1 stable)
7. ✅ TECH-DEBT.md 留尾登记 (跟 L4.12 留尾 SSOT 治理 1:1 stable)

### 4.2 接手人决定路径 (advisory, 非 mandate)

跟"系统写死"哲学 1:1 stable, **接手人 决定 是否** 启动 Trino 迁移:

**接手人 不启动 迁移** (跟 system locked down 1:1 stable 沿用, 推荐):
- 维持 DuckDB 128GB 现状
- 继续用 W2 baseline 性能 (跟 Q17 <2s 满足 73x headroom)
- 等 ClickHouse POC 启动条件触发 (DuckDB > 200GB / P95 > 30s 持续 1 周 / 5+ 业务分析师并发)
- 0 触发 → 0 启动 → 维持现状

**接手人 启动 迁移** (如果业务方需求变化):
- 读 `docs/sprints/SPRINT-N+5-GO-DECISION-2026-07-06.md` (Go 推荐条件)
- 读 `docs/sprints/SPRINT-N+5-TRINO-POC-SUMMARY.md` (TCO + 6 风险评估)
- 走完整 12 步流程
- 跟 L4.42 立项实证 + L4.55 立项 spec 实证 + L4.56 POC 留尾 SOP + L4.57 跨 sprint 留尾 + L4.58 跑批 wall_min + L4.40 fail-open 永久规则沿用 1:1 stable

---

## 5. Sprint 60+ L4.x 永久规则沿用合规 (跟累计 +50 sprint 1:1 stable)

| L4 永久规则 | 本 doc 应用 |
|---|---|
| L4.40 fail-open | ✅ 反转理由接受 fail-open (Go → No-Go 状态变化接受) |
| L4.42 立项实证 SOP | ✅ git log/grep 验证 W2 baseline + Q20 + TCO + 6+2 风险 |
| L4.55 立项 spec 实证 | ✅ 3 件新约束 (在职时间 / 系统写死 / DuckDB 跑得好) 1:1 stable 实证 |
| L4.56 POC 留尾 SOP | ✅ Sprint N+3/N+4/灰度 → advisory 给接手人 |
| L4.57 跨 sprint 留尾 0 commit 续期 | ✅ 状态从"续期"→"advisory" (跟 L4.57 1:1 stable 沿用) |
| L4.58 跑批 wall_min SOP | ✅ W2 baseline 满足 = 0 wall_min 触发 |
| L4.59 跨 sprint 维护性 SOP | ✅ ClickHouse POC 监控维持 |
| L4.20 SSOT 反漂移 | ✅ 反转 Go → No-Go, evidence 全引用现有 (SSOT) |
| L4.31 branch cleanup | ✅ post-merge hook 自动跑 |
| L4.60 跨平台 Path | ✅ 0 业务代码改动 |
| L4.61 跨 CI runner 适配 | ✅ pytest 跨平台跑过 |
| L4.62 launchd plist plutil -lint | ✅ 0 launchd 改动 (ClickHouse POC monitor 已配) |
| L4.7 launchd 首选 python3 | ✅ 0 launchd 改动 |
| L4.36 禁停 uvicorn | ✅ uvicorn PID 79384 持续运行 |
| L4.38 DuckDB flock 锁死 | ✅ 0 DuckDB 改动 |

---

## 6. 反转来源

本 doc 反转自 `docs/sprints/SPRINT-N+5-GO-DECISION-2026-07-06.md` (2026-07-06 当日 Go 拍板)。

**反转真因** (跟 L4.20 SSOT 反漂移 + L4.42 立项实证 + L4.55 立项 spec 实证 1:1 stable 沿用):

1. **3 件新约束** (在职时间 / 系统写死 / DuckDB 跑得好) 在 Go 拍板当时**没考虑**, 拍板后 user 提出来, 重新评估
2. **新增 2 件致命风险** (烂摊子风险 + 跟写死哲学冲突) 跟原 6 风险累计 = **8 风险**, **远超可控 6 风险阈值**
3. **Boring by default** + **Reversibility preference** + **Essential vs accidental complexity** + **Two-week smell test** 4 大 cognitive pattern 1:1 stable 验证 No-Go 是 强推荐

跟 Sprint 60+ L4.14 amend 物理限制 1 commit drift 永久规则沿用 1:1 stable 接受, **Go → No-Go 反转 = 1 commit 1 doc 1:1 stable 接受**。

---

## 7. STATUS

**STATUS**: 🔴 **NO-GO** (跟 system locked down + handoff advisory 跟离职 1:1 stable 沿用, 跟原 Go 拍板反转)

**REASON**: 3 件新约束触发反转 (在职时间 / 系统写死 / DuckDB 跑得好) + 新增 2 件致命风险 (烂摊子 + 跟写死哲学冲突) + 4 大 cognitive pattern 1:1 stable 验证 No-Go 是 强推荐.

**CROSS-STABLE**: 0 业务代码改动 Sprint 60+ 60+ 次 1:1 stable. Wave 1 5/5 docs 保留 (接手人 advisory 资料). 跨 sprint 留尾 4 维度 → advisory 状态 (跟 L4.57 + L4.58 SOP 1:1 stable 永久规则沿用).

**NEXT**:
1. ✅ 三方签字 (业务方 + DBA + 架构师, 跟 Q20 1:1 stable 接受)
2. ✅ 反转 Sprint N+5 Go → No-Go (本 doc, 系统写死 + 离职 + 跑得好 1:1 stable 沿用)
3. 📋 接手人 advisory (读 Go doc + TRINO-POC-SUMMARY 决定是否启动迁移)
4. ⏸ ClickHouse POC 启动条件监控维持 (launchd weekly, 跟 L4.58 1:1 stable)
5. ⏸ Sprint N+3/N+4 跨 sprint 续期 → advisory (接手人决定)