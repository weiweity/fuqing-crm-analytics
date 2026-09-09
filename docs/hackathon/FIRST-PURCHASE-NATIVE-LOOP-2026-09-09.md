# 首购原生闭环本地交付（2026-09-09）

状态：LOCAL_NATIVE_LOOP / UNCOMMITTED。不替代 [第二轮复核](./PARALLEL-ROUND2-REVIEW-2026-09-08.md) 的历史记录。

## 做了什么

- 共享 `RunStore` 允许 `first_purchase` native 受理与 `_query_context`。prompt 在执行前分配真实 `run_*`，绑定 session/request/attempt/method digest。
- adapter/serve/gateway 使用该接口。同键在途返回 `IN_FLIGHT` 202，不报 `TOOL_FAILED`。取消找真实 run；无活动任务返回 `NO_ACTIVE_RUN`，不宣称已停止。宿主 `RunDispatcher.tick` 推进排队任务。GET 只读。
- decoder 按 Python 合同校验转化率、空成熟分母、完整 `resolved_filters`、receipt 的 request/call/查询绑定；超限取消响应流。`FIRST_PURCHASE_RECEIPT_LIMIT` 已导出。
- 编译后卡片走 `loadCardHarness().renderFirstPurchase`；缺少 renderer 失败。拒绝态不断言文案禁 “0%”。
- 原生成功 `run_id` → 保存分析 → 重读 → 加入驾驶舱 → 重读。负例：REJECTED、未完成、额外 facts 字段、取消。
- OCR 委托 Medium：`accept()` location 改为 `/api/v1/analytics-first-purchase/runs/{run_id}`；共享来源校验失败文案按当前族 codec 生成，不再写死渠道族名。

## 验证分层

| 层 | 结果 |
|---|---|
| 模块 / 共享绑定 / native HTTP | PASS：`test_analytics_first_purchase_native.py`（含 location 与来源文案） |
| decoder / 类型检查 | PASS：8 项 decoder 单测；host/client 正式类型检查 |
| 编译后 DOM | PASS：`first-purchase-query-card.test.mjs` ×2；干净重建 49 项 |
| 保存→驾驶舱合成 HTTP | PASS：两次独立 `run_id`，合同均为 `first_purchase_product_path` / `analytics-first-purchase-cockpit/v1` |
| 统一 pipeline `--check` | PASS：428 Python + 223 源 Node + 编译后 49（含干净重建；OCR Medium 修复后重跑） |
| 原生浏览器 DSH stub | **PASS**：runtime-FDP682，原生查询→总结→保存→驾驶舱→脱离会话重读 |
| 真实模型 / 真实数据 / OCR | **NOT RUN**（无授权） |

## 浏览器补验与历史限制

2026-09-09 Codex：只读 symlink 复用固定 upstream（d347e703），未安装/改写上游。浏览器发现成功后总结步被拒；已修为首购 SUCCEEDED 可读总结上下文，原预算、deadline、身份与方法绑定继续有效，终态方法读取仍拒绝。新增预算耗尽回归。成功实例 runtime-FDP682；旧失败 runtime-NWkSxS 保留。

浏览器操作结果：1 run、1 physical worker、1 analysis、dashboard 两版本（创建与加入）。控制台包含网关对上游 inventory/inspect 等非授权接口的 403，未宣称无控制台错误。证据 browser-report.json / browser-sessionless.txt / browser-cockpit.png。

以下为补验前失败与仍未运行项目：

- 原生浏览器 DSH：`scripts/dsh-b0/serve.mjs --native-first-purchase` 因本 worktree 没有 `.context/dsh-b0/upstream`，在 `git -C …/upstream rev-parse HEAD` 失败退出。pipeline `--check` 使用只读 `B0_BUILD_UPSTREAM` 指向主仓库已准备的 pinned checkout，不把该覆盖写进 serve，也不在 worktree 安装/改写固定上游。
- 真实模型调用：无授权。
- OCR 全量：不重跑（本轮超时、退出码 1 不是通过）。
- Git commit/push/PR：无授权。
- 8000/5173 演示：未触碰。

本地证据包：`.context/parallel-round2-review/evidence-2026-09-09/`（pipeline 日志、native 测试、保存闭环 JSON、浏览器补验证据；旧 NOT RUN 保留为历史）。交接说明：[HANDOFF](./FIRST-PURCHASE-NATIVE-HANDOFF-2026-09-09.md)。

候选人群 catalog 仍 DEFERRED。未把 W4 接入首购，未扩展 W5。
