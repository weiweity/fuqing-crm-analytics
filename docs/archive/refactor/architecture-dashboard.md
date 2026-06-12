# 芙清 CRM 数据库架构看板

**更新时间**: 2026-04-12
**架构师视角**: 限界上下文 + 领域驱动设计

---

## 1. 数据库整体视图

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           芙清 CRM 数据仓库 (DuckDB)                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────────────────────┐    ┌──────────────────────────────┐          │
│  │     📦 事实表 (Fact)          │    │     📊 汇总表 (Aggregation)    │          │
│  │                              │    │                              │          │
│  │  ┌────────────────────┐     │    │  ┌────────────────────┐     │          │
│  │  │      orders         │     │    │  │   daily_metrics     │     │          │
│  │  │  ────────────────   │     │    │  │  ────────────────   │     │          │
│  │  │  13,933,881 行      │     │    │  │  每日汇总 KPIs      │     │          │
│  │  │  订单级明细数据      │     │    │  │  GMV/订单/用户      │     │          │
│  │  └────────────────────┘     │    │  └────────────────────┘     │          │
│  │           │                 │    │           │                 │          │
│  │           ▼                 │    │           ▼                 │          │
│  │  ┌────────────────────┐     │    │  ┌────────────────────┐     │          │
│  │  │    user_rfm        │     │    │  │  monthly_metrics   │     │          │
│  │  │  ────────────────   │     │    │  │  ────────────────   │     │          │
│  │  │  用户 RFM 评分      │     │    │  │  月度汇总          │     │          │
│  │  │  8象限分类          │     │    │  └────────────────────┘     │          │
│  │  └────────────────────┘     │    │                              │          │
│  └──────────────────────────────┘    └──────────────────────────────┘          │
│                                                                                  │
│  ┌──────────────────────────────┐    ┌──────────────────────────────┐          │
│  │     🔖 维度表 (Dimension)     │    │     🔗 映射表 (Mapping)       │          │
│  │                              │    │                              │          │
│  │  ┌────────────────────┐     │    │  ┌────────────────────┐     │          │
│  │  │   spu_mapping       │     │    │  │  (无独立映射表)    │     │          │
│  │  │  ────────────────   │     │    │  │  SPU字段已内嵌    │     │          │
│  │  │  产品品类体系        │     │    │  │  到 orders 表     │     │          │
│  │  │  category/tier/...  │     │    │  └────────────────────┘     │          │
│  │  └────────────────────┘     │    │                              │          │
│  └──────────────────────────────┘    └──────────────────────────────┘          │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 表结构详解

### 2.1 orders（订单事实表）- 核心表

| 字段分组 | 字段名 | 类型 | 说明 | 可用性 |
|---------|--------|------|------|--------|
| **主键** | order_id | VARCHAR | 订单号 | ✅ 已索引 |
| **主键** | sub_order_id | VARCHAR | 子订单号 | ✅ |
| **外键** | user_id | VARCHAR | 用户ID | ✅ 已索引 |
| 时间 | order_time | TIMESTAMP | 下单时间 | ✅ 已索引 |
| 时间 | pay_time | TIMESTAMP | 支付时间 | |
| 时间 | ship_time | TIMESTAMP | 发货时间 | |
| 用户 | user_nickname | VARCHAR | 用户昵称 | |
| 商品 | product_id | VARCHAR | 商品ID | ✅ 已索引 |
| 商品 | product_title | VARCHAR | 商品标题 | |
| 商品 | sku_id / sku_code / sku_name | VARCHAR | SKU信息 | |
| 商品 | quantity | INTEGER | 数量 | |
| 金额 | amount | DECIMAL(12,2) | 标价 | |
| 金额 | actual_amount | DECIMAL(12,2) | 实付金额 | |
| 金额 | refund_amount | DECIMAL(12,2) | 退款金额 | |
| 地域 | province | VARCHAR | 省份 | ✅ 地域分析 |
| 地域 | city | VARCHAR | 城市 | |
| 渠道 | channel | VARCHAR | 渠道 | ✅ 渠道分析 |
| 渠道 | traffic_source / traffic_type | VARCHAR | 流量来源 | |
| 渠道 | influencer_name / influencer_id | VARCHAR | 达人 | |
| 渠道 | live_room_id / video_id | VARCHAR | 直播/视频 | |
| 会员 | is_member | BOOLEAN | 是否会员 | |
| 时间切片 | year / month | INTEGER | 年月 | ✅ 已索引 |
| **SPU** | spu_category | VARCHAR | 品类 | ✅ 品类分析 |
| **SPU** | spu_type | VARCHAR | 类型(正装/小样) | ✅ |
| **SPU** | spu_tier | VARCHAR | 梯队 | ✅ |
| **SPU** | spu_product_class | VARCHAR | 单品归类 | ✅ |
| **SPU** | spu_product_subclass | VARCHAR | 单品细分 | ✅ |
| **SPU** | spu_cosmetic | VARCHAR | 妆/械 | ✅ |
| **SPU** | spu_spec | VARCHAR | 规格 | ✅ |

**数据规模**: 13,933,881 订单 / 848,631 用户

---

### 2.2 user_rfm（RFM分析表）

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | VARCHAR | 用户ID (PK) |
| user_nickname | VARCHAR | 用户昵称 |
| analysis_date | DATE | 分析日期 (PK) |
| metric_type | VARCHAR | GMV/GSV (PK) |
| lookback_days | INTEGER | 回溯天数 (PK) |
| recency_days | INTEGER | 最近购买距今天数 |
| frequency | INTEGER | 购买频次 |
| monetary | DECIMAL(12,2) | 购买金额 |
| r_score / f_score / m_score | INTEGER | 各维度得分 1-5 |
| rfm_tier | VARCHAR | RFM分层名称 |
| segment_id | INTEGER | 象限ID (1-9) |
| first_order_date | DATE | 首购日期 |
| last_order_date | DATE | 最近购买日期 |

**主键**: (user_id, analysis_date, metric_type, lookback_days)

---

### 2.3 daily_metrics / monthly_metrics（汇总表）

**daily_metrics**: 每日关键指标聚合
- GMV/GSV/订单数/新客数/老客数/会员指标/客单价

**monthly_metrics**: 月度汇总
- 与 daily_metrics 结构相同，按月聚合

---

### 2.4 spu_mapping（产品映射表）

| 字段 | 类型 | 说明 |
|------|------|------|
| product_id | VARCHAR | 商品ID (PK) |
| category | VARCHAR | 品类 |
| product_type | VARCHAR | 正装/小样 |
| tier | VARCHAR | 梯队 |
| product_class | VARCHAR | 单品归类 |
| detail | VARCHAR | 单品细分 |
| cosmetic | VARCHAR | 妆/械 |
| spec | VARCHAR | 规格 |
| start_date / end_date | DATE | 有效期 |

> ⚠️ **注意**: 当前 SPU 字段已内嵌到 orders 表，spu_mapping 表主要用于补充映射

---

## 3. 领域模型视图（DDD 限界上下文）

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           限界上下文 (Bounded Context)                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐             │
│  │   订单上下文     │    │   客户上下文     │    │   品类上下文     │             │
│  │  (Orders)       │    │   (Customer)    │    │   (Category)    │             │
  │  ───────────────  │    │  ───────────────  │    │  ───────────────  │             │
│  │                 │    │                 │    │                 │             │
│  │ • orders 表     │    │ • user_rfm 表   │    │ • orders 表     │             │
│  │ • 订单主键      │    │ • RFM评分      │    │ • spu_category  │             │
│  │ • 时间维度      │    │ • 8象限分类    │    │ • spu_type      │             │
│  │ • 地域维度      │    │ • 流失风险     │    │ • spu_tier      │             │
│  │ • 渠道维度      │    │ • 客户生命周期 │    │ • spu_product_* │             │
│  │                 │    │                 │    │                 │             │
│  │  聚合: Order   │    │  聚合: Customer │    │  聚合: Product  │             │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘             │
│                                                                                  │
│  ┌─────────────────┐    ┌─────────────────┐                                     │
│  │   地域上下文     │    │   营销上下文     │                                     │
│  │   (Geography)   │    │   (Marketing)   │                                     │
│  │  ───────────────  │    │  ───────────────  │                                     │
│  │                 │    │                 │                                     │
│  │ • orders 表     │    │ • daily_metrics │                                     │
│  │ • province      │    │ • 活动效果     │                                     │
│  │ • city          │    │ • 渠道ROI      │                                     │
│  │ • 地域交叉分析  │    │ • 转化率       │                                     │
│  │                 │    │                 │                                     │
│  │  聚合: Region  │    │  聚合: Campaign│                                     │
│  └─────────────────┘    └─────────────────┘                                     │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 功能模块与数据表映射

| Week | 功能模块 | 涉及数据表 | 核心查询模式 |
|------|---------|-----------|-------------|
| Week 1 | 核心指标看板 | orders, daily_metrics | 聚合查询 + 趋势分析 |
| Week 2 | RFM 分析 | orders, user_rfm | 用户分组 + 评分计算 |
| Week 3 | 人群流转 | user_rfm | 象限流转矩阵 |
| Week 3 | 流失预警 | user_rfm, orders | 动态阈值 + 风险分层 |
| Week 4 | 地域分析 | orders | 省份/城市聚合 |
| Week 4 | 品类分析 | orders | SPU多级维度聚合 |
| Week 4 | PPT 导出 | 全部 | 数据整合 |
| Week 5 | 缺口追踪 | orders, user_rfm | 预测 + 缺口计算 |

---

## 5. 如何新增功能 - 决策树

```
当你需要新增一个功能时
         │
         ▼
┌─────────────────────────┐
│  这个功能分析什么？       │
└───────────┬─────────────┘
            │
    ┌───────┼───────┬───────────┬────────────┐
    ▼       ▼       ▼           ▼            ▼
  用户    订单    地域/城市    品类/SPU      时间趋势
    │       │       │           │            │
    ▼       ▼       ▼           ▼            ▼
┌─────────────────────────┐
│  需要新表还是新字段？     │
└───────────┬─────────────┘
            │
    ┌───────┴───────┐
    ▼               ▼
  新增表          扩展现有表
    │               │
    ▼               ▼
┌─────────────────────────┐
│  扩展模式选择：           │
├─────────────────────────┤
│  A. 新事实表 (fact_xxx)  │  ← 需要独立聚合口径
│  B. 新汇总表 (xxx_summary)│  ← 预计算常用指标
│  C. 扩展 orders 表       │  ← 新增维度字段
│  D. 新建 user_rfm 派生表 │  ← RFM 衍生分析
└─────────────────────────┘
```

---

## 6. 架构原则与红线

### ✅ 可以做
- 在 orders 表新增维度字段（province, channel, spu_* 都是这么来的）
- 新建汇总表预计算常用指标（daily_metrics 就是这么做的）
- 新建独立分析表（user_rfm 独立于 orders）
- 在现有 service 中新增查询方法

### ❌ 不要做
- 不要在 orders 表上做实时复杂计算 → 预计算到汇总表
- 不要创建跨限界上下文的混合表 → 保持领域边界清晰
- 不要删除或修改已有字段类型 → 历史数据兼容性
- 不要绕过 service 层直接查询数据库 → 保持数据访问一致性

---

## 7. 未来扩展方向（Week 5+）

| 方向 | 当前状态 | 新增需求 |
|------|---------|---------|
| 缺口追踪 | 待启动 | 可能需要 `prediction` 表或 `gap_analysis` 表 |
| 预测模型 | 不存在 | 可能需要 `model_results` 表 |
| 标签系统 | 不存在 | 可能需要 `user_tags` 表 |
| 618 大促 | 待规划 | 可能需要 `campaign` 表 + `campaign_metrics` 表 |

---

## 8. 快速参考

### 数据库路径
```
/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb
```

### 核心表一览
| 表名 | 行数(估) | 用途 |
|------|---------|------|
| orders | 13.9M | 订单事实表 |
| user_rfm | ~1M | RFM分析表 |
| daily_metrics | ~450 | 每日汇总 |
| monthly_metrics | ~15 | 月度汇总 |
| spu_mapping | ~1K | 产品映射 |

### 常用查询索引
- 订单查询: `idx_orders_user` (user_id)
- 时间查询: `idx_orders_time` (order_time)
- 产品查询: `idx_orders_product` (product_id)
- 年月查询: `idx_orders_year_month` (year, month)
