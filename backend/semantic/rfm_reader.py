"""
RFM 预计算读取模块（语义层）

从 user_rfm 表读取预计算的 RFM 分群数据，供 Service 层 API 加速使用。
未命中时返回 None，由调用方回退到实时 SQL 查询。

用法：
    from backend.semantic.rfm_reader import try_read_rfm_segment

    result = try_read_rfm_segment(conn, "2026-04-30", 90, "GMV", "全店")
    if result is not None:
        # 使用预计算结果
        pass
    else:
        # 回退到实时 SQL
"""

from typing import Dict, Optional, List
import logging

from backend.db.connection import get_connection

logger = logging.getLogger(__name__)


def try_read_rfm_segment(
    conn,
    analysis_date: str,
    lookback_days: int,
    metric_type: str,
    channel: str = "全店",
) -> Optional[Dict[str, Dict]]:
    """从 user_rfm 预计算表读取分段统计。

    参数:
        conn: DuckDB 连接（已开启事务或自动提交）
        analysis_date: 分析日期 (YYYY-MM-DD)
        lookback_days: 回看天数（如 30/90/180）
        metric_type: "GMV" 或 "GSV"
        channel: 渠道名称，默认 "全店"

    返回:
        None 如果：
        - user_rfm 表不存在该组合的数据（预计算未命中）
        - 查询异常

        Dict[segment_name, Dict] 如果命中：
        {
            "重要价值客户": {
                "user_count": int,
                "monetary_sum": float,
                "frequency_sum": int,
                "avg_recency": float,
                "r_score": int,
                "f_score": int,
                "m_score": int,
            },
            ...
        }

    注意:
        - 返回的 segment 名称为中文 rfm_tier
        - caller 必须处理 None 返回值（回退到实时 SQL）
    """
    try:
        # 检查数据是否存在（快速计数）
        check_sql = """
        SELECT COUNT(*)
        FROM user_rfm
        WHERE analysis_date = ?
          AND lookback_days = ?
          AND metric_type = ?
          AND channel = ?
        """
        count = conn.execute(
            check_sql,
            [analysis_date, lookback_days, metric_type, channel],
        ).fetchone()[0]

        if count == 0:
            logger.debug(
                f"rfm_reader cache miss: {analysis_date}/{lookback_days}d/"
                f"{metric_type}/{channel} (0 rows)"
            )
            return None

        # 读取分群聚合数据
        agg_sql = """
        SELECT
            rfm_tier,
            COUNT(*)                                    AS user_count,
            SUM(monetary)                               AS monetary_sum,
            SUM(frequency)                             AS frequency_sum,
            AVG(recency_days)::DECIMAL(10, 1)          AS avg_recency,
            AVG(r_score)::INT                          AS avg_r_score,
            AVG(f_score)::INT                          AS avg_f_score,
            AVG(m_score)::INT                           AS avg_m_score,
            MIN(r_score)                                AS min_r_score,
            MAX(r_score)                               AS max_r_score,
            MIN(f_score)                               AS min_f_score,
            MAX(f_score)                               AS max_f_score,
            MIN(m_score)                               AS min_m_score,
            MAX(m_score)                               AS max_m_score
        FROM user_rfm
        WHERE analysis_date = ?
          AND lookback_days = ?
          AND metric_type = ?
          AND channel = ?
        GROUP BY rfm_tier
        ORDER BY user_count DESC
        """
        rows = conn.execute(
            agg_sql,
            [analysis_date, lookback_days, metric_type, channel],
        ).fetchall()

        if not rows:
            return None

        result: Dict[str, Dict] = {}
        for row in rows:
            (
                tier_name,
                user_count,
                monetary_sum,
                frequency_sum,
                avg_recency,
                avg_r,
                avg_f,
                avg_m,
                min_r,
                max_r,
                min_f,
                max_f,
                min_m,
                max_m,
            ) = row
            result[tier_name] = {
                "user_count": user_count,
                "monetary_sum": float(monetary_sum) if monetary_sum else 0.0,
                "frequency_sum": int(frequency_sum) if frequency_sum else 0,
                "avg_recency": float(avg_recency) if avg_recency else 0.0,
                "avg_r_score": int(avg_r) if avg_r else 0,
                "avg_f_score": int(avg_f) if avg_f else 0,
                "avg_m_score": int(avg_m) if avg_m else 0,
                "r_score_range": (int(min_r), int(max_r)),
                "f_score_range": (int(min_f), int(max_f)),
                "m_score_range": (int(min_m), int(max_m)),
            }

        logger.debug(
            f"rfm_reader hit: {analysis_date}/{lookback_days}d/"
            f"{metric_type}/{channel} -> {len(result)} segments, "
            f"{sum(v['user_count'] for v in result.values()):,} users"
        )
        return result

    except Exception as e:
        logger.warning(
            f"rfm_reader error: {analysis_date}/{lookback_days}d/"
            f"{metric_type}/{channel} -> {e}"
        )
        return None


def get_rfm_summary(
    conn,
    analysis_date: str,
    lookback_days: int,
    metric_type: str,
    channel: str = "全店",
) -> Optional[Dict]:
    """读取 RFM 全局汇总指标（从 user_rfm）。

    返回:
        None 如果未命中，否则 Dict 含：
        - total_users: 总用户数
        - total_monetary: 总消费金额
        - total_frequency: 总订单次数
        - avg_recency: 平均最近购买天数
        - segment_distribution: {"重要价值客户": 1234, ...}
    """
    try:
        check_sql = """
        SELECT COUNT(*)
        FROM user_rfm
        WHERE analysis_date = ?
          AND lookback_days = ?
          AND metric_type = ?
          AND channel = ?
        """
        count = conn.execute(
            check_sql,
            [analysis_date, lookback_days, metric_type, channel],
        ).fetchone()[0]

        if count == 0:
            return None

        summary_sql = """
        SELECT
            COUNT(*)                                    AS total_users,
            SUM(monetary)::DECIMAL(15, 2)              AS total_monetary,
            SUM(frequency)                              AS total_frequency,
            AVG(recency_days)::DECIMAL(10, 1)           AS avg_recency,
            AVG(r_score)::DECIMAL(3, 1)                AS avg_r_score,
            AVG(f_score)::DECIMAL(3, 1)                AS avg_f_score,
            AVG(m_score)::DECIMAL(3, 1)                AS avg_m_score
        FROM user_rfm
        WHERE analysis_date = ?
          AND lookback_days = ?
          AND metric_type = ?
          AND channel = ?
        """
        row = conn.execute(
            summary_sql,
            [analysis_date, lookback_days, metric_type, channel],
        ).fetchone()

        if not row:
            return None

        (
            total_users,
            total_monetary,
            total_frequency,
            avg_recency,
            avg_r,
            avg_f,
            avg_m,
        ) = row

        # 分群分布
        dist_sql = """
        SELECT rfm_tier, COUNT(*)
        FROM user_rfm
        WHERE analysis_date = ?
          AND lookback_days = ?
          AND metric_type = ?
          AND channel = ?
        GROUP BY rfm_tier
        ORDER BY COUNT(*) DESC
        """
        dist_rows = conn.execute(
            dist_sql,
            [analysis_date, lookback_days, metric_type, channel],
        ).fetchall()
        segment_dist = {tier: cnt for tier, cnt in dist_rows}

        return {
            "total_users": int(total_users) if total_users else 0,
            "total_monetary": float(total_monetary) if total_monetary else 0.0,
            "total_frequency": int(total_frequency) if total_frequency else 0,
            "avg_recency": float(avg_recency) if avg_recency else 0.0,
            "avg_r_score": float(avg_r) if avg_r else 0.0,
            "avg_f_score": float(avg_f) if avg_f else 0.0,
            "avg_m_score": float(avg_m) if avg_m else 0.0,
            "segment_distribution": segment_dist,
        }

    except Exception as e:
        logger.warning(
            f"rfm_summary error: {analysis_date}/{lookback_days}d/"
            f"{metric_type}/{channel} -> {e}"
        )
        return None


def get_user_count_by_channel(
    conn,
    analysis_date: str,
    lookback_days: int,
    metric_type: str,
) -> Dict[str, int]:
    """返回各渠道用户数（从 user_rfm），用于渠道维度汇总。

    永远不返回 None，只返回 Dict（无数据时返回全零字典）。
    """
    try:
        sql = """
        SELECT channel, COUNT(DISTINCT user_id)
        FROM user_rfm
        WHERE analysis_date = ?
          AND lookback_days = ?
          AND metric_type = ?
        GROUP BY channel
        """
        rows = conn.execute(
            sql,
            [analysis_date, lookback_days, metric_type],
        ).fetchall()
        return {ch: cnt for ch, cnt in rows}
    except Exception as e:
        logger.warning(f"get_user_count_by_channel error: {e}")
        return {}
