# 项目状态 (Project Status)

> 当前短表；编年与旧运维事项见 [STATUS-HISTORY.md](docs/history/STATUS-HISTORY.md)。

## 当前快照（2026-09-11）

| 项 | 状态 |
|---|---|
| VERSION / main | `0.7.0.0`。HEAD 以 `git log -1` 为准；已合 #112、#114、#115、**#116–#122** |
| DSH 钉 | **main 固定 0.1.5-rc.1**（`183f08e9`）。本地 0.1.3 checkout 已删。后续再升架构走 `toolchain.json` + pipeline，见 AGENTS「二开基座与可升级性」 |
| 产品 | 仍 PARTIAL。验收账本：[产品验收与发布准备](docs/hackathon/PRODUCT-READINESS-2026-09-10.md) |
| T13 | 有界真实 DeepSeek 与分项取证已有；完整 T13 仍 PARTIAL。离线 eval 不代替真实模型复测 |
| T15 / T16 / T17 | T15 须用户本人 UAT；T16 仅单用户合成基线；T17 视觉与其余边界仍开放 |
| 归档数据 | `data/processed/fuqing_crm.duckdb` 不进 Git；约 131GB。禁止打开、复制、改写或对其执行 SQL |
| 发布 | 非正式 release。公网部署仍要独立授权 |

## 本轮施工计划（现行，不要只记在对话里）

收口原则：一次一刀短 PR；合了再说下一刀；业务不直接改 `main`；不另起文档海。勾选与待办见 [TODOS 本轮施工队列](docs/hackathon/TODOS.md)。9 月 5–10 日总待办 / T01–T09 **不是**本轮任务卡。

| 顺序 | 刀 | 证据 | 状态 |
|---|---|---|---|
| 1 | 文档入口，对齐施工边界 | #116 | 已合 |
| 2 | L4.91 R3 白名单：入会率水平值允许展示 `*100` | #117 | 已合 |
| 3 | main DSH 钉升级到 0.1.5-rc.1 | #118 | 已合 |
| 4 | 访客入会率 API 0-1 raw，前端水平值 `*100` | #119 | 已合 |
| 5 | GSV 口径谓词 SSOT | #121 | 已合 |
| 6 | DQ 本地告警（不接飞书） | #122 | 已合 |
| 7 | T13 可重放离线 eval | 归档 `archive/2026-09-11-iron-rules-t4` | **下一刀**（说「开 T13」）；不代替真实模型复测 |
| 8 | 驾驶舱 UI：`sidebar.panellist` / `main` key=`cockpit` | 归档 `archive/2026-09-11-cockpit-t2` | 其后；钉已是 0.1.5，**可以上 main**，不要提前捡 |

## 当前施工边界（防乱）

遇到下列项就停，不要当顺手活：

- 不要把比赛工具接到通用 metric HTTP，也不要把 `ChannelFollowupQueryRequest` 泛化成新合同
- 不要给模型新增 SQL 工具，不要从 `FORBIDDEN_EXPANSIONS` 拿掉 `execute_sql`，不要把 `ai_sandbox` 接到比赛 Agent
- 不要改 DSH 上游源码。不要打开、复制、改写 131GB DuckDB，也不对其执行 SQL
- T3 备份、`cleanup_backups.sh` 的 `keep_min`、口令轮换、T15 本人验收、公网部署：要显式授权
- T13 eval / 驾驶舱 WIP 在上表对应归档分支，**未合进 main 前不要从别的刀顺手捡**

## 验证与历史入口

本地及 CI 按 [验证入口](docs/operating/verification.md)。skip 不算运行通过。B0 当轮 T01–T09 已收口，清单是历史队列，不是当前任务卡。

#108 首购、W4/W5 和更早测试数已迁入 [历史记录](docs/history/STATUS-HISTORY.md)，不扩大为当前真实模型、容量或业务验收通过。

行为与数据边界见 [AGENTS.md](AGENTS.md)，设计合同见 [DESIGN.md](DESIGN.md)，开放债见 [TECH-DEBT](docs/TECH-DEBT.md)，验收缺口见 [TODOS](docs/hackathon/TODOS.md)。
