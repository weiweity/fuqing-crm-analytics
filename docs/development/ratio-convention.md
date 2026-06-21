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
- `backend/contracts/types.py` (`RatioField` / `PercentageField` / `PpField`)
- `backend/semantic/calculations.py` (`yoy_ratio` / `yoy_absolute` / `mom_*`)
- `frontend-vue3/src/components/MetricCard.vue` + `YOYBadge.vue` JSDoc
- `docs/operating/linting.md` — ground-truth-lint 规则