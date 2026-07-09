# PostgreSQL 16 Citus Cluster 运维手册

> Sprint 205+ L4.74 阶段 3 运维交付物。

## 启动

```bash
docker compose -f docker-compose-postgresql16-citus-cluster.yml up -d
docker compose -f docker-compose-postgresql16-citus-cluster.yml ps
```

默认端口：

| 服务 | 端口 |
|---|---:|
| coordinator | 5434 |
| worker 1-3 | docker internal |

## 初始化检查

```sql
SELECT citus_version();
SELECT * FROM pg_dist_node;
SELECT crm_semantic.r_interval(current_date - 40, current_date);
```

如果 worker 未注册，先进入 coordinator 手动执行：

```sql
SELECT citus_add_node('citus-worker-1', 5432);
SELECT citus_add_node('citus-worker-2', 5432);
SELECT citus_add_node('citus-worker-3', 5432);
```

## 表分布建议

| 表 | 策略 | 分布键 |
|---|---|---|
| orders | distributed | user_id |
| user_first_purchase | reference 或 distributed | user_id |
| user_rfm_precompute | distributed | user_id |
| 小维表 | reference | 无 |

## 扩缩容

1. 新增 worker service 和 volume。
2. 启动新 worker。
3. coordinator 执行 `citus_add_node`。
4. 对大表执行 rebalance，低峰期操作。

## 告警

重点看四类指标：

- coordinator CPU / memory / active connections
- worker shard imbalance
- 慢查询 P95/P99
- 连接池等待时间

## 回滚

POC 阶段不替换生产 DuckDB。回滚只需停止 Citus compose，保留 DuckDB 读路径。
