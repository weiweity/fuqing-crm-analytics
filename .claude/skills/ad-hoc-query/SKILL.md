---
name: ad-hoc-query
description: Ad-hoc data query CLI for fuqing-crm-analytics — 复用 backend/semantic + services + contracts, 不造 SQL. Sprint 62 已实现 3 子命令 daily-gsv / yoy-battle / channel-slice. 输出 stdout 表格 / CSV. read_only DuckDB 连接 (跟 uvicorn 共存, 跟 Sprint 53 race flake 治本同模式). 触发场景: 用户报"最近 N 天 GSV 趋势" / "YOY 大促去年 vs 今年" / "按渠道切片" / "MOM 增长" / "导 CSV 给老板".
disable-model-invocation: false
---

# /ad-hoc-query — 即席查询 CLI (Sprint 62: 3 子命令)

## 适用场景

- 用户口头问 "最近 30 天 GSV 趋势" / "上周日均 vs 上上周日均" / "MOM 增长曲线"
- 用户报 "618 大促去年 vs 今年 GSV / 订单 / 客户 / AOV 对比" / "同比百分比"
- 用户报 "按渠道切片" / "全店 vs 单店 vs 达播 vs 货架" / "渠道 YOY"
- 用户报 "导 CSV 给 BI 团队" / "发 PPT 前先 dump 一下数据"

## 已实现的子命令 (Sprint 61+62, 3 子命令)

### 1. daily-gsv (日序列 GSV + customers + YOY%, Sprint 61 MVP)

```bash
python scripts/ad_hoc_query.py daily-gsv \
  --start 2026-06-19 --end 2026-06-21 \
  [--format table|csv] [--output /tmp/gsv.csv]
```

输出示例 (table):

```
date        | gsv       | customers | yoy_pct
------------+-----------+-----------+---------
2026-06-19  | 12345678  | 1         | +37.17%
2026-06-20  | 11234567  | 1         | +32.17%
2026-06-21  | 13456789  | 1         | +41.65%
```

### 2. yoy-battle (双窗口 YOY 战斗, Sprint 62 新增)

```bash
python scripts/ad_hoc_query.py yoy-battle \
  --baseline-start 2025-06-01 --baseline-end 2025-06-21 \
  --current-start  2026-06-01 --current-end  2026-06-21 \
  --metric gsv|orders|customers|aov|all \
  [--format table|csv] [--output /tmp/yoy.csv]
```

输出示例 (table, --metric all):

```
metric    | baseline_value | current_value | abs_diff  | yoy_pct
----------+----------------+---------------+-----------+--------
gsv       | 17,718,340     | 15,674,622    | -2,043,717| -11.53%
orders    | 145,269        | 159,816       | +14,547   | +10.01%
customers | 109,166        | 126,981       | +17,815   | +16.32%
aov       | 121.97         | 98.08         | -23.89    | -19.59%
```

### 3. channel-slice (按 channel 切片, Sprint 62 新增)

```bash
python scripts/ad_hoc_query.py channel-slice \
  --date 2026-06-21 \
  [--channel all|online|offline] [--store-id <id>] \
  [--compare yoy|pop|none] \
  [--format table|csv] [--output /tmp/channel.csv]
```

输出示例 (table, --compare yoy, 9 channel + 全店):

```
channel    | gsv     | orders | customers | aov | yoy_pct
-----------+---------+--------+-----------+-----+----------
全店       | 586,236 | 6,165  | 4,947     | 95  | +267.89%
货架       | 357,577 | 3,381  | 2,963     | 105 | +261.75%
达播       | 49,874  | 476    | 463       | 104 | +1163.59%
直播       | 107,154 | 664    | 485       | 161 | +548.89%
...
```

## 输出双层目录规则 (Sprint 61+ 拍板)

不传 `--output` 时, CSV 自动落到 `~/Desktop/fuqin date/取数/<base_year>年/<生成日期>/<base_year>年-<生成日期>-<业务标签>/`:

```
~/Desktop/fuqin date/取数/
└── 2026年/                                      ← 业务基期年份
    └── 2026年6月22日/                          ← 生成日期
        └── 2026年-2026年6月22日-日序列GSV/       ← 业务上下文
            └── 日序列GSV-2026-06-01至2026-06-21.csv
```

业务标签 (跟查询一一对应):
- `daily-gsv` → `日序列GSV`
- `yoy-battle` → `YOY对比`
- `channel-slice` → `渠道切片`

测试隔离: `FQ_TAKE_ROOT=/tmp/test_take_root python3 scripts/ad_hoc_query.py daily-gsv ...`

## 留 Sprint 63+ 的子命令 (TODO)

- `rfm-distribution` — RFM 8 象限分布
- `customer-segment` — 客群分层 (new/old/member/non-member)
- `list-endpoints` — 元查询 (列已注册 query)
- `health-check` — DuckDB 健康检查
- `export` — 委派 1-5 + XLSX 输出 (复用 openpyxl, Sprint 32.1 已引)
- `rich-table` — 输出模式升级 (用 rich 库替代 plain stdout)

## 设计原则 (硬约束, Sprint 60+ 沉淀)

1. **复用 backend/semantic/ 口径层** — 禁 inline SQL, 走 `OrderFilters.valid_order()` / `calculations.yoy_absolute()` / `safe_ratio()` 等 SSOT 函数
2. **复用 backend/services/ 业务逻辑** — channel-slice 跟 audience_service._expand_channel 同模式
3. **复用 backend/contracts/schemas.py Pydantic 类型** — 不裸返回 dict
4. **read_only DuckDB 连接** — `duckdb.connect(path, read_only=True, config={"memory_limit": ...})` (跟 uvicorn 共存, Sprint 53 race flake 治本同模式)
5. **强制 LIMIT + 时间窗口 ≤ 366 天** — 防 OOM (Sprint 58 #S58-1 治本同模式)
6. **DuckDB 端 SQL aggregation** — `GROUP BY date/channel` 后 fetch, 不取明细
7. **YOY 范围强截断** — `|v| > 1e6` 视为脏数据 → None (Sprint 27/60+ 同模式)
8. **占位符数强校验** — `assert sql.count("?") == len(params)` (Sprint 60 留尾)
9. **路径 sanitize** — `_sanitize_path_component` 防 `../../../tmp/evil` 路径逃逸 (Codex P1 fix)
10. **同秒覆盖防 race** — `O_EXCL` 独占创建 + 微秒后缀 (Codex P2 fix TOCTOU)
11. **audit trail 必留** — `/tmp/fuqing_adhoc_audit.log` (跟 `/ship .ship-audit.log` 同模式)
12. **ETL 跑批中检测** — `/tmp/.etl_running.flag` 存在 → 警告但继续 (不强制中断)

## 风险硬约束 (Sprint 60+ 沉淀)

| 风险 | 治本模式 |
|------|---------|
| DuckDB read_only vs RW 冲突 | `read_only=True` + 单独 `memory_limit` |
| 大数据集 OOM | 强制时间窗口 ≤ 366 天 + DuckDB 端 aggregation |
| 口径错误 (绕过 semantic) | 强走 `OrderFilters` + `calculations` |
| 输出格式分裂 | `--format` 强制枚举 + 默认 stdout table |
| 路径遍历攻击 (business_tag 含 `../`) | `_sanitize_path_component` 全部替换为 `_` |
| 同秒覆盖 (TOCTOU) | `O_EXCL` 独占创建 + 微秒后缀 |
| ETL 跑批中查询卡顿 | `/tmp/.etl_running.flag` 检测 → 警告 |
| 误覆盖已存在文件 | `export` 路径冲突自动 timestamp suffix |
| 数据逃逸 TAKE_ROOT | `_check_take_root_containment` 自动路径校验 (user --output 显式不受限) |

## 跟其他 skill 联动

- `/ship` (gstack) — 上报表 (`/ad-hoc-query daily-gsv → /ship "v0.4.14.150 daily-gsv 报表"`)
- `/qa` (gstack) — 端到端验证 (`/ad-hoc-query yoy-battle --metric gsv` 验 200)
- `/investigate` (gstack) — 排查 500 错误: 复现现场用 future `health-check` 验 DuckDB 状态
- `/regen-types` (项目内) — 改了 `contracts/schemas.py` 后必跑

## 实施文件清单 (Sprint 62)

- `scripts/ad_hoc_query.py` (entry, ~150 行 argparse + dispatch + auto-path resolve)
- `scripts/ad_hoc_queries/__init__.py`
- `scripts/ad_hoc_queries/registry.py` (QuerySpec + QUERIES dict + 3 子命令注册)
- `scripts/ad_hoc_queries/_utils.py` (~282 行: read_only conn + ETL flag + audit + formatters + sanitize + containment + race fix)
- `scripts/ad_hoc_queries/daily_gsv.py` (146 行, Sprint 61 MVP)
- `scripts/ad_hoc_queries/yoy_battle.py` (218 行, Sprint 62 新增)
- `scripts/ad_hoc_queries/channel_slice.py` (264 行, Sprint 62 新增)
- `backend/tests/test_ad_hoc_query.py` (Sprint 61, 23 case: sanitize / race / containment / CLI subprocess)
- `backend/tests/test_ad_hoc_query_sprint61plus.py` (Sprint 62, 6 case: yoy-battle 业务 3 + channel-slice 业务 2 + CLI subprocess 1)

## Sprint 63+ 留尾 (backlog)

- `rfm-distribution` + `customer-segment` (复用 backend/services/rfm/ 跟 backend/services/audience/)
- ratio ≤ 1.0 / YOY 范围强截断的 CI lint (从 ground-truth-lint 扩)
- 3 个 query 的 e2e CLI 自动化 (`scripts/test_e2e_cli.sh`)
- `--parallel` 多查询并发 (限 4 worker, 复用 Sprint 53 fixture 模式)
- `web` 子命令 (起 mini HTTP server)
- `list-endpoints` / `health-check` / `export` 元查询
- rich table + XLSX 输出 (Sprint 32.1 已引 openpyxl)
- 业务定义 SSOT 文档 (业务口径集中, 跟 Sprint 27 沉淀一致)

## 跟 Sprint 60+ 沉淀的对齐

| 沉淀 | ad-hoc-query 怎么落 |
|------|---------------------|
| 端到端必须覆盖所有 user-input 路径 | `--start/end/format/output/business_tag` 5 路径全测 (test_cli_daily_gsv_table + test_cli_yoy_battle_table) |
| 复用 L3 FilterBuilder | 留 Sprint 62+ (MVP 直接用 OrderFilters.valid_order) |
| ground-truth-lint | 留 Sprint 62+ (L1 SQL f-string lint 在 daily_gsv.py + yoy_battle.py 干净) |
| pytest baseline 持续 | Sprint 62 29/29 pass (Sprint 61 23 + Sprint 62 6), 不影响主仓 baseline |
| audit trail 必留 | `/tmp/fuqing_adhoc_audit.log` |
| DuckDB read_only 跟 uvicorn 共存 | `_utils.read_only_conn()` 复用 Sprint 53 fixture 模式 |
| OOM 治本 | 时间窗口 ≤ 366 天 + DuckDB 端 aggregation |
| YOY 范围强截断 | `|v| > 1e6 → None` (Sprint 60+ 同模式) |
| 占位符数强校验 | `assert sql.count("?") == len(params)` |
