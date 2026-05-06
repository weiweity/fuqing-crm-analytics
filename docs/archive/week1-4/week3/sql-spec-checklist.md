# Week 3 SQL 规范清单 & 验收测试点

> QA Agent 出品 | 版本 v1.0 | 2026-04-02
> 基于 Week 2 血泪经验（CTE 类型推断 Bug、SQL 注入）制定

---

## 一、DuckDB CTE 类型安全（必须遵守）

### 规则 1：禁止 `SELECT *` + `INSERT INTO` 混用

**危险等级：P0**
**历史 Bug："Could not convert string 'Others' to INT32"**

DuckDB 对混合类型 CTE 的类型推断不稳定，`SELECT *` 会引入未声明类型的列，导致 INSERT 时类型转换失败。

**❌ 禁止模式：**
```sql
WITH cte AS (
    SELECT * FROM orders  -- 禁止 SELECT *
)
INSERT INTO user_rfm
SELECT * FROM cte  -- 禁止 SELECT *
```

**✅ 正确模式：**
```sql
WITH cte AS (
    SELECT user_id, order_id, actual_amount, order_time,
           COALESCE(refund_status, '') AS refund_status
    FROM orders  -- 显式列
)
INSERT INTO user_rfm (user_id, order_id, monetary, order_date)
SELECT user_id, order_id, monetary, order_time FROM cte  -- 显式列
```

**规则总结：**
- [ ] CTE 内部禁止 `SELECT *`，必须显式列出所有列
- [ ] INSERT 语句必须显式列出所有目标列名
- [ ] SELECT 子句必须显式列出所有源列名（与 INSERT 列名一一对应）
- [ ] 类型不一致时显式 CAST（如 `CAST(col AS INTEGER)`）

---

### 规则 2：参数化查询（P0）

**危险等级：P0**
**历史 Bug：app.py Lines 82-105 SQL 注入**

所有外部输入（API 参数、前端回调）必须使用 `?` 占位符 + 参数列表。

**❌ 禁止模式：**
```python
conn.execute(f"""
    SELECT * FROM orders
    WHERE order_time >= '{start_date} 00:00:00'
      AND order_time <= '{end_date} 23:59:59'
""")
```

**✅ 正确模式：**
```python
conn.execute("""
    SELECT * FROM orders
    WHERE order_time >= ? AND order_time <= ?
      AND order_status LIKE '%成功%'
""", [f"{start_date} 00:00:00", f"{end_date} 23:59:59"])
```

**规则总结：**
- [ ] 所有 API 参数使用 `?` 占位符
- [ ] 参数通过列表传递（第二个参数）
- [ ] 业务常量（如 `'%成功%'`）可直接写在 SQL 中（非用户输入）

---

### 规则 3：CASE WHEN 类型一致性

**危险等级：P1**
**风险：CTE 类型推断混乱**

所有分支必须返回相同数据类型。

**❌ 禁止模式：**
```sql
CASE
    WHEN condition THEN 1
    WHEN condition THEN 2
    ELSE 'Others'  -- 突然返回字符串！
END AS segment_id
```

**✅ 正确模式：**
```sql
CASE segment_id
    WHEN 1 THEN '钻石会员'
    WHEN 2 THEN '潜力新贵'
    ...
    ELSE '其他用户'
END AS segment_name  -- 全程字符串
```
或全程整数。

---

## 二、Week 3 新增风险点

### 风险 1：流转矩阵 JOIN（85万用户 × 2时间点）

**风险描述：** 双时间点 JOIN 可能产生重复记录或丢失记录，需验证结果一致性。

**必须验证：**
- [ ] from_date 和 to_date 交换后矩阵转置一致（即 A→B 人数 = B→A 人数的逻辑对称性）
- [ ] 矩阵行合计 = from月用户总数
- [ ] 矩阵列合计 = to月用户总数
- [ ] 留存率 = 对角线用户数 / 总数（健康区间 0.6~0.9）

**SQL 规范：**
- [ ] 使用 `COUNT(DISTINCT user_id)` 而非 `COUNT(*)` 计算用户数
- [ ] JOIN 条件明确（user_id + 分析时间戳）
- [ ] 同一用户同一时间段只有一条记录（GROUP BY 聚合前验证 DISTINCT）

---

### 风险 2：MEDIAN() 聚合类型推断

**风险描述：** DuckDB 对 MEDIAN() 的类型推断可能因输入类型不同而异，与其他 INT 聚合混用时可能类型冲突。

**必须验证：**
- [ ] MEDIAN() 输入列显式声明类型（避免 NULL/字符串混入）
- [ ] MEDIAN() 结果与其他聚合列类型一致，必要时 CAST
- [ ] DuckDB 版本对 MEDIAN() 的支持（DuckDB 0.10+ 支持）

**示例：**
```sql
-- ✅ 正确：显式处理 NULL + 类型一致
SELECT
    category,
    MEDIAN(CAST(interpurchase_days AS DOUBLE)) AS median_days,
    COUNT(DISTINCT user_id) AS user_count
FROM user_purchase_pattern
WHERE interpurchase_days IS NOT NULL
GROUP BY category
```

---

### 风险 3：单品类计算（防重复/遗漏）

**风险描述：** 同一用户在不同品类有独立记录，需确保：
1. 用户-品类组合唯一
2. 品类间互斥（用户不会同时出现在两个品类的"流失"名单中，除非确实满足条件）
3. 汇总时不去重（品类级别求和 ≠ 用户级别）

**必须验证：**
- [ ] 每个 (user_id, category) 组合只有一条风险记录
- [ ] 流失判断以"最近购买日期 + 品类典型周期 × 150%"为基准
- [ ] 汇总表 SUM(流失用户数) 可能 > 总用户数（正常，因为跨品类重复计算）

**SQL 规范：**
- [ ] GROUP BY 必须包含 category（按品类分组）
- [ ] 不做去重汇总（SELECT COUNT(DISTINCT user_id) 只在单品类语境下使用）

---

## 三、流失预警动态阈值公式

**业务定义：**
- 典型购买周期：从用户历史订单计算单品类平均购买间隔
- 风险阈值：典型周期 × 150%
- 高风险：当前日期 - 最近购买日期 > 风险阈值
- 中风险：当前日期 - 最近购买日期 > 典型周期，但 ≤ 风险阈值

**DuckDB 实现规范：**
```sql
-- 计算用户品类级别购买间隔
WITH user_category_pattern AS (
    SELECT
        user_id,
        spu_category,
        MAX(order_time) AS last_order_time,
        DATEDIFF('day', MIN(order_time), MAX(order_time)) / NULLIF(COUNT(DISTINCT order_id) - 1, 0) AS avg_interpurchase_days
    FROM orders
    WHERE order_status LIKE '%成功%'
    GROUP BY user_id, spu_category
),
user_risk AS (
    SELECT
        user_id,
        spu_category,
        last_order_time,
        avg_interpurchase_days,
        CAST(avg_interpurchase_days * 1.5 AS INTEGER) AS risk_threshold_days,
        DATEDIFF('day', last_order_time, CURRENT_DATE) AS days_since_last_order,
        CASE
            WHEN DATEDIFF('day', last_order_time, CURRENT_DATE) > avg_interpurchase_days * 1.5 THEN 'high'
            WHEN DATEDIFF('day', last_order_time, CURRENT_DATE) > avg_interpurchase_days THEN 'medium'
            ELSE 'low'
        END AS risk_level
    FROM user_category_pattern
    WHERE avg_interpurchase_days IS NOT NULL AND avg_interpurchase_days > 0
)
SELECT * FROM user_risk
```

**验收测试点：**
- [ ] 动态阈值：`risk_score` 边界值正确（>150% 高风险，>100% 中风险）
- [ ] 固定阈值兜底：购买次数 < 3 的用户使用 R > 60 判断（样本不足时降级）
- [ ] 单品类：同一用户不同品类有独立风险记录
- [ ] NULL 处理：`avg_interpurchase_days IS NULL` 或 `= 0` 时不参与计算

---

## 四、资产分析验收点

**业务定义：**
- 按 RFM 8象限 + 其他（segment_id 1-9）聚合 GMV、用户数、人均价值
- gmv_share = 各象限 GMV / 总 GMV

**必须验证：**
- [ ] segment_id 1-9 都有数据（无空洞）
- [ ] SUM(gmv_share) = 1.0（或 100%，允许浮点误差 ±0.01）
- [ ] GMV = SUM(各象限 GMV)（加减法闭合）
- [ ] 用户数 = SUM(各象限用户数)

---

## 五、代码审查检查清单（Review Checklist）

### 提交前必须自检
- [ ] 无 `SELECT *`（在 CTE + INSERT 场景）
- [ ] 所有外部输入已参数化
- [ ] CASE WHEN 所有分支类型一致
- [ ] 日期计算使用 `DATEDIFF('day', date1, date2)` 而非字符串减法
- [ ] 聚合查询有 GROUP BY
- [ ] NULL 可能性已处理（COALESCE / IFNULL / WHERE 过滤）
- [ ] DuckDB 语法检查通过（无 MySQL/PostgreSQL 特有语法）

### 审查者检查
- [ ] SQL 逻辑与业务公式一致（动态阈值、流转矩阵、资产汇总）
- [ ] 无重复计算（特别是 JOIN 后再 GROUP BY 的场景）
- [ ] 索引覆盖（orders 表按 order_time + order_status 过滤后是否还有索引可用）
- [ ] 性能：85万用户 × 2时间点 的 JOIN 是否会爆内存

---

## 六、文件 Owner 约定

| 文件 | Owner | 审查者 |
|------|-------|--------|
| backend/services/cohort_service.py | backend-dev | qa-agent |
| backend/services/churn_service.py | backend-dev | qa-agent |
| backend/services/asset_service.py | backend-dev | qa-agent |
| frontend/pages/cohort_page.py | frontend-dev | qa-agent |
| frontend/pages/churn_page.py | frontend-dev | qa-agent |
| frontend/pages/asset_page.py | frontend-dev | qa-agent |
| frontend/components/cohort_charts.py | frontend-dev | qa-agent |
| frontend/components/churn_charts.py | frontend-dev | qa-agent |
| frontend/components/asset_charts.py | frontend-dev | qa-agent |

> 注：任何共享文件（如 app.py、config.py）修改前需先与 Owner 确认。

---

## 版本历史

| 版本 | 日期 | 作者 | 变更 |
|------|------|------|------|
| v1.0 | 2026-04-02 | qa-agent | 初始版本 |
