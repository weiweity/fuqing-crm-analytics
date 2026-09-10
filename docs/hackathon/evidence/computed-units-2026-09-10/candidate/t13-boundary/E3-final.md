重新计算**没有产生任何数值**——三次尝试都被后端拒绝，`EXCLUDE_AND_RECOMPUTE_HISTORY` 在本部署不可用。上一轮 `INCLUDE` 口径的结果仍是唯一有效证据。

## 实际调用与返回

| 尝试 | 提交内容 | 返回 |
|---|---|---|
| `diag.gsv` | 两个 8 月窗 + 全域范围 + `sample_mode=EXCLUDE_AND_RECOMPUTE_HISTORY` + `sample_channel_ids=["CH_SAMPLE"]` | `INVALID_REQUEST`，`http_status=422`，"条件与 competition-condition/v1 不匹配"，`request_id=fbb5912478b24c7d8c94f5607d1626d5` |
| `diag.sample_recompute_history` | 同一条件体 | 同样 `INVALID_REQUEST` 422，`request_id=695e05bee8c840898ae8bc8805b16a62` |
| `diag.sample_exclude_current` | 仅把 `sample_mode` 换成 `EXCLUDE_CURRENT_SALES_ONLY`，其余完全相同 | 通过了条件校验，返回 `NOT_CONNECTED`，`http_status=503`，"当前计算源尚未实现此诊断步骤"，`doc_ref=docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T10`，`request_id=7da1de7dfd014e4b97cc1f6920708cfe` |

## 能力状态结论

- **`EXCLUDE_AND_RECOMPUTE_HISTORY`：不可用。** 第 3 次尝试与第 1、2 次只差 `sample_mode` 一个字段，却从 422 变成 503——说明该枚举值本身没被本部署的 `competition-condition/v1` 校验器接受，后端也没给出字段级 `param`（`param=null`），属于 C0 只定义了枚举、A2 未接线的状态；能力目录中 `diag.sample_recompute_history` 也标注 `NOT_CONNECTED`，`notes` 明确「没有在历史范围剔除小样后重算新老客或 RFM 的旧路径」。
- **`EXCLUDE_CURRENT_SALES_ONLY`：条件合法但同样未接通。** 带上你给的 `CH_SAMPLE` 后校验通过，后端直接以 `NOT_CONNECTED` 拒绝，落在测试计划 T10。
- 因此**剔除小样后的本期/对比期净额、差额、相对变化都无法给出**。按证据规则，不输出无证据的数值事实，也不用 `EXCLUDE_CURRENT_SALES_ONLY` 的单期结果冒充双期同比。

## 仍未改变的有效证据（口径 INCLUDE，小样计入）

| 项目 | 值 |
|---|---|
| 本期 GSV（2026-08-01~08-31） | 410 |
| 对比期 GSV（2025-08-01~08-31） | 305 |
| 差额 / `change_ratio` | 105 / 0.3442622950819672 |
| 来源 | `result_id` = `result_diag_87628ae21accaa39b08bc2c487ae40ce834f58be87268a82`；`run_id` = `run_diag_87628ae21accaa39b08bc2c487ae40ce834f58be87268a82`；`evidence_digest` = `2b7992fbca99eeab8118f34565c8b5dd467fd4957dcf41b7bd3dbeac5c4cbf73` |
| 金额单位 | 单位未知（`money_unit.status = UNKNOWN`） |
| 保存状态 | 该成功结果 `analysis_persisted = true`（已自动保存） |

三次失败调用没有回显 `result_id`/`run_id`，也未返回 `analysis_persisted`，即**没有新增被保存的结果**；本轮同样未成板、未编辑。注意你给出的 `CH_SAMPLE` 只是被当作显式选择的合成渠道提交，工具链全程没有校验它在合成快照中真实存在——这也正是 `SAMPLE_CHANNEL_SET` 仍为 `UNKNOWN` 的缘故。

需要在这个已接通的口径上继续（如换对比方式、上周同星期、大促双窗），我可以直接算；剔除小样这条路要等 A2 接通 T10 后才能给数。
