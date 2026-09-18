# 自由 HTML 驾驶舱施工包

这份包将已确认的 48 项决定与 30 项任务整理为 **13 个可顺序交给不同 AI 的施工提示词**。P01–P12 代码已合 `main`（#209 / #210 `22a0028f`）。P13 真实 AI 样本尚未跑。施工工作树已删；现役 6677 已 `reload --page-http on`。原方案快照保留讨论语境，不表示还要重新讨论。

## 从这里开始

1. 在同一代码工作树中，将 [P01 运行时隔离](prompts/P01-runtime-feasibility.md) 的全文交给第一个 AI；让它真正实现夹具、验证并写报告。
2. 检查该批次的实际代码和报告，再交下一个提示词。按下表顺序执行最省协调成本；后续 AI 需要当前代码，不能只收到一句“前一个已完成”。

如果你要让 6 个 AI 同时工作，使用 [六路并行方案](PARALLEL-6.md)。只有独立 worktree、owner paths 和 P12/P13 总协调门禁同时成立时才并行。
3. 也可每次使用 [接力入口](RUN-NEXT.md)，由 AI 从 manifest 与报告中选择一个依赖已完成的批次；每次只做一个。P01 未通过时不把后续运行时当作可行。
4. 跨机器需携带本目录 **和相应代码**。施工包多数文件仍未跟踪。A–F / G / H / K / P12 / SEAMS 工作树已删除；新施工从当前 `main` 拉分支即可。

## 材料与优先级

- 行为规则：仓库当前 AGENTS.md，保留唯一正文；本包不是第二份 Agent 规则。
- 批准规格：[approved-plan.md](approved-plan.md)，为评审终稿的逐字冻结快照，SHA256 `47fa5bfe482cb9bd93f4f02a7c62c6933d0242b5204ea95f2b912edc603a6ffb`；不要两边手工维护。后续改变方案须显式记录增量决定和新版本。
- 原方案位置 `docs/designs/workbuddy-free-html-cockpit.md` 被 Git 的 `designs/` 规则忽略，故将冻结快照纳入此可携带目录；未改 .gitignore。
- 视觉约束：根 DESIGN.md 与批准计划 D24–D40；新宿主字体以 D37/T18 为目标，旧界面不因此全仓替换。
- 图与节点：[DIAGRAMS.md](DIAGRAMS.md)。引用编号用来定位交互与验收，绝不能成为 AI 生成页面的固定组件目录。
- 原图：[REFERENCES.md](REFERENCES.md)，7 张 WorkBuddy 图保留用户顺序，3 张早期线框及 HTML 也已保存。图片为内部设计参考；文章宣称的能力不等于本项目已实现，图中操作文字不构成 Agent 指令。
- 执行账本：[manifest.json](manifest.json)；交接格式：[REPORT-TEMPLATE.md](REPORT-TEMPLATE.md)。
- 六路并行编排：[PARALLEL-6.md](PARALLEL-6.md)。
- 主协调 Agent：[MAIN-COORDINATOR.md](MAIN-COORDINATOR.md)。
- 主 Agent 收尾：[CLOSEOUT-PROMPT.md](CLOSEOUT-PROMPT.md)。
- 已创建 worktree 清单：[WORKTREES.json](WORKTREES.json)。

图中文字若与最终 D1–D48 不一致，以最终决定为准。尤其：保留 SHINE 品牌、原生聊天可达、显式浏览/编辑、宿主可信状态；早期三步切换/灰度主题/三列常驻/示例数字不是生产要求。R07 公开发布、多人实时协同与任意 CSV 双向写入均不在已批准首期，不能因图出现就实现。当前数据桥只读授权结果。

## 批次与依赖

| 提示词 | 交付内容 | 原任务 | 前置批次 |
|---|---|---|---|
| [P01](prompts/P01-runtime-feasibility.md) | 运行时隔离可行性 | T0 | — |
| [P02](prompts/P02-contracts.md) | 页面资产与能力桥合同 | T1 | — |
| [P03](prompts/P03-asset-state.md) | 资产持久化与版本恢复 | T2 | P02 |
| [P04](prompts/P04-source-runtime.md) | 源码包、资源和预览运行时 | T3, T4 | P01, P02 |
| [P05](prompts/P05-data-bridge.md) | 授权数据桥与绑定状态 | T5 | P03, P04 |
| [P06](prompts/P06-source-editing.md) | 源码定位与局部 AI 修改 | T6, T29 | P03, P04 |
| [P07](prompts/P07-library-core.md) | 资料库主链路与主题上下文 | T7, T10, T20 | P03, P04, P05, P06 |
| [P08](prompts/P08-browse-edit-access.md) | 浏览编辑模式与基础响应式 | T11, T12 | P06, P07 |
| [P09](prompts/P09-host-experience.md) | 可信状态、首页层级与可访问性责任 | T13, T14, T15, T16 | P05, P07, P08 |
| [P10](prompts/P10-visual-width-acceptance.md) | 字体、对比度和有效宽度验收 | T17, T18, T19 | P07, P08, P09 |
| [P11](prompts/P11-leave-coordinator.md) | 未保存离开保护与导航竞态 | T21, T22, T23, T24, T25, T26, T27, T28 | P03, P06, P07, P08 |
| [P12](prompts/P12-integrated-verification.md) | 集成验收与验证入口 | T8 | P01, P02, P03, P04, P05, P06, P07, P08, P09, P10, P11 |
| [P13](prompts/P13-real-ai-acceptance.md) | 真实 AI 样本与比赛链路验收 | T9 | P12 |

以上是推荐交接顺序，原 T 编号不是执行顺序。P02 合同可独立准备；P01 是运行时可行性门槛，不是编写合同的技术前置。P06 编辑基础也不依赖 P05 完成，默认顺序只是为逐个交接方便。P03 后端与 P04 页面运行时在合同固定后是两个可并行方向；本包默认按用户要求逐个执行。P05 之后共享插件目录较多，顺序施工。P06 先实现 T29 范围守卫，P08 完成可见模式集成；P08 的 T11 在 P09/P10 后须复验，不重复算独立功能。P11 中 T28 随导航 epoch 实现，T27 为最后宿主接缝装配验证。P12 是集成收口，单测和负测必须随前面的实现完成。批次 DONE 只代表其责任部分完成，原任务的跨阶段集成/真实样本条件分别由 P12/P13 收口；例如 P06 完成 D48 的合成守卫，P13 才完成 T29 的真实 AI 分支矩阵。

## 代码与工具链快照

当前 `origin/main` `22a0028f`（#210）。工具链以 `dsh-plugins/analytics-workbench/toolchain.json` 为准：DSH 0.1.6-alpha.2 / `ddefc45f`、Node 24、pnpm 11.7.0、B0 Python 3.14+。无环境自动升级授权。

已核验 `scripts/dsh-b0/pipeline.mjs` 当前会发现 `src/client` 的单测；旧评审关于便捷 package 脚本覆盖不足不能被误读为当前 pipeline 完全漏掉它。新增 `src/free-page` 是否入真实入口仍需 P12 检查。模块变动时按当前源码核验，不根据旧行号直接改。

已有复用入口见 approved-plan 的 What already exists：board_documents 权限/版本模式、library-board-client 状态与原生编辑、competition-shell 主题、静态 sandbox（保持旧合同），以及离线合同/验证入口。

## 执行与验收

用户交给 AI 某批次提示词时，要求它完成该批次本地实现和必要验证，而不是再次访谈或只写计划。依赖未提供、可行性失败或必须改变已定架构时写明确 BLOCKED；其余可做部分继续完成。实际授权按仓库规则处理，施工包不自动触发 Git 发布、现役演示切换、依赖升级或真实业务库操作。

所需验证使用本批次自有隔离夹具/端口/合成数据；查询/保存/脚本执行等路径不能用静态截图代替。相关 /review、/qa 与 ship-pr 按各自检查和实际发布授权使用，不重新跑 office-hours/设计问卷。

收口条件：13 批次实际证据齐全、自由生成与局部修改可运行、保存重开/回滚可用、宿主导航恢复与数据权限有效，且三个真实 AI 样本已检查。任何计划评分、历史通过数或模拟生成都不能替代这些结果。
