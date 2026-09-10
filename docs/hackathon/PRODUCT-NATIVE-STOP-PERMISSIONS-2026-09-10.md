# T17 原生停止与文件权限补验（2026-09-10）

本轮用完整原生 DSH 配置和本地确定性 provider，补齐 **停止后不发布、同会话恢复、只读读取/拒写、工作区写入、新建与切回会话** 的实际证据。这些局部用例 PASS，完整 T17 仍 PARTIAL。本轮没有调用外部模型，不能计入 T13。

源码绑定 `6b32ce94937bf7cc82dbfc72ee93fa6a27ec2c00`（代码为 `d482bd6`），固定上游 `d347e703908d0406b7a7ef80e3a0e594d86b2215`，Node 24.19.0、Python 3.14.4。该提交的 [CI 34419690573](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34419690573) 已核验 SUCCESS。业务源码及固定上游均未修改；临时插件编译目标为 18084，编译产物和夹具源码摘要见[原始证据](evidence/t17-native-2026-09-10/verification.json)。

| 用例 | 实际动作与判断依据 |
|---|---|
| 只读读取 | 原生权限设为 Read Only，真实 `read` 返回 `T17_READ_ONLY_SEED`；初始文件未改变 |
| 只读拒写 | 真实 `write` 返回 sandbox read-only 拒绝；独立检查 `denied.txt` 不存在 |
| 原生停止 | 发出 T17_STOP，真实计算到达发布前屏障后，浏览器点击原生 `Stop generating`；服务收到相同 Host session/request 的 CANCELLED，释放屏障后 save 返回 CANCELLED |
| 停止后的落盘 | 新只读 SQLite 连接中没有被取消请求的结果，只有取消标记；不是通过 provider 的总结文本判断 |
| 同会话恢复 | T17_RECOVER 使用新 request_id，真实工具计算并保存 410 / 305；取消请求和恢复请求属于同一原生会话 |
| 工作区可写 | 原生权限切为 Workspace Write，真实 `write` 创建 `written.txt`，文件 29 字节、内容及 SHA-256 匹配 |
| 刷新与切换 | 刷新后新建空白原生会话，再切回旧会话；Stop 错误、恢复和写入记录仍在，权限显示 Workspace Write |
| 进程退出 | 关闭本轮 DSH/API/provider 后重新检查小 SQLite 和文件，结果仍成立；4328/18084 无监听 |

![原生停止、恢复与工作区写入](evidence/t17-native-2026-09-10/native-stop-recover-write.png)

截图已实际查看，原生 Stop 当前以红色 `Error: Diagnosis aborted` 显示，后续会话可继续。刷新后拒写工具卡折叠，因此 `browser-switched-back.readDenied=false` 仅描述可见 DOM；原生持久日志中的拒绝结果仍存在，已归档。

## 失败与边界

首次读取夹具用了旧工具名 `str_replace_editor`，没有执行工具，不算通过。第一次修正又将请求计数起点设为 100，触发夹具的 40 次限制并得到本地 HTTP 409；该失败会话保留。修正为当前真实 `read/write` 合同和计数后，才运行上述通过用例。初次 CLI 相对路径参数及 textarea 选择器也曾被拒绝/超时，均未被当作产品失败或通过。

发布前屏障加在小型 SQL 计算完成后：本次证明停止可以阻止结果发布，**不证明物理 SQL 被中断**。工作区通过原生 HTTP RPC 准备，操作系统目录选择器未验。提权审批、运行中撤权、preset 持久化完整矩阵及完整视觉仍开放。用户真实 DeepSeek 配置、4325 会话与资产没有复制到夹具。

4328 DSH、18084 API 和本地 provider 已关闭。验收候选继续为 [4325](http://127.0.0.1:4325/) / 18083（PID 23690 / 23661）；4327、8000、5173、14327 原 PID 保持。完整产品、本人 T15、正式 T16、业务默认值及完整诊断链仍未标通过。

## 独立复现

本次四个辅助脚本归档在 [证据目录](evidence/t17-native-2026-09-10/)，后缀 `.txt` 表示证据副本；仅规范化末尾空行，运行时与归档摘要分别保留。复现时复制到工作树 `.context/` 并去掉 `.txt`；不得直接在已结束的运行目录重跑 Stop，它会主动拒绝覆盖旧屏障证据。

1. 在 `6b32ce9` 的隔离工作树确认 4328/18084 空闲，使用已有固定上游和上述 Node/Python。在 `.context/` 下创建新的 `t17-native-*` 临时目录及 `runtime/harness`、`runtime/workspace`、`state`、`source`。
2. 写入 `.context/t17-native-current.json`：`root` 为新临时目录绝对路径，`repo` 为工作树绝对路径，`upstream` 为固定上游绝对路径，`web_port=4328`、`api_port=18084`。写入 seed.txt 的精确内容 `T17_READ_ONLY_SEED\n`。新建 mode 0600 的 `runtime/harness/.credentials.yaml`，仅含夹具引用 `version: 1\nrefs:\n  T17_FIXTURE_KEY: t17-local-fixture-only\n`，不要复制用户凭据。
3. 在工作树用 Node 启动 `.context/t17-native-provider.mjs`，用指定 Python 及绝对 PYTHONPATH 启动 `.context/t17-native-api.py`。设置 `COMPETITION_HTTP_BASE=http://127.0.0.1:18084` 和测试 token `COMPETITION_HTTP_TOKEN=b0-competition-synth-token-32chars`，调用 `dsh-plugins/analytics-workbench/build.mjs <固定上游绝对路径>`。
4. 仍带这两个测试环境变量，调用 `scripts/dsh-dev/cli.mjs start --plugin on --web-port 4328 --upstream <绝对路径> --runtime <新目录/runtime 的绝对路径> --extra-patch <新目录/provider.patch.json 的绝对路径> --detach`。该 patch 只替换本地 provider，保留原生工具/权限配置。
5. 用私有 launch URL 在浏览器认证，但不要输出 URL/token。运行 `.context/t17-native-workspace.mjs`，刷新后通过 UI 选择工作区。把权限设为 Read Only，分别发送包含 `T17_READ`、`T17_DENY` 的消息并等每轮结束；查实际 tool/result 和文件。运行 `.context/t17-native-stop.py` 会在同一浏览器执行发问、等待屏障、点原生停止、核对回执及释放屏障。
6. 同会话发送 `T17_RECOVER`；切 Workspace Write 后发送 `T17_WRITE`。用新只读 SQLite 连接检查 `state/diagnosis/diagnosis_results.sqlite3`，只能有 `t17-recover-r1` 的结果和 `t17-stop-r1` 取消标记；再核对 seed/denied/written 文件及刷新切换。
7. 通过该工作树的 `cli.mjs stop` 仅停拥有的 DSH；按 provider-ready/API_READY PID 与监听端口双重核对后停止本轮 provider/API。最后重新检查落盘与进程退出。保留失败记录，不将本地 provider 计作真实模型评测。
