"""Sprint 142 RFM 扩展分群 service."""

from datetime import date
from typing import Dict, List, Optional

from backend.contracts.rfm_segments import RFMSegmentExtended
from backend.semantic.segments import (
    SegmentRegistry,
    lifecycle_case_sql,
    potential_tier_case_sql,
    value_tier_case_sql,
)


def get_user_rfm_extended(
    conn,
    user_ids: List[str],
    as_of_date: Optional[str] = None,
) -> Dict[str, RFMSegmentExtended]:
    """计算用户 RFM 扩展分群（8 quadrant + 生命周期/价值层/潜力层）."""
    clean_user_ids = [str(user_id) for user_id in user_ids if user_id]
    if not clean_user_ids:
        return {}

    analysis_date = as_of_date or date.today().isoformat()
    placeholders = ",".join(["?"] * len(clean_user_ids))
    registry = SegmentRegistry()

    sql = f"""
        WITH params AS (
            SELECT ?::DATE AS as_of_date
        ),
        user_orders AS (
            SELECT
                o.user_id,
                MIN(CAST(o.pay_time AS DATE)) AS first_active,
                MAX(CAST(o.pay_time AS DATE)) AS last_active,
                COALESCE(SUM(o.actual_amount), 0) AS gsv_sum,
                COUNT(DISTINCT o.order_id) AS order_count,
                COALESCE(SUM(
                    CASE
                        WHEN o.pay_time >= params.as_of_date - INTERVAL '30' DAY
                         AND o.pay_time <= params.as_of_date + INTERVAL '1' DAY
                            THEN o.actual_amount
                        ELSE 0
                    END
                ), 0)
                - COALESCE(SUM(
                    CASE
                        WHEN o.pay_time >= params.as_of_date - INTERVAL '60' DAY
                         AND o.pay_time < params.as_of_date - INTERVAL '30' DAY
                            THEN o.actual_amount
                        ELSE 0
                    END
                ), 0) AS gsv_growth,
                params.as_of_date
            FROM orders o
            CROSS JOIN params
            WHERE o.user_id IN ({placeholders})
              AND o.pay_time <= params.as_of_date + INTERVAL '1' DAY
              AND o.is_refund = FALSE
              AND o.order_status != '交易关闭'
              AND o.channel != '购物金'
            GROUP BY o.user_id, params.as_of_date
        ),
        rfm_base AS (
            SELECT
                user_id,
                first_active,
                last_active,
                gsv_sum,
                order_count,
                gsv_growth,
                as_of_date,
                DATEDIFF('day', last_active, as_of_date) AS recency_days,
                order_count AS frequency,
                gsv_sum AS monetary
            FROM user_orders
        ),
        scored AS (
            SELECT
                user_id,
                first_active,
                last_active,
                gsv_sum,
                order_count,
                gsv_growth,
                as_of_date,
                {registry.build_r_score_sql()} AS r_score,
                {registry.build_f_score_sql()} AS f_score,
                {registry.build_m_score_sql()} AS m_score
            FROM rfm_base
        ),
        segmented AS (
            SELECT
                user_id,
                {registry.build_segment_case_when_sql()} AS segment_id,
                {lifecycle_case_sql("as_of_date")} AS lifecycle_stage,
                {value_tier_case_sql()} AS value_tier,
                {potential_tier_case_sql("as_of_date")} AS potential_tier
            FROM scored
        )
        SELECT
            user_id,
            {registry.build_segment_name_case_when_sql()} AS rfm_quadrant,
            lifecycle_stage,
            value_tier,
            potential_tier
        FROM segmented
    """
    params = [analysis_date, *clean_user_ids]
    assert sql.count("?") == len(params), (
        f"get_user_rfm_extended params mismatch: SQL has {sql.count('?')} ? but {len(params)} params"
    )

    rows = conn.execute(sql, params).fetchall()
    return {
        row[0]: RFMSegmentExtended(
            user_id=row[0],
            rfm_quadrant=row[1],
            lifecycle_stage=row[2],
            value_tier=row[3],
            potential_tier=row[4],
        )
        for row in rows
    }
