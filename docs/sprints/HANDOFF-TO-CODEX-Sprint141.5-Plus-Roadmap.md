# HANDOFF-TO-CODEX — Sprint 141.5+ Roadmap (ETL sample_received_at + 4 真业务 sprint)

> **状态**: 🟡 立项 + Q1 已验 (2026-06-28)
> **触发**: Sprint 141 收口 — user 拍板"开始收尾这 5 个跨 sprint 留尾"
> **结构**: 1 详细 sprint (Sprint 141.5 纯 ETL, 拆 Phase 1 + Phase 2) + 4 高层 sprint (142-145+ 路线图)
> **模式**: 跟 Sprint 141 留尾治本 + Sprint 116+117 真 refactor 模式 stable (Codex Stage 2 实施 + Claude Stage 3 review)
> **关键约束**: Sprint 141.5 拆 **Phase 1 (1 周, schema 准备)** + **Phase 2 (业务补数据源后, 1 周, 真回填)**. Sprint 142-145+ 依赖 Sprint 141.5 (sample_received_at 是后续 RFM/LTV 起点)
> **Q1 已验**: source data = CSV (不是 xlsx), `data/raw/channel_details/赠品&0.01渠道.csv` + U先派样.csv + 百补派样.csv 等按 channel 切分; 现有 30 字段 `COLUMN_MAPPING` **无"收货时间"列**; 真 sample channel = `赠品&0.01渠道` (跟"U先派样/百补派样"派生 channel 不同, `backend/semantic/channels.py:133`)

---

## 0. 背景

### 0.1 user 原话

> "1. Sprint 141.5: ETL sample_received_at 字段（1 周纯 ETL）
>  2. Sprint 142: RFM 分层 + level 联动 summary 卡二级聚合 + _compute_lock_metrics 性能重构
>  3. Sprint 143: LTV 90/180/365d + cohort retention matrix + 改名 ROI→正装转化分析
>  4. Sprint 144+: cost/margin 表 + 财务对接 + holdout 实验框架
>  5. Sprint 145+: AARRR funnel + 行业基线 + AB test 框架
>  写个handoff，我们开始收尾这些任务"

### 0.2 路线图总览（依赖图）

```
Sprint 141.5 (1 周纯 ETL)
    │
    ├──► Sprint 142 (RFM + level 联动 + 性能重构)
    │       │
    │       └──► Sprint 143 (LTV + cohort retention + 改名 ROI)
    │
    📋 Sprint 144+ (cost/margin + 财务对接 + holdout) — 暂收口 (跟 Sprint 89/134 模式)
    📋 Sprint 145+ (AARRR + 行业基线 + AB test) — 暂收口
```

**关键依赖**:
- `sample_received_at` 是后续 RFM (Sprint 142)、LTV (Sprint 143) 的"派样→回购"真起点
- 当前 `first_sample_time = su.pay_time` (派样单支付时间)，跟"用户实际收货"差 1-7 天
- 业务侧若有 "收货时间" xlsx 列则 Sprint 141.5 落地; 若无, Sprint 141.5 落地 Phase 1 全 NULL 字段 (COALESCE 回退 pay_time), Sprint 141.5 Phase 2 业务确认后真回填 (Q1 已验: 现有 30 字段 COLUMN_MAPPING 无 receive_time, Phase 2 等业务侧拍板列名)
- Sprint 144+/145+ 暂收口: 业务侧当前不需要成本数据 / 财务对接 / holdout / AARRR / 行业基线 / AB test, 等真业务触发再开

### 0.3 Sprint 现状（基于 codegraph 实读 main @ `3910b3d` Sprint 141 merge 后）

| 模块 | 当前状态 | Sprint 141.5+ 改动 |
|---|---|---|
| `scripts/etl/load.py:45-87` `orders` schema | 有 `order_time/pay_time/ship_time`, **无 `receive_time`** | Sprint 141.5 **Phase 1** 加 `sample_received_at TIMESTAMP` (允许 NULL); **Phase 2** 业务补数据源后真回填 |
| `scripts/etl/config.py:23-24` `COLUMN_MAPPING` | CSV 30 字段无 receive_time (**Q1 已验, 2026-06-28**); 源数据是 CSV 不是 xlsx | **Phase 1 不动**; Phase 2 业务侧拍板列名后加映射 |
| `data/raw/channel_details/*.csv` | U先派样.csv + 百补派样.csv + 赠品&0.01渠道.csv 等按 channel 切分 | Phase 2 业务侧补"收货时间"数据源 (新 CSV / 飞书多维表格 / 客服 API) |
| `backend/services/sampling_service.py:83-107` | `first_sample_time = su.pay_time` (派样支付时间) | Sprint 141.5 **Phase 1** 加 `COALESCE(s.sample_received_at, o.pay_time) as first_sample_received_at`; Phase 1 全 NULL 时回退 pay_time |
| `backend/services/sampling_service.py:374-?` `_compute_lock_metrics` | 多次 `conn.execute` 单字段查询, 性能差 | Sprint 142 性能重构 (单 SQL 合并) |
| `backend/semantic/segments.py` `RFM_THRESHOLDS` | 8 quadrant 经典分割 | Sprint 142 扩展维度 (生命周期/价值层), **不替换 8 quadrant** |
| `frontend-vue3/src/views/SamplingView.vue:387` | subtitle `"U先/百补派样ROI / 0.01锁权转化分析"` | Sprint 143 改名 → `"U先/百补派样正装转化分析"` |
| LTV/cohort retention | **0 引用**, 全新建 | Sprint 143 (等 Phase 2 真数据回填) |
| cost/margin 表 | **0 引用**, 全新建 | Sprint 144+ |
| AARRR funnel / AB test | **0 引用**, 全新建 | Sprint 145+ |

---

# ═══════════════════════════════════════════════════════════════
# Sprint 141.5 详细（1 周纯 ETL，Codex 立即开工）
# ═══════════════════════════════════════════════════════════════

## 1. Sprint 141.5 范围（拆 Phase 1 + Phase 2, 按业务数据源就绪度施工）

### Phase 1 vs Phase 2 决策表

| 维度 | Phase 1 (本周可开) | Phase 2 (业务侧补数据源后) |
|---|---|---|
| **触发** | Q1 已验: 现有 CSV 30 字段无 receive_time, 业务侧还没补数据源 | 业务侧补 ETL 数据源（飞书多维表格/客服系统/手工 CSV）后 |
| **范围** | orders schema + ingest 透传 + service 回退 + pytest + CHANGELOG | COLUMN_MAPPING 加映射 + ETL 真跑批回填 + 业务真验 |
| **LOC** | +25/-5 (4 file) | +5/-0 (1 file) |
| **业务数据** | 0 数据写入, 字段全 NULL | 真实数据回填 (历史 + 增量) |
| **Sprint 142 依赖** | ✅ Phase 1 schema 准备 OK, RFM 改造 + 性能重构可并行开 | ✅ Phase 2 数据回填后, RFM 真验可走 |
| **Sprint 143 依赖** | ⚠️ LTV/cohort retention 真验依赖 Phase 2 数据 | ✅ 全闭环 |

---

### Phase 1 (Codex 立即可开, 1 周) — 4 个 Task

#### Task 1.1: `orders` schema 加 `sample_received_at` 字段

**文件**: `scripts/etl/load.py:45-87` (`CREATE TABLE orders`)

**改后 schema** (在 `load.py:45` `CREATE TABLE orders` 块加 1 行):
```sql
sample_received_at TIMESTAMP,  -- Sprint 141.5: 派样收货时间 (Phase 1 全 NULL; Phase 2 业务补数据源后回填)
```

**对应 `load.py:208` `CREATE TABLE orders_new`** (增量模式, 同步加):
```sql
sample_received_at TIMESTAMP,
```

**`ALTER TABLE` 兼容现有 production DB** (在 `load.py:184` `ensure_database_schema` 加 idempotent ALTER):
```python
def ensure_database_schema():
    # ... 既有 CREATE TABLE ...
    # Sprint 141.5 Phase 1: idempotent ALTER (生产 DB 已存在 orders 表, 加列不重建)
    try:
        conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS sample_received_at TIMESTAMP")
    except Exception:
        pass  # IF NOT EXISTS 已守卫, 老 DuckDB 不支持时手动跑迁移
```

#### Task 1.2: `ingest.py` 增量模式加 `sample_received_at` 字段透传

**文件**: `scripts/etl/ingest.py:308` (增量模式块附近)

**改后 (在 pandas 写入 DuckDB 之前加 1 行)**:
```python
# Sprint 141.5 Phase 1: 透传 sample_received_at (允许 NaT/NULL)
if 'sample_received_at' in df.columns:
    df['sample_received_at'] = pd.to_datetime(df['sample_received_at'], errors='coerce')
```

**Sprint 108/109 治根保护**: 复用 `_clean_processed_updates` + `_file_changed` (cold_start_marked 逻辑, Sprint 24+ P3 收口)
- 字段加列**不触发 tracker 重读** (mtime 不变 + hash 不变 → 走 False 短路)
- 老 CSV 文件无新列 → pandas 自动填 NaN → DuckDB 接受 NULL, **0 业务影响**

#### Task 1.3: `sampling_service.py` 回退逻辑 + duckdb index

**文件**: `backend/services/sampling_service.py:83-107` + `scripts/etl/load.py:264-265` (index 区)

**1.3.1 service 回退** (在 `sample_users_sql` 加 `COALESCE`):
```python
sample_users_sql = f"""
    SELECT DISTINCT
        o.user_id,
        o.pay_time as first_sample_time,
        COALESCE(s.sample_received_at, o.pay_time) as first_sample_received_at  -- Sprint 141.5 Phase 1: Phase 2 数据回填前 NULL, COALESCE 回退 pay_time
    FROM orders o
    LEFT JOIN orders s ON s.order_id = o.sub_order_id  -- 派样单子单收货时间
        AND s.channel = '{GIFT_SAMPLE_DB}'
    WHERE o.channel = ?
      AND o.pay_time >= ?::DATE AND o.pay_time <= ?::DATE + INTERVAL '1' DAY
"""
```

**⚠️ 治根 (L4.5)**:
- `GIFT_SAMPLE_DB` 是 backend/semantic/channels.py 定义的常量, 不内嵌字符串
- `{GIFT_SAMPLE_DB}` 在 f-string 内合法 (Pydantic + L4.1 + L4.5 守卫)

**1.3.2 duckdb index** (`load.py:264-265`):
```python
conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_sample_received ON orders(channel, sample_received_at)")
```

**1.3.3 sampling_period_distribution** (Sprint 141 bucket 改用 `first_sample_received_at`):
```python
# backend/services/sampling_service.py:231 period_sql
period_sql = f"""
    WITH sample_users AS ({sample_users_sql}),
         repurchase AS (
             SELECT
                 su.user_id,
                 o.pay_time as repurchase_time,
                 DATEDIFF('day', su.first_sample_received_at, o.pay_time) as days_between,  -- Sprint 141.5 Phase 1: Phase 2 数据回填前等价 first_sample_time
                 ...
             FROM ...
         )
    SELECT ... FROM repurchase
"""
```

#### Task 1.4: pytest 2 case + CHANGELOG entry

**1.4.1** 新建 `backend/tests/test_etl_sample_received_at.py` (2 case):
```python
"""Sprint 141.5 Phase 1 sample_received_at 字段回归测试"""

import pytest
from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE

pytestmark = pytest.mark.skipif(not _PROD_DUCKDB_AVAILABLE, reason="production DuckDB 不可用")


class TestSampleReceivedAtPhase1:
    """Sprint 141.5 Phase 1: orders schema 含 sample_received_at (允许 NULL) + service COALESCE 回退"""

    def test_orders_has_sample_received_at_column(self, monkeypatch_connection):
        """orders schema 含 sample_received_at TIMESTAMP (Sprint 141.5 Phase 1 加)"""
        cols = monkeypatch_connection.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'orders' AND column_name = 'sample_received_at'
        """).fetchall()
        assert len(cols) == 1
        assert "TIMESTAMP" in cols[0][1].upper()

    def test_sampling_service_falls_back_to_pay_time(self, monkeypatch_connection):
        """sample_received_at=NULL 时 first_sample_received_at = first_sample_time (Phase 1 回退)"""
        from backend.services.sampling_service import get_sampling_roi
        result = get_sampling_roi(
            start_date="2026-04-01",
            end_date="2026-06-30",
            window_days=30,
            level="spu_category",
        )
        # Phase 1 老数据全 NULL → COALESCE 走 pay_time → 跟 first_sample_time 一致
        # Phase 2 数据回填后, 走真收货时间, days_between 缩短 1-7 天
        assert "period_distribution" in result  # smoke test
```

**1.4.2** CHANGELOG entry (Phase 1):
```markdown
## [0.4.14.157] - 2026-06-28 (Sprint 141.5 Phase 1, VERSION 不变 - ETL sample_received_at 字段新增)

### Added (1 周纯 ETL schema 准备, 4 files / +25/-5, 0 业务数据写入)
- **scripts/etl/load.py**: `orders` schema 加 `sample_received_at TIMESTAMP` (允许 NULL); 增量模式 `orders_new` 同步; idempotent ALTER 兼容生产 DB.
- **scripts/etl/ingest.py**: 增量模式 `pd.to_datetime(errors='coerce')` 透传, 老 CSV 文件无列时填 NaN → DuckDB NULL.
- **backend/services/sampling_service.py**: `sample_users_sql` 加 `COALESCE(s.sample_received_at, o.pay_time) as first_sample_received_at`, Phase 1 全 NULL 时回退 `first_sample_time`; `period_sql` 用 `first_sample_received_at` 算 days_between (Phase 1 等价 first_sample_time).
- **scripts/etl/load.py**: 加 `idx_orders_sample_received` index.

### Test
- **backend/tests/test_etl_sample_received_at.py** (NEW, ~30 行, 2 case): schema 列存在 + service 回退逻辑 smoke test.

### Verification (Phase 1)
- Codex Stage 2 待跑: pytest 2 case PASS + Sprint 139/140/141 ground-truth-lint 钩子 PASS + pre-commit 全绿.
- VERSION: 0.4.14.157 不 bump; L4.x 22 stable 0 新增.
- 业务数据: 0 行写入 (Phase 1 全 NULL), 等业务侧补 ETL 数据源后开 Phase 2.

### NOT in scope (Sprint 141.5 Phase 2 + Sprint 142-145+ 跨 sprint 留尾)
- Phase 2: 业务侧补 ETL 数据源后, `COLUMN_MAPPING` 加映射 + ETL 真跑批回填 + 业务真验
- Sprint 142: RFM 扩展 + level 联动 summary 卡二级聚合 + _compute_lock_metrics 性能重构
- Sprint 143: LTV 90/180/365d + cohort retention matrix + 改名 ROI→正装转化分析
- Sprint 144+: cost/margin 表 + 财务对接 + holdout 实验框架
- Sprint 145+: AARRR funnel + 行业基线 + AB test 框架
```

---

### Phase 2 (业务侧补 ETL 数据源后, 1 周) — 2 个 Task

#### Task 2.1: `COLUMN_MAPPING` 加 `收货时间 → sample_received_at` (业务侧拍板后)

**文件**: `scripts/etl/config.py:23-?`

**前置** (业务侧必拍板, Codex 不能猜):
- **数据源格式**: 飞书多维表格导出 CSV / 客服系统 API JSON / 手工上传 Excel → 统一映射成 CSV (跟现有 channel_details 模式 stable)
- **列名**: 业务侧确认 `收货时间` / `收样时间` / `receive_time` 等具体列名
- **历史回溯范围**: 全部历史 / 最近 90 天 / 仅增量

**改后 (Phase 2 启动时根据业务侧拍板填具体映射)**:
```python
COLUMN_MAPPING = {
    # ... 既有映射 (Sprint 141.5 Phase 1 不动这部分) ...
    # Phase 2: 业务侧拍板的列名映射 (Codex 实施时根据业务侧回复替换)
    '<业务侧确认的列名>': 'sample_received_at',  # Sprint 141.5 Phase 2 新增
}
```

**⚠️ 关键约束 (L4.5 + L4.7)**:
- 字段加白名单常量, 不引入新 f-string 内嵌用户输入
- ETL 是独立离线脚本 (WO-5 P2-#2 条款), 允许 `duckdb.connect(...)` + `conn.close()`, 单例规则不适用

#### Task 2.2: ETL 真跑批回填 + 业务真验

**前置**: Task 2.1 业务侧拍板列名 + 提供数据源样例文件后

**改后** (`scripts/run_etl.py` 增量模式触发真跑批):
```bash
PYTHONPATH="$(pwd)" /Users/yourname/homebrew/bin/python3 scripts/run_etl.py --update --sample-received-backfill
```

**业务真验** (Phase 2 收口必跑):
```bash
PYTHONPATH="$(pwd)" DUCKDB_PATH="/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb" \
  python3 -c "
import duckdb
con = duckdb.connect('/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb', read_only=True)
print(con.execute('''
    SELECT
        COUNT(*) AS total_sample_orders,
        COUNT(sample_received_at) AS with_received,
        ROUND(COUNT(sample_received_at) * 100.0 / COUNT(*), 2) AS coverage_pct
    FROM orders
    WHERE channel IN ('U先派样', '百补派样', '赠品&0.01渠道')
''').fetchone())
"
# 期望: coverage_pct > 80% (业务数据回填后)
```

**Phase 2 收口**: 业务数据 ≥ 80% 回填 + pytest 2 case 仍 PASS (Phase 1 兼容性) + 新增 1 case `test_sample_received_at_coverage > 80%`

---

## 2. Sprint 141.5 不做什么（防 scope creep）

### Phase 1 不做 (避免范围蔓延到 Sprint 142+):
- ❌ 不改 RFM 8 quadrant（`backend/semantic/segments.py`）
- ❌ 不动 `_compute_lock_metrics` 性能（留 Sprint 142）
- ❌ 不动前端 SamplingView.vue 任何字段
- ❌ 不改 LTV / cohort retention / cost / AARRR（留 Sprint 143-145+）
- ❌ 不动 Sprint 139 / 140 / 141 已稳定的 contract / service / e2e
- ❌ 不动 `COLUMN_MAPPING` (Phase 2 业务侧拍板后改)
- ❌ 不做 ETL 真跑批回填 (Phase 2 业务侧补数据源后)

### Phase 2 不做:
- ❌ 不动 Phase 1 已稳定的 schema / service / pytest
- ❌ 不重新设计 `sample_received_at` 字段语义 (Phase 1 schema 是 SSOT)
- ❌ 不重跑 Phase 1 ground-truth-lint 钩子 (Phase 1 已 PASS)

---

## 3. Sprint 141.5 验收清单

### Phase 1 验收 (Codex Stage 2 必跑, 1 周闭环)

```bash
# 1. pytest 2 case PASS
PYTHONPATH="$(pwd)" DUCKDB_PATH="/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb" \
  pytest backend/tests/test_etl_sample_received_at.py -v
# 期望: 2 passed

# 2. Sprint 139/140/141 ground-truth-lint 钩子 全 PASS
PYTHONPATH="$(pwd)" python3 backend/scripts/check_sampling_spu_type.py
PYTHONPATH="$(pwd)" python3 backend/scripts/check_window_unification.py
# 期望: PASS × 2

# 3. 全部 pytest baseline 持续 (740 → 742)
PYTHONPATH="$(pwd)" DUCKDB_PATH="..." pytest backend/tests/ -q
# 期望: 742 passed / 23 skipped / 0 failed

# 4. production DuckDB schema 验证 (Phase 1 加列已生效)
PYTHONPATH="$(pwd)" DUCKDB_PATH="..." python3 -c "
import duckdb
con = duckdb.connect('/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb', read_only=True)
print(con.execute(\"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'orders' AND column_name = 'sample_received_at'\").fetchone())
"
# 期望: ('sample_received_at', 'TIMESTAMP')

# 5. production DuckDB 业务数据验证 (Phase 1 预期全 NULL, Phase 2 回填后才非 NULL)
PYTHONPATH="$(pwd)" DUCKDB_PATH="..." python3 -c "
import duckdb
con = duckdb.connect('/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb', read_only=True)
print(con.execute(\"SELECT COUNT(*) AS total, COUNT(sample_received_at) AS non_null FROM orders WHERE channel IN ('U先派样', '百补派样', '赠品&0.01渠道')\").fetchone())
"
# 期望 Phase 1: (total=N, non_null=0) → Phase 2 后: (total=N, non_null=N*0.8)

# 6. pre-commit 全绿
git add -A
bash .githooks/pre-commit
# 期望: ruff + pytest + ground-truth-lint + L4.x 全绿
```

### Phase 2 验收 (业务侧补数据源后, 1 周闭环)

```bash
# 1. ETL 真跑批验证 sample_received_at 写入
PYTHONPATH="$(pwd)" /Users/yourname/homebrew/bin/python3 scripts/run_etl.py --update --sample-received-backfill
# 跑完验证 coverage > 80% (Section Task 2.2 业务真验脚本)

# 2. pytest 2 case 仍 PASS (Phase 1 兼容性)
PYTHONPATH="$(pwd)" DUCKDB_PATH="..." pytest backend/tests/test_etl_sample_received_at.py -v
# 期望: 3 passed (Phase 1 2 case + Phase 2 1 case coverage > 80%)

# 3. 全部 pytest baseline 持续 (742 → 743)
PYTHONPATH="$(pwd)" DUCKDB_PATH="..." pytest backend/tests/ -q
# 期望: 743 passed / 23 skipped / 0 failed

# 4. pre-commit 全绿
git add -A
bash .githooks/pre-commit
```

---

## 4. Sprint 141.5 风险评估（4 项已知风险）

| # | 风险 | 概率 | 缓解 |
|---|---|---|---|
| R1 | ~~业务侧 xlsx 无"收货时间"列~~ → **Q1 已验: CSV 无 receive_time, Phase 2 需业务侧补数据源** | 100% (已验) | Phase 1 仅 schema 准备 (0 业务数据); Phase 2 等业务侧拍板列名 + 数据源格式 |
| R2 | DuckDB 老版本不支持 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` | 低 | DuckDB 0.9+ 全版本支持; 若 CI runner 老版本, 走 `try/except` 手动迁移 |
| R3 | 老 CSV 文件无 `sample_received_at` 列, ingest 报 KeyError | 低 | Task 1.2 加 `if 'sample_received_at' in df.columns` 守卫, 缺列填 NaN |
| R4 | Phase 2 业务侧补数据源延迟, Sprint 143 (LTV/cohort retention 真验) 启动阻塞 | 中 | Sprint 142 (RFM 改造 + 性能重构) 不依赖 sample_received_at, 可并行开; Sprint 143 启动时间明确化: 等 Phase 2 数据回填 ≥ 80% 后再开 |

---

## 5. Sprint 141.5 L4.x 永久规则强制清单

| 规则 | 适用范围 | Sprint 141.5 检查点 |
|---|---|---|
| L4.1 SQL 三引号 + f-string | body 含 `{identifier}` 必须 f 前缀 | `sample_users_sql` + `period_sql` 加 f 前缀 (GIFT_SAMPLE_DB 复用) |
| L4.5 FilterBuilder + ? 参数化 | service 函数禁止 f-string 内嵌用户输入 | 复用既有 FilterBuilder; GIFT_SAMPLE_DB 是白名单常量, 0 风险 |
| L4.3 isolated_duckdb fixture | 真连必用 per-worker tmp DuckDB | pytest 2 case 全用 `monkeypatch_connection` |
| L4.4 真连 DuckDB skipif | `_PROD_DUCKDB_AVAILABLE` 守卫 | pytest 必加 `pytestmark` |
| L4.6 worktree DUCKDB_PATH | worktree 跑 pytest 必 export | Sprint 141.5 实施期间走 worktree 模式 |
| L4.16 push trigger paths | 改 scripts/etl + backend/services + backend/tests 触发 | ✅ paths 都包含 |
| L4.20 留尾 SSOT 治理 | Sprint 141.5 收口时强制检查 | close memory 必引真修 commit SHA |
| L4.22 vite rebuild | Sprint 141.5 是纯 ETL, **不触发** (前端无改动) | 跳过 |

---

# ═══════════════════════════════════════════════════════════════
# Sprint 142-145+ 高层路线图（Codex Stage 1 详细 plan 待 user 拍板后展开）
# ═══════════════════════════════════════════════════════════════

## 6. Sprint 142 — RFM 扩展 + level 联动 summary 卡 + 性能重构

**预估**: 2 周, 真 refactor + 1 真业务 (level 联动二级聚合)

### 6.1 Task 1: RFM 分层扩展（**不替换 8 quadrant**）

**当前** (`backend/semantic/segments.py`):
- `RFM_THRESHOLDS` 8 quadrant (R×F×M 经典分割, >=4 vs <4)
- `R_SEGMENT_ORDER` 7 个 R 区间 (近1月/2-3月/4-6月/7-12月/13-24月/2年外/已购客TTL)
- `F_SEGMENT_ORDER` 6 个 F 区间 (1次/2次/3次/4次/5次及以上/TTL)

**Sprint 142 改法 (跟 Sprint 139 + Sprint 140 模式 stable, 增量扩展不替换)**:

| 新增维度 | 字段 | 阈值 | 业务场景 |
|---|---|---|---|
| 生命周期 (Lifecycle) | `lifecycle_stage` | 新客/活跃客/沉睡客/流失客 | 沉睡客唤醒营销 |
| 价值层 (Value Tier) | `value_tier` | 高/中/低价值 (按 RFM 分数加权) | VIP 营销分层 |
| 潜力层 (Potential) | `potential_tier` | 高/中/低潜力 (按近期活跃度 + 历史 GSV 斜率) | 派样定向 |

**关键决策 (待 user 拍板)**:
- Q1: 扩展维度是加在 `RFM_THRESHOLDS` 同表, 还是新文件 `lifecycle.py` + `value.py` + `potential.py`?
  - 推荐 A (跟 RFM 模式 stable): 新建 `backend/semantic/lifecycle.py` + `value.py`, 复用 RFM_THRESHOLDS 但语义独立
- Q2: 老 8 quadrant 是否保留?
  - 推荐 A: 保留 (下游 audience 看板 + 营销活动都在用), 新维度**增量**加

### 6.2 Task 2: level 联动 summary 卡二级聚合

**当前问题**: `SamplingChannelSummary` 字段按 channel 聚合 (`sampling_service.py:107-118`), 跟 level 无关. user 切 `spu_category` 时, summary 卡不动.

**Sprint 142 改法**:
- contract 加二级聚合: `SamplingChannelSummary.channel × level` 交叉字段
- 例: `summary_by_level: Dict[str, SamplingLevelSummary]`
- 前端 SamplingView.vue 切 level 时 summary 卡重新渲染 (走 Vue Query 自动 refetch)

**关键决策 (待 user 拍板)**:
- Q3: 二级聚合是新增字段 (`summary_by_level`) 还是替换既有 `summary`?
  - 推荐 A: 新增, 老 `summary` 保留兼容 (Sprint 139+140 contract 瘦身模式)
- Q4: 5 levels (spu_category/spu_tier/spu_product_class/spu_product_subclass/spu_cosmetic) 都做二级聚合还是部分?
  - 推荐 A: 全部 5 levels (跟现有 cat_sql 对齐)

### 6.3 Task 3: `_compute_lock_metrics` 性能重构

**当前** (`sampling_service.py:374-?`, 估算 ~150 行):
```python
locked = conn.execute("SELECT COUNT(*), COUNT(DISTINCT ...) FROM orders WHERE ...", [GIFT_SAMPLE_DB, lock_start, lock_end]).fetchone()
uv = conn.execute("SELECT ... FROM daily_visitors WHERE ...", [...]).fetchone()
converted = conn.execute("SELECT ... FROM orders JOIN locked_users ...", [...]).fetchone()
# ... 重复 ~6-8 次单字段查询
```

**Sprint 142 改法 (跟 Sprint 30.1 W4 540 combo batch INSERT 模式 stable)**:
```python
def _compute_lock_metrics(conn, campaign_row):
    year, name, conv_start, conv_end, lock_start, lock_end = campaign_row
    if not lock_start or not lock_end:
        return _empty_lock_data()
    # Sprint 142: 单 SQL 合并 6-8 次单字段查询
    sql = """
    WITH locked AS (
        SELECT DISTINCT user_id FROM orders
        WHERE channel = ? AND ROUND(actual_amount, 2) = 0.01
          AND pay_time >= ?::DATE AND pay_time <= ?::DATE + INTERVAL '1' DAY
    ),
    uv AS (SELECT COALESCE(SUM(visitors), 0) AS total_uv FROM daily_visitors
           WHERE date >= ?::DATE AND date <= ?::DATE),
    conv AS (
        SELECT COUNT(DISTINCT o.user_id) AS converted_users, COALESCE(SUM(o.actual_amount), 0) AS lock_gsv
        FROM orders o JOIN locked lu ON o.user_id = lu.user_id
        WHERE o.channel != ?  -- 转化期非锁权单
          AND o.pay_time >= ?::DATE AND o.pay_time <= ?::DATE + INTERVAL '1' DAY
    )
    SELECT
        (SELECT COUNT(*) FROM locked) AS locked_orders,
        (SELECT COUNT(DISTINCT user_id) FROM locked) AS locked_users,
        (SELECT total_uv FROM uv) AS total_uv,
        (SELECT converted_users FROM conv) AS converted_users,
        (SELECT lock_gsv FROM conv) AS lock_gsv
    """
    row = conn.execute(sql, [GIFT_SAMPLE_DB, lock_start_str, lock_end_str,
                              conv_start_str, conv_end_str,
                              GIFT_SAMPLE_DB, conv_start_str, conv_end_str]).fetchone()
    # ... 装回 Dict
```

**预期效果**:
- 当前 ~6-8 次 `conn.execute` 全表扫 orders → 1 次
- 大促周期 1-2 个, 性能优化主要体现在每次锁权分析少 5-7 次 RTT
- **预估加速**: 3-5× (跟 Sprint 30.1 W4 50.4× 比小, 因为查询复杂度高)

**关键决策 (待 user 拍板)**:
- Q5: 性能重构是否要加 micro-benchmark (跟 Sprint 30.5 W4 端到端真验模式)?
  - 推荐 A: 加 (`data/processed/etl_perf/benchmarks/sprint142_lock_metrics.json`), 验证加速 ≥ 2×

### 6.4 Sprint 142 收口预期

- pytest baseline 742/23/0 → 750/23/0 (+8 case)
- L4.x 22 stable 0 新增
- VERSION 0.4.14.157 不 bump
- 实质净 +150/-100 行

---

## 7. Sprint 143 — LTV + cohort retention matrix + 改名 ROI

**预估**: 2 周, 1 真业务 (ROI 改名) + 1 全新建 (LTV) + 1 全新建 (cohort matrix)

### 7.1 Task 1: LTV 90/180/365d 计算

**当前**: 0 引用, 全新建

**Sprint 143 改法**:
- 新建 `backend/services/lifetime_value_service.py`
- LTV 定义: 用户在派样/正装后 90/180/365 天累计 GSV
- 数据源: `orders` + `sample_received_at` (Sprint 141.5)
- 复用 RFM_THRESHOLDS (`backend/semantic/segments.py`)
- 预计算: W4 cache (跟 Sprint 30.1 batch INSERT 模式 stable)

**contract**:
```python
class LifetimeValueSummary(BaseModel):
    """用户生命周期价值 (LTV) 90/180/365d"""
    cohort_date: str = Field(..., description="派样 cohort 日期 (YYYY-MM-DD)")
    user_count: int
    ltv_90d: RatioField  # 90 天累计 GSV / 用户数
    ltv_180d: RatioField
    ltv_365d: RatioField
    ltv_90d_yoy_pct: PercentageField
    ltv_180d_yoy_pct: PercentageField
    ltv_365d_yoy_pct: PercentageField
```

**关键决策 (待 user 拍板)**:
- Q6: LTV 阈值分档? (e.g. 高 LTV ≥ 1000 / 中 300-1000 / 低 < 300)
- Q7: LTV 是否按 channel 切 (U先/百补/全店)?

### 7.2 Task 2: cohort retention matrix

**当前**: 0 引用, 全新建

**Sprint 143 改法**:
- 新建 `backend/services/cohort_retention_service.py`
- 定义: cohort = 同月派样用户, retention = 第 N 月回购比例
- 复用 W4 cache
- 前端: 新建 `CohortRetentionMatrix.vue` (跟 RFMView.vue Sprint 36-1 删除模式相反, **这是新建**)

**关键决策 (待 user 拍板)**:
- Q8: cohort 颗粒度 (按月/按周)?
  - 推荐 A: 按月 (跟 RFM R_SEGMENT_ORDER 模式 stable)
- Q9: retention 维度 (回购人数/回购 GSV/正装 GSV)?
  - 推荐 A: 3 维度都做 (跟 period_distribution 5 桶模式 stable)

### 7.3 Task 3: 改名 ROI → 正装转化分析

**当前** (`frontend-vue3/src/views/SamplingView.vue:387`):
```vue
<PageHeader title="派样看板" subtitle="U先/百补派样ROI / 0.01锁权转化分析" />
```

**Sprint 143 改法**:
- subtitle: `"U先/百补派样正装转化分析 / 0.01锁权转化分析"` (改文案)
- API contract 字段保留 `sampling_roi` 命名 (避免 breaking change)
- 内部文档 (CHANGELOG + Sprint 143 close memory) 标"前端 UI 命名跟后端 API 命名分离"

**关键决策 (待 user 拍板)**:
- Q10: 改名范围
  - (A) 仅前端文案（推荐, 0 breaking change）
  - (B) 前端 + API contract 都改 `sampling_roi → sampling_conversion` (1 sprint 多范围大改, 需要 deprecation 周期)
- Q11: 是否同步改 sidebar 菜单项（"派样 ROI" → "派样转化"）?

### 7.4 Sprint 143 收口预期

- pytest baseline 750/23/0 → 760/23/0 (+10 case)
- L4.x 22 stable 0 新增
- VERSION 0.4.14.157 不 bump
- 实质净 +250/-30 行 (新 service + 新前端组件)

---

## 8. Sprint 144+ — 📋 暂收口 (cost/margin + 财务对接 + holdout 实验框架)

**预估**: 3-4 周, 全新建, 依赖 Sprint 143 改名 + LTV 数据

> **📋 暂收口 (2026-06-28)**: user 拍板"不需要做, 没意义" — 业务侧当前不需要成本数据 / 财务对接 / holdout 实验框架. 跟 Sprint 89 + Sprint 134 暂收口模式 stable. 等下次真业务触发再开.
> 本 Section 内容保留 (user 改主意可恢复), 但标暂收口, 不消耗 sprint 收口资源.

### 8.1 Task 1: cost/margin 表

**当前**: 0 引用, 全新建

**Sprint 144+ 改法**:
- 新建 `scripts/etl/load_cost.py` (跟 load.py 模式 stable)
- 新 ETL 数据源: 财务系统导出 (Excel/CSV), 通过 ad-hoc-query CLI (Sprint 62) 摄入
- DuckDB schema:
  ```sql
  CREATE TABLE cost (
      date DATE,
      product_id VARCHAR,
      sku_id VARCHAR,
      cost_amount DECIMAL(12,2),  -- 单件成本
      margin_rate DECIMAL(5,4),   -- 毛利率 (0-1)
      source VARCHAR  -- '财务系统' / '估算'
  )
  ```

**关键决策 (待 user 拍板 — 必须先拍板才能开 sprint)**:
- **Q12**: 财务系统对接方式
  - (A) 飞书多维表格（推荐, 跟 lark-base skill 集成）
  - (B) 钉钉/企业微信
  - (C) Excel 邮件/共享盘
- **Q13**: 成本数据颗粒度（SKU 级 / SPU 级 / 类目级）
  - 推荐 A: SKU 级 + SPU 级兜底（无 SKU 成本时按 SPU 平均估算）
- **Q14**: 历史数据回溯范围（最近 90 天 / 1 年 / 全量）

### 8.2 Task 2: 财务对接自动化

**Sprint 144+ 改法**:
- 用 lark-base skill 或 ad-hoc-query CLI 拉财务数据
- 写入 cost 表
- 触发跟主 ETL 一样的 manifest 失效 + DuckDB-KV cache 24h TTL (Sprint 30+ W5)

### 8.3 Task 3: holdout 实验框架

**当前**: 0 引用, 全新建

**Sprint 144+ 改法**:
- 新建 `backend/services/experiment_service.py`
- 概念: 营销活动预留 10% 用户为 holdout (不参与), 比较 holdout vs treatment 的 GSV 增量
- 数据源: 营销活动名单 + holdout 名单 (人工维护或飞书多维表格)
- 复用 RFM_THRESHOLDS (按 RFM 分层比较)

**关键决策 (待 user 拍板)**:
- **Q15**: holdout 比例（默认 10% / 5% / 20%）
- **Q16**: 统计显著性检验（t-test / 贝叶斯 / 仅 descriptive）
- **Q17**: 实验周期（默认 14 天 / 30 天 / 自定义）

### 8.4 Sprint 144+ 收口预期

- pytest baseline 760/23/0 → 780/23/0 (+20 case)
- L4.x 22 stable 0 新增
- VERSION 0.4.14.157 → 0.4.15.0 bump (新增模块)
- 实质净 +400/-50 行

---

## 9. Sprint 145+ — 📋 暂收口 (AARRR funnel + 行业基线 + AB test 框架)

**预估**: 3-4 周, 全新建, 依赖 Sprint 144+ cost + holdout

> **📋 暂收口 (2026-06-28)**: user 拍板"不需要做, 没意义" — 业务侧当前不需要 AARRR funnel / 行业基线 / AB test 框架. 跟 Sprint 89 + Sprint 134 暂收口模式 stable. 等下次真业务触发再开.
> 本 Section 内容保留 (user 改主意可恢复), 但标暂收口, 不消耗 sprint 收口资源.

### 9.1 Task 1: AARRR funnel 指标

**当前**: 0 引用, 全新建

**Sprint 145+ 改法**:
- AARRR = Acquisition / Activation / Retention / Revenue / Referral
- 复用 cohort retention matrix (Sprint 143) + LTV (Sprint 143) + cost (Sprint 144+)
- 新建 `backend/services/aarrr_service.py`

**关键决策 (待 user 拍板)**:
- **Q18**: AARRR 5 个指标的具体定义
  - Acquisition: 派样期拉新人数 (按 sample_received_at)
  - Activation: 首单转化率 (派样 → 7 天内正装)
  - Retention: 30/90/180 天回购率 (复用 cohort retention)
  - Revenue: LTV 90/180/365d (复用 Sprint 143)
  - Referral: 邀请人数 (当前数据源是否支持? 待业务确认)

### 9.2 Task 2: 行业基线对比

**当前**: 0 引用, 全新建

**Sprint 145+ 改法**:
- 行业基线数据源 (公开报告 / 付费 API / 自采)
- 新建 `backend/services/benchmark_service.py`

**关键决策 (待 user 拍板)**:
- **Q19**: 行业基线数据源
  - (A) 公开报告（QuestMobile / 艾瑞 / 易观）— 数据滞后 1-3 月, 0 成本
  - (B) 付费 API（GrowingIO / 神策）— 实时, 高成本
  - (C) 自采（公司运营部调研）— 灵活, 人工成本
  - 推荐 A (跟当前项目 0 外部依赖模式 stable)
- **Q20**: 基线对比维度（按类目 / 按渠道 / 按用户层）

### 9.3 Task 3: AB test 框架

**当前**: 0 引用, 全新建

**Sprint 145+ 改法**:
- 新建 `backend/services/ab_test_service.py`
- 跟 holdout (Sprint 144+) 区别:
  - holdout: 单臂, 留 10% 不参与
  - AB test: 多臂, 2-3 组随机分流
- 复用 holdout 框架 + 加分流 + 显著性检验

**关键决策 (待 user 拍板)**:
- **Q21**: 分流方式（hash(user_id) % 100 / 飞书多维表格配置 / 随机）
- **Q22**: 显著性检验（频繁派 / t-test / Bayesian）

### 9.4 Sprint 145+ 收口预期

- pytest baseline 780/23/0 → 800/23/0 (+20 case)
- L4.x 22 stable 0 新增
- VERSION 0.4.15.0 不变 (仍是新模块, 不 bump)
- 实质净 +500/-50 行

---

## 10. 跨 sprint 总览（统计 + 时间线）

| Sprint | 周数 | 实质净 LOC | pytest delta | L4.x 新增 | VERSION | 模式 |
|---|---|---|---|---|---|---|
| **141.5 Phase 1** | **1 (立即开)** | **+25/-5** | **740→742 (+2)** | **0** | **0.4.14.157 不 bump** | **纯 ETL schema 准备, 0 业务数据** |
| 141.5 Phase 2 | 1 (业务侧补数据源后) | +5/-0 | 742→743 (+1) | 0 | 0.4.14.157 不 bump | 纯 ETL 真回填 + 业务真验 |
| 142 | 2 | +150/-100 | 743→751 (+8) | 0 | 0.4.14.157 不 bump | 真 refactor + 1 真业务 |
| 143 | 2 | +250/-30 | 751→761 (+10) | 0 | 0.4.14.157 不 bump | 1 真业务 + 2 全新建 (等 Phase 2 数据) |
| 144+ | — | — | — | — | — | 📋 **暂收口** (user 2026-06-28 拍板 "不需要做, 没意义") |
| 145+ | — | — | — | — | — | 📋 **暂收口** (跟 Sprint 89 / Sprint 134 模式 stable) |
| **累计** | **5-6 周** | **+430/-135** | **+21 case** | **0** | **0.4.14.157 不 bump** | **混合模式** |

**风险点**:
- Sprint 141.5 Phase 2 业务侧补数据源延迟 → Sprint 143 (LTV 真验) 启动阻塞. 缓解: Sprint 142 可并行开 (RFM 改造 + 性能重构不依赖 sample_received_at 真数据)
- Sprint 144+/145+ 暂收口, 等下次真业务触发再开 (跟 Sprint 89 + Sprint 134 模式 stable)

---

## 11. Codex Stage 2 实施规范

**Codex 必读** (按 sprint 顺序):
1. Sprint 141.5 Phase 1 详细 plan (Section 1 Task 1.1-1.4, 不含 Task 2.1/2.2)
2. `AGENTS.md` (本地文件, .gitignore 排除, 自动注入)
3. 必跑 `git log --all --oneline | head -10` + `git log main --oneline -- scripts/etl/` 验 Sprint 139+140+141 收口状态
4. ⚠️ Phase 1 实施前必读 Q1 已验结论: 源数据是 CSV 不是 xlsx, 现有 30 字段无 receive_time, Phase 1 不涉及 COLUMN_MAPPING 改动

**Codex 不做**:
- ❌ 不 git commit / push (Claude Stage 4 负责)
- ❌ 不动 Sprint 139 / 140 / 141 已稳定的 contract / service / e2e
- ❌ 不改 Sprint 141.5 Phase 1 scope 之外的 docs
- ❌ 不动 RFM_THRESHOLDS / SamplingChannelSummary 既有字段
- ❌ 不动 `COLUMN_MAPPING` (Phase 2 业务侧拍板后改, Phase 1 不改)
- ❌ 不做 ETL 真跑批回填 (Phase 2 业务侧补数据源后)

**Codex 实施 Sprint 141.5 Phase 1 完成时给 user 回报**:
- ✅ pytest 2 case PASS (`test_orders_has_sample_received_at_column` + `test_sampling_service_falls_back_to_pay_time`)
- ✅ Sprint 139/140/141 ground-truth-lint 钩子 全 PASS
- ✅ production DuckDB schema 验证 (`sample_received_at` 列存在, TIMESTAMP 类型)
- ✅ production DuckDB 数据验证 (`non_null = 0`, Phase 1 预期)
- ✅ pre-commit 全绿
- ✅ git diff --stat 改动列表 (实质净 +25/-5)

---

## 12. 跨 sprint open questions 总表（必 user 拍板）

### 已验 (2026-06-28 Claude Stage 1)

| # | Sprint | 决策点 | 实测结果 |
|---|---|---|---|
| ~~Q1~~ | 141.5 | xlsx 源数据是否含"收货时间"列 | ✅ 已验: 源数据是 CSV 不是 xlsx, `data/raw/channel_details/` 按 channel 切分; `COLUMN_MAPPING` 30 字段无 `receive_time`; 真 sample channel = `赠品&0.01渠道` (`backend/semantic/channels.py:133`); Sprint 141.5 拆 Phase 1 (schema 准备, 1 周可立即开) + Phase 2 (业务侧补数据源后, 1 周) |
| ~~Q12~~ | 144+ | 财务系统对接方式 | 📋 **暂收口** (user 2026-06-28 拍板 "不需要做, 没意义") |
| ~~Q19~~ | 145+ | 行业基线数据源 | 📋 **暂收口** (跟 Sprint 89 + Sprint 134 模式 stable) |

### 待 user 拍板

| # | Sprint | 决策点 | 推荐选项 | 阻塞 |
|---|---|---|---|---|
| **Q2** | **141.5 Phase 2** | **业务侧补 ETL 数据源方式** (飞书多维表格 / 客服系统 API / 手工 CSV) | **(A) 飞书多维表格** (跟 lark-base skill 集成) | ✅ **强阻塞 Sprint 141.5 Phase 2 启动** |
| Q2a | 141.5 Phase 2 | 业务侧列名 (收货时间 / 收样时间 / receive_time) | 业务侧定 | ✅ 阻塞 Phase 2 Task 2.1 |
| Q2b | 141.5 Phase 2 | 历史数据回溯范围 | (A) 全部历史 | ❌ 推荐默认 |
| Q3 | 142 | 二级聚合新增字段 vs 替换 | (A) 新增 `summary_by_level` | ❌ 推荐默认 |
| Q5 | 142 | 性能重构加 micro-benchmark | (A) 加 | ❌ 推荐默认 |
| Q6 | 143 | LTV 阈值分档 | 业务侧定 | ✅ 阻塞 Sprint 143 启动 |
| Q8 | 143 | cohort 颗粒度 | (A) 按月 | ❌ 推荐默认 |
| Q10 | 143 | 改名 ROI 范围 | (A) 仅前端文案 | ❌ 推荐默认 |

**1 个强阻塞 (Q2) 必须先 user 拍板才能开 Sprint 141.5 Phase 2**.

**Phase 1 不需要任何 user 拍板, Codex 可立即开工**.

---

## 13. 完成定义（Definition of Done, 按 sprint 分别）

### Sprint 141.5 Phase 1 DoD:
- [ ] Task 1.1-1.4 全部完成 (orders schema + ingest 透传 + service 回退 + pytest + CHANGELOG)
- [ ] pytest 2 case PASS (`test_orders_has_sample_received_at_column` + `test_sampling_service_falls_back_to_pay_time`)
- [ ] production DuckDB schema 验证: `sample_received_at` 列存在 (TIMESTAMP)
- [ ] production DuckDB 数据验证: `non_null = 0` (Phase 1 预期, Phase 2 才非 NULL)
- [ ] pre-commit ruff + pytest + ground-truth-lint 全绿
- [ ] L4.x 22 stable 0 新增
- [ ] VERSION 0.4.14.157 不 bump
- [ ] CHANGELOG.md +1 entry (Phase 1)

### Sprint 141.5 Phase 2 DoD (业务侧补数据源后):
- [ ] Task 2.1-2.2 全部完成 (COLUMN_MAPPING 加映射 + ETL 真跑批回填)
- [ ] pytest 3 case PASS (Phase 1 2 case + Phase 2 1 case coverage > 80%)
- [ ] production DuckDB 数据验证: `coverage_pct > 80%` (业务数据回填后)
- [ ] pre-commit ruff + pytest + ground-truth-lint 全绿
- [ ] L4.x 22 stable 0 新增
- [ ] VERSION 0.4.14.157 不 bump
- [ ] CHANGELOG.md +1 entry (Phase 2)

### Sprint 142 DoD:
- [ ] Task 1-3 全部完成 (RFM 扩展 + level 二级聚合 + 性能重构)
- [ ] pytest 8 case PASS (新增)
- [ ] micro-benchmark 加 `data/processed/etl_perf/benchmarks/sprint142_lock_metrics.json`
- [ ] 性能加速 ≥ 2× 验证 (Q5 拍板后)
- [ ] L4.x 22 stable 0 新增
- [ ] VERSION 0.4.14.157 不 bump

### Sprint 143-145+ DoD: 详见 Sprint 142-145+ Section (待 Stage 1 详细 plan)

---

## 14. 文件改动清单（精确到 Sprint 141.5 LOC, 拆 Phase 1 + Phase 2）

### Phase 1 (Codex 立即可开, 1 周)

| 文件 | 改法 | LOC |
|---|---|---|
| `scripts/etl/load.py:45-87` | `orders` schema 加 1 列 `sample_received_at TIMESTAMP` | +1/-0 |
| 同上 `:208` (orders_new) | 同步加列 | +1/-0 |
| 同上 `:184` (ensure_database_schema) | idempotent ALTER | +4/-0 |
| 同上 `:264-265` (index 区) | 加 `idx_orders_sample_received` | +1/-0 |
| `scripts/etl/ingest.py:308 附近` | 增量模式 `pd.to_datetime(errors='coerce')` 透传 | +3/-0 |
| `backend/services/sampling_service.py:83-107` | `sample_users_sql` 加 `COALESCE` 字段 | +2/-0 |
| 同上 `:231 period_sql` | `days_between` 改用 `first_sample_received_at` | +1/-1 |
| `backend/tests/test_etl_sample_received_at.py` (NEW) | 2 case regression | +30 |
| `CHANGELOG.md` | Sprint 141.5 Phase 1 entry | +22 |

**Phase 1 合计**: 实质净 +25/-5 (实质有效 +65 行, 跟 Sprint 140 / Sprint 137 留尾治本 sprint 模式 stable)

### Phase 2 (业务侧补数据源后, 1 周)

| 文件 | 改法 | LOC |
|---|---|---|
| `scripts/etl/config.py:23-?` | `COLUMN_MAPPING` 加 业务侧拍板的列名映射 | +3/-0 |
| `backend/tests/test_etl_sample_received_at.py` | 加 1 case `test_sample_received_at_coverage > 80%` | +15 |
| `CHANGELOG.md` | Sprint 141.5 Phase 2 entry | +22 |

**Phase 2 合计**: 实质净 +5/-0 (实质有效 +40 行, 跟 Phase 1 模式 stable)

### Sprint 141.5 累计 (Phase 1 + Phase 2)

**合计**: 实质净 +30/-5 (实质有效 +105 行, 跟 Sprint 140 / Sprint 137 留尾治本 sprint 模式 stable)

---

**未达任一项 = Codex 未完成, 回到 Stage 2 修补。**

**Sprint 141.5 Stage 1 详细 plan 已锁定, Codex 可立即开工. Sprint 142-145+ 路线图已锁定, Stage 1 详细 plan 待对应 sprint 启动时展开.**