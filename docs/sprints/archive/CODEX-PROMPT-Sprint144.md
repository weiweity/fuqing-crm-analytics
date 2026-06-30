# Codex Prompt — Sprint 144 Sampling 板块重构

> **复制下面整段贴给 Codex app**, Codex 会读 `AGENTS.md` + 本文件 + 引用 handoff, 本地编辑代码, **不动 git**。

---

## 任务背景

Sprint 144 是真业务 sprint (user 报 "我需要做 sampling 调整")。改 Sampling 板块, 5 个需求:

1. SamplingView 顶部时间/渠道/低价筛选解耦到全局 AppFilterBar (filterStore)
2. 删除 SamplingView 本地时间筛选 ref + UI
3. 派样正装转化 tab 卡片 3 列对齐 (TTL / U先派样 / 百补派样)
4. 卡片加 YOY/MOM 同比环比
5. 新增 5 个 section 标题 (总览/汇总/各板块情况/派样明细/回购周期分布) + 回购周期分布 4 桶柱状图

**完整 handoff 文档**: `docs/sprints/HANDOFF-TO-CODEX-Sprint144-Sampling-Refactor.md` — 改之前必读

---

## ⚠️ 核心定义 (不要违背)

**TTL 派样 = U先派样 ∪ 百补派样, user_id COUNT DISTINCT 去重**。

- TTL **不是** 新 channel 值, 不要改 `SAMPLING_CHANNELS = ['U先派样', '百补派样']`
- TTL **是** 后端聚合层: `WHERE channel IN ('U先派样', '百补派样')` + `GROUP BY user_id (取 MIN first_sample_time)`
- TTL sample_users = COUNT(DISTINCT user_id) — **必须去重**
- TTL repurchase_gsv / full_repurchase_gsv = SUM — 不去重 (一个人买多次算多次)
- channels_result 顺序: **[0] TTL派样, [1] U先派样, [2] 百补派样**

---

## 实施顺序 (按这个顺序改)

### Step 1: 创建分支 + DB 验证

```bash
cd /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics
git checkout main && git pull origin main --ff-only
git checkout -b feature/sprint144-sampling-refactor

PYTHONPATH="$(pwd)" python3 -c "
import duckdb
conn = duckdb.connect('data/processed/fuqing_crm.duckdb', read_only=True)
rows = conn.execute(\"SELECT DISTINCT channel FROM orders WHERE channel IN ('U先派样', '百补派样') ORDER BY channel\").fetchall()
print(f'渠道数: {len(rows)} (期望 2)')
for r in rows: print(r[0])
"
```

### Step 2: Backend — `backend/services/sampling_service.py`

**改动**:
- `SAMPLING_CHANNELS` **保持不变**
- 新增 `_compute_ttl_metrics(start_date, end_date, window_days)` 函数 — 返回 TTL 单行 metrics 字典
- 新增 `_empty_channel_metrics(channel)` helper — 空指标模板
- `get_sampling_roi()` 函数签名加 `compare_date_range: Optional[Tuple[str, str]] = None`
- `get_sampling_roi()` 拼接 `channels_result = [ttl_row] + single_channel_result` (TTL 在最前)
- 新增 `get_sampling_repurchase_buckets(start_date, end_date, window_days=90, channel=None)` 函数 — 4 桶聚合

**TTL SQL** (新加的 `_compute_ttl_metrics` 内部):
```sql
WITH sample_users AS (
    SELECT user_id, MIN(o.pay_time) as first_sample_time
    FROM orders o
    WHERE o.channel IN (?, ?)
      AND o.pay_time >= ?::TIMESTAMP AND o.pay_time <= ?::TIMESTAMP + INTERVAL '1' DAY
    GROUP BY o.user_id
),
repurchase AS (
    SELECT su.user_id, su.first_sample_time, o.actual_amount,
           COALESCE(o.spu_type, '未知') as spu_type,
           DATEDIFF('day', su.first_sample_time, o.pay_time) as days_between
    FROM sample_users su
    JOIN orders o ON su.user_id = o.user_id
    WHERE o.pay_time > su.first_sample_time
      AND DATEDIFF('day', su.first_sample_time, o.pay_time) <= ?
      AND o.is_refund = FALSE AND o.order_status != '交易关闭'
      AND o.channel != '购物金'
)
SELECT COUNT(DISTINCT su.user_id) as sample_users,
       COUNT(DISTINCT CASE WHEN r.days_between <= ? THEN r.user_id END) as repurchase_users,
       SUM(CASE WHEN r.days_between <= ? THEN r.actual_amount ELSE 0 END) as repurchase_gsv,
       COUNT(DISTINCT CASE WHEN r.days_between <= ? AND r.spu_type = '正装' THEN r.user_id END) as full_repurchase_users,
       SUM(CASE WHEN r.days_between <= ? AND r.spu_type = '正装' THEN r.actual_amount ELSE 0 END) as full_repurchase_gsv,
       COUNT(DISTINCT CASE WHEN r.days_between <= ? AND r.spu_type != '正装' THEN r.user_id END) as nonfull_repurchase_users,
       SUM(CASE WHEN r.days_between <= ? AND r.spu_type != '正装' THEN r.actual_amount ELSE 0 END) as nonfull_repurchase_gsv
FROM sample_users su
LEFT JOIN repurchase r ON su.user_id = r.user_id
```
`?` 顺序: 2 channel + 2 date + 1 window + 6 window = 11 params

**YOY/MOM 计算** (compare_date_range 不为空时):
- 调用 `_compute_ttl_metrics(cmp_start, cmp_end, window_days)` 拿 TTL 对比行
- 单渠道对比窗口跑原 summary_sql 改日期参数
- 用 `yoy_absolute()` / `yoy_ratio()` (从 `backend.semantic.calculations` import) 算 per channel 的 yoy_pct / yoy_pp

**回购周期分布 SQL** (新增函数 `get_sampling_repurchase_buckets`):
```sql
WITH sample_users AS (
    -- TTL: WHERE o.channel IN (?, ?); 单渠道: WHERE o.channel IN (?, ?, ...)
    ...
),
repurchase AS (
    SELECT su.user_id, su.first_sample_time, o.actual_amount,
           DATEDIFF('day', su.first_sample_time, o.pay_time) as days_between
    FROM sample_users su JOIN orders o ON ...
    WHERE o.pay_time > su.first_sample_time
      AND DATEDIFF('day', su.first_sample_time, o.pay_time) <= ?
      AND ...
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
```
后端补全缺失桶 (返回 4 桶固定顺序 `['0-7d', '8-30d', '31-60d', '61-90d']`)

### Step 3: Contract — `backend/contracts/sampling.py`

**`SamplingChannelSummary`** 加 Optional 字段 (per metric):
- `repurchase_users_yoy_pct: Optional[PercentageField] = None`
- `repurchase_gsv_yoy_pct: Optional[PercentageField] = None`
- `repurchase_rate_yoy_pp: Optional[PpField] = None`
- `full_repurchase_users_yoy_pct: Optional[PercentageField] = None`
- `full_repurchase_gsv_yoy_pct: Optional[PercentageField] = None`
- `full_repurchase_rate_yoy_pp: Optional[PpField] = None`
- mom_* 字段同结构 (本期可选, 跟 compare_date_range 模式联动)

**新增 `SamplingRepurchaseBucket`** (bucket: '0-7d' | '8-30d' | '31-60d' | '61-90d', users, gsv, aus)
**新增 `SamplingRepurchaseDistribution`** (buckets: List[SamplingRepurchaseBucket], window_days: int)

**`SamplingLevelSummary`** 加 `repurchase_distribution: Optional[SamplingRepurchaseDistribution] = None`

### Step 4: Frontend — `frontend-vue3/src/views/SamplingView.vue`

**删除**:
- `const roiDateRange = ref<[number, number] | null>(null)` (L20)
- 默认日期初始化 (L49-53)
- 时间选择器 UI (L407-414)

**改 `roiParams`** (从 filterStore 读):
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

**保留本地 ref**: `windowDays` / `windowDaysDebounced` / `categoryLevel` / `levelOptions` / `sliderMarks` (sampling 独有)

**改 useQuery enabled**: `enabled: computed(() => activeTab.value === 'roi')` (不要等 roiDateRange)

**改渠道对比卡** (L545-588):
- `<n-grid :cols="3">` (原来是 2)
- 加 `<n-gi v-for ... span="1 m:1 l:1">`
- `<n-card class="h-full">` (高度一致)
- TTL 卡 header 加紫色 + "(全渠道汇总)" 副标题
- 5 个 metric (派样人数/回购人数/回购率/贡献GSV/AUS) 加 `<YOYBadge>` 旁标 (repackage_users 已有, sample_users 不加 YOY)
- `channelColorClass` helper: `'TTL派样': 'text-purple-600'`, `'U先派样': 'text-rose-600'`, `'百补派样': 'text-orange-500'`

**加 5 个 section 标题** (在 ROI tab 内):
1. L447 上方: `<h2 class="text-base font-semibold text-slate-800 mb-3">📊 总览</h2>`
2. L502 上方: `<h2 class="text-base font-semibold text-slate-800 mb-3">📈 {{ levelLabel }}汇总</h2>`
3. L545 上方: `<h2 class="text-base font-semibold text-slate-800 mb-3">🏷️ 各派样渠道情况</h2>`
4. L601 上方: `<h2 class="text-base font-semibold text-slate-800 mb-3">📋 派样明细 (按 {{ levelLabel }})</h2>`
5. 派样明细下方 (新增 section): `<h2 class="text-base font-semibold text-slate-800 mb-3">⏱️ 回购周期分布</h2>`

**回购周期分布 section** (新增, 紧跟派样明细):
- `useQuery` 取 `repurchaseDistribution`, queryFn 调 `fetchSamplingRepurchaseDistribution({start_date, end_date, window_days: 90, channel: roiParams.value.channel})`
- 4 桶柱状图: `v-for bucket in repurchaseDistribution.buckets`, 每桶显示 bucket/users/gsv/aus

### Step 5: API — `frontend-vue3/src/api/sampling.ts`

**`fetchSamplingROI`** 签名加 `compare_date_range?: [string, string] | null` 和 `exclude_low_price?: boolean`

**新增 `fetchSamplingRepurchaseDistribution`**:
```ts
export async function fetchSamplingRepurchaseDistribution(params: {
  start_date: string
  end_date: string
  window_days: number
  channel?: string  // undefined = 默认 TTL
}): Promise<{ buckets: SamplingRepurchaseBucket[]; window_days: number }>
```

### Step 6: 测试 (新增 3 个 test file)

**`backend/tests/test_sampling_ttl_aggregation.py`** (4 case):
1. `test_ttl_dedup_user` — 同 user U先+百补 都派样, TTL sample_users=1 (核心验证)
2. `test_ttl_gsv_sum` — TTL repurchase_gsv = U先+百补 repurchase_gsv 之和
3. `test_ttl_empty_baseline` — DB 没数据时返回 `_empty_channel_metrics` 模板
4. `test_ttl_full_gsv_sum` — TTL full_repurchase_gsv = U先+百补 full_repurchase_gsv 之和

**`backend/tests/test_sampling_roi_yoy.py`** (5 case):
1. `test_roi_yoy_compare_none` — compare_date_range=None → yoy_* 字段全 None
2. `test_roi_yoy_compare_tuple` — compare_date_range=tuple → yoy_* 字段有值
3. `test_roi_yoy_zero_baseline` — 对比窗口数据全 0 → yoy_* = None
4. `test_roi_yoy_pct_pp` — yoy_pct 用 PercentageField, yoy_pp 用 PpField
5. `test_roi_yoy_ttl_included` — TTL 行的 yoy_* 字段也有值

**`backend/tests/test_sampling_repurchase_distribution.py`** (4 case):
1. `test_distribution_4_buckets` — 返回 4 桶
2. `test_distribution_window_days` — window_days=90 边界
3. `test_distribution_empty` — 空数据返回 4 桶全 0
4. `test_distribution_ttl` — channel=undefined/TTL → UNION; channel='U先派样' → 单渠道

### Step 7: 契约 lint + pytest + build

```bash
PYTHONPATH="$(pwd)" python -m backend.contracts._lint
PYTHONPATH="$(pwd)" pytest backend/tests/ -x -q

cd frontend-vue3 && npm run build
grep -c "TTL派样" dist/assets/*.js  # ≥ 1
grep -c "全渠道汇总" dist/assets/*.js  # ≥ 1
grep -c "/visitor" dist/assets/*.js  # 0

ps aux | grep "vite preview" | grep -v grep | awk '{print $2}' | xargs kill
nohup npx vite preview --port 5173 --host 0.0.0.0 --strictPort >> /tmp/fuqing-crm-frontend.log 2>&1 &
```

### Step 8: CHANGELOG.md

加 Sprint 144 entry (跟 Sprint 143 格式一致):
- Changed: Sampling 板块顶部筛选解耦到全局 AppFilterBar
- Added: TTL 派样聚合 (U先∪百补 user_id 去重)
- Added: 渠道对比卡 YOY/MOM 同比环比 (复用 filterStore.compareMode)
- Added: 5 个 section 标题化 (总览/汇总/各板块情况/派样明细/回购周期分布)
- Added: 回购周期分布 section (4 桶: 0-7d / 8-30d / 31-60d / 61-90d)

---

## L4 永久规则强制 (违反会被 review 拦下)

- **L4.2**: SQL 三引号赋值若 body 含 `{identifier}` 必须 f-string 前缀
- **L4.5**: service 必须用 `?` 参数化, 禁止 f-string 内嵌用户输入
- **L4.19**: SQL `WHERE o.channel IN (...)` 必须有 `o.` 表别名
- **L4.22**: 前端 sprint 改完必 `npm run build` + kill 旧 vite preview + restart
- **CLAUDE.md §B1+B2**: yoy_* 字段用 `PercentageField` / `PpField` 强类型, 禁止裸 float

---

## 不要做 ❌

- ❌ 不要改 `SAMPLING_CHANNELS` (保持 `['U先派样', '百补派样']`)
- ❌ 不要把 TTL 当 SUM(U先 metrics + 百补 metrics) — **必须 COUNT DISTINCT user_id**
- ❌ 不要 bump VERSION (累计 67 sprint 0 debt)
- ❌ 不要碰 ETL / sample_received_at schema (Sprint 141.5 已完成)
- ❌ 不要直接 git commit — 改完 `git status` 给 user 看, 等 review
- ❌ 不要引入新的 compareMode 状态 (复用 filterStore.compareMode)
- ❌ 不要把 windowDays / categoryLevel 移到 filterStore (sampling 独有)

---

## 跑批回归 (改完跑一下)

```bash
PYTHONPATH="$(pwd)" python3 -c "
from backend.services.sampling_service import get_sampling_roi
result = get_sampling_roi('2026-06-01', '2026-06-27', window_days=30)
channels = result['summary']['channels']
print(f'channels: {[ch[\"channel\"] for ch in channels]}')  # 期望 [TTL, U先, 百补]
ttl_users = channels[0]['sample_users']
u_users = channels[1]['sample_users']
b_users = channels[2]['sample_users']
print(f'TTL: {ttl_users}, U先: {u_users}, 百补: {b_users}')
assert ttl_users < u_users + b_users, 'TTL 必须去重!'
print('✅ TTL 去重验证通过')
"
```

---

## 完成后

1. `git status` 给我看 (不要 commit)
2. `git diff --stat` 给我看
3. 跑 `pytest backend/tests/ -x -q` 验证全绿
4. 跑 `npm run build` 验证前端 build 成功
5. 等 user 给 review 反馈

---

**Sprint 144 主线到此。Codex 实施完贴 git diff 摘要回 user review。**