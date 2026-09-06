# 渠道后续购买共享 worker（G3b2）

日期：2026-09-07。任务分支 `codex/channel-followup-worker`。基线 G3b1 `15585855582cad2600be13f0335c07bb332fefde`。状态：**BACKEND_WORKER**。HTTP / native / UI **NOT RUN**。G3 整体未完成。

本文件记录 G3b2：`channel_followup` 复用既有 `WorkerManager` / `RunStore` / `active_slot` / lease / parent pipe / 资源档位，跑通首条真正的受控合成查询。不是 HTTP 上线，不是 native adapter，不是真实业务。

## 1. 范围

| 层 | 本单元 |
|---|---|
| 共享 worker | 同一 `backend.analytics_worker.run_child` 控制管道；B0 仍严格 6 键配置；query 固定加 `family/request/permission_scope/fixture_descriptor/resolved_filters`，禁止未知键 |
| 受信读取 | `RunStore.query_step_binding` 只从 store 读冻结 request/resolved/descriptor；不扣 budget，调用方不能换 scope/descriptor |
| 结果 codec | 按 `store.family` 选择 `ChannelFollowupResult` 或 `AnalyticsB0Result`，不按 `schema_version` 挑类型 |
| 提交门 | `complete_step` 要求同 step 的 `EXITED` + `exit_code=0` + `error_code` null + `active_slot` 已释放；`observe` 成功路径解码 query 结果 |
| HTTP / native / UI | **未做** |

旧 B0 worker 入口、6 键 config、G2 固定 SQL/金标准、query-run v1 wire 未改。`expected.json` 的 `computation: NOT_RUN` 保持手算时点，测试对照原文件字段，不由被测函数生成 expected。

## 2. 受信链

- `WorkerManager.execute` 只接受 `disposition=EXECUTE`；PENDING / REUSE_RESULT 不 spawn、不重置预算。
- 初始化：query 族要求 `ChannelFollowupFixture`，descriptor 与 store 已冻结 fixture 一致。
- 子进程在 lease 内重新核验物理 seal 与 `binding_descriptor`；封板后篡改落 durable `TOOL_FAILED` / `EXITED`，不用父 preflight 逃过审计。
- 连接：`connect_channel_followup_readonly(..., memory_mib=min(profile.duckdb_memory_mib, 32), threads=min(profile.duckdb_threads, 2), temp_mib=min(profile.worker_temp_mib, 32))`，保留 C collation、external false、config lock、实际 SET temp quota 与 engine 身份。
- 执行：`execute_channel_followup_query` 使用冻结 request + 已限制只读连接；父端与 `complete_step` 再对 frozen resolved/data/as_of/filter/scope 核对。

## 3. 本轮验证

命令使用 `PYTHONNOUSERSITE=1 PYTHON_DOTENV_DISABLED=1`、`/Users/hutou/homebrew/bin/python3.14`。Node 24 位于 `/Users/hutou/homebrew/opt/node@24/bin/node`（v24.19.0）。完整 B0 pipeline 由 Codex prepush，本单 **NOT RUN**。

| 层 | 范围 | 结果 |
|---|---|---|
| 新 query worker + 调整后的 jobs 门 | `test_analytics_query_worker.py` + `test_analytics_query_jobs.py` | 46 passed / 10.63s |
| 共享相关 Python | jobs/worker/context/channel_followup/query_contracts/query_run_contracts/access/run_contracts/run_resources/native_runtime/native_probe + 上列 | 302 passed / 30.56s（1 条非 ResourceWarning） |
| ruff | 受影响 Python（worker/jobs/queries/fixture/新测试与 probe） | PASS |
| 旧 B0 / G2 金标准 / query-run codegen | 未改源合同或 golden 文件 | 未漂移（本单未重跑 codegen） |
| HTTP / native | 未接线 | **NOT RUN** |

真实 worker：成功路径 `exit_code=0`、`error_code` null、lease 释放、一步一执行。取消/只撤 query 族 scope/deadline 在 `SQL_ACTIVE` 后停子进程（忽略 SIGTERM 时 SIGKILL `-9`），pid 退出、lease 可再独占、step 无结果、预算不重置。`result+closed` 而进程未退出不得 `complete_step`。自洽错 N/scope 的成功 result 帧不带 child error，由父/`complete_step` 绑定检查 `BINDING_MISMATCH`；未知 schema 由 family 固定 codec 拒绝。封板物理改变 → durable `TOOL_FAILED`。owner 崩溃沿用既有 pipe EOF，恢复不 adopt PID、不重发查询。

N30/N60/N90 对照 `backend/tests/fixtures/analytics_channel_followup_v1_expected.json` 原文字段；只读源 hash 查询前后不变。

## 4. 未做

HTTP `/api/v1/analytics-query`、native adapter、UI、G4 `execute_native_fixture`、query 族独立 spill/OOM 负测、远端 CI、完整 B0 pipeline。G3 不得因此记完成。
