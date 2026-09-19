# 项目状态 (Project Status)
> 当前短表；编年与旧运维事项见 [STATUS-HISTORY.md](docs/history/STATUS-HISTORY.md)。

## 当前快照（2026-09-19）

| 项 | 状态 |
|---|---|
| 本地 Git 基线 | 已 fetch 核验 `origin/main` 为 **c0f47a24（#213）**；任务分支以此为基线，`git merge origin/main` 为 Already up to date。 |
| 当前工作树 | `fuqin-date/.worktrees/cockpit-v2-kernel`，分支 `codex/cockpit-v2-kernel`；接管 Grok G01–G04 累计未提交成果。 |
| VERSION / 产品 | **0.10.0.0**，用户确认的 V2 功能候选版本；产品仍 **PARTIAL**，原全量 Goal **PAUSED**。loopback，不上公网。 |
| DSH 基座 | **0.1.6-alpha.2（ddefc45f）**，不改上游。 |
| 现役 | 交接记录为 #213 已 reload6677、页库18091；本轮未切换、未重启，未将隔离验收写成现役验收。 |
| 原始数据 | 约131GB归档 DuckDB 不进 Git，不复制、改写或全表扫描；本轮全部使用小型合成夹具。 |

## 本轮施工计划

### 驾驶舱第二版：修复与 PR 交付

- 当前 C01–C03：Codex 接管前端与集成；工作区交付进柜 → HTML 显式入库/精确改字 → 看板字段 PATCH，延续现有布局/历史/回退。
- 页面采用驾驶舱特定浅灰/深色文字/橙色强调。产物栏可折叠，编辑侧栏按容器宽度调整，小屏切换画布/设置；不宣称完整 Figma 像素还原。
- 来源在离开原生会话前捕获；HTML 工作区文件先预览、再显式确认副本。点看板不发送消息，只有「用 AI 改」进入原生对话。
- 沿原有 leaveCoordinator 处理切资产/退出/返回；未知保存回执锁定切换并保留幂等键；原生侧栏不能 veto，重新进入恢复 store 中草稿。
- 本轮修复看板属性 PATCH、原生预览选择、未知确认后的安全取消/刷新、HTML 脚本顺序及原始文件重入；107 项针对性测试、21 条真实隔离浏览器主链均通过，失败过程留证。
- 本轮证据与操作说明见 [驾驶舱 V2 本地交付](docs/hackathon/COCKPIT-V2-LOCAL-2026-09-19.md)。C01–C03本地完成：B0完整聚合、合成backend及浏览器主链通过；77项backend跳过。分层证据与NOT_RUN见该文及C03。
- 本次用户已授权修复及 `/ship` 到 commit、push、PR，并明确跳过追加代码审查；提交/推送进度按交付说明记录。未授权 merge 或 reload。原仓 HANDOVER-CODEX.md 和本地交接材料保留，不入 Git。

### 仍开放且不由本轮代签的验收

- **P13**：保留原第一场真实失败，Agent Team 可见文件/Bash，未取得 free_html_page_generate 交付；后两场 **NOT_RUN**。文件入柜不代表工具注入已修复，字面替换不代表复杂 AI 编辑通过。
- 本轮完整 DSH 宿主浏览器、现役6677、真实模型、真实业务及用户本人视觉/UAT 未验收。隔离浏览器和合成 HTTP 结果分开记账。
- 工作区变化当前手动/重入刷新；未冒接不存在的宿主事件。无可靠映射或动态/绑定区域只读；外链及不可读取二进制相对资源明确拒绝入库。
- 原生侧栏 veto、openPlazaRole、Noto 字体及正式壳 B3 仍按原账本记录，不以新局部界面覆盖旧验收限制。

### 已有交付与产品边界

一期产物柜、本页编辑壳、看板布局/回退、HTML 悬停已随 #213 合入。S2-C1/#136、R-1/#153、比赛看板入口/#155+#157、人群行动/#166、品类脱敏/#165 的历史证据保留在 [TODOS](docs/hackathon/TODOS.md#m1-核心交付)。G1–G6/U1 的2026-09-16记录不重开，不等于本轮验收。

T13 有界合成复测；diag.fixed_cohort 仍 UNSUPPORTED。T15 用户原确认保留。T16 原合成基线不是 SLO 通过；T17 用户原“缺口也算关”不写成能力通过。未知金额 WATERFALL 仍422。

## 当前施工边界

不改 DSH 上游、不引入第二运行时；不新增 SQL 工具或泛化比赛问数合同。不启动真实 ETL、不碰归档库、不停无关端口。公网、真实消息、模型/凭据迁移和现役切换分别授权。

本地与 CI 按 [验证入口](docs/operating/verification.md)，未跑/skip 不算通过。行为规则见 [AGENTS](AGENTS.md)，视觉见完整 [DESIGN](DESIGN.md)，历史见 [STATUS-HISTORY](docs/history/STATUS-HISTORY.md)。
