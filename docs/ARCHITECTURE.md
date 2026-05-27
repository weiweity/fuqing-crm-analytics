# 芙清 CRM 客户分析系统 — 架构文档

> 最后更新: 2026-05-27 | 版本: v0.3.0（Phase 0-5 重构完成）

## 五层架构

```
前端展示层  Vue3 + ECharts 5 + naive-ui + Tailwind CSS
    ↕ HTTP JSON
API 层      FastAPI + Pydantic（backend/main.py + routers/）
    ↕ 函数调用
服务层      backend/services/（业务逻辑）
    ↕ 函数调用
语义层      backend/semantic/（口径唯一真实数据源）
    ↕ DuckDB
数据层      data/processed/fuqing.duckdb（10.5M 行）
```

## 目录结构

```
fuqing-crm-analytics/
├── backend/
│   ├── main.py                    # ~180 行：app 初始化 + include_router
│   ├── routers/                   # 16 个路由模块（每个 ≤ 350 行）
│   ├── contracts/                 # 13 个域模块（Pydantic 模型）
│   │   ├── schemas.py             # 向后兼容重导出
│   │   ├── common.py              # 通用模型
│   │   ├── metrics.py / audience.py / flow.py / ...
│   │   └── __init__.py            # 重导出 140 个类
│   ├── services/
│   │   ├── metrics/               # 概览指标 + 人群分析（4 模块）
│   │   ├── category_service/      # 品类分析（9 模块）
│   │   ├── health/                # 老客健康分析（已有子模块）
│   │   ├── metrics_service.py     # 薄包装层
│   │   ├── category_service.py    # 薄包装层
│   │   └── ...                    # 其他 < 800 行的 service
│   ├── semantic/                  # 语义层（口径定义）
│   ├── db/                        # 数据库连接
│   └── tests/                     # 140 个测试用例
├── frontend-vue3/
│   ├── src/
│   │   ├── views/ / components/   # 页面组件
│   │   ├── api/                   # API 调用 + types.ts
│   │   └── stores/                # Pinia 状态
│   └── e2e/                       # E2E 测试
├── scripts/
│   ├── run_etl.py                 # 薄包装层
│   ├── etl/                       # 7 个 ETL 模块
│   └── ...                        # 其他生产脚本
├── data/                          # DuckDB + Parquet + 缓存
└── docs/                          # 文档中心
```

## API 端点

| Router | 前缀 | 端点数 |
|--------|------|--------|
| metrics | `/api/v1/metrics` | 3 |
| flow | `/api/v1/flow` | 3 |
| churn | `/api/v1/churn` | 3 |
| asset | `/api/v1/asset` | 2 |
| geo | `/api/v1/geo` | 3 |
| category | `/api/v1/category` | 14 |
| audience | `/api/v1/audience` | 3 |
| rfm | `/api/v1/rfm` | 6 |
| market_focus | `/api/v1/market-focus` | 2 |
| visitor | `/api/v1/visitor` | 2 |
| breakdown | `/api/v1/breakdown` | 2 |
| sampling | `/api/v1/sampling` | 4 |
| export | `/api/v1/export` | 3 |
| report | `/api/v1/report` | 2 |
| auth | `/api/v1/auth` | 2 |
| health | `/api/v1/health` | 5 |

## 数据流

```
原始 Excel/CSV → ETL (scripts/etl/) → DuckDB (data/processed/)
    ↓
语义层 (backend/semantic/) — 口径定义
    ↓
服务层 (backend/services/) — 业务逻辑
    ↓
契约层 (backend/contracts/) — Pydantic 模型
    ↓
API 层 (backend/routers/) — FastAPI 端点
    ↓
前端 (frontend-vue3/) — Vue3 + ECharts
```

## 详细文档

- [飞书版架构文档](./飞书版架构文档/) — 7 份完整架构文档
- [语义层设计](./semantic/) — 指标管理、分群设计
- [DESIGN.md](./DESIGN.md) — AI 操作手册
- [MODULE-INDEX.md](./MODULE-INDEX.md) — 模块索引
