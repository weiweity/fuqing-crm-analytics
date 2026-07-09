# Sprint L4.74 Stage 5 风险评估与成本估算

## 风险总览

| 风险 | 等级 | 触发 | 缓解 |
|---|---|---|---|
| 数据一致性 | 高 | DuckDB 与 PG row/amount/RFM 差异 | 1 个月双写 + 日维度校验 |
| 10 人并发 | 高 | P95 > 30s 或成功率 < 99% | Citus 3 worker + role-level 资源治理 |
| SQL 兼容 | 中 | DuckDB 特有语法无法迁移 | SQL 兼容报告 + UDF |
| 运维复杂度 | 中 | worker 故障、rebalance、备份恢复不熟 | runbook + 演练 |
| 业务接受度 | 中 | 字段/导出格式变化 | UX 透明迁移 + DuckDB fallback |
| 成本膨胀 | 中 | Citus 机器/人力高于备选 | 阶段性 Go/No-Go |

## 成本估算

| 方案 | 资源 | 年成本估算 | 适用 |
|---|---|---:|---|
| DuckDB 继续优化 | PC2 本机 + 预计算 | 既有成本 | 短中期缓解 |
| PostgreSQL 16 单节点 | 32C64G + 1TB NVMe | 0.8 万/年 | 单用户/低并发 |
| Citus 3 worker | 3 台中配机器 + coordinator | 2.4 万/年 | 10 人并发 POC |
| ClickHouse Cloud | 托管 OLAP | 1 万/年起 | 纯 OLAP |
| Trino cluster | coordinator + 3 worker + S3 | 5 万/年起 | 联邦查询 |

## 人力估算

| 阶段 | 人力 |
|---|---:|
| Stage 3 Citus cluster + benchmark | 1-2 人 / 2 周 |
| Stage 4 ETL + UDF + 双写 | 1-2 人 / 2 周 |
| Stage 5 决策 + 风险成本 | 1 人 / 2 周 |
| 运维交接 | 0.5 人 / 1 周 |

总计仍按 L4.74 memo：8-10 周，1-2 人月量级。

## ROI 判断

Go 倾向：

- 10 人并发是长期常态。
- Citus P95 显著优于 DuckDB。
- 双写差异可解释且连续 7 天达标。
- 运维愿意接 Citus。

No-Go 倾向：

- 10 人并发只是短期峰值。
- L4.70/L4.71/L4.72.4 已把核心查询压到可接受范围。
- Citus 运维成本超过收益。
- ClickHouse/Trino 对当前查询形态更适合。

## 建议

先进入双写 POC，不做立即生产切换。把“Citus 是否值得生产化”的判断延后到 Stage 3 benchmark 和 Stage 4 连续 7 天一致性校验之后。
