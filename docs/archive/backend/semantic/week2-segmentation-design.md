# Week 2 RFM 客户分层与运营策略设计

**版本**: v1.0
**日期**: 2026-03-31
**作者**: rfm-segmentation-strategy
**状态**: 设计稿，待评审

---

## 1. RFM 分层策略设计

### 1.1 指标定义

| 指标 | 全称 | 定义 | 计算方式 |
|------|------|------|----------|
| **R** | Recency | 最近一次购买距分析日的天数 | `分析日 - 最后一次购买日期` |
| **F** | Frequency | 分析周期内购买频次 | `分析周期内去重订单数` |
| **M** | Monetary | 分析周期内累计消费金额 | `分析周期内实际支付金额之和` |

**分析周期设定**：
- 标准 RFM：近 90 天（近一个季度）
- 618 大促 RFM：近 180 天（覆盖去年双11至今年618）
- 基准日期（MISSION_DATE）：`2026-06-18`（618大促日）

### 1.2 分值计算规则

采用 **1-5 分制**（5分最优）：

```
R_Score:
  R >= 90天 → 1分（濒临流失）
  60天 <= R < 90天 → 2分
  30天 <= R < 60天 → 3分
  14天 <= R < 30天 → 4分
  R < 14天 → 5分（高度活跃）

F_Score:
  F = 1 → 1分
  F = 2 → 2分
  F = 3 → 3分
  4 <= F <= 5 → 4分
  F >= 6 → 5分

M_Score:
  M < 100元 → 1分
  100 <= M < 300元 → 2分
  300 <= M < 500元 → 3分
  500 <= M < 1000元 → 4分
  M >= 1000元 → 5分
```

### 1.3 八象限分层定义

| 象限 | R分 | F分 | M分 | 命名 | 定位 |
|------|-----|-----|-----|------|------|
| **1** | 高(4-5) | 高(4-5) | 高(4-5) | `钻石会员` | 核心高价值客户 |
| **2** | 高(4-5) | 高(4-5) | 低(1-3) | `潜力新贵` | 高活跃度，有消费潜力 |
| **3** | 低(1-2) | 高(4-5) | 高(4-5) | `忠实金主` | 老客户，高度信任 |
| **4** | 低(1-2) | 高(4-5) | 低(1-3) | `频次买家` | 忠诚但不富裕 |
| **5** | 高(4-5) | 低(1-3) | 高(4-5) | `豪气新客` | 新客户中高消费 |
| **6** | 高(4-5) | 低(1-3) | 低(1-3) | `清新路人` | 新客户，低活跃 |
| **7** | 低(1-2) | 低(1-3) | 高(4-5) | `沉睡土豪` | 高消费但很久没来 |
| **8** | 低(1-2) | 低(1-3) | 低(1-3) | `流失用户` | 濒临或已流失 |

### 1.4 各象限运营策略

#### 象限1：钻石会员（RRFM = 高高高）

**定义**：近14天内有购买、年内购买6次以上、累计消费1000元以上

**特征**：
- 占比预估：5-8%
- GMV贡献预估：35-45%
- 客单价：最高

**运营策略**：
```
✓ 专属1对1客服 + 优先发货
✓ 新品优先体验（限量装免费申领）
✓ 年度会员专属权益（生日礼、节日礼）
✓ 禁发优惠券（防止价格敏感）
✓ 每月定期回访，了解使用反馈
✓ 邀请参与产品共创（内测官）
```

#### 象限2：潜力新贵（RRFM = 高低高）

**定义**：近14天内有购买、购买1-2次、消费300-1000元

**特征**：
- 占比预估：10-15%
- 升级潜力最大
- 偏好：性价比+新鲜感

**运营策略**：
```
✓ 升级激励：满X送正装活动
✓ 组合套餐推荐（提升客单）
✓ 加微信专属福利群
✓ 定向推送高客单价产品
✓ 积分加速兑换活动
```

#### 象限3：忠实金主（RRFM = 低高高）

**定义**：30-90天未购买、购买6次以上、累计消费1000元以上

**特征**：
- 占比预估：3-5%
- 信任度高，但可能流失
- 偏好：老客专享

**运营策略**：
```
✓ 老客专属召回礼包（限时）
✓ 专属客服电话回访
✓ 产品用完提醒 + 复购推荐
✓ 邀请参加线下活动
✓ 定向推送新品/爆款
```

#### 象限4：频次买家（RRFM = 低高低）

**定义**：30-90天未购买、购买4次以上、消费300-1000元

**特征**：
- 占比预估：8-12%
- 复购意愿强，客单中等
- 偏好：实惠+品质

**运营策略**：
```
✓ 月度会员日专享价
✓ 复购提醒（产品周期推送）
✓ 满额赠品活动
✓ 拼团邀请（老带新）
```

#### 象限5：豪气新客（RRFM = 高低高）

**定义**：近14天内有购买、购买1次、消费500元以上

**特征**：
- 占比预估：5-8%
- 首购高价值客户
- 偏好：品质+服务

**运营策略**：
```
✓ 首次购后关怀（使用指导）
✓ 限时加购优惠（提升F）
✓ 邀请关注店铺/加粉
✓ 推送搭配产品
```

#### 象限6：清新路人（RRFM = 高低低）

**定义**：近14天内有购买、购买1次、消费300元以下

**特征**：
- 占比预估：20-30%
- 新客主体
- 偏好：低价引流品

**运营策略**：
```
✓ 新人专享券（满99减20）
✓ 爆款低价引流
✓ 关注店铺领积分
✓ 产品种草内容推送
```

#### 象限7：沉睡土豪（RRFM = 低高低）

**定义**：60天以上未购买、消费500元以上

**特征**：
- 占比预估：5-8%
- 高价值但流失风险高
- 偏好：尊享体验

**运营策略**：
```
✓ 大额召回券（限时7天）
✓ 人工电话召回
✓ 专属回购礼盒
✓ 清仓/特卖专场邀请
```

#### 象限8：流失用户（RRFM = 低低低）

**定义**：90天以上未购买、消费500元以下

**特征**：
- 占比预估：25-35%
- 沉默用户
- 偏好：极大优惠

**运营策略**：
```
✓ 全站大促通知（618/双11）
✓ 极低价格召回（清货专场）
✓ 流失用户再营销标签
✓ 考虑移出日常运营预算
```

---

## 2. 618 大促专项策略

### 2.1 高价值客户618激活方案

#### 钻石会员 × 618

```
【预热期 5.1-5.31】
1. 提前30天发放"钻石专享入场券"（限量大额券）
2. 专属客服一对一沟通需求
3. 提前锁定热门产品库存

【正式期 6.1-6.18】
1. 6.1日0点优先抢购权
2. 全场任意叠加使用专属折扣
3. 满额赠豪华礼包（正装优先发货）

【返场期 6.19-6.30】
1. 限时加购专属福利
2. 老带新奖励（介绍1人得100积分）
```

#### 潜力新贵 × 618

```
【预热期】
1. 定向推送"升级攻略"（凑单技巧）
2. 发放"膨胀券"（满300抵450）
3. 邀请进 618 专属福利群

【正式期】
1. 组合套餐限时特价
2. 整点秒杀通知
3. 满额抽大奖活动
```

### 2.2 618专属人群标签

| 标签名 | 定义 | 用途 |
|--------|------|------|
| `大促高潜_30日加购未购` | 近30天加购但未下单 | 推送优惠券促进转化 |
| `大促高潜_收藏未购` | 收藏商品但未下单 | 定向推送降价提醒 |
| `大促高潜_去年618买过` | 2025年618有购买 | 召回老客户 |
| `大促高潜_去年双11买过` | 2025年双11有购买 | 关联大促记忆 |
| `大促警戒_退货率>30%` | 退货订单占比>30% | 限制优惠力度 |
| `大促新客_2025首购` | 2025年首次购买 | 视为新客户 |
| `大促休眠_180天未购` | 近180天无购买 | 流失召回 |

### 2.3 618人群包与普通RFM人群包的区别

| 维度 | 普通RFM人群包 | 618大促人群包 |
|------|-------------|--------------|
| **分析周期** | 近90天 | 近180天（跨大促周期） |
| **R定义** | 最近购买距今天数 | 最近购买距618活动日天数 |
| **人群规模** | 侧重长期价值分层 | 侧重短期转化 |
| **标签丰富度** | 基础RFM分+象限 | 叠加行为标签（加购/收藏/浏览） |
| **推送内容** | 日常运营 | 大促专属活动 |
| **时间敏感度** | 低 | 极高（限时/限量） |
| **优惠力度** | 常规 | 加大（专属券/膨胀券） |

---

## 3. 人群包设计

### 3.1 命名规范

```
格式：{用途}_{象限}_{周期}_{版本}
示例：
- RFM_01_DIAMOND_90D_v1        # 钻石会员，普通RFM
- RFM_05_NEWRICH_618_180D_v1   # 豪气新客，618版本
- 618_HIGHVALUE_180D_v1         # 618高价值客户包
```

### 3.2 标准人群包字段清单

```python
STANDARD_FIELDS = [
    # 基础标识
    "user_id",              # 用户ID（脱敏）
    "user_nickname",         # 用户昵称（脱敏）

    # RFM核心分
    "r_score",               # R分 1-5
    "f_score",               # F分 1-5
    "m_score",               # M分 1-5
    "rfm_total",             # RFM总分 3-15

    # 分层结果
    "segment_id",            # 象限编号 1-8
    "segment_name",          # 象限名称（中文）
    "segment_en",            # 象限名称（英文）

    # RFM原始值
    "recency_days",          # 最近购买距分析日天数
    "frequency_count",       # 分析周期内购买频次
    "monetary_amount",       # 分析周期内累计消费金额

    # 时间信息
    "last_order_date",       # 最近购买日期
    "first_order_date",      # 首次购买日期
    "analysis_date",         # 分析基准日期

    # 用户属性
    "is_member",             # 是否会员
    "province",              # 省份
    "city",                  # 城市

    # 标签
    "spu_category",          # 偏好品类
    "spu_tier",              # 偏好梯队
    "channel",               # 主要渠道
]
```

### 3.3 618专项人群包字段清单

```python
CAMPAIGN_618_FIELDS = [
    # 基础标识
    "user_id",
    "user_nickname",

    # RFM核心分（618版本）
    "r_score_618",
    "f_score_618",
    "m_score_618",
    "rfm_total_618",

    # 分层结果
    "segment_id_618",
    "segment_name_618",

    # 618专项标签
    "tag_added_cart_30d",     # 近30天加购未购
    "tag_favorited",          # 收藏未购
    "tag_618_2025_buyer",     # 去年618买过
    "tag_double11_2025_buyer",# 去年双11买过
    "tag_risk_return",        # 退货率警戒
    "tag_new_2025",           # 2025年新客
    "tag_dormant_180d",       # 180天未购

    # 618营销信息
    "coupon_eligibility",     # 优惠券领取资格
    "priority_level",          # 优先级（1-3级）
    "recommended_action",     # 推荐动作

    # 价值预估
    "ltv_score",              # 生命周期价值评分
    "churn_risk",             # 流失风险等级
]
```

### 3.4 Excel导出规范

```python
EXPORT_COLUMNS = [
    # Sheet1: 人群包总览
    {
        "sheet_name": "人群包总览",
        "columns": ["segment_id", "segment_name", "user_count", "gmv_contribution_pct", "avg_order_value"]
    },
    # Sheet2: 钻石会员
    {
        "sheet_name": "01_钻石会员",
        "columns": STANDARD_FIELDS,
        "filter": "segment_id == 1"
    },
    # Sheet3-9: 其他象限...
    # Sheet10: 618专项
    {
        "sheet_name": "618专项人群",
        "columns": CAMPAIGN_618_FIELDS,
        "filter": "tag_618_2025_buyer == True OR tag_double11_2025_buyer == True"
    },
]
```

---

## 4. 代码设计建议

### 4.1 核心函数签名

```python
# rfm_segmentation.py

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class RFMResult:
    """RFM计算结果"""
    user_id: str
    r_score: int           # 1-5
    f_score: int           # 1-5
    m_score: int           # 1-5
    rfm_total: int         # 3-15
    segment_id: int         # 1-8
    segment_name: str
    recency_days: int
    frequency_count: int
    monetary_amount: float


@dataclass
class RFMSegment:
    """RFM象限定义"""
    segment_id: int
    name_cn: str
    name_en: str
    r_range: tuple          # (min, max)
    f_range: tuple
    m_range: tuple
    strategy: Dict[str, Any]  # 运营策略
    tags: List[str]          # 人群标签


def calculate_rfm_scores(
    start_date: str,
    end_date: str,
    r_thresholds: tuple = (14, 30, 60, 90),    # R分界点
    f_thresholds: tuple = (1, 2, 3, 5),        # F分界点
    m_thresholds: tuple = (100, 300, 500, 1000),  # M分界点
    conn=None  # 可选外部传入连接
) -> List[RFMResult]:
    """
    计算RFM分值

    Args:
        start_date: 分析周期开始
        end_date: 分析周期结束
        r_thresholds: R分阈值 [14天,30天,60天,90天]
        f_thresholds: F分阈值 [1次,2次,3次,5次]
        m_thresholds: M分阈值 [100,300,500,1000]
        conn: DuckDB连接（可选）

    Returns:
        List[RFMResult]: 用户RFM分值列表
    """
    pass


def assign_segments(
    rfm_results: List[RFMResult],
    segment_definitions: List[RFMSegment]
) -> List[RFMResult]:
    """
    分配RFM象限

    Args:
        rfm_results: RFM分值列表
        segment_definitions: 象限定义列表

    Returns:
        List[RFMResult]: 带象限的RFM结果
    """
    pass


def generate_segment_stats(
    rfm_results: List[RFMResult]
) -> Dict[str, Dict[str, Any]]:
    """
    生成各象限统计数据

    Returns:
        Dict: {segment_name: {user_count, gmv_sum, avg_order_value, ...}}
    """
    pass


def export_segment_packages(
    rfm_results: List[RFMResult],
    output_path: str,
    include_fields: List[str],
    sheet_filter: Optional[Dict[str, Any]] = None
) -> str:
    """
    导出人群包

    Args:
        rfm_results: RFM结果
        output_path: 输出路径
        include_fields: 导出字段
        sheet_filter: 分Sheet过滤条件

    Returns:
        str: 导出文件路径
    """
    pass


def calculate_618_segments(
    analysis_date: str = "2026-06-18",
    lookback_days: int = 180
) -> List[RFMResult]:
    """
    计算618大促版RFM（使用180天周期）

    Args:
        analysis_date: 618分析基准日
        lookback_days: 回溯天数

    Returns:
        List[RFMResult]: 618版RFM结果
    """
    pass


def add_campaign_tags(
    rfm_results: List[RFMResult],
    cart_data: bool = True,         # 是否加购标签
    favorite_data: bool = True,      # 是否收藏标签
    return_data: bool = True         # 是否退货标签
) -> List[RFMResult]:
    """
    添加618专项行为标签

    Returns:
        List[RFMResult]: 带标签的RFM结果
    """
    pass
```

### 4.2 配置文件设计（strategy_config.yaml）

```yaml
# strategy_config.yaml
# RFM分层策略配置

rfm:
  # 标准RFM参数
  standard:
    analysis_period_days: 90
    r_thresholds: [14, 30, 60, 90]
    f_thresholds: [1, 2, 3, 5]
    m_thresholds: [100, 300, 500, 1000]

  # 618大促RFM参数
  campaign_618:
    analysis_period_days: 180
    campaign_date: "2026-06-18"
    r_thresholds: [30, 60, 90, 180]
    f_thresholds: [1, 2, 3, 4]
    m_thresholds: [200, 500, 1000, 2000]

segments:
  1:
    name_cn: "钻石会员"
    name_en: "Diamond VIP"
    r_range: [4, 5]
    f_range: [4, 5]
    m_range: [4, 5]
    priority: 1
    strategy:
      - action: "专属客服1对1"
      - action: "新品优先体验"
      - action: "年度会员权益"
      - exclude_actions:
          - "发放优惠券"  # 防止价格敏感

  2:
    name_cn: "潜力新贵"
    name_en: "Rising Stars"
    r_range: [4, 5]
    f_range: [1, 3]
    m_range: [4, 5]
    priority: 2
    strategy:
      - action: "升级激励活动"
      - action: "组合套餐推荐"
      - action: "加微信福利群"

  # ... 其他象限

campaign_618:
  tags:
    high_value:
      - name: "大促高潜_30日加购未购"
        condition: "added_cart_30d == True AND first_order_date >= {start}"
      - name: "大促高潜_收藏未购"
        condition: "favorited == True"
      - name: "大促高潜_去年618买过"
        condition: "order_time BETWEEN '2025-06-01' AND '2025-06-30'"

    risk:
      - name: "大促警戒_退货率>30%"
        condition: "return_rate > 0.3"
      - name: "大促休眠_180天未购"
        condition: "recency_days > 180"

export:
  path_template: "data/packages/RFM_{segment}_{date}_{version}.xlsx"
  sheets:
    - name: "人群包总览"
      type: "summary"
    - name: "01_钻石会员"
      filter: "segment_id == 1"
    # ...
```

### 4.3 架构扩展性设计

#### 支持渠道规则高频调整

```python
# 策略：配置与代码分离
# 1. 所有阈值均可通过 YAML 配置调整，无需改代码
# 2. 渠道规则作为独立模块，可热更新

# channel_rules.yaml（独立维护）
channels:
  - id: "douyin"
    name: "抖音渠道"
    spu_weights:  # 不同渠道SPU权重不同
      tier1: 1.2
      tier2: 1.0
      tier3: 0.8

  - id: "tmall"
    name: "天猫渠道"
    spu_weights:
      tier1: 1.0
      tier2: 1.1
      tier3: 0.9
```

#### 支持SPU微调

```python
# 策略：SPU映射表可独立配置
# SPU变化时，只需更新 spu_mapping 表，无需改代码

# SPU映射在 ETL 阶段处理，RFM计算只读取结果
# 架构上保证：SPU定义变化 -> ETL重跑 -> RFM重新计算
```

---

## 5. 数据依赖与下游接口

### 5.1 数据依赖

| 上游 | 数据表 | 字段 | 用途 |
|------|--------|------|------|
| orders | orders | user_id, order_time, actual_amount | RFM计算 |
| ETL | spu_mapping | spu_category, spu_tier | 偏好分析 |
| 行为 | cart/favorite | user_id, product_id, add_time | 618标签 |

### 5.2 下游接口

| 下游 | 接口 | 数据格式 |
|------|------|----------|
| 运营系统 | POST /api/rfm/export | Excel文件流 |
| 营销系统 | GET /api/rfm/segments/{id}/users | JSON分页 |
| BI看板 | GET /api/rfm/dashboard | JSON聚合数据 |

---

## 6. 实施计划

### Week 2 任务分解

| 阶段 | 任务 | 负责方 | 产出 |
|------|------|--------|------|
| Day 1 | RFM计算核心函数 | rfm-calculations | `rfm_segmentation.py` |
| Day 1 | 配置YAML设计 | rfm-segmentation-strategy | `strategy_config.yaml` |
| Day 2 | 8象限分层逻辑 | rfm-calculations | 单元测试通过 |
| Day 2 | 人群包导出功能 | rfm-calculations | Excel导出 |
| Day 3 | 618专项标签计算 | rfm-calculations | 行为标签数据 |
| Day 3 | 618人群包导出 | rfm-calculations | 618专项Excel |
| Day 4 | ~~Streamlit~~ Vue3 RFM页面 | frontend-vue3 | `RfmView.vue` |
| Day 5 | 联调测试 + 文档 | 全体 | 可运行版本 |

---

## 7. 附录

### A. RFM分值计算参考SQL

```sql
-- DuckDB RFM计算SQL（参考实现）
WITH user_metrics AS (
    SELECT
        user_id,
        user_nickname,
        DATEDIFF('day', MAX(order_time), '2026-03-31') as recency_days,
        COUNT(DISTINCT order_id) as frequency,
        SUM(actual_amount) as monetary
    FROM orders
    WHERE order_time >= '2025-12-31'
      AND order_status LIKE '%成功%'
    GROUP BY user_id, user_nickname
)
SELECT
    user_id,
    user_nickname,
    recency_days,
    frequency,
    monetary,
    CASE
        WHEN recency_days >= 90 THEN 1
        WHEN recency_days >= 60 THEN 2
        WHEN recency_days >= 30 THEN 3
        WHEN recency_days >= 14 THEN 4
        ELSE 5
    END as r_score,
    CASE
        WHEN frequency = 1 THEN 1
        WHEN frequency = 2 THEN 2
        WHEN frequency = 3 THEN 3
        WHEN frequency BETWEEN 4 AND 5 THEN 4
        ELSE 5
    END as f_score,
    CASE
        WHEN monetary < 100 THEN 1
        WHEN monetary < 300 THEN 2
        WHEN monetary < 500 THEN 3
        WHEN monetary < 1000 THEN 4
        ELSE 5
    END as m_score
FROM user_metrics
```

### B. 术语表

| 术语 | 定义 |
|------|------|
| GMV | Gross Merchandise Volume，总成交金额 |
| GSV | Gross Sales Value，排除退款后的成交金额 |
| RFM | Recency, Frequency, Monetary，客户价值模型 |
| SPU | Standard Product Unit，标准化产品单元 |
| SKU | Stock Keeping Unit，库存量单位 |
| LTV | Life Time Value，生命周期价值 |
| 象限 | RFM三分法形成的9宫格（实际用8格） |
