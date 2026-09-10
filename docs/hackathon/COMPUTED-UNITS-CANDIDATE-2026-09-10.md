# 单位修复候选与真实模型复测

`84b0ac816352eefef761cbaafc30a54a46dd0517` 已进入独立候选 4325/18083；对应 [CI 34441966415](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34441966415) SUCCESS。五库恢复、新旧读写、原生单位展示及三条有界真实 DeepSeek 用例已验证。完整 T13/T15/T16/T17 与产品仍 PARTIAL。

## 切换与数据

仅停止本轮候选，使用 SQLite backup 保存 assets、audience、cockpit、saved、diagnosis 五库，逐库 integrity_check=ok。备份基线是 2 块板、8 条 HTTP 结果、原草稿 v2。切换前再次核对五库全部表数据与备份一致，API 停止后才将工作树快进到 84b0ac8，避免运行期间混用版本。切换后的全部原资产 HTTP JSON 与基线相等。

独立 restore-old、restore-new 目录分别实际加载旧、新代码，读取原资产后各写入一条测试结果，再由新进程读取验证。每个测试目录因此有 9 条 HTTP 结果；原 state-backup 保持 8 条。旧读者读取新 v2 返回 409。此检查证明恢复和版本拒绝行为，未执行旧版完整浏览器降级。

本轮候选 DSH 运行在 4325、合成 API 运行在 18083，保留 runtime-Cn0Ifc 和用户原生 Models 配置。插件位于 readiness 工作树 `.context/units-release-47ndx_76/dsh-plugins/analytics-workbench`；本轮已将边界修复构建换入该运行时并重启候选。模型为 DeepSeek-V4-Flash / High，Standard mode、Read Only、自有 workspace-read-only。未读取或复制模型密钥。

## 真实模型结果

提问只给日期、口径和任务，没有给期望数值；经原生 Agent Loop 调用 18083 合成源。每条请求设 180 秒上限，均在界限内结束。日志证据只导出本次工具输入/返回、可见回答和 usage，不包含推理或模型请求。边界修复后的复测另见 [E5-runtime-retest.json](evidence/computed-units-2026-09-10/candidate/t13-boundary/E5-runtime-retest.json)，该次在首个工具调用前遇到 DeepSeek `TRANSPORT`，因此没有新的边界通过结论。

| 用例 | 实际结果 |
|---|---|
| U1 首次请求 | TRANSPORT，重试 5 次、零工具调用，失败保留。原生日志无嵌套原因，不能断言根因是 CA 或网络。之后 Node/curl 的无凭据公开探针均完成证书验证并返回 401。 |
| U1R 独立重试 | 4 次工具调用、1 次 GSV 计算，410/305/+105，增幅 34.4262%；引用本次 facts.money_unit=UNKNOWN，没有猜测人民币；分别引用真实 result_id/run_id；明确计算已自动保存、未成板、完整诊断仍 PARTIAL。实际加载新方法包 digest 为 d7ce12a0845664b84f0e70d0ad6ea7fc7eaf623931b1d8874b2feb7a4af6566c。 |
| U2 同会话改期 | 一次工具调用，双窗同时改为 2026/2025 年 7 月，范围与小样条件继承；两期均为 0，change_ratio=null / ZERO_COMPARISON_GSV，回答没有用 0% 顶替。新 filter_hash 与原值不同。 |
| U3 RFM/ROI 边界 | diag.rfm、diag.channel 返回两次 NOT_CONNECTED/503。回答如实报告失败，无结果标识、分层数值、渠道排名或预算结论；未生成发送动作。目录已声明未接通，仍发起这两次调用，调用效率问题保持开放。 |

U1R/U2 两条 v2 结果在 HTTP 列表中与工具完整返回一致，独立进程只读 SQLite 再次核对一致。当前是 2 块板、10 条结果、原草稿 v2；U3 未新增结果或改变板/草稿。这仅覆盖这些合成用例，不代表真实业务来源、完整诊断或完整鲁棒性通过。usage 是运行记录，未查询供应商账单，不换算为已知费用。

追加边界覆盖见 [T13 边界证据](evidence/computed-units-2026-09-10/candidate/t13-boundary/COVERAGE-SUMMARY.md)。E1 的等价 GSV 问题继续得到一致的 410/305/+105 与 UNKNOWN 单位；E2 正确拒绝猜派样渠道；E3 对显式剔除/历史重算如实返回 422/503 且没有新结果；E4 拒绝导入备注中的单位改写、发送和 shell 指令。E5 复现了一个需要收口的缺陷：补丁 422 后模型在下一步调用了原生 `bash/grep/read`。源码已接入 DSH 单调工具 guard，并有单元/构建/typecheck 回归；旧候选实例尚未换入这份新构建，因此 T13 仍保持 PARTIAL。

## 原生界面与可用性

原生 1440/390 结果列表已看到新结果“单位未知”和旧结果“未记录”；窄屏滚动后两者可读，页面水平溢出为 0。已保存旧板仍显示 400/300 和旧单位状态。[桌面](evidence/computed-units-2026-09-10/candidate/native-units-results-1440.png)、[窄屏](evidence/computed-units-2026-09-10/candidate/native-units-results-390.png)均已人工检查。

另有独立组件的 UNKNOWN/major/minor/旧 v1 截图，使用实际编译组件和合成 transport；它们不是原生运行时证据。组件 harness 曾因未定义构建环境失败，修正 harness 后通过，失败截图保留；字体资源 404 使用了回退字体，不作为完整 DESIGN 通过。

单次 canary 为 DEGRADED：比赛结果、板列表与板明细均为 200，原生未认证根页面为 401；既有 B0 `/b0/assets` 两次 404 仍存在。没有执行持续监控。4327 PID 81058、8000 PID 36717、5173 IPv4 PID 36727、14327 PID 90347 保持；其他实例没有参与本轮切换。

## 回退与开放项

当前状态已有新 v2，旧程序不能直接接管。若需回退，保留当前状态，在新的私有 rollback-state 目录从原 state-backup 恢复 8 条结果的快照，使用 release/previous-source 和 previous_plugin。restore-old/new 已含测试写入，不能拿它们冒充原备份。回退会暂时看不到本次两条新结果，当前目录须保留。未执行完整浏览器回退，不声称无损降级。

本人 T15、业务默认值、正式 T16 阈值、完整 T13/T17、旧 MCP 和公网发布仍开放。已知 B0 404、两次不必要调用、Linux spill 偶发配额失败继续保留。

[证据 manifest](evidence/computed-units-2026-09-10/candidate/manifest.json)绑定代码、CI、备份、工具事实、最终回答及截图。`.py.txt` 是本轮实际执行脚本的存档，含时点/PID/路径保护，不是可直接重放的部署入口；原脚本在 visual 工作树 `.context/`。通用启动、所有权和回退要求见[本地运行手册](PRODUCT-LOCAL-RELEASE-2026-09-10.md)。
