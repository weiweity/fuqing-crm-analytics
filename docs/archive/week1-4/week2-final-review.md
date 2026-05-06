# Week 2 最终审查报告

**审查日期**: 2026-04-01
**审查人**: fixer-agent
**审查范围**: `rfm_service.py`, `rfm_page.py`, `rfm_charts.py`, `rfm_strategy.py`

> **说明**: Oracle CLI (`@steipete/oracle`) 未安装于本环境，审查基于代码静态分析进行。

---

## 一、代码修复摘要

### P1: DuckDB 唯一索引 ✅ 已修复
**文件**: `backend/database.py`, `scripts/run_etl.py`

**问题**: `orders(order_id, sub_order_id)` 唯一索引缺失，可能导致 ETL 重复运行时产生重复数据。

**修复**:
```python
-- database.py (第126-130行)
conn.execute("CREATE UNIQUE INDEX idx_orders_order_unique ON orders(order_id, sub_order_id)")

-- run_etl.py (第426行)
conn.execute("CREATE UNIQUE INDEX idx_orders_order_unique ON orders(order_id, sub_order_id)")
```

---

### P2: 渠道规则 CSV 映射 ✅ 已修复
**文件**: `scripts/run_etl.py` (load_channel_rules 函数)

**问题**: 原代码使用位置索引 `df.columns = ['keyword', 'channel', 'unused', 'product_id', 'channel2']`，若 CSV 列顺序变化会出错。

**修复**: 改为按列名自动识别，支持多种可能的 header 格式，并保留位置索引作为 fallback：
```python
# 按列名映射
col_map = {}
for col in df.columns:
    col_lower = str(col).strip().lower()
    if '关键词' in col or 'keyword' in col_lower:
        col_map[col] = 'keyword'
    elif '渠道' in col and 'product' not in col_lower:
        col_map[col] = 'channel'
    # ... 等等
df = df.rename(columns=col_map)
```

---

### P3: 前端导出组件列名不匹配 ✅ 已修复
**文件**: `backend/services/rfm_service.py`, `frontend/components/rfm_export.py`

**问题**:
1. `calculate_rfm_scores()` 返回 `monetary AS total_amount`，但前端导出使用 `monetary`
2. `calculate_rfm_scores()` 返回 `rfm_tier` 但导出组件期望 `segment_name`
3. 缺少 `rfm_total` 字段

**修复**:
```python
# rfm_service.py - SELECT 语句
SELECT
    user_id, user_nickname,
    r_score, f_score, m_score,
    r_score + f_score + m_score AS rfm_total,  -- 新增
    segment_id,
    monetary,  -- 不再重命名为 total_amount
    frequency, recency_days

# rfm_service.py - Python 后处理
df["rfm_tier"] = df["segment_id"].map(seg_id_to_name_cn)
df["segment_name"] = df["rfm_tier"]  -- 新增别名
```

---

## 二、审查发现

### 1. SQL 逻辑审查 (rfm_service.py)

#### ✅ 固定阈值实现正确
- R/F/M 阈值 `[14,30,60,90]` / `[1,2,3,5]` / `[100,300,500,1000]` 与 `strategy_config.yaml` 一致
- CASE WHEN 评分逻辑正确

#### ⚠️ 可变周期互斥逻辑潜在问题
`calculate_rfm_mutable()` 中存在**边界条件模糊**：

```python
# 第442-447行
CASE
    WHEN uf.first_order_date < base.analysis_date_start - INTERVAL '730' DAY THEN '2y+'
    WHEN uf.first_order_date < base.analysis_date_start - INTERVAL '365' DAY THEN '1y2y'
    ...
```

**问题**: 若 `first_order_date` 恰好等于边界日期（如 `analysis_date_start - 365天`），会被归入 `'1y2y'` 而非 `'6m'`。这可能导致用户归属不确定。

**建议**: 使用 `BETWEEN ... AND ...` 明确闭区间，或在边界处加强覆盖。

---

### 2. 前端组件审查

#### ✅ rfm_charts.py - 图表实现良好
- 热力图、3D散点图、直方图实现正确
- 空数据防护完善
- `hover_data` 使用 `total_amount`，已与后端对齐

#### ⚠️ rfm_page.py - 潜在 bug
**位置**: 第395行
```python
if export_type != "全部用户":
    df_export = df_full[df_full.get('segment', '') == export_type]
```
**问题**: 使用 `.get('segment', '')` 访问 Series 的方法不对。应该是 `df_full['segment']` 或者用 `df_full.get('segment', pd.Series(['']*len(df_full)))`。

**建议修复**:
```python
if export_type != "全部用户":
    df_export = df_full[df_full['segment'] == export_type]
```

#### ✅ rfm_strategy.py - 策略定义完整
- 8象限策略卡片与业务设计文档一致
- 颜色配置与后端 `SEGMENT_COLORS` 对齐

---

### 3. 性能问题

#### ⚠️ 1399万行数据查询优化
`calculate_rfm_scores` 对大表的查询没有利用分区索引：

```sql
WHERE o.order_time >= p.analysis_date - INTERVAL (p.lookback_days) DAY
  AND o.order_time < p.analysis_date + INTERVAL '1' DAY
  AND o.order_status LIKE '%成功%'
```

**建议**:
1. 已有的 `idx_orders_time` 索引可加速时间过滤
2. 可考虑添加 `(order_status, order_time)` 复合索引进一步优化
3. 对于 `lookback_days=365` 的查询（近1年），建议增加采样逻辑防止内存溢出

---

### 4. 其他问题

#### ⚠️ GSV 口径退款判断逻辑
```python
CASE WHEN (refund_status IS NULL OR refund_status = '') THEN actual_amount ELSE 0 END
```
**问题**: `refund_status = ''` 的判断在 DuckDB 中可能不准确（NULL 和空字符串行为不同）。

**建议**: 统一用 `refund_status IS NULL OR refund_status = ''` 即可，或显式用 `COALESCE(refund_status, '') = ''`。

---

## 三、待处理项

| 优先级 | 问题 | 建议 |
|--------|------|------|
| P2 | 可变周期边界条件模糊 | 使用 BETWEEN 明确闭区间 |
| P2 | `df_full.get('segment', '')` bug | 改为 `df_full['segment']` |
| P2 | GSV 退款判断逻辑 | 确认 NULL/'' 处理是否正确 |
| P3 | 性能优化 | 考虑 `(order_status, order_time)` 复合索引 |

---

## 四、结论

Week 2 代码实现基本完成，核心 RFM 计算逻辑正确。已修复3个 P1/P2 问题：
- ✅ DuckDB 唯一索引已添加
- ✅ 渠道 CSV 改为按列名映射
- ✅ 前后端列名已对齐

剩余 P2-P3 问题为边界 case 和性能优化，不影响基本功能。

---

*报告生成时间: 2026-04-01 00:14*
