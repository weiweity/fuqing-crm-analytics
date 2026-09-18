# 主协调审查 · Lane A

- 状态：Lane A **DONE**（T1/T2 owner 范围）。P02 **DONE**。P03 **DONE**。未挂现役 HTTP；pipeline / iframe / P12/P13 **NOT_RUN**
- 审查日期：2026-09-18
- 工作树：`/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/fuqing-crm-analytics-free-html-A`
- 分支 / HEAD：`codex/free-html/lane-a` @ `b45a27bb9022057ce37aa9123927e8b4663a2720`（业务代码 **未 commit** / 未 push）
- 报告：`reports/LANE-A.md`
- 本轮未改 A 的 owner 文件，未 commit A，未切 6677（PID **8758**）

## 越界核对（通过）

| 路径 | 结果 |
|---|---|
| `board_spec.py` / `board_documents.py` | 与主仓相同 |
| `html-sandbox.mjs` / `library-board-client.mjs` / `pipeline.mjs` | 与主仓相同 |
| `src/free-page/` | 仅 `contract/` |
| 现役挂载 | `main.py` / `analytics_competition_app.py` 无 `page_documents` |
| `INVALID_BOARD` | 不在 PAGE_ERRORS；仅注释/负测提到 |

OCR 五条 Medium 对得上：总字节超限 `PACKAGE_TOO_LARGE` 413；无 `result_refs` ⇔ `UNBOUND_SAMPLE`；JS 用 `TextEncoder`；非法 sha256 / 未知字段 / mode 校验；D6 生成类型为可省略字段，`title: null` 带 `@ts-expect-error`。

## 复跑证据（本轮主协调执行）

cwd = Lane A worktree。Python **3.14.4**，Node **v24.19.0**。

| 检查 | 结果 |
|---|---|
| ruff 四个新 Python 文件 | All checks passed，exit 0 |
| `backend.contracts._lint` | OK，exit 0 |
| `python3.14 scripts/run_backend_tests_bounded.py backend/tests/test_page_documents.py` | **13 passed**，exit 0；`.context/checks/20260918T062524066142Z` |
| 同上 `test_board_documents.py`（本轮补跑） | **60 passed**，exit 0；`.context/checks/20260918T062654567005Z` |
| `node --test …/contract/schema.test.mjs` | **4 passed**，exit 0 |
| `page-contract.mjs --check --python …/python3.14` | exit 0；`sha256=86ad3cf4d71b05cb827a52f38b568ae3e0ed02ea7312a9dd3b6d848971e0ef3a` |

该 SHA 是 OpenAPI schema 的 `x-schema-sha256`（规范化 JSON），不是文件字节。文件 `shasum -a 256 analytics-page.openapi.json` = `ed19b569…`（含包裹字段）。以 `--check` 打印的 86ad3cf4 为合同 SSOT。

含重开新连接、CAS 并行确认、D6/D9 分路、cancel 不保存、权限/撤权、回滚重查授权。

## 未运行

- `scripts/dsh-b0/pipeline.mjs --check`（尚未接入 `page-contract.mjs` / `src/free-page`）
- 挂到 B0/6677 HTTP
- 真浏览器 iframe
- P12 集成旅程；P13 真实 AI

## P12 接缝（尚未移植）

1. 按 A→B→C→D→E→F。B–F 改引用 `src/free-page/contract/` 与 `analytics-page.openapi.json`，不要再发明字段，不要只靠 `frozen-contract-v0.json`。
2. `pipeline.mjs` 在 board-spec-contract 之后加 `page-contract.mjs --check`，并扫描 `src/free-page` 的 `.test.mjs`。
3. 把 `page_documents_router` 挂到正式 B0 HTTP；不要改 BoardSpec codec，不要扩展 `html-sandbox.mjs`。
4. 新库 `page_documents.sqlite3`，`application_id=1804289383`。抽共享 Python 类由 P12 做，且不得改 BoardSpec codec。
5. C：`resolve_binding`；B：只用 `resources[].sha256` + `byte_length`，不要用 A 的资产表当缓存。
