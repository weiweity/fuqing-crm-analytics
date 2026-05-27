# 芙清 CRM — 模块索引

> 最后更新: 2026-05-27 | 重构 Phase 0-7 完成 | 代码总量 23,710 行

## 后端服务层 (`backend/services/`)

### 已拆分为包的模块

| 包 | 模块数 | 总行数 | 说明 |
|---|---|---|---|
| `category_service/` | 9 | ~4,800 | 品类分析（分布/画像/概览/流转/购物篮/流失/复购） |
| `metrics/` | 4 | ~1,800 | 指标服务（概览/人群表格/人群汇总） |
| `health/` | 8 | ~4,500 | 老客健康分析（概览/复购/价值分层/RFM/配置） |

### 独立服务文件

| 文件 | 行数 | 说明 |
|------|------|------|
| `rfm_service.py` | 1,398 | RFM 分群分析（待拆分） |
| `breakdown_service.py` | 832 | 一键拆解 |
| `dmp_asset_service.py` | 809 | DMP 资产分析 |
| `sampling_service.py` | 698 | U先派样分析 |
| `churn_service.py` | 553 | 流失分析 |
| `geo_service.py` | 475 | 地域分析 |
| `export_service.py` | 448 | 导出服务 |
| `flow_service.py` | 389 | 人群流转 |

### 薄包装层（向后兼容）

| 文件 | 说明 |
|------|------|
| `metrics_service.py` | → `metrics/` 包 |
| `category_service.py` | → `category_service/` 包 |

## 契约层 (`backend/contracts/`)

| 模块 | 行数 | 类数 | 说明 |
|------|------|------|------|
| `common.py` | 51 | 6 | 通用模型 |
| `metrics.py` | 35 | 2 | 概览指标 |
| `audience.py` | 271 | 6 | 人群分析 |
| `flow.py` | 114 | 10 | 流转矩阵 |
| `churn.py` | 118 | 11 | 流失分析 |
| `asset.py` | 119 | 8 | 资产分析 |
| `geo.py` | 31 | 4 | 地域分布 |
| `category.py` | 197 | 11 | 品类分析 |
| `rfm.py` | 284 | 16 | RFM 分群 |
| `health.py` | 389 | 26 | 健康分析 |
| `visitor.py` | 40 | 3 | 访客数据 |
| `breakdown.py` | 132 | 11 | 一键拆解 |
| `sampling.py` | 168 | 12 | U先派样 |
| `schemas.py` | 60 | — | 统一导出（唯一入口） |
| `__init__.py` | 7 | — | 包初始化，从 schemas.py 重导出 |

## 语义层 (`backend/semantic/`)

| 文件 | 行数 | 说明 |
|------|------|------|
| `filters.py` | 305 | OrderFilters, FilterBuilder |
| `channels.py` | ~200 | 渠道映射（DB_TO_UI/UI_TO_DB） |
| `calculations.py` | ~100 | YOY/MOM/safe_ratio |
| `segments.py` | ~150 | RFM 分群注册表 |
| `time.py` | ~100 | PeriodBuilder |
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
| `cli.py` | 542 | CLI 入口 |
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
| **总计** | **148 collected, 140 passed, 8 skipped** | |
