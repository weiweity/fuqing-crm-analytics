# Lane A · 合同与资产

- 状态：**DONE**（T1/T2 本 lane 责任部分有离线证据；P12/P13 未运行，不提前勾总计划）
- 执行日期：2026-09-18
- 执行者：Lane A（Grok Build）
- 工作树：`/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/fuqing-crm-analytics-free-html-A`
- branch：`codex/free-html/lane-a`（无 upstream）
- 开始/结束 HEAD：`b45a27bb9022057ce37aa9123927e8b4663a2720`（未 commit）
- dirty：施工前仅未跟踪 `AI-PROMPT.md`、`MAIN-COORDINATOR.md`、施工包；本轮新增页面合同/存储/测试与 `src/free-page/contract/`，未改已跟踪业务文件
- 任务：T1/T2（P02/P03）；节点 N05/N07/N11/N12/N13
- 方案 SHA256：`47fa5bfe482cb9bd93f4f02a7c62c6933d0242b5204ea95f2b912edc603a6ffb`（本工作树 `approved-plan.md` 字节核验一致）
- 无 `.codegraph/`，用限定路径源码阅读。未 push/merge/commit，未切 6677，未读 131GB DuckDB，未改 DSH 上游，未写 `manifest.json`

## 实际完成

独立 `free-page/v1` 合同，不把 HTML 塞进 BoardSpec：

- Schema / 错误：`schema_version=free-page/v1`；绑定只有 `UNBOUND_SAMPLE|BOUND_VERIFIED|BOUND_STALE`；操作 `GENERATE|PATCH|SAVE|ROLLBACK`；页面非法用 `INVALID_PAGE`（422），代码路径无 `INVALID_BOARD`
- D6：`POST .../patch-preview` 再 `confirm`，同一 `Idempotency-Key` 只产生一个版本
- D9：`POST .../save-preview` 再 `confirm`（宿主草稿显式保存）。`cancel` / 未 confirm 不落盘；无“退出编辑=保存”接口
- 源码包（自由 HTML/CSS/JS + resources hash + node_map）与 binding manifest 同一原子版本
- 新 SQLite：`page_documents.sqlite3`，`application_id=1804289383`，`kind=library_page_documents`；preview/confirm/CAS/幂等/回执/回滚协议与看板相同，codec 独立
- 回滚重读目标 manifest 后经 `resolve_binding` 重查授权；无绑定页不需要 resolver
- 离线生成：`scripts/dsh-b0/page-contract.mjs`；OpenAPI SHA-256 `86ad3cf4d71b05cb827a52f38b568ae3e0ed02ea7312a9dd3b6d848971e0ef3a`（OCR 修复后重生成）
- 插件夹具：`dsh-plugins/analytics-workbench/src/free-page/contract/`（B–F 应改引用这里，而不是继续发明字段）

HTTP 前缀：`/api/v1/analytics/page-documents`。本 lane 提供 `create_page_app` / `page_documents_router`，**未**挂到 `analytics_competition_app` 或现役 6677。

## 改动文件

| 路径 | 作用 |
|---|---|
| `backend/contracts/page_documents.py` | 页面包、manifest、桥消息、错误、OpenAPI 源 |
| `backend/contracts/analytics-page.openapi.json` | 离线生成物 |
| `scripts/dsh-b0/page-contract.mjs` | `--check/--write`，不启动 CRM |
| `backend/services/analytics/page_documents.py` | 存储、CAS、幂等、回滚 |
| `backend/services/analytics/page_documents_routes.py` | 路由与隔离 FastAPI 工厂 |
| `backend/tests/test_page_documents.py` | 合同负测、D6/D9、重开、冲突、权限、HTTP |
| `dsh-plugins/analytics-workbench/src/free-page/contract/*` | fixture、JS 校验、生成类型、typecheck |

未改：`board_spec.py`、`board_documents.py`、`html-sandbox.mjs`、`src/client/`、`src/free-page/{runtime,resource,preview,bridge,source-index,patch,edit}`、DSH 上游、`manifest.json`

## 验证证据

| 检查 | 准确命令 | 环境/夹具 | 结果/退出码 | 证据 |
|---|---|---|---|---|
| Ruff（新 Python） | `python3.14 -m ruff check backend/contracts/page_documents.py backend/services/analytics/page_documents.py backend/services/analytics/page_documents_routes.py backend/tests/test_page_documents.py` | Python 3.14.4 | 0 | All checks passed |
| 页面存储/合同/HTTP | `python3.14 scripts/run_backend_tests_bounded.py backend/tests/test_page_documents.py` | 隔离 HOME/TMP，合成 SQLite mode 0700 | 0；13 passed | 初版 `.context/checks/20260918T054210840912Z/summary.json`；OCR 修复后 `.context/checks/20260918T061010868921Z/summary.json` |
| 旧 BoardSpec 回归 | `python3.14 scripts/run_backend_tests_bounded.py backend/tests/test_board_documents.py` | 同上，未改看板 codec | 0；60 passed | `.context/checks/20260918T054231792380Z/summary.json`（OCR 修复未改看板文件，未重跑） |
| 离线合同 write/check | `/Users/hutou/homebrew/opt/node@24/bin/node scripts/dsh-b0/page-contract.mjs --write|--check --python /Users/hutou/homebrew/bin/python3.14` | Node v24.19.0；复用主仓 `build-tools` 的 openapi-typescript 7.13.0 / TS 6.0.3，未 pnpm install | 0 | sha256=`86ad3cf4d71b05cb827a52f38b568ae3e0ed02ea7312a9dd3b6d848971e0ef3a` |
| 离线合同 check | 同上 `--check` | 同上 | 0 | 无 drift |
| 插件契约单测 | `/Users/hutou/homebrew/opt/node@24/bin/node --test dsh-plugins/analytics-workbench/src/free-page/contract/schema.test.mjs` | Node v24.19.0 | 0；4 passed | 与 `frozen-contract-v0.json` 字段对齐；拒绝 BoardSpec/未知 op |
| 合同 ground-truth lint | `python3.14 -m backend.contracts._lint` | 全 `backend/contracts/` | 0 | OK All contracts pass |

本机宿主 `node` 为 v25.8.2、pnpm 11.19.0（toolchain 钉 Node 24 / pnpm 11.7.0）。合同生成只用 Node 24；未升降 pnpm。

## 未运行

| 项 | 原因 |
|---|---|
| `node scripts/dsh-b0/pipeline.mjs --check` | 未把 `page-contract.mjs` / `src/free-page` 扫进入口（P12）；本 worktree 无授权 `--prepare`；不能把未接线的 pipeline 写成通过 |
| 挂载到比赛/B0 现役 HTTP 或 6677 | 禁止切现役服务；路由仅隔离 `create_page_app` |
| 浏览器 iframe / MessageChannel | Lane B/P12 |
| `test_page_result_access.py` / 真实 result 读取 | Lane C |
| 真实 AI / P13 | 未授权 |
| commit / push / merge | 无另行授权 |

未运行项均不报通过。

## OCR 委派审查后的修复（同日）

审查 11 个可审文件，0 skipped。无 Critical/High。已修全部 Medium：

1. 包总字节超限 → `PACKAGE_TOO_LARGE` 413（Pydantic `package_too_large`，store/HTTP 同步）；字段 `max_length` 仍 422 `INVALID_PAGE`
2. `PageDocument` 强制无 `result_refs` ⇔ `UNBOUND_SAMPLE`；store 校验前 `stamp_binding_state`
3. `schema.mjs` 用 `TextEncoder`，不再依赖 `Buffer`
4. JS：非法 sha256 为 `INVALID_PAGE`；校验 binding/read `mode`；桥消息拒绝未知字段
5. 离线 OpenAPI 去掉 D6 可选项的 `default: null` / `anyOf null`，生成类型为 `title?`/`package?`/`binding_manifest?`；typecheck 用 omit 形，`title: null` 为 `@ts-expect-error`

## 交给下一批次 / integration notes

1. **合同 SSOT**：`backend/contracts/page_documents.py` + `analytics-page.openapi.json` + `src/free-page/contract/page-contract.generated.d.ts`。协调夹具 `fixtures/frozen-contract-v0.json` 语义未改；Lane A 落地后调用方应改引用生成类型/`contract/fixture.json`。
2. **P12 接线**：在 `pipeline.mjs` 的 `board-spec-contract.mjs` 之后增加 `page-contract.mjs --check`；`src/free-page` 的 `.test.mjs` 纳入扫描。将 `page_documents_router` 挂到正式 B0 HTTP，不要改 BoardSpec codec，不要扩展 `html-sandbox.mjs`。
3. **D12**：本 lane 未改 `board_documents.py`。公共层是同一套 preview/confirm/CAS/receipts 协议 + 新库新 `application_id`。若要抽共享 Python 类，由 P12 在不改 BoardSpec codec 的前提下做，避免六路冲突。
4. **Lane C**：`resolve_binding(actor, session_id, result_ref) -> VERIFIED|STALE|UNAVAILABLE|REVOKED`。桥请求 `data.read` / `data.cancel`；禁止 sql/save/http.fetch/credential.read。
5. **Lane B**：包内 `resources[].sha256` + `byte_length`；运行时不要从本 lane 资产表写缓存实现。
6. **Lane D/E/F**：D6=`patch-preview`+confirm；D9=`save-preview`+confirm。`cancel` 不是保存。生成失败不写 head。
7. 无 commit：下一 AI 使用本 worktree 绝对路径，不要猜提交。

## 进程与文件归属

- 仅 pytest `TestClient` 与重开用的短生命周期 `python -c` 子进程；结束后无自有监听
- 现役 6677 未触碰
- 合成库均在 pytest 临时目录，mode 0700；无归档 DuckDB 访问
- 未安装依赖、未写凭据、未发布公网
