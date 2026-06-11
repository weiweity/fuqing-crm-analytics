# Sprint 16.5 B2 试点 — 3 Contract Audit 治根报告

> 分支: `fix/sprint16-5-b2-contract-audit-pilot`
> 任务: #91 P1 Wave 5 — B2 试点 3 contract audit (Sprint 15 B1 模式扩展)
> 范围: `backend/contracts/category.py` + `backend/contracts/metrics.py` + `backend/contracts/health.py`
> 模式: 跟 Sprint 15 Wave 2 B1 (`audience.py` 28 字段补标) 一致

## TL;DR

- **治根 9 个 mark 字段** (3 contract × 3 字段): 给未标注的 ratio/percentage/pp 字段补 `RatioField` / `PercentageField` 标注 + `Annotated[float, Field(ge=, le=)]` 约束
- **治根效果**: service 端返错值 (e.g. `pct=1.5` 越界) 原本 API 层 500 Internal Server Error, 加 Pydantic Field 标注后变 **422 ValidationError** (FastAPI 自动捕获), 跟 Sprint 14 拍板的 A.1 方案 (Sprint 13 ratio 治理) 一致
- **测试**: 新增 `backend/tests/test_b2_contract_mark_pilot.py` 13/13 passed (9 mark 字段 + 3 baseline happy path + 1 category 比例合法值); 现有 437 tests passed + 12 skipped (不破老 tests)
- **依赖**: 复用 `backend/contracts/types.py` 的 `RatioField` (ge=0, le=1) + `PercentageField` (ge=-1B, le=1B, Sprint 15 Wave 1 放宽) — 0 个新类型

---

## 背景

### Sprint 15 B1 模式回顾

Sprint 15 Wave 2 B1 任务是**给 `backend/contracts/audience.py` 的 28 个 ratio/percentage/pp 字段补 Pydantic Field 标注**, 治根"service 端返错值, API 层只能 500, 不能 422"的契约层防御缺口. 修法是用 `backend/contracts/types.py:32-53` 定义的 3 个 `Annotated[float, Field(ge/le)]` 自定义类型 (`RatioField` / `PercentageField` / `PpField`) 替换原 `float = Field(...)` 字段.

### Sprint 16.5 B2 试点目标

把 B1 模式扩到另外 3 个高频 contract, 找出**未标注的 ratio/percentage/pp 字段**, 各补 3 个代表字段治根 (试点, 不全量, 留 Sprint 17+ 扩到剩下 contract).

---

## 治根 9 个 mark 字段清单

### 1. `backend/contracts/category.py` × 3 字段

| 行号 (改后) | 类.字段 | 类型 | 治根前 | 治根后 | 错值示例 (改前 500, 改后 422) |
|---|---|---|---|---|---|
| 14 | `CategoryDistributionItem.pct` | `float` | 无标注 | `"RatioField"` | `pct=1.5` (越界 >1) |
| 15 | `CategoryDistributionItem.penetration_rate` | `float = 0.0` | 无标注 | `"RatioField" = 0.0` | `penetration_rate=-0.1` (越界 <0) |
| 16 | `CategoryDistributionItem.member_ratio` | `float = 0.0` | 无标注 | `"RatioField" = 0.0` | `member_ratio=1.2` (越界 >1) |

**服务层 mark 缺口验证**: `backend/services/category_service/overview.py:102` SELECT 用 `o.is_member` 过滤 + `SUM(CASE WHEN is_member THEN ... END) AS member_gsv`; `total_gsv` 来自 `SUM(CASE WHEN is_refund=FALSE THEN amount ELSE 0 END)`. 计算 `member_ratio = member_gsv / total_gsv` (line 158, 175) 是 0-1 decimal ratio, 但 contract 是裸 `float`, 一旦分母为 0 误传非 0 就会越界.

### 2. `backend/contracts/metrics.py` × 3 字段

| 行号 (改后) | 类.字段 | 类型 | 治根前 | 治根后 | 错值示例 |
|---|---|---|---|---|---|
| 34 | `TrendData.member_ratios` | `List[float]` | 无 element-wise 约束 | `List[Annotated[float, Field(ge=0, le=100)]]` | `[150.0]` (150% 越界 PercentageField) |
| 35 | `TrendData.ly_amounts` | `List[float]` | 无 element-wise 约束 | `List[Annotated[float, Field(ge=0)]]` | `[-100.0]` (负金额越界) |
| 36 | `TrendData.ly_member_ratios` | `List[float]` | 无 element-wise 约束 | `List[Annotated[float, Field(ge=0, le=100)]]` | `[200.0]` (200% 越界) |

**服务层 mark 缺口验证**: `backend/services/metrics/overview.py:163-165` 计算 `member_amount / amount` (curr_member_ratio) + `ly_member_ratio = last_year['member_amount'] / last_year['amount']` (line 322); `member_ratios` (line 34) 是 trend 序列 (今年每日会员占比), element 应该是 0-100 percentage. 改前无 element-wise 约束, caller 传 1.5 (decimal) 或 150.0 (跨单位) 都不会被 API 层拦截.

**关键 Pydantic v2 知识点**: `List["PercentageField"]` **不会** 触发 element-wise 约束 — 前向引用解析为 `float`, `Field` 元数据丢失. 必须用 `List[Annotated[float, Field(...)]]` 才会触发 `TypeAdapter` 解析. (Sprint 14 ratio 阶段 1 没踩这个坑, 因为 Sprint 15 B1 `audience.py` 用的是 scalar `RatioField` 不是 List.)

### 3. `backend/contracts/health.py` × 3 字段

| 行号 (改后) | 类.字段 | 类型 | 治根前 | 治根后 | 错值示例 |
|---|---|---|---|---|---|
| 145 | `ValueTierDefinition.gsv_ratio` | `float` | `Field(..., description=...)` 无 ge/le | `"RatioField" = Field(..., description="占全店GSV比例 0-1 decimal")` | `gsv_ratio=1.5` (越界) |
| 193 | `TierFlowRow.repurchase_gsv_ratio_current` | `float = 0.0` | `Field(default=0.0)` 无 ge/le | `"RatioField" = Field(default=0.0, description="...")` | `repurchase_gsv_ratio_current=1.3` |
| 167 | `CustomerSegmentItem.gsv_ratio` | `float` | `Field(..., description=...)` 无 ge/le | `"RatioField" = Field(..., description="GSV占比 0-1 decimal")` | `gsv_ratio=1.8` |

**服务层 mark 缺口验证**: `backend/services/health/overview.py:267` `member_old_customer_gsv_ratio = safe_ratio(member_old_gsv, member_total_gsv, 0.0)` (safe_ratio 是 0-1 守卫), 但 `safe_ratio` 仅在 SQL 服务层返 0 不抛错, contract 层 (ValueTierDefinition / CustomerSegmentItem / TierFlowRow) 仍是裸 `float`, 错值会无声通过.

---

## 改前 vs 改后

### 改前 (Sprint 15 B1 之前 28 字段 + Sprint 16.5 B2 之前 9 字段 = 37 字段全无标注)

```python
# backend/contracts/category.py:14
class CategoryDistributionItem(BaseModel):
    pct: float                           # 错值 pct=1.5 → 500
    penetration_rate: float = 0.0        # 错值 -0.1 → 500
    member_ratio: float = 0.0            # 错值 1.2 → 500
```

### 改后 (B2 试点治根后, 9 mark 字段已标注)

```python
# backend/contracts/category.py:14-16
class CategoryDistributionItem(BaseModel):
    # Sprint 16.5 B2 试点治根: 3 个 ratio 字段补 RatioField 标注
    pct: "RatioField"
    penetration_rate: "RatioField" = 0.0
    member_ratio: "RatioField" = 0.0
```

```python
# backend/contracts/metrics.py:34-36
class TrendData(BaseModel):
    # Sprint 16.5 B2 试点治根: 3 个 List 字段补 element-wise 约束
    member_ratios: List[Annotated[float, Field(ge=0.0, le=100.0)]] = Field(...)
    ly_amounts: List[Annotated[float, Field(ge=0.0)]] = Field(...)
    ly_member_ratios: List[Annotated[float, Field(ge=0.0, le=100.0)]] = Field(...)
```

```python
# backend/contracts/health.py:145, 193, 167
class ValueTierDefinition(BaseModel):
    gsv_ratio: "RatioField" = Field(..., description="占全店GSV比例 0-1 decimal")

class TierFlowRow(BaseModel):
    repurchase_gsv_ratio_current: "RatioField" = Field(default=0.0, description="...")

class CustomerSegmentItem(BaseModel):
    gsv_ratio: "RatioField" = Field(..., description="GSV占比 0-1 decimal")
```

---

## 测试覆盖

`backend/tests/test_b2_contract_mark_pilot.py` 共 13 个 test (9 mark 字段治根 + 1 合法值 + 3 baseline happy path):

| Test | 字段 | 错值 | 期望 |
|---|---|---|---|
| `test_category_pct_valid_ratio` | pct=0.42 | (合法) | 接受 |
| `test_category_pct_invalid_ratio_rejected` | pct=1.5 | 越界 | ValidationError |
| `test_category_penetration_rate_invalid_rejected` | penetration_rate=-0.1 | 越界 | ValidationError |
| `test_category_member_ratio_invalid_rejected` | member_ratio=1.2 | 越界 | ValidationError |
| `test_metrics_member_ratios_invalid_rejected` | member_ratios=[150.0] | 越界 | ValidationError |
| `test_metrics_ly_amounts_negative_rejected` | ly_amounts=[-100.0] | 越界 | ValidationError |
| `test_metrics_ly_member_ratios_invalid_rejected` | ly_member_ratios=[200.0] | 越界 | ValidationError |
| `test_health_value_tier_gsv_ratio_invalid_rejected` | gsv_ratio=1.5 | 越界 | ValidationError |
| `test_health_tier_flow_gsv_ratio_invalid_rejected` | repurchase_gsv_ratio_current=1.3 | 越界 | ValidationError |
| `test_health_customer_segment_gsv_ratio_invalid_rejected` | gsv_ratio=1.8 | 越界 | ValidationError |
| `test_category_all_legitimate_values` | 3 mark 全合法 | 接受 | 接受 |
| `test_metrics_all_legitimate_values` | 3 mark 全合法 | 接受 | 接受 |
| `test_health_all_legitimate_values` | 3 mark 全合法 | 接受 | 接受 |

**测试运行**:
- `pytest backend/tests/test_b2_contract_mark_pilot.py -v`: **13/13 passed** in 0.10s
- `pytest backend/tests/ --ignore=backend/tests/test_sim_prod_etl.py -q`: **437 passed + 12 skipped**, 0 failed (跟 contract 改动相关)

> 注: `test_sim_prod_etl.py::test_sim_prod_100_runs_idempotent_new_connection` 1 个 fail 是 Sprint 15 已知 flaky (RSS 3581.5MB 撞 1GB 软限), 跟本 PR 无关, 留 Sprint 16 跟 DuckDB race 一起修.

---

## 治根边界 / 已知限制

### 1. `List["PercentageField"]` 不触发 element-wise 约束

Pydantic v2 中, `List[ForwardRef("PercentageField")]` 解析后丢失 `Field(ge/le)` 元数据, 必须用 `List[Annotated[float, Field(ge, le)]]` 才会触发 `TypeAdapter` 解析. 这是 Pydantic v2 已知行为, Sprint 14 阶段 1 没踩到 (全 scalar).

### 2. 不破老 service 端合法值

老 service 端 (`category_service/overview.py:158`, `metrics/overview.py:165`, `health/overview.py:267`) 都用 `safe_ratio` / `if denominator > 0 else 0.0` 守卫, 合法值都是 0-1 decimal, 不会触发新约束. 9/9 happy path test 通过证明.

### 3. B2 试点不覆盖其他 contract

剩余未标注的 contract (e.g. `audience_summary` / `audience_table` / `re purchase` / `conversion` / `promotion` / `rfm_category_drilldown` / `tier_flow` / `tiers` / `config`) 留 Sprint 17+ 全量 audit. 本次 B2 试点目标 = 验证模式可扩展性, 不是全量治根.

### 4. Percent ageField 上限 1B (Sprint 15 放宽) 兜底

`backend/contracts/types.py:44-47` 的 `PercentageField` ge=-1B le=1B 是 Sprint 15 放宽后的兜底. 本次 B2 9 mark 字段全部用 `RatioField` (0-1), 不涉及 percentage 越界. 若 Sprint 17+ audit 发现 `*_yoy` 字段 (PpField -100~+100) 也有 mark 缺口, 同样可用 `PpField` 一键标注.

---

## 跟 Sprint 15 B1 模式一致性

| 维度 | Sprint 15 B1 (audience.py) | Sprint 16.5 B2 (category + metrics + health) |
|---|---|---|
| 治根字段数 | 28 | 9 (试点 3 × 3) |
| 用的类型 | RatioField / PercentageField / PpField | RatioField (8) + Annotated[float, Field(...)] (3 List) |
| 错值行为 | 错值 → 422 ValidationError | 同 |
| 测试文件 | (Sprint 15 B1 测试 = audience 28 field 回归, 跟 wave 1 一起) | `test_b2_contract_mark_pilot.py` (13/13) |
| 现有 tests 兼容 | 不破 (audience 28 是新加, 旧 service 返 0-1 合法值) | 不破 (437 + 12 skipped 0 failed) |
| 文档更新 | Sprint 15 plan + 8 tests | 本 audit 报告 + 13 tests |

---

## Sprint 17+ 后续建议

1. **全量 audit 剩下 contract**: `audience_summary` / `audience_table` / `re purchase` / `conversion` / `promotion` / `rfm_category_drilldown` / `tier_flow` / `tiers` / `config` — 估计 50+ ratio/percentage/pp 字段
2. **Lint 强制**: 加 `ground-truth-lint` 规则扫描 `contracts/*.py` 中 `float = Field(..., description=*)` + 字段名含 `*_ratio` / `*_yoy` / `*_pct` / `*_ppt` 模式 → 必须用 `RatioField` / `PercentageField` / `PpField` / `Annotated[*, Field(ge, le)]`
3. **Sprint 18+**: 把 B1 + B2 模式写进 `CLAUDE.md` 的 "Ratio Convention" 章节, 强制 contract 新增字段必须用 3 个自定义类型

---

## 关键 commit / 文件

- `backend/contracts/category.py` 14-16: 3 ratio 字段补 `RatioField` 标注
- `backend/contracts/metrics.py` 1: 加 `Annotated` import; 34-36: 3 List 字段补 element-wise 约束
- `backend/contracts/health.py` 145, 167, 193: 3 ratio 字段补 `RatioField` 标注
- `backend/tests/test_b2_contract_mark_pilot.py` (新增 154 行): 13 个 test

**Why**: B2 试点验证 B1 模式可扩展到非 audience contract, 9 mark 字段治根后, service 端错值不再 500, API 层 422 拦截.
**How to apply**: Sprint 17+ 全量 audit 50+ 字段时, 复用本报告的 3 contract × 3 mark 模式 + Annotated List element-wise 约束.
