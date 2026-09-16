"""Sample CRM - Pydantic 契约模型"""
from __future__ import annotations
from typing import Optional, List, Dict, Annotated
from pydantic import BaseModel, Field
from .types import RatioField
# WoolPartyBreakdown.high_risk_ratio 在 service 层钳到 0-1

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
    wool_party_ratios: List[Annotated[float, Field(ge=0.0, le=1.0, description="0-1 decimal 羊毛高风险占比")]]
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
    """羊毛风险：用户级证据分的品类聚合，不是窗口 100% 小样布尔。"""
    high_risk_count: int = Field(..., description="score>=0.70 的用户数")
    mean_score: float = Field(..., ge=0.0, le=1.0, description="平均风险分 0-1")
    never_converted_count: int = Field(..., description="截止窗口末日从未买正装")
    converted_then_sample_count: int = Field(..., description="曾买正装、窗口内仍 100% 小样")
    sample_only_window_count: int = Field(..., description="窗口内 100% 小样")
    scored_users: int = Field(..., description="参与计分的窗口用户数")
    high_risk_ratio: RatioField = Field(..., description="高风险人数 / 品类人数, 已钳到 0-1")

