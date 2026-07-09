# Sprint L4.74 Stage 2 Benchmark 报告模板

## 范围

对比 DuckDB 122GB 与 PostgreSQL 16 单节点在 10 个业务场景下的 P50/P95/P99、错误率和资源使用。

## 结果表

| 场景 | DuckDB P95 | PostgreSQL 16 P95 | 差异 | 结论 |
|---|---:|---:|---:|---|
| 老客概览 | 待测 | 待测 | 待测 | 待测 |
| RFM 8 象限 | 待测 | 待测 | 待测 | 待测 |
| 渠道健康评分 | 待测 | 待测 | 待测 | 待测 |

## 命令

```bash
docker compose -f docker-compose-postgresql16-single-node.yml up -d
python3 scripts/etl/duckdb_to_parquet_etl.py --dry-run
```

## 验收

单节点 PostgreSQL 16 至少要证明 SQL 兼容和数据装载可行；性能若不足，进入 Citus cluster 阶段验证横向扩展。
