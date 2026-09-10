# 看板入口、切换与独立流程预演

已修复三个直接影响验收的问题：配置比赛 HTTP 后「我的驾驶舱」仍先打开未接线 B0；已保存多块板时只能读取第一块；保存后的板缺少销售范围和完整条件证据。现在直接进入诊断看板，可选择服务端列出的已保存板，重开保留当前选择，板内常显销售范围与小样条件，完整日期和证据可展开。

基线 `dea8332` 的 [CI 34428570582](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34428570582) 已成功。本次源文件与浏览器构建以 [verification.json](evidence/uat-navigation-2026-09-10/verification.json) 的 SHA-256 绑定；本记录写入时尚未切换 4325。用户候选仍运行 `9948de3`，DeepSeek 配置原位保留。

## 实际验证

全新隔离状态，DSH 4328、合成 API 18084、确定性本地 provider 63359。浏览器从原生聊天发出两次工具调用，工具实际计算合成快照，没有向页面注入结果。5 次本地 provider 请求包含 2 次工具发出、2 次带完整工具结果的返回、1 次会话标题请求；不是付费模型或 T13。

| 路径 | 实际结果 |
|---|---|
| 全渠道 GSV | 2026-08 与 2025-08，410 / 305，差额 105；全部销售范围 |
| 零售 GSV | 同期 400 / 300，差额 100；CH_RETAIL |
| 批量成板 | 浏览器勾选两个 COMPLETE 结果，显式选「批量分板」，生成两块独立板；dialog 保持 |
| 切换与证据 | 两块板分别重读，数值、渠道与持久化 digest 对应；完整对比期、历史范围与 UNKNOWN 可展开 |
| 布局与重开 | 全渠道板经键盘减宽和右移，v1→v2→v3；最终 x1/y0/w5/h4，刷新后同一板和布局保持 |
| 编辑保护 | 预览未保存时选择器禁用；组件负测中读取拒绝保留原板，已撤权的选择偏好不绕过当前列表 |
| 运营草稿 | 固定合成队列去重 6 人；首次建草稿 v1、修改文案为 v2，刷新后 ID/版本/文案保持，自动发送禁用 |
| 脱离会话 | 无活动会话仍可读取已存板；经营判断需本人验收 |
| 窄屏与键盘 | 1440/1024/390 的选择器弹层位于 dialog 内，键盘选择零售板成功，dialog 无横向溢出；截图已查看 |

服务退出后用新只读 SQLite 连接再次核对：2 条计算结果、2 块板、全渠道板 3 个版本、草稿 2 个版本仍在，板与计算结果 digest 完全匹配。临时 4328/18084/provider 均已关闭；4325/18083、4327/8000/5173 未改动。

## 检查及失败证据

重新验证 `18dfc58` 的 [CI 34433743967](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34433743967) 中，B0 再次 SUCCESS，后端在 `test_real_duckdb_external_sort_spill_and_quota[64]` 遇到 `RESOURCE_EXCEEDED`，未到后续 Ruff 步骤。原始日志未给出触发限制的资源指标。本机该组 3 项通过，另 24 次相同合成排序全部成功，临时文件峰值 47.4375–59.6875 MiB；这不能代替 Linux 失败归因。现仅在失败分支补持久化 worker 记录和有界 probe 回执，保留原配额、成功断言和负测，等待新远端证据。见[诊断记录](evidence/uat-navigation-2026-09-10/spill-ci-diagnostics.json)。

切换前还发现准备包的 `COMPETITION_HTTP_BASE` 误含 API 路径；实际共享 HTTP 选项在该配置下返回 404，改为服务根地址后返回 200 和原有 2 块板。已重新构建独立插件，错误准备包保留且从未启用；4325 仍是原版本。

提交 `2dae78d` 的 [CI 34432529663](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34432529663) 中，后端 2322 passed / 79 skipped，B0 SUCCESS；整体失败来自本次新增证据 Python 的 40 项 Ruff 格式问题。后续修正四个现行辅助脚本的格式，展开多模块 import 后 AST 等价；历史失败草稿改存 `.py.txt`，字节与失败提交一致。打包器同步保留该文本后缀。原始 CI 输出与[修正核验](evidence/uat-navigation-2026-09-10/ci-format-fix.json)均保留，远端重新验证仍待完成，4325 未切换。

最终完整 B0 pipeline 通过：离线合同、480 项 Python、Node、编译后 DOM、严格类型检查和干净重建。原始 [pipeline 日志](evidence/uat-navigation-2026-09-10/uat-navigation-final-pipeline.log) 保留每组实际数量，不用 45 项局部测试代替全套。提交前完成[人工范围审查](evidence/uat-navigation-2026-09-10/review.json)。

修复前入口回归失败，以及首轮新测试被既有在途状态污染的失败均保留。测试使用独立编译模块隔离状态后，最终全套通过。浏览器初稿错误选择器、只支持 headed 的 focus 命令、隐藏下拉项及过快键盘取证导致的失败也保留；最终脚本从刷新后的确定状态开始，检查真实 combobox 展开和激活项后操作。

浏览器工具的 CDP allowlist 拒绝 `Input.dispatchMouseEvent`，本轮没有绕过，因此真实鼠标拖动/缩放仍为 NOT_RUN。键盘布局保存是独立通过项。截图显示既有长 result ID 标题与技术枚举仍影响阅读，完整 DESIGN 保持 PARTIAL。

## 复现与开放项

运行环境固定 DSH `d347e703908d0406b7a7ef80e3a0e594d86b2215`、Node 24、已有 Python 3.14。只使用隔离合成状态和本地 dummy provider；不得复制用户 Models 凭据。原始 provider、工作区、浏览器、编辑、视觉与打包脚本存于[证据目录](evidence/uat-navigation-2026-09-10/)，辅助脚本从 `.context/uat-navigation-current.json` 读取独立目录和端口。默认完整检查使用 `node scripts/dsh-b0/pipeline.mjs --check --python /absolute/b0-python`，构建前移除 `COMPETITION_HTTP_*` 环境变量；浏览器插件则显式编入本轮 18084 并复制为独立产物。

本轮预演不是完整 T15：人群来自固定队列，尚未由本次 GSV 自动推导；完整多步诊断、模型编辑、真实鼠标拖动与本人签字仍缺。完整 T13/T17、业务默认值/UNKNOWN、旧 MCP/截断和正式 T16 继续开放，未做真实数据、公网部署或营销发送。
