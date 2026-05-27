# 芙清 CRM 客户分析系统 — 项目参考

> 本文件是项目的**结构和命令参考**。修改代码的规则在 MEMORY.md（系统自动注入）。
> 详细文档见 `docs/DOCUMENT-INDEX.md`。

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

# ETL 增量更新
PYTHONPATH="$(pwd)" ~/.workbuddy/binaries/python/envs/default/bin/python scripts/run_etl.py --update

# 跑测试
PYTHONPATH="$(pwd)" pytest backend/tests/ -v
```

---

## Git 工作流

### 提交规范（强制）
```
<type>: <subject>

feat     新功能
fix      Bug 修复
docs     文档改动
style    格式调整（不影响逻辑）
refactor 重构（不影响功能）
test     测试相关
chore    工具/构建/依赖

示例：feat: 新增人群看板RFM视图
```

### 提交步骤（强制，不得跳过）

```
① 写代码
  ↓
② 跑测试 — pytest backend/tests/ -x -q
  ↓
③ review skill — commit 前自检（找逻辑问题、SQL 安全、边界条件）
  ↓
④ 修复 review 发现的问题
  ↓
⑤ git commit（规范 message）
  ↓
⑥ git push
  ↓
⑦ qa skill — 功能验收（跑全量测试 + API 检查）
```

**对应 Skill**：
- `review` — commit 前必须调用，审查代码质量
- `qa` — push 后调用，验收测试
- `ship` — 大功能完成后，完整检查（测试 + 类型 + 文档 + 版本号）

```bash
cd fuqing-crm-analytics

# 1. 跑测试
PYTHONPATH="$(pwd)" pytest backend/tests/ -x -q

# 2. review（自动调用 Skill）
# 触发词：review、代码审查、逻辑有没有问题

# 3. 按逻辑分组提交
git add backend/services/health/    # 同一功能模块一起提交
git commit

# 4. 推送到 GitHub
git push origin main

# 5. qa 验收（自动调用 Skill）
# 触发词：qa、测试一下、验收、检查一下
```

### 分支策略
- 目前只用 `main`，单分支推进
- 大功能先用 `git stash` 暂存，分开提交
- commit message 模板：`.gitmessage`（自动生效）

### 禁止事项
- ❌ `git commit -m "fix"` / "update" / "asdf" — 提交信息必须说明改了什么
- ❌ 一次 commit 混多个不相关功能
- ❌ commit 后不 push — 代码在本地 = 代码丢了

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
数据层      data/processed/fuqing.duckdb
```

契约层 `backend/contracts/schemas.py` 横跨 API 和前端：Pydantic → OpenAPI → TypeScript。

---

## 目录结构

```
fuqing-crm-analytics/
├── CLAUDE.md              ← 本文件（项目参考）
├── README.md              ← 项目介绍
├── backend/
│   ├── main.py            ← FastAPI 入口
│   ├── semantic/          ← 语义层（口径定义）
│   │   ├── filters.py     ← OrderFilters / FilterBuilder
│   │   ├── metrics.py     ← 指标注册表
│   │   ├── segments.py    ← RFM 分群（SegmentRegistry）
│   │   ├── channels.py    ← 渠道映射（DB_TO_UI/UI_TO_DB）
│   │   ├── time.py        ← PeriodBuilder（WTD/MTD/YTD/free）
│   │   └── calculations.py← YOY/MOM/safe_ratio
│   ├── contracts/
│   │   └── schemas.py     ← Pydantic 模型（唯一来源）
│   ├── services/          ← 业务逻辑
│   │   └── health/        ← 老客健康分析（6 个子服务）
│   ├── routers/           ← API 路由
│   ├── db/                ← 数据库连接
│   ├── cache/             ← 缓存模块
│   └── tests/             ← 单元测试（8 个文件，148 个用例）
├── frontend-vue3/
│   ├── src/
│   │   ├── views/         ← 页面组件
│   │   ├── components/    ← 公共组件
│   │   ├── api/           ← API 调用 + types.ts
│   │   └── stores/        ← Pinia 状态
│   └── e2e/               ← E2E 测试
├── scripts/               ← ETL 和数据脚本
├── config/                ← 配置（健康评分、RFM 阈值）
├── data/                  ← 数据（raw/processed/parquet/cache）
├── docs/                  ← 文档（见 DOCUMENT-INDEX.md）
└── designs/               ← 设计稿和截图
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
| `test_api_integration.py` | FastAPI 集成测试（需 DB + API Key） |

---

## 数据库表

| 表 | 说明 |
|---|---|
| `orders` | 核心订单表（34 列，1030 万行） |
| `user_rfm` | RFM 预计算表（17 字段） |
| `user_first_purchase` | 首购日期（409 万用户） |
| `daily_visitors` | 日粒度访客数据（846 行） |

---

## 渠道漏斗（9 层）

```
P1 U先派样 → P2 百补派样 → P3 赠品&0.01 → P4 达播/微博 → P5 直播 → P6 淘客 → P7 购物金 → P8 货架 → P9 其他
```

---

## 新增/修改接口规范（必读）

> 每次新增或修改后端接口，必须按以下 6 步走，不得跳过。

### Step 1: 口径先找语义层

```python
# ✅ 正确：引用语义层
from backend.semantic.filters import OrderFilters, expand_channels
valid_sql, _ = OrderFilters.valid_order()

# ❌ 禁止：在 Service 里硬编码口径
"order_status LIKE '%成功%'"
"is_goujinjin = FALSE"  # 自己写
```

口径来源（唯一真实数据源）：
- `backend/semantic/filters.py` → 过滤条件
- `backend/semantic/channels.py` → 渠道映射
- `backend/semantic/calculations.py` → YOY/MOM/safe_ratio
- `backend/semantic/segments.py` → RFM 分群

### Step 2: Service 必须遵守连接规范

```python
conn = get_connection()
try:
    result = conn.execute(sql, params).fetchall()
    total = conn.execute(total_sql, params).fetchone()
    # ... 组装返回值
    return { ... }
finally:
    conn.close()
```

- `?` 参数化，禁止字符串拼接值
- 列名动态化必须走白名单字典（如 `SPU_LEVELS`）
- `level not in SPU_LEVELS` → raise ValueError

### Step 3: 渠道参数统一走语义层

```python
from backend.semantic.filters import expand_channels

# channel 和 exclude_channels 都要展开
db_channels = expand_channels([channel])
db_exclude = expand_channels(exclude_channels)
```

前端渠道常量统一引用：
```ts
import { LOW_PRICE_CHANNELS } from '@/constants/channels'
// 禁止在各 View 里重复定义 const LOW_PRICE_CHANNELS = [...]
```

### Step 4: Schema 字段同步（改 Service 必须同步）

```
backend/services/xxx_service.py  →  改返回字段
backend/contracts/schemas.py     →  同步 Pydantic model
frontend-vue3/src/api/xxx.ts     →  同步 TypeScript interface
```

- Service 新增字段 → Schema 加默认值（`float = 0.0`），前端加 `?` 可选
- Service 删除字段 → Schema + 前端同时删除，不留死字段
- **最常见 crash**：Pydantic 缺字段 → FastAPI 静默过滤 → 前端 undefined → 白屏

### Step 5: 前端只做展示，不做业务计算

```ts
// ✅ 正确：后端算好，前端展示
{ title: '渗透率', key: 'penetration_rate', render: (row) => `${(row.penetration_rate * 100).toFixed(1)}%` }

// ❌ 禁止：前端自己算 YOY / 占比 / 客单价
const ratio = (current - previous) / previous  // 不要在前端算
```

### Step 6: 三层验证

1. **Python import** → `from backend.main import app`
2. **后端测试** → `pytest backend/tests/ -x -q`
3. **前端类型** → `vue-tsc --noEmit`
4. **浏览器** → 0 console error，筛选联动正常

---

## 公共模块（避免重复造轮子）

| 模块 | 位置 | 用途 |
|---|---|---|
| `expand_channels` | `backend/semantic/filters.py` | 渠道名展开/标准化 |
| `OrderFilters` | `backend/semantic/filters.py` | 有效订单、GMV/GSV 口径 |
| `LOW_PRICE_CHANNELS` | `frontend-vue3/src/constants/channels.ts` | 低价渠道列表 |
| `YOYBadge` | `frontend-vue3/src/components/YOYBadge.vue` | 同比标签组件 |
| `MetricCard` | `frontend-vue3/src/components/MetricCard.vue` | KPI 卡片（支持 subtitle + formula） |

---

## 文档导航

| 文件 | 说明 |
|---|---|
| `MEMORY.md`（自动注入） | 修改代码的规则 + 当前状态 + 历史教训 |
| `docs/DOCUMENT-INDEX.md` | 文档分类索引 |
| `docs/PRD-v3.0.md` | 产品需求文档 |
| `docs/飞书版架构文档/` | 系统架构文档（7 份） |
| `docs/测试报告.md` | 测试覆盖详情 |
| `docs/MIGRATION-CHECKLIST.md` | 重构迁移清单 |

---

## Skill 路由（单人项目）

当请求匹配以下场景时，**立即调用对应 Skill**，不要直接回答。

| 场景 | 触发词示例 | 调用的 Skill |
|------|-----------|-------------|
| 修 Bug / 报错 / 数据异常 | `调试`、`investigate`、`排查`、`出问题了`、`报错` | `workbuddy-investigate` |
| 写完模块自检 / commit 前审查 | `review`、`代码审查`、`逻辑有没有问题`、`业务逻辑` | `workbuddy-review` |
| 功能上线前验收测试 | `qa`、`测试一下`、`验收`、`检查一下`、`跑一下测试` | `workbuddy-qa` |
| 大功能完成，推送前完整检查 | `发布`、`上线`、`部署`、`ship` | `workbuddy-ship` |

**单人项目不需要 PR 流程**，上述 Skill 直接在本地运行，无需远程审查者。
