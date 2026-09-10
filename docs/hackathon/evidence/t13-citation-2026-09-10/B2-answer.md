已完成查询。结论：**2026-08 比 2025-08 多**，净额上升 105，约 +34.4%。

## 结果

| 项 | 数值 |
|---|---|
| 本期 2026-08-01 ~ 2026-08-31 | **410** |
| 对比期 2025-08-01 ~ 2025-08-31 | **305** |
| 变化额 | **+105** |
| 变化比例 | **+34.43%**（后端 raw ratio 0.3442622950819672，按 B0 0–1 合同换算） |

两期都是 31 天，日期边界均为 `INCLUSIVE_CALENDAR_DAY`，无闰日平移。

## 查询来源

- 能力：`diag.gsv`（能力目录 `SUPPORTED`），条件模式 `EXPLICIT`，一次运行内含双期比较
- 条件：`metric_type=GSV`、`timezone=Asia/Shanghai`、`comparison_mode=YOY_SAME_PERIOD`、`sales_scope.kind=ALL`、`history_scope.kind=ALL`、`sample_mode=INCLUDE`、`sample_channel_ids=null`
- 后端回显标识：`result_id` = `result_diag_37395f8f67fe570a5a7a218291c247a21cc33f52cb4e1fd7`；`run_id` = `run_diag_37395f8f67fe570a5a7a218291c247a21cc33f52cb4e1fd7`
- `evidence_digest` / `filter_hash` 均为 `ce5d1dfebdd34ac7c18faab7cc852cddd54b6644d66aeea026f48da0f60bf3b9` / `59a9e266efdb0a7a3a3cbac15c9db5cef171e12925062d813e92ff8f6c9edc2a`
- `completeness=COMPLETE`（结果集完整，2/2 行），`cutoff=2026-07-31`，数据快照 `synthetic-diagnosis-202608-v1`，`contains_real_data=false`

## 局限

1. **链未完成**：`chain_status=PARTIAL`、`analysis_complete=false`。只跑通 GSV 双期计算，渠道贡献、小样、新老客、会员、产品、RFM、固定 cohort、未回购均未执行（相关能力多为 `NOT_CONNECTED`），因此**不能**说明这 105 的增量来自哪里。
2. **不能当经营结论**：仅显式小型合成快照，非真实业务数据。
3. **样本极小**：每期仅 3 单 / 3 客，单笔订单即可显著改变比例，百分比不宜作趋势解读。
4. **小样按 INCLUDE 计入**，符合本次要求；但 `sample_channel_set_status=UNKNOWN`，派样渠道全集未确认，故未做任何剔除，也无法验证“若剔除会怎样”。`sample_history_recomputed=false`（INCLUDE 下无需重算）。
5. **金额单位未在 facts 中回显**：返回体没有 `currency`/`amount_unit` 字段，我只按原值抄录；能力目录注明合成仓按 minor 单位存储、币种 CNY，未做换算。
6. **会员历史 UNKNOWN**，`MEMBER_HISTORY`、`SAMPLE_CHANNEL_SET` 两个 `UNKNOWN` 标志已由后端标注。
7. 本次为纯分析：**未成板、未建行动草稿、未发送**，未写入任何文件。

预算用量 2/12。
