# 渠道首次观察队列离线计算（G3a）

日期：2026-09-07。修订时点：2026-09-06T20:21:10Z（G3-F1–F4 修复）。任务分支 `codex/channel-followup-compute`，基于已提交 G2a `ae02f873cfdbfc5a53e3fe8e5ae137872f1203a1` / [PR #71](https://github.com/weiweity/fuqing-crm-analytics/pull/71)（CI PASS，`state.json.g2a` / `G2a-final-ci.json`）。状态：**OFFLINE_DETERMINISTIC_COMPUTE**。不是 HTTP 上线、不是 worker/权限/预算/物理退出总治理、不是完整 G3、不是原生接线、不是真实业务。G3a 源码 Git 由 Codex 按 PR 交付，不以「待提交」描述已落地的 G2。

本文件记录 G3a 离线确定性层。合同与手算金标准仍见 [渠道后续购买合同](./CHANNEL-FOLLOWUP-CONTRACT-2026-09-07.md)；`expected.json` 保持 `hand_calculated` / `NOT_RUN`，生产代码不读取它。

## 1. 范围

| 层 | 本单元 |
|---|---|
| 三表 synthetic snapshot 初始化/封板 | `backend/analytics_query_fixture.py`：`create_channel_followup_fixture`、`validate`、`connect_channel_followup_readonly`、`verify_sealed_content` |
| 固定参数化 SQL | `backend/semantic/analytics_channel_followup.py`：`channel_followup_query` / `channel_followup_query_parameters` |
| 只读执行 | `backend/services/analytics/queries.py`：`execute_channel_followup_query` |
| 目录阶段说明 | `catalog.QUERY_FAMILIES` 注明离线 SQL 已有、worker/HTTP 不在 G3a |
| worker / RunStore / HTTP / native | **未做** |

G2 公共 contract、旧 B0 fixture/hash、既有 worker/store/core/native/type 合同、CI 策略/hooks/AGENTS 未改。旧 `MAX_DATABASE_BYTES=4MiB` 与 `private_directory`/`bounded_bytes` 复用，未放宽。

## 2. 实际路径与函数

- 创建：显式空私有目录；G2 `ChannelFollowupSnapshot` 完整校验；订单头/商品行/退款分表；复合键 `(synthetic_user_id, order_id)`；write / `CHECKPOINT` / close 后再开只读连接。
- 文件名固定：`channel-followup.duckdb`、`manifest.json`。技术限额 1000 订单 / 3000 行 / 1000 退款、快照 JSON ≤512KiB、库 ≤4MiB，不能由 request 放宽。
- `validate()` 只做 bounded 文件、canonical `as_of` 与 manifest/物理 hash，不开分析连接。schema/内容在已限制连接内：核对用户 catalog/schema/表/列/视图（不把 information_schema/pg_catalog/temp 当业务表），用 `LIMIT cap+1` 有界读取重建 `snapshot_digest`，并与封板 manifest 的 digest、as_of、行数、版本对齐。
- 时间按 UTC naive `TIMESTAMP` 存微秒 instant；隔离引擎禁止 autoload ICU，因此不 `SET TimeZone`。VARCHAR 身份列 `COLLATE C`；SQL 对 join/group/排序使用 `encode()`，与 session/列 collation 无关。逻辑 digest 与物理 `database_sha256` 分开。
- 查询只接受 G2 request + 已登记 fixture + `permission_scope` + 调用方持有的只读连接。SQL 口径只在 semantic；全部 `?` 参数化。连接治理：`read_only`、`default_collation=C`、禁 autoload/autoinstall/community extension/persistent secrets、私有 temp、`enable_external_access=false`、`lock_configuration=true`。已 lock 的 nocase 连接 fail closed。服务不 close 调用方连接，也不是 Web singleton。
- 结果 `LIMITATIONS` 只保留候选口径/hash/传输上限，不再把「SQL 未实现」写成运行时业务局限。

## 3. 金标准逐窗口（真实查询，不是生产常量）

as_of=`2026-09-01T00:00:00+08:00`。与 G2 `expected.json` 字面字段一致：

| N | A 成熟/未成熟/二单/跨渠道/净额 | B | 全体 |
|---|---|---|---|
| 30 | 7 / 1 / 4 / 3 / 87000 | 2 / 0 / 1 / 0 / 23000 | 9 / 1 / 5 / 3 / 110000 |
| 60 | 7 / 1 / 5 / 4 / 92000 | 2 / 0 / 1 / 0 / 23000 | 9 / 1 / 6 / 4 / 115000 |
| 90 | 2 / 6 / 2 / 2 / 30000 | 0 / 2 / 0 / 0 / null + `EMPTY_MATURE_COHORT` | 2 / 8 / 2 / 2 / 30000 |

数据反例（独立手写预期，查询计算）：

- 只把 b 的 `b02` 从 2026-07-03 移到 2026-06-30：N30 变为 A 7/1/5/4/92000，B 2/0/1/0/23000，全体 9/1/6/4/115000（与原 N60 相同）。
- 只把 f 的 Jul30 二单延后 1 微秒：N30 A 二单 3 / 跨渠 3 / 净 82000，全体二单 4 / 跨渠 3 / 净 105000；成熟/未成熟不变。
- 筛选仅 A：后续 B 仍计入 cross，total 等于 A 行。

## 4. 验证

本单元修复验证（Grok）：`test_analytics_channel_followup.py` + G2 `test_analytics_query_contracts.py` 与 ruff。Codex 独立 55tests 是修复前基线，不替代本轮回归。

| 命令 | 退出码 | 范围 |
|---|---|---|
| `PYTHONNOUSERSITE=1 PYTHON_DOTENV_DISABLED=1 python3.14 -m pytest --noconftest -W error::ResourceWarning -q backend/tests/test_analytics_channel_followup.py backend/tests/test_analytics_query_contracts.py` | 0 | 62 passed（29 compute + 33 G2 合同） |
| 同上 pipeline Python 子集（jobs/access/run_contracts/run_resources/native_runtime/worker/context/native_probe/query_contracts/channel_followup） | 0 | 240 passed, 1 warning |
| `python3.14 -m ruff check` 本单元 Python | 0 | All checks passed |

初验日志保留 `.context/goal-8h/evidence/G3a-verify.log`。本轮修复日志 `.context/goal-8h/evidence/G3a-repair-verify.log`。无 HTTP/DSH 启动；未改资源 profile。全量 backend / 远端 CI / 原生 **NOT RUN**。

G3-F1：`require_restricted_connection` 校验 `default_collation`；SQL `encode()`；Z/a 同刻首渠 A；u/U 分用户；nocase 已 lock 连接拒绝。G3-F2：manifest `as_of` 必须 canonical；counts/as_of 与同连接 snapshot 对齐；`extra.unregistered` 拒绝并 close/reopen。G3-F3：订单 `SELECT … LIMIT cap+1`，超量小文件先有界取回再 fail closed。

## 5. 未做

native、共用 worker 权限/预算/取消/期限/physical exit、RunStore 持久化、真实业务库、ETL、产品模型。G3 整体不得因此记完成。
