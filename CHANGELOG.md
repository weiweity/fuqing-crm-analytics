# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **ETL 导入路径错误** — `scripts/etl/cli.py` 中 4 处导入路径错误导致 ETL Step 3-7 崩溃：`scripts.etl_status_override` → `scripts.etl.etl_status_override`（3处），`scripts.preload_rfm` → `scripts.etl.preload_rfm`（1处）

### Added
- **Parquet 缓存填充脚本** — 新增 `scripts/etl/fill_parquet_cache.py`，将 161 个 xlsx 文件批量转换为 Parquet 缓存，增量 ETL 加速 10-50x
- **原子写入** — `_save_parquet_cache()` 和 `_save_processed_files()` 支持 tmp+rename 原子写入，防止中断产生损坏文件
- **Parquet 缓存测试** — 新增 9 个测试覆盖 Parquet 写入、增量检测、原子写入、processed_files 更新等核心逻辑

### Fixed
- **processed_files 覆写** — `fill_parquet_cache.py` 保存时合并已有记录，避免丢失历史 ETL 状态
- **单元测试全覆盖** — 新增 91 个测试覆盖 12 个模块：breakdown_service（15）、rfm_service（16）、rfm_analysis（8）、health/overview（19）、health/conversion（7）、health/repurchase（2）、health/tier_flow（1）、health/channel_scores（1）、category_service/overview（4）、category_service/distribution（1）、category_service/churn（1）、category_service/basket（1）
- **R 区间边界测试** — 验证 `_get_r_interval_current_distribution` 的 R 区间分桶（30/90/180/365/730 天）和 F 段（F>1/F=1）正确性
- **GSV 口径测试** — 验证退款订单（is_refund=TRUE）、购物金（is_goujinjin=TRUE）、交易关闭订单不计入 GSV
- **Codex 交叉审核** — 使用 Codex regular + adversarial 模式审核代码变更，发现并修复 5 个问题

### Fixed
- **check_future_date(None) 崩溃** — `backend/semantic/time.py` 的 `check_future_date()` 在 mtd/wtd/ytd 模式下接收 None 参数时触发 TypeError。修复：函数入口加 `if date_str is None: return None` 守卫，except 加 `TypeError`
- **日期正则不验证日历** — `re.fullmatch(r'\d{4}-\d{2}-\d{2}')` 接受无效日期如 2025-02-30。修复：regex 后加 `datetime.strptime` 验证实际日期有效性
- **visitor.py 未使用 import** — 删除 `backend/routers/visitor.py` 中未使用的 `import json`
- **品类回购分析数据为 0** — `_RFM_SEGMENT_ORDER`（`category_service/_shared.py`）与 SQL `rfm_segmented` CTE 的 RFM 象限命名不一致：常量定义了 4 个无"客户"后缀的名称（如 `"重要价值"`），而 SQL 生成 8 个带后缀的名称（如 `"重要价值客户"`）。`api.py` 的 `_build_rows` 用旧名称查找 SQL 结果 → key 不匹配 → 所有数值归零。修复：`_RFM_SEGMENT_ORDER` 更新为 8 个带"客户"后缀的完整象限名称。`/category/repurchase-flow` 接口现已正确返回品类各 RFM 象限回购数据（hist/repurchased），可通过 `curl http://localhost:8000/api/category/repurchase-flow` 验证
- **Lint 清理** — 消除 `rfm/r_flow.py`、`rfm/m_flow.py`、`rfm/f_flow.py`、`rfm/segment_orders.py` 的 F403/F405 star import（117 errors → 0）；清理 `routers/__init__.py` 16 个 F401 unused import；删除死代码 `breakdown_service.py` shim；修复 `rfm/_shared.py`/`export_service.py`/`metrics/__init__.py` 等多处 F401；E701/E741 若干
- **Lint 清理（续）** — `category_service/flow/__init__.py`、`category_service/flow.py`、`category_service/repurchase/__init__.py`、`category_service/repurchase.py` 消除 F403 star import；删除死代码 `dmp_asset_service.py` shim；`dmp_asset_service/__init__.py` 改为显式导入；`health/rfm_analysis/__init__.py`、`health/rfm_analysis.py` 消除 F403

## [0.3.3] - 2026-05-29

### Fixed
- **SQL 注入修复** — `breakdown_service/_shared.py` 4 个函数将日期参数从 f-string 拼接改为 DuckDB `?` 参数化；`_r_interval_sql` 内部 `DATE '{cutoff}'` 也改为参数化
- **硬编码路径修复** — `VISITOR_XLSX_FILE` 从 Mac 绝对路径迁移到 `backend/config.py` 的环境变量配置

### Changed
- **开发者体验** — `/docs` 和 `/redoc` 从认证中间件白名单移除，新开发者可直接浏览器探索 API
- **未来日期警告** — 传入未来日期时，API 在 `X-Data-Warning` 响应头返回明确警告（`backend/semantic/time.py` 的 `check_future_date()`），覆盖 `/overview`、`/targets`、`/repurchase-cycle`、`/value-tiers`、`/tier-flow`、`/rfm-analysis`、`/rfm-category-drilldown`、`/channel-health-scores`、`/new-customer-conversion`、`/r-flow`、`/f-flow`、`/m-flow`、`/segment-orders` 等 13 个端点

## [0.3.2] - 2026-05-28

### Fixed
- **后端代码审计** — 修复 23 个问题（P0×5/P1×7/P2×11），包括口径不一致、测试阈值硬编码、contracts 重复、类重复定义等
- **大文件拆分** — 将 6 个超大文件拆分为包（rfm_service/flow/breakdown/dmp_asset/repurchase/rfm_analysis），并补全所有交叉导入
- **SPU 版本化** — orders 表新增 `spu_hash` 字段，避免 SPU 重命名导致历史数据不可追溯
- **Bundle 优化** — xlsx 依赖改为懒加载，减少首屏 bundle 体积

### Added
- **ETL Parquet 缓存层** — 中间计算结果写入 parquet，减少重复计算
- **前端性能基线** — 建立性能 benchmark，便于回归检测

## [0.3.1] - 2026-05-27

### Changed
- **Docker 化就绪** — 后端支持 Docker 部署
- **磁盘清理** — data/ 目录清理，释放 7.7G 空间

## [0.3.0] - 2026-04-20

### Added
- **Vue3 前端上线** — 8 个 dashboard 页面，SPA 路由，xlsx 导出
- **RFM 8 象限重构** — 区间流转 + 品类下钻完整实现

## [0.2.0] - 2026-04-16

### Added
- **语义层 + 契约层** — v3.0 架构重构，口径统一管理
- **DuckDB 数据平台** — 1030 万订单 / 410 万用户数据接入

## [0.1.0] - 2026-03-27

### Added
- **项目启动** — 基础架构设计，FastAPI 后端框架搭建

---

## 版本说明

本项目使用 **semver** 格式：`MAJOR.MINOR.PATCH`

| 字段 | 含义 |
|------|------|
| MAJOR | 不兼容的 API 变更（如删除端点、修改 Schema） |
| MINOR | 向后兼容的新功能（如新增端点、新增响应字段） |
| PATCH | 向后兼容的缺陷修复（如 BugFix、安全补丁） |

> 注意：当前 MAJOR = 0 表示项目仍在初始开发阶段，API 可能在 MINOR 版本中变化。
