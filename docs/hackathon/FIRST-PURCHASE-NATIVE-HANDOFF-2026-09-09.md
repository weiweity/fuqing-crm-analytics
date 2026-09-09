# 首购原生闭环交接（2026-09-09）

给后续接手人（Codex 或其他）用。本地未提交，无 commit/push/PR 授权。不替代 [闭环交付记录](./FIRST-PURCHASE-NATIVE-LOOP-2026-09-09.md)。

## 位置

- 工作位置：`/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/.worktrees/parallel-query-w4-integration`
- 分支：`codex/parallel-query-w4-integration`
- HEAD：`3ec1c866aa794baee6c0ebb7205aee375db1a49f`（改动都在未提交工作区）
- 交付指纹：`.context/parallel-round2-review/DELIVERY.sha256`
- 证据包：`.context/parallel-round2-review/evidence-2026-09-09/`

只读候选，禁止在那里返修：

`fuqing-crm-analytics/.claude/worktrees/codex-first-purchase-native-r2`

候选清单 SHA256：`fc1589ca678b75da363146e5c8bf377ba678e6c9d74d59bbb5c4528788df7446`。不要用旧 `.context/parallel-final/FILES.sha256` 覆盖本工作区。

## 已完成

1. 共享 `RunStore` family=`first_purchase` 持久绑定 principal/session/native request/run/attempt/method digest。prompt 在 execute 前即有真实 `run_*`。
2. 同键在途 `IN_FLIGHT` 202；取消找真实 run；无活动任务 `NO_ACTIVE_RUN`；`RunDispatcher.tick`；GET 只读。
3. `FIRST_PURCHASE_RECEIPT_LIMIT` 已导出。decoder 对齐 Python 合同。编译后卡片走 `renderFirstPurchase`。
4. 合成路径：native 成功查询 → 只传 `created_from_run_id` 保存 → 重读 → 加入驾驶舱 → 重读。REJECTED/未完成/伪造 facts/取消不得保存。
5. catalog：`first_purchase` = `SUPPORTED_CONTRACT`；候选人群仍 `DEFERRED`。未把 W4 接入首购。
6. OCR 委托 Medium 已修：`accept()` location 用 `/api/v1/analytics-first-purchase/runs/{run_id}`；共享来源 422 文案按当前族 codec 生成。

## 接手约束

- Python：`/Users/hutou/homebrew/bin/python3.14`
- Node：`/Users/hutou/homebrew/opt/node@24/bin/node`
- pipeline：`B0_BUILD_UPSTREAM` 指向主仓库已准备的 pinned checkout，只读 `--check`。不要安装或改写固定 DSH 上游。
- 禁止 commit/push/PR、真实模型、真实数据、停 8000/5173、编辑候选 worktree。
- 原生浏览器 stub 合成闭环已补验 PASS；只读复用固定 upstream，详见闭环记录。真实模型仍未调用。
- 干净重建会把插件拷到 `.context/dsh-b0/clean-build-*`；首购编译后卡片测试必须向上查找仓库 fixtures。

## 建议下一步（等用户点名）

1. 复核代码，只报真实缺陷。
2. 原生浏览器合成验收已完成；真实模型与真实业务验收仍需另定范围。
3. 若要 Git 发布：先停，等明确 commit/push/PR 授权。
