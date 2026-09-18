# 主协调审查 · Lane C

- 状态：Lane C **PARTIAL**（合成夹具模块完成）。P05 批次 **PARTIAL**，**不是 DONE**（依赖 P03/P04；A 生成类型、真实结果库、iframe、pipeline 扫描均为 NOT_RUN）
- 审查日期：2026-09-18
- 工作树：`/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/fuqing-crm-analytics-free-html-C`
- 分支 / HEAD：`codex/free-html/lane-c` @ `b45a27bb9022057ce37aa9123927e8b4663a2720`（业务代码 **未 commit** / 未 push）
- 报告：`reports/LANE-C.md`
- approved-plan SHA256：`47fa5bfe482cb9bd93f4f02a7c62c6933d0242b5204ea95f2b912edc603a6ffb`
- 本轮未把 C cherry-pick 进主仓，未 commit C，未切 6677（PID 8758）

## 越界核对（通过）

| 路径 | 结果 |
|---|---|
| `board_documents.py` | 与主仓相同 |
| `page_documents.py` | C 树当时还没有该文件（A 未并入） |
| `library-board-client.mjs` / `html-sandbox.mjs` / `pipeline.mjs` | 与主仓相同 |
| `src/free-page/` | 仅 `bridge/` |
| 新增 | `backend/services/analytics/page_result_access.py`、`backend/tests/test_page_result_access.py`、`src/free-page/bridge/*` |
| `frozen-contract-v0.json` | 与主协调副本相同 |

## 复跑证据（本轮主协调执行）

cwd = Lane C worktree。

1. `python3 -m ruff check backend/services/analytics/page_result_access.py backend/tests/test_page_result_access.py` → All checks passed，exit **0**
2. `python3 scripts/run_backend_tests_bounded.py backend/tests/test_page_result_access.py` → **15 passed**，组 rc=0，总 rc=0；报告 `.context/checks/20260918T061215063350Z/summary.json`
3. `PATH=$HOME/homebrew/opt/node@24/bin:$PATH node --test dsh-plugins/analytics-workbench/src/free-page/bridge/*.test.mjs` → Node **v24.19.0**，**15 pass / exit 0**

OCR 返修对得上：`aborted` 按 `instance_id` 分桶；测试 `new instance can reuse an aborted request_id` 通过。无 `execute_sql` / DuckDB / `INVALID_BOARD`。

## 必须保持为 mock（不能当 P12 通过）

1. `fixtures/frozen-contract-v0.json`，不是 A 的生成类型
2. `PageResultAccess.put_snapshot` 合成快照，不是原生问数结果库
3. `createSyntheticAccess` 进程内 JS，没有 HTTP 打到 Python
4. `createBridgeHost({ manifest })` 注入，没有读 `page_documents`

Node `MessageChannel` 是同进程端口，不是 Chrome opaque-origin iframe。

## 未运行

- `scripts/dsh-b0/pipeline.mjs --check`
- filterbuilder 全量
- 真浏览器 iframe
- 真实授权结果库 / 原生 Agent 新查询
- A 生成类型替换夹具

## P12 接缝（尚未移植）

按 A→B→C。用 A 类型替换 frozen fixture；把 Python `PageResultAccess` 接到宿主 access；`src/free-page` 加入 pipeline 扫描。E 可 import `createBridgeHost` / `createSyntheticAccess`，必须标明 synthetic 为 mock。取消读继续用 `RESULT_UNAVAILABLE`；额度继续用 `PACKAGE_TOO_LARGE`。破坏性改冻结字段 BLOCKED。
