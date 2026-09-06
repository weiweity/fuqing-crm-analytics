# B0 原生 running 与非法 worker 结果拒绝（G1）

日期：2026-09-07。任务 `G1-native-running-invalid`。工作树 `.worktrees/hackathon-mission-mvp`，分支 `codex/b0-native-state-proof`，实现基线 HEAD `bd6d8fe`（P1/T09 已提交 SHA，不是 G1 提交）。**本 G1 范围原生状态补证 PASS。整体 B0 仍 PARTIAL。** G1 源码尚未 commit/push/CI；Git 交 Codex。本页是文档收尾，不改实现。

## 结论

opt-in `serve.mjs --native-state` 启动 test-only kernel（真实 `runtime_app` + `ProbeLauncher`）。默认 lifecycle / `--native-cards` / `backend.analytics_runtime` 不启用探针。生产 HTTP 无故障字段。

**本范围出口（`runtime-SNWYss`）PASS。** 四问由原生 UI 发出：`SUCCEEDED` / `FAILED TOOL_FAILED` / `FAILED TOOL_FAILED` / `SUCCEEDED`。第一问在 `SQL_ACTIVE` 时实际 `.analytics-b0-card` 为「B0 合成工具运行中…」，截图在 release 之前；`call_id`/`request_id`/`turn`/`run`/`attempt`/`execution` 一致且当时无 durable result，同一 call 随后成功。两次失败无 result/meta/25%。4 个 worker `EXITED`、`active_slot` 空、lease 物理可独占。刷新 0 新增 run，native tool/call 与 result 一致。

**第一次** `runtime-hkeo4K` 因 G1-F3 仅第一问后失败（backend 终态后 composer 仍为 Stop generating）。该失败保留，**不能**说第一次四问全过。

独立 pipeline（F3 前口径）PASS：178 Python / **143 源 Node** / 14 built+clean/typecheck（`G1-independent-pipeline.log`）。F3 后仅 7 项 Node smoke 测试 PASS，**不是** 145 源 Node，也不是新的全量 pipeline。最终 full pipeline 由 Codex 另行运行；本文不提前写 PASS 或伪造新数量。P1 CI（runs `34049400372` / `34049400375` 对 `bd6d8fe`）属于 T09，**不是 G1 CI**。

## 入口与边界

| 入口 | 行为 |
|---|---|
| `python -m backend.analytics_runtime` 或 `serve.mjs` 默认 / `--native-cards` | 生产 kernel；`launch is spawn_worker` |
| `serve.mjs --native-state` | `runtime/probe/`（0700）；kernel `-m backend.tests.analytics_native_probe` |
| 私有控制 | `sequence.json` / `proof.jsonl` / `current.json` / `release/<execution_id>`；`O_NOFOLLOW`、属主、0700 |

非法 facts/未知版本经 `ProbeDumpOnly.model_dump` 走正常 ready/result/closed；生产 `AnalyticsB0Result.model_validate` 拒绝。F1：mutant 绕过 validator 时原测试 **exit 1 / DID NOT RAISE**（`G1-rejection-mutant-after.log`）；修复前同一 mutant **exit 0**（`G1-rejection-mutant-before.log`）；正常校验 **exit 0**（`G1-rejection-normal-after.log`）。组件「版本不支持」回退与 native 失败卡分开。

下一问须等上一 request 的 `summarizeRequest` 终态、durable tool/result，以及 Send message 路径（空输入 disabled 可填；fill 后再点）。不能用 backend 终态单独放行。

## 原生证据（SNWYss）

报告：`.context/dsh-b0/runtime-SNWYss/native-state-evidence-1788719130605.json`，`status: PASS`，`G1-native-retry.log` exit 0。截图：running `native-state-running-1788719108194.png`（Codex 已看）；最终失败+恢复 `.context/goal-8h/evidence/G1-final-native-cards-tall.png`。

| 问 | run | 状态 |
|---|---|---|
| 1 | `run_3911484a4aed42cdba6ff76bd0445a4b` | SUCCEEDED；running 时 call `b0-request-1:mock-call-1` / request `53eb9a5e-70b9-427f-929f-fee7a03d6ff5` / turn 1 / exec `exec_cecd09ad88f04404b57e390da44b9561` |
| 2 | `run_410c18bdb3c64ec6919703b47b4ce236` | FAILED / TOOL_FAILED；无成功 meta |
| 3 | `run_770757b763dd4dd19a57fe547049286b` | FAILED / TOOL_FAILED；无成功 meta |
| 4 | `run_e89d0d999a7f4525ada2dbcf0c50cad9` | SUCCEEDED |

Worker 四条均为 EXITED。失败子进程 exit_code `-15` 是父协议拒绝后 terminate，账本仍为 TOOL_FAILED。刷新 `new_runs: 0`。

控制台保留网关有意拒绝的 Cordis inventory/inspect **403** 以及刷新连接事件，**不是**零 console error。失败轮上游摘要可显示 `UNKNOWN`（下一 pre-step 被 kernel 拒绝）；业务 ledger 明确 `TOOL_FAILED`。未改 DSH 核心或产品 UI。

第一次失败：`runtime-hkeo4K` / `native-state-evidence-1788718607839.json` / `G1-current-native.log`。live running 当时已成立，四问未完成。

## 实现 hash（本收尾未改源码）

以 `.context/goal-8h/evidence/G1-post-F3-candidate-hashes.json` 与 SNWYss `source_hashes` 为准：

| 文件 | sha256 |
|---|---|
| backend/tests/analytics_worker_probe.py | d85de3d645384de5bd5eaf1d3d925d4b6545462c53ddc8609f81efb0c3d81841 |
| backend/tests/analytics_native_probe.py | d829fb3f22825a198257f83ec3f8ddfbb858f141f9ac17cc4be58d601c782aaa |
| backend/tests/test_analytics_native_probe.py | 945e614c1e533a04007830a9f0f88b2cc29c312cf61866dcc1a2784573c72925 |
| scripts/dsh-b0/serve.mjs | 87926195763856bbdaf6b2259f1f00c7bff6759b95d5464d17ea3117fc7df8cb |
| scripts/dsh-b0/native-state-smoke.mjs | c7429f8a015ec1aa247833e54086794ae31fb75726f3d348468cc093da72c3f6 |
| scripts/dsh-b0/native-state-smoke.test.mjs | 5cb3618562dd38387ff14c7dd2f78187d1fb622bde66576b24fee77108660f8d |
| scripts/dsh-b0/pipeline.mjs | 10cc656bdf681de1ed7a0d6770d90a08f2bfcf3687e8112f2cd70435f0a90ec9 |
| 插件 client.js（只读） | 85adb016fa059cb8774c2a1febdb40de3fb4da7e46c9bdf958d6c21dfd0da208 |

## 分层结果

| 层级 | 结果 | 说明 |
|---|---|---|
| F3 后 Node smoke | 7 PASS | 不是全量 145 源 Node |
| G1 独立 pipeline | 178 Python / 143 源 Node / 14 built | F3 前口径；`G1-independent-pipeline.log` |
| G1 原生四问 | PASS `runtime-SNWYss` | 保留 hkeo4K F3 失败 |
| 最终 full pipeline | **待 Codex** | 不提前 PASS |
| G1 Git/CI | 未提交 | 待 Codex；勿把 PR #69 CI 当 G1 CI |
| T09 / P1 | `bd6d8fe` PR #69 base #68 | CI 34049400372 / 34049400375 对该 SHA 成功；原生 `runtime-eDvn6c` PASS |

进程：本次 supervisor **69417**、gateway **70581** 已停，预期正常 STOPPED（Codex 复核）。4315–4319 空闲。演示 36717/36727 保持。无部署/合并/真实业务。

## 未闭合（整体 B0，非本 G1 出口）

- 历史三次 supervisor 退出：OPEN / UNKNOWN
- 完整 B1–B4、真实模型、业务 UAT、公开部署
- G1 源码的 commit/push/PR 与最终 full pipeline（Codex）
