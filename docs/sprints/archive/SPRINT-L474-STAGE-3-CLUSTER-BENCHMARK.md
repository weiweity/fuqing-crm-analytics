# Sprint L4.74 Stage 3 Citus Cluster Benchmark

## 目标

验证 PostgreSQL 16 + Citus 3 worker 在 10 个业务分析师并发取数下是否能替代 DuckDB 单文件 122GB 的高并发读路径。

## 拓扑

| 方案 | 节点 | 说明 |
|---|---|---|
| DuckDB baseline | 1 file | 当前生产回滚源 |
| PostgreSQL 16 single node | 1 postgres | Stage 2 单节点 POC |
| Citus cluster | coordinator + 3 worker | Stage 3 横向扩展 POC |

Citus 分布建议：

- `orders` by `user_id`
- `user_rfm_precompute` by `user_id`
- `user_first_purchase` by `user_id` 或 reference
- 小维表 reference

## 10 个查询场景

| # | 场景 | 表/模块 | DuckDB 基线风险 | Citus 验收 |
|---:|---|---|---|---|
| 1 | 老客 overview | customer-health overview | 共享池阻塞 | P95 < 5s |
| 2 | RFM 3 周期 | rfm_analysis | 3 周期全表聚合 | P95 < 8s |
| 3 | R 区间分布 | user_rfm_precompute | R_INTERVALS 口径漂移 | 0 口径差异 |
| 4 | 复购周期 | health repurchase | 多 CTE 聚合 | P95 < 5s |
| 5 | cohort retention | health cohort | 时间窗口 join | P95 < 8s |
| 6 | value tiers | health tiers | 金额聚合 | P95 < 5s |
| 7 | tier flow | health tier_flow | 前后期 join | P95 < 8s |
| 8 | category drilldown | rfm_category_drilldown | 品类维度大 group by | P95 < 8s |
| 9 | channel scores | channel_scores | 多渠道并发读 | P95 < 5s |
| 10 | ad-hoc daily GSV | orders daily | 分析师取数高峰 | P95 < 5s |

## 测试矩阵

| 维度 | 值 |
|---|---|
| 并发 | 1 / 5 / 10 |
| 数据量 | 122GB production snapshot + 10% sample |
| 运行轮次 | warmup 2 + measured 3 |
| 指标 | P50 / P95 / P99 / error rate / fallback count |
| 资源 | coordinator CPU/mem, worker CPU/mem, temp bytes, active connections |

## 通过线

| 指标 | 目标 |
|---|---:|
| 10 并发成功率 | >= 99% |
| 核心场景 P95 | < 5s |
| RFM 下钻 P95 | < 8s |
| fallback 次数 | 连续 7 天 0 |
| worker skew | < 20% |
| SQL 口径差异 | 0 个 blocker |

## 记录模板

| 场景 | DuckDB P95 | PG16 single P95 | Citus P95 | Citus P99 | error rate | 结论 |
|---|---:|---:|---:|---:|---:|---|
| 老客 overview | TBD | TBD | TBD | TBD | TBD | 待跑 |
| RFM 3 周期 | TBD | TBD | TBD | TBD | TBD | 待跑 |
| R 区间分布 | TBD | TBD | TBD | TBD | TBD | 待跑 |
| 复购周期 | TBD | TBD | TBD | TBD | TBD | 待跑 |
| cohort retention | TBD | TBD | TBD | TBD | TBD | 待跑 |
| value tiers | TBD | TBD | TBD | TBD | TBD | 待跑 |
| tier flow | TBD | TBD | TBD | TBD | TBD | 待跑 |
| category drilldown | TBD | TBD | TBD | TBD | TBD | 待跑 |
| channel scores | TBD | TBD | TBD | TBD | TBD | 待跑 |
| ad-hoc daily GSV | TBD | TBD | TBD | TBD | TBD | 待跑 |

## 风险

Docker Compose 不能完全代表真实物理机网络和磁盘。Stage 3 只能作为 Mac dev + PC2 端 POC 依据；Go/No-Go 必须结合连续 7 天双写一致性和业务高峰窗口。
