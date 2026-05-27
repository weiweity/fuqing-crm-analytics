"""芙清 CRM - Pydantic 契约模型"""
from typing import Optional, List
from pydantic import BaseModel

class DateRangeResponse(BaseModel):
    start: str
    end: str
    cutoff: Optional[str] = None

class YearComparisonRow(BaseModel):
    """30指标对比表格的一行"""
    field: str
    kind: str = "money"           # 指标类型: money | ratio | count | aus
    value_2026: Optional[float] = None
    value_2025: Optional[float] = None
    value_2024: Optional[float] = None
    yoy: Optional[float] = None    # 相对2025的YOY

class DualAxisLineData(BaseModel):
    """双轴折线图数据"""
    categories: List[str]
    wool_party_ratios: List[float]
    high_value_ratios: List[float]

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
    type1_ratio: float
    type2_ratio: float

