# 老客健康分析仪表盘 - 设计文档

> 版本: v1.1（Review修复后）  
> 日期: 2026-04-18  
> 状态: ✅ 已确认，进入 Phase 1 编码  
> 变更记录: v1.0→v1.1 整合工程/设计Review修复方案（P1×5 + P2×5 + 用户决策6项）

---

## 1. 概述

### 1.1 目标

将现有RFM分析页面升级为**老客健康分析仪表盘**，从"数据报告"转向**"运营行动指引"**。核心解决用户痛点：**"看了不知道干什么"**。

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **行动导向** | 每个模块必须回答"So What"——数据变化意味着该做什么 |
| **分层设计** | 运营视图（每日）+ 深度分析（历史/复盘） |
| **数据驱动** | 所有分层、阈值必须基于数据分布，禁止拍脑袋 |
| **可导出** | 历史数据支持导出，用于预测和复盘 |

### 1.3 页面定位

- **路由**: `/customer-health`（替换现有 `/rfm`）
- **页面标题**: 老客健康分析
- **默认进入Tab**: 现状概览

---

## 2. 模块架构（5大模块）

```
┌─────────────────────────────────────────────────────────────┐
│  老客健康分析仪表盘                                          │
├─────────────────────────────────────────────────────────────┤
│  Tab 1: 现状概览 (运营日报)  ← Phase 1 先交付               │
│  Tab 2: 复购周期 (历史分析)  ← Phase 2                      │
│  Tab 3: 价值分层 (客户分层)  ← Phase 2                      │
│  Tab 4: 新客转化 (转化追踪)  ← Phase 2                      │
│  Tab 5: 大促日历 (大促 vs 日常) ← Phase 2                   │
└─────────────────────────────────────────────────────────────┘
```

**Tab顺序逻辑**: 按使用频率 + 决策链路排列
1. 现状概览 → 每天必看（最高频）
2. 复购周期 → 理解客户行为节奏
3. 价值分层 → 识别重点人群
4. 新客转化 → 追踪源头质量
5. 大促日历 → 阶段性复盘（最低频）

---

## 3. 模块详细设计

### 模块1：现状概览（运营日报）

**目标**: 每日晨会3分钟看完，知道今天该盯什么。

**页面层次**（从上到下）：
1. 全局筛选栏（日期范围、渠道排除）— 影响所有Tab
2. 告警横幅（如有异常，置顶显示）— 仅本Tab
3. 健康评分大卡片区（1大环形图 + 4小指标，非对称布局）
4. 核心指标趋势图（7日滑动窗口）

#### 3.1.1 指标卡片区

| 指标 | 口径 | 行动指引 |
|------|------|----------|
| 全店复购率 | 周期内有2+有效订单的人数 / 总购买人数 | <30%: 预警，检查触达 |
| 本品复购率 | 周期内同品类2+有效订单人数 / 该品类购买人数 | 与全店对比，差>10pp: 跨品引导 |
| 老客贡献占比 | 老客GSV / 全店GSV | <50%: 拉新过度，老客流失 |
| 老客人均价值(AUS) | 老客GSV / 老客人数 | 连续3天下降: 检查大促后疲软 |
| 近7日复购人数 | 滑动窗口 | 环比变化 |

#### 3.1.2 健康度评分（新增）

基于5个指标**归一化后**加权计算综合健康分（0-100）：

```python
# Step 1: 各指标 Min-Max 归一化到 0-1
#   - 复购率: 直接使用（本身就是0-1）
#   - 老客占比: 直接使用
#   - AUS趋势: (当期AUS / 基准AUS - 1) 映射到 0-1（负增长=0，增长>20%=1）
#   - 近7日复购人数: 与上周环比，映射到 0-1
#   - 本品复购率: 直接使用

# Step 2: 加权（均匀加权，V2支持配置）
health_score = (
    norm_all_store_repurchase_rate * 0.20 +
    norm_same_product_repurchase_rate * 0.20 +
    norm_old_customer_contribution * 0.20 +
    norm_old_customer_aus_trend * 0.20 +
    norm_recent_repurchase_momentum * 0.20
) * 100
```

- 80-100: 绿色 `#52c41a`（健康）
- 60-79: 黄色 `#faad14`（关注）
- <60: 红色 `#f5222d`（预警）

#### 3.1.3 异常告警区

自动识别以下异常（vs 去年同期或 vs 上周）：

| 告警类型 | 触发条件 | 建议行动 | 跳转Tab |
|----------|----------|----------|---------|
| 复购率暴跌 | 本品复购率 YOY < -10pp | 检查SKU缺货/竞品促销 | 复购周期 |
| 老客沉默 | 7天无复购人数占比 > 40% | 推送老客专属券 | 价值分层 |
| AUS下滑 | 老客AUS MOM < -15% | 检查是否低价渠道占比过高 | 现状概览 |
| 新客质量差 | 新客30天复购率 < 5% | 优化首购体验/入会引导 | 新客转化 |

**交互设计**: 告警卡片可点击，直接切换到对应Tab并高亮相关数据。

#### 3.1.4 交互状态表

| 功能 | Loading | Empty | Error | Success |
|------|---------|-------|-------|---------|
| 健康评分加载 | 骨架屏（环形+4卡片） | "暂无足够数据，请扩大分析周期" | "计算失败，点击重试" | 显示评分+颜色+指标 |
| 告警区 | — | "暂无异常，运营良好 👍" | — | 告警卡片列表（可跳转） |
| 趋势图 | 转圈 | "该周期无数据" | 报错+重试 | 折线图 |

#### 3.1.5 API 契约

```python
class HealthOverviewMetrics(BaseModel):
    """现状概览指标"""
    analysis_date: str                    # 分析日期
    period_days: int = 30                 # 分析周期（默认30天）
    
    # 核心指标（当期）
    all_store_repurchase_rate: float      # 全店复购率
    same_product_repurchase_rate: float   # 本品复购率
    old_customer_gsv_ratio: float         # 老客GSV占比
    old_customer_aus: float               # 老客人均消费
    recent_7d_repurchase_users: int       # 近7日复购人数
    
    # 健康评分（归一化后加权）
    health_score: float                   # 0-100
    health_level: str                     # "healthy" | "warning" | "critical"
    
    # 同比（vs去年同期同周期）
    yoy_all_store_repurchase_rate: Optional[float]
    yoy_same_product_repurchase_rate: Optional[float]
    yoy_old_customer_gsv_ratio: Optional[float]
    yoy_old_customer_aus: Optional[float]
    
    # 告警列表
    alerts: List[HealthAlertItem]


class HealthAlertItem(BaseModel):
    """健康度告警项"""
    alert_type: str                       # 告警类型编码
    alert_name: str                       # 告警名称
    severity: str                         # "high" | "medium" | "low"
    current_value: float
    threshold_value: float
    comparison_basis: str                 # "yoy" | "mom" | "absolute"
    suggested_action: str                 # 建议行动
    target_tab: str                       # 跳转目标Tab名
```

#### 3.1.6 SQL 逻辑（DuckDB兼容语法）

```sql
-- 全店复购率计算（使用 FilterBuilder，禁止硬编码渠道名）
-- Python构造: fb = FilterBuilder(); fb.with_valid_order(); fb.with_time_range(start, end); fb.with_exclude_channels(exclude)
-- fb.build() 返回 WHERE子句 + 参数列表

WITH valid_orders AS (
    SELECT *
    FROM orders
    WHERE {where_clause}  -- 由FilterBuilder生成
),
user_order_count AS (
    SELECT 
        user_id,
        COUNT(DISTINCT order_id) as order_count
    FROM valid_orders
    GROUP BY user_id
),
total_buyers AS (
    SELECT COUNT(DISTINCT user_id) as total
    FROM valid_orders
)
SELECT 
    COUNT(CASE WHEN order_count >= 2 THEN 1 END) * 1.0 / NULLIF(total, 0) as repurchase_rate
FROM user_order_count
CROSS JOIN total_buyers;

-- 本品复购率（按 spu_product_class）
WITH valid_orders AS (
    SELECT user_id, spu_product_class, order_id
    FROM orders
    WHERE {where_clause}  -- 由FilterBuilder生成
      AND spu_product_class IS NOT NULL
),
product_user_count AS (
    SELECT 
        spu_product_class,
        user_id,
        COUNT(DISTINCT order_id) as order_count
    FROM valid_orders
    GROUP BY spu_product_class, user_id
)
SELECT 
    spu_product_class,
    COUNT(CASE WHEN order_count >= 2 THEN 1 END) * 1.0 / 
        COUNT(DISTINCT user_id) as product_repurchase_rate
FROM product_user_count
GROUP BY spu_product_class;
```

---

### 模块2：复购周期分析（Phase 2）

**目标**: 理解客户多久买一次，指导触达节奏。

**默认周期**: 30天（后续支持自定义）

#### 3.2.1 核心图表

**图表1：复购间隔分布（直方图）**
- X轴：两次购买间隔天数（桶：0-7, 8-14, 15-30, 31-60, 61-90, 91-180, 181-365, 365+）
- Y轴：人数占比
- 分线：全店 / 本品 / 分品类

**图表2：品类复购周期对比（箱线图/柱状图）**
- 各品类 median / P25 / P75 复购间隔

**图表3： cohort 留存（月度）**
- 首购月份为行，后续月份为列
- 单元格：该 cohort 在对应月份的复购率

#### 3.2.2 数据表

| 品类 | 购买人数 | 复购人数 | 复购率 | 中位复购天数 | P25 | P75 |
|------|----------|----------|--------|-------------|-----|-----|
| 白膜 | 12,345 | 4,567 | 37.0% | 45 | 21 | 89 |
| 经典膜 | 8,901 | 2,345 | 26.3% | 62 | 28 | 120 |
| ... | | | | | | |

#### 3.2.3 API 契约

```python
class RepurchaseCycleOverview(BaseModel):
    """复购周期概览"""
    period_start: str
    period_end: str
    
    # 全店分布
    all_store_median_days: int            # 中位复购天数
    all_store_p25_days: int
    all_store_p75_days: int
    
    # 分桶分布
    bucket_distribution: List[RepurchaseBucket]
    
    # 分品类
    by_product_class: List[ProductClassRepurchase]


class RepurchaseBucket(BaseModel):
    """复购间隔桶"""
    bucket_label: str                     # "0-7天", "8-14天"...
    bucket_start: int
    bucket_end: Optional[int]
    user_count: int
    user_ratio: float                     # 占复购人群比例


class ProductClassRepurchase(BaseModel):
    """品类复购指标"""
    product_class: str
    total_buyers: int
    repurchase_users: int
    repurchase_rate: float
    median_days: int
    p25_days: int
    p75_days: int
    avg_order_value: float                # 复购客单价
    gsv: float


class CohortRetentionResponse(BaseModel):
    """Cohort留存矩阵"""
    cohort_months: List[str]              # 首购月份列表
    periods: List[str]                    # 周期标签 (M0, M1, M2...)
    matrix: List[List[Optional[float]]]   # 复购率矩阵（None表示无数据）
    avg_by_period: List[Optional[float]]  # 各周期平均复购率
```

#### 3.2.4 SQL 逻辑（DuckDB兼容）

```sql
-- 复购间隔分布（全店）
-- DuckDB: 使用 DATEDIFF('day', prev_pay_time, pay_time) 替代 EXTRACT(DAY FROM interval)
WITH valid_orders AS (
    SELECT user_id, pay_time, order_id
    FROM orders
    WHERE {where_clause}  -- FilterBuilder生成
),
user_order_sequence AS (
    SELECT 
        user_id,
        pay_time,
        LAG(pay_time) OVER (PARTITION BY user_id ORDER BY pay_time) as prev_pay_time
    FROM valid_orders
),
repurchase_gaps AS (
    SELECT 
        user_id,
        DATEDIFF('day', prev_pay_time, pay_time) as gap_days
    FROM user_order_sequence
    WHERE prev_pay_time IS NOT NULL
)
SELECT 
    CASE 
        WHEN gap_days <= 7 THEN '0-7天'
        WHEN gap_days <= 14 THEN '8-14天'
        WHEN gap_days <= 30 THEN '15-30天'
        WHEN gap_days <= 60 THEN '31-60天'
        WHEN gap_days <= 90 THEN '61-90天'
        WHEN gap_days <= 180 THEN '91-180天'
        WHEN gap_days <= 365 THEN '181-365天'
        ELSE '365天以上'
    END as bucket,
    COUNT(*) as user_count,
    COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () as ratio
FROM repurchase_gaps
GROUP BY bucket
ORDER BY MIN(gap_days);

-- Cohort 留存（添加 pay_time 过滤减少扫描）
WITH valid_orders AS (
    SELECT user_id, pay_time, DATE_TRUNC('month', pay_time) as order_month
    FROM orders
    WHERE {where_clause}  -- FilterBuilder生成
      AND pay_time >= ?   -- 添加时间下限，减少扫描（start_month 前推1年）
),
first_purchase AS (
    SELECT user_id, MIN(order_month) as cohort_month
    FROM valid_orders
    GROUP BY user_id
),
user_monthly AS (
    SELECT DISTINCT user_id, order_month
    FROM valid_orders
)
SELECT 
    fp.cohort_month,
    um.order_month,
    COUNT(DISTINCT um.user_id) * 1.0 / COUNT(DISTINCT fp.user_id) as retention_rate
FROM first_purchase fp
LEFT JOIN user_monthly um ON fp.user_id = um.user_id 
    AND um.order_month >= fp.cohort_month
GROUP BY fp.cohort_month, um.order_month
ORDER BY fp.cohort_month, um.order_month;
```

---

### 模块3：客户价值分层（Phase 2）

**目标**: 用数据驱动替代11象限，产出可直接指导运营的分层。

#### 3.3.1 分层逻辑（基于历史数据分布）

**Step 1**: 计算全店用户 R/F/M 分布，用百分位确定阈值：

```
价值分层（基于GSV）:
- S级 (Top 5%): 累计贡献 ~30% GSV → 专属客服 + 新品优先体验
- A级 (Top 20%): 累计贡献 ~60% GSV → 会员日专属 + 生日礼
- B级 (Top 50%): 累计贡献 ~85% GSV → 常规积分 + 满赠
- C级 (Bottom 50%): 长尾 → 低成本触达 / 放任

频次分层（基于订单数）:
- 高频 (>=4单/年): 忠诚用户 → 订阅制 / 年度礼盒
- 中频 (2-3单/年): 潜力用户 → 复购券引导
- 低频 (1单/年): 边缘用户 → 大促激活

结合 = 4×3 = 12个细分群，运营合并为6个 actionable 群：
```

#### 3.3.2 运营分层表

| 分层 | 定义 | 人数 | GSV占比 | 行动策略 |
|------|------|------|---------|----------|
| 超级用户 | S级+高频 | ~3% | ~25% | 1v1专属，新品内测 |
| 忠实买家 | A级+高频 | ~8% | ~25% | 会员日优先，积分翻倍 |
| 潜力金主 | S/A级+中频 | ~15% | ~25% | 复购券，跨品推荐 |
| 价格敏感 | B/C级+高频 | ~10% | ~10% | 满减活动，拼团 |
| 沉睡价值 | S/A级+低频 | ~20% | ~10% | 大促召回，短信触达 |
| 边缘用户 | B/C级+低频 | ~44% | ~5% | 低成本维护 |

#### 3.3.3 API 契约

```python
class ValueTierDefinition(BaseModel):
    """价值分层定义（动态计算）"""
    tier_code: str                        # "S", "A", "B", "C"
    tier_name: str                        # "超级价值", "高价值"...
    gsv_threshold_min: Optional[float]    # GSV下限
    gsv_threshold_max: Optional[float]    # GSV上限
    user_count: int
    gsv: float
    gsv_ratio: float                      # 占全店GSV比例


class FrequencyTierDefinition(BaseModel):
    """频次分层定义"""
    tier_code: str                        # "high", "medium", "low"
    tier_name: str                        # "高频", "中频", "低频"
    order_threshold_min: int
    order_threshold_max: Optional[int]
    user_count: int


class CustomerSegmentItem(BaseModel):
    """运营分层项（价值×频次交叉）"""
    segment_code: str                     # "S-high", "A-medium"...
    segment_name: str                     # "超级用户", "忠实买家"...
    value_tier: str
    frequency_tier: str
    user_count: int
    gsv: float
    gsv_ratio: float
    avg_order_value: float
    avg_orders_per_user: float
    suggested_action: str                 # 建议运营动作
    priority: int                         # 运营优先级 1-6


class ValueTierResponse(BaseModel):
    """价值分层响应"""
    analysis_date: str
    lookback_days: int                    # 回溯天数（默认365）
    
    # 分层阈值（基于数据分布动态计算）
    value_tiers: List[ValueTierDefinition]
    frequency_tiers: List[FrequencyTierDefinition]
    
    # 交叉分层
    segments: List[CustomerSegmentItem]
    
    # 关键洞察
    insights: List[str]                   # 自动生成的洞察文本
```

#### 3.3.4 SQL 逻辑（DuckDB兼容）

```sql
-- 用户价值/频次计算（基于回溯期）
-- DuckDB日期计算: 使用参数化日期，不在SQL中写 DATE_SUB
WITH valid_orders AS (
    SELECT user_id, actual_amount, order_id
    FROM orders
    WHERE {where_clause}  -- FilterBuilder生成（含时间范围）
),
user_stats AS (
    SELECT 
        user_id,
        SUM(actual_amount) as gsv,
        COUNT(DISTINCT order_id) as order_count
    FROM valid_orders
    GROUP BY user_id
),
-- 使用 NTILE 计算百分位（DuckDB支持）
ranked_users AS (
    SELECT 
        user_id,
        gsv,
        order_count,
        NTILE(20) OVER (ORDER BY gsv) as gsv_tile,      -- 20分位
        NTILE(20) OVER (ORDER BY order_count) as freq_tile
    FROM user_stats
)
SELECT 
    user_id,
    gsv,
    order_count,
    CASE 
        WHEN gsv_tile >= 20 THEN 'S'
        WHEN gsv_tile >= 16 THEN 'A'
        WHEN gsv_tile >= 10 THEN 'B'
        ELSE 'C'
    END as value_tier,
    CASE 
        WHEN order_count >= 4 THEN 'high'
        WHEN order_count >= 2 THEN 'medium'
        ELSE 'low'
    END as freq_tier
FROM ranked_users;
```

---

### 模块4：新客转化追踪（Phase 2）

**目标**: 追踪新客从首购到复购的转化漏斗，识别卡点。

#### 3.4.1 转化漏斗

```
新客转化漏斗:
1. 首购用户 ──→ 2. 7天内复购 ──→ 3. 30天内复购 ──→ 4. 90天内复购 ──→ 5. 年度忠诚
   100%             X%               Y%                Z%               W%
```

#### 3.4.2 核心指标

| 指标 | 口径 | 目标 |
|------|------|------|
| 7日复购率 | 首购后7天内再次购买 / 首购人数 | >15% |
| 30日复购率 | 首购后30天内再次购买 / 首购人数 | >25% |
| 90日复购率 | 首购后90天内再次购买 / 首购人数 | >35% |
| 首购到复购中位天数 | 复购间隔中位数 | <30天 |
| 首购客单价 | 首购订单平均金额 | >¥150 |

#### 3.4.3 分渠道新客质量

| 渠道 | 首购人数 | 30日复购率 | 90日复购率 | 首购AUS | 质量评级 |
|------|----------|-----------|-----------|---------|----------|
| 货架 | ... | ... | ... | ... | A/B/C |
| 直播 | ... | ... | ... | ... | |
| 淘客 | ... | ... | ... | ... | |

#### 3.4.4 API 契约

```python
class NewCustomerConversionFunnel(BaseModel):
    """新客转化漏斗"""
    cohort_date: str                      # 首购月份
    total_first_purchase: int             # 首购人数
    
    # 各阶段转化
    day7_repurchase: int
    day7_rate: float
    day30_repurchase: int
    day30_rate: float
    day90_repurchase: int
    day90_rate: float
    year_repurchase: int
    year_rate: float
    
    # 流失（未在对应周期复购）
    day7_churn: int
    day30_churn: int
    day90_churn: int


class NewCustomerChannelQuality(BaseModel):
    """分渠道新客质量"""
    channel: str
    first_purchase_users: int
    first_purchase_aus: float             # 首购客单价
    day30_repurchase_rate: float
    day90_repurchase_rate: float
    avg_days_to_repurchase: Optional[float]
    quality_score: float                  # 综合质量分 0-100
    quality_grade: str                    # "A" | "B" | "C" | "D"


class NewCustomerConversionResponse(BaseModel):
    """新客转化追踪响应"""
    analysis_date: str
    
    # 总体漏斗（最近12个月cohort平均）
    overall_funnel: NewCustomerConversionFunnel
    
    # 分cohort历史
    cohort_funnels: List[NewCustomerConversionFunnel]
    
    # 分渠道质量
    channel_quality: List[NewCustomerChannelQuality]
    
    # 趋势（最近12个月）
    monthly_trend: List[Dict[str, Any]]   # 每月的7/30/90日复购率
```

#### 3.4.5 SQL 逻辑（DuckDB兼容）

```sql
-- 新客转化漏斗（按首购月份cohort）
-- DuckDB: 使用 INTERVAL '7 days' 语法，不使用 MySQL DATE_ADD
WITH valid_orders AS (
    SELECT user_id, pay_time, actual_amount, channel
    FROM orders
    WHERE {where_clause}  -- FilterBuilder生成
),
first_purchase AS (
    SELECT 
        user_id,
        MIN(pay_time) as first_pay_time,
        DATE_TRUNC('month', MIN(pay_time)) as cohort_month
    FROM valid_orders
    GROUP BY user_id
),
cohort_users AS (
    SELECT user_id, first_pay_time, cohort_month
    FROM first_purchase
    WHERE cohort_month = ?
),
repurchase_stats AS (
    SELECT 
        cu.user_id,
        cu.first_pay_time,
        MIN(CASE WHEN vo.pay_time > cu.first_pay_time 
                 AND vo.pay_time <= cu.first_pay_time + INTERVAL '7 days' 
            THEN vo.pay_time END) as repurchase_day7,
        MIN(CASE WHEN vo.pay_time > cu.first_pay_time 
                 AND vo.pay_time <= cu.first_pay_time + INTERVAL '30 days' 
            THEN vo.pay_time END) as repurchase_day30,
        MIN(CASE WHEN vo.pay_time > cu.first_pay_time 
                 AND vo.pay_time <= cu.first_pay_time + INTERVAL '90 days' 
            THEN vo.pay_time END) as repurchase_day90
    FROM cohort_users cu
    LEFT JOIN valid_orders vo ON cu.user_id = vo.user_id AND vo.pay_time > cu.first_pay_time
    GROUP BY cu.user_id, cu.first_pay_time
)
SELECT 
    COUNT(*) as total_first_purchase,
    COUNT(repurchase_day7) as day7_repurchase,
    COUNT(repurchase_day30) as day30_repurchase,
    COUNT(repurchase_day90) as day90_repurchase
FROM repurchase_stats;
```

---

### 模块5：大促 vs 日常对比（Phase 2）

**目标**: 理解大促对老客行为的影响，优化促销节奏。

#### 3.5.1 大促日历标记

基于 CSV `芙清全年平台活动节奏 - Sheet2.csv` 映射。启动时预加载到内存：

```python
# backend/config.py 追加
PROMOTION_CSV_PATH = PROJECT_ROOT / "data" / "promotions" / "promotion_calendar.csv"
# 或从现有CSV路径加载: 
# PROMOTION_CSV_PATH = Path(r"/Users/hutou/Desktop/fuqin-date/芙清CRM数据库/芙清crm原始数据库/芙清全年平台活动节奏 - Sheet2.csv")
```

```python
# 加载函数（模块级缓存）
from functools import lru_cache

@lru_cache(maxsize=1)
def load_promotion_periods() -> List[Dict[str, Any]]:
    """加载大促日历（启动时预加载，内存缓存）"""
    csv_path = config.PROMOTION_CSV_PATH
    periods = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_range = row['正式时间']
            start_str, end_str = date_range.split('-')
            start_date = _parse_chinese_date(start_str.strip())
            end_date = _parse_chinese_date(end_str.strip())
            periods.append({
                'year': int(row['year']),
                'name': row['活动名称'],
                'start_date': start_date,
                'end_date': end_date,
            })
    return periods
```

#### 3.5.2 对比维度

| 维度 | 大促期间 | 日常期间 | 差异 |
|------|----------|----------|------|
| 老客复购率 | X% | Y% | +Zpp |
| 老客AUS | ¥X | ¥Y | +Z% |
| 购买频次 | X次/月 | Y次/月 | |
| 品类集中度 | X% | Y% | |
| 渠道分布 | ... | ... | |

#### 3.5.3 大促依赖度

```
大促依赖度 = 大促期间老客GSV / 年度老客GSV

- >60%: 重度依赖，日常运营薄弱
- 40-60%: 中度依赖
- <40%: 健康，日常复购良好
```

#### 3.5.4 API 契约

```python
class PromotionPeriod(BaseModel):
    """大促周期定义"""
    name: str                             # "38节日", "618节日", "双11"
    start_date: str
    end_date: str
    year: int


class PromotionVsDailyMetrics(BaseModel):
    """单个大促 vs 日常对比"""
    promotion: PromotionPeriod
    
    # 大促期间
    promo_old_customer_count: int
    promo_old_customer_gsv: float
    promo_old_customer_aus: float
    promo_repurchase_rate: float
    
    # 日常期间（大促前30天或全年日常平均）
    daily_old_customer_count: int
    daily_old_customer_gsv: float
    daily_old_customer_aus: float
    daily_repurchase_rate: float
    
    # 差异
    gsv_lift: Optional[float]             # GSV提升率
    aus_lift: Optional[float]             # AUS提升率
    repurchase_lift: Optional[float]      # 复购率提升（pp）


class PromotionCalendarResponse(BaseModel):
    """大促日历响应"""
    analysis_year: int
    
    # 年度大促列表
    promotions: List[PromotionVsDailyMetrics]
    
    # 年度汇总
    annual_promo_gsv_ratio: float         # 大促GSV占全年比例
    annual_promo_user_ratio: float        # 大促购买人数占全年比例
    promo_dependency_score: float         # 大促依赖度 0-1
    dependency_level: str                 # "high" | "medium" | "low"
    
    # 趋势（多年对比）
    yearly_trend: List[Dict[str, Any]]
```

#### 3.5.5 SQL 逻辑

```sql
-- 大促 vs 日常（以单个活动为例）
WITH valid_orders AS (
    SELECT user_id, pay_time, actual_amount, spu_product_class
    FROM orders
    WHERE {where_clause}  -- FilterBuilder生成
),
-- 标记大促期间（由Python根据加载的promotion_periods标记）
promo_orders AS (
    SELECT *,
        CASE 
            WHEN pay_time BETWEEN ? AND ? THEN 'promo'
            ELSE 'daily'
        END as period_type
    FROM valid_orders
    WHERE pay_time BETWEEN ? AND ?  -- 年度范围
),
-- 识别老客（活动前已有购买记录）
old_customers AS (
    SELECT DISTINCT user_id
    FROM valid_orders
    WHERE pay_time < ?  -- 活动开始日期
),
metrics AS (
    SELECT 
        period_type,
        COUNT(DISTINCT CASE WHEN oc.user_id IS NOT NULL THEN vo.user_id END) as old_customer_count,
        SUM(CASE WHEN oc.user_id IS NOT NULL THEN vo.actual_amount ELSE 0 END) as old_customer_gsv,
        COUNT(DISTINCT vo.user_id) as total_users
    FROM promo_orders vo
    LEFT JOIN old_customers oc ON vo.user_id = oc.user_id
    GROUP BY period_type
)
SELECT * FROM metrics;
```

---

## 4. 视觉规范

### 4.1 设计系统对齐

| 项 | 规范 |
|----|------|
| UI框架 | Naive UI（与现有项目一致） |
| 图表库 | ECharts 5（与现有项目一致） |
| 布局 | Naive UI `n-grid` + `n-card` |
| 字体 | 系统默认 |
| 图标 | 与现有项目一致 |

### 4.2 颜色语义

| 语义 | 颜色值 | 用途 |
|------|--------|------|
| 健康/成功 | `#52c41a` | 健康评分>=80，正向趋势 |
| 预警/关注 | `#faad14` | 健康评分60-79，需关注 |
| 危险/告警 | `#f5222d` | 健康评分<60，严重告警 |
| 信息 | `#1890ff` | 中性提示，链接 |
| 主色 | 与现有Stripe Design System一致 | 标题、强调 |

### 4.3 布局规范

- **健康评分区**: 非对称布局——1大（环形图居中，占60%宽度）+ 4小（指标环绕，占40%宽度）
- **告警横幅**: 置顶，单列全宽，可折叠
- **Tab切换**: 桌面端横向Tabs，移动端转为下拉选择或横向滚动
- **图表**: ECharts 需监听 window resize
- **无障碍**: 图表添加 `aria-label` 描述

---

## 5. 前端组件结构

### 5.1 页面布局

```vue
<!-- CustomerHealthView.vue -->
<template>
  <div class="customer-health-dashboard">
    <!-- 顶部筛选栏（复用现有） -->
    <AppFilterBar />
    
    <!-- Tab 切换 -->
    <n-tabs v-model:value="activeTab" @update:value="onTabChange">
      <n-tab-pane name="overview" tab="现状概览">
        <HealthOverviewTab />
      </n-tab-pane>
      <n-tab-pane name="repurchase" tab="复购周期">
        <RepurchaseCycleTab />
      </n-tab-pane>
      <n-tab-pane name="tiers" tab="价值分层">
        <ValueTierTab />
      </n-tab-pane>
      <n-tab-pane name="conversion" tab="新客转化">
        <NewCustomerConversionTab />
      </n-tab-pane>
      <n-tab-pane name="promotion" tab="大促日历">
        <PromotionCalendarTab />
      </n-tab-pane>
    </n-tabs>
  </div>
</template>
```

### 5.2 组件清单（Phase 1 + Phase 2）

| 组件名 | 路径 | 说明 | 阶段 |
|--------|------|------|------|
| `CustomerHealthView.vue` | `views/CustomerHealthView.vue` | 主页面容器（含Tab切换） | P1 |
| `HealthOverviewTab.vue` | `views/health/HealthOverviewTab.vue` | 现状概览（含告警横幅+健康评分+趋势） | P1 |
| `HealthScoreCard.vue` | `components/health/HealthScoreCard.vue` | 健康度评分大环形图（核心视觉焦点） | P1 |
| `MetricCards.vue` | `components/health/MetricCards.vue` | 4个小指标卡片（环绕健康评分） | P1 |
| `AlertBanner.vue` | *(已合并至 HealthOverviewTab)* | 告警横幅（内联，不单独组件） | P1 |
| `RepurchaseCycleTab.vue` | `views/health/RepurchaseCycleTab.vue` | 复购周期 | P2 |
| `GapDistributionChart.vue` | `components/health/GapDistributionChart.vue` | 复购间隔分布直方图 | P2 |
| `CohortHeatmap.vue` | `components/health/CohortHeatmap.vue` | Cohort留存热力图 | P2 |
| `ValueTierTab.vue` | `views/health/ValueTierTab.vue` | 价值分层 | P2 |
| `SegmentTable.vue` | `components/health/SegmentTable.vue` | 分层表格（带行动建议） | P2 |
| `NewCustomerConversionTab.vue` | `views/health/NewCustomerConversionTab.vue` | 新客转化 | P2 |
| `ConversionFunnel.vue` | `components/health/ConversionFunnel.vue` | 转化漏斗图 | P2 |
| `ChannelQualityTable.vue` | `components/health/ChannelQualityTable.vue` | 渠道质量表 | P2 |
| `PromotionCalendarTab.vue` | `views/health/PromotionCalendarTab.vue` | 大促日历 | P2 |
| `PromoVsDailyChart.vue` | `components/health/PromoVsDailyChart.vue` | 大促日常对比图 | P2 |

**组件合并说明**: AlertBanner 合并到 HealthOverviewTab 内联实现（避免过度原子化）；HealthScoreCard 保持独立（作为核心视觉组件）。

### 5.3 状态管理

```typescript
// stores/healthDashboard.ts
export const useHealthDashboardStore = defineStore('healthDashboard', () => {
  // 共享筛选状态（与现有filterStore联动）
  const periodDays = ref(30)
  const analysisDate = ref(new Date().toISOString().split('T')[0])
  
  // 各模块数据缓存
  const overviewData = ref<HealthOverviewMetrics | null>(null)
  const repurchaseData = ref<RepurchaseCycleOverview | null>(null)
  const tierData = ref<ValueTierResponse | null>(null)
  const conversionData = ref<NewCustomerConversionResponse | null>(null)
  const promotionData = ref<PromotionCalendarResponse | null>(null)
  
  // 加载状态
  const loading = ref<Record<string, boolean>>({})
  
  // Tab懒加载标记（首次切换时才请求）
  const tabLoaded = ref<Record<string, boolean>>({
    overview: false,
    repurchase: false,
    tiers: false,
    conversion: false,
    promotion: false,
  })
  
  // Actions
  async function fetchOverview() { ... }
  async function fetchRepurchase() { ... }
  async function fetchTiers() { ... }
  async function fetchConversion() { ... }
  async function fetchPromotion() { ... }
  
  return {
    periodDays, analysisDate,
    overviewData, repurchaseData, tierData, conversionData, promotionData,
    loading, tabLoaded,
    fetchOverview, fetchRepurchase, fetchTiers, fetchConversion, fetchPromotion
  }
})
```

---

## 6. 后端服务架构

### 6.1 新增文件

```
backend/
├── routers/
│   └── health.py                  # APIRouter: /api/v1/health/* 路由
├── services/
│   └── health/
│       ├── __init__.py            # 统一导出
│       ├── overview.py            # 模块1: 现状概览
│       ├── repurchase.py          # 模块2: 复购周期
│       ├── tiers.py               # 模块3: 价值分层
│       ├── conversion.py          # 模块4: 新客转化
│       └── promotion.py           # 模块5: 大促日历
├── contracts/
│   └── schemas.py                 # 追加 Health* 模型（见第3节）
└── main.py                        # include_router(health_router)
```

### 6.2 渠道排除常量（统一从 filters.py 导入）

```python
# backend/services/health/__init__.py
from backend.semantic.filters import OrderFilters, FilterBuilder

# 默认排除渠道（与 filters.py 一致，禁止重新定义）
# 需要排除时: OrderFilters.channel_not_in(["U先派样", "百补派样", "赠品&0.01", "其他"])
# 或: fb = FilterBuilder(); fb.with_exclude_channels([...])
```

### 6.3 API 路由（使用 APIRouter 拆分）

```python
# backend/routers/health.py
from fastapi import APIRouter, Query
from typing import Optional, List
from backend.contracts.schemas import (
    HealthOverviewMetrics, RepurchaseCycleOverview, CohortRetentionResponse,
    ValueTierResponse, NewCustomerConversionResponse, PromotionCalendarResponse
)
from backend.services.health import overview, repurchase, tiers, conversion, promotion

router = APIRouter(prefix="/api/v1/health", tags=["health"])

@router.get("/overview", response_model=HealthOverviewMetrics)
def get_health_overview(
    analysis_date: str = Query(..., description="分析日期 YYYY-MM-DD"),
    period_days: int = Query(default=30, description="分析周期天数"),
    exclude_channels: Optional[List[str]] = Query(default=None, description="排除渠道"),
):
    """现状概览（运营日报）"""
    return overview.get_overview(analysis_date, period_days, exclude_channels)

@router.get("/repurchase-cycle", response_model=RepurchaseCycleOverview)
def get_repurchase_cycle(
    start_date: str = Query(..., description="开始日期"),
    end_date: str = Query(..., description="结束日期"),
    exclude_channels: Optional[List[str]] = Query(default=None),
):
    """复购周期分析"""
    return repurchase.get_repurchase_cycle(start_date, end_date, exclude_channels)

@router.get("/cohort-retention", response_model=CohortRetentionResponse)
def get_cohort_retention(
    start_month: str = Query(..., description="开始月份 YYYY-MM"),
    end_month: str = Query(..., description="结束月份 YYYY-MM"),
    exclude_channels: Optional[List[str]] = Query(default=None),
):
    """Cohort留存矩阵"""
    return repurchase.get_cohort_retention(start_month, end_month, exclude_channels)

@router.get("/value-tiers", response_model=ValueTierResponse)
def get_value_tiers(
    analysis_date: str = Query(..., description="分析日期"),
    lookback_days: int = Query(default=365, description="回溯天数"),
    exclude_channels: Optional[List[str]] = Query(default=None),
):
    """客户价值分层"""
    return tiers.get_value_tiers(analysis_date, lookback_days, exclude_channels)

@router.get("/new-customer-conversion", response_model=NewCustomerConversionResponse)
def get_new_customer_conversion(
    analysis_date: str = Query(..., description="分析日期"),
    lookback_months: int = Query(default=12, description="回溯月数"),
    exclude_channels: Optional[List[str]] = Query(default=None),
):
    """新客转化追踪"""
    return conversion.get_new_customer_conversion(analysis_date, lookback_months, exclude_channels)

@router.get("/promotion-calendar", response_model=PromotionCalendarResponse)
def get_promotion_calendar(
    year: int = Query(default=2025, description="分析年份"),
    exclude_channels: Optional[List[str]] = Query(default=None),
):
    """大促日历对比"""
    return promotion.get_promotion_calendar(year, exclude_channels)
```

```python
# backend/main.py 追加
from backend.routers import health
app.include_router(health.router)
```

### 6.4 服务函数签名（按模块拆分）

```python
# backend/services/health/overview.py
from backend.semantic.calculations import yoy_absolute, yoy_ratio, safe_ratio
from backend.semantic.filters import FilterBuilder, OrderFilters, MetricType
from backend.config import DUCKDB_PATH
import duckdb

def get_connection():
    return duckdb.connect(str(DUCKDB_PATH))

def _build_filter(exclude_channels, start_date, end_date):
    """构建统一过滤条件"""
    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    fb.with_time_range(start_date, end_date)
    if exclude_channels:
        fb.with_exclude_channels(exclude_channels)
    return fb.build()

def get_overview(analysis_date: str, period_days: int = 30, exclude_channels=None):
    """模块1：现状概览"""
    ...

# backend/services/health/repurchase.py
def get_repurchase_cycle(start_date, end_date, exclude_channels=None): ...
def get_cohort_retention(start_month, end_month, exclude_channels=None): ...

# backend/services/health/tiers.py
def get_value_tiers(analysis_date, lookback_days=365, exclude_channels=None): ...

# backend/services/health/conversion.py
def get_new_customer_conversion(analysis_date, lookback_months=12, exclude_channels=None): ...

# backend/services/health/promotion.py
def get_promotion_calendar(year=2025, exclude_channels=None): ...
```

---

## 7. Schema 变更清单

### 7.1 追加到 `backend/contracts/schemas.py`

**Phase 1 追加（2个模型）**:
1. `HealthOverviewMetrics`
2. `HealthAlertItem`

**Phase 2 追加（14个模型）**:
3. `RepurchaseCycleOverview`
4. `RepurchaseBucket`
5. `ProductClassRepurchase`
6. `CohortRetentionResponse`
7. `ValueTierDefinition`
8. `FrequencyTierDefinition`
9. `CustomerSegmentItem`
10. `ValueTierResponse`
11. `NewCustomerConversionFunnel`
12. `NewCustomerChannelQuality`
13. `NewCustomerConversionResponse`
14. `PromotionPeriod`
15. `PromotionVsDailyMetrics`
16. `PromotionCalendarResponse`

### 7.2 类型生成

```bash
cd frontend-vue3
npm run gen-types
```

---

## 8. 数据依赖与性能考量

### 8.1 数据依赖

| 数据 | 来源表 | 备注 |
|------|--------|------|
| 订单数据 | `orders` | 主数据源 |
| 首购日期 | `user_first_purchase` | 新老客判定 |
| 大促日历 | CSV文件 | 启动时加载到内存（`@lru_cache`） |
| RFM数据 | `user_rfm` | 价值分层可复用 |

### 8.2 性能优化

| 策略 | 适用场景 |
|------|----------|
| 物化视图 | `user_first_purchase` 已存在，复购计算可预聚合 |
| 缓存 | 大促日历（年维度）`@lru_cache` 缓存 |
| 异步加载 | 5个Tab独立加载，首次切换时才请求（懒加载） |
| 时间过滤 | Cohort查询添加 `pay_time >= start_month` 减少扫描 |

### 8.3 预估查询耗时

| 查询 | 数据量 | 预估耗时 | 优化后 |
|------|--------|----------|--------|
| 现状概览 | 886万订单 | <500ms | 预聚合表可<100ms |
| 复购周期 | 886万订单 | <2s | 限制分析周期可<1s |
| 价值分层 | 84万用户 | <1s | NTILE计算较快 |
| 新客转化 | 按cohort | <1s/cohort | 并行加载 |
| 大促日历 | 年度数据 | <500ms | 缓存 |

---

## 9. 开发排期（分批交付）

### Phase 1（核心日报，预计 ~10h）

| 步骤 | 内容 | 预估工时 |
|------|------|----------|
| 1 | Schema: `HealthOverviewMetrics` + `HealthAlertItem` | 1h |
| 2 | Service: `services/health/overview.py` + SQL | 3h |
| 3 | Router: `routers/health.py` + main.py include | 1h |
| 4 | 前端: `CustomerHealthView.vue` + `HealthOverviewTab.vue` | 3h |
| 5 | 联调: 类型生成 + API测试 + Bug修复 | 2h |
| **小计** | | **~10h** |

### Phase 2（分析工具，预计 ~16h）

| 步骤 | 内容 | 预估工时 |
|------|------|----------|
| 6 | Schema: 其余14个模型 | 2h |
| 7 | Service: `repurchase.py` + `tiers.py` + `conversion.py` + `promotion.py` | 6h |
| 8 | Router: 追加4个API端点 | 1h |
| 9 | 前端: 4个Tab + 图表组件 | 5h |
| 10 | 联调: 全链路测试 + 性能优化 | 2h |
| **小计** | | **~16h** |

### Phase 3（优化，预计 ~4h）

| 步骤 | 内容 | 预估工时 |
|------|------|----------|
| 11 | 懒加载 + 缓存优化 | 1h |
| 12 | CSV导出功能 | 1h |
| 13 | 告警阈值配置化（V2） | 2h |
| **小计** | | **~4h** |

| **总计** | | **~30h** |

---

## 10. 已确认事项

| 编号 | 问题 | 决策 | 状态 |
|------|------|------|------|
| Q1 | 页面路由 | `/customer-health`（替换 `/rfm`） | ✅ 已确认 |
| Q2 | 默认分析周期 | 现状概览30天，复购周期30天（后续优化） | ✅ 已确认 |
| Q3 | 健康评分权重 | 均匀加权（各0.2），V2支持配置 | ✅ 已确认 |
| Q4 | 大促CSV加载 | 启动时预加载到内存（`@lru_cache`） | ✅ 已确认 |
| Q5 | 历史数据导出 | 支持CSV导出（Phase 2后追加） | ✅ 已确认 |
| Q6 | 告警阈值 | 固定值，V2支持配置 | ✅ 已确认 |
| Q7 | 分批交付 | Phase 1（现状概览）→ Phase 2（其余4Tab） | ✅ 已确认 |

---

## 11. 修复方案汇总（v1.0 Review后调整）

### 11.1 P1修复（编码前必须完成）

| # | 问题 | 修复方案 | 位置 |
|---|------|----------|------|
| 1 | SQL渠道名硬编码 | 所有SQL使用 `FilterBuilder.with_exclude_channels()` 或 `OrderFilters.channel_not_in()` 生成 | 所有SQL示例 |
| 2 | `DATE_SUB` MySQL语法 | 改为DuckDB兼容: Python计算日期后参数化传入，或使用 `?::DATE - INTERVAL '? days'` | 3.3.4 SQL |
| 3 | `EXTRACT(DAY FROM interval)` | 改为 `DATEDIFF('day', prev_pay_time, pay_time)` | 3.2.4 SQL |
| 4 | 渠道排除重复定义 | 删除 `EXCLUDE_CHANNELS_DEFAULT`，统一从 `filters.py` 导入 `OrderFilters.channel_not_in()` | 5.3 常量 |
| 5 | 大促CSV绝对路径 | 改为 `config.PROMOTION_CSV_PATH`，支持相对路径 | 10.1 代码 |

### 11.2 P2修复（Phase 1同步完成）

| # | 问题 | 修复方案 | 位置 |
|---|------|----------|------|
| 6 | main.py 路由膨胀 | 使用 `APIRouter` 拆出 `routers/health.py` | 5.2 |
| 7 | health_score 未归一化 | 补充 Min-Max 归一化说明（各指标先归一到0-1再加权） | 3.1.2 |
| 8 | Cohort SQL 全表扫描 | 添加 `pay_time >= ?` 时间下限过滤 | 3.2.4 SQL |
| 9 | 前端组件过度拆分 | AlertBanner 合并到 HealthOverviewTab 内联 | 4.2 |
| 10 | 缺少视觉规范 | 新增第4节「视觉规范」（颜色语义、图表库、布局） | 第4节 |

### 11.3 P3优化（Phase 2或后续）

| # | 问题 | 修复方案 | 计划 |
|---|------|----------|------|
| 11 | Schema 集中化 | 当 schemas.py 超过800行时按模块拆分 | 未来 |
| 12 | 前端懒加载 | Tab首次切换时才请求数据 | Phase 1已实现（tabLoaded标记） |
| 13 | 测试覆盖 | 补充 DuckDB 集成测试（空数据、单用户、小范围cohort） | Phase 2 |
| 14 | 告警跳转交互 | 告警卡片点击切换到对应Tab | Phase 1（前端实现） |

---

## 12. 附录

### 12.1 复购率计算统一口径

```python
# 所有模块的复购率计算必须遵循：
REPUCHASE_DEFINITION = {
    "min_orders": 2,                          # 2+订单
    "exclude_channels": ["U先派样", "百补派样", "赠品&0.01", "其他"],
    "exclude_refunds": True,                  # 剔除退款
    "exclude_goujinjin": True,                # 剔除购物金
    "time_scope": "same_period",              # 在分析周期内
}

# SQL过滤统一使用：
# fb = FilterBuilder()
# fb.with_metric_type(MetricType.GSV)  # 自动添加 is_goujinjin=FALSE AND order_status!='交易关闭' AND is_refund=FALSE
# fb.with_time_range(start_date, end_date)
# fb.with_exclude_channels(["U先派样", "百补派样", "赠品&0.01", "其他"])
# where_clause, params = fb.build()
```

### 12.2 大促CSV解析

```python
# backend/services/health/promotion.py
import csv
from pathlib import Path
from functools import lru_cache
from backend import config

@lru_cache(maxsize=1)
def load_promotion_periods() -> List[Dict[str, Any]]:
    """加载大促日历CSV（启动时预加载，内存缓存）"""
    csv_path = config.PROMOTION_CSV_PATH
    periods = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_range = row['正式时间']
            start_str, end_str = date_range.split('-')
            start_date = _parse_chinese_date(start_str.strip())
            end_date = _parse_chinese_date(end_str.strip())
            periods.append({
                'year': int(row['year']),
                'name': row['活动名称'],
                'start_date': start_date,
                'end_date': end_date,
            })
    return periods
```

### 12.3 DuckDB 语法速查

| MySQL语法 | DuckDB语法 | 用途 |
|-----------|-----------|------|
| `DATE_SUB(date, INTERVAL n DAY)` | `date - INTERVAL 'n days'` | 日期减法 |
| `DATE_ADD(date, INTERVAL n DAY)` | `date + INTERVAL 'n days'` | 日期加法 |
| `EXTRACT(DAY FROM (d1 - d2))` | `DATEDIFF('day', d2, d1)` | 天数差 |
| `DATE_TRUNC('month', date)` | `DATE_TRUNC('month', date)` | 月截断（相同） |

---

*文档 v1.1 完成。所有Review修复已整合，用户决策已确认，进入 Phase 1 编码阶段。*
