# 芙清 CRM — AI 执行手册

> 本文件是项目的唯一权威参考。AI 每次启动时优先加载「必读·启动项」，按需查阅各章节。
> 详细文档见 `docs/DOCUMENT-INDEX.md`。

---

## 必读·启动项

> 每次对话开始时，首先加载以下信息。任何任务都以此为前提。

| # | 事实 | 说明 |
|---|---|---|
| 1 | **本地即生产** | GitHub merge 后，必须 `git pull origin main --ff-only` + `kill + 重启 uvicorn`，否则服务跑旧代码 |
| 2 | **层边界不可跨越** | 语义层定义口径 → 服务层处理逻辑 → 契约层定义 Schema；三层禁止互相渗透 |
| 3 | **Schema 变动三同步** | Service 改字段 → `contracts/schemas.py` → 前端 `types.ts`，三者必须同步 |
| 4 | **版本状态** | v0.3.3（main），测试 140 passed / 8 skipped / 0 failed |
| 5 | **ETL 状态** | user_rfm 最大日期 2026-05-28, orders 最大日期 2026-05-28 |
| 6 | **禁止事项（Git）** | ❌ 跳过 review/qa ❌ merge 后不 pull ❌ 直接在 main commit ❌ commit -m "fix" |
| 7 | **认证** | `.env` 中 `FQ_CRM_PASSWORDS` 配置登录密码，未配置时启动自动生成随机密码 |
| 8 | **安全** | CSO 审计已通过，5 个修复已合并：安全响应头 / 审计日志签名 / 非特权 nginx / 健康检查脱敏 |

---

## 索引

> 按需查阅。高优先级章节是每次相关操作都必须完整执行的流程。

| 优先级 | 章节 | 触发条件 |
|--------|------|---------|
| 🔴 必走 | [Git 工作流 + 禁止事项](#git-工作流) | commit / merge / push 前 |
| 🔴 必走 | [接口开发六步](#新增修改接口必走六步) | 新增或修改后端接口时 |
| 🔴 必走 | [包拆分检查清单](#包拆分检查清单) | 拆分大文件为包时 |
| 🟡 按需 | [语义层参考](#语义层口径) | 口径/渠道/计算规则疑问时 |
| 🟡 按需 | [Skill 路由](#skill-路由) | 不确定用哪个 skill 时 |
| 🟢 参考 | [快速启动命令](#快速启动) | 启动服务 / 跑 ETL / 跑测试时 |
| 🟢 参考 | [目录结构](#目录结构) | 新建文件不知道放哪时 |
| 🟢 参考 | [架构五层](#架构五层) | 需要全局视野时 |

---

## Git 工作流

### 禁止事项（每次 commit / merge 前必检查）

> 以下是导致线上事故的高频错误，发现任意一条立刻停止当前操作。

| # | 禁止行为 | 真实教训 |
|---|---|---|
| 1 | 跳过 `review` skill 直接 commit | 2026-05-28：拆分 `dmp_asset_service` 时漏掉 7 个辅助函数，线上 500 |
| 2 | 跳过 `qa` skill 直接 merge | 必须跑完 qa 才能 merge main |
| 3 | merge + push 后不 pull | 2026-05-28：GraphQL API merge 后 GitHub 有新代码，本地 main 没更新，uvicorn 跑旧代码 |
| 4 | 直接在 main 分支 commit | 必须通过 feature 分支 PR 流程 |
| 5 | `commit -m "fix"` / `"asdf"` / `"update"` | 提交信息必须说明改了什么 |
| 6 | commit 混多个不相关功能 | 按逻辑分批次提交 |
| 7 | commit 后不 push | 代码在本地 = 代码丢了 |

### 正确流程（12 步，顺序不得调整）

```
① git checkout -b feature/xxx
  ↓
② 写代码
  ↓
③ pytest backend/tests/ -x -q
  ↓
④ review skill — commit 前自检
  ↓
⑤ 修复 review 发现的问题
  ↓
⑥ git commit -m "feat: xxx"
  ↓
⑦ git push origin feature/xxx
  ↓
⑧ qa skill — 功能验收
  ↓
⑨ git checkout main && git merge feature/xxx --no-ff
  ↓
⑩ git push origin main
  ↓
⑪ git pull origin main --ff-only   ← 本地即生产，必须同步
  ↓
⑫ kill 并重启 uvicorn
```

**Skill 映射**：`review` → commit 前 · `qa` → merge 前 · `ship` → 大功能推送前

---

## 新增/修改接口必走六步

> 每次新增或修改后端接口时，按顺序完整执行，不得跳过。

### Step 1 — 口径先找语义层（禁止硬编码）

```python
# ✅ 正确：引用语义层
from backend.semantic.filters import OrderFilters
valid_sql, _ = OrderFilters.valid_order()

# ❌ 禁止：在 Service 里硬编码口径
"order_status LIKE '%成功%'"    # 会误杀有效订单
"is_goujinjin = FALSE"
```

语义层唯一真实数据源：
- `backend/semantic/filters.py` → 过滤条件（有效订单/GMV/GSV）
- `backend/semantic/channels.py` → 渠道映射（DB_TO_UI / UI_TO_DB）
- `backend/semantic/calculations.py` → YOY/MOM/safe_ratio
- `backend/semantic/segments.py` → RFM 分群阈值

### Step 2 — Service 连接规范

```python
conn = get_connection()
try:
    result = conn.execute(sql, params).fetchall()
finally:
    conn.close()   # 禁止遗漏
```

- **DuckDB 用 `?` 参数化所有动态值（日期/渠道/金额等），禁止 f-string 拼接 SQL**
- **CASE WHEN 中的动态比较值（如 `DATE ?`）也要参数化，不能用 `f"'{date}'"`**
- 列名动态化走白名单字典（如 `SPU_LEVELS`），禁止直接拼接
- ⚠️ 教训（2026-05-29）：`breakdown_service/_shared.py` 4个函数用 f-string 拼接日期参数，修复后统一改为 `conn.execute(sql, [p1, p2, ...])`

### Step 3 — 渠道参数统一展开

```python
from backend.semantic.filters import expand_channels
db_channels = expand_channels([channel])
db_exclude = expand_channels(exclude_channels)
```

### Step 4 — Schema 三同步（最容易遗漏）

```
backend/services/xxx_service.py  →  改返回字段
backend/contracts/schemas.py     →  同步 Pydantic model
frontend-vue3/src/api/xxx.ts    →  同步 TypeScript interface
```

- 新增字段：Schema 加默认值（`float = 0.0`），前端加 `?` 可选
- 删除字段：三者同时删除，不留死字段
- **最常见 crash**：Pydantic 缺字段 → FastAPI 静默过滤 → 前端 undefined → 白屏

### Step 5 — 前端只做展示，不做业务计算

```ts
// ✅ 正确：后端算好，前端展示
{ title: '渗透率', render: (row) => `${(row.penetration_rate * 100).toFixed(1)}%` }

// ❌ 禁止：前端自己算 YOY / 占比 / 客单价
const ratio = (current - previous) / previous
```

### Step 6 — 三层验证

1. Python import：`from backend.main import app`
2. 后端测试：`pytest backend/tests/ -x -q`
3. 前端类型：`vue-tsc --noEmit`

---

## 包拆分检查清单

> 拆分 `xxx.py` 为 `xxx/` 包时必做，少一步就可能线上 500。
>
> ⚠️ 2026-05-28 真实事故: `dmp_asset_service` 拆分丢 7 个辅助函数 → 线上 500；
> 同日 `rfm_service` 拆分丢 `get_connection` / `yoy_absolute` / `yoy_repurchase_rate` / `expand_channels` → 再次 500。
> 根因相同: 拆分子模块时只复制了业务代码，没梳理跨文件的函数调用关系。

### 强制执行流程（顺序不可跳过）

```bash
# Step 1 — 交叉导入校验（自动发现所有遗漏的 NameError）
# 对每个子模块单独 import，触发顶层代码执行，捕获 NameError
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
# 确保 _shared.py 导出了所有子模块共享的依赖（至少检查这 3 类）
grep -rn "get_connection\|expand_channels\|yoy_absolute\|yoy_repurchase_rate\|PeriodBuilder" backend/services/xxx/ | grep -v "_shared.py"
# ↑ 如果有输出，说明这些函数在某子模块中使用了但 _shared.py 未导出 → 补齐 _shared.py

# Step 3 — 全量测试
PYTHONPATH="$(pwd)" pytest backend/tests/ -x -q
```

### 关键教训

子模块的 `from _shared import *` 是一条单向依赖链。**拆分时先把所有共享依赖从单体文件提取到 `_shared.py`，再分割业务逻辑。** 反过来做（先拆再补导入）必然漏。

**教训（2026-05-28）**：`dmp_asset_service` 拆分为 store.py / product.py / other.py 时，7 个共享辅助函数（`_check_reload` / `_parse_date` / `_load_data2` 等）全部丢失，导致 `name '_check_reload' is not defined` 线上 500。根因：提取代码段时只复制了表面，没有梳理段间的函数调用关系。同日 `rfm_analysis` 拆分也有类似问题。

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

## Skill 路由

> 当请求匹配以下场景时，**立即调用对应 Skill**，不得直接回答。

| 场景 | 触发词 | Skill |
|------|--------|-------|
| 报错 / 500 / 数据异常 | `调试`、`investigate`、`排查`、`出问题了`、`报错` | `investigate` |
| commit 前自检 | `review`、`代码审查`、`逻辑有没有问题`、`业务逻辑` | `review` |
| 功能上线前验收 | `qa`、`测试一下`、`验收`、`检查一下` | `qa` |
| 大功能推送前完整检查 | `发布`、`上线`、`部署`、`ship` | `ship` |

---

## 快速启动

```bash
# 后端（端口 8000）
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics"
export HEALTH_API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
PYTHONPATH="$(pwd)" nohup ~/.workbuddy/binaries/python/envs/default/bin/python -m uvicorn backend.main:app \
  --host 0.0.0.0 --port 8000 --reload --reload-dir backend >> /tmp/fuqin-crm-backend.log 2>&1 &

# 前端（端口 5173）
cd frontend-vue3 && npm run dev

# ETL 增量更新（必须用 homebrew Python 3.14，workbuddy Python 3.13 有代码签名冲突）
# 前置依赖：pyarrow（brew 装不了，pip 装 pre-built wheel）
#   /Users/hutou/homebrew/bin/python3 -m pip install pyarrow --only-binary :all: --break-system-packages
PYTHONPATH="$(pwd)" /Users/hutou/homebrew/bin/python3 scripts/run_etl.py --update

# RFM 预计算（ETL 完成后单独跑，600任务约10分钟）
PYTHONPATH="$(pwd)" /Users/hutou/homebrew/bin/python3 scripts/etl/preload_rfm.py --auto

# 跑测试
PYTHONPATH="$(pwd)" pytest backend/tests/ -v
```

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
├── CLAUDE.md              ← 本文件（项目参考）
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
│   │   ├── rfm/          ← RFM 区间流转
│   │   ├── breakdown_service/ ← 一键拆解
│   │   └── dmp_asset_service/ ← DMP 资产
│   ├── routers/           ← API 路由（16 个模块）
│   ├── db/                ← 数据库连接（get_connection）
│   └── tests/             ← 单元测试（8 个文件，148 个用例）
├── frontend-vue3/
│   └── src/
│       ├── views/         ← 页面组件
│       ├── components/     ← 公共组件
│       ├── api/           ← API 调用 + types.ts
│       └── stores/        ← Pinia 状态
├── scripts/               ← ETL 脚本
├── config/                ← 配置（健康评分、RFM 阈值）
├── data/                  ← DuckDB 主库（33G）
└── docs/                  ← 文档（backend/frontend/deploy/ai/product）
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

---

## 历史教训（来自真实事故，非理论）

> 每次教训都是真实 bug，每个禁止规则背后都有一段事故史。AI 必须将这些视为约束条件而非建议。

| 日期 | 事故 | 根因 | 教训 |
|------|------|------|------|
| 2026-05-29 | `breakdown_service` 4个函数 SQL 注入 | f-string 拼接日期到 SQL，用户输入未参数化 | DuckDB 所有动态值用 `?` 占位符，`conn.execute(sql, [p1, ...])` |
| 2026-05-28 | `dmp_asset_service` 线上 500 | 拆分为 3 个子模块时 7 个辅助函数全部丢失 | 包拆分必须用 AST 分析函数调用关系 |
| 2026-05-28 | GraphQL API merge 后服务仍跑旧代码 | GitHub 有新代码，本地 main 没 pull，uvicorn 不知道 | **本地即生产**，merge 后必须 pull + 重启 |
| 2026-05-27 | `rfm_analysis` 线上 500 | 拆分 `rfm_analysis.py` 为包时缺少 `_read_db_cache` 等函数导入 | 包拆分时遗漏交叉导入 |

---

## 文档导航

| 文件 | 说明 |
|---|---|
| `MEMORY.md`（自动注入） | 修改代码规则 + 当前状态 + 历史教训 |
| `docs/DOCUMENT-INDEX.md` | 文档分类索引 |
| `docs/product/PRD-v3.0.md` | 产品需求文档 |
| `docs/飞书版架构文档/` | 系统架构文档（7 份） |
| `docs/ai/DESIGN.md` | AI 改代码操作规范 |
| `docs/frontend/frontend-contract-guide.md` | 前端契约指南 |
| `docs/deploy/DEPLOY.md` | 部署文档 |
