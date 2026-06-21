# Ratio Convention 开发指南

> **本文档是 `CLAUDE.md` §Ratio Convention (B1+B2 模式) 的详细展开, 主章节是 single source of truth, 改动先改 `CLAUDE.md` 再同步本文件**。

## 1. 字段命名 (后端, 强制)

| 后缀 | 数值范围 | 是否已 *100 | 示例 |
|------|----------|-------------|------|
| `*_ratio` | 0-1 decimal | **否** | `old_gsv_ratio`, `member_ratio` |
| `*_pct` | 0-100 percentage | **是** | `gsv_yoy_pct`, `member_penetration_pct` |
| `*_ppt` | -100 ~ +100 pp 差 | **是** | `old_gsv_ratio_yoy_ppt`, `lock_rate_yoy_ppt` |
| `*_rate` | 0-100 percentage | **是** | `repurchase_rate` |
| `*_yoy` / `*_mom` | 按上面 4 种后缀对应 | 视字段而定 | `gsv_yoy` (pct), `old_gsv_ratio_yoy` (ppt) |

## 2. Pydantic 类型 (B2 模式)

| Contract 字段名后缀 | 必须使用的 Pydantic 类型 | 数值范围 |
|---------------------|------------------------|----------|
| `*_ratio` | `RatioField` | 0-1 decimal |
| `*_pct` | `PercentageField` | 0-1B (含 YOY 异常值) |
| `*_ppt` | `PpField` | -100 ~ +100 pp 差 |
| `*_rate` | `PercentageField` (0-100) | 0-100 percentage |
| `List[X]` (X 是约束类型) | `List[Annotated[X, Field(...)]]` | **禁止** `List["X"]` 前向引用 |

## 3. 前端契约 (pass-through)

- `YOYBadge` / `MetricCard` 的 `humanizeChange`: **caller 已 `*100` 传值, 组件只做 `abs + toFixed(2)`**
- `fmtYoy` / `fmtYoY` / `fmtPctChange` 等自定义函数: caller 传已 `*100` 数值, 函数不乘
- **不要在前端 `* 100`**
- `YOYBadge` `unit` 默认 `'%'`, ratio 类必须显式 `unit="pp"`
- `|v|>1e6` 异常值守卫: `humanizeChange` 返 `'数据异常'` (Sprint 16.5 #92 + Sprint 17 #124 扩到 MetricCard)
- None 透传显示 `—` (`humanizeChange` 已加 `v == null` 守卫)

## 4. 反模式 (Sprint 13 P3 / Sprint 17 #121 ground-truth-lint)

| ❌ 反模式 | ✅ 正例 |
|-----------|---------|
| 前端 `* 100` 散落 | caller 自乘, 组件不乘 |
| `*_ratio_yoy` vs `*_yoy_ratio` 混用 | 统一 `*_yoy_ppt` / `*_yoy_pct` |
| `series = [0.0] * len(dates)` hardcode | 数据驱动 |
| pp 字段用 `'0.0"%"'` numFmt | pp 用 `'0.0"pp"'` 字面量后缀 |
| `field: float = Field(...)` 裸 float | `RatioField` / `PercentageField` / `PpField` |
| `List["PercentageField"]` 前向引用 | `List[Annotated[PercentageField, Field(...)]]` |

## 5. 字段命名约定

- **B1 模式** (mark 字段补标 + ETL 反向回填): 详见 `CLAUDE.md` §B1 模式
- **B2 模式** (contract 字段补标 + Pydantic 422 拦截): 详见 `CLAUDE.md` §B2 模式
- **字段后缀选型** (`*_ratio` / `*_pct` / `*_ppt` / `*_rate`): 严格按 §1 + `CLAUDE.md` §字段命名

## 关联文档

- `CLAUDE.md` §"Ratio Convention (B1+B2 模式)" 主章节
- `docs/business/RFM_DEFINITIONS.md` — R/F/M 跟 RFM 8 象限 ratio 模式对照 (L4.8 永久规则, Sprint 60+ 留尾已闭环)
- `backend/contracts/types.py` (`RatioField` / `PercentageField` / `PpField`)
- `backend/semantic/calculations.py` (`yoy_ratio` / `yoy_absolute` / `mom_*`)
- `frontend-vue3/src/components/MetricCard.vue` + `YOYBadge.vue` JSDoc
- `docs/operating/linting.md` — ground-truth-lint 规则

## 6. 强截断模式 (Sprint 60.1.1 实战 + Sprint 27 YOYBadge 模式)

### 6.1 触发场景

业务计算分子分母口径不一致时, ratio 可能 > 1.0 触发 Pydantic 422 验证失败 (B2 `RatioField(0,1)`). 强截断是治本 (业务定义: 该 ratio 不能 > 100%).

### 6.2 Sprint 60.1.1 实战案例

**症状**: `dual_axis_line.wool_party_ratios` 字段值 > 1.0 (实际 3.7593, 21.6751, 1.3461) 触发 Pydantic 422.

**根因**: `_compute_wool_party_breakdown` 算的 `total_wool_count` 是"100% 小样且买过品类 X 的去重用户数" (不应用 `exclude_channels`), 跟 `_compute_value_tier_base` 算的 `total_users` (应用 exclude_channels) 不同口径, 排除低价后分子>分母.

**修本**: `dual_axis_line.wool_party_ratios` 加 `min(round(ratio, 4), 1.0)` 强截断.

```python
# ✅ Sprint 60.1.1 正例: 强截断保持 B2 RatioField(0,1) 范围
wool_party_ratios = [min(round(r, 4), 1.0) for r in wool_party_ratios_raw]
```

**业务定义**: 羊毛党指数 0-1, 业务语义保留 (羊毛党指数不能 > 100%). 跟 Sprint 27 YOYBadge `|v|>1e6` 异常值守卫模式一致.

### 6.3 跟 Sprint 27 YOYBadge `|v|>1e6` 模式对比

| 模式 | 触发 | 修本 | 业务语义 |
|------|------|------|----------|
| **Sprint 27 YOYBadge `|v|>1e6`** | YOY 异常值 (万倍涨) | 守卫返 `'数据异常'` | 异常值过滤 |
| **Sprint 60.1.1 wool_party 强截断** | ratio > 1.0 (口径不一致) | `min(ratio, 1.0)` 强截断 | 业务定义 0-1 |

**两种模式都是治本, 业务语义保留**: 异常值过滤 + 强截断都是"业务合理, 不强求全表 sum=1.0".

## 7. RFM ratio 模式对照 (Sprint 14.5 P1.1 + Sprint 60.2 治本)

### 7.1 R / F / M 区间 (Sprint 14.5 P1.1 治根)

- **ratio 模式**: `ratio = None` (前端 `RFMView.vue:lines` `.filter(r => r.ratio !== null)` 过滤 TTL 行不展示)
- **业务语义**: R/F/M 是"分桶"维度, TTL 是"合计"维度, ratio = 区间 GSV / TTL GSV 会让用户困惑
- **Pydantic 契约**: `Optional[RatioField]` (0-1 or None)

### 7.2 RFM 8 象限 (Sprint 60.2 治本)

- **ratio 模式**: `ratio = 1.0` (TTL 行保留显示, 9 行 sum=2.0 业务合理双计)
- **业务语义**: "合计"行的 ratio = 100% (自己除以自己), 跟"分桶"行 ratio 各自独立 (sum=1.0) 是双计关系
- **Pydantic 契约**: `RatioField` (0-1, TTL 强制 1.0)

### 7.3 两种模式业务合理

R/F/M 隐藏合计 (避免分桶 + 合计视觉混淆) + RFM 8 象限保留合计 (合计 = 8 象限和, 业务对账需要), 跟 Sprint 60.1.1 wool_party 强截断模式一致 (ratio 各自 0-1 合规).

**详见** `docs/business/RFM_DEFINITIONS.md` §4 ratio 模式对照.