---
name: ad-hoc-query
description: Ad-hoc data query CLI for fuqing-crm-analytics — 复用 backend/semantic + services + contracts, 不造 SQL. MVP 范围: 1 个子命令 daily-gsv (日序列 GSV + customers + YOY%). 输出 stdout 表格 / CSV. read_only DuckDB 连接 (跟 uvicorn 共存, 跟 Sprint 53 race flake 治本同模式). 触发场景: 用户报"最近 N 天 GSV 趋势" / "MOM 增长" / "YOY 验证" / "导 CSV 给老板".
disable-model-invocation: false
---

# /ad-hoc-query — 即席查询 CLI (Sprint 61 MVP)

## 适用场景

- 用户口头问 "最近 30 天 GSV 趋势" / "上周日均 vs 上上周日均" / "MOM 增长曲线"
- 用户报 "YOY 增长口径验证" / "同比百分比"
- 用户报 "导 CSV 给 BI 团队" / "发 PPT 前先 dump 一下数据"

## 当前实现的子命令 (Sprint 61 MVP)

### 1. daily-gsv (日序列)

```bash
python scripts/ad_hoc_query.py daily-gsv \
  --start 2026-06-19 --end 2026-06-21 \
  [--format table|csv] [--output /tmp/gsv.csv]
```

输出示例 (table 格式, plain stdout):

```
date        | gsv       | customers | yoy_pct
------------+-----------+-----------+---------
2026-06-19  | 12345678  | 1         | +37.17%
2026-06-20  | 11234567  | 1         | +32.17%
2026-06-21  | 13456789  | 1         | +41.65%
```

输出示例 (csv 格式, --output 写到文件):

```bash
python scripts/ad_hoc_query.py daily-gsv \
  --start 2026-06-19 --end 2026-06-21 \
  --format csv --output /tmp/gsv.csv
# → [OK] CSV written to /tmp/gsv.csv
```

## 留 Sprint 62+ 的子命令 (TODO)

- `channel-slice` — 渠道切片 (online/offline/单店)
- `yoy-battle` — 同比对比 (--metric gsv|orders|customers|aov)
- `rfm-distribution` — RFM 8 象限分布
- `customer-segment` — 客群分层 (new/old/member/non-member)
- `list-endpoints` — 元查询 (列已注册 query)
- `health-check` — DuckDB 健康检查
- `export` — 委派 1-5 + XLSX 输出

## 设计原则 (硬约束, Sprint 60+ 沉淀)

1. **复用 backend/semantic/ 口径层** — 禁 inline SQL, 走 `OrderFilters.valid_order()` / `calculations.yoy_absolute()` 等 SSOT 函数
2. **复用 backend/services/ 业务逻辑** — 不重复造 service
3. **复用 backend/contracts/schemas.py Pydantic 类型** — 不裸返回 dict
4. **read_only DuckDB 连接** — `duckdb.connect(path, read_only=True, config={"memory_limit": ...})` (跟 uvicorn 共存, Sprint 53 race flake 治本同模式)
5. **强制 LIMIT + 时间窗口 ≤ 366 天** — 防 OOM (Sprint 58 #S58-1 治本同模式)
6. **DuckDB 端 SQL aggregation** — `GROUP BY date` 后 fetch, 不取明细
7. **YOY 范围强截断** — `|v| > 1e6` 视为脏数据 → None (Sprint 27/60+ 同模式)
8. **占位符数强校验** — `assert sql.count("?") == len(params)` (Sprint 60 留尾)
9. **audit trail 必留** — `/tmp/fuqing_adhoc_audit.log` (跟 `/ship .ship-audit.log` 同模式)
10. **路径冲突自动避让** — `export` 路径已存在 → 加 `_%Y%m%d_%H%M%S` suffix
11. **ETL 跑批中检测** — `/tmp/.etl_running.flag` 存在 → 警告但继续 (不强制中断)

## 风险硬约束 (Sprint 60+ 沉淀)

| 风险 | 治本模式 |
|------|---------|
| DuckDB read_only vs RW 冲突 | `read_only=True` + 单独 `memory_limit` |
| 大数据集 OOM | 强制时间窗口 ≤ 366 天 + DuckDB 端 aggregation |
| 口径错误 (绕过 semantic) | 强走 `OrderFilters` + `calculations` |
| 输出格式分裂 | `--format` 强制枚举 + 默认 stdout table |
| ETL 跑批中查询卡顿 | `/tmp/.etl_running.flag` 检测 → 警告 |
| 误覆盖已存在文件 | `export` 路径冲突自动 timestamp suffix |

## 跟其他 skill 联动

- `/ship` (gstack) — 上报表 (`/ad-hoc-query daily-gsv → /ship "v0.4.14.148 daily-gsv 报表"`)
- `/qa` (gstack) — 端到端验证 (`/ad-hoc-query daily-gsv --start ... --end ...` 验 200)
- `/investigate` (gstack) — 排查 500 错误: 复现现场用 future `health-check` 验 DuckDB 状态
- `/regen-types` (项目内) — 改了 `contracts/schemas.py` 后必跑

## 实施文件清单 (MVP)

- `scripts/ad_hoc_query.py` (entry, ~125 行 argparse + dispatch)
- `scripts/ad_hoc_queries/__init__.py`
- `scripts/ad_hoc_queries/registry.py` (QuerySpec + QUERIES dict)
- `scripts/ad_hoc_queries/_utils.py` (read_only conn + ETL flag + audit + formatters)
- `scripts/ad_hoc_queries/daily_gsv.py` (demo query, ~120 行)
- `backend/tests/test_ad_hoc_query.py` (7 case: basic / no-data / cross-month / window-too-large / invalid-range / registry / CLI subprocess)

## Sprint 61+ 留尾 (backlog)

- ratio ≤ 1.0 / YOY 范围强截断的 CI lint (从 ground-truth-lint 扩)
- 5 个 query 的 e2e CLI 自动化 (`scripts/test_e2e_cli.sh`)
- `--sql` 调试模式 (高级用户, 强制走 semantic)
- `--parallel` 多查询并发 (限 4 worker, 复用 Sprint 53 模式)
- `web` 子命令 (起 mini HTTP server)
- `list-endpoints` / `health-check` / `export` 元查询
- rich table + XLSX 输出 (Sprint 32.1 已引 openpyxl)
- 业务定义 SSOT 文档 (业务口径集中, 跟 Sprint 27 沉淀一致)

## 跟 Sprint 60+ 沉淀的对齐

| 沉淀 | ad-hoc-query 怎么落 |
|------|---------------------|
| 端到端必须覆盖所有 user-input 路径 | `--start/end/format/output` 4 路径全测 (test_cli_daily_gsv_table) |
| 复用 L3 FilterBuilder | 留 Sprint 62+ (MVP 直接用 OrderFilters.valid_order) |
| ground-truth-lint | 留 Sprint 62+ (L1 SQL f-string lint 在 daily_gsv.py 干净) |
| pytest baseline 持续 | 7 case 全过, 不影响主仓 758/1 baseline |
| audit trail 必留 | `/tmp/fuqing_adhoc_audit.log` |
| DuckDB read_only 跟 uvicorn 共存 | `_utils.read_only_conn()` 复用 Sprint 53 模式 |
| OOM 治本 | 时间窗口 ≤ 366 天 + DuckDB 端 aggregation |
