# 数据布局 (Data Layout)

> 项目所有数据目录的单一 source of truth。Sprint 56 起新增/迁移数据必读。

**最后更新**: 2026-06-21

---

## 顶层结构

```
fuqing-crm-analytics/
├── data/                       [运行时数据, .gitignore 大部分排除]
│   ├── raw/                    [原始输入, 不可变]
│   ├── cache/                  [ETL 中间缓存, 可重建]
│   ├── exports/                [用户导出 CSV, 业务交付物]
│   ├── parquet/                [列存中间层, W2 规范化产物]
│   └── processed/              [主 DuckDB + dq snapshot + etl perf + backups]
├── analysis/                   [业务分析 xlsx, 业务方提供]
│   ├── sampling_analysis_v3.xlsx
│   └── sampling_analysis_v4.xlsx
├── config/                     [业务配置 + 备份]
│   ├── health_config.json      [健康评分配置, 5 指标权重 + 阈值]
│   └── health_config_backups/  [30+ 天历史快照, 自动滚动]
└── data/processed/backups/     [DuckDB 全量备份, .zst 压缩, 7 天滚动]
```

---

## data/raw/ — 原始输入

| 子目录 | 用途 | 读写模式 | 清理策略 |
|---|---|---|---|
| `channel_details/` | 11 个渠道 csv (货架/直播/淘客/达播 等) | **只读**, ETL W1 拉取源 | **永不清理**, 业务方上游数据, 丢失不可重建 |

**写入者**: 业务方手动放置 (Sprint 6+ 流程)
**读取者**: `scripts/etl/sources.py::load_channel_details()`
**大小**: ~数 MB, .gitignore 排除

---

## data/cache/ — ETL 中间缓存

| 子目录 | 用途 | 读写模式 | 清理策略 |
|---|---|---|---|
| `health_overview/` | 健康评分 API 响应缓存 (json, ~200 文件) | **R+W**, W3 DQ 写, FastAPI /health/* 读 | **TTL 24h**, `scripts/backend/cache/cleanup_health_cache.py` |
| `rfm_flow/` | RFM 桑基图前端缓存 (json, ~25 文件) | **R+W**, W4 写, FastAPI /v1/flow/* 读 | **TTL 7d** (业务低频), 手动清理 |

**详细**: 见 [data/cache/README.md](../data/cache/README.md)
**关键**: 可重建, 清掉后下次 ETL 自动重生成。生产慎清 — 会瞬时打爆 FastAPI。

---

## data/exports/ — 用户导出 CSV

| 文件 | 用途 | 读写模式 | 清理策略 |
|---|---|---|---|
| `gsv_daily_export.csv` | **核心**, GSV 日维度全量导出 (~100KB) | **R+W**, `/v1/exports/gsv` API 写, 业务方下载 | **永不清理**, 业务交付物, 审计要求 |
| `gsv_daily_export_pid_*.csv` | 3 个历史 pid 分片, 已废弃 | R | 历史归档, 不删 (跟 pid 1009707365820/1010458880710/933524395698 业务绑定) |
| `gsv_daily_export_pid.csv` | 单 pid 旧版 | R | 历史归档 |

**详细**: 见 [data/exports/README.md](../data/exports/README.md)
**关键**: 这是业务方直接消费的产物, 改格式 = 业务方合同变更。

---

## data/parquet/ — 列存中间层

| 子目录 | 用途 | 读写模式 | 清理策略 |
|---|---|---|---|
| `member/` | 会员维表 parquet (~90 文件) | **R+W**, W2 规范化写, DuckDB 读 | **可重建**, 手动清理 (跟 ETL 同步) |
| `shop/` | 店铺维表 parquet (~115 文件) | **R+W**, W2 规范化写, DuckDB 读 | **可重建**, 手动清理 |

**详细**: 见 [data/parquet/README.md](../data/parquet/README.md)
**关键**: 这是 DuckDB 直接 attach 的源头, 清掉 = ETL 必跑批重建。

---

## data/processed/ — 主 DuckDB + 元数据

| 子目录/文件 | 用途 | 读写模式 | 清理策略 |
|---|---|---|---|
| `fuqing_crm.duckdb` | **核心**, 主库 (~115GB, 10.75M 订单 + RFM 预计算) | **R+W**, ETL 写, FastAPI 读 | **永不删**, 业务方主消费源 |
| `dq_snapshot.json` | DQ 监控快照 (member_ratio + orders_count + timestamp) | **R+W**, W3 写, /qa 读 | 覆盖写, 不累积 |
| `live_file_cache.json` (~7MB) | 实时订单 ID 缓存 (pkl/json 索引) | **R+W**, W1 写, FastAPI 读 | 覆盖写, 不累积 |
| `taoke_order_ids.pkl` | 淘客订单 ID pkl 索引 | **R+W**, W1 写, FastAPI 读 | 覆盖写, 不累积 |
| `cache/` | processed 层 pkl 索引 (跟 data/cache 区分, 这里存 ETL 内部用) | R+W | 覆盖写 |
| `etl_perf/` | ETL 跑批性能日志 (json) | **append**, W7 helper 写 | **30 天滚动**, `scripts/etl/etl_perf_cleanup.py` |
| `backups/` | DuckDB 全量备份 (`*.duckdb.zst`, 7 天滚动, Sprint 25 信任化) | **W** (Sprint 25 cron), **R** (manual restore) | **7 天自动清**, 3 restore 演练 test 通过 |

**关键恢复命令**:
```bash
# 列出备份
ls -la data/processed/backups/

# 恢复 (示例)
zstd -d data/processed/backups/fuqing_crm_2026-06-20_0330.duckdb.zst \
  -o /tmp/fuqing_crm_restore.duckdb
```

---

## analysis/ — 业务分析 xlsx

| 文件 | 用途 | 写入者 | 读取者 | 备注 |
|---|---|---|---|---|
| `sampling_analysis_v3.xlsx` | 派样分析 v3 业务模板 | 业务方 | 采样分析 endpoint | 12.9KB |
| `sampling_analysis_v4.xlsx` | 派样分析 v4 业务模板 (Sprint 后继) | 业务方 | 采样分析 endpoint | 11.8KB |

**v3 vs v4 区别** (业务语义):
- **v3**: 老版本, 派样渠道只算"派样自身渠道" (U先派样/百补派样)
- **v4**: 新版本, 派样渠道扩展, 含"派样带来的二次复购" (跟主订单交叉 join)
- **endpoint 选择**: 前端 `SamplingView.vue` 顶部 dropdown 切换 v3/v4, 后端 `sampling_service.py` 根据 query 参数分派

**读写模式**: **只读** (业务方资产, 不写回)
**清理策略**: 永不删, 业务合同资产

---

## config/ — 业务配置

| 文件 | 用途 | 读写模式 | 清理策略 |
|---|---|---|---|
| `health_config.json` | 健康评分配置 (5 指标权重 + 阈值 + 告警 + 等级边界) | **R+W** (管理后台 UI 改), FastAPI /health/* 读 | 改前自动备份 |
| `health_config_backups/` | `health_config.json` 历史快照 (~30+ 天) | **W** (UI 改前自动), **R** (manual diff) | **30 天滚动** |

**关键 schema** (5 指标权重总和必须 = 1.0):
- `all_store_repurchase_rate` 0.3
- `same_product_repurchase_rate` 0.2
- `old_customer_gsv_ratio` 0.05
- `old_customer_aus` 0.4
- `recent_7d_repurchase_users` 0.05

未在 json 出现的字段 → 用 `backend/services/health/config.py` 第 32-97 行 Python 默认值。

---

## .gitignore 规则 (Sprint 验证后)

```gitignore
# data/ 大目录 (除 .gitkeep / README.md)
data/cache/
data/exports/*.csv
data/parquet/
data/processed/fuqing_crm.duckdb
data/processed/cache/
data/processed/etl_perf/
data/processed/live_file_cache.json
data/processed/taoke_*.pkl
data/raw/channel_details/

# backups 保留 7 天滚动, 旧备份不进 git (cron 自动清)
data/processed/backups/

# analysis/ 业务资产 → 进 git (业务方版本控制)
!analysis/sampling_analysis_v3.xlsx
!analysis/sampling_analysis_v4.xlsx

# config/ 配置文件 + 备份 → 进 git (历史快照审计)
!config/health_config.json
!config/health_config_backups/
```

---

## 关联文档

- [STATUS.md](../STATUS.md) — 项目总状态
- [docs/architecture/DATA_PIPELINE.md](architecture/DATA_PIPELINE.md) — ETL 4 阶段数据流
- [docs/TECH-DEBT.md](TECH-DEBT.md) — 技术债台账
- [data/cache/README.md](../data/cache/README.md) — cache 子目录
- [data/exports/README.md](../data/exports/README.md) — exports 子目录
- [data/parquet/README.md](../data/parquet/README.md) — parquet 子目录
