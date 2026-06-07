# 芙清 CRM — 服务层文档

**版本**: v3.1（2026-06-06 补 W3 DQ assertions + W5 cache）
**对应目录**: `backend/services/`
**核心原则**: Service 只负责编排查询，禁止硬编码 SQL 过滤条件。

---

## 1. 服务层总览

```
backend/services/
├── metrics_service.py       # 核心指标（GSV/GMV/新老客/会员）
├── rfm/                  # RFM 服务包 (7 个 .py: __init__/_shared/_flow_engine/r_flow/f_flow/m_flow/segment_orders/loader)
├── churn_service.py         # 流失分析（动态阈值）
├── geo_service.py           # 地域分布/人群
├── category_service.py      # 品类分布/人群
├── flow_service.py          # 人群流转矩阵
├── asset_service.py         # 人群资产总览
├── export_service.py        # CSV/Excel 导出（健康分析）
├── report_service.py        # 报告生成
├── health/                 # 老客健康分析（10 模块）
│   ├── overview.py         # 现状概览（运营日报）
│   ├── repurchase.py       # 复购周期分析
│   ├── tiers.py            # 价值分层
│   ├── tier_flow.py        # 梯队流转矩阵
│   ├── rfm_analysis.py     # RFM 分析（8 象限 + 预计算缓存）
│   ├── conversion.py       # 新客转化
│   ├── promotion.py        # 推广日历
│   ├── config.py           # 配置管理（认证 + 历史 + 审计）
│   └── channel_scores.py   # 渠道健康评分
```

---

## 2. 各 Service 状态

| Service | 语义层接入 | 状态 | 说明 |
|---------|----------|------|------|
| `metrics_service.py` | `FilterBuilder`, `MetricType`, `OrderFilters` | ✅ 通过 | 6 处过滤条件已替换 |
| `churn_service.py` | `OrderFilters.valid_order()` | ✅ 通过 | 4 处硬编码已替换 |
| `geo_service.py` | `OrderFilters.valid_order()` | ✅ 通过 | 5 处硬编码已替换 |
| `category_service.py` | `OrderFilters.valid_order()` | ✅ 通过 | 8 处硬编码已替换 |
| `rfm/` 包 | `SegmentRegistry` | ✅ 通过（v4.0） | 8 象限 CASE WHEN 已迁移至 `segments.py`；W2 manifest 走 `loader.py:get_rfm_view_name()` |
| `export_service.py` | — | ✅ 新增 | CSV 导出（健康分析） |
| `report_service.py` | — | ✅ 新增 | 报告生成 |
| `health/overview.py` | `calculations.py` | ✅ 通过 | YoY/MoM 使用统一函数 |
| `health/repurchase.py` | `OrderFilters.valid_order()` | ✅ 通过 | 复购周期分析 |
| `health/tiers.py` | `SegmentRegistry` | ✅ 通过 | 价值分层 |
| `health/rfm_analysis.py` | `RFM_THRESHOLDS` | ✅ 通过 | 预计算缓存（Plan C + Plan P1） |

---

## 3. 核心 Service 说明

### 3.1 MetricsService

**职责**：提供 GSV/GMV/新老客/会员等核心指标。

**关键接口**：
```python
# GET /api/v1/metrics/overview
# 参数: metric_type (GSV/GMV), start_date, end_date, channels[], member_only
# 返回: OverviewMetrics

# GET /api/v1/metrics/trend
# 参数: metric_type, start_date, end_date, group_by (day/week/month)
# 返回: TrendResponse

# GET /api/v1/audience/table
# 参数: start_date, end_date, channel[], spu_tier[], segment_id[]
# 返回: AudienceTableResponse
```

**GSV vs GMV 口径选择**：
```python
# 由 FilterBuilder 根据 metric_type 自动选择
fb.with_metric_type(MetricType.GSV)   # 选 valid_order()
fb.with_metric_type(MetricType.GMV)   # 选 gmv_base()
```

> ⚠️ **2026-04-17 人群看板口径统一**：所有 audience 相关 API 的 KPI/日趋势/30指标/渠道概览全部改为 GSV 口径。

### 3.2 RFMService

**职责**：8 象限分析 + RFM 评分计算（v4.0 从 11 象限重构为经典 8 象限）。

**关键接口**：
```python
# GET /api/v1/rfm/segments
# 返回: RFMSegmentResponse（8 象限 + 覆盖率 100%）

# GET /api/v1/rfm/distribution
# 参数: lookback_days (90/180/365)
# 返回: R/F/M 各维度分布

# 内部: refresh_rfm_table() — ETL 定时刷新 RFM 表
```

**象限渲染**（前端）：
```typescript
// 8 象限颜色（v4.0，经典 RFM）
const SEGMENT_COLORS: Record<number, string> = {
  1: '#FF6B6B',   // 重要价值
  2: '#4ECDC4',   // 重要保持
  3: '#45B7D1',   // 重要发展
  4: '#96CEB4',   // 重要挽留
  5: '#DDA0DD',   // 一般价值
  6: '#98D8C8',   // 一般保持
  7: '#F7DC6F',   // 一般发展
  8: '#BDC3C7',   // 一般挽留
};
```

**预计算缓存**（v4.0 新增）：
- Plan C：文件缓存 JSON（`backend/cache/rfm/`），历史周期第 2 次 17ms（36x 加速）
- Plan P1：DuckDB 预计算表 `rfm_analysis_cache`，12 组合预计算，14ms（260x 加速）

### 3.3 ChurnService

**职责**：流失分析（动态阈值 + 单品类）。

**动态流失阈值**（典型周期 × 150%）：

| 象限 | 典型周期 | 流失阈值 |
|------|---------|---------|
| 钻石会员 | 30 天 | 45 天 |
| 潜力新贵 | 30 天 | 45 天 |
| 忠实金主 | 90 天 | 135 天 |
| 频次买家 | 60 天 | 90 天 |
| 豪气新客 | 30 天 | 45 天 |
| 清新路人 | 30 天 | 45 天 |

---

## 4. Service 开发规范

### 4.1 禁止事项

```python
# ❌ 禁止：在 Service 中硬编码过滤条件
SELECT SUM(actual_amount)
FROM orders
WHERE order_status LIKE '%成功%'   # 硬编码！

# ❌ 禁止：在 Service 中硬编码 8 象限 CASE WHEN
CASE WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 1 ...  # 硬编码！

# ❌ 禁止：在同一 SQL 中混用不一致的过滤条件
WHERE ... (部分用 is_refund=FALSE，部分用 order_status LIKE '%成功%')
```

### 4.2 正确做法

```python
# ✅ 正确：通过 FilterBuilder 构造条件
fb = FilterBuilder()
fb.with_metric_type(MetricType.GSV)
fb.with_time_range(start_date, end_date)
sql, params = fb.build()  # 统一引用语义层

# ✅ 正确：通过 SegmentRegistry 生成象限 SQL
from backend.semantic.segments import get_registry
registry = get_registry()
segment_sql = registry.build_segment_case_when_sql()
```

---

## 5. 近期 Bug 修复记录

| 日期 | Bug | 修复 | 影响 |
|------|-----|------|------|
| 2026-04-20 | RFM评分阈值硬编码不一致 | `rfm_analysis.py` 硬编码与 `RFM_THRESHOLDS` 不一致 | 8象限人群分层错误 |
| 2026-04-20 | P4 ETL Bug（keyword_rules直接覆盖所有订单） | 添加 `channel=='其他'` 保护 P1-P3 | 渠道数据准确性 |
| 2026-04-20 | `get_overview_metrics` MoM/YoY 内联计算 | 替换为 `calculations.py` 统一函数 | 语义层口径统一 |
| 2026-04-20 | 渠道名大小写不统一 | DB迁移108万条，`u先派样`→`U先派样` | 渠道筛选准确性 |
| 2026-04-20 | ETL增量检测失效（只判断文件名） | 升级为文件名+mtime双重判断 | 覆盖文件重新处理 |
| 2026-04-20 | 淘客49个文件每次全量加载 | 文件级缓存 `taoke_file_cache.json` | 49文件0秒加载 |
| 2026-04-19 | 健康分析PUT /config无API Key认证 | 添加 API Key 认证 | 安全加固 |
| 2026-04-19 | 8处连接泄漏（conn.close缺失） | 全部添加 try/finally | 连接资源安全 |
| 2026-04-17 | `order_status LIKE '%成功%'` 误杀"卖家已发货"订单 | 改为 `is_refund=FALSE AND order_status!='交易关闭'` | 4月GSV ¥143万→¥534万 |
| 2026-04-17 | WTD prev2 日期倒置 | 修复 date 计算逻辑 | 同比数据错误 |
| 2026-04-17 | 新老客 cutoff Bug | cutoff = start_date - 1天 | Q1老客占比 75%→38.9% |

---

## 6. W3 DQ Assertions（v0.4.10, 2026-06-06）

> **目标**：SaaS 标准 — 脏数据隔离不阻塞业务，失败入 `rfm_quarantine` + 告警，ETL 继续。

### 6.1 3 核心断言

| 断言 | 检查内容 | 触发动作 |
|------|----------|---------|
| `assert_total_not_drop` | `total < prev_30d_avg × 0.3` (T-1 vs 过去 30 天均值) | quarantine + lark alert |
| `assert_repurchase_nonzero` | `fact_rfm_long.repurchase_count` 查 W4 配套 | quarantine + lark alert |
| `assert_idempotency` | `(date, dimension_key, version)` 唯一 (W4 配套) | quarantine + skip |

### 6.2 总入口

```python
# scripts/etl/assertions.py:run_assertions()
from scripts.etl.assertions import run_assertions

# Service / CLI 调用
def post_etl_hook(target_date: date):
    result = run_assertions(conn, target_date, send_alert=True)
    # result = {'passed': int, 'failed': int, 'failed_names': [str], 'alert_sent': bool}
    if result['failed'] > 0:
        log.warning(f"DQ failed: {result['failed_names']}")
    return result
```

> ⚠️ 当前 main 上 `pipeline.py` **未集成** step 8 调 `run_assertions()`（W3 full 留作下次 sprint）。可独立 CLI 调用。

### 6.3 quarantine 表

```sql
-- scripts/etl/assertions.py
CREATE TABLE IF NOT EXISTS rfm_quarantine (
    id                INTEGER PRIMARY KEY DEFAULT nextval('seq_rfm_quarantine'),
    date              DATE    NOT NULL,
    failed_assertion  VARCHAR NOT NULL,  -- 'assert_total_not_drop' | 'assert_repurchase_nonzero' | 'assert_idempotency'
    reason            TEXT    NOT NULL,
    raw_data          JSON,              -- 失败时的上下文
    created_at        TIMESTAMP DEFAULT now()
);
CREATE SEQUENCE IF NOT EXISTS seq_rfm_quarantine START 1;
```

- **写入幂等**：`create_quarantine_table()` 自带 `IF NOT EXISTS`，可独立调用
- **跨子项目 import**：复用 `scraper/core/sanity_check.py:_send_lark_alert`（6 道门禁 lark-cli 通道，不新写 lark 客户端）
- **DuckDB 1.5+ 序列**：`nextval('seq_rfm_quarantine')` 自增 id

### 6.4 CLI 入口

```bash
# 手动跑断言
python3 scripts/etl/assertions.py --date=2026-06-05

# 不发 lark 告警（用于本地/CI）
python3 scripts/etl/assertions.py --date=2026-06-05 --no-alert
```

### 6.5 测试覆盖

- `backend/tests/test_w3_dq_assertions.py` (10 tests)
  - `TestQuarantineTable`: `test_create_quarantine_idempotent` (1)
  - `TestAssertTotalNotDrop`: pass / fail / skip-新项目 3 个
  - `TestAssertRepurchaseNonzero`: pass / fail / skip-W4-未跑 3 个
  - `TestAssertIdempotency`: pass / fail-重复 2 个
  - `TestRunAssertions`: 全 pass / 部分 fail + alert 2 个
  - mock lark 不真发（MVP 测试不触发 lark-cli）
- commit SHA: `937b034` (merge: `1917e08`)

---

## 7. W5 DuckDB-KV cache（设计稿, 未落地）

> ⚠️ **W5 当前状态**: 仅设计稿（`feat/wo5-cache` 分支，v0.4.13），未合 main。W5 是 RFM 缓存层重构：用 DuckDB 表替代 JSON 文件缓存。

### 7.1 现状（v0.4.10 main）

```python
# backend/services/rfm/_shared.py
# _get_cached_flow() / _set_cached_flow() — 文件级 JSON 缓存 (TTL 24h, 走 sha256 key)
# 路径: FLOW_CACHE_DIR = DATA_DIR/"cache"/"rfm_flow"
# 缺点: 清理不彻底 / 文件 IO 慢 / 无法 atomic invalidate
```

### 7.2 W5 设计目标（`feat/wo5-cache` 分支, v0.4.13）

```python
# backend/services/rfm/cache.py  — W5 设计稿
class RfmQueryCache:
    def __init__(self, ttl_hours: int = DEFAULT_TTL_HOURS):  # 24h
        ...

    def get(self, endpoint: str, params: dict) -> Optional[Any]:
        # SHA-256 key = sha256(f"{endpoint}|{canonical(params)}")
        # SELECT value FROM rfm_query_cache WHERE key = ? AND expire_at > now()
        ...

    def set(self, endpoint: str, params: dict, value: Any) -> None:
        # INSERT OR REPLACE INTO rfm_query_cache ...
        # DuckDB 没有 changes(), 用 RETURNING 拿真实插入行数
        ...

# _ManifestTracker: 进程内单例, 读 manifest version, 变化时整表失效
# tracker.check_and_invalidate(conn) → DELETE FROM rfm_query_cache
```

### 7.3 4 个 RFM 端点的 cache_key（W5 设计）

> 实际 router: `backend/routers/rfm.py`（无 cache 装饰器，W5 落地后挂）

| 端点 | endpoint | cache_key 模板 |
|------|---------|---------------|
| GET /api/v1/rfm/r-flow | `r-flow` | sha256("r-flow\|{canonical params}") |
| GET /api/v1/rfm/f-flow | `f-flow` | sha256("f-flow\|{canonical params}") |
| GET /api/v1/rfm/m-flow | `m-flow` | sha256("m-flow\|{canonical params}") |
| GET /api/v1/rfm/segment-orders | `segment-orders` | sha256("segment-orders\|{canonical params}") |
| GET /api/v1/rfm/version | — | （不缓存，实时读 manifest） |

### 7.4 manifest invalidate 集成（W5 设计）

```python
# _ManifestTracker.check_and_invalidate(conn) → bool
# 读 SnapshotManifest 当前 version, 跟上次的 _current_version 比:
#   - 变化 → DELETE FROM rfm_query_cache (整表失效, 与 W2 atomic snapshot 配套)
#   - 一样 → noop
```

> ⚠️ DuckDB 不支持 `LIKE ANY (?)`。W5 实际用 `DELETE FROM rfm_query_cache`（整表清空），**不**走 key 过滤。

### 7.5 与 W2 / W3 / W4 的协作

| W | 协作点 |
|---|--------|
| W2 manifest | `_ManifestTracker` 读 version 变化 → 整表失效 |
| W3 DQ | 失败断言隔离走 `rfm_quarantine` 表（**不**走 cache，避免污染业务表） |
| W4 fact_rfm_long | W5 落地后，`fact_rfm_long` 行数暴跌可手动调 `tracker.check_and_invalidate()` |

### 7.6 单元测试规划

- `backend/tests/test_w5_cache.py` (待 C-3 落地, ~8 tests) — **`feat/wo5-cache` 分支已写, 未合 main**
  - `get` / `set` / `expire` 行为
  - `tracker.check_and_invalidate` 触发整表失效
  - 4 端点 `endpoint` 一致性

> 完整 W5 实现见 `feat/wo5-cache` 分支（C-3 task 跟进，**未合 main**）。
