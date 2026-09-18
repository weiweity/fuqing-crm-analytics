# Lane H · 隔离 page-documents / result-access HTTP

- 状态:**DONE**(实现与隔离验证完成;未 commit,未 push,未触碰现役 6677)
- 执行日期:2026-09-18
- 工作树:`/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/fuqing-crm-analytics-free-html-H`
- 分支:`codex/free-html/lane-h`,HEAD = `d6b57452`(== origin/main 基线,0 commit)
- 现役 6677 PID 83542:全程未 stop / 未 reload / 未 HTTP 探测(仅 `ps -p 83542` 静态确认存活)
- 131GB DuckDB:未打开、未复制、未执行 SQL

## 交付物

生产保存不再停在内存的完整接缝,`index.tsx` **零改动**(P12 store 已读 env,本轮补的是 env 到达浏览器与隔离 HTTP 本体):

| 文件 | 类型 | 职责 |
|---|---|---|
| `scripts/dsh-dev/page_http_server.py` | 新增 | 隔离 HTTP 本体:uvicorn loopback 单进程,`create_page_app(identities, page_state_dir=显式小 SQLite, result_access=PageResultAccess())`,CORS 允许 127.0.0.1 任意端口(浏览器 6677 页面跨源必需);拒绝非 loopback host 与 6677 端口;token 走 `PAGE_DOCUMENTS_HTTP_TOKEN` env |
| `scripts/dsh-dev/page-http.mjs` | 新增 | Node 启动器:spawn 上述 Python 子进程,默认端口 **18091**(随机端口亦可,`--page-http-port`),spawn 前 `assert.notEqual(port, 6677)`;就绪探测 = ready 日志行 + 对 binding-state 的带 token 只读探测(200);提供 `stop()`、`writePageHttpState()`(base 写 `page-http-state.json`,token 单独 0600 文件) |
| `scripts/dsh-dev/page-globals.mjs` | 新增 | 新 overlay row `analytics-dev-page-globals`(仿 `brand.mjs` 先例):宿主 env 有 `PAGE_DOCUMENTS_HTTP_BASE/TOKEN` 时,通过 upstream 官方通道 `ctx.on('webserver/index-inject', table => table.push({kind:'global', ...}))` 把 4 个 `globalThis.__PAGE_*__` 行渲染进 index.html——这是浏览器 bundle(`page-http.mjs` 客户端)读配置的唯一通道(build 时 `process.env.PAGE_*` 被 define 成空,`dsh-plugins/.../build.mjs:38-43` 现状);未配置则不注入任何行,客户端保持 `http_not_configured` 失败,绝不默认 6677 |
| `scripts/dsh-dev/overlay.mjs` | 修改(+4/-1) | `buildPluginOverlay` insert 行从 1 行(brand)变 2 行(brand + page-globals) |
| `scripts/dsh-dev/serve.mjs` | 修改(+37/-2) | `isolatedEnv` 透传 `PAGE_DOCUMENTS_HTTP_BASE/TOKEN` 与 `PAGE_RESULT_*` 到 6677 host 进程(仅显式配置时;base 含 `:6677` 直接 throw);`parseServeArgs` 新增 `--page-http on|off`、`--page-http-port N`(拒 6677 与 owned web 端口);`writeCurrent` 记录 `pageHttpBase` |
| `scripts/dsh-dev/cli.mjs` | 修改(+30/-1) | `start`/`reload` 支持 `--page-http on`:boot 时在 host 启动**前**拉起隔离 HTTP(同 supervisor 生命周期,cleanup 停止),把 base/token 写进 supervisor 自身 `process.env`(由 `isolatedEnv` 自然传给 boot 子进程),打印 `DSH_DEV_PAGE_HTTP <base>`(token 不打);`status` 新增 `DSH_DEV_PAGE_HTTP` 行;reload flag 透传 |
| `scripts/dsh-dev/page-http.test.mjs` | 新增测试 | 7 case:真实 spawn Python 端到端(401/200/generate+confirm/save+confirm/binding-state)、6677 双重拒绝(launcher + REFUSED_LIVE_PORT)、isolatedEnv 透传与 6677 拒绝、overlay rows 与 6677 拒绝、result base override、serve flags、state 文件 |
| `backend/tests/test_page_http_launcher.py` | 新增测试 | 6 case(TestClient):显式 state_dir 挂载 + SQLite 落盘 + result 路由同 app、服务器拒绝 0.0.0.0/6677/缺 token、CORS 放行 127.0.0.1:6677 且拒外域、result bridge read 200 / sql op 400 BRIDGE_UNKNOWN_OP、launcher/server 源码契约(6677 拒绝、create_page_app 复用、无 BoardSpec)、默认端口非常见保留端口 |
| `dsh-plugins/analytics-workbench/src/client/free-html-library/page-http-globals.test.mjs` | 新增测试 | 2 case:pin 浏览器端契约——`globalThis.__PAGE_*__` 注入后 `pageDocumentsHttpOptions()/pageResultHttpOptions()` 正确读取(result 回落 documents base/token),未配置返回 null,`:6677` 抛 `REFUSED_LIVE_PORT` |
| `scripts/dsh-dev/cli.test.mjs` | 修改 | overlay 断言同步:2 行 id 顺序 + name 以 `.mjs` 结尾 |

## 关键设计决定

1. **6677 进程不挂这些路由**:隔离 HTTP 是独立 Python 进程(uvicorn),与 6677(Node/DSH web)完全分离;`create_page_app` 只在 `page_http_server.py` 显式调用,competition app 默认挂载行为未触碰(`test_p12_page_mount.py` 与 `test_page_result_access_http.py` 的 AST 门禁原样保留且通过)。
2. **env → 浏览器的桥**:upstream `webserver/index-inject` 的 `kind:'global'` 行渲染为 `<script>globalThis["名"]=值</script>`(`packages/host/webserver/src/injections.ts`),overlay row 是 upstream 官方插件机制(inspector 先例 `ctx.on('webserver/index-inject')`、本仓 brand.mjs 先例),不改 DSH 上游。
3. **未配置 = 保持失败**:客户端 `page-http.mjs` 现有语义不变(`http_not_configured` / `RESULT_HTTP_NOT_CONFIGURED`),宿主侧不注入即维持;无任何路径默认指向 6677。
4. **幂等键是合同要求**:confirm 不带 `Idempotency-Key` 返回 428 `IDEMPOTENCY_KEY_REQUIRED`(冒烟中验证),与 live-adapters 的 `confirmPreview(idempotencyKey)` 行为一致;隔离 HTTP 端到端全部带 key。
5. **launcher spawn 前后三重 6677 防线**:Node launcher `assert.notEqual(port, 6677)`;Python server `--port 6677` exit 2;`isolatedEnv`/`page-globals` 对含 `:6677` 的 base 直接 throw(含 `REFUSED_LIVE_PORT`)。

## 验证证据

cwd = 本工作树。Node v24.19.0(`$HOME/homebrew/opt/node@24/bin`)、Python 3.14.4、ruff 0.15.14(仓库 select E4/E7/E9/F)、`DSH_DEV_UPSTREAM` = 主仓 `.context/dsh-b0/upstream`(ddefc45f)。

| 检查 | 命令 | 结果 |
|---|---|---|
| 语法 | `node --check` ×5 个 mjs + `ast.parse` py | 全过 |
| Python 页面全套 | `python3 -m pytest backend/tests/test_page_documents.py test_p12_page_mount.py test_page_result_access.py test_page_result_access_http.py test_page_http_launcher.py` | **41 passed** |
| ruff | `python3 -m ruff check scripts/dsh-dev/page_http_server.py backend/tests/test_page_http_launcher.py` | All checks passed |
| dsh-dev node 全套 | `DSH_DEV_UPSTREAM=… node --test scripts/dsh-dev/*.test.mjs` | **76 passed / 2 failed**;2 个失败为 `brand.test.mjs`+`diagnose.test.mjs` 的 `lfs_pointer`(本树 `shine-mage.png` 是 git-lfs 指针)。stash 后基线复跑同样 2 fail → **与本 lane 无关的既有失败**,未执行 `git lfs pull`(共同规则禁装/拉浮动内容) |
| 本 lane node 测试 | `node --test scripts/dsh-dev/page-http.test.mjs`(含真实 spawn Python 子进程) | **7 passed**(约 3.5s,端口 18091) |
| cli.test 回归 | `node --test scripts/dsh-dev/cli.test.mjs` | **20 passed**(含更新后的 overlay 2 行断言) |
| client 测试 | `node --test p12-live-adapters.test.mjs page-http-globals.test.mjs` | **13 passed** |
| client 既有 library DOM | `node --test free-html-library.test.mjs` | **fail:esbuild Cannot resolve `antd/es/*`**。stash 后基线同样 fail → 既有环境失败(本树未装 antd,共同规则禁装浮动依赖),与本 lane 无关 |
| 全链路 E2E(一次性脚本) | launcher → `pageGlobalRows()` → 写 `globalThis.__PAGE_*__` → `createLivePageAdapters(pageDocumentsHttpOptions(), pageResultHttpOptions())` 真实 HTTP | **PASS**:generateAndConfirm v1 → savePreview+confirm v2 → pullHistory 2 items → rollback+confirm v3 → pullPage → bridge.readResult 200 ok → bridge.readBinding UNBOUND_SAMPLE |
| 冒烟(一次性脚本) | 18091 真实 uvicorn:401 无 token / generate 201 / confirm 200 v1 / patch 201→v2 / save 201→v3 / history 3 / rollback→v4 / result seed 201 / read 200 / sql op 400 / CORS preflight(Origin 6677)200 allow-origin=http://127.0.0.1:6677 / `REFUSED_LIVE_PORT` | 全过 |
| overlay patch 可被 pinned CLI 读 | `dsh apps/cli/lib/bin.js --profile web --patch <overlay> --dump-config`(临时 HOME) | 成功,dump 含 `analytics-dev-page-globals` 与 `analytics-dev-brand-assets` 两行 |
| reload 透传 | 源码断言 `reloadStartArgs` 保留 `--page-http`/`--page-http-port` | OK |
| `git diff --check` | 工作区 | 无空白错误 |
| 真实浏览器 headed | 未运行 | 未跑(headed 主链路属 P12 既有覆盖;本轮浏览器端桥已由 globalThis 模拟 + client 测试 pin 住) |

## 未运行项 / 边界

- **未 commit、未 push**(无授权;清单见上,集成 PR 由总协调统一开)。
- **真实 Chrome headed 端到端未跑**:本轮验证到 globalThis 注入模拟 + client adapter 真实 HTTP 全链路;headlight 层 P12 已有 `p12-headed-journey` 先例,如需可由集成轮复跑(命令:`node --test p12-headed-journey.test.mjs`,需本树先解决 antd 依赖或复用 P12 树环境)。
- **未用真模型**(P13 范围,无额度授权);测试中 generate 走合同 API 直写源码包,不经生成工具。
- **antd / git-lfs 品牌资产**:本树环境缺失,相关 3 个测试失败为基线既有,未修复(超 owner paths;已在 integration notes 记录)。
- **18091 常驻监听已停**:所有启动器子进程在测试/冒烟后 stop,`ps` 确认无残留;6677 与其 supervisor control 端口全程未探测。

## Integration notes(供总协调)

1. `buildPluginOverlay` 的 insert 行顺序为 brand → page-globals;若 G/K 也改 overlay,合并时保持两行并列即可,行间无耦合。
2. `isolatedEnv` 的 PAGE_* 透传与 COMPETITION_HTTP_* 平行,互不影响;`--page-http on` 与 caller 自设 `PAGE_DOCUMENTS_HTTP_BASE` 互斥(后者直接转发,launcher 拒绝重复 spawn,assert 信息已写明)。
3. 隔离 HTTP 的 CORS 放行 `http(s)://127.0.0.1|localhost 任意端口`;若未来 web host 改绑非 loopback,CORS 需同步收紧(当前 `assertOwnedHost` 已强制 loopback)。
4. `writeCurrent` 新增 `pageHttpBase` 字段;`status` 打印 `DSH_DEV_PAGE_HTTP off|<base>`;老 `current.json` 无该字段时按 `off` 显示,无兼容问题。
5. Python 启动器依赖 `requirements-lock` 既有 fastapi/uvicorn/pydantic(0.136.1/0.47.0/2.x),无新依赖;B0 venv 亦可跑(`FQ_B0_PYTHON` 模式未验证,本轮用 runner python3.14)。
6. 本树既有失败(与本 lane 无关):`brand.test.mjs`/`diagnose.test.mjs` lfs_pointer、`free-html-library.test.mjs` antd 未装。若集成轮跑 `pipeline.mjs --check`,需先处理这两项(P12 报告已有同类记录)。
