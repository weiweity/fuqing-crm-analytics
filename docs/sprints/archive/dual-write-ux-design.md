# L4.74 看板 / 取数 UX 透明迁移设计

## 目标

PostgreSQL 16 POC、双写和切换期间，业务用户继续使用现有看板和取数入口，不感知 DuckDB 与 PostgreSQL 双栈差异。迁移只改变数据源和观测，不改变字段名、筛选项、导出格式和错误处理习惯。

## 约束

1. 不改前端业务口径。
2. 不让用户选择数据库。
3. 不暴露 SQL 方言、Citus worker、Parquet、UDF 等内部概念。
4. fallback 优先返回已有 DuckDB 结果。
5. 所有数据源差异进入诊断日志，不进入业务页面主体。

## 用户旅程

| 阶段 | 用户动作 | 后端路径 | 用户可见状态 |
|---|---|---|---|
| POC | 打开看板 | DuckDB primary + PostgreSQL shadow read | 无变化 |
| 双写 | 查询/导出 | PostgreSQL primary read + DuckDB fallback | 无变化或轻量重试提示 |
| 灰度 | 10% 用户命中 PG | PostgreSQL primary | 无变化 |
| 切换 | 全量用户命中 PG | PostgreSQL primary | 无变化 |
| 回滚 | PG 异常 | DuckDB primary | 仅看到查询恢复 |

## 后端响应契约

后端可以加诊断 header，但不要改变 JSON 业务结构：

| Header | 示例 | 用途 |
|---|---|---|
| `X-FQ-Data-Source` | `duckdb` / `postgresql16` | 内部排障 |
| `X-FQ-Fallback-Used` | `0` / `1` | 双写期间观测 |
| `X-FQ-Query-Class` | `interactive` / `shadow` / `batch` | 资源治理映射 |
| `X-FQ-Consistency-Date` | `2026-07-09` | 对账快照 |

前端只允许在 `fallback_used=1` 且请求耗时明显变长时展示现有轻量错误层，不新增数据库说明文案。

## 页面状态

| 状态 | 条件 | 展示 |
|---|---|---|
| loading | 请求中 | 沿用现有 loading |
| ready | 任一 primary/fallback 成功 | 正常展示 |
| degraded | PG 失败但 DuckDB fallback 成功 | 结果展示 + 轻量可重试提示 |
| failed | 两边都失败 | 沿用现有错误层 |

## 导出 / 取数

导出文件必须保持：

- 文件命名规则不变。
- Sheet 名不变。
- 字段顺序不变。
- 数值单位不变。
- RFM/R 区间中文标签不变。

取数平台只记录 `data_source` 和 `fallback_used` 到审计日志；业务人员下载的 CSV/XLSX 不出现这些内部字段。

## 观测

后端记录：

- endpoint
- query_type
- data_source
- latency_ms
- fallback_used
- consistency_snapshot_date
- user-facing success/failure

Stage 4 通过线：

1. 连续 7 天 fallback 次数为 0，或每次都有明确可接受原因。
2. 10 个业务场景字段/排序/导出格式 0 差异。
3. 业务方无需培训即可继续使用。
4. PostgreSQL 异常时 DuckDB fallback 不让用户处理数据库差异。

## Rollout

| 批次 | 流量 | 条件 |
|---|---:|---|
| shadow | 0% 用户读 PG | 只跑 shadow read + 校验 |
| canary | 10% | 一致性连续 3 天通过 |
| beta | 50% | P95 达标 + fallback 可解释 |
| primary | 100% | Go 决策通过 |

## 回滚

回滚只改 data source flag，不改前端资源：

1. `primary=duckdb`
2. `postgres_shadow=true`
3. 保留双写和校验，直到异常关闭
4. 复盘后重新进入 canary
