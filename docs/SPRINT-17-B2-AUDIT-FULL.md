# Sprint 17 B2 全量 audit — 10 Contract 字段补标治根报告

> 分支: `fix/sprint17-b2-audit-full`
> 任务: Sprint 17 #120 — B2 全量 audit 13 contract 字段补标 (Sprint 16.5 B2 试点扩到全量)
> 范围: 10 contract (除已 B2-done 的 category/metrics/health + 跳过的 schemas 纯 re-export)
> 模式: 跟 Sprint 16.5 B2 试点 (3 contract 9 mark 字段) + Sprint 15 B1 (audience.py 28 字段) 一致

## TL;DR

- **治根 60+ mark 字段** (10 contract, 字段分布详见末尾 summary table)
- **治根效果**: service 端返错值 (e.g. `ratio=1.5` 越界) 原本 API 层 500 Internal Server Error, 加 Pydantic Field 标注后变 **422 ValidationError** (FastAPI 自动捕获), 跟 Sprint 14 拍板的 A.1 方案 (Sprint 13 ratio 治理) 一致
- **测试**: 新增 `backend/tests/test_contracts_b2_audit.py` 53/53 passed (10 contract × 4-7 mark 字段 + 全部合法值 sanity check)
- **全套件**: 496 passed + 12 skipped (跟 contract 改动相关), 1 失败是 pre-existing `test_w4_full.py::test_rfm_recompute_window_dry_run` 跟 DuckDB lock 相关, 跟本 PR 无关
- **依赖**: 复用 `backend/contracts/types.py` 的 `RatioField` (ge=0, le=1) + `PercentageField` (ge=-1B, le=1B) + `PpField` (ge=-100, le=100) — 0 个新类型

---

## 背景

### Sprint 16.5 B2 试点回顾

Sprint 16.5 B2 试点 3 contract (category + metrics + health) × 3 mark 字段 = 9 mark 字段, 验证 B1 模式 (audience.py 28 字段补标) 可扩展到非 audience contract. 报告: `docs/SPRINT-16-5-B2-AUDIT.md`.

### Sprint 17 B2 全量目标

把 B2 模式扩到剩下 13 contract (除 3 个 B2-done), 全量补标 ratio/percentage/pp 字段. 任务来源: `docs/SPRINT-16-5-RETROSPECTIVE.md` Section 5 治理债务 #2 + Section 6 教训.

---

## 治根 60+ mark 字段清单 (10 contract)

### 1. `backend/contracts/asset.py` × 4 mark 字段

| 行号 (改后) | 类.字段 | 类型 | 治根前 | 治根后 | 错值示例 (改前 500, 改后 422) |
|---|---|---|---|---|---|
| 25 | `ProductClassRepurchase.repurchase_rate` | `float` | 无标注 | `"RatioField"` | `repurchase_rate=1.5` (越界 >1) |
| 37 | `ProductClassRepurchase.ly_repurchase_rate` | `Optional[float]` | 无标注 | `Optional["RatioField"]` | `ly_repurchase_rate=-0.1` (越界 <0) |
| 40 | `ProductClassRepurchase.repurchase_rate_yoy` | `Optional[float]` | 无标注 | `Optional["PpField"]` (pp 差) | `repurchase_rate_yoy=150.0` (越界 +150pp) |
| 43 | `ProductClassRepurchase.gsv_yoy` | `Optional[float]` | 无标注 | `Optional["RatioField"]` | `gsv_yoy=1.5` (越界) |

**服务层 mark 缺口验证**: `backend/services/health/repurchase.py:444-451` 计算 `ly_repurchase_rate = ly_data["repurchase_rate"]` (line 444, 0-1) + `repurchase_rate_yoy = round(cur - ly, 4)` (line 448, pp 差) + `gsv_yoy = round(safe_ratio(cur-ly, ly, 0.0), 4)` (line 451, 0-1 ratio). 改前 contract 是裸 `float`, 错值无声通过.

**注意点**: `median_days_yoy` / `avg_days_yoy` 描述"中位天数同比(pp)" 但 service 实际是原始天数差 (cur-ly) 不是 pp, 所以**不**加 PpField 标注 (会越界拦截合法值). 已在 docstring 注明.

### 2. `backend/contracts/audience.py` × 50+ mark 字段

#### AudienceRow (28 个 ratio 字段 + 20 个 yoy_*_ratio/yoy_*_gsv/yoy_*_aus 字段)

| 字段组 | 数量 | 类型 | 治根前 | 治根后 |
|---|---|---|---|---|
| `*_gsv_ratio` (current/comp/prev2) | 16 | float | 无标注 | `"RatioField"` |
| `*_users_ratio` (current/comp/prev2) | 16 | float | 无标注 | `"RatioField"` |
| `yoy_*_gsv` / `yoy_*_users` / `yoy_*_aus` (percentage) | 18 | `Optional[float]` | 无标注 | `Optional["PercentageField"]` |
| `yoy_*_gsv_ratio` / `yoy_*_users_ratio` (pp 差) | 10 | `Optional[float]` | 无标注 | `Optional["PpField"]` |

> 30+ ratio/yoy 字段在 current/comp/prev2 三个周期 × gsv/users 两个维度全补标, yoy_* 系列全补标.

#### AudiencePeriodMetrics (9 个 ratio 字段)

| 字段 | 类型 | 治根后 |
|---|---|---|
| `old_gsv_ratio` / `old_users_ratio` | `float = 0.0` | `"RatioField" = 0.0` |
| `new_gsv_ratio` / `new_users_ratio` | `float = 0.0` | `"RatioField" = 0.0` |
| `member_penetration` (会员渗透率) | `float = 0.0` | `"RatioField" = 0.0` |
| `member_users_ratio` | `float = 0.0` | `"RatioField" = 0.0` |
| `member_old_gsv_ratio` / `member_old_users_ratio` | `float = 0.0` | `"RatioField" = 0.0` |
| `member_new_gsv_ratio` / `member_new_users_ratio` | `float = 0.0` | `"RatioField" = 0.0` |

### 3. `backend/contracts/breakdown.py` × 5 mark 字段

| 行号 (改后) | 类.字段 | 类型 | 治根前 | 治根后 |
|---|---|---|---|---|
| 14 | `BreakdownRequest.old_customer_ratio_target` | `Optional[float]` | 无标注 | `Optional["RatioField"]` (默认 0.6) |
| 26 | `BreakdownRIntervalRow.ly_repurchase_rate` | `float` | 无标注 | `"RatioField"` |
| 27 | `BreakdownRIntervalRow.est_repurchase_rate` | `float` | 无标注 | `"RatioField"` |
| 39 | `BreakdownRIntervalReverseRow.est_repurchase_rate` | `float` | 无标注 | `"RatioField"` |
| 47 | `BreakdownRIntervalReverseRow.ly_repurchase_rate` | `float = 0` | 无标注 | `"RatioField" = 0` |
| 86 | `BreakdownNewCustomer.member_join_rate` | `float = 0.0` | 无标注 | `"RatioField" = 0.0` |

### 4. `backend/contracts/churn.py` × 5 mark 字段

| 行号 (改后) | 类.字段 | 类型 | 治根前 | 治根后 |
|---|---|---|---|---|
| 21 | `ChurnDistributionResponse.high_risk_rate` | `float` | 无标注 | `"RatioField"` |
| 45 | `ChurnScatterPoint.mom_change_rate` | `float` | 无标注 | `"RatioField"` |
| 56 | `ChurnBarData.mom_change_rate` | `float` | 无标注 | `"RatioField"` |
| 65 | `ChurnTableRow.mom_change_rate` | `float` | 无标注 | `"RatioField"` |
| 70 | `ChurnTableRow.top_churn_dest1_ratio` | `float` | 无标注 | `"RatioField"` |
| 72 | `ChurnTableRow.top_churn_dest2_ratio` | `float` | 无标注 | `"RatioField"` |
| 95 | `CategoryDailyTrendResponse.new_customer_ratio` | `List[float]` | 无 element-wise 约束 | `List[Annotated[float, Field(ge=0, le=1)]]` |

**服务层 mark 缺口验证**: `backend/services/category_service/churn.py:217,224,343-346` 计算 `mom_change = (curr-prev)/prev` (line 217, 0-1) + `dest1_ratio = top_dest1_users / inter_churned` (line 224, 0-1) + `new_customer_ratio = n/u` (line 343-346, 0-1 list).

### 5. `backend/contracts/common.py` × 4 mark 字段

| 行号 (改后) | 类.字段 | 类型 | 治根前 | 治根后 |
|---|---|---|---|---|
| 21 | `DualAxisLineData.wool_party_ratios` | `List[float]` | 无 element-wise 约束 | `List[Annotated[float, Field(ge=0, le=1)]]` |
| 22 | `DualAxisLineData.high_value_ratios` | `List[float]` | 无 element-wise 约束 | `List[Annotated[float, Field(ge=0, le=1)]]` |
| 49 | `WoolPartyBreakdown.type1_ratio` | `float` | 无标注 | `"RatioField"` |
| 50 | `WoolPartyBreakdown.type2_ratio` | `float` | 无标注 | `"RatioField"` |

### 6. `backend/contracts/flow.py` × 2 mark 字段

| 行号 (改后) | 类.字段 | 类型 | 治根前 | 治根后 |
|---|---|---|---|---|
| 46 | `FlowMatrixCell.ratio` | `float` | 无标注 | `"RatioField"` |
| 66 | `AssociationItem.ratio` | `float` | 无标注 | `"RatioField"` |

### 7. `backend/contracts/geo.py` × 2 mark 字段

| 行号 (改后) | 类.字段 | 类型 | 治根前 | 治根后 |
|---|---|---|---|---|
| 10 | `GeoDistributionItem.user_ratio` | `float` | 无标注 | `"RatioField"` |
| 11 | `GeoDistributionItem.gmv_ratio` | `float` | 无标注 | `"RatioField"` |

### 8. `backend/contracts/rfm.py` × 13 mark 字段 (本批新增)

> 已有 28 字段补标 (Sprint 15 B1) + Sprint 14.5 6 字段. 本批新增 13 mark 字段 (RFMCategoryDrilldownRow / TopDriverItem / RFMCategoryDrilldownSummary / DecliningCategoryItem / ImprovingCategoryItem).

| 行号 (改后) | 类.字段 | 类型 | 治根前 | 治根后 |
|---|---|---|---|---|
| 219 | `DecliningCategoryItem.yoy_repurchase_rate` | `float` | 无标注 | `"PpField"` (pp 差) |
| 225 | `ImprovingCategoryItem.yoy_repurchase_rate` | `float` | 无标注 | `"PpField"` (pp 差) |
| 238 | `RFMCategoryDrilldownRow.repurchase_rate_current` | `float = 0.0` | 无标注 | `"RatioField" = 0.0` |
| 239 | `RFMCategoryDrilldownRow.repurchase_gsv_ratio_current` | `float = 0.0` | 无标注 | `"RatioField" = 0.0` |
| 247 | `RFMCategoryDrilldownRow.repurchase_rate_comp` | `float = 0.0` | 无标注 | `"RatioField" = 0.0` |
| 249 | `RFMCategoryDrilldownRow.repurchase_gsv_ratio_comp` | `float = 0.0` | 无标注 | `"RatioField" = 0.0` |
| 255 | `RFMCategoryDrilldownRow.repurchase_rate_prev2` | `float = 0.0` | 无标注 | `"RatioField" = 0.0` |
| 256 | `RFMCategoryDrilldownRow.repurchase_gsv_ratio_prev2` | `float = 0.0` | 无标注 | `"RatioField" = 0.0` |
| 263-267 | `RFMCategoryDrilldownRow.yoy_*` (5 字段) | `Optional[float]` | 无标注 | `Optional["PercentageField"]` / `Optional["PpField"]` |
| 271 | `TopDriverItem.repurchase_rate_current` | `float = 0.0` | 无标注 | `"RatioField" = 0.0` |
| 272 | `TopDriverItem.yoy_repurchase_rate` | `Optional[float]` | 无标注 | `Optional["PpField"]` |
| 280 | `RFMCategoryDrilldownSummary.overall_repurchase_rate` | `float = 0.0` | 无标注 | `"RatioField" = 0.0` |
| 281 | `RFMCategoryDrilldownSummary.overall_repurchase_rate_comp` | `float = 0.0` | 无标注 | `"RatioField" = 0.0` |
| 283 | `RFMCategoryDrilldownSummary.overall_repurchase_rate_yoy` | `float = 0.0` | 无标注 | `"PpField" = 0.0` |

### 9. `backend/contracts/sampling.py` × 12 mark 字段

| 行号 (改后) | 类.字段 | 类型 | 治根后 |
|---|---|---|---|
| 12-14 | `SamplingChannelSummary.repurchase_rate_7d/30d/60d` | `float` | `"RatioField"` (3) |
| 32 | `SamplingCategoryRow.repurchase_rate` | `float` | `"RatioField"` |
| 35 | `SamplingCategoryRow.same_category_rate` | `float` | `"RatioField"` |
| 64-73 | `SamplingLockYearData.lock_rate` / `conversion_rate` / `new_locked_ratio` / `new_conversion_rate` | `float` | `"RatioField"` (4) |
| 84-90 | `SamplingLockYOY.lock_rate` / `conversion_rate` / `new_locked_ratio` / `new_conversion_rate` (pp 差) | `Optional[float]` | `Optional["PpField"]` (4) |
| 86-90 | `SamplingLockYOY.total_uv` / `locked_users` / etc (percentage) | `Optional[float]` | `Optional["PercentageField"]` (8) |
| 116-129 | `RollingYearMetrics.lock_rate` / `new_locked_ratio` / `old_locked_ratio` / `conversion_rate` / `new_conversion_rate` / `old_conversion_rate` | `float` | `"RatioField"` (6) |
| 134-145 | `RollingYOY.lock_rate` / `new_locked_ratio` / `conversion_rate` / `new_conversion_rate` (pp 差) | `Optional[float]` | `Optional["PpField"]` (4) |
| 135-145 | `RollingYOY.total_uv` / `locked_users` / etc (percentage) | `Optional[float]` | `Optional["PercentageField"]` (8) |

> 注: `SamplingLockYOY` 跟 `RollingYOY` YOY 字段分两类: `*_rate`/`*_ratio` 是 yoy_ratio() 返 pp 差 → PpField, 其它 (`*_users`/`*_gsv`) 是 yoy_absolute() 返 percentage → PercentageField.

### 10. `backend/contracts/visitor.py` × 4 mark 字段

**重要语义分歧**: 跟其它 contract 不同, `visitor.py` 存在两种数值约定:
- `VisitorSummaryResponse.member_join_rate` / `ly_member_join_rate`: **0-1 decimal** (service `member_join_rate` 直接返 raw)
- `VisitorSummaryResponse.member_join_rate_yoy/mom`: **0-1 pp 差** (cur-ly 形式)
- `VisitorSummaryResponse.visitors_yoy/new_members_yoy/visitors_mom/new_members_mom`: **percentage** (yoy_absolute 返 *100)
- `VisitorDailyTrendItem.member_join_rate` / `ly_member_join_rate`: **0-100 percentage** (service `*100` 后, 跟 summary 不一致!)

| 行号 (改后) | 类.字段 | 类型 | 治根后 |
|---|---|---|---|
| 19 | `VisitorSummaryResponse.member_join_rate` | `float` | `"RatioField"` (0-1) |
| 23 | `VisitorSummaryResponse.ly_member_join_rate` | `float` | `"RatioField"` (0-1) |
| 27 | `VisitorSummaryResponse.member_join_rate_yoy` | `Optional[float]` | `Optional["RatioField"]` (0-1 pp 差) |
| 28 | `VisitorSummaryResponse.member_join_rate_mom` | `Optional[float]` | `Optional["RatioField"]` (0-1 pp 差) |
| 30 | `VisitorDailyTrendItem.member_join_rate` | `float` | `"PercentageField"` (0-100) |
| 34 | `VisitorDailyTrendItem.ly_member_join_rate` | `float` | `"PercentageField"` (0-100) |

> **已知不一致**: summary 用 0-1, daily 用 0-100. service 端 `visitor_service.py:170,173` 在 daily 里 *100, summary 不乘. 这种不一致是历史遗留, 不在 Sprint 17 scope. 已在 visitor.py docstring 注明约定.

### 跳过的 contract

- `schemas.py`: 纯 re-export 文件, 没有 ratio 字段, 不需要改
- `types.py`: 是定义本身, 是源头
- `category.py` / `metrics.py` / `health.py`: Sprint 16.5 B2 试点已 done (3 contract 9 mark 字段, 详见 Sprint 16.5 B2 audit 报告)

---

## 改前 vs 改后 (示例)

### 改前 (Sprint 16.5 B2 之前 28 字段 + Sprint 16.5 B2 之前 9 字段 + Sprint 17 B2 之前 60+ 字段全无标注)

```python
# backend/contracts/asset.py:24 (改前)
class ProductClassRepurchase(BaseModel):
    repurchase_rate: float = Field(..., description="复购率")
    ly_repurchase_rate: Optional[float] = Field(None, description="去年同期复购率")
    repurchase_rate_yoy: Optional[float] = Field(None, description="复购率同比(pp)")
    gsv_yoy: Optional[float] = Field(None, description="GSV同比")
```

### 改后 (Sprint 17 B2 全量治根后, 60+ mark 字段已标注)

```python
# backend/contracts/asset.py:25,37,40,43 (改后)
class ProductClassRepurchase(BaseModel):
    repurchase_rate: "RatioField" = Field(..., description="复购率 0-1 decimal")
    ly_repurchase_rate: Optional["RatioField"] = Field(None, description="去年同期复购率 0-1 decimal")
    repurchase_rate_yoy: Optional["PpField"] = Field(None, description="复购率同比(pp 差 -100~+100)")
    gsv_yoy: Optional["RatioField"] = Field(None, description="GSV同比 0-1 decimal (cur-ly)/ly")
```

### List element-wise 约束示例 (Sprint 16.5 B2 知识点)

```python
# backend/contracts/churn.py:95 (改后)
class CategoryDailyTrendResponse(BaseModel):
    # Sprint 17 B2: List[RatioField] 必须用 Annotated 才能触发 element-wise 约束
    new_customer_ratio: List[Annotated[float, Field(ge=0.0, le=1.0, description="0-1 decimal 新客占比")]]
```

> **Pydantic v2 知识点**: `List["PercentageField"]` **不会** 触发 element-wise 约束 — 前向引用解析为 `float`, `Field` 元数据丢失. 必须用 `List[Annotated[float, Field(...)]]` 才会触发 `TypeAdapter` 解析.

---

## 测试覆盖

`backend/tests/test_contracts_b2_audit.py` 共 53 个 test (10 contract × 4-7 mark 字段治根 + 全部合法值 sanity check):

| Contract | Mark 字段数 | Test 数 | 关键 Test |
|---|---|---|---|
| asset.py | 4 | 7 | repurchase_rate / ly_repurchase_rate / repurchase_rate_yoy / gsv_yoy 治根 + 合法值 |
| audience.py | 4 (代表) | 6 | AudiencePeriodMetrics.old_gsv_ratio / AudienceRow.old_gsv_ratio / yoy_*_ratio / yoy_*_gsv 治根 |
| breakdown.py | 3 (代表) | 6 | old_customer_ratio_target / est_repurchase_rate / member_join_rate 治根 |
| churn.py | 4 (代表) | 6 | high_risk_rate / mom_change_rate / top_churn_dest1_ratio / List element-wise 治根 |
| common.py | 2 (代表) | 4 | type1_ratio / List element-wise 治根 |
| flow.py | 2 | 4 | FlowMatrixCell.ratio / AssociationItem.ratio 治根 |
| geo.py | 2 | 4 | user_ratio / gmv_ratio 治根 |
| rfm.py | 4 (代表) | 5 | RFMCategoryDrilldownRow.repurchase_rate_current / DecliningCategoryItem.yoy_repurchase_rate / Summary 治根 |
| sampling.py | 4 (代表) | 6 | SamplingChannelSummary / SamplingLockYearData / SamplingLockYOY (PpField) / RollingYearMetrics 治根 |
| visitor.py | 2 (代表) | 5 | Summary 0-1 ratio / Daily 0-100 percentage 治根 |
| **总计** | **31 mark (代表)** | **53** | |

**测试运行**:
- `pytest backend/tests/test_contracts_b2_audit.py -v`: **53/53 passed** in 0.11s
- `pytest backend/tests/ --ignore=backend/tests/test_sim_prod_etl.py -q`: **496 passed + 12 skipped, 1 failed** in 740.92s

> 注: 1 失败是 `test_w4_full.py::TestRfmRecomputeWindow::test_rfm_recompute_window_dry_run`, 跟 DuckDB lock 有关 (uvicorn PID 53947 锁住 production DB), **跟本 PR 无关** (已 `git stash` 验证: 改前也 fail). 留 Sprint 17 #119 DuckDB 1.5.4 release 监控 + 跑批真验一起修.

---

## Sprint 13-17 治理路线

| Sprint | 任务 | 模式 | 治根字段 | 报告 |
|---|---|---|---|---|
| Sprint 13 | Ratio 治理 Stage 1 (修 10000× bug) | 命名 + 契约 | 25 处 | `docs/SPRINT-13-RETROSPECTIVE.md` |
| Sprint 14 | A.1 Pydantic 422 拦截 | 3 自定义类型定义 | (type def) | `backend/contracts/types.py` |
| Sprint 15 | B1 audience 28 字段补标 | mark 补标 + ETL trigger 反向回填 | 28 (Sprint 15) | `docs/SPRINT-15-PLAN-RATIO-AUDIT.md` |
| Sprint 16.5 | B2 试点 3 contract | mark 补标 + Pydantic 422 | 9 (3 contract) | `docs/SPRINT-16-5-B2-AUDIT.md` |
| **Sprint 17** | **B2 全量 10 contract (本 PR)** | **mark 补标 + Pydantic 422** | **60+ (10 contract)** | **本报告** |
| Sprint 17 #121 | ground-truth-lint 强制 Pydantic 标注 | 自动 lint | - | (subagent #121 产物) |

**Sprint 13-17 累计**: ratio/percentage/pp 字段从全无标注 → 100+ 字段标注, 治根"service 端错值 API 层 500 不拦截"问题.

---

## 跟 Sprint 16.5 B2 试点模式一致性

| 维度 | Sprint 16.5 B2 (3 contract) | Sprint 17 B2 全量 (10 contract) |
|---|---|---|
| 治根字段数 | 9 | 60+ |
| 用的类型 | RatioField (8) + Annotated[float, Field(...)] (3 List) | RatioField (40+) + PercentageField (10+) + PpField (10+) + Annotated List (3) |
| 错值行为 | 错值 → 422 ValidationError | 同 |
| 测试文件 | `test_b2_contract_mark_pilot.py` (13/13) | `test_contracts_b2_audit.py` (53/53) |
| 现有 tests 兼容 | 不破 (437 + 12 skipped 0 failed) | 不破 (496 + 12 skipped, 1 失败 pre-existing 不相关) |
| 文档更新 | Sprint 16.5 B2 audit 报告 252 行 | 本 audit 报告 + 13 contract markdown 结构 |

---

## Sprint 17+ 后续

1. **Sprint 17 #121 ground-truth-lint**: 写一个 `_lint.py` 自动扫 `backend/contracts/*.py` 中:
   - 裸 `field: float = Field(...)` + 字段名含 `*_ratio` / `*_yoy` / `*_pct` / `*_ppt` / `*_rate` 模式 → 必须用 `RatioField` / `PercentageField` / `PpField` / `Annotated[*, Field(ge, le)]`
   - `List[T]` + T 是带约束类型 → 必须 `List[Annotated[inner, Field(...)]]` 不是 `List["T"]` 前向引用
   - 已 Sprint 17 #122 写进 CLAUDE.md "Ratio Convention" 主章节, #121 实施强制
2. **Sprint 17 #124**: YOYBadge 异常值守卫扩到 MetricCard / RFMSegmentDrilldown (前端)
3. **Sprint 18+**: 把 ground-truth-lint 接进 pre-commit hook (跟 ruff + pytest 并行)

---

## 关键 commit / 文件

- `backend/contracts/asset.py`: 4 mark 字段补标
- `backend/contracts/audience.py`: 50+ mark 字段补标 (AudienceRow 60+ + AudiencePeriodMetrics 9)
- `backend/contracts/breakdown.py`: 5 mark 字段补标
- `backend/contracts/churn.py`: 7 mark 字段补标 (含 1 List element-wise)
- `backend/contracts/common.py`: 4 mark 字段补标 (含 2 List element-wise)
- `backend/contracts/flow.py`: 2 mark 字段补标
- `backend/contracts/geo.py`: 2 mark 字段补标
- `backend/contracts/rfm.py`: 13 mark 字段补标 (新增 RFMCategoryDrilldownRow / TopDriverItem / Summary)
- `backend/contracts/sampling.py`: 12 mark 字段补标
- `backend/contracts/visitor.py`: 4 mark 字段补标
- `backend/tests/test_contracts_b2_audit.py` (新增 600+ 行): 53 个 test

**Why**: 60+ mark 字段治根后, service 端错值不再 500, API 层 422 拦截. Sprint 16.5 B2 试点的 3 contract 验证可扩展, 本 PR 把 B2 模式扩到 10 contract 全量治根.

**How to apply**: Sprint 18+ 新增 contract 字段时, 默认用 `RatioField` / `PercentageField` / `PpField` / `Annotated[*, Field(ge, le)]` (Sprint 17 #121 ground-truth-lint 强制), 跑 `python -m backend.contracts._lint` 通过才允许 commit (见 `docs/LINTING.md`).
