# 芙清 CRM — 数据源映射

> 最后更新: 2026-06-07

## 数据源一览

| 数据源 | 物理位置 | 配置方式 | 用途 |
|--------|---------|---------|------|
| 店铺订单数据 | `~/Desktop/fuqin date/芙清CRM数据库/` | `.env` SHOP_DATA_SOURCE | ETL 主数据源 |
| 会员数据 | `~/Desktop/fuqin date/芙清CRM数据库/` | `.env` MEMBER_DATA_SOURCE | 会员标签 |
| SPU映射表 | 项目内 `config/` | `.env` SPU_MAPPING_SOURCE | 品类映射 |
| 渠道规则 | 项目内 `config/` | `.env` CHANNEL_RULES_SOURCE | 渠道匹配 |
| 淘客订单号 | 外部CSV | `.env` TAOKE_DATA_SOURCE | 淘客渠道标记 |
| 淘客商品规则 | 外部CSV | `.env` TAOKE_PRODUCT_SOURCE | 淘客商品标记 |
| 直播订单号 | 外部CSV | `.env` LIVE_DATA_SOURCE | 直播渠道标记 |
| DuckDB数据库 | `data/processed/fuqing.duckdb` | `.env` DUCKDB_PATH | 主数据库 |
| DMP数据 | `~/Desktop/work plat/DMP_test_package/` | `.env` | 阿里达摩盘数据 |

## 文件删除影响

| 文件/目录 | 删除后果 | 风险等级 |
|-----------|---------|---------|
| `data/processed/fuqing.duckdb` | 所有看板数据丢失，需重跑ETL | 🔴 高 |
| `config/spu_mapping.xlsx` | 品类映射失效，ETL无法运行 | 🔴 高 |
| `config/channel_rules.xlsx` | 渠道匹配失效，所有渠道显示为"其他" | 🔴 高 |
| `backend/semantic/` | 口径定义丢失，所有计算出错 | 🔴 高 |
| `backend/contracts/` | API模型丢失，前后端崩溃 | 🔴 高 |
| `frontend-vue3/src/` | 前端白屏 | 🔴 高 |
| `scripts/etl/` | 无法运行ETL | 🟡 中 |
| `backend/tests/` | 无法跑测试 | 🟡 中 |
| `docs/` | 文档丢失，不影响运行 | 🟢 低 |
| `data/cache/` | 缓存丢失，下次访问重建 | 🟢 低 |

## ETL 数据流

```
原始 Excel/CSV 文件
    ↓ load_data_files() (ingest.py)
    ↓ rename_columns() — 中文→英文
    ↓ match_channel() — 渠道匹配
    ↓ clean_data() — 数据清洗 + SPU映射
    ↓ upsert_to_duckdb() — 写入 DuckDB
    ↓
DuckDB orders 表 (10.5M 行)
    ↓
语义层 → 服务层 → API → 前端
```

## 数据库表

| 表 | 行数 | 说明 |
|---|---|---|
| `orders` | 10,508,088 | 核心订单表（34列） |
| `user_rfm` | ~500K | RFM预计算表（17字段） |
| `user_first_purchase` | 4,090,000 | 首购日期 |
| `daily_visitors` | ~900 | 日粒度访客数据 |
| `order_status_override` | ~30K | 近30天订单状态覆盖 |
| `fact_rfm_long` | ~62M | RFM 长表（按周期展开） |
| `rfm_quarantine` | ~10K | RFM 隔离表（异常数据） |
| `rfm_query_cache` | ~5K | RFM 查询缓存 |
