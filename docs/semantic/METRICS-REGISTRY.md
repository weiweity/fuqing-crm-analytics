# 芙清 CRM - 指标注册表与口径管理手册

本文件是业务指标的唯一真实来源。任何指标变更必须在此登记。

---

## 一、已注册指标总览

### 1.1 金额类指标

| key | 中文名 | SQL 表达式 | 口径说明 | 支持维度 |
|-----|--------|-----------|----------|----------|
| `gmv` | GMV | `SUM(actual_amount)` | 商品交易总额，含退款和购物金 | 全维度 |
| `gsv` | GSV | `SUM(CASE WHEN (is_goujinjin=FALSE AND is_refund=FALSE) THEN actual_amount ELSE 0 END)` | 有效销售额，剔除购物金和退款 | 全维度 |
| `member_gmv` | 会员GMV | `SUM(CASE WHEN is_member=TRUE THEN actual_amount ELSE 0 END)` | 会员订单GMV | 全维度 |
| `member_gsv` | 会员GSV | `SUM(CASE WHEN is_member=TRUE AND (is_goujinjin=FALSE AND is_refund=FALSE) THEN actual_amount ELSE 0 END)` | 会员有效销售额 | 全维度 |
| `old_gsv` | 老客GSV | `SUM(CASE WHEN is_old=1 THEN amount ELSE 0 END)` | 老客贡献的GSV | channel, spu_tier, spu_product_class, spu_product_subclass |
| `new_gsv` | 新客GSV | `SUM(CASE WHEN is_new=1 THEN amount ELSE 0 END)` | 新客贡献的GSV | 同上 |

### 1.2 人数类指标

| key | 中文名 | SQL 表达式 | 口径说明 |
|-----|--------|-----------|----------|
| `total_users` | 购买人数 | `COUNT(DISTINCT user_id)` | 去重购买用户数 |
| `gsv_users` | 有效购买人数 | `COUNT(DISTINCT user_id)` | 在GSV过滤后的查询中使用 |
| `order_count` | 订单数 | `COUNT(DISTINCT order_id)` | 去重订单数 |
| `gsv_order_count` | 有效订单数 | `COUNT(DISTINCT CASE WHEN (is_goujinjin=FALSE AND is_refund=FALSE) THEN order_id END)` | GSV口径订单数 |
| `member_users` | 会员人数 | `COUNT(DISTINCT CASE WHEN is_member=TRUE THEN user_id END)` | 去重会员数 |
| `new_users` | 新客人数 | `COUNT(DISTINCT CASE WHEN is_new=1 THEN user_id END)` | 窗口期内首次购买 |
| `old_users` | 老客人数 | `COUNT(DISTINCT CASE WHEN is_old=1 THEN user_id END)` | 窗口期内有购买且历史有购买 |
| `member_new_users` | 会员新客人数 | `COUNT(DISTINCT CASE WHEN is_member=TRUE AND is_new=1 THEN user_id END)` | - |
| `member_old_users` | 会员老客人数 | `COUNT(DISTINCT CASE WHEN is_member=TRUE AND is_old=1 THEN user_id END)` | - |

### 1.3 均值/占比类指标

| key | 中文名 | 计算方式 | 说明 |
|-----|--------|---------|------|
| `avg_order_value` | 客单价 | `AVG(actual_amount)` | 平均订单金额 |
| `aus` | 人均消费 | `SUM(actual_amount) / NULLIF(COUNT(DISTINCT user_id), 0)` | GSV/人数 |
| `member_aus` | 会员人均消费 | 会员金额 / 会员人数 | - |
| `member_gsv_ratio` | 会员GSV占比 | `member_gsv / gsv` | Python层计算 |
| `old_gsv_ratio` | 老客GSV占比 | `old_gsv / gsv` | Python层计算 |

---

## 二、维度总览

| key | 数据库列 | 中文名 | 下钻关系 |
|-----|---------|--------|----------|
| `channel` | channel | 渠道 | - |
| `spu_tier` | spu_tier | 商品梯队 | - |
| `spu_category` | spu_category | 品类销售 | - |
| `spu_type` | spu_type | 正装/小样 | - |
| `spu_product_class` | spu_product_class | 单品归类 | ← spu_category |
| `spu_product_subclass` | spu_product_subclass | 单品细分 | ← spu_product_class |
| `spu_cosmetic` | spu_cosmetic | 妆/械 | - |
| `province` | province | 省份 | - |
| `city` | city | 城市 | ← province |
| `segment` | segment_id | 人群象限 | - |

---

## 三、新增指标 SOP（标准操作流程）

### Step 1: 在 metrics.py 注册

打开 `backend/semantic/metrics.py`，在 `METRICS` 字典末尾添加：

```python
"your_metric_key": MetricDefinition(
    key="your_metric_key",
    name="你的指标中文名",
    sql_expr="SUM(CASE WHEN ... THEN actual_amount ELSE 0 END)",
    description="清晰的业务口径说明，方便后人理解",
    filters=["gsv", "member"],  # 依赖的过滤条件
    dimensions=["channel", "spu_tier"],  # 支持的分组维度
    format="currency",  # int | float | pct | currency
    precision=2,
),
```

### Step 2: 检查过滤条件

如果 SQL 中用到新的过滤逻辑，打开 `backend/semantic/filters.py`：
- 通用条件 → 加到 `OrderFilters`
- 动态构造 → 加到 `FilterBuilder`

### Step 3: 更新 API 契约

打开 `backend/contracts/schemas.py`，在相关 Response 模型中加入新字段：

```python
class SomeResponse(BaseModel):
    # ... 原有字段
    your_metric_key: float = Field(..., description="你的指标中文名")
```

### Step 4: 在 Service 中引用

```python
from backend.semantic import MetricRegistry

reg = MetricRegistry()
sql_expr = reg.get_sql("your_metric_key")  # 自动带 AS your_metric_key
```

### Step 5: 生成前端类型

后端启动后执行：

```bash
cd frontend-vue3
npx openapi-typescript http://localhost:8000/openapi.json -o src/api/types.ts
```

### Step 6: 前端使用

```typescript
import { components } from "@/api/types";
type Row = components["schemas"]["AudienceRow"];
// your_metric_key 会自动出现在类型提示中
```

---

## 四、修改口径 SOP

### 场景 A：GSV 定义调整

**只改一处**：`backend/semantic/filters.py`

找到 `OrderFilters.valid_order()` 和 `AmountExprBuilder` 中的条件，统一修改即可。

所有使用 `FilterBuilder.build()` 和 `AmountExprBuilder.sum_gsv()` 的代码自动生效。

### 场景 B：RFM 阈值调整

**只改一处**：`backend/semantic/segments.py`

修改 `RFM_THRESHOLDS` 字典，并确保 `strategy_config.yaml` 同步更新（YAML 用于运营策略文档，Python 用于计算）。

### 场景 C：渠道漏斗调整

**改两处**：
1. `scripts/run_etl.py` 中的 `match_channel()`（实际判定逻辑）
2. `backend/semantic/channels.py` 中的 `CHANNEL_FUNNEL`（元数据文档化）

---

## 五、Code Review Checklist

任何涉及指标/口径的 PR，必须通过以下检查：

- [ ] 没有在 Service 中新增硬编码的 `is_goujinjin = FALSE AND is_refund = FALSE`
- [ ] 没有在 Service 中新增硬编码的 `order_status LIKE '%成功%'`
- [ ] 新增指标已在 `metrics.py` 注册
- [ ] 新增维度已在 `dimensions.py` 注册
- [ ] API 字段变更已同步更新 `contracts/schemas.py`
- [ ] 前端类型已重新生成（大版本变更时）

---

## 六、变更日志

| 日期 | 变更人 | 变更内容 |
|------|--------|----------|
| 2026-04-16 | AI Agent | 建立 metrics.py / dimensions.py / filters.py / contracts/schemas.py 初始版本 |
