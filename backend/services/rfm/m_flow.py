"""
Sample CRM - RFM M 区间流转

M 维度：按历史累计消费金额（monetary）分段。
配置驱动，核心逻辑在 _flow_engine 中。
"""

from typing import Any, Dict, List, Optional

from backend.semantic.segments import M_SEGMENT_ORDER
from backend.services.rfm._flow_engine import run_flow_period, get_rfm_flow

# ── M 维度配置 ──
_M_SEGMENTATION_CTE = """
    segmented_customers AS (
        SELECT
            user_id,
            channel_flag,
            is_member,
            CASE
                WHEN monetary < 100 THEN '0-100元'
                WHEN monetary < 300 THEN '100-300元'
                WHEN monetary < 500 THEN '300-500元'
                WHEN monetary < 1000 THEN '500-1000元'
                ELSE '1000元以上'
            END AS m_segment
        FROM hist_customers
    )
"""

# ── 公共接口（向后兼容）──

def _run_m_flow_period(
    conn, start_dt, end_dt, cutoff_dt,
    channel=None, metric_type="GSV", exclude_channels=None,
):
    """M 维度单周期流转（委托引擎）。"""
    return run_flow_period(
        conn, start_dt, end_dt, cutoff_dt,
        dimension="m",
        segment_order=M_SEGMENT_ORDER,
        hist_extra_cols="SUM(actual_amount) AS monetary",
        segmentation_cte=_M_SEGMENTATION_CTE,
        channel=channel,
        metric_type=metric_type,
        exclude_channels=exclude_channels,
    )


def get_rfm_m_flow(
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
    """M 区间流转看板接口（委托引擎）。"""
    return get_rfm_flow(
        dimension="m",
        segment_order=M_SEGMENT_ORDER,
        hist_extra_cols="SUM(actual_amount) AS monetary",
        segmentation_cte=_M_SEGMENTATION_CTE,
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
