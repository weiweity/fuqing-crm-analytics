# L4.74 双写期方案

## 范围

双写期持续 1 个月。DuckDB 继续作为生产回滚源，PostgreSQL 16/Citus 作为 shadow/primary 迁移目标。Stage 4 不直接删除 DuckDB，不改变现有看板 URL 和导出格式。

## 数据流

```mermaid
flowchart LR
    A["现有 ETL"] --> B["DuckDB production"]
    B --> C["DuckDB -> Parquet ETL"]
    C --> D["PostgreSQL 16 staging"]
    D --> E["Citus serving"]
    E --> F["shadow/primary read"]
    B --> G["DuckDB fallback"]
    F --> H["看板 / 取数"]
    G --> H
```

## 每日流程

1. ETL 写入 DuckDB。
2. `duckdb_to_parquet_etl.py` 导出指定表和 snapshot manifest。
3. PostgreSQL 16 staging 加载 Parquet。
4. Citus 分布大表或刷新分区。
5. `validate_dual_write_consistency.py` 对账。
6. 看板 shadow read 记录差异。

## 一致性校验

| 层 | 校验 | 通过线 |
|---|---|---|
| row count | orders / user_first_purchase / user_rfm_precompute | 差异 = 0 |
| amount sum | orders actual_amount 日维度 | 差异 <= 0.1% |
| user count | distinct user_id 日维度 | 差异 <= 0.1% |
| RFM | r_interval / rfm_segment 分布 | 差异 = 0 |
| UX | 10 个场景字段、排序、导出格式 | 差异 = 0 |

校验脚本：

```bash
python3 scripts/etl/validate_dual_write_consistency.py \
  --snapshot-date 2026-07-09 \
  --postgres-dsn postgresql://fuqing:***@localhost:5434/fuqing_crm
```

先 dry-run 看 SQL：

```bash
python3 scripts/etl/validate_dual_write_consistency.py \
  --snapshot-date 2026-07-09 \
  --dry-run
```

## 切换条件

1. 连续 7 天核心表 row count 差异为 0。
2. 核心金额指标差异小于 0.1%。
3. 老客/RFM 10 个业务场景 P95 < 5s，RFM 下钻 P95 < 8s。
4. fallback 次数连续 7 天为 0 或有明确可接受原因。
5. 业务方确认字段、口径、导出格式不变。
6. 运维确认备份、恢复、监控和扩容流程可执行。

## 回滚

保留 DuckDB read path 和原有 `.env` 配置。切换失败时：

1. `primary_data_source=duckdb`
2. `postgres_shadow_read=true`
3. 暂停 PostgreSQL primary read。
4. 继续保留 Parquet export 和校验，直到问题定位。

## 风险

| 风险 | 缓解 |
|---|---|
| PostgreSQL schema 与 DuckDB 漂移 | manifest + SQL 兼容报告 |
| RFM/R 区间口径漂移 | UDF 由 `segments.py` SSOT 实证 |
| 双写延迟 | snapshot_date 分区 + manifest |
| 业务误解 fallback | UX 不暴露数据库名，只进诊断 header |
| 运维复杂度 | runbook + role-level 资源治理 |
