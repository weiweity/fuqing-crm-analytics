# 本地候选已切换到 d482bd6

4325 DSH / 18083 合成 API 已加载 `d482bd603c04f608c5e66f33291cfb0aee35bac7`，包含原生主题同步、实际 AntD、状态恢复及探针管道归属修复。[CI 34418047588](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34418047588) 全部通过：Linux 后端 2322 passed / 79 skipped，B0 480 passed / 20 warnings；本地后端 2324 passed / 77 skipped，两处差异为平台条件。历史失败未删除。#115 保持 draft，未合入 main。

切换时仅停止本轮 4325/18083。五个 SQLite 库通过 backup 接口保存到 `.context/visual-release-backup-hxgrs_oq`，共 258048 字节，并恢复到另一个私有目录。完整性检查、2 块板、3 条结果及草稿响应均一致。当前状态保留原位；原 DSH runtime、Models 配置和会话也保留。构建依赖在本候选独立目录离线按锁安装，未修改此前共享依赖目标。

浏览器刷新后通过 footer 再开同一 BAR 看板，仍为本期 400、对比期 300、差额 100、同比 33.33%。模型选择仍是 DeepSeek-V4-Flash / High，原会话可见。原生与业务 Light 同步；浏览器媒体模拟 Dark 时两者同步，390 视口弹层宽度与 scrollWidth 均为 342；已恢复媒体模拟和桌面视口。Logo 200。未调用新模型或改用户主题设置。

`/canary --quick` 结果为 **DEGRADED**：比赛 results/boards/板明细均为 200，取消回执 CANCELLED，重复计算请求 409；控制台仍有 4 条既有 B0 404（assets 两次、dashboards、analyses）。单次页面 loadEventEnd 134ms，没有同配置数值基线，不作性能结论，也不称连续监控。截图可读，但技术说明仍过密，完整 DESIGN 与原生 Stop/权限执行验收继续开放。

[绑定、备份和浏览器证据](evidence/visual-readiness-2026-09-10/candidate-switch.json)包含原始失败限制与 JS 哈希。[1440 浅色截图](evidence/visual-readiness-2026-09-10/screenshots/candidate-light-1440.png)、[390 深色截图](evidence/visual-readiness-2026-09-10/screenshots/candidate-dark-390.png)均已查看。

回退时先保留当前状态，仅停本轮服务；把五库备份恢复到新目录，再用对应旧代码/插件读验。不得覆盖活库、复制模型配置或假设旧版可继续写新状态；旧版写入回退仍未验证。用户可继续在 [4325](http://127.0.0.1:4325/) 按[三角色清单](PRODUCT-UAT-2026-09-10.md)验收。T15 本人签字、正式 T16、完整 T17、业务默认值和完整诊断链仍未关闭。
