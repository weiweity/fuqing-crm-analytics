"""Sample CRM - Pydantic 契约模型"""
from __future__ import annotations
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from typing import Annotated
# WoolPartyBreakdown.type1/2_ratio 已用 float (跨品类可超 1) - 不需要 RatioField

class DateRangeResponse(BaseModel):
    start: str
    end: str
    cutoff: Optional[str] = None

class YearComparisonRow(BaseModel):
    """30指标对比表格的一行（年份动态）"""
    field: str
    kind: str = "money"           # 指标类型: money | ratio | count | aus
    values_by_year: Dict[str, Optional[float]] = {}  # {"2026": 123.4, "2025": 100.0, ...}
    yoy: Optional[float] = None    # 最近年份相对上一年的 YOY

class DualAxisLineData(BaseModel):
    """双轴折线图数据"""
    categories: List[str]
    # Sprint 17 B2 全量 audit: List[RatioField] 必须用 Annotated 才能触发 element-wise 约束
    wool_party_ratios: List[Annotated[float, Field(ge=0.0, le=1.0, description="0-1 decimal 羊毛党占比")]]
    high_value_ratios: List[Annotated[float, Field(ge=0.0, le=1.0, description="0-1 decimal 高价值用户占比")]]

class SankeyNode(BaseModel):
    """桑基图节点"""
    name: str
    category_name: str


class SankeyLink(BaseModel):
    """桑基图连线"""
    source: str
    target: str
    value: int


class SankeyGraphData(BaseModel):
    """桑基图数据"""
    nodes: List[SankeyNode]
    links: List[SankeyLink]


class WoolPartyBreakdown(BaseModel):
    """羊毛党细分统计"""
    type1_count: int  # 历史有正装，后续一直买小样
    type2_count: int  # 历史只买小样
    total_count: int
    # type1/2_ratio = count / total_users (品类级), 可超 1 (单用户跨多品类)
    type1_ratio: float = Field(..., description="type1 人数 / 品类总人数, 0-1 decimal, 可超 1")
    type2_ratio: float = Field(..., description="type2 人数 / 品类总人数, 0-1 decimal, 可超 1")

