# Sample CRM 后端

> FastAPI 后端服务，提供 RESTful API 接口
> 最后更新：2026-06-07

---

## 模块概览

| 模块 | 路径 | 说明 |
|------|------|------|
| **语义层** | `semantic/` | 口径定义唯一来源（filters/metrics/segments/channels/time） |
| **契约层** | `contracts/` | Pydantic 模型（135 个类），OpenAPI → TypeScript 自动生成 |
| **服务层** | `services/` | 业务逻辑层，按业务域拆分为包 |
| **路由层** | `routers/` | API 路由（16 个模块） |
| **数据库** | `db/` | DuckDB 连接管理（单例 + ThreadSafeCursor） |
| **测试** | `tests/` | 单元测试（391+ passed / 12 skipped） |

---

## 目录结构

```
backend/
├── main.py                    # FastAPI 入口（端口 8000）
├── config.py                  # 配置管理（环境变量、路径）
├── semantic/                  # 语义层（口径定义唯一来源）
│   ├── filters.py             # OrderFilters / FilterBuilder
│   ├── metrics.py             # 指标注册表
│   ├── segments.py            # RFM 分群（RFM_THRESHOLDS）
│   ├── channels.py            # 渠道映射（DB_TO_UI/UI_TO_DB）
│   ├── time.py                # PeriodBuilder（WTD/MTD/YTD/free）
│   ├── calculations.py        # YOY/MOM/safe_ratio
│   └── README.md              # 语义层文档
├── contracts/                 # 契约层（Pydantic 模型）
│   └── schemas.py             # 统一导出，135 个类
├── services/                  # 业务逻辑层（按业务域拆分为包）
│   ├── category_service/      # 品类分析（flow/repurchase/distribution/...）
│   ├── health/                # 老客健康分析（rfm_analysis/overview/repurchase/...）
│   ├── metrics/               # 指标服务
│   ├── rfm/                   # RFM 区间流转（r_flow/f_flow/m_flow/segment_orders）
│   ├── breakdown_service/     # 一键拆解（forward/reverse/suggestions/main）
│   └── sample_asset_service/     # Sample Asset（store/product/other）
├── routers/                   # API 路由（16 个模块）
│   ├── overview.py            # 指标概览
│   ├── audience.py            # 人群看板
│   ├── geo.py                 # 地域分析
│   ├── category.py            # 品类分析
│   ├── churn.py               # 流失分析
│   ├── rfm.py                 # RFM 分析
│   ├── health.py              # 老客健康
│   ├── breakdown.py           # 一键拆解
│   ├── export.py              # 导出
│   ├── config.py              # 配置管理
│   ├── auth.py                # 认证
│   ├── visitor.py             # 访客数据
│   └── ...                    # 其他路由
├── db/                        # 数据库连接
│   ├── connection.py          # 单例连接 + ThreadSafeCursor
│   └── memory_monitor.py      # 内存监控
└── tests/                     # 单元测试
    ├── test_calculations.py   # YOY/MOM/safe_ratio/单位转换
    ├── test_filters.py        # OrderFilters/FilterBuilder/AmountExprBuilder
    ├── test_time.py           # PeriodBuilder（7 种周期模式）
    ├── test_channels.py       # 渠道漏斗/DB↔UI 映射
    ├── test_segments.py       # RFM 分群注册表/评分 SQL
    ├── test_flow_service.py   # 人群流转服务
    ├── test_exceptions.py     # 异常类型与 HTTP 状态码
    ├── test_api_integration.py # FastAPI 集成测试
    ├── test_health_overview.py # 健康概览
    ├── test_rfm_analysis.py   # RFM 分析
    ├── test_fill_parquet_cache.py # Parquet 缓存
    ├── test_etl_atomicity.py  # ETL 原子写入
    └── ...                    # 其他测试
```

---

## 核心模块说明

### 语义层 (semantic/)

口径定义唯一来源，禁止在 Service 中硬编码 SQL。

| 文件 | 职责 |
|------|------|
| `filters.py` | OrderFilters / FilterBuilder / AmountExprBuilder |
| `metrics.py` | 指标注册表（GMV/GSV/订单数/用户数等） |
| `segments.py` | RFM 分群（8 象限定义 + 评分 SQL） |
| `channels.py` | 渠道映射（DB ↔ UI 转换） |
| `time.py` | PeriodBuilder（WTD/MTD/YTD/free 周期） |
| `calculations.py` | YOY/MOM/safe_ratio 计算 |

### 契约层 (contracts/)

Pydantic 模型统一导出，OpenAPI → TypeScript 自动生成。

| 文件 | 职责 |
|------|------|
| `schemas.py` | 135 个 Pydantic 模型，统一导出 |

### 服务层 (services/)

业务逻辑层，按业务域拆分为包。

| 包 | 职责 |
|------|------|
| `category_service/` | 品类分析（flow/repurchase/distribution/basket） |
| `health/` | 老客健康分析（rfm_analysis/overview/repurchase/conversion/tier_flow） |
| `metrics/` | 指标服务 |
| `rfm/` | RFM 区间流转（r_flow/f_flow/m_flow/segment_orders） |
| `breakdown_service/` | 一键拆解（forward/reverse/suggestions） |
| `sample_asset_service/` | Sample Asset（store/product/other） |

### 路由层 (routers/)

API 路由，16 个模块。

| 路由 | 端点 |
|------|------|
| `overview.py` | `/api/v1/overview/*` |
| `audience.py` | `/api/v1/audience/*` |
| `geo.py` | `/api/v1/geo/*` |
| `category.py` | `/api/v1/category/*` |
| `churn.py` | `/api/v1/churn/*` |
| `rfm.py` | `/api/v1/rfm/*` |
| `health.py` | `/api/v1/customer-health/*` |
| `breakdown.py` | `/api/v1/breakdown/*` |
| `export.py` | `/api/v1/export/*` |
| `config.py` | `/api/v1/config/*` |
| `auth.py` | `/api/v1/auth/*` |

---

## 快速启动

```bash
# 启动后端服务
cd "/Users/yourname/Desktop/fuqin date/sample-crm-analytics"
export HEALTH_API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
PYTHONPATH="$(pwd)" nohup python3 -m uvicorn backend.main:app \
  --host 0.0.0.0 --port 8000 >> /tmp/fuqin-crm-backend.log 2>&1 &

# 运行测试
PYTHONPATH="$(pwd)" pytest backend/tests/ -v

# 查看 API 文档
open http://localhost:8000/docs
```

---

## 相关文档

| 文档 | 路径 | 说明 |
|------|------|------|
| 语义层文档 | `backend/semantic/README.md` | 口径定义、模块说明 |
| 数据源映射 | `docs/backend/data-source-map.md` | 数据库表、数据流 |
| 前端契约指南 | `docs/frontend/frontend-contract-guide.md` | 前后端契约 |
| 系统架构 | `docs/feishu-architecture/00-system-overview.md` | 整体架构 |

---

*此文件由 AI 维护，最后更新：2026-06-07*
