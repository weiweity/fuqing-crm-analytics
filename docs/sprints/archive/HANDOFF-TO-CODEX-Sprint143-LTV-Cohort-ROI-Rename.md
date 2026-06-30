# HANDOFF-TO-CODEX — Sprint 143 (LTV + cohort retention matrix + 改名 ROI)

> **状态**: 📋 立项待 Codex 实施 (2026-06-28)
> **触发**: Sprint 141.5 Phase 1 收口 — user 拍板"并行开 Sprint 142 和 143"
> **范围**: 1 真业务 (改名 ROI) + 2 全新建 (LTV + cohort retention), 7 文件, **实质净 +250/-30 行**
> **模式**: 跟 Sprint 137 真 refactor (AudienceView 拆 3 tabs) + Sprint 116+117 真 refactor sprint 模式 stable (Codex Stage 2 + Claude Stage 3 review)
> **跟 Sprint 142 并行**: Sprint 143 改 `SamplingView.vue` ROI 命名 + 新增 cohort retention 组件; Sprint 142 改 `SamplingView.vue` level 联动 UI. **关键约定**: Sprint 143 只动 ROI tab subtitle (L387) + 新增 CohortRetentionMatrix.vue (新组件, 不动 Sprint 142 区域).
> **预期影响**: pytest baseline 750/23/0 → 760/23/0 (+10 case), L4.x 22 stable 0 新增, VERSION 0.4.14.157 不 bump

---

## 0. 背景

### 0.1 user 原话 (Sprint 141.5 Phase 1 收口后拍板)

> "并行开sprint142和143，给两个handoff，我让codex,并行开发"

### 0.2 Sprint 143 三件事 (基于 codegraph 实读 main @ `b180568`)

| # | 范围 | 现状 (基于 main @ `b180568`) | 改造方向 |
|---|---|---|---|
| Task 1 | LTV 90/180/365d | **0 引用**, 全新建 | 新建 `backend/services/lifetime_value_service.py` + W4 cache (复用 RFM_THRESHOLDS) |
| Task 2 | cohort retention matrix | **0 引用**, 全新建 | 新建 `backend/services/cohort_retention_service.py` + 前端 CohortRetentionMatrix.vue (新组件) |
| Task 3 | 改名 ROI → 正装转化分析 | `SamplingView.vue:387` subtitle = "U先/百补派样ROI / 0.01锁权转化分析" | 改 subtitle 文案; API 字段 `sampling_roi` 保留 (Q10 推荐 A: 仅前端文案) |

### 0.3 跟 Sprint 142 并行约定 (避免 SamplingView.vue 冲突)

| 文件区 | Sprint 143 改 | Sprint 142 改 |
|---|---|---|
| `SamplingView.vue` L387 (PageHeader subtitle) | ✅ 改文案 | ❌ 不动 |
| `SamplingView.vue` L400-460 (level 联动 UI + summary 卡) | ❌ 不动 | ✅ 改 |
| `SamplingView.vue` 新增 tab | ✅ CohortRetentionMatrix.vue | ❌ 不动 |
| 新文件 `backend/services/lifetime_value_service.py` | ✅ 新建 | ❌ 不动 |
| 新文件 `backend/services/cohort_retention_service.py` | ✅ 新建 | ❌ 不动 |
| `backend/contracts/sampling.py` `SamplingChannelSummary` | ❌ 不动 | ✅ 加 `summary_by_level` |
| `frontend-vue3/src/api/sampling.ts` | ✅ 加 `fetchLifetimeValue` + `fetchCohortRetention` | ❌ 不动 |

---

## 1. 范围 (3 个 Task, 按顺序施工)

### Task 1: LTV 90/180/365d 计算 service

**前置**: Sprint 141.5 Phase 1 sample_received_at 字段已加 (COALESCE 回退 pay_time 等价 Sprint 141 状态), LTV 不依赖真 sample_received_at 数据. 0 阻塞.

**1.1 semantic 层 LTV 计算** (`backend/semantic/lifetime_value.py` NEW):

```python
"""Sprint 143 用户生命周期价值 (LTV) 计算 — 90/180/365d 累计 GSV"""

from typing import Dict, Optional, List
from dataclasses import dataclass


# LTV 时间窗口 (天)
LTV_WINDOWS = [90, 180, 365]


@dataclass
class LTVResult:
    """单用户 LTV 计算结果"""
    user_id: str
    cohort_date: str          # 派样 cohort 日期 (YYYY-MM-DD)
    gsv_90d: float            # 90 天累计 GSV
    gsv_180d: float           # 180 天累计 GSV
    gsv_365d: float           # 365 天累计 GSV
    order_count_90d: int      # 90 天订单数
    order_count_180d: int
    order_count_365d: int


def compute_ltv_for_user(conn, user_id: str, cohort_date: str) -> LTVResult:
    """计算单个用户的 LTV 90/180/365d

    Args:
        conn: DuckDB 连接
        user_id: 用户 ID
        cohort_date: 派样 cohort 日期 (YYYY-MM-DD), LTV 起点

    Returns:
        LTVResult (gsv + order_count 3 窗口)
    """
    sql = """
        SELECT
            user_id,
            ?::DATE as cohort_date,
            SUM(CASE WHEN DATEDIFF('day', ?::DATE, o.pay_time) BETWEEN 1 AND 90
                     THEN o.actual_amount ELSE 0 END) as gsv_90d,
            SUM(CASE WHEN DATEDIFF('day', ?::DATE, o.pay_time) BETWEEN 1 AND 180
                     THEN o.actual_amount ELSE 0 END) as gsv_180d,
            SUM(CASE WHEN DATEDIFF('day', ?::DATE, o.pay_time) BETWEEN 1 AND 365
                     THEN o.actual_amount ELSE 0 END) as gsv_365d,
            COUNT(DISTINCT CASE WHEN DATEDIFF('day', ?::DATE, o.pay_time) BETWEEN 1 AND 90
                                THEN o.order_id END) as order_count_90d,
            COUNT(DISTINCT CASE WHEN DATEDIFF('day', ?::DATE, o.pay_time) BETWEEN 1 AND 180
                                THEN o.order_id END) as order_count_180d,
            COUNT(DISTINCT CASE WHEN DATEDIFF('day', ?::DATE, o.pay_time) BETWEEN 1 AND 365
                                THEN o.order_id END) as order_count_365d
        FROM orders o
        WHERE o.user_id = ?
          AND o.is_refund = FALSE
          AND o.order_status != '交易关闭'
          AND o.channel != '购物金'
        GROUP BY user_id
    """
    # SQL中?出现顺序: 1(cohort_date for select) + 6(cohort_date x 6 for SUM/COUNT CASE WHEN) + 1(user_id) = 8 params
    params = [cohort_date, cohort_date, cohort_date, cohort_date, cohort_date, cohort_date, cohort_date, user_id]
    row = conn.execute(sql, params).fetchone()
    if not row:
        return LTVResult(user_id=user_id, cohort_date=cohort_date,
                         gsv_90d=0, gsv_180d=0, gsv_365d=0,
                         order_count_90d=0, order_count_180d=0, order_count_365d=0)
    return LTVResult(
        user_id=row[0],
        cohort_date=str(row[1]),
        gsv_90d=float(row[2] or 0),
        gsv_180d=float(row[3] or 0),
        gsv_365d=float(row[4] or 0),
        order_count_90d=int(row[5] or 0),
        order_count_180d=int(row[6] or 0),
        order_count_365d=int(row[7] or 0),
    )
```

**1.2 service 层 + W4 cache** (`backend/services/lifetime_value_service.py` NEW):

```python
"""Sprint 143 用户生命周期价值 (LTV) service — 90/180/365d 累计 GSV"""

from typing import Dict, List
from backend.semantic.lifetime_value import compute_ltv_for_user, LTVResult, LTV_WINDOWS
from backend.db.connection import get_connection
import logging

logger = logging.getLogger(__name__)


# W4 cache key (复用 Sprint 30.1 W4 540 combo batch INSERT 模式)
LTV_CACHE_KEY_PREFIX = "ltv_v1"


def get_user_ltv(
    user_id: str,
    cohort_date: str,
    use_cache: bool = True,
) -> LTVResult:
    """获取用户 LTV 90/180/365d

    Args:
        user_id: 用户 ID
        cohort_date: 派样 cohort 日期
        use_cache: 是否使用 W4 cache (默认 True)

    Returns:
        LTVResult
    """
    cache_key = f"{LTV_CACHE_KEY_PREFIX}:{user_id}:{cohort_date}"

    if use_cache:
        # 复用 backend.services.rfm.cache 模式
        cached = _read_ltv_cache(cache_key)
        if cached:
            return cached

    conn = get_connection()
    result = compute_ltv_for_user(conn, user_id, cohort_date)

    if use_cache:
        _write_ltv_cache(cache_key, result)

    return result


def get_users_ltv_batch(
    user_ids: List[str],
    cohort_date: str,
) -> Dict[str, LTVResult]:
    """批量获取用户 LTV (W4 cache 模式, 跟 Sprint 30.1 batch INSERT 模式 stable)

    Args:
        user_ids: 用户 ID 列表
        cohort_date: 派样 cohort 日期

    Returns:
        Dict[user_id, LTVResult]
    """
    conn = get_connection()
    results = {}
    for user_id in user_ids:
        results[user_id] = compute_ltv_for_user(conn, user_id, cohort_date)
    return results


def _read_ltv_cache(cache_key: str):
    """读 W4 cache (复用 backend.services.rfm.cache 模式)"""
    # 实现细节跟 backend/services/rfm/cache.py 模式 stable
    ...


def _write_ltv_cache(cache_key: str, result: LTVResult):
    """写 W4 cache (24h TTL, 跟 Sprint 30+ W5 模式 stable)"""
    ...
```

**1.3 contract 新增** (`backend/contracts/lifetime_value.py` NEW):

```python
"""Sprint 143 LTV contract"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date
from .types import RatioField, PercentageField


class LifetimeValueSummary(BaseModel):
    """用户生命周期价值 (LTV) 90/180/365d"""
    cohort_date: str = Field(..., description="派样 cohort 日期 (YYYY-MM-DD)")
    user_count: int = Field(..., description="cohort 用户数")
    # LTV 90/180/365d 平均值
    ltv_90d_avg: RatioField = Field(default=0.0, description="90 天累计 GSV / cohort 用户数 (0-1 区间, * GSV 系数)")
    ltv_180d_avg: RatioField = Field(default=0.0, description="180 天累计 GSV / cohort 用户数")
    ltv_365d_avg: RatioField = Field(default=0.0, description="365 天累计 GSV / cohort 用户数")
    # LTV 90/180/365d 中位数
    ltv_90d_median: RatioField = Field(default=0.0, description="90 天中位数 GSV")
    ltv_180d_median: RatioField = Field(default=0.0, description="180 天中位数 GSV")
    ltv_365d_median: RatioField = Field(default=0.0, description="365 天中位数 GSV")
    # YOY 对比 (跟 cohort_date 同期去年对比)
    ltv_90d_yoy_pct: PercentageField = Field(default=0.0, description="90 天 YOY 变化 (Sprint 17 #120 B2)")
    ltv_180d_yoy_pct: PercentageField = Field(default=0.0, description="180 天 YOY 变化")
    ltv_365d_yoy_pct: PercentageField = Field(default=0.0, description="365 天 YOY 变化")
```

**1.4 router 端点** (`backend/routers/lifetime_value.py` NEW):

```python
"""Sprint 143 LTV router"""

from fastapi import APIRouter, Depends
from backend.services.lifetime_value_service import get_users_ltv_batch
from backend.contracts.lifetime_value import LifetimeValueSummary
from backend.db.connection import get_connection

router = APIRouter()


@router.get("/v1/lifetime-value/cohort", response_model=LifetimeValueSummary)
def get_lifetime_value_cohort(cohort_date: str):
    """Sprint 143: cohort LTV 90/180/365d summary

    Args:
        cohort_date: 派样 cohort 日期 (YYYY-MM-DD)

    Returns:
        LifetimeValueSummary (ltv_90d/180d/365d_avg + median + yoy)
    """
    # 实现细节: 找 cohort 用户 + 批量 get_users_ltv_batch + 聚合 avg/median + 算 YOY
    ...
```

**1.5 pytest** (`backend/tests/test_lifetime_value_sprint143.py` NEW, 3 case):

```python
"""Sprint 143 LTV 90/180/365d 回归测试"""

import pytest
from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE

pytestmark = pytest.mark.skipif(not _PROD_DUCKDB_AVAILABLE, reason="production DuckDB 不可用")


class TestLifetimeValue:
    """Sprint 143: LTV 90/180/365d 累计 GSV 计算"""

    def test_ltv_3_windows_monotonic(self, monkeypatch_connection):
        """LTV 90d <= LTV 180d <= LTV 365d (累计 GSV 单调递增)"""
        from backend.semantic.lifetime_value import compute_ltv_for_user
        result = compute_ltv_for_user(monkeypatch_connection, user_id="U00001", cohort_date="2026-01-01")
        assert result.gsv_90d <= result.gsv_180d <= result.gsv_365d

    def test_ltv_excludes_refund_and_goujinjin(self, monkeypatch_connection):
        """LTV 计算排除退款单 + 购物金 channel (跟 Sprint 60+ RFM 排除逻辑一致)"""
        # 验证 LTV GSV 不含退款单 + 不含购物金 channel 订单
        ...

    def test_ltv_w4_cache_24h_ttl(self, monkeypatch_connection):
        """W4 cache 24h TTL 验证 (跟 Sprint 30+ W5 DuckDB-KV cache 模式 stable)"""
        ...
```

---

### Task 2: cohort retention matrix service + 前端组件

**前置**: Sprint 141.5 Phase 1 sample_received_at 字段已加 (COALESCE 回退 pay_time), cohort retention 不依赖真数据. 0 阻塞.

**2.1 semantic 层** (`backend/semantic/cohort_retention.py` NEW):

```python
"""Sprint 143 cohort retention matrix 计算"""

from typing import Dict, List
from dataclasses import dataclass


@dataclass
class CohortRetentionRow:
    """单 cohort retention 矩阵行"""
    cohort_month: str          # cohort 月份 (YYYY-MM, e.g. "2026-01")
    cohort_size: int           # cohort 用户数
    retention: Dict[int, float]  # {月偏移: 留存率} (0-1 decimal)


def compute_cohort_retention(
    conn,
    start_month: str,
    end_month: str,
    channel: str = "全店",
) -> List[CohortRetentionRow]:
    """计算 cohort retention matrix (按月 cohort)

    Args:
        conn: DuckDB 连接
        start_month: cohort 起始月份 (YYYY-MM)
        end_month: cohort 结束月份 (YYYY-MM)
        channel: 渠道 (默认全店)

    Returns:
        List[CohortRetentionRow], 每行 1 个 cohort 月份 + cohort_size + retention dict

    业务逻辑:
    - cohort = 同月首次活跃用户
    - retention[N] = cohort 中, 在 cohort + N 月仍有有效订单的用户比例
    """
    # CTE: 找 cohort 用户 + 计算每月留存
    sql = """
        WITH cohort_users AS (
            SELECT
                strftime(MIN(o.pay_time), '%Y-%m') as cohort_month,
                o.user_id
            FROM orders o
            WHERE o.channel LIKE ?
              AND o.is_refund = FALSE
              AND o.order_status != '交易关闭'
              AND strftime(o.pay_time, '%Y-%m') BETWEEN ? AND ?
            GROUP BY o.user_id
        ),
        cohort_active_months AS (
            SELECT
                cu.cohort_month,
                cu.user_id,
                strftime(o.pay_time, '%Y-%m') as active_month,
                DATEDIFF('month', cu.cohort_month || '-01', o.pay_time) as month_offset
            FROM cohort_users cu
            JOIN orders o ON cu.user_id = o.user_id
            WHERE o.channel LIKE ?
              AND o.is_refund = FALSE
              AND o.order_status != '交易关闭'
        )
        SELECT
            cohort_month,
            COUNT(DISTINCT user_id) as cohort_size,
            month_offset,
            COUNT(DISTINCT user_id) as active_users
        FROM cohort_active_months
        WHERE month_offset BETWEEN 0 AND 12  -- 0-12 月留存
        GROUP BY cohort_month, month_offset
        ORDER BY cohort_month, month_offset
    """
    # SQL中?出现顺序: 1(channel for cohort) + 2(start_month, end_month) + 1(channel for active_months) = 4 params
    channel_pattern = f"%{channel}%" if channel != "全店" else "%"
    params = [channel_pattern, start_month, end_month, channel_pattern]
    rows = conn.execute(sql, params).fetchall()

    # 聚合 cohort × month_offset → retention dict
    cohort_map: Dict[str, CohortRetentionRow] = {}
    for cohort_month, cohort_size, month_offset, active_users in rows:
        if cohort_month not in cohort_map:
            cohort_map[cohort_month] = CohortRetentionRow(
                cohort_month=cohort_month,
                cohort_size=cohort_size,
                retention={},
            )
        if cohort_size > 0:
            cohort_map[cohort_month].retention[month_offset] = active_users / cohort_size
    return list(cohort_map.values())
```

**2.2 service + W4 cache** (`backend/services/cohort_retention_service.py` NEW):

```python
"""Sprint 143 cohort retention matrix service"""

from typing import Dict, List
from backend.semantic.cohort_retention import compute_cohort_retention, CohortRetentionRow
from backend.db.connection import get_connection
import logging

logger = logging.getLogger(__name__)


COHORT_RETENTION_CACHE_KEY = "cohort_retention_v1"


def get_cohort_retention_matrix(
    start_month: str,
    end_month: str,
    channel: str = "全店",
    use_cache: bool = True,
) -> List[CohortRetentionRow]:
    """获取 cohort retention matrix

    Args:
        start_month: cohort 起始月份
        end_month: cohort 结束月份
        channel: 渠道 (默认全店)
        use_cache: 是否使用 W4 cache

    Returns:
        List[CohortRetentionRow]
    """
    cache_key = f"{COHORT_RETENTION_CACHE_KEY}:{start_month}:{end_month}:{channel}"

    if use_cache:
        cached = _read_cohort_cache(cache_key)
        if cached:
            return cached

    conn = get_connection()
    result = compute_cohort_retention(conn, start_month, end_month, channel)

    if use_cache:
        _write_cohort_cache(cache_key, result)

    return result


def _read_cohort_cache(cache_key):
    """读 W4 cache"""
    ...


def _write_cohort_cache(cache_key, result):
    """写 W4 cache (24h TTL)"""
    ...
```

**2.3 contract** (`backend/contracts/cohort_retention.py` NEW):

```python
"""Sprint 143 cohort retention matrix contract"""

from pydantic import BaseModel, Field
from typing import Dict, List
from .types import RatioField


class CohortRetentionRow(BaseModel):
    """cohort retention 矩阵单行"""
    cohort_month: str = Field(..., description="cohort 月份 (YYYY-MM)")
    cohort_size: int = Field(..., description="cohort 用户数")
    retention: Dict[int, "RatioField"] = Field(
        default_factory=dict,
        description="{月偏移: 留存率 0-1 decimal}, 0 = cohort 月, 12 = cohort + 12 月",
    )


class CohortRetentionResponse(BaseModel):
    """cohort retention matrix response"""
    rows: List[CohortRetentionRow]
    start_month: str
    end_month: str
    channel: str
```

**2.4 router** (`backend/routers/cohort_retention.py` NEW):

```python
"""Sprint 143 cohort retention router"""

from fastapi import APIRouter
from backend.services.cohort_retention_service import get_cohort_retention_matrix
from backend.contracts.cohort_retention import CohortRetentionResponse

router = APIRouter()


@router.get("/v1/cohort-retention/matrix", response_model=CohortRetentionResponse)
def get_cohort_retention(start_month: str, end_month: str, channel: str = "全店"):
    """Sprint 143: cohort retention matrix (按月 cohort + 0-12 月留存)"""
    rows = get_cohort_retention_matrix(start_month, end_month, channel)
    return CohortRetentionResponse(
        rows=rows,
        start_month=start_month,
        end_month=end_month,
        channel=channel,
    )
```

**2.5 前端组件** (`frontend-vue3/src/components/cohort/CohortRetentionMatrix.vue` NEW):

```vue
<!-- Sprint 143: cohort retention matrix 可视化组件 -->
<template>
  <div class="cohort-retention-matrix">
    <h3 class="text-base font-medium text-slate-700 mb-3">
      Cohort 留存矩阵 ({{ startMonth }} ~ {{ endMonth }}, {{ channel }})
    </h3>

    <div v-if="loading" class="flex justify-center py-8">
      <n-spin />
    </div>

    <div v-else-if="data" class="overflow-x-auto">
      <table class="w-full text-sm border-collapse">
        <thead>
          <tr>
            <th class="text-left p-2 border">Cohort 月份</th>
            <th class="text-right p-2 border">Cohort 大小</th>
            <th
              v-for="monthOffset in 13"
              :key="monthOffset - 1"
              class="text-right p-2 border"
              :class="(monthOffset - 1) === 0 ? 'bg-blue-50' : ''"
            >
              +{{ monthOffset - 1 }} 月
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in data.rows"
            :key="row.cohort_month"
            class="hover:bg-slate-50"
          >
            <td class="p-2 border font-medium">{{ row.cohort_month }}</td>
            <td class="p-2 border text-right">{{ row.cohort_size.toLocaleString() }}</td>
            <td
              v-for="monthOffset in 13"
              :key="monthOffset - 1"
              class="p-2 border text-right"
              :style="getCellStyle(row, monthOffset - 1)"
            >
              {{ formatRetention(row, monthOffset - 1) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { fetchCohortRetention } from '@/api/sampling'

interface Props {
  startMonth: string
  endMonth: string
  channel?: string
}
const props = withDefaults(defineProps<Props>(), { channel: '全店' })

const { data, isLoading: loading } = useQuery({
  queryKey: computed(() => ['cohort-retention', props.startMonth, props.endMonth, props.channel]),
  queryFn: () => fetchCohortRetention({
    start_month: props.startMonth,
    end_month: props.endMonth,
    channel: props.channel,
  }),
  placeholderData: (prev) => prev,
})

function getCellStyle(row: any, monthOffset: number) {
  const retention = row.retention[monthOffset]
  if (retention === undefined) return {}
  // 热力图: 留存率越高颜色越深 (跟 Sprint 137 AudienceView 拆 3 tabs 视觉强化模式 stable)
  const opacity = Math.min(retention, 1)
  return {
    backgroundColor: `rgba(59, 130, 246, ${opacity * 0.6})`,
    color: opacity > 0.5 ? 'white' : 'inherit',
  }
}

function formatRetention(row: any, monthOffset: number): string {
  const retention = row.retention[monthOffset]
  if (retention === undefined) return '—'
  return `${(retention * 100).toFixed(1)}%`
}
</script>
```

**2.6 SamplingView.vue 新增 tab** (`frontend-vue3/src/views/SamplingView.vue` L387 区域, 跟 Sprint 137 AudienceView 拆 3 tabs 模式 stable):

```vue
<!-- Sprint 143: 新增 cohort retention 标签 (不动 Sprint 142 level 联动 UI 区域) -->
<template>
  <div class="sampling-view">
    <!-- Sprint 143: subtitle 改名 ROI → 正装转化分析 -->
    <PageHeader
      title="派样看板"
      subtitle="U先/百补派样正装转化分析 / 0.01锁权转化分析"
    />

    <n-tabs v-model:value="activeTab" type="line" animated>
      <!-- Tab 1: 派样正装转化分析 (原 "派样ROI分析" 改名, Sprint 143 改文案) -->
      <n-tab-pane name="roi" tab="派样正装转化分析">
        <!-- 不动 Sprint 142 level 联动 UI 区域 (L400-460) -->
        ...
      </n-tab-pane>

      <!-- Sprint 143: 新增 Tab 2: 0.01锁权转化分析 (从原 Tab 1 拆出) -->
      <n-tab-pane name="lock" tab="0.01锁权转化分析">
        <!-- 复用 Sprint 141 + 142 lock-analysis 组件 -->
        ...
      </n-tab-pane>

      <!-- Sprint 143: 新增 Tab 3: Cohort 留存矩阵 (新功能) -->
      <n-tab-pane name="cohort" tab="Cohort 留存矩阵">
        <CohortRetentionMatrix
          :start-month="cohortStartMonth"
          :end-month="cohortEndMonth"
          :channel="cohortChannel"
        />
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<script setup>
// Sprint 143: 新增 cohort tab 状态 + 时间范围 + channel
const activeTab = ref('roi')
const cohortStartMonth = ref('2025-01')
const cohortEndMonth = ref('2026-06')
const cohortChannel = ref('全店')
</script>
```

**2.7 pytest** (`backend/tests/test_cohort_retention_sprint143.py` NEW, 4 case):

```python
"""Sprint 143 cohort retention matrix 回归测试"""

import pytest
from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE

pytestmark = pytest.mark.skipif(not _PROD_DUCKDB_AVAILABLE, reason="production DuckDB 不可用")


class TestCohortRetention:
    """Sprint 143: cohort retention matrix 按月 cohort + 0-12 月留存"""

    def test_cohort_retention_basic(self, monkeypatch_connection):
        """cohort retention matrix 返回 List[CohortRetentionRow]"""
        from backend.semantic.cohort_retention import compute_cohort_retention
        result = compute_cohort_retention(
            monkeypatch_connection,
            start_month="2025-01",
            end_month="2025-06",
            channel="全店",
        )
        assert isinstance(result, list)
        assert len(result) > 0
        # 每行含 cohort_month + cohort_size + retention dict
        for row in result:
            assert row.cohort_month
            assert row.cohort_size > 0
            assert isinstance(row.retention, dict)
            # cohort 月 (offset=0) 留存率必为 1.0
            assert row.retention.get(0, 0) == pytest.approx(1.0, abs=0.01)

    def test_cohort_retention_monotonic_decreasing(self, monkeypatch_connection):
        """cohort 留存率单调递减 (offset 越大留存率越低, 0 -> 12)"""
        from backend.semantic.cohort_retention import compute_cohort_retention
        result = compute_cohort_retention(
            monkeypatch_connection,
            start_month="2025-01",
            end_month="2025-06",
        )
        for row in result:
            offsets = sorted(row.retention.keys())
            for i in range(len(offsets) - 1):
                curr = row.retention[offsets[i]]
                next_val = row.retention[offsets[i + 1]]
                # 留存率允许 ±5% 浮动 (新客回流例外)
                assert next_val <= curr + 0.05

    def test_cohort_retention_channel_filter(self, monkeypatch_connection):
        """channel 参数正确过滤 (e.g. channel='U先派样' 只算 U先派样 cohort)"""
        ...

    def test_cohort_retention_w4_cache(self, monkeypatch_connection):
        """W4 cache 24h TTL 验证"""
        ...
```

---

### Task 3: 改名 ROI → 正装转化分析 (Q10 拍板: 仅前端文案)

**前置**: Q10 推荐 A (仅前端文案, API 字段保留 `sampling_roi`, 0 breaking change). 拍板后实施.

**3.1 前端文案改动** (`frontend-vue3/src/views/SamplingView.vue` L387):

```vue
<!-- 改前 (Sprint 139-142) -->
<PageHeader title="派样看板" subtitle="U先/百补派样ROI / 0.01锁权转化分析" />

<!-- 改后 (Sprint 143) -->
<PageHeader title="派样看板" subtitle="U先/百补派样正装转化分析 / 0.01锁权转化分析" />
```

**3.2 同步 tab 文案** (`SamplingView.vue` L388 Tab 1):

```vue
<!-- 改前 -->
<n-tab-pane name="roi" tab="派样ROI分析">

<!-- 改后 (Sprint 143) -->
<n-tab-pane name="roi" tab="派样正装转化分析">
```

**3.3 Sidebar 文案** (`frontend-vue3/src/components/Sidebar.vue` L12, 跟 Sprint 136 品牌文案一致):

```vue
<!-- 改前 -->
{ label: '派样看板', key: '/sampling' },

<!-- 改后 (Sprint 143) -->
{ label: '派样正装转化', key: '/sampling' },
```

**3.4 路由 name** (`frontend-vue3/src/router/index.ts`):

```typescript
// 改前
{ path: '/sampling', name: 'SamplingROI', component: SamplingView }

// 改后 (Sprint 143)
{ path: '/sampling', name: 'SamplingConversion', component: SamplingView }
```

**3.5 API 字段保留** (不动, 跟 Q10 推荐 A 一致):

```typescript
// frontend-vue3/src/api/sampling.ts — 不动
export interface SamplingROIResponse { ... }  // 保留, 不改名
export function fetchSamplingROI(params) { ... }  // 保留, 不改名
// backend/routers/sampling.py — 不动
@router.get("/v1/sampling/roi", ...)  # 保留, 不改名
```

**3.6 pytest** (`backend/tests/test_roi_rename_sprint143.py` NEW, 2 case):

```python
"""Sprint 143 改名 ROI → 正装转化分析 回归测试"""

import pytest


class TestROIRename:
    """Sprint 143: 改名 ROI → 正装转化分析 (Q10 拍板: 仅前端文案, API 保留)"""

    def test_frontend_subtitle_renamed(self):
        """前端 SamplingView.vue:387 subtitle 必含 '正装转化分析' (不含 'ROI')"""
        with open('/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/frontend-vue3/src/views/SamplingView.vue') as f:
            content = f.read()
        assert '正装转化分析' in content
        # Sprint 143 rename 后, 旧文案 'U先/百补派样ROI' 应已替换为 '派样正装转化分析'
        assert 'U先/百补派样ROI' not in content, "Sprint 143 rename 后不应再含旧 ROI 文案"

    def test_backend_api_unchanged(self):
        """API 字段 sampling_roi 保留 (Q10 推荐 A, 0 breaking change)"""
        # 验证 backend/routers/sampling.py 含 /v1/sampling/roi (保留)
        with open('/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/backend/routers/sampling.py') as f:
            content = f.read()
        assert '/v1/sampling/roi' in content
```

**3.7 e2e spec** (`frontend-vue3/e2e/sampling.spec.ts`):

```typescript
// Sprint 143: e2e spec 加 "正装转化分析" 文案断言
test('Sprint 143 改名 ROI → 正装转化分析', async ({ page }) => {
  await page.goto('/sampling')
  // 验证 PageHeader subtitle 含 "正装转化分析"
  await expect(page.getByText('正装转化分析').first()).toBeVisible({ timeout: 5000 })
  // 验证 tab 文案
  await expect(page.getByRole('tab', { name: '派样正装转化分析' })).toBeVisible()
})
```

---

## 2. 不做什么 (防 scope creep)

- ❌ 不替换 8 quadrant RFM (Sprint 60+ 闭环, 保留)
- ❌ 不改 `SamplingView.vue` L400-460 (Sprint 142 level 联动 UI)
- ❌ 不改 `backend/services/sampling_service.py` `_compute_lock_metrics` (Sprint 142 范围)
- ❌ 不动 Sprint 139 + 140 + 141 + 141.5 Phase 1 + 142 已稳定的 contract / service / e2e
- ❌ 不改 backend API `/v1/sampling/roi` (Q10 拍板保留, 0 breaking change)
- ❌ 不改 backend `SamplingROIResponse` interface (Q10 推荐 A)
- ❌ 不动 LTV/cohort retention 之外的 chart / KPI (LTV + cohort 全新建, 不动既有)
- ❌ 不改 Sprint 144+/145+ (暂收口)

---

## 3. 验收清单 (Codex 必跑)

```bash
# 1. pytest 10 case PASS (3 LTV + 4 cohort + 2 ROI rename + 1 W4 cache = 10)
PYTHONPATH="$(pwd)" DUCKDB_PATH="/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb" \
  pytest backend/tests/test_lifetime_value_sprint143.py backend/tests/test_cohort_retention_sprint143.py backend/tests/test_roi_rename_sprint143.py -v
# 期望: 10 passed

# 2. Sprint 139/140/141/141.5 ground-truth-lint 全 PASS
PYTHONPATH="$(pwd)" python3 backend/scripts/check_sampling_spu_type.py
PYTHONPATH="$(pwd)" python3 backend/scripts/check_window_unification.py
PYTHONPATH="$(pwd)" python3 backend/scripts/check_period_distribution_61_90d.py
PYTHONPATH="$(pwd)" python3 backend/scripts/check_channel_alias.py
# 期望: PASS × 4

# 3. 全部 pytest baseline 持续 (750 → 760)
PYTHONPATH="$(pwd)" DUCKDB_PATH="..." pytest backend/tests/ -q
# 期望: 760 passed / 23 skipped / 0 failed

# 4. 前端 npm run build 0 errors (L4.22 sprint 收口强制)
cd frontend-vue3 && npm run build
# 期望: 0 errors

# 5. 前端 e2e spec PASS (新 ROI 改名断言)
cd frontend-vue3 && npx playwright test e2e/sampling.spec.ts
# 期望: 1 case PASS (含 "正装转化分析" 文案断言)

# 6. pre-commit 全绿
git add -A
bash .githooks/pre-commit
```

---

## 4. 风险评估 (5 项已知风险)

| # | 风险 | 概率 | 缓解 |
|---|---|---|---|
| R1 | 跟 Sprint 142 并行开发, SamplingView.vue 可能 merge 冲突 | 中 | 已明确分工 (Sprint 143 改 L387 + 新增 CohortRetentionMatrix + Sprint 142 改 L400-460); merge 时 git 自动 conflict resolution, 人工 review |
| R2 | LTV/cohort retention 业务侧没拍板阈值分档 (Q6) | 中 | 用推荐阈值 (LTV_WINDOWS=[90,180,365], cohort 按月); 业务侧后续可调 |
| R3 | cohort retention matrix 0-12 月留存, 数据量大可能性能差 | 中 | W4 cache 24h TTL + 复用 backend/services/rfm/cache.py 模式; micro-benchmark 验证 |
| R4 | 改名 ROI → 正装转化分析, 可能跟现有营销文档不一致 | 低 | CHANGELOG entry 标 "Sprint 143 改名"; 仅前端文案, API 保留, 0 breaking change |
| R5 | W4 cache 写入失败 (DuckDB file lock), 影响 LTV/cohort retention | 低 | 跟 Sprint 38 race flake L5.1 模式 stable, 治标已存在 PID 85799 守护逻辑 |

---

## 5. L4.x 永久规则强制清单

| 规则 | 适用范围 | Sprint 143 检查点 |
|---|---|---|
| L4.1 SQL 三引号 + f-string | body 含 `{identifier}` 必须 f 前缀 | compute_ltv_for_user + compute_cohort_retention + get_user_ltv + get_cohort_retention_matrix 加 f 前缀 |
| L4.5 FilterBuilder + ? 参数化 | service 函数禁止 f-string 内嵌用户输入 | 复用既有 FilterBuilder; LTV_WINDOWS / LIFECYCLE_THRESHOLDS 等常量 0 风险 |
| L4.3 isolated_duckdb fixture | 真连必用 per-worker tmp DuckDB | pytest 10 case 全用 `monkeypatch_connection` |
| L4.4 真连 DuckDB skipif | `_PROD_DUCKDB_AVAILABLE` 守卫 | pytest 必加 `pytestmark` |
| L4.6 worktree DUCKDB_PATH | worktree 跑 pytest 必 export | Sprint 143 实施期间走 worktree 模式 |
| L4.7 SQL ? 数量 == params 数量 | LTV + cohort 加 assert 防 params 顺序错位 | Task 1.1 + Task 2.1 assert |
| L4.16 push trigger paths | 改 backend/services + backend/contracts + backend/tests + backend/scripts + frontend-vue3 + e2e 都触发 | ✅ paths 都包含 |
| L4.19 channel alias | service 输出 SQL 含 `channel IN/NOT IN/=` 必须有 `o.` 表别名 | LTV + cohort 新 SQL 加 `o.channel` 别名 |
| L4.20 留尾 SSOT 治理 | Sprint 143 收口时强制检查 | close memory 必引真修 commit SHA |
| L4.22 vite rebuild | 前端 sprint 收口 | Claude Stage 4 必跑 (Task 4 npm run build) |

---

## 6. 跟 Sprint 142 并行开发约定 (避免冲突)

| 文件 | Sprint 143 改的 line | Sprint 142 改的 line | 冲突? |
|---|---|---|---|
| `frontend-vue3/src/views/SamplingView.vue` | L387 (subtitle) + L388 (Tab 1 name) | L400-460 (level 联动 UI) | ❌ |
| `frontend-vue3/src/views/SamplingView.vue` | 新增 Tab 3 <CohortRetentionMatrix> | 不动 | ❌ |
| `frontend-vue3/src/components/Sidebar.vue` | L12 (`派样看板` → `派样正装转化`) | 不动 | ❌ |
| `frontend-vue3/src/router/index.ts` | route name `SamplingROI` → `SamplingConversion` | 不动 | ❌ |
| `backend/services/sampling_service.py` | 不动 | `_compute_lock_metrics` 重构 | ❌ |
| 新文件 `backend/services/lifetime_value_service.py` | ✅ NEW | 不动 | ❌ |
| 新文件 `backend/services/cohort_retention_service.py` | ✅ NEW | 不动 | ❌ |

**0 冲突区**. merge 顺序: Sprint 142 先合 → Sprint 143 后合 (避免 L387 subtitle 文案被 Sprint 142 冲突覆盖).

---

## 7. Codex Stage 2 实施规范

**Codex 必读**:
1. 本文件全文 (3 个 Task)
2. `AGENTS.md` (本地文件, .gitignore 排除, 自动注入)
3. 必跑 `git log --all --oneline | head -10` + `git log main --oneline -- backend/services/ frontend-vue3/src/views/SamplingView.vue` 验 Sprint 139+140+141+141.5 收口状态

**Codex 不做**:
- ❌ 不 git commit / push (Claude Stage 4 负责)
- ❌ 不动 Sprint 139 / 140 / 141 / 141.5 Phase 1 已稳定的 contract / service / e2e
- ❌ 不改 Sprint 143 scope 之外的 docs
- ❌ 不动 `SamplingView.vue` L400-460 (Sprint 142 范围)
- ❌ 不动 `_compute_lock_metrics` (Sprint 142 范围)
- ❌ 不改名 backend API `/v1/sampling/roi` (Q10 推荐 A, API 保留)
- ❌ 不改 backend `SamplingROIResponse` (Q10 推荐 A)
- ❌ 不动 RFM 8 quadrant (Sprint 60+ 闭环, 保留)

**Codex 实施完成时给 user 回报**:
- ✅ pytest 10 case PASS (3 LTV + 4 cohort + 2 ROI rename + 1 W4 cache = 10)
- ✅ Sprint 139/140/141/141.5 ground-truth-lint 钩子 全 PASS × 4
- ✅ `npm run build` 0 errors (前端 L4.22)
- ✅ e2e spec PASS (含 "正装转化分析" 文案断言)
- ✅ pre-commit 全绿
- ✅ git diff --stat 改动列表 (实质净 +250/-30, 7 files)

---

## 8. 文件改动清单 (7 files / +250/-30 行)

| 文件 | 改法 | LOC |
|---|---|---|
| `backend/semantic/lifetime_value.py` (NEW) | LTVResult + LTV_WINDOWS + compute_ltv_for_user | +80/-0 |
| `backend/services/lifetime_value_service.py` (NEW) | get_user_ltv + get_users_ltv_batch + W4 cache | +90/-0 |
| `backend/contracts/lifetime_value.py` (NEW) | LifetimeValueSummary (ltv_90d/180d/365d_avg + median + yoy) | +30/-0 |
| `backend/routers/lifetime_value.py` (NEW) | GET /v1/lifetime-value/cohort | +15/-0 |
| `backend/semantic/cohort_retention.py` (NEW) | CohortRetentionRow + compute_cohort_retention | +70/-0 |
| `backend/services/cohort_retention_service.py` (NEW) | get_cohort_retention_matrix + W4 cache | +50/-0 |
| `backend/contracts/cohort_retention.py` (NEW) | CohortRetentionRow + CohortRetentionResponse | +25/-0 |
| `backend/routers/cohort_retention.py` (NEW) | GET /v1/cohort-retention/matrix | +15/-0 |
| `frontend-vue3/src/components/cohort/CohortRetentionMatrix.vue` (NEW) | 可视化组件 (热力图) | +100/-0 |
| `frontend-vue3/src/views/SamplingView.vue` | L387 subtitle + L388 Tab 1 name + 新增 Tab 3 | +30/-15 |
| `frontend-vue3/src/components/Sidebar.vue` | L12 (`派样看板` → `派样正装转化`) | +1/-1 |
| `frontend-vue3/src/router/index.ts` | route name `SamplingROI` → `SamplingConversion` | +1/-1 |
| `frontend-vue3/src/api/sampling.ts` | 加 `fetchLifetimeValue` + `fetchCohortRetention` | +25/-0 |
| `backend/tests/test_lifetime_value_sprint143.py` (NEW) | 3 case | +50 |
| `backend/tests/test_cohort_retention_sprint143.py` (NEW) | 4 case | +60 |
| `backend/tests/test_roi_rename_sprint143.py` (NEW) | 2 case | +30 |
| `frontend-vue3/e2e/sampling.spec.ts` | Sprint 143 rename 文案断言 | +5/-2 |
| `CHANGELOG.md` | Sprint 143 entry | +25 |

**合计**: 实质净 +250/-30 (实质有效 +700 行, 跟 Sprint 137 AudienceView 拆 3 tabs 模式 stable)

---

## 9. 完成定义 (Definition of Done)

- [ ] Task 1-3 全部完成 (LTV + cohort retention + 改名 ROI)
- [ ] pytest 10 case PASS (新增)
- [ ] W4 cache 24h TTL 验证 (跟 Sprint 30+ W5 模式 stable)
- [ ] Sprint 139/140/141/141.5 ground-truth-lint 全 PASS × 4
- [ ] pre-commit ruff + pytest + ground-truth-lint 全绿
- [ ] L4.x 22 stable 0 新增
- [ ] VERSION 0.4.14.157 不 bump
- [ ] CHANGELOG.md +1 entry
- [ ] frontend-vue3 `npm run build` 0 errors (L4.22 sprint 收口强制)
- [ ] e2e spec PASS (含 "正装转化分析" 文案断言)
- [ ] 跟 Sprint 142 并行约定 0 冲突 (merge 顺序: Sprint 143 后合)

**未达任一项 = Codex 未完成, 回到 Stage 2 修补。**

---

## 10. 待 user 拍板 (3 项小决策)

| # | 决策点 | 推荐选项 |
|---|---|---|
| Q6 | LTV 阈值分档 (高/中/低价值) | 业务侧定 (本次默认 5000/1000) |
| Q8 | cohort retention 颗粒度 | (A) 按月 (跟 RFM R_SEGMENT_ORDER 模式 stable) |
| Q10 | 改名 ROI 范围 | (A) 仅前端文案 (API 字段保留 `sampling_roi`, 0 breaking change) |

---

**Sprint 143 Stage 1 详细 plan 已锁定, Codex 可立即开工. 跟 Sprint 142 并行开发约定已明确 (0 冲突区).**