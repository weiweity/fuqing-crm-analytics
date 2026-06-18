"""Sample CRM - Pydantic 契约模型

Sprint 36-6: 删 FlowSankeyResponse (前端 0 + 后端 0 业务消费, S36-1 留尾闭环).
保留 SankeyNode/SankeyLink/CategoryFlowResponse 等 (category 路由在用).
"""
from __future__ import annotations
from typing import Optional, List, Any, Dict
from enum import Enum
from pydantic import BaseModel, Field
from .types import RatioField  # Sprint 17 B2 全量 audit
class FlowMatrixResponse(BaseModel):
    flow_matrix: List[Dict[str, Any]]
    segments: List[Dict[str, Any]]
    from_date: str
    to_date: str
    from_total: int
    to_total: int
    summary: Dict[str, float]


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


class FlowMatrixCell(BaseModel):
    """流转矩阵单元格"""
    source_category: str
    target_category: str
    user_count: int
    # Sprint 17 B2 全量 audit: 0-1 decimal ratio 字段补 RatioField 标注
    ratio: "RatioField"
    concentration_risk: bool  # True if TOP1来源占比>60%


class FlowMatrix(BaseModel):
    """品类流转矩阵"""
    sources: List[str]
    targets: List[str]
    matrix: List[List[int]]
    row_totals: List[int] = Field(default_factory=list, description="每行流转人数总和，用于前端计算行百分比")
    concentration_warnings: List[str]


class AssociationItem(BaseModel):
    """关联品类项"""
    category_name: str
    user_count: int
    order_count: int
    gsv: float
    # Sprint 17 B2 全量 audit: 0-1 decimal ratio 字段补 RatioField 标注
    ratio: "RatioField"  # 占该品类购买用户的比例 (0-1 decimal)
    avg_days_gap: float  # 与目标品类的平均购买间隔天数


class CategoryFlowResponse(BaseModel):
    """品类流转 Tab 响应（兼容旧接口）"""
    sankey_data: SankeyGraphData
    matrix: FlowMatrix
    data_stale: bool = False
    data_quality_note: str
    # 时序关联分析(当传入 target_category 时填充)
    target_category: Optional[str] = None
    post_purchase: Optional[List[AssociationItem]] = None  # 买A之后买了什么
    pre_purchase: Optional[List[AssociationItem]] = None   # 买A之前买了什么
    # 前后置流转桑基图(当传入 target_category 时填充)
    pre_sankey: Optional[SankeyGraphData] = None   # 前置流转：其他品类 → 目标品类
    post_sankey: Optional[SankeyGraphData] = None  # 后置流转：目标品类 → 其他品类


class CategoryFlowAssociationResponse(BaseModel):
    """品类流转 - 时序关联分析响应"""
    target_category: str
    post_purchase: List[AssociationItem] = Field(default_factory=list)
    pre_purchase: List[AssociationItem] = Field(default_factory=list)
    post_sankey: SankeyGraphData = Field(default_factory=lambda: SankeyGraphData(nodes=[], links=[]))
    pre_sankey: SankeyGraphData = Field(default_factory=lambda: SankeyGraphData(nodes=[], links=[]))
    data_quality_note: str = ""


class CategoryFlowMatrixResponse(BaseModel):
    """品类流转 - 全局流转矩阵响应"""
    sankey_data: SankeyGraphData
    matrix: FlowMatrix
    data_stale: bool = False
    data_quality_note: str = ""


class AnchorMode(str, Enum):
    """锚点模式：以目标品类的哪次购买为分析锚点"""
    first = "first"   # 首次购买（分析期间内第一次买A）
    last = "last"     # 末次购买（分析期间内最后一次买A）
    every = "every"   # 每次购买（按购买事件统计，非按用户去重）


class PathDepth(str, Enum):
    """路径深度：时序关联分析的探索步数"""
    d1 = "1"   # 1步：直接前后置关联
    d2 = "2"   # 2步：再向外延伸一层（A→B→C）

