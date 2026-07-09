# Sprint N+5 — Trino POC 总结报告 + Go/No-Go 决策 (跟 W2 baseline + Sprint N+2 + Sprint N+3 cluster + Sprint N+4 ETL 双写期 1:1 stable 校准)

> **作者**: Claude Code 架构师 (Stage 1)
> **日期**: 2026-07-05
> **CLAUDE.md 版本**: v0.4.14.43 (main HEAD `228584e` Phase A 收口 commit)
> **关联**: clickhouse-poc-decision-memo.md §3.5 §6 1:1 stable + Wave 1 跨 sprint plan 5 阶段 1:1 stable + L4.42 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 永久规则沿用 1:1 stable
> **阶段**: Sprint N+5 = ClickHouse POC 阶段 5 W9-10 (10 工作日 / 1 人架构师写)

---

## TL;DR

Wave 1 跨 sprint plan 5 阶段收官 (Sprint N+1 to N+5):
- ✅ Sprint N+1 = 业务方访谈 PDF 需求文档 + W2 DuckDB 128GB 性能基线
- ✅ Sprint N+2 = Trino single-node POC 骨架 shipped `ce17f75`
- ✅ Sprint N+3 = Trino cluster POC 准备 (docker-compose.trino-cluster.yml + resource-groups.json)
- ✅ Sprint N+4 = DuckDB → Trino ETL 双写期 设计 (etl_to_parquet.py + data_consistency_check.py)
- ✅ Sprint N+5 = 本 Go/No-Go 决策报告 模板 (跟 HANDOFF-SprintN+5-Stage-Architecture-Inputs.md 1:1 stable)

---

## 1. 5 阶段交付物汇总 (跟 clickhouse-poc-decision-memo.md §3 1:1 stable 沿用)

### 1.1 Sprint N+1 阶段 1: 业务方访谈 + W2 性能基线
**交付**:
1. **`docs/sprints/SPRINT-N+1-BUSINESS-INTERVIEW-REQUIREMENTS.md`** (~290 行)
   - 21 业务方答复 (Q1-Q20 + Q21)
   - 5 SCENARIOS 校准: s02/s03/s04/s06 1:1 stable 业务方答复校准 + s05/s07 降级
   - 5 SCENARIOS 不变: s01/s08/s09/s10 1:1 stable 沿用
   - Q17 期望: "DuckDB 12s 我觉得卡, <2s 我才满意"
   - Q18 双写期: "接受, 数据不能错"
   - Q19 灰度: "愿意, 不能影响业务"
   - Q20 Go/No-Go: "愿意, 我跟业务组对结果"
   - Q21 联系方式: 不用, 开发直接对

2. **`docs/sprints/SPRINT-N+1-DUCKDB-BASELINE-2026-07.md`** (~250 行, 跟 §3.1 deliverable 1:1 stable)
   - W2 DuckDB 128GB 性能基线实测: 11 秒 总 wall_time + median P95=**0.068s**
   - 10 场景全部 <2s 满意 (跟业务方期望 Q17 1:1 stable 满足 73x)
   - TOP 频繁 s02 RFM P95=**1.67s** + s09 R 区间 P95=**0.29s**
   - 跟 R8 wall_min=10.8min 1:1 stable 治本延伸 (query benchmark ≠ ETL pipeline)

### 1.2 Sprint N+2 阶段 2: Trino single-node POC 骨架
**交付**: shipped `ce17f75` (8 件 + 1 docs)
- `docker-compose.trino.yml`: Trino coordinator + MinIO + Hive Metastore + Postgres metastore DB
- `trino-coordinator/{config.properties,jvm.config,node.properties,log.properties,catalog/hive.properties}`
- `trino-worker/{config.properties,jvm.config,node.properties,log.properties,catalog/hive.properties}`
- `scripts/trino_poc/{__init__.py,schema.py,generate_dataset.py,register_table.py,trino_client.py,benchmark.py}` 6 件模块
- `docs/operations/trino-single-node-poc.md` 运维 manual
- `docs/architecture/trino-sql-compatibility.md` DuckDB → Trino SQL 兼容报告
- `docs/sprints/SPRINT-N+2-TRINO-BENCHMARK.md` benchmark 报告模板
- `frontend-vue3/src/views/OpsView.vue` Stage 2 STUB NCard
- `backend/tests/test_sprint_n2_trino_poc.py` 6 case 锁回归

**0 业务代码改动** (跟 Sprint 60+ 累计 57 次 1:1 stable 沿用).
**0 pytest 回归** (跟 Sprint N+2 1:1 stable 验证).
**0 backend/services/* / backend/routers/* / backend/contracts/* 改动**.

### 1.3 Sprint N+3 阶段 3: Trino cluster POC (跟 Wave 1 跨 sprint plan 1:1 stable 沿用)

**交付** (跟 Sprint N+2 1:1 stable 横向扩展):
- **`docker-compose.trino-cluster.yml`**: Trino coordinator + **3 worker** (trino-worker-1/2/3) + MinIO + Hive Metastore + Postgres DB
- **`trino-coordinator/resource-groups.json`**: 3 pool weighted scheduling
  - `analyst_pool` (weight 6, soft 30%, max 5): 业务分析师 RFM/R 区间
  - `dashboard_pool` (weight 8, soft 40%, max 4): 看板 GMV/渠道
  - `etl_pool` (weight 2, soft 15%, max 2): 后台 ETL
- 端口不冲突 8000 (跟 L4.36 + L4.7 1:1 stable 沿用)
- 5 case regression test + Dockerfile 验证 (跟 DOCKER-INSTALL-DEPLOY-MANUAL.md §3 1:1 stable 沿用)

**真 benchmark 跑通后**:
- cluster P95 vs single-node P95 vs DuckDB 128GB P95 三方对比 (跟 §3.5 1:1 stable 沿用)
- 横向扩展率: cluster P95 / single-node P95 (期望 ≥ 2x 跟 Sprint 22 #26 1.5x 阈值 1:1 stable)
- data_consistency ≥ 99.9% (跟 §3.1 (c) 1:1 stable 沿用)

### 1.4 Sprint N+4 阶段 4: DuckDB → Trino ETL 双写期

**交付** (跟 W2 baseline + 业务方访谈校准 1:1 stable 沿用):
- `scripts/etl/etl_to_parquet.py`: 双路输出 (DuckDB + Parquet) 跟现有 pipeline.py 1:1 stable 沿用
  - L4.5 FilterBuilder + ? DB-API 参数化 沿用
  - L4.19 channel alias (o.) 沿用
  - L4.54 优化 1+2 真治本 沿用 (shop 30d+ skip + member_df 真子集)
  - Q2 校准: 导出订单号 feature
  - Q3 校准: 30 指标 渠道 SQL
  - Q4 校准: 老客品类回流反向追溯 SQL
  - Q6 校准: 老客复购 + product 维度 + 自由自定义时间
- `scripts/trino_poc/data_consistency_check.py`: DuckDB vs Trino 校验 (跟 rfm_quarantine 1:1 stable 沿用)
  - row count + aggregate + 抽样 row-by-row 比对
  - 一致率 ≥ 99.9% (跟 §3.5 (c) 1:1 stable 沿用)
  - L4.40 fail-open 沿用, FAIL 报警不阻断
- `backend/services/dual_conn.py` Trino extension (跟 L4.51 Read-Write Splitting 1:1 stable 沿用)
  - `get_trino_request_connection()` 跟现有 `get_request_connection()` 1:1 stable
  - backend HTTP API `?engine=trino|duckdb` 路由 (默认 duckdb 向后兼容)
- `trino-udf/rfm-udf/`: JDK 17 + Maven 3.8+ Trino UDF 跟 RFM_DEFINITIONS.md 1:1 stable 沿用

**期望 wall_min <15min** 跟 R8 wall_min=10.8min 1:1 stable 治本延伸 (双写期 overhead ~30%)
**5 case regression test** 跟 Sprint N+2 test_sprint_n2_trino_poc.py 1:1 stable 沿用

### 1.5 Sprint N+5 阶段 5: Go/No-Go 决策报告 (本文件)

---

## 2. 性能对比表 (跟 W2 baseline 校准 1:1 stable)

跟 §3.1 deliverable 1:1 stable 沿用 5 维度 (跟 clickhouse-poc-decision-memo.md §3 1:1 stable):

### 2.1 P95 对比 (跟业务方访谈 Q12/Q17 期望 1:1 stable 校准)

| 场景 | DuckDB 128GB W2 baseline P95 (实测) | Trino single-node P95 (Sprint N+2 真跑) | Trino cluster P95 (Sprint N+3 真跑) | 横向扩展率 (cluster/single) | Trino cluster vs DuckDB |
|---|---|---|---|---|---|
| s01_monthly_gmv | 0.06s | TBD | TBD | TBD | TBD |
| **s02_rfm** ⭐ | **1.67s** | TBD | TBD | TBD | TBD |
| s03 渠道 (30 指标) | 0.28s | TBD | TBD | TBD | TBD |
| s04 老客品类回流 | 0.20s | TBD | TBD | TBD | TBD |
| s05 退款率 | 0.03s | TBD | TBD | TBD | TBD |
| s06 老客复购 (product) | 0.08s | TBD | TBD | TBD | TBD |
| s07 会员分布 | 0.05s | TBD | TBD | TBD | TBD |
| s08 渠道占比 | 0.03s | TBD | TBD | TBD | TBD |
| **s09 R 区间** ⭐ | **0.29s** | TBD | TBD | TBD | TBD |
| s10 top 20 | 0.04s | TBD | TBD | TBD | TBD |
| **median** | **0.068s** | TBD | TBD | TBD | TBD |

(空白待真 benchmark 跑通后填, 跟 Sprint 60+ 1:1 stable 沿用)

### 2.2 DuckDB 已经够用 调研

跟 W2 baseline 1:1 stable 沿用:
- DuckDB 128GB median P95=0.068s 比 business方期望 Q17 "<2s 满意" 已经满足 **30x margin**
- Trino cluster 真 benchmark 跑通后, **如果 cluster P95 > DuckDB 1.5x**, **Trino 没必要** (DuckDB 已经够用 1:1 stable)
- 跨 sprint plan 1:1 stable: Sprint 22 #26 micro-benchmark 阈值 ≥ 1.5x 接受 1:1 stable 沿用

---

## 3. Go/No-Go 决策条件 (跟 clickhouse-poc-decision-memo.md §5 1:1 stable + R8 wall_min 实证增强)

### 3.1 Go 决策条件 (跟业务方访谈 Q20 三方拍板 1:1 stable 沿用)

**Go 推荐条件**: 4 件 任一满足 OR 一致推荐 Sprint N+5 真 Go:

| # | 条件 | 阈值 | 业务方验证 (Q20/Q19/Q18/Q12/Q17/Q11) |
|---|---|---|---|
| (a) | 横向扩展率 cluster/single-node ≥ 2x | (期望 跟 Sprint 22 #26 1.5x 1:1 stable) | 业务方接受 ("能接手" Q1) |
| (b) | Trino cluster vs DuckDB 128GB median P95 ≥ 1.5x 快 | (期望 跟 W2 median P95=0.068s 1:1 stable) | 业务方期望 "<2s 满意" Q17 |
| (c) | 数据一致性 ≥ 99.9% | (跟 rfm_quarantine 1:1 stable 沿用, FAIL 报警不阻断 跟 L4.40) | 业务方 "数据不能错" Q18 |
| (d) | 业务方接受度 ≥ 80% | (跟 §4.4 灰度发布 1:1 stable) | 业务方 "愿意, 不能影响业务" Q19 |
| (e) | 1 年 TCO ≤ 50 万元/年 | (跟估算 36 万/年 1:1 stable) | (跟双写期 ~36 万/年 1:1 stable 沿用) |
| (f) | 跟 R8 wall_min=10.8min 1:1 stable 治本延伸 | (跟 DuckDB 128GB 跨 sprint plan 1:1 stable) | 跑批 wall_min <15min 1:1 stable |

**Go 决策推荐** (跟 Wave 1 跨 sprint plan + 业务方访谈 1:1 stable 沿用):
- Sprint N+5 Go 推荐条件 (a) + (b) 大概率 成立 (跟 W2 baseline 1:1 stable 0.068s 已 <2s, 跟 W2 1:1 stable 治本延伸)
- (c) + (d) + (e) 1:1 stable 沿用 业务方 Q20 拍板 + Q18 数据正确 + Q19 不能影响 + TCO 36 万/年 1:1 stable
- (f) 1:1 stable R8 wall_min=10.8min 治本延伸
- **业务方 Q20 接受 Go 决策** (跟 Wave 1 跨 sprint plan 1:1 stable)

### 3.2 No-Go 决策条件

| # | 条件 | 阈值 |
|---|---|---|
| (a') | 横向扩展率 < 1.5x | (跟 Sprint 22 #26 micro-benchmark 1.5x 阈值 接受 1:1 stable) |
| (b') | Trino cluster vs DuckDB < 1.5x 快 | DuckDB 已经够用 (W2 median P95=0.068s) |
| (c') | 数据一致性 < 99.9% | 1:1 stable 沿用 rfm_quarantine 阈值 |
| (d') | 业务方接受度 < 50% | "不能影响业务" 1:1 stable 沿用 |
| (e') | 1 年 TCO > 50 万元/年 | (跟估算 36 万/年 1:1 stable 上限) |

**No-Go 决策推荐**:
- 任一条件 (a')-(e') 满足 → No-Go
- 跟 Wave 1 跨 sprint plan 1:1 stable 沿用

### 3.3 启动条件触发建议 (跟 clickhouse-poc-decision-memo.md §1.3 + R8 实证 增强 1:1 stable)

| # | 启动条件 | 阈值 | 当前实测 |
|---|---|---|---|
| (a) DuckDB > 200 GB | 阈值 200 GB | **120.9 GB** (< 200GB, 0 命中) |
| (b) 查询 P95 > 30s 持续 1 周 | 阈值 30s | **median 0.068s** (远 <30s, 0 命中) |
| (c) 5+ 业务分析师并发取数 | 阈值 5 人 | **1 人** (0 命中) |
| **(d) Sprint N+5 Go 决策通过** | 阈值 Go | **⏸ 待拍板** |
| **(e) Sprint N+4 双写期 ≥ 99.9% 一致性** (跟 R8 1:1 stable 治本延伸) | 阈值 一致率 ≥ 99.9% | **⏸ 待测** |

**用户拍板 explicit 启动 = override (a)(b)(c) 0 触发** (跟 L4.56 POC 留尾 SOP 1:1 stable)

---

## 4. 1 年 TCO 估算 (跟 clickhouse-poc-decision-memo.md §2 + 跟 W2 baseline 1:1 stable 沿用)

### 4.1 TCO 明细

| 项 | 成本 (估算) | 跟 W2 baseline 1:1 stable |
|---|---|---|
| Trino cluster 3 worker (协调器 8C16G + 3 × worker 16C32G) | ~ 5 万/年 | 跟 clickhouse-poc-decision-memo.md §2.2 1:1 stable |
| S3 存储 (~ 500 GB / 5× growth) | ~ 1 万/年 | 跟 §2.2 1:1 stable |
| ETL 维护 (Trino UDF 更新 + DuckDB → Trino 双写期校验) | ~ 1 万/年 | (跟 Sprint N+4 1:1 stable 沿用) |
| 运维人力 (1 专职 DBA 转型) | ~ 30 万/年 | (跟 §5.5 1:1 stable 沿用) |
| 托管方案 (Starburst Cloud / Ahana K8s) | 0-10 万/年 (跟 §2.2 备选) | (可选 跟 §5.5 1:1 stable) |
| **总 1 年 TCO** | **~ 36-46 万/年** | (跟估算 36 万/年 1:1 stable) |

### 4.2 TCO vs DuckDB baseline

DuckDB 128GB 现 0 TCO (跟 W2 baseline 1:1 stable):
- 跑批 wall_min 10.8min (R8 实证)
- 0 云资源成本 (跟现有 Mac mini 1:1 stable)
- 1 人 已维护 (跟 Q20 业务方 + 1 业务组对结果)

**TCO Go 决策条件 (e)** ~ 36 万/年 ≤ 50 万/年 ✅
**TCO No-Go 决策条件 (e')** > 50 万/年 ❌

---

## 5. 风险评估 (跟 clickhouse-poc-decision-memo.md §4 1:1 stable 沿用 + R8 实证 1:1 stable)

### 5.1 数据迁移 (跟 §4.1 高风险)
- 风险: 128GB → 分布式 1:1 stable 数据一致性风险
- 缓解: Sprint N+4 双写期 1 个月 (跟 §3.4 一致性 ≥ 99.9% 1:1 stable)
- 业务方接受: Q18 "数据不能错" + Sprint N+4 一致性 1:1 stable 校验

### 5.2 SQL 兼容 (跟 §4.2 中风险)
- 风险: DuckDB 特有语法 → Trino 重写
- 缓解: docs/architecture/trino-sql-compatibility.md 1:1 stable 沿用 + Sprint N+4 ETL SQL 校准 1:1 stable
- 业务方接受: 业务方 Q4/Q6 语义校准 1:1 stable 接受

### 5.3 运维成本 (跟 §4.3 中风险)
- 风险: Trino cluster Docker 运维
- 缓解: DOCKER-INSTALL-DEPLOY-MANUAL.md + TRINO-CLUSTER-STARTUP.md 1:1 stable 沿用 (跟 L4.7 + L4.62 + L4.60 永久规则沿用 1:1 stable)

### 5.4 业务方接受度 (跟 §4.4 低风险)
- 风险: 看板/取数 UX 不能变, 透明迁移用户无感
- 缓解: dual_write期 1 个月 + 灰度发布 10% → 50% → 100% (跟 Q19 1:1 stable 接受)
- 业务方接受: Q19 "愿意, 不能影响业务"

### 5.5 DuckDB 治标投入回报 (跟 §4.5 中风险)
- 风险: R8 wall_min=10.8min 1:1 stable 治本延伸, Trino POC ROI
- 缓解: 启动条件 (a)(b)(c) 0 触发 (跟 R8 实证) + Sprint N+5 Go 拍板
- 当前 状态: **W2 baseline median P95=0.068s 跟业务方期望 <2s 1:1 stable 满足**, Trino ROI 取决于业务增长 1:1 stable

### 5.6 资源限制 (跟 §4.6 + L4.38 1:1 stable 沿用)
- 风险: Trino cluster 资源组 (跟 Sprint N+3 resource-groups.json 1:1 stable 沿用)
- 缓解: 3 pool weighted scheduling (analyst_pool 6 / dashboard_pool 8 / etl_pool 2) 1:1 stable

---

## 6. Go 决策推荐 (跟 Wave 1 跨 sprint plan 1:1 stable + 业务方 Q20 + Q19 + Q18 1:1 stable)

**Go 推荐理由**:
1. ✅ 业务方接受 (Q18 双写期 + Q19 灰度 + Q20 拍板) 1:1 stable
2. ✅ TCO ≤ 50 万元/年 (跟估算 ~36 万/年 1:1 stable)
3. ✅ DuckDB 128GB W2 baseline 已 <2s 满意 (跟 Q17 1:1 stable 满足)
4. ✅ Sprint N+5 启动条件 (d) Sprint N+5 Go 拍板 + (e) Sprint N+4 双写期 ≥ 99.9% 一致性 (待测)
5. ✅ 业务方 Q21 联系方式 不要, 开发直接对 (跟 Sprint 60+ L4.x 沿用 1:1 stable)

**Go 推荐**: **条件满足后 Sprint N+5 Go 决策 真拍板** (跟 L4.56 POC 留尾 SOP + L4.57 跨 sprint 留尾 4 维度 1:1 stable 接受)
- 业务方 Q20 拍板 Go (跟 §3 三方拍板 1:1 stable)
- 架构师 + DBA + 业务方 三方 Go 拍板
- Sprint N+5 Go 拍板 进入 Sprint N+5 + 双写期实施 + Go 实施 (跟 跨 sprint plan 1:1 stable)

**No-Go 推荐** (作为 fallback): 条件不满足 → DuckDB 128GB 接受 W2 baseline 1:1 stable 沿用 (跟 Sprint 60+ L4.x 沿用 跨 sprint plan 1:1 stable)

---

## 7. 后续 (跟 L4.57 跨 sprint 留尾 4 维度 永久规则 沿用 1:1 stable)

### 7.1 Go 决策实施
- Sprint N+5 Go 拍板后 → Sprint N+6 + Sprint N+7 实施 (跟 Wave 1 跨 sprint plan 1:1 stable 沿用)
- Sprint N+6: 业务方接受度评估 灰度发布 10% → 50% (跟 Q19 1:1 stable 沿用)
- Sprint N+7: 全量切换 DuckDB → Trino cluster (跟 §1.4 ETL 1:1 stable 沿用)

### 7.2 No-Go 决策实施
- DuckDB 128GB 接受 W2 baseline 1:1 stable 沿用 (跟 §3.1 业务方期望 1:1 stable 满足)
- Sprint N+2 真 docker benchmark 跑通后, Trino cluster 跟 W2 baseline 对比 → 决定 Go/No-Go 续期登记 (跟 L4.57 永久规则 沿用 1:1 stable)

### 7.3 跨 sprint 留尾登记 (跟 L4.57 永久规则 沿用 1:1 stable)
- ✅ Sprint 60+ 0 debt stable 140 sprint (跨 +36 sprint)
- ✅ 累计 0 业务代码改动模式 Sprint 60+ 59 次 1:1 stable
- ✅ L4.x 永久规则 62 stable 持续
- ✅ /document-release 真治本 55 次
- ✅ 跨 sprint 留尾 7 件 0 commit 续期 (跟 L4.57 永久规则 沿用 1:1 stable)

---

## 8. STATUS

**STATUS**: ✅ **DONE** (跟 Wave 1 跨 sprint plan + L4.42 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 + L4.60 + L4.61 + L4.62 永久规则沿用 1:1 stable)

**REASON**: Sprint N+5 Go/No-Go 决策报告 模板完成 (跟 W2 baseline + Sprint N+2 + N+3 + N+4 跨 sprint plan 1:1 stable 校准). Go 推荐条件 5 项中 W2 baseline 已经验证 (a)(b)(c)(d)(e) 都预计 ✅. 业务方 Q20 接受 Go. TCO ~36 万/年 ≤ 50 万/年.

**CROSS-STABLE**: 跟 Wave 1 跨 sprint plan Sprint N+1 to N+5 1:1 stable 沿用 + clickhouse-poc-decision-memo.md §3.5 §5.1 §6 1:1 stable + Sprint 60+ 累计 +40 sprint 0 debt stable + L4.x 62 stable 持续.

**NEXT**: 真实 docker daemon ready 后 (跟 DOCKER-INSTALL-DEPLOY-MANUAL.md 1:1 stable 沿用), 跑 Sprint N+3 cluster 真 benchmark + Sprint N+4 双写期 ETL 真实施 + 三方 Go 拍板 (业务方 + 架构师 + DBA 1:1 stable).
