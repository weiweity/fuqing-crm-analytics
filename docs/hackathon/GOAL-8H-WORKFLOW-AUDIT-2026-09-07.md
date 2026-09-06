# Goal 8 小时流程审查（2026-09-07）

结论：**计划静态复核通过，可交付启动提示词；运行验收 NOT RUN。** 用户选择先接收提示词，再次发送后启动。本次只修改四份规划材料，没有启动 Goal/Grok 实施、业务服务、Git 写入或修改 gstack 本体。

## 核对来源

- 当前工作树 AGENTS.md 第 32–39 行：授权、commit 前 review、merge 前 qa、现有 hooks 和验证矩阵。
- 上级 fuqin-date/AGENTS.md：归档、真实数据、隔离工程及演示边界。
- [当前验证入口](../operating/verification.md)；[ship 历史说明](../operating/ship.md) 明确是历史资料，不把旧 12 步当本轮授权。
- 本机 gstack-review/SKILL.md：Codex Host Contract、review Step 2/3/4 和 5a–5d；gstack-qa/SKILL.md：Phases 1–6、Phase 8/9；gstack-ship/SKILL.md：Step 1/3/12/13/15–19。此次检查适用流程条款，不是执行代码 review、浏览器 QA 或发布。
- Grok CLI 实测版本 1.0.21 (3aedf38d5cfb)，bridge help 正常；源码确认 prompt-file/thread/timeout/write 参数。未调用模型检查登录或额度，也未验证 8 小时运行稳定性。

## 发现和修订

| 项目 | 原缺口 | 修订结果 |
|---|---|---|
| Git 流程 | 只有本地交付边界，没有可执行小 PR 流程 | LOCAL_ONLY 与用户发送后 PR_DELIVERY 分开；Codex 管 Git |
| gstack 职责 | 默认自动修复和文档子 agent 会破坏单实施者约定 | 4B 明确适配；修复/文档全部交单一 Grok，Codex 验收 |
| 提交证据 | 可能只审已跟踪 diff、遗漏新增文件 | 明确 staged 内容、未跟踪文件、候选 SHA 和变更后复验 |
| 现有 dirty | 固定 16 文件快照会过期 | 启动重新识别 T09、规划文档和其他改动，具名保护 |
| 已关闭 PR | 可能继续使用已合并 PR 分支交付 | 新 codex/ 任务分支；不复用已关闭 PR |
| 小 PR 依赖 | 等 merge 可能阻塞后续，直接从 main 又缺依赖 | 独立分支与依赖 PR 分开，记录 base PR/SHA，不伪称 main 集成 |
| P0 规划材料 | 当前 worktree 同时有 T09，会混入代码 PR | 可用轻量隔离 worktree 仅复制四份规划材料 |
| 发布后文档 | ship 缺省 push 后文档变化会使已验收候选过期 | 文档同步移到最终 review/commit/push 前 |
| 版本决策 | Skill 自动发布级别会扩大范围 | 普通文档不强制 bump，适用 MICRO/PATCH 与 MAJOR/MINOR 分开 |
| 计时/恢复 | 8 小时与 token 或产品完成可能混淆 | 固定绝对截止、恢复不重置、末 30 分钟收尾、Goal 为执行与交接契约 |
| 动作授权 | 计划内容本身可能被当成授权 | 启动词再次发送才生效；merge/部署/删除不在默认授权内 |
| 远端故障 | CI 排队/失败可能导致卡住或假成功 | 独立 Git 状态，不等于 PASSED；继续安全独立任务 |
| 费用/数据 | 编码执行器与产品真实模型、真实库容易混淆 | 仅正常 Grok 编码调用与 synthetic；真实数据和产品模型仍未授权 |

## 检查与限制

本次检查 Markdown 围栏、相对链接、所需本地文件/Skill/checklist 存在性、角色与授权一致性、Git 差异空白规则，以及 Grok 无模型的 version/help。原 16 个 T09 文件保留，本轮只编辑原两份规划材料并新增启动词和本报告。

本机桥接器 write 模式会自动批准工具，未提供任务专属写沙箱；这是已记录的执行限制，任务卡和差异审查不能冒充强隔离。启动时仍须核实登录/额度、当前代码、依赖、端口与远端状态；静态复核不证明这些运行条件已经通过。

没有为文档调整启动业务 QA、全量测试、commit/push/PR/merge。计划采用角色适配后的 gstack，不宣称未调整地执行了默认 /ship 全流程。

相关文件：[主计划](./GOAL-8H-CODEX-GROK-2026-09-07.md)、[Grok 模板](./GROK-EXECUTION-TASK-TEMPLATE-2026-09-07.md)、[启动词](./GOAL-8H-START-2026-09-07.md)。
