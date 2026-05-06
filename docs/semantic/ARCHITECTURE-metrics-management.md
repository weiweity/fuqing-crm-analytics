# 芙清 CRM - 业务口径与计算逻辑统一管理架构

> 目标：解决前后端接口混乱、口径散落、新增指标困难的问题。

---

## 一、现状诊断

### 1.1 核心问题

| 问题 | 影响 | 典型表现 |
|------|------|----------|
| **口径碎片化** | 改一个定义要改十几个文件 | `is_goujinjin = FALSE AND is_refund = FALSE` 散落在 metrics/rfm/churn/geo/category/ETL 中 |
| **业务规则硬编码** | 新增维度=重写服务层 | 8象限定义在 4 个文件里各自有一份 |
| **前后端契约混乱** | 前端调用后猜字段格式 | `main.py` 内联 Pydantic 模型，和实际返回不一致 |
| **无指标注册中心** | 无法回答"系统有哪些指标" | 口口相传，文档滞后 |

### 1.2 问题根因

当前架构是 **"管道模式"**：数据从 ETL → DuckDB → Service → API，每一层都在自己本地做过滤和计算，没有统一的 **语义层 (Semantic Layer)**。

SaaS 公司发展到一定阶段，都会从管道模式演进为 **"语义层模式"**（也叫 Metrics Layer / Headless BI）。

---

## 二、目标架构：语义层 + 契约层 + 服务层

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (Vue3)                          │
│         类型从 OpenAPI 自动生成，禁止手写 guess              │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ HTTP / API Contract
┌─────────────────────────────────────────────────────────────┐
│                     API 契约层 (contracts)                   │
│              Pydantic Schemas = 唯一真实来源                 │
│         生成 /openapi.json → 前端自动生成 TS 类型            │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ 调用
┌─────────────────────────────────────────────────────────────┐
│                      服务层 (services)                       │
│   只负责编排查询、拼接结果、处理业务参数（如 MTD/自由模式）   │
│   禁止在此层写任何过滤条件 SQL 片段                           │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ 引用
┌─────────────────────────────────────────────────────────────┐
│                      语义层 (semantic)                       │
│  ├─ filters.py    → SQL 过滤条件工厂（GSV/GMV/时间/渠道等）  │
│  ├─ metrics.py    → 指标注册表（名称、公式、口径、维度）     │
│  ├─ dimensions.py → 维度注册表（字段名、中文名、下钻关系）   │
│  ├─ segments.py   → 人群分层（RFM评分、8象限定义）          │
│  ├─ channels.py   → 渠道漏斗定义                            │
│  └─ time.py       → 时间周期构造器（MTD/YoY/MoM）           │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ 读取
┌─────────────────────────────────────────────────────────────┐
│                      数据层 (DuckDB)                         │
│                         orders 表                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、语义层详解

### 3.1 filters.py — 统一过滤条件

**核心原则**：禁止在任何 Service/ETL 中直接写 `"order_status LIKE '%成功%'"` 或 `"is_goujinjin = FALSE AND is_refund = FALSE"`。

所有 SQL 过滤通过 `FilterBuilder` 生成：

```python
from backend.semantic import FilterBuilder, MetricType

fb = FilterBuilder()
fb.with_metric_type(MetricType.GSV)
fb.with_time_range("2026-01-01", "2026-01-31")
fb.with_channels(["直播", "货架"])

where_sql, params = fb.build()
# 输出: "pay_time >= ? AND pay_time <= ? AND order_status LIKE '%成功%' AND is_goujinjin = FALSE AND is_refund = FALSE AND channel IN (?, ?)"
```

同时提供 `AmountExprBuilder` 处理混合 GMV/GSV 计算：

```python
from backend.semantic import AmountExprBuilder

gsv_expr = AmountExprBuilder.sum_gsv()     # SUM(CASE WHEN ... THEN actual_amount ELSE 0 END)
gmv_expr = AmountExprBuilder.sum_gmv()     # SUM(actual_amount)
```

### 3.2 metrics.py — 指标注册表

所有指标在此注册，包含：key、中文名、SQL表达式、口径说明、支持维度。

```python
from backend.semantic import MetricRegistry

reg = MetricRegistry()
m = reg.get("gsv")
print(m.sql_expr)
# SUM(CASE WHEN (is_goujinjin = FALSE AND is_refund = FALSE) THEN actual_amount ELSE 0 END)
```

已注册指标清单：
- 金额类：gmv、gsv、member_gmv、member_gsv、old_gsv、new_gsv
- 人数类：total_users、gsv_users、order_count、gsv_order_count、member_users、new_users、old_users...
- 均值类：avg_order_value、aus、member_aus
- 占比类：member_gsv_ratio、old_gsv_ratio（由 Python 层计算，注册表记录公式）

### 3.3 dimensions.py — 维度注册表

统一定义所有分析维度，与前端筛选器保持一致。

```python
from backend.semantic import DimensionRegistry

dim_reg = DimensionRegistry()
dim_reg.get_group_expr("channel", table_alias="o")
# 输出: "COALESCE(o.channel, '其他')"
```

支持维度：channel、spu_tier、spu_product_class、spu_product_subclass、spu_category、spu_type、province、city、segment

### 3.4 segments.py — 人群分层

统一管理：
- RFM 固定阈值（R=[14,30,60,90], F=[1,2,3,5], M=[100,300,500,1000]）
- 8象限定义和 CASE WHEN SQL 生成
- 中英文名称、颜色映射

```python
from backend.semantic import SegmentRegistry

seg_reg = SegmentRegistry()
sql = seg_reg.build_segment_case_when_sql()
# 生成 8象限的完整 CASE WHEN 语句
```

### 3.5 channels.py — 渠道漏斗

文档化 ETL 中的 9层渠道判定规则，供 API 文档和前端下拉选项使用。

### 3.6 time.py — 时间周期

统一构造 MTD、自由模式、同比、环比、回溯期的时间范围。

```python
from backend.semantic import PeriodBuilder

periods = PeriodBuilder.mtd()
# {
#   "current": DateRange(start="2026-04-01", end="2026-04-15", cutoff="2026-03-31"),
#   "comparison": DateRange(...2025...),
#   "prev2": DateRange(...2024...)
# }
```

---

## 四、契约层详解

### 4.1 设计原则

1. **单一真实来源**：所有 Pydantic 模型必须在 `backend/contracts/schemas.py` 定义。
2. **禁止在 main.py 中内联定义 Response 模型**。
3. **字段命名 100% 对齐实际返回**。
4. **前端类型自动生成**：从 `/openapi.json` 生成 TypeScript 类型。

### 4.2 目录结构

```
backend/contracts/
├── __init__.py       # 统一暴露所有模型
└── schemas.py        # 所有 Request/Response 模型
```

### 4.3 前端类型生成

在 `frontend-vue3/` 中配置：

```bash
# 安装 openapi-typescript
npm install -D openapi-typescript

# 生成类型（后端启动后）
npx openapi-typescript http://localhost:8000/openapi.json -o src/api/types.ts
```

前端代码中：

```typescript
import { paths } from "@/api/types";

// 自动获得类型提示
type OverviewResponse = paths["/api/v1/metrics/overview"]["get"]["responses"]["200"]["content"]["application/json"];
```

---

## 五、服务层重构规范

### 5.1 重构前后对比

#### 重构前（硬编码，错误示范）

```python
def calculate_metrics(start, end, metric_type):
    if metric_type == "GSV":
        where_extra = "AND is_goujinjin = FALSE AND is_refund = FALSE"
        amount_expr = "SUM(actual_amount)"
    else:
        where_extra = ""
        amount_expr = "SUM(actual_amount)"
    # ... 这段逻辑在 5 个文件里重复出现
```

#### 重构后（使用语义层）

```python
from backend.semantic import FilterBuilder, MetricType, AmountExprBuilder

def calculate_metrics(start, end, metric_type):
    fb = FilterBuilder().with_metric_type(MetricType(metric_type)).with_time_range(start, end)
    where_sql, params = fb.build()
    amount_expr = AmountExprBuilder.sum_gsv() if metric_type == "GSV" else AmountExprBuilder.sum_gmv()
    # ... 只此一处定义，所有服务共用
```

### 5.2 待重构文件清单

按优先级排序：

1. `backend/services/metrics_service.py` — 人群看板核心
2. `backend/services/rfm_service.py` — RFM 计算
3. `backend/services/churn_service.py` — 流失预警
4. `backend/services/geo_service.py` — 地域分析
5. `backend/services/category_service.py` — 品类分析
6. `scripts/run_etl.py` — ETL 渠道判定和清洗逻辑（filters 可复用）

---

## 六、新增指标/维度的 SOP

### 6.1 新增一个指标

**Step 1**: 在 `backend/semantic/metrics.py` 的 `METRICS` 字典中注册：

```python
"my_metric": MetricDefinition(
    key="my_metric",
    name="我的新指标",
    sql_expr="SUM(CASE WHEN ... THEN actual_amount ELSE 0 END)",
    description="业务口径说明",
    dimensions=["channel", "spu_tier"],
    format="currency",
)
```

**Step 2**: 如果涉及新的过滤条件，在 `backend/semantic/filters.py` 的 `FilterBuilder` 中添加方法。

**Step 3**: 在 `backend/contracts/schemas.py` 中更新相关 Response 模型字段。

**Step 4**: 在 Service 中通过 `MetricRegistry.get("my_metric").sql_expr` 引用。

**Step 5**: 重新生成前端类型：`npx openapi-typescript ...`

**Step 6**: 更新前端页面，使用新类型调用 API。

### 6.2 新增一个维度

**Step 1**: 在 `backend/semantic/dimensions.py` 中注册：

```python
"my_dim": DimensionDefinition(
    key="my_dim",
    column="my_column",
    name="我的维度",
    default_value="未知",
)
```

**Step 2**: 在 `metrics.py` 中为需要支持的指标添加该维度到 `dimensions` 列表。

**Step 3**: 在 Service 中用 `DimensionRegistry.get_group_expr("my_dim")` 替代硬编码 GROUP BY。

**Step 4**: 前端筛选器中加入该维度选项。

### 6.3 修改一个口径

例如：GSV 定义从"仅剔除退款"改为"剔除退款+购物金+赠品"。

**只需要改一处**：`backend/semantic/filters.py` 中的 `valid_order()` 和 `AmountExprBuilder`。

修改后，所有引用 `FilterBuilder` 和 `AmountExprBuilder` 的服务自动生效。

---

## 七、迁移计划

### Phase 1（本周）：建立语义层和契约层 ✅
- [x] 创建 `backend/semantic/` 和 `backend/contracts/`
- [x] 抽取 filters、metrics、dimensions、segments、channels、time
- [x] 编写 `metrics_service_refactored.py` 作为重构示例

### Phase 2（下周）：逐个迁移 Service
- [ ] 重构 `metrics_service.py`（人群看板优先级最高）
- [ ] 重构 `rfm_service.py`
- [ ] 重构 `churn_service.py`
- [ ] 重构 `geo_service.py`
- [ ] 重构 `category_service.py`

### Phase 3（第三周）：ETL 对齐 + 前端契约
- [ ] ETL 中的 `clean_data` 和 `match_channel` 复用 `semantic/filters.py`
- [ ] 配置 `frontend-vue3` 的 openapi-typescript 自动生成
- [ ] 替换前端手写类型为自动生成类型

### Phase 4（持续）：建立 Code Review 规范
- [ ] PR 中禁止出现硬编码过滤条件
- [ ] 新增指标必须附带 `MetricDefinition` 注册
- [ ] API 变更必须同步更新 `contracts/schemas.py`

---

## 八、关键文件索引

| 文件 | 职责 |
|------|------|
| `backend/semantic/filters.py` | 统一 SQL 过滤条件 |
| `backend/semantic/metrics.py` | 指标注册表 |
| `backend/semantic/dimensions.py` | 维度注册表 |
| `backend/semantic/segments.py` | 8象限 + RFM 阈值 |
| `backend/semantic/channels.py` | 9层渠道漏斗定义 |
| `backend/semantic/time.py` | 时间周期构造器 |
| `backend/contracts/schemas.py` | 前后端契约模型 |
| `backend/services/metrics_service_refactored.py` | Service 重构示例 |

---

## 九、FAQ

**Q: 为什么要把 Pydantic 模型从 main.py 抽出来？**
A: main.py 的职责应该是路由注册和依赖注入。模型定义放在 contracts 层，才能作为前后端的"契约文件"被双方引用。否则前端看不到完整的字段定义。

**Q: FilterBuilder 会不会有性能损耗？**
A: 不会。FilterBuilder 只是字符串拼接，最终生成的 SQL 和原来硬编码的一模一样。

**Q: 如果某个指标需要特殊的过滤条件，FilterBuilder 支持不了怎么办？**
A: 先用 `fb.add_extra("your_custom_sql", [params])` 临时注入。如果该条件通用化程度高，应升级为 FilterBuilder 的正式方法。

**Q: Vue3 前端如何获得类型？**
A: 后端启动后访问 `http://localhost:8000/openapi.json`，用 `openapi-typescript` 一键生成 TS 类型文件。具体命令见本文第 4.3 节。
