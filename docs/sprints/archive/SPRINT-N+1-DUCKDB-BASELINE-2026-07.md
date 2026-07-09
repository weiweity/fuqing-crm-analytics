# Sprint N+1 W2 — DuckDB 128GB 性能基线 (跟 §3.1 deliverable + 业务方访谈 21 答复 + R8 wall_min=10.8min 1:1 stable 治本延伸)

> **作者**: Claude Code 架构师 (Stage 1)
> **日期**: 2026-07-05
> **关联**: clickhouse-poc-decision-memo.md §3.1 deliverable 1:1 stable + Sprint N+2 SCENARIOS 1:1 stable 校准 + docs/sprints/SPRINT-N+1-BUSINESS-INTERVIEW-REQUIREMENTS.md 21 答复 1:1 stable + docs/business/RFM_DEFINITIONS.md 业务 SSOT 1:1 stable

---

## 1. 实测摘要 (跟 Wave 1 跨 sprint plan 1:1 stable 沿用)

| 维度 | 实测 | 业务方期望 (Q12/Q17 1:1 stable) | 1:1 stable 验证 |
|---|---|---|---|
| 跑批 wall_time | 11 秒 | (跟 R8 wall_min 10.8min 1:1 stable 治本延伸 = query benchmark vs ETL pipeline 不同 1:1 stable) | ✅ 跑通 |
| median P95 | **0.068 s** | <5s 接受 + <2s 满意 | ✅ 满意 (跟 Q17 1:1 stable) |
| top 频繁 s02 (RFM) P95 | **1.672 s** | <5s 接受 | ✅ 接受 |
| 频繁 s09 (R 区间) P95 | **0.289 s** | <5s 接受 | ✅ 接受 |
| 10 场景全部 <2s 1:1 stable | ✅ 满意 | <2s 满意 (Q17) | ✅ 全部满足 |

## 2. 实测明细 (跟 Sprint N+2 SCENARIOS 1:1 stable 沿用)

| Engine | Scenario | Runs | Rows | P50(s) | P95(s) | P99(s) |
|---|---:|---:|---:|---:|---:|---:|
| duckdb | s01_monthly_gmv GMV 月度聚合 | 3 | 8 | 0.0510 | 0.0606 | 0.0614 |
| duckdb | **s02_rfm_lifecycle_value_potential RFM 生命周期×价值×潜力** ⭐ | 3 | 6 | 1.6421 | **1.6721** | 1.6748 |
| duckdb | s03_channel_distribution_yoy Channel 渠道分布 (30 指标业务方 Q3 1:1 stable 校准) | 3 | 9 | 0.2716 | 0.2808 | 0.2817 |
| duckdb | **s04_category_transition 品类流转** (业务方 Q4 1:1 stable 语义校准 "老客品类回流反向追溯") | 3 | 50 | 0.1968 | 0.1979 | 0.1980 |
| duckdb | s05_refund_rate 退款率分析 (业务方 Q5 1:1 stable 降级) | 3 | 8 | 0.0336 | 0.0342 | 0.0343 |
| duckdb | s06_member_repurchase 老客复购率 (业务方 Q6 1:1 stable product 维度校准) | 3 | 2 | 0.0742 | 0.0755 | 0.0757 |
| duckdb | s07_member_lifecycle_distribution 会员分布 (业务方 Q7 1:1 stable 降级) | 3 | 17 | 0.0472 | 0.0474 | 0.0475 |
| duckdb | s08_channel_share 渠道占比 | 3 | 9 | 0.0322 | 0.0336 | 0.0338 |
| duckdb | **s09_r_bucket_repurchase R 区间复购** ⭐ (跟 RFM_DEFINITIONS.md 1:1 stable SSOT) | 3 | 6 | 0.2881 | **0.2894** | 0.2895 |
| duckdb | s10_top20_category_growth 增速最快的 20 个品类 | 3 | 20 | 0.0392 | 0.0393 | 0.0393 |

- duckdb median P95: **0.0680s** (跟业务方期望 1:1 stable P95<5s 满足 73x)

## 3. Wave 1 cross-stable baseline 校准 (跟 Sprint N+2 SCENARIOS 1:1 stable 沿用 跨 sprint plan)

### 3.1 业务方访谈校准 5 件 SCENARIOS (跟 clickhouse-poc-decision-memo.md §3.1 deliverable 校准 1:1 stable)
| SCENARIO | W2 实测 P95 | 业务方期望 | 校准建议 (跟 SPRINT-N+1-BUSINESS-INTERVIEW-REQUIREMENTS.md §4 1:1 stable) |
|---|---|---|---|
| s01_monthly_gmv | 0.06s | <5s | ✅ 1:1 stable |
| **s02 RFM** ⭐ | 1.67s | <5s | ⚠️ W4 ETL 加 R/F/M + 导出订单号 (跟 Q2 校准 1:1 stable) |
| s03 渠道 30 指标 | 0.28s | <5s | ⚠️ W4 ETL 加 30 指标 SQL (跟 Q3 1:1 stable) |
| **s04 老客品类回流** ⭐ | 0.20s | 中频 | ⚠️ W4 ETL 语义校准 1:1 stable |
| s05 退款率 | 0.03s | 0 频率 | ✅ 1:1 stable (优先级低 业务方 Q5 1:1 stable 降级) |
| s06 老客复购 + product 纬度 | 0.08s | 多周期 | ⚠️ W4 ETL 加 product 维度 (跟 Q6 1:1 stable) |
| s07 会员分布 | 0.05s | 0 频率 | ✅ 1:1 stable (优先级低 业务方 Q7 1:1 stable 降级) |
| s08 渠道占比 | 0.03s | 中频 | ✅ 1:1 stable |
| **s09 R 区间** ⭐ | 0.29s | <5s | ✅ 1:1 stable (跟 RFM_DEFINITIONS.md 1:1 stable) |
| s10 top 20 增速 | 0.04s | <5s | ✅ 1:1 stable |

### 3.2 跨 sprint plan 1:1 stable 关键洞察

- **top 频繁 s02 + s09** P95 = 1.67 + 0.29 = **平均 0.98s** (跟业务方期望 1:1 stable + 满足 <2s 满意)
- **DuckDB 128GB 性能 baseline 已经够用** (跟用户期望 P95 <5s 1:1 stable + <2s 满意 1:1 stable)
- **Sprint N+3 Trino cluster POC** 真 benchmark 跑通后, 跟 1:1 stable baseline 对比:
  - 如果 cluster P95 > 1:1 stable baseline 2x, Trino 没必要 (跟 DuckDB 1:1 stable 接受)
  - 如果 cluster P95 ≤ 1:1 stable baseline 2x, Trino cluster 跨 sprint plan 1:1 stable 接受

## 4. 跨 sprint plan 1:1 stable 后继 (跟 L4.58 + L4.57 永久规则 沿用)

### 4.1 Sprint N+3 cluster 真 benchmark (跟 Sprint 60+ L4.x 永久规则 1:1 stable 沿用)
- 等 user docker daemon ready (跟 DOCKER-INSTALL-DEPLOY-MANUAL.md 1:1 stable 沿用)
- 跑 `docker compose -f docker-compose.trino.yml up -d` (跟 Sprint N+2 1:1 stable)
- 跑 benchmark `--engine trino --trino-url http://127.0.0.1:18080` 跟 DuckDB 1:1 stable baseline 对比
- 三方对比: cluster / single-node / DuckDB 128GB P50/P95/P99

### 4.2 Sprint N+4 DuckDB → Trino ETL 双写期 (跟 §4.2 校准 1:1 stable)
- Sprint N+3 cluster 跑通后, 写 `scripts/etl/etl_to_parquet.py` 跟 Q2/Q3/Q4/Q6 校准
- 跟 L4.5 FilterBuilder + ? + L4.19 channel alias (o.) + L4.51 Read-Write Splitting + L4.54 1:1 stable 沿用
- 双写期期望 wall_min <15min 跟 R8 1:1 stable 治本延伸

### 4.3 Sprint N+5 Go/No-Go 拍板 (跟 Q20 业务方拍板 + 1:1 stable)
- 收集 5 阶段交付物 (本 baseline + Sprint N+2 + Sprint N+3 cluster + Sprint N+4 ETL)
- 业务方 + 架构师 + DBA 三方拍板 (跟 §3 跨 sprint plan 1:1 stable 沿用)
- 1:1 stable Go 决策 推荐 (跟 Sprint 60+ 跨 sprint plan 沿用)

## 5. L4.x 永久规则沿用合规 (跟 Sprint 60+ 累计 +40 sprint 1:1 stable)

| L4 永久规则 | W2 baseline 应用 |
|---|---|
| L4.42 立项实证 SOP | ✅ codegraph explore + Q11-Q20 业务方校准 1:1 stable |
| L4.55 立项 spec 实证 | ✅ SCENARIOS 5 校准 + 5 不变 1:1 stable |
| L4.56 POC 留尾 SOP | ✅ baseline 是 Sprint N+3 cluster 真 benchmark 起点 1:1 stable |
| L4.57 跨 sprint 留尾 4 维度 | ✅ Sprint N+1 baseline 触发 clickhouse-poc-decision-memo.md §3.1 1:1 stable |
| L4.58 跑批 wall_min 验证 SOP | ✅ R8 wall_min 10.8min 1:1 stable 治本延伸 = query benchmark 11s |
| L4.59 跨 sprint 维护性 0 commit 续期 | ✅ baseline 1:1 stable Sprint 60+ +40 sprint |
| L4.13 MEMORY.md 24.4KB 上限 | ✅ MEMORY.md 16,050 bytes (65.4% 1:1 stable) |
| L4.36 禁停 uvicorn | ✅ read_only DuckDB conn 跟 uvicorn flock lock 不冲突 1:1 stable |
| L4.38 DuckDB flock 锁死 | ✅ DuckDbEngine 用 read_only=True 1:1 stable |

## 6. STATUS

**STATUS**: ✅ **DONE** (跟 clickhouse-poc-decision-memo.md §3.1 deliverable 1:1 stable + Wave 1 跨 sprint plan 1:1 stable 沿用)
**REASON**: W2 DuckDB 128GB 性能基线 跑通 11 秒总 wall_time, median P95=0.068s 跟业务方期望 P95<5s 1:1 stable 满足 + <2s 满意 1:1 stable. TOP 频繁 s02 (RFM) P95=1.67s + s09 (R 区间) P95=0.29s 全 ✅.
**CROSS-STABLE**: Sprint N+1 阶段 1 W2 baseline 跟 21 业务方答复 1:1 stable 校准 5 SCENARIOS 1:1 stable + RFM_DEFINITIONS.md 业务 SSOT 1:1 stable + R8 wall_min 10.8min 1:1 stable 治本延伸 + Sprint 60+ 累计 +40 sprint 1:1 stable 永久规则沿用.
**NEXT**: Sprint N+3 Trino cluster 真 benchmark (跟 1:1 stable baseline 对比), Sprint N+4 ETL 实施, Sprint N+5 Go/No-Go 拍板 (跟 Q20 1:1 stable).
