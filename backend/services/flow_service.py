"""
芙清 CRM 客户分析系统 - 人群流转分析服务
Week 3 人群流转矩阵 + 桑基图数据

接入语义层: 使用 semantic/segments.py 中的 SegmentRegistry 作为唯一真实数据源。
"""

import duckdb
import pandas as pd
from typing import Dict, Any, List, Optional
from functools import lru_cache
from backend.db.connection import get_connection
from backend.semantic.segments import get_registry, SEGMENTS
from backend.semantic.filters import OrderFilters


# ============================================================
# 缓存: 用户象限计算结果 (内存级 LRU，按日期+lookback+metric_type 缓存)
# ============================================================

@lru_cache(maxsize=128)
def _cached_user_segments(
    date: str,
    lookback_days: int,
    metric_type: str,
    exclude_channels_str: Optional[str] = None,
) -> pd.DataFrame:
    """
    带缓存的用户象限计算。返回 DataFrame 的 dict 表示（因为 pd.DataFrame 不可 hash）。
    实际计算在 _compute_user_segments_raw 中完成。
    """
    conn = get_connection()
    try:
        exclude_channels = exclude_channels_str.split(",") if exclude_channels_str else None
        df = _compute_user_segments_raw(conn, date, lookback_days, metric_type, exclude_channels)
        return df
    finally:
        conn.close()


def _try_load_from_user_rfm(
    conn: duckdb.DuckDBPyConnection,
    date: str,
    lookback_days: int,
    metric_type: str
) -> Optional[pd.DataFrame]:
    """
    尝试从 user_rfm 预计算表读取用户象限分布。
    命中时可直接返回，无需重新扫描 orders 表。
    """
    try:
        sql = """
        SELECT
            user_id,
            segment_id,
            r_score,
            f_score,
            m_score,
            monetary,
            frequency
        FROM user_rfm
        WHERE analysis_date = DATE(?)
          AND metric_type = ?
          AND lookback_days = ?
        """
        df = conn.execute(sql, [date, metric_type, lookback_days]).fetchdf()
        if not df.empty:
            return df
    except Exception as e:
        # user_rfm 表可能不存在或结构不匹配，记录后 fallback
        import logging
        logging.getLogger(__name__).debug(f"user_rfm 读取失败，fallback 到实时计算: {e}")
    return None


def _compute_user_segments_raw(
    conn: duckdb.DuckDBPyConnection,
    date: str,
    lookback_days: int,
    metric_type: str,
    exclude_channels: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    原始 SQL 计算指定日期的用户象限分布（参数化查询，无 SQL 注入）。
    """
    from datetime import datetime, timedelta
    from backend.semantic.segments import RFM_THRESHOLDS

    start_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    valid_sql, _ = OrderFilters.valid_order()
    amount_cond = "actual_amount > 0" if metric_type == "GMV" else "actual_amount >= 0"

    registry = get_registry()
    r_score_sql = registry.build_r_score_sql(RFM_THRESHOLDS["r"])
    f_score_sql = registry.build_f_score_sql(RFM_THRESHOLDS["f"])
    m_score_sql = registry.build_m_score_sql(RFM_THRESHOLDS["m"])
    segment_sql = registry.build_segment_case_when_sql()

    params = [date, start_date, date, date]

    channel_where = ""
    if exclude_channels:
        # 安全内联：channel 值来自预定义白名单，使用单引号转义避免注入
        safe_channels = [ch.replace("'", "''") for ch in exclude_channels]
        quoted = ", ".join([f"'{ch}'" for ch in safe_channels])
        channel_where = f"AND o.channel NOT IN ({quoted})"

    sql = f"""
    WITH base_params AS (
        SELECT DATE(?) AS analysis_date, DATE(?) AS start_date
    ),
    period_orders AS (
        SELECT o.user_id, o.actual_amount, o.order_id, o.pay_time
        FROM orders o
        CROSS JOIN base_params p
        WHERE o.pay_time >= p.start_date
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          AND ({amount_cond})
          {channel_where}
    ),
    user_metrics AS (
        SELECT
            user_id,
            SUM(actual_amount) AS monetary,
            COUNT(DISTINCT order_id) AS frequency,
            MAX(pay_time) AS last_pay_time
        FROM period_orders
        GROUP BY user_id
    ),
    user_with_rfm AS (
        SELECT
            um.user_id, um.monetary, um.frequency,
            DATEDIFF('day', um.last_pay_time, DATE(?)) AS recency_days
        FROM user_metrics um
    ),
    user_with_scores AS (
        SELECT
            user_id, monetary, frequency, recency_days,
            {r_score_sql} AS r_score,
            {f_score_sql} AS f_score,
            {m_score_sql} AS m_score
        FROM user_with_rfm
    ),
    user_with_segment AS (
        SELECT
            user_id, monetary, frequency, recency_days,
            r_score, f_score, m_score,
            {segment_sql} AS segment_id
        FROM user_with_scores
    )
    SELECT user_id, segment_id, r_score, f_score, m_score, monetary, frequency
    FROM user_with_segment
    """

    return conn.execute(sql, params).fetchdf()


def _compute_user_segments_sql(
    conn: duckdb.DuckDBPyConnection,
    date: str,
    lookback_days: int,
    metric_type: str,
    exclude_channels: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    计算指定日期的用户象限分布，优先走三级缓存：
    1) user_rfm 预计算表（磁盘级，ETL/预加载生成）
    2) 进程级 LRU 内存缓存
    3) 原始 SQL 实时计算（fallback）
    """
    # 1. 优先查 user_rfm 表（仅当无渠道排除时；user_rfm 无渠道维度）
    if not exclude_channels:
        df = _try_load_from_user_rfm(conn, date, lookback_days, metric_type)
        if df is not None:
            return df

    # 2. 查内存缓存
    exclude_channels_str = ",".join(sorted(exclude_channels)) if exclude_channels else None
    df = _cached_user_segments(date, lookback_days, metric_type, exclude_channels_str)
    if df is not None and not df.empty:
        return df.copy()

    # 3. fallback 到原始 SQL
    return _compute_user_segments_raw(conn, date, lookback_days, metric_type, exclude_channels)


def get_flow_matrix(
    from_date: str,
    to_date: str,
    lookback_days: int = 90,
    metric_type: str = "GMV",
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    获取人群流转矩阵（8象限版本）

    Args:
        from_date: 起始日期 (YYYY-MM-DD)
        to_date: 结束日期 (YYYY-MM-DD)
        lookback_days: 回溯天数
        metric_type: GMV/GSV
        exclude_channels: 排除的渠道列表

    Returns:
        {
            "flow_matrix": List[{"from": int, "to": int, "count": int}],
            "segments": List[{"id": int, "name": str, "color": str}],
            "from_total": int,
            "to_total": int,
            "summary": {
                "retention_rate": float,  # 留在原象限的用户比例
                "upgrade_rate": float,    # 升级比例
                "downgrade_rate": float   # 降级比例
            }
        }
    """
    conn = get_connection()

    try:
        # 计算两个时间点的用户象限
        df_from = _compute_user_segments_sql(conn, from_date, lookback_days, metric_type, exclude_channels)
        df_to = _compute_user_segments_sql(conn, to_date, lookback_days, metric_type, exclude_channels)

        df_from = df_from.rename(columns={"segment_id": "from_segment"})
        df_to = df_to.rename(columns={"segment_id": "to_segment"})

        # LEFT JOIN 计算流转（流失用户在 to_segment 为 NULL）
        df_merged = df_from.merge(
            df_to[["user_id", "to_segment"]],
            on="user_id",
            how="left"
        )
        # to_segment 为 NULL 表示流失（90天内无订单）
        df_merged["to_segment"] = df_merged["to_segment"].fillna(8).astype(int)

        # 使用语义层获取所有11个象限
        registry = get_registry()
        all_segments = registry.list_all()
        segment_ids = sorted([s.segment_id for s in all_segments if s.segment_id != 9]) + [9]

        # NxN 矩阵（N=11）
        matrix_records = []
        for f in segment_ids:
            for t in segment_ids:
                count = len(df_merged[
                    (df_merged["from_segment"] == f) &
                    (df_merged["to_segment"] == t)
                ])
                if count > 0:
                    matrix_records.append({"from": f, "to": t, "count": count})

        # 汇总指标
        from_total = len(df_from)
        to_total = len(df_to)

        # 留存率：to_segment == from_segment 的用户 / from_total
        retained = len(df_merged[df_merged["from_segment"] == df_merged["to_segment"]])
        retention_rate = round(retained / from_total, 4) if from_total > 0 else 0

        # 升级/降级（基于象限定义：1最好，数值越大象限越差）
        # 升级：to_segment < from_segment
        upgraded = len(df_merged[df_merged["to_segment"] < df_merged["from_segment"]])
        downgraded = len(df_merged[df_merged["to_segment"] > df_merged["from_segment"]])
        upgrade_rate = round(upgraded / from_total, 4) if from_total > 0 else 0
        downgrade_rate = round(downgraded / from_total, 4) if from_total > 0 else 0

        return {
            "flow_matrix": matrix_records,
            "segments": [
                {
                    "id": seg.segment_id,
                    "name": seg.name_cn,
                    "color": seg.color,
                    "priority": seg.priority,
                }
                for seg in sorted(all_segments, key=lambda s: s.priority)
            ],
            "from_date": from_date,
            "to_date": to_date,
            "from_total": from_total,
            "to_total": to_total,
            "summary": {
                "retention_rate": retention_rate,
                "upgrade_rate": upgrade_rate,
                "downgrade_rate": downgrade_rate
            }
        }
    finally:
        conn.close()


def get_flow_sankey(
    from_date: str,
    to_date: str,
    lookback_days: int = 90,
    metric_type: str = "GMV",
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    获取桑基图数据（8象限版本）

    Returns:
        {
            "nodes": List[{"id": str, "name": str, "color": str, "stage": str}],
            "links": List[{"source": str, "target": str, "value": int}]
        }
    """
    conn = get_connection()

    try:
        df_from = _compute_user_segments_sql(conn, from_date, lookback_days, metric_type, exclude_channels)
        df_to = _compute_user_segments_sql(conn, to_date, lookback_days, metric_type, exclude_channels)

        df_from = df_from.rename(columns={"segment_id": "from_segment"})
        df_to = df_to.rename(columns={"segment_id": "to_segment"})

        df_merged = df_from.merge(
            df_to[["user_id", "to_segment"]],
            on="user_id",
            how="left"
        )
        df_merged["to_segment"] = df_merged["to_segment"].fillna(8).astype(int)

        # 使用语义层获取所有象限
        registry = get_registry()
        all_segments = registry.list_all()
        segment_ids = sorted([s.segment_id for s in all_segments if s.segment_id != 9]) + [9]

        # Nodes: 左节点（from阶段）+ 右节点（to阶段）
        nodes = []
        for seg_id in segment_ids:
            seg = registry.get(seg_id)
            if seg:
                nodes.append({
                    "id": f"from_{seg_id}",
                    "name": seg.name_cn,
                    "color": seg.color,
                    "stage": "from"
                })
                nodes.append({
                    "id": f"to_{seg_id}",
                    "name": seg.name_cn,
                    "color": seg.color,
                    "stage": "to"
                })

        # Links: 流转边
        links = []
        for f in segment_ids:
            for t in segment_ids:
                count = len(df_merged[
                    (df_merged["from_segment"] == f) &
                    (df_merged["to_segment"] == t)
                ])
                if count > 0:
                    links.append({
                        "source": f"from_{f}",
                        "target": f"to_{t}",
                        "value": count
                    })

        return {
            "nodes": nodes,
            "links": links,
            "from_date": from_date,
            "to_date": to_date
        }
    finally:
        conn.close()