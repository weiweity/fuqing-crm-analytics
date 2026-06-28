# HANDOFF-TO-CODEX — Sprint 142 (RFM 扩展 + level 联动二级聚合 + _compute_lock_metrics 性能重构)

> **状态**: 📋 立项待 Codex 实施 (2026-06-28)
> **触发**: Sprint 141.5 Phase 1 收口 — user 拍板"并行开 Sprint 142 和 143"
> **范围**: 1 真 refactor + 1 真业务, 8 文件, **实质净 +150/-100 行**
> **模式**: 跟 Sprint 116+117+141 留尾治本 sprint 模式 stable (Codex Stage 2 + Claude Stage 3 review)
> **跟 Sprint 143 并行**: Sprint 143 改 `SamplingView.vue` ROI 命名 + 新增 cohort retention; Sprint 142 改 `SamplingView.vue` level 联动 UI. **关键约定**: Sprint 142 只动 ROI tab 的 level 联动 (L415-450), Sprint 143 只动 ROI tab subtitle (L387) + 新增 CohortRetentionMatrix.vue (新组件). 0 冲突区.
> **预期影响**: pytest baseline 742/23/0 → 750/23/0 (+8 case), L4.x 22 stable 0 新增, VERSION 0.4.14.157 不 bump

---

## 0. 背景

### 0.1 user 原话 (Sprint 141.5 Phase 1 收口后拍板)

> "并行开sprint142和143，给两个handoff，我让codex,并行开发"

### 0.2 Sprint 142 三件事 (基于 codegraph 实读 main @ `b180568`)

| # | 范围 | 现状 (基于 main @ `b180568`) | 改造方向 |
|---|---|---|---|
| Task 1 | RFM 扩展 (生命周期/价值层/潜力层) | `backend/semantic/segments.py` RFM_THRESHOLDS 8 quadrant 经典分割 | **不替换 8 quadrant**, 增量加 lifecycle_stage + value_tier + potential_tier 3 个新维度 |
| Task 2 | level 联动 summary 卡二级聚合 | `SamplingChannelSummary` 字段按 channel 聚合, `cat_sql` 已按 level 聚合 | 新增 `summary_by_level: Dict[str, SamplingLevelSummary]`, summary 卡按 level 重渲染 |
| Task 3 | `_compute_lock_metrics` 性能重构 | `sampling_service.py:374-450` 多次 `conn.execute` 单字段查询 (4-5 次全表扫 orders) | 单 SQL 合并 (CTE 一次扫表, 多指标聚合) |

### 0.3 跟 Sprint 143 并行约定 (避免 SamplingView.vue 冲突)

| 文件区 | Sprint 142 改 | Sprint 143 改 |
|---|---|---|
| `SamplingView.vue` L387 (PageHeader subtitle) | ❌ 不动 | ✅ 改文案 |
| `SamplingView.vue` L400-460 (level 联动 UI + summary 卡) | ✅ 改 | ❌ 不动 |
| `SamplingView.vue` 新增 tab | ❌ 不动 | ✅ CohortRetentionMatrix.vue |
| `backend/services/sampling_service.py` `_compute_lock_metrics` | ✅ 重构 | ❌ 不动 |
| `backend/services/sampling_service.py` `cat_sql` | ✅ 加 level 二级聚合 | ❌ 不动 |
| 新文件 `backend/services/lifetime_value_service.py` | ❌ 不动 | ✅ 新建 |
| 新文件 `backend/services/cohort_retention_service.py` | ❌ 不动 | ✅ 新建 |
| `backend/contracts/sampling.py` `SamplingChannelSummary` | ✅ 加 `summary_by_level` | ❌ 不动 |
| `backend/contracts/sampling.py` `SamplingLevelSummary` (NEW) | ✅ 新建 | ❌ 不动 |

---

## 1. 范围 (3 个 Task, 按顺序施工)

### Task 1: RFM 分层扩展 (3 个新维度, 不替换 8 quadrant)

**前置**: Sprint 89/134 模式 — 增量扩展, 0 breaking change.

**1.1 contract 新增 3 个 Pydantic enum** (`backend/contracts/rfm_segments.py` NEW, 跟 `sampling.py` 模式 stable):

```python
"""Sprint 142 RFM 扩展维度 (生命周期/价值层/潜力层) — 不替换 8 quadrant, 增量加"""

from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional


class LifecycleStage(str, Enum):
    """用户生命周期阶段 (基于首次活跃 vs 最近活跃 时间差)"""
    NEW = "新客"          # first_active < 30 天
    ACTIVE = "活跃客"      # last_active < 30 天 + 历史 > 30 天
    DORMANT = "沉睡客"     # 30-180 天无活跃
    CHURNED = "流失客"     # > 180 天无活跃


class ValueTier(str, Enum):
    """用户价值层 (基于历史 GSV + 购买频次加权)"""
    HIGH = "高价值"        # GSV >= 5000 OR frequency >= 10
    MEDIUM = "中价值"      # GSV 1000-5000
    LOW = "低价值"         # GSV < 1000


class PotentialTier(str, Enum):
    """用户潜力层 (基于近期活跃度 + GSV 斜率)"""
    HIGH = "高潜力"        # 近 30 天活跃 + GSV 斜率 > 0
    MEDIUM = "中潜力"      # 近 30 天活跃 + GSV 斜率 = 0
    LOW = "低潜力"         # 近 30 天不活跃 + GSV 斜率 < 0


class RFMSegmentExtended(BaseModel):
    """RFM 扩展分群 (Sprint 142 新增, 跟 8 quadrant 共存)"""
    user_id: str = Field(..., description="用户 ID")
    # 既有 8 quadrant
    rfm_quadrant: str = Field(..., description="8 quadrant 经典分割 (保留)")
    # Sprint 142 新增 3 维度
    lifecycle_stage: LifecycleStage = Field(..., description="生命周期阶段")
    value_tier: ValueTier = Field(..., description="价值层")
    potential_tier: PotentialTier = Field(..., description="潜力层")
```

**1.2 semantic 层新增 SQL 生成** (`backend/semantic/segments.py` 加 3 个函数):

```python
# 跟 RFM_THRESHOLDS 模式 stable, 阈值从单点常量改成模块级常量, 业务侧可调

LIFECYCLE_THRESHOLDS = {
    "new_max_days": 30,       # NEW: 首次活跃 < 30 天
    "active_max_days": 30,    # ACTIVE: 最近活跃 < 30 天
    "dormant_max_days": 180,  # DORMANT: 30-180 天无活跃
    # > 180 = CHURNED
}

VALUE_THRESHOLDS = {
    "high_gsv": 5000,
    "high_frequency": 10,
    "medium_gsv": 1000,
}

POTENTIAL_THRESHOLDS = {
    "active_recent_days": 30,  # 近 30 天活跃
    "gsv_growth_threshold": 0.0,  # GSV 斜率阈值 (> 0 = HIGH, = 0 = MEDIUM, < 0 = LOW)
}


def lifecycle_case_sql() -> str:
    """生成 lifecycle_stage CASE WHEN SQL 片段"""
    return f"""
        CASE
            WHEN DATEDIFF('day', first_active, CURRENT_DATE) < {LIFECYCLE_THRESHOLDS['new_max_days']}
                THEN '新客'
            WHEN DATEDIFF('day', last_active, CURRENT_DATE) < {LIFECYCLE_THRESHOLDS['active_max_days']}
                AND DATEDIFF('day', first_active, CURRENT_DATE) >= {LIFECYCLE_THRESHOLDS['new_max_days']}
                THEN '活跃客'
            WHEN DATEDIFF('day', last_active, CURRENT_DATE) BETWEEN {LIFECYCLE_THRESHOLDS['active_max_days']} AND {LIFECYCLE_THRESHOLDS['dormant_max_days']}
                THEN '沉睡客'
            ELSE '流失客'
        END
    """


def value_tier_case_sql() -> str:
    """生成 value_tier CASE WHEN SQL 片段"""
    return f"""
        CASE
            WHEN COALESCE(gsv_sum, 0) >= {VALUE_THRESHOLDS['high_gsv']} OR COALESCE(order_count, 0) >= {VALUE_THRESHOLDS['high_frequency']}
                THEN '高价值'
            WHEN COALESCE(gsv_sum, 0) >= {VALUE_THRESHOLDS['medium_gsv']}
                THEN '中价值'
            ELSE '低价值'
        END
    """


def potential_tier_case_sql() -> str:
    """生成 potential_tier CASE WHEN SQL 片段"""
    return f"""
        CASE
            WHEN DATEDIFF('day', last_active, CURRENT_DATE) < {POTENTIAL_THRESHOLDS['active_recent_days']}
                AND gsv_growth > {POTENTIAL_THRESHOLDS['gsv_growth_threshold']}
                THEN '高潜力'
            WHEN DATEDIFF('day', last_active, CURRENT_DATE) < {POTENTIAL_THRESHOLDS['active_recent_days']}
                THEN '中潜力'
            ELSE '低潜力'
        END
    """
```

**1.3 service 新增 `get_user_rfm_extended()`** (`backend/services/rfm_service.py` NEW 或加到 `backend/services/rfm/`):

```python
"""Sprint 142 RFM 扩展分群 service (生命周期/价值层/潜力层)"""

from backend.semantic.segments import (
    lifecycle_case_sql, value_tier_case_sql, potential_tier_case_sql,
    RFM_THRESHOLDS,
)


def get_user_rfm_extended(
    conn,
    user_ids: List[str],
    as_of_date: str = None,
) -> Dict[str, RFMSegmentExtended]:
    """计算用户 RFM 扩展分群 (8 quadrant + 3 新维度).

    Args:
        conn: DuckDB 连接
        user_ids: 用户 ID 列表
        as_of_date: 分析日期 (YYYY-MM-DD), 默认 CURRENT_DATE

    Returns:
        Dict[user_id, RFMSegmentExtended]
    """
    if not user_ids:
        return {}

    placeholders = ','.join(['?'] * len(user_ids))

    # CTE: 计算每个用户的 first_active / last_active / gsv_sum / order_count / gsv_growth
    # 然后用 3 个 CASE WHEN 计算新维度
    sql = f"""
        WITH user_orders AS (
            SELECT
                o.user_id,
                MIN(o.pay_time) as first_active,
                MAX(o.pay_time) as last_active,
                SUM(CASE WHEN o.is_refund = FALSE THEN o.actual_amount ELSE 0 END) as gsv_sum,
                COUNT(DISTINCT o.order_id) as order_count,
                SUM(CASE WHEN o.pay_time >= CURRENT_DATE - INTERVAL '30' DAY THEN o.actual_amount ELSE 0 END)
                    - SUM(CASE WHEN o.pay_time BETWEEN CURRENT_DATE - INTERVAL '60' DAY AND CURRENT_DATE - INTERVAL '30' DAY
                            THEN o.actual_amount ELSE 0 END) as gsv_growth
            FROM orders o
            WHERE o.user_id IN ({placeholders})
              AND o.channel != '购物金'
              AND o.is_refund = FALSE
              AND o.order_status != '交易关闭'
            GROUP BY o.user_id
        ),
        rfm_score AS (
            SELECT
                user_id,
                first_active,
                last_active,
                gsv_sum,
                order_count,
                gsv_growth,
                {lifecycle_case_sql()} as lifecycle_stage,
                {value_tier_case_sql()} as value_tier,
                {potential_tier_case_sql()} as potential_tier,
                -- 既有 8 quadrant (Sprint 60+ RFM 8 quadrant 经典分割)
                CASE
                    WHEN gsv_sum >= {RFM_THRESHOLDS['m'][3]} AND order_count >= {RFM_THRESHOLDS['f'][3]}
                        THEN '重要价值客户'
                    WHEN gsv_sum >= {RFM_THRESHOLDS['m'][3]}
                        THEN '重要唤回客户'
                    -- ... (8 quadrant 全套)
                END as rfm_quadrant
            FROM user_orders
        )
        SELECT user_id, rfm_quadrant, lifecycle_stage, value_tier, potential_tier
        FROM rfm_score
    """

    rows = conn.execute(sql, user_ids).fetchall()
    return {
        row[0]: RFMSegmentExtended(
            user_id=row[0],
            rfm_quadrant=row[1],
            lifecycle_stage=row[2],
            value_tier=row[3],
            potential_tier=row[4],
        )
        for row in rows
    }
```

**1.4 前端接口** (`frontend-vue3/src/api/rfm.ts` NEW):

```typescript
export type LifecycleStage = '新客' | '活跃客' | '沉睡客' | '流失客'
export type ValueTier = '高价值' | '中价值' | '低价值'
export type PotentialTier = '高潜力' | '中潜力' | '低潜力'

export interface RFMSegmentExtended {
  user_id: string
  rfm_quadrant: string
  lifecycle_stage: LifecycleStage
  value_tier: ValueTier
  potential_tier: PotentialTier
}

export function fetchUserRFMExtended(params: {
  user_ids: string[]
  as_of_date?: string
}): Promise<{ segments: RFMSegmentExtended[] }> {
  return client.post('/v1/rfm/extended', params)
}
```

**1.5 router 端点** (`backend/routers/rfm.py` NEW 或加到 `backend/routers/audience.py`):

```python
@router.post("/v1/rfm/extended", response_model=RFMExtendedResponse)
def get_rfm_extended(req: RFMExtendedRequest):
    """Sprint 142: RFM 扩展分群 (生命周期/价值层/潜力层)"""
    segments = get_user_rfm_extended(
        get_connection(),
        user_ids=req.user_ids,
        as_of_date=req.as_of_date,
    )
    return {"segments": list(segments.values())}
```

**1.6 pytest** (`backend/tests/test_rfm_extended_sprint142.py` NEW, 3 case):

```python
"""Sprint 142 RFM 扩展分群回归测试"""

import pytest
from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE

pytestmark = pytest.mark.skipif(not _PROD_DUCKDB_AVAILABLE, reason="production DuckDB 不可用")


class TestRFMExtended:
    """Sprint 142: lifecycle_stage + value_tier + potential_tier 3 个新维度"""

    def test_lifecycle_classification_basic(self, monkeypatch_connection):
        """lifecycle_stage 4 桶分类正确 (NEW < 30, ACTIVE 30+, DORMANT 30-180, CHURNED > 180)"""
        # 构造测试数据, 验证 4 桶 SQL CASE WHEN
        ...

    def test_value_tier_gsv_threshold(self, monkeypatch_connection):
        """value_tier 3 桶分类正确 (HIGH GSV >= 5000, MEDIUM 1000-5000, LOW < 1000)"""
        ...

    def test_potential_tier_growth_slope(self, monkeypatch_connection):
        """potential_tier 3 桶分类正确 (HIGH growth > 0 + active, MEDIUM active only, LOW else)"""
        ...
```

---

### Task 2: level 联动 summary 卡二级聚合

**前置**: 现状 `SamplingChannelSummary` 字段按 channel 聚合 (跟 level 无关), `cat_sql` 已按 level 聚合. user 切 level 时 summary 卡不动. Task 2 加二级聚合.

**2.1 contract 新增 `SamplingLevelSummary`** (`backend/contracts/sampling.py`):

```python
class SamplingLevelSummary(BaseModel):
    """派样 level 二级聚合 (Sprint 142 新增, channel × level 交叉)

    字段语义跟 SamplingChannelSummary 一致, 但 level_value 是 cat_sql 聚合的 category
    """
    channel: str = Field(..., description="渠道")
    level: str = Field(..., description="5 levels: spu_category / spu_tier / spu_product_class / spu_product_subclass / spu_cosmetic")
    level_value: str = Field(..., description="level 聚合维度值 (e.g. spu_category='胶原膜', spu_tier='核心品')")
    sample_users: int = Field(..., description="派样人数")
    repurchase_users: int = Field(..., description="回购人数")
    repurchase_rate: "RatioField" = Field(default=0.0, description="回购率 (0-1)")
    repurchase_gsv: float = Field(default=0.0, description="回购 GSV")
    repurchase_aus: float = Field(default=0.0, description="客单价")
    # Sprint 139 保留
    full_repurchase_users: int = 0
    full_repurchase_gsv: float = 0.0
    full_repurchase_aus: float = 0.0
    full_repurchase_rate: "RatioField" = 0.0
    nonfull_repurchase_users: int = 0
    nonfull_repurchase_gsv: float = 0.0


class SamplingROIResponse(BaseModel):
    """派样 ROI response (Sprint 142 加 summary_by_level)"""
    # 既有字段保留
    channel_summary: List[SamplingChannelSummary]
    category_detail: List[SamplingCategoryRow]
    period_distribution: PeriodDistribution
    quality_flags: List[QualityFlag] = []
    time_range: SamplingROITimeRange
    # Sprint 142 新增
    summary_by_level: Dict[str, List[SamplingLevelSummary]] = Field(
        default_factory=dict,
        description="level 二级聚合 {level_name: [SamplingLevelSummary]}, 切 level 时 summary 卡重渲染",
    )
```

**2.2 service 改造** (`backend/services/sampling_service.py:159 cat_sql` 段):

```python
# 既有 cat_sql 已经按 level 聚合, 在 return dict 里加 summary_by_level 包装
# Sprint 142: 复用 cat_sql, 按 level 分组返回

# 在 get_sampling_roi() return dict 里加:
return {
    'channel_summary': [...],  # 既有
    'category_detail': cat_rows,  # 既有
    'period_distribution': period_distribution,  # 既有
    'quality_flags': quality_flags,  # 既有
    'time_range': {...},  # 既有
    # Sprint 142 新增: 按 level 分组 category_detail
    'summary_by_level': _group_by_level(cat_rows, level),
}


def _group_by_level(cat_rows: List, level: str) -> Dict[str, List[SamplingLevelSummary]]:
    """把 cat_rows 按 level 字段分组, 返回 {level_value: [SamplingLevelSummary]}

    复用既有 cat_rows 数据, 0 新 SQL 查询
    """
    grouped = {}
    for row in cat_rows:
        level_value = row.get('repurchase_cat_detail') or '未知'
        if level_value not in grouped:
            grouped[level_value] = []
        grouped[level_value].append(SamplingLevelSummary(
            channel=row['channel'],
            level=level,
            level_value=level_value,
            sample_users=row['sample_users'],
            repurchase_users=row['repurchase_users'],
            repurchase_rate=row['repurchase_rate'],
            repurchase_gsv=row['repurchase_gsv'],
            repurchase_aus=row['repurchase_aus'],
            full_repurchase_users=row['full_repurchase_users'],
            full_repurchase_rate=row['full_repurchase_rate'],
            full_repurchase_gsv=row['full_repurchase_gsv'],
            full_repurchase_aus=row['full_repurchase_aus'],
            nonfull_repurchase_users=row['nonfull_repurchase_users'],
            nonfull_repurchase_gsv=row['nonfull_repurchase_gsv'],
        ))
    return grouped
```

**2.3 前端 level 联动 summary 卡** (`frontend-vue3/src/views/SamplingView.vue` L415-450 区域):

```vue
<!-- Sprint 142: summary 卡按 level 联动, 切 level 时 summary 卡重渲染 -->
<template>
  <div class="summary-by-level">
    <h3 class="text-base font-medium text-slate-700 mb-2">品类维度汇总 ({{ levelLabel }})</h3>
    <n-grid :cols="3" :x-gap="12" :y-gap="12">
      <n-grid-item v-for="(summaries, levelValue) in summaryByLevel" :key="levelValue">
        <n-card :title="levelValue" size="small">
          <div class="space-y-2">
            <div class="flex justify-between text-sm">
              <span class="text-slate-500">派样人数</span>
              <span class="font-medium">{{ summaries[0]?.sample_users?.toLocaleString() || 0 }}</span>
            </div>
            <div class="flex justify-between text-sm">
              <span class="text-slate-500">回购人数</span>
              <span class="font-medium">{{ summaries[0]?.repurchase_users?.toLocaleString() || 0 }}</span>
            </div>
            <div class="flex justify-between text-sm">
              <span class="text-slate-500">回购率</span>
              <MetricCard :value="summaries[0]?.repurchase_rate || 0" unit="%" />
            </div>
            <div class="flex justify-between text-sm">
              <span class="text-slate-500">回购 GSV</span>
              <span class="font-medium">¥{{ summaries[0]?.repurchase_gsv?.toLocaleString() || 0 }}</span>
            </div>
          </div>
        </n-card>
      </n-grid-item>
    </n-grid>
  </div>
</template>

<script setup>
// Sprint 142: 复用 roiData, 计算属性派生 summary_by_level
const summaryByLevel = computed(() => {
  if (!roiData.value?.summary_by_level) return {}
  return roiData.value.summary_by_level
})
</script>
```

**2.4 pytest** (`backend/tests/test_sampling_level_aggregation_sprint142.py` NEW, 2 case):

```python
"""Sprint 142 level 联动 summary 二级聚合回归测试"""

import pytest
from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE

pytestmark = pytest.mark.skipif(not _PROD_DUCKDB_AVAILABLE, reason="production DuckDB 不可用")


class TestLevelAggregation:
    """Sprint 142: summary_by_level 字段在 5 levels 都正确返回"""

    @pytest.mark.parametrize("level", ["spu_category", "spu_tier", "spu_product_class", "spu_product_subclass", "spu_cosmetic"])
    def test_summary_by_level_5_levels(self, monkeypatch_connection, level):
        """5 levels 都返回 summary_by_level 字段 (Sprint 142 加)"""
        from backend.services.sampling_service import get_sampling_roi
        result = get_sampling_roi(
            start_date="2026-04-01", end_date="2026-06-30",
            window_days=30, level=level,
        )
        assert "summary_by_level" in result
        assert isinstance(result["summary_by_level"], dict)
        # 至少有 1 个 level_value (e.g. spu_category='胶原膜')
        assert len(result["summary_by_level"]) > 0

    def test_summary_by_level_reuses_cat_rows_no_extra_query(self, monkeypatch_connection):
        """summary_by_level 复用 cat_rows, 0 新 SQL 查询 (性能优化)"""
        # 通过 query log 验证, 或 code review
        ...
```

---

### Task 3: `_compute_lock_metrics` 性能重构

**前置**: `sampling_service.py:374-450` 4-5 次 `conn.execute` 单字段查询, 每次全表扫 orders. Sprint 142 性能重构: 单 SQL 合并.

**3.1 当前性能瓶颈** (sampling_service.py:374-450):

```python
def _compute_lock_metrics(conn, campaign_row) -> Dict[str, Any]:
    locked = conn.execute(...)   # 1 次全表扫 orders
    uv = conn.execute(...)        # 1 次全表扫 daily_visitors
    converted = conn.execute(...) # 1 次全表扫 orders
    new_data = conn.execute(...)  # 1 次全表扫 orders + user_first_purchase
    # 总 4 次 RTT, 每次扫大表
```

**3.2 重构后** (`sampling_service.py:374-450` 区域):

```python
def _compute_lock_metrics(conn, campaign_row) -> Dict[str, Any]:
    """Sprint 142: 单 SQL 合并 4 次查询, 性能加速 ≥ 2× (跟 Sprint 30.1 W4 模式 stable)"""
    year, name, conv_start, conv_end, lock_start, lock_end = campaign_row

    if not lock_start or not lock_end:
        return _empty_lock_data()

    lock_start_str = str(lock_start)
    lock_end_str = str(lock_end)
    conv_start_str = str(conv_start)
    conv_end_str = str(conv_end)

    # Sprint 142: 单 SQL 合并 locked + uv + converted + new_data 4 个指标
    # SQL 中 ? 出现顺序: 3(GIFT_SAMPLE_DB, lock_start, lock_end) + 2(conv_start, conv_end) + 3(lock_start x3, used as new customer threshold)
    sql = f"""
        WITH locked_users AS (
            SELECT DISTINCT user_id
            FROM orders o
            WHERE o.channel = ?
              AND ROUND(o.actual_amount, 2) = 0.01
              AND o.pay_time >= ?::DATE AND o.pay_time <= ?::DATE + INTERVAL '1' DAY
        ),
        uv AS (
            SELECT COALESCE(SUM(visitors), 0) AS total_uv
            FROM daily_visitors
            WHERE date >= ?::DATE AND date <= ?::DATE
        ),
        converted AS (
            SELECT
                COUNT(DISTINCT o.user_id) AS converted_users,
                COALESCE(SUM(o.actual_amount), 0) AS lock_gsv
            FROM orders o
            JOIN locked_users lu ON o.user_id = lu.user_id
            WHERE o.pay_time >= ?::DATE AND o.pay_time <= ?::DATE + INTERVAL '1' DAY
              AND o.is_refund = FALSE
              AND o.order_status != '交易关闭'
              AND o.channel != '购物金'
        ),
        new_data AS (
            SELECT
                COUNT(DISTINCT CASE WHEN ufp.first_pay_date >= ?::DATE THEN lu.user_id END) AS new_locked,
                COUNT(DISTINCT CASE WHEN ufp.first_pay_date >= ?::DATE AND o.order_id IS NOT NULL THEN lu.user_id END) AS new_converted,
                COALESCE(SUM(CASE WHEN ufp.first_pay_date >= ?::DATE THEN o.actual_amount ELSE 0 END), 0) AS new_gsv
            FROM locked_users lu
            LEFT JOIN user_first_purchase ufp ON lu.user_id = ufp.user_id
            LEFT JOIN orders o ON lu.user_id = o.user_id
                AND o.pay_time >= ?::DATE AND o.pay_time <= ?::DATE + INTERVAL '1' DAY
                AND o.is_refund = FALSE AND o.order_status != '交易关闭' AND o.channel != '购物金'
        )
        SELECT
            (SELECT COUNT(*) FROM locked_users) AS locked_orders,
            (SELECT COUNT(DISTINCT user_id) FROM locked_users) AS locked_users,
            (SELECT total_uv FROM uv) AS total_uv,
            (SELECT converted_users FROM converted) AS converted_users,
            (SELECT lock_gsv FROM converted) AS lock_gsv,
            (SELECT new_locked FROM new_data) AS new_locked,
            (SELECT new_converted FROM new_data) AS new_converted,
            (SELECT new_gsv FROM new_data) AS new_gsv
    """
    # SQL中?出现顺序: 3(GIFT_SAMPLE_DB, lock_start, lock_end) + 2(conv_start, conv_end) + 2(conv_start, conv_end) + 3(lock_start x3) + 2(conv_start, conv_end)
    params = [
        GIFT_SAMPLE_DB, lock_start_str, lock_end_str,         # locked_users
        conv_start_str, conv_end_str,                          # uv
        conv_start_str, conv_end_str,                          # converted
        lock_start_str, lock_start_str, lock_start_str,        # new_data (3 个 lock_start 阈值)
        conv_start_str, conv_end_str,                          # new_data (转化期)
    ]
    row = conn.execute(sql, params).fetchone()

    locked_users = int(row[1] or 0)
    total_uv = int(row[2] or 0)
    converted_users = int(row[3] or 0)
    lock_gsv = float(row[4] or 0)
    new_locked = int(row[5] or 0)
    new_converted = int(row[6] or 0)
    new_gsv = float(row[7] or 0)

    lock_rate = safe_ratio(locked_users, total_uv)
    conversion_rate = safe_ratio(converted_users, locked_users)
    lock_aus = safe_ratio(lock_gsv, converted_users)
    new_locked_ratio = safe_ratio(new_locked, locked_users)
    new_conversion_rate = safe_ratio(new_converted, new_locked)
    new_lock_aus = safe_ratio(new_gsv, new_converted)

    return {
        'total_uv': total_uv,
        'locked_users': locked_users,
        'lock_rate': round(lock_rate, 6),
        'converted_users': converted_users,
        'conversion_rate': round(conversion_rate, 4),
        'lock_gsv': round(lock_gsv, 2),
        'lock_aus': round(lock_aus, 2),
        'new_locked_users': new_locked,
        'new_locked_ratio': round(new_locked_ratio, 4),
        'new_converted_users': new_converted,
        'new_conversion_rate': round(new_conversion_rate, 4),
        'new_lock_gsv': round(new_gsv, 2),
        'new_lock_aus': round(new_lock_aus, 2),
    }
```

**3.3 L4.7 ground-truth-lint 治根** (跟 Sprint 60+ 实战 fix 模式):

```python
# Sprint 142: 加 assert 防 params 顺序错位 (Sprint 60 实战 fix 模式)
def _compute_lock_metrics(conn, campaign_row) -> Dict[str, Any]:
    """Sprint 142: 单 SQL 合并 4 次查询, 性能加速 ≥ 2× (跟 Sprint 30.1 W4 模式 stable)"""
    # ... (SQL 已合并)
    # Sprint 60+ L4.7 治根: assert ? 出现顺序 == params 数量
    assert sql.count('?') == len(params), f"_compute_lock_metrics params mismatch: SQL has {sql.count('?')} ? but {len(params)} params"
```

**3.4 micro-benchmark** (`data/processed/etl_perf/benchmarks/sprint142_lock_metrics.json`):

```bash
# Sprint 142 必跑 micro-benchmark, 验证加速 ≥ 2×
PYTHONPATH="$(pwd)" /Users/yourname/homebrew/bin/python3 -c "
import time
import duckdb
con = duckdb.connect('/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb', read_only=True)
# 找一个大促周期 (Sprint 134+ P3 有默认 fixture)
campaign_row = (2025, '双11', '2025-11-01', '2025-11-11', '2025-10-25', '2025-10-31')

# 跑 5 次, 算平均
start = time.time()
for _ in range(5):
    _compute_lock_metrics(con, campaign_row)
elapsed = time.time() - start
print(f'平均耗时: {elapsed/5:.3f}s')

# 跟 Sprint 141 baseline 对比 (Sprint 141 多次单 SQL 累计 ~1.0s, 期望 Sprint 142 单 SQL ~0.5s)
"
```

**3.5 pytest** (`backend/tests/test_lock_metrics_sprint142.py` NEW, 3 case):

```python
"""Sprint 142 _compute_lock_metrics 性能重构回归测试"""

import pytest
from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE

pytestmark = pytest.mark.skipif(not _PROD_DUCKDB_AVAILABLE, reason="production DuckDB 不可用")


class TestLockMetricsRefactor:
    """Sprint 142: _compute_lock_metrics 单 SQL 合并, 行为等价 Sprint 141"""

    def test_lock_metrics_consistent_with_baseline(self, monkeypatch_connection):
        """Sprint 142 重构后 _compute_lock_metrics 输出字段值跟 Sprint 141 baseline 等价"""
        from backend.services.sampling_service import _compute_lock_metrics
        # 跑同一 campaign_row, 验证字典所有字段值
        campaign_row = (2025, '618', '2025-06-01', '2025-06-18', '2025-05-25', '2025-05-31')
        result = _compute_lock_metrics(monkeypatch_connection, campaign_row)
        # 13 个字段都返回 (跟 Sprint 141 _compute_lock_metrics 行为一致)
        expected_fields = [
            'total_uv', 'locked_users', 'lock_rate', 'converted_users',
            'conversion_rate', 'lock_gsv', 'lock_aus',
            'new_locked_users', 'new_locked_ratio', 'new_converted_users',
            'new_conversion_rate', 'new_lock_gsv', 'new_lock_aus',
        ]
        for field in expected_fields:
            assert field in result
            assert isinstance(result[field], (int, float))

    def test_lock_metrics_empty_lock_returns_empty(self, monkeypatch_connection):
        """lock_start/lock_end 都为 None 时返回 _empty_lock_data() (跟 Sprint 141 行为一致)"""
        from backend.services.sampling_service import _compute_lock_metrics
        campaign_row = (2025, 'noop', '2025-06-01', '2025-06-18', None, None)
        result = _compute_lock_metrics(monkeypatch_connection, campaign_row)
        assert result['locked_users'] == 0
        assert result['converted_users'] == 0
        assert result['lock_gsv'] == 0

    def test_lock_metrics_params_order_assertion(self, monkeypatch_connection):
        """L4.7 治根: assert sql.count('?') == len(params), 防 params 顺序错位"""
        # 故意传错 params 顺序, 期望 AssertionError
        ...
```

---

## 2. 不做什么 (防 scope creep)

- ❌ 不替换 8 quadrant RFM 阈值 (Sprint 60+ 闭环, 保留)
- ❌ 不改 Sprint 139 + 140 + 141 + 141.5 Phase 1 已稳定的 contract / service / e2e
- ❌ 不动 `SamplingView.vue` L387 subtitle (Sprint 143 改)
- ❌ 不动 `SamplingView.vue` 新增 tab / CohortRetentionMatrix (Sprint 143 新建)
- ❌ 不新建 `backend/services/lifetime_value_service.py` (Sprint 143 新建)
- ❌ 不新建 `backend/services/cohort_retention_service.py` (Sprint 143 新建)
- ❌ 不改 LTV / cohort retention / 改名 ROI (Sprint 143 范围)
- ❌ 不改 Sprint 144+/145+ (暂收口)

---

## 3. 验收清单 (Codex 必跑)

```bash
# 1. pytest 8 case PASS
PYTHONPATH="$(pwd)" DUCKDB_PATH="/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb" \
  pytest backend/tests/test_rfm_extended_sprint142.py backend/tests/test_sampling_level_aggregation_sprint142.py backend/tests/test_lock_metrics_sprint142.py -v
# 期望: 8 passed (3 + 5 parametrize expansion + 3 = 8 case)

# 2. Sprint 139/140/141/141.5 ground-truth-lint 全 PASS
PYTHONPATH="$(pwd)" python3 backend/scripts/check_sampling_spu_type.py
PYTHONPATH="$(pwd)" python3 backend/scripts/check_window_unification.py
PYTHONPATH="$(pwd)" python3 backend/scripts/check_period_distribution_61_90d.py
PYTHONPATH="$(pwd)" python3 backend/scripts/check_channel_alias.py
# 期望: PASS × 4

# 3. 全部 pytest baseline 持续 (740 → 750)
PYTHONPATH="$(pwd)" DUCKDB_PATH="..." pytest backend/tests/ -q
# 期望: 750 passed / 23 skipped / 0 failed

# 4. _compute_lock_metrics 性能加速 ≥ 2× (Task 3.4 micro-benchmark)
# 输出到 data/processed/etl_perf/benchmarks/sprint142_lock_metrics.json

# 5. 前端 npm run build 0 errors (跟 L4.22 sprint 收口强制)
cd frontend-vue3 && npm run build
# 期望: 0 errors

# 6. pre-commit 全绿
git add -A
bash .githooks/pre-commit
```

---

## 4. 风险评估 (4 项已知风险)

| # | 风险 | 概率 | 缓解 |
|---|---|---|---|
| R1 | 跟 Sprint 143 并行开发, SamplingView.vue 可能 merge 冲突 | 中 | 已明确分工 (Sprint 142 改 L400-460 + Sprint 143 改 L387 + 新增组件); merge 时 git 会自动 conflict resolution, 人工 review |
| R2 | _compute_lock_metrics 单 SQL 合并后, CTE 复杂度高, DuckDB query planner 可能不优 | 中 | micro-benchmark 验证加速 ≥ 2×; 失败时 fallback 到 Sprint 141 多次 query 模式 |
| R3 | RFM 扩展维度 (lifecycle_stage + value_tier + potential_tier) 阈值业务侧没拍板 | 中 | 用推荐阈值 (LIFECYCLE_THRESHOLDS + VALUE_THRESHOLDS + POTENTIAL_THRESHOLDS), 业务侧后续可调 |
| R4 | frontend-vue3 e2e spec 5 levels parametrize 跟 Sprint 140 + 141 e2e 冲突 | 低 | Sprint 142 e2e 新增独立 test, 不动 Sprint 139/140/141 e2e |

---

## 5. L4.x 永久规则强制清单

| 规则 | 适用范围 | Sprint 142 检查点 |
|---|---|---|
| L4.1 SQL 三引号 + f-string | body 含 `{identifier}` 必须 f 前缀 | lifecycle_case_sql / value_tier_case_sql / potential_tier_case_sql / get_user_rfm_extended / _compute_lock_metrics 加 f 前缀 |
| L4.5 FilterBuilder + ? 参数化 | service 函数禁止 f-string 内嵌用户输入 | 复用既有 FilterBuilder; LIFECYCLE_THRESHOLDS / VALUE_THRESHOLDS / POTENTIAL_THRESHOLDS 是常量, 0 风险 |
| L4.3 isolated_duckdb fixture | 真连必用 per-worker tmp DuckDB | pytest 8 case 全用 `monkeypatch_connection` |
| L4.4 真连 DuckDB skipif | `_PROD_DUCKDB_AVAILABLE` 守卫 | pytest 必加 `pytestmark` |
| L4.6 worktree DUCKDB_PATH | worktree 跑 pytest 必 export | Sprint 142 实施期间走 worktree 模式 |
| L4.7 SQL ? 数量 == params 数量 | _compute_lock_metrics 加 assert 防 params 顺序错位 | Task 3.3 assert |
| L4.16 push trigger paths | 改 backend/services + backend/contracts + backend/tests + backend/scripts + frontend-vue3 + e2e 都触发 | ✅ paths 都包含 |
| L4.19 channel alias | service 输出 SQL 含 `channel IN/NOT IN/=` 必须有 `o.` 表别名 | Sprint 142 复用既有服务, 不动 channel alias; 新 SQL 加 `o.channel` 别名 |
| L4.20 留尾 SSOT 治理 | Sprint 142 收口时强制检查 | close memory 必引真修 commit SHA |
| L4.22 vite rebuild | 前端 sprint 收口 | Claude Stage 4 必跑 (Task 5 npm run build) |

---

## 6. 跟 Sprint 143 并行开发约定 (避免冲突)

| 文件 | Sprint 142 改的 line | Sprint 143 改的 line | 冲突? |
|---|---|---|---|
| `frontend-vue3/src/views/SamplingView.vue` | L400-460 (level 联动 summary 卡) | L387 (subtitle) | ❌ |
| `frontend-vue3/src/views/SamplingView.vue` | 不动 | 新增 <cohort-retention-matrix> 标签 | ❌ |
| `frontend-vue3/src/api/sampling.ts` | 加 `SamplingLevelSummary` + `summary_by_level` | 不动 | ❌ |
| `frontend-vue3/src/api/sampling.ts` | 不动 | 加 `fetchLifetimeValue` + `fetchCohortRetention` | ❌ |
| `backend/services/sampling_service.py` | `_compute_lock_metrics` 重构 + `summary_by_level` 计算 | 不动 | ❌ |
| `backend/contracts/sampling.py` | 加 `SamplingLevelSummary` + `SamplingROIResponse.summary_by_level` | 不动 | ❌ |

**0 冲突区**. merge 顺序: Sprint 142 先合 → Sprint 143 后合 (避免 L387 subtitle 文案被 Sprint 142 冲突覆盖).

---

## 7. Codex Stage 2 实施规范

**Codex 必读**:
1. 本文件全文 (3 个 Task)
2. `AGENTS.md` (本地文件, .gitignore 排除, 自动注入)
3. 必跑 `git log --all --oneline | head -10` + `git log main --oneline -- backend/services/sampling_service.py backend/contracts/sampling.py backend/semantic/segments.py` 验 Sprint 139+140+141+141.5 收口状态

**Codex 不做**:
- ❌ 不 git commit / push (Claude Stage 4 负责)
- ❌ 不动 Sprint 139 / 140 / 141 / 141.5 Phase 1 已稳定的 contract / service / e2e
- ❌ 不改 Sprint 142 scope 之外的 docs
- ❌ 不动 RFM 8 quadrant (Sprint 60+ 闭环, 保留)
- ❌ 不动 `SamplingView.vue` L387 + 新增 CohortRetentionMatrix (Sprint 143 范围)
- ❌ 不新建 `lifetime_value_service.py` + `cohort_retention_service.py` (Sprint 143 范围)
- ❌ 不改名 ROI → 正装转化分析 (Sprint 143 范围)

**Codex 实施完成时给 user 回报**:
- ✅ pytest 8 case PASS (3 RFM + 2/5 parametrize level + 3 lock metrics = 8 case)
- ✅ Sprint 139/140/141/141.5 ground-truth-lint 钩子 全 PASS × 4
- ✅ _compute_lock_metrics micro-benchmark ≥ 2× 加速 (Q5 拍板后)
- ✅ `npm run build` 0 errors (前端 L4.22)
- ✅ pre-commit 全绿
- ✅ git diff --stat 改动列表 (实质净 +150/-100 行, 8 files)

---

## 8. 文件改动清单 (8 files / +150/-100 行)

| 文件 | 改法 | LOC |
|---|---|---|
| `backend/contracts/rfm_segments.py` (NEW) | LifecycleStage + ValueTier + PotentialTier enum + RFMSegmentExtended | +60/-0 |
| `backend/semantic/segments.py` | LIFECYCLE_THRESHOLDS + VALUE_THRESHOLDS + POTENTIAL_THRESHOLDS + lifecycle_case_sql + value_tier_case_sql + potential_tier_case_sql | +60/-0 |
| `backend/services/rfm_service.py` (NEW) | get_user_rfm_extended() 8 quadrant + 3 新维度聚合 | +90/-0 |
| `backend/routers/rfm.py` (NEW) | POST /v1/rfm/extended endpoint | +15/-0 |
| `backend/contracts/sampling.py` | 加 SamplingLevelSummary + SamplingROIResponse.summary_by_level | +20/-5 |
| `backend/services/sampling_service.py` | `_compute_lock_metrics` 单 SQL 重构 + `summary_by_level` 包装 + L4.7 assert | +60/-50 |
| `frontend-vue3/src/views/SamplingView.vue` | L400-460 level 联动 summary 卡 | +25/-15 |
| `frontend-vue3/src/api/rfm.ts` (NEW) | fetchUserRFMExtended + RFMSegmentExtended interface | +30/-0 |
| `backend/tests/test_rfm_extended_sprint142.py` (NEW) | 3 case | +50 |
| `backend/tests/test_sampling_level_aggregation_sprint142.py` (NEW) | 2 case + 5 parametrize expansion | +60 |
| `backend/tests/test_lock_metrics_sprint142.py` (NEW) | 3 case | +50 |
| `data/processed/etl_perf/benchmarks/sprint142_lock_metrics.json` (NEW) | micro-benchmark 输出 | +20 |
| `CHANGELOG.md` | Sprint 142 entry | +25 |

**合计**: 实质净 +150/-100 (实质有效 +565 行, 跟 Sprint 141 模式 stable)

---

## 9. 完成定义 (Definition of Done)

- [ ] Task 1-3 全部完成 (RFM 扩展 + level 联动 + 性能重构)
- [ ] pytest 8 case PASS (新增)
- [ ] micro-benchmark 加 `data/processed/etl_perf/benchmarks/sprint142_lock_metrics.json`
- [ ] 性能加速 ≥ 2× 验证 (Q5 拍板后)
- [ ] Sprint 139/140/141/141.5 ground-truth-lint 全 PASS × 4
- [ ] pre-commit ruff + pytest + ground-truth-lint 全绿
- [ ] L4.x 22 stable 0 新增
- [ ] VERSION 0.4.14.157 不 bump
- [ ] CHANGELOG.md +1 entry
- [ ] frontend-vue3 `npm run build` 0 errors (L4.22 sprint 收口强制)
- [ ] 跟 Sprint 143 并行约定 0 冲突 (merge 顺序: Sprint 142 先合)

**未达任一项 = Codex 未完成, 回到 Stage 2 修补。**

---

## 10. 待 user 拍板 (5 项小决策)

| # | 决策点 | 推荐选项 |
|---|---|---|
| Q3 | level 二级聚合新增字段 vs 替换既有 `summary` | (A) 新增 `summary_by_level` (0 breaking change) |
| Q5 | 性能重构加 micro-benchmark | (A) 加（验证加速 ≥ 2×） |
| RFM 阈值 | LIFECYCLE_THRESHOLDS / VALUE_THRESHOLDS / POTENTIAL_THRESHOLDS 业务侧定 | (A) 推荐阈值 (NEW<30, HIGH_GSV>=5000, ACTIVE<30) |

---

**Sprint 142 Stage 1 详细 plan 已锁定, Codex 可立即开工. 跟 Sprint 143 并行开发约定已明确 (0 冲突区).**