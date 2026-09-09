你继续原 W4 候选返修，不新建分支、不提交或推送。

> 历史阶段证据：后续已由 Codex 完成本地修复与集成，无需转交。当前结果见 [集成报告](./PARALLEL-INTEGRATION-RESULT-2026-09-08.md)。

工作区：/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/.worktrees/w4-shared-customer-features
基线 3ec1c866aa794baee6c0ebb7205aee375db1a49f；compute.py 当前 SHA256 18f54d005e13be8fed575902ded14374d24a9afdd60472a96090a9f1e3ea8df1。

Codex 独立复跑 11 passed，另复现 P1：compute 返回后修改 result.rows[0]['valid_net_paid_minor']=1，write_customer_features 成功导出 1，但 published.features_sha256 保持原值。frozen dataclass 没有冻结内部 dict。
另一个合同缺口：_finish 摘要基于 JSON 数组，写出文件却是 JSONL。原金标准 5 行 manifest 哈希 8539b882ae1960af70c8523d2a7c1c40c5bb1f6c1fef4cfe00eae90312f2283a，实际文件 SHA256 7027fbf2a03abbf79b4672819046e5fc9b01d109c0912f48eb3c9a588bcdc9e9。没有明确读回规范；即使选择逻辑摘要，变更后沿用旧摘要也不正确。

修复：定义摘要到底覆盖规范化逻辑行还是文件字节；若保留两种则字段分开。写出内容、返回 manifest 和哈希必须源于同一份已验证内容；结果修改要么明确拒绝，要么按正确合同重新验证并重新计算，不允许错误摘要继续发布。测试覆盖落盘新读者验证、变更行、空集、篡改文件/摘要的拒绝。不要把本轮扩成 W5、多版本发布或修改 W1–W3 schema。
保持业务口径和读取边界，更新交接与 FILES.sha256；保留本次失败证据。仍只交本地候选，不改主工作区、共用 pipeline、HTTP、catalog。
