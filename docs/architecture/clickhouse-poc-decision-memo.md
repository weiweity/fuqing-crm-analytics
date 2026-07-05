# ClickHouse / Trino POC 立项决策备忘录

> **作者**: Codex app (Stage 2 实施者, gpt-5.5 high reasoning sandbox=worktree)
> **架构师**: Claude Code (Stage 1)
> **日期**: 2026-07-03 (初始) + 2026-07-05 (你拍板启动 amend §5.1)
> **状态**: 🚀 **Sprint N+1 启动** (你 7/5 拍板启动, override §5.1 "暂不启动" 决策, 跟 L4.56 POC 留尾 SOP 1:1 stable 接受 user explicit 拍板优先)
> **CLAUDE.md 版本**: v0.4.14.35 (main @ `df29bad`) → v0.4.14.43 (main @ `e602a41`)
> **配套**: L4.56 永久规则化 (POC 留尾 SOP) + `docs/TECH-DEBT.md` line 12 #S201+-ClickHouse-POC
> **关联**: Sprint 200 R1 Codex consult 6 补强 + Sprint 184 v3 L4.38 DuckDB flock 模型 + Sprint 202 R1 ETL 性能治本 (L4.54 文件分桶 46min→<15min, R8 wall_min=10.8min PASS)

---

## 1. 背景 (Background)

### 1.1 当前状态 (7/3 main HEAD `88e8ae8`)
- **DuckDB 单文件 117GB**: 单一 OLAP 存储, 数据累积风险
- **ETL 跑批 18min→46min**: 业务方反映慢, Sprint 202 R1 治标 46min→<15min (L4.54 文件分桶 + member_df 真子集)
- **看板+取数 0 锁竞争**: Sprint 201 R1 Read-Write Splitting + Query worker 独立进程 + Snapshot 根除 (L4.51/L4.48/L4.53)
- **0 业务触发 POC**: Sprint 201+ 立项 ClickHouse / Trino POC 0 真业务方邮件/工单, 长期增长预期触发

### 1.2 长期增长预期 (3 年)
- 年度 GSV 数据 5× 增长 → DuckDB 单文件 117GB × 5 = **585GB**
- 单机 DuckDB 上限 ~500GB (实测 L4.38 flock 模型 + 单机 OS file handle 上限)
- 业务分析师从 1 人 → 5+ 人并发取数 → 当前 1 uvicorn + 1 query worker 模式可能不够

### 1.3 决策触发条件 (任一满足 → 立 Sprint 203+ ClickHouse POC sprint)
- (a) DuckDB 单文件 > 200GB (目前 117GB, 增长 70% 触发)
- (b) 业务方反映查询延迟 > 30s 持续 1 周 (Sprint 202 R1 治标后 P95 < 5s 期望)
- (c) 新增 5+ 业务分析师需要并发取数 (目前 1 人)

---

## 2. 选型对比 (Alternatives)

### 2.1 ClickHouse
| 维度 | 评估 |
|---|---|
| **类型** | 列存 OLAP (column-oriented) |
| **数据规模** | 单节点 100GB+ 性能强, 横向扩展 shard/replica |
| **SQL 兼容** | 90% 兼容 DuckDB/PostgreSQL 语法, 但 DuckDB 特有 (`SELECT * EXCLUDE` / `LIST` / `STRUCT`) 需要重写 |
| **学习曲线** | 低, SQL 方言跟 PostgreSQL 类似 |
| **运维** | 需要专门 DBA, 单节点可用 docker-compose, cluster 需 zookeeper |
| **生态** | ClickHouse Cloud (托管) / Altinity (K8s operator) |
| **大厂对比** | 字节跳动 / 腾讯 / 快手 OLAP 主力, DataWorks 内置 |
| **ROI** | 中, 适合"查询层列存 + ETL 输出 Parquet" 场景 |
| **成本** | 单节点 (32C64G + 1TB NVMe) ~ 1 万/年; 3 节点 cluster ~ 3 万/年 |

### 2.2 Trino (原 PrestoSQL)
| 维度 | 评估 |
|---|---|
| **类型** | 分布式 SQL 查询引擎 (federated query) |
| **数据规模** | 不存数据, 需要外部存储 (S3/HDFS/Hive/Iceberg), 查询层分布式 |
| **SQL 兼容** | 95% 兼容 ANSI SQL, 跨数据源联邦查询 (MySQL/PG/Hive/S3 同 query) |
| **学习曲线** | 中, 需要懂 connector 架构 + 资源组配置 |
| **运维** | 需要专门 DBA, coordinator + worker 集群, resource groups 限制并发/内存/CPU/扫描量 |
| **生态** | Starburst (托管) / Ahana (K8s operator) |
| **大厂对比** | Meta / Uber / 字节跳动 联邦查询主力, DataWorks 内置 |
| **ROI** | 高, 适合"查询层分布式 + 不动数据层" 场景 |
| **成本** | coordinator (8C16G) + worker (3 × 16C32G) ~ 5 万/年 + S3 存储费 |

### 2.3 大厂架构对比 (Sprint 200 R1 Codex consult 6 补强沉淀)

| 平台 | 架构特点 | 跟 ClickHouse/Trino 对比 |
|---|---|---|
| **阿里 DataWorks** | DataOps 全套 + 语义层 + NL2SQL + 隔离 worker + 资源组 | 商业 SaaS, 自带 ETL + 调度 + 监控 |
| **腾讯 WeData** | DataOps 全套 + 语义层 + NL2SQL + 隔离 worker + 资源组 | 商业 SaaS, 跟 DataWorks 类似 |
| **Trino resource groups** | 限制并发/内存/CPU/扫描量 | 跟 L4.51 Read-Write Splitting 类似 (按 query 优先级) |
| **Firecracker microVM** | 多租户隔离 (AWS Lambda 同款) | 跟 L4.48 进程隔离 类似 |
| **ClickHouse Cloud** | 托管列存 OLAP | 跟自建 ClickHouse 一样, 但免运维 |

### 2.4 选型推荐: Trino + S3 + Parquet (跟 Sprint 200 R1 Codex consult 阶段 D 1:1 stable)

**理由**:
1. **不动数据层**: DuckDB ETL 继续输出 Parquet → S3, Trino 只做查询层联邦
2. **联邦查询**: 后续业务增长, 可以把 MySQL/PG/Hive/S3 都在 Trino 联邦查询
3. **DuckDB 兼容**: Trino SQL 95% 兼容 DuckDB, 改造量小
4. **资源隔离**: Trino resource groups 跟 L4.51 Read-Write Splitting 类似, 按 query 优先级限流
5. **运维可接受**: coordinator + 3 worker 中小规模, 比 ClickHouse cluster 简单

**ClickHouse 备选场景** (未来): 如果业务是 "纯列存 OLAP 查询" (无联邦需求), 选 ClickHouse 列存性能更优.

---

## 3. POC 阶段拆分 (8-10 周, 1-2 人月)

### 阶段 1: 需求文档 + 性能基线 (W1-2, 1 人)

**目标**: 锁定 POC 范围 + 性能基线数据

**交付物**:
- 需求文档 (PDF): 业务方真实查询场景 10 个 + 期望 P50/P95/P99 延迟
- DuckDB 117GB 当前查询性能基线 (Excel): 10 个场景实测 P50/P95/P99
- Trino 选型推荐报告 (本 memo §2.4)

**风险**:
- 业务方需求文档需要 1-2 周访谈, 可能拖延
- DuckDB 性能基线需要跟 Sprint 202 R1 ETL 跑批错峰 (凌晨跑)

**估时**: 5 工作日 (1 人)

### 阶段 2: Trino 单节点 POC (W3-4, 1 人)

**目标**: 1 个 SPU 维度 + 1 个月度聚合查询 benchmark, 对比 DuckDB

**交付物**:
- Trino 单节点 docker-compose 部署 (coordinator + 1 worker)
- S3 模拟数据集 (Parquet 格式, 100GB, 跟 DuckDB schema 1:1)
- 10 个查询场景 benchmark 报告 (Trino vs DuckDB 对比)
- SQL 兼容性报告 (DuckDB 特有语法需要重写的列表)

**风险**:
- S3 模拟数据集可能 100GB 不够, 需要分段 (W3 跑 100GB, W4 跑 500GB)
- DuckDB → Trino SQL 改造可能 5-10% 工作量

**估时**: 10 工作日 (1 人)

### 阶段 3: Trino cluster POC (W5-6, 1-2 人)

**目标**: 3 worker cluster 验证横向扩展

**交付物**:
- Trino cluster docker-compose 部署 (coordinator + 3 worker)
- 资源组配置 (按 query 优先级限制并发/内存/CPU/扫描量)
- 10 个查询场景 benchmark 报告 (cluster vs 单节点 vs DuckDB)
- 运维手册 (worker 节点扩缩容 / 监控告警 / 故障转移)

**风险**:
- 3 worker cluster 需要真实物理机/虚拟机, docker-compose 模拟可能不准确
- 资源组配置需要多次调优, 可能 1 周才能稳定

**估时**: 10 工作日 (1-2 人)

### 阶段 4: 数据迁移 ETL 设计 (W7-8, 1-2 人)

**目标**: DuckDB → Trino 兼容层 + RFM/R 区间语义层适配

**交付物**:
- DuckDB → Parquet ETL 脚本 (跟现有 ETL 兼容, 输出 Parquet 到 S3)
- RFM/R 区间语义层 Trino UDF (UDAF / UDF)
- 看板 / 取数 UX 透明迁移设计 (用户无感)
- 双写期方案 (DuckDB + Trino 并行 1 个月, 验证数据一致性)

**风险**:
- 双写期数据一致性风险, 需要校验脚本
- 看板 / 取数 UX 改造可能涉及 frontend-vue3 改动

**估时**: 10 工作日 (1-2 人)

### 阶段 5: 选型决策 + 风险评估 + 成本估算 (W9-10, 1 人)

**目标**: POC 总结报告 + Go/No-Go 决策

**交付物**:
- POC 总结报告 (PDF): 5 阶段交付物汇总 + 性能对比 + SQL 兼容性 + 运维成本
- 选型决策 (Go/No-Go): 推荐 Trino (跟 §2.4 1:1) 还是 ClickHouse (备选)
- 风险评估: 业务方接受度 / 数据迁移 / 运维成本 / DuckDB 治标投入回报
- 成本估算: 1 年 TCO (Trino cluster + S3 + 运维人力)
- 启动条件触发建议 (跟 §1.3 1:1 stable)

**风险**:
- Go/No-Go 决策需要业务方 + 架构师 + DBA 三方拍板, 可能拖延

**估时**: 10 工作日 (1 人)

### 总工作量
- 1-2 人 × 8-10 周 = 8-20 人周
- 折合 1.5-3 人月 (按 4 周/月, 1 人)

---

## 4. 风险列表 (Risks)

### 4.1 数据迁移 (高风险)
- 117GB → 分布式存储 (S3) 数据一致性风险
- 缓解: 双写期 (DuckDB + Trino 并行 1 个月, 校验脚本对比两边数据)
- 缓解: 分段迁移 (先迁移 RFM 维度 → 再迁移订单维度 → 最后迁移全量)

### 4.2 SQL 兼容 (中风险)
- DuckDB 特有语法 (`SELECT * EXCLUDE` / `LIST` / `STRUCT`) 在 Trino 需要重写
- 缓解: Sprint 200 R1 Codex consult 阶段 B 6 补强 (SQL AST allowlist sqlglot)
- 缓解: L4.5 FilterBuilder + `?` DB-API 参数化模式在 Trino 同样适用

### 4.3 运维成本 (中风险)
- Trino cluster (coordinator + 3 worker) 需要专职 DBA
- 当前 0 专职 OLAP 运维, 需要 1 人转型
- 缓解: 托管方案 (Starburst Cloud / Ahana K8s) 可减负, 但成本增加
- 缓解: docker-compose 模拟本地开发, 生产再上 K8s

### 4.4 业务方接受度 (低风险)
- 看板/取数 UX 不能变, 透明迁移用户无感
- 缓解: 双写期用户无感切换
- 缓解: 灰度发布 (10% 业务方先切 → 50% → 100%)

### 4.5 DuckDB 治标投入回报 (中风险)
- Sprint 202 R1 已治标 < 15min, ClickHouse POC ROI 取决于业务增长预期
- 缓解: 启动条件触发再立 (DuckDB > 200GB / 查询 P95 > 30s / 5+ 业务分析师并发)
- 缓解: Sprint 202 R1 治标是"短期 ROI 高", POC 是"长期 ROI 待验证"

### 4.6 资源限制 (L4.38 DuckDB flock 模型延伸)
- 跟 Sprint 184 v3 L4.38 DuckDB flock 模型 1:1 stable, Trino 资源组 (resource groups) 限制并发/内存/CPU/扫描量
- 缓解: Trino resource groups 跟 L4.51 Read-Write Splitting 类似 (按 query 优先级限流)
- 缓解: 隔离 worker (跟 L4.48 进程隔离类似, Trino worker 可按业务分组)

---

## 5. 决策建议 (Recommendation)

### 5.1 Sprint 201+ 决策: 🚀 **你 7/5 拍板启动** (override §5.1 初始 "暂不启动")

**你拍板理由 (2026-07-05)**:
1. Sprint 202 R8 wall_min **10.8min PASS** (跟 R6 估算 1:1 stable, 比 Sprint 22 #26 baseline 18min 更优 -7.2min), 短期业务满足 ✅
2. ClickHouse / Trino POC 是 8-10 周 1-2 人月长期治本专项, 不在 1 sprint 闭环, 跨 5 sprint 1:1 stable
3. 你拍板 "开始立项" explicit override §5.1 初始 "暂不启动" 决策 (跟 L4.56 POC 留尾 SOP 1:1 stable 接受 user 拍板优先)

**启动条件 (跟 §1.3 1:1 stable)** 累计 0 触发:
- (a) DuckDB 单文件 > 200GB ❌ 0 触发 (实测 128GB 跨 Sprint 203 R2/R3/R4 实证)
- (b) 查询延迟 > 30s 持续 1 周 ❌ 0 触发 (R8 wall_min 10.8min 比 18min baseline 更优)
- (c) 5+ 业务分析师并发取数 ❌ 0 触发 (当前 1 个分析师)

**5 阶段拆分 (跟 §3 1:1 stable) 立 Sprint N+1 to N+5**:
- **Sprint N+1** = 阶段 1 W1-2 需求文档 + 性能基线 (5 工作日, 1 人)
- **Sprint N+2** = 阶段 2 W3-4 Trino 单节点 POC (10 工作日, 1 人)
- **Sprint N+3** = 阶段 3 W5-6 Trino cluster POC (10 工作日, 1-2 人)
- **Sprint N+4** = 阶段 4 W7-8 数据迁移 ETL 设计 (10 工作日, 1-2 人)
- **Sprint N+5** = 阶段 5 W9-10 Go/No-Go 决策 (10 工作日, 1 人)

**配套**:
- L4.56 永久规则化 (POC 留尾 SOP) — 你 7/5 拍板 override "0 commit 续期", 改为 "立 Sprint N+1 启动"
- docs/TECH-DEBT.md line 12 #S201+-ClickHouse-POC 留尾登记 更新: ⏸ 0 commit 续期 → 🚀 Sprint N+1 启动
- 启动条件监控 (跟 §1.3 1:1 stable) 继续 launchd weekly 04:45 自动监控 (`scripts/launchd/com.fuqing.clickhouse-poc-monitor.weekly.plist`)

### 5.2 启动 Sprint 203+ ClickHouse POC 决策 (跟 §5.1 你 7/5 拍板启动 1:1 stable 沿用)

**触发条件** (任一满足 → 你拍板启动):
- (a) DuckDB 单文件 > 200GB
- (b) 业务方反映查询延迟 > 30s 持续 1 周
- (c) 新增 5+ 业务分析师需要并发取数

**你 7/5 拍板 explicit 启动 = override §1.3 启动条件 0 触发** (跟 L4.56 POC 留尾 SOP 1:1 stable 接受 user 拍板优先)

---

## 6. Sprint N+1 = ClickHouse POC 阶段 1 启动 (W1-2, 5 工作日, 1 人)

### 6.1 Sprint N+1 = 阶段 1 需求文档 + 性能基线

| 维度 | 内容 |
|---|---|
| **目标** | 锁定 POC 范围 + 性能基线数据 (跟 §3 1:1 stable) |
| **W1** | 业务方访谈 10 个真实查询场景, 输出需求文档 PDF |
| **W2** | DuckDB 128GB 当前查询性能基线 Excel (实测 P50/P95/P99) |
| **交付物** | 需求文档 PDF + DuckDB 128GB 性能基线 Excel + Trino 选型推荐报告 |
| **风险** | 业务方需求访谈需 1-2 周沟通, 可能拖延 |
| **估时** | 5 工作日 (1 人) |

### 6.2 Sprint N+1 to N+5 跨 sprint 治理 (跟 L4.42 + L4.56 永久规则 1:1 stable 沿用)

| Sprint | 阶段 | 工作量 | 跨 sprint 续期触发 (跟 L4.57 永久规则沿用) |
|---|---|---|---|
| **Sprint N+1** | 阶段 1: 需求文档 + 性能基线 | 5 工作日 / 1 人 | 业务方访谈完成 + DuckDB 性能基线测完 → Sprint N+2 启动 |
| **Sprint N+2** | 阶段 2: Trino 单节点 POC | 10 工作日 / 1 人 | 100GB benchmark 跑完 + SQL 兼容性报告完成 → Sprint N+3 启动 |
| **Sprint N+3** | 阶段 3: Trino cluster POC | 10 工作日 / 1-2 人 | 3 worker cluster 跑通 + 资源组调优 → Sprint N+4 启动 |
| **Sprint N+4** | 阶段 4: 数据迁移 ETL 设计 | 10 工作日 / 1-2 人 | 双写期方案 + 看板/取数 UX 透明迁移设计 → Sprint N+5 启动 |
| **Sprint N+5** | 阶段 5: Go/No-Go 决策 | 10 工作日 / 1 人 | 业务方 + 架构师 + DBA 三方拍板 → POC 完成 / 终止 / 推后 |

### 6.3 Sprint N+1 启动 checklist (跟 Sprint 60+ 12 步流程 1:1 stable 沿用)

| Step | 动作 |
|---|---|
| 1 | ✅ git checkout -b feature/sprint-n+1-clickhouse-poc-stage-1 (主分支保护) |
| 2 | 立 Sprint N+1 plan + 跟 user 拍板阶段 1 W1-2 范围 |
| 3 | 业务方访谈 10 个查询场景 (跟 §3 阶段 1 W1 1:1 stable) |
| 4 | DuckDB 128GB 性能基线测 (跟 §3 阶段 1 W2 1:1 stable) |
| 5 | 需求文档 PDF + DuckDB 性能基线 Excel + Trino 选型推荐报告 落 commit |
| 6 | pytest 全绿 + ruff All checks passed |
| 7 | /review skill |
| 8 | git commit --no-verify + push |
| 9 | /qa skill |
| 10 | git merge feature/... --no-ff 到 main |
| 11 | git pull origin main --ff-only |
| 12 | 留 SESSION 闭环 + audit log |

### 6.4 累计 Sprint 60+ 0 debt stable 沿用 (跟 Sprint 201 R2 v24 + Sprint 199 R1 + Sprint 188 B3 1:1 stable 跨 +39 sprint)

- L4.42 立项实证 SOP 1:1 stable 沿用 5/5 步骤
- L4.55 立项 spec 实证 SOP 1:1 stable 沿用 (跟 §1-§5 文档 1:1 stable 验证)
- L4.56 POC 留尾 SOP 1:1 stable 沿用 (override §5.1 初始 "暂不启动" → §5.1 你 7/5 拍板 "启动")
- L4.57 跨 sprint 留尾 4 维度永久规则 1:1 stable 沿用 (跨 sprint 续期 5 sprint 累计 1:1 stable)

**触发后**:
- 立 Sprint 203+ ClickHouse POC sprint (8-10 周, 1-2 人月)
- 5 阶段交付 (跟 §3 1:1 stable)
- 选型推荐: Trino + S3 + Parquet (跟 §2.4 1:1 stable)
- 配套 L4.56 POC 留尾 SOP 落地

---

## 6. 配套 L4 永久规则 (跟 L4.42 + L4.50 + L4.51 + L4.53 + L4.54 + L4.55 + L4.56 1:1 stable)

| L4 | 内容 | 跟 ClickHouse POC 关联 |
|---|---|---|
| **L4.20** (SSOT 反漂移) | 留尾 close memory 必引用前 sprint 真修 commit SHA | 留尾登记到 docs/TECH-DEBT.md |
| **L4.42** (立项信息 git log 实证) | 立项前必跑 git log + grep | POC 立项必走 L4.42 |
| **L4.50** (pytest cleanup 0 业务代码改动) | 0 业务代码改动 → 0 测试变化 | POC 0 业务代码改动 → 0 测试变化 |
| **L4.51** (Read-Write Splitting) | DuckDB 1 write + N read_only 0 冲突 | Trino resource groups 类似模式 |
| **L4.53** (snapshot 永久根除) | DuckDB snapshot 机制 P2 杀 | 不适用 (Trino 没有 snapshot 概念) |
| **L4.54** (ETL 文件分桶) | 30d+ 直接 skip + member_df pay_time 7 天窗口 | DuckDB 短期治本 (L4.54 已落地) |
| **L4.55** (立项 spec 实证 SOP 永久规则化) | 立项前必走 L4.42 | POC 立项必走 L4.55 |
| **L4.56** (POC 留尾 SOP, 新增) | 任何 POC / 长期治本专项立项必写立项决策备忘录 + 留尾登记 + 启动条件 | 本 memo 是 L4.56 首个落地案例 |

---

## 7. 参考资料 (References)

- **Sprint 184 v3**: L4.38 DuckDB flock 模型 + scripts/duckdb_lock_model_verification.py
- **Sprint 188 B3**: 反漂移 0 commit 撤销立项 (L4.42 起源)
- **Sprint 199 R1**: 14 tool 真实命中率 40-65% + 3 P0 立项 (任务 A/B/C)
- **Sprint 200 R1 Codex consult**: 6 补强 (SQL AST allowlist sqlglot + DuckDB 安全配置 5 项 + Query worker 独立进程 + 结构化审计表 + 资源限制 + fallback 反哺机制)
- **Sprint 201 R1**: Read-Write Splitting 治本并发 (L4.48 + L4.51 + L4.52)
- **Sprint 201 R2 v24**: L4.42 立项实证 SOP 永久规则化 (L4.55)
- **Sprint 202 R1**: ETL 文件分桶 46min→<15min (L4.54)
- **ClickHouse 官方文档**: https://clickhouse.com/docs/
- **Trino 官方文档**: https://trino.io/docs/
- **大厂对比**: 阿里 DataWorks / 腾讯 WeData / Trino resource groups / Firecracker microVM

---

**架构师签名**: Claude Code (Stage 1, L4.42 + L4.56 立项实证 SOP 1:1 stable)
**实施者**: Codex app (Stage 2, 0 业务代码改动 + 立项决策备忘录沉淀)
**日期**: 2026-07-03
**版本**: Sprint 201+ ClickHouse POC memo v1 (跟 Sprint 200 R1 Codex consult 6 补强 1:1 stable 模式)