# R 区间流转看板 — API 契约设计

**版本**: v1.0  
**日期**: 2026-04-17  
**关联 PRD**: `docs/week1/PRD-rfm-r-flow.md`

---

## 1. 接口概览

| 项目 | 说明 |
|------|------|
| **接口路径** | `GET /api/v1/rfm/r-flow` |
| **HTTP Method** | GET |
| **Response Model** | `RFMRFlowResponse` |
| **设计原则** | 复用人群看板 `audience-summary` 的 3 年同比模式，一次请求返回完整表格数据 |

---

## 2. Request 设计

```python
class RFMRFlowRequest(BaseModel):
    """R区间流转看板请求参数"""
    year: int = Field(default=2026, description="对比基准年（仅影响列标签）")
    metric_type: str = Field(default="GSV", description="GMV 或 GSV")
    period: Optional[str] = Field(default=None, description="WTD / MTD / YTD / Q1-Q4")
    start_date: Optional[str] = Field(default=None, description="开始日期 YYYY-MM-DD")
    end_date: Optional[str] = Field(default=None, description="结束日期 YYYY-MM-DD")
    channel: Optional[str] = Field(default=None, description="渠道筛选（空=全店）")
```

**参数解析优先级**（与 `audience-summary` 完全一致）：
1. `period` 存在且无自定义日期 → 调用 `PeriodBuilder` 自动计算三周期
2. `start_date + end_date` 存在 → 自定义日期范围
3. 否则 → 默认当月 MTD

---

## 3. Response 设计

### 3.1 顶层结构

```python
class RFMRFlowResponse(BaseModel):
    year_label: str = "2026"
    comp_year_label: str = "2025"
    prev2_year_label: str = "2024"
    metric_type: str
    rows: List[RFMRFlowRow]
```

### 3.2 单行数据结构

```python
class RFMRFlowRow(BaseModel):
    # R 区间标识
    r_segment: str

    # ── 当前年 ──
    hist_users_current: int = 0
    repurchase_users_current: int = 0
    repurchase_rate_current: float = 0.0
    repurchase_gsv_current: float = 0.0
    repurchase_gsv_ratio_current: float = 0.0

    # ── 去年（同比基准）──
    hist_users_comp: int = 0
    repurchase_users_comp: int = 0
    repurchase_rate_comp: float = 0.0
    repurchase_gsv_comp: float = 0.0
    repurchase_gsv_ratio_comp: float = 0.0

    # ── 前年 ──
    hist_users_prev2: int = 0
    repurchase_users_prev2: int = 0
    repurchase_rate_prev2: float = 0.0
    repurchase_gsv_prev2: float = 0.0
    repurchase_gsv_ratio_prev2: float = 0.0

    # ── YOY（相对去年）──
    yoy_hist_users: Optional[float] = None
    yoy_repurchase_users: Optional[float] = None
    yoy_repurchase_rate: Optional[float] = None
    yoy_repurchase_gsv: Optional[float] = None
    yoy_repurchase_gsv_ratio: Optional[float] = None
```

### 3.3 `r_segment` 取值（固定顺序）

```python
R_SEGMENT_ORDER = [
    "近1个月已购客",
    "近2-3个月已购客",
    "近4-6月已购客",
    "近7-12个月已购客",
    "近两年已购客",
    "2年外已购客",
    "已购客TTL",
]
```

---

## 4. SQL 生成策略

### 4.1 单次周期查询逻辑

对于给定的 `(start_dt, end_dt, cutoff_dt, channel)`：

```sql
WITH
-- 1. 当期有效订单
base_orders AS (
    SELECT user_id, actual_amount, pay_time, channel
    FROM orders
    WHERE pay_time >= ?::TIMESTAMP
      AND pay_time <= ?::TIMESTAMP
      AND is_goujinjin = FALSE
      AND order_status != '交易关闭'
      AND is_refund = FALSE
      AND (? IS NULL OR channel = ?)
),
-- 2. 历史老客（cutoff 前至少购买过 1 次）+ 其最近一次购买距 cutoff 的天数
hist_customers AS (
    SELECT
        user_id,
        DATEDIFF('day', MAX(pay_time)::DATE, ?::DATE) AS recency_days
    FROM orders
    WHERE pay_time <= ?::TIMESTAMP
      AND is_goujinjin = FALSE
      AND order_status != '交易关闭'
      AND is_refund = FALSE
      AND (? IS NULL OR channel = ?)
    GROUP BY user_id
    HAVING COUNT(*) >= 1
),
-- 3. R 区间标记
r_segmented AS (
    SELECT
        user_id,
        recency_days,
        CASE
            WHEN recency_days BETWEEN 0 AND 30 THEN '近1个月已购客'
            WHEN recency_days BETWEEN 31 AND 90 THEN '近2-3个月已购客'
            WHEN recency_days BETWEEN 91 AND 180 THEN '近4-6月已购客'
            WHEN recency_days BETWEEN 181 AND 365 THEN '近7-12个月已购客'
            WHEN recency_days BETWEEN 366 AND 730 THEN '近两年已购客'
            WHEN recency_days > 730 THEN '2年外已购客'
        END AS r_segment
    FROM hist_customers
),
-- 4. 回购标记（当期有购买）
repurchase AS (
    SELECT DISTINCT user_id FROM base_orders
),
-- 5. 汇总（按区间）
segment_stats AS (
    SELECT
        r.r_segment,
        COUNT(DISTINCT r.user_id) AS hist_users,
        COUNT(DISTINCT CASE WHEN rp.user_id IS NOT NULL THEN r.user_id END) AS repurchase_users,
        SUM(CASE WHEN rp.user_id IS NOT NULL THEN bo.actual_amount ELSE 0 END) AS repurchase_gsv
    FROM r_segmented r
    LEFT JOIN repurchase rp ON r.user_id = rp.user_id
    LEFT JOIN base_orders bo ON r.user_id = bo.user_id
    GROUP BY r.r_segment
),
-- 6. TTL 汇总
ttl_stats AS (
    SELECT
        '已购客TTL' AS r_segment,
        SUM(hist_users) AS hist_users,
        SUM(repurchase_users) AS repurchase_users,
        SUM(repurchase_gsv) AS repurchase_gsv
    FROM segment_stats
)
SELECT * FROM segment_stats
UNION ALL
SELECT * FROM ttl_stats
ORDER BY
    CASE r_segment
        WHEN '近1个月已购客' THEN 1
        WHEN '近2-3个月已购客' THEN 2
        WHEN '近4-6月已购客' THEN 3
        WHEN '近7-12个月已购客' THEN 4
        WHEN '近两年已购客' THEN 5
        WHEN '2年外已购客' THEN 6
        WHEN '已购客TTL' THEN 7
    END;
```

### 4.2 3 年同比执行流程

后端 `calculate_rfm_r_flow()` 中：
1. 解析日期 → 得到 `current / comparison / prev2` 三周期的 `(start, end, cutoff)`
2. 分别执行 3 次上述 SQL
3. 按 `r_segment` 对齐，计算各指标 YOY
4. 组装 `RFMRFlowResponse`

---

## 5. 与现有 `audience-summary` 的差异对照

| 维度 | `audience-summary` | `rfm/r-flow` |
|------|-------------------|--------------|
| **分析对象** | 全部购买用户（新客+老客） | 仅老客（cutoff 前有购买记录） |
| **分组维度** | 渠道 / 30 指标 | R 区间（6 个休眠层级） |
| **核心指标** | GSV / 人数 / AUS / 占比 | 历史人群 / 回购人数 / 回购率 / 回购金额 |
| **可视化** | 日趋势折线图 | 回购率分组柱状图 |
| **页面位置** | 人群看板独立页 | RFM 分析页第 3 个 Tab |

---

## 6. 迁移与扩展建议

- **优先复用 `calculate_audience_summary` 的日期解析逻辑**，避免重复造轮子
- `r_segment` 的 CASE WHEN 建议写入 `backend/semantic/segments.py`，作为 `R_SEGMENT_SQL` 统一引用
- 若后续需要 F 区间流转、M 区间流转，只需复用同一 Response 结构，替换 `r_segment` 为 `f_segment`/`m_segment`
