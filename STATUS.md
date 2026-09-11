# 项目状态 (Project Status)

> 当前短表；编年与旧运维事项见 [STATUS-HISTORY.md](docs/history/STATUS-HISTORY.md)。

## 当前快照（2026-09-11）

| 项 | 状态 |
|---|---|
| VERSION / main | `0.7.0.0` / `bda4e47`（vitest 4.1.11）；#112、#114、**#115 已合并**（#115 = `f380c1e`） |
| main CI | [34566156877](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34566156877) SUCCESS，绑定 `bda4e47`；#115 合并 CI [34498144935](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34498144935) SUCCESS |
| DSH 钉 | **main 固定 0.1.5-rc.1**（`183f08e9`）。本地仍保留 gitignored 的 0.1.3 checkout 供回退，不删。后续再升架构走 `toolchain.json` + pipeline，见 AGENTS「二开基座与可升级性」 |
| 产品 | 仍 PARTIAL。验收账本：[产品验收与发布准备](docs/hackathon/PRODUCT-READINESS-2026-09-10.md) |
| T13 | 有界真实 DeepSeek 与分项取证已有；完整 T13 仍 PARTIAL。离线 eval 不代替真实模型复测 |
| T15 / T16 / T17 | T15 须用户本人 UAT；T16 仅单用户合成基线；T17 视觉与其余边界仍开放 |
| 归档数据 | `data/processed/fuqing_crm.duckdb` 不进 Git；约 131GB。禁止打开、复制、改写或对其执行 SQL |
| 发布 | 非正式 release。公网部署仍要独立授权 |

## 当前施工边界（防乱）

下一轮默认只做已授权的短 PR。遇到下列项就停，不要当顺手活：

- 不要把比赛工具接到通用 metric HTTP，也不要把 `ChannelFollowupQueryRequest` 泛化成新合同
- 不要给模型新增 SQL 工具，不要从 `FORBIDDEN_EXPANSIONS` 拿掉 `execute_sql`，不要把 `ai_sandbox` 接到比赛 Agent
- 驾驶舱 UI（`sidebar.panellist` / `main` key=`cockpit`）仍只在 `codex/competition-next`；本钉已有槽位，但不在 main 上捡驾驶舱。不要改 DSH 上游源码
- T3 备份、`cleanup_backups.sh` 的 `keep_min`、口令轮换、T15 本人验收：要显式授权
- 未提交的 visitor / GSV / DQ / 驾驶舱 WIP 在本地归档分支，**不在 main 上**

## 验证与历史入口

本地及 CI 按 [验证入口](docs/operating/verification.md)。skip 不算运行通过。B0 当轮 T01–T09 已收口，清单是历史队列，不是当前任务卡。

#108 首购、W4/W5 和更早测试数已迁入 [历史记录](docs/history/STATUS-HISTORY.md)，不扩大为当前真实模型、容量或业务验收通过。

行为与数据边界见 [AGENTS.md](AGENTS.md)，设计合同见 [DESIGN.md](DESIGN.md)，开放债见 [TECH-DEBT](docs/TECH-DEBT.md)，验收缺口见 [TODOS](docs/hackathon/TODOS.md)。
