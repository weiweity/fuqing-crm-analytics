# 芙清 CRM — 参考手册

> 按需查阅，不自动加载。AI 在需要时主动 Read 本文件。
> 行为规则见 CLAUDE.md（每次会话自动加载）。

---

## 包拆分检查清单

> 拆分 `xxx.py` 为 `xxx/` 包时必做，少一步就可能线上 500。
>
> ⚠️ 2026-05-28 真实事故: `dmp_asset_service` 拆分丢 7 个辅助函数 → 线上 500；
> 同日 `rfm_service` 拆分丢 `get_connection` / `yoy_absolute` / `yoy_repurchase_rate` / `expand_channels` → 再次 500。

### 强制执行流程（顺序不可跳过）

```bash
# Step 1 — 交叉导入校验（自动发现所有遗漏的 NameError）
cd "/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics"
PYTHONPATH="$(pwd)" python3 -c "
import importlib, sys
modules = ['backend.services.xxx.sub1', 'backend.services.xxx.sub2']
for m in modules:
    try:
        importlib.import_module(m)
        print(f'OK: {m}')
    except NameError as e:
        sys.exit(f'MISSING IMPORT in {m}: {e}')
    except Exception as e:
        print(f'WARN: {m} raised {type(e).__name__}, but not NameError')
print('All submodules import cleanly')
"

# Step 2 — _shared.py 完整性检查
grep -rn "get_connection\|expand_channels\|yoy_absolute\|yoy_repurchase_rate\|PeriodBuilder" backend/services/xxx/ | grep -v "_shared.py"

# Step 3 — 全量测试
PYTHONPATH="$(pwd)" pytest backend/tests/ -x -q
```

### 关键教训

子模块的 `from _shared import *` 是一条单向依赖链。**拆分时先把所有共享依赖从单体文件提取到 `_shared.py`，再分割业务逻辑。** 反过来做（先拆再补导入）必然漏。

---

## 语义层口径

| 概念 | 定义 | 位置 |
|------|------|------|
| 有效订单 | `is_refund=FALSE AND order_status!='交易关闭'` | `filters.py` |
| GMV | 剔除购物金，含退款 | `filters.py` |
| GSV | 剔除购物金+退款 | `filters.py` |
| 新老客 cutoff | `pay_date - INTERVAL '1 day'` | 各 service 内联计算，禁止硬编码固定日期 |
| 禁止写法 | `LIKE '%成功%'` | 会误杀有效订单 |
| 渠道漏斗（9层） | U先派样→百补派样→赠品&0.01→达播/微博→直播→淘客→购物金→货架→其他 | `channels.py` |

---

## 架构五层

```
前端展示层  Vue3 + ECharts 5 + naive-ui + Tailwind CSS
    ↕ HTTP JSON
API 层      FastAPI + Pydantic（backend/main.py + routers/）
    ↕ 函数调用
服务层      backend/services/（业务逻辑）
    ↕ 函数调用
语义层      backend/semantic/（口径唯一真实数据源）
    ↕ DuckDB
数据层      data/processed/fuqing_crm.duckdb（33G）
```

契约层 `backend/contracts/schemas.py` 横跨 API 和前端：Pydantic → OpenAPI → TypeScript。

---

## 目录结构

```
fuqing-crm-analytics/
├── CLAUDE.md              ← AI 行为规则（自动加载）
├── README.md              ← 项目介绍
├── backend/
│   ├── main.py            ← FastAPI 入口（端口 8000）
│   ├── semantic/          ← 语义层（口径唯一真实数据源）
│   │   ├── filters.py     ← OrderFilters / FilterBuilder
│   │   ├── metrics.py     ← 指标注册表
│   │   ├── segments.py    ← RFM 分群（RFM_THRESHOLDS）
│   │   ├── channels.py    ← 渠道映射（DB_TO_UI/UI_TO_DB）
│   │   ├── time.py        ← PeriodBuilder（WTD/MTD/YTD/free）
│   │   └── calculations.py← YOY/MOM/safe_ratio
│   ├── contracts/
│   │   └── schemas.py     ← Pydantic 模型（统一导出，135个类）
│   ├── services/          ← 业务逻辑（按业务域拆分为包）
│   │   ├── category_service/  ← 品类分析
│   │   ├── health/        ← 老客健康分析
│   │   ├── metrics/       ← 指标服务
│   │   ├── rfm/           ← RFM 区间流转
│   │   ├── breakdown_service/ ← 一键拆解
│   │   └── dmp_asset_service/ ← DMP 资产
│   ├── routers/           ← API 路由（16 个模块）
│   ├── db/                ← 数据库连接（get_connection）
│   └── tests/             ← 单元测试（12 个文件，391+ passed / 12 skipped）
├── frontend-vue3/
│   └── src/
│       ├── views/         ← 页面组件
│       ├── components/    ← 公共组件
│       ├── api/           ← API 调用 + types.ts
│       └── stores/        ← Pinia 状态
├── scripts/               ← ETL 脚本
├── config/                ← 配置（健康评分、RFM 阈值）
├── data/                  ← DuckDB 主库（33G）
└── docs/                  ← 文档
```

---

## 测试文件

| 文件 | 覆盖 |
|---|---|
| `test_calculations.py` | YOY/MOM/safe_ratio/单位转换 |
| `test_filters.py` | OrderFilters/FilterBuilder/AmountExprBuilder |
| `test_time.py` | PeriodBuilder（7 种周期模式） |
| `test_channels.py` | 渠道漏斗/DB↔UI 映射 |
| `test_segments.py` | RFM 分群注册表/评分 SQL |
| `test_flow_service.py` | 人群流转服务 |
| `test_exceptions.py` | 异常类型与 HTTP 状态码 |
| `test_api_integration.py` | FastAPI 集成测试 |
| `test_health_overview.py` | 健康概览 |
| `test_rfm_analysis.py` | RFM 分析 |
| `test_fill_parquet_cache.py` | Parquet 缓存 |
| `test_etl_atomicity.py` | ETL 原子写入 |

---

## 历史教训（来自真实事故，非理论）

> 每次教训都是真实 bug，每个禁止规则背后都有一段事故史。

| 日期 | 事故 | 根因 | 教训 |
|------|------|------|------|
| 2026-05-31 | ETL 运行 1 小时 | RFM 预计算 540 个组合串行执行，每个全表扫描 | 使用 GROUPING SETS 合并 CTE，并行执行周期查询，3x 加速（修 W1 fix/wo1-mt1-grouping-sets）|
| 2026-05-31 | Parquet 缓存失效 | `_mark_all_files_processed` 只存 mtime 不存 hash，key 格式不统一 | 统一使用 `{mtime, hash}` 格式，key 使用相对路径 |
| 2026-05-31 | DuckDB 内存 Swap | memory_limit=12.7GB 超出物理内存 | 添加 `DUCKDB_MEMORY_LIMIT` 环境变量，默认 8GB |
| 2026-05-30 | 173 个 ruff lint 错误持续累积 | 无 pre-commit hook、无 CI，错误无人拦 | 三层防线：pre-commit (ruff) + pre-push (pytest) + GitHub Actions CI |
| 2026-05-30 | 老客GSV占比 pp 显示 155pp/193pp | `fmtYoy()` ×100 + MetricCard pp 模板 ×100 = 双重乘法 | pp 类型 MetricCard 用 `fmtPpt()` 直传原值，YOYBadge ratio 列用 `unit='pp'` + 调用方 ×100 |
| 2026-06-10 | Sprint 13 比率口径治理 | 33 处 100× + 1 处 10000× + 1 处 0% + Excel 4 处 + 8 处 unit 漏标 | 契约统一: 后端 `yoy_ratio` 返 pp 数值, 前端 `humanizeChange` 改 pass-through. 详见下文 **Ratio Convention** 章节 |
| 2026-05-30 | `_r_interval_sql` 安全设计决策 | DuckDB 不支持 `DATE ?` 语法 | 函数入口加 regex + `datetime.strptime` 双重校验 |
| 2026-05-30 | DuckDB INSERT 列数不匹配 | f-string 硬编码值容易漏列或多列 | 用参数化 INSERT `conn.execute(sql, [v1, v2, ...])` |
| 2026-05-30 | 测试 monkeypatch 目标错误 | `from x import get_connection` 把名称绑定到本地模块 | monkeypatch 目标必须是 use site，不是定义 site |
| 2026-05-30 | `check_future_date(None)` 崩溃 | mtd/wtd/ytd 模式下 None 触发 TypeError | 函数入口加 `if date_str is None: return None` 守卫 |
| 2026-05-30 | 日期正则接受无效日期 | regex 不验证日历有效性 | regex 后必须加 `datetime.strptime` 验证 |
| 2026-05-29 | `breakdown_service` SQL 注入 | f-string 拼接日期到 SQL | DuckDB 所有动态值用 `?` 占位符 |
| 2026-05-29 | 未来日期静默返回全0 | 日期参数无校验 | 所有日期参数端点必须调用 `check_future_date()` |
| 2026-05-29 | RFM 回购率虚高27-35% | `cutoff = end_date` 形成循环论证 | cutoff 必须为 `start_date - 1 day` |
| 2026-05-29 | `category/repurchase-flow` 全0 | RFM 象限名不一致（有无"客户"后缀） | 常量必须与生成它的 SQL 严格同步 |
| 2026-05-29 | breakdown UV 窗口不准确 | 参数注释说31实际41 | 注释必须与实现严格一致 |
| 2026-05-31 | DuckDB 并发崩溃 + 结果集覆盖 | `ThreadSafeConnection.execute()` 只在执行 SQL 时加锁，返回后另一个线程的 `execute()` 覆盖连接结果集；`fetchone()` 读到错误数据 | DuckDB 没有真正独立的 cursor — `execute()` 结果集绑定在连接上。`ThreadSafeCursor` 必须在构造时（锁内）预取全部结果到内存 |
| 2026-05-28 | `dmp_asset_service` 线上 500 | 拆分时 7 个辅助函数全部丢失 | 包拆分必须用 AST 分析函数调用关系 |
| 2026-05-28 | merge 后服务仍跑旧代码 | 本地 main 没 pull | merge 后必须 pull + 重启 |
| 2026-05-27 | `rfm_analysis` 线上 500 | 拆包时缺少交叉导入 | 包拆分时遗漏交叉导入 |

---

## 已知待修复

| 问题 | 优先级 | 说明 |
|------|--------|------|
| user_rfm 全局累计值 | P2 | ETL 预计算的 user_rfm 在查历史周期时 RFM 分类全部错误，需 ETL 重构 |
| 测试深度 | P2 | 当前测试以边界+结构验证为主，缺少业务逻辑验证 |

---

## Sprint 历史教训 (Sprint 5-8)

| 日期 | Sprint | 事故/问题 | 根因 | 教训 |
|------|--------|-----------|------|------|
| 2026-06-07 | Sprint 5 | DuckDB UNIQUE INDEX race condition | DuckDB 1.5.2 并发写入 UNIQUE INDEX 时 race | Fix A 拆 2 tx：先 DELETE 再 INSERT，避免单 tx 内 race |
| 2026-06-07 | Sprint 6 | 16 root test 失败 | pyproject.toml testpaths 配置错误 | 删 testpaths 恢复默认，16 root test 改 ignore |
| 2026-06-07 | Sprint 7 | P0 治根 10 root test fail | 测试文件路径和导入问题 | 修复测试文件路径，确保导入正确 |
| 2026-06-07 | Sprint 8 | YOYBadge 模式不统一 | 前端组件模式判断逻辑不一致 | 统一 YOYBadge 模式判断，R 桶 pre_cutoff 改 end_dt |

---

## Ratio Convention (Sprint 13 更新)

> 本节取代 line 148 旧规则。Sprint 11/12 的"前端 caller 散落 `*100`"模式已正式 deprecate，从 Sprint 13 起改用 **pass-through 契约**。
>
> 适用范围：所有 ratio / pct / ppt 类字段（YOY、MOM、占比、同比差、绝对值变化等）。

### 1. 旧规则 (Sprint 11/12) — DEPRECATE

- `MetricCard.vue` / `YOYBadge.vue` 的 `humanizeChange` 在 `unit='pp'` 时内部 `*100`，调用方传 0-1 decimal
- 前端 `fmtYoy` / `fmtYoY` / `fmtPctChange` 散落 `*100`
- 命名: `*_rate` / `*_ratio` / `*_pct` 含义模糊，依赖调用方自行判断
- 结果: 33 处 100× bug + 1 处 10000× bug（Sprint 13 audit 查出）

### 2. 新规则 (Sprint 13 起) — 当前生效

| 字段名后缀 | 数值范围 | 是否已 *100 | 典型字段 |
|---|---|---|---|
| `*_ratio` | 0-1 decimal | 否 | `old_gsv_ratio`, `member_ratio` |
| `*_pct` | 0-100 percentage | **是** | `gsv_yoy_pct`, `member_penetration_pct` |
| `*_ppt` | -100 ~ +100 pp 差 | **是** | `old_gsv_ratio_yoy_ppt`, `lock_rate_yoy_ppt` |
| `*_yoy` / `*_mom` | 按上面 3 种语义对应 | 视字段而定 | `gsv_yoy` (pct), `old_gsv_ratio_yoy` (ppt) |

**核心契约**:

- `yoy_ratio()` / `mom_ratio()` 返回 **pp 数值**（已 `*100`）— 例如 0.05 → 5.0
- `yoy_absolute()` / `mom_absolute()` 返回 **percentage**（已 `*100`）— 例如 0.25 → 25.0
- `audience_summary._extract_metrics` 不再 `*100` 存 ratio 字段（避免 10000× bug）
- `visitor_service` `rate - comp` 公式对齐其它 yoy 字段
- `churn.py:336` `new_customer_ratio` 真正实现（不 hardcode 0）

### 3. 命名约定（强制）

| 类型 | 命名 | 示例 | 说明 |
|---|---|---|---|
| 后端 ratio 字段 | `*_ratio` | `old_gsv_ratio` | 0-1 decimal，**前端展示需 `*100`** |
| 后端 percentage 字段 | `*_pct` | `gsv_yoy_pct` | 已 *100，前端直接 `toFixed(2)+'%'` |
| 后端 pp 差字段 | `*_ppt` | `old_gsv_ratio_yoy_ppt` | 已 *100，前端直接 `toFixed(2)+'pp'` |
| YOY/MOM 字段 | `*_yoy` / `*_mom` + 上面 3 种后缀 | `gsv_yoy_pct`, `lock_rate_yoy_ppt` | 类型由后缀决定 |
| 命名冲突 | `*_ratio_yoy` vs `*_yoy_ratio` | — | 禁止: 必须用 `*_yoy_ppt` 或 `*_yoy_pct` |

### 4. 字段单位速查表

| 场景 | 后端字段 | 单位 | 前端组件 | caller 传值 |
|---|---|---|---|---|
| 全店 GSV 同比 | `gsv_yoy` | % | `YOYBadge unit='%'` | 已 *100 (e.g. 14) |
| 老客 GSV 同比 | `old_gsv_yoy` | % | `YOYBadge unit='%'` | 已 *100 |
| 老客 GSV 占比同比 | `old_gsv_ratio_yoy` | pp | `YOYBadge unit='pp'` | 已 *100 (e.g. 5.28) |
| 锁权率 同比 | `lock_rate_yoy` | pp | `YOYBadge unit='pp'` | 已 *100 |
| 复购率 同比 | `repurchase_rate_yoy` | pp | `YOYBadge unit='pp'` | 已 *100 |
| 入会率 同比 | `member_join_rate_yoy` | pp | `YOYBadge unit='pp'` | 已 *100 |
| 老客 GSV 占比当前值 | `old_gsv_ratio` | ratio (0-1) | `MetricCard value` + caller `*100` | 0-1, 展示时 *100 |
| 30 指标对比表 ratio 列 | `*_ratio` | ratio (0-1) | `renderValue` `v.toFixed(2)+'%'` | 0-1, 展示时 *100 |

### 5. caller 模式示例

**示例 1: 占比 YOY（pp 类）**

```typescript
// 后端: old_gsv_ratio_yoy (pp 数值, 已 *100, e.g. 5.28)
<YOYBadge :value="row.old_gsv_ratio_yoy" unit="pp" />
// 显示: +5.28pp ↑
// MetricCard 内部 humanizeChange: caller 已 *100, 只做 abs + toFixed(2)
```

**示例 2: GSV YOY（% 类）**

```typescript
// 后端: gsv_yoy (percentage 数值, 已 *100, e.g. 14.0)
<YOYBadge :value="row.gsv_yoy" unit="%" />
// 显示: +14.00% ↑
// MetricCard 内部 humanizeChange: caller 已 *100, 只做 abs + toFixed(2)
```

**示例 3: 复购率 YOY（pp 类）**

```typescript
// 后端: repurchase_rate_yoy (pp 数值, 已 *100, e.g. 3.5)
<YOYBadge :value="row.repurchase_rate_yoy" unit="pp" />
// 显示: +3.50pp ↑
// RFMSegmentDrilldown.vue:174,194 fmtYoY 去掉 v * 100
```

### 6. 文档链接

- 行为规则：`CLAUDE.md` "Ratio Convention (Sprint 13+)" 章节
- 契约定义：`backend/semantic/calculations.py` docstring（`yoy_ratio` / `yoy_absolute`）
- 组件实现：`frontend-vue3/src/components/MetricCard.vue` + `YOYBadge.vue` `humanizeChange` JSDoc
- 改版历史：本文件 line 148 旧规则 + CHANGELOG.md v0.4.14.26 / v0.4.14.29

### 7. 禁止事项（lint 规则待加）

1. **前端 0 处散落 `* 100`** — caller 自乘，组件不乘
2. **命名冲突** — `*_ratio_yoy` vs `*_yoy_ratio` 二选一，强制用 `*_yoy_ppt` / `*_yoy_pct`
3. **hardcode 0 占位** — 禁止 `series = [0.0] * len(dates)` 之类占位（Sprint 13 P3 教训）
4. **Excel numFmt 错配** — pp 字段用 `'0.0"pp"'` 字面量后缀，% 字段用 `'0.0"%"'`
5. **YOYBadge / MetricCard 不传 unit** — 默认 `%`，但 ratio 类必须显式 `unit="pp"`

---

## ⚠️ 不要碰的文件

- `.env` — 包含密码，用 `.env.example` 代替
- `data/` — 33GB DuckDB 数据库，不进 git
- `.gstack/`、`.workbuddy/`、`.context/` — AI 工具私有目录
