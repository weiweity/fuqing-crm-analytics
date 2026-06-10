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
"""
from typing import Annotated
from pydantic import Field

# 0-1 decimal (e.g. 0.42 = 42%, 旧名 *_ratio)
RatioField = Annotated[
    float,
    Field(ge=0.0, le=1.0, description="0-1 decimal (e.g. 0.42 = 42%), 4 位精度"),
]

# 0-100 percentage (e.g. 42.0 = 42%, 旧名 *_pct, 已 *100)
PercentageField = Annotated[
    float,
    Field(ge=0.0, le=100.0, description="0-100 percentage (e.g. 42.0 = 42%), 2 位精度"),
]

# -100 ~ +100 pp 差 (e.g. 5.28 = +5.28pp, 旧名 *_ppt / *_yoy_ppt, 已 *100)
PpField = Annotated[
    float,
    Field(ge=-100.0, le=100.0, description="pp 差 -100~+100 (e.g. 5.28 = +5.28pp), 2 位精度"),
]
