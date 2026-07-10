"""Sprint 14 Stage 2 Pydantic 契约自定义类型 (ratio/percentage/pp 三种) — L4.81 治本 no *100 契约

背景: Sprint 13 ratio 治理后, 后端 ratio/pct/ppt 字段在 API 层无 validator, 错值无
法在 API 入口拦截 (e.g. ratio 字段传 5.0, 应返 422 ValidationError 而非 500).

Sprint 14 拍板 (A.1 方案): 用 Pydantic v2 Annotated + Field(ge/le) 做 3 个自定义类型,
替换 backend/contracts/audience.py:146-215 + metrics.py:19-23 等 6 个 contract 文件中
的 float = Field(...) 字段.

L4.81 治本契约 (user 7/10 拍板 "我需要的是 pp, 然后不要 *100"):
  RatioField       0-1 decimal (e.g. 0.42 = 42%, frontend *100 显示)         ratio/decimal
  PercentageField  0-1 raw ratio (e.g. 0.42, frontend *100 显示 = 42%)      pct/no *100
  PpField          -1 ~ +1 raw ratio diff (e.g. 0.05, frontend *100 显示 = 5pp) ppt/no *100

注意: Pydantic 2 的 `decimal_places` 约束不支持 float 类型 (限制), 改用 description
描述精度, 不在类型层强约束. 精度约束在 caller 端 (后端 service 层 round(2/4)) 保证.

Sprint 14/15 治根历史 (已废, 跟 L4.81 1:1 stable 沿用 no *100 契约):
- Sprint 14 QA 修: PercentageField 上限放宽到 ±1M (兼容 yoy_absolute *100 后 percentage)
- Sprint 15 治根: 上限进一步放宽到 ±1B (兼容 yoy_absolute *100 后万倍异常值)
- Sprint 16.5 #92: 前端 YOYBadge 加异常值守卫 (abs(v) > 1e6 → "数据异常")
- L4.81 (本次): backend yoy_absolute/yoy_ratio 改 no *100, frontend 必 *100 显示
"""
from typing import Annotated
from pydantic import Field

# 0-1 decimal (e.g. 0.42 = 42%, 旧名 *_ratio) — Sprint 13 契约严守, 0-1 不放宽
RatioField = Annotated[
    float,
    Field(ge=0.0, le=1.0, description="0-1 decimal (e.g. 0.42 = 42%), 4 位精度"),
]

# L4.81 治本契约: 0-1 raw ratio (no *100, frontend caller 必 *100 显示 = percentage)
# 兼容旧字段: 历史 *_pct 字段 (已 *100) 可通过 *100 转 raw 适配
# 上限 ±1e10 兼容 yoy_absolute 万倍异常值 (eg. 新品类从 0 涨到有量, 涨 1 万倍 ratio = 1e4, frontend 显示 1e6% / 100 = 1e6)
PercentageField = Annotated[
    float,
    Field(ge=-1e10, le=1e10, description="L4.81 治本契约: 0-1 raw ratio (no *100, frontend caller 必 *100 显示 = percentage, e.g. 0.42 = 42%). 上限 ±1e10 兼容 yoy_absolute 万倍异常值, 4 位精度. 真实值 |v| > 100 建议前端 YOYBadge 守卫 (\"数据异常\"). 旧契约已 *100 字段请先 *0.01 转 raw"),
]

# L4.81 治本契约: -1 ~ +1 raw ratio diff (no *100, frontend caller 必 *100 显示 = pp)
PpField = Annotated[
    float,
    Field(ge=-1e10, le=1e10, description="L4.81 治本契约: -1 ~ +1 raw ratio diff (no *100, frontend caller 必 *100 显示 = pp, e.g. 0.05 = +5pp). 上限 ±1e10 兼容 yoy_ratio 万倍异常值, 4 位精度. 真实值 |v| > 100 建议前端 YOYBadge 守卫 (\"数据异常\"). 旧契约已 *100 字段请先 *0.01 转 raw"),
]
