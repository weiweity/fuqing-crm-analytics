# Sprint L4.74 Stage 5 风险评估与成本估算

## 风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| 数据一致性 | 高 | 双写期 + 日维度校验 |
| SQL 兼容 | 中 | UDF + 兼容性报告 |
| 10 人并发 | 高 | Citus + 连接池 + 预计算 |
| 运维复杂度 | 中 | runbook + compose + 告警 |
| 业务接受度 | 中 | UX 透明迁移 |

## 年成本估算

| 方案 | 资源 | 估算 |
|---|---|---:|
| PostgreSQL 16 单节点 | 32C64G + NVMe | 0.8 万/年 |
| Citus 3 worker | 3 台中配机器 | 2.4 万/年 |
| ClickHouse Cloud | 托管 OLAP | 1 万/年起 |
| Trino cluster | coordinator + workers | 5 万/年起 |

## 建议

先跑单节点兼容性，再跑 Citus 并发验证。若 Citus 达标，进入双写期；若不达标，回到 ClickHouse/Trino 备选。
