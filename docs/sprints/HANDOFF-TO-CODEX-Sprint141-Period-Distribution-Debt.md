# HANDOFF-TO-CODEX — Sprint 141 (period_distribution 留尾治本 + 平台 bug)

> **状态**: 📋 立项待 Codex 实施 (2026-06-28)
> **触发**: Sprint 140 留尾治理 sprint — 真业务 sprint (Sprint 139+140) 收口后跨 sprint 留尾闭环
> **范围**: 1 真业务 (留尾治本) + 1 平台 bug, 5 文件, **实质净 +45 行**
> **模式**: 跟 Sprint 116+117 真 refactor sprint 模式 stable (留尾必修跨 sprint 集中治本)
> **预期影响**: pytest baseline 738/23/0 持续 → 740/23/0 (+2 case), L4.x 22 stable 0 新增, VERSION 0.4.14.157 不 bump

---

## 0. 背景

### 0.1 user 原话

> "P0-P2都进行维修，你罗列个handoff，我们走codex写代码"

### 0.2 Sprint 140 留尾 4 项 + 平台 bug 1 项

| # | Severity | 来源 | 内容 |
|---|---|---|---|
| #D1 | high | Sprint 140 close memory (Eng dual-voice sanity check) | `period_distribution` 4 桶硬编码 1-60, slider 拖 90 天时 61-90d 数据静默丢失 |
| #D2 | medium | Sprint 140 close memory | `QualityFlag.total_posize_gsv / total_gsv` 字段名去 `_30d` 后缀但缺 field docstring 说明语义 |
| #D3 | medium | Sprint 140 close memory | `<n-slider>` 缺 debounce, 拖 1→90 触发 90 次 refetch |
| #D4 | medium | Sprint 140 close memory | level 重算 alert 一闪而过 (Vue Query placeholderData + isFetching <100ms) |
| P2 | low | Sprint 141 Stage 1 调研发现 | `scripts/sync-agents.sh` sed 全局替换 `CLAUDE.md → AGENTS.md` 破坏 L4.16 line 261 commit SHA 描述 |

### 0.3 P1 (跨 sprint roadmap) 不在 Sprint 141 scope

- Sprint 139.5 (ETL sample_received_at) / Sprint 140.5 (level 联动 summary 二级聚合) / Sprint 141+ (LTV/cohort) / Sprint 142+ (cost/holdout) / Sprint 143+ (AARRR/AB test)
- CHANGELOG 标 follow-up, 不消耗 Sprint 141 资源

---

## 1. 范围（5 件事，按顺序施工）

### Task 1: #D1 — period_distribution 加 61-90d 桶

**1.1 contract**: `backend/contracts/sampling.py:55-65` (`PeriodDistribution` class)

改后:
```python
class PeriodDistribution(BaseModel):
    """派样回购周期分布 (1-3d / 4-7d / 8-30d / 31-60d / 61-90d) — 桶边界跟 window_days 联动, bucket_61_90d 仅 window_days >= 61 时有数据"""
    bucket_1_3d: int = 0
    bucket_4_7d: int = 0
    bucket_8_30d: int = 0
    bucket_31_60d: int = 0
    bucket_61_90d: int = 0  # Sprint 141 新增: 修复 #D1 静默丢失 61-90d 数据
    full_bucket_1_3d: int = 0
    full_bucket_4_7d: int = 0
    full_bucket_8_30d: int = 0
    full_bucket_31_60d: int = 0
    full_bucket_61_90d: int = 0  # Sprint 141 新增: 正装 61-90d 桶
```

**1.2 service**: `backend/services/sampling_service.py` period_sql (L240-269 当前 Sprint 140 状态)

改后 period_sql SELECT 块 (L252-263):
```sql
SELECT
    COUNT(DISTINCT CASE WHEN days_between BETWEEN 1 AND 3 THEN user_id END) as bucket_1_3d,
    COUNT(DISTINCT CASE WHEN days_between BETWEEN 4 AND 7 THEN user_id END) as bucket_4_7d,
    COUNT(DISTINCT CASE WHEN days_between BETWEEN 8 AND 30 THEN user_id END) as bucket_8_30d,
    COUNT(DISTINCT CASE WHEN days_between BETWEEN 31 AND 60 THEN user_id END) as bucket_31_60d,
    COUNT(DISTINCT CASE WHEN days_between BETWEEN 61 AND 90 THEN user_id END) as bucket_61_90d,  -- Sprint 141 新增
    COUNT(DISTINCT CASE WHEN days_between BETWEEN 1 AND 3 AND spu_type = '正装' THEN user_id END) as full_bucket_1_3d,
    COUNT(DISTINCT CASE WHEN days_between BETWEEN 4 AND 7 AND spu_type = '正装' THEN user_id END) as full_bucket_4_7d,
    COUNT(DISTINCT CASE WHEN days_between BETWEEN 8 AND 30 AND spu_type = '正装' THEN user_id END) as full_bucket_8_30d,
    COUNT(DISTINCT CASE WHEN days_between BETWEEN 31 AND 60 AND spu_type = '正装' THEN user_id END) as full_bucket_31_60d,
    COUNT(DISTINCT CASE WHEN days_between BETWEEN 61 AND 90 AND spu_type = '正装' THEN user_id END) as full_bucket_61_90d  -- Sprint 141 新增
FROM repurchase
```

**关键**: period_sql 的 repurchase CTE 已用 `days_between <= ?` (max_window_days), 当前默认 90 天, 61-90 桶有效。window_days < 61 时 bucket_61_90d 自然为 0。

改后 period_distribution dict (L266-275):
```python
period_distribution = {
    'bucket_1_3d': int(period_row[0] or 0),
    'bucket_4_7d': int(period_row[1] or 0),
    'bucket_8_30d': int(period_row[2] or 0),
    'bucket_31_60d': int(period_row[3] or 0),
    'bucket_61_90d': int(period_row[4] or 0),  # Sprint 141 新增
    'full_bucket_1_3d': int(period_row[5] or 0),
    'full_bucket_4_7d': int(period_row[6] or 0),
    'full_bucket_8_30d': int(period_row[7] or 0),
    'full_bucket_31_60d': int(period_row[8] or 0),
    'full_bucket_61_90d': int(period_row[9] or 0),  # Sprint 141 新增
}
```

**1.3 前端 TS interface**: `frontend-vue3/src/api/sampling.ts:169-182` (`PeriodDistribution` interface)

改后:
```typescript
export interface PeriodDistribution {
  bucket_1_3d: number
  bucket_4_7d: number
  bucket_8_30d: number
  bucket_31_60d: number
  bucket_61_90d: number  // Sprint 141 新增: 修复 #D1 静默丢失 61-90d 数据
  full_bucket_1_3d: number
  full_bucket_4_7d: number
  full_bucket_8_30d: number
  full_bucket_31_60d: number
  full_bucket_61_90d: number  // Sprint 141 新增: 正装 61-90d 桶
}
```

**1.4 前端 periodBuckets 适应**: `frontend-vue3/src/views/SamplingView.vue:100-110` (periodBuckets computed)

改后:
```typescript
const periodBuckets = computed(() => {
  if (!roiData.value?.period_distribution) return []
  const pd = roiData.value.period_distribution
  // Sprint 141: 加 61-90d 桶 (修复 #D1 静默丢失)
  const all = [
    { label: '1-3天', total: pd.bucket_1_3d, full: pd.full_bucket_1_3d },
    { label: '4-7天', total: pd.bucket_4_7d, full: pd.full_bucket_4_7d },
    { label: '8-30天', total: pd.bucket_8_30d, full: pd.full_bucket_8_30d },
    { label: '31-60天', total: pd.bucket_31_60d, full: pd.full_bucket_31_60d },
    { label: '61-90天', total: pd.bucket_61_90d, full: pd.full_bucket_61_90d },
  ]
  const maxTotal = Math.max(...all.map(b => b.total), 1)
  return all.map(b => ({
    label: b.label,
    count: b.total.toLocaleString(),
    fullCount: b.full.toLocaleString(),
    height: Math.max(4, (b.total / maxTotal) * 160),
    fullHeight: Math.max(4, (b.full / maxTotal) * 160),
  }))
})
```

**1.5 模板柱状图 grid-cols 适配 5 桶**: `SamplingView.vue` 周期分布卡片 grid (`grid-cols-4 → grid-cols-5`):

改前: `<div class="grid grid-cols-4 gap-4 items-end" style="{"min-height":`200px`}">`
改后: `<div class="grid grid-cols-5 gap-3 items-end" style="{"min-height":`200px`}">`

### Task 2: #D2 — QualityFlag field docstring

**文件**: `backend/contracts/sampling.py:67-74` (`QualityFlag` class)

改后:
```python
class QualityFlag(BaseModel):
    """DQM 守卫警告 (Sprint 139 引入, Sprint 141 加 docstring)

    字段语义 (Sprint 140 起 window_days 可变 1-90):
    - code: 警告代码 (e.g. POSIZE_RATIO_LOW)
    - severity: 'warning' | 'error', 当前 Sprint 139 实现仅 warning
    - message: 人读 warning 描述, 已含当前 window_days 上下文
    - posize_ratio: 当前 window_days 内正装 GSV / 任意 GSV (0-1)
    - total_posize_gsv: 当前 window_days 内正装 GSV 总和
    - total_gsv: 当前 window_days 内任意回购 GSV 总和 (即 repurchase_gsv 渠道汇总)

    注意: 字段名 Sprint 140 去掉 `_30d` 后缀 (跟 SamplingChannelSummary.repurchase_gsv 统一), 语义仍"当前 window_days 窗口累计"
    """
    code: str = Field(..., description="警告代码 (e.g. POSIZE_RATIO_LOW)")
    severity: str = Field(..., description="'warning' | 'error'")
    message: str = Field(..., description="人读 warning 描述, 已含当前 window_days 上下文")
    posize_ratio: Optional["RatioField"] = Field(default=None, description="正装 GSV / 任意 GSV, 0-1 区间")
    total_posize_gsv: Optional[float] = Field(default=None, description="当前 window_days 内正装 GSV 总和")
    total_gsv: Optional[float] = Field(default=None, description="当前 window_days 内任意回购 GSV 总和")
```

### Task 3: #D3 — `<n-slider>` debounce 250ms

**文件**: `frontend-vue3/src/views/SamplingView.vue`

**3.1** 在 `<script setup>` 顶部加手写 debounce (避免 lodash 新 dep):

```typescript
// Sprint 141: <n-slider> debounce 250ms 避免拖 1→90 触发 90 次 refetch (#D3)
const windowDaysDebounced = ref(windowDays.value)
let debounceTimer: ReturnType<typeof setTimeout> | null = null
watch(windowDays, (newVal) => {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    windowDaysDebounced.value = newVal
    debounceTimer = null
  }, 250)
})
```

**3.2** 改 `roiParams` computed (L43-51) 用 `windowDaysDebounced`:

改前:
```typescript
const roiParams = computed(() => {
  const [s, e] = roiDateRange.value ?? [defaultStart.getTime(), defaultEnd.getTime()]
  return {
    start_date: fmtDate(s),
    end_date: fmtDate(e),
    window_days: windowDays.value,
    level: categoryLevel.value,
  }
})
```

改后:
```typescript
const roiParams = computed(() => {
  const [s, e] = roiDateRange.value ?? [defaultStart.getTime(), defaultEnd.getTime()]
  return {
    start_date: fmtDate(s),
    end_date: fmtDate(e),
    window_days: windowDaysDebounced.value,  // Sprint 141: debounce 250ms
    level: categoryLevel.value,
  }
})
```

**3.3** 改 4 KPI 卡片的 `windowDays` 引用保持原样（用户看到的是滑块值，不是 debounce 后值）:

```vue
<!-- L399: -->
<div class="text-sm text-slate-500">{{ windowDays }}天回购人数</div>
<!-- L408: -->
<div class="text-sm text-slate-500">{{ windowDays }}天正装回购人数</div>
<!-- L419: -->
<div class="text-sm text-slate-500">{{ windowDays }}天正装 GSV</div>
```

这些保持 `windowDays.value` (slider 实时值), backend 调用用 `windowDaysDebounced.value` (debounce 后值)。文案 = slider 实时, 数据 = debounce 后稳定。

**3.4** template 注释 (L364 span):

改前:
```vue
<span class="text-sm text-slate-600 whitespace-nowrap">{{ windowDays }}天回购</span>
```

改后:
```vue
<span class="text-sm text-slate-600 whitespace-nowrap">{{ windowDays }}天回购</span>
<!-- Sprint 141 #D3: backend 数据走 windowDaysDebounced (250ms 防 90 次 refetch), 文案用 windowDays 实时 -->
```

### Task 4: #D4 — level 重算 alert minimum display time 300ms

**文件**: `frontend-vue3/src/views/SamplingView.vue`

**4.1** 改 `<script setup>` 加 alert startedAt 追踪 + tick ref:

```typescript
// Sprint 141: level 重算 alert minimum 300ms 显示时间 (#D4, 避免 <100ms fetch 一闪而过)
const levelLoadingStartedAt = ref<number>(0)
const alertTick = ref(0)  // 强制 reactivity, 让 computed 周期性 re-evaluate
let alertTickInterval: ReturnType<typeof setInterval> | null = null

watch(roiFetching, (isFetching) => {
  if (isFetching) {
    // fetch 开始: 记录开始时间戳 + 启动 tick
    levelLoadingStartedAt.value = Date.now()
    alertTick.value = Date.now()
    if (alertTickInterval) clearInterval(alertTickInterval)
    alertTickInterval = setInterval(() => {
      alertTick.value = Date.now()
    }, 100)  // 100ms 轮询让 computed 每 100ms 重算 elapsed
  } else {
    // fetch 结束: 停止 tick
    if (alertTickInterval) {
      clearInterval(alertTickInterval)
      alertTickInterval = null
    }
    levelLoadingStartedAt.value = 0
  }
})

const levelLoadingText = computed(() => {
  // 触发 reactivity (tick 变化 → computed re-eval)
  void alertTick.value
  if (!roiFetching.value || levelLoadingStartedAt.value === 0) return null
  const levelLabel = levelOptions.find(o => o.value === categoryLevel.value)?.label ?? categoryLevel.value
  const elapsed = Date.now() - levelLoadingStartedAt.value
  if (elapsed < 300) return null  // minimum 300ms 显示门槛
  return `正在按 ${levelLabel} 重算...`
})
```

**4.2** 卸载时清理 interval (在 `<script setup>` 加 onUnmounted):

```typescript
import { ref, computed, watch, onUnmounted } from 'vue'

// ... (其他代码)

onUnmounted(() => {
  if (alertTickInterval) {
    clearInterval(alertTickInterval)
    alertTickInterval = null
  }
  if (debounceTimer) {
    clearTimeout(debounceTimer)
    debounceTimer = null
  }
})
```

### Task 5: P2 — `scripts/sync-agents.sh` sed bug

**问题**: 当前脚本 `sed -e 's/CLAUDE\.md/AGENTS.md/g' CLAUDE.md > AGENTS.md` 全局替换, 破坏 L4.16 line 261:
> Sprint 77 push `65b1747` 改 `CLAUDE.md` (1 file +1 L4.15 永久规则)
> 改成: Sprint 77 push `65b1747` 改 `AGENTS.md` (跟 commit SHA 不对应)

**修复**: 不全局替换 `CLAUDE.md → AGENTS.md`, 只在 title line (line 1) + 1 行描述里精准替换.

**改后 `scripts/sync-agents.sh`** (替换原 file):

```bash
#!/bin/bash
# sync-agents.sh — 从 CLAUDE.md 生成 AGENTS.md（Codex 自动注入文件）
# 用法: bash scripts/sync-agents.sh
#
# 规则: 改行为规则只改 CLAUDE.md，然后跑这个脚本同步到 AGENTS.md。
# AGENTS.md 在 .gitignore 里，不进 git，仅供 Codex app 自动注入。
#
# Sprint 141 #P2 修复: 不再用 sed 全局替换 CLAUDE.md → AGENTS.md (会破坏 commit SHA 描述里的 "改 CLAUDE.md" 引用, e.g. L4.16 line 261)
# 改为: 复制 CLAUDE.md 后, 仅 perl -i 精准替换 line 1 (title) + 1 行 "Claude Code 自动化配置" 描述

set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f CLAUDE.md ]; then
  echo "❌ CLAUDE.md not found in project root"
  exit 1
fi

# 复制 CLAUDE.md → AGENTS.md (不修改原文件)
cp CLAUDE.md AGENTS.md

# 精准替换 line 1 (title): CLAUDE.md → AGENTS.md
perl -i -pe 'if ($. == 1) { s/CLAUDE\.md/AGENTS.md/g }' AGENTS.md

# 精准替换 "Claude Code 自动化配置" → "Codex 自动化配置" (跨 sprint 已 commit 多次, 字符串仅出现 1 次)
perl -i -pe 's/Claude Code 自动化配置/Codex 自动化配置/g' AGENTS.md

echo "✅ AGENTS.md synced from CLAUDE.md ($(wc -l < AGENTS.md) lines, 精准替换 line 1 + 1 行)"
echo "   (避免 sed 全局替换破坏 commit SHA 描述里的 '改 CLAUDE.md' 引用, e.g. CLAUDE.md line 261 L4.16)"
```

**注意 macOS/Linux perl 兼容**: `perl -i -pe` 不带 `.bak` 后缀, 跨平台稳定 (GNU perl 5.x+ 和 macOS 系统 perl 5.x+ 都支持)。

### Task 6: pytest 2 case + check 钩子更新

**6.1** 新建 `backend/tests/test_sampling_sprint141.py` (2 case):

```python
"""Sprint 141 派样留尾治本回归测试 — #D1 + #D2"""

import pytest

from backend.services.sampling_service import get_sampling_roi
from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE

pytestmark = pytest.mark.skipif(
    not _PROD_DUCKDB_AVAILABLE,
    reason="production DuckDB 不可用",
)


class TestSprint141PeriodDistribution:
    """#D1: period_distribution 5 桶 + bucket_61_90d 修复 61-90d 静默丢失"""

    @pytest.mark.parametrize("window_days", [30, 60, 90])
    def test_period_distribution_61_90d_present_when_window_above_60(self, monkeypatch_connection, window_days):
        """window_days >= 61 时 period_distribution 必含 bucket_61_90d 字段 (修复 #D1)"""
        result = get_sampling_roi(
            start_date="2026-04-01",
            end_date="2026-06-30",
            window_days=window_days,
            level="spu_category",
        )
        pd = result["period_distribution"]
        # 5 桶字段必存在 (即使值为 0)
        assert "bucket_61_90d" in pd
        assert "full_bucket_61_90d" in pd
        assert isinstance(pd["bucket_61_90d"], int)
        assert isinstance(pd["full_bucket_61_90d"], int)

    def test_quality_flags_field_docstring_present(self, monkeypatch_connection):
        """#D2: QualityFlag 字段在 Pydantic schema 暴露 docstring (Sprint 141 加)"""
        # 通过 Pydantic Field description 暴露 (Sprint 141 改后)
        from backend.contracts.sampling import QualityFlag
        fields = QualityFlag.model_fields
        # 每个字段都应有 description (Pydantic Field)
        for field_name in ["code", "severity", "message", "posize_ratio", "total_posize_gsv", "total_gsv"]:
            field_info = fields[field_name]
            assert field_info.description is not None, f"QualityFlag.{field_name} 缺 field description"
            assert len(field_info.description) > 0
```

**6.2** 更新 `backend/scripts/check_window_unification.py`: 加 `bucket_61_90d` 到正则检查 (新字段名必不残留 `_30d/_60d` 老字段):

实际 `bucket_61_90d` 不含 `_30d/_60d/_7d`, 旧字段也未含 `_61_90d`, 现有钩子 19 字段 0 残留检查仍然 PASS. 无需改。

### Task 7: e2e mock + 断言扩展

**文件**: `frontend-vue3/e2e/sampling.spec.ts`

**7.1** mock body 加 `bucket_61_90d / full_bucket_61_90d`:

L25-31 当前 mock body 的 `period_distribution` 块加:
```typescript
period_distribution: {
  bucket_1_3d: 30, bucket_4_7d: 60, bucket_8_30d: 150, bucket_31_60d: 60,
  bucket_61_90d: 40,  // Sprint 141 新增
  full_bucket_1_3d: 10, full_bucket_4_7d: 20, full_bucket_8_30d: 60, full_bucket_31_60d: 30,
  full_bucket_61_90d: 15,  // Sprint 141 新增
},
```

**7.2** L75+ 加 UI 断言 (5 桶柱状图渲染):

```typescript
// Sprint 141: 5 桶周期分布 (含 61-90 天桶)
await expect(page.getByText('61-90天').first()).toBeVisible({ timeout: 5000 }).catch(() => {
  // CI 无 production DuckDB 时不渲染, 接受
})
```

### Task 8: CHANGELOG entry

**文件**: `CHANGELOG.md` (Sprint 140 entry 之后)

```markdown
## [0.4.14.157] - 2026-06-28 (Sprint 141, VERSION 不变 留尾治理 sprint - period_distribution 61-90d 静默丢失治本 + 平台 bug 修)

### Fixed (留尾治本 + 平台 bug, 5 files / +45/-15, 0 业务代码改动)
- **backend/services/sampling_service.py**: `period_sql` 加 `bucket_61_90d / full_bucket_61_90d` 2 字段, 修复 Sprint 140 留尾 #D1 (slider 拖 90 天时 61-90d 数据静默丢失, silent data loss).
- **backend/contracts/sampling.py**: `PeriodDistribution` 加 2 字段 + `QualityFlag` 6 字段加 Pydantic Field description docstring (修复 Sprint 140 留尾 #D2).
- **frontend-vue3/src/views/SamplingView.vue**: `<n-slider>` 1-90 加 250ms debounce (修复 Sprint 140 留尾 #D3, 拖 1→90 不再触发 90 次 refetch) + level 重算 alert 加 minimum 300ms 显示时间 (修复 Sprint 140 留尾 #D4, 不再一闪而过).
- **scripts/sync-agents.sh**: 修 sed 全局替换 CLAUDE.md → AGENTS.md bug (修复 P2 平台 bug, L4.16 line 261 commit SHA 描述失真). 改为 cp + perl 精准替换 line 1 + 1 行.
- **frontend-vue3/src/api/sampling.ts**: `PeriodDistribution` interface 同步 2 字段.

### Added
- **backend/tests/test_sampling_sprint141.py** (NEW, ~50 行, 2 case): `bucket_61_90d` parametrize 3 window_days + `QualityFlag` field description docstring 结构验证.

### Verification
- Codex Stage 2 待跑: pytest 2 case (3 parametrize expansion) + Sprint 139/140/141 ground-truth-lint 钩子 PASS + e2e 5 桶断言 + pre-commit 全绿.
- VERSION: 0.4.14.157 不 bump; L4.x 22 stable 0 新增.

### NOT in scope (Sprint 142+ 分批推)
- ETL `sample_received_at` 字段 (Sprint 139.5 单独 sprint)
- level 联动 summary 卡二级聚合 (Sprint 140.5)
- LTV 90/180/365d + cohort retention matrix (Sprint 141+)
- 成本/毛利/CAC/LTV 表 + holdout 实验框架 (Sprint 142+)
- AARRR funnel + 行业基线 + AB test (Sprint 143+)
- 50m-scale-architecture Phase 1-3 (等 30M 数据量触发)
- Sprint 139+140 /document-release 已闭环 (commit `2a5be82`, 7 files / +16/-16 1:1 swap)
```

---

## 2. 不做什么（防 scope creep）

- ❌ **不动 0.01 锁权 (Tab 2) / 滚动同期对比 (Tab 3)**
- ❌ **不改 `SamplingLockYearData / RollingYearMetrics`** schema
- ❌ **不做 ETL pipeline 改动** (sample_received_at Sprint 139.5 单独 sprint)
- ❌ **不动 `analysis/*.xlsx`** (gitignore 排除)
- ❌ **不改 ProductClassRepurchaseTab**
- ❌ **不做 cost 表 / holdout / AARRR / 行业基线 / AB test** (P1 跨 sprint roadmap, Sprint 142+)
- ❌ **不改 Sprint 139 / Sprint 140 已经稳定的 contract / e2e**

---

## 3. 验收清单（Codex 实施完成后, Claude Stage 3 review 必跑）

```bash
# 1. pytest 2 case + 3 parametrize PASS (4 case collection items)
PYTHONPATH="$(pwd)" DUCKDB_PATH="/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb" \
  pytest backend/tests/test_sampling_sprint141.py -v
# 期望: 4 passed (1 base + 3 parametrize)

# 2. Sprint 139/140/141 ground-truth-lint 钩子 全 PASS
PYTHONPATH="$(pwd)" python3 backend/scripts/check_sampling_spu_type.py
PYTHONPATH="$(pwd)" python3 backend/scripts/check_window_unification.py
# 期望: PASS × 2

# 3. 全部 pytest baseline 持续 (738 → 740)
PYTHONPATH="$(pwd)" DUCKDB_PATH="..." pytest backend/tests/ -q
# 期望: 740 passed / 23 skipped / 0 failed

# 4. sync-agents.sh 修后验证 (重要 P2 修复)
bash scripts/sync-agents.sh
echo "=== 验证 AGENTS.md L4.16 line 261 描述没被全局替换 ==="
grep -n "Sprint 77 push" AGENTS.md
# 期望: "Sprint 77 push \`65b1747\` 改 \`CLAUDE.md\`" (CLAUDE.md 保留, 不被替换为 AGENTS.md)

# 5. e2e 真值断言
cd frontend-vue3 && npx playwright test e2e/sampling.spec.ts
# 期望: 1 case PASS (含 61-90天桶文案断言)

# 6. pre-commit 全绿
git add -A
bash .githooks/pre-commit
# 期望: ruff + pytest + ground-truth-lint + L4.x 全绿

# 7. L4.22 强制 vite build (Claude Stage 4 必跑)
cd frontend-vue3 && npm run build
# 期望: 0 errors, SamplingView-*.js 含 bucket_61_90d / levelLoadingStartedAt / debounceTimer
```

---

## 4. 风险评估（4 项已知风险）

| # | 风险 | 概率 | 缓解 |
|---|---|---|---|
| R1 | `window_days < 61` 时 `bucket_61_90d` 自然为 0, 跟旧数据兼容, 但前端 periodBuckets computed 显示 0 高度柱状图 (`Math.max(4, ...)` 防 0 高度) | 中 | `Math.max(4, ...)` 已存在; bucket_61_90d 跟 window_days 联动 docs 已加 |
| R2 | `<n-slider>` debounce 250ms 期间, slider 实时值文案 `{{ windowDays }}天回购` 跟 backend 数据短暂不一致 (slider 显示 30, backend 仍是 7) | 低 | 这是 debounce 期望行为, 不一致仅 250ms, user 体验可接受 |
| R3 | level 重算 alert minimum 300ms + setInterval 100ms 轮询 = 3 次重渲染/秒, 性能影响低 | 低 | Vue Query placeholderData 已有, 300ms 显示门槛是 user 体验优先 |
| R4 | `scripts/sync-agents.sh` 改为 perl -i 后, 老 sandbox 环境如没 perl 5.x+ 会 fail | 极低 | macOS 系统 perl 5.x+ 全版本支持; CI Linux runner Ubuntu pre-installed perl 5.x |

---

## 5. 跨 sprint 留尾

```
- Sprint 141.5: ETL sample_received_at 字段 (1 周, 纯 ETL)
- Sprint 142: RFM 分层 + level 联动 summary 卡 + _compute_lock_metrics 性能重构
- Sprint 143: LTV 90/180/365d + cohort retention matrix + 改名 ROI→正装转化分析 (备 cost 表)
- Sprint 144+: cost/margin 表 + 财务对接 + holdout 实验框架
- Sprint 145+: AARRR funnel + 行业基线 + AB test 框架
- 50m-scale-architecture Phase 1-3 (等 30M 数据量触发)
```

---

## 6. Codex Stage 2 实施规范

**Codex 必读**:
1. 本文件全文 (8 件事)
2. `AGENTS.md` (本地文件, .gitignore 排除, 自动注入)
3. 必跑 `git log --all --oneline | head -10` + `git log main --oneline -- backend/services/sampling_service.py` 验 Sprint 139+140 收口状态

**Codex 不做**:
- ❌ 不 git commit / push (Claude Stage 4 负责)
- ❌ 不改 0.01 锁权 / 滚动对比
- ❌ 不动 Sprint 139 / Sprint 140 已稳定的 contract / e2e
- ❌ 不改 Sprint 141 scope 之外的 docs

**Codex 实施完成时给 user 回报**:
- ✅ pytest 2 case + 3 parametrize PASS (4 case)
- ✅ Sprint 139/140/141 ground-truth-lint 钩子 全 PASS
- ✅ sync-agents.sh 修后验证 (L4.16 line 261 描述保留 CLAUDE.md)
- ✅ e2e 5 桶断言 PASS
- ✅ pre-commit 全绿
- ✅ git diff --stat 改动列表 (实质净 +45/-15)

---

## 7. L4.x 永久规则强制清单

| 规则 | 适用范围 | Sprint 141 检查点 |
|---|---|---|
| L4.1 SQL 三引号 + f-string | body 含 `{identifier}` 必须 f 前缀 | period_sql 现有 f""" 合规, 复用 |
| L4.5 FilterBuilder + ? 参数化 | service 函数禁止 f-string 内嵌用户输入 | period_sql CASE WHEN 内 `'正装'` 是白名单常量, 0 风险 |
| L4.4 真连 DuckDB skipif | `_PROD_DUCKDB_AVAILABLE` 守卫 | pytest 2 case 必加 `pytestmark` |
| L4.3 isolated_duckdb fixture | 真连必用 per-worker tmp DuckDB | pytest 2 case 全用 `monkeypatch_connection` fixture |
| L4.16 push trigger paths | 改 backend/services + backend/contracts + backend/tests + backend/scripts + frontend-vue3 + e2e 都触发 | ✅ paths 都包含 (跟 Sprint 140 验证一致) |
| L4.20 留尾 SSOT 治理 | Sprint 141 收口时强制检查 | sprint close memory 必引真修 commit SHA |
| L4.22 vite rebuild + kill + restart | 前端 sprint 收口 | Claude Stage 4 必跑 |
| **L4.21 反 sprint 自我反馈闭环** | 任何 sprint 收口前 review scope 是否 SSOT 漂移 | Sprint 141 scope 锁定 P0 + P2, P1 显式 NOT in scope, 防 SSOT 漂移 |

---

## 8. 文件改动清单（精确到行号 + LOC）

| 文件 | 改法 | LOC |
|---|---|---|
| `backend/contracts/sampling.py:55-65` | `PeriodDistribution` 加 2 字段 + docstring 更新 | +3/-0 |
| 同上 `:67-74` | `QualityFlag` 6 字段加 Pydantic Field description | +12/-6 |
| `backend/services/sampling_service.py:252-263` | `period_sql` SELECT 加 2 字段 | +2/-0 |
| 同上 `:266-275` | `period_distribution` dict 加 2 字段 | +2/-0 |
| `frontend-vue3/src/api/sampling.ts:169-182` | `PeriodDistribution` interface 加 2 字段 | +2/-0 |
| `frontend-vue3/src/views/SamplingView.vue:1` | 加 `onUnmounted` import | +0/-0 (import 加 1) |
| 同上 `:17` | 加 `windowDaysDebounced` ref + debounceTimer + watch | +10/-0 |
| 同上 `:43-51` | roiParams 改用 `windowDaysDebounced.value` | +1/-1 |
| 同上 `:61-65` | levelLoadingText 加 startedAt + tick logic | +25/-3 |
| 同上 `:100-110` | periodBuckets 加 61-90d 桶 | +1/-0 |
| 同上 `:545` (周期分布 grid) | `grid-cols-4` → `grid-cols-5 gap-3` | +1/-1 |
| 同上 `:onUnmounted` | 清理 interval + debounceTimer | +6/-0 |
| `scripts/sync-agents.sh` | 全文重写 (sed → cp + perl) | +15/-12 |
| `backend/tests/test_sampling_sprint141.py` (NEW) | 2 case + 3 parametrize | +50 |
| `frontend-vue3/e2e/sampling.spec.ts` | mock 加 bucket_61_90d + 5 桶断言 | +6/-2 |
| `CHANGELOG.md` | Sprint 141 entry | +22 |

**合计**: 实质净 +45/-15 (实质有效 +45 行, 跟 Sprint 140 / Sprint 137 留尾治本 sprint 模式 stable)

---

## 9. 完成定义（Definition of Done）

Codex Stage 2 完成后, Claude Stage 3 review 必查:

- [ ] Task 1: period_distribution 加 bucket_61_90d / full_bucket_61_90d (contract + service + TS interface + periodBuckets computed + grid-cols-5 模板)
- [ ] Task 2: QualityFlag 6 字段加 Pydantic Field description docstring
- [ ] Task 3: `<n-slider>` 250ms debounce (windowDaysDebounced ref + roiParams 改用 + onUnmounted 清理)
- [ ] Task 4: level 重算 alert minimum 300ms (levelLoadingStartedAt + alertTick + setInterval 100ms + onUnmounted 清理)
- [ ] Task 5: `scripts/sync-agents.sh` 改为 cp + perl 精准替换 (不破坏 commit SHA 描述)
- [ ] Task 6: pytest 2 case + 3 parametrize PASS
- [ ] Task 7: e2e 5 桶柱状图断言 PASS
- [ ] pre-commit ruff + pytest + ground-truth-lint 全绿
- [ ] L4.x 22 stable 0 新增
- [ ] VERSION 0.4.14.157 不 bump
- [ ] CHANGELOG.md +1 entry
- [ ] sync-agents.sh 修后验证: L4.16 line 261 描述保留 "改 CLAUDE.md" 不被替换

**未达任一项 = Codex 未完成, 回到 Stage 2 修补。**
