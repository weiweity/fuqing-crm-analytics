# Sprint L4.74 Stage 2 SQL 兼容性报告

## 已知兼容

- 标准 `SELECT / JOIN / GROUP BY / CASE`
- `COUNT(DISTINCT ...)`
- `DATE_TRUNC`
- `BOOL_OR`
- 参数化过滤语义

## 需改写

| DuckDB 语法 | PostgreSQL 16 方案 |
|---|---|
| `DATEDIFF('day', a, b)` | `b::date - a::date` |
| `?::TIMESTAMP` DB-API 参数 | psycopg `$1::timestamp` 或 SQLAlchemy bind |
| `COPY ... FORMAT PARQUET` | staging 工具或 FDW/外部 loader |
| DuckDB 特定 list/struct | 拆成 JSONB 或维表 |

## UDF

RFM 与 R 区间口径落在 `scripts/postgresql16_udf/`，其中 R 区间已按 `backend/semantic/segments.py:R_INTERVALS` 实证。
