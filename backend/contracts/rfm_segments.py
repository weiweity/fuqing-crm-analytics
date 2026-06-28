"""Sprint 142 RFM 扩展维度（生命周期 / 价值层 / 潜力层）."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class LifecycleStage(str, Enum):
    """用户生命周期阶段."""

    NEW = "新客"
    ACTIVE = "活跃客"
    DORMANT = "沉睡客"
    CHURNED = "流失客"


class ValueTier(str, Enum):
    """用户价值层."""

    HIGH = "高价值"
    MEDIUM = "中价值"
    LOW = "低价值"


class PotentialTier(str, Enum):
    """用户潜力层."""

    HIGH = "高潜力"
    MEDIUM = "中潜力"
    LOW = "低潜力"


class RFMSegmentExtended(BaseModel):
    """RFM 扩展分群（保留 8 quadrant, 增量追加 3 个新维度）."""

    user_id: str = Field(..., description="用户 ID")
    rfm_quadrant: str = Field(..., description="8 quadrant 经典分割")
    lifecycle_stage: LifecycleStage = Field(..., description="生命周期阶段")
    value_tier: ValueTier = Field(..., description="价值层")
    potential_tier: PotentialTier = Field(..., description="潜力层")


class RFMExtendedRequest(BaseModel):
    """RFM 扩展分群请求."""

    user_ids: List[str] = Field(..., min_length=1, description="用户 ID 列表")
    as_of_date: Optional[str] = Field(default=None, description="分析日期 YYYY-MM-DD")


class RFMExtendedResponse(BaseModel):
    """RFM 扩展分群响应."""

    segments: List[RFMSegmentExtended] = Field(default_factory=list)
