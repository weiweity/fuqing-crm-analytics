"""芙清 CRM - Pydantic 契约模型"""
from __future__ import annotations
from typing import List, Any, Dict
from pydantic import BaseModel
from .types import RatioField, PercentageField, PpField  # Sprint 17 B2 全量 audit

class GeoDistributionItem(BaseModel):
    name: str
    user_count: int
    gmv: float
    # Sprint 17 B2 全量 audit: 2 个 0-1 decimal ratio 字段补 RatioField 标注
    user_ratio: "RatioField"
    gmv_ratio: "RatioField"


class GeoDistributionResponse(BaseModel):
    date: str
    level: str
    total_users: int
    total_gmv: float
    distribution: List[GeoDistributionItem]


class GeoSegmentMatrixResponse(BaseModel):
    date: str
    matrix: Dict[str, List[Dict[str, Any]]]
    segments: List[Dict[str, Any]]


class GeoTrendResponse(BaseModel):
    time_points: List[str]
    top_provinces: List[str]
    trends: Dict[str, Any]

