# 芙清 CRM — 模块索引

> 最后更新: 2026-05-28 | 后端代码审计修复完成 | 大文件拆分完成

## 后端服务层 (`backend/services/`)

### 包结构（按业务域拆分）

| 包 | 子模块 | 说明 |
|---|---|---|
| `category_service/` | `distribution/`, `overview/`, `user_profile/`, `basket/`, `churn/`, `flow/`, `repurchase/` | 品类分析（7个子包） |
| `health/` | `overview/`, `repurchase/`, `tiers/`, `tier_flow/`, `rfm_analysis/`, `conversion/`, `promotion/`, `channel_scores/`, `config/` | 老客健康分析（9个子包） |
| `metrics/` | `_shared/`, `audience_summary/`, `audience_table/`, `overview/` | 指标服务（4个子模块） |
| `rfm/` | `_shared/`, `r_flow/`, `f_flow/`, `m_flow/`, `segment_orders/` | RFM 区间流转（5个子模块） |
| `breakdown_service/` | `forward/`, `reverse/`, `suggestions/`, `main/` | 一键拆解（4个子模块） |
| `dmp_asset_service/` | `store/`, `product/`, `other/` | DMP 资产分析（3个子模块） |

### 向后兼容 Shim（原文件 → 包重导出）

| 文件 | 目标包 |
|------|--------|
| `rfm_service.py` | → `rfm/` |
| `category_service/flow.py` | → `category_service/flow/` |
| `category_service/repurchase.py` | → `category_service/repurchase/` |
| `breakdown_service.py` | → `breakdown_service/` |
| `dmp_asset_service.py` | → `dmp_asset_service/` |
| `health/rfm_analysis.py` | → `health/rfm_analysis/` |

### 独立服务文件（未拆分）

| 文件 | 行数 | 说明 |
|------|------|------|
| `sampling_service.py` | 698 | U先派样分析 |
| `churn_service.py` | 553 | 流失分析 |
| `geo_service.py` | 475 | 地域分析 |
| `export_service.py` | 448 | 导出服务 |
| `flow_service.py` | 389 | 人群流转 |
| `metrics/audience_summary.py` | 891 | 人群汇总（单函数，无法拆分） |

## 契约层 (`backend/contracts/`)

| 模块 | 行数 | 说明 |
|------|------|------|
| `common.py` | ~50 | 通用模型（DateRangeResponse, YearComparisonRow 等） |
| `metrics.py` | ~35 | 概览指标 |
| `audience.py` | ~270 | 人群分析 |
| `flow.py` | ~115 | 流转矩阵（AnchorMode, PathDepth 定义处） |
| `churn.py` | ~120 | 流失分析 |
| `asset.py` | ~120 | 资产分析 |
| `geo.py` | ~30 | 地域分布 |
| `category.py` | ~190 | 品类分析 |
| `rfm.py` | ~285 | RFM 分群 |
| `health.py` | ~390 | 健康分析 |
| `visitor.py` | ~40 | 访客数据 |
| `breakdown.py` | ~130 | 一键拆解 |
| `sampling.py` | ~170 | U先派样 |
| `schemas.py` | 60 | **统一导出**（唯一入口，135个类） |
| `__init__.py` | 7 | 包初始化，从 schemas.py 重导出 |

## 语义层 (`backend/semantic/`)

| 文件 | 行数 | 说明 |
|------|------|------|
| `filters.py` | 305 | OrderFilters, FilterBuilder |
| `channels.py` | ~200 | 渠道映射（DB_TO_UI/UI_TO_DB/CHANNEL_ORDER） |
| `calculations.py` | ~100 | YOY/MOM/safe_ratio |
| `segments.py` | ~150 | RFM 分群注册表（RFM_THRESHOLDS） |
| `time.py` | ~100 | PeriodBuilder（WTD/MTD/YTD/free） |
| `metrics.py` | ~100 | 指标注册表 |
| `rfm_reader.py` | 295 | RFM 预计算读取 |

## ETL (`scripts/etl/`)

| 模块 | 行数 | 说明 |
|------|------|------|
| `config.py` | 180 | 常量、缓存路径 |
| `sources.py` | 406 | 数据源加载 |
| `ingest.py` | 217 | 文件读取 |
| `transform.py` | 311 | 渠道匹配、数据清洗 |
| `load.py` | 574 | DuckDB 写入 |
| `pipeline.py` | 820 | 主流程编排 |
| `cli.py` | 542 | CLI 入口（--update/--full/--rescan-spu/--rescan-channel） |
| `run_etl.py` | 51 | 薄包装层 |

## 测试 (`backend/tests/`)

| 文件 | 用例数 | 说明 |
|------|--------|------|
| `test_calculations.py` | ~20 | YOY/MOM/safe_ratio |
| `test_filters.py` | ~30 | OrderFilters/FilterBuilder |
| `test_time.py` | ~15 | PeriodBuilder |
| `test_channels.py` | ~20 | 渠道漏斗/映射 |
| `test_segments.py` | ~15 | RFM 分群 |
| `test_flow_service.py` | ~10 | 人群流转 |
| `test_exceptions.py` | ~10 | 异常类型 |
| `test_api_integration.py` | ~20 | FastAPI 集成测试 |
| **总计** | **148 collected, 140 passed, 8 skipped** |

## 关键设计决策

### 口径统一（2026-05-28 修复）
- `_VALID_BASE` 统一为 `is_goujinjin = FALSE AND order_status != '交易关闭'`
- 所有 service 通过语义层 `OrderFilters.valid_order()` 获取口径
- `breakdown_service.py` 曾缺少 `order_status` 条件，已修复

### contracts 去重（2026-05-28 修复）
- `schemas.py` 为唯一导出入口（135个类）
- `__init__.py` 仅做包初始化（7行）
- `AnchorMode`/`PathDepth` 统一定义在 `flow.py`，`category.py` 从 `flow.py` 导入
- `YearComparisonRow` 年份字段改为 `values_by_year: Dict[str, Optional[float]]`

### 包拆分规范
- 拆分后必须检查子模块间的交叉导入
- 原文件保留为向后兼容 shim
- `__init__.py` 使用 wildcard import 重导出所有子模块
