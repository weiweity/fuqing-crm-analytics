"""品类分析服务 - 复购分析"""
import duckdb
from typing import Dict, Any, Optional, List

from backend.db.connection import get_connection
from backend.semantic.filters import OrderFilters, expand_channels
from backend.semantic.calculations import yoy_absolute, yoy_ratio
from backend.semantic.segments import RFM_THRESHOLDS

from .._shared import (
    SPU_LEVELS,
    _RFM_SEGMENT_ORDER,
    _resolve_repurchase_date_ranges,
)


def get_category_repurchase_flow(
    start_date: str,
    end_date: str,
    category: str,
    level: str = "class",
    metric_type: str = "GSV",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    品类回购分析主接口
    同品回购 + 跨品类回购，RFM 8象限分群，3年同比
    """
    if level not in SPU_LEVELS:
        raise ValueError(f"Invalid level: {level}")
    category_field = SPU_LEVELS[level]

    ranges = _resolve_repurchase_date_ranges(start_date, end_date)
    cur_start, cur_end, cutoff = ranges["current"]
    comp_start, comp_end, comp_cutoff = ranges["comp"]
    prev2_start, prev2_end, prev2_cutoff = ranges["prev2"]
    year_label, comp_label, prev2_label = ranges["labels"]

    conn = get_connection()
    try:
        # 当前年
        cur_same, cur_cross, cur_m_same, cur_m_cross = _run_category_repurchase_period(
            conn, cur_start, cur_end, cutoff, category, category_field, metric_type, channel, exclude_channels
        )
        # 去年
        comp_same, comp_cross, comp_m_same, comp_m_cross = _run_category_repurchase_period(
            conn, comp_start, comp_end, comp_cutoff, category, category_field, metric_type, channel, exclude_channels
        )
        # 前年
        prev2_same, prev2_cross, prev2_m_same, prev2_m_cross = _run_category_repurchase_period(
            conn, prev2_start, prev2_end, prev2_cutoff, category, category_field, metric_type, channel, exclude_channels
        )
    finally:
        conn.close()

    def _build_rows(cur_data, comp_data, prev2_data):
        rows = []
        for seg in _RFM_SEGMENT_ORDER:
            c = cur_data.get(seg, {})
            p = comp_data.get(seg, {})
            p2 = prev2_data.get(seg, {})
            rows.append({
                "rfm_segment": seg,
                "hist_users_current": c.get("hist_users", 0),
                "repurchase_users_current": c.get("repurchase_users", 0),
                "repurchase_rate_current": round(c.get("repurchase_rate", 0.0), 4),
                "repurchase_gsv_current": round(c.get("repurchase_gsv", 0.0), 2),
                "repurchase_gsv_ratio_current": round(c.get("repurchase_gsv_ratio", 0.0), 4),
                "hist_users_comp": p.get("hist_users", 0),
                "repurchase_rate_comp": round(p.get("repurchase_rate", 0.0), 4),
                "hist_users_prev2": p2.get("hist_users", 0),
                "repurchase_rate_prev2": round(p2.get("repurchase_rate", 0.0), 4),
                "yoy_hist_users": yoy_absolute(c.get("hist_users", 0), p.get("hist_users", 0)),
                "yoy_repurchase_users": yoy_absolute(c.get("repurchase_users", 0), p.get("repurchase_users", 0)),
                "yoy_repurchase_rate": yoy_ratio(c.get("repurchase_rate", 0.0), p.get("repurchase_rate", 0.0)),
                "yoy_repurchase_gsv": yoy_absolute(c.get("repurchase_gsv", 0.0), p.get("repurchase_gsv", 0.0)),
                "yoy_repurchase_gsv_ratio": yoy_ratio(c.get("repurchase_gsv_ratio", 0.0), p.get("repurchase_gsv_ratio", 0.0)),
            })
        return rows

    return {
        "year_label": year_label,
        "comp_year_label": comp_label,
        "prev2_year_label": prev2_label,
        "target_category": category,
        "same_category_rows": _build_rows(cur_same, comp_same, prev2_same),
        "cross_category_rows": _build_rows(cur_cross, comp_cross, prev2_cross),
        "member_same_category_rows": _build_rows(cur_m_same, comp_m_same, prev2_m_same),
        "member_cross_category_rows": _build_rows(cur_m_cross, comp_m_cross, prev2_m_cross),
    }

def get_category_repurchase_flow_by_rfm(
    start_date: str,
    end_date: str,
    category: str,
    level: str = "class",
    metric_type: str = "GSV",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    历史老客回购分析主接口（RFM 8象限分群，不限品类）
    同品回购 + 跨品类回购，3年同比
    """
    if level not in SPU_LEVELS:
        raise ValueError(f"Invalid level: {level}")
    category_field = SPU_LEVELS[level]

    ranges = _resolve_repurchase_date_ranges(start_date, end_date)
    cur_start, cur_end, cutoff = ranges["current"]
    comp_start, comp_end, comp_cutoff = ranges["comp"]
    prev2_start, prev2_end, prev2_cutoff = ranges["prev2"]
    year_label, comp_label, prev2_label = ranges["labels"]

    conn = get_connection()
    try:
        # 当前年
        cur_same, cur_cross, cur_m_same, cur_m_cross = _run_category_repurchase_period_by_rfm(
            conn, cur_start, cur_end, cutoff, category, category_field, metric_type, channel, exclude_channels
        )
        # 去年
        comp_same, comp_cross, comp_m_same, comp_m_cross = _run_category_repurchase_period_by_rfm(
            conn, comp_start, comp_end, comp_cutoff, category, category_field, metric_type, channel, exclude_channels
        )
        # 前年
        prev2_same, prev2_cross, prev2_m_same, prev2_m_cross = _run_category_repurchase_period_by_rfm(
            conn, prev2_start, prev2_end, prev2_cutoff, category, category_field, metric_type, channel, exclude_channels
        )
    finally:
        conn.close()

    def _build_rows(cur_data, comp_data, prev2_data):
        rows = []
        for seg in _RFM_SEGMENT_ORDER:
            c = cur_data.get(seg, {})
            p = comp_data.get(seg, {})
            p2 = prev2_data.get(seg, {})
            rows.append({
                "rfm_segment": seg,
                "hist_users_current": c.get("hist_users", 0),
                "repurchase_users_current": c.get("repurchase_users", 0),
                "repurchase_rate_current": round(c.get("repurchase_rate", 0.0), 4),
                "repurchase_gsv_current": round(c.get("repurchase_gsv", 0.0), 2),
                "repurchase_gsv_ratio_current": round(c.get("repurchase_gsv_ratio", 0.0), 4),
                "hist_users_comp": p.get("hist_users", 0),
                "repurchase_rate_comp": round(p.get("repurchase_rate", 0.0), 4),
                "hist_users_prev2": p2.get("hist_users", 0),
                "repurchase_rate_prev2": round(p2.get("repurchase_rate", 0.0), 4),
                "yoy_hist_users": yoy_absolute(c.get("hist_users", 0), p.get("hist_users", 0)),
                "yoy_repurchase_users": yoy_absolute(c.get("repurchase_users", 0), p.get("repurchase_users", 0)),
                "yoy_repurchase_rate": yoy_ratio(c.get("repurchase_rate", 0.0), p.get("repurchase_rate", 0.0)),
                "yoy_repurchase_gsv": yoy_absolute(c.get("repurchase_gsv", 0.0), p.get("repurchase_gsv", 0.0)),
                "yoy_repurchase_gsv_ratio": yoy_ratio(c.get("repurchase_gsv_ratio", 0.0), p.get("repurchase_gsv_ratio", 0.0)),
            })
        return rows

    return {
        "year_label": year_label,
        "comp_year_label": comp_label,
        "prev2_year_label": prev2_label,
        "target_category": category,
        "same_category_rows": _build_rows(cur_same, comp_same, prev2_same),
        "cross_category_rows": _build_rows(cur_cross, comp_cross, prev2_cross),
        "member_same_category_rows": _build_rows(cur_m_same, comp_m_same, prev2_m_same),
        "member_cross_category_rows": _build_rows(cur_m_cross, comp_m_cross, prev2_m_cross),
    }
