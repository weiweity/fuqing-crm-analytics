# T17 原生审批、权限与 preset 补验（2026-09-10）

**本轮局部用例 PASS，完整 T17 仍 PARTIAL。** 在固定上游的完整原生配置中，实际验证拒绝提权、仅批准一次、运行中切为只读后约束下一次文件调用、新会话默认权限隔离和重启恢复；另完成 Minimal 的插件 off/on 工具目录对照。

基线 `d2a5a6f0ecb204bfe315f7448ab7859192745110`，运行代码 `d482bd6`，固定 DSH `d347e703908d0406b7a7ef80e3a0e594d86b2215`。Node 24.19.0、Python 3.14.4。该基线的 [CI 34421652594](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34421652594) 已核验 SUCCESS，路径跳过项不算通过。业务源码和上游均未修改。

本轮 provider 是本地官方 mock 服务，14 次请求全部在 loopback 内，包含标题请求与工具返回后的续轮；**不计入 T13 真实模型评测**。所有工具执行、审批状态及会话日志来自真实 DSH；结论由原生结果和落盘证明，不采用 provider 的固定结束语作为判断。

| 用例 | 观察到的结果 |
|---|---|
| 拒绝提权 | Read Only 下首次 write 被沙箱拒绝；随后对同一文件、同一内容请求 Workspace Write。原生审批卡点击 Reject，工具返回用户拒绝，目标文件不存在 |
| 仅批准一次 | 另一次真实拒写后，点击 Allow once，原生 write 写出精确内容；会话权限仍 Read Only |
| 批准不延续 | 后续未申请提权的不同文件写入仍被拒绝，文件不存在 |
| 运行中收窄权限 | 会话开始时 Workspace Write，provider 在发出工具调用前等待；原生 Stop 按钮仍可见时切为 Read Only，再放出调用。原生日志先记录只读事件 seq 80，后记录 write 调用 seq 83；写入被拒绝 |
| 新会话默认隔离 | Settings 默认改为 Read Only，现有会话仍 Workspace Write；新建会话为 Read Only |
| 重启恢复 | 同一私有运行目录重启 DSH 后，原会话仍 Workspace Write，新会话仍 Read Only，Settings 默认仍 Read Only |
| Agent preset | 在新会话选择 Minimal，原生 `agent-preset/selected` 记录 minimal；重启后模式与历史仍在。会话创建 header 保留 standard，后续选择由事件覆盖，不能只读 header 判断最终 preset |
| 插件 off/on | Minimal 关闭插件时暴露 `bash`、`str_replace_editor`；开启时保留两者并增加四个 competition 工具。原生会话、只读权限在关闭插件后仍可用 |

![原生提权审批卡](evidence/t17-permissions-2026-09-10/approval-pending.png)

两次 `approval/asked` 与 `approval/decided` 的 ID 成对，结果分别为 rejected、allowed-once；提权重试的文件路径和内容与各自首次拒写相同。退出 DSH/API/provider 后，获准文件仍为 `T17_ALLOWED_ONCE\n`，其余三个目标文件均不存在。完整记录、截图和辅助脚本摘要见[原始证据](evidence/t17-permissions-2026-09-10/verification.json)。

## 判断边界与未完成项

固定上游 `packages/sandbox/sandbox-policy/README.md` 明确：模式变化作用于下一次受限调用；`packages/fs/fs-sandbox/README.md` 说明文件操作按调用解析权限。本轮据此设置“工具发出前”的屏障，不宣称中断已开始的系统调用，也不替代业务 actor/data-scope 撤权或真实数据/凭据可达边界的验收。

Minimal 的对照是实际工具目录与会话恢复证据，不是 PTC、Creator、自定义 preset 或所有工具的完整执行验收。系统目录选择器、长会话/压缩、完整视觉、完整 T13、本人 T15、正式 T16 及发布条件仍开放；[上一轮原生 Stop 的发布边界证据](PRODUCT-NATIVE-STOP-PERMISSIONS-2026-09-10.md)继续有效。

首次工作区 `:text-is` 选择器未命中内部 span，后续控件尚未出现；修正后才开始用例。运行中切换驱动第一次将 CLI 返回的字符串当 JSON 解析，发问前即失败；确认没有该请求后，将失败报告和释放标记另名保留，再运行修正版。第一次过宽 Reject 选择器也有歧义，缩到原生审批卡后才点击。没有把这些夹具/驱动失败记为通过。

本轮临时 4328/18084 和本地 provider 已退出；4325/18083 仍为 PID 23690/23661，4327 为 81058，8000/5173/14327 的原 PID 保持。用户真实 Models 配置没有读取或复制；新夹具只使用从零创建的虚拟凭据。

## 独立复现

沿[上一轮隔离初始化](PRODUCT-NATIVE-STOP-PERMISSIONS-2026-09-10.md#独立复现)的方法，创建新的 `.context/t17-native-permissions-*` 目录，写 `.context/t17-permissions-current.json`，不要覆盖已有证据目录。配置字段仍为 root/repo/upstream 的绝对路径及 4328/18084；虚拟凭据仍用 T17_FIXTURE_KEY。从本轮证据目录复制四个 `.txt` 辅助脚本到 `.context/` 并去掉后缀，末尾空行规范化前后的摘要均已保存。

启动 `t17-permissions-provider.mjs` 和 `t17-permissions-api.py`，使用指向 18084 的已验证插件产物；新增工作树则按固定锁重新构建。用 `cli.mjs start --plugin on --web-port 4328`、固定 upstream、私有 runtime、provider.patch.json 的绝对路径启动。私有 launch URL 只用于浏览器认证，不输出 token。运行 `t17-permissions-workspace.mjs` 准备工作区后，通过 UI 选择它。

在 Read Only 下依次发送 T17_ESC_REJECT、T17_ESC_ALLOW、T17_AFTER_ALLOW，每轮等原生结果；前两轮分别点击审批卡内的 Reject、Allow once。运行 `t17-permissions-switch.py` 驱动原生权限切换和工具发出前屏障。该脚本拒绝覆盖既有屏障文件，失败后先保留并判定实际请求状态，不盲目重跑。

随后将原会话切回 Workspace Write，在 Settings → General 把新会话默认改为 Read Only；检查原会话不变、新会话只读。在新会话选择 Minimal，发送 T17_PRESET_MINIMAL 消息并记录 provider 实收的工具名。仅重启拥有的 4328 运行时，再检查两个会话和 Settings；再以同目录 `--plugin off` 启动，发送 T17_PRESET_OFF 并确认原生两工具仍保留。最终只停止本轮拥有的实例，并在进程退出后核对文件、原生日志和监听端口。
