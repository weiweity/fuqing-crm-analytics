# T17 目录选择、preset 与手动压缩补验

本轮局部用例 PASS，完整 T17 仍 PARTIAL。系统目录选择器、五种 preset 的实际文件读取、插件 off/on 对照、既有会话重启恢复和原生 `/compact` 已取得浏览器及落盘证据。未改业务源码或固定上游。

基线 `84a4eb3dae7dbbf020f152a04da49971c87fa2bf`，运行代码 `9948de39e87d71dbfefc223aa020b696ed8068c8`，固定 DSH `d347e703908d0406b7a7ef80e3a0e594d86b2215`。该基线的 [CI 34426683769](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34426683769) 已核验 SUCCESS，路径跳过项不计通过。Node 24.19.0、Python 3.14.4，浏览器截图为 1280×720。

33 次模型请求尝试全部发往本机官方 mock 服务，其中一次标题请求因夹具路由错误返回 502，32 次正常响应；包含标题、工具后续轮和压缩摘要请求。原生工具与存储实际执行，结果以日志和文件判断，不以固定结束语判断。本轮不计 T13，也不评价真实模型摘要质量。

## 实际结果

| 路径 | 证据 |
|---|---|
| 系统目录选择 | 浏览器 Add workspace 打开 DSH 子进程持有的 macOS 目录选择器；在原生 Go to Folder 输入新夹具目录并点击选取。工作区由这次交互创建，没有调用之前的 workspace/create 准备脚本 |
| 目录选择取消 | 插件关闭时再次打开原生选择器并点 Cancel；退出后原生存储仍只有 1 个工作区、5 个会话 |
| Standard | 插件开启和关闭时，实际 `read` 均读到 `T17_EXTENDED_NATIVE_SEED` |
| Minimal | 两种状态下实际 `str_replace_editor` 的 view 均读到相同文件；关闭插件时目录正好是 bash、str_replace_editor |
| PTC | 两种状态下模型均只收到 `run_code`；实际通过生成的 SDK 执行 `tools.read`，返回文件行号和精确内容 |
| Creator | 两种状态下实际 read 成功；关闭插件仍保留原生 cordis 工具目录。未执行插件创作或任意代码实验 |
| 自定义 preset | 在 Settings → Agent presets 复制 Standard 为 `t17-standard-copy`；选择后实际读取。落盘 agent.cordis.yml 与内置 Standard 字节一致。off 重启和再次 on 重启后原会话继续执行成功 |
| 组合保留 | Standard、Minimal、Creator、自定义四组 on/off 工具差集均正好是 4 个 competition 工具。PTC 的外层目录保持 run_code，不据此推断所有 SDK 子工具已验 |
| 会话恢复 | 五个原会话分别恢复原 preset、历史和文件调用；已有消息的会话展示固定模式，不再提供空白会话的模式选择控件 |

所有文件调用均发生在新建的隔离工作区。用户 Models 配置没有读取或复制；仅从零写入虚拟 T17_FIXTURE_KEY 凭据。最后测试文件内容未变。

## 手动压缩与恢复

Standard 原会话先完成文件读取，再接收三段各 160 行的合成历史。浏览器输入 `/compact` 并按 Enter，实际执行原生命令，显示 `Compacted 12 history items (~10613 tokens)`。

同一压缩 ID 的原生日志顺序为 command/run 47 → compaction/start 48 → summary 49 → 带 `<compacted-summary>` 的替换 user/message 50 → end 51 → command/done 52。12 个被替换历史项约 10,613 tokens，包含较早的 320 行合成历史；较新的 160 行保留。完整原始日志仍保留历史，压缩作用于后续模型上下文。

压缩后再次 read 成功。停止 DSH、用同一目录关闭插件重启后，再次读取成功；provider 实际收到压缩摘要和保留的近期历史。最后再次开启插件，自定义原会话也能继续读文件。没有把“历史还显示在界面”误判为压缩未发生，也没有声称所有历史都被删除。

![原生压缩与后续执行](evidence/t17-extended-2026-09-10/compact-replay.png)

这验证手动压缩的控制流、持久化和恢复；自动上下文溢出、真实模型摘要质量未运行。五种 preset 的文件读取和组合保留不代表每个专用工具或任意自定义 preset 都已通过。

## 失败记录与范围

首次路由器误将无工具的会话标题请求当作 read 请求并返回 502；原生文件读取仍成功。保留原脚本和错误事件，修正后才继续。旧浏览器引用、Settings 的 aria-label、Duplicate 的文本选择器和过宽 dialog 快照各有失败，均按实际 DOM 修正，没有作为产品失败或通过证据。日志检查曾误读无 seq 的 session 头；第一次归档还把流式拼装片段重复计入历史行数，改为最终消息内容后断言通过。

早期 `has_checkpoint` 观察器会匹配压缩指令里提到的标签，不能单独证明恢复。修正为匹配实际 checkpoint 前言后，请求 22 与持久替换记录才用于证明重启后的摘要输入。

完整 DESIGN、业务 actor/data-scope 撤权和真实数据/凭据可达边界仍按各自验收条件判断。完整 T13、本人 T15、正式 T16、发布条件继续开放；[已有原生审批与权限证据](PRODUCT-NATIVE-APPROVAL-2026-09-10.md)继续有效。

临时 4328/18084 和本地 provider 已全部退出。4325/18083 仍为 73577/23661；4327、8000、5173、14327 保持原 PID。用户验收入口与模型配置未改。

## 独立复现

[证据目录](evidence/t17-extended-2026-09-10/)保存 provider、浏览器驱动、归档校验器、修正前脚本及截图；[verification.json](evidence/t17-extended-2026-09-10/verification.json)绑定文件摘要、工具请求、原生日志、工作区存储和退出检查。

1. 按[隔离初始化说明](PRODUCT-NATIVE-STOP-PERMISSIONS-2026-09-10.md#独立复现)创建新的 `.context/t17-native-extended-*`，不得覆盖旧目录。配置写 `.context/t17-extended-current.json`，字段 root/repo/upstream、web_port=4328、api_port=18084。seed.txt 内容为 `T17_EXTENDED_NATIVE_SEED\n`，仅创建虚拟凭据。
2. 复制归档脚本到工作树 `.context/` 并去掉 `.txt`。用固定上游构建指向 18084 的插件，保存独立产物。启动 provider；运行标准 `scripts/competition-synth-http.py`，显式设置新状态目录、18084 和允许来源 4328。
3. 用 dsh-dev 的 `--plugin on --plugin-path <产物> --runtime <新目录/runtime> --web-port 4328 --upstream <固定上游> --extra-patch <新目录/provider.patch.json> --detach` 启动。私有 launch URL 只用于认证，不输出。通过真实 Add workspace 选择新目录；macOS 自动化只控制实际 DSH 子进程持有的 osascript 选择器，不使用全局无目标按键。
4. 各建空白会话并选择 Standard、Minimal、PTC、Creator；分别发送 T17_EXT_STANDARD、T17_EXT_MINIMAL、T17_EXT_PTC、T17_EXT_CREATOR。通过设置复制 Standard，再选择自定义模式并发送 T17_EXT_CUSTOM。驱动的 `prompt` 子命令负责填入原生输入框并等待结束。
5. 回到 Standard 会话发三次 T17_EXT_HISTORY，输入 `/compact` 按 Enter，随后发 T17_EXT_REPLAY。检查实际 compaction 事件、原生工具结果和后续模型上下文。
6. 只停止拥有的 DSH，再用同一目录 `--plugin off` 启动。认证后逐个打开原会话，发送对应 marker 加 off；Standard 用 T17_EXT_OFF。测试原生目录取消，再停止并开启插件，确认自定义原会话继续执行。
7. 只停止本轮拥有的 DSH/API/provider，按监听端口与 PID 双重校验。退出后核对 seed、preset 文件、工作区存储和压缩日志。归档脚本中的固定请求 ID、会话数量及 PID 是本次结果断言，新复现应绑定自己的实际记录，不能为得到相同数字伪造日志。
