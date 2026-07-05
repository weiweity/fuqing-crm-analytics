# DuckDB → Trino SQL 兼容性报告

> Sprint N+2 交付物。范围只覆盖 POC benchmark 与未来迁移风险识别，不修改 `backend/services/*` 业务 SQL 口径。

## 1. 结论

10 个 POC 场景可用 Trino SQL 表达。主要重写点集中在 DuckDB 便捷语法、复杂类型命名、文件读写函数和少量日期/百分位函数。服务层迁移前仍需逐个 service 走 L4.5 FilterBuilder + `?` 参数化 + L4.19 `o.channel` 别名规则。

## 2. 兼容性矩阵

| DuckDB 写法 | Trino 状态 | POC 处理 |
|---|---|---|
| `SELECT * EXCLUDE(col)` | 需重写 | Trino 当前文档未列 `SELECT * EXCLUDE/EXCEPT`，迁移时显式枚举列 |
| `LIST` / `STRUCT` | 需重写 | 改为 `ARRAY` / `ROW` |
| `read_parquet('path')` | 需重写 | 通过 Hive connector 外部表读取 S3 Parquet |
| `COPY ... TO PARQUET` | 需重写 | 由 `scripts/trino_poc/generate_dataset.py` 或后续 ETL 写 Parquet |
| `DATE_TRUNC('day', col)` | 兼容 | Trino / DuckDB 都支持，保留 |
| `date_diff('day', a, b)` | 兼容但需验证参数类型 | POC 显式 `CAST(... AS DATE)` |
| `LAG` / `LEAD` / `ROW_NUMBER` | 兼容 | POC 品类流转使用 `ROW_NUMBER()` |
| `COUNT(DISTINCT ...)` | 兼容 | 保留精确去重；不默认改 `approx_distinct` |
| `FULL OUTER JOIN` | 兼容 | POC top-N YOY 保留 |
| `NULLS LAST` | 兼容 | POC top-N YOY 保留 |
| `BOOLEAN` 聚合 `MAX(bool)` | 方言差异 | POC 改为 `SUM(CASE WHEN bool THEN 1 ELSE 0 END) > 0` |
| `DECIMAL(12,2)` | 兼容 | Parquet schema 显式 decimal128(12,2) |

## 3. POC SQL 防线

- 所有 10 个场景使用 `FROM hive.crm.orders o` 或等价别名。
- 任何 `channel` 过滤或聚合都写 `o.channel`，避免 JOIN 后 Binder ambiguity。
- R 区间复购使用 SSOT 边界：`0-30 / 31-90 / 91-180 / 181-365 / 366-730 / 731+`。
- benchmark SQL 是固定 POC 查询，不接收用户输入；未来接入 API 时必须回到 FilterBuilder + DB-API 参数化。

## 4. 后续迁移前置检查

1. 对每个候选 service 先跑 CodeGraph callers / impact。
2. 把 DuckDB 独有 SQL 列成 per-service diff，不做全局替换。
3. 每个 service 至少用 5 case regression test 锁住 DuckDB vs Trino 一致性。
4. 任何 contract 字段变更同步 `backend/contracts/*.py` 与 `frontend-vue3/src/api/types.ts`。

## 5. 官方参考

- Trino container: https://trino.io/docs/current/installation/containers.html
- Trino Hive connector: https://trino.io/docs/current/connector/hive.html
- Trino S3 object storage: https://trino.io/docs/current/object-storage/file-system-s3.html
- Trino resource groups: https://trino.io/docs/current/admin/resource-groups.html
