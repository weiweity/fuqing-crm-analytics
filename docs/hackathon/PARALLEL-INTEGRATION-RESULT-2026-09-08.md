# 首购 / W4 本轮本地集成结果

日期：2026-09-08。状态：LOCAL_INTEGRATION_PASS / UNCOMMITTED。
基线：`3ec1c866aa794baee6c0ebb7205aee375db1a49f`，分支 `codex/parallel-query-w4-integration`。VERSION 保持 0.6.3.0，新增未发布 CHANGELOG。

## 四步交付

1. **共享内核与 worker 完成。** 首购使用 `RunStore(family="first_purchase")`、现有 attempts/预算/lease 与物理 `WorkerManager`；独立临时 ledger 已移除。可信 family codec 区分 B0、渠道、首购，重开状态库验证 family。首购 child 执行既有 JSON 金标准，不连接真实库。并发同 key 只启动一个 worker。
2. **独立 HTTP 与合同完成。** `/api/v1/analytics-first-purchase` 使用共享运行快照，POST 返回终态 200 或在途 202；离线 OpenAPI、生成 TypeScript 和类型样例纳入统一 pipeline。装配入口及宿主 tick 责任见 [使用说明](./FIRST-PURCHASE-SHARED-HTTP.md)。没有默认启动服务。
3. **受影响回归完成。** 验证正常结果、缺角色、权限隔离、运行中撤权、重复 key、并发、排队取消、进程崩溃及退出证据。W4 独立读取订单头；JSONL 实际字节 SHA256 与 manifest 一致，变更行或摘要会在写文件前拒绝。W4 未自动接入首购。
4. **交付资料完成。** 更新 STATUS、hackathon 入口与总待办；保留接收审查和早期失败证据。实际候选差异和文件 SHA256 保存在本 worktree `.context/parallel-final/`，不纳入源交付。

## 本次实际验证

| 验证 | 结果 |
|---|---|
| `scripts/dsh-b0/pipeline.mjs --check --python /Users/hutou/homebrew/bin/python3.14` | 退出 0；405 Python 测试通过，10 warnings |
| 同一 pipeline 插件检查 | 210 源 Node 测试；Host/Client 类型检查；48 编译测试及干净重建后的 48 测试通过 |
| 同一 pipeline 离线合同 | 6 份合同检查通过，包含首购 OpenAPI / TS |
| bounded W1/W2/W3 仓测试 | 27 passed，退出 0，峰值 RSS 0.28 GiB |
| 受影响 Python Ruff / contracts._lint | 通过 |
| `git diff --check` | 通过 |

完整日志：`.context/parallel-final/pipeline.log` 与 `warehouse-regression.log`。构建复用原工作区固定 DSH 上游及已有依赖，通过 B0_BUILD_UPSTREAM 与本地 node_modules 链接引用；未复制依赖或安装升级。依赖链接不属于交付清单。未把重复执行的测试数累加为独立用例数。

首购恢复遵循共享内核：RUNNING 的同 key 返回同一个 run；活跃派发不重复启动。宿主崩溃后等待物理退出证据，无法证明成功的原 attempt 收口 FAILED / EXECUTION_UNKNOWN，保留原 run，不自动重算。GET 不执行恢复；宿主调用 tick 或 POST 重试推进。缺商品角色为 run SUCCEEDED + result REJECTED / facts=null，不等于产品查询支持通过。

## 仍开放的层级

首购 native tool/catalog、原生 UI、保存分析与驾驶舱尚未接通或验收，catalog 保持 DEFERRED；候选人群同样未开放。W4 只完成最小客户特征层，完整共享分析层及 W5 发布仍开放。多人容量、千万行性能、真实模型/业务 UAT、公网部署与新远端 CI 均未执行。

两份交接均已收到并复核，没有等待外部交付。原候选 worktree 保持不变；主工作区未跟踪文件未纳入。8000/5173 原演示未停止或重启，后续运行收尾方案见 [协调清单](./PARALLEL-QUERY-W4-INTEGRATION-2026-09-08.md)。未 commit、push、PR、merge 或删除分支。
