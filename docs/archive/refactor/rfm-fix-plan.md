# RFM 模型口径统一修复方案

## 一、问题一句话

品类象限矩阵和老客健康仪表盘使用**同一套象限定义**，但底层 R/F 计算口径不同，导致两个模块的象限分布不一致。

---

## 二、根因（通俗易懂版）

### 2.1 象限定义（两套系统完全一致）

```
重要价值客户：R高(最近买过) + F高(买得多) + M高(花得多)
重要保持客户：R低(很久没买) + F高(买得多) + M高(花得多)  ← 问题象限
重要发展客户：R高(最近买过) + F低(买得少) + M高(花得多)
重要挽留客户：R低(很久没买) + F低(买得少) + M高(花得多)
一般价值客户：R高(最近买过) + F高(买得多) + M低(花得少)
一般保持客户：R低(很久没买) + F高(买得多) + M低(花得少)  ← 问题象限
一般发展客户：R高(最近买过) + F低(买得少) + M低(花得少)
一般挽留客户：R低(很久没买) + F低(买得少) + M低(花得少)
```

### 2.2 两套系统的 F 计算差异

| | 品类象限 (`user_rfm` 表) | 老客健康 (`rfm_analysis`) |
|---|---|---|
| **F 统计什么** | 90天内买了几次 | 全历史买了几次 |
| **R 统计什么** | 距今天多少天（基于90天内最近一单） | 距今天多少天（基于全历史最近一单） |

### 2.3 为什么"重要保持客户"在品类象限里几乎为空？

```
重要保持客户定义：R低(很久没买) + F高(买得多)

在品类象限的口径下：
  - F高 = 90天内买了4次以上
  - R低 = 最近一单距今≥90天

矛盾点：
  如果90天内买了4次，那最后一次购买必然发生在90天内
  → 不可能同时满足"最近一单≥90天"
  
所以：这个象限在数学上几乎不可能出现（数据库里只有2人，是边界极端情况）
```

在老客健康的口径下：
  - F高 = 全历史买了4次以上（可以是过去2年累计的）
  - R低 = 最近一单距今≥90天
  
  不矛盾：用户过去2年买了6次，但最近一单在100天前 → 完全合理

### 2.4 验证数据

```
2026-04-20, lookback=90天：

品类象限 (user_rfm 表)：
  重要价值客户: 16,537人 ✅
  重要保持客户: 2人 ⚠️（数学互斥）
  重要发展客户: 93,877人 ✅
  重要挽留客户: 292人 ✅
  一般价值客户: 25,026人 ✅
  一般保持客户: 12人 ⚠️（数学互斥）
  一般发展客户: 2,696,145人 ✅
  一般挽留客户: 18,891人 ✅

老客健康 (rfm_analysis)：
  所有8个象限均有正常分布 ✅
```

---

## 三、修复目标

让品类象限矩阵的 RFM 计算口径与老客健康仪表盘**完全一致**。

---

## 四、修复方案（推荐：方案 B）

### 方案 A：修改 `preload_rfm.py`（改预计算表）

**思路**：让 `user_rfm` 表的 F 计算也使用全历史订单数，而不是仅 lookback 窗口内的。

**修改点**：
1. `preload_rfm.py` 中 `user_metrics` CTE 的 `frequency` 计算，从 `period_orders`（90天窗口）改为全历史
2. 但 R 的 `last_pay_time` 仍基于 `period_orders`（保持与品类时间窗口一致）

**问题**：
- `user_rfm` 表被多个模块共用（flow_service 等），改 F 口径可能影响其他模块
- 需要重新跑 ETL 预计算所有历史日期（约360次写入，耗时10-20分钟）

**不推荐**，影响面太大。

---

### 方案 B：品类象限改用实时 SQL（推荐）

**思路**：不动 `user_rfm` 预计算表，让品类象限矩阵直接走老客健康的实时 SQL 逻辑计算 RFM。

**修改点**：
1. `category_service.py` 的 `get_category_segment_matrix` 函数
2. 不再 JOIN `user_rfm` 表获取 segment_id
3. 改用与 `rfm_analysis.py` 相同的 CTE 结构实时计算 RFM

**优点**：
- 不动 `user_rfm` 表，不影响其他模块
- 口径与老客健康完全一致
- 实现简单，只改一个函数

**缺点**：
- 品类象限查询速度会变慢（实时 SQL vs 预计算表 JOIN）
- 但品类象限不是高频查询，可接受

**推荐此方案**。

---

### 方案 C：前端降级提示（兜底）

**思路**：不改后端，只改前端显示。

**修改点**：
1. `QuadrantMatrixTab.vue` 中，当某象限全为"-"时，显示"该象限在此周期无用户"

**优点**：
- 立即可上线
- 不改任何数据逻辑

**缺点**：
- 治标不治本
- 用户仍会在不同模块看到不一致的象限分布

**可作为方案 B 实施前的临时措施**。

---

## 五、方案 B 详细实施步骤

### 5.1 需要修改的文件

| 文件 | 修改内容 | 行数估算 |
|------|---------|---------|
| `backend/services/category_service.py` | `get_category_segment_matrix` 函数重写 | ~80行 |
| `backend/contracts/schemas.py` | 确认 `CategorySegmentMatrixResponse` 字段 | 无需修改 |
| `frontend-vue3/src/views/category-tabs/QuadrantMatrixTab.vue` | 可选：添加空象限提示 | ~5行 |

### 5.2 具体修改：`category_service.py`

当前 `get_category_segment_matrix` 函数（约第195-280行）：
- 从 `user_rfm` 表读取 `segment_id`
- 按 segment_id + category 聚合
- 返回 `matrix: {"1": [...], "2": [...], ...}`

**新逻辑**：
1. 用 CTE 计算每个用户的 RFM（同 `rfm_analysis.py`）
2. 按 RFM segment + category 聚合
3. 返回结构与现在完全一致（前端无需修改）

**关键 SQL 结构**：

```sql
WITH
-- 1. 品类订单（当前周期）
base_orders AS (
    SELECT user_id, actual_amount, category_field
    FROM orders
    WHERE pay_time >= ? AND pay_time < ?
      AND valid_order条件
),
-- 2. 用户全历史统计（用于 RFM，截至 cutoff）
user_stats AS (
    SELECT
        user_id,
        MAX(pay_time) as last_pay_time,
        COUNT(DISTINCT order_id) as order_count,  -- 全历史F
        SUM(actual_amount) as gsv                  -- 全历史M
    FROM orders
    WHERE pay_time <= ?::TIMESTAMP
      AND valid_order条件
    GROUP BY user_id
),
-- 3. RFM 评分（同 rfm_analysis.py 的评分逻辑）
rfm_scored AS (
    SELECT
        user_id,
        CASE WHEN DATEDIFF(...) < 14 THEN 5 ... END as r_score,
        CASE WHEN order_count >= 6 THEN 5 ... END as f_score,
        CASE WHEN gsv >= 1000 THEN 5 ... END as m_score
    FROM user_stats
),
-- 4. 象限分配（同 segments.py 的 CASE WHEN）
segmented AS (
    SELECT user_id,
        CASE
            WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 1
            WHEN r_score < 4 AND f_score >= 4 AND m_score >= 4 THEN 2
            ...
        END as segment_id
    FROM rfm_scored
),
-- 5. 品类-象限交叉聚合
category_segment AS (
    SELECT
        s.segment_id,
        bo.category_field as category_name,
        COUNT(DISTINCT bo.user_id) as user_count,
        SUM(bo.actual_amount) as gmv
    FROM base_orders bo
    LEFT JOIN segmented s ON bo.user_id = s.user_id
    GROUP BY s.segment_id, bo.category_field
)
SELECT ... FROM category_segment
```

### 5.3 参数传递

当前函数参数：
```python
def get_category_segment_matrix(
    date: str,           # 分析日期
    lookback_days: int,  # 回溯天数（用于品类订单窗口）
    level: str,          # 品类层级
    top_n: int,          # 每个象限返回前N品类
    exclude_channels: Optional[List[str]] = None,
)
```

新函数需要额外参数：
```python
def get_category_segment_matrix(
    date: str,
    lookback_days: int,  # 品类订单窗口（保持）
    level: str,
    top_n: int,
    exclude_channels: Optional[List[str]] = None,
    # 新增：RFM cutoff 日期，默认 = date - 1天
    cutoff_date: Optional[str] = None,
)
```

### 5.4 前端修改（可选，方案 C 兜底）

在 `QuadrantMatrixTab.vue` 中，渲染矩阵单元格时：

```typescript
// 当前
if (!value) return '—'

// 改为
if (!value) {
    // 如果整行都是空的，显示更明确的提示
    const rowAllEmpty = rowData.every(cell => !cell)
    return rowAllEmpty ? '该象限无用户' : '—'
}
```

---

## 六、验证清单

修复后必须验证：

1. **数据一致性**：
   - 品类象限的 8 个象限分布与老客健康的 8 个象限分布数量级一致
   - segment 2（重要保持）和 segment 6（一般保持）不再为空

2. **API 返回结构**：
   - `GET /api/v1/category/segment` 返回的 JSON 结构与现在完全一致
   - 前端无需修改即可正常显示

3. **性能**：
   - 品类象限查询耗时 < 3 秒（可接受范围）

4. **边界情况**：
   - 切换不同 lookback_days（30/90/180）时，象限分布合理变化
   - 切换不同 level（type/class/tier）时，品类聚合正确

---

## 七、执行顺序

```
Step 1: 备份当前 category_service.py
Step 2: 修改 get_category_segment_matrix 函数（按5.2节SQL）
Step 3: 本地测试：python -c "from backend.services.category_service import get_category_segment_matrix; print(get_category_segment_matrix('2026-04-20', 90, 'class'))"
Step 4: 重启后端，浏览器验证品类象限矩阵
Step 5: 对比老客健康的象限分布，确认一致
Step 6: （可选）前端添加空象限提示
Step 7: 更新文档，记录口径统一
```

---

## 八、关键代码引用

### 8.1 当前有问题的代码（category_service.py ~244行）

```python
# 当前：从 user_rfm 表读 segment_id（F 是90天窗口口径）
LEFT JOIN user_rfm r ON o.user_id = r.user_id
    AND r.analysis_date = p.rfmx_date
    AND r.metric_type = 'GMV'
    AND r.lookback_days = ?
```

### 8.2 老客健康的正确代码（rfm_analysis.py ~164-249行）

```python
# 正确：实时计算 RFM（F 是全历史口径）
user_stats_all AS (
    SELECT user_id, MAX(pay_time), COUNT(DISTINCT order_id), SUM(actual_amount)
    FROM orders WHERE pay_time <= ?::TIMESTAMP
    GROUP BY user_id
),
rfm_scored_all AS (
    SELECT user_id,
        CASE WHEN DATEDIFF(...) < 14 THEN 5 ... END as r_score,
        CASE WHEN order_count >= 6 THEN 5 ... END as f_score,
        CASE WHEN gsv >= 1000 THEN 5 ... END as m_score
    FROM user_stats_all
),
segmented_all AS (
    SELECT user_id,
        CASE
            WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN '重要价值客户'
            WHEN r_score < 4 AND f_score >= 4 AND m_score >= 4 THEN '重要保持客户'
            ...
        END as rfm_segment
    FROM rfm_scored_all
)
```

### 8.3 阈值常量（backend/semantic/segments.py）

```python
RFM_THRESHOLDS = {
    "r": [30, 90, 180, 365],   # R 阈值（preload_rfm 用）
    "f": [1, 2, 3, 4],         # F 阈值（preload_rfm 用）
    "m": [100, 300, 500, 1000] # M 阈值
}
```

注意：rfm_analysis.py 用的是硬编码阈值 `[14, 30, 60, 90]` 和 `[1, 2, 3, 5]`，与 `RFM_THRESHOLDS` 不同。修复时应统一引用 `RFM_THRESHOLDS`。

---

## 九、风险与回滚

| 风险 | 应对措施 |
|------|---------|
| 实时 SQL 太慢 | 加缓存（同 rfm_analysis 的 Plan C） |
| 象限分布与老客健康仍不一致 | 检查是否用了相同的阈值常量 |
| 影响其他使用 user_rfm 的模块 | 方案 B 不动 user_rfm，无影响 |

回滚：恢复 `category_service.py` 备份，重启后端即可。

---

**文档版本**: v1.0
**创建日期**: 2026-04-22
**状态**: 待执行
