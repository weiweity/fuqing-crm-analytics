## 结论

2026-08-01～08-31 的 GSV **多于** 去年同期：本期 410，对比期 305，**增加 105（+34.43%）**。

| 口径 | 期间 | GSV（净额） | 订单数 | 客户数 |
|---|---|---|---|---|
| 本期 | 2026-08-01 ～ 2026-08-31（含端点） | 410 | 3 | 3 |
| 对比期 | 2025-08-01 ～ 2025-08-31（含端点） | 305 | 3 | 3 |
| 变化 | — | **+105** | 0 | 0 |

变化比例 = 105 / 305 = 0.3442622950819672（raw ratio，0–1 口径，即 **+34.43%**）。

## 条件与查询来源

- 条件（EXPLICIT 首提，后端回显确认）：`metric_type=GSV`、`timezone=Asia/Shanghai`、`comparison_mode=YOY_SAME_PERIOD`、`sales_scope.kind=ALL`、`history_scope.kind=ALL`、`sample_mode=INCLUDE`、`sample_channel_ids=null`；`event_time=2026-08-31`、`source_tense=PUBLISHED_SNAPSHOT`、`cutoff=2026-07-31`、`data_cutoff_policy=T_PLUS_1_YESTERDAY`。
- 查询来源：`competition_growth_step`，`capability_id=diag.gsv`，`request_id=req-b-equiv-001`；`result_id/run_id=result_diag_c5a1e368967791c1af667b4aad15535c6df8115ec8b5e13b`，`evidence_digest=ce5d1dfebdd34ac7c18faab7cc852cddd54b6644d66aeea026f48da0f60bf3b9`，`filter_hash=59a9e266efdb0a7a3a3cbac15c9db5cef171e12925062d813e92ff8f6c9edc2a`，`metric_version=competition-gsv-metric/v1`，`query_version=competition-gsv-query/v1`。
- 快照：`synthetic-diagnosis-202608-v1`（`contains_real_data=false`），`completeness=COMPLETE`、`row_count=2`、`empty_reason=null`。

## 局限

- **仅双期 GSV 完成**：`chain_status=PARTIAL`、`analysis_complete=false`。渠道下降贡献、新老客、会员交叉、产品、RFM 等步骤在能力目录中均为 `NOT_CONNECTED`，本次未做任何下降/增长归因，也未声称完整诊断链。
- **合成数据**：结论只对显式小型合成快照成立，不代表真实经营结论。
- **单位未回显**：结果未带币种/单位字段；能力目录标注合成仓为 minor/CNY。绝对值不宜与真实业务金额直接比较，变化额与变化比例是同一口径下的相对结论。
- **两个 UNKNOWN**：派样渠道全集 `SAMPLE_CHANNEL_SET=UNKNOWN`（小样按 `INCLUDE` 计入，未剔除、未重算历史）；`MEMBER_HISTORY=UNKNOWN`。
- 同期口径上 2025-08 与 2026-08 均为 31 天，`leap_day_alignment=CLAMP_TO_MONTH_END` 未触发，无需月末钳制平移。
- 未创建看板、未建行动草稿、未发送；本次也未保存任何 SNAPSHOT 资产。
