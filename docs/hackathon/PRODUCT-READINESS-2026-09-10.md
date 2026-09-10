# 产品验收与发布准备（2026-09-10）

## 目标与基线

执行用户明确采用的七阶段目标，先完成前 3 项，后续阶段保持开放直至具备相应真实证据。主线基线 `788b5b108fed22526805248a86f310ef7602cc6e`；本轮工作树 `competition-product-readiness`，分支 `codex/competition-product-readiness`。工作树从主线新建，原主工作副本的未提交设计和规划文件保留。

[PR #114](https://github.com/weiweity/fuqing-crm-analytics/pull/114) 已合并；最终候选 CI `34385964860`、[main CI `34386758906`](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34386758906) 均已实时核验为 SUCCESS。原修复与合成浏览器证据见 [维修交付](COMPETITION-REPAIR-2026-09-10.md) 和 [维修 QA](COMPETITION-REPAIR-QA-2026-09-10.md)。既有通过项不扩大为整产品通过。

## 要求与完成证据

| 阶段 | 明确要求 | 必须取得的证据 | 当前状态 |
|---|---|---|---|
| 1 工程状态 | STATUS、README、TODO、交付记录一致；核验 main CI | 文档引用/差异核验；CI 绑定 `788b5b1` | 文档已同步，差异检查通过，main CI SUCCESS |
| 2 缺陷修复 | 首次启动无误报；图表类型保存/刷新/重开一致 | 根因复现、失败到通过回归、真实浏览器 | 图表修复已通过组件和 HTTP 持久化回归；首次欢迎误报暂未复现 |
| 3 原生与视觉 | T17 工作区、会话、设置、工具、权限；主题、弹层、窄屏、错误状态 | 固定 DSH 的真实原生路径、按 DESIGN 的截图和结果矩阵 | PARTIAL：原生 Stop、文件权限/审批、默认隔离和重启恢复已实测；目录选择器、完整 preset/压缩及视觉仍开放 |
| 4 业务与模型 | 明确默认值/UNKNOWN；核对旧 MCP/截断；T13 | 业务口径确认记录、完整工具返回证据、真实模型 eval | T13 PARTIAL：真实 DeepSeek 调用与合成工具已实测，见下文 |
| 5 三角色 UAT | 分析师诊断成板、运营候选草稿、老板阅读决策 | 完整路径预演和业务代表验收记录 | GSV 模型结果入板与重开已通；本人待验，完整诊断与视觉仍 PARTIAL |
| 6 性能容量 | 页面性能基线；数据量/并发/P95/RSS/超时 | 可复现测量配置、原始结果及预算比较 | 单用户合成基线已测；T16 正式阈值及归档规模待确认 |
| 7 发布 | 版本/环境、状态备份与回退、部署后验证 | 目标环境及配置、恢复证据、发布版本和关键路径/指标 | 本地候选已更新，状态备份恢复 PASS；Git 候选交付中，未正式发布 |

任何阶段仅有局部测试、清单或工具调用都不算整体完成。不猜业务默认值、不把合成数据当真实经营数据。七阶段完整目标持续保留。

用户已确认：T13 使用 DSH 的 DeepSeek-V4-Flash；T15 由用户本人验收；T16 按现有数据量、并发 1；部署由本轮推荐执行，采用本地隔离候选实例。费用上限和容量阈值尚未约定，现阶段只准备有界评测及性能基线。

## 本轮实际结果（持续更新）

- 图表根因：原选择器只改组件内存，未创建待保存补丁。新增独立 `competition-board-chart-patch/v1` 扩展，沿既有预览、版本、权限、取消及幂等链路保存。冻结 C0 哈希仍为 `97ee36833200b3a1626a4fa88e6b3bc9591bfb5f6bebc5e666aeabdcce13815a`。
- 回归：新增图表 HTTP 测试 8 passed；相关后端合计 27 passed；最终图表/草稿 20 passed（含 11 个编译后组件）；完整后端日常 profile 2282 passed / 77 skipped，完整 B0 pipeline PASS。新应用重开、重试、冲突、权限、取消、非法载荷及草稿恢复/放弃均有覆盖。具体失败修复及计数见 [审查与验证](evidence/product-readiness-2026-09-10/REVIEW-AND-VERIFICATION.md)。
- 浏览器实际创建合成板 `board_4dcb6d75329580a96315a8882a1819a7`，TABLE v1 → BAR 预览 → 保存 v2，弹层保持打开。请求证据见 [HTTP trace](evidence/product-readiness-2026-09-10/chart-http-trace.json)。
- 视觉检查发现原 BAR/LINE 图形使用固定装饰数据，已改为明确的“暂无可绘制的数值序列”及真实元数据表。图表偏好可保存不等于已具备真实数值绘图。
- 共 3 个全新运行时首次 Continue 点击成功；追加 2 次首点后刷新仍正常，见 [欢迎页复现](evidence/product-readiness-2026-09-10/welcome-reproduction.json)。未复现历史保存失败，不能声称根因已修复。原生 Settings 的 Dark、Read Only 可设置，Plugins/Agent presets 可达。两个工作区由原生 API 准备后，通过 UI 切换；系统目录选择器未验。
- 原生新建空白会话、切回已保存会话、进程重启后恢复历史均已实际验证。用户在原生 Models 配置后，已解决 CA 证书链问题并完成真实 DeepSeek 调用；详见 [T13 实测](evidence/product-readiness-2026-09-10/T13-LIVE.md)。工具真实执行已有证据；后续只读拒写已补验，运行中撤权及提权审批仍开放。
- 普通原生会话的 B0 连接中断误报已修复，只为登记的 B0/查询会话挂载状态组件；编译后回归及三次浏览器加载均不再出现。主题截图是用户偏好选为 Dark 后的结果，不代表默认主题或全部 DESIGN 要求通过。
- 已完成浏览器刷新后重开图表：仍为 BAR，行数 1，弹层保持，390 宽无页面横向溢出。截图已人工查看；外层浅色原生 UI 与内层深色业务区不一致，保留设计偏差。
- 已测 [HTTP 基线](evidence/product-readiness-2026-09-10/http-baseline.json)：现有 1 块合成板，并发 1，3 条路径各 30 次，全到达分母 90/90 成功，P95 7.627/8.538/10.478ms，采样 RSS 峰值约 36.9 MiB。没有冷缓存、真实大库或多板容量证明。
- [页面基线](evidence/product-readiness-2026-09-10/browser-baseline.json)：1440×1000，原生已认证会话、暖缓存三次，FCP 中位 84ms、LCP 中位 188ms，27 个资源请求、约 436KB 传输。首份基线不作性能回归结论。
- 默认值确认及容量数据目标已提出具体选择：既有归档 `data/processed/fuqing_crm.duckdb` 文件约 131GB，仅检查文件元数据，尚未打开。用户演示服务不为此停止。

截图位于 [本轮证据目录](evidence/product-readiness-2026-09-10/screenshots/)。`chart-before-visual.png` 是修正固定装饰图形之前的失败证据；不得作为修复后视觉通过截图。

## 本轮文档覆盖

最终浏览器补验：LINE 预览刷新后，先读到已保存 BAR，再恢复出 LINE 草稿；放弃后仍为 BAR 且可继续编辑。运营预览得去重 6 人，草稿 `draft_46510707572a435c92b27ed1eef98fe1` 从 v1 保存为 v2，刷新重开文案保持；老板脱离会话仍可阅读原板。见 [本人 UAT 清单](PRODUCT-UAT-2026-09-10.md)。模型诊断结果进入认可列表仍未接通，完整主线不算通过。

本地状态备份及新目录恢复已通过，恢复出原板 v2/BAR；备份发生在上述运营草稿创建前。部署及回退边界见 [本地候选运行说明](PRODUCT-LOCAL-RELEASE-2026-09-10.md)。

| 变化 | 参考 | 使用说明 | 解释/证据 | 补齐点 |
|---|---|---|---|---|
| #112/#114 合并与 CI | STATUS、根 README | 当前验证入口 | 修复 QA | 删除当前入口中的过期状态判断，保留历史记录 |
| 比赛 HTTP、会话及草稿 | `docs/operating/competition-http.md` | dsh-dev README、维修复现命令 | 修复交付、截图/HTTP 记录 | 已链接当前入口；完整三角色使用路径在阶段 5 验收 |
| 剩余缺陷与发布条件 | 本账本、TODOS | 各阶段验证命令随执行记录 | 尚未取得的证据明确 NOT_RUN | 不把任务包、旧测试数或 CI 代替实际产品验收 |

## 起点核验与隔离

用户演示 4327 PID 81058，旧 8000/5173 PID 36717/36727，已有独立 14327 PID 90347，均保持。本轮独立候选在 4325（DSH）和 18083（合成 API），状态位于本树 `.context/dsh-dev/runtime-Cn0Ifc` 和 `.context/competition-synth`。现保留用于配置和用户验收；结束后只回收本轮拥有的实例。

固定 DSH `d347e703908d0406b7a7ef80e3a0e594d86b2215`，Node 24，已有锁定 Python 环境。首次启动修复先追溯设置写入与反馈路径；不直接修改固定上游。图表类型修复沿 UI 预览、保存合同、后端版本和重读逐层验证。

## 追加：诊断计算隔离与接线计划

2026-09-10 重新核验：main 仍为 `788b5b1`；[PR #115](https://github.com/weiweity/fuqing-crm-analytics/pull/115) 为 draft/open，候选 `8c2e676` 的必需 CI 全部 SUCCESS，路径跳过项不计通过。旧版状态备份/恢复结果仍有效，但不覆盖其后创建的行动草稿。

从 `8c2e676` 新建 `competition-diagnosis-integration` 工作树，分支 `codex/competition-diagnosis-integration`。移除计算模块通过已加载模块搜寻 A9 JSON、隐式创建 refunds 的路径；测试显式准备退款表，并按发生日期验证全额/部分退款。修复前独立负测 2 failed / 2 passed；修复后完整日常合成后端 2287 passed / 77 skipped（240 个文件、10 组），Ruff 与差异检查通过。绑定源文件 hash 与原始检查位置见[验证记录](evidence/diagnosis-integration-2026-09-10/computation-isolation-verification.json)。这是 D1 完成时点的历史记录；随后数值接线、运行时切换和真实模型结果见下节。

工程审查确认 GSV 数值结果需要独立运行时合同、可信快照和前端分派，不能将 C0 引用夹具当作 ChannelFollowup 保存分析。[接线计划 D2–D5](DIAGNOSIS-INTEGRATION-PLAN-2026-09-10.md) 已覆盖架构、代码、测试和性能。此处保留实施前的缺口判断；新增完成项见下节，不扩大为“完整诊断主线通过”。七阶段及既有异步待确认项均保持开放。

## 追加：计算快照与真实模型成板

数值增量已经接通，完整合成后端 2315 passed / 77 skipped，B0 全流程及干净重建 PASS。真实 DeepSeek 两条有界问题分别得到 ALL 的 410/305/+105/+34.43% 和 CH_RETAIL 的 400/300/+100/+33.33%；ID、条件与 digest 均匹配持久化快照。后一结果由浏览器认可成板，保存 BAR v2 后刷新重开数值一致。

4325/18083 已使用新插件/计算代码，原模型配置、旧 BAR 看板和行动草稿 v2 保留。切换前四库备份/隔离恢复通过；新结果库另有独立备份恢复。90 次单用户合成读取全部成功，P95 8.36–13.83 ms，只是当前数据基线。

证据、运行位置和回退边界统一见[本轮交付](DIAGNOSIS-INTEGRATION-DELIVERY-2026-09-10.md)。此处为数值接线完成时点；后续提交、取消与主题接入见下文。完整诊断/旧 MCP、业务口径、本人 T15 和正式 T16 仍开放。T13 的两个 GSV 用例通过不替代全套真实业务评测。

## 诊断取消增量复查

计算中取消后仍发布已实际复现并修复。Node transport 手动 AbortSignal 和 5 秒超时均经真实 HTTP 阻止 SQLite 发布，跨进程与回执失败语义已覆盖；完整 backend 2320 passed / 77 skipped、独立 B0 全流程 PASS，见[交付](DIAGNOSIS-CANCELLATION-2026-09-10.md)。浏览器原生停止入口、用户 T15、正式 T16、业务默认值和整体发布条件继续开放，不缩减七阶段范围。

数值与取消代码 `d9c9162` 已推送到 #115，并切换 4325/18083；五库备份恢复和旧资产一致性通过，Models 配置保留原位。见[当前切换记录](DIAGNOSIS-CANCELLATION-2026-09-10.md)。`d9c9162` 的远端 CI 成功；后续文档提交 `afb62b0` 的首购原生测试收到可重试 503 而失败。现已用隔离 SQLite 写锁验证沿原调用恢复和单 worker，并修正测试的瞬态等待，11 项通过；修复提交 `e63df18` 的 [CI 34410948184](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34410948184) 已成功，详见[失败与回归记录](evidence/diagnosis-integration-2026-09-10/CI-NATIVE-RETRY.md)。

## 原生主题与实际 AntD 增量

独立 `competition-visual-readiness` 基于 `e63df18` 补官方主题服务、实际 AntD 表单和窄屏控件。4328/18084 临时合成浏览器实测 Light/Dark 刷新保持、BAR 410/305 保存重开与弹层焦点；完整 B0 pipeline 和干净重建 PASS，依赖审计漏洞计数为 0。临时实例已停止；随后 `d482bd6` CI SUCCESS，已切换 4325/18083，见[当前切换](PRODUCT-CANDIDATE-SWITCH-2026-09-10.md)。失败截图、测试告警和未完成项见[视觉结果](PRODUCT-VISUAL-INTEGRATION-2026-09-10.md)，不能把本增量当作完整 T17、T15 或 T16。

正常 pre-push 曾暴露首购原生观察写锁误记 UNKNOWN 的恢复缺陷；已独立复现并修复共享调度器，相关 23 项回归通过，后续完整检查、推送及 CI 已完成。见[恢复记录](OBSERVATION-STATE-RECOVERY-2026-09-10.md)。

## 原生停止与文件权限补验

`6b32ce9` 的 [CI 34419690573](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34419690573) 已核验 SUCCESS。独立完整原生 DSH 配置配合本地 provider，实际验证 Stop 点击→CANCELLED 回执→迟到发布拒绝→同会话恢复 410/305；只读读取、只读拒写及 Workspace Write 写入均核对原生 tool/result 与落盘。刷新、新建空白会话及切回旧会话已验证。见[补验与复现](PRODUCT-NATIVE-STOP-PERMISSIONS-2026-09-10.md)。

这是本地工具控制面的局部验收，不计入 T13、不证明物理 SQL 中断。首次两次夹具失败保留，目录选择器、提权审批、运行中撤权及完整 preset/视觉矩阵仍开放。临时 4328/18084 已关闭；用户 4325/18083 保留。

## 原生审批与 preset 补验

`d2a5a6f` 的 CI `34421652594` SUCCESS。新增真实原生审批卡的 Reject/Allow once、批准不延续、运行中收窄权限约束下一次调用、默认只影响新会话和重启恢复证据。Minimal 关闭业务插件时保留两个原生工具，开启时保留并增加四个业务工具。全部使用独立本地 provider，不计 T13；详见[审批补验](PRODUCT-NATIVE-APPROVAL-2026-09-10.md)。

系统目录选择器、其他 preset 的完整行为、长会话/压缩、完整视觉及其余业务和发布门禁继续开放。原生权限按上游下一次调用合同判断，未宣称杀掉已执行中的系统调用。新夹具 4328/18084 已关闭，用户 4325/18083 保持。

## 首屏与断连恢复增量

会话/连接说明、板块标识和错误请求标识改为可展开详情，合成边界常显；编辑操作按页面显示。独立浏览器断连负测发现初始化异常未展示，现已修复并验证恢复后原 BAR v2、410/305 和 1 块板保持。390/1024/1440 无横向溢出、键盘展开与焦点闭环、模拟 System 深浅切换通过；32 项定向 DOM、11 项 transport 和完整 B0 PASS。见[本轮记录](PRODUCT-VISUAL-DENSITY-2026-09-10.md)。尚未切换 4325；完整七阶段门禁继续开放。

后续 `9948de3` 的远端 CI SUCCESS，界面现已[切换 4325](PRODUCT-DENSITY-CANDIDATE-2026-09-10.md)，18083 API 原进程、原模型选择、2 块板/3 条结果及所有板明细保持。切换证据独立于上述实现验收，完整七阶段门禁继续开放。
