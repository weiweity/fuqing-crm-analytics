# 8 小时 Goal 启动提示词

状态：待用户发送。**本文件由 Codex 编写；生成、打开或检查此文件均不启动执行。**

下面整段发送给当前 Codex 任务后开始。它授权本轮范围内 commit/push/小 PR；合并留待具体候选批准。

```text
现在启动约 8 小时的 Goal。

工作目录：/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/.worktrees/hackathon-mission-mvp
先完整读取该目录 docs/hackathon/GOAL-8H-CODEX-GROK-2026-09-07.md（修订 2）、GROK-EXECUTION-TASK-TEMPLATE-2026-09-07.md 和适用 AGENTS.md，按计划 G0→G5 的依赖顺序持续推进。

分工固定：Codex 写方案、拆任务、调度、执行 gstack 审查/QA、独立验收和管理 Git；业务代码、测试、构建脚本、类型、VERSION/CHANGELOG 及实现文档统一由本机 Grok CLI 写。每次只有一个 Grok 实施作业，不另派 agent，Codex 不代写实现。按计划 4B 适配 gstack 的自动修复和文档子 agent，保留适用验收门。

本轮选择 PR_DELIVERY。我授权你在上述项目、本轮 T09/B0 收尾、数据合同/合成金标准、首条合成业务查询及原生接线范围内，保护现有改动后创建 codex/ 任务分支和必要隔离工作树，具名暂存、正常 commit、push 到核验的现有 origin、按功能创建或更新小 PR，并跟踪 CI。包含现有 T09 成果与本轮规划文档的交付，不得夹带其他改动。允许把核验的 base 同步到本轮 clean 任务分支，冲突实现交 Grok 修复并重验；不重写已推送历史，不动共享 main。上述范围内无需逐次再问 commit/push/PR。

每单元执行：Grok 实施和相关测试 → Codex /review → Grok 修复 → Codex 复验 → /ship 适配交付检查 → commit/push/小 PR → 候选 SHA 对应 CI 和 /qa → 修复重验。按计划核对已有证据，不跳过正常 hooks 和必需 CI。依赖未合并时用明确 base 的依赖 PR，独立任务从核验主干起，避免一个大 PR。

我没有授权自动 merge、部署、公开网址提交、分支删除、真实业务数据读写/复制/ETL、产品模型付费调用、全局环境改动或守护安装。允许按既有入口使用小型 synthetic fixture、临时状态库和必要 B0 服务；结束只停止本轮拥有的实例，保留原演示。普通 MICRO/PATCH 按适用策略处理；MAJOR/MINOR、破坏性合同或架构变更须提出具体方案，继续不依赖该决定的工作。

收到本消息才创建或恢复匹配的 Goal，记录开始时间和 8 小时截止时间；8 小时不是 token 预算。每轮 Grok 限定 15–30 分钟，保存 run/thread/日志与任务账本；失败先核实 partial diff，再定点修复。上下文恢复沿用原截止时间，禁止重复派发。执行器或依赖受阻时记录证据并继续独立任务，不用 Codex 代写或无限重试。

最后 30 分钟停止新增功能，完成必要验收、进程收尾和交接。按真实结果报告单元、分支/PR/CI/QA、失败与下一步；8 小时到点不等于产品全部完成。先给出当前基线和第一个 Grok 单元，然后开始执行。
```

主计划：[Goal 计划](./GOAL-8H-CODEX-GROK-2026-09-07.md)。
检查记录：[流程审查](./GOAL-8H-WORKFLOW-AUDIT-2026-09-07.md)。
