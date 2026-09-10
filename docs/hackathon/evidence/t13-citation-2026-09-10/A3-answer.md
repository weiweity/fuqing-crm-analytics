## 结论

已用当前合成快照完成 2026 年 8 月整月 GSV 与 2025 年 8 月同期的同比核算，两次结果均为实际计算（非估算）。

| 项目 | 数值 |
|---|---|
| 本期 2026-08-01 ~ 2026-08-31 GSV | **410**（分，CNY；3 单 / 3 客） |
| 基期 2025-08-01 ~ 2025-08-31 GSV | **305**（分，CNY；3 单 / 3 客） |
| 差额（本期 − 基期） | **+105** |
| 同比变动比例 | **+0.3442622950819672（约 +34.43%）** |

口径按要求锁定：`metric_type=GSV`、`timezone=Asia/Shanghai`、`comparison_mode=YOY_SAME_PERIOD`、销售范围与历史范围均为 `ALL`（通道/商品列表为空）、`sample_mode=INCLUDE`（保留小样，`sample_channel_ids=null`，未剔除任何派样渠道）、`end_bound=INCLUSIVE_CALENDAR_DAY`（含 8 月 31 日）。

## 可核验来源

单步计算（能力 `diag.yoy`，步骤状态 `PARTIAL`，执行模式 `COMPUTED_SYNTHETIC`）：

- `result_id`：`result_diag_367feb5ab5be7f7c200eabb6401cac25cba4afbee251d0c9`
- `run_id`：`run_diag_367feb5ab5be7f7c200eabb6401cac25cba4afbee251d0c9`（与 `result_id` 是两个独立标识，此处各自抄录原值）
- `evidence_digest`：`7a5ac0ed988b1fdb284f35983045527ccc84717fc906dbeb4ed4a7cf62b066c5`
- `filter_hash`：`59a9e266efdb0a7a3a3cbac15c9db5cef171e12925062d813e92ff8f6c9edc2a`
- 查询：`competition_gsv_comparison` / `competition-gsv-query/v1`；指标：`competition-gsv-metric/v1`；facts schema：`competition-gsv-facts/v1`；`completeness=COMPLETE`，`row_count=2`。

确认 `resolved_condition` 原样回显了上表口径（含 `cutoff=2026-07-31`、`data_cutoff_policy=T_PLUS_1_YESTERDAY`、`leap_day_alignment=CLAMP_TO_MONTH_END`）。

## 数据边界

- 数据源：合成快照 `synthetic-diagnosis-202608-v1`（`synthetic-diagnosis-data/v1`），`contains_real_data=false`，数据截止 2026-08-31，仓库时点 `2026-08-31T16:00:00+00:00`（即北京时间 2026-09-01 00:00），快照发布于 2026-09-01。**不是真实经营结论**。
- 金额单位：分（minor unit）/ CNY；GSV 按订单净额计算，含退款抵扣。
- 样本极小（每期各 3 单、3 客），同比比例对单笔订单极度敏感，只能作为口径一致的算术结果读，不能当趋势结论。
- 同比按同名整月对齐，未做闰日平移（8 月不涉及）；本期/基期均为完整自然月，非 WTD/MTD 截断。
- `sample_mode=INCLUDE` 已生效，`sample_history_recomputed=false`；`sample_channel_set_status=UNKNOWN`（真实派样渠道全集未确认），因此本次无需也不得猜测派样渠道集合。
- 仍为 `UNKNOWN`：派样渠道全集、会员历史（`MEMBER_HISTORY`）；渠道贡献、小样剔除重算、新老客、会员交叉、产品、RFM、固定 cohort 与三种未回购在当前环境均为 `NOT_CONNECTED`。
- 因此 `chain_status=PARTIAL`、`analysis_complete=false`：**仅完成双期 GSV 同比这一环，完整诊断链未完成**，不得据此断言投放 ROI 或最优预算。

本次只做诊断，未创建看板、未生成行动草稿、未发送任何消息；工具预算使用 2/12。另说明：若再用 `diag.gsv` 复算本期，与本次结果一致只能说明同源返回一致，不构成独立复核。
