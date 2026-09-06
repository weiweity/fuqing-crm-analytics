# 本地 RFM：证据收尾与后续验收边界

日期：2026-09-05。范围：本地源码、隔离机制验证、实施顺序留存。

诊断证据状态：`DONE`（限定上述范围）；性能与产品改造状态：`NOT RUN / NOT IMPLEMENTED`。

**收尾对象是本轮架构诊断证据，不是性能修复。** 旧 PC2 的卡死不再复现或追责；不能把移除该环境写成故障已经修好。本地大规模 SQL、多人使用、Agent 集成与公网均未在本轮验收。

## 1. 已确认的范围决定

- 用户明确：PC2 无需考虑，暂时不用，先本地环境；其他架构方向接受，开始证据收尾。
- 不再请求 PC2 版本、日志或访问权限，也不以它阻塞后续开发。未执行关机、停服、删除或远端配置操作。
- 保留 Vue/FastAPI 产品层；在线服务与重计算隔离，应用状态与分析数据分层。PostgreSQL 面向协作应用状态，分析引擎不凭名称选定。
- 真实归档 DuckDB 不读取、不复制、不迁移、不修改。后续测试使用生成的合成数据，不是抽取或掩码后的真实客户记录。
- 本轮只新增验证脚本与更新文档；不修业务代码、不放宽登录/查询限制、不改端口、不安装 runtime、不提交/推送/部署。

## 2. 证据绑定

| 项目 | 本轮值 |
|---|---|
| 工作树 | `.worktrees/hackathon-mission-mvp` |
| 分支 | `codex/shine-mage-figma-refinement` |
| HEAD | `de2d785f4e0c7abe7fcd8fbb39be7d8c5a0c9642` |
| 未提交状态 | 开始时已有视觉、免登录和方案改动；保留不重置。结论绑定下方文件哈希，不假定 HEAD 包含所有当前代码 |
| 隔离验证宿主 | macOS 26.5.2，arm64，Python 3.14.4 |
| 验证方式 | 标准库 unittest；从实际源码 AST 提取指定函数，注入 fake 依赖，不导入 backend 模块 |
| 未使用 | `.env`、真实数据库、HTTP 服务、浏览器、PC2、模型 API、外部发送 |

相关源文件 SHA256（非数据库哈希）：

```text
6a1ddbfe8ff4cfdb8ebb9319c195e741f9d86eeb7d616ea141f95cf53f57c258  backend/routers/health.py
bc91f5551e09ec40351982f83eec9da7e47085698c9df8b1a116d2dda40d0f2b  backend/services/health/rfm_analysis/analysis.py
5fb1b2eddb34a6e7d3de816a7baa6eed4a48ce3666f4488c6f45f518947b858a  backend/services/rfm/_flow_engine.py
7659973f1c9ce67b1a5cc6a1f1473da2c680d3b7e610a09a8c97d5248c3584f8  backend/services/rfm/r_flow.py
13762e0d2960e2d21ca036de399d7601cf34090222611c94ccd1c97fe9490133  backend/services/rfm/f_flow.py
039d6e6e6add3e4a5e5ac9ddf1fdfd5dde86cf9662b319294178b36e44be2d06  backend/services/rfm/m_flow.py
379836c70bf1bb8b7bf9377d16241f7fbfb0b8d9c0f1a85a2f9dfeaf16f15cce  backend/routers/rfm.py
5dd8bc13871236f71de25b38869231df2322f15ea5258291716ce5081e059b1c  backend/middleware/query_router.py
b3cee3e7ae983f0ee953792978e97214fc43aa15d2c8279d34ad2adf80096f1f  backend/services/dual_conn.py
0cfb7730a29e9edb7c71e0b6741153096b16f7b23ab6297beef1c42d4f518506  backend/middleware/single_user_mode.py
399e040577f6d2a63ab63b839f390f8bea76202d57a27e872e6bea385977dd91  backend/routers/auth.py
912612d53e05d119ad7e36cc8776f2096c05b3e60b53b7064f08375b15aef1d1  frontend-vue3/src/api/index.ts
```

代码变更后须重新运行探针、复核行号与结论。Git 历史/注释里的耗时、内存、watchdog 和测试成绩仅作历史线索，不作为本轮实测。

## 3. 已建立的源码事实

| ID | 已确认事实 | 依据（行号对应上述源码快照） | 不能由此推出 |
|---|---|---|---|
| E01 | 八象限 HTTP 入口传 `allow_live_compute=False`；cache miss 返回 503，不进入三期计算 | [health.py](../../backend/routers/health.py) 196–211；[analysis.py](../../backend/services/health/rfm_analysis/analysis.py) 157–174 | 所有 RFM 端点都已 cache-only，或 503 会自动创建预热任务 |
| E02 | R/F/M 区间缓存未命中仍在一次请求内顺序调用当前期、对比期、再前一期计算；前端实际调用该接口 | [_flow_engine.py](../../backend/services/rfm/_flow_engine.py) 459–486；[flow.ts](../../frontend-vue3/src/api/flow.ts) 52–79 | 具体耗时、物理扫描次数、必然 OOM；这些需真实执行计划和资源测量 |
| E03 | 八象限缓存读取前仍取得数据版本、查询订单数；缓存读取内部会锁内初始化缓存表 | [analysis.py](../../backend/services/health/rfm_analysis/analysis.py) 143–150；[cache.py](../../backend/services/health/rfm_analysis/cache.py) 299–306 | cache hit 完全不查询业务库；也不能仅凭 COUNT 或 DDL 存在断言它是最大瓶颈 |
| E04 | RFM 共用读池；池大小默认 2，实际活跃上限取池大小与并发配置的较小者，等待许可默认最多 5 秒 | [dual_conn.py](../../backend/services/dual_conn.py) 24–29、139–150 | 当前本地实际配置就是 2；5 秒是 SQL 执行超时；全站最多只能有 2 个用户 |
| E05 | Axios 默认等待 30 秒；服务端收到外层取消仍等待工作结束，避免连接被提前复用 | [api/index.ts](../../frontend-vue3/src/api/index.ts) 4–6；[query_router.py](../../backend/middleware/query_router.py) 87–103 | 浏览器超时必然发送相同 ASGI 取消事件；查询立即中断；可以直接删 shield 来修复 |
| E06 | 普通认证实现同账号单会话，不同账号不互斥；RFM V2 则是另一套按 IP 的进程内租约 | [auth.py](../../backend/routers/auth.py) 534–544；[single_user_mode.py](../../backend/middleware/single_user_mode.py) 62–63、396–399、500–523 | DuckDB 限制单人登录；该租约覆盖全部 RFM/下钻接口；V2 在本地实际已启用 |
| E07 | 主八象限查询已有手动触发、执行中防重复和 `retry:false` | [ValueTierTab.vue](../../frontend-vue3/src/views/health/ValueTierTab.vue) 300–327；[manualQuery.ts](../../frontend-vue3/src/composables/manualQuery.ts) 17–22 | 进入页面就必然并发多条主分析；任何条件下都只可能由按钮触发 |
| E08 | 本地免登录只放行受控 synthetic Mission，旧 CRM/RFM 不因此匿名开放 | [本地免登录说明](./README.md)；[local_demo_access.py](../../backend/services/local_demo_access.py) | 当前免登录演示就等于已接入旧 RFM，或允许复用真实 CRM 为公开演示数据源 |

原先候选故障链“冷重算 → 客户端停止等待 → 后台仍占资源 → 后续请求受阻”具备代码层面的机制依据，但没有在 PC2 或本地真实规模复现。PC2 已移出范围，不再要求补齐它；后续只验证本地目标架构。

## 4. 可重复运行的隔离探针

入口：[verify_rfm_execution_contract.py](../../scripts/diagnostics/verify_rfm_execution_contract.py)。这是现状刻画测试，不是修复后的回归验收，也不等同项目全量 pytest。

```bash
cd "/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/.worktrees/hackathon-mission-mvp"
/Users/hutou/homebrew/bin/python3.14 -B scripts/diagnostics/verify_rfm_execution_contract.py
```

探针仅执行提取的函数控制流。数据库连接、缓存读写、周期计算等由 fake/stub 替代；源模块顶层配置、导入和后台启动不执行。输出包括被测源码哈希。若源码需要新增依赖，测试应失败并要求复核，不回退导入整个项目。

本轮由实现 Agent 连续复跑两次后，主代理阅读全部脚本并独立复跑一次；最终结果 **12 tests / OK**，退出码 0。三个维度分别以 subTest 验证，不将 subTest 另计为测试方法数。

| 测试组 | 测试方法数 | 结果 | 具体观察 |
|---|---|---|---|
| 八象限 | 3 | PASS | 缓存命中直接返回；cache-only miss/缓存异常不执行三期；fake 连接仍观察到 COUNT 调用 |
| R/F/M 区间 | 3 | PASS | 命中不计算；miss 按三期顺序调用；第二期失败不调用第三期、不缓存半成品 |
| 外层 KV 包装 | 2 | PASS | 命中不进入服务；miss 先计算再尝试写缓存。真实写入是否成功不在此测试范围 |
| 请求工作等待/取消 | 4 | PASS | 正常完成、正常失败、单次取消后等待、取消后工作失败保留取消语义 |

最终复跑输出摘录：

```text
Ran 12 tests in 0.033s

OK
```

`0.033s` 仅为 fake 探针执行时间，绝不是 RFM 查询速度。脚本 SHA256：`f57b681854008b1afea2d5c688cd66248b0e2f3ae180697f61eae3a52b48551b`。三期 miss 测试在第三次调用用 sentinel 停止，不执行 SQL 或验证完整结果；取消测试使用 asyncio Event，不是原生数据库线程中断验证。

文档核验：本轮 5 份文档的 72 个本地链接目标均存在；12 个源码哈希及脚本哈希与磁盘一致；结果占位已清除。`git diff --check` 与两个新文件的 `git diff --no-index --check /dev/null <file>` 均通过。链接检查只验证本地文件目标，不冒充远端 URL 或所有标题锚点可用。

独立 Agent 只读复核通过：未发现性能/修复夸大、PC2 遗留前置或 G1/G2 循环依赖。该复核不计为新增测试运行。

这组测试不覆盖：真实 SQL 的数值与速度、缓存文件/事务完整性、实际浏览器断连、ASGI 全链、原生查询中断、进程 RSS/临时磁盘、多人吞吐、匿名安全全量回归。

## 5. 外部交叉验证与推断边界

核验日期：2026-09-05。来源互相独立，不把同一组织的官网与 GitHub 算成两方。

| 设计判断 | 独立依据 | 适用边界 |
|---|---|---|
| 长任务从网页同步等待中拆出，先受理再查状态/结果 | [微软异步请求-响应模式](https://learn.microsoft.com/en-us/azure/architecture/patterns/asynchronous-request-reply)；[AWS 异步任务模式](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/process-events-asynchronously-with-amazon-api-gateway-amazon-sqs-and-aws-fargate.html) | 两方都给出请求、后台任务、结果查询分离的实现参照；本地不必采购其云服务，也不照搬无界运行配置 |
| 查询耗时与资源问题应测量执行计划，增加连接/线程不保证提速 | [DuckDB 调优指南](https://duckdb.org/docs/current/guides/performance/how_to_tune_workloads)；结合上面微软/AWS 的执行隔离模式 | DuckDB 提供引擎内部依据，另两方提供架构隔离依据，属于互补证据，不是三方都证明 PostgreSQL 更快 |

微软还明确区分受理与完成、幂等重放与再次入队，以及取消指令到达后台后才更新取消状态；本项目据此把业务运行、计算执行和客户端等待分开建模。AWS 示例也把 job ID、队列、执行器与持久结果分开。两者支持模式选择，不证明本项目已经实现或达到某个 SLA。

本项目推断：多个老板页面与数字员工应共用受控的结果/任务服务，而不是分别扫描订单库。该建议来自 E01–E07 与上述模式对照；是否保留 DuckDB 在线查询、是否采用 PostgreSQL 分析层，仍需相同工作负载实测。

## 6. 收尾结论与下一项任务

| 检查点 | 状态 |
|---|---|
| 本地优先、PC2 移出范围 | 已确认，不再是阻塞项 |
| 两条 RFM 链路、登录与查询租约区别 | 源码证据已建立 |
| 隔离控制流测试 | 12 tests / OK；主代理已独立复跑 |
| 真实规模查询/本地多人性能 | NOT RUN，不在本轮证据完成率内 |
| RFM 业务代码修复、异步执行层、PostgreSQL 部署 | NOT IMPLEMENTED，本轮未修改 |
| Hermes/模型集成、公网、真实触达 | NOT RUN，保持原边界 |

下一项是 [本地数据面 P01–P06](./RUNTIME-VALIDATION-PLAN.md)：先建立合成 RFM 金标准，再验证缓存/任务分流、同条件去重、控制请求可用、取消与资源预算。通过后再接正式 AI 工具，不重复展开已经采纳的产品路线。

主方案已同步此顺序，见 [G0–G2](./UNIFIED-ANALYTICS-PLAN.md)。身份权限和算力配额应分别治理；本轮不通过放开登录、增加连接、延长浏览器超时或仅新增一层缓存来冒充架构修复。
