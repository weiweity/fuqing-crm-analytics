# Week 3 人群流转模块 - 技术方案草案

**版本**: v1.0（正式）
**日期**: 2026-04-02
**作者**: pm-agent
**状态**: 已确认

> **用户决策（v1.0）**: 状态分类=8象限✅ / 流转粒度=双轨（周+月）✅ / 流失=动态阈值+单品类✅ / 资产=先用订单模拟✅

---

## 1. 模块拆分

### 1.1 人群流转矩阵（Flow Matrix）

**功能描述**: 追踪用户在两个时间点之间的 RFM 象限变化，回答"上周/月的高价值用户本周/月留住了多少？降级了多少？"

**输入**:
- `user_rfm` 表（两个 analysis_date 的快照）
- 参数：from_date, to_date, metric_type（GMV/GSV）, granularity（week/month）

**输出**:
- 流转矩阵热力图（9×9 网格，cell=用户数）
- 桑基图（直观展示人群流动方向）
- 关键指标：留存率、升级率、降级率

**流转粒度**：双轨
- **周快报**：每周一推送上周 vs 上上周 的流转数据
- **月总结**：每月初推送上月 vs 上上月 的流转数据

**核心逻辑**:
```
对每个 user_id：
  T-1月 segment = get_segment(user_id, from_date)
  T月 segment = get_segment(user_id, to_date)
  matrix[T-1月 segment][T月 segment] += 1
```

**数据源依赖**:
- 现有 `user_rfm` 表（已按 analysis_date 存储历史快照）

**时间范围**:
- 流转矩阵需要两个时间点的快照：T-1月 和 T月
- **最早可用数据**：取决于 ETL 刷历史 analysis_date 的覆盖范围
- 当前已知数据范围：2025-01 起（需 ETL 确认是否刷了每月末的 analysis_date）
- 如果历史快照不足，流转矩阵最早只能从有数据的月份开始

**ETL 依赖检查清单**:
- [ ] `run_etl.py` 是否支持指定 analysis_date？
- [ ] 是否已刷过 2025-01 至 2026-03 的每月末快照？
- [ ] 如果没有，需要补充哪些日期的快照？

---

### 1.2 资产分析（Asset Analysis）

> **⚠️ 状态**: 资产分析模块暂时用**订单数据模拟**（无优惠券/积分数据），后续有数据再调整

**功能描述**: 统计每类人群的"资产沉淀"——累计 GMV、订单数、人均价值，帮助运营了解各象限的实际贡献

**数据源问题**:
- `user_rfm` 表中没有优惠券/积分/权益字段
- 需要新增 `user_assets` 表，但数据来源未确认（需用户确认是否有此类数据）

**输入**（待定）:
- 可能的来源：会员数据库 / 优惠券系统 / 积分系统

**输出**（待定）:
- 资产汇总表
- 资产趋势图

**待用户确认**:
- [ ] 是否有优惠券发放数据？
- [ ] 是否有积分累计/兑换数据？
- [ ] 是否有权益（会员等级/专属优惠）数据？

**核心逻辑**（先用订单模拟）:
```sql
SELECT
    r.segment_id,
    r.rfm_tier,
    COUNT(DISTINCT r.user_id) AS user_count,
    SUM(o.actual_amount) AS total_gmv,
    COUNT(DISTINCT o.order_id) AS total_orders,
    AVG(o.actual_amount) AS avg_order_value
FROM user_rfm r
JOIN orders o ON r.user_id = o.user_id
WHERE r.analysis_date = :date AND r.metric_type = :metric_type
GROUP BY r.segment_id, r.rfm_tier
```

> **注意**: 当前资产分析仅基于 `orders` 表的 GMV/订单统计，待优惠券/积分数据就绪后再扩展 `user_assets` 表。

---

### 1.3 流失预警（Churn Warning）

**功能描述**: 识别"应该买但没买"的高风险用户，基于用户历史购买间隔分布判断

**输入**:
- `orders` 表（购买记录，按 spu_category 或 spu_product_class 区分品类）

**输出**:
- 流失风险用户列表（user_id, risk_score, last_order_date, typical_cycle, days_since_last, product_category）
- 流失风险分布图（饼图：高/中/低风险占比）
- 各象限流失风险热力图

**流失定义**：动态阈值 + 单品类

> **用户确认**：动态阈值（超过典型购买周期 150% = 高风险），且按**单品类**计算用户购买周期

#### 方案A：固定阈值（简单粗暴）
基于 RFM 的 R 值直接判断，不考虑用户个性化行为。

```
高风险：R > 60 天 且 近90天无购买
流失：R > 90 天 且 近180天无购买
```

**优点**: 简单易解释，业务方容易理解
**缺点**: 不区分用户个体差异，高频购买用户 R>30 就可能是高风险

#### 方案B：动态阈值（个性化，推荐）
基于用户历史购买间隔计算典型周期，个性化判断。

```
1. 计算每个用户的典型购买周期：
   - 统计该用户所有相邻订单的时间间隔
   - 取中位数作为 typical_cycle（避免极端值干扰）

2. 风险评分公式：
   risk_score = (days_since_last - typical_cycle) / typical_cycle × 100

   - risk_score > 150 → 高风险（超过典型周期 1.5 倍）
   - risk_score > 100 → 中风险（超过典型周期 1 倍）
   - risk_score ≤ 100 → 低风险（还在正常购买窗口内）
```

**优点**: 个性化，高频用户不会被误判
**缺点**: 购买次数 < 3 次的用户样本不足，结果不准

#### 兜底逻辑（方案B）
购买次数 < 3 的用户，使用方案A 的固定阈值（避免样本不足误差）

#### API 参数扩展
```python
# GET /api/v1/churn/risk 增加参数
churn_mode: str  # "fixed" 或 "dynamic"，默认 "dynamic"
fixed_threshold: int  # 方案A 的阈值天数，默认 60
```

---

## 2. 数据模型

### 2.1 现有表结构

**user_rfm 表**（已存在）:
```sql
CREATE TABLE user_rfm (
    user_id            VARCHAR,
    user_nickname      VARCHAR,
    analysis_date      DATE,
    metric_type        VARCHAR,      -- 'GMV' 或 'GSV'
    lookback_days      INTEGER,
    recency_days       INTEGER,
    frequency          INTEGER,
    monetary           DECIMAL(12,2),
    r_score            INTEGER,
    f_score            INTEGER,
    m_score            INTEGER,
    rfm_tier           VARCHAR,
    rfm_tier_en        VARCHAR,
    segment_id         INTEGER,       -- 1-9 象限ID
    first_order_date   DATE,
    last_order_date    DATE,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, analysis_date, metric_type, lookback_days)
);
```

**orders 表**（已存在，核心字段）:
```sql
order_id, user_id, order_time, actual_amount, order_status, province, channel,
spu_category, spu_type, spu_tier, spu_product_class, spu_product_subclass...
```

### 2.2 新增表

**方案：复用 user_rfm，不新增表**

分析后发现 `user_rfm` 表已支持多时间点快照（analysis_date 字段），可直接用于流转分析：
- 查询 T-1月数据：`WHERE analysis_date = '2026-02-28'`
- 查询 T月数据：`WHERE analysis_date = '2026-03-31'`

**不需要新建 `user_rfm_history` 表**，但需要确认：
- 当前是否有定期刷历史 analysis_date 的任务？
- 如果没有，需要 ETL 支持（见 4.1 节）

**user_assets 表**（待确认，视数据源情况决定是否创建）:
```sql
-- 用户购买周期表（预计算每个用户的典型购买间隔）
CREATE TABLE IF NOT EXISTS user_typical_cycle (
    user_id            VARCHAR PRIMARY KEY,
    typical_cycle_days INTEGER,       -- 用户典型购买间隔（天）
    avg_order_interval DECIMAL(6,2),  -- 历史平均间隔
    std_deviation      DECIMAL(6,2),  -- 标准差
    order_count        INTEGER,       -- 样本量
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 3. API 契约草案

### 3.1 人群流转 API

**GET /api/v1/flow/matrix**

参数:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| from_date | string (date) | 是 | 起始月（格式：YYYY-MM-DD） |
| to_date | string (date) | 是 | 终止月（格式：YYYY-MM-DD） |
| metric_type | string | 否 | GMV/GSV，默认 GMV |
| lookback_days | int | 否 | 回顾天数，默认 180 |

返回:
```json
{
  "from_date": "2026-02-28",
  "to_date": "2026-03-31",
  "metric_type": "GMV",
  "matrix": {
    "1": {"1": 1200, "2": 150, "3": 80, ...},
    "2": {"1": 90, "2": 800, "3": 120, ...},
    ...
  },
  "summary": {
    "total_users": 50000,
    "retention_rate": 0.75,
    "upgrade_rate": 0.12,
    "downgrade_rate": 0.13
  },
  "segment_names": {
    "1": "钻石会员", "2": "潜力新贵", "3": "忠实金主",
    "4": "频次买家", "5": "豪气新客", "6": "清新路人",
    "7": "沉睡土豪", "8": "流失用户", "9": "其他"
  }
}
```

**GET /api/v1/flow/sankey**

参数: 同 matrix

返回:
```json
{
  "nodes": [
    {"id": "1_钻石会员", "category": "from"},
    {"id": "1_钻石会员", "category": "to"},
    ...
  ],
  "links": [
    {"source": "1_钻石会员", "target": "1_钻石会员", "value": 1200},
    {"source": "1_钻石会员", "target": "2_潜力新贵", "value": 150},
    ...
  ]
}
```

---

### 3.2 资产分析 API

**GET /api/v1/asset/summary**

参数:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| date | string (date) | 是 | 分析日期 |
| metric_type | string | 否 | GMV/GSV，默认 GMV |

返回:
```json
{
  "date": "2026-03-31",
  "metric_type": "GMV",
  "segments": {
    "1": {
      "name": "钻石会员",
      "user_count": 5000,
      "total_gmv": 5000000,
      "total_orders": 15000,
      "avg_gmv_per_user": 1000,
      "avg_orders_per_user": 3.0,
      "gmv_share": 0.35
    },
    ...
  },
  "total_gmv": 14000000,
  "total_users": 85000
}
```

**GET /api/v1/asset/trend**

参数:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| start_date | string | 是 | 开始日期 |
| end_date | string | 是 | 结束日期 |
| metric_type | string | 否 | GMV/GSV，默认 GMV |

返回:
```json
{
  "dates": ["2026-01-31", "2026-02-28", "2026-03-31"],
  "segments": {
    "1": {"name": "钻石会员", "gmv_trend": [4500000, 4800000, 5000000]},
    "2": {"name": "潜力新贵", "gmv_trend": [1200000, 1350000, 1500000]},
    ...
  }
}
```

---

### 3.3 流失预警 API

**GET /api/v1/churn/risk**

参数:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| date | string (date) | 是 | 分析日期 |
| risk_level | string | 否 | high/medium/low/all，默认 all |
| segment_id | int | 否 | 筛选特定象限 |
| churn_mode | string | 否 | fixed/dynamic，默认 dynamic |
| fixed_threshold | int | 否 | 固定阈值天数（churn_mode=fixed 时生效），默认 60 |

返回:
```json
{
  "date": "2026-03-31",
  "total_at_risk": 12000,
  "risk_distribution": {
    "high": 3000,
    "medium": 4000,
    "low": 5000
  },
  "users": [
    {
      "user_id": "U12345",
      "risk_score": 165,
      "risk_level": "high",
      "last_order_date": "2026-01-15",
      "days_since_last": 75,
      "typical_cycle": 45,
      "segment_id": 4,
      "segment_name": "频次买家"
    },
    ...
  ]
}
```

**GET /api/v1/churn/distribution**

参数: 同 risk，可选 segment_id

返回:
```json
{
  "date": "2026-03-31",
  "by_segment": {
    "1": {"high": 100, "medium": 200, "low": 500, "total": 800},
    "2": {"high": 150, "medium": 300, "low": 600, "total": 1050},
    ...
  }
}
```

---

## 4. 技术风险

### 4.1 最高风险：历史快照缺失

**风险描述**: `user_rfm` 表虽支持多 analysis_date，但当前 ETL 可能只保留最新日期的数据。如果历史快照不足，流转矩阵无法计算。

**影响**: 流转矩阵模块可能无法工作

**应对方案**:
1. 检查 `scripts/run_etl.py` 是否支持历史 analysis_date 批量刷
2. 如果不支持，需要新增 ETL 任务：`calculate_rfm_mutable(analysis_date=每月末日期, ...)`

**缓解措施**: 先用当前数据验证 T-1月 vs T月的流转，后续补历史

**需要 backend-dev 立即确认**:
- [ ] ETL 最近一次运行是否刷了 2026-02-28 和 2026-03-31 的 user_rfm 快照？
- [ ] `calculate_rfm_mutable()` 函数签名是否支持传入 analysis_date 参数？
- [ ] 最早可以从哪个月开始计算流转？（取决于历史快照最远追溯到什么时候）

---

### 4.2 高风险：计算性能

**风险描述**: 85万用户 × 2个月 × 9象限的流转计算，涉及大表 JOIN

**影响**: 查询响应时间可能超过 3 秒

**应对方案**:
1. 流转矩阵结果预计算（每日/每周任务）
2. 使用 DuckDB 的向量化查询优化
3. 前端加 loading 状态，避免重复请求

---

### 4.3 中风险：流失定义不精确

**风险描述**: 方案B（动态阈值）需要计算每个用户的历史购买间隔，用户样本量不足时（<3次购买）误差大

**影响**: 流失预警准确性下降

**应对方案**:
1. 购买次数 < 3 的用户使用固定阈值（R>60天）
2. 在 UI 上标注"样本量不足，结果仅供参考"

---

### 4.4 低风险：桑基图渲染

**风险描述**: 9×9 矩阵的桑基图可能过于复杂，用户难以解读

**影响**: 用户体验差

**应对方案**: 提供筛选器，允许用户只看"主要流动"（过滤掉 value < 100 的小流量）

---

## 5. 待确认事项

| # | 问题 | 选项 | 推荐 |
|---|------|------|------|
| 1 | 用户状态定义 | A: 沿用 RFM 8象限 / B: 简化为4类 | A（复用现有分层） |
| 2 | 流转时间粒度 | A: 月 / B: 周 | A（月粒度足够） |
| 3 | 流失定义阈值 | A: 固定（R>60高风险）/ B: 动态（>150%典型周期） | B，但样本不足时降级到A |
| 4 | 历史快照覆盖 | 需要确认最早可以追溯到哪个月 | 待 ETL 确认 |

---

## 6. 实施计划（草案）

| 阶段 | 任务 | 负责 | 工时 |
|------|------|------|------|
| 阶段一 | ETL：补充历史 analysis_date 快照 | backend-dev | 4h |
| 阶段二 | 后端：flow_matrix API + asset_summary API | backend-dev | 6h |
| 阶段三 | 后端：churn_risk API + user_typical_cycle 计算 | backend-dev | 6h |
| 阶段四 | 前端：流转矩阵页面 + 热力图 | frontend-dev | 6h |
| 阶段五 | 前端：资产分析页面 + 趋势图 | frontend-dev | 4h |
| 阶段六 | 前端：流失预警页面 + 风险列表 | frontend-dev | 4h |
| 阶段七 | 集成测试 + 验收 | qa-agent | 4h |

**总工时**: 约 34 小时
**预计完成**: 2026-04-09（周三）

---

## 附录：segment_id 映射表

| segment_id | 名称 | tier_en | 颜色 |
|------------|------|---------|------|
| 1 | 钻石会员 | Diamond | 紫色 |
| 2 | 潜力新贵 | Rising Star | 蓝色 |
| 3 | 忠实金主 | Loyal Elite | 深绿 |
| 4 | 频次买家 | Frequent Buyer | 绿色 |
| 5 | 豪气新客 | Big Spender New | 橙色 |
| 6 | 清新路人 | Fresh Rambler | 蓝灰 |
| 7 | 沉睡土豪 | Sleeping VIP | 红色 |
| 8 | 流失用户 | Churned | 深灰 |
| 9 | 其他 | Others | - |
