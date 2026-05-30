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
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics"
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
│   └── tests/             ← 单元测试（8 个文件，149 个用例）
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
| 2026-05-30 | 173 个 ruff lint 错误持续累积 | 无 pre-commit hook、无 CI，错误无人拦 | 三层防线：pre-commit (ruff) + pre-push (pytest) + GitHub Actions CI |
| 2026-05-30 | 老客GSV占比 pp 显示 155pp/193pp | `fmtYoy()` ×100 + MetricCard pp 模板 ×100 = 双重乘法 | pp 类型 MetricCard 用 `fmtPpt()` 直传原值，YOYBadge ratio 列用 `unit='pp'` + 调用方 ×100 |
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

## ⚠️ 不要碰的文件

- `.env` — 包含密码，用 `.env.example` 代替
- `data/` — 33GB DuckDB 数据库，不进 git
- `.gstack/`、`.workbuddy/`、`.context/` — AI 工具私有目录
