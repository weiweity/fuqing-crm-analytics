# HANDOFF-TO-CODEX-Sprint171 — ad-hoc-query v2.0 升级（两年对比分析模式）

> **接收方**：Codex app（Stage 2 实施者）
> **架构师**：Claude Code（Stage 1）
> **分支**：`feature/sprint171-ad-hoc-query-v2`（已建好，不要再创）
> **CLAUDE.md 版本**：v0.4.14.22（main @ 83a01e2）
> **AGENTS.md**：本地自动注入（Codex 不读 CLAUDE.md，靠 AGENTS.md 同步）

---

## 1. 任务一句话

把 `scripts/ad_hoc_query.py` + `scripts/ad_hoc_queries/` 从「3 子命令 MVP」升级到「9 子命令 + AI 问数 + Excel 多 sheet」两年对比分析工具，覆盖芙清 CRM 业务组高频取数场景。

---

## 2. 必读文件（读不全不准动手）

| 文件 | 看什么 |
|---|---|
| `~/.claude/skills/ad-hoc-query/SKILL.md` | **完整读**，v2.0 规格、子命令清单、设计原则、风险硬约束全在这 |
| `scripts/ad_hoc_query.py` | 入口（argparse + dispatch + auto-path） |
| `scripts/ad_hoc_queries/registry.py` | `QuerySpec` 数据类 + `QUERIES` 注册表 |
| `scripts/ad_hoc_queries/_utils.py` | read_only conn + ETL flag + audit + formatters + sanitize + 路径规则 |
| `scripts/ad_hoc_queries/daily_gsv.py` | 已实现 query 的范本 |
| `scripts/ad_hoc_queries/yoy_battle.py` | 同上 |
| `scripts/ad_hoc_queries/channel_slice.py` | 同上 |
| `backend/services/metrics/audience_summary.py` | `calculate_audience_summary` — `two-year-overview` 复用 |
| `backend/services/metrics/audience_table.py` | `get_audience_table` — `new-old-customer` 复用 |
| `backend/services/rfm/service.py` | `get_rfm_distribution` — `rfm-repurchase` 复用 |
| `backend/semantic/segments.py` | `R_SEGMENT_ORDER` (Sprint 170 已改 6 桶) |
| `backend/contracts/schemas.py` | Pydantic schema：`AudienceSummaryResponse` / `AudienceTableResponse` |
| `backend/routers/audience.py` | `/api/v1/audience/summary` `/api/v1/audience/table` 路由 |
| `backend/services/metrics_service.py` | 路由层 service 入口 |
| `backend/services/__init__.py` | `PeriodBuilder`（wtd/mtd/ytd/q1-q4） |
| `docs/development/services.md` | 加新 service 的规范 |
| `docs/development/ratio-convention.md` | B1+B2 ratio/pct/ppt 命名 |
| `docs/development/testing.md` | test 怎么写 |

---

## 3. 接入方式（**硬约束**）

### 方案 A：直接 import backend services

```python
# ✅ 正确范式
from backend.services.metrics.audience_summary import calculate_audience_summary
from backend.services.metrics.audience_table import get_audience_table
from backend.services.rfm.service import get_rfm_distribution
```

```python
# ❌ 错误反例（禁止）
import duckdb
conn = duckdb.connect(...)
df = conn.execute("SELECT ...").fetchdf()
```

**为什么禁 inline SQL / 直连 DuckDB**：
1. 口径 100% 复用 backend service，不漂移
2. 跟 uvicorn 单例 DuckDB 连接不冲突（Sprint 24+ P3 race flake 治本）
3. 零写库风险
4. Service 函数已做 YOY 单位处理（pp vs %）

---

## 4. 9 个子命令接口契约

### 4.1 已存在（不要重写，只读参考）

#### `daily-gsv`
```
--start YYYY-MM-DD (required)
--end YYYY-MM-DD (required)
--format table|csv|xlsx (default table)
--output PATH (optional)
```
输出：`date, gsv, customers, yoy_pct`

#### `yoy-battle`
```
--baseline-start, --baseline-end, --current-start, --current-end (all required)
--metric gsv|orders|customers|aov|all (default all)
--format table|csv|xlsx
--output PATH
```
输出：baseline vs current 5 列

#### `channel-slice`
```
--date YYYY-MM-DD (required)
--channel all|online|offline (default all)
--store-id ID (optional)
--compare yoy|pop|none (default none)
--format table|csv|xlsx
--output PATH
```
输出：channel × {gsv, orders, customers, aov, yoy_pct}

### 4.2 本轮 Sprint 171 新增（6 个）

#### `two-year-overview` ⭐ 最高优先级
```
--year INT (default 2026, 影响列标签)
--period wtd|mtd|ytd|q1|q2|q3|q4 (optional)
--start YYYY-MM-DD (optional, period 为空时使用)
--end YYYY-MM-DD (optional, period 为空时使用)
--channel STR (optional)
--exclude-channels STR (逗号分隔, optional)
--format table|csv|xlsx (default xlsx)
--output PATH
```

**复用**：`calculate_audience_summary(year=year, metric_type='GSV', start_date=..., end_date=..., channel=..., exclude_channels=...)`

**输出列**（每个指标三列：`2026 值 | 2025 值 | 同比`）：

| 指标分组 | 字段 |
|---|---|
| 总量 | GSV / 订单 / 客户 / AUS / 退款率 |
| 新客 | 新客 GSV / 新客人数 / 新客 AUS / 新客占比 |
| 老客 | 老客 GSV / 老客人数 / 老客 AUS / 老客占比 |
| 会员 | 会员 GSV / 会员人数 / 会员 AUS / 会员占比 / 会员溢价 |

**同比单位**：
- GSV / 订单 / 客户 / AUS / 新客 GSV / 老客 GSV / 会员 GSV → **%**（已 `*100`，如 `28.5` 表示 +28.5%）
- 占比类（新客占比 / 老客占比 / 会员占比）/ 复购率 / 退款率 → **pp**（已 `*100`，如 `5.0` 表示 +5pp）

#### `new-old-customer`
```
--start YYYY-MM-DD (required)
--end YYYY-MM-DD (required)
--exclude-channels STR (optional)
--dimension channel|category (default channel)
--format xlsx
--output PATH
```

**复用**：`get_audience_table(dimension=dimension, mode='free', start_date=start, end_date=end, exclude_channels=...)`

**输出**：每个维度（GSV / 人数 / AUS / 占比）独立三列块，分别对新客 / 老客展开。

#### `rfm-repurchase` ⭐ Sprint 170 口径
```
--start YYYY-MM-DD (required)
--end YYYY-MM-DD (required)
--channel STR (optional)
--format xlsx
--output PATH
```

**复用**：`backend.services.rfm.service.get_rfm_distribution(start_date, end_date, channel=...)` + `backend.semantic.segments.R_SEGMENT_ORDER`

**R 6 桶**（Sprint 170 拍板，旧 8 象限已弃用）：
- R1 (0-7 天)
- R2 (8-30 天)
- R3 (31-60 天)
- R4 (61-90 天)
- R5 (91-180 天)
- R6 (181+ 天)

**输出**：6 桶 × {人数, 占比, GSV, AUS, 复购率} + 两年对比（如有）

#### `top-n`
```
--dimension spu_category|spu_product_subclass|spu_product_class (default spu_category)
--start YYYY-MM-DD (required)
--end YYYY-MM-DD (required)
--exclude-channels STR (optional)
--limit INT (default 20)
--format xlsx
--output PATH
```

**复用**：`calculate_audience_summary(...)`（按 dimension 切），前端 `dimension_value` 字段映射成维度值

**输出**：TOP N 行 × {维度值, GSV_2026, GSV_2025, GSV_yoy, 人数_2026, 人数_2025, 人数_yoy, AUS_2026, AUS_2025, AUS_yoy}

#### `export-excel` ⭐ 最高优先级
```
--start YYYY-MM-DD (required)
--end YYYY-MM-DD (required)
--exclude-channels STR (optional)
--year INT (default 2026)
--output PATH (optional, 默认 auto-path)
--format xlsx (强制)
```

**复用**：组合上面 4 个 query 的 service 调用结果

**Sheet 顺序**（用户固定偏好）：
1. `00_说明`
2. `01_数据排查报告`（自动调 dq-report 写入）
3. `02_新老客30指标`（= two-year-overview）
4. `03_单品概览TOP20`（= top-n, dimension=spu_category）
5. `04_复购周期RFM`（= rfm-repurchase）
6. `05_回购周期RFM`（= 同品类回购周期，留 TODO 占位可空 sheet）
7. `06_连带TOP20`（= top-n, dimension=spu_product_subclass）
8. `07_品类流转矩阵`（80×80 留 TODO 占位可空 sheet）
9. `08_R区间回购周期`（= rfm-repurchase 同样输出）
10. `09_渠道概览`（= channel-slice）
11. `10_同品复购与回购店铺`（留 TODO 占位可空 sheet）

**视觉规范**（**用户固定偏好，0 妥协**）：

| 元素 | 规则 |
|---|---|
| 主题色 | 表头深蓝 `#1F4E79`，子标题中蓝 `#2E75B6` |
| 同比正值 | 红色粗体 `#D32F2F`，格式 `+X.XX%` |
| 同比负值 | 绿色粗体 `#2E7D32`，格式 `-X.XX%` |
| 占比同比 | pp 单位，同样红绿正负 |
| **公式** | **0 公式**，Python 算好直接写值 |

**实现要点**：
- `openpyxl`（Sprint 32.1 已引）新建 `Workbook`，每个 sheet 走 `_utils.excel_styles.py` 的样式函数
- 新建 `scripts/ad_hoc_query_excel_styles.py` 集中管理样式 SSOT
- 文件名冲突走 `O_EXCL` 独占创建 + 微秒后缀（沿用 Sprint 60+ 治本）

#### `dq-report` ⭐ 数据质量
```
--start YYYY-MM-DD (required)
--end YYYY-MM-DD (required)
--full (默认 False = 轻量 5 项; True = 完整 15 项)
--format table|csv|xlsx (default table)
--output PATH
```

**复用**：组合 service 调用结果做交叉验证，**不调 LLM**

**15 项校验清单**（完整版 `--full`）：
1. 完整性检查（缺失率>50% 标 WARN）
2. YOY 范围合理性（`|yoy| > 1e6` 标 ERROR）
3. 占比类 yoy 单位检查（必须是 pp）
4. 子项之和 = 父项检查（新客 GSV + 老客 GSV ≈ 全店 GSV，误差>0.1% 标 WARN）
5. 关键口径交叉验证（req1 全店 GSV vs req2 TTL GSV，误差>0.5% 标 WARN）
6. 同接口字段单位一致性（AUS yoy vs GSV yoy 量级一致）
7. 2026 和 2025 真相等性检查（`yoy=None` 时数据应相等，误差>0.01 标 ERROR）
8. 渠道覆盖率（9 个标准 channel 是否齐全）
9. 日期连续性（窗口内无断层）
10. 会员口径稳定性（is_member 字段不为 NULL）
11. 退款率范围（0-100%）
12. AUS 量级合理性（10-10000 区间）
13. 复购率范围（0-100%）
14. 维度 drilldown 一致性（channel → category 汇总误差<0.5%）
15. ETL 状态（/tmp/.etl_running.flag 不存在）

**WARN/ERROR 分级**：
- `WARN`：可继续，记录到 audit
- `ERROR`：必须 `--force` 才继续，否则退出 1

#### `ask` 自然语言路由
```
--text STR (required)
--format table|csv|xlsx (default table)
```

**复用**：内部关键词路由（**不调 LLM**）

**关键词路由表**：

| 关键词 | 路由到 |
|---|---|
| 两年对比 / 30指标 / 老客 / 新客 / 会员 | `two-year-overview` |
| 新老客拆分 / 新客老客 | `new-old-customer` |
| 渠道 / 货架 / 达播 / 直播 / 全店 | `channel-slice` |
| 复购周期 / R 区间 / RFM | `rfm-repurchase` |
| TOP20 / 品类 / 单品 / SPU | `top-n` |
| 导出 / Excel / 报告 / 整份 | `export-excel` |
| 排查 / 校验 / 数据质量 | `dq-report` |
| 日 GSV / 每日 / 趋势 | `daily-gsv` |
| 同比 / YOY / 战斗 | `yoy-battle` |

**参数提取**（基础规则，能用正则就用正则）：
- `最近 N 天` / `近 N 天` → `--start` = today-N, `--end` = today-1
- `2026` / `2025` / `2024` → `--year`
- `MTD` / `WTD` / `YTD` → `--period`
- 渠道列表 → `--channel` / `--exclude-channels`

**不命中回退**：`list-endpoints` 列出全部 query + 提示「请说更具体点」

---

## 5. 输出格式规范

### 5.1 stdout (table)

- 默认 plain 文本表（沿用 `_utils.format_stdout_table`，列宽对齐）
- 数字千分位格式化（`{:,}`），百分比保留 2 位小数

### 5.2 CSV

- 沿用 `_utils.write_csv`，千分位去掉（CSV 是给 BI 工具吃的）
- auto-path：`~/Desktop/fuqin date/取数/<year>年/<生成日期>/...`

### 5.3 XLSX（**重点**）

- 走 `openpyxl`，新建 `scripts/ad_hoc_query_excel_styles.py`
- **0 公式**：`ws.cell(row, col, value=...)`，所有数值在 Python 算好
- 样式 SSOT 集中管理：

```python
# scripts/ad_hoc_query_excel_styles.py (新)
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

THEME_HEADER = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')  # 深蓝
THEME_SUBHEADER = PatternFill(start_color='2E75B6', end_color='2E75B6', fill_type='solid')  # 中蓝
FONT_HEADER = Font(name='Microsoft YaHei', size=11, bold=True, color='FFFFFF')
FONT_BODY = Font(name='Microsoft YaHei', size=10)
FONT_YOY_POS = Font(name='Microsoft YaHei', size=10, bold=True, color='D32F2F')  # 红涨
FONT_YOY_NEG = Font(name='Microsoft YaHei', size=10, bold=True, color='2E7D32')  # 绿跌

def apply_header(cell):
    cell.fill = THEME_HEADER
    cell.font = FONT_HEADER
    cell.alignment = Alignment(horizontal='center', vertical='center')

def apply_yoy(cell, value):
    cell.font = FONT_YOY_POS if value >= 0 else FONT_YOY_NEG
    if value >= 0:
        cell.value = f'+{value:.2f}%'
    else:
        cell.value = f'{value:.2f}%'
```

---

## 6. 实施步骤（Codex 按此顺序做）

### Step 1: 搭骨架（30min）
- 新建 `scripts/ad_hoc_queries/two_year_overview.py`（空 stub + 注册）
- 新建 `scripts/ad_hoc_queries/new_old_customer.py`（空 stub + 注册）
- 新建 `scripts/ad_hoc_queries/rfm_repurchase.py`（空 stub + 注册）
- 新建 `scripts/ad_hoc_queries/top_n.py`（空 stub + 注册）
- 新建 `scripts/ad_hoc_queries/export_excel.py`（空 stub + 注册）
- 新建 `scripts/ad_hoc_queries/dq_report.py`（空 stub + 注册）
- 新建 `scripts/ad_hoc_queries/ask.py`（空 stub + 注册）
- 新建 `scripts/ad_hoc_query_excel_styles.py`（完整实现）
- 更新 `scripts/ad_hoc_queries/registry.py`：注册 7 个新 QuerySpec

### Step 2: 实现 service 调用层（2h）
每个 query 文件：
1. `from backend.services.metrics.audience_summary import calculate_audience_summary`（按需）
2. `from backend.services.metrics.audience_table import get_audience_table`（按需）
3. `from backend.services.rfm.service import get_rfm_distribution`（按需）
4. 调 service 函数，传参
5. 把 service 返回 dict 转成 `List[List[Any]]`（rows）+ `headers`
6. **不要写 SQL，不要直连 DuckDB**

### Step 3: export-excel 多 sheet 装配（2h）
- 走 openpyxl，11 个 sheet 顺序按用户偏好
- 复用 Step 2 各个 query 的 service 调用结果，**不独立 SQL**
- 视觉样式严格按第 5.3 节
- 0 公式

### Step 4: dq-report 15 项校验（1.5h）
- 逐项实现，参考 backend/tests 里现成的校验模式
- WARN/ERROR 分级
- 不调 LLM，纯规则

### Step 5: ask 路由（1h）
- 关键词字典（dict[str, callable]）
- 简单正则提取日期、year、period
- 不命中回退 list-endpoints

### Step 6: pytest 配套（1.5h）
- `backend/tests/test_ad_hoc_query_two_year.py` (5 case: 2026/2025/同比 三列、单位 %/pp、exclude_channels、format xlsx、auto-path)
- `backend/tests/test_ad_hoc_query_export_excel.py` (3 case: 11 sheet 顺序、视觉样式 hex、0 公式)
- `backend/tests/test_ad_hoc_query_dq_report.py` (5 case: 完整性、YOY 范围、子项之和、渠道覆盖、ETL flag)
- `backend/tests/test_ad_hoc_query_ask_router.py` (5 case: 4 个关键词命中 + 1 个不命中回退)

**pytest baseline 要求**：新增 case 全部 PASS，不退化现有 795/72/0。

### Step 7: 跑全量验证（30min）
```bash
cd /Users/hutou/Desktop/fuqin-date/wt-main-active
export DUCKDB_PATH="$(pwd)/data/processed/fuqing_crm.duckdb"
PYTHONPATH="$(pwd)" pytest backend/tests/ -x -q
PYTHONPATH="$(pwd)" python3 scripts/ad_hoc_query.py list-endpoints  # 验证 9 个 query 都注册
PYTHONPATH="$(pwd)" python3 scripts/ad_hoc_query.py two-year-overview --year 2026 --start 2026-01-01 --end 2026-06-30 --format xlsx --output /tmp/test_two_year.xlsx
PYTHONPATH="$(pwd)" python3 scripts/ad_hoc_query.py dq-report --start 2026-01-01 --end 2026-06-30 --full
```

---

## 7. 硬约束（**0 妥协**）

### 7.1 禁止

1. ❌ 直连 DuckDB（`duckdb.connect(...)` 禁出现在 `scripts/ad_hoc_queries/` 下任何新文件）
2. ❌ inline SQL（`SELECT * FROM orders WHERE ...` 写在 ad-hoc 文件里就违规）
3. ❌ 写库（任何 `INSERT/UPDATE/DELETE`）
4. ❌ 调 LLM（`ask` 子命令必须规则路由，不调 OpenAI/Anthropic API）
5. ❌ 前端依赖（Vue 组件、axios、frontend-vue3 任何引用）
6. ❌ 公式（Excel 单元格 value 必须是数值/字符串，不接受 `=A1+B1` 公式字符串）
7. ❌ 改 `backend/services/*` 已存在函数（复用，不动）
8. ❌ 改 `frontend-vue3/*` 任何文件
9. ❌ 改 `scripts/run_etl.py` `scripts/etl/cli.py` `backend/db/connection.py`
10. ❌ 改 `backend/contracts/schemas.py`（如需新字段，先回 Claude）

### 7.2 必须

1. ✅ 走 backend service 函数（方案 A）
2. ✅ 走 `FilterBuilder` 或已封装 service（不直接拼 SQL）
3. ✅ 走 `backend/contracts/schemas.py` Pydantic 类型（返回 dict 也行，但要 match schema）
4. ✅ pytest case 全 PASS
5. ✅ ruff check 干净
6. ✅ audit log 留 `/tmp/fuqing_adhoc_audit.log`
7. ✅ auto-path 走 `~/Desktop/fuqin date/取数/<year>年/<生成日期>/...`
8. ✅ 时间窗口 ≤ 366 天（防 OOM）
9. ✅ YOY 范围 `|v| > 1e6` → None
10. ✅ 路径 sanitize 防 `../`

---

## 8. 测试隔离

- 测试用 `FQ_TAKE_ROOT=/tmp/test_take_root` env var 隔离
- 测试用 `monkeypatch` 注入 mock service 返回值，**不要 mock `duckdb.connect`**
- 测试用 `tmp_path` fixture 写临时 XLSX

---

## 9. 输出交付物（Codex Stage 2 完成时）

1. **代码文件**：7 个新 query + 1 个 excel styles + 8 个新 pytest case
2. **本地跑通**：所有 pytest PASS + 手动跑 2-3 个 query 出结果
3. **不动 git**：不要 `git add / commit / push`，留给 Claude 走 12 步流程
4. **回报 Claude**：用 prose 报告改了哪些文件、新增多少行、pytest 数量

---

## 10. 风险清单

| 风险 | 治本 |
|---|---|
| Service 函数返回 None | 加 None 守卫 |
| YOY 单位混淆 | 严格按 schema 字段类型（`PpField` vs `PercentageField`） |
| XLSX 大文件 | 限制 sheet 行数 ≤ 10000 |
| openpyxl 公式残留 | 所有单元格 `value=` 数值，不接受公式字符串 |
| ETL 跑批中查询 | `/tmp/.etl_running.flag` 检测 + WARN |
| pytest fixture 与真实 DuckDB 冲突 | 走 service 注入，**禁直连 DuckDB** |

---

## 11. 验收标准（Claude Stage 3 review 时会查）

1. ✅ 9 个子命令全部注册（`ad_hoc_query.py list-endpoints` 列出 9 个）
2. ✅ pytest 全绿，新增 18 case（5+3+5+5），baseline 不退化
3. ✅ ruff check 干净
4. ✅ manual smoke test：`export-excel --start 2026-01-01 --end 2026-06-30` 跑通，XLSX 文件 11 sheet 齐全
5. ✅ `dq-report --full` 跑通，15 项校验都实现
6. ✅ `ask --text "最近7天各渠道GSV"` 路由到 `channel-slice` 并执行
7. ✅ 0 直连 DuckDB（grep `duckdb.connect` 在 `scripts/ad_hoc_queries/` 下 0 命中）
8. ✅ 0 公式（grep `=` 在 `scripts/ad_hoc_query_excel_styles.py` 周边代码 0 公式残留）
9. ✅ 0 前端引用（grep `frontend-vue3|axios|Vue` 在新文件 0 命中）
10. ✅ audit log 有 9 个子命令的执行记录

---

## 12. 联系架构师

如有以下情况，停下来回报 Claude：

- backend service 函数签名跟你预期不符
- 字段在 schema 找不到
- R 6 桶口径有歧义
- 视觉规范有歧义
- pytest baseline 已退化

不要自己拍板改 backend 或前端。

---

> **签名**：Claude Code（架构师）
> **日期**：2026-06-30
> **分支**：`feature/sprint171-ad-hoc-query-v2`

---

# ADDENDUM v2 (2026-06-30) — Codex 阻塞点回执

> 本节覆盖 v1 第 4.2 节的部分内容，由架构师根据 Codex 反馈的 3 个 STOP 条件修正。

## A. RFM service 真实路径（替代 v1 写错的 `service.py`）

**v1 错误**：`backend/services/rfm/service.py:get_rfm_distribution`（**不存在**）。

**真实路径**：`backend/services/rfm/` 是包，真实入口：

```python
from backend.services.rfm.r_flow import get_rfm_r_flow      # R 区间分布（替代 get_rfm_distribution）
from backend.services.rfm.f_flow import get_rfm_f_flow      # F 频次分布
from backend.services.rfm.m_flow import get_rfm_m_flow      # M 金额分布
from backend.services.rfm import get_rfm_flow               # 综合 flow
from backend.services.rfm.extended import get_user_rfm_extended  # 单用户 RFM
```

**`rfm-repurchase` 子命令实现**：

```python
from backend.services.rfm.r_flow import get_rfm_r_flow

def run_rfm_repurchase(start: str, end: str, channel: str | None = None) -> list[list]:
    result = get_rfm_r_flow(
        start_date=start,
        end_date=end,
        channel=channel,
        metric_type="GMV",  # 或 GSV，按需
    )
    # result 包含 R 6 桶 × {人数, GSV, AUS, 占比, 复购率}
    rows = []
    for r_seg in result["r_segments"]:  # 6 桶
        rows.append([
            r_seg["name"],               # "近1个月已购客" 等
            r_seg["user_count"],
            r_seg["gsv"],
            r_seg["aus"],
            r_seg["repurchase_rate"],
            r_seg["share_pct"],          # 占比，已 *100
        ])
    return rows
```

**headers**：`["R 区间", "人数", "GSV", "AUS", "复购率(%)", "占比(%)"]`

## B. R 6 桶真实口径（替代 v1 写错的 R1=0-7/R2=8-30...）

**v1 错误边界**：`R1=0-7 / R2=8-30 / R3=31-60 / R4=61-90 / R5=91-180 / R6=181+`（**不在代码里**）。

**真实口径**（`backend/semantic/segments.py:R_INTERVALS`，Sprint 60+ 沉淀公共 SSOT）：

| 中文名 | 天数范围 | 含义 |
|---|---|---|
| `近1个月已购客` | 0-30 | 最近 30 天内 |
| `近2-3个月已购客` | 31-90 | 30 天前 ~ 90 天内 |
| `近4-6月已购客` | 91-180 | 90 天前 ~ 180 天内 |
| `近7-12个月已购客` | 181-365 | 180 天前 ~ 365 天内 |
| `近13个月-近24个月已购客` | 366-730 | 365 天前 ~ 730 天内 |
| `2年外已购客` | 731+ | 730 天前之外 |
| `已购客TTL` | — | 汇总 |

**规则**：
- 写代码时**直接复用** `from backend.semantic.segments import R_SEGMENT_ORDER`（7 项含 TTL）
- 不要硬编码 R1-R6 编号
- 不要硬编码天数边界
- Excel Sheet 04 表头用 `R_SEGMENT_ORDER[0:6]`（不含 TTL）

## C. 旧 MVP query 重构决策（替代 v1 的「不要重写」）

**v1 矛盾**：
- v1 第 7.1 节：禁 inline SQL、禁直连 DuckDB
- v1 第 2 节：列了 `daily_gsv.py` / `yoy_battle.py` / `channel_slice.py` 作为「已存在范本」
- 这 3 个文件本身就用 `read_only_conn` + inline SQL

**架构师决策（v2）**：

### C.1 旧 3 个 MVP query + `_utils.py`：**保留**，不重构

理由：
1. 现有 29 个 pytest case（`test_ad_hoc_query.py` 23 + `test_ad_hoc_query_sprint61plus.py` 6）全 PASS
2. 重构会破坏这些 case，需要重写，工作量大
3. `read_only_conn` + `duckdb.connect(read_only=True)` 跟 uvicorn 共存安全（Sprint 53 race flake 治本模式）
4. 这 3 个 query 是 Sprint 61+62 MVP，跑了一年半验证

### C.2 必须在 3 个旧文件顶部加 docstring 说明

```python
# scripts/ad_hoc_queries/daily_gsv.py
"""
Sprint 171 决策（架构师拍板）：
- 保留 read_only_conn + inline SQL 实现，不重构走 service
- 理由：29 个 pytest case 已 PASS，重构风险大于收益
- read_only=True 跟 uvicorn 单例共存安全（Sprint 53 race flake 治本）
- 本文件不计入「scripts/ad_hoc_queries/ 下 duckdb.connect 0 命中」验收（新文件才计入）
"""
```

`yoy_battle.py` / `channel_slice.py` / `_utils.py` 同样加。

### C.3 验收标准**修改**

v1 第 11 节验收标准第 7 条「scripts/ad_hoc_queries/ 下 duckdb.connect 0 命中」**改为**：

- ✅ **`scripts/ad_hoc_queries/` 下**新文件** `duckdb.connect` 0 命中**（grep 验证）
- ✅ 旧文件（`daily_gsv.py` / `yoy_battle.py` / `channel_slice.py` / `_utils.py`）允许保留 `read_only_conn`，但必须加 Sprint 171 docstring 顶部说明（4 个文件都要加）

## D. 其他 service 真实路径（v1 写错的补充）

| v1 写的 | 真实路径 |
|---|---|
| `backend/services/metrics/audience_summary.calculate_audience_summary` | ✅ 正确 |
| `backend/services/metrics/audience_table.get_audience_table` | ✅ 正确（文件实际是 `backend/services/metrics/audience_table.py`，函数名也是 `get_audience_table`，但需要核对 schema） |
| `backend/services/rfm/service.py:get_rfm_distribution` | ❌ **不存在**，改成 `backend/services/rfm/r_flow.get_rfm_r_flow`（见 A） |
| `backend/services/metrics/overview.get_daily_trend` | ✅ 存在，可用于未来重构 daily-gsv（非 Sprint 171 范围） |

## E. Stage 2 验收标准（v2 修订版）

| # | 标准 | 状态 |
|---|---|---|
| 1 | 9 个子命令全部注册（`list-endpoints` 列出 9 个） | ✅ 必须 |
| 2 | pytest 全绿，新增 18 case（5+3+5+5），baseline 795 + 18 = 813 期望 | ✅ 必须 |
| 3 | ruff check 干净 | ✅ 必须 |
| 4 | manual smoke test：`export-excel --start 2026-01-01 --end 2026-06-30` 跑通，XLSX 11 sheet 齐全 | ✅ 必须 |
| 5 | `dq-report --full` 跑通，15 项校验都实现 | ✅ 必须 |
| 6 | `ask --text "最近7天各渠道GSV"` 路由到 `channel-slice` 并执行 | ✅ 必须 |
| 7 | `scripts/ad_hoc_queries/` 下**新文件** `duckdb.connect` 0 命中（grep 验证） | ✅ 必须（**v2 修改**） |
| 8 | 旧 4 个文件（`daily_gsv.py` / `yoy_battle.py` / `channel_slice.py` / `_utils.py`）顶部加 Sprint 171 docstring 说明 | ✅ 必须（**v2 新增**） |
| 9 | `scripts/ad_hoc_queries/` 下**新文件** 0 前端引用（grep `frontend-vue3|axios|Vue` 0 命中） | ✅ 必须 |
| 10 | audit log 有 9 个子命令的执行记录 | ✅ 必须 |

---

> **ADDENDUM v2 签名**：Claude Code（架构师）
> **日期**：2026-06-30
> **覆盖范围**：v1 第 2 / 4.2 / 7.1 / 11 节
> **不变部分**：v1 第 1 / 3 / 4.1 / 5 / 6 / 7.2 / 8 / 9 / 10 / 12 节继续有效

---

# ADDENDUM v3 (2026-06-30) — codegraph 教训 + R 6 桶 vs 老客 防串台

## F. codegraph 教训（架构师自身失误）

**v1 R 6 桶写错根因**：架构师**没调 codegraph 也没 Read 实际文件**，凭 MEMORY.md 记忆脑补了 `R1=0-7 / R2=8-30 / R3=31-60 / R4=61-90 / R5=91-180 / R6=181+`，跟代码真实 `R_INTERVALS` (0-30 / 31-90 / 91-180 / 181-365 / 366-730 / 731+) 完全不一致。

**Codex 反馈 STOP**：发现代码里根本不是这个边界。

**架构师永久规则（v3 起执行）**：

1. 写代码相关业务规格前，**必须**用 `codegraph_search` 查实际值：
   ```bash
   mcp__codegraph__codegraph_search "R_INTERVALS R_SEGMENT_ORDER"
   ```
2. **不脑补业务口径**，口径 SSOT 都在代码里（跟 L4.20 SSOT 反漂移配套）
3. 跨 sprint 业务变更（如 Sprint 170 R 8→6 桶），**必须** Read 实际 `backend/semantic/*.py` 看新边界
4. 业务口径相关 SPEC 写完后，加一句 `git grep "<关键字段>" backend/ --include="*.py"` 实证

## G. R 6 桶 vs 老客分析 防串台硬规则

**风险场景**：
- 用户看 Sheet 02「老客 GSV 占比 60%」再切到 Sheet 04「近 1 个月已购客 GSV」
- 「老客」≠「近 1 个月已购客」（老客可能 6 个月没来了）
- 两 sheet 如果用裸 `gsv` 字段名无前缀区分，**人会看错**

### G.1 字段命名严格分离

| Sheet | 字段前缀 | 走 service |
|---|---|---|
| Sheet 02 新老客 30 指标 | `new_gsv` / `old_gsv` / `member_gsv` / `all_gsv` / `new_user_count` / ... | `calculate_audience_summary` |
| Sheet 04 复购周期 RFM | `r_seg_name` / `r_seg_user_count` / `r_seg_gsv` / `r_seg_repurchase_rate` / `r_seg_share_pct` | `get_rfm_r_flow` |
| Sheet 09 渠道概览 | `channel_name` / `channel_gsv` / `channel_user_count` | `channel-slice` 内部 |

**硬规则**：
- ❌ 任何 sheet 不能用裸 `gsv` / `users` / `aus` 字段名
- ✅ 必须带 sheet 专属前缀（`new_` / `old_` / `r_seg_` / `channel_`）
- ❌ Sheet 02 和 Sheet 04 不共享任何中间变量

### G.2 service 调用严格分离

```python
# ✅ Sheet 02 装配 (export_excel.py)
from backend.services.metrics.audience_summary import calculate_audience_summary

def build_sheet_02_new_old_customer(start, end, exclude_channels):
    result = calculate_audience_summary(  # 不返回 R 分布
        year=2026,
        metric_type="GSV",
        start_date=start,
        end_date=end,
        exclude_channels=exclude_channels,
    )
    # 只用 result["indicators"] 跟 result["channel_all"]
    # 不用 result 里的 rfm 相关字段（如果有）
    return build_new_old_rows(result)
```

```python
# ✅ Sheet 04 装配 (export_excel.py)
from backend.services.rfm.r_flow import get_rfm_r_flow

def build_sheet_04_rfm_repurchase(start, end, channel):
    result = get_rfm_r_flow(  # 只返回 R 6 桶，不返回新老客
        start_date=start,
        end_date=end,
        channel=channel,
        metric_type="GMV",
    )
    # 只用 result["r_segments"]
    # 不用 result 里的 new/old/member 字段（如果有）
    return build_rfm_rows(result["r_segments"])
```

**硬规则**：
- ❌ 不在 `export_excel.py` 顶层调一次 service 后拆给多个 sheet 复用
- ✅ 每个 sheet 调**独立**的 service 函数，独立参数

### G.3 XLSX 表头用合并单元格明示维度

```
Sheet 02 表头（一级 + 二级）：
| 维度: 新老客       | GSV_2026 | GSV_2025 | GSV_yoy | 人数_2026 | 人数_2025 | 人数_yoy | AUS_2026 | AUS_2025 | AUS_yoy |
| 全店 (all)         |   ...    |   ...    |   ...   |    ...    |    ...    |   ...    |    ...   |    ...   |   ...   |
| 新客 (new)         |   ...    |   ...    |   ...   |    ...    |    ...    |   ...    |    ...   |    ...   |   ...   |
| 老客 (old)         |   ...    |   ...    |   ...   |    ...    |    ...    |   ...    |    ...   |    ...   |   ...   |
| 会员 (member)      |   ...    |   ...    |   ...   |    ...    |    ...    |   ...    |    ...   |    ...   |   ...   |

Sheet 04 表头（一级 + 二级）：
| 维度: R 区间       | 人数 | GSV | AUS | 复购率(%) | 占比(%) |
| 近1个月已购客     | ...  | ... | ... |   ...     |   ...   |
| 近2-3个月已购客   | ...  | ... | ... |   ...     |   ...   |
| 近4-6月已购客     | ...  | ... | ... |   ...     |   ...   |
| 近7-12个月已购客   | ...  | ... | ... |   ...     |   ...   |
| 近13-24个月已购客 | ...  | ... | ... |   ...     |   ...   |
| 2年外已购客       | ...  | ... | ... |   ...     |   ...   |
| 已购客TTL         | ...  | ... | ... |   ...     |   ...   |
```

### G.4 新文件顶部必须加 docstring 防混用

```python
# scripts/ad_hoc_queries/new_old_customer.py 顶部 docstring
"""
Sprint 171 防串台硬规则:
- 本文件只走 calculate_audience_summary，不返回 R 区间分布
- 字段前缀 new_*/old_*/member_*/all_*，绝不混用 r_seg_*
- 跟 rfm_repurchase.py 完全独立，绝不复用中间 dict / 变量
"""

# scripts/ad_hoc_queries/rfm_repurchase.py 顶部 docstring
"""
Sprint 171 防串台硬规则:
- 本文件只走 get_rfm_r_flow，不返回新老客分布
- 字段前缀 r_seg_*，绝不混用 new_*/old_*/member_*
- 跟 new_old_customer.py 完全独立，绝不复用中间 dict / 变量
"""
```

## H. Stage 2 验收标准（v3 修订版，最终）

| # | 标准 | 状态 |
|---|---|---|
| 1 | 9 个子命令全部注册（`list-endpoints` 列出 9 个） | ✅ 必须 |
| 2 | pytest 全绿，新增 18 case（5+3+5+5），baseline 795 + 18 = 813 期望 | ✅ 必须 |
| 3 | ruff check 干净 | ✅ 必须 |
| 4 | manual smoke test：`export-excel --start 2026-01-01 --end 2026-06-30` 跑通，XLSX 11 sheet 齐全 | ✅ 必须 |
| 5 | `dq-report --full` 跑通，15 项校验都实现 | ✅ 必须 |
| 6 | `ask --text "最近7天各渠道GSV"` 路由到 `channel-slice` 并执行 | ✅ 必须 |
| 7 | `scripts/ad_hoc_queries/` 下**新文件** `duckdb.connect` 0 命中（grep 验证） | ✅ 必须 |
| 8 | 旧 4 个文件（`daily_gsv.py` / `yoy_battle.py` / `channel_slice.py` / `_utils.py`）顶部加 Sprint 171 docstring 说明 | ✅ 必须 |
| 9 | `scripts/ad_hoc_queries/` 下**新文件** 0 前端引用（grep `frontend-vue3\|axios\|Vue` 0 命中） | ✅ 必须 |
| 10 | audit log 有 9 个子命令的执行记录 | ✅ 必须 |
| **11** | **新文件** `new_old_customer.py` 和 `rfm_repurchase.py` 顶部加防串台 docstring | ✅ **v3 新增** |
| **12** | **新文件** Sheet 02 / Sheet 04 / Sheet 09 字段前缀严格分离（grep `_gsv\b` 验证不带前缀的 `gsv` 裸字段在 export_excel.py 里 0 命中） | ✅ **v3 新增** |
| **13** | **新文件** `export_excel.py` 每个 sheet 调独立 service 函数，不复用中间 dict | ✅ **v3 新增** |

---

> **ADDENDUM v3 签名**：Claude Code（架构师）
> **日期**：2026-06-30
> **覆盖范围**：v2 + F (codegraph 教训) + G (防串台) + H (验收标准 11/12/13)
> **永久规则**：F 节 codegraph 教训 + G 节防串台硬规则 进 L4.x 永久规则候选（Sprint 172 评估）