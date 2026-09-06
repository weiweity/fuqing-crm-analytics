# B0 监督器复查与当前软件工程阶段

日期：2026-09-06。当前状态：`EXIT_OBSERVABILITY_VERIFIED / NATIVE_EXTENDED_RECHECK_PASS / SUPERVISOR_ROOT_CAUSE_UNRESOLVED / B0_PARTIAL`。

后续状态入口：[B0 本地连续执行收口](./B0-LOCAL-CLOSEOUT-2026-09-06.md)。本文保留本专项原始记录；后续方法/界面等通过不改变历史退出根因 OPEN。

> 第二次“继续”的执行更新见 §5：新增被动退出记录与 8 项测试，统一检查 151 Python / 100 Node 通过，原启动方式七问复验 PASS。§1–4 保留此前外层观察轮次；历史故障仍未定位，不宣称修复或 B0 全通过。

承接用户“继续这一步，并说明目前处于哪个软件工程环节”。本轮完成专项诊断和一次完整原生七问复验，没有修改产品源码、上游 DSH 或监督器行为。此前三次失败仍保留，不能用本次通过覆盖历史问题。

## 1. 调查结论

- 原症状：上一轮监督器消失，其同进程 mock 端口也消失；API、网关和 DSH 成为孤儿。没有留下可确认退出原因的日志。
- 已测试假设：在实际隔离监督器上关闭 stdout 读取端，再触发宿主重启。监督器保持存活，新宿主 READY，无 stderr 错误；本实验不支持“console 输出 EPIPE 导致退出”。未据此修改输出处理。
- 历史目标时间/PID的本地系统日志查询和 Node 崩溃报告文件名检查未提供原因。不能推定 DSH 缺陷、系统杀进程或外层运行器重启。
- 新增一次性外层观察：持有本次子进程句柄，记录时间、代际、stdout/stderr、close 退出码/信号；10 分钟有界预算，不安装守护进程，不重启其他服务，不记录配置或凭据。
- 本次监督器贯穿 API/宿主故障注入保持存活；最终由本次观察器接收明确 TERM 后停止。外层收到 `code=0 / signal=null`，监督器留下正常停止和 mock 证据。

**根因仍未确认，不能声明已修复。** 本次观察改变了外层启动/输出承接方式，单次通过不能证明旧启动条件稳定。后续需要在可记录退出原因的原启动条件下复现；不为捕获偶发问题自行安装后台常驻监控。

## 2. 本次原生旅程

使用既有固定 Node 24、Python 3.14、DSH SHA 和上一轮干净构建 `clean-build-SqV8kJ`；新建小合成运行目录 `runtime-Y7fspZ`。浏览器只有本次 tab 2；模型请求全部指向本地 mock。

第一次调用验证器时，内部测试提示尚未从页面状态移除，发送按钮点击超时；账本为 0 行，没有提交问题。确认提示内容并通过既有内部准备入口保存提示状态后，刷新并确认页面就绪，才在这份仍为空的会话执行七问。首次准备失败报告独立保留，未改成 PASS。

| 原生问题 | 预期与实际 |
|---|---|
| 1 / 2：连续查询 | 均 SUCCEEDED，各 1 个工具步骤 |
| 3：慢生成，API 重启后停止 | CANCELLED；原任务与账本保留 |
| 4：停止后再次查询 | SUCCEEDED，1 个工具步骤 |
| 5：固定模型错误 | FAILED / error，不冒充完成 |
| 6：慢生成中 DSH 宿主崩溃 | FAILED / interrupted，核对原执行退出 |
| 7：宿主恢复后再次查询 | SUCCEEDED，1 个工具步骤 |

全部七个 run 的 `dispatch_attempts=1`、`execution_exit_confirmed=true`。刷新后原生历史恢复，原 ID/结果不变，新增 run 为 0。未出现验证器检查的原生事件回放错误。11 次 mock HTTP 请求中两个慢流为 `client_closed`；没有收费模型调用。

证据均在本地隔离目录，以下不链接带能力凭据的私有启动文件：

- [完整七问 PASS](../../.context/dsh-b0/runtime-Y7fspZ/native-ui-1788668692904.json)、[准备阶段 FAIL](../../.context/dsh-b0/runtime-Y7fspZ/native-ui-1788668614984.json)。
- [监督器退出观察](../../.context/dsh-b0/supervisor-observation-AoJZKJ/lifecycle.jsonl)、[正常停止](../../.context/dsh-b0/runtime-Y7fspZ/stopped.json)。
- [桌面 1280×900](../../.context/dsh-b0/runtime-Y7fspZ/native-success-desktop.png)、[移动 390×844 稳定状态](../../.context/dsh-b0/runtime-Y7fspZ/native-success-mobile-settled.png)。刚调整宽度的过渡截图另存保留；等待原生响应布局完成后再检查，document/body 宽均为 390，无页面横向溢出。这是局部视觉检查，不是完整 UI 验收。

## 3. 软件工程上处于哪里

**处于“技术底座实现后的集成验证与可靠性加固”，对应 B0 工程验证阶段；不是完整产品进入上线前测试。**

| 工程环节 | 当前状态 |
|---|---|
| 需求、范围、架构与测试设计 | 主线及 D1–D4 已确认，有实现任务和故障地图；不等于全部业务需求已验收 |
| 技术底座编码 | 最小任务内核、DSH 协议接线、合成只读 worker 已实现 |
| 单元/合同/局部集成测试 | 上一轮 151 Python、92 Node、类型检查与干净构建通过；源码未改，本轮复用该证据，没有虚报重新运行 |
| 原生端到端与故障恢复 | 本次完整七问单次通过；历史监督器偶发退出仍未定位，稳定性关卡未关闭 |
| 完整业务 MVP | B1–B4 尚未开始；完整查询金标准、分析资产、可配置驾驶舱及营销业务链不能报完成 |
| 用户验收与发布 | 未进入完整 UAT；远端 CI 未跑，无 commit/push/PR/merge、部署或生产验收 |

B0 剩余还包括获批 Skill 整包 hash/引用漂移、compaction 与旧记忆冲突、完整当前 live 权限绕过矩阵、BI/主题/品牌等原门。MCP 仍未启用。下一步先关闭监督器稳定性证据缺口并完成其余 B0，再进入后续业务阶段；不重复进行已完成的架构静态评审。

## 4. 收尾

本次观察器、监督器、网关、API 和 DSH 均已退出；4315–4319 无监听，本次浏览器 tab 已关闭，原共享 tab 保留。未触碰旧 5173/8000、归档真实 DuckDB、ETL、个人模型凭据或全局依赖。只更新本报告和当前计划入口，保留原有脏工作树与全部失败证据。

## 5. 后续：被动退出记录与原启动方式复验

用户再次授权“继续”后，完成退出证据子项。此次没有外层 Node 包装器，直接执行原 `node serve.mjs --python … --plugin …` 入口。

### 改动及边界

- 新增 [lifecycle-observer.mjs](../../scripts/dsh-b0/lifecycle-observer.mjs)：每个新运行目录内独占创建 `0600` 日志，使用同步追加，记录启动、父 PID、受控信号、子进程代际/退出、宿主就绪、停止、fatal 和 exit。字段白名单不保存提示词、路径、token、原始 error message/stack 或 stdout/stderr。
- [serve.mjs](../../scripts/dsh-b0/serve.mjs) 仅接入记录，不修改重启、派发、停止或模型行为。错误观察使用 `uncaughtExceptionMonitor`，不安装 `uncaughtException` / `unhandledRejection` 恢复处理器，不增加信号处理种类；Node 默认异常退出行为保留。此选择与 [Node 官方说明](https://nodejs.org/api/process.html#event-uncaughtexceptionmonitor)一致，并由实际 Node 24.19.0 子进程测试验证。
- 5 秒记录定时器 `unref`，不会延长进程寿命；最多 500 条普通事件、1 条上限标记及各 1 条 fatal/exit。写入失败不抛出第二次异常；日志文件创建失败会在启动子服务前失败，不覆盖旧文件。该记录不是持久化业务账本，也没有磁盘断电耐久性保证。
- `SIGKILL`、默认致命信号和掉电可能没有进程内 exit 记录。**没有 exit 记录不等于已经证明 SIGKILL、OOM 或外层运行器退出。** 不新增守护进程、自动重试、常驻监控或费用。

### 验证

新增 [8 项隔离测试](../../scripts/dsh-b0/lifecycle-observer.test.mjs)：正常非零退出/定时器不保活、uncaught exception、unhandled rejection、默认 SIGTERM、SIGKILL、字段脱敏/权限、容量上限保留终态、旧文件及软链不覆盖。前五项运行真实短生命周期子进程，不在主测试进程上发终止信号。已加入 [统一 pipeline](../../scripts/dsh-b0/pipeline.mjs)，不是只运行一次的未登记脚本。

本轮统一 pipeline 于 `2026-09-06T06:08:44Z` 完成：**151 Python（1 条已有警告）、100 Node（无失败/跳过）、类型检查、真实 Cordis loader 与两处构建通过**；干净目录 `clean-build-KKKU0I`。三份插件产物 hash 与 §3 引用的上一轮一致；远端 CI 仍未执行。

新运行目录 `runtime-2efKvv` 的[原生七问报告](../../.context/dsh-b0/runtime-2efKvv/native-ui-1788675064277.json)为 PASS。七个状态依次为 `SUCCEEDED / SUCCEEDED / CANCELLED / SUCCEEDED / FAILED / FAILED / SUCCEEDED`；全部只派发一次、实际执行退出已确认，刷新恢复原历史且新增任务为 0。提示确认后先刷新并检查页面就绪，本轮没有准备阶段失败或重复提交。

[退出记录](../../.context/dsh-b0/runtime-2efKvv/supervisor-lifecycle.jsonl)共 55 条、4604 字节、权限 0600，实际捕捉 `SIGUSR1 → kernel SIGKILL → generation 2`、`SIGUSR2 → host SIGKILL → generation 2 READY`、受控 `SIGTERM → stop-complete → exit 0`。没有 fatal 事件；原父 PID 贯穿观察。11 次本地 mock 请求中两个慢流 `client_closed`。[停止记录](../../.context/dsh-b0/runtime-2efKvv/stopped.json)与退出记录一致。

监督器、网关、API、宿主均已核验退出；4315–4319 无监听，本次 tab 2 已关，原 tab 1 保留。没有运行真实库/ETL、调用收费模型、提交或发布。

### 当前判断与下一项

退出记录子项 **DONE**；历史监督器故障根因仍 **OPEN / NOT REPRODUCED**。本轮与此前外层包装轮次分别通过，不合并成“同配置连续稳定性测试”，不把诊断接入称作故障修复。后续若自然复发，以新记录继续定位；不无依据重复七问或扩大到常驻系统监控。

下一项推进独立的 B0 Skill 整包/引用漂移与 compaction（上下文压缩）验证，同时保留这个开放风险。技术底座仍处于集成验证与可靠性加固，未进入 B1–B4、完整业务 UAT 或发布。
