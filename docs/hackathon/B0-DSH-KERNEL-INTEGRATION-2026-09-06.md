# B0 原生接线与固定构建：实现及本地验证

日期：2026-09-06。状态：`NATIVE_KERNEL_UNIT_VERIFIED / LOCAL_BUILD_VERIFIED / B0_PARTIAL`。

本报告承接[首个任务内核单元](./B0-RUN-KERNEL-2026-09-06.md)。本次已把同一 FastAPI 任务账本接入固定 DSH 的原生发送、停止、恢复及界面读回，并加入统一本地/CI 构建入口。结论只适用于本地、单活动任务、固定代码 fixture 与本地 mock；不是完整 B0、真实模型、真实数据、容量、整分支审查或发布通过报告。

## 1. 实际改动与责任边界

| 层 | 本次落点与职责 |
|---|---|
| FastAPI 唯一任务权威 | [jobs.py](../../backend/services/analytics/jobs.py)、[runtime.py](../../backend/services/analytics/runtime.py)、[analytics_runtime.py](../../backend/analytics_runtime.py)：原 202、幂等、原生 requestId/attempt 绑定、派发意图、预算、取消、恢复与终态仍只在同一 SQLite 账本决定 |
| Node 网关 | [gateway.mjs](../../scripts/dsh-b0/gateway.mjs)：原生 prompt/cancel 映射到 FastAPI，其他允许的原生协议受限转发；不再创建或读取旧 `b0-dispatch.sqlite` 实验任务账本，没有第二套业务调度循环 |
| DSH Host 协议桥 | [bridge.ts](../../dsh-plugins/analytics-workbench/src/bridge.ts)：从可信原生 request/call/turn 取关联信息；返回原生日志、活动状态和 `whenIdle + flush` 证据，不自立任务权威或模型循环 |
| 分析工具 | [tool.ts](../../dsh-plugins/analytics-workbench/src/tool.ts)：模型只传固定 query；可信原生调用关联后向 FastAPI 预留工具步骤，再取得固定合成结果；没有本地备用结果、任意 SQL 或通用文件/网络工具 |
| 原生客户端增量 | [index.tsx](../../dsh-plugins/analytics-workbench/src/client/index.tsx)、[styles.ts](../../dsh-plugins/analytics-workbench/src/client/styles.ts)：保留原生输入、发送、停止和消息；在公开输入区插槽展示最近三项任务投影，断线标记旧快照，不因刷新重提问题 |
| 固定构建和验收 | [pipeline.mjs](../../scripts/dsh-b0/pipeline.mjs)、[toolchain.json](../../dsh-plugins/analytics-workbench/toolchain.json)、[CI 文件](../../.github/workflows/dsh-b0.yml)：同一准备/检查入口、完整类型、真实 Loader、干净目录复建及产物比较 |

公开 B0 六路由继续使用 `analytics-run-b0/v1`；没有把内部运行时能力、原生关联标识或外部 actor 声明加入公开请求体。生成合同的规范化 OpenAPI SHA-256 仍为 `5d93c3aabf362865e8f24e28c96a8d1f75717c80370f31734407d85b128b9679`。

只有 FastAPI 在提交受理事务后派发。原生界面的 requestId 被保留，避免原生乐观消息无法退场；重复请求返回原 202，不新建 native prompt。运行时失联、未知或取消中继续持有执行名额；收到 DSH 受理/取消回执本身不表示完成或停止。终态需要原请求关联、主结果/步骤条件及实际退出证据。

Host 和工具使用分离的本次运行能力访问受限 loopback 端点；浏览器只通过网关，不获得该能力。固定 B0 主会话由可信启动器绑定，不允许浏览器任意选择外部工作区/会话，也不是多租户生产登录实现。旧 CRM/Vue/Mission、原有认证、真实库、ETL 和生产路径不在本单元改动范围。

## 2. 固定构建的实际证据

| 固定项 | 本次值 |
|---|---|
| DSH 公共源码 | `deepseek-ai/deepseek-harness@d347e703908d0406b7a7ef80e3a0e594d86b2215`；没有 core fork 或上游源码补丁 |
| 上游锁文件 SHA-256 | `2c903ab870f821ee2db62fa9417d11b1c2b9c65fbeec30e851ddc53c4cc8c383` |
| 构建运行时 | Node `24.19.0`、pnpm `11.7.0`；当前 Python `3.14.4` |
| 本地依赖闭包 | 插件 [build-tools 锁文件](../../dsh-plugins/analytics-workbench/build-tools/pnpm-lock.yaml)；Python [22 项精确版本](../../scripts/dsh-b0/requirements.lock)；没有全局配置或安装变更 |
| SDK 和类型 | 固定上游 SDK、TypeScript `6.0.3`、openapi-typescript `7.13.0`；Host/client 分别完整检查，`skipLibCheck: false` |

`--prepare` 已在现有、干净且 SHA/锁文件匹配的上游 checkout 实际完成：冻结安装、指定原生依赖重建和官方 `build:official`。它不是在全新机器/空缓存上的完成声明。初次小构建依赖安装遇到镜像下载失败，已停止本次安装器，仅对后续命令选择官方 registry 并明确使用 Node 24；未修改全局 registry、Node 或 pnpm 设置。

`--check` 不安装依赖、不调用模型或打开业务数据库。真实 Loader 测试会短暂监听私有 4316 后关闭；端口冲突失败，不抢占无关进程。流水线通过后，把没有 `lib`/`node_modules` 的插件源码复制到新的独立小目录，重新绑定已核验的固定 SDK、完整检查及构建。三个 JS 产物逐字节相同，且不存在 `/Users/`、`/home/runner/` 或绝对 file URL 导入。它仍依赖固定 SDK 装配，不宣称是任意宿主可独立运行的 npm 包。

最终[构建证据](../../.context/dsh-b0/build-evidence.json)时间为 `2026-09-06T01:27:57.265Z`；其干净目录产物用于后面的最终原生运行。

| 验证层 | 最终结果 |
|---|---|
| Python 任务/合同/访问/预算/原生适配 | **111 passed**，5 个文件；新 SQLite、小合成夹具和受控进程，不运行旧 CRM conftest；ResourceWarning 按错误处理 |
| 网关/传输/mock/插件源逻辑 | **82 passed**，其中插件自身 20 项 |
| 编译产物与真实 Cordis Loader | **3 项通过 × 原目录和干净目录各一轮**，不是 6 项不同用例；服务门面为合成，完整原生运行另列 |
| 合同生成、正反 TypeScript 类型、Host/client 类型、scoped Ruff | **PASS** |
| 干净目录产物一致与机器路径扫描 | **PASS**，`index.js`、`tool.js`、`client.js` 全部匹配 |
| macOS Seatbelt 正/负权限探针 | **20 项基础 + 4 项原生路径探针通过**；新增桥监听/内核连接的正例与外部网络、无关文件/loopback、shell 的负例分开验证 |
| 远端 GitHub Actions、新机器冷启动、required checks | **NOT RUN / NOT CONFIGURED**；只新增本地 CI 文件，不冒充已有运行结果 |

仍有 1 条现有 Starlette TestClient 关于 httpx2 的弃用提示；未为隐藏警告升级依赖。测试辅助器原有 `select + TextIOWrapper.readline` 在连续两行时存在读缓冲竞态，已改为有界字节缓冲并加入相邻双事件回归，随后重跑通过。

CI 使用 `contents: read`，关闭 checkout 凭据持久化，调用同一 `--prepare`/`--check`，而非另一套命令。所固定 action 的执行引擎已逐个核对为 Node 24，与本项目构建 Node 24 是两层概念：[checkout](https://raw.githubusercontent.com/actions/checkout/fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09/action.yml)、[setup-node](https://raw.githubusercontent.com/actions/setup-node/a0853c24544627f65ddf259abe73b1d18a591444/action.yml)、[setup-python](https://raw.githubusercontent.com/actions/setup-python/ece7cb06caefa5fff74198d8649806c4678c61a1/action.yml)。没有 push、触发远端运行或更改分支保护。

## 3. 原生 UI 五问、恢复和退出

最终运行目录为 `.context/dsh-b0/runtime-jnJ8om`，使用上述干净目录插件。浏览器操作发生于 `2026-09-06 09:32`（Asia/Shanghai）。所有问题从 DSH 原生输入框发送，停止使用当时可见的原生 Stop 按钮，不用私有 RPC 假装点击。完整[原生 UI 证据](../../.context/dsh-b0/runtime-jnJ8om/native-ui-1788658347946.json)与[独立账本/原生日志证据](../../.context/dsh-b0/runtime-jnJ8om/kernel-native-final-1788658347522.json)分开保存。

| 顺序 | 原生操作/场景 | FastAPI 最终态 | 工具步数 / 派发次数 | 核验 |
|---|---|---|---|---|
| 1 | 查询固定合成渠道 | `SUCCEEDED` | 1 / 1 | 主结果完成、原生 completed、实际退出 |
| 2 | 同会话连续第二问 | `SUCCEEDED` | 1 / 1 | 新请求正常执行；不会被旧 in-flight 状态锁死 |
| 3 | 慢速生成中崩溃重启 API，恢复后点 Stop | `CANCELLED` | 0 / 1 | 先 `CANCELLING` 且持额；原生 aborted、活动退出后再终态 |
| 4 | 停止后再次发送 | `SUCCEEDED` | 1 / 1 | 前一任务退出后释放名额，新问正常完成 |
| 5 | 固定服务端错误 | `FAILED` | 0 / 1 | UI 明确失败，不把 HTTP 回执或缺主结果当成功 |

第 3 问的故障只杀死本次启动的 API 子进程，DSH 和账本保留；API PID 从 512 变为 17516。恢复前后同一 `run/attempt/requestId`、原始 deadline 和派发次数 1 均保持，原生用户消息仍只有 1 条，恢复后状态为 `RUNNING`。详见[恢复证据](../../.context/dsh-b0/runtime-jnJ8om/kernel-native-restart-active-1788658337007.json)。这是 API 崩溃恢复，不是 DSH Host 崩溃、整机重启或全部故障窗口覆盖。

停止的独立证据同时包含：FastAPI 取消回执为 `CANCELLING`、执行名额仍占用；对应原生 turn 为 aborted；Host 活动完成并 flush；官方本地 mock 的慢请求结果为 `client_closed`。最终再由 FastAPI 记录 `CANCELLED`，不能用“Stop 按钮点到了”代替退出验收。

同 key/同 payload 回放返回原 202，改 payload 为 409，没有新增 run/native prompt。第五问后刷新页面，五条原生用户消息和三张工具卡恢复，原 ID/结果保持，新增任务数为 0。状态栏展示最近三个 run，分别为停止、完成、失败。SSE 游标和撤权等更多边界由内核测试覆盖，不将它们全部算成浏览器原生故障验收。

所有业务事实仅来自源码 fixture：100 位合成客户、25 位复购、`repeat_ratio=0.25`，日期 2026-09-01。模型端为本机官方 mock；UI 保留的模型选择名称不代表接入了付费/真实模型。

## 4. 浏览器验证发现与修正

早期原生五问已能走到终态，但刷新出现空白。实际定位到固定上游 mock 对多次响应重复使用 `mock-call-1`，与 DSH 会话内工具关联冲突。新增 [mock-provider.mjs](../../scripts/dsh-b0/mock-provider.mjs) 仅按请求为工具 ID 加命名空间；不改工具参数、事实或业务结果，不修改上游。两项回归覆盖唯一 ID 和取消传递，最终原生证据也严格检查 ID 唯一。旧失败尝试保留，不用它们充当最终通过证据。

浏览器视口检查还发现新增任务栏在窄屏透明叠字。修正仅在本插件样式内，沿用固定 DSH 原生输入区的宽度、边距及不透明底色令牌，不修改上游 DOM/CSS。最终三个视口均实际渲染并人工查看截图，文档宽度等于视口宽度，无横向溢出，任务行可读：[1440×1000](../../.context/dsh-b0/runtime-jnJ8om/native-1440.png)、[768×1024](../../.context/dsh-b0/runtime-jnJ8om/native-768.png)、[390×844](../../.context/dsh-b0/runtime-jnJ8om/native-390.png)。另查阅[手机宽度底部状态](../../.context/dsh-b0/runtime-jnJ8om/native-390-bottom.png)。尺寸/底色/状态原始数值见[视口证据](../../.context/dsh-b0/runtime-jnJ8om/responsive-evidence.json)。这是 Chromium 视口检查，不是实体移动设备或完整设计验收。

最终刷新未再出现原生 event-feed 崩溃、TypeError 或 Uncaught。控制台仍有受限插件 inventory/inspect/settings 请求的 403，以及人为 API 崩溃时一次 502；这些均留在证据中，不声称“零控制台错误”。网关没有为消除噪声放开配置、检查器或额外写能力；发布级噪声与界面适配仍需后续处理。

## 5. 复现入口与关闭状态

在本工作树根、已有固定依赖下执行本地流水线（显式解释器，不启动旧 CRM）：

```bash
/Users/hutou/homebrew/opt/node@24/bin/node scripts/dsh-b0/pipeline.mjs --check --python /Users/hutou/homebrew/bin/python3.14
```

依赖准备是显式 `--prepare` 模式；Python 依赖应装入专用环境，不由脚本全局安装。CI 的专用 venv 方案已写入 workflow，尚未远端实跑。

原生验证按 [serve.mjs](../../scripts/dsh-b0/serve.mjs)、[rpc.mjs](../../scripts/dsh-b0/rpc.mjs)、[gateway.mjs](../../scripts/dsh-b0/gateway.mjs)、[native-ui-smoke.mjs](../../scripts/dsh-b0/native-ui-smoke.mjs) 的显式参数分步启动/检查；`serve` 仅支持本次 macOS Seatbelt 环境，`--python` 为绝对路径，`--plugin` 可选指向干净构建目录。浏览器入口要求显式 `--browse` 路径，测试要求新建、空账本运行目录和本次浏览器 tab；固定 mock 序列不可作为长期开启的普通聊天服务重复使用。

本次结束已向核验归属后的监督器/网关发送 SIGTERM，DSH 子进程正常 exit 0，API、mock、桥全部退出。`stopped.json` 时间 `2026-09-06T01:36:36.510Z`（09:36:36 本地）。监督器 502、DSH 513、网关 14578、恢复后的 API 17516 均不再存在；4315–4319 无监听；本次浏览器 tab 已关闭，无关 tab 保留。没有对旧 5173/8000 或无关服务发停止命令。小型合成证据保留在本工作树私有 `.context/dsh-b0`；报告不链接运行能力/会话凭据文件，未读取或复制真实 DuckDB。

## 6. 仍未闭合的门

| 计划检查点 | 当前状态与剩余工作 |
|---|---|
| D1 / 最小内核接线 | **本单元本地通过**：同一账本、原生发送/取消、原 ID 恢复与读回；完整产品身份、共享资产与更多会话不在这次验收内 |
| D2 / 固定插件交付 | **本地通过、CI 待跑**：冻结准备、完整类型、真实 Loader、干净目录复建通过；没有全新机器/空缓存或远端 Actions 成功证据 |
| D3 / 故障矩阵 | **PARTIAL**：账本/受控进程测试及上述原生五问通过；DSH Host 崩溃、派发/终态各持久化窗口组合和[完整地图](./ENGINEERING-RUN-TEST-PLAN-2026-09-06.md)仍需逐项证据，不整图勾选 |
| D4 / 资源执行 | **PARTIAL**：任务 deadline/额度/工具步数由原账本控制，真实原生停止已核对；DuckDB 分析 worker、RSS/temp/spill、真实资源压测与强制退出矩阵未实现/未测 |
| 其余 B0 与 B1–B4 | **OPEN / NOT STARTED**：Skill/compaction、完整业务插件与主题约束等原 B0 门尚未全部通过；不据此开始真实分析、共享数仓/ETL、完整驾驶舱或公网发布 |

本次使用 browse 的原生操作/截图检查发现并修正上述测试关联和窄屏样式问题；没有独立模型、子 agent 或整分支 pre-landing review。保留早期报告、静态审查 hash、原 11 工作包和未完成勾选，当前进度入口更新到本报告。

Git：沿用 `codex/architecture-warehouse-plan-closeout`，HEAD `de2d785f4e0c7abe7fcd8fbb39be7d8c5a0c9642`；本次代码仍未提交。未 commit、push、PR、merge、部署、发布、读取真实凭据、付费模型调用、ETL 或删除业务数据。当前分支先前已有其他未提交改动；本报告只认证本单元的已列验证，不宣称整个脏工作树 clean。
