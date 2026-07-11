# PostgreSQL 16 Citus Cluster 运维手册

> Sprint 205+ L4.74 阶段 3 运维交付物。目标是验证 10 个业务分析师并发取数时，PostgreSQL 16 + Citus 3 worker 能否比 DuckDB 单文件更稳。

## 1. 拓扑

| 角色 | 服务名 | 端口 | 说明 |
|---|---|---:|---|
| coordinator | `citus-coordinator` | `5434:5432` | SQL 入口、metadata、worker 注册 |
| worker 1 | `citus-worker-1` | internal | shard executor |
| worker 2 | `citus-worker-2` | internal | shard executor |
| worker 3 | `citus-worker-3` | internal | shard executor |

默认镜像是 `citusdata/citus:14.1-pg16`，可用 `CITUS_IMAGE=...` 覆盖。所有密码只用于本地 POC；生产必须改 `.env` 或密钥管理。

## 2. 启动

```bash
docker compose -f docker-compose-postgresql16-citus-cluster.yml config
docker compose -f docker-compose-postgresql16-citus-cluster.yml up -d
docker compose -f docker-compose-postgresql16-citus-cluster.yml ps
```

本 compose 使用 `citus_pg16_*` named volumes，避免旧 POC 的 PGDATA 被 PostgreSQL 16 镜像复用。若需要重建空集群：

```bash
docker compose -f docker-compose-postgresql16-citus-cluster.yml down -v
```

初始化脚本会执行三件事：

1. 等待 `citus-worker-1..3` `pg_isready`。
2. 在 coordinator 创建 `citus` extension 并注册 worker。
3. 建立 `crm_admin` helper、`crm_semantic` UDF 和资源治理角色。

## 3. 初始化检查

```bash
docker compose -f docker-compose-postgresql16-citus-cluster.yml exec citus-coordinator \
  psql -U fuqing -d fuqing_crm -c "SELECT citus_version();"

docker compose -f docker-compose-postgresql16-citus-cluster.yml exec citus-coordinator \
  psql -U fuqing -d fuqing_crm -c "SELECT nodename, nodeport, isactive FROM pg_dist_node ORDER BY nodename;"

docker compose -f docker-compose-postgresql16-citus-cluster.yml exec citus-coordinator \
  psql -U fuqing -d fuqing_crm -c "SELECT crm_semantic.r_interval(current_date - 40, current_date);"
```

期望：

- `pg_dist_node` 至少 3 行。
- `crm_semantic.r_interval` 返回 `近2-3个月已购客`。
- `crm_admin.resource_governance` 能看到 `crm_interactive`、`crm_shadow_read`、`crm_batch`。

## 4. 表分布策略

| 表 | 策略 | 分布键 | 说明 |
|---|---|---|---|
| `orders` | distributed | `user_id` | 订单事实表，最大表，按用户聚合最多 |
| `user_rfm_precompute` | distributed | `user_id` | RFM 预计算表，跟订单同分布键 |
| `user_first_purchase` | distributed 或 reference | `user_id` | 与订单 join 时分布；小表可 reference |
| `fact_rfm_long` | distributed | `dimension_key` | 宽表快照，按维度键分布 |
| 小维表 | reference | 无 | 渠道、品类、映射表 |

首次建表和导入后执行：

```sql
SELECT crm_admin.distribute_if_exists('orders', 'user_id');
SELECT crm_admin.distribute_if_exists('user_rfm_precompute', 'user_id');
SELECT crm_admin.distribute_if_exists('user_first_purchase', 'user_id');
```

## 5. 资源治理

PostgreSQL/Citus 没有 Trino resource group 原语，本 POC 用 role-level 设置记录 query class 基线。`crm_interactive`、`crm_shadow_read`、`crm_batch` 是 POC role class，不直接承诺生产登录用户已经被限流；生产要在 PgBouncer/应用 DSN 侧创建对应 login role，或在连接建立后显式套用同一组 `ALTER ROLE ... SET` 参数。

| query class | role | connection limit | statement timeout | work_mem | temp_file_limit |
|---|---|---:|---:|---:|---:|
| 看板交互 | `crm_interactive` | 20 | 8s | 64MB | 4GB |
| shadow read | `crm_shadow_read` | 10 | 15s | 64MB | 6GB |
| ETL/批处理 | `crm_batch` | 4 | 30min | 256MB | 32GB |

应用层后续可以通过 PgBouncer 或连接 DSN 把看板请求路由到带 `crm_interactive` 设置的登录用户，把 Parquet load 和双写校验路由到带 `crm_batch` 设置的登录用户。

## 6. 数据导入

先用 DuckDB 导出 Parquet：

```bash
python3 scripts/etl/duckdb_to_parquet_etl.py \
  --snapshot-date "$(date +%F)" \
  --output-dir data/processed/postgresql16_parquet
```

导入 PostgreSQL 16 可选两种方式：

1. 本地 POC：用 `COPY` 从容器挂载目录导入 CSV/Parquet 中间产物。
2. 生产候选：用 `COPY FROM PROGRAM`、`aws_s3` 或外部 loader 拉 S3 Parquet。

本仓库当前只锁 DuckDB -> Parquet 和双写校验脚本，不在 POC 阶段直接改生产读路径。

## 7. 10 并发 benchmark

执行顺序：

1. 单用户 warmup 每个场景跑 2 次。
2. 10 并发跑 3 轮，记录 P50/P95/P99、错误率、fallback 次数。
3. 分别跑 DuckDB、PostgreSQL 16 单节点、Citus 3 worker。
4. Citus 每轮后记录 `pg_dist_node`、worker CPU、慢查询和 temp file。

通过线：

- 10 并发成功率 >= 99%。
- 核心看板 P95 < 5s。
- RFM 下钻 P95 < 8s。
- coordinator CPU < 80%。
- worker shard skew < 20%。

## 8. 监控

| 指标 | SQL/来源 | 告警 |
|---|---|---|
| active connection | `pg_stat_activity` | `crm_interactive` > 18 持续 5min |
| slow query | `pg_stat_statements` | P95 > 5s 持续 15min |
| shard skew | `citus_shards` / table size | 最大 worker 比最小 worker > 1.2x |
| temp file | `pg_stat_database.temp_bytes` | 1h 增量 > 20GB |
| worker health | `pg_dist_node.isactive` | 任一 worker inactive |

## 9. 扩容

1. 在 compose 里新增 `citus-worker-4` 和 volume。
2. `docker compose up -d citus-worker-4`。
3. coordinator 执行 `SELECT citus_add_node('citus-worker-4', 5432);`。
4. 低峰执行 rebalance。
5. 重跑 10 场景 benchmark。

回退扩容：

1. 停止业务写入到 PostgreSQL 影子集群。
2. `SELECT citus_drain_node('citus-worker-4', 5432);`
3. `SELECT citus_remove_node('citus-worker-4', 5432);`
4. 删除 compose service 和 volume。

## 10. 故障处理

### worker 未注册

```sql
SELECT * FROM pg_dist_node ORDER BY nodename;
SELECT citus_add_node('citus-worker-1', 5432);
```

如果 worker healthcheck 失败，先看容器日志：

```bash
docker compose -f docker-compose-postgresql16-citus-cluster.yml logs citus-worker-1
```

### 查询排队或超时

1. 查 `pg_stat_activity` 是否有长事务。
2. 查 `crm_admin.resource_governance` 确认 role 限额生效。
3. 看是否把批处理误接到 `crm_interactive`。
4. 业务方先回退 DuckDB fallback，不让用户处理数据库差异。

### 数据不一致

1. 跑 `scripts/etl/validate_dual_write_consistency.py --snapshot-date YYYY-MM-DD --dry-run` 确认 SQL。
2. 对异常日期跑真实校验。
3. 若金额差异 > 0.1%，暂停 PostgreSQL primary read。
4. 保留 DuckDB 作为回滚源。

## 11. 回滚

POC 阶段不替换生产 DuckDB。回滚只需：

```bash
docker compose -f docker-compose-postgresql16-citus-cluster.yml down
```

生产灰度期回滚：

1. 应用 data source flag 改回 DuckDB。
2. 停止 PostgreSQL primary read，只保留 shadow read。
3. 继续 Parquet 导出和校验，直到异常定位完成。
4. 不删除 Citus volume，保留排查现场。
