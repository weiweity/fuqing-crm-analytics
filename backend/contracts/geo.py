"""芙清 CRM - Pydantic 契约模型"""
from typing import List, Any, Dict
from pydantic import BaseModel

class GeoDistributionItem(BaseModel):
    name: str
    user_count: int
    gmv: float
    user_ratio: float
    gmv_ratio: float


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

