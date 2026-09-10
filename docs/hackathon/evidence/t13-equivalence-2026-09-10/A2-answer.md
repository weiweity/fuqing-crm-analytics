## 结论

2026 年 8 月整月 GSV **410**，2025 年 8 月整月 GSV **305**，同比 **+105**，同比比例 **0.3442622950819672（+34.43%）**。两个独立能力步骤（`diag.gsv`、`diag.yoy`）返回完全一致的数值与 `data_digest`。

| 项目 | 2026-08（本期） | 2025-08（对比期） |
|---|---|---|
| 窗口 | 2026-08-01 ~ 2026-08-31 | 2025-08-01 ~ 2025-08-31 |
| 边界 | INCLUSIVE_CALENDAR_DAY | INCLUSIVE_CALENDAR_DAY |
| through_date（后端回显实际执行窗口） | 2026-08-31 | 2025-08-31 |
| GSV | 410 | 305 |
| 订单数 / 客户数 | 3 / 3 | 3 / 3 |
| 差额 | +105 | — |
| 同比比例 | 0.3442622950819672（比值口径 0–1，即 +34.43%） | — |

比例口径：合同按 **raw ratio 0–1** 回传，未做 0–100 命名套用；105 ÷ 305 = 0.344262…，分母非 0，`change_ratio_unavailable_reason` 为 `null`。

## 条件与可核验来源

- 条件：`metric_type=GSV`，`timezone=Asia/Shanghai`，`comparison_mode=YOY_SAME_PERIOD`，`sales_scope=ALL`、`history_scope=ALL`（两者分别保存，渠道/商品列表均为空），`sample_mode=INCLUDE`，`sample_channel_ids=null` —— 按你的要求保留小样、未剔除任何派样渠道，也没有猜派样渠道集合。
- `resolved_condition.cutoff = 2026-07-31`（分析 start 前一天），`as_of/warehouse_as_of = 2026-08-31T16:00:00Z`（= 2026-09-01 00:00 +08:00），`source_tense=PUBLISHED_SNAPSHOT`，`data_cutoff_policy=T_PLUS_1_YESTERDAY`。
- `filter_hash = 59a9e266efdb0a7a3a3cbac15c9db5cef171e12925062d813e92ff8f6c9edc2a`（两步一致）。
- `data_digest = 4ed2e7e41226acd33034e931680a998c1399fb5ebda53acd9dec3a70b03fd21c`（两步一致）。
- 步骤 1（`diag.gsv`，EXPLICIT）：`result_id/run_id = result_diag_0fc1336f3e38099d399fb6e3482c206ec322ed4bedf1ffc6`，`evidence_digest = ce5d1dfebdd34ac7c18faab7cc852cddd54b6644d66aeea026f48da0f60bf3b9`。
- 步骤 2（`diag.yoy`，INHERIT，用于独立复核）：`result_id/run_id = result_diag_ed30c88f875d0454c217e3c16c5709ad32e49abe6973d953`，`evidence_digest = 7a5ac0ed988b1fdb284f35983045527ccc84717fc906dbeb4ed4a7cf62b066c5`。
- `completeness=COMPLETE`、`row_count=2`、`page.complete=true`，非 `EMPTY`。

## 数据边界

- **合成快照**：`data_snapshot_ref=synthetic-diagnosis-202608-v1`，`data_version=synthetic-diagnosis-data/v1`，`contains_real_data=false`，`data_mode=SNAPSHOT`。数值仅代表该小型合成快照，不是真实经营结论。
- **样本极小**：每期仅 3 单、3 个客户。+105 / +34.43% 在这个样本量上不具备经营含义，不能据此推断趋势或投放效果；GSV 变化只用于定位方向，不等于投放 ROI 判断。
- **链路未完成**：`chain_status=PARTIAL`、`analysis_complete=false`。本次只完成 GSV 双期同比；渠道下降贡献、新老客、会员、产品、RFM、固定去年 cohort 本期回购、三种未回购在能力目录中为 `NOT_CONNECTED`/`NOT_IMPLEMENTED`，因此**不能**声称完成完整诊断链，也无法说明增长由哪个渠道驱动。
- **UNKNOWN 项**：`SAMPLE_CHANNEL_SET`（未确认真实派样渠道全集）、`MEMBER_HISTORY`（当前合成源不提供会员历史）均为 UNKNOWN。因你明确保留小样且未指定渠道，这两项不影响本期口径，但使“剔除小样”类对照不可用（`sample_history_recomputed=false`）。
- **单位未在结果中回显**：事实对象只给出 `gsv: 410 / 305`，未回显 currency/unit 字段；能力目录对合成仓标注 `amount_unit minor / currency CNY`。因此 **410/305 的具体金额单位（元或分）在本次证据中无法核验**，我只按后端回显的原始数值引用，不做换算或前缀 ¥。
- **日期对齐**：两期都是 31 天整月，`leap_day_alignment=CLAMP_TO_MONTH_END` 未触发；对比期严格使用 2025-08-01~2025-08-31，未做闰日平移。
- `GSV 按订单净额计算；商品过滤下退款沿现有订单级规则抵扣`（本次未用商品过滤）。
- GSV 口径为订单净额；本快照 `feature_as_of=null`。

## 边界说明

按要求仅执行诊断：未创建看板、未生成行动草稿、未发送任何消息、未保存快照；仅两次只读能力步骤，`analysis_persisted=true` 为后端对本次计算的既有记账，非我发起的保存动作。工具预算：已用 3/12。
