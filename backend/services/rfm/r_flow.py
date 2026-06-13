"""
Sample CRM - RFM R 区间流转

R 维度：按最近购买时间（recency_days）分段。
配置驱动，核心逻辑在 _flow_engine 中。
"""

from typing import Any, Dict, List, Optional

from backend.semantic.segments import R_SEGMENT_ORDER
from backend.services.rfm._flow_engine import run_flow_period, get_rfm_flow
from backend.services.rfm._shared import _VALID_BASE
from backend.semantic.filters import expand_channels


# ── R 维度配置 ──
# R 桶窗口：Sprint 8 P0 改回 cutoff_dt (= start_dt - 1) 截止，
# 与 hist_customers 改用 start_dt 保持一致：R 桶分桶必须基于 pre-period 行为。
# 否则有当期订单的回购用户 pre_cutoff_last_pay 落在当期 → DATEDIFF 到 end_dt = 0-6 天
# → 全部归入近1个月，R 桶 2-6 ∩ base_orders = ∅，回购率恒为 0%（Sprint 7 教训）。
# 当前期间新购客（pre_cutoff=NULL）不归入任何 R 桶，仅出现在已购客TTL行。
# 段级和 < TTL by 当期新购客数（业务语义正确的代价）。
_R_BUCKET_SEGMENTATION_TEMPLATE = """
    pre_cutoff_users AS (
        SELECT user_id, MAX(pay_time) AS pre_cutoff_last_pay
        FROM orders o
        WHERE pay_time <= ?::TIMESTAMP
          AND {valid_base}
          {refund_where}
          {exclude_where_hist}
        GROUP BY user_id
    ),
    cutoff_ref AS (SELECT ?::DATE AS cutoff_date),
    segmented_customers AS (
        SELECT
            hc.user_id,
            hc.channel_flag,
            hc.is_member,
            CASE
                WHEN DATEDIFF('day', pcu.pre_cutoff_last_pay::DATE, cr.cutoff_date) BETWEEN 0 AND 30 THEN '近1个月已购客'
                WHEN DATEDIFF('day', pcu.pre_cutoff_last_pay::DATE, cr.cutoff_date) BETWEEN 31 AND 90 THEN '近2-3个月已购客'
                WHEN DATEDIFF('day', pcu.pre_cutoff_last_pay::DATE, cr.cutoff_date) BETWEEN 91 AND 180 THEN '近4-6月已购客'
                WHEN DATEDIFF('day', pcu.pre_cutoff_last_pay::DATE, cr.cutoff_date) BETWEEN 181 AND 365 THEN '近7-12个月已购客'
                WHEN DATEDIFF('day', pcu.pre_cutoff_last_pay::DATE, cr.cutoff_date) BETWEEN 366 AND 730 THEN '近13个月-近24个月已购客'
                WHEN DATEDIFF('day', pcu.pre_cutoff_last_pay::DATE, cr.cutoff_date) > 730 THEN '2年外已购客'
            END AS r_segment
        FROM hist_customers hc
        LEFT JOIN pre_cutoff_users pcu ON hc.user_id = pcu.user_id
        CROSS JOIN cutoff_ref cr
    )
"""


def _build_r_segmentation_cte(
    refund_where: str,
    exclude_where_hist: str,
) -> str:
    """构造 R 桶分桶 CTE，注入 valid_base / refund_where / exclude_where_hist 过滤。"""
    return _R_BUCKET_SEGMENTATION_TEMPLATE.format(
        valid_base=_VALID_BASE,
        refund_where=refund_where,
        exclude_where_hist=exclude_where_hist,
    )


def _r_hist_filters(metric_type: str, exclude_channels: Optional[List[str]]):
    """
    R flow 段级 hist 过滤 SQL 片段（与 _flow_engine 中 R flow 口径一致）。
    返回 (refund_where, exclude_where_hist)。
    渠道名走白名单映射 (expand_channels) 且为常量字符串，inline 安全。
    """
    refund_where = "AND is_refund = FALSE" if metric_type == "GSV" else ""
    exclude_where_hist = ""
    if exclude_channels:
        db_exc = expand_channels(exclude_channels)
        # 内联白名单渠道名（来自 _CHANNEL_UI_TO_DB / _CHANNEL_GROUP_MAP，安全）
        inlined = ",".join(f"'{ch}'" for ch in db_exc)
        exclude_where_hist = f" AND o.channel NOT IN ({inlined})"
    return refund_where, exclude_where_hist


# ── 公共接口（向后兼容）──

def _run_r_flow_period(
    conn, start_dt, end_dt, cutoff_dt,
    channel=None, metric_type="GSV", exclude_channels=None,
):
    """R 维度单周期流转（委托引擎）。"""
    refund_where, exclude_where_hist = _r_hist_filters(metric_type, exclude_channels)
    segmentation_cte = _build_r_segmentation_cte(
        refund_where=refund_where,
        exclude_where_hist=exclude_where_hist,
    )
    return run_flow_period(
        conn, start_dt, end_dt, cutoff_dt,
        dimension="r",
        segment_order=R_SEGMENT_ORDER,
        hist_extra_cols="",
        segmentation_cte=segmentation_cte,
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
    refund_where, exclude_where_hist = _r_hist_filters(metric_type, exclude_channels)
    segmentation_cte = _build_r_segmentation_cte(
        refund_where=refund_where,
        exclude_where_hist=exclude_where_hist,
    )
    return get_rfm_flow(
        dimension="r",
        segment_order=R_SEGMENT_ORDER,
        hist_extra_cols="",
        segmentation_cte=segmentation_cte,
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
