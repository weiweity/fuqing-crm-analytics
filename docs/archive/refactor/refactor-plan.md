# 芙清 CRM 客户分析系统 — 代码重构与标准化方案

> 版本：v1.0 | 日期：2026-05-25 | 状态：待审批
> 参考：dafuyan-wording 项目的 docs/ 体系

---

## 一、背景与目标

### 问题

| # | 问题 | 根因 | 影响 |
|---|------|------|------|
| 1 | AI 写代码幻觉率高 | 单文件 4000 行，上下文爆炸 | 改一行坏三行，综合性 Bug 无法修复 |
| 2 | 交接看不懂 | 无模块边界文档、无数据源映射 | 新人/AI 上手成本极高 |
| 3 | 新功能不敢加 | 文件耦合严重，不知道改了影响什么 | 功能迭代停滞 |
| 4 | Windows 跑不起来 | Python 环境不一致 + 代码路径硬编码 | 无法部署到其他机器 |
| 5 | 数据源散乱 | workplat、芙清CRM数据库、data/ 互相交叉 | 误删就崩 |

### 目标

1. **每个文件 ≤ 400 行** — AI 单次改动可控，幻觉率降低
2. **每个模块有文档** — AI 和人都能看懂边界
3. **Docker 一键部署** — `docker compose up` 即可运行，任何机器
4. **数据源统一入口** — `.env` 一个文件管所有路径，不怕删错

---

## 二、现状诊断

### 代码规模

```
总 Python 代码: 30,203 行
后端代码:       24,000+ 行
ETL 脚本:       5,700+ 行
测试:           148 个用例（覆盖语义层，不覆盖业务层和 ETL）
```

### 问题文件 Top 5

| 文件 | 行数 | 问题 |
|------|------|------|
| `backend/services/category_service.py` | 4033 | 8 种分析逻辑塞一个文件，20 个函数互相调用 |
| `scripts/run_etl.py` | 2942 | 全量/增量/SPU重匹配全在一个文件，无测试 |
| `backend/contracts/schemas.py` | 1990 | 135 个 Pydantic 模型堆在一个文件 |
| `backend/services/metrics_service.py` | 1778 | 概览指标 + 趋势指标混在一起 |
| `backend/main.py` | 1229 | 45 个 API 端点全写在一个文件，没有用 Router |

### 散乱文件

- `backend/services/` 下 3 个 `.bak` 备份文件
- `scripts/` 下 6 个一次性脚本与生产脚本混在一起
- `data/` 下 6 个废弃的 `.duckdb` 文件（12KB 空壳）
- 项目根目录 1 个散落的 `export_category_r_analysis.py`
- `docs/临时脚本/` 下 3 个调试脚本

### 数据源散乱

| 数据源 | 物理位置 | 配置方式 | 风险 |
|--------|---------|---------|------|
| 店铺数据库 | `~/Desktop/fuqin-date/芙清CRM数据库/` | `.env` | ✅ 已配置 |
| DMP 数据 | `~/Desktop/work plat/DMP_test_package/` | `.env` | ✅ 已配置 |
| 人群画像数据 | `workplat/` 内 | 未纳入项目 | ⚠️ 高风险 |
| 爬虫脚本 | `workplat/` 内 | 未纳入项目 | ⚠️ 高风险 |

---

## 三、拆分方案

### 原则

1. **只拆文件，不改逻辑** — 函数签名和返回值不变，只改变文件位置
2. **渐进式拆分** — 每拆一个模块，跑一遍测试确认无破坏
3. **每个新文件加 docstring** — 3 行说清楚：做什么、输入什么、输出什么
4. **Git 每步提交** — 每拆完一个模块，commit 一次

### Phase 0: 清理（0.5 天）

| # | 动作 | 文件 |
|---|------|------|
| 1 | 删 `.bak` 文件 | `services/category_service.py.bak*`（3个） |
| 2 | 删废弃 DuckDB | `data/` 下 6 个 12KB 空壳 `.duckdb` |
| 3 | 移动一次性脚本 | `scripts/migrate_views.py` → `scripts/archive/` |
| 4 | 移动测试脚本 | `scripts/test_channel_*.py` → `scripts/archive/` |
| 5 | 移动散落文件 | `export_category_r_analysis.py` → `scripts/archive/` |
| 6 | 删除 `docs/临时脚本/` | 3 个调试脚本 |
| 7 | 删除 `data/` 根下散落的 `.xlsx` | `近30天订单数据_*.xlsx`（41MB，原始数据不应在项目内） |

### Phase 1: main.py 拆分为 Router 模块（1 天）

**目标：1229 行 → 每个路由文件 ≤ 300 行**

```
backend/
├── main.py                    # 只保留 app 初始化 + CORS + mount（~80 行）
├── routers/
│   ├── __init__.py
│   ├── metrics.py             # /api/v1/metrics/* (overview, trend)
│   ├── flow.py                # /api/v1/flow/* (matrix, sankey)
│   ├── churn.py               # /api/v1/churn/* (distribution, risk)
│   ├── asset.py               # /api/v1/asset/*
│   ├── geo.py                 # /api/v1/geo/*
│   ├── category.py            # /api/v1/category/* (14 个端点)
│   ├── audience.py            # /api/v1/audience/*
│   ├── rfm.py                 # /api/v1/rfm/*
│   ├── market_focus.py        # /api/v1/market-focus/*
│   ├── visitor.py             # /api/v1/visitor/*
│   ├── breakdown.py           # /api/v1/breakdown/*
│   ├── sampling.py            # /api/v1/sampling/*
│   ├── export.py              # /api/v1/export/*
│   ├── report.py              # /api/v1/report/*
│   ├── auth.py                # /api/v1/auth/* (保留现有)
│   └── health.py              # /api/v1/health/* (保留现有)
```

**具体拆法**：
- 把 `main.py` 里的 `@app.get(...)` 函数体 + import 移到对应的 `routers/*.py`
- 每个 Router 用 `APIRouter(prefix="/api/v1/xxx")`
- `main.py` 只做 `app.include_router(xxx_router)`

### Phase 2: category_service.py 拆分（2 天）

**目标：4033 行 → 6-8 个文件，每个 ≤ 500 行**

```
backend/services/category/
├── __init__.py                 # 导出所有 get_* 公共函数
├── _shared.py                 # _normalize_date, _segment_meta, _cat_expr 等共享工具
├── distribution.py             # get_category_distribution (~170 行)
├── segment_matrix.py           # get_category_segment_matrix (~170 行)
├── user_profile.py             # get_category_user_profile (~250 行)
├── overview.py                 # get_category_overview (~210 行)
├── value_tier.py               # get_category_value_tier + _build_value_score + _compute_wool_party_breakdown (~350 行)
├── flow.py                     # get_category_flow + get_category_flow_matrix + get_category_flow_association (~700 行)
│                                #   如果仍超 400 行，继续拆成 flow_matrix.py + flow_association.py
├── repurchase.py               # get_category_repurchase_flow + _run_category_repurchase_period (~600 行)
│                                #   如果仍超 400 行，拆成 repurchase_flow.py + repurchase_period.py
├── market_basket.py            # get_market_basket + _compute_market_basket (~350 行)
├── churn.py                    # get_category_churn (~240 行)
└── daily_trend.py              # get_category_daily_trend + get_category_user_list (~200 行)
```

**依赖关系**（拆分时必须保证的导入链）：

```
_shared.py ← distribution.py
           ← segment_matrix.py
           ← user_profile.py
           ← overview.py
           ← value_tier.py
           ← flow.py
           ← repurchase.py
           ← market_basket.py
           ← churn.py
           ← daily_trend.py
```

**兼容性保证**：
- `from backend.services.category_service import get_category_distribution` 仍然可用
- 通过 `category/__init__.py` 重新导出所有公共函数

### Phase 3: run_etl.py 拆分（2 天）

**目标：2942 行 → 5 个文件，每个 ≤ 400 行**

```
scripts/etl/
├── __init__.py
├── config.py                   # 路径配置 + 缓存路径 + .env 加载 (~50 行)
├── sources.py                  # 数据源加载（load_spu_mapping, load_channel_rules, load_taoke_*, load_live_*）(~400 行)
├── ingest.py                   # 文件读取 + 列名映射 + 增量追踪（load_data_files, rename_columns）(~500 行)
│                                #   如果仍超 400 行，拆成 ingest_loader.py + ingest_tracker.py
├── transform.py                # match_channel + clean_data（数据清洗核心逻辑）(~400 行)
├── load.py                     # DuckDB 写入（init_database, write_to_duckdb, upsert_to_duckdb, ensure_schema）(~400 行)
├── pipeline.py                 # run_full_etl 主流程编排（~400 行）
└── cli.py                     # argparse + 入口函数（~80 行）

scripts/
├── run_etl.py                  # 入口脚本（~10 行）：from etl.cli import main; main()
├── archive/                    # 已归档脚本
│   ├── migrate_views.py
│   ├── test_channel_judge.py
│   └── test_channel_rebuild.py
├── clean_crowd_data.py         # 保留（生产脚本）
├── etl_status_override.py      # 保留（生产脚本）
├── precompute_category_flow.py # 保留（预计算脚本）
├── precompute_category_churn.py # 保留
└── preload_rfm.py              # 保留
```

### Phase 4: schemas.py 拆分（1 天）

**目标：1990 行 → 按业务域拆分，每个 ≤ 300 行**

```
backend/contracts/
├── __init__.py                 # 重新导出所有模型（保持 from backend.contracts.schemas import Xxx 可用）
├── schemas.py                  # 保留，但只放公共模型 + 重新导出（~50 行）
├── common.py                   # DateRangeResponse, YearComparisonRow 等公共模型
├── metrics.py                  # OverviewMetrics, TrendData
├── flow.py                     # FlowMatrixResponse, FlowSankeyResponse, SankeyNode, SankeyLink 等
├── churn.py                    # ChurnDistributionResponse, ChurnUsersResponse 等
├── asset.py                    # AssetSummaryResponse, AssetTrendResponse
├── geo.py                      # GeoDistributionResponse 等
├── category.py                 # 所有 Category* 模型（~400 行，最大的域）
├── audience.py                 # AudienceTable*, AudienceSummary*
├── rfm.py                      # RFM*, SegmentOrders*
├── health.py                   # HealthOverviewMetrics, Repurchase*, ValueTier*, Tier*, Promotion*, ChannelHealth*, RFMConfig*
├── market_focus.py             # StoreAsset*, ProductAsset*
├── visitor.py                  # Visitor*
├── breakdown.py                # Breakdown*
├── sampling.py                 # Sampling*, Rolling*
└── export.py                   # ExportPPT*, Templates*
```

### Phase 5: metrics_service.py 拆分（0.5 天）

**目标：1778 行 → 2-3 个文件**

```
backend/services/metrics/
├── __init__.py
├── overview.py                 # get_overview_metrics, get_trend_data
└── (视情况拆分更多子模块)
```

### Phase 6: 文档体系（1-2 天）

**参照 dafuyan-wording 的 docs/ 结构**

```
docs/
├── ARCHITECTURE.md             # 系统架构图（参照 dafuyan-wording 格式）
│                                #   五层架构图 + API 端点表 + 目录结构 + 数据流图
├── DESIGN.md                   # AI 操作手册（参照 dafuyan-wording 的 DESIGN.md）
│                                #   改代码前的检查清单 + 模块边界 + 禁止事项
├── DATA-SOURCE-MAP.md          # 数据源映射（哪个文件在哪、删了影响什么）
├── DEPLOY.md                   # 部署指南（Docker + 手动部署）
├── MODULE-INDEX.md             # 模块索引（每个文件做什么、输入输出、行数）
├── DOCUMENT-INDEX.md           # 文档索引（保留现有）
└── archive/                    # 已归档文档
```

### Phase 7: Docker 化（1-2 天）

```
项目根目录/
├── Dockerfile                  # Python 3.12 + 依赖 + 项目代码
├── docker-compose.yml          # backend + frontend 服务编排
├── .dockerignore               # 排除 data/、node_modules/、.git/
├── .env.example                # 环境变量模板（不含真实路径/密钥）
└── scripts/
    └── docker-entrypoint.sh    # 容器启动脚本
```

**Docker 架构**：

```yaml
# docker-compose.yml
services:
  backend:
    build: .
    ports: ["8001:8001"]
    volumes:
      - ./data:/app/data              # DuckDB 数据
      - ${SHOP_DATA_SOURCE}:/data/sources/shop:ro     # 只读挂载原始数据
      - ${MEMBER_DATA_SOURCE}:/data/sources/member:ro
    env_file: .env

  frontend:
    build: ./frontend-vue3
    ports: ["5173:80"]                # nginx 托管静态文件
    depends_on: [backend]
```

**关键决策**：
- 原始数据通过 volume 只读挂载（不拷进镜像）
- DuckDB 数据库在 volume 里持久化（不进镜像）
- 前端用 nginx 托管 `dist/`（不用 dev server）
- ETL 在容器内运行：`docker compose exec backend python scripts/run_etl.py --update`

---

## 四、执行顺序与 Git 工作流

### 执行顺序（严格按 Phase 0 → 7）

```
Phase 0 (清理)     → commit: chore: clean up .bak files and archive scripts
Phase 1 (main.py)  → commit: refactor: extract routers from main.py
Phase 2 (category) → commit: refactor: split category_service into module package
Phase 3 (ETL)      → commit: refactor: split run_etl into etl package
Phase 4 (schemas)  → commit: refactor: split schemas by business domain
Phase 5 (metrics)  → commit: refactor: split metrics_service into module package
Phase 6 (文档)     → commit: docs: add ARCHITECTURE.md, DESIGN.md, DATA-SOURCE-MAP.md
Phase 7 (Docker)   → commit: feat: add Docker and docker-compose
```

### 每个 Phase 的验证步骤

```bash
# 1. 拆完后跑测试
PYTHONPATH="$(pwd)" pytest backend/tests/ -v

# 2. 启动后端确认 API 可达
curl http://localhost:8001/docs

# 3. 前端类型检查
cd frontend-vue3 && npx vue-tsc --noEmit

# 4. 前端启动确认
cd frontend-vue3 && npm run dev
# 浏览器打开 http://localhost:5173，确认页面正常
```

---

## 五、拆分后的目录结构

```
fuqing-crm-analytics/
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .dockerignore
├── requirements.txt
├── CLAUDE.md
│
├── backend/
│   ├── main.py                    # ~80 行：app 初始化 + include_router
│   ├── config.py                  # 145 行：保留
│   ├── database.py                # 204 行：保留
│   ├── routers/                   # 16 个路由模块（每个 ≤ 300 行）
│   │   ├── metrics.py
│   │   ├── flow.py
│   │   ├── churn.py
│   │   ├── category.py           # 14 个端点，可能 ~350 行
│   │   ├── ...
│   │   └── health.py
│   ├── contracts/                 # 按业务域拆分的 Schema
│   │   ├── __init__.py            # 重新导出
│   │   ├── common.py
│   │   ├── category.py
│   │   └── ...
│   ├── services/
│   │   ├── category/              # 拆分后的品类分析模块（6-8 个文件）
│   │   │   ├── __init__.py
│   │   │   ├── _shared.py
│   │   │   ├── distribution.py
│   │   │   ├── flow.py
│   │   │   └── ...
│   │   ├── metrics/               # 拆分后的指标模块
│   │   ├── health/                # 保留现有结构（已经拆好了）
│   │   ├── breakdown_service.py   # 833 行，暂不拆
│   │   ├── rfm_service.py         # 1398 行，后续拆
│   │   └── ...                    # 其他 < 800 行的 service 暂不拆
│   ├── semantic/                  # 保留（已经是好的结构）
│   ├── db/
│   └── tests/
│
├── scripts/
│   ├── run_etl.py                 # ~10 行：入口
│   ├── etl/                       # 拆分后的 ETL 模块
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── sources.py
│   │   ├── ingest.py
│   │   ├── transform.py
│   │   ├── load.py
│   │   ├── pipeline.py
│   │   └── cli.py
│   ├── archive/                   # 已归档脚本
│   └── ...                        # 保留生产脚本
│
├── frontend-vue3/                 # 不动
│
├── data/                          # .gitignore，不入仓库
│   ├── processed/fuqing_crm.duckdb
│   └── exports/
│
└── docs/
    ├── ARCHITECTURE.md            # 系统架构图
    ├── DESIGN.md                  # AI 操作手册
    ├── DATA-SOURCE-MAP.md         # 数据源映射
    ├── DEPLOY.md                  # 部署指南
    ├── MODULE-INDEX.md            # 模块索引
    └── DOCUMENT-INDEX.md          # 文档索引
```

---

## 六、风险与回退

| 风险 | 概率 | 缓解措施 |
|------|------|---------|
| 拆分后 import 路径变化导致前端 API 报错 | 中 | 每个 Phase 跑测试 + curl 验证 API |
| 拆 category_service 时共享函数引用混乱 | 中 | `_shared.py` 集中管理，`__init__.py` 重新导出 |
| ETL 拆分后 Windows 路径处理出问题 | 低 | Phase 3 专门测试 Windows 路径兼容 |
| Docker 在 Windows 上性能差 | 低 | 前端用 nginx 托管静态文件，后端纯 Python |
| 拆分过程中 Mac 生产环境中断 | 低 | 每个 Phase 单独 commit，出问题 `git revert` |

**回退策略**：每个 Phase 都是独立 commit，任何一个出问题都可以 `git revert` 回到上一个稳定状态。

---

## 七、时间估算

| Phase | 工作量 | 说明 |
|-------|--------|------|
| Phase 0 | 0.5 天 | 清理，风险最低 |
| Phase 1 | 1 天 | main.py → routers，最直接的价值 |
| Phase 2 | 2 天 | category 拆分，最复杂 |
| Phase 3 | 2 天 | ETL 拆分，Windows 兼容关键 |
| Phase 4 | 1 天 | schemas 拆分，机械操作 |
| Phase 5 | 0.5 天 | metrics 拆分 |
| Phase 6 | 1-2 天 | 文档，参照 dafuyan-wording |
| Phase 7 | 1-2 天 | Docker |
| **总计** | **9-11 天** | |

---

## 八、成功标准

1. ✅ 没有单个 Python 文件超过 500 行（main.py 除外，目标 ≤ 100 行）
2. ✅ `from backend.services.category_service import get_category_distribution` 仍然可用
3. ✅ `pytest backend/tests/` 全部通过
4. ✅ `curl http://localhost:8001/api/v1/category/overview` 返回正常
5. ✅ `docker compose up` 启动成功
6. ✅ Windows 上 `docker compose up` 也能启动成功
7. ✅ AI 在单个文件内改代码时，不需要读取超过 500 行的上下文
8. ✅ `docs/ARCHITECTURE.md` 存在且包含架构图 + API 端点表 + 目录结构
