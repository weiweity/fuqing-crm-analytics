# Week 2 RFM 模型设计文档

> 芙清 CRM 客户分析系统 · RFM 计算模块
> 版本: v1.0 · 日期: 2026-03-31

---

## 1. 业务背景与目标

**业务场景**: 618 大促前需要精准人群包，用于：
- 高价值用户触达（Champions）
- 流失用户召回（At Risk / Lost Customers）
- 潜力用户培养（Potential Loyalists）

**设计目标**:
- 分析周期可配置（默认 180 天）
- 单条 SQL 完成 RFM 计算，禁止循环
- 支持 GSV（退款过滤）和 GMV 两种口径
- 预计算表 `user_rfm` 加速前端查询

---

## 2. RFM 定义

| 维度 | 名称 | 计算逻辑 | 业务含义 |
|------|------|----------|----------|
| **R** | Recency | `分析日 - 最近一次下单日期`（天数） | 越近越好 |
| **F** | Frequency | 分析周期内有效订单数 | 越多越好 |
| **M** | Monetary | 分析周期内累计消费金额 | 越高越好 |

### 2.1 分析周期

- **默认**: 近 180 天
- **可选配置**: 90 / 180 / 365 天
- **分析日**: `CURRENT_DATE`（可参数化）

### 2.2 订单口径

| 口径 | 过滤条件 |
|------|----------|
| **GMV** | `order_status LIKE '%成功%'` |
| **GSV** | `order_status LIKE '%成功%' AND (refund_status IS NULL OR refund_status = '')` |

---

## 3. 分值计算方案

### 3.1 百分位分箱法（推荐）

使用 `NTILE(5)` 对有消费记录的用户分箱：

| 分值 | 含义 | R 解读 | F/M 解读 |
|------|------|--------|----------|
| 5 | Top 20% | 最近 20% | 最高 20% |
| 4 | 20-40% | 次近 20% | 次高 20% |
| 3 | 40-60% | 中间 20% | 中间 20% |
| 2 | 60-80% | 次远 20% | 次低 20% |
| 1 | Bottom 20% | 最远 20% | 最低 20% |

**注意**: 仅对分析周期内有消费记录的用户计算 NTILE，确保分箱在活跃用户内部分发。

### 3.2 固定阈值参考方案（备选）

如需固定阈值参考：

| 分值 | R（天数） | F（频次） | M（金额） |
|------|-----------|-----------|-----------|
| 5 | 0-30 | ≥10 | ≥5000 |
| 4 | 31-60 | 5-9 | 2000-4999 |
| 3 | 61-90 | 3-4 | 500-1999 |
| 2 | 91-180 | 2 | 100-499 |
| 1 | >180 | 1 | <100 |

**推荐使用百分位分箱**，数据驱动，不受业务假设干扰。

---

## 4. RFM 人群分层

### 4.1 八大人群定义

```
Champions (冠军用户)        : R≥4 AND F≥4 AND M≥4
Loyal Customers (忠诚用户)   : R≥3 AND F≥3 AND M≥3 AND NOT Champions
Potential Loyalists (潜力用户): R≥3 AND F<3 AND M≥3
At Risk (风险用户)          : R≤2 AND F≥3 AND M≥3
Cannot Lose Them (重点挽回)  : R≤2 AND F≥4 AND M≥4
Lost Customers (流失用户)    : R≤2 AND F≤2 AND M≤2
Hibernating (沉睡用户)      : R≤2 AND F≤3 AND M≤3 AND NOT Lost
Promising (萌芽用户)        : R≥4 AND F≤2 AND M≤2
```

### 4.2 人群特征

| 人群 | 业务策略 | 触达时机 |
|------|----------|----------|
| Champions | VIP 专属权益、限量款优先购 | 大促前 7 天 |
| Loyal Customers | 会员日提醒、积分加倍 | 日常维护 |
| Potential Loyalists | 升级激励、满减券 | 大促前 14 天 |
| At Risk | 定向召回、流失预警券 | 大促前 21 天 |
| Cannot Lose Them | 1对1客服、专属折扣 | 立即触达 |
| Lost Customers | 大额唤醒券 | 大促主力 |
| Hibernating | 老客专享价 | 日常唤醒 |
| Promising | 新品试用、满额赠礼 | 大促前 14 天 |

---

## 5. DuckDB SQL 设计

### 5.1 预计算表建表语句

```sql
-- RFM 预计算表（按分析日和口径分区）
CREATE TABLE IF NOT EXISTS user_rfm (
    user_id            VARCHAR,      -- 用户ID
    user_nickname      VARCHAR,      -- 用户昵称
    analysis_date      DATE,        -- 分析日期
    metric_type        VARCHAR,     -- 'GMV' 或 'GSV'
    recency_days       INTEGER,     -- R: 最近购买距分析日天数
    frequency          INTEGER,     -- F: 有效订单数
    monetary           DECIMAL(12,2),-- M: 累计消费金额
    r_score            TINYINT,     -- R 分值 1-5
    f_score            TINYINT,     -- F 分值 1-5
    m_score            TINYINT,     -- M 分值 1-5
    rfm_tier           VARCHAR,     -- RFM 人群标签
    first_order_date   DATE,       -- 用户首次下单日期
    last_order_date    DATE,       -- 用户最近下单日期
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, analysis_date, metric_type)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_rfm_tier ON user_rfm(rfm_tier);
CREATE INDEX IF NOT EXISTS idx_rfm_analysis ON user_rfm(analysis_date, metric_type);
```

### 5.2 RFM 计算单条查询

```sql
-- =============================================
-- RFM 计算查询（单条 SQL，无循环）
-- 参数化：分析日、回顾天数、口径
-- =============================================
WITH base_params AS (
    SELECT
        DATE '2026-03-31'       AS analysis_date,   -- 分析日
        180                      AS lookback_days,   -- 回顾天数
        'GMV'                    AS metric_type      -- GMV 或 GSV
),
-- Step 1: 过滤分析周期内有效订单
period_orders AS (
    SELECT
        o.user_id,
        o.user_nickname,
        DATE(p.analysis_date)                                       AS analysis_date,
        p.metric_type,
        o.order_id,
        o.order_time,
        CASE
            WHEN p.metric_type = 'GSV'
            THEN CASE WHEN o.refund_status IS NULL OR o.refund_status = '' THEN o.actual_amount ELSE 0 END
            ELSE o.actual_amount
        END AS valid_amount
    FROM orders o
    CROSS JOIN base_params p
    WHERE o.order_time >= DATE(p.analysis_date) - INTERVAL (p.lookback_days) DAY
      AND o.order_time <  DATE(p.analysis_date) + INTERVAL '1' DAY
      AND o.order_status LIKE '%成功%'
),
-- Step 2: 计算每个用户的 R/F/M 原始值
user_rfm_raw AS (
    SELECT
        user_id,
        user_nickname,
        analysis_date,
        metric_type,
        MIN(order_time)                                       AS first_order_time,
        MAX(order_time)                                       AS last_order_time,
        COUNT(DISTINCT order_id)                              AS frequency,
        SUM(valid_amount)                                    AS monetary
    FROM period_orders
    GROUP BY user_id, user_nickname, analysis_date, metric_type
),
-- Step 3: 计算 Recency（距分析日天数）
user_rfm_base AS (
    SELECT
        user_id,
        user_nickname,
        analysis_date,
        metric_type,
        DATEDIFF('day', last_order_time, analysis_date)      AS recency_days,
        frequency,
        monetary
    FROM user_rfm_raw
),
-- Step 4: NTILE 分箱（分别对 R/F/M 计算分值）
-- R: 越小分越高（使用降序）
rf_scored AS (
    SELECT
        *,
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score
    FROM user_rfm_base
),
-- F: 越大分越高（使用升序）
rfm_scored AS (
    SELECT
        *,
        NTILE(5) OVER (ORDER BY frequency ASC)      AS f_score,
        NTILE(5) OVER (ORDER BY monetary ASC)      AS m_score
    FROM rf_scored
),
-- Step 5: RFM 人群分层
user_rfm_final AS (
    SELECT
        user_id,
        user_nickname,
        analysis_date,
        metric_type,
        recency_days,
        frequency,
        monetary,
        r_score,
        f_score,
        m_score,
        CONCAT(r_score, f_score, m_score)          AS rfm_code,
        CASE
            WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions'
            WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN 'Loyal Customers'
            WHEN r_score >= 3 AND f_score <  3 AND m_score >= 3 THEN 'Potential Loyalists'
            WHEN r_score <= 2 AND f_score >= 3 AND m_score >= 3 THEN 'At Risk'
            WHEN r_score <= 2 AND f_score >= 4 AND m_score >= 4 THEN 'Cannot Lose Them'
            WHEN r_score <= 2 AND f_score <= 2 AND m_score <= 2 THEN 'Lost Customers'
            WHEN r_score <= 2 AND f_score <= 3 AND m_score <= 3 THEN 'Hibernating'
            WHEN r_score >= 4 AND f_score <= 2 AND m_score <= 2 THEN 'Promising'
            ELSE 'Others'
        END AS rfm_tier,
        DATE(first_order_time)                       AS first_order_date,
        DATE(last_order_time)                        AS last_order_date
    FROM rfm_scored
)
-- 最终输出
SELECT
    user_id,
    user_nickname,
    analysis_date,
    metric_type,
    recency_days,
    frequency,
    monetary,
    r_score,
    f_score,
    m_score,
    rfm_code,
    rfm_tier,
    first_order_date,
    last_order_date
FROM user_rfm_final
ORDER BY rfm_tier, m_score DESC;
```

### 5.3 人群分布查询

```sql
-- RFM 人群分布统计
WITH base_params AS (
    SELECT
        DATE '2026-03-31'       AS analysis_date,
        180                      AS lookback_days,
        'GMV'                    AS metric_type
),
period_orders AS (
    SELECT
        o.user_id,
        o.user_nickname,
        CASE
            WHEN p.metric_type = 'GSV'
            THEN CASE WHEN o.refund_status IS NULL OR o.refund_status = '' THEN o.actual_amount ELSE 0 END
            ELSE o.actual_amount
        END AS valid_amount
    FROM orders o
    CROSS JOIN base_params p
    WHERE o.order_time >= DATE(p.analysis_date) - INTERVAL (p.lookback_days) DAY
      AND o.order_time <  DATE(p.analysis_date) + INTERVAL '1' DAY
      AND o.order_status LIKE '%成功%'
),
user_rfm_raw AS (
    SELECT
        user_id,
        user_nickname,
        COUNT(DISTINCT order_id)  AS frequency,
        SUM(valid_amount)        AS monetary
    FROM period_orders
    GROUP BY user_id, user_nickname
),
user_rfm_base AS (
    SELECT
        user_id,
        user_nickname,
        DATEDIFF('day', MAX(order_time), (SELECT analysis_date FROM base_params)) AS recency_days,
        frequency,
        monetary
    FROM period_orders
    GROUP BY user_id, user_nickname, frequency, monetary
),
rfm_scored AS (
    SELECT
        *,
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
        NTILE(5) OVER (ORDER BY frequency ASC)    AS f_score,
        NTILE(5) OVER (ORDER BY monetary ASC)       AS m_score
    FROM user_rfm_base
),
user_rfm_tiered AS (
    SELECT
        *,
        CASE
            WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions'
            WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN 'Loyal Customers'
            WHEN r_score >= 3 AND f_score <  3 AND m_score >= 3 THEN 'Potential Loyalists'
            WHEN r_score <= 2 AND f_score >= 3 AND m_score >= 3 THEN 'At Risk'
            WHEN r_score <= 2 AND f_score >= 4 AND m_score >= 4 THEN 'Cannot Lose Them'
            WHEN r_score <= 2 AND f_score <= 2 AND m_score <= 2 THEN 'Lost Customers'
            WHEN r_score <= 2 AND f_score <= 3 AND m_score <= 3 THEN 'Hibernating'
            WHEN r_score >= 4 AND f_score <= 2 AND m_score <= 2 THEN 'Promising'
            ELSE 'Others'
        END AS rfm_tier
    FROM rfm_scored
)
SELECT
    rfm_tier,
    COUNT(*)                                     AS user_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS user_pct,
    SUM(monetary)                               AS total_amount,
    ROUND(AVG(monetary), 2)                     AS avg_amount,
    ROUND(AVG(frequency), 2)                    AS avg_frequency,
    ROUND(AVG(recency_days), 1)                 AS avg_recency
FROM user_rfm_tiered
GROUP BY rfm_tier
ORDER BY SUM(monetary) DESC;
```

### 5.4 618 人群包导出查询

```sql
-- 618 大促高价值人群包
WITH base_params AS (
    SELECT
        DATE '2026-06-01'    AS campaign_date,   -- 618 分析日（预估）
        180                  AS lookback_days,
        'GMV'                AS metric_type
),
-- ... (同上计算逻辑) ...
SELECT
    user_id,
    user_nickname,
    rfm_tier,
    monetary            AS total_spend,
    frequency           AS order_count,
    recency_days        AS days_since_last,
    -- 618 适用标签
    CASE
        WHEN rfm_tier IN ('Champions', 'Cannot Lose Them') THEN '618_VIP_Priority'
        WHEN rfm_tier = 'Loyal Customers'                   THEN '618_Loyal_Gift'
        WHEN rfm_tier = 'At Risk'                           THEN '618_Risk_Recall'
        WHEN rfm_tier = 'Lost Customers'                    THEN '618_Lost_Rescue'
        WHEN rfm_tier = 'Potential Loyalists'               THEN '618_Potential_Upgrade'
        WHEN rfm_tier = 'Promising'                         THEN '618_Promising_Trial'
        WHEN rfm_tier = 'Hibernating'                       THEN '618_Hibernate_Awaken'
        ELSE '618_General'
    END AS campaign_tag
FROM user_rfm_final
WHERE rfm_tier != 'Others'
ORDER BY m_score DESC, f_score DESC
LIMIT 50000;  -- 导出上限
```

---

## 6. 服务层接口设计

### 6.1 Python 函数签名

```python
# backend/services/rfm_service.py

from typing import Literal, Optional
from datetime import date

def calculate_rfm(
    analysis_date: str,           # 分析日期 YYYY-MM-DD
    lookback_days: int = 180,     # 回顾天数
    metric_type: Literal["GMV", "GSV"] = "GMV"
) -> list[dict]:
    """
    计算 RFM 分值和人群
    返回: [{user_id, r_score, f_score, m_score, rfm_tier, ...}, ...]
    """
    pass

def get_rfm_distribution(
    analysis_date: str,
    lookback_days: int = 180,
    metric_type: Literal["GMV", "GSV"] = "GMV"
) -> dict:
    """
    获取 RFM 人群分布统计
    """
    pass

def export_rfm_segment(
    segment: str,                # 人群标签
    analysis_date: str,
    lookback_days: int = 180,
    metric_type: Literal["GMV", "GSV"] = "GMV",
    limit: int = 10000
) -> list[dict]:
    """
    导出指定人群包
    """
    pass

def refresh_rfm_table(
    analysis_dates: list[str],   # 批量刷新日期
    metric_types: list[str] = ["GMV", "GSV"]
) -> dict:
    """
    刷新预计算表 user_rfm
    """
    pass
```

---

## 7. 预计算策略

### 7.1 增量刷新

| 场景 | 策略 |
|------|------|
| 每日凌晨 | 刷新昨天 analysis_date 的 RFM |
| 大促前 7 天 | 额外刷新大促日 analysis_date |
| ETL 完成后 | 追加刷新最新数据的 RFM |

### 7.2 分区建议

`user_rfm` 表按 `(analysis_date, metric_type)` 联合主键，可按月分区：

```sql
-- 按月分区（ DuckDB 支持）
CREATE TABLE user_rfm (
    ...
) PARTITION BY (analysis_date);
```

---

## 8. 前端集成

### 8.1 Vue3 页面规划（Streamlit 已废弃）

- `/rfm` 页面：RFM 人群分布看板（`frontend-vue3/src/views/RfmView.vue`）
  - 人群占比饼图
  - 人群特征表格（人数/金额/频次/平均 Recency）
  - 人群明细下载

- `/rfm/segments` 页面：人群包管理
  - 选中人群查看用户列表
  - 导出人群包（CSV）

---

## 9. 技术风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| 新用户无历史订单 | RFM 无法计算 | 单独标记为 "New User"，不参与 RFM 分层 |
| 数据倾斜（少量超头部用户） | M 分箱失效 | 考虑对数变换或分层 NTILE |
| 回顾期内无消费用户 | 不出现在结果中 | 这是预期行为，结果集仅包含活跃用户 |

---

## 10. 下一步任务

- [ ] 在 `backend/services/` 下新建 `rfm_service.py`
- [ ] 在 DuckDB 中创建 `user_rfm` 表
- [ ] 实现 `calculate_rfm()` 单条 SQL 查询
- [ ] 实现 `get_rfm_distribution()` 人群统计
- [ ] 前端 `/rfm` 页面开发
- [ ] 618 人群包导出功能

---

*设计: rfm-calculations · 审查: team-lead · 日期: 2026-03-31*
