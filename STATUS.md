# 项目状态 (Project Status)

> 当前短表；编年与旧运维事项见 [STATUS-HISTORY.md](docs/history/STATUS-HISTORY.md)。

## 当前快照（2026-09-14）

| 项 | 状态 |
|---|---|
| VERSION / main | VERSION 仍 **0.8.0.0**（版本基线 `a729ff6`，#129）；最新业务落点 `12a21de`（#134），后续文档不升版本。版本基线不等于最新代码 SHA；实际 HEAD 用 `git log -1` 核对 |
| DSH 钉 | **main 固定 0.1.5-rc.1**（`183f08e9`）。本地 0.1.3 checkout 已删。后续再升架构走 `toolchain.json` + pipeline，见 AGENTS「二开基座与可升级性」 |
| 产品 | 仍 PARTIAL。验收账本：[产品验收与发布准备](docs/hackathon/PRODUCT-READINESS-2026-09-10.md) |
| T13 | 有界真实 DeepSeek 与分项取证已有；完整 T13 仍 PARTIAL。离线 eval 不代替真实模型复测 |
| T15 / T16 / T17 | T15 须用户本人 UAT；T16 仅单用户合成基线；T17 视觉与其余边界仍开放 |
| 归档数据 | `data/processed/fuqing_crm.duckdb` 不进 Git；约 131GB。禁止打开、复制、改写或对其执行 SQL |
| 发布 | 非正式 release。公网部署仍要独立授权 |

## 本轮施工计划（现行，不要只记在对话里）

当前先完成现有成果的 Git、文档和工作树收尾，不开启新功能。唯一接续卡为 [TODOS 的 M1 核心交付](docs/hackathon/TODOS.md#m1-核心交付)，不用另建 `todo.md`。交付按本仓 [ship-pr](.agents/skills/ship-pr/SKILL.md)，审查、QA、CI 与各动作授权分别核验。

产品方向：原生问数 → 复用结果、优先定制组件自由组板 → 预览 → 确认保存 → 指定组件 AI 修改／自由布局 → 重开／回退。六类是首批能力，不是六张固定模板或最终上限；旧交接的三操作、固定会话和主区互斥不是最终产品要求。

| 包 | Git 交付 | 适用范围 |
|---|---|---|
| P1 启动器 | [#131](https://github.com/weiweity/fuqing-crm-analytics/pull/131)，`c6e27d3` | owned 启动就绪、清理与取消；不把隔离竞态认作历史现场退出的确定原因 |
| P2 计算事实 | [#132](https://github.com/weiweity/fuqing-crm-analytics/pull/132)，`13bf175` | 逐日／渠道贡献／购买频次及 Python/JS 差额校验；原施工树旧快照不是最终 R4 |
| 工作流纳管 | [#133](https://github.com/weiweity/fuqing-crm-analytics/pull/133)，`a52309b` | 仓库专属 ship-pr；PR 与该 main CI 均成功 |
| P3/P4 + AI-1 | [#134](https://github.com/weiweity/fuqing-crm-analytics/pull/134)，`12a21de` | 104 文件业务包 + 3 文件取消修复，按组合验证交付；不宣称每个子包独立可发布 |

本轮合成检查与受控浏览器 QA 的精确范围见 #134；[PR CI 34809535341](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34809535341)与该业务提交的[main CI 34810185362](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34810185362)均成功。原失败日志和隔离证据保留；CI不替代完整真实模型、Figma或本人UAT。P2后的历史main CI `34768344985`失败不回写为成功；本轮取消修复证实机制，不声称重现了那次CI的具体交错。

### M1 接续与剩余事项

- S0/S1已有基线与同实例装配证据；S2仍 **PARTIAL**。9 月 13 日真实模型已完成六类自由组板，以及 METRIC 只改标题的取消／确认 v2／重开和生成快捷入口；其余五类指定编辑、LINE 日期换数尚未验完。
- **下一产品修复是 S2-C1 方案 B，尚未实施**：确认只更新 UI／服务端，模型下一轮目录缺已存板摘要，因而误称已保存 v2 为“旧草稿”。补同权限／同会话 `saved_boards` 摘要与状态指引，不自动追加模型 prompt、不新增模型确认写入权限。
- S3 对齐正式 Figma、组件属性与原生交互；S4 综合 QA；S5 可用 UAT 入口和交接；G1–G6及用户本人 U1均不能以 Git 交付代签。四类扩库已有实现，完整变体与真实模型验证归 M2。
- 开发协作沿用户人工转发 Grok Build 任务、主 Agent 复核的方式；不同 Agent 的共享入口与 Figma 母组件保持单写入者。原 App 全量 Goal 仍 PAUSED，本次未恢复或关闭它。
- 本轮不切换运行环境：6677／18082 保留，不重启、不改模型、不读真实数据；Git 更新不表示运行中的产物已切到最新 main。后续集成须核对产物、状态兼容与维护窗口，不用 `--fresh`。
- 文档与本地清理单独验收。原施工文件已逐项私有备份；`HANDOVER-CODEX.md` 继续保留、不提交。只有完成合并、main 检查、独有成果及进程归属对账后，才清理已完成分支／工作树。

## 已合施工记录（#116–#129）

下表是上一轮短 PR 记录。9 月 5–10 日总待办／T01–T09也不是当前 M1 任务卡；不根据历史测试数重新认领已完成项。

| 顺序 | 刀 | 证据 | 状态 |
|---|---|---|---|
| 1 | 文档入口，对齐施工边界 | #116 | 已合 |
| 2 | L4.91 R3 白名单：入会率水平值允许展示 `*100` | #117 | 已合 |
| 3 | main DSH 钉升级到 0.1.5-rc.1 | #118 | 已合 |
| 4 | 访客入会率 API 0-1 raw，前端水平值 `*100` | #119 | 已合 |
| 5 | GSV 口径谓词 SSOT | #121 | 已合 |
| 6 | DQ 本地告警（不接飞书） | #122 | 已合 |
| 7 | 聊天下「生成驾驶舱」（`conversation.input.dock`） | #124 | 已合 |
| 8 | T13 可重放离线 eval | #125 | 已合 |
| 9 | 侧栏固定入口：`sidebar.panellist` / `main` key=`cockpit` | #126 | 已合 |
| 10 | dsh-dev 收进 main：6677 + 插件插拔 | #127 | 已合。日常改插件用 `reload`，固定 `.context/dsh-dev/runtime`，不要 `--fresh` |
| 11 | 驾驶舱按 BoardSpec 生成：确认写入、`result_id` 绑数字、沙箱无脚本 | #129 | 已合 |

## 当前施工边界（防乱）

遇到下列项就停，不要当顺手活：

- 不要把比赛工具接到通用 metric HTTP，也不要把 `ChannelFollowupQueryRequest` 泛化成新合同
- 不要给模型新增 SQL 工具，不要从 `FORBIDDEN_EXPANSIONS` 拿掉 `execute_sql`，不要把 `ai_sandbox` 接到比赛 Agent
- 不要改 DSH 上游源码。不要打开、复制、改写 131GB DuckDB，也不对其执行 SQL
- T3 备份、`cleanup_backups.sh` 的 `keep_min`、口令轮换、T15 本人验收、公网部署：要显式授权
- 自由任意组件、受控脚本、飞书真实操作另作范围确认；保留现有静态 HTML 沙箱及 LINK 占位，不接 token。不要把聊天下生成和侧栏查看混成一个入口

## 验证与历史入口

本地及 CI 按 [验证入口](docs/operating/verification.md)。skip 不算运行通过。B0 当轮 T01–T09 已收口，清单是历史队列，不是当前任务卡。

#108 首购、W4/W5 和更早测试数已迁入 [历史记录](docs/history/STATUS-HISTORY.md)，不扩大为当前真实模型、容量或业务验收通过。

行为与数据边界见 [AGENTS.md](AGENTS.md)，设计合同见 [DESIGN.md](DESIGN.md)，开放债见 [TECH-DEBT](docs/TECH-DEBT.md)，验收缺口见 [TODOS](docs/hackathon/TODOS.md)。
