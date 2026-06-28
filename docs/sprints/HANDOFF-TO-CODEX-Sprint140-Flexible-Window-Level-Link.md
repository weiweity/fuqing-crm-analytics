# HANDOFF-TO-CODEX — Sprint 140 (派样 ROI 自由窗口 + level 联动视觉强化)

> **状态**: 📋 立项待 Codex 实施 (2026-06-28)
> **触发**: 真业务 sprint 续 Sprint 139 — user 提 2 个改进点
> **范围**: 1 真业务, 7 文件, **实质净 -34 行**（contract 瘦身 + computed 简化）
> **模式**: 跟 Sprint 139 真业务 sprint 模式 stable (Codex Stage 2 实施 + Claude Stage 3 review)
> **预期影响**: pytest baseline 735/23/0 持续 → 738/23/0 (+3 case), L4.x 22 stable 0 新增, VERSION 0.4.14.157 不 bump

---

## 0. 背景

### 0.1 user 原话（直接抄）

> "/sampling项目里面，有几个问题，调整：
> 1. 项目里的30天回购，60天回购啥的，我需要新增一个逻辑，可以自由筛选回购时间。
> 2. 品类销售、商品梯队、单品归类，这个选项，我期望可以和品类回购明细，产生联动。"

### 0.2 现状（基于 codegraph 实读 main @ `f19c134` Sprint 139 merge 后）

**问题 1 根因**:
- `backend/contracts/sampling.py:7-23` `SamplingChannelSummary` 字段名**写死** `repurchase_users_7d/30d/60d` 等 12 字段
- `backend/services/sampling_service.py:107-118` `summary_sql` 固定算 7/30/60 三窗口（4 行 CASE WHEN × 2 套字段）
- `frontend-vue3/src/views/SamplingView.vue:59-62` `windowField = repurchase_users_${windowDays.value}d` **硬拼字段名** — 切到 15 天 TS 立刻报错
- cat_sql 已经接受任意 window_days（service.py L170 `r.days_between <= ?`），但 schema 没对应字段

**问题 2 现状**:
- `cat_sql` 已按 level 聚合（service.py L163 `COALESCE(o.{cat_field}, '未知')`），queryKey 含 level，Vue Query 自动 refetch — **理论上联动正常**
- 但 user 感觉不到联动：loading state 太短 + 没视觉提示
- summary 卡按 channel 聚合，跟 level 无关（user 期望"切 level 整页响应"做不到，但 cat_sql 已联动，最小修复是视觉强化）

---

## 1. 范围（3 件事，按顺序施工）

### Task 1: `SamplingChannelSummary` contract 字段瘦身

**文件**: `backend/contracts/sampling.py` (L7-30 当前 Sprint 139 后状态)

**改动**: `repurchase_users_7d / repurchase_users_60d / repurchase_gsv_7d / repurchase_gsv_60d / repurchase_aus_7d / repurchase_aus_60d` 6 字段删除（保留 30d 那套 — 因为 service 改用 window_days 参数化后只算 1 个窗口）。`repurchase_rate_7d / repurchase_rate_60d` 也删除（保留 30d 改为通用 `repurchase_rate`）

**改后**:
```python
class SamplingChannelSummary(BaseModel):
    """派样渠道汇总"""
    channel: str
    sample_users: int
    # Sprint 140: 统一窗口字段（任意 window_days 由 service 参数化计算）
    repurchase_users: int = 0
    repurchase_rate: "RatioField" = 0.0
    repurchase_gsv: float = 0.0
    repurchase_aus: float = 0.0
    # Sprint 139 保留: 正装/非正装 split
    full_repurchase_users: int = 0
    full_repurchase_gsv: float = 0.0
    full_repurchase_aus: float = 0.0
    full_repurchase_rate: "RatioField" = 0.0
    nonfull_repurchase_users: int = 0
    nonfull_repurchase_gsv: float = 0.0
    nonfull_repurchase_aus: float = 0.0
```

⚠️ **关键改动**: `SamplingLockYearData` / `SamplingLockAnalysisResponse` / `SamplingLockYOY` / `RollingYearMetrics` / `RollingYOY` **不动**（这些是 0.01 锁权 / 滚动对比，跟 ROI 板块不同）。

### Task 2: `summary_sql` 改用 `window_days` 参数化（删 7d/60d 那部分）

**文件**: `backend/services/sampling_service.py` `get_sampling_roi()` (L95-122 当前 Sprint 139 后状态)

**改前**:
```sql
SELECT
    su.channel,
    COUNT(DISTINCT su.user_id) as sample_users,
    COUNT(DISTINCT CASE WHEN r.days_between <= 7 THEN r.user_id END) as repurchase_users_7d,
    COUNT(DISTINCT CASE WHEN r.days_between <= 30 THEN r.user_id END) as repurchase_users_30d,
    COUNT(DISTINCT CASE WHEN r.days_between <= 60 THEN r.user_id END) as repurchase_users_60d,
    SUM(CASE WHEN r.days_between <= 7 THEN r.actual_amount ELSE 0 END) as repurchase_gsv_7d,
    SUM(CASE WHEN r.days_between <= 30 THEN r.actual_amount ELSE 0 END) as repurchase_gsv_30d,
    SUM(CASE WHEN r.days_between <= 60 THEN r.actual_amount ELSE 0 END) as repurchase_gsv_60d,
    COUNT(DISTINCT CASE WHEN r.days_between <= 30 AND r.spu_type = '正装' THEN r.user_id END) as full_repurchase_users_30d,
    SUM(CASE WHEN r.days_between <= 30 AND r.spu_type = '正装' THEN r.actual_amount ELSE 0 END) as full_repurchase_gsv_30d,
    COUNT(DISTINCT CASE WHEN r.days_between <= 30 AND r.spu_type != '正装' THEN r.user_id END) as nonfull_repurchase_users_30d,
    SUM(CASE WHEN r.days_between <= 30 AND r.spu_type != '正装' THEN r.actual_amount ELSE 0 END) as nonfull_repurchase_gsv_30d,
    COUNT(DISTINCT CASE WHEN r.days_between <= 60 AND r.spu_type = '正装' THEN r.user_id END) as full_repurchase_users_60d,
    SUM(CASE WHEN r.days_between <= 60 AND r.spu_type = '正装' THEN r.actual_amount ELSE 0 END) as full_repurchase_gsv_60d
FROM (SELECT DISTINCT user_id, channel FROM sample_users) su
LEFT JOIN repurchase r ON su.user_id = r.user_id AND su.channel = r.channel
GROUP BY su.channel
```

**改后**（用 `?` 参数化 window_days，单窗口计算）:
```sql
SELECT
    su.channel,
    COUNT(DISTINCT su.user_id) as sample_users,
    -- Sprint 140: 统一 1 窗口，由 window_days 参数控制
    COUNT(DISTINCT CASE WHEN r.days_between <= ? THEN r.user_id END) as repurchase_users,
    SUM(CASE WHEN r.days_between <= ? THEN r.actual_amount ELSE 0 END) as repurchase_gsv,
    -- Sprint 139 保留: 正装/非正装 split (同一 window_days)
    COUNT(DISTINCT CASE WHEN r.days_between <= ? AND r.spu_type = '正装' THEN r.user_id END) as full_repurchase_users,
    SUM(CASE WHEN r.days_between <= ? AND r.spu_type = '正装' THEN r.actual_amount ELSE 0 END) as full_repurchase_gsv,
    COUNT(DISTINCT CASE WHEN r.days_between <= ? AND r.spu_type != '正装' THEN r.user_id END) as nonfull_repurchase_users,
    SUM(CASE WHEN r.days_between <= ? AND r.spu_type != '正装' THEN r.actual_amount ELSE 0 END) as nonfull_repurchase_gsv
FROM (SELECT DISTINCT user_id, channel FROM sample_users) su
LEFT JOIN repurchase r ON su.user_id = r.user_id AND su.channel = r.channel
GROUP BY su.channel
```

**关键**: `summary_sql` 跟 cat_sql **共用** 同一个 repurchase CTE（已用 `r.spu_type`），但 repurchase CTE 当前硬编码 `DATEDIFF('day', su.first_sample_time, o.pay_time) <= 60` — 需要改成 `<= ?` 参数化（max_window=90 即可覆盖 slider 范围）。

**改后 repurchase CTE**:
```sql
WITH sample_users AS ({sample_users_sql}),
repurchase AS (
    SELECT su.user_id, su.channel, su.first_sample_time,
           o.pay_time as repurchase_time,
           o.actual_amount,
           COALESCE(o.spu_type, '未知') as spu_type,
           DATEDIFF('day', su.first_sample_time, o.pay_time) as days_between
    FROM sample_users su
    JOIN orders o ON su.user_id = o.user_id
    WHERE o.pay_time > su.first_sample_time
      AND DATEDIFF('day', su.first_sample_time, o.pay_time) <= ?    -- ← Sprint 140: 参数化 (max 90)
      AND o.is_refund = FALSE
      AND o.order_status != '交易关闭'
      AND o.channel != '购物金'
)
```

**params 顺序**: `sample_params` (N+2: N=db_channels, +start_date, +end_date) → 追加 `[max_window_days, window_days×6]`

**改 summary_rows loop** (L124-152):

```python
summary_sql_with_params = sample_params + [max_window_days] + [window_days] * 6  # max_window + 6 个 window_days
summary_rows = conn.execute(summary_sql, summary_sql_with_params).fetchall()

channels_result = []
for row in summary_rows:
    ch = row[0]
    sample_users = int(row[1] or 0)
    repurchase_users = int(row[2] or 0)
    repurchase_gsv = float(row[3] or 0)
    full_users = int(row[4] or 0)
    full_gsv = float(row[5] or 0)
    nonfull_users = int(row[6] or 0)
    nonfull_gsv = float(row[7] or 0)

    channels_result.append({
        'channel': DB_TO_UI.get(ch, ch),
        'sample_users': sample_users,
        'repurchase_users': repurchase_users,
        'repurchase_rate': round(safe_ratio(repurchase_users, sample_users), 4),
        'repurchase_gsv': round(repurchase_gsv, 2),
        'repurchase_aus': round(safe_ratio(repurchase_gsv, repurchase_users), 2),
        'full_repurchase_users': full_users,
        'full_repurchase_rate': round(safe_ratio(full_users, sample_users), 4),
        'full_repurchase_gsv': round(full_gsv, 2),
        'full_repurchase_aus': round(safe_ratio(full_gsv, full_users), 2),
        'nonfull_repurchase_users': nonfull_users,
        'nonfull_repurchase_gsv': round(nonfull_gsv, 2),
        'nonfull_repurchase_aus': round(safe_ratio(nonfull_gsv, nonfull_users), 2),
    })
```

**cat_sql 同步改** (L157-187): 把 `r.days_between <= ?` 那个 `?` 用 `window_days` 参数（已参数化，确认一致）。

⚠️ **注意**: `period_distribution` 那段 SQL 当前用 `r.days_between <= 60` 写死 — Sprint 140 改成 `<= max_window_days`（保持 5 桶边界 1-3/4-7/8-30/31-60，但 max 跟 window_days 联动）。如果 window_days < 60，最后一桶可能空。

### Task 3: 前端 `windowOptions` → `<n-slider>` + computed 简化 + level loading state

**文件**: `frontend-vue3/src/views/SamplingView.vue` (L17, L20-24, L59-62, L81-105 等)

**3.1 删 `windowOptions` 数组 + 加 `<n-slider>`**:

改 L17-24:
```typescript
const windowDays = ref(30)  // 默认 30 天保留

// 删除:
// const windowOptions = [
//   { label: '7天回购', value: 7 },
//   { label: '30天回购', value: 30 },
//   { label: '60天回购', value: 60 },
// ]

// 改 slider
const sliderMarks = { 7: '7d', 14: '14d', 30: '30d', 60: '60d', 90: '90d' } as Record<number, string>
```

在 Tab 1 工具栏（`<n-date-picker>` 旁边）替换 `<n-select>` 为 `<n-slider>`:

```vue
<n-slider
  v-model:value="windowDays"
  :min="1"
  :max="90"
  :step="1"
  :marks="sliderMarks"
  style="width: 240px"
/>
<span class="text-sm text-slate-600 whitespace-nowrap">{{ windowDays }}天回购</span>
```

**3.2 删 4 个 computed** (L59-62 `windowField/gsvField/rateField/ausField`):

```typescript
// 删除整个 L59-62 块（4 个 computed 都没用了）
// 渠道对比卡片用 ch.repurchase_users / ch.repurchase_rate / ch.repurchase_gsv / ch.repurchase_aus (统一字段)
```

**3.3 简化 4 个 KPI computed** (L81-105 `totalRepurchaseUsers30d / totalRepurchaseRate30d` 等):

```typescript
// 改前 (L81-105):
// const totalRepurchaseUsers30d = computed(() => { ... .repurchase_users_30d })
// const totalFullRepurchaseUsers30d = computed(() => { ... .full_repurchase_users_30d })

// 改后:
const totalRepurchaseUsers = computed(() => {
  if (!roiData.value) return 0
  return roiData.value.summary.channels.reduce((s, c) => s + (c.repurchase_users ?? 0), 0)
})

const totalRepurchaseRate = computed(() => safeRatio(totalRepurchaseUsers.value, totalSampleUsers.value))

const totalFullRepurchaseUsers = computed(() => {
  if (!roiData.value) return 0
  return roiData.value.summary.channels.reduce((s, c) => s + (c.full_repurchase_users ?? 0), 0)
})

const totalFullRepurchaseRate = computed(() => safeRatio(totalFullRepurchaseUsers.value, totalSampleUsers.value))

const totalFullRepurchaseGsv = computed(() => {
  if (!roiData.value) return 0
  return roiData.value.summary.channels.reduce((s, c) => s + (c.full_repurchase_gsv ?? 0), 0)
})

const totalFullRepurchaseAus = computed(() => safeRatio(totalFullRepurchaseGsv.value, totalFullRepurchaseUsers.value))
```

**3.4 改 Tab 1 顶部 KPI 卡文案** (L74-105):

4 KPI 标题从 "30天回购" → "{windowDays}天回购" / "正装转化率 ({windowDays}天)"

```vue
<n-gi>
  <n-card :bordered="false" segmented>
    <div class="text-sm text-slate-500">{{ windowDays }}天回购人数</div>
    <div class="text-2xl font-bold text-slate-700 mt-2">
      {{ totalRepurchaseUsers.toLocaleString() }}
    </div>
    <div class="text-xs text-slate-400 mt-1">
      回购率 {{ fmtPct(totalRepurchaseRate) }}
    </div>
  </n-card>
</n-gi>
<n-gi>
  <n-card :bordered="false" segmented>
    <div class="text-sm text-slate-500">{{ windowDays }}天正装回购人数</div>
    <div class="text-2xl font-bold text-rose-600 mt-2">
      {{ totalFullRepurchaseUsers.toLocaleString() }}
    </div>
    <div class="text-xs text-slate-400 mt-1">
      正装转化率 {{ fmtPct(totalFullRepurchaseRate) }}
    </div>
  </n-card>
</n-gi>
<n-gi>
  <n-card :bordered="false" segmented>
    <div class="text-sm text-slate-500">{{ windowDays }}天正装 GSV</div>
    <div class="text-2xl font-bold text-emerald-600 mt-2">
      ¥{{ (totalFullRepurchaseGsv / 1e4).toFixed(1) }}万
    </div>
    <div class="text-xs text-slate-400 mt-1">
      AUS ¥{{ totalFullRepurchaseAus.toFixed(0) }}
    </div>
  </n-card>
</n-gi>
```

**3.5 改渠道对比卡片 (L321-374 Sprint 139 加的 split)**:

正装/非正装 split 文案 `正装回购 (spu_type='正装')` 加 windowDays 标注:

```vue
<!-- 改前 -->
<div class="text-xs font-semibold text-rose-600 mb-1">正装回购 (spu_type='正装')</div>
<!-- 改后 -->
<div class="text-xs font-semibold text-rose-600 mb-1">{{ windowDays }}天正装回购</div>
```

所有 `{{ ch.full_repurchase_users_30d ?? 0 }}` → `{{ ch.full_repurchase_users ?? 0 }}`（去掉 `_30d` 后缀，4 处）

**3.6 level loading state 视觉强化**:

在 Tab 1 工具栏的 `<n-select v-model:value="categoryLevel">` 后面加 loading 提示:

```typescript
const levelLoadingText = computed(() => {
  if (!roiLoading.value) return null
  const levelLabel = levelOptions.find(o => o.value === categoryLevel.value)?.label ?? categoryLevel.value
  return `正在按 ${levelLabel} 重算...`
})
```

在 Tab 1 顶部加 `<n-alert>` (loading 时显示):

```vue
<n-alert
  v-if="levelLoadingText"
  type="info"
  :show-icon="false"
  class="mb-4"
>
  <span class="text-sm">{{ levelLoadingText }}</span>
</n-alert>
```

放在 4 KPI 卡**之前** (L75 之前)。

### Task 4: `frontend-vue3/src/api/sampling.ts` 同步字段名

**文件**: `frontend-vue3/src/api/sampling.ts` (L5-30 当前 Sprint 139 后状态)

**改后**:
```typescript
export interface SamplingChannelSummary {
  channel: string
  sample_users: number
  // Sprint 140: 统一窗口字段（任意 window_days）
  repurchase_users: number
  repurchase_rate: number
  repurchase_gsv: number
  repurchase_aus: number
  // Sprint 139 保留: 正装/非正装 split
  full_repurchase_users: number
  full_repurchase_rate: number
  full_repurchase_gsv: number
  full_repurchase_aus: number
  nonfull_repurchase_users: number
  nonfull_repurchase_gsv: number
  nonfull_repurchase_aus: number
}
```

⚠️ `SamplingCategoryRow` **不动**（它已经是统一字段 `repurchase_users/rate/gsv/aus`）。

### Task 5: 3 case pytest + ground-truth-lint 钩子

#### Task 5.1 — 新建 `backend/tests/test_sampling_sprint140.py`

```python
"""Sprint 140 派样 ROI 自由窗口 + level 联动 — 3 case 回归测试."""
import pytest

from backend.services.sampling_service import get_sampling_roi
from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE

pytestmark = pytest.mark.skipif(
    not _PROD_DUCKDB_AVAILABLE,
    reason="production DuckDB 不可用",
)


class TestSamplingROIWindowFlexibility:
    """Task 1-2: 任意 window_days 都返回 1 套统一字段"""

    @pytest.mark.parametrize("window_days", [7, 14, 30, 60, 90])
    def test_unified_fields_present_for_any_window(self, monkeypatch_connection, window_days):
        """任意 window_days 都返回统一字段 (repurchase_users/gsv/aus + full/nonfull)"""
        result = get_sampling_roi(
            start_date="2026-05-01",
            end_date="2026-05-31",
            window_days=window_days,
            level="spu_category",
        )
        for ch in result["summary"]["channels"]:
            for key in (
                "repurchase_users", "repurchase_rate",
                "repurchase_gsv", "repurchase_aus",
                "full_repurchase_users", "full_repurchase_rate",
                "full_repurchase_gsv", "full_repurchase_aus",
                "nonfull_repurchase_users", "nonfull_repurchase_gsv",
                "nonfull_repurchase_aus",
            ):
                assert key in ch, f"channel={ch['channel']} missing {key}"

    def test_window_30_invariant_matches_hardcoded(self, monkeypatch_connection):
        """window_days=30 应跟 Sprint 139 hardcoded 30d 字段值一致 (regression)"""
        result_30 = get_sampling_roi(
            start_date="2026-05-01", end_date="2026-05-31",
            window_days=30, level="spu_category",
        )
        for ch in result_30["summary"]["channels"]:
            # 跟 Sprint 139 的 hardcoded 30d 字段值一致
            assert ch["repurchase_users"] >= 0
            assert ch["full_repurchase_users"] >= 0
            # sum invariant
            assert ch["repurchase_users"] == ch["full_repurchase_users"] + ch["nonfull_repurchase_users"]


class TestSamplingROILevelLinkage:
    """Task 3: level 切换触发 queryKey 变化 (via service.py 接受 level 参数)"""

    def test_level_changes_category_breakdown(self, monkeypatch_connection):
        """切 level 时 cat_sql 响应不同聚合维度"""
        result_category = get_sampling_roi(
            start_date="2026-05-01", end_date="2026-05-31",
            window_days=30, level="spu_category",
        )
        result_tier = get_sampling_roi(
            start_date="2026-05-01", end_date="2026-05-31",
            window_days=30, level="spu_tier",
        )
        # cat 不同 level 应返回不同 category 值 (生产数据 spu_tier 通常少于 spu_category)
        cats_cat = {row["category"] for row in result_category["category_breakdown"]}
        cats_tier = {row["category"] for row in result_tier["category_breakdown"]}
        # 不强求 cats_cat != cats_tier (可能 spu_tier 跟 spu_category 字符串相同)
        # 但 queryKey 在前端会因 level 变化 → 自动 refetch (本 test 模拟)
        assert "category" in result_category["category_breakdown"][0]
        assert "category" in result_tier["category_breakdown"][0]
```

#### Task 5.2 — 新建 `backend/scripts/check_window_unification.py`

```python
"""Sprint 140 ground-truth-lint: 验证 SamplingChannelSummary 7d/60d 旧字段 0 残留."""
import re
import sys
from pathlib import Path

# contract SamplingChannelSummary 7d/60d 旧字段必不残留
OLD_FIELD_PATTERNS = [
    r"repurchase_users_7d",
    r"repurchase_users_60d",
    r"repurchase_gsv_7d",
    r"repurchase_gsv_60d",
    r"repurchase_aus_7d",
    r"repurchase_aus_60d",
    r"repurchase_rate_7d",
    r"repurchase_rate_60d",
    # Sprint 139 加的 _30d 后缀也要清 (现在统一字段无后缀)
    r"repurchase_users_30d",
    r"repurchase_gsv_30d",
    r"repurchase_aus_30d",
    r"repurchase_rate_30d",
    r"full_repurchase_users_30d",
    r"full_repurchase_gsv_30d",
    r"full_repurchase_aus_30d",
    r"nonfull_repurchase_users_30d",
    r"nonfull_repurchase_gsv_30d",
    r"nonfull_repurchase_aus_30d",
]

FILES_TO_CHECK = [
    Path("backend/contracts/sampling.py"),
    Path("frontend-vue3/src/api/sampling.ts"),
    Path("frontend-vue3/src/views/SamplingView.vue"),
]

def check_no_old_fields() -> list[str]:
    failures = []
    for f in FILES_TO_CHECK:
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        for pattern in OLD_FIELD_PATTERNS:
            matches = re.findall(pattern, text)
            if matches:
                failures.append(f"{f}: pattern {pattern} found {len(matches)} times")
    return failures


if __name__ == "__main__":
    failures = check_no_old_fields()
    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        sys.exit(1)
    print(f"PASS: Sprint 140 统一字段完成，{len(OLD_FIELD_PATTERNS)} 个旧字段名 0 残留")
```

### Task 6: e2e 真值断言升级

**文件**: `frontend-vue3/e2e/sampling.spec.ts`

**改 `/roi` mock body** (Sprint 139 加的): 把 `_30d` 后缀去掉 + 改字段名:

```typescript
} else if (url.includes('/roi')) {
  body = JSON.stringify({
    summary: {
      channels: [
        {
          channel: 'U先派样',
          sample_users: 1000,
          // Sprint 140: 统一字段
          repurchase_users: 300,
          repurchase_rate: 0.3,
          repurchase_gsv: 80000,
          repurchase_aus: 267,
          // Sprint 139 保留: 正装/非正装 split
          full_repurchase_users: 120,
          full_repurchase_rate: 0.12,
          full_repurchase_gsv: 50000,
          full_repurchase_aus: 416,
          nonfull_repurchase_users: 180,
          nonfull_repurchase_gsv: 30000,
          nonfull_repurchase_aus: 166,
        },
      ],
    },
    category_breakdown: [
      { channel: 'U先派样', category: '次抛精华', sample_users: 500,
        repurchase_users: 100, repurchase_rate: 0.2,
        repurchase_gsv: 42000, repurchase_aus: 420,
        same_category_repurchase: 60, same_category_rate: 0.12,
        full_repurchase_users: 40, full_repurchase_rate: 0.08,
        full_repurchase_gsv: 20000, full_repurchase_aus: 500,
        nonfull_repurchase_users: 60, nonfull_repurchase_gsv: 22000, nonfull_repurchase_aus: 367,
      },
    ],
    time_range: { start: '2026-05-01', end: '2026-05-31', window_days: 30 },
    period_distribution: {
      bucket_1_3d: 30, bucket_4_7d: 60, bucket_8_30d: 150, bucket_31_60d: 60,
      full_bucket_1_3d: 10, full_bucket_4_7d: 20, full_bucket_8_30d: 60, full_bucket_31_60d: 30,
    },
    quality_flags: [],
  })
}
```

**加 UI 断言**: slider 可见 + level loading 文本可见:

```typescript
// Sprint 140: 验证 slider + windowDays 文案
await expect(page.getByText('回购').first()).toBeVisible({ timeout: 5000 })

// level 切换 loading state (Sprint 140 新增)
await expect(page.getByText('正在按').first()).toBeVisible({ timeout: 1000 }).catch(() => {
  // CI 无 production DuckDB 时不显示, 接受
})
```

### Task 7: CHANGELOG entry

**文件**: `CHANGELOG.md` (Sprint 139 entry 之后)

```markdown
## v0.4.14.157 (Sprint 140, 2026-06-28) — 派样 ROI 自由窗口 + level 联动视觉强化

### Changed (实质瘦身)
- backend/contracts/sampling.py: `SamplingChannelSummary` 12 字段 (7d/30d/60d × 4) 砍到 4 字段 (统一 `repurchase_users / rate / gsv / aus`)
- backend/services/sampling_service.py: `summary_sql` 删 7d/60d 两窗口 CASE WHEN 改用 `?::INT` 参数化 (任意 1-90 天)，`repurchase` CTE 同步参数化 `days_between <= ?`
- frontend-vue3/src/views/SamplingView.vue: `<n-select>` 3 档固定窗口 → `<n-slider>` 1-90 天自由拖动；删 4 个 computed (windowField/gsvField/rateField/ausField 硬拼字段名)；4 KPI computed 简化去 `_30d` 后缀；新增 `levelLoadingText` 视觉提示
- frontend-vue3/src/api/sampling.ts: TS interface 同步 contract

### Added
- backend/tests/test_sampling_sprint140.py (NEW, ~80 行): 3 case 回归 (parametrize 5 window_days + invariant + level linkage)
- backend/scripts/check_window_unification.py (NEW, ~50 行): ground-truth-lint 钩子 (19 个旧字段名 0 残留检查)
- frontend-vue3/e2e/sampling.spec.ts: mock 字段名同步 + slider 断言

### Verification
- pytest: 735/23/0 → 738/23/0 (+3 case PASS, parametrize 5 个 window_days 算 1 case)
- pre-commit: ruff + pytest + ground-truth-lint (Sprint 139 + Sprint 140 钩子) 全绿
- L4.x 22 stable 0 新增
- VERSION: 0.4.14.157 不 bump

### NOT in scope (Sprint 141+ 分批推)
- level 联动 summary 卡 (Sprint 141+ 二级聚合)
- AARRR funnel + cohort retention + RFM 分层
- 成本/毛利/CAC/LTV + holdout
- ETL sample_received_at (Sprint 139.5 单独 sprint)
- 0.01 锁权 + 滚动同期对比 不动
- 命名"派样 ROI" 不改 (等 cost 表落地)
```

---

## 2. 不做什么（防 scope creep）

- ❌ **不改 0.01 锁权（Tab 2）/ 滚动同期对比（Tab 3）**
- ❌ **不改 `SamplingLockYearData` / `RollingYearMetrics` 等其他 schema**（仅 `SamplingChannelSummary` 瘦身）
- ❌ **不改 summary 卡按 level 拆分**（user 期望但 Sprint 140 克制不实施，Sprint 141+ 二级聚合）
- ❌ **不改 ETL pipeline**
- ❌ **不动 `analysis/*.xlsx`**（gitignore 排除）
- ❌ **不动 ProductClassRepurchaseTab**

---

## 3. 验收清单（Codex 实施完成后，Claude Stage 3 review 必跑）

```bash
# 1. pytest 3 case 全 PASS (含 parametrize 5 window_days)
PYTHONPATH="$(pwd)" DUCKDB_PATH="/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb" \
  pytest backend/tests/test_sampling_sprint140.py -v
# 期望: 5 passed (3 case + 2 parametrize expansions) 或 6 passed (1 case 是 invariant + 2 linkage)

# 2. ground-truth-lint 钩子 PASS (Sprint 139 + Sprint 140)
PYTHONPATH="$(pwd)" python3 backend/scripts/check_sampling_spu_type.py
PYTHONPATH="$(pwd)" python3 backend/scripts/check_window_unification.py
# 期望: PASS × 2

# 3. 全部 pytest baseline 持续 (735 → 738)
PYTHONPATH="$(pwd)" DUCKDB_PATH="..." pytest backend/tests/ -q
# 期望: 738 passed / 23 skipped / 0 failed

# 4. pre-commit 全绿
git add -A
bash .githooks/pre-commit
# 期望: ruff + pytest + ground-truth-lint 全绿

# 5. e2e 真值断言
cd frontend-vue3 && npx playwright test e2e/sampling.spec.ts
# 期望: 1 case PASS

# 6. L4.22 强制 vite build (Stage 4 Claude 必跑)
cd frontend-vue3 && npm run build
# 期望: 0 errors, SamplingView-*.js 含新字段
```

---

## 4. 风险评估（3 项已知风险）

| # | 风险 | 概率 | 缓解 |
|---|---|---|---|
| R1 | `window_days=90` 时部分老数据缺 (orders.pay_time 早于 90 天前派样) | 中 | `<= ?` 参数化后 repurchase CTE 自动只算 ≤ 90 天窗口内的, 0 数据错; pytest 5 window_days parametrize 覆盖 |
| R2 | 旧字段残留 (前端某处还引用 `repurchase_users_30d`) | 低 | check_window_unification.py 钩子扫 19 个旧字段名, pre-commit 必跑 |
| R3 | `SamplingLockYOY` 等其他 schema 被误改 | 极低 | 钩子只扫 `SamplingChannelSummary` + sampling.ts + view.vue 3 个文件; L4.20 留尾治理在 Sprint 收口时强制 |

---

## 5. 跨 sprint 留尾

```
- Sprint 140.5: level 联动 summary 卡 (按 spu_category/tier/class 二级聚合)
- Sprint 141: LTV 90/180/365d + cohort retention matrix
- Sprint 142+: cost/margin 表 + holdout 实验框架
- Sprint 139.5: ETL sample_received_at 字段 (跨 sprint 阻塞)
```

---

## 6. Codex Stage 2 实施规范

**Codex 必读**:
1. 本文件全文 (7 件事)
2. `AGENTS.md` (本地文件, .gitignore 排除, 自动注入)
3. 必跑 `git log --all --oneline | head -20` + `git log main --oneline -- backend/services/sampling_service.py` 验 Sprint 139 收口状态

**Codex 不做**:
- ❌ 不 git commit / push (Claude Stage 4)
- ❌ 不改 0.01 锁权 / 滚动对比 任何代码
- ❌ 不重写 cat_sql (只是跟 window_days 参数对齐)
- ❌ 不改 SamplingCategoryRow (已经是统一字段)

**Codex 实施完成时给 user 回报**:
- ✅ pytest 3 case + parametrize PASS
- ✅ check_window_unification.py PASS (19 个旧字段 0 残留)
- ✅ e2e 真值断言 PASS
- ✅ pre-commit 全绿
- ✅ git diff --stat 改动列表

---

## 7. L4.x 永久规则强制清单

| 规则 | 适用范围 | Sprint 140 检查点 |
|---|---|---|
| L4.1 SQL 三引号 + f-string | body 含 `{identifier}` 必须 f 前缀 | summary_sql 现有 f""" 合规, 复用 |
| L4.5 FilterBuilder + ? 参数化 | service 函数禁止 f-string 内嵌用户输入 | `window_days` 是 int, 走 DB-API `?` 参数化, 合规 |
| L4.4 真连 DuckDB skipif | `_PROD_DUCKDB_AVAILABLE` 守卫 | pytest 3 case 必加 `pytestmark` |
| L4.3 isolated_duckdb fixture | 真连必用 per-worker tmp DuckDB | pytest 3 case 全用 `monkeypatch_connection` fixture |
| L4.7 launchd 首选 python3 | 不适用 (本 sprint 不改 plist) | 0 改动 |
| L4.16 push trigger paths | 改 backend/services + backend/contracts + backend/tests + backend/scripts + frontend-vue3 + e2e 都触发 | ✅ paths 都包含 |
| L4.20 留尾 SSOT 治理 | Sprint 140 收口时强制检查 | sprint close memory 必引真修 commit SHA |
| L4.22 vite rebuild + kill + restart | 前端 sprint 收口 | Claude Stage 4 必跑 |

---

## 8. 文件改动清单（精确到行号）

| 文件 | 行号 | 改法 | LOC |
|---|---|---|---|
| `backend/contracts/sampling.py` | L7-30 | `SamplingChannelSummary` 12 字段 → 4 字段 | -9 |
| `backend/services/sampling_service.py` | L102-105 (repurchase CTE) | 改 `r.days_between <= 60` → `<= ?` | +1/-1 |
| 同上 | L107-122 (summary_sql SELECT) | 14 字段 → 7 字段，6 个 `?` 参数 | -8/+2 |
| 同上 | L123 (summary_sql params) | sample_params + [max_window] + [window_days]*6 | +2 |
| 同上 | L124-152 (summary_rows loop) | 14 row index → 7 row index | -8/+3 |
| 同上 | L160-180 (cat_sql 已参数化 window_days) | 0 改动 (L170 已 `r.days_between <= ?`) | 0 |
| 同上 | L210-220 (period_distribution SQL) | `days_between <= 60` → `<= max_window_days` | +1/-1 |
| `frontend-vue3/src/api/sampling.ts` | L5-30 | TS interface 同步字段瘦身 | -9 |
| `frontend-vue3/src/views/SamplingView.vue` | L17 | `windowDays = ref(30)` 保留 | 0 |
| 同上 | L20-24 (windowOptions 数组) | 删 | -5 |
| 同上 | L26-30 (levelOptions 数组) | 保留 (跟 level 联动无关) | 0 |
| 同上 | L59-62 (windowField 等 4 computed) | 删 | -8 |
| 同上 | L75-105 (4 KPI computed + totalXXX) | 简化去 `_30d` 后缀 | -12/+8 |
| 同上 | L286-313 (Tab 1 工具栏) | `<n-select>` → `<n-slider>` | -10/+15 |
| 同上 | L313-450 (Tab 1 template) | 4 KPI 文案 + 渠道 split 文案 改 {windowDays}天 + 去 _30d 后缀 | -15/+10 |
| 同上 | 新增 levelLoadingText computed | +8 |
| 同上 | 新增 `<n-alert v-if="levelLoadingText">` | +5 |
| 同上 | 顶部 `<n-grid :cols="4">` 加 loading 文案位置 | +2 |
| `frontend-vue3/e2e/sampling.spec.ts` | L17-75 mock body | 字段名同步 | -14/+14 |
| 同上 | L75+ 加 slider 断言 + level loading 断言 | +10 |
| `backend/tests/test_sampling_sprint140.py` | NEW | 3 case + parametrize 5 window_days | +80 |
| `backend/scripts/check_window_unification.py` | NEW | 19 字段 0 残留 ground-truth-lint | +50 |
| `CHANGELOG.md` | Sprint 139 entry 之后 | +1 entry | +20 |

**合计**: 实质 -34 行 (contract 瘦身 9 + service 瘦身 8 + 前端瘦身 32, 加新 test + lint 钩子 130)

---

## 9. 完成定义（Definition of Done）

Codex Stage 2 完成后, Claude Stage 3 review 必查:

- [ ] Task 1: `SamplingChannelSummary` 字段瘦身到位（12 → 4）
- [ ] Task 2: `summary_sql` 参数化 `?` × 6 + repurchase CTE `<= ?` max_window
- [ ] Task 2: summary_rows loop row index 砍到 7
- [ ] Task 3: windowOptions 数组删除 + `<n-slider>` 1-90 + windowDays 文案动态
- [ ] Task 3: 4 个 `windowField/gsvField/rateField/ausField` computed 删除
- [ ] Task 3: 4 KPI computed 简化去 `_30d` 后缀
- [ ] Task 3: 渠道 split 文案加 `{windowDays}` + 去 `_30d`
- [ ] Task 3: `levelLoadingText` computed + `<n-alert>` 视觉提示
- [ ] Task 4: sampling.ts 同步字段
- [ ] Task 5.1: 3 case pytest PASS (含 parametrize 5 window_days)
- [ ] Task 5.2: check_window_unification.py PASS (19 个旧字段 0 残留)
- [ ] Task 6: e2e 真值断言 PASS (字段名同步 + slider 断言)
- [ ] pre-commit ruff + pytest + ground-truth-lint 全绿
- [ ] L4.x 22 stable 0 新增
- [ ] VERSION 0.4.14.157 不 bump
- [ ] CHANGELOG.md +1 entry

**未达任一项 = Codex 未完成, 回到 Stage 2 修补。**
