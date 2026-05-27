"""
芙清 CRM - 核心指标计算服务（薄包装层）
实际实现已拆分到 backend/services/metrics/ 包中。

向后兼容：
  from backend.services.metrics_service import get_overview_metrics
  from backend.services.metrics import get_overview_metrics
"""

from backend.services.metrics._shared import _get_conn, _expand_channel  # noqa: F401
from backend.services.metrics.overview import (  # noqa: F401
    calculate_metrics, calculate_new_old_users, calculate_member_metrics,
    get_overview_metrics, get_daily_trend, get_product_metrics,
)
from backend.services.metrics.audience_table import get_audience_table  # noqa: F401
from backend.services.metrics.audience_summary import calculate_audience_summary  # noqa: F401
