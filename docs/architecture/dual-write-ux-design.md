# L4.74 看板 / 取数 UX 透明迁移设计

## 目标

PostgreSQL 16 POC 期间，业务用户继续使用现有看板和取数入口，不感知 DuckDB 与 PostgreSQL 双栈切换。

## UX 原则

1. 默认仍展示原有页面和字段名。
2. 迁移期只在错误信息和诊断信息里标注数据源。
3. 对业务方只暴露“查询中、可重试、结果已生成”三类状态。
4. 失败时优先回退 DuckDB 结果，禁止让用户处理数据库差异。

## 后端路由策略

| 阶段 | 读路径 | 写路径 | 用户感知 |
|---|---|---|---|
| POC | DuckDB + PostgreSQL shadow read | DuckDB | 无 |
| 双写 | PostgreSQL primary read, DuckDB fallback | DuckDB + Parquet | 无 |
| 切换 | PostgreSQL primary | PostgreSQL | 无 |

## 前端状态

- `loading`: 保持原 loading。
- `degraded`: 后端返回 fallback header 时展示轻量重试提示。
- `failed`: 仍沿用现有错误层，不展示数据库内部错误。

## 观测

后端记录 query_type、data_source、latency_ms、fallback_used。迁移验收看 P95、错误率、fallback 次数和业务抽样一致性。
