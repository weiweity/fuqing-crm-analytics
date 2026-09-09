你继续原 first-purchase-runtime 候选返修，不创建新任务、不提交或推送。

> 历史阶段证据：后续已由 Codex 完成本地修复与集成，无需转交。当前结果见 [集成报告](./PARALLEL-INTEGRATION-RESULT-2026-09-08.md)。

目标工作区：/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/fuqing-crm-analytics/.claude/worktrees/codex-first-purchase-runtime
基线 3ec1c866aa794baee6c0ebb7205aee375db1a49f；ledger.py 当前 SHA256 3d8b9ca4c09919d0828a26e62edc4b897a7d9d2985bd2870a3178a01c2c2f247。

Codex 独立复跑 26 passed，另复现 P1：execute 对 RUNNING 无执行者存活判定，两个同 key 同体并发请求计算两次、返回同 run。复现方法：现有 make_ledger/fp_actor 和金标准 request；两个线程调用 submit_and_execute；patch ledger.bound_first_purchase_result 为先 Barrier(2) 再执行原函数；调用数为 2。

修复要求：区分仍活跃执行和真正退出后的恢复。同 key 的活跃重试不能重新计算；崩溃恢复仍返回原 run，不能永远卡 RUNNING。优先复用现有执行所有权机制，不复制第二套 attempt/lease/预算调度系统。原 ledger 只是待替换验证适配，不升级为长期运行内核；若无法在原文件边界安全实现，明确给出最小接缝而不是宣称此候选可直接集成。

新增确定性并发回归与子进程真实退出后的重开恢复测试，避免只用线程异常代替进程退出证据。修正 HANDOFF 中旧 25 passed 与实际计数不一致；记录遗留 warning 来源。
共用 jobs/worker/runtime/catalog/前端/pipeline 仍交 Codex，不改这些文件。不要为通过测试新增平行任务状态机。
更新 HANDOFF、INTEGRATION、EVIDENCE、FILES.sha256，给出准确层级 ADAPTER_HTTP / SHARED_WORKER_NOT_RUN。
