# Sprint L4.74 Stage 5 POC 总结

## 结论

当前状态是 **POC Ready / 不直接生产切换**。Stage 2 已完成单节点骨架，Stage 3+4+5 本轮补齐 Citus 3 worker、资源治理、Parquet ETL manifest、RFM/R 区间 UDF、双写校验脚本、UX 透明迁移和 Go/No-Go 决策材料。

## 触发背景

| 启动条件 | 阈值 | 实证 | 状态 |
|---|---|---|---|
| DuckDB > 200GB | > 200GB | PC2 端 122GB | 未触发 |
| 查询 P95 > 30s 持续 1 周 | > 30s | PC2 端“取不了数”跨 sprint 持续 | 真触发 |
| 5+ 分析师并发 | >= 5 | PC2 端 10 业务分析师 | 真触发 |

## 5 阶段交付物

| 阶段 | 交付物 | 状态 | 证据 |
|---|---|---|---|
| Stage 1 | 需求与基线 | 已落模板 | `SPRINT-L474-STAGE-1-*` |
| Stage 2 | PostgreSQL 16 单节点 | 已落 compose + tests | `docker-compose-postgresql16-single-node.yml` |
| Stage 3 | Citus cluster | 本轮补强 | 3 worker compose + runbook + benchmark |
| Stage 4 | Parquet ETL + UDF + 双写 | 本轮补强 | ETL manifest + UDF + dual write validator |
| Stage 5 | Go/No-Go + 风险成本 | 本轮补强 | 本文件 + 决策 + 成本表 |

## POC 验收矩阵

| 维度 | 通过线 | 当前状态 |
|---|---|---|
| 10 并发成功率 | >= 99% | 待 PC2/集群实跑 |
| 核心场景 P95 | < 5s | 待实跑 |
| RFM 下钻 P95 | < 8s | 待实跑 |
| 双写 row count | 连续 7 天 0 差异 | 校验脚本已就绪 |
| 金额差异 | <= 0.1% | 校验脚本已就绪 |
| UX 差异 | 0 字段/导出差异 | 设计已锁 |
| 回滚 | 只切 data source flag | 方案已锁 |

## 当前建议

1. Mac dev 只做 POC 骨架和静态验证，不把 PostgreSQL 直接设为生产 primary。
2. PC2 端按 runbook 启动 Citus，跑 10 场景 benchmark。
3. 连续 7 天跑双写校验后再进入 Go/No-Go。
4. 若 Citus 未达标，保留 DuckDB + L4.70/L4.71/L4.72.4 短中期方案，同时评估 ClickHouse/Trino。

## 仍需人工实证

- PC2 端真实 10 人并发窗口。
- 122GB 全量 Parquet export 时长与磁盘占用。
- PostgreSQL 16 load Parquet 的实际策略。
- DBA 对 Citus 运维复杂度的接受度。
- 业务方对灰度/回滚流程的确认。
