"""
芙清 CRM - 语义层 (Semantic Layer)

统一管理业务口径、计算逻辑、维度定义和人群分层。
所有 Service 层的 SQL 构造必须通过本层提供的 API，禁止硬编码过滤条件。

核心模块:
- filters:      SQL 过滤条件构造器（GSV/GMV、时间范围、新老客等）
- metrics:      指标注册表（统一定义每个指标的名称、公式、口径）
- calculations: 统一计算规则（YOY、占比、MOM 等，所有 Service 必须调用此模块）
- dimensions:    维度定义（channel、spu_tier、province 等）
- segments:     人群分层定义（11象限、新老客、会员等）
- channels:     渠道漏斗定义（9层渠道判定规则文档化）
- time:         时间范围构造器（MTD、同比、环比、自由模式）
"""

from .filters import FilterBuilder, OrderFilters, MetricType
from .metrics import MetricRegistry, MetricDefinition
from .calculations import (
    yoy_absolute,
    yoy_ratio,
    yoy_repurchase_rate,
    mom_absolute,
    mom_ratio,
    safe_ratio,
    GSV_AMOUNT_COL,
)
from .dimensions import DimensionRegistry, DimensionDefinition
from .segments import (
    SegmentRegistry, SegmentDefinition, RFM_THRESHOLDS,
    R_SEGMENT_ORDER, F_SEGMENT_ORDER, M_SEGMENT_ORDER,
    R_INTERVALS, segment_meta,
)
from .channels import CHANNEL_FUNNEL, CHANNEL_PRIORITY
from .time import PeriodBuilder, DateRange

__all__ = [
    # filters
    "FilterBuilder",
    "OrderFilters",
    "MetricType",
    # metrics
    "MetricRegistry",
    "MetricDefinition",
    # calculations（所有 Service 必须使用此处函数，禁止自行定义）
    "yoy_absolute",
    "yoy_ratio",
    "yoy_repurchase_rate",
    "mom_absolute",
    "mom_ratio",
    "safe_ratio",
    "GSV_AMOUNT_COL",
    # dimensions
    "DimensionRegistry",
    "DimensionDefinition",
    # segments
    "SegmentRegistry",
    "SegmentDefinition",
    "RFM_THRESHOLDS",
    "R_SEGMENT_ORDER",
    "F_SEGMENT_ORDER",
    "M_SEGMENT_ORDER",
    "R_INTERVALS",
    "segment_meta",
    # channels
    "CHANNEL_FUNNEL",
    "CHANNEL_PRIORITY",
    # time
    "PeriodBuilder",
    "DateRange",
]
