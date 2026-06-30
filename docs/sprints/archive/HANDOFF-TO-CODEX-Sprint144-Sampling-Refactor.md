# Sprint 144 HANDOFF — Sampling 板块重构

> **目标**: Sampling 板块顶部筛选解耦到全局 AppFilterBar + TTL 派样聚合 (U先∪百补, user_id 去重) + 渠道卡 3 列对齐 + YOY/MOM 同比环比 + 5 个 section 标题化
>
> **Branch**: `feature/sprint144-sampling-refactor`
> **Main HEAD**: `5bd1754` (Sprint 143 merge, 0 drift)
> **VERSION**: 不 bump (留尾治理 sprint 模式, 累计 67 sprint 0 debt)
> **Sprint 模式**: 真业务 sprint (user 报 "我需要做 sampling 调整")
> **Codex**: Stage 2 实施 (Claude Stage 1 架构 → Codex Stage 2 → Claude Stage 3 review)

---

## 0. ⚠️ 改代码前必读 (CLAUDE.md §强制自检)

1. **当前分支检查**: `git branch --show-current` — 必须在 `feature/sprint144-sampling-refactor` 上, 不在 main
2. **走完整 12 步流程**: review → qa → merge → push → pull → restart (L4.15)
3. **AI write safety net**:
   - L4.2 任何 SQL 三引号赋值若 body 含 `{identifier}` 必须 f-string 前缀
   - L4.5 service 必须用 FilterBuilder + `?` 参数化, 禁止 f-string 内嵌用户输入
   - L4.19 service 输出 SQL `channel IN/NOT IN/=` 必须有 `o.` 表别名
4. **Schema 三同步** (CLAUDE.md §接口开发六步): service 改字段 → `contracts/sampling.py` → 前端 `api/sampling.ts`
5. **Ratio Convention** (CLAUDE.md §B1+B2): yoy_* 字段必须用 `PpField` / `PercentageField` 强类型, 禁止裸 `float`
6. **契约 lint**: 改 `backend/contracts/*.py` 必跑 `python -m backend.contracts._lint`
7. **TTL 派样核心定义** (本 sprint 重定义): TTL派样 = U先派样 ∪ 百补派样, **用户 ID 去重**, GSV/AUS 是 SUM (详见 §3.3)

---

## 1. Sprint 范围

### 1.1 In Scope

| # | 内容 | 类型 |
|---|---|---|
| A | SamplingView 顶部时间/渠道/低价筛选 解耦 → filterStore | 前端 |
| B | 删除 SamplingView 本地 `roiDateRange` ref + 时间选择器 UI | 前端 |
| C | **新增 TTL 派样聚合**: 后端 UNION ALL (U先∪百补) + user_id COUNT DISTINCT | 后端 |
| D | 渠道对比卡 cols 2 → 3 (TTL 在最前, U先/百补 跟后) | 前端 |
| E | get_sampling_roi 加 `compare_date_range` 参数 + 返回 yoy_* / mom_* 字段 | 后端 + 契约 |
| F | SamplingChannelSummary contract 加 yoy_pct / yoy_pp per metric | 契约 |
| G | 加 5 个 section 标题: 总览 / 汇总 / 各板块情况 / 派样明细 / 回购周期分布 | 前端 |
| H | 回购周期分布 section: 4 桶聚合 (0-7d / 8-30d / 31-60d / 61-90d) + 柱状图 | 后端 + 前端 |

### 1.2 NOT in Scope

- **不动 SAMPLING_CHANNELS** (保持 `['U先派样', '百补派样']`, TTL 是聚合层不是 channel 值)
- ETL 改造 (本期不需要)
- 新增第三个 tab
- 顶部全局筛选加新字段
- windowDays / categoryLevel 仍然保留本地 ref (sampling 独有)

---

## 2. 关键决策 (user 拍板)

| # | 决策 | 方案 |
|---|---|---|
| **D1** | **TTL 派样定义** | **U先派样 ∪ 百补派样, user_id COUNT DISTINCT 去重**, GSV/AUS 是 SUM。**TTL 不是新 channel 值, 不动 SAMPLING_CHANNELS** |
| D2 | 回购周期分布 | 本期做完整, 4 桶聚合 + 柱状图 |
| D3 | YOY/MOM 状态归属 | 复用 `filterStore.compareMode`, 0 新状态 |
| D4 | 卡片高度一致性 | n-card h-full + grid item-responsive (Tailwind 默认 stretch) |
| D5 | TTL 卡 UI 标识 | 紫色 (`text-purple-600`), 加 "全渠道汇总" 副标题 |

---

## 3. 当前架构 (改前必读)

### 3.1 前端

| 文件 | 关键内容 |
|---|---|
| `frontend-vue3/src/components/AppFilterBar.vue` | 全局筛选 (dateRange / periodType / channel / excludeLowPrice / compareMode / compareDateRange) |
| `frontend-vue3/src/stores/filterStore.ts` | pinia store, 6 字段 + 3 computed |
| `frontend-vue3/src/views/SamplingView.vue` | Tab 1 派样正装转化 (~750 行, L400-700+) |
| `frontend-vue3/src/api/sampling.ts` | fetchSamplingROI / fetchSamplingLockAnalysis / fetchRollingComparison |

**SamplingView 现状关键代码** (L20-22, 407-432):
```ts
const roiDateRange = ref<[number, number] | null>(null)  // 本地, 跟 filterStore 零联动
const windowDays = ref(30)                                // 保留本地 (sampling 独有)
const categoryLevel = ref('spu_category')                 // 保留本地 (sampling 独有)
```

**渠道对比卡** (L545-588, 当前 cols=2):
```vue
<n-grid :cols="2" :x-gap="16" :y-gap="16" class="mb-6" responsive="screen">
  <n-gi v-for="ch in roiData.summary.channels" :key="ch.channel">
    <n-card :bordered="false" segmented>...</n-card>
  </n-gi>
</n-grid>
```

### 3.2 后端

| 文件 | 关键内容 |
|---|---|
| `backend/services/sampling_service.py:21` | `SAMPLING_CHANNELS = ['U先派样', '百补派样']` **本期保持不变** |
| `backend/services/sampling_service.py:38-200` | `get_sampling_roi(start_date, end_date, window_days, level, channel)` |
| `backend/contracts/sampling.py` | `SamplingLevelSummary` + `SamplingChannelSummary` (加 yoy 字段) |
| `backend/semantic/calculations.py:14` | `yoy_absolute()` / `yoy_ratio()` 已实现 (锁权分析已用) |

### 3.3 TTL 派样聚合架构 (新增)

```
单渠道 (现有):
  orders WHERE channel IN ('U先派样', '百补派样')
    → GROUP BY channel → 2 行 (U先/百补)

TTL 聚合 (新增):
  orders WHERE channel IN ('U先派样', '百补派样')
    → UNION ALL user_id + GROUP BY user_id (取 MIN first_sample_time)
    → 跟原 sample_users 一样的 repurchase 逻辑
    → 1 行 (TTL)

最终 channels_result 顺序:
  [0] TTL派样    (聚合)
  [1] U先派样
  [2] 百补派样
```

**TTL 聚合 SQL 关键点**:
- `sample_users` = COUNT(DISTINCT user_id) — 去重
- `repurchase_users` = COUNT(DISTINCT user_id) where window_days — 去重
- `repurchase_gsv` = SUM(actual_amount) — 不去重 (一个人买多次算多次)
- `repurchase_aus` = safe_ratio(GSV, repurchase_users) — 跟单渠道算法一致
- 正装/非正装 同结构

---

## 4. 实施步骤

### Step 1: 创建 feature branch + 前期验证

```bash
cd /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics
git checkout main
git pull origin main --ff-only
git checkout -b feature/sprint144-sampling-refactor
```

**DB 验证** (确认 U先/百补 渠道存在, TTL 是后端聚合不需 DB 验证):
```bash
PYTHONPATH="$(pwd)" python3 -c "
import duckdb
conn = duckdb.connect('data/processed/fuqing_crm.duckdb', read_only=True)
rows = conn.execute(\"\"\"
  SELECT DISTINCT channel FROM orders
  WHERE channel IN ('U先派样', '百补派样')
  ORDER BY channel
\"\"\").fetchall()
print(f'渠道数: {len(rows)} (期望 2)')
for r in rows: print(r[0])
"
```

### Step 2: Backend 改造

#### 2.1 修改 `backend/services/sampling_service.py`

**SAMPLING_CHANNELS 不动** (L21):
```python
SAMPLING_CHANNELS = ['U先派样', '百补派样']  # 保持不变
```

**新增私有函数 `_compute_ttl_metrics()`** (放在 SAMPLING_CHANNELS 下面):

```python
def _compute_ttl_metrics(
    start_date: str,
    end_date: str,
    window_days: int = 30,
) -> Dict[str, Any]:
    """
    TTL 派样聚合 = U先派样 ∪ 百补派样, user_id COUNT DISTINCT 去重。

    Sprint 144 重定义: TTL 不是新 channel 值, 是后端聚合层。
    人数 = COUNT DISTINCT user_id (去重)
    GSV/AUS = SUM (不去重, 一个人买多次算多次)
    """
    conn = get_connection()
    try:
        ttl_sql = """
            WITH sample_users AS (
                SELECT user_id, MIN(o.pay_time) as first_sample_time
                FROM orders o
                WHERE o.channel IN (?, ?)
                  AND o.pay_time >= ?::TIMESTAMP
                  AND o.pay_time <= ?::TIMESTAMP + INTERVAL '1' DAY
                GROUP BY o.user_id
            ),
            repurchase AS (
                SELECT su.user_id, su.first_sample_time,
                       o.actual_amount,
                       COALESCE(o.spu_type, '未知') as spu_type,
                       DATEDIFF('day', su.first_sample_time, o.pay_time) as days_between
                FROM sample_users su
                JOIN orders o ON su.user_id = o.user_id
                WHERE o.pay_time > su.first_sample_time
                  AND DATEDIFF('day', su.first_sample_time, o.pay_time) <= ?
                  AND o.is_refund = FALSE
                  AND o.order_status != '交易关闭'
                  AND o.channel != '购物金'
            )
            SELECT
                COUNT(DISTINCT su.user_id) as sample_users,
                COUNT(DISTINCT CASE WHEN r.days_between <= ? THEN r.user_id END) as repurchase_users,
                SUM(CASE WHEN r.days_between <= ? THEN r.actual_amount ELSE 0 END) as repurchase_gsv,
                COUNT(DISTINCT CASE WHEN r.days_between <= ? AND r.spu_type = '正装' THEN r.user_id END) as full_repurchase_users,
                SUM(CASE WHEN r.days_between <= ? AND r.spu_type = '正装' THEN r.actual_amount ELSE 0 END) as full_repurchase_gsv,
                COUNT(DISTINCT CASE WHEN r.days_between <= ? AND r.spu_type != '正装' THEN r.user_id END) as nonfull_repurchase_users,
                SUM(CASE WHEN r.days_between <= ? AND r.spu_type != '正装' THEN r.actual_amount ELSE 0 END) as nonfull_repurchase_gsv
            FROM sample_users su
            LEFT JOIN repurchase r ON su.user_id = r.user_id
        """
        # ?顺序: 2 channel + 2 date + 1 window + 6 window = 11
        params = ['U先派样', '百补派样', start_date, end_date, window_days] + [window_days] * 6
        row = conn.execute(ttl_sql, params).fetchone()

        if not row:
            return _empty_channel_metrics('TTL派样')

        sample_users = int(row[0] or 0)
        repurchase_users = int(row[1] or 0)
        repurchase_gsv = float(row[2] or 0)
        full_users = int(row[3] or 0)
        full_gsv = float(row[4] or 0)
        nonfull_users = int(row[5] or 0)
        nonfull_gsv = float(row[6] or 0)

        return {
            'channel': 'TTL派样',
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
        }
    finally:
        # ETL 脚本连接例外: get_connection() 单例, 不 close
        pass
```

**新增 helper `_empty_channel_metrics()`** (放在 _compute_ttl_metrics 上面):
```python
def _empty_channel_metrics(channel: str) -> Dict[str, Any]:
    """空指标模板, 用于 DB 没数据时返回"""
    return {
        'channel': channel,
        'sample_users': 0,
        'repurchase_users': 0,
        'repurchase_rate': 0.0,
        'repurchase_gsv': 0.0,
        'repurchase_aus': 0.0,
        'full_repurchase_users': 0,
        'full_repurchase_rate': 0.0,
        'full_repurchase_gsv': 0.0,
        'full_repurchase_aus': 0.0,
        'nonfull_repurchase_users': 0,
        'nonfull_repurchase_gsv': 0.0,
        'nonfull_repurchase_aus': 0.0,
    }
```

**修改 `get_sampling_roi()`** (L38-200):

函数签名加 `compare_date_range`:
```python
def get_sampling_roi(
    start_date: str,
    end_date: str,
    window_days: int = 30,
    level: str = 'spu_category',
    channel: Optional[str] = None,
    compare_date_range: Optional[Tuple[str, str]] = None,
) -> Dict[str, Any]:
```

**关键改动**: channels_result 拼接 (L133-160 之后):

```python
# 现有逻辑: summary_rows 跑单渠道 (U先/百补) GROUP BY channel
summary_rows = conn.execute(summary_sql, summary_params).fetchall()

single_channel_result = []
for row in summary_rows:
    # ... 现有逻辑 ...
    single_channel_result.append({...})

# 新增: TTL 聚合行 (放在最前)
ttl_row = _compute_ttl_metrics(start_date, end_date, window_days)

# 顺序: TTL 在前 (聚合视图), 单渠道在后 (明细)
channels_result = [ttl_row] + single_channel_result
```

**YOY/MOM 计算** (新增 compare_date_range 分支):
```python
if compare_date_range:
    cmp_start, cmp_end = compare_date_range
    # TTL 对比窗口
    ttl_compare = _compute_ttl_metrics(cmp_start, cmp_end, window_days)
    # 单渠道对比窗口 (复用现有 summary_sql, 改日期范围)
    cmp_summary_params = sample_params_for_compare + [window_days] * 7  # 类似 summary_params
    cmp_summary_rows = conn.execute(summary_sql, cmp_summary_params).fetchall()
    # ... 跟当前逻辑一样构造 single_channel_compare_result ...

    # 计算 yoy_* / mom_* per channel
    for i, ch in enumerate(channels_result):
        cmp_ch = (
            ttl_compare if ch['channel'] == 'TTL派样'
            else next((c for c in cmp_single_result if c['channel'] == ch['channel']), None)
        )
        if cmp_ch:
            ch['repurchase_users_yoy_pct'] = round(yoy_absolute(ch['repurchase_users'], cmp_ch['repurchase_users']), 2)
            ch['repurchase_gsv_yoy_pct'] = round(yoy_absolute(ch['repurchase_gsv'], cmp_ch['repurchase_gsv']), 2)
            ch['repurchase_rate_yoy_pp'] = round(yoy_ratio(ch['repurchase_rate'], cmp_ch['repurchase_rate']), 2)
            # ... full_repurchase_*, nonfull_repurchase_* 同结构 ...
```

**新增 `get_sampling_repurchase_buckets()`** (TTL/单渠道共用, 4 桶聚合):

```python
def get_sampling_repurchase_buckets(
    start_date: str,
    end_date: str,
    window_days: int = 90,
    channel: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    回购周期分布: 0-7d / 8-30d / 31-60d / 61-90d

    channel='TTL派样' → UNION 聚合; channel='U先派样'/'百补派样' → 单渠道
    channel=None → 默认 TTL
    """
    if channel is None or channel == 'TTL派样':
        # UNION 聚合逻辑 (跟 _compute_ttl_metrics 的 sample_users 一样)
        sample_users_sql = """
            SELECT user_id, MIN(o.pay_time) as first_sample_time
            FROM orders o
            WHERE o.channel IN (?, ?)
              AND o.pay_time >= ?::TIMESTAMP AND o.pay_time <= ?::TIMESTAMP + INTERVAL '1' DAY
            GROUP BY o.user_id
        """
        sample_params = ['U先派样', '百补派样', start_date, end_date]
    else:
        db_channels = expand_channels([channel])
        ch_placeholders = ','.join(['?'] * len(db_channels))
        sample_users_sql = f"""
            SELECT user_id, MIN(o.pay_time) as first_sample_time
            FROM orders o
            WHERE o.channel IN ({ch_placeholders})
              AND o.pay_time >= ?::TIMESTAMP AND o.pay_time <= ?::TIMESTAMP + INTERVAL '1' DAY
            GROUP BY o.user_id
        """
        sample_params = db_channels + [start_date, end_date]

    bucket_sql = f"""
        WITH sample_users AS ({sample_users_sql}),
        repurchase AS (
            SELECT su.user_id, su.first_sample_time,
                   o.actual_amount,
                   DATEDIFF('day', su.first_sample_time, o.pay_time) as days_between
            FROM sample_users su
            JOIN orders o ON su.user_id = o.user_id
            WHERE o.pay_time > su.first_sample_time
              AND DATEDIFF('day', su.first_sample_time, o.pay_time) <= ?
              AND o.is_refund = FALSE
              AND o.order_status != '交易关闭'
              AND o.channel != '购物金'
        )
        SELECT
            CASE
                WHEN days_between <= 7 THEN '0-7d'
                WHEN days_between <= 30 THEN '8-30d'
                WHEN days_between <= 60 THEN '31-60d'
                ELSE '61-90d'
            END as bucket,
            COUNT(DISTINCT user_id) as users,
            SUM(actual_amount) as gsv
        FROM repurchase
        GROUP BY bucket
        ORDER BY bucket
    """
    conn = get_connection()
    rows = conn.execute(bucket_sql, sample_params + [window_days]).fetchall()

    # 补全缺失桶
    bucket_map = {row[0]: (int(row[1] or 0), float(row[2] or 0)) for row in rows}
    result = []
    for bucket in ['0-7d', '8-30d', '31-60d', '61-90d']:
        users, gsv = bucket_map.get(bucket, (0, 0.0))
        result.append({
            'bucket': bucket,
            'users': users,
            'gsv': round(gsv, 2),
            'aus': round(safe_ratio(gsv, users), 2),
        })
    return result
```

#### 2.2 修改 `backend/contracts/sampling.py`

**SamplingChannelSummary 加 yoy 字段** (per metric, 全部 Optional):
```python
class SamplingChannelSummary(BaseModel):
    channel: str
    sample_users: int
    repurchase_users: int
    repurchase_rate: float
    repurchase_gsv: float
    repurchase_aus: float
    full_repurchase_users: int
    full_repurchase_rate: float
    full_repurchase_gsv: float
    full_repurchase_aus: float
    nonfull_repurchase_users: int
    nonfull_repurchase_gsv: float
    nonfull_repurchase_aus: float
    # 新增 YOY (compare_date_range 不为空时有值)
    repurchase_users_yoy_pct: Optional[PercentageField] = None
    repurchase_gsv_yoy_pct: Optional[PercentageField] = None
    repurchase_rate_yoy_pp: Optional[PpField] = None
    full_repurchase_users_yoy_pct: Optional[PercentageField] = None
    full_repurchase_gsv_yoy_pct: Optional[PercentageField] = None
    full_repurchase_rate_yoy_pp: Optional[PpField] = None
    # MOM 字段同结构 (本期可选, 跟 compare_date_range 模式联动)
    repurchase_users_mom_pct: Optional[PercentageField] = None
    repurchase_gsv_mom_pct: Optional[PercentageField] = None
    repurchase_rate_mom_pp: Optional[PpField] = None
```

**新增 `SamplingRepurchaseBucket` + `SamplingRepurchaseDistribution`**:
```python
class SamplingRepurchaseBucket(BaseModel):
    bucket: str  # '0-7d' | '8-30d' | '31-60d' | '61-90d'
    users: int
    gsv: float
    aus: float

class SamplingRepurchaseDistribution(BaseModel):
    buckets: List[SamplingRepurchaseBucket]
    window_days: int
```

**`SamplingLevelSummary`** 加字段:
```python
class SamplingLevelSummary(BaseModel):
    # 现有字段...
    repurchase_distribution: Optional[SamplingRepurchaseDistribution] = None
```

#### 2.3 修改 `backend/routers/sampling.py` (如果有)

透传 `compare_date_range` 参数到 service。检查现有 router 调用。

### Step 3: Frontend 改造

#### 3.1 修改 `frontend-vue3/src/api/sampling.ts`

`fetchSamplingROI` 签名加 `compare_date_range` 参数:
```ts
export async function fetchSamplingROI(params: {
  start_date: string
  end_date: string
  window_days: number
  level: string
  channel?: string
  compare_date_range?: [string, string] | null  // 新增
  exclude_low_price?: boolean                    // 新增透传
}): Promise<SamplingROIData>
```

`compare_date_range` 从 `filterStore.compareParams` 读 (`null` = auto_yoy 不传后端; tuple = auto_mom/custom 传)。

新增 `fetchSamplingRepurchaseDistribution`:
```ts
export async function fetchSamplingRepurchaseDistribution(params: {
  start_date: string
  end_date: string
  window_days: number
  channel?: string
}): Promise<{ buckets: SamplingRepurchaseBucket[]; window_days: number }>
```

#### 3.2 修改 `frontend-vue3/src/views/SamplingView.vue`

**删除** (L20, L49-53, L407-414):
```ts
// L20 整行
const roiDateRange = ref<[number, number] | null>(null)

// L49-53 默认日期逻辑 (改用 filterStore.dateRange)
const now = new Date()
const defaultStart = new Date(now.getFullYear(), now.getMonth(), 1)
const defaultEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0)
roiDateRange.value = [defaultStart.getTime(), defaultEnd.getTime()]

// L407-414 时间选择器 UI (整段删除)
<n-date-picker v-model:value="roiDateRange" type="daterange" clearable style="width: 280px" size="small" />
```

**改 `roiParams`** (L55-63):
```ts
import { useFilterStore } from '@/stores/filterStore'

const filterStore = useFilterStore()

const roiParams = computed(() => ({
  start_date: filterStore.dateRange[0],
  end_date: filterStore.dateRange[1],
  window_days: windowDaysDebounced.value,
  level: categoryLevel.value,
  channel: filterStore.channel === '全店' ? undefined : filterStore.channel,
  compare_date_range: filterStore.compareParams,
  exclude_low_price: filterStore.excludeLowPrice,
}))
```

**改 useQuery enabled** (L68):
```ts
enabled: computed(() => activeTab.value === 'roi'),
```

**保留本地 ref**: `windowDays` / `windowDaysDebounced` / `categoryLevel` / `levelOptions` / `sliderMarks` / debounce 逻辑全部不变。

**改渠道对比卡** (L545):
```vue
<h2 class="text-base font-semibold text-slate-800 mb-3">🏷️ 各派样渠道情况</h2>
<n-grid :cols="3" :x-gap="16" :y-gap="16" class="mb-6" responsive="screen" item-responsive>
  <n-gi v-for="ch in roiData.summary.channels" :key="ch.channel" span="1 m:1 l:1">
    <n-card :bordered="false" segmented class="h-full">
      <template #header>
        <div class="flex items-baseline gap-2">
          <span class="text-base font-bold" :class="channelColorClass(ch.channel)">
            {{ ch.channel }}
          </span>
          <span v-if="ch.channel === 'TTL派样'" class="text-xs font-normal text-slate-400">
            (全渠道汇总)
          </span>
        </div>
      </template>

      <n-grid :cols="5" :x-gap="12">
        <n-gi><n-statistic label="派样人数" :value="ch.sample_users" /></n-gi>
        <n-gi>
          <n-statistic label="回购人数" :value="ch.repurchase_users ?? 0">
            <template #default>
              <div class="flex items-baseline gap-1">
                <span class="text-slate-700 font-bold">{{ (ch.repurchase_users ?? 0).toLocaleString() }}</span>
                <YOYBadge v-if="ch.repurchase_users_yoy_pct != null" :value="ch.repurchase_users_yoy_pct" unit="%" size="tiny" />
              </div>
            </template>
          </n-statistic>
        </n-gi>
        <n-gi>
          <n-statistic label="回购率">
            <template #default>
              <div class="flex items-baseline gap-1">
                <span class="text-indigo-600 font-bold">{{ ((ch.repurchase_rate ?? 0) * 100).toFixed(1) }}%</span>
                <YOYBadge v-if="ch.repurchase_rate_yoy_pp != null" :value="ch.repurchase_rate_yoy_pp" unit="pp" size="tiny" />
              </div>
            </template>
          </n-statistic>
        </n-gi>
        <n-gi>
          <n-statistic label="贡献GSV">
            <template #default>
              <div class="flex items-baseline gap-1">
                <span class="text-emerald-600 font-bold">¥{{ ((ch.repurchase_gsv ?? 0) / 1e4).toFixed(1) }}万</span>
                <YOYBadge v-if="ch.repurchase_gsv_yoy_pct != null" :value="ch.repurchase_gsv_yoy_pct" unit="%" size="tiny" />
              </div>
            </template>
          </n-statistic>
        </n-gi>
        <n-gi>
          <n-statistic label="AUS">
            <template #default>
              <span class="text-sky-600 font-bold">¥{{ (ch.repurchase_aus ?? 0).toFixed(0) }}</span>
            </template>
          </n-statistic>
        </n-gi>
      </n-grid>

      <n-divider />
      <div class="flex items-center gap-6 text-sm text-slate-500">
        <span>{{ windowDays }}天回购: <b class="text-slate-700">{{ (ch.repurchase_users ?? 0).toLocaleString() }}</b> 人</span>
        <span>贡献GSV: <b class="text-slate-700">¥{{ ((ch.repurchase_gsv ?? 0) / 1e4).toFixed(1) }}万</b></span>
        <span>AUS: <b class="text-slate-700">¥{{ (ch.repurchase_aus ?? 0).toFixed(0) }}</b></span>
      </div>

      <n-divider />
      <div class="grid grid-cols-2 gap-4">
        <div>
          <div class="text-xs font-semibold text-rose-600 mb-1">{{ windowDays }}天正装回购</div>
          <div class="text-sm text-slate-600"> 人数: <b class="text-slate-800">{{ ch.full_repurchase_users }}</b> ({{ fmtPct(ch.full_repurchase_rate) }}) </div>
          <div class="text-sm text-slate-600"> GSV: <b class="text-emerald-700">¥{{ (ch.full_repurchase_gsv / 1e4).toFixed(1) }}万</b> · AUS ¥{{ ch.full_repurchase_aus.toFixed(0) }}</div>
        </div>
        <div>
          <div class="text-xs font-semibold text-slate-500 mb-1">非正装回购 (小样/赠品等)</div>
          <div class="text-sm text-slate-600"> 人数: <b class="text-slate-800">{{ ch.nonfull_repurchase_users }}</b></div>
          <div class="text-sm text-slate-600"> GSV: <b class="text-slate-700">¥{{ (ch.nonfull_repurchase_gsv / 1e4).toFixed(1) }}万</b> · AUS ¥{{ ch.nonfull_repurchase_aus.toFixed(0) }}</div>
        </div>
      </div>
    </n-card>
  </n-gi>
</n-grid>
```

**channelColorClass helper** (新增):
```ts
function channelColorClass(channel: string): string {
  if (channel === 'TTL派样') return 'text-purple-600'  // 紫色, 区分单渠道
  if (channel === 'U先派样') return 'text-rose-600'
  if (channel === '百补派样') return 'text-orange-500'
  return 'text-slate-600'
}
```

**新增 5 个 section 标题** (在 ROI tab 内, 用 `<h2>`):
1. **总览** — L447 n-grid 上方: `<h2 class="text-base font-semibold text-slate-800 mb-3">📊 总览</h2>`
2. **汇总** — L502 上方: `<h2 class="text-base font-semibold text-slate-800 mb-3">📈 {{ levelLabel }}汇总</h2>`
3. **各板块情况** — L545 上方: `<h2 class="text-base font-semibold text-slate-800 mb-3">🏷️ 各派样渠道情况</h2>`
4. **派样明细** — L601 上方: `<h2 class="text-base font-semibold text-slate-800 mb-3">📋 派样明细 (按 {{ levelLabel }})</h2>`
5. **回购周期分布** — 新增 section: `<h2 class="text-base font-semibold text-slate-800 mb-3">⏱️ 回购周期分布</h2>`

**回购周期分布 section** (新增, 紧跟派样明细):
```vue
<div v-if="repurchaseDistribution" class="mb-6">
  <h2 class="text-base font-semibold text-slate-800 mb-3">⏱️ 回购周期分布</h2>
  <n-card :bordered="false" segmented>
    <div class="grid grid-cols-4 gap-4">
      <div v-for="bucket in repurchaseDistribution.buckets" :key="bucket.bucket" class="text-center p-4 rounded bg-slate-50">
        <div class="text-sm font-semibold text-slate-600 mb-2">{{ bucket.bucket }}</div>
        <div class="text-2xl font-bold text-indigo-600">{{ bucket.users.toLocaleString() }} 人</div>
        <div class="text-sm text-slate-500 mt-1">GSV ¥{{ (bucket.gsv / 1e4).toFixed(1) }}万</div>
        <div class="text-xs text-slate-400 mt-1">AUS ¥{{ bucket.aus.toFixed(0) }}</div>
      </div>
    </div>
  </n-card>
</div>
```

**新增 useQuery**:
```ts
const { data: repurchaseDistribution } = useQuery({
  queryKey: computed(() => ['sampling-repurchase-distribution', roiParams.value]),
  queryFn: () => fetchSamplingRepurchaseDistribution({
    start_date: roiParams.value.start_date,
    end_date: roiParams.value.end_date,
    window_days: 90,
    channel: roiParams.value.channel,  // undefined = 默认 TTL
  }),
  enabled: computed(() => activeTab.value === 'roi'),
  placeholderData: previousData => previousData,
})
```

### Step 4: 契约 lint + pytest

```bash
# 契约 lint (CLAUDE.md §AI 执行检查点 - 改 contract 字段强制)
PYTHONPATH="$(pwd)" python -m backend.contracts._lint

# 全量 pytest
PYTHONPATH="$(pwd)" pytest backend/tests/ -x -q

# 针对性 pytest (新增 sampling 相关)
PYTHONPATH="$(pwd)" pytest backend/tests/test_sampling_service.py -v -x
PYTHONPATH="$(pwd)" pytest backend/tests/test_sampling_ttl_aggregation.py -v -x  # 新增
PYTHONPATH="$(pwd)" pytest backend/tests/test_sampling_roi_yoy.py -v -x  # 新增
PYTHONPATH="$(pwd)" pytest backend/tests/test_sampling_repurchase_distribution.py -v -x  # 新增
```

### Step 5: 前端 build + vite preview restart

```bash
cd frontend-vue3 && npm run build

# 验证 dist
grep -c "TTL派样" dist/assets/*.js  # 期望 ≥ 1
grep -c "全渠道汇总" dist/assets/*.js  # 期望 ≥ 1
grep -c "/visitor" dist/assets/*.js  # 期望 0 (L4.22)

# kill 旧 vite preview + restart
ps aux | grep "vite preview" | grep -v grep | awk '{print $2}' | xargs kill
nohup npx vite preview --port 5173 --host 0.0.0.0 --strictPort >> /tmp/fuqing-crm-frontend.log 2>&1 &
```

### Step 6: CHANGELOG 更新

`CHANGELOG.md` 加 Sprint 144 entry:
- Changed: Sampling 板块顶部筛选解耦到全局 AppFilterBar
- Added: TTL 派样聚合 (U先∪百补 user_id 去重)
- Added: 渠道对比卡 YOY/MOM 同比环比 (复用 filterStore.compareMode)
- Added: 5 个 section 标题化
- Added: 回购周期分布 section (4 桶)

---

## 5. 验收标准

### 5.1 功能验收

| 项 | 标准 |
|---|---|
| 顶部联动 | AppFilterBar 改 dateRange/channel/excludeLowPrice/compareMode → SamplingView 自动重查询 |
| 删除本地筛选 | SamplingView 无 `roiDateRange` ref + 无独立时间选择器 UI |
| **TTL 聚合** | TTL 派样的 sample_users < (U先 sample_users + 百补 sample_users) — **必须证明去重生效** (例: 同一用户 U先+百补 都派样, TTL 只算 1) |
| TTL 顺序 | channels_result[0]='TTL派样' (聚合在最前) |
| TTL UI | 紫色 + "全渠道汇总" 副标题 |
| YOY/MOM | filterStore.compareMode='auto_yoy' → yoy_* 字段有值; 'auto_mom' → mom_* 字段有值; 'custom' → 跟 custom 日期范围计算 |
| 5 section 标题 | 总览 / 汇总 / 各板块情况 / 派样明细 / 回购周期分布 5 个 h2 都有 |
| 回购周期分布 | 4 桶数据完整, 缺桶补 0 |
| 高度一致 | 3 个渠道卡视觉高度一致 (n-card h-full + grid item-responsive) |

### 5.2 pytest 验收

- 全量 pytest 不退化 (baseline 762 passed / 23 skipped / 0 failed)
- **新增 test_sampling_ttl_aggregation.py 至少 4 case**:
  1. `test_ttl_dedup_user` — 同一用户 U先+百补 都派样, TTL sample_users=1 (不是 2)
  2. `test_ttl_gsv_sum` — TTL repurchase_gsv = U先+百补 repurchase_gsv 之和 (不限制唯一 user)
  3. `test_ttl_empty_baseline` — DB 没数据时返回空指标
  4. `test_ttl_full_gsv_sum` — TTL full_repurchase_gsv = U先+百补 full_repurchase_gsv 之和
- 新增 test_sampling_roi_yoy.py 至少 5 case
- 新增 test_sampling_repurchase_distribution.py 至少 4 case

### 5.3 L4 永久规则验收

- L4.2 SQL f-string 前缀 (`sample_users_sql` / `summary_sql` / `cat_sql` 保持, 新加 `_compute_ttl_metrics` 不含 f-string 因为用 `?`)
- L4.5 FilterBuilder + `?` 参数化 (TTL SQL 全用 `?`, 严格遵守)
- L4.19 channel IN 有 `o.` 表别名 (`WHERE o.channel IN (?, ?)` ✅)
- L4.22 vite preview rebuild dist (Step 5 强制)

### 5.4 契约验收

- `backend/contracts/sampling.py` 加 yoy_pct/yoy_pp 字段后 `_lint` 0 violation
- 新增 `SamplingRepurchaseBucket` 用强类型

---

## 6. 风险点

| 风险 | 等级 | 缓解 |
|---|---|---|
| TTL 聚合 SQL 性能 (UNION + COUNT DISTINCT) | 中 | 单 SQL 一次出, DuckDB 列存优化, 加 monitor |
| TTL sample_users 不去重 bug | **高** | test_sampling_ttl_aggregation.py 必须有 `test_ttl_dedup_user` case 验证 |
| 前端 cols 2 → 3 视觉塌陷 | 中 | n-card h-full + grid item-responsive (L 1 m:1 l:1) |
| YOY/MOM 字段契约破坏 | 低 | 全部 Optional, Pydantic 422 兜底 |
| 回购周期分布聚合性能 | 中 | window_days=90 限上限, 单 SQL 一次出 |
| filterStore.channel 与 SAMPLING_CHANNELS 不一致 | 低 | channel 透传让 service 走展开逻辑 |

---

## 7. 测试用例

### 7.1 Backend pytest (新增 3 个文件)

**test_sampling_ttl_aggregation.py** (4 case):
1. `test_ttl_dedup_user` — 同一用户 U先+百补 都派样, TTL sample_users=1 (不是 2)
2. `test_ttl_gsv_sum` — TTL repurchase_gsv = U先+百补 repurchase_gsv 之和 (不限制唯一 user)
3. `test_ttl_empty_baseline` — DB 没数据时返回 _empty_channel_metrics
4. `test_ttl_full_gsv_sum` — TTL full_repurchase_gsv = U先+百补 full_repurchase_gsv 之和

**test_sampling_roi_yoy.py** (5 case):
1. `test_roi_yoy_compare_none` — compare_date_range=None → yoy_* 字段全 None
2. `test_roi_yoy_compare_tuple` — compare_date_range=tuple → yoy_* 字段有值
3. `test_roi_yoy_zero_baseline` — 对比窗口数据全 0 → yoy_* = None (防除零)
4. `test_roi_yoy_pct_pp` — yoy_pct 用 PercentageField (范围 0-1B), yoy_pp 用 PpField (范围 -100~+100)
5. `test_roi_yoy_ttl_included` — TTL 行的 yoy_* 字段也有值 (不只单渠道)

**test_sampling_repurchase_distribution.py** (4 case):
1. `test_distribution_4_buckets` — 返回 4 桶
2. `test_distribution_window_days` — window_days=90 边界
3. `test_distribution_empty` — 空数据返回 4 桶全 0 (不漏桶)
4. `test_distribution_ttl` — channel=undefined/TTL → UNION 聚合; channel='U先派样' → 单渠道

### 7.2 手工验收

1. 启 uvicorn + vite preview
2. 进 /sampling, Tab 1 默认 MTD, 渠道「全店」
3. 改 AppFilterBar dateRange → 卡片自动刷新
4. 切 AppFilterBar compareMode → YOYBadge 显示/隐藏
5. 看 3 个渠道卡 (TTL紫色, U先红色, 百补橙色) 高度一致
6. 验证 TTL sample_users < U先 sample_users + 百补 sample_users (证明去重生效)
7. 看 5 个 section 标题清晰
8. 回购周期分布 4 桶柱状图数据完整
9. 检查 console 0 error, network 0 4xx/5xx

---

## 8. 文件改动清单 (预估)

| 文件 | 类型 | 改动量 |
|---|---|---|
| `backend/services/sampling_service.py` | 改 | +180/-30 |
| `backend/contracts/sampling.py` | 改 | +50/-5 |
| `backend/routers/sampling.py` | 改 | +10/-5 (如有) |
| `frontend-vue3/src/api/sampling.ts` | 改 | +30/-10 |
| `frontend-vue3/src/views/SamplingView.vue` | 改 | +220/-150 |
| `backend/tests/test_sampling_ttl_aggregation.py` | 新增 | +100 |
| `backend/tests/test_sampling_roi_yoy.py` | 新增 | +120 |
| `backend/tests/test_sampling_repurchase_distribution.py` | 新增 | +80 |
| `CHANGELOG.md` | 改 | +15/-2 |
| **合计** | | **+725/-202 (实质有效 ~+520)** |

---

## 9. Codex Stage 2 实施注意事项

1. **不要直接 git commit**: 改完后 `git status` 给用户看, 等 Claude Stage 3 review
2. **保持 L4.2 SQL f-string 前缀**: 现有 `sample_users_sql` / `summary_sql` / `cat_sql` 已有 f 前缀, 保持; 新加的 `_compute_ttl_metrics` 用 `?` 不需要 f-string
3. **保持 L4.5 FilterBuilder 模式**: TTL SQL 全用 `?` 参数化, 不要 f-string 内嵌 channel 名
4. **保持 L4.19 channel IN 别名**: SQL `WHERE o.channel IN (?, ?)` 是正确模式
5. **不要碰 SAMPLING_CHANNELS**: 本期保持 `['U先派样', '百补派样']`, **TTL 是后端聚合层不是 channel 值**
6. **TTL sample_users 必须去重**: test_ttl_dedup_user 是核心验证, 不能 SUM 后给出来
7. **不要 bump VERSION**: 留尾治理 sprint 模式, 累计 67 sprint 0 debt
8. **保持现有 category 字段顺序**: `cat_field` 仍然走 `_SPU_LEVELS` 白名单
9. **不要碰 Sprint 141.5 Phase 1 的 sample_received_at schema**: 那是 Sprint 141.5 完成的, 本期不动

---

## 10. 跑批回归 (sprint 收口前必跑)

```bash
# 验证 TTL 聚合
PYTHONPATH="$(pwd)" python3 -c "
from backend.services.sampling_service import get_sampling_roi
result = get_sampling_roi('2026-06-01', '2026-06-27', window_days=30)
channels = result['summary']['channels']
print(f'channels: {[ch[\"channel\"] for ch in channels]}')
print(f'count: {len(channels)}')
ttl_users = channels[0]['sample_users']
u_users = channels[1]['sample_users']
b_users = channels[2]['sample_users']
print(f'TTL: {ttl_users}, U先: {u_users}, 百补: {b_users}')
print(f'TTL < U先 + 百补? {ttl_users < u_users + b_users} (期望 True, 证明去重生效)')
"

# 验证回购周期分布
PYTHONPATH="$(pwd)" python3 -c "
from backend.services.sampling_service import get_sampling_repurchase_buckets
result = get_sampling_repurchase_buckets('2026-06-01', '2026-06-27', window_days=90)
for b in result: print(b)
"
```

**期望**: 3 个 channel 顺序 [TTL, U先, 百补], TTL 去重生效; 4 桶数据完整。

---

## 11. Handoff 完成度自检

Codex 改完后, 在 PR 描述里 check:

- [ ] SAMPLING_CHANNELS 保持 `['U先派样', '百补派样']` (没改)
- [ ] `_compute_ttl_metrics()` 函数实现并被 `get_sampling_roi()` 调用
- [ ] channels_result 顺序: [TTL, U先, 百补]
- [ ] 5 个 section 标题都加
- [ ] 渠道对比卡 cols=3, TTL 紫色 + "全渠道汇总" 标签
- [ ] YOYBadge 在 metric 旁显示
- [ ] filterStore 替代本地 ref (无 roiDateRange)
- [ ] 回购周期分布 4 桶
- [ ] pytest 全部 pass (含新增 3 个 test file, 13 case)
- [ ] contract _lint 0 violation
- [ ] npm run build 成功
- [ ] vite preview 重启跑新 dist

---

**Sprint 144 范围到此为止。等用户拍板后启动 Codex Stage 2。**