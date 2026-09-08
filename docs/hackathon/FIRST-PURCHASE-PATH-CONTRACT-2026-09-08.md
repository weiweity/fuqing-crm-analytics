# 首购商品路径 → N 日正装转化（离线合同与金标准）

日期：2026-09-08。任务分支 `feat/first-purchase-gold`。状态：**CONTRACT_PLUS_OFFLINE_JSON_COMPUTE**。不是 HTTP 上线、不是 worker、不是 DuckDB 归档、不是渠道族、不是完整 B1。

本文件是可验证的 tracked synthetic 子集合同。完整产品目标仍见 [接口草案](./ANALYTICS-CONTRACTS-DRAFT.md) §2 / §3.1 与 [实施方案](./UNIFIED-ANALYTICS-PLAN.md)。手算输入与预期以本文件第 5 节和 `backend/tests/fixtures/analytics_first_purchase_v1*.json` 为准。结构抄 [渠道后续购买合同](./CHANNEL-FOLLOWUP-CONTRACT-2026-09-07.md)，**不抄**其 22 单 / 11 用户冻结数字。

## 1. 范围

| 层 | 本单元 |
|---|---|
| 查询合同 `analytics-first-purchase-path/v1` | 已落地：请求、resolved filters、snapshot 输入、结果模型 |
| 手工 ≤12 用户金标准 | 已落地；字面手算，不是查询输出转储 |
| JSON snapshot 变换 | 已落地：`execute_first_purchase_path_query` |
| SQL / DuckDB / worker / HTTP | **无**。本族是 fixture in → result out |
| `analytics-channel-followup/v1` Literal `query_id` | **未改**。渠道请求仍拒绝 `first_purchase_product_path` |
| 旧 `analytics-run-b0/v1` 固定 25% | **未改** |
| 会计批准 / 真实获客 / 终身复购 | **不是**。本子集是 synthetic 候选口径 |

## 2. 可验证字段、单位、版本

| 项 | 值 |
|---|---|
| schema | `analytics-first-purchase-path/v1` |
| query | `first_purchase_product_path` / `first-purchase-path-query/v1` |
| metric | `first_purchase_product_n_day_finished` / `first-purchase-path-metric/v1` |
| data | `synthetic-first-purchase-data/v1` |
| hash | `first-purchase-path-filter-hash/v1` |
| snapshot | `synthetic-first-purchase-v1` |
| 显示名 | `首购商品路径 / N日正装转化` |
| 时区 | `Asia/Shanghai`（必须显式；as_of 仅从快照解析） |
| 金额 | 整数分（`minor` / `integer_fen`），币种 CNY；wire 上限 `9007199254740991` |
| 比例 | 有限浮点 0–1；空成熟分母为 `null` + `EMPTY_MATURE_COHORT` |
| 计数 | 严格非 bool 整数，同一传输上限 |
| 时间 | 带时区 RFC3339；规范化为 UTC `YYYY-MM-DDTHH:MM:SS.ffffff+00:00` |
| 权限域 | 进入 `filter_hash`；不同 scope 不得同 hash。hash 只证明 payload 自洽，不是权限凭证 |
| 前端 facts | 无用户/订单明细名单 |

订单唯一键是 `(synthetic_user_id, order_id)`。商品行/退款必须绑定同一用户+订单。不能只靠 `order_id` 跨用户归并。ID 保持字符串。11 用户 / 19 订单只是本手工例子的数目，不是通用业务常量。

商品角色映射在 snapshot `product_roles`：`sample` / `finished`（正装）。计算前若任一 line 的 `product_id` 无角色，整次查询 `status=REJECTED`、`reason_code=MISSING_PRODUCT_ROLE`、`facts=null`，**不得**输出 `finished_conversion_ratio`（含 0% 冒充）。

## 3. 入组、成熟、窗口

- FIXED 入组窗口：开始含、结束不含。本例子 `[2026-06-01, 2026-09-01)`。
- as_of 仅快照解析：`2026-09-01T00:00:00+08:00`。请求不得覆盖。
- N = 30 / 60 / 90，精确 N×24 小时，不取自然月。
- 先在全可观察历史上找净额为正的首单，再按首购渠道过滤（空 `channel_ids` = 已登记 A/B）。
- 同刻订单按 `order_id` UTF-8/`encode` 稳定排序；多品首单每人入组一次，本族按首单去重 SKU 展开。
- 有效订单：截至 as_of 已支付且未取消、净额 > 0。退款截止含 as_of；未来退款不影响当前快照。
- 成熟：`as_of >= first_paid_at + N×24h`。
- 正装转化分子：该成熟用户在 `(first, first+N×24h]` 内（时间晚于首单，或同刻且 `order_id` 更大）另有一笔有效订单，且该单含 `role=finished` 的 SKU。**不含**首单同篮正装。
- 空成熟分母不得把转化率写成 0。

未支持即拒绝，不能静默丢弃：ROLLING、`cohort_ref`、非空 `product_ids`、`exclude_low_price=true`、`comparison`、未知版本、额外字段、未知渠道。

## 4. 三查询族

| 族 | 状态 | 本单元 |
|---|---|---|
| 渠道首次观察队列 → N 日二单/跨渠道 | 既有 `SUPPORTED_CONTRACT` | **不改**其 Literal `query_id` 与冻结数字 |
| 首购商品路径 | 本单元离线 JSON 合同 + compute | catalog 仍 DEFERRED；本模块不走 `require_supported_query` |
| 候选承接人群 | `DEFERRED` | 不在本轨 |

`ChannelFollowupQueryRequest.query_id` 仍为 `Literal["channel_first_observed_followup"]`。本族独立模块：`backend/contracts/analytics_first_purchase.py`。

## 5. 手工例子预期（as_of=2026-09-01T00:00:00+08:00）

金额为整数分。用户 k 的 ID 字面量 `0009007199254740993`。映射：`sku-s1`/`sku-s2` = sample，`sku-f1` = finished。

入组追溯（全历史最早有效单，再套 FIXED 窗）：

| 用户 | 有效首单 | 首购 SKU | 后续正装（相对首单） | 备注 |
|---|---|---|---|---|
| fp-a | 2026-06-01 `fp-a-1` | sku-s1（两行去重） | 2026-06-15 `fp-a-2` sku-f1（14d） | N30/60/90 均转化 |
| fp-b | 2026-06-02 `fp-b-1` | sku-s1 | 2026-07-03 `fp-b-2` sku-f1（31d） | N30 窗外；N60/90 内 |
| fp-c | 2026-06-03 `fp-c-1` | sku-s2 | 2026-06-20 `fp-c-2` sku-f1（17d） | 均转化 |
| fp-d | 2026-06-04 `fp-d-1` | sku-s2 | 无 | 未转化 |
| fp-e | 2026-08-20 `fp-e-1` | sku-s1 | 无 | 全部 N 未成熟 |
| fp-f | 2026-05-20 `fp-f-1` | sku-s1 | （06-10 正装不算入组） | 首单早于窗，排除 |
| fp-g | 2026-06-07 `fp-g-ok` | sku-s2 | 无 | 06-05 全退净额 0，首单改为 06-07 |
| fp-h | 2026-06-08 `fp-h-1` | sku-f1 | 06-18 仅为 sku-s1 | 后续不是正装；同篮正装不计转化 |
| fp-i | 2026-06-09 `dup-oid` | sku-s1 | 2026-06-12 sku-f1 | 与 k 共享 `order_id` 字符串，不得串单 |
| fp-j | 2026-06-10T12:00 `a-first` | sku-s1 | 同时刻 `b-second` sku-f1 | `a-first` < `b-second` |
| 0009007199254740993 | 2026-06-11 `dup-oid` | sku-s1 | 无 | 长 ID 保持字符串 |

入组 10 人（排除 fp-f）。成熟：`as_of - N×24h` 为 08-02 / 07-03 / 06-03 的 00:00+08。故 N30/60 未成熟仅 fp-e；N90 成熟仅 fp-a/b/c。

| 窗口 | sku-s1 入组/成熟/未成熟/正装转化/比率 | sku-s2 | sku-f1 | 全体入组/成熟/未成熟 |
|---|---|---|---|---|
| N=30 | 6 / 5 / 1 / 3 / 3/5=0.6 | 3 / 3 / 0 / 1 / 1/3 | 1 / 1 / 0 / 0 / 0.0 | 10 / 9 / 1 |
| N=60 | 6 / 5 / 1 / 4 / 4/5=0.8 | 3 / 3 / 0 / 1 / 1/3 | 1 / 1 / 0 / 0 / 0.0 | 10 / 9 / 1 |
| N=90 | 6 / 2 / 4 / 2 / 2/2=1.0 | 3 / 1 / 2 / 1 / 1/1=1.0 | 1 / 0 / 1 / 0 / **null** `EMPTY_MATURE_COHORT` | 10 / 3 / 7 |

N30 sku-s1 转化：fp-a、fp-i、fp-j（fp-b 第 31 日不计）。N60 另计入 fp-b。N90 sku-f1 不得写成 0%。

独立负例：

- 去掉 fp-a 的 `fp-a-2`（少一单）：N30 sku-s1 转化 3→2，比率 2/5=0.4；`data_digest` 必变。
- 去掉 `sku-s1` 角色映射：`REJECTED` / `MISSING_PRODUCT_ROLE` / `missing_product_ids=["sku-s1"]`，`facts=null`，无转化率字段。
- 两用户同一 `order_id` 字符串不得串单。
- 不同 `permission_scope` 不得同 `filter_hash`。

## 6. 尚未实现

- worker、RunStore 接线、新 HTTP、原生工具卡
- catalog 从 DEFERRED 升为成功路径
- 人群审批、保存资产、仓库/ETL
- 真实业务数据与产品模型

## 7. 产物

- `docs/hackathon/FIRST-PURCHASE-PATH-CONTRACT-2026-09-08.md`（本文件）
- `docs/hackathon/FIRST-PURCHASE-PATH-COMPUTE-2026-09-08.md`
- `backend/contracts/analytics_first_purchase.py`
- `backend/services/analytics/first_purchase/`
- `backend/tests/test_analytics_first_purchase.py`
- fixtures：`backend/tests/fixtures/analytics_first_purchase_v1.json` 与 `_expected.json`，以及 mutated / 缺角色映射副本
