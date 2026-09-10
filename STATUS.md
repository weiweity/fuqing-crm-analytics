# 项目状态 (Project Status)

> 当前短表；编年与旧运维事项见 [STATUS-HISTORY.md](docs/history/STATUS-HISTORY.md)。

## 当前快照（2026-09-10）

| 项 | 状态 |
|---|---|
| VERSION / main | `0.7.0.0` / `788b5b1`（#114）；#112 比赛集成及 #114 七项修复已合并 |
| 当前候选 | `codex/competition-product-readiness`，#115 draft；源码 `d482bd6` 已推送并切换 4325/18083；[切换证据](docs/hackathon/PRODUCT-CANDIDATE-SWITCH-2026-09-10.md) |
| 视觉增量 | 原生浅/深色同步、实际 AntD 与窄屏修复已进入候选；完整 T17/视觉仍 PARTIAL |
| main CI | [34386758906](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34386758906) SUCCESS，绑定 `788b5b1`；不代表本轮未提交修改通过 CI |
| 本轮修复 | 图表类型经预览/保存落盘，刷新重开保持；普通原生会话不再误报 B0 中断；原生比赛工具注册、条件入参及显式 CA 配置已补齐 |
| 验证 | `d482bd6` [CI 34418047588 SUCCESS](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34418047588)：Linux 后端 2322 passed / 79 skipped，B0 480 passed / 20 warnings；本地后端 2324 passed / 77 skipped |
| T13 | GSV 两条真实 DeepSeek 评测 PASS：ALL 410/305、CH_RETAIL 400/300，结果成板刷新重开一致；完整 T13 仍 PARTIAL，见[本轮交付](docs/hackathon/DIAGNOSIS-INTEGRATION-DELIVERY-2026-09-10.md) |
| T15 / T16 / T17 | 用户本人 UAT 待执行；现有合成单用户性能基线已测，正式容量范围/阈值待确认；原生能力仍 PARTIAL |
| 产品边界 | B0、比赛合成 HTTP、旧 CRM 分开；真实人群/完整诊断、完整视觉及旧 MCP 开放项仍保留 |
| 原服务 | 4327（PID 81058）、8000/5173（36717/36727）、14327（90347）未动；不是本轮运行证据 |
| 本轮候选 | 4325 DSH + 18083 合成 API，独立状态；保留供配置和验收，停止仅限本轮实例 |
| 归档数据 | `data/processed/fuqing_crm.duckdb` 不进 Git；本轮只核对文件元数据约 131GB，未打开、复制或改写 |
| 发布 | 本地候选已更新；五库新备份恢复、旧资产一致性与 BAR 刷新重开 PASS，Models 配置保留。快速 canary DEGRADED（既有 B0 404）；#115 未合并，非正式 release |

## 验证与历史入口

本地及 CI 按 [验证入口](docs/operating/verification.md) 的共同路径矩阵执行；skip 不算运行通过。固定 DSH、Node/Python、React 和 TypeScript 未升级；视觉增量新增 AntD 锁及声明补丁，并修复构建依赖链的 js-yaml。

#114 最终候选 CI `34385964860` 与合并后 main CI 均已核验，见 [维修 QA](docs/hackathon/COMPETITION-REPAIR-QA-2026-09-10.md)。本轮独立证据与开放项以 [产品验收与发布准备](docs/hackathon/PRODUCT-READINESS-2026-09-10.md) 为准。

#108 首购、W4/W5 和更早测试数、原生 stub 闭环及历史运维门禁已迁入 [历史记录](docs/history/STATUS-HISTORY.md)，不扩大为当前真实模型、容量或业务验收通过。

行为与数据边界见 [AGENTS.md](AGENTS.md)，设计合同见 [DESIGN.md](DESIGN.md)，其他债务见 [TECH-DEBT](docs/TECH-DEBT.md)。
