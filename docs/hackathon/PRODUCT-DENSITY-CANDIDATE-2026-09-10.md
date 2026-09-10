# 4325 界面候选已更新

`9948de39e87d71dbfefc223aa020b696ed8068c8` 已推送到 #115，[CI 34425535023](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34425535023) SUCCESS。#115 继续为 draft，未合并或发布正式版本。此前[首屏与断连验证](PRODUCT-VISUAL-DENSITY-2026-09-10.md)中的“尚未切换”是切换前状态；当前以本记录为准。

仅重启本轮 4325 DSH，现为 PID 73577；18083 API 始终为 PID 23661。原 runtime、模型配置和会话保留。浏览器确认 DeepSeek-V4-Flash / High、原会话、2 块板和 3 条结果仍在，所有板明细 HTTP 响应与切换前相同。原 BAR 看板仍为本期 400、对比 300、变动额 100、变动比例 33.33%。本次没有模型调用。

新插件位于候选工作树 `.context/visual-density-release-z9u8cg_q/plugin`；旧插件留在同目录 `previous-plugin`，均绑定原有依赖。没有修改 API、状态库或 Schema；没有新增数据备份，此前五库备份/恢复仍是历史快照。回退只准备了旧插件与启动参数，未实际执行，不能据此承诺旧代码写回新状态的兼容性。

原 DSH 合并 46 个模块响应，不能与单一插件文件直接比较 SHA。首次整包比较失败，单模块无 revision 的探测返回 404；随后从浏览器实际加载的合并响应中核对插件代码：排除构建文件末尾 sourceMappingURL 后，全部代码逐字出现在响应中。完整构建文件 SHA 为 `2e10270eb957dee97d3fe7743202a4f6178da8b30b74f6e1589527707ba7949e`。这两项取证失败已保留。

切换记录及绑定见 [candidate-switch.json](evidence/visual-density-2026-09-10/candidate-switch.json)；[1440 截图](evidence/visual-density-2026-09-10/screenshots/candidate-1440.png)和[390 截图](evidence/visual-density-2026-09-10/screenshots/candidate-390.png)均已查看，浏览器已恢复桌面尺寸。新界面和只读资产检查通过；既有 B0 404 仍在，整体快速 canary 继续 DEGRADED，不代表连续监控或完整 T17。

用户可继续在 [4325](http://127.0.0.1:4325/) 按[三角色清单](PRODUCT-UAT-2026-09-10.md)验收。用户本人 T15、正式 T16、完整 T13/T17、业务口径和旧 MCP 开放项仍在。4327/8000/5173 未动，临时 4328/18084 已关闭。
