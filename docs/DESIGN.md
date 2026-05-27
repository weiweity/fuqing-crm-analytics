# 芙清 CRM — AI 操作手册

> 最后更新: 2026-05-27 | 版本: v0.3.0

## 改代码前的检查清单

### 必读文件
1. `CLAUDE.md` — 项目参考（结构、命令、规范）
2. `MEMORY.md`（自动注入）— 修改代码的规则 + 当前状态
3. 本文档 — 模块边界 + 禁止事项

### 层边界（禁止跨界）

| 层 | 职责 | 禁止做 |
|---|---|---|
| **语义层** `backend/semantic/` | 定义口径、过滤、计算规则 | 不处理业务逻辑 |
| **服务层** `backend/services/` | 业务逻辑、数据组装 | 不硬编码SQL口径，必须引用语义层 |
| **契约层** `backend/contracts/` | API请求/响应模型 | 不内联到main.py |
| **前端** `frontend-vue3/` | 展示和交互 | 不计算YOY/占比/客单价等业务指标 |

### 改动纪律

1. **改Service返回字段** → 立刻同步`contracts/schemas.py`中的response_model
2. **改渠道名** → 验证三处映射：`channels.py`的DB_TO_UI / UI_TO_DB / CHANNEL_ORDER
3. **删除功能** → 后端删接口 → 前端同步：①删API调用 ②删query/mutation ③删状态变量 ④改只读
4. **连接管理** → `conn = get_connection()` 后必须 `try:` `finally: conn.close()`
5. **SQL安全** → DuckDB用`?`参数化，禁止字符串拼接
6. **Schema变动** → 同步运行`openapi-typescript`重新生成前端类型

### Git 工作流（强制）

```
写代码 → 跑测试 → review skill → 修复 → commit → push → qa skill
```

**禁止跳过 review 直接 commit。**

## 模块边界

### 品类分析 (`backend/services/category_service/`)

| 模块 | 职责 | 依赖 |
|------|------|------|
| `_shared.py` | 共享常量和工具 | — |
| `distribution.py` | 品类分布 | `_shared` |
| `user_profile.py` | 用户画像 | `_shared` |
| `overview.py` | 品类概览 + 价值分层 | `_shared` |
| `flow.py` | 品类流转 | `_shared` |
| `basket.py` | 购物篮分析 | `_shared` |
| `churn.py` | 品类流失 | `_shared` |
| `repurchase.py` | 复购分析 | `_shared` |

### 指标服务 (`backend/services/metrics/`)

| 模块 | 职责 | 依赖 |
|------|------|------|
| `_shared.py` | _get_conn, _expand_channel | — |
| `overview.py` | 概览指标 | `_shared` |
| `audience_table.py` | 人群表格 | `_shared` |
| `audience_summary.py` | 人群汇总 | `_shared` |

### ETL (`scripts/etl/`)

| 模块 | 职责 |
|------|------|
| `config.py` | 常量、缓存路径 |
| `sources.py` | 数据源加载 |
| `ingest.py` | 文件读取 |
| `transform.py` | 渠道匹配、数据清洗 |
| `load.py` | DuckDB 写入 |
| `pipeline.py` | 主流程编排 |
| `cli.py` | CLI 入口 |

### 契约层 (`backend/contracts/`)

| 模块 | 职责 |
|------|------|
| `common.py` | DateRangeResponse, SankeyNode, WoolPartyBreakdown |
| `metrics.py` | OverviewMetrics, TrendData |
| `audience.py` | AudienceRow, ChannelGSVRow |
| `flow.py` | FlowMatrix, CategoryFlowResponse |
| `churn.py` | ChurnDistribution, CategoryChurn |
| `asset.py` | AssetSummary, StoreAsset |
| `geo.py` | GeoDistribution |
| `category.py` | CategoryOverview, MarketBasket |
| `rfm.py` | RFMRFlow, RFMAnalysis |
| `health.py` | HealthOverview, ValueTier, ExportPPT |
| `visitor.py` | VisitorSummary |
| `breakdown.py` | BreakdownRequest/Response |
| `sampling.py` | SamplingROI, RollingComparison |

## 禁止事项

- ❌ 在Service里硬编码口径（如`order_status LIKE '%成功%'`）
- ❌ 在前端算YOY/占比/客单价
- ❌ 用`git commit -m "fix"` / "update" / "asdf"
- ❌ 一次commit混多个不相关功能
- ❌ commit后不push
- ❌ 跳过review直接commit
