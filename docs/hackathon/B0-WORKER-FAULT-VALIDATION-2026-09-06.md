# B0 只读 worker 与故障恢复：本轮证据和阻碍

> 后续更新：用户授权继续专项复查后，完整七问已取得单次 PASS；历史监督器退出根因仍未确认，B0 仍 PARTIAL。当前状态见[监督器复查与工程阶段](./B0-SUPERVISOR-RECHECK-2026-09-06.md)。下文保留上一轮三次失败和当时暂停状态，不追改历史证据。

日期：2026-09-06。状态：`LOCAL_WORKER_FAULT_SUBSET_VERIFIED / NATIVE_EXTENDED_BLOCKED / B0_PARTIAL`。

本轮响应“继续剩余任务”，承接[原生接线与固定构建单元](./B0-DSH-KERNEL-INTEGRATION-2026-09-06.md)。已实现真正读取小合成 DuckDB 的独立 worker，并补齐一组提交、取消、资源和进程故障测试。**完整七问浏览器旅程仍未通过，B0 不关闭。** 已暂停该旅程的第四次重试，保留三次失败证据；没有启动 B1–B4、真实模型、真实数据库或 ETL。

## 1. 实现内容

| 落点 | 本轮变化 |
|---|---|
| [analytics_b0.py](../../backend/semantic/analytics_b0.py)、[analytics_fixture.py](../../backend/analytics_fixture.py) | 125 笔代码生成订单、100 位合成客户、25 位复购；日期 2026-09-01。固定 SQL 参数化计算，不再由工具直接回传硬编码结果。独立私有目录、manifest/hash/来源/文件类型/体积验证；缺失或污染不回退旧库 |
| [analytics_worker.py](../../backend/analytics_worker.py) | 使用实际子进程及 `read_only=True` 连接；关闭外部访问和扩展自动安装/加载，锁配置；读取结果后关闭连接，再上报协议帧。父进程仍须等待实际退出，不能把 `closed` 帧当退出 |
| [execution_lease.py](../../backend/services/analytics/execution_lease.py)、[worker.py](../../backend/services/analytics/worker.py) | 派生进程前持有独占文件描述符锁；worker 继承同一锁，恢复方用独立描述符验证原 inode 已释放。原 PID 消失不等于执行退出；未知锁、替换文件或可疑临时对象不放槽、不接管旧 PID |
| [jobs.py](../../backend/services/analytics/jobs.py)、[runtime.py](../../backend/services/analytics/runtime.py) | 同一 SQLite 增加 worker 执行记录和唯一物理执行名额；只在实际退出后提交结果/回收。运行名额还须等待 DSH 原生循环退出。SQLite 写锁故障不会让 dispatcher 永久悄悄退出，恢复继续核对原意图，不重发新请求 |
| [bridge.ts](../../dsh-plugins/analytics-workbench/src/bridge.ts) | DSH 宿主重启后通过固定上游 `sessionController.resolveAgent` 恢复原会话；官方独占写锁和中断尾修复提供证据。只在匹配原请求、独立 idle/flush 等条件满足后把 interrupted 记为失败；失败/未知不盲重放 |
| [serve.mjs](../../scripts/dsh-b0/serve.mjs)、[gateway.mjs](../../scripts/dsh-b0/gateway.mjs) | 仅供已授权本地验证的显式宿主崩溃控制和新代际握手；新启动凭据保持私有。网关只允许同一模块集合、同一内容批次下的启动 nonce 轮换，不为重连扩充操作权限 |

公开六路由、Pydantic/TS 合同仍为 `analytics-run-b0/v1`，规范化 OpenAPI SHA-256 仍是 `5d93c3aabf362865e8f24e28c96a8d1f75717c80370f31734407d85b128b9679`。Node 不新增业务账本、第二套调度器或模型循环。没有修改固定 DSH 上游源码。

私有 B0 任务库 schema 升至 2；旧 schema 1 测试库明确拒绝并要求新建验证目录，不自动迁移、覆盖或删除旧证据。它不是对归档业务库的迁移。成功结果复用仍读正式账本，不能触发第二次查询。

## 2. 资源配置与实际进程验证

默认上限未提高：全局一个活动任务/物理 worker，队列 8、单调用者在途 3；整次 120 秒、单工具 30 秒、8 步；DuckDB buffer memory 512 MiB、2 线程、临时文件 512 MiB；RSS 观察阈值 1 GiB。压力用例只使用更低的显式阈值。

`memory_limit` 不是完整进程 RSS 的硬限制，另以进程采样阈值停止本次 worker；采样也不是瞬时 OS 硬上限。[DuckDB 官方 OOM 说明](https://duckdb.org/docs/current/guides/performance/oom)与[配置说明](https://duckdb.org/docs/current/configuration/overview)支持这一边界，不能据此宣称已完成生产内存沙箱。

| 故障或对照 | 已实际看到的断言 |
|---|---|
| 正常只读查询 | 独立进程计算 100 / 25 / 0.25；源 DB hash 未改变；实际引擎/设置入账；退出码 0、原租约可由独立描述符取得后才提交 |
| SQL 中取消、撤权、query deadline、run deadline | 使用实际 DuckDB SQL 内的独立屏障进入目标位置；先保留取消中/执行名额。忽略 TERM 的受控 worker 由本次 Popen 句柄 KILL 并实际 wait；原 deadline、attempt 和步骤计数不重置 |
| RSS / 文件量超限 | 32 MiB RSS 低阈值触发真实采样超限；1 MiB 临时上限用 2 MiB 一次性测试文件触发。只停止所持有的 worker，不填满磁盘，不提高默认上限 |
| DuckDB 真正 spill | 在 125 行只读 fixture 连接内运行有界 `range(2000000)` 排序压力 SQL，不扩大 DB；32 MiB buffer / 64 MiB temp 正例实际出现 spill 并完成；1 MiB temp 负例停止且不提交假成功 |
| 独立引擎临时配额 | 另用有时限的受控子进程，不依赖父进程 temp 观察器，确认 DuckDB 抛出临时配额 OutOfMemory；不是把父级文件阈值误写成引擎已拒绝 |
| API/worker 父进程崩溃 | 真实 SQL 中，以及 worker 意图提交前/后、spawn 后分别中断本次父句柄；stdin EOF 让 worker 自行退出；新实例核对原 lease 后仅回收一次，不按旧 PID 杀进程，不重做 SQL |
| 伪完成/错归属/并发 manager | 先发 result + closed 但子进程未退出时不得提交；错 attempt/result frame 拒绝；两个 manager 共用唯一 SQLite 物理名额，第二个在 spawn 前拒绝 |
| 残余临时文件 | 只在持有已退出原租约时清理该执行私有 tmp 中已验证的一次性 DuckDB spill；名字未知、软链、硬链则拒绝清理并保留名额。结果、事件、状态库与旧测试证据均不删 |

用例与屏障见 [worker 测试](../../backend/tests/test_analytics_worker.py)及[仅测试可执行夹具](../../backend/tests/analytics_worker_probe.py)。测试注入 workload 不开放到模型/HTTP 配置。未进行千万行容量、CPU/多调用者延迟基线或真实业务金标准；不把上述小规模资源门等同 P01–P06 全通过。

本轮实际修正的环境/退出问题：

- 隔离执行设置 `PYTHONNOUSERSITE=1` 后实际使用 DuckDB **1.5.3 / revision 14eca11bd9**，不是交互 user-site 的 dev 版本。锁文件按真实隔离环境固定 1.5.3，psutil 为 7.2.2；没有安装/升级全局依赖。
- 在该隔离引擎上，仅连接配置中填写临时限额并读回不足以证明限额有效；新增连接后的显式 `SET max_temp_directory_size`，再关闭外部访问/锁配置，独立引擎负测通过。此为本地观测，不泛化成所有 DuckDB 版本的缺陷。
- Python stdin 监视线程原先阻塞在缓冲读取，导致正确结果之后进程以 -6 退出。改用原始 fd 读取；仍保留实际退出核验，未通过忽略退出码来“修复”测试。

## 3. D3 故障地图：本轮覆盖与保留的区别

原[完整测试地图](./ENGINEERING-RUN-TEST-PLAN-2026-09-06.md)继续保留全部目标。本表只归位现有证据，不将同一种协议替身重复算成原生端到端。

| 地图行 | 当前证据层/落点 | 尚不能声称 |
|---|---|---|
| I2a/e 同 key、冲突、撤权 | 正式 router、独立 SQLite 连接及授权测试通过 | 多租户生产身份已验收 |
| I2f 受理提交前/后崩溃 | 真实进程屏障、实际 KILL、新连接验证 run/key/intent 原子性 | 整机断电耐久性 |
| I2f 认领提交前/后崩溃 | 新增真实进程屏障；独立接收方零派发；提交后保持 UNKNOWN/原标识，不凭死 PID 重发 | 未收到请求便能推断永远没有收到 |
| I2e 202 响应丢失 | 新增真实 ASGI 响应 body 交付边界中断；QUEUED/RUNNING/SUCCEEDED 均同 key 返回原 bytes/Location，一份 run | TCP 网络设备丢包测试 |
| I2f DSH 受理回包丢失 | 协议替身分别已受理/未受理/未知；固定 DSH 小样另证关联 | 跨系统 exactly-once |
| I2b/g 取消与终态竞争 | 独立连接 CAS 两种先后/真实竞争；SQL 真实屏障/物理退出；原生慢生成 Stop 与 API 重启恢复 | 每个取消阶段与每个宿主故障的笛卡尔组合均已运行 |
| I2c 孤儿/旧 attempt/错 run | worker lease/父进程死亡/独立回收/错帧测试；原生 Host 中断修复取得局部证据 | 七问恢复旅程稳定通过，见下一节失败 |
| I2f/g 模型失败/澄清 | 首工具前及已完成一部分步骤后 FAILED/NEEDS_INPUT；保留步骤证据但不标完整成功；澄清新 run 关联父 run | 真实模型理解与完整多查询族协作 |
| I2d/e 事件恢复 | 合同游标、顺序、过期与权限；插件 GET-only/错 run 负测；旧五问原生刷新证据仍留存 | 本轮七问刷新已通过 |
| A1/A2 来源与控制隔离 | 新 fixture 五类污染拒绝、当前授权和固定网关策略测试 | 本轮旧 gateway-smoke live 负测已重跑；该旧脚本含固定历史路径，未拿来冒充本轮证据 |
| I2a/B1 连续提问 | 本轮原生前两问与取消后第四问通过；第二轮第七问独立账本/原生日志也成功 | 三轮完整浏览器旅程通过 |
| P2/P3 提交/SQLite busy | 新增终态提交前/后真实进程中断及通知丢失后回查；取消/step/result 写锁失败不伪造状态，解除锁后原请求恢复；dispatcher busy 不永久退出 | 磁盘写满/断电、状态读取 SLA 已完成 |

新增测试在 [test_analytics_jobs.py](../../backend/tests/test_analytics_jobs.py)、[test_analytics_run_contracts.py](../../backend/tests/test_analytics_run_contracts.py)、[test_analytics_native_runtime.py](../../backend/tests/test_analytics_native_runtime.py)。它们与物理 worker 测试都纳入同一本地/CI 流水线。

## 4. 三次扩展原生旅程：不能合并成一次 PASS

固定 DSH SHA `d347e703908d0406b7a7ef80e3a0e594d86b2215`，本地官方 mock、私有新 runtime、浏览器原生输入和 Stop。前三次均未取得完整旅程 PASS：

| 运行目录与证据 | 已取得证据 | 本轮失败及处置 |
|---|---|---|
| `runtime-mtbsO8`：[UI 报告](../../.context/dsh-b0/runtime-mtbsO8/native-ui-1788663481304.json) | API 恢复、前五问、DSH 中断归位 | 新 DSH 启动 nonce 变化使网关拒绝旧清单。修复为严格校验模块/内容批次后接纳新 nonce；9 个正负回归通过；没有放开 URL 通配符 |
| `runtime-w12nfr`：[UI 报告](../../.context/dsh-b0/runtime-w12nfr/native-ui-1788664060035.json)、[七问独立账本/原生日志](../../.context/dsh-b0/runtime-w12nfr/kernel-native-extended-final-1788664052944.json) | 七条状态为成功、成功、取消、成功、失败、失败、成功；原 run/attempt/request、实际退出、只派发一次；四个成功步骤均为新只读 worker。API 和 Host 恢复分别有证据 | 最后刷新断言错误地要求最近三条任务区仍显示第三问的中文“已停止”；原生历史实际保留 `Stopped`。已修正断言，但不把这个 FAIL 文件改写成 PASS |
| `runtime-nK9iRj`：[UI 报告](../../.context/dsh-b0/runtime-nK9iRj/native-ui-1788664429861.json) | API 和 Host 恢复检查通过；前六条状态符合预期 | 第七问成为 `MODEL_FAILED`，原生诊断为 `TRANSPORT`。随后只读检查发现监督器 80940 已不在、mock 4319 无监听，原生/API/网关三个自建进程仍存活且 PPID=1；没有正常 stopped/mock 收尾文件。监督器为何退出尚未查明，不能认定 DSH 根因或声称已修复 |

第三轮故障 UI 已实际截图并查看：[1280×900](../../.context/dsh-b0/runtime-nK9iRj/native-failure-desktop.png)、[390×844](../../.context/dsh-b0/runtime-nK9iRj/native-failure-mobile.png)。这些是失败现场，不是窄屏、品牌或交互全通过截图。界面显示了失败，没有把第七问包装为实时成功。

依 browse 技能三次失败升级规则，当前暂停第四次完整浏览器重试。建议下一单元先专项定位临时监督器/本地 mock 的退出原因，补稳定的进程与诊断留存，再在全新空会话复跑；不能通过提高预期、跳过第七问、延长至无界等待或重写失败报告获得 PASS。

## 5. 最终本地流水线

实际命令，工作目录为本 worktree 根：

```bash
/Users/hutou/homebrew/opt/node@24/bin/node scripts/dsh-b0/pipeline.mjs --check --python /Users/hutou/homebrew/bin/python3.14
```

最终时间 `2026-09-06T03:19:52.783Z`（11:19:52 本地），Node 24.19.0 / Python 3.14.4；[当前构建证据](../../.context/dsh-b0/build-evidence.json)。

| 检查 | 本轮最终结果 |
|---|---|
| Python 六文件任务/授权/合同/预算/原生适配/worker | **151 passed**，14.49 秒，1 条已有 Starlette httpx2 弃用提示；ResourceWarning 按错误处理；无 skip |
| Node 插件/网关/传输/mock 源测试 | **92 passed**，无 skip |
| 真实 Cordis Loader 与编译产物 | **3 个用例 × 原目录/干净目录各一次 PASS**；不是 6 个不同用例 |
| schema/生成类型、完整 Host/client 类型、scoped Ruff | **PASS** |
| 干净目录复建和机器路径扫描 | **PASS**；`.context/dsh-b0/clean-build-SqV8kJ`；三个 JS 字节相同 |
| 扩展七问原生浏览器 | **FAIL / 暂停重试**，不能用上面的测试数量抵消 |
| 远端 Actions / required checks / 新机器空缓存 | **NOT RUN / NOT CONFIGURED**；未推送或改分支保护 |

最终产物 SHA-256：`index.js=e16bfe25f7a1453d322bbfe5aac179df278bf69c466a6f072b6d27026e34dd70`；`tool.js=a6c44fc43883cb760a1931c611b28cd6d5958cc36a5739c3b66385e4d38f0740`；`client.js=5b8561998ae9a909ce968cf4022df2c179a7e37a1ecd7f4046b6efca3d0afa3d`。

本轮没有重跑旧 CRM/Mission 的完整测试或其真实 lifespan；新模块的隔离导入/不触碰旧数据入口测试在 151 项内。此前 Mission/匿名权限报告保留原时间与范围，不用历史测试数替代本轮结果。

## 6. 当前剩余门与关闭情况

- **D3：仍 PARTIAL。** 持久提交/实际 worker 故障子集已补，扩展原生旅程阻碍未清；不能勾选完整故障地图。
- **D4：本地物理资源子集已验证。** 默认资源配置、取消/超时、RSS/temp/spill、孤儿退出与清理有实际证据；完整容量、控制请求延迟/CPU 和 B1–B3 基线仍未跑。
- **其余 B0：OPEN。** 获批 Skill 整包 hash/引用漂移、compaction/旧记忆冲突小样未装配/未验证；V25 本轮仅策略/启动轮换单元与正常原生接线，完整当前 live 绕过矩阵未重跑；MCP 继续 `NOT ENABLED`。合成 BI/主题等原定未闭合项不因后端通过而勾选。
- **B1–B4、真实模型、外部投递和发布：未开始。** 没有新权限、个人凭据读取、收费模型调用、Git commit/push/PR/merge、部署或真实数据操作；验证器只使用本次自行生成的隔离运行能力。

前两轮通过各自本次监督器正常停止；第三轮监督器已失联，已逐个核验本次网关 82242、DSH 85247、API 84730 的命令与 cwd，再对这三个明确自建目标发送 TERM。最终 4315–4319 无监听；本次浏览器 tab 2/3/4 已关闭，共享原有 tab 保留。没有对旧 5173/8000 或无关进程发送停止指令。只清理本次测试生成的一次性 spill；状态库、manifest、合成 fixture、报告与失败证据保留。

沿用分支 `codex/architecture-warehouse-plan-closeout`，HEAD `de2d785f4e0c7abe7fcd8fbb39be7d8c5a0c9642`，本轮改动未提交；保留原有脏工作树。此报告不是整分支审查或独立模型复核。
