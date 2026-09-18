# LANE-C 施工交接 · 授权数据桥（T5 / P05）

- 状态：**PARTIAL**
- 执行日期：2026-09-18
- 执行者：Lane C 独立执行者
- 工作树：`/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/fuqing-crm-analytics-free-html-C`
- 分支：`codex/free-html/lane-c`（无 upstream）
- 开始/结束 HEAD：`b45a27bb9022057ce37aa9123927e8b4663a2720`（未 commit）
- dirty：本 lane 新增未跟踪业务文件；施工包 `docs/hackathon/free-html-cockpit/`、`AI-PROMPT.md`、`MAIN-COORDINATOR.md` 仍为开工时未跟踪文件。无已跟踪文件 diff。OCR 复审 1 High / 3 Medium 已修；残留 Low（abort 集合跨实例污染 request_id）已按实例分桶。
- 任务：T5；节点 N06 / N07 / N12
- 方案 SHA256：`47fa5bfe482cb9bd93f4f02a7c62c6933d0242b5204ea95f2b912edc603a6ffb`（对本机 `approved-plan.md` 字节核验一致）
- 工具链：Node v24.19.0（`$HOME/homebrew/opt/node@24`）、Python 3.14.4、DSH 钉仍为 toolchain.json 的 `0.1.6-alpha.2` / `ddefc45f`。宿主 pnpm 11.19.0 未改。无 `.codegraph/`。
- **不能记 DONE 的原因（依赖约束）**：P03/P04 代码不在当前 checkout；A 生成类型与 B 运行时未落地。本 lane 用 `fixtures/frozen-contract-v0.json` 与合成结果夹具施工。下列 mock **不是**真实数据桥通过证据。

## 实际完成

只读授权 `result_ref` / `data_ref` 读取、摘要/分页/范围、取消/过期/额度、actor/单位/时间/版本/撤权校验、宿主来源状态。新查询仍不在本模块；页面拿不到 SQL、token、任意外联或保存。未绑定页可握手并打开，不能因此获得 `BOUND_VERIFIED`。

| 行为 | 位置 |
|---|---|
| 权威读取与授权（合成快照） | `backend/services/analytics/page_result_access.py` |
| pytest 入口 | `backend/tests/test_page_result_access.py` |
| 冻结合同常量 | `dsh-plugins/analytics-workbench/src/free-page/bridge/contract.mjs` |
| MessageChannel 宿主会话 | `…/src/free-page/bridge/host.mjs` |
| 进程内合成 access（给 E/测试，**mock**） | `…/src/free-page/bridge/synthetic.mjs` |
| 公开 adapter | `…/src/free-page/bridge/index.mjs` |

合同消费自 `fixtures/frozen-contract-v0.json`：`free-page-bridge/v1`、握手字段、`data.read`/`data.cancel`、禁止 `sql`/`save`/`http.fetch`/`credential.read`、摘要字段 `unit/time_range/queried_at/source/row_count`、额度 `65536` 字节 / `2000` 行、绑定态 `UNBOUND_SAMPLE|BOUND_VERIFIED|BOUND_STALE`。未改 Lane A 资产存储，未改 `page_documents`、宿主 UI、DSH 上游、`manifest.json`。

## 验证证据

| 检查 | 准确命令/操作 | 环境/夹具 | 结果/退出码 | 证据路径 |
|---|---|---|---|---|
| 冻结合同 SHA | `shasum -a 256 docs/hackathon/free-html-cockpit/approved-plan.md` | 本工作树文件字节 | `47fa5bfe…6ffb` | 本报告 |
| Ruff E4/E7/E9/F | `python3 -m ruff check backend/services/analytics/page_result_access.py backend/tests/test_page_result_access.py` | Python 3.14.4 | 0，All checks passed | stdout |
| 后端合成单测 | `python3 scripts/run_backend_tests_bounded.py backend/tests/test_page_result_access.py` | 隔离 HOME/TMP；合成快照；无 DuckDB | **15 passed**，组 rc=0，总 rc=0，0.627s | `.context/checks/20260918T060537178352Z/summary.json` |
| 桥协议/合成 access | `PATH="$HOME/homebrew/opt/node@24/bin:$PATH" node --test dsh-plugins/analytics-workbench/src/free-page/bridge/*.test.mjs` | Node v24.19.0；`frozen-contract-v0.json`；Node `MessageChannel` | **15 passed**，exit 0 | stdout |
| OCR delegate 复审 | workspace 可审 9 文件；修 1 High / 3 Medium 后再审 | 只审 owner 实现，排除施工包 | 原 High/Medium 已关闭；abort 分桶后无新 High/Medium | 对话记录 |
| 路径计划 | `python3 scripts/ci/run_checks.py --files-from changed-files.txt --plan-only` | 本 lane 10 个业务文件 | `backend=scoped` 目标即本测试；另标 `b0=true`、`filterbuilder=true` | stdout JSON |
| B0 pipeline | 未执行 | pipeline.mjs 目前只扫 `src/board-spec`/`src/client`/`src/competition-agent`/`tests`，**不含** `src/free-page` | **NOT_RUN** | — |
| filterbuilder 轴 / 全量 backend | 未执行 | 计划因 `backend/services/` 标了 filterbuilder | **NOT_RUN** | — |
| 真实浏览器 iframe | 未执行 | 属 P01/P04/P12 | **NOT_RUN** | — |
| 真实授权结果库 / 原生 Agent 新查询 | 未执行 | 本 lane 禁止任意查询入口 | **NOT_RUN** | — |
| A 生成类型替换夹具 | 未执行 | A 未落地 | **NOT_RUN（mock）** | — |

Node `MessageChannel` 只证明同进程端口握手与 `data.chunk`/`data.end`，**不是** Chrome opaque-origin iframe 证据。

覆盖过的失败路径（合成）：跨 actor `NOT_FOUND`、撤权后缓存命中 `RESULT_REVOKED`、撤权后跨 actor 仍 `NOT_FOUND`、过期/单位/时间/版本 `RESULT_STALE`、SQL/token/save/外联 `BRIDGE_UNKNOWN_OP`、nonce 重放、过期实例、取消中途读取、读未完成时重新握手丢弃旧读、新实例可复用旧 `request_id`、累计额度、空结果可恢复、未绑定禁止 `data.read`。

## 声明的 mock 清单

1. `fixtures/frozen-contract-v0.json` 代替 Lane A 生成 OpenAPI/类型。
2. `PageResultAccess.put_snapshot` / `default_synthetic_snapshot` 代替原生 Agent 写入的授权结果库。
3. `createSyntheticAccess` 是 JS 进程内 mock，**没有** HTTP 打到 Python 服务。
4. 宿主 `manifest` 由 `createBridgeHost({ manifest })` 注入，**没有**读 `page_documents`。
5. 数据 scope `free-page-result-fixture`、capability `dashboard:read` 为桥夹具身份，不是现役 CRM 鉴权。

以上 mock 只用于本 lane 模块测试。不能把它们写成 P12 真实桥通过。

## 未完成与失败

- **DONE 门禁未满足**：manifest 中 P05 依赖 P03/P04；当前 checkout 无 A/B 实现。
- 未把 `src/free-page` 测例纳入 `scripts/dsh-b0/pipeline.mjs`（owner 是 P12；本 lane 未改 pipeline）。
- 未接 HTTP 路由、未接真实 result store、未在浏览器里跑 iframe。
- 取消读复用冻结码 `RESULT_UNAVAILABLE`（合同没有 `READ_CANCELLED`）；额度超限复用 `PACKAGE_TOO_LARGE`。
- `backend/tests/test_page_result_access.py` 不在 glob `page_result_access*` 字面下，但是 `testpaths = ["backend/tests"]` 的实际入口；否则 pytest 收集不到。

无失败的已运行项。未运行项未报通过。

## 交给下一批次

- E 可 `import { createBridgeHost, createSyntheticAccess, UNBOUND_MANIFEST, BOUND_MANIFEST } from './free-page/bridge/index.mjs'`，必须继续标明 synthetic 为 mock。
- P12 应：按 A→C 接缝把 Python `PageResultAccess` 接到宿主 access；用 A 生成类型替换 frozen fixture；把 `src/free-page` 加进 pipeline 扫描；真实 iframe + 授权结果走一遍。
- 必须保留：页面不能 SQL/token/save；缓存命中仍 `authorize`；未绑定不得 `verified`；分页 cursor 钉 `result_version`；宿主只背书结果来源，不背书 DOM。
- 无 commit。交接以本工作树未跟踪文件为准。

## 进程与文件归属

本次未启动临时 HTTP/uvicorn/dsh-dev，未碰 6677，未读 131GB DuckDB，未 `pnpm add`，未 push/merge/commit。`python3 scripts/run_backend_tests_bounded.py` 自建隔离目录并已退出。`.context/checks/20260918T053731839812Z/` 为本地检查产物，不进 Git。

## Integration notes（给 P12）

1. 破坏性改 `frozen-contract-v0.json` 字段应 BLOCKED；本 lane 未改该 JSON。
2. JS `synthetic.mjs` 与 Python 授权规则平行实现，仅供隔离单测；接真实后端后删掉生产路径上的 mock。
3. 握手 `page_id`/`version` 必须与宿主资产一致，页面不能自报 binding manifest。
4. 不要把 BoardSpec `INVALID_BOARD` 或 `html-sandbox` 扩进本桥。
5. 本 lane 未写 `reports/P05.md`、未改 `manifest.json`（按 COORDINATOR-KICKOFF）。
6. 取消读复用 `RESULT_UNAVAILABLE`；额度超限复用 `PACKAGE_TOO_LARGE`。不要发明第二套错误码。
7. `aborted` 按 `instance_id` 分桶；刷新后新实例可复用旧 `request_id`。

## 给主协调的汇报提示词

把下面整段交给主协调 Agent（不要当 DONE，不要把 mock 写成真实桥通过）：

```text
Lane C（授权数据桥 / T5 / P05）已交付本地实现，状态 PARTIAL，不是 DONE。你是自由 HTML 驾驶舱主协调，不重新设计产品，不要让 C 自己 cherry-pick 进主仓。

工作树：/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/fuqing-crm-analytics-free-html-C
分支：codex/free-html/lane-c（无 upstream）
HEAD：b45a27bb9022057ce37aa9123927e8b4663a2720（与开工基线相同；业务代码未 commit）
报告：docs/hackathon/free-html-cockpit/reports/LANE-C.md
approved-plan SHA256：47fa5bfe482cb9bd93f4f02a7c62c6933d0242b5204ea95f2b912edc603a6ffb

核对：只读 owner paths。C 新增
- backend/services/analytics/page_result_access.py
- backend/tests/test_page_result_access.py（pytest 实际入口，不在 glob 字面下）
- dsh-plugins/analytics-workbench/src/free-page/bridge/* （contract/host/synthetic/index 及测试）
未改 page_documents、宿主 UI、DSH 上游、manifest.json。未 push/merge/commit。未切 6677，未读真实大库。

实现（合成夹具）：result_ref/data_ref 只读摘要/分页/范围；取消/过期/额度；actor/单位/时间/版本/撤权；宿主来源状态；未绑定可打开但不得 BOUND_VERIFIED；禁止 SQL/token/save/外联。新查询仍走原生 Agent（本模块无查询入口）。

必须声明的 mock（不能当 P12 通过）：
1. fixtures/frozen-contract-v0.json，不是 A 的生成类型
2. PageResultAccess.put_snapshot 合成快照，不是原生问数结果库
3. createSyntheticAccess 是进程内 JS mock，没有 HTTP 打到 Python
4. manifest 由 createBridgeHost 注入，没有读 page_documents

已跑（未跑不报通过）：
- python3 scripts/run_backend_tests_bounded.py backend/tests/test_page_result_access.py → 15 passed，exit 0；.context/checks/20260918T060537178352Z/summary.json
- PATH="$HOME/homebrew/opt/node@24/bin:$PATH" node --test dsh-plugins/analytics-workbench/src/free-page/bridge/*.test.mjs → 15 passed，exit 0
- ruff 上述 Python 文件 exit 0
- OCR delegate 复审 9 文件：1 High（刷新后旧读标到新 instance）/ 3 Medium（撤权泄漏、attach 队列、握手 Promise）已修；abort 已按 instance_id 分桶。B0 pipeline / filterbuilder 全量 / 真浏览器 iframe / 真实结果库 NOT_RUN。

P12 接缝：按 A→B→C 移植；用 A 生成类型替换 frozen fixture；把 Python PageResultAccess 接到宿主 access；把 src/free-page 加进 scripts/dsh-b0/pipeline.mjs 扫描（当前只扫 board-spec/client/competition-agent/tests）。E 可 import createBridgeHost / createSyntheticAccess，但必须标明 synthetic 为 mock。破坏性改冻结字段一律 BLOCKED。

更新 reports 与 manifest 时：Lane C 记 PARTIAL，不要勾 P05 DONE，不要提前勾 P12/P13。
```
