"""Sprint 14 Stage 2 Pydantic 契约自定义类型 (ratio/percentage/pp 三种)

背景: Sprint 13 ratio 治理后, 后端 ratio/pct/ppt 字段在 API 层无 validator, 错值无
法在 API 入口拦截 (e.g. ratio 字段传 5.0, 应返 422 ValidationError 而非 500).

Sprint 14 拍板 (A.1 方案): 用 Pydantic v2 Annotated + Field(ge/le) 做 3 个自定义类型,
替换 backend/contracts/audience.py:146-215 + metrics.py:19-23 等 6 个 contract 文件中
的 float = Field(...) 字段.

数值范围约定 (跟 CLAUDE.md "Ratio Convention (Sprint 13+)" 一致):
  RatioField       0-1 decimal (e.g. 0.42 = 42%)         ratio/decimal
  PercentageField  0-100 percentage (e.g. 42.0 = 42%)    pct/已 *100
  PpField          -100 ~ +100 pp 差 (e.g. 5.28 = +5.28pp) ppt/已 *100

注意: Pydantic 2 的 `decimal_places` 约束不支持 float 类型 (限制), 改用 description
描述精度, 不在类型层强约束. 精度约束在 caller 端 (后端 service 层 round(2/4)) 保证.

Sprint 14 QA 修 (2026-06-10): 9620 个 validator 越界 — service 端 yoy_absolute 已 *100
返 percentage (e.g. 117829.76 = 1178.29% YOY), 超出 PercentageField 0-100 范围. 临时
放宽 PercentageField 上限到 1_000_000 (允许 YOY 千倍异常值), 留 Sprint 14.5 治根
(service 改 yoy_absolute 不 *100 OR 加 normalized 字段).

Sprint 15 治根 (2026-06-11): 用户排查品类看板占比 YOY 时, 25 期间单拉 endpoint
返 500 — 真实 gsv_yoy 值 1,157,823.86% 越界 1M 上限. /autoplan 4 phase review 后
user 拍 A 修法 (放宽到 1B). 跟 Sprint 14 QA 0-1M 退让一致, 进一步放宽到 0-1B 兼容
yoy_absolute 万倍异常值 (eg. 新品类从 0 涨到有量, 涨 1 万倍仍合理).
"""
from typing import Annotated
from pydantic import Field

# 0-1 decimal (e.g. 0.42 = 42%, 旧名 *_ratio) — Sprint 13 契约严守, 0-1 不放宽
RatioField = Annotated[
    float,
    Field(ge=0.0, le=1.0, description="0-1 decimal (e.g. 0.42 = 42%), 4 位精度"),
]

# 0-100 percentage (e.g. 42.0 = 42%, 旧名 *_pct, 已 *100)
# Sprint 14 QA 修 (2026-06-10): 上限放宽到 ±1M, 兼容 yoy_absolute *100 后 percentage
#   (e.g. -50.0 负 YOY 或 1178.29% 千倍异常值)
# Sprint 15 治根 (2026-06-11): 上限进一步放宽到 ±1B, 兼容 yoy_absolute *100 后万倍异常值
#   (eg. 新品类从 0 涨到有量, 涨 1 万倍仍合理). /autoplan 4 phase review + user 拍 A.
#   Sprint 13 治理契约 0-100 严守保留, 0-1B 仅作为 yoy_absolute 兼容兜底.
#   前端 YOYBadge 加异常值守卫 (abs(v) > 1e6 → "数据异常") 防止 UI 误导.
PercentageField = Annotated[
    float,
    Field(ge=-1_000_000_000.0, le=1_000_000_000.0, description="0-100 percentage 或 yoy_absolute *100 后 ±1B 范围 (含负 YOY + 万倍异常值), 2 位精度. 真实值 > 1e6 建议前端 YOYBadge 守卫"),
]

# -100 ~ +100 pp 差 (e.g. 5.28 = +5.28pp, 旧名 *_ppt / *_yoy_ppt, 已 *100)
PpField = Annotated[
    float,
    Field(ge=-100.0, le=100.0, description="pp 差 -100~+100 (e.g. 5.28 = +5.28pp), 2 位精度"),
]
