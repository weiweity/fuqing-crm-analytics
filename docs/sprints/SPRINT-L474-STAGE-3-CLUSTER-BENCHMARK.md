# Sprint L4.74 Stage 3 Citus Cluster Benchmark

## 目标

验证 3 worker Citus cluster 在 10 人并发取数下是否比单节点 PostgreSQL 16 更稳。

## 拓扑

- coordinator: 1
- worker: 3
- shard key: `user_id`
- 大表: `orders`, `user_rfm_precompute`

## 指标

| 指标 | 目标 |
|---|---:|
| 10 并发成功率 | >= 99% |
| 核心场景 P95 | < 5s |
| RFM 下钻 P95 | < 8s |
| coordinator CPU | < 80% |
| worker skew | < 20% |

## 风险

Docker Compose 不能完全代表真实物理机网络和磁盘，需要 PC2 或服务器二次验证。
