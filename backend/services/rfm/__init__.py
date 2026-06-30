"""
Sample CRM - RFM 专项服务包

按 R/F/M 维度拆分的区间流转看板。
"""

from backend.services.rfm._shared import _resolve_date_ranges
from backend.semantic.segments import R_SEGMENT_ORDER, F_SEGMENT_ORDER, M_SEGMENT_ORDER
from backend.services.rfm._flow_engine import run_flow_period, get_rfm_flow
from backend.services.rfm.r_flow import _run_r_flow_period, get_rfm_r_flow
from backend.services.rfm.f_flow import _run_f_flow_period, get_rfm_f_flow
from backend.services.rfm.m_flow import _run_m_flow_period, get_rfm_m_flow
from backend.services.rfm.extended import get_user_rfm_extended
from backend.services.rfm.cache import RfmQueryCache  # W5 v0.4.13

__all__ = [
    "_resolve_date_ranges",
    "R_SEGMENT_ORDER", "F_SEGMENT_ORDER", "M_SEGMENT_ORDER",
    "run_flow_period", "get_rfm_flow",
    "_run_r_flow_period", "get_rfm_r_flow",
    "_run_f_flow_period", "get_rfm_f_flow",
    "_run_m_flow_period", "get_rfm_m_flow",
    "get_user_rfm_extended",
    "RfmQueryCache",
]
