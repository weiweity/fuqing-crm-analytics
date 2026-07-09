# RFM 高并发临时使用通知

> Sprint 205+ L4.74 P0 缓解项。适用窗口：PostgreSQL 16 分布式 POC 和老客预计算正式接管前。

## 背景

PC2 端 122GB DuckDB 单文件在 10 位业务分析师同时取数时，会触发 read pool 排队、503 友好降级或查询超时。当前 `.env` 已确认 `FQ_READ_POOL_SIZE=10`，短期能缓解排队，但不能把 DuckDB 单文件变成真正的多用户数据库。

## 临时使用规则

1. 老客分析、RFM、品类下钻等重查询尽量错峰使用，避免 10 人同时点同一批报表。
2. 页面出现 503 或 read pool full 时，等待 30 秒后重试，不要连续刷新。
3. 批量导出、即席查询和老客分析不要同时跑。
4. ETL 跑批期间不直连 DuckDB，不停 uvicorn，必要时走后端 HTTP API。

## 短期技术动作

- `FQ_READ_POOL_SIZE=10` 已在 Mac dev `.env` 中生效。
- L4.72.2 已有 read semaphore timeout，池满返回 503，避免无限阻塞。
- L4.72.4 新增 `scripts/precompute_old_customer_9_sub_modules.py`，用于把 7/30/180/365 天热窗口预计算到 JSON cache。

## 长期治本

L4.74 PostgreSQL 16 分布式 POC 接管后，目标是 10+ 业务分析师并发取数、查询 P95 < 5s、看板 UX 透明迁移。
