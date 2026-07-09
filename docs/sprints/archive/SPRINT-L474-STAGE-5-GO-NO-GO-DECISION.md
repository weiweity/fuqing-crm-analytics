# Sprint L4.74 Stage 5 Go / No-Go 决策

## 推荐状态

**当前推荐: Conditional Go to dual-write POC, No-Go to immediate production cutover.**

理由：

1. 启动条件 b + c 已真触发，长期治本需要继续。
2. Citus/ETL/UDF/双写校验资产已具备 POC 启动条件。
3. 真实 Go 仍依赖 PC2 端连续 7 天数据一致性和 10 并发 benchmark。

## Go 条件

| 条件 | 目标 |
|---|---|
| 10 个核心场景 | Citus P95 < 5s，RFM 下钻 P95 < 8s |
| 并发 | 10 并发成功率 >= 99% |
| 双写 | 连续 7 天 row count 0 差异 |
| 金额 | actual_amount 日维度差异 <= 0.1% |
| UX | 字段、筛选、导出格式 0 差异 |
| 运维 | runbook 的备份、恢复、扩容、回滚可执行 |
| 风险 | DBA/业务方/架构师三方确认 |

## No-Go 条件

| 条件 | 处理 |
|---|---|
| Citus 10 并发 P95 仍 > 30s | 保留 DuckDB + L4.70/L4.71/L4.72.4，转 ClickHouse/Trino 评估 |
| SQL 改造量 > 10% | 暂停 primary cutover，只做 shadow read |
| 双写差异无法解释 | 停止 PG primary，保留 DuckDB fallback |
| 运维成本 > 替代方案 | 回到 ClickHouse/Trino 成本比较 |
| 业务导出格式变化 | No-Go，必须先修 UX/导出兼容 |

## 决策表

| 角色 | 拍板内容 | 状态 |
|---|---|---|
| 业务方 | 字段、口径、导出格式不变 | 待确认 |
| 架构师 | SQL 兼容、回滚策略、数据源 flag | 待确认 |
| DBA/运维 | Citus 备份、恢复、扩缩容、监控 | 待确认 |

## 当前决策

进入 Stage 4 双写 POC 准备，不切生产 primary。等 10 场景 benchmark + 连续 7 天一致性校验完成后再做最终 Go/No-Go。
