# 首购共享 worker / HTTP 本地候选

本候选沿用 `analytics-first-purchase-path/v1` JSON 金标准。独立 HTTP factory 使用共享 RunStore（family=first_purchase）、WorkerManager、继承执行 lease 和同一预算/事件/退出规则；没有第二个任务数据库或模型循环。旧 ledger 候选已移除。

## 装配

由明确授权的宿主注入小型 synthetic snapshot、私有状态目录、固定资源 profile、身份 registry 与当前 actor resolver：

```python
from backend.analytics_first_purchase_fixture import create_first_purchase_fixture
from backend.services.analytics.jobs import RunStore
from backend.services.analytics.first_purchase.runtime import FirstPurchaseRuntime
from backend.analytics_first_purchase_app import create_first_purchase_app

fixture = create_first_purchase_fixture(snapshot_dict)
store = RunStore(private_state_directory, resource_profile, family="first_purchase")
runtime = FirstPurchaseRuntime(store, fixture, resolve_current_actor)
app = create_first_purchase_app(runtime, identity_registry)
```

状态目录必须预先以 0700 创建；不兼容旧 B0/渠道或临时首购 ledger 数据库，不自动迁移。fixture 使用规范 JSON，当前限制 24000 字节，属于小合成验证，不支持千万行内联 payload。principal 能力为 run:create/read/cancel，数据域为 first-purchase-fixture；resolver 必须与身份 registry 使用同一授权主源并反映当前撤权。permission_scope 由共享 store 的 owner+data_scope 绑定生成，不接受客户端覆盖。

## HTTP

| 方法 / 路径 | 输入 / 结果 |
|---|---|
| POST /api/v1/analytics-first-purchase/runs | Bearer + Idempotency-Key；body 为 FirstPurchaseQueryRequest；完成返回 200，仍在排队/运行返回 202，均为 FirstPurchaseKernelSnapshot |
| GET /api/v1/analytics-first-purchase/runs/{run_id} | 当前 owner 的快照；只读，不创建 run 或启动 worker |
| POST /api/v1/analytics-first-purchase/runs/{run_id}/cancel | Bearer + Idempotency-Key + If-Match；body={"reason":"USER_REQUEST"}；保留成功结果，运行中先记录取消并等待实际退出 |

POST 做一次有界 queue turn；忙时不争抢执行。宿主需按自己的生命周期调用 runtime.tick() 消费排队任务或重启后核对，模块不自动开启常驻线程。客户端重试必须保留原 key；GET 不推进队列。没有守护进程或服务安装。

只读身份创建返回 403；跨 owner 读取 404；同键异体 409；缺 key/版本 428；无效合同 422；内核未配置/未就绪 503。数据库 busy 遵循共享 503 重试规则，不绕过事务超时。

缺商品角色为 SUCCEEDED + result.status=REJECTED，facts=null；表示计算得出合同拒绝，不是经营分析成功。空成熟分母保留 null。结果在真正子进程退出、lease 释放且 codec/冻结条件验证后才能落盘。

## 恢复与边界

同键并发通过共享调度槽和适配器文件锁只执行一次。父进程退出后：活跃 lease 未释放则不释放槽；确认退出但无完整成功步骤则原 run FAILED/EXECUTION_UNKNOWN，不重算、不新建任务；已有完整成功步骤可按共享 observe 规则恢复终态。旧临时 ledger 的“重算 RUNNING”行为不再采用。

首购 native 走共享 prompt/run-context/execute：受理时写入 principal/session/request/run/attempt/method digest，禁止 request_id 冒充 run_id。`serve.mjs --native-first-purchase` 装配独立 HTTP、gateway `/b0/runs` 与资产路径。catalog 的首购族已按合成执行路径升为 SUPPORTED_CONTRACT；候选人群仍 DEFERRED。原渠道保存/驾驶舱保持渠道专属。保存只接受可信 `created_from_run_id`，REJECTED/未完成/取消不得落有效分析。见 [第二轮复核](./PARALLEL-ROUND2-REVIEW-2026-09-08.md) 的历史阻断与本轮本地修复。

W4 作为独立只读客户特征模块导入；日期推进只改变 recency，净额仍属仓 as_of。features_sha256 是实际 JSONL UTF-8 字节摘要；序列化前后行漂移被拒绝。不自动调用 W4 更新首购或 W1–W3 发布，不代表 W5。

离线生成/核验：`node scripts/dsh-b0/first-purchase-contract.mjs --write|--check --python /absolute/python3.14`，Node 24、现有锁定 openapi-typescript/TypeScript。统一 pipeline 已包含新合同和首购/W4 测试；不启动 CRM。
