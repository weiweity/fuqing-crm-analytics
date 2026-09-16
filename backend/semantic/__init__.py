"""
Sample CRM - 语义层 (Semantic Layer)

统一管理业务口径、计算逻辑、维度定义和人群分层。
所有 Service 层的 SQL 构造必须通过本层提供的 API，禁止硬编码过滤条件。

核心模块:
- filters:      SQL 过滤条件构造器（GSV/GMV、时间范围、渠道等）
- calculations: YOY / GSV 谓词（所有 Service 必须调用，禁止自写 YOY）
- time:         PeriodBuilder（MTD、YTD、季度、近 N 天）
- channels:     渠道漏斗与 UI↔DB 别名
- segments:     RFM 8 象限、R 桶、新老客辅助 SQL
- metrics:      指标目录，未接入查询；出数 SQL 以各 service 为准
- dimensions:   维度目录，未接入查询；品类层用 service 内 SPU_LEVELS
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
