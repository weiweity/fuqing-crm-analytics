# T09 原生故障、卡片共存与监督器验证

日期：2026-09-07。第 3 项本地限定链路已完成，**整体 B0 仍 PARTIAL**。工作树为 `.worktrees/hackathon-mission-mvp`，分支 `codex/b0-native-fault-validation`，基于 `c5b1566`；本页新增修复未提交/推送。第 1、2 项 PR #67 已合并为 `ee66469`，与本页本地补丁分开。

## 两处实证修复

**日志管道关闭可使 supervisor 退出。** `serve.mjs` 原先直接把内核 stderr 转发到自己的 stderr；接收端关闭后，真实内核错误输出触发未处理的 `EPIPE`，Node 退出，子进程需要验证器收尾。此前 stdout 的负测未覆盖这条链路，不能排除此原因。

本次使用同一受控驱动：新建隔离实例，关闭父进程的 stderr reader，在本次生成的 manifest 尾部加一个换行，再对本次 supervisor 发送 SIGUSR1；内核重启时校验拒绝并产生真实 stderr。只恢复本次 manifest，按已记录的进程身份回收本次子进程。

| 对照 | 结果 |
|---|---|
| 关闭 stderr reader，健康内核重启 | supervisor 存活；没有错误输出，不能单独证明容错 |
| 关闭 reader + 无效合成 manifest，修复前 | PID 90836 退出 1；生命周期记录 `fatal / uncaughtException / EPIPE` |
| reader 保持打开 + 同一 manifest 故障 | PID 91449 存活，主动停止后退出 0 |
| 关闭 reader + 同一故障，修复后 | PID 94750 存活；只记录一次 `diagnostic-pipe-closed / EPIPE`，主动停止后退出 0 |

`diagnostic-sink.mjs` 在日志流的 EPIPE 后停止继续转发，使用已有受限生命周期记录，不记录原始异常文本/凭据。其他流错误仍抛出；未加入全局异常吞掉、自动重启循环或常驻监控。真实 Node 子进程管道关闭、非 EPIPE 错误及现有被动观察器共 11 项通过。

**运行中夹具漂移曾绕过 worker 失败记录。** 原父进程在执行租约登记前调用 `fixture.validate()`；启动后 manifest 改变或数据文件丢失时，异常直接离开请求，账本没有 worker 故障记录，最终只得到 `MODEL_FAILED`。新增两条回归先复现失败。

现在复用 `analytics_worker.py` 已有的校验：worker 在打开 DuckDB 前及输出结果前各校验一次；启动时 `WorkerManager` 的校验也保留。执行期校验位于持有租约的子进程协议内，错误生成 `TOOL_FAILED`，父进程确认退出后记录原因并释放计算槽。两个新用例用小型临时 fixture、真实子进程和重新打开的 SQLite 验证落盘；不改业务库、不放宽资源限制或事实校验。

`steps` 沿用既有 STARTED/SUCCEEDED 模型，失败的步骤不被伪造为成功；本次完善的是 worker 退出证据和任务失败原因，不新增状态迁移。最终任务 `FAILED / TOOL_FAILED`、结果为空、worker 为 EXITED 且无占用。

## 原生四问与证据绑定

固定上游仍为 `d347e703908d0406b7a7ef80e3a0e594d86b2215`，Node 24.19.0 / Python 3.14.4 / DuckDB 1.5.3，原 DSH Web、单 Agent Loop、独立插件与本地官方 mock。使用 `serve.mjs --native-cards` 的有限八步官方 mock 配置；仅为各请求选择工具名/参数，不改写工具结果、原生日志或组件状态。

浏览器实际通过输入框发送四问；第二问前只改变当前临时 manifest，失败后恢复原字节。未直接调用 prompt RPC。

| 问次 | 实际链路 | 最终任务与可见结果 |
|---|---|---|
| 1 | 原生 analytics_b0_query → FastAPI → 只读合成 worker | SUCCEEDED；原生卡显示 100 / 25 / 25% |
| 2 | 同一工具 → 损坏 manifest → worker 校验拒绝 → HTTP 拒绝 → 原生 tool/result | FAILED / TOOL_FAILED；卡片明确无可用结果，不显示 25% |
| 3 | 原生 skill（growth-analysis-b0）→ 原生 analytics_b0_query | SUCCEEDED；同一轮 2 tool calls，原生 Skill 行与分析卡同时存在 |
| 4 | 故障后新问数 → 新 worker | SUCCEEDED；结果正常，故障未占住计算槽 |

运行实例：`runtime-Su4aaO`。核对了 SQLite 的 4 个 run/attempt/request、原生持久化日志的 5 个唯一 call ID、对应 turn 与 tool/result。仅失败调用的 `isError=true` 且无成功 meta；三个查询成功 meta 均通过实际解码，Skill 保留自身原生渲染。4 个物理 worker 都有 EXITED 记录，租约 inode 与独立非阻塞锁检查一致，无活动槽。

刷新后重新展开工具组：3 张成功分析卡、1 张失败卡及 Skill 行保留；四个任务身份与结果相同，新增 run 为 0。截图 `native-cards-fault-and-skill.png` 已实际查看，失败卡与同轮 Skill/成功卡可见；未修改页面 DOM 来制造状态。

## 检查、失败留痕与文件

| 层级 | 最终结果 |
|---|---|
| B0 Python | 167 PASS，保留 1 项既有 warning |
| 源 Node | 138 PASS，包括真实管道、有限多工具 mock 和现有权限/协议检查 |
| 编译/装配/组件 | 14 PASS；原目录和干净目录各验证，不累加成不同测试 |
| 类型与构建 | Host/Client 完整类型通过；`clean-build-KE8eQs` 四个入口逐字节一致 |
| 原生浏览器 | 四问 3 成功 / 1 预期工具失败；多 key 同轮、刷新、持久化身份与物理退出核验通过 |
| Git/远端 | T09 仅本地；PR #67 的绿灯不能替代本补丁的远端 CI |

本地证据位于 `.context/closeout-20260906/`：

- `supervisor-closed-stderr-invalid-fixture-1788710738682972000/report.json`：EPIPE 修复前；`supervisor-baseline-invalid-fixture-1788710793375417000/report.json`：reader 打开对照；`supervisor-closed-stderr-invalid-fixture-1788711162861774000/report.json`：修复后。
- `probe-supervisor-stderr.py`：有界实际启动与故障驱动；上述报告保留运行目录与完整受限生命周期事件。
- `native-fault-final-evidence.json`：源码哈希、构建哈希及原生报告定位；两张 `native-cards-*.png` 为实际页面截图。
- 原生报告：`.context/dsh-b0/runtime-Su4aaO/native-card-evidence-1788711875848.json`，同目录保留压缩原生日志、SQLite、mock-evidence 与 `native-card-snapshot.txt`。
- `.context/checks/native-fault-before.log`：运行中夹具变化的两条失败回归；`native-card-b0-pipeline-final.log`：最终统一检查。

早期原生实例 `runtime-iaiR4w` 保留父进程异常的基线：有失败卡但缺 worker 记录，Skill-only 问次也不能满足“必须有分析主结果”的成功契约。修复后的四问改为 Skill 后继续分析，不将方法读取冒充分析成功。证据脚本最初误读 result 顶层 callId、误把原生 role=button 当成 HTML button，纠正后仅核对已有四问，没有重发。此前检查与原生实例并行时 loader 被占用的 4316 正确阻断；停止临时实例后整条 pipeline 通过。

控制台保留网关有意拒绝的 Cordis inventory/inspect 403，以及刷新期间连接重建提示；不声称零控制台错误，也不为消除提示扩大权限。失败轮的原生摘要仍显示上游 `UNKNOWN` 与后续上下文拒绝，业务内核明确记录 TOOL_FAILED；没有改动上游错误渲染。

## 仍开放与收尾

- 历史三次 supervisor 消失没有可用原始致因证据，仍 **OPEN / 原因未证实**。本次 EPIPE 因果模式已复现并修复，不能倒推三次历史事件都是该原因，也不声明长期稳定性通过。
- UI-B02 的原生 running 状态与未知版本全链未补测。8 状态组件测试仍是组件证据；现有生产者拒绝无效 meta，不能通过伪造成功结果来强造未知版本原生卡。
- 真实模型、业务数据/UAT、多人容量、B1–B4、数仓 ETL 和公开部署仍未进入。
- 本次两个原生实例与所有故障探针子进程已停止；4315–4319 无监听，测试页 2/3 已关闭，最终 supervisor 退出 0。原有 Mission 演示 PID 36717/36727（8000/5173）保持运行。未部署、删除分支或触碰其他工作树。

复用入口：先启动 `node scripts/dsh-b0/serve.mjs --python /absolute/python3.14 --native-cards`，按现有 rpc bootstrap / gateway / browser 与测试声明流程准备新实例，再运行 `node scripts/dsh-b0/native-card-smoke.mjs /absolute/current-runtime /absolute/browse <owned-tab-id>`。只有已存在该脚本四问时可用 `--verify-existing` 补证，它不会重发问题。统一检查须在临时原生实例停止后运行，避免与 loader 的 4316 占用冲突。
