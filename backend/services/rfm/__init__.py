"""
芙清 CRM - RFM 专项服务包

按 R/F/M 维度拆分的区间流转看板。
"""

from backend.services.rfm._shared import (
    _resolve_date_ranges,
    R_SEGMENT_ORDER, F_SEGMENT_ORDER, M_SEGMENT_ORDER,
)
from backend.services.rfm.r_flow import _run_r_flow_period, get_rfm_r_flow
from backend.services.rfm.f_flow import _run_f_flow_period, get_rfm_f_flow
from backend.services.rfm.m_flow import _run_m_flow_period, get_rfm_m_flow
from backend.services.rfm.segment_orders import get_segment_orders

__all__ = [
    "_resolve_date_ranges",
    "R_SEGMENT_ORDER", "F_SEGMENT_ORDER", "M_SEGMENT_ORDER",
    "_run_r_flow_period", "get_rfm_r_flow",
    "_run_f_flow_period", "get_rfm_f_flow",
    "_run_m_flow_period", "get_rfm_m_flow",
    "get_segment_orders",
]
