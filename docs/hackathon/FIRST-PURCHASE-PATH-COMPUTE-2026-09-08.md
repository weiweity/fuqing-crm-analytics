# 首购商品路径离线计算（JSON snapshot 变换）

日期：2026-09-08。任务分支 `feat/first-purchase-gold`。状态：**OFFLINE_JSON_DETERMINISTIC_COMPUTE**。不是 HTTP、不是 worker、不是 DuckDB 归档、不是渠道族 SQL。

合同与手算金标准见 [首购商品路径合同](./FIRST-PURCHASE-PATH-CONTRACT-2026-09-08.md)。`expected.json` 标记 `hand_calculated`；生产代码不读取它。

## 1. 范围

| 层 | 本单元 |
|---|---|
| 输入 | `FirstPurchaseQueryRequest` + `FirstPurchaseSnapshot` + `permission_scope` |
| 执行 | `backend/services/analytics/first_purchase/compute.py`：`execute_first_purchase_path_query` |
| 存储 | 无。纯内存 JSON 变换 |
| worker / RunStore / HTTP / native / DuckDB | **未做** |

不改 `backend/services/analytics/warehouse/`，不改渠道族冻结数字，不把本族 `query_id` 写入 `analytics-channel-followup/v1` 的 Literal。

## 2. 实际路径与函数

- `execute_first_purchase_path_query(request=..., snapshot=..., permission_scope=...)` → JSON 对象。
- 校验走独立合同 `backend/contracts/analytics_first_purchase.py`。
- 订单键 `(synthetic_user_id, order_id)`；金额整数分；FIXED 窗 + N×24h 成熟。
- 有效单：`PAID`、`paid_at <= as_of`、净额（gross − 截止 as_of 退款）> 0。
- 每用户全历史最早有效单（`paid_at` 升序，同刻 `encode(order_id)`）入组一次，再套 `[start, end)` 与渠道。
- 首购 SKU = 首单 line 去重 `product_id`。正装转化 = 排序晚于首单且 `paid_at <= first + N×24h` 的另一有效单上存在 `role=finished`。
- 任一 line 的 SKU 不在 `product_roles`：`status=REJECTED`、`reason_code=MISSING_PRODUCT_ROLE`、`facts=null`，wire 中不得出现 `finished_conversion_ratio`。
- `filter_hash` 含 `permission_scope` 与 `data_digest`；输入排列变化不改 digest。

## 3. 金标准逐窗口（手算，见合同第 5 节）

as_of=`2026-09-01T00:00:00+08:00`。与 expected fixture 字面字段一致：

| N | sku-s1 入组/成熟/未成熟/转化/比率 | sku-s2 | sku-f1 | 全体入组/成熟/未成熟 |
|---|---|---|---|---|
| 30 | 6 / 5 / 1 / 3 / 0.6 | 3 / 3 / 0 / 1 / 1/3 | 1 / 1 / 0 / 0 / 0.0 | 10 / 9 / 1 |
| 60 | 6 / 5 / 1 / 4 / 0.8 | 3 / 3 / 0 / 1 / 1/3 | 1 / 1 / 0 / 0 / 0.0 | 10 / 9 / 1 |
| 90 | 6 / 2 / 4 / 2 / 1.0 | 3 / 1 / 2 / 1 / 1.0 | 1 / 0 / 1 / 0 / null + `EMPTY_MATURE_COHORT` | 10 / 3 / 7 |

数据反例（独立手写预期，同一 compute）：

- 只删 `fp-a-2`：N30 sku-s1 转化 2 / 5 = 0.4；digest 与基线不同。
- 只删 `sku-s1` 角色：拒绝缺项，不 emit 转化率。

## 4. 验证

| 命令 | 范围 |
|---|---|
| `PYTHONPATH=<worktree> python3.14 -m pytest -q backend/tests/test_analytics_first_purchase.py` | 本族 shipped compute vs 手算 snapshot |

无 HTTP/DSH 启动；未读 `data/processed/fuqing_crm.duckdb`；未跑 ETL。

## 5. 未做

native、worker、HTTP、仓库、真实业务库。catalog 成功路径不在本轨。
