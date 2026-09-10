## 结论

| 项目 | 数值 |
|---|---|
| 2026-07 整月 GSV（本期） | 0 |
| 2025-07 整月 GSV（去年同期） | 0 |
| 差额 | 0 |
| 同比增幅 | **无法计算** |
| 无法计算原因 | `change_ratio_unavailable_reason = ZERO_COMPARISON_GSV`（对比期 GSV 为 0，分母为零，`change_ratio=null`） |
| 金额单位 | **UNKNOWN**（本步 `facts.money_unit = {"status":"UNKNOWN","currency":null,"amount_unit":null}`） |

两期的订单数、客户数也均为 0。按证据策略，此处**不展示 0%**——缺分母时不得用 0% 顶替；金额按原数值报告，不称“元 / CNY / 分”。

## 条件变更与继承

`condition_trace.mode = EXPLICIT`：

- **继承（未重发，按上次条件沿用）**：`sales_scope`（`ALL`）、`history_scope`（`ALL`）、`sample_mode`（`INCLUDE`）、`sample_channel_ids`（`null`），以及 `data_snapshot_ref`、`as_of`、`rule_version`。与你的要求一致：销售/历史范围仍为全部，仍保留小样、不剔除派样渠道。
- **变更**：`current_period` → `2026-07-01~2026-07-31`；`comparison_period` → `2025-07-01~2025-07-31`（两者同时提交，符合“改本期必须同时给对比期”的约束）。`comparison_mode` 本次随补丁重发，取值仍为 `YOY_SAME_PERIOD`（语义未变）。
- **连带重算**：`cutoff` 由 `2026-07-31` 变为 `2026-06-30`（分析 start 前一天），`timezone` 仍为 `Asia/Shanghai`，`leap_day_alignment=CLAMP_TO_MONTH_END`。
- 新的 `filter_hash`：`824b7d4857dd457f2652a036df24d2d7f716c7e9e141feb3bbfc2132f4ef50b5`（与上一步不同，说明条件确已变化，不是换标签复用旧结果）。

## 标识（分别引用原值）

- `result_id` = `result_diag_d6dc526c45233092c37740f5146c85ee4b3e7f288c4a39d6`
- `run_id` = `run_diag_d6dc526c45233092c37740f5146c85ee4b3e7f288c4a39d6`
- `evidence_digest`（即本页 checksum）：`07f1207b09142aa38cfe1442feb3d3497d9dd437a2b1ec525bf356ea237722de`

两个字段按后端原值分别抄录，未做前缀替换推导。

## 状态说明

- `completeness=COMPLETE`、`row_count=2`、`empty_reason=null`：本期是**真实算出 0**，而不是 `EMPTY` 无样本状态；两者含义不同，我按后端给出的 COMPLETE + 0 报告，并把“无法计算同比”的原因归于分母为零。
- 本次仍读取同一快照 `synthetic-diagnosis-202608-v1`（`data_digest` 与上一步相同），因此这两步是同一数据源下的两次计算，不构成独立复核。
- **计算结果已保存**：`analysis_persisted=true`（`analysis_id=analysis_diag_d6dc526c45233092c37740f5146c85ee4b3e7f288c4a39d6`）。
- **未成板**：未调用 `board.single_cockpit`、`board.batch` 或 `competition_growth_patch`，也未创建/发送行动草稿。
- `chain_status=PARTIAL`、`analysis_complete=false`：仅完成 GSV 双期一步，完整诊断链未完成；`SAMPLE_CHANNEL_SET`、`MEMBER_HISTORY` 仍为 UNKNOWN。剩余预算：12 次中已用 3 次。
