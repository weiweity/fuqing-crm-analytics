"""
芙清 CRM - RFM 区间流转
"""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from backend.db.connection import get_connection
from backend.services.rfm._shared import (
    _VALID_BASE, _VALID_BASE_T,
)
from backend.semantic.filters import expand_channels

# RFM 区间订单明细导出
# ============================================================

def get_segment_orders(
    dimension: str,
    segment: str,
    start_date: str,
    end_date: str,
    metric_type: str = "GSV",
    mode: str = "all",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    根据 RFM 维度和区间，导出该区间内所有用户的订单号明细。
    """
    cur_start_dt = f"{start_date} 00:00:00"
    cur_end_dt = f"{end_date} 23:59:59"
    cutoff_date = date(int(start_date[:4]), int(start_date[5:7]), 1) - timedelta(days=1)
    cutoff = cutoff_date.strftime("%Y-%m-%d")

    refund_where = "AND is_refund = FALSE" if metric_type == "GSV" else ""

    # 渠道条件 - base_orders（回购订单）
    channel_where_base = ""
    base_params_extra: List = []
    if channel and channel != "全店":
        db_ch = expand_channels([channel])
        if len(db_ch) == 1:
            channel_where_base = " AND o.channel = ?"
            base_params_extra = [db_ch[0]]
        else:
            ph = ",".join(["?"] * len(db_ch))
            channel_where_base = f" AND o.channel IN ({ph})"
            base_params_extra = list(db_ch)

    # 渠道条件 - history（same_channel / member_same_channel 限渠道）
    channel_where_hist = ""
    hist_params_extra: List = []
    if mode in ("same_channel", "member_same_channel") and channel and channel != "全店":
        db_ch = expand_channels([channel])
        if len(db_ch) == 1:
            channel_where_hist = " AND o.channel = ?"
            hist_params_extra = [db_ch[0]]
        else:
            ph = ",".join(["?"] * len(db_ch))
            channel_where_hist = f" AND o.channel IN ({ph})"
            hist_params_extra = list(db_ch)

    # 排除渠道（统一参数化，避免 SQL 注入风险）
    # db_exc 同时用于 hist_sql（CTE 内）和 target_orders（CTE 外），需要追加到两处 params
    exc_params: List[str] = []
    exclude_where_base = ""
    exclude_where_hist = ""
    if exclude_channels:
        db_exc = expand_channels(exclude_channels)
        exc_params = list(db_exc)  # 保持独立副本
        exc_placeholders = ",".join(["?"] * len(db_exc))
        exclude_where_base = f" AND o.channel NOT IN ({exc_placeholders})"
        exclude_where_hist = f" AND o.channel NOT IN ({exc_placeholders})"

    member_where = "AND hc.is_member = TRUE" if mode in ("member", "member_same_channel") else ""

    # 维度分段
    if dimension == "r":
        seg_case = """CASE
            WHEN recency_days BETWEEN 0 AND 30 THEN '近1个月已购客'
            WHEN recency_days BETWEEN 31 AND 90 THEN '近2-3个月已购客'
            WHEN recency_days BETWEEN 91 AND 180 THEN '近4-6月已购客'
            WHEN recency_days BETWEEN 181 AND 365 THEN '近7-12个月已购客'
            WHEN recency_days BETWEEN 366 AND 730 THEN '近13个月-近24个月已购客'
            WHEN recency_days > 730 THEN '2年外已购客'
        END AS segment_label"""
        hist_sql = (
            "SELECT user_id, DATEDIFF('day', MAX(pay_time)::DATE, ?::DATE) AS recency_days, "
            "0 AS frequency, 0 AS monetary, BOOL_OR(is_member) AS is_member "
            "FROM orders o "
            f"WHERE pay_time <= ?::TIMESTAMP AND {_VALID_BASE} "
            f"{refund_where} {channel_where_hist} {exclude_where_hist} "
            "GROUP BY user_id"
        )
        hist_params: List = [cutoff, cutoff] + hist_params_extra + exc_params
    elif dimension == "f":
        seg_case = """CASE
            WHEN frequency = 1 THEN '1次购买'
            WHEN frequency = 2 THEN '2次购买'
            WHEN frequency = 3 THEN '3次购买'
            WHEN frequency = 4 THEN '4次购买'
            ELSE '5次及以上'
        END AS segment_label"""
        hist_sql = (
            "SELECT user_id, DATEDIFF('day', MAX(pay_time)::DATE, ?::DATE) AS recency_days, "
            "COUNT(*) AS frequency, 0 AS monetary, BOOL_OR(is_member) AS is_member "
            "FROM orders o "
            f"WHERE pay_time <= ?::TIMESTAMP AND {_VALID_BASE} "
            f"{refund_where} {channel_where_hist} {exclude_where_hist} "
            "GROUP BY user_id"
        )
        hist_params = [cutoff, cutoff] + hist_params_extra + exc_params
    elif dimension == "m":
        seg_case = """CASE
            WHEN monetary < 100 THEN '0-100元'
            WHEN monetary < 300 THEN '100-300元'
            WHEN monetary < 500 THEN '300-500元'
            WHEN monetary < 1000 THEN '500-1000元'
            ELSE '1000元以上'
        END AS segment_label"""
        hist_sql = (
            "SELECT user_id, DATEDIFF('day', MAX(pay_time)::DATE, ?::DATE) AS recency_days, "
            "0 AS frequency, SUM(actual_amount) AS monetary, BOOL_OR(is_member) AS is_member "
            "FROM orders o "
            f"WHERE pay_time <= ?::TIMESTAMP AND {_VALID_BASE} "
            f"{refund_where} {channel_where_hist} {exclude_where_hist} "
            "GROUP BY user_id"
        )
        hist_params = [cutoff, cutoff] + hist_params_extra + exc_params
    else:
        raise ValueError(f"Invalid dimension: {dimension}")

    sql = f"""
    WITH
    hist_customers AS ({hist_sql}),
    hist_segmented AS (
        SELECT user_id, is_member, {seg_case}
        FROM hist_customers hc
        WHERE 1=1 {member_where}
    ),
    target_users AS (
        SELECT user_id FROM hist_segmented WHERE segment_label = ?
    ),
    target_orders AS (
        SELECT o.order_id, o.user_id,
               CAST(o.pay_time AS VARCHAR) AS pay_time,
               o.actual_amount, o.channel, o.spu_product_class
        FROM orders o
        INNER JOIN target_users tu ON o.user_id = tu.user_id
        WHERE o.pay_time >= ?::TIMESTAMP
          AND o.pay_time <= ?::TIMESTAMP
          AND {_VALID_BASE_T}
          {refund_where}
          {channel_where_base}
          {exclude_where_base}
    )
    SELECT order_id, user_id, pay_time, actual_amount, channel, spu_product_class
    FROM target_orders
    ORDER BY pay_time DESC
    """

    params = hist_params + [segment, cur_start_dt, cur_end_dt] + base_params_extra + exc_params

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        pass

    order_rows = []
    for r in rows:
        order_rows.append({
            "order_id": str(r[0]) if r[0] else "",
            "user_id": str(r[1]) if r[1] else "",
            "pay_time": str(r[2]) if r[2] else "",
            "actual_amount": float(r[3] or 0),
            "channel": str(r[4]) if r[4] else "",
            "spu_product_class": str(r[5]) if r[5] else None,
        })

    return {
        "dimension": dimension,
        "segment": segment,
        "mode": mode,
        "total_orders": len(order_rows),
        "rows": order_rows,
    }
