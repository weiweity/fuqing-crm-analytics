# 芙清 CRM — 数据层文档

**版本**: v4.2（2026-06-06 刷 W4 fact_rfm_long + W5 cache）
**对应文件**: `backend/config.py`（DUCKDB_PATH 唯一入口）

---

## 1. 数据库架构

### 1.1 DuckDB 配置

```python
# backend/config.py
from pathlib import Path
DATA_DIR = Path("/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/data")
DUCKDB_PATH = DATA_DIR / "processed" / "fuqing_crm.duckdb"
```

> ⚠️ 所有 Service/ETL 必须从 `backend.config` 导入 `DUCKDB_PATH`，禁止硬编码路径。

### 1.2 核心表结构

#### orders 表（34 列，主表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `order_id` | VARCHAR | 主键 |
| `user_id` | VARCHAR | 用户标识 |
| `pay_time` | TIMESTAMP | **付款时间（时间维度统一用此字段）** |
| `order_status` | VARCHAR | 订单状态 |
| `actual_amount` | DOUBLE | 实付金额 |
| `is_goujinjin` | BOOLEAN | 是否购物金订单（三字段 OR 含"购物金"/"面值"） |
| `is_refund` | BOOLEAN | 是否退款（三条件：order_status含"交易关闭"/"退款"/refund_status非空） |
| `channel` | VARCHAR | 渠道（9层漏斗分类，统一大写 U 如 `U先派样`） |
| `province` / `city` | VARCHAR | 地域 |
| `spu_tier` / `spu_product_class` | VARCHAR | 产品梯队/品类 |
| `is_member` | BOOLEAN | 是否会员 |
| `etl_date` | DATE | 数据导入日期 |

**索引**：
```sql
CREATE INDEX idx_orders_pay_time ON orders(pay_time);
CREATE INDEX idx_orders_channel_pay_time ON orders(channel, pay_time);
CREATE INDEX idx_orders_channel_member ON orders(channel, is_member);
```

#### user_rfm 表（17 字段）

主键：`(user_id, analysis_date, metric_type, lookback_days)`

| 字段 | 说明 |
|------|------|
| `r_score` / `f_score` / `m_score` | RFM 评分（1-5 分） |
| `segment_id` | 象限 ID（**1-8**，v4.0 从11象限改为8象限） |
| `segment_name` | 象限名称 |
| `recency_days` | 最近购买距今天数 |
| `frequency` | 购买频次 |
| `monetary` | 累计消费金额 |

#### user_first_purchase 表

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | VARCHAR | 主键 |
| `first_pay_date` | DATE | 首购日期（= 有效订单 MIN DATE） |

> 首购日期 = 有效订单（`is_goujinjin=FALSE AND order_status!='交易关闭' AND is_refund=FALSE`）的 MIN DATE。

#### rfm_analysis_cache 表（RFM 预计算缓存，v4.0 新增）

| 字段 | 说明 |
|------|------|
| 预计算组合 | YTD/MTD × 2024/2025/2026 × GSV/GMV = **12 条** |
| 用途 | RFM 分析查询加速（14ms，原 2-4s） |

---

## 2. 数据规模

> 截至 2026-06-04 6/4 增量 ETL 跑批后（run 1/3 real elapsed 63.2min / step_wall_time_sum 126.4min）

| 指标 | 数量 |
|------|------|
| 原始 orders 表 | 10,654,714 行（+18,477 vs 5/31） |
| 有效订单（剔除购物金+退款） | ~10.6M |
| user_first_purchase | 4,246,328 用户（+8,379） |
| user_rfm 累计 | 72,401,294 行（+9.66M，含 Step 7b 466 组合预加载） |
| rfm_analysis_cache | 60 行（YTD/MTD × 3年 × 2指标 = 12 组合） |
| daily_metrics | 1,781 行 |
| order_status_override | 340,262 行（含 6/4 刷 91,307 行） |
| parquet 文件 | `data/parquet/`（shop/ + member/） |
| 淘客文件 | 41 个（2022-2026） |
| **fact_rfm_long**（W4 新增） | W4 MVP 1 组合 (`channel=全店`) 预计算 + PRIMARY KEY `(date, dimension_key, version)` + UNIQUE INDEX `idx_fact_rfm_dkv` |
| **manifest.json**（W2 新增） | `data/processed/manifest.json` + `.versions/{ts}_v{N}.json` 备份 7 天保留（POSIX atomic rename，**不**用 symlink） |
| **rfm_quarantine**（W3 新增） | 失败断言隔离表（id, date, failed_assertion, reason, raw_data JSON, created_at） |

---

## 3. ETL 流程

### 3.1 入口命令

```bash
# 增量更新（推荐每日使用；必须用 homebrew Python 3.14，workbuddy Python 3.13 有代码签名冲突）
PYTHONPATH="/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics" \
/Users/hutou/homebrew/bin/python3 scripts/run_etl.py --update

# 全量重建（数据异常时使用）
PYTHONPATH="/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics" \
/Users/hutou/homebrew/bin/python3 scripts/run_etl.py --full
```

> **6/4 update 跑批实测**（10:42→11:46，real elapsed 63.2min / step_wall_time_sum 126.4min）：4 个新源文件（店铺 1 + 会员 1 + 状态刷新 2 任务 21378 共 46MB → 91,307 行 override）；DuckDB 增量 orders +18,477 / user_first_purchase +8,379 / user_rfm +9.66M。Step 7b 540 组合 RFM 预加载完成 466 个（74 个 30 天窗口为 0 行属正常）。

### 3.2 ETL 流程图

```
原始数据源（xlsx + 淘客CSV）
    │
    ▼
┌──────────────┐
│ 增量检测    │  文件名 + mtime 双重判断
│             │  覆盖旧文件后自动重新处理
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 数据读取     │  Polars/Pandas 读取大文件
│             │  dtype=str 防精度丢失
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 数据清洗     │  时间格式化/金额标准化/去重
│             │  破折号"——"占位符清理
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 渠道归因     │  9层漏斗匹配（U先派样/百补派样/赠品/达播/微博/直播/淘客/货架/其他）
│             │  P4 达播/微博 → keyword_rules/id_rules（仅对 channel='其他' 生效）
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 状态覆盖表   │  zip/xlsx 自动解压
│             │  反向同步 override→orders
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ DuckDB 写入  │  Sanity Check 门卫
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ RFM 预计算   │  DuckDB 预计算表（12组合）
│ 缓存         │  Plan C 文件缓存 + Plan P1 DuckDB 表
└──────┬───────┘
       │
       ▼
清洗后 DuckDB 数据库
```

### 3.3 数据门卫

| 门卫 | 规则 | 触发动作 |
|------|------|---------|
| 退款率门卫 | 退款率 < 25% | 收紧：退款率 < 25% 才通过 |
| 会员覆盖率门卫 | **已移除** | — |
| 金额 null 检查 | actual_amount IS NOT NULL | 清洗 |
| 订单状态占位符 | order_status != '——' | 清洗 |

### 3.4 淘客缓存机制（v4.0 新增）

- **文件级缓存**：`data/processed/taoke_file_cache.json`（filename → {mtime, ids}）
- **未变化文件**：直接跳过，0 秒加载
- **效果**：49 个淘客文件全部秒级加载

### 3.5 渠道漏斗判定顺序（v4.0）

| 层级 | 名称 | 判定规则 |
|------|------|---------|
| P1 | U先派样 | spu_type 含"小样-U先" 或 product_title 含"U先" |
| P2 | 百补派样 | spu_type 含"小样-百亿补贴" 或 product_title 含"by" |
| P3 | 赠品&0.01 | spu_type 含"小样"（排除P1/P2）或 product_title 含"赠品" 或 actual_amount < 4 |
| P4 | 达播 | keyword_rules / id_rules（**仅对 channel='其他' 生效**，保护P1-P3） |
| P5 | 微博 | keyword_rules / id_rules（**仅对 channel='其他' 生效**） |
| P6 | 直播 | order_id 在直播 CSV 父订单号集合中（**仅对 channel='其他' 生效**） |
| P7 | 淘客 | order_id 在淘客数据库中（**仅对 channel='其他' 生效**） |
| P8 | 货架 | P1-P7 未命中且 spu_type 含"正装" |
| P9 | 其他 | P1-P8 未命中 |

> ⚠️ P4/P5/P6/P7 均需通过 `channel == '其他'` 保护 P1-P3，v4.0 修复了此 bug。

---

## 4. 口径变更记录

### 4.1 2026-04-17 P0 Bug 修复

**问题**：`order_status LIKE '%成功%'` 错误过滤掉 4 月 49,064 条"卖家已发货"有效订单。

**修复前（错误）**：
```sql
order_status LIKE '%成功%'
```

**修复后（正确）**：
```sql
-- 双保险过滤
is_refund = FALSE AND order_status != '交易关闭'
```

**影响范围**：
- `OrderFilters.valid_order()` → `is_goujinjin = FALSE AND order_status != '交易关闭' AND is_refund = FALSE`
- `OrderFilters.gmv_base()` → `is_goujinjin = FALSE AND order_status != '交易关闭'`
- `FilterBuilder.build()` → 按 metric_type 选 gmv_base() 或 valid_order()

### 4.2 2026-04-20 渠道名大小写统一

**问题**：数据库存 `u先派样`（小写u），前端/后端硬编码全用 `U先派样`（大写U）。

**修复**：
- 数据库：108万条记录 `u先派样` → `U先派样`
- ETL：`match_channel()` P1 写入 `U先派样`
- 语义层：`DB_TO_UI["U先派样"]` 恒等映射

### 4.3 2026-04-20 P4 ETL Bug 修复

**问题**：P4（达播/微博）keyword_rules **直接覆盖所有订单**，与 docstring 承诺的"含P4保护（仅对channel='其他'生效）"矛盾。

**修复**：P4/P5/P6/P7 均添加 `mask_unmatched = df['channel'] == '其他'` 检查。

---

## 5. Parquet 文件说明

| 路径 | 说明 |
|------|------|
| `data/parquet/shop/` | 店铺订单数据 |
| `data/parquet/member/` | 会员数据 |
| `dtype` | 统一为 `str`（防精度丢失） |

> ⚠️ parquet 文件由 ETL 自动生成，不要手动修改。

---

## 6. W4 fact_rfm_long 预计算表（v0.4.9, 2026-06-05）

### 6.1 表结构

```sql
CREATE TABLE fact_rfm_long (
    date              DATE          NOT NULL,     -- 业务日期 (T-1 增量)
    dimension_key     VARCHAR       NOT NULL,     -- e.g. "channel=全店"
    dimension_json    JSON          NOT NULL,     -- e.g. {"channel": "全店"}
    user_count        BIGINT        NOT NULL,     -- 购买人数
    gmv               DECIMAL(18,2),              -- GMV 金额
    repurchase_count  BIGINT,                     -- 复购人数 (order_count >= 2)
    version           INTEGER       NOT NULL,     -- dbt-style snapshot version
    created_at        TIMESTAMP     DEFAULT now(),
    PRIMARY KEY (date, dimension_key, version)
);
```

**UNIQUE INDEX**：
```sql
CREATE UNIQUE INDEX idx_fact_rfm_dkv
    ON fact_rfm_long (date, dimension_key, version);
```

> 设计原则：W4 MVP 仅 1 组合 (`channel=全店`) 验证机制；W4 full 扩 9 channel × 60 item × 1 segment = 540 组合。`dimension_key` 用 key=value 格式（如 `channel=全店&item=面膜&segment_id=3`），`dimension_json` 是结构化 JSON。

### 6.2 组合数计算（W4 full 目标）

| 维度 | 取值 | 数量 |
|------|------|------|
| channel | U先派样/百补派样/赠品&0.01/达播/微博/直播/淘客/货架/其他 | 9 |
| item | top 60 `spu_product_class` by GMV（不足 60 走 `W4_ITEMS_FALLBACK`） | 60 |
| segment_id | 1 | 1 |
| **理论组合** | | **540** |

### 6.3 写入策略（W4 MVP: 纯增量 append T-1）

```python
# scripts/etl/precompute_fact_rfm.py:incremental_load()
# MVP 简化: 1 组合 (channel='全店') append T-1 (target_date - 1) 当天数据
# 走 ON CONFLICT DO NOTHING 保证幂等, RETURNING date 拿实际插入行数
insert_sql = f"""
    INSERT INTO {FACT_RFM_TABLE}
        (date, dimension_key, dimension_json, user_count, gmv, repurchase_count, version)
    SELECT
        ?::DATE, ?, ?::JSON,
        COUNT(DISTINCT user_id) as user_count,
        SUM(actual_amount) as gmv,
        COUNT(DISTINCT CASE WHEN order_count >= 2 THEN user_id END) as repurchase_count,
        ? as version
    FROM (
        SELECT user_id, actual_amount,
               COUNT(order_id) OVER (PARTITION BY user_id) as order_count
        FROM orders
        WHERE DATE(pay_time) = ?::DATE AND channel = '全店' AND valid_sql = 1
    ) t
    ON CONFLICT (date, dimension_key, version) DO NOTHING
""" + " RETURNING date"  # DuckDB 1.5+ RETURNING 拿真实插入行数
```

- **T-1 增量**：每次跑批只 append `target_date - 1` 当天数据（W4 full 留 T-7 dbt-style merge 兜底）
- **幂等性**：`ON CONFLICT (date, dimension_key, version) DO NOTHING` + `_next_version()` 续号
- **W4 full 留 `merge_replace()` / `incremental_load_with_merge(t_minus_days=7)` 占位**：本期未实施

### 6.4 读路径

```python
# backend/services/rfm/loader.py:get_rfm_view_name()
# W2 配套: 走 manifest 原子读
view = SnapshotManifest(DEFAULT_MANIFEST_PATH).read_active()

# 实际 RFM 5 指标在 backend/services/rfm/ 包内 (r_flow/f_flow/m_flow) 委托
# run_flow_period() 实时聚合, W4 full 后才走 fact_rfm_long 预计算
```

> ⚠️ W4 MVP 仅完成预计算表 + 1 组合验证, RFM 5 指标当前走实时聚合 (r_flow/f_flow/m_flow), W4 full 才接 fact_rfm_long。

> ✅ W4 配套 W3：`assert_repurchase_nonzero` 查 `fact_rfm_long.repurchase_count` 验证回购率非 0。

---

## 7. W5 DuckDB-KV cache（设计稿, 未落地）

> ⚠️ **W5 当前状态**: 仅设计稿（`feat/wo5-cache` 分支），未合 main。W5 计划用 DuckDB-KV 替代文件级 JSON 缓存，目前 main 上仍走文件级缓存。

### 7.1 现状（v0.4.10 main）

```python
# backend/services/rfm/_shared.py
# _get_cached_flow() / _set_cached_flow() — 文件级 JSON 缓存 (与 W5 独立)
# 路径: FLOW_CACHE_DIR = DATA_DIR/"cache"/"rfm_flow"
# 文件名: {period}_{lookback_days}_{start_date}_{end_date}.json
# 缺点: 清理不彻底 / 文件 IO 慢 / 无法 atomic invalidate
```

### 7.2 W5 目标（v0.4.13 规划, `feat/wo5-cache` 分支）

```python
# backend/services/rfm/cache.py  — W5 设计稿 (未合 main)
CREATE TABLE rfm_query_cache (
    key         VARCHAR PRIMARY KEY,        -- SHA-256 hex
    endpoint    VARCHAR NOT NULL,            -- 'r-flow'/'f-flow'/'m-flow'/'segment-orders'
    params_hash VARCHAR NOT NULL,            -- SHA-256 hex of canonical params
    value       JSON NOT NULL,               -- json.dumps(result)
    expire_at   TIMESTAMP NOT NULL,          -- > now() 才算 hit
    created_at  TIMESTAMP NOT NULL
);

# 读
SELECT value FROM rfm_query_cache WHERE key = ? AND expire_at > now();

# 写 (DuckDB 不支持 changes(), 用 RETURNING 拿真实影响行数)
INSERT INTO rfm_query_cache (key, endpoint, params_hash, value, expire_at, created_at)
VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, expire_at=EXCLUDED.expire_at
RETURNING key;
```

### 7.3 与 W2 manifest 集成

```python
# _ManifestTracker: 进程内单例, 读 manifest version, 变化时 DELETE FROM rfm_query_cache
# (与 W2 atomic snapshot 配套 — 切换 active view 后所有 cache 失效)
```

### 7.4 与 4 个 RFM 端点的对应（实际 router: backend/routers/rfm.py）

| 端点 | router 函数 |
|------|-----------|
| GET /api/v1/rfm/r-flow | `get_rfm_r_flow_api` |
| GET /api/v1/rfm/f-flow | `get_rfm_f_flow_api` |
| GET /api/v1/rfm/m-flow | `get_rfm_m_flow_api` |
| GET /api/v1/rfm/segment-orders | `get_segment_orders_api` |
| GET /api/v1/rfm/version | `get_rfm_manifest_version`（不缓存，实时读 manifest） |

> 完整 W5 实现见 `feat/wo5-cache` 分支（C-3 task 跟进，**未合 main**）。
