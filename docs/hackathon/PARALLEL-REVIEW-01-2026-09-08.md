# 并行候选接收复核 01

结论：RETURN_FOR_REVISION；未导入候选业务文件。两轨 HEAD 均为 3ec1c866aa794baee6c0ebb7205aee375db1a49f，Claude 5 个文件、Grok 9 个清单条目 SHA256 全匹配，无 tracked 修改混入。

独立 bounded runner：Claude 首购 HTTP+离线 26 passed（1 warning）；Grok W4 11 passed。以上是候选基础验证，不是共享 worker/native/集成通过。

## F1 / P1：同键重试对仍活跃的 RUNNING 再次计算

文件 first_purchase/ledger.py（SHA256 3d8b9ca4c09919d0828a26e62edc4b897a7d9d2985bd2870a3178a01c2c2f247）。execute 对任何 RUNNING 都继续执行；它没有执行所有权/lease。两个线程调用 submit_and_execute(actor, 同 key, 同 request)，在 bound_first_purchase_result 上用 Barrier(2) 同步，观察到计算调用 2 次、返回同一个 run id。该探针使用私有临时 SQLite 与现有金标准，不改源码。

影响：崩溃恢复修复也放行了活跃请求的重复执行，未来物理 worker/预算接线不能沿用。候选本身还未实现共享 WorkerManager，不能把 26 项 HTTP 测试作为 worker 交付。

修复边界：不要叠加第二套调度；把独立账本限定为候选验证，或使用现有可复用的执行所有权保护，让活跃重试返回当前 run/明确可重试状态，确定退出后才恢复。同 key 的单一逻辑执行及真实退出后的恢复都必须保留。共享 RunStore family/child 集成仍由 Codex 负责。

## F2 / P1：特征产物内容改变但摘要不变

文件 customer_features/compute.py（SHA256 18f54d005e13be8fed575902ded14374d24a9afdd60472a96090a9f1e3ea8df1）。CustomerFeatureRun frozen 只冻结属性，不冻结 rows 内 dict。修改 result.rows[0]['valid_net_paid_minor']=1，write_customer_features 仍成功写出修改值，published.features_sha256 沿用修改前值。

另外 _finish 哈希的是 JSON 数组，writer 写的是 JSONL。基准 5 行结果 manifest 为 8539b882…，实际 JSONL 字节为 7027fbf2…；文档未定义规范化读回算法或双摘要，消费者不能用文件直接校验该字段。即使选择逻辑行摘要，修改后沿用旧摘要仍是确定缺陷。

修复边界：明确逻辑摘要/文件摘要合同，在写出时对同一份不可变/重新验证后的内容计算；拒绝变更或重新生成一致摘要。补落盘读回、改值、空集及坏摘要负测；不升级成 W5。

## 后续

两个返修提示见同目录 CLAUDE-FIRST-PURCHASE-REVISION-01.md、GROK-W4-REVISION-01.md，由用户转交。Codex 保留首购共享接线任务，不以当前独立 ledger 代替 RunStore，不提前开放 catalog 或 native。
