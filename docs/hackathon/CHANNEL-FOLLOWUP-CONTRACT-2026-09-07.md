# 渠道首次观察队列 → N 日二单 / 跨渠道（G2a 合同与金标准）

日期：2026-09-07。修订时点：G2a 审查修复（任务分支 `codex/channel-followup-contracts`，基于 G1 `857d2ce` / [PR #70](https://github.com/weiweity/fuqing-crm-analytics/pull/70)，P1 [PR #69](https://github.com/weiweity/fuqing-crm-analytics/pull/69)）。状态：**CONTRACT_AND_HAND_GOLDENS_ONLY**。不是 SQL 通过、不是 HTTP 上线、不是完整 B1、不是三查询族全部合同通过。

本文件是可验证的 tracked synthetic 子集合同。完整产品目标仍见 [接口草案](./ANALYTICS-CONTRACTS-DRAFT.md) §2 / §3.1 / §7 与 [实施方案](./UNIFIED-ANALYTICS-PLAN.md) §4。手算输入与预期以本文件第 5 节和 `backend/tests/fixtures/analytics_channel_followup_v1*.json` 为准，不是旧 B0 100/25/25%。

## 1. 范围

| 层 | 本单元 |
|---|---|
| 查询合同 `analytics-channel-followup/v1` | 已落地：请求、resolved filters、snapshot 输入、结果模型 |
| 离线 OpenAPI / 生成 TS | 已落地：`paths` 为空，`x-not-an-http-api=true` |
| 手工 11 用户 / 22 订单金标准 | 已落地；字面手算，不是查询输出 |
| SQL / worker / 运行调度 | **尚未实现（NOT RUN）** |
| 新 HTTP 路由 | **无**。不得把 OpenAPI components 当成可调用 API |
| 旧 `analytics-run-b0/v1` 与插件 `analytics-b0/v1` 固定 25% | **未改** |
| 会计批准 / 真实获客 / 终身复购 | **不是**。本子集是 synthetic 候选口径 |

G1 源码已提交 `857d2cee7096027b87dc6ca1f2dfd0720fb1a7fd`，PR #70，base PR #69。G1 CI 对该精确 SHA **PASS**（runs 34052132760 / 34052132799；B0 + path plans SUCCESS，其余按范围 SKIPPED；证据 `G1-final-ci.json`，约 2026-09-06T18:34–18:37Z）。P1 CI 不是 G1 CI。G2a 实现待 Codex 提交。

## 2. 可验证字段、单位、版本

| 项 | 值 |
|---|---|
| schema | `analytics-channel-followup/v1` |
| query | `channel_first_observed_followup` / `channel-followup-query/v1` |
| metric | `channel_first_observed_n_day_repeat` / `channel-followup-metric/v1` |
| data | `synthetic-channel-followup-data/v1` |
| hash | `channel-followup-filter-hash/v1` |
| snapshot | `synthetic-channel-followup-v1` |
| 显示名 | `首次观察到的渠道 / N日二单率` |
| 时区 | `Asia/Shanghai`（必须显式；as_of 仅从快照解析） |
| 金额 | 整数分（`minor` / `integer_fen`），币种 CNY；wire 上限 `9007199254740991`（JSON/JS 安全整数，非经营阈值） |
| 比例 | 有限浮点 0–1；空成熟分母为 `null` + `EMPTY_MATURE_COHORT` |
| 计数 / quantity | 严格非 bool 整数，同一传输上限 |
| 时间 | 带时区 RFC3339；规范化为 UTC `YYYY-MM-DDTHH:MM:SS.ffffff+00:00`（固定 6 位小数）。同 instant 不同 offset 哈希相同；+1 微秒必变。拒绝 epoch/naive/>6 位小数截断 |
| 权限域 | 进入 `filter_hash`；不同 scope 不得同 hash。hash 只证明 payload 自洽，不是权限凭证 |
| 前端 facts | 无用户/订单明细名单；`product_ids` 仅空数组 |

订单唯一键是 `(synthetic_user_id, order_id)`，商品行/退款必须绑定同一用户+订单。不能只靠 `order_id` 跨用户归并。ID 保持字符串，不转 JS 数字。22 订单 / 11 用户只是本手工例子的数目，不是通用业务常量。

## 3. 入组、成熟、窗口

- FIXED 入组窗口：开始含、结束不含。本例子 `[2026-06-01, 2026-09-01)`。
- as_of 仅快照解析：`2026-09-01T00:00:00+08:00`。请求不得覆盖。
- N = 30 / 60 / 90，精确 N×24 小时，不取自然月。
- 先在全可观察历史上找净额为正的首单，再按首购渠道过滤。
- 同刻订单按 `order_id` ASCII 稳定排序；多品首单每人入组一次。
- 有效订单：截至 as_of 已支付且未取消、净额 > 0。退款截止含 as_of；未来退款不影响当前快照。
- 成熟：`as_of >= first_paid_at + N×24h`。分子为该成熟队列在 `[first, first+N]` 且排序晚于首单的另一有效订单。
- 窗口净支付含有效首单，不是利润/增量。无成熟队列时金额也是 `null`，不能输出 0 冒充有观察值。

未支持即拒绝，不能静默丢弃：ROLLING、`cohort_ref`、非空 `product_ids`、`exclude_low_price=true`、`comparison`、未知版本、额外字段、未知渠道。

## 4. 三查询族

| 族 | 状态 | 本单元 |
|---|---|---|
| 渠道首次观察队列 → N 日二单/跨渠道 | `SUPPORTED_CONTRACT` | 合同 + 手算金标准 |
| 首购商品路径 | `DEFERRED` | 共享 FIXED 窗口 / N / snapshot / 渠道等输入形状；无本族金标准、成功 payload 或 HTTP |
| 候选承接人群 | `DEFERRED` | 后续可复用同一 `(synthetic_user_id, order_id)` 粒度；G2a 不是三族合同都通过 |

本候选 v1 已核对：`ChannelFollowupQueryRequest.query_id`、`ChannelFollowupResolvedFilters.query_id`、`ChannelFollowupResult.query_id` 均为 `Literal["channel_first_observed_followup"]`（`backend/contracts/analytics_query.py`）。`test_request_rejects_unsupported_or_unknown_inputs` 对 `query_id=first_purchase_product_path` 期望 `ValidationError`；`require_supported_query` 对 `DEFERRED` 族抛 `UnsupportedQueryError`（`this subset does not emit a success payload`），由 `test_deferred_families_have_no_success_payload` 覆盖。其他查询族在本候选 v1 被拒绝，不提供成功结果。渠道族 SQL 留 G3。

## 5. 手工例子预期（as_of=2026-09-01T00:00:00+08:00）

金额为整数分。用户 k 的 ID 字面量 `0009007199254740993`。

| 窗口 | 渠道 A（成熟/未成熟/二单/跨渠道/净额） | 渠道 B | 全体 |
|---|---|---|---|
| N=30 | 7 / 1 / 4 / 3 / 87000 | 2 / 0 / 1 / 0 / 23000 | 9 / 1 / 5 / 3 / 110000 |
| N=60 | 7 / 1 / 5 / 4 / 92000 | 2 / 0 / 1 / 0 / 23000 | 9 / 1 / 6 / 4 / 115000 |
| N=90 | 2 / 6 / 2 / 2 / 30000 | 0 / 2 / 0 / 0 / **null** `EMPTY_MATURE_COHORT` | 2 / 8 / 2 / 2 / 30000 |

比例：N30 A 4/7 与 3/7，B 1/2 与 0，全体 5/9 与 1/3。N90 B 不得写成 0%。N60 仅 b 的第 31 日二单进入窗口。N90 仅 a、b 成熟（d 的 6/3 全退无效，首次变为 6/15 仍未成熟）。

跨字段：`repeat <= mature`、`cross <= repeat`；有分母时 ratio = 分子/分母；全体 counts 等于选中渠道明细之和。输入排列变化不改 digest；权限域不同不得同 hash。

独立负例（不改 22 单基线）：两个合成用户可拥有同一字符串 `order_id`，不得串单。

## 6. 尚未实现

- 查询函数 / SQL / DuckDB
- worker、RunStore 接线、新 HTTP
- 人群审批、保存资产、仓库/ETL
- 真实业务数据与产品模型

测试只证明合同与手工例子自洽。实际计算留 G3。

## 7. 产物

- `backend/contracts/analytics_query.py`
- `backend/semantic/analytics_channel_followup.py`
- `backend/services/analytics/catalog.py`（静态目录与规范化 hash，不连库）
- `backend/contracts/analytics-query.openapi.json`（OpenAPI SHA-256 `38b72d2728131084e8038a16f958e6d245aa035cfbcf44bb49d32cc28b6c2f17`）
- `dsh-plugins/analytics-workbench/src/query-contract.generated.d.ts`
- fixtures：`backend/tests/fixtures/analytics_channel_followup_v1.json` 与 `_expected.json`
- 旧 B0 OpenAPI SHA-256 保持 `5d93c3aabf362865e8f24e28c96a8d1f75717c80370f31734407d85b128b9679`
