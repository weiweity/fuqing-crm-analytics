# 渠道后续购买受信 run 绑定（G3b1）

日期：2026-09-07。任务分支 `codex/channel-followup-run-binding`。状态：**STORE_ONLY**。worker / HTTP / native **NOT RUN**。

本文件记录 G3b1：同一 `RunStore` / SQLite `user_version=2` 上的显式单运行族、独立 query-run 合同，以及有界 descriptor / step 绑定。不是 G3b2 共享 worker 出口，不是 G4 native/HTTP 接线，不是真实业务。

## 1. 范围

| 层 | 本单元 |
|---|---|
| 单族 runtime | 构造参数 `family: Literal["b0","channel_followup"]="b0"`；新 query 库同事务写 `metadata.run_family`；缺键旧库仅当无 query 证据时按 B0 打开 |
| 独立 run 合同 | `analytics-run-channel-followup/v1`；结果只接 G2 `ChannelFollowupResult`；离线 OpenAPI `paths={}`，`x-not-an-http-api` |
| 有界绑定 | accept 冻结 family / method digest / fixture 小 descriptor / `permission_scope`；reserve 冻结完整 G2 request + 纯 metadata 归一化 resolved filters |
| worker / HTTP / native | **未做**。`complete_step` 在新族拒绝成功提交（无 EXITED 记录，或有 EXITED 仍 `QUERY_COMPLETE_NOT_ENABLED`） |

旧 `analytics-run-b0/v1`、G2 `analytics-channel-followup/v1` 与 G3a SQL 计算未改。Store 不打开 DuckDB。

## 2. 失败关闭

- 错族、未知 `run_family`、损坏 metadata：拒绝打开，不覆盖。
- 删掉 `run_family` 但仍有新族 `request_json` 或 `runtime.binding` descriptor：不得当 B0 降级打开。
- 新族读路径核验 stored request schema / descriptor / 实例 family；缺绑定 fail closed。
- 权限：`require(..., data_scope=)` 默认仍 `b0-fixture`；query 使用静态 `channel-followup-fixture`。撤权后不能读缓存结果。
- 无 SQL、路径、scope、family 可从模型注入。

## 3. 本轮验证（store/contract，不是 query worker）

命令使用 `PYTHONNOUSERSITE=1 PYTHON_DOTENV_DISABLED=1`、`/Users/hutou/homebrew/bin/python3.14` 与 Node 24。完整 B0 pipeline 由 Codex prepush，不在本单把旧 B0 worker 回归算作新 query worker PASS。

| 层 | 范围 | 结果 |
|---|---|---|
| 新 query 测试 | `test_analytics_query_jobs.py` + `test_analytics_query_run_contracts.py` | 37 passed |
| 共享相关 Python | jobs/access/run_contracts/run_resources/native_runtime/worker/context/native_probe/query_contracts/channel_followup + 上列新测试 | 280 passed / 20.52s |
| 契约 | `_lint`、ruff 受影响模块、新 query-run codegen `--write/--check` | PASS；新 bundle sha256 `303b59d4…` |
| 旧 B0 / G2 codegen `--check` | B0 `5d93c3aa…`、G2 `38b72d27…` | 未漂移 |
| query worker / HTTP / native | 未接线；`complete_step` 仍 `WORKER_NOT_EXITED` / `QUERY_COMPLETE_NOT_ENABLED` | **NOT RUN** |

审查复现：descriptor/method/step JSON 改内容不改 hash、缺 descriptor 仍 replay 202、`ORDER BY step_id` 取错当前条件、`schema_version=[]` TypeError、`model_construct` 非法请求写入。本修复用统一持久化完整性读取器 + rowid 最新条件 + 入参 dump 重验覆盖；原证据小库 `G3b1-review-aws66v11` 只读保留。

## 4. 未做

共用 worker 真实执行到 SUCCEEDED、HTTP `/api/v1/analytics-query`、native adapter、UI。G3b2 才证明实际进程到成功结果的完整出口。store-only 状态写在本报告，不写入长期 result/snapshot limitations。
