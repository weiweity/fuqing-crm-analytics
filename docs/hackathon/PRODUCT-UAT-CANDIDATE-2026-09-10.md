# 看板候选切换与真实等价问法评测

**最新状态**：方法修正 `6202e89` 的 CI 34437915131 SUCCESS，已进入同一 4325；A3/B2 两次真实复测正确区分结果与运行标识。原有资产保持，现有 2 块板、8 条计算结果。完整 T13 仍 PARTIAL，下文保留各阶段失败及切换时点。

**单位判断更正**：重新核对 A3/B2 各自原生能力目录，实际都没有 currency/amount_unit；“目录标注 CNY/minor”是模型无来源推断，此前仅称措辞不一致不准确。[原生复核证据](evidence/computed-units-2026-09-10/native-unit-source-audit.json)保留绑定哈希；原回答和旧报告仍留存。[本地修复](COMPUTED-UNITS-DELIVERY-2026-09-10.md)已接通明确单位状态，但尚未切换当前候选或复测模型。

独立候选 4325 已切换看板直达、多板选择和条件证据补丁。插件源码 `2dae78d4da6741162732401ea3b0827a7dce073c`，验证提交 `cde6a81ef332414fda815076576f7fb795b37082` 的 [CI 34435439275](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34435439275) SUCCESS。先前证据脚本 Ruff 失败已关闭；上一次 Linux spill 的 RESOURCE_EXCEEDED 本次未再出现，新增诊断信息没有改变配额，根因仍未确定，不能写成已修复。

## 当前运行与切换验证

- 4325 DSH 从 PID 73577 切换至 10843，18083 API 一直为 PID 23661。仍使用原 runtime-Cn0Ifc，DeepSeek-V4-Flash / High、Read Only 及原生会话保留，未读取或复制模型密钥。
- 编译产物使用服务根地址 `COMPETITION_HTTP_BASE=http://127.0.0.1:18083`；客户端和工具自己追加 API 路径。此前错误准备包从未启动。新插件为 `.context/uat-navigation-release-1xkkouyu/plugin-origin`，原插件保留为 `previous-plugin`。
- 实际浏览器 `/plugins/` 合并响应包含完整插件代码（去掉末尾 sourceMappingURL）；构建文件 SHA-256 为 `5d4ba5535dd6882c52a1942a02036b73d1b8c220316c123d133a6f7a3787e3a2`。未认证根页面仍为 401。
- 更新后默认面板为 competition-board，dialog 保持打开，选择器列出原有 2 块板；切换前后的 2 块板、3 条结果及所有板明细 HTTP JSON 完全一致。这是模型复测前的状态，后续复测新增 3 条计算结果，现为 6 条结果，仍是 2 块板。
- 1440/390 的稳定截图已查看。第一张桌面截图过早拍到下拉关闭动画，保留为取证失败，采用重新等待关闭后的截图。技术枚举、原始查询名和长日期仍影响阅读，完整 DESIGN 未通过。
- 快速 canary 为 DEGRADED：比赛资产读取成功，现有 `/b0/assets` 两次 404 仍存在；没有把这些请求计为比赛读取失败，也没有声称完成连续监控。

见[切换绑定](evidence/uat-candidate-2026-09-10/candidate-switch.json)、[桌面](evidence/uat-candidate-2026-09-10/candidate-1440-settled.png)、[窄屏](evidence/uat-candidate-2026-09-10/candidate-390-settled.png)。本次不迁移状态，没有新增完整备份；历史五库恢复只是对应时点的证据。旧插件已保留，尚未实际执行这次插件回退。

## 真实模型评测

使用用户配置的 DSH DeepSeek-V4-Flash / High，经原生会话与工具访问 18083 合成源。评测问题只给日期与条件，没有提供期望数值。初次 A 在五次重试后报 TRANSPORT，未计算任何结果，失败保留。公开无凭据探测中，Node 使用系统公共 CA 时返回 401，不带该 CA 时出现 issuer certificate 错误；原生日志没有保留嵌套原因，因此该次失败是否由证书导致只能推断。切换时显式传入公共 CA，后续 A2/B 均恢复真实调用。

| 检查 | A2 | B |
|---|---|---|
| 问法 | 8 月整月 GSV 同比 | 相同日期的交易净额增减，指定 GSV |
| 原生工具调用 | 5 次，含 2 次实际计算 | 4 次，含 1 次实际计算 |
| 数值 | 410 / 305，+105，+34.43% | 相同 |
| 条件与证据 | 全渠道、保留小样、上海时区；两期窗口和 digest 对应 | 相同 GSV evidence/data/filter digest |
| 合成与未完成边界 | 明确合成、UNKNOWN、完整诊断仍 PARTIAL | 同左 |
| 来源标识 | FAIL：把 result_id 与 run_id 合并为同一值 | 同样 FAIL |

后端实际返回不同的 `result_diag_…` 与 `run_diag_…`，最终回答却均写 `result_id/run_id=result_diag_…`。A2 还把共享计算路径的两次返回称为独立复核。数值与条件等价检查通过，来源引用准确性没有通过，因此本轮 T13 仍为 PARTIAL。工具事实、最终回答、原生日志哈希及持久化检查见[评测证据](evidence/t13-equivalence-2026-09-10/verification.json)。只保存本次会话的工具输入/结果及最终回答，没有打包模型请求、推理内容或其他用户会话。

本次方法修正明确区分两个标识、禁止补前缀推导，并要求只有不同数据源/方法证据才能称独立复核；同步重新生成实际运行包和锁。完整 B0 pipeline 已通过。**修正尚未进入 4325，也尚未用真实模型复测，不标记问题已关闭。** 两次成功评测的缓存/非缓存输入、输出计数分别记录；未查询 provider 账单，不把 token 数换算为已知费用。

用户本人 T15、正式 T16、完整 T13/T17、业务默认值与 UNKNOWN、旧 MCP/截断以及完整发布与回退门禁继续开放。4327/8000/5173 和 14327 未动；仅本轮候选 4325/18083 保持供验收。


## 方法修正后的实际复测

`6202e89c9a998fc868758fe993da5b163d146e38` 的 [CI 34437915131](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34437915131) SUCCESS 后，仅重启本轮 4325 DSH，PID 28243；18083 API 仍是 PID 23661。新插件为 `.context/t13-method-release-hws0ksxq/plugin`，此前可用插件保留为同目录 `previous-plugin`，仍未执行这次回退。相同 runtime、模型选择和全部 2 块板/6 条结果在切换前后保持，随后 A3/B2 新增两条计算结果，现为 8 条。见[切换证据](evidence/t13-citation-2026-09-10/candidate-switch.json)。

两次均从新原生会话开始，使用原问题条件，未在问题中提供正确数值或标识。每次各 4 个工具调用、1 次实际计算；工具读取的新方法包 digest 均为 `ae3b0f92ac34a11c161b246648ca1c3421cce02c208d2704f708715f72cc0713`，证据规则 digest 为 `f0d2c54797dff5ac9bf6464bcf9f1ebdda06bf18d05339bf6a8cfcc981f1d345`。因此确认实际运行了修正的方法，而非仅修改源文档。

A3 选择 diag.yoy，B2 选择 diag.gsv，两者都返回完整双期事实 410/305/+105/+34.43%，销售/历史范围、日期、时区和小样条件一致，data_digest/filter_hash 一致。两者 capability_id 不同，evidence_digest 可以不同，各自与持久化结果匹配；不要求模型必须调用同一个能力。最终回答都分别给出真实的 result_diag_… 与 run_diag_…，也没有再把同源返回称为独立复核。

[复测及原始工具证据](evidence/t13-citation-2026-09-10/verification.json)关闭的是这两条用例中的标识混用。完整 T13 不因此通过：A3/B2 对金额单位的表达仍不一致；B2 将比例合同称为 B0，且“未写入任何文件”没有解释工具已自动持久化分析。见[剩余表述问题](evidence/t13-citation-2026-09-10/remaining-findings.json)。真实问题保留，不通过删掉失败回答或只保留数字检查来标整体成功。

本轮亦核对旧 MCP 当前源码：截断返回 isError=true/FAILED，大消息 JSON 不被字节切坏，两项针对性回归通过；stdio 仍串行，CLI 同步最长 300 秒且先捕获全部输出，分页和运行中取消仍开放。只运行 mocked CLI/stdout 测试，未启动旧 MCP 或真实业务查询。见[核对记录](evidence/t13-citation-2026-09-10/legacy-mcp-audit.json)。
