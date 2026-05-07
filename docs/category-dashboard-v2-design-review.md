# 品类看板 v2 设计文档评审报告

**评审日期**: 2026-04-21  
**评审范围**: `category_service.py` + `CategoryView.vue` + `week4/api-contract.md` + `week4/requirements.md` + 语义层 (`filters.py`, `calculations.py`, `segments.py`)  
**评审标准**: P0 = 会导致错误业务决策 / 数据完全不可信；P1 = 会误导运营 / 关键场景不可用；P2 = 体验差 / 存在隐患  

---

## 一、指标定义逻辑错误（Logic Bugs）

### P0-001 全站 GMV/GSV 口径校准灾难：Category 服务把 GSV 当 GMV 卖
**位置**: `category_service.py` 全文件  
**问题**:  
- `get_category_distribution()` 使用 `OrderFilters.valid_order()`（剔除退款+购物金+交易关闭）后 `SUM(actual_amount)`，结果字段名却叫 `gmv`
- `get_category_segment_matrix()` 同样逻辑，返回字段也叫 `gmv`
- `get_category_user_profile()` 同样逻辑，`total_gmv` 实际是 GSV
- 只有 `get_category_overview()` 有 `metric_type` 参数，但内部 `_compute_category_period()` 对 GMV 和 GSV **都**使用 `OrderFilters.valid_order()`，唯一的区别是 `amount_cond`（GMV 用 `>0`，GSV 用 `>=0`）

**后果**:  运营团队看"品类GMV"饼图，实际看到的是 GSV（有效销售额）。在大促期间，如果退款/购物金订单占比高，饼图显示的"GMV"会严重偏低，导致对品类真实交易规模的误判。老板基于这个"GMV"做预算分配，会直接砍错品类的资源。

**修复**:  
- `get_category_distribution()` / `segment_matrix()` / `user_profile()` 必须支持 `metric_type` 参数
- GMV 场景使用 `OrderFilters.gmv_base()`（仅排除交易关闭，保留退款和购物金）
- GSV 场景使用 `OrderFilters.valid_order()`
- 返回字段名必须与口径一致：`gmv` / `gsv` 不能混用

---

### P0-002 会员表（member_rows）完全是假数据
**位置**: `category_service.py` 第 742-806 行  
**问题**:  
```python
all_rows = []
member_rows = []
for name in all_names:
    c = cur.get(name, {})
    p = comp.get(name, {})
    all_rows.append(_build_row(name, c, p))
    member_rows.append(_build_row(name, c, p))  # ← 和 all_rows 用完全一样的数据！
```

`member_rows` 没有进行任何会员过滤，与 `all_rows` 数据完全一致。前端 "单品概览 — 会员" 表格展示的 GSV、人数、老客/新客拆分全是**全店 totals**，只在全店分组里加了一列 `member_ratio`。

**后果**: 运营看到"会员"表格，以为这是会员-only 数据，据此制定会员专属策略（如"会员老客 AUS 下降了，推会员专属券"），但实际上看到的是全店数据，策略会严重失焦。例如：某品类全店老客 AUS ¥300，会员占比 30%，运营误以为会员老客 AUS 就是 ¥300，给会员发券后发现 ROI 极差。

**修复**:  
- `member_rows` 必须基于 `is_member = TRUE` 过滤后的数据重新计算
- 或者删除"会员"表格，只保留 `member_ratio` 列在"全店"表格中

---

### P0-003 会员 TTL 行计算完全错误
**位置**: `category_service.py` 第 786-806 行  
**问题**:  
```python
mem_total_gsv = sum(c.get("gsv", 0) for c in cur.values() if c.get("member_ratio", 0) > 0)
```
这里：
1. 求和的是 `gsv`（全店总 GSV），不是 `member_gsv`（会员 GSV）
2. 过滤条件是 `member_ratio > 0`，排除了所有会员占比为 0 的品类，导致分母被人为缩小

后续 `_build_row` 中 `member_ratio = member_gsv / gsv`，而 `member_gsv` 和 `gsv` 都被传入 `mem_total_gsv`，所以 **TTL 行的会员占比永远显示 100%**。

同时 TTL 行的 `users`、`old_users`、`new_users` 传入的是全店 totals，不是会员人数。

**后果**: 会员 TTL 行显示：GSV = 全店有会员贡献的品类 GSV 之和，会员占比 = 100%，人数 = 全店总人数。这个数字没有任何业务意义，但会出现在运营日报的汇总行，成为错误决策的"权威数据"。

**修复**:  重新设计会员 TTL：
```python
mem_total_gsv = sum(c.get("member_gsv", 0) for c in cur.values())  # 实际会员 GSV
mem_total_users = sum(...)  # 需要新增会员人数指标
```

---

### P1-004 YoY 同比的去年 cutoff 逻辑与新老客定义矛盾
**位置**: `category_service.py` 第 696-703 行  
**问题**:  
```python
cutoff = (date(start_dt.year, start_dt.month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")
ly_start = (start_dt - timedelta(days=365)).strftime("%Y-%m-%d")
ly_end = (end_dt - timedelta(days=365)).strftime("%Y-%m-%d")
ly_cutoff = (date(ly_start_dt.year, ly_start_dt.month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")
```

当分析周期跨月份时（如 2026-04-15 至 2026-04-17），cutoff 仍然是 2026-03-31。这意味着：
- 在 4 月 1-14 日首次购买的用户，在 4 月 15-17 日的分析中被算作**老客**
- 但运营直觉上会认为"这个月刚买的人当然是新客"

YoY 对比时，去年 4 月 15-17 日的老客 cutoff 是 2025-03-31。一个用户在 2025-04-01 首次购买，在 2025-04-15 的分析中是"新客"，但在 2026-04-15 的分析中首购日期 < 2026-03-31，变成"老客"。所以**同一个用户在不同年份的同期分析中，新/老身份不一致**。

**后果**: 老客 GSV YoY 看起来上涨，可能是因为大量去年 4 月上旬的新客在今年变成了老客（结构性迁移），而不是老客复购率真的提升了。运营会误判老客维护效果。

**修复**:  在 UI 上明确标注新老客定义（"基于自然月首购日期判断"），并增加"周期内新客"（首次购买在 start_date 之后）作为辅助指标。

---

### P1-005 `user_rfm` JOIN 硬编码 `metric_type = 'GMV'`，与 GSV 分析场景错配
**位置**: `category_service.py` 第 116-119、256-258、375-377、442-444 等  
**问题**: 所有涉及 `user_rfm` 的 JOIN 都写死 `metric_type = 'GMV'`：
```sql
LEFT JOIN user_rfm r ON o.user_id = r.user_id
    AND r.analysis_date = ?
    AND r.metric_type = 'GMV'
    AND r.lookback_days = ?
```

但 `get_category_overview()` 支持 `metric_type='GSV'`，且默认就是 GSV。当用户看 GSV 数据时，品类-象限交叉分析用的却是 GMV 口径计算的 RFM 分段。

**后果**: 某用户在 GSV 口径下是"流失用户"（因为 TA 的退款订单被剔除后金额很低），但在 GMV 口径下是"忠实金主"。品类象限矩阵会把这个用户分到错误的象限，导致品类-人群交叉洞察完全失真。

**修复**:  `metric_type` 参数必须透传到 `user_rfm` JOIN 条件中。

---

## 二、缺失功能（Missing Features）

### P1-006 没有 MoM（环比），只有 YoY
**位置**: `get_category_overview()` / `CategoryView.vue`  
**问题**: 表格中只有 YoY（同比），没有 MoM（环比）。对于日常运营，环比比同比更敏感、更能发现近期问题。

**后果**: 如果某品类 4 月老客 AUS 环比下降 20% 但同比上升 5%，运营完全看不到下降信号，错过干预窗口。

**修复**:  增加上月同期数据对比，返回 `mom_*` 字段。

---

### P1-007 `get_category_user_profile` 完全不支持全局筛选器
**位置**: `category_service.py` 第 314 行  
**问题**: `get_category_user_profile()` 没有 `exclude_channels` 参数，也不支持 `channel` 过滤。前端 `CategoryView.vue` 也没有调用这个 API（第三 Tab "品类画像" 不存在）。

**后果**: 即使未来加了"品类画像" TAB，全局的"剔除低价"开关对这个 TAB 无效，运营看到的品类用户画像包含了 U先派样、赠品等低价渠道用户，与"单品概览"表格的数据口径不一致。

**修复**:  给 `get_category_user_profile` 增加 `exclude_channels` 和 `channel` 参数，并在前端补上第三 TAB。

---

### P1-008 没有品类层级钻取（Drill-down）
**位置**: `CategoryView.vue`  
**问题**: 前端 level 写死为 `'class'`（`queryParams.level = 'class'`），没有提供切换层级（category / type / tier / class / subclass）的 UI 控件。

**后果**: 运营只能看到 `spu_product_class`（产品系列）层级，无法下钻到 `subclass` 看具体 SKU 表现，也无法上卷到 `category` 看大类趋势。一个问题品类（如"凉茶系列"表现差）无法定位是"凉茶经典款"还是"凉茶清新款"的问题。

**修复**:  在页面顶部增加层级选择器（下拉菜单：一级品类 → 二级品类 → 梯队 → 产品系列 → 产品子类）。

---

### P2-009 没有导出功能
**位置**: `CategoryView.vue`  
**问题**: 页面没有"导出 Excel"按钮。运营需要把品类数据复制到飞书/Excel 做进一步分析或汇报。

**后果**: 运营只能手动截图或复制表格，12 行分页的数据要翻很多页才能复制全，极易出错。

---

### P2-010 没有搜索/过滤品类名称
**位置**: `CategoryView.vue`  
**问题**: 如果 `spu_product_class` 有 50+ 个值，DataTablePro 没有提供按名称搜索的功能。

**后果**: 运营想快速查看某个特定系列的表现，需要翻页查找，效率极低。

---

## 三、边界情况（Edge Cases）

### P1-011 品类分布的 `pct` 基于用户数，但饼图基于 GMV，两者不互斥
**位置**: `category_service.py` 第 178 行 + `CategoryView.vue` 饼图  
**问题**: 
- 表格中的 `pct` = `user_count / total_users * 100`
- 饼图中的 `value` = `gmv`
- 一个用户可以在多个品类购买，所以 `SUM(category_user_counts) > total_users`

**后果**: 饼图显示"护肤占 40% GMV"，表格显示"护肤占 35% 用户"。运营看到两个数字不一致，会怀疑数据错了。更严重的是，如果某大促期间爆品吸引了大量一次性用户，该品类的 `user_count pct` 会飙升，但 `gmv pct` 可能不变，运营可能误判为"拉新效果好"（看用户占比）而实际上"复购不行"（看 GMV 占比）。

**修复**:  在表格中同时显示 `user_ratio` 和 `gmv_ratio`，并在图表旁边明确标注"基于 GMV"或"基于用户数"。

---

### P1-012 `user_rfm` 缺失日期时，所有用户被静默归类为"其他"
**位置**: `category_service.py` 第 252 行  
**问题**:  
```sql
COALESCE(r.segment_id, 9) AS segment_id
```

如果 ETL 漏跑或 `user_rfm` 表中没有对应 `analysis_date` + `lookback_days` + `metric_type='GMV'` 的数据，LEFT JOIN 返回 NULL，`segment_id` 被强制转为 9（"其他"）。没有任何错误提示。

**后果**: 运营某天打开品类-象限矩阵，发现所有用户都是"其他"，以为是产品出了什么问题（比如所有用户都流失了），实际上只是 `user_rfm` 表没更新。

**修复**:  在 API 返回中增加 `data_quality` 字段，当"其他"占比超过阈值时返回警告。或在 `get_category_segment_matrix` 中先检查 `user_rfm` 数据是否存在。

---

### P1-013 新去年均无数据的品类，YoY 显示为空白而非"新品"
**位置**: `_build_row()` 第 714-734 行  
**问题**:  `yoy_absolute()` 在 `comp = 0` 时返回 `None`。对于今年新上线的品类（去年无销售），所有 YoY 列都是空白。

**后果**: 运营无法区分"新品"（应该庆祝）和"数据缺失"（应该排查），可能忽略新品的良好表现。

**修复**:  当 `comp = 0` 且 `cur > 0` 时，返回 `"NEW"` 或一个特殊标记，前端用 "新品" 标签展示。

---

### P2-014 `_normalize_date` 对非法输入无防护
**位置**: `category_service.py` 第 14-20 行  
**问题**:  
```python
def _normalize_date(date_val):
    if hasattr(date_val, 'strftime'):
        return date_val.strftime("%Y-%m-%d")
    if isinstance(date_val, str):
        return date_val[:10] if len(date_val) > 10 else date_val
    return str(date_val)
```

如果传入 `"not-a-date"`，它返回 `"not-a-date"`，随后 `datetime.strptime` 会抛异常，导致 500 错误。前端会看到通用的"计算失败"，无法区分是参数错误还是服务端故障。

---

### P2-015 `exclude_channels` 依赖渠道名硬编码，ETL 改名即失效
**位置**: `CategoryView.vue` 第 26 行  
**问题**: 前端硬编码：
```javascript
const LOW_PRICE_CHANNELS = ['U先派样', '百补派样', '赠品&0.01', '其他']
```

如果 ETL 将渠道名从 `"U先派样"` 改为 `"U先试用"`，或后端 `semantic/channels.py` 调整了映射，前端继续传旧名字，低价渠道不会被排除，但用户以为已经排除了。

**修复**:  后端提供 `/api/v1/channels` 接口返回渠道列表和"低价"标记，前端动态获取。

---

## 四、业务逻辑不一致（Business Logic Inconsistencies）

### P0-016 8 象限名称：PRD/业务文档 vs `segments.py` vs 品类看板，三方完全不一致
**位置**: `backend/semantic/segments.py` vs `docs/rfm-business-design.md` vs `docs/PRD-v2.0.md`  
**问题**:  

| 象限 ID | PRD / 业务文档 / API 契约 | `segments.py` 实际返回 | 品类看板显示 |
|---------|--------------------------|----------------------|-------------|
| 1 | 钻石会员 | **重要价值客户** | 重要价值客户 |
| 2 | 潜力新贵 | **重要保持客户** | 重要保持客户 |
| 3 | 忠实金主 | **重要发展客户** | 重要发展客户 |
| 4 | 频次买家 | **重要挽留客户** | 重要挽留客户 |
| 5 | 豪气新客 | **一般价值客户** | 一般价值客户 |
| 6 | 清新路人 | **一般保持客户** | 一般保持客户 |
| 7 | 沉睡土豪 | **一般发展客户** | 一般发展客户 |
| 8 | 流失用户 | **一般挽留客户** | 一般挽留客户 |

**后果**: 运营在 RFM 页面看到"钻石会员"，在品类看板看到"重要价值客户"，以为是两个人群。更糟糕的是，`week2-segmentation-design.md` 和 `rfm-business-design.md` 对同一 ID 的人群策略完全不同（如 ID 2 在业务文档是"潜力新贵"需要升级激励，在 `segments.py` 是"重要保持客户"需要维护关系）。

**修复**:  `segments.py` 必须与 PRD 和业务文档对齐，统一使用 钻石会员/潜力新贵/忠实金主/频次买家/豪气新客/清新路人/沉睡土豪/流失用户。

---

### P0-017 R 阈值：`segments.py` [30, 90, 180, 365] 与业务文档 [14, 30, 60, 90] 完全不同
**位置**: `backend/semantic/segments.py` 第 21 行  
**问题**:  

| 维度 | `segments.py` 阈值 | 业务文档阈值 | 差异 |
|------|-------------------|-------------|------|
| R (5分) | < 30 天 | < 14 天 | 差 2 倍 |
| R (4分) | 30-89 天 | 14-29 天 | 差 2-3 倍 |
| R (3分) | 90-179 天 | 30-59 天 | 差 3 倍 |
| R (2分) | 180-364 天 | 60-89 天 | 差 2-4 倍 |
| F (4分) | >= 4 次 | 4-5 次 | 范围一致 |
| F (5分) | >= 5 次 | >= 6 次 | F=5 被多给 1 分 |

**后果**:  
- 一个 20 天未购的用户，在 `segments.py` 是 5 分（高活跃/钻石会员），在业务文档是 4 分（轻度预警/潜力新贵）
- 一个 45 天未购的用户，在 `segments.py` 是 4 分，在业务文档是 3 分（中度预警）
- 一个 5 次购买的用户，在 `segments.py` 是 5 分，在业务文档是 4 分

这意味着品类-象限矩阵中大量用户被错误归类。运营基于"钻石会员"做 VIP 维护，实际上其中很多人只是"轻度预警"用户，维护资源被严重浪费。

**修复**:  `segments.py` 的 `RFM_THRESHOLDS` 必须与 `rfm-business-design.md` 完全一致：
```python
RFM_THRESHOLDS = {
    "r": [14, 30, 60, 90],
    "f": [1, 2, 3, 5],   # 注意 F 的 CASE WHEN 逻辑也需要改，>=4 → 4分，>=6 → 5分
    "m": [100, 300, 500, 1000],
}
```

---

### P1-018 顶部 KPI 卡片与主表格时间口径不一致
**位置**: `CategoryView.vue` 第 28-35 行 vs 第 58-64 行  
**问题**:  
- 顶部 4 张 KPI 卡片（总GMV、总用户数、TOP1品类、品类数量）使用 `distributionParams`：
  - `date = filterStore.dateRange[1]`（结束日期）
  - `lookback_days = 90`（固定 90 天回溯）
- 主表格（单品概览）使用 `queryParams`：
  - `start_date = filterStore.dateRange[0]`
  - `end_date = filterStore.dateRange[1]`

当用户选择日期范围为"2026-04-01 ~ 2026-04-17"时：
- KPI 卡片展示的是 2026-01-17 ~ 2026-04-17（90天）的数据
- 表格展示的是 2026-04-01 ~ 2026-04-17（17天）的数据

**后果**: 用户看到"总GMV ¥500万"（90天），但表格里所有品类的 GSV 加起来只有 ¥80万（17天），会以为表格漏数据了。或者用户选了一个大促日（如 6 月 18 日单日），KPI 卡片显示近 90 天数据，表格显示单日数据，完全无法对比。

**修复**:  KPI 卡片必须与主表格使用完全相同的 `start_date` / `end_date` 参数，或者明确标注卡片是"近90天"、表格是"选定周期"。

---

### P1-019 品类分布 API 返回字段与前端类型定义不匹配
**位置**: `frontend-vue3/src/api/category.ts` vs `category_service.py`  
**问题**:  

`CategoryDistributionItem` 接口声明了 7 个字段：
```typescript
export interface CategoryDistributionItem {
  name: string
  user_count: number
  gmv: number
  order_count: number        // ← 后端不返回
  avg_order_value: number    // ← 后端不返回
  user_ratio: number         // ← 后端不返回（返回的是 pct）
  gmv_ratio: number          // ← 后端不返回
}
```

后端 `get_category_distribution()` 只返回 `name`、`user_count`、`gmv`、`pct`。  
`CategorySegmentMatrixResponse` 中 `matrix` 的 item 类型是 `{ name: string; user_count: number; gmv: number }`，但后端返回的是 `{ category: string; user_count: number; gmv: number }`（字段名 `category` 而非 `name`）。

**后果**: TypeScript 编译通过（因为都是对象），但运行时访问 `item.name` 会得到 `undefined`，导致饼图图例或矩阵表格显示空白名称。

---

### P1-020 新老客定义在 PRD v1.0 和 v2.0 之间发生变化，但 category 服务未同步
**位置**: `PRD.md` vs `PRD-v2.0.md` vs `category_service.py`  
**问题**:  
- PRD v1.0: "老客 = 当月复购用户数（2月1日前买过）" — 表述模糊
- PRD v2.0: 明确首购日期统一来源于 `user_first_purchase` 表，cutoff = 分析窗口起始日期 - 1 天
- `category_service.py` 的 `_compute_category_period` 确实使用了 `user_first_purchase` 表，但 `get_category_distribution()` 和 `get_category_segment_matrix()` **完全没有新老客概念**

也就是说，品类分布和象限矩阵两个 TAB 的数据是全用户口径，而"单品概览"表格有新/老拆分。当运营对比这三个 TAB 时，"全店用户数"在分布 TAB 和概览 TAB 中可能不一致（因为概览有 cutoff 逻辑，分布没有）。

**后果**: 分布 TAB 说"护肤品类有 10 万用户"，概览 TAB 说"护肤系列全店用户数 9.5 万"，运营会困惑那 5000 人去哪了（答案是：他们在分析周期 cutoff 之前首购，但在 90 天分布周期内是"老客"... 等等，分布 API 根本不区分新/老，所以口径本就不同）。

---

## 五、数据管道缺口（Data Pipeline Gaps）

### P1-021 `user_first_purchase` 表缺失时的降级策略
**位置**: `_compute_category_period()` 第 629 行  
**问题**: 新老客拆分依赖 `LEFT JOIN user_first_purchase ufp`。如果这张表：
- 不存在（尚未创建）
- 为空（ETL 失败）
- 缺失部分用户

则 `ufp.first_pay_date` 为 NULL，`is_new` 永远为 0（老客），`new_users` 永远为 0。

**后果**: 运营看到"本月所有品类的新客数为 0"，以为拉新完全停滞，实际上只是 `user_first_purchase` 表没更新。

**修复**:  在 `_compute_category_period` 开始时检查 `user_first_purchase` 的行数或最近更新日期，如果异常则抛出明确错误或返回 `new_users = null` 并附带警告。

---

### P1-022 SPU 字段覆盖率 97%，但 3% 的"未知"订单在品类分析中完全丢失
**位置**: `category_service.py` 第 81 行  
**问题**:  
```python
category_field_expr = f"COALESCE(o.{category_field}, '未知')"
```

这看起来处理了 NULL，但如果 `spu_product_class` 为 NULL 或空字符串，会被归入"未知"品类。然而：
1. "未知"可能出现在分布 TOP 榜中，运营不知道这是什么
2. 如果 3% 的订单都是某个爆品但映射缺失，该爆品在品类看板中完全不可见
3. 没有"未分类订单监控"机制告诉运营"有 X 万订单缺少 SPU 映射"

**后果**: 运营基于品类看板做选品决策，但最热销的新品可能因为 SPU 映射缺失而被归入"未知"，导致决策遗漏。

**修复**:  在品类分布返回中增加 `unmapped_order_count` 和 `unmapped_gmv` 字段，并在前端当"未知"占比超过 1% 时显示警告。

---

### P2-023 没有 ETL  freshness  indicator
**位置**: 整个页面  
**问题**: 页面没有任何地方显示"数据最后更新时间"。运营不知道看到的是 T+1、T+2 还是上周的数据。

**后果**: 周一早上 9 点，运营看到数据以为是最新的，但实际上 ETL 在周末失败了，数据是上周五的。基于此做的库存调配或投放决策会基于过期数据。

---

## 六、UX 问题（UX Issues）

### P1-024 YOY 没有区分 "%" 和 "pp"，同一个组件渲染两种不同量纲
**位置**: `CategoryView.vue` + `YOYBadge` 组件  
**问题**:  
- `gsv_yoy`、`users_yoy`、`aus_yoy` 是百分比变化（如 +25%）
- `old_ratio_yoy`、`new_ratio_yoy`、`member_ratio_yoy` 是百分点差（如 +5pp）

但两者都通过同一个 `YOYBadge` 组件渲染，UI 上没有任何视觉区分。

**后果**: 运营看到老客占比 YOY 为 "+5"，以为是 +5%，实际上是 +5 个百分点（从 30% 到 35%，真实百分比变化是 +16.7%）。在汇报时会说"老客占比提升了 5%"，实际上应该是"提升了 5 个百分点"，口径错误会让老板误解。

**修复**:  `YOYBadge` 对 ratio 类型指标显示 "+5.0pp"，对 absolute 类型显示 "+25.0%"。

---

### P1-025 品类-象限矩阵单元格把两个指标粘在一起，不可排序不可读
**位置**: `CategoryView.vue` 第 337-349 行  
**问题**:  
```javascript
row[`cat_${idx}`] = `${cat.user_count.toLocaleString()} | ¥${(cat.gmv / 10000).toFixed(1)}万`
```

单元格格式是"1,234 | ¥12.3万"，既：
1. 无法按用户数排序
2. 无法按 GMV 排序
3. 视觉拥挤，快速扫描困难

**后果**: 运营想找出"某象限 GMV 最高的品类"，必须肉眼逐行比较，无法点击表头排序。

**修复**:  拆分为两列（用户数列、GMV 列），或提供切换视图的功能。

---

### P1-026 饼图 tooltip 写死"GMV"，但实际可能是 GSV
**位置**: `CategoryView.vue` 第 122 行  
**问题**:  
```javascript
formatter: (params) => {
  return `${params.name}<br/>GMV: ¥${(params.value / 10000).toFixed(1)}万 (${params.percent}%)`
}
```

饼图标题是"品类GMV分布"，tooltip 也写死"GMV"。但如 P0-001 所述，数据实际是 GSV。

**修复**:  根据 `metric_type` 动态显示"GMV"或"GSV"。

---

### P2-027 表格横向滚动条在 1200-1250px，小屏幕体验差
**位置**: `CategoryView.vue` 第 426、442 行  
**问题**: `scroll-x={1200}` 和 `1250`，在 13 寸笔记本（1280px 宽度）上会出现横向滚动条，关键指标可能被挤出可视区域。

**修复**:  提供"紧凑模式"或允许用户折叠 YOY 列，只显示核心指标。

---

### P2-028 `DataTablePro` 的 `total-row` 没有视觉区分度
**位置**: `CategoryView.vue` 第 424、440 行  
**问题**: TTL 行（汇总行）样式与普通数据行相同，运营快速滚动时难以定位汇总数据。

**修复**: TTL 行加粗、底色高亮或固定到底部。

---

## 附录：问题汇总表

| 编号 | 严重性 | 类别 | 一句话描述 |
|------|--------|------|-----------|
| P0-001 | P0 | 逻辑错误 | 全站把 GSV 当 GMV 返回，口径完全错误 |
| P0-002 | P0 | 逻辑错误 | 会员表格使用全店数据，会员分析完全失真 |
| P0-003 | P0 | 逻辑错误 | 会员 TTL 行计算错误，会员占比永远显示 100% |
| P0-016 | P0 | 业务不一致 | 8 象限名称：PRD/业务/代码三方完全不一致 |
| P0-017 | P0 | 业务不一致 | R 阈值 [30,90,180,365] 与业务文档 [14,30,60,90] 完全不同 |
| P1-004 | P1 | 逻辑错误 | YoY cutoff 与新老客定义在跨月分析时矛盾 |
| P1-005 | P1 | 逻辑错误 | `user_rfm` JOIN 硬编码 GMV，与 GSV 分析错配 |
| P1-006 | P1 | 缺失功能 | 只有 YoY 没有 MoM，日常运营缺少环比敏感 |
| P1-007 | P1 | 缺失功能 | 品类画像 API 不支持全局筛选器 |
| P1-008 | P1 | 缺失功能 | 品类层级写死为 class，无法钻取 |
| P1-011 | P1 | 边界情况 | 饼图基于 GMV、表格 pct 基于用户数，两者不一致 |
| P1-012 | P1 | 边界情况 | `user_rfm` 缺失时所有用户静默归为"其他" |
| P1-013 | P1 | 边界情况 | 新品类 YoY 空白，无法识别新品 |
| P1-018 | P1 | 业务不一致 | KPI 卡片是 90 天滚动，表格是选定周期，口径打架 |
| P1-019 | P1 | 业务不一致 | API 返回字段与前端 TS 类型不匹配 |
| P1-020 | P1 | 业务不一致 | 分布/矩阵 TAB 无新老客概念，与概览 TAB 口径不一致 |
| P1-021 | P1 | 管道缺口 | `user_first_purchase` 缺失时新客数恒为 0 |
| P1-022 | P1 | 管道缺口 | 3% 未映射 SPU 订单无监控无告警 |
| P1-024 | P1 | UX | YOY 不区分 "%" 和 "pp"，汇报口径易错 |
| P1-025 | P1 | UX | 矩阵单元格把用户数和 GMV 粘在一起，不可排序 |
| P1-026 | P1 | UX | 饼图 tooltip 写死"GMV"，与实际口径不符 |
| P2-009 | P2 | 缺失功能 | 无导出功能 |
| P2-010 | P2 | 缺失功能 | 无品类搜索/过滤 |
| P2-014 | P2 | 边界情况 | 日期解析无非法输入防护 |
| P2-015 | P2 | 边界情况 | 低价渠道名前端硬编码，ETL 改名即失效 |
| P2-023 | P2 | 管道缺口 | 无数据 freshness 指示器 |
| P2-027 | P2 | UX | 表格横向滚动条过宽，小屏幕体验差 |
| P2-028 | P2 | UX | TTL 汇总行无视觉区分 |

---

*评审结论：品类看板 v2 当前存在 4 个 P0 级问题（其中 2 个是指标定义/校准错误，2 个是业务逻辑不一致），这些问题会导致运营基于错误数据做出错误决策。建议在修复 P0 问题后再投入生产使用。*
