## 结论

| 项目 | 数值 |
|---|---|
| 2026-08 整月 GSV（本期） | 410 |
| 2025-08 整月 GSV（去年同期） | 305 |
| 差额 | +105 |
| 同比增幅 | 34.42622950819672%（raw ratio 0.3442622950819672 × 100） |
| 金额单位 | **UNKNOWN**（本步 `facts.money_unit` = `{"status":"UNKNOWN","currency":null,"amount_unit":null}`） |

金额按原数值报告，不称“元 / CNY / 分”。本期与对比期订单数、客户数均为 3 / 3。

## 依据

- 能力：`diag.gsv`（`SUPPORTED`，`execution_mode=COMPUTED_SYNTHETIC`），`condition_mode=EXPLICIT`。
- 生效条件（`resolved_condition`）：`metric_type=GSV`，`timezone=Asia/Shanghai`，`current_period=2026-08-01~2026-08-31`，`comparison_period=2025-08-01~2025-08-31`，`comparison_mode=YOY_SAME_PERIOD`（`leap_day_alignment=CLAMP_TO_MONTH_END`），`sales_scope.kind=ALL`、`history_scope.kind=ALL`，`sample_mode=INCLUDE`、`sample_channel_ids=null`、`sample_history_recomputed=false`。小样保留、未剔除派样渠道，与要求一致。
- 数据源：`synthetic-diagnosis-202608-v1`（`contains_real_data=false`，`data_through=2026-08-31`），`cutoff=2026-07-31`。
- `filter_hash`：`59a9e266efdb0a7a3a3cbac15c9db5cef171e12925062d813e92ff8f6c9edc2a`
- `completeness=COMPLETE`，`row_count=2`，`evidence_digest`：`2b7992fbca99eeab8118f34565c8b5dd467fd4957dcf41b7bd3dbeac5c4cbf73`

## 标识（分别引用原值）

- `result_id` = `result_diag_b2a6ca3444c0fdff61171b489c01b1cfccc1713d24abbeb3`
- `run_id` = `run_diag_b2a6ca3444c0fdff61171b489c01b1cfccc1713d24abbeb3`

两者是不同字段，此处按后端原值分别抄录；未做任何前缀替换推导。

## 持久化与诊断链状态

- **计算结果已保存**：本步返回 `analysis_persisted=true`（并给出 `analysis_id=analysis_diag_b2a6ca3444c0fdff61171b489c01b1cfccc1713d24abbeb3`）。这是工具自身的自动持久化，不等于“未写入任何文件”。
- **未创建看板**：本次未调用 `board.single_cockpit` / `board.batch` / `competition_growth_patch`，未生成任何驾驶舱或 patch。按你的要求，没有创建看板、没有发送草稿（`action.draft` 也未调用，其能力本身为 `NOT_CONNECTED`）。
- **完整诊断链未完成**：本步 `chain_status=PARTIAL`、`analysis_complete=false`。仅完成 GSV 双期同比一步；渠道下降贡献（`diag.channel`）、小样敏感性（`diag.sample_exclude_current`）、新老客、会员交叉、产品、RFM 均为 `NOT_CONNECTED`，固定去年 cohort 本期回购与三种未回购也均为 `NOT_CONNECTED`。因此不得声称完整诊断链已完成。
- 已知 `unknown_flags`：`SAMPLE_CHANNEL_SET=UNKNOWN`（未确认真实派样渠道全集）、`MEMBER_HISTORY=UNKNOWN`；本次结论仅限显式小型合成快照，不代表真实经营结论。剩余预算：12 次中已用 2 次。

如需继续，下一步可考虑渠道下降贡献或（在你显式指定派样渠道后）小样剔除敏感性，但这些能力当前为 `NOT_CONNECTED`，会如实拒答而不是给数。
