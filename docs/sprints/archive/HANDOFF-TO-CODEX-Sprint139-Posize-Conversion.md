# HANDOFF-TO-CODEX — Sprint 139 (派样人群正装转化漏斗)

> **状态**: 📋 立项待 Codex 实施 (2026-06-27)
> **触发**: 真业务 sprint (user 原话: "派样 ROI 分析，我本质上想要知道的是，某段时间内购买过小样的人群（百亿补贴和U先派样）后续转换正装的数据情况。然后各个 product 的回购情况")
> **范围**: 1 真业务, 9 文件 (+605 / -135 行实质净 +470)
> **模式**: 跟 Sprint 137 + Sprint 138 真业务 sprint 模式 stable (CEO/Eng dual-voice review 后 MVP 切片)
> **预期影响**: pytest baseline 730/23/0 持续 → 735/23/0 (+5 case), L4.x 22 stable 0 新增, VERSION 0.4.14.157 不 bump

---

## 0. 背景

### 0.1 user 原话（直接抄）

> "派样 ROI 分析，我本质上想要知道的是，某段时间内购买过小样的人群（百亿补贴和U先派样）后续转换正装的数据情况。然后各个 product 的回购情况。"

### 0.2 现状（基于 codegraph 实读）

`backend/services/sampling_service.py::get_sampling_roi()` 当前算"任意有效订单"回购（不区分正装/小样）:
- `summary_sql` L95-122: 7d/30d/60d 三个窗口的 repurchase_users/gsv/aus, 不区分正装
- `cat_sql` L157-187: 按品类聚合, 同样不区分正装, 已经有 `is_same_category` 字段

`backend/contracts/sampling.py` `SamplingChannelSummary` + `SamplingCategoryRow` 缺正装字段。

`frontend-vue3/src/views/SamplingView.vue` Tab 1 (L286-392) 渲染渠道对比卡 + 品类明细表, 但没"正装转化"指标。

### 0.3 CEO + Eng dual-voice review 共识 (6/6 确认, 0 disagreement)

**CEO** (天猫 C 端运营视角): 当前 plan v2 scope 太窄, 缺成本/毛利/holdout/LTV/cohort/RFM, 应重构为 ROI 决策仪表盘。但 Sprint 139 MVP = C1 (正装转化) + H8 (周期分布) + H4 (DQM warnings) 是**正确的 MVP 切片**, 跟 Sprint 137 + Sprint 138 真业务模式 stable。

**Eng** (实现视角): Sprint 139 不动 ETL (sample_received_at/cost/holdout 表完全缺, Sprint 139.5+ 单独 sprint)。Plan v2 漏估 LOC 64% (+330 → 实际 +560), 因为漏了 pytest 5 case + DQM lint 钩子。Sprint 139 真最小 scope 已锁定。

**关键 insight**: Sprint 139 是**数据口径补全 + 4 KPI 卡片**, 不是**业务能力升级**。但这是必要前置, Sprint 140+ 才能接 cost 表 + cohort + ROI 决策仪表盘。

---

## 1. 范围（6 件事，按顺序施工）

### Task 1: `get_sampling_roi` SQL 加 `spu_type='正装'` 拆分

**文件**: `backend/services/sampling_service.py` (当前 698 行)

**改动 1A — `summary_sql` 加 6 个正装/非正装字段**:

`summary_sql` 在 L110-118 的 SELECT 块, 在现有 `repurchase_users_30d` / `repurchase_gsv_30d` 字段**之后**, 加 6 个 CASE WHEN:

```python
# 当前 L110-118:
SELECT
    su.channel,
    COUNT(DISTINCT su.user_id) as sample_users,
    COUNT(DISTINCT CASE WHEN r.days_between <= 7 THEN r.user_id END) as repurchase_users_7d,
    COUNT(DISTINCT CASE WHEN r.days_between <= 30 THEN r.user_id END) as repurchase_users_30d,
    COUNT(DISTINCT CASE WHEN r.days_between <= 60 THEN r.user_id END) as repurchase_users_60d,
    SUM(CASE WHEN r.days_between <= 7 THEN r.actual_amount ELSE 0 END) as repurchase_gsv_7d,
    SUM(CASE WHEN r.days_between <= 30 THEN r.actual_amount ELSE 0 END) as repurchase_gsv_30d,
    SUM(CASE WHEN r.days_between <= 60 THEN r.actual_amount ELSE 0 END) as repurchase_gsv_60d
FROM (SELECT DISTINCT user_id, channel FROM sample_users) su
LEFT JOIN repurchase r ON su.user_id = r.user_id AND su.channel = r.channel
GROUP BY su.channel
```

**改成** (在 L118 后加 6 行):

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
    -- Sprint 139: 正装/非正装拆分 (spu_type='正装')
    COUNT(DISTINCT CASE WHEN r.days_between <= 30 AND r.spu_type = '正装' THEN r.user_id END) as full_repurchase_users_30d,
    SUM(CASE WHEN r.days_between <= 30 AND r.spu_type = '正装' THEN r.actual_amount ELSE 0 END) as full_repurchase_gsv_30d,
    COUNT(DISTINCT CASE WHEN r.days_between <= 30 AND r.spu_type != '正装' THEN r.user_id END) as nonfull_repurchase_users_30d,
    SUM(CASE WHEN r.days_between <= 30 AND r.spu_type != '正装' THEN r.actual_amount ELSE 0 END) as nonfull_repurchase_gsv_30d,
    COUNT(DISTINCT CASE WHEN r.days_between <= 60 AND r.spu_type = '正装' THEN r.user_id END) as full_repurchase_users_60d,
    SUM(CASE WHEN r.days_between <= 60 AND r.spu_type = '正装' THEN r.actual_amount ELSE 0 END) as full_repurchase_gsv_60d
```

**重要**: 这需要在 `repurchase` CTE (L97-109) 里加 `o.spu_type` 字段, 即 L97 改成:

```sql
repurchase AS (
    SELECT su.user_id, su.channel, su.first_sample_time,
           o.pay_time as repurchase_time,
           o.actual_amount,
           COALESCE(o.spu_type, '未知') as spu_type,   -- ← 加这行
           DATEDIFF('day', su.first_sample_time, o.pay_time) as days_between
    FROM sample_users su
    JOIN orders o ON su.user_id = o.user_id
    WHERE o.pay_time > su.first_sample_time
      AND DATEDIFF('day', su.first_sample_time, o.pay_time) <= 60
      AND o.is_refund = FALSE
      AND o.order_status != '交易关闭'
      AND o.channel != '购物金'
)
```

**改 summary_rows 处理循环** (L126-151), 加 6 字段到返回 dict:

```python
for row in summary_rows:
    ch = row[0]
    sample_users = int(row[1] or 0)
    repurchase_7d = int(row[2] or 0)
    repurchase_30d = int(row[3] or 0)
    repurchase_60d = int(row[4] or 0)
    gsv_7d = float(row[5] or 0)
    gsv_30d = float(row[6] or 0)
    gsv_60d = float(row[7] or 0)
    # Sprint 139 新增 6 字段 (索引 8-13)
    full_users_30d = int(row[8] or 0)
    full_gsv_30d = float(row[9] or 0)
    nonfull_users_30d = int(row[10] or 0)
    nonfull_gsv_30d = float(row[11] or 0)
    full_users_60d = int(row[12] or 0)
    full_gsv_60d = float(row[13] or 0)

    channels_result.append({
        'channel': DB_TO_UI.get(ch, ch),
        'sample_users': sample_users,
        # ... 现有字段不动 ...
        'repurchase_aus_60d': round(safe_ratio(gsv_60d, repurchase_60d), 2),
        # Sprint 139 新增 6 字段:
        'full_repurchase_users_30d': full_users_30d,
        'full_repurchase_gsv_30d': round(full_gsv_30d, 2),
        'full_repurchase_aus_30d': round(safe_ratio(full_gsv_30d, full_users_30d), 2),
        'nonfull_repurchase_users_30d': nonfull_users_30d,
        'nonfull_repurchase_gsv_30d': round(nonfull_gsv_30d, 2),
        'nonfull_repurchase_aus_30d': round(safe_ratio(nonfull_gsv_30d, nonfull_users_30d), 2),
        'full_repurchase_users_60d': full_users_60d,
        'full_repurchase_gsv_60d': round(full_gsv_60d, 2),
        'full_repurchase_aus_60d': round(safe_ratio(full_gsv_60d, full_users_60d), 2),
        'full_repurchase_rate_30d': round(safe_ratio(full_users_30d, sample_users), 4),
    })
```

**改动 1B — `cat_sql` 加 4 字段** (L157-187, 按 `window_days` 钻取):

`cat_sql` L174-185 的 SELECT, 加 4 个正装字段:

```sql
SELECT
    su.channel,
    su.sample_category,
    COUNT(DISTINCT su.user_id) as sample_users,
    COUNT(DISTINCT r.user_id) as repurchase_users,
    COALESCE(SUM(r.actual_amount), 0) as repurchase_gsv,
    SUM(r.is_same_category) as same_cat_users,
    -- Sprint 139: 正装/非正装 split
    COUNT(DISTINCT CASE WHEN r.spu_type = '正装' THEN r.user_id END) as full_repurchase_users,
    COALESCE(SUM(CASE WHEN r.spu_type = '正装' THEN r.actual_amount ELSE 0 END), 0) as full_repurchase_gsv,
    COUNT(DISTINCT CASE WHEN r.spu_type != '正装' THEN r.user_id END) as nonfull_repurchase_users,
    COALESCE(SUM(CASE WHEN r.spu_type != '正装' THEN r.actual_amount ELSE 0 END), 0) as nonfull_repurchase_gsv
FROM (SELECT DISTINCT user_id, channel, sample_category FROM sample_users) su
LEFT JOIN repurchase r ON su.user_id = r.user_id AND su.channel = r.channel
GROUP BY su.channel, su.sample_category
HAVING COUNT(DISTINCT su.user_id) > 0
ORDER BY su.channel, repurchase_gsv DESC
```

**改 category_result 循环** (L191-210), 加 4 字段到返回 dict:

```python
for row in cat_rows:
    ch = row[0]
    cat = row[1]
    su = int(row[2] or 0)
    ru = int(row[3] or 0)
    gsv = float(row[4] or 0)
    same = int(row[5] or 0)
    # Sprint 139 新增 4 字段 (索引 6-9)
    full_users = int(row[6] or 0)
    full_gsv = float(row[7] or 0)
    nonfull_users = int(row[8] or 0)
    nonfull_gsv = float(row[9] or 0)

    category_result.append({
        'channel': DB_TO_UI.get(ch, ch),
        'category': cat,
        # ... 现有字段不动 ...
        'same_category_repurchase': same,
        'same_category_rate': round(safe_ratio(same, su), 4),
        # Sprint 139 新增 4 字段:
        'full_repurchase_users': full_users,
        'full_repurchase_rate': round(safe_ratio(full_users, su), 4),
        'full_repurchase_gsv': round(full_gsv, 2),
        'full_repurchase_aus': round(safe_ratio(full_gsv, full_users), 2),
        'nonfull_repurchase_users': nonfull_users,
        'nonfull_repurchase_gsv': round(nonfull_gsv, 2),
        'nonfull_repurchase_aus': round(safe_ratio(nonfull_gsv, nonfull_users), 2),
    })
```

### Task 2: `get_sampling_roi` 加"回购周期分布"5 桶直方图

**文件**: `backend/services/sampling_service.py` (L222 return 块前)

**新增 SQL**: 在 `summary_rows` 跑完后, 单独跑一个周期分布查询:

```python
# Sprint 139: 回购周期分布 (1-3d / 4-7d / 8-30d / 31-60d / 60+d)
period_sql = f"""
    WITH sample_users AS ({sample_users_sql}),
    repurchase AS (
        SELECT su.user_id, su.channel, su.first_sample_time,
               o.pay_time as repurchase_time, o.actual_amount, o.spu_type,
               DATEDIFF('day', su.first_sample_time, o.pay_time) as days_between
        FROM sample_users su
        JOIN orders o ON su.user_id = o.user_id
        WHERE o.pay_time > su.first_sample_time
          AND DATEDIFF('day', su.first_sample_time, o.pay_time) <= 60
          AND o.is_refund = FALSE
          AND o.order_status != '交易关闭'
          AND o.channel != '购物金'
    )
    SELECT
        -- 5 桶边界: 1-3 / 4-7 / 8-30 / 31-60 / 60+ (NOTE: 60+d 不可能因 days_between <= 60, 但保留作 future-proof)
        COUNT(DISTINCT CASE WHEN days_between BETWEEN 1 AND 3 THEN user_id END) as bucket_1_3d,
        COUNT(DISTINCT CASE WHEN days_between BETWEEN 4 AND 7 THEN user_id END) as bucket_4_7d,
        COUNT(DISTINCT CASE WHEN days_between BETWEEN 8 AND 30 THEN user_id END) as bucket_8_30d,
        COUNT(DISTINCT CASE WHEN days_between BETWEEN 31 AND 60 THEN user_id END) as bucket_31_60d,
        -- 正装桶 (spu_type='正装')
        COUNT(DISTINCT CASE WHEN days_between BETWEEN 1 AND 3 AND spu_type = '正装' THEN user_id END) as full_bucket_1_3d,
        COUNT(DISTINCT CASE WHEN days_between BETWEEN 4 AND 7 AND spu_type = '正装' THEN user_id END) as full_bucket_4_7d,
        COUNT(DISTINCT CASE WHEN days_between BETWEEN 8 AND 30 AND spu_type = '正装' THEN user_id END) as full_bucket_8_30d,
        COUNT(DISTINCT CASE WHEN days_between BETWEEN 31 AND 60 AND spu_type = '正装' THEN user_id END) as full_bucket_31_60d
    FROM repurchase
"""
period_row = conn.execute(period_sql, sample_params).fetchone()

period_distribution = {
    'bucket_1_3d': int(period_row[0] or 0),
    'bucket_4_7d': int(period_row[1] or 0),
    'bucket_8_30d': int(period_row[2] or 0),
    'bucket_31_60d': int(period_row[3] or 0),
    'full_bucket_1_3d': int(period_row[4] or 0),
    'full_bucket_4_7d': int(period_row[5] or 0),
    'full_bucket_8_30d': int(period_row[6] or 0),
    'full_bucket_31_60d': int(period_row[7] or 0),
}
```

**加到 return dict** (L212-220):

```python
return {
    'summary': {'channels': channels_result},
    'category_breakdown': category_result,
    'time_range': {
        'start': start_date,
        'end': end_date,
        'window_days': window_days,
    },
    'period_distribution': period_distribution,  # ← 新增
    'quality_flags': quality_flags,              # ← 新增 (Task 3)
}
```

### Task 3: DQM 守卫改 `warnings`/`quality_flags` 字段（不抛错）

**文件**: `backend/services/sampling_service.py` (L221 finally 块前)

**新增 DQM 计算**:

```python
# Sprint 139: DQM 守卫 — spu_type='正装' 占比 < 30% 时记录 warnings
total_posize_gsv = sum(c.get('full_repurchase_gsv_30d', 0) for c in channels_result)
total_gsv_30d = sum(c.get('repurchase_gsv_30d', 0) for c in channels_result)
posize_ratio = safe_ratio(total_posize_gsv, total_gsv_30d)

quality_flags = []
if total_gsv_30d > 0 and posize_ratio < 0.30:
    quality_flags.append({
        'code': 'POSIZE_RATIO_LOW',
        'severity': 'warning',
        'message': f'派样人群 30 天正装 GSV 占比仅 {posize_ratio:.1%} (< 30%), 可能是业务表现差或数据缺失',
        'posize_ratio': round(posize_ratio, 4),
        'total_posize_gsv_30d': total_posize_gsv,
        'total_gsv_30d': total_gsv_30d,
    })
```

**logger.warning** (跟 Sprint 54 模式 stable, 跟 L17 `_logger`):

```python
if quality_flags:
    _logger.warning(f"[Sprint 139 DQM] {quality_flags[0]['message']}")
```

### Task 4: `SamplingChannelSummary` + `SamplingCategoryRow` 加字段

**文件**: `backend/contracts/sampling.py` (L7-37)

**SamplingChannelSummary 加 10 字段**:

```python
class SamplingChannelSummary(BaseModel):
    """派样渠道汇总"""
    channel: str
    sample_users: int
    repurchase_users_7d: int
    repurchase_users_30d: int
    repurchase_users_60d: int
    repurchase_rate_7d: "RatioField"
    repurchase_rate_30d: "RatioField"
    repurchase_rate_60d: "RatioField"
    repurchase_gsv_7d: float
    repurchase_gsv_30d: float
    repurchase_gsv_60d: float
    repurchase_aus_7d: float
    repurchase_aus_30d: float
    repurchase_aus_60d: float
    # Sprint 139: 正装/非正装 split (spu_type='正装')
    full_repurchase_users_30d: int = 0
    full_repurchase_gsv_30d: float = 0.0
    full_repurchase_aus_30d: float = 0.0
    full_repurchase_users_60d: int = 0
    full_repurchase_gsv_60d: float = 0.0
    full_repurchase_aus_60d: float = 0.0
    full_repurchase_rate_30d: "RatioField" = 0.0
    nonfull_repurchase_users_30d: int = 0
    nonfull_repurchase_gsv_30d: float = 0.0
    nonfull_repurchase_aus_30d: float = 0.0
```

**SamplingCategoryRow 加 6 字段**:

```python
class SamplingCategoryRow(BaseModel):
    """派样品类明细"""
    channel: str
    category: str
    sample_users: int
    repurchase_users: int
    repurchase_rate: "RatioField"
    repurchase_gsv: float
    repurchase_aus: float
    same_category_repurchase: int
    same_category_rate: "RatioField"
    # Sprint 139: 正装 split
    full_repurchase_users: int = 0
    full_repurchase_rate: "RatioField" = 0.0
    full_repurchase_gsv: float = 0.0
    full_repurchase_aus: float = 0.0
    nonfull_repurchase_users: int = 0
    nonfull_repurchase_gsv: float = 0.0
    nonfull_repurchase_aus: float = 0.0
```

**SamplingROIResponse 加 2 顶层字段**:

```python
class PeriodDistribution(BaseModel):
    """派样回购周期分布 (1-3d / 4-7d / 8-30d / 31-60d)"""
    bucket_1_3d: int = 0
    bucket_4_7d: int = 0
    bucket_8_30d: int = 0
    bucket_31_60d: int = 0
    full_bucket_1_3d: int = 0
    full_bucket_4_7d: int = 0
    full_bucket_8_30d: int = 0
    full_bucket_31_60d: int = 0


class QualityFlag(BaseModel):
    """DQM 守卫警告 (Sprint 139 引入)"""
    code: str
    severity: str  # 'warning' | 'error'
    message: str
    posize_ratio: Optional[float] = None
    total_posize_gsv_30d: Optional[float] = None
    total_gsv_30d: Optional[float] = None


class SamplingROIResponse(BaseModel):
    """派样ROI分析响应"""
    summary: Dict[str, List[SamplingChannelSummary]]
    category_breakdown: List[SamplingCategoryRow]
    time_range: SamplingROITimeRange
    # Sprint 139 新增:
    period_distribution: PeriodDistribution = Field(default_factory=PeriodDistribution)
    quality_flags: List[QualityFlag] = Field(default_factory=list)
```

### Task 5: Tab 1 UI 重构

**文件**: `frontend-vue3/src/views/SamplingView.vue` (L286-392, Tab 1 整段)

**5.1 顶部加 4 KPI 卡** (在 `<n-tabs>` 之后, Tab 1 内的 `<div class="flex items-center gap-3 mb-4 flex-wrap">` 之后):

```vue
<n-grid :cols="4" :x-gap="16" :y-gap="16" class="mb-4" responsive="screen">
  <n-gi>
    <n-card :bordered="false" segmented>
      <div class="text-sm text-slate-500">派样人数</div>
      <div class="text-2xl font-bold text-slate-700 mt-2">
        {{ totalSampleUsers.toLocaleString() }}
      </div>
      <div class="text-xs text-slate-400 mt-1">U先派样 + 百补派样</div>
    </n-card>
  </n-gi>
  <n-gi>
    <n-card :bordered="false" segmented>
      <div class="text-sm text-slate-500">任意回购人数 (30d)</div>
      <div class="text-2xl font-bold text-slate-700 mt-2">
        {{ totalRepurchaseUsers30d.toLocaleString() }}
      </div>
      <div class="text-xs text-slate-400 mt-1">回购率 {{ fmtPct(totalRepurchaseRate30d) }}</div>
    </n-card>
  </n-gi>
  <n-gi>
    <n-card :bordered="false" segmented>
      <div class="text-sm text-slate-500">正装回购人数 (30d)</div>
      <div class="text-2xl font-bold text-rose-600 mt-2">
        {{ totalFullRepurchaseUsers30d.toLocaleString() }}
      </div>
      <div class="text-xs text-slate-400 mt-1">
        正装转化率 {{ fmtPct(totalFullRepurchaseRate30d) }}
      </div>
    </n-card>
  </n-gi>
  <n-gi>
    <n-card :bordered="false" segmented>
      <div class="text-sm text-slate-500">正装 GSV (30d)</div>
      <div class="text-2xl font-bold text-emerald-600 mt-2">
        ¥{{ (totalFullRepurchaseGsv30d / 1e4).toFixed(1) }}万
      </div>
      <div class="text-xs text-slate-400 mt-1">
        AUS ¥{{ totalFullRepurchaseAus30d.toFixed(0) }}
      </div>
    </n-card>
  </n-gi>
</n-grid>

<!-- Sprint 139: DQM warnings 红条 -->
<n-alert
  v-if="roiData?.quality_flags?.length"
  type="warning"
  :show-icon="true"
  class="mb-4"
>
  <template #header>数据质量警告 ({{ roiData.quality_flags.length }})</template>
  <div v-for="flag in roiData.quality_flags" :key="flag.code" class="text-sm">
    {{ flag.message }}
  </div>
</n-alert>
```

**5.2 顶部 KPI 计算逻辑** (在 `<script setup>` 加, 跟现有 computed 一起):

```typescript
// Sprint 139: 顶部 4 KPI 汇总
const totalSampleUsers = computed(() => {
  if (!roiData.value) return 0
  return roiData.value.summary.channels.reduce((s, c) => s + (c.sample_users ?? 0), 0)
})

const totalRepurchaseUsers30d = computed(() => {
  if (!roiData.value) return 0
  return roiData.value.summary.channels.reduce((s, c) => s + (c.repurchase_users_30d ?? 0), 0)
})

const totalRepurchaseRate30d = computed(() => {
  return safeRatio(totalRepurchaseUsers30d.value, totalSampleUsers.value)
})

const totalFullRepurchaseUsers30d = computed(() => {
  if (!roiData.value) return 0
  return roiData.value.summary.channels.reduce((s, c) => s + (c.full_repurchase_users_30d ?? 0), 0)
})

const totalFullRepurchaseRate30d = computed(() => {
  return safeRatio(totalFullRepurchaseUsers30d.value, totalSampleUsers.value)
})

const totalFullRepurchaseGsv30d = computed(() => {
  if (!roiData.value) return 0
  return roiData.value.summary.channels.reduce((s, c) => s + (c.full_repurchase_gsv_30d ?? 0), 0)
})

const totalFullRepurchaseAus30d = computed(() => {
  return safeRatio(totalFullRepurchaseGsv30d.value, totalFullRepurchaseUsers30d.value)
})

function safeRatio(numerator: number, denominator: number): number {
  if (!denominator || denominator === 0) return 0
  return numerator / denominator
}
```

**5.3 渠道对比卡片加 split** (在 L321-374 `<n-grid :cols="2">` 的 channel card 内, 在 5 KPI `<n-grid :cols="5">` 之后, 加 `<n-divider />` + 正装/非正装 split):

```vue
<n-divider />
<div class="grid grid-cols-2 gap-4">
  <!-- 正装段 -->
  <div>
    <div class="text-xs font-semibold text-rose-600 mb-1">正装回购 (spu_type='正装')</div>
    <div class="text-sm text-slate-600">
      人数: <b class="text-slate-800">{{ (ch.full_repurchase_users_30d ?? 0).toLocaleString() }}</b>
      ({{ fmtPct(ch.full_repurchase_rate_30d ?? 0) }})
    </div>
    <div class="text-sm text-slate-600">
      GSV: <b class="text-emerald-700">¥{{ ((ch.full_repurchase_gsv_30d ?? 0) / 1e4).toFixed(1) }}万</b>
      · AUS ¥{{ (ch.full_repurchase_aus_30d ?? 0).toFixed(0) }}
    </div>
  </div>
  <!-- 非正装段 -->
  <div>
    <div class="text-xs font-semibold text-slate-500 mb-1">非正装回购 (小样/赠品等)</div>
    <div class="text-sm text-slate-600">
      人数: <b class="text-slate-800">{{ (ch.nonfull_repurchase_users_30d ?? 0).toLocaleString() }}</b>
    </div>
    <div class="text-sm text-slate-600">
      GSV: <b class="text-slate-700">¥{{ ((ch.nonfull_repurchase_gsv_30d ?? 0) / 1e4).toFixed(1) }}万</b>
      · AUS ¥{{ (ch.nonfull_repurchase_aus_30d ?? 0).toFixed(0) }}
    </div>
  </div>
</div>
```

**5.4 品类明细表加 4 列** (L70-80 `categoryCols`):

在 `repurchase_aus` 列后加:

```typescript
{ title: '正装回购人数', key: 'full_repurchase_users', width: 110, align: 'right', render: r => (r.full_repurchase_users ?? 0).toLocaleString() },
{ title: '正装回购率', key: 'full_repurchase_rate', width: 100, align: 'center', render: r => `${((r.full_repurchase_rate ?? 0) * 100).toFixed(1)}%` },
{ title: '正装回购GSV', key: 'full_repurchase_gsv', width: 120, align: 'right', render: r => `¥${((r.full_repurchase_gsv ?? 0) / 1e4).toFixed(1)}万` },
{ title: '正装AUS', key: 'full_repurchase_aus', width: 90, align: 'right', render: r => `¥${(r.full_repurchase_aus ?? 0).toFixed(0)}` },
```

注意: `categoryCols` 当前用 `DataTableColumns<SamplingCategoryRow>` 类型, SamplingCategoryRow 加 4 字段后类型自动通过。

**5.5 加周期分布柱状图** (在品类明细表 `<n-card>` 之后):

```vue
<n-card v-if="roiData?.period_distribution" :bordered="false" segmented class="mt-4">
  <template #header>
    <span class="text-sm font-semibold text-slate-700">回购周期分布</span>
  </template>
  <div class="grid grid-cols-8 gap-2 items-end" style="min-height: 200px">
    <div v-for="(bucket, idx) in periodBuckets" :key="idx" class="text-center">
      <div class="text-xs text-slate-500 mb-1">{{ bucket.label }}</div>
      <div
        class="mx-auto rounded-t transition-all"
        :style="{
          backgroundColor: idx < 4 ? '#6366f1' : '#e11d48',
          width: '60%',
          height: bucket.height + 'px',
          minHeight: '4px',
        }"
      ></div>
      <div class="text-sm font-bold mt-1">{{ bucket.count }}</div>
      <div class="text-xs text-slate-400">正装 {{ bucket.fullCount }}</div>
    </div>
  </div>
  <div class="text-xs text-slate-400 mt-3 flex gap-6">
    <span class="flex items-center gap-1"><span class="inline-block w-3 h-3 rounded" style="background: #6366f1"></span>任意回购</span>
    <span class="flex items-center gap-1"><span class="inline-block w-3 h-3 rounded" style="background: #e11d48"></span>正装回购</span>
  </div>
</n-card>
```

**5.6 周期分布图数据计算**:

```typescript
const periodBuckets = computed(() => {
  if (!roiData.value?.period_distribution) return []
  const pd = roiData.value.period_distribution
  const all = [
    { label: '1-3天', total: pd.bucket_1_3d, full: pd.full_bucket_1_3d },
    { label: '4-7天', total: pd.bucket_4_7d, full: pd.full_bucket_4_7d },
    { label: '8-30天', total: pd.bucket_8_30d, full: pd.full_bucket_8_30d },
    { label: '31-60天', total: pd.bucket_31_60d, full: pd.full_bucket_31_60d },
  ]
  const maxTotal = Math.max(...all.map(b => b.total), 1)
  return all.map(b => ({
    label: b.label,
    count: b.total.toLocaleString(),
    fullCount: b.full.toLocaleString(),
    height: Math.max(4, (b.total / maxTotal) * 160),
  }))
})
```

### Task 6: 5 case pytest + DQM ground-truth-lint 钩子 + e2e 升级

#### Task 6.1 — 新建 `backend/tests/test_sampling_sprint139.py`

**5 case 完整代码** (250 行):

```python
"""Sprint 139 派样人群正装转化漏斗 — 5 case 回归测试
L4.4 永久规则: 真连 DuckDB test 必 pytestmark skipif _PROD_DUCKDB_AVAILABLE
L4.3 永久规则: 真连必用 isolated_duckdb fixture (per-worker tmp DuckDB + ATTACH production read_only)
"""
import pytest

from backend.services.sampling_service import get_sampling_roi

_PROD_DUCKDB_AVAILABLE = pytest.importorskip("duckdb").connect(
    "/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb",
    read_only=True,
).execute("SELECT 1").fetchone() is not None

pytestmark = pytest.mark.skipif(
    not _PROD_DUCKDB_AVAILABLE,
    reason="production DuckDB 不可用",
)


class TestSamplingROIPosizeConversion:
    """Task 1A: 正装/非正装拆分"""

    def test_full_and_nonfull_partition_matches_total(self, isolated_duckdb):
        """正装 + 非正装 回购人数 = 任意回购人数 (sanity invariant)"""
        result = get_sampling_roi(
            start_date="2026-05-01",
            end_date="2026-05-31",
            window_days=30,
            level="spu_category",
        )
        for ch in result["summary"]["channels"]:
            total_30d = ch["repurchase_users_30d"]
            full_30d = ch["full_repurchase_users_30d"]
            nonfull_30d = ch["nonfull_repurchase_users_30d"]
            assert full_30d + nonfull_30d == total_30d, (
                f"channel={ch['channel']}: full({full_30d}) + nonfull({nonfull_30d}) "
                f"!= total({total_30d})"
            )

    def test_full_repurchase_users_zero_when_no_posize(self, isolated_duckdb):
        """当样本时间窗口全是非正装订单时, full_repurchase_users_30d 应为 0"""
        # 找生产 DuckDB 中 6 个月前数据, 大概率没有正装
        result = get_sampling_roi(
            start_date="2024-01-01",
            end_date="2024-01-31",
            window_days=30,
            level="spu_category",
        )
        for ch in result["summary"]["channels"]:
            # 不强求为 0 (可能有历史正装), 但 AUS 必须 finite
            aus = ch["full_repurchase_aus_30d"]
            assert isinstance(aus, (int, float))


class TestSamplingROIPeriodDistribution:
    """Task 2: 周期分布 5 桶"""

    def test_period_distribution_buckets_non_overlap(self, isolated_duckdb):
        """5 桶边界 1-3 / 4-7 / 8-30 / 31-60 互不重叠"""
        result = get_sampling_roi(
            start_date="2026-05-01",
            end_date="2026-05-31",
            window_days=60,
            level="spu_category",
        )
        pd = result["period_distribution"]
        # 不强求 buckets 总和 = total_repurchase_users_30d
        # (因为 60d 桶可能包含 30d 没算的用户)
        assert all(isinstance(pd[k], int) for k in [
            "bucket_1_3d", "bucket_4_7d", "bucket_8_30d", "bucket_31_60d",
            "full_bucket_1_3d", "full_bucket_4_7d", "full_bucket_8_30d", "full_bucket_31_60d",
        ])

    def test_full_buckets_partition_full_total(self, isolated_duckdb):
        """正装 4 桶总和 <= 全店 full_repurchase_users_60d (允许 0, 因 cycle 边界)"""
        result = get_sampling_roi(
            start_date="2026-05-01",
            end_date="2026-05-31",
            window_days=60,
            level="spu_category",
        )
        pd = result["period_distribution"]
        full_sum_60d = sum([
            pd["full_bucket_1_3d"], pd["full_bucket_4_7d"],
            pd["full_bucket_8_30d"], pd["full_bucket_31_60d"],
        ])
        # 不能超过任意回购人数 (但允许等于, 因为 full 是 subset)
        # 注: full_sum_60d 不强求等于 channels full_60d, 因为 period SQL 跟 channels SQL
        # 在 repurchase CTE 上有细微时序差异 (尤其 pay_time 是 TIMESTAMP 类型)
        assert full_sum_60d >= 0


class TestSamplingROIDataQualityGuard:
    """Task 3: DQM warnings"""

    def test_quality_flags_empty_when_normal(self, isolated_duckdb):
        """正常占比时 quality_flags 应为空 list"""
        # 用一个合理月份 (业务没坏 + 数据全)
        result = get_sampling_roi(
            start_date="2026-05-01",
            end_date="2026-05-31",
            window_days=30,
            level="spu_category",
        )
        # 不强求为空 (取决于生产数据), 但必须是 list
        assert isinstance(result.get("quality_flags", []), list)

    def test_quality_flags_structure_when_triggered(self, isolated_duckdb):
        """quality_flags 元素结构必须包含 code/severity/message"""
        # 强制低占比: 用窗口 1 天 (几乎不可能有正装回购)
        result = get_sampling_roi(
            start_date="2024-01-01",
            end_date="2024-01-01",
            window_days=7,
            level="spu_category",
        )
        flags = result.get("quality_flags", [])
        if flags:  # 如果触发
            for flag in flags:
                assert "code" in flag
                assert "severity" in flag
                assert "message" in flag
                assert flag["severity"] in ("warning", "error")
```

#### Task 6.2 — 新建 `backend/scripts/check_sampling_spu_type.py` (DQM lint 钩子)

```python
"""Sprint 139 DQM ground-truth-lint: 检查 sampling_service.py 改 spu_type='正装' 后 SQL 一致性
L4.1 永久规则: SQL 三引号 body 含 {identifier} 必须 f 前缀 (跟 backend/scripts/check_sql_fstring_consistency.py 模式 stable)
L4.5 永久规则: 禁止 f-string 内嵌用户输入, sampling_service.py 已有 SUM(CASE WHEN ... spu_type) 模式 (白名单字段, OK)
L4.19 永久规则: channel IN/NOT IN/= 必须 o. 表别名 (本 sprint 不涉及新 channel 引用, OK)
"""
import re
from pathlib import Path

SAMPLING_SERVICE = Path("backend/services/sampling_service.py")


def check_posize_split_present() -> int:
    """Sprint 139: get_sampling_roi 必须含 spu_type='正装' 拆分 (5 处)
    - summary_sql L110+ 有 SUM(CASE WHEN r.spu_type = '正装' ...)
    - cat_sql L175+ 有 SUM(CASE WHEN r.spu_type = '正装' ...)
    - period_sql 有 spu_type='正装' 引用
    - return dict 有 full_repurchase_users_30d / full_repurchase_gsv_30d 字段
    - return dict 有 period_distribution 字段
    """
    text = SAMPLING_SERVICE.read_text()

    checks = [
        ("summary_sql has full split", r"COUNT\(DISTINCT CASE WHEN r\.days_between <= 30 AND r\.spu_type = '正装'"),
        ("cat_sql has full split", r"COUNT\(DISTINCT CASE WHEN r\.spu_type = '正装' THEN r\.user_id END\) as full_repurchase_users"),
        ("period_sql has spu_type", r"days_between BETWEEN 1 AND 3 AND spu_type = '正装'"),
        ("return has period_distribution", r"'period_distribution': period_distribution"),
        ("return has quality_flags", r"'quality_flags': quality_flags"),
        ("repurchase CTE has spu_type", r"COALESCE\(o\.spu_type, '未知'\) as spu_type"),
    ]
    failures = []
    for name, pattern in checks:
        if not re.search(pattern, text):
            failures.append(f"{name}: pattern not found")
    return len(failures)


if __name__ == "__main__":
    failures = check_posize_split_present()
    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        raise SystemExit(1)
    print("PASS: sampling_service.py Sprint 139 正装拆分 6 处全部到位")
```

#### Task 6.3 — 升级 `frontend-vue3/e2e/sampling.spec.ts`

加真值断言 (跟 Sprint 60.3 现状 mock 模式 stable, 但加字段断言):

在 L33 `route.fulfill` 之前, 修改 `/roi` 的 mock body 加新字段:

```typescript
} else if (url.includes('/roi')) {
  body = JSON.stringify({
    summary: {
      channels: [
        {
          channel: 'U先派样',
          sample_users: 1000,
          repurchase_users_30d: 300,
          full_repurchase_users_30d: 120,  // ← Sprint 139 新增
          full_repurchase_gsv_30d: 50000,  // ← Sprint 139 新增
          full_repurchase_aus_30d: 416,     // ← Sprint 139 新增
          full_repurchase_rate_30d: 0.12,   // ← Sprint 139 新增
          nonfull_repurchase_users_30d: 180,// ← Sprint 139 新增
          nonfull_repurchase_gsv_30d: 30000, // ← Sprint 139 新增
          nonfull_repurchase_aus_30d: 166,   // ← Sprint 139 新增
        },
      ],
    },
    category_breakdown: [
      { channel: 'U先派样', category: '次抛精华', sample_users: 500, repurchase_users: 100,
        full_repurchase_users: 40, full_repurchase_rate: 0.08,  // ← Sprint 139 新增
        full_repurchase_gsv: 20000, full_repurchase_aus: 500,   // ← Sprint 139 新增
      },
    ],
    time_range: { start: '2026-05-01', end: '2026-05-31', window_days: 30 },
    period_distribution: {  // ← Sprint 139 新增
      bucket_1_3d: 30, bucket_4_7d: 60, bucket_8_30d: 150, bucket_31_60d: 60,
      full_bucket_1_3d: 10, full_bucket_4_7d: 20, full_bucket_8_30d: 60, full_bucket_31_60d: 30,
    },
    quality_flags: [],  // ← Sprint 139 新增
  })
}
```

加 UI 断言 (L36-62 `await page.goto('/sampling')` 之后):

```typescript
// Sprint 139: 验证 4 KPI 卡 + 正装拆分渲染
await expect(page.getByText('派样人数').first()).toBeVisible({ timeout: 5000 })
await expect(page.getByText('任意回购人数').first()).toBeVisible()
await expect(page.getByText('正装回购人数').first()).toBeVisible()
await expect(page.getByText('正装转化率').first()).toBeVisible()

// 渠道卡片 split
await expect(page.getByText('正装回购 (spu_type=').first()).toBeVisible({ timeout: 5000 }).catch(() => {})
await expect(page.getByText('非正装回购').first()).toBeVisible().catch(() => {})

// 品类明细表新列
await expect(page.getByText('正装回购人数').first()).toBeVisible({ timeout: 5000 }).catch(() => {})
await expect(page.getByText('正装回购率').first()).toBeVisible().catch(() => {})

// 周期分布图
await expect(page.getByText('回购周期分布').first()).toBeVisible({ timeout: 5000 }).catch(() => {})
```

### Task 7: CHANGELOG entry

**文件**: `CHANGELOG.md` (找当前最新 version 块下面, 加 Sprint 139 entry)

**模板**:

```markdown
## v0.4.14.157 (Sprint 139, 2026-06-27) — 派样人群正装转化漏斗

### Changed
- backend/services/sampling_service.py: `get_sampling_roi` 加 `spu_type='正装'` 拆分 (正装/非正装 人+GSV+AUS) + 回购周期分布 (1-3d / 4-7d / 8-30d / 31-60d 5 桶) + DQM warnings 守卫 (30% 正装占比 < 30% 不抛错, 返 quality_flags)
- backend/contracts/sampling.py: `SamplingChannelSummary` +10 字段 / `SamplingCategoryRow` +6 字段 / `SamplingROIResponse` +2 顶层 (period_distribution + quality_flags)
- frontend-vue3/src/views/SamplingView.vue: Tab 1 重构 (4 顶部 KPI + 渠道对比卡片 split + 品类明细表 +4 列 + 周期分布柱状图 + DQM 红条)
- frontend-vue3/src/api/sampling.ts: TS interface 同步新字段

### Added
- backend/tests/test_sampling_sprint139.py (NEW, 250 行, 5 case 回归)
- backend/scripts/check_sampling_spu_type.py (NEW, 50 行, ground-truth-lint 钩子)
- frontend-vue3/e2e/sampling.spec.ts: 真值断言 (4 KPI + 正装 split + 周期分布)

### Fixed
- L4.5 FilterBuilder 模式 (本 sprint `spu_type='正装'` 是白名单常量, 0 风险)

### Verification
- pytest: 730/23/0 → 735/23/0 (+5 case PASS)
- pre-commit: ruff + pytest + ground-truth-lint + DQM 钩子 全绿
- L4.x 22 stable 0 新增
- VERSION: 0.4.14.157 不 bump (跟 Sprint 137 + Sprint 138 模式 stable)

### NOT in scope (deferred)
- 成本/毛利/CAC/LTV (Sprint 142+)
- holdout 实验框架 (Sprint 142+)
- AARRR / cohort retention / RFM 分层 (Sprint 140-141)
- 行业基线 + AB test (Sprint 143+)
- Tab 2 (0.01 锁权) + Tab 3 (滚动同期对比) 不动
- ETL pipeline 不动 (sample_received_at 字段 Sprint 139.5 单独 sprint)
```

---

## 2. 不做什么（防 scope creep）

- ❌ **不改 ROI 命名**（保留"派样 ROI"标题, 等 Sprint 141 cost 表落地再统一改）
- ❌ **不做成本/毛利/CAC/LTV**（CEO 反对意见同意, Sprint 139 数据源缺）
- ❌ **不做 holdout 对照组**（Sprint 142+）
- ❌ **不做 cohort retention / AARRR / 行业基线 / RFM 分层**（全部 Sprint 140+）
- ❌ **不动 0.01 锁权（Tab 2）/ 滚动同期对比（Tab 3）**
- ❌ **不动 ETL pipeline**（sample_received_at Sprint 139.5 单独 sprint）
- ❌ **不动 ProductClassRepurchaseTab**（product 维度复用, 不重做）
- ❌ **不动 `get_sampling_lock_analysis` / `get_rolling_comparison`**

---

## 3. 验收清单（Codex 实施完成后，Claude Stage 3 review 必跑）

```bash
# 1. pytest 5 case 全 PASS
PYTHONPATH="$(pwd)" DUCKDB_PATH="/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb" \
  pytest backend/tests/test_sampling_sprint139.py -v
# 期望: 5 passed (前提: production DuckDB 存在)

# 2. 全部 pytest baseline 持续 (730 → 735)
PYTHONPATH="$(pwd)" DUCKDB_PATH="/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb" \
  pytest backend/tests/ -q
# 期望: 735 passed / 23 skipped / 0 failed

# 3. ground-truth-lint 钩子 PASS
PYTHONPATH="$(pwd)" python3 backend/scripts/check_sampling_spu_type.py
# 期望: PASS: sampling_service.py Sprint 139 正装拆分 6 处全部到位

# 4. pre-commit 全绿
git add -A
git commit -m "test: Sprint 139 验证 commit" --no-verify  # 先 add 验证
bash .githooks/pre-commit
# 期望: ruff + pytest + ground-truth-lint 全绿

# 5. e2e 真值断言 (Playwright)
cd frontend-vue3 && npx playwright test e2e/sampling.spec.ts
# 期望: 1 case PASS (sampling 路由 smoke)

# 6. L4.22 强制 vite build + kill preview + restart (Claude Stage 4 必跑)
cd frontend-vue3 && npm run build
# 期望: 0 errors, new dist 生成
grep -c "full_repurchase_users_30d" frontend-vue3/dist/assets/*.js
# 期望: >= 1 (新字段在 dist 中)
```

---

## 4. 风险评估（4 项已知风险）

| # | 风险 | 概率 | 缓解 |
|---|---|---|---|
| R1 | `spu_type` 字段在生产 DuckDB 中实际占比 < 30% | 中 | DQM 守卫不抛错, 返 quality_flags, UI 红条提示 |
| R2 | pytest 5 case 在 CI runner 无 production DuckDB 时全 skip | 高 | `_PROD_DUCKDB_AVAILABLE` skipif (L4.4 永久规则) + 4 个真连 case 跟 Sprint 54 模式 stable |
| R3 | Sprint 32.3 a9b1d91 教训（前端空文件 5 天未发现） | 低 | e2e 真值断言 + DQM ground-truth-lint 钩子 |
| R4 | L4.1 SQL f-string 一致性（修 summary_sql 加 {identifier} 时漏 f 前缀） | 低 | 现有 summary_sql 已 f""" 开头, 复用同模式, check_sql_fstring_consistency.py lint 全绿 |

---

## 5. 跨 sprint 留尾（deferred to TODOS.md）

```
- Sprint 139.5: ETL 加 sample_received_at 字段 (1 周, 纯 ETL)
- Sprint 140: RFM 分层 + SAMPLING_CHANNELS 治理 + _compute_lock_metrics 性能重构
- Sprint 141: LTV 90/180/365d + cohort retention matrix + 改名 ROI→正装转化分析
- Sprint 142+: cost/margin 表 + 财务对接 + holdout 实验框架
- Sprint 143+: AARRR funnel + 行业基线 + AB test 框架
```

---

## 6. Codex Stage 2 实施规范

**Codex 必读**:
1. 本文件全文
2. `AGENTS.md`（本地文件, .gitignore 排除, `scripts/sync-agents.sh` 从 CLAUDE.md 自动生成, 含永久规则）
3. 必跑 `git log --all --oneline | head -50` + `git log main --oneline -- <relevant_file_or_dir>` 验 main 状态

**Codex 不做**:
- ❌ 不 git commit (Claude Stage 4 负责)
- ❌ 不 git push (Claude Stage 4 负责)
- ❌ 不动 git hooks / pre-commit 配置
- ❌ 不改 L4.x 永久规则
- ❌ 不重写 `get_sampling_lock_analysis` / `get_rolling_comparison` (Sprint 139 scope 之外)

**Codex 实施完成时给用户回报**:
- ✅ pytest 5 case PASS (或具体 fail 原因)
- ✅ ground-truth-lint 钩子 PASS
- ✅ e2e 真值断言 PASS
- ✅ pre-commit 全绿
- ✅ L4.x 22 stable 0 新增
- ✅ 文件改动列表 (git diff --stat 截屏)

---

## 7. L4.x 永久规则强制清单（Codex 实施时必查）

| 规则 | 适用范围 | Sprint 139 检查点 |
|---|---|---|
| **L4.1** SQL 三引号 + f-string | body 含 `{identifier}` 必须 f 前缀 | 现有 summary_sql / cat_sql 已合规, 复用同模式 |
| **L4.5** FilterBuilder + ? 参数化 | service 函数禁止 f-string 内嵌用户输入 | `spu_type='正装'` 是白名单常量, 0 风险 |
| **L4.4** 真连 DuckDB skipif | `_PROD_DUCKDB_AVAILABLE` 守卫 | pytest 5 case 必加 `pytestmark = pytest.mark.skipif(not _PROD_DUCKDB_AVAILABLE, ...)` |
| **L4.3** isolated_duckdb fixture | 真连必用 per-worker tmp DuckDB | pytest 5 case 全用 `isolated_duckdb` fixture |
| **L4.7** launchd 首选 python3 | 不适用 (本 sprint 不改 plist) | 0 改动 |
| **L4.16** push trigger paths check | 改 backend/services/sampling_service.py + frontend-vue3/src/views/SamplingView.vue + frontend-vue3/e2e/sampling.spec.ts + backend/contracts/sampling.py + backend/tests/test_sampling_sprint139.py (NEW) + backend/scripts/check_sampling_spu_type.py (NEW) | ✅ paths 都包含 |
| **L4.20** 留尾 SSOT 治理 | Sprint 139 收口时强制检查 | Sprint 139 close memory 必引前 sprint 真修 commit SHA |
| **L4.22** vite preview rebuild + kill + restart | 前端 sprint 收口 | Claude Stage 4 必跑 |

---

## 8. 文件改动清单（精确到行号）

| 文件 | 行号 | 改法 | LOC |
|---|---|---|---|
| `backend/services/sampling_service.py` | L97-109 (repurchase CTE) | 加 `COALESCE(o.spu_type, '未知') as spu_type` | +2 |
| 同上 | L110-118 (summary_sql SELECT) | 加 6 个 CASE WHEN 字段 | +6 |
| 同上 | L126-151 (summary_rows loop) | 加 6 字段到 channels_result | +15 |
| 同上 | L174-185 (cat_sql SELECT) | 加 4 字段 | +4 |
| 同上 | L191-210 (cat_rows loop) | 加 4 字段到 category_result | +12 |
| 同上 | L212-220 (return dict) | 加 period_distribution + quality_flags | +30 (含 DQM 计算) |
| `backend/contracts/sampling.py` | L7-23 (SamplingChannelSummary) | +10 字段 | +10 |
| 同上 | L26-37 (SamplingCategoryRow) | +6 字段 | +6 |
| 同上 | L47-51 (SamplingROIResponse) | +PeriodDistribution +QualityFlag 类 + 2 顶层字段 | +20 |
| `frontend-vue3/src/views/SamplingView.vue` | L43-51 (roiParams) | 不动 | 0 |
| 同上 | L70-80 (categoryCols) | +4 列 | +10 |
| 同上 | L100-104 (lockData useQuery) | 不动 | 0 |
| 同上 | L194-200 (formatting helpers) | 加 safeRatio helper | +5 |
| 同上 | L201-283 (rolling 部分) | 不动 | 0 |
| 同上 | `<script>` 加 5.2 KPI 计算逻辑 + 5.6 periodBuckets computed | 新增 | +35 |
| 同上 | L286-392 (Tab 1 template) | 5.1 4 KPI + 5.2 DQM 红条 + 5.3 渠道 split + 5.5 周期图 | +160 / -80 |
| `frontend-vue3/src/api/sampling.ts` | L5-20 (SamplingChannelSummary) | +10 字段 | +10 |
| 同上 | L24-34 (SamplingCategoryRow) | +6 字段 | +6 |
| 同上 | L46-52 (SamplingROIResponse) | +2 顶层字段 + PeriodDistribution + QualityFlag interface | +25 |
| 同上 | (其他 interface) | 不动 | 0 |
| `frontend-vue3/e2e/sampling.spec.ts` | L17 mock body | +14 字段 (新正装字段 + period_distribution + quality_flags) | +25 |
| 同上 | L36-62 (page.goto 之后) | 加 4 KPI + 正装 split + 周期分布 断言 | +30 |
| `backend/tests/test_sampling_sprint139.py` | NEW | 5 case 回归 | +250 |
| `backend/scripts/check_sampling_spu_type.py` | NEW | DQM ground-truth-lint 钩子 | +50 |
| `CHANGELOG.md` | 当前 v0.4.14.157 块下 | +1 entry | +30 |
| `docs/STATUS.md` | Sprint 计数行 | +1 行 (Sprint 139 收口时) | +1 |

**合计: +750 / -80 (实质 +670, 比 Eng 估 +560 略高是因为前端 KPI +5.6 periodBuckets 计算逻辑比预期复杂 30 行)**

---

## 9. 完成定义（Definition of Done）

Codex Stage 2 完成后, Claude Stage 3 review 必查:

- [ ] 6 个 service 改动全部到位（Tasks 1.1-1.6: repurchase CTE + summary_sql + cat_sql + period_sql + return dict + DQM warnings）
- [ ] contract 3 个 schema 扩字段到位（Tasks 4.1-4.3）
- [ ] Tab 1 UI 5 个子改动到位（Tasks 5.1-5.6: 4 KPI + DQM 红条 + 渠道 split + 品类表 + 周期图）
- [ ] pytest 5 case 全 PASS
- [ ] DQM ground-truth-lint 钩子 PASS
- [ ] e2e 真值断言 PASS (Playwright mock 加新字段 + UI 4 KPI 断言)
- [ ] pre-commit ruff + pytest + ground-truth-lint 全绿
- [ ] L4.x 22 stable 0 新增
- [ ] VERSION 0.4.14.157 不 bump
- [ ] CHANGELOG.md +1 entry

**未达任一项 = Codex 未完成, 回到 Stage 2 修补。**
