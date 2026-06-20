"""
Sample CRM 客户分析系统 - 人群流转分析服务
Week 3 人群流转矩阵数据

Sprint 36-6 清理: 删 get_flow_sankey (前端 0 + 后端 0 业务消费).
接入语义层: 使用 semantic/segments.py 中的 SegmentRegistry 作为唯一真实数据源。
"""

import duckdb
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from functools import lru_cache
from backend.db.connection import get_connection
from backend.semantic.segments import get_registry
from backend.semantic.filters import FilterBuilder, MetricType


# ─────────────────────────────────────────────────────────────
# Sprint 54 Lane A L3 FilterBuilder helpers
#
# 两个 helper 把 flow_service 2 处 valid_sql f-string 内嵌统一收到 `?` DB-API 参数化.
# 设计原则 (跟 Sprint 53.5 churn.py 一致):
#   1. F/M 指标 (lookback_days 窗口) 应用 channel 排除; R 指标 (365 天固定) 不应用
#      (与 preload_rfm.py 口径一致).
#   2. 所有用户输入 (channel) 走 `?` 占位符.
#   3. 返回 (where_sql, params) 直接拼到 SQL 的 WHERE 子句.
# ─────────────────────────────────────────────────────────────


def _build_flow_fm_filter(
    start_date: str,
    end_date: str,
    exclude_channels: Optional[List[str]] = None,
) -> Tuple[str, List[Any]]:
    """flow_service F/M 指标过滤器 (含 time + valid_order + exclude_channels).

    Returns:
        (where_sql, params) — 含 time range (lookback_days 窗口) + valid_order 三条件
        + exclude_channels NOT IN.
    """
    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    fb.with_time_range(start_date, end_date)
    if exclude_channels:
        fb.with_exclude_channels(exclude_channels)
    return fb.build()


def _build_flow_r_filter(
    start_date: str,
    end_date: str,
) -> Tuple[str, List[Any]]:
    """flow_service R 指标过滤器 (含 time + valid_order, 不含 channel 过滤).

    R 指标用固定 365 天窗口, 不应用 channel 过滤 (与 preload_rfm.py 口径一致).

    Returns:
        (where_sql, params) — 含 time range + valid_order 三条件.
    """
    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    fb.with_time_range(start_date, end_date)
    return fb.build()



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
        pass


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

    Sprint 54 Lane A L3: 2 处 valid_sql 字符串内嵌 → FilterBuilder.build() 参数化.
    F/M 窗口 (lookback_days) 应用 channel 过滤, R 窗口 (365 天) 不应用 (跟预计算口径一致).
    """
    from datetime import datetime, timedelta
    from backend.semantic.segments import RFM_THRESHOLDS

    start_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    r_start_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=365)).strftime("%Y-%m-%d")
    amount_cond = "actual_amount > 0" if metric_type == "GMV" else "actual_amount >= 0"

    registry = get_registry()
    r_score_sql = registry.build_r_score_sql(RFM_THRESHOLDS["r"])
    f_score_sql = registry.build_f_score_sql(RFM_THRESHOLDS["f"])
    m_score_sql = registry.build_m_score_sql(RFM_THRESHOLDS["m"])
    segment_sql = registry.build_segment_case_when_sql()

    # F/M 指标: lookback_days 窗口 + channel 过滤
    fb_fm = FilterBuilder()
    fb_fm.with_metric_type(MetricType.GSV)
    fb_fm.with_time_range(start_date, date)
    if exclude_channels:
        fb_fm.with_exclude_channels(exclude_channels)
    where_fm, params_fm = fb_fm.build()

    # R 指标: 365 天固定窗口, 不带 channel 过滤 (与 preload_rfm.py 口径一致)
    fb_r = FilterBuilder()
    fb_r.with_metric_type(MetricType.GSV)
    fb_r.with_time_range(r_start_date, date)
    where_r, params_r = fb_r.build()

    # params 顺序:
    # 1. base_params CTE: analysis_date, start_date, r_start_date (3 个)
    # 2. user_with_rfm: recency_days (1 个)
    # 3. where_fm params (time range + exclude channels)
    # 4. where_r params (time range)
    params = [date, start_date, r_start_date, date] + params_fm + params_r

    sql = f"""
    WITH base_params AS (
        SELECT
            DATE(?) AS analysis_date,
            DATE(?) AS start_date,
            DATE(?) AS r_start_date
    ),
    -- F/M 指标: 使用 lookback_days 窗口, 应用 channel 过滤
    fm_orders AS (
        SELECT o.user_id, o.actual_amount, o.order_id, o.pay_time
        FROM orders o
        WHERE {where_fm}
          AND ({amount_cond})
    ),
    fm_metrics AS (
        SELECT
            user_id,
            SUM(actual_amount) AS monetary,
            COUNT(DISTINCT order_id) AS frequency,
            MAX(pay_time) AS last_pay_time
        FROM fm_orders
        GROUP BY user_id
    ),
    -- R 指标: 使用固定 365 天窗口, 不应用 channel 过滤 (与预计算口径一致)
    r_orders AS (
        SELECT o.user_id, MAX(o.pay_time) AS r_last_pay_time
        FROM orders o
        WHERE {where_r}
          AND ({amount_cond})
        GROUP BY o.user_id
    ),
    user_with_rfm AS (
        SELECT
            fm.user_id,
            fm.monetary,
            fm.frequency,
            -- R基于 365 天窗口的最近购买, F/M 基于 lookback_days 窗口
            DATEDIFF('day', COALESCE(r.r_last_pay_time, fm.last_pay_time), DATE(?)) AS recency_days
        FROM fm_metrics fm
        LEFT JOIN r_orders r ON fm.user_id = r.user_id
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

        # 使用语义层获取所有象限
        registry = get_registry()
        all_segments = registry.list_all()

        # NxN 矩阵：用 groupby 一次性聚合，替代 N*N 逐对过滤
        flow_counts = (
            df_merged.groupby(["from_segment", "to_segment"])
            .size()
            .reset_index(name="count")
        )
        matrix_records = [
            {"from": int(row.from_segment), "to": int(row.to_segment), "count": int(row["count"])}
            for _, row in flow_counts.iterrows()
            if row["count"] > 0
        ]

        # 汇总指标
        from_total = len(df_from)
        to_total = len(df_to)

        # 留存/升级/降级：向量化操作
        same = df_merged["from_segment"] == df_merged["to_segment"]
        retained = same.sum()
        retention_rate = round(retained / from_total, 4) if from_total > 0 else 0

        upgraded = (df_merged["to_segment"] < df_merged["from_segment"]).sum()
        downgraded = (df_merged["to_segment"] > df_merged["from_segment"]).sum()
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
        pass