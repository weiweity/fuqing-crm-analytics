"""
芙清 CRM - RFM F 区间流转

F 维度：按历史购买频次（frequency）分段。
配置驱动，核心逻辑在 _flow_engine 中。
"""

from typing import Any, Dict, List, Optional

from backend.semantic.segments import F_SEGMENT_ORDER
from backend.services.rfm._flow_engine import run_flow_period, get_rfm_flow

# ── F 维度配置 ──
_F_SEGMENTATION_CTE = """
    segmented_customers AS (
        SELECT
            user_id,
            channel_flag,
            is_member,
            CASE
                WHEN frequency = 1 THEN '1次购买'
                WHEN frequency = 2 THEN '2次购买'
                WHEN frequency = 3 THEN '3次购买'
                WHEN frequency = 4 THEN '4次购买'
                ELSE '5次及以上'
            END AS f_segment
        FROM hist_customers
    )
"""

# ── 公共接口（向后兼容）──

def _run_f_flow_period(
    conn, start_dt, end_dt, cutoff_dt,
    channel=None, metric_type="GSV", exclude_channels=None,
):
    """F 维度单周期流转（委托引擎）。"""
    return run_flow_period(
        conn, start_dt, end_dt, cutoff_dt,
        dimension="f",
        segment_order=F_SEGMENT_ORDER,
        hist_extra_cols="COUNT(*) AS frequency",
        segmentation_cte=_F_SEGMENTATION_CTE,
        channel=channel,
        metric_type=metric_type,
        exclude_channels=exclude_channels,
    )


def get_rfm_f_flow(
    year: int = 2026,
    metric_type: str = "GSV",
    period: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
    compare_start_date: Optional[str] = None,
    compare_end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """F 区间流转看板接口（委托引擎）。"""
    return get_rfm_flow(
        dimension="f",
        segment_order=F_SEGMENT_ORDER,
        hist_extra_cols="COUNT(*) AS frequency",
        segmentation_cte=_F_SEGMENTATION_CTE,
        year=year,
        metric_type=metric_type,
        period=period,
        start_date=start_date,
        end_date=end_date,
        channel=channel,
        exclude_channels=exclude_channels,
        compare_start_date=compare_start_date,
        compare_end_date=compare_end_date,
    )
