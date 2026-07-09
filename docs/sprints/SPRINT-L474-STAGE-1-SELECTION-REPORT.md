# Sprint L4.74 Stage 1 PostgreSQL 16 选型报告

## 推荐

推荐 PostgreSQL 16 + Citus 作为 L4.74 POC 主线，ClickHouse 和 Trino 保留为备选。

## 判断

| 维度 | PostgreSQL 16 | ClickHouse | Trino |
|---|---|---|---|
| DuckDB SQL 兼容 | 高 | 中 | 中 |
| OLTP/OLAP 双用 | 高 | 低 | 低 |
| 10 人并发 | 中到高 | 高 | 高 |
| 运维复杂度 | 中 | 中 | 高 |
| 迁移风险 | 低 | 中 | 高 |

## POC 路径

1. 单节点 PostgreSQL 16 验证 SQL 兼容。
2. Citus 3 worker 验证并发和横向扩展。
3. DuckDB -> Parquet -> PostgreSQL 验证迁移链路。
4. 双写期验证数据一致性。

## Go 条件

10 个场景 P95 达标、数据一致性达标、运维成本可接受，则 Go。
