# 驾驶舱首屏与断连恢复

本增量基于 `8475407`，在独立 `competition-visual-readiness` 修改和验证。4325/18083 继续运行 `d482bd6` 与用户原有 DeepSeek 配置；本记录不表示已切换该候选。源码摘要、构建摘要和检查结果见 [verification.json](evidence/visual-density-2026-09-10/verification.json)。

## 实际修复

会话和连接说明改为键盘可展开的详情，合成数据标记继续常显。B0 的状态、重新读取按钮只出现在对应页面；认可成板保留自身请求错误。保存、撤销和放弃预览集中到编辑页面，缩小状态说明的占用；板块标识、布局和请求标识可展开查看。默认入口、业务待确认枚举、草稿、版本及权限合同未改变。

断连负测另发现：`fetch` 拒绝后，初始化 Promise 没有进入错误状态，只剩空列表和禁用成板按钮。HTTP transport 现在将连接失败转换为明确错误，非合同 HTTP 错误也有兜底；已存看板的列表/明细读取失败会显示。写入没有自动重试，原幂等键和版本头保留；断连不能据此宣称保存未发生。`client-transport` 是客户端固定标识，连接异常映射的 503 不是服务端实际回执。

## 浏览器与回归

测试仅使用本轮 4328/18084、小型合成源与独立 SQLite。通过正式 HTTP 算得 GSV 410/305；浏览器选择结果成板，TABLE 改 BAR、保存、同页关闭重开；再停止本轮 API 制造真实拒绝连接，修复后展示错误，恢复 API 后仍是 1 块板、版本 2、BAR 410/305。没有模型调用或真实数据查询。

| 检查 | 结果与边界 |
|---|---|
| 390 / 1024 / 1440 | dialog 的 clientWidth 与 scrollWidth 分别为 342 / 976 / 1100，无横向溢出；390 的板块顶端为 594px，首屏可见两条柱图及数值 |
| 合成数据、空结果 | 合成边界常显；空结果不能成板；业务默认值仍显示待确认 |
| 键盘 | Enter 展开/折叠说明；Shift+Tab 从关闭按钮回到弹层末控件，Tab 返回关闭按钮 |
| System 主题 | CDP 模拟 prefers-color-scheme 深浅切换时，原生和业务模式均同步；不是实体设备操作系统设置验收 |
| 断连 / 恢复 | 错误可见、B0 错误没有覆盖比赛错误；恢复后读回原板，无新增板 |
| 编译后定向 DOM | 32 passed；含可展开详情、B0 与比赛错误隔离、连接拒绝、看板列表/明细失败 |
| transport 回归 | 11 passed；包含不自动重发未知结果的写入及版本/幂等头保留 |
| 完整 B0 pipeline | 480 Python passed / 20 warnings；Node 分阶段 225 / 58 / 70 / 58 passed，严格类型及干净构建 PASS。最后 58 为干净构建后的重复验证，不合并成独立用例总数 |

本轮保留 Python pytest 标记及 React act 告警；无新依赖、上游修改或业务库迁移。正常 pre-push 与远端 CI 是后续独立记录，不能用此处本地结果代替。

## 截图与失败记录

以下截图均实际查看：[390 浅色](evidence/visual-density-2026-09-10/screenshots/board-light-390.png)、[390 深色](evidence/visual-density-2026-09-10/screenshots/board-dark-390.png)、[1024 深色](evidence/visual-density-2026-09-10/screenshots/board-dark-1024.png)、[1440 深色](evidence/visual-density-2026-09-10/screenshots/board-dark-1440.png)、[1440 浅色](evidence/visual-density-2026-09-10/screenshots/board-light-1440.png)、[空结果](evidence/visual-density-2026-09-10/screenshots/empty-390.png)。这些图在视觉补丁、断连修复前拍摄；最终构建另有[断连提示](evidence/visual-density-2026-09-10/screenshots/disconnected-fixed-390.png)和[恢复原板](evidence/visual-density-2026-09-10/screenshots/restored-fixed-390.png)。

[断连失败图](evidence/visual-density-2026-09-10/screenshots/disconnected-390.png)显示修复前未提示错误的状态。首轮浏览器初始化曾被原生测试公告/配置向导拦住，按原生 Continue / Configure later 完成后重试；没有注入凭据。指标采集脚本曾将 CLI 的非 JSON 字符串误作 JSON，改为返回对象后重跑，通过记录在 [browser-check.json](evidence/visual-density-2026-09-10/browser-check.json)。

## 复现与开放项

使用已有固定 Node 24、Python 3.14 和 DSH `d347e703`。完整检查仍为 `B0_BUILD_UPSTREAM=/absolute/pinned/upstream node scripts/dsh-b0/pipeline.mjs --check --python /absolute/b0-python3.14`。浏览器需单独以合成 HTTP 的 18084 地址构建插件，复制至隔离插件目录后，通过 `scripts/dsh-dev/cli.mjs start --plugin on --plugin-path /absolute/isolated/plugin --runtime /absolute/isolated/runtime --web-port 4328 --upstream /absolute/pinned/upstream --detach` 启动；API 使用 `scripts/competition-synth-http.py`，显式指定独立状态路径和 4328 CORS origin。不得复用用户端口或真实大库。

本轮临时 DSH/API 均已停止，4325/18083 PID 23690/23661 保留。完整 T17、原生目录选择器/其他 preset/长会话、图表与局部编辑的其余技术文案、业务默认值/UNKNOWN、旧 MCP、完整 T13、本人 T15、正式 T16 和正式发布继续开放。
