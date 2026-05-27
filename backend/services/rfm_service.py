"""
芙清 CRM - RFM 专项服务（向后兼容）

本文件已重构为 backend/services/rfm/ 包。
所有导入从新包重导出，保持向后兼容。
"""

from backend.services.rfm import (
    _resolve_date_ranges,
    R_SEGMENT_ORDER, F_SEGMENT_ORDER, M_SEGMENT_ORDER,
    _run_r_flow_period, get_rfm_r_flow,
    _run_f_flow_period, get_rfm_f_flow,
    _run_m_flow_period, get_rfm_m_flow,
    get_segment_orders,
)

__all__ = [
    "_resolve_date_ranges",
    "R_SEGMENT_ORDER", "F_SEGMENT_ORDER", "M_SEGMENT_ORDER",
    "_run_r_flow_period", "get_rfm_r_flow",
    "_run_f_flow_period", "get_rfm_f_flow",
    "_run_m_flow_period", "get_rfm_m_flow",
    "get_segment_orders",
]
