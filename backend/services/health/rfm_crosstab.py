"""
RFM 分群 CTE 共享模块

将 rfm_analysis._run_rfm_period() 中的 RFM 分群 CTE 提取为共享函数，
供 rfm_category_drilldown.py 复用，避免代码重复。
"""

from typing import List, Optional, Tuple
from backend.semantic.segments import RFM_THRESHOLDS


def build_rfm_segment_sql(
    cutoff_dt: str,
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> Tuple[str, List]:
    """
    构建 RFM 分群 CTE SQL 片段 + 参数列表。

    生成的 CTE 名称：
        user_stats → rfm_scored → segmented → member_segmented

    调用方可在 WITH 子句中直接拼接此 CTE 片段，
    并在外部添加 repurchase_users / repurchase_amounts 等后续 CTE。

    Parameters
    ----------
    cutoff_dt : str
        历史截止日期（cutoff date）
    channel : Optional[str]
        渠道筛选（不传或"全店"表示不限渠道）
    exclude_channels : Optional[List[str]]
        排除的渠道列表

    Returns
    -------
    Tuple[str, List]
        (cte_sql_fragment, params_list)

    Usage Example
    ------------
    cte_sql, params = build_rfm_segment_sql("2025-12-31", channel="天猫")
    full_sql = f\"\"\"
    WITH
    {cte_sql},
    base_orders AS (...)
    SELECT ...
    \"\"\"
    """
    _rt = RFM_THRESHOLDS["r"]   # [14, 30, 60, 90]
    _ft = RFM_THRESHOLDS["f"]   # [1, 2, 3, 5]
    _mt = RFM_THRESHOLDS["m"]   # [100, 300, 500, 1000]

    params: List = []
    channel_where_all = ""
    channel_where_same = ""

    if channel and channel != "全店":
        from backend.semantic.filters import expand_channels
        db_channels = expand_channels([channel])
        if len(db_channels) == 1:
            channel_where_all = " AND o.channel = ?"
            channel_where_same = " AND o.channel = ?"
            params.append(db_channels[0])
        else:
            placeholders = ",".join(["?"] * len(db_channels))
            channel_where_all = f" AND o.channel IN ({placeholders})"
            channel_where_same = f" AND o.channel IN ({placeholders})"
            params.extend(db_channels)

    # exclude_channels 追加到 user_stats 阶段（复用 rfm_analysis 的处理方式）
    exclude_where_all = ""
    exclude_where_same = ""
    if exclude_channels:
        from backend.semantic.filters import expand_channels
        db_exclude = expand_channels(exclude_channels)
        safe_ch = [ch.replace("'", "''") for ch in db_exclude]
        quoted = ", ".join([f"'{c}'" for c in safe_ch])
        exclude_where_all = f" AND o.channel NOT IN ({quoted})"
        exclude_where_same = f" AND o.channel NOT IN ({quoted})"

    # cutoff_dt 追加到 user_stats_all
    params_all = [cutoff_dt]
    # cutoff_dt 追加到 user_stats_same（先 channel 再 cutoff）
    params_same = []
    if channel_where_same:
        # channel 已追加到 params，cutoff 前置
        params_same = [cutoff_dt]
    else:
        params_same = [cutoff_dt]

    # rfm_scored_all: cutoff_dt × 4
    params_rfm_scored_all = [cutoff_dt] * 4
    # rfm_scored_same: cutoff_dt × 4
    params_rfm_scored_same = [cutoff_dt] * 4

    refund_where = "AND is_refund = FALSE"  # GSV 口径，品类下钻统一用 GSV

    sql = f"""
    user_stats_all AS (
        SELECT
            user_id,
            MAX(pay_time) as last_pay_time,
            COUNT(DISTINCT order_id) as order_count,
            SUM(actual_amount) as gsv,
            BOOL_OR(is_member) AS is_member
        FROM orders o
        WHERE pay_time <= ?::TIMESTAMP
          AND is_goujinjin = FALSE
          AND order_status != '交易关闭'
          {refund_where}
          {exclude_where_all}
        GROUP BY user_id
    ),
    user_stats_same AS (
        SELECT
            user_id,
            MAX(pay_time) as last_pay_time,
            COUNT(DISTINCT order_id) as order_count,
            SUM(actual_amount) as gsv,
            BOOL_OR(is_member) AS is_member
        FROM orders o
        WHERE pay_time <= ?::TIMESTAMP
          AND is_goujinjin = FALSE
          AND order_status != '交易关闭'
          {refund_where}
          {channel_where_same}
          {exclude_where_same}
        GROUP BY user_id
    ),
    rfm_scored_all AS (
        SELECT
            user_id,
            is_member,
            CASE
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[0]} THEN 5
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[1]} THEN 4
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[2]} THEN 3
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[3]} THEN 2
                ELSE 1
            END as r_score,
            CASE WHEN order_count >= {_ft[3] + 1} THEN 5 WHEN order_count >= {_ft[2] + 1} THEN 4 WHEN order_count = {_ft[2]} THEN 3 WHEN order_count = {_ft[1]} THEN 2 ELSE 1 END as f_score,
            CASE WHEN gsv >= {_mt[3]} THEN 5 WHEN gsv >= {_mt[2]} THEN 4 WHEN gsv >= {_mt[1]} THEN 3 WHEN gsv >= {_mt[0]} THEN 2 ELSE 1 END as m_score
        FROM user_stats_all
    ),
    rfm_scored_same AS (
        SELECT
            user_id,
            is_member,
            CASE
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[0]} THEN 5
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[1]} THEN 4
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[2]} THEN 3
                WHEN DATEDIFF('day', last_pay_time::DATE, ?::DATE) < {_rt[3]} THEN 2
                ELSE 1
            END as r_score,
            CASE WHEN order_count >= {_ft[3] + 1} THEN 5 WHEN order_count >= {_ft[2] + 1} THEN 4 WHEN order_count = {_ft[2]} THEN 3 WHEN order_count = {_ft[1]} THEN 2 ELSE 1 END as f_score,
            CASE WHEN gsv >= {_mt[3]} THEN 5 WHEN gsv >= {_mt[2]} THEN 4 WHEN gsv >= {_mt[1]} THEN 3 WHEN gsv >= {_mt[0]} THEN 2 ELSE 1 END as m_score
        FROM user_stats_same
    ),
    segmented_all AS (
        SELECT user_id, is_member,
            CASE
                WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN '重要价值客户'
                WHEN r_score < 4 AND f_score >= 4 AND m_score >= 4 THEN '重要保持客户'
                WHEN r_score >= 4 AND f_score < 4 AND m_score >= 4 THEN '重要发展客户'
                WHEN r_score < 4 AND f_score < 4 AND m_score >= 4 THEN '重要挽留客户'
                WHEN r_score >= 4 AND f_score >= 4 AND m_score < 4 THEN '一般价值客户'
                WHEN r_score < 4 AND f_score >= 4 AND m_score < 4 THEN '一般保持客户'
                WHEN r_score >= 4 AND f_score < 4 AND m_score < 4 THEN '一般发展客户'
                ELSE '一般挽留客户'
            END as rfm_segment
        FROM rfm_scored_all
    ),
    segmented_same AS (
        SELECT user_id, is_member,
            CASE
                WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN '重要价值客户'
                WHEN r_score < 4 AND f_score >= 4 AND m_score >= 4 THEN '重要保持客户'
                WHEN r_score >= 4 AND f_score < 4 AND m_score >= 4 THEN '重要发展客户'
                WHEN r_score < 4 AND f_score < 4 AND m_score >= 4 THEN '重要挽留客户'
                WHEN r_score >= 4 AND f_score >= 4 AND m_score < 4 THEN '一般价值客户'
                WHEN r_score < 4 AND f_score >= 4 AND m_score < 4 THEN '一般保持客户'
                WHEN r_score >= 4 AND f_score < 4 AND m_score < 4 THEN '一般发展客户'
                ELSE '一般挽留客户'
            END as rfm_segment
        FROM rfm_scored_same
    ),
    member_segmented_all AS (
        SELECT user_id, rfm_segment FROM segmented_all WHERE is_member = TRUE
    ),
    member_segmented_same AS (
        SELECT user_id, rfm_segment FROM segmented_same WHERE is_member = TRUE
    )
    """

    # 组装完整参数顺序：
    # user_stats_all: cutoff_dt
    # user_stats_same: cutoff_dt
    # rfm_scored_all: cutoff_dt × 4
    # rfm_scored_same: cutoff_dt × 4
    full_params = params_all + params_same + params_rfm_scored_all + params_rfm_scored_same

    return sql, full_params
