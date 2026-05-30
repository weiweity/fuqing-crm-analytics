"""
芙清 CRM - RFM R 区间流转

R 维度：按最近购买时间（recency_days）分段。
配置驱动，核心逻辑在 _flow_engine 中。
"""

from typing import Any, Dict, List, Optional

from backend.semantic.segments import R_SEGMENT_ORDER
from backend.services.rfm._flow_engine import run_flow_period, get_rfm_flow

# ── R 维度配置 ──
_R_SEGMENTATION_CTE = """
    r_segmented_all AS (
        SELECT
            user_id,
            recency_days,
            is_member,
            CASE
                WHEN recency_days BETWEEN 0 AND 30 THEN '近1个月已购客'
                WHEN recency_days BETWEEN 31 AND 90 THEN '近2-3个月已购客'
                WHEN recency_days BETWEEN 91 AND 180 THEN '近4-6月已购客'
                WHEN recency_days BETWEEN 181 AND 365 THEN '近7-12个月已购客'
                WHEN recency_days BETWEEN 366 AND 730 THEN '近13个月-近24个月已购客'
                WHEN recency_days > 730 THEN '2年外已购客'
            END AS r_segment
        FROM hist_customers_{alias}
    )
"""

# ── 公共接口（向后兼容）──

def _run_r_flow_period(
    conn, start_dt, end_dt, cutoff_dt,
    channel=None, metric_type="GSV", exclude_channels=None,
):
    """R 维度单周期流转（委托引擎）。"""
    return run_flow_period(
        conn, start_dt, end_dt, cutoff_dt,
        dimension="r",
        segment_order=R_SEGMENT_ORDER,
        hist_extra_cols="",
        segmentation_cte=_R_SEGMENTATION_CTE,
        channel=channel,
        metric_type=metric_type,
        exclude_channels=exclude_channels,
    )


def get_rfm_r_flow(
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
    """R 区间流转看板接口（委托引擎）。"""
    return get_rfm_flow(
        dimension="r",
        segment_order=R_SEGMENT_ORDER,
        hist_extra_cols="",
        segmentation_cte=_R_SEGMENTATION_CTE,
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
