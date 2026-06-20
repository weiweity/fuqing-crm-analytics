"""
Sample CRM 客户分析系统 - 流失预警服务
Week 3 流失风险分析（动态阈值 + 单品类）
所有 SQL 均使用参数化查询，无 SQL 注入风险

Sprint 54 Lane B L3 FilterBuilder 改造:
- 4 个 builder (_build_dynamic_churn_sql / _build_fixed_churn_sql /
  _build_dynamic_user_sql / _build_fixed_user_sql) 中 6 处 (valid_order filter) +
  多处 ex_clause 字符串拼接 — 全部收到 `?` DB-API 参数化.
- 设计原则:
  1. valid_order / exclude_channels 用 FilterBuilder.build() 统一产出.
  2. pay_time >= ? 进 add_extra (保留原始 date 字符串形式, 不切到 with_time_range
     因为 builder 需要 lookback_start 而不是 start_dt/end_dt 范围).
  3. order_intervals 特有的 `spu_product_class IS NOT NULL` 走专用 helper.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from backend.db.connection import get_connection
from backend.semantic.filters import FilterBuilder, MetricType
from backend.semantic.segments import get_registry


def _segment_name(seg_id: int) -> str:
    """从 registry 获取象限中文名，避免硬编码"""
    registry = get_registry()
    seg = registry.get(seg_id)
    return seg.name_cn if seg else "其他"

# 固定阈值（当购买次数 < 3 或 churn_mode=fixed 时使用）
FIXED_R_THRESHOLD = 90  # R > 90天 为高风险


# ─────────────────────────────────────────────────────────────
# Sprint 54 Lane B L3 FilterBuilder helpers
#
# 三个 helper 把 churn_service.py 4 个 builder 的 WHERE 统一收到 `?` DB-API
# 参数化:
#   _build_order_intervals_where — 动态流失 order_intervals CTE 用 (含 spu_product_class 检查)
#   _build_user_orders_where     — 4 个 builder 的 user_last_order / ulo 子查询共用
#   _build_segment_filter        — segment_id 可选过滤 (用 add_extra)
# ─────────────────────────────────────────────────────────────


def _build_order_intervals_where(
    lookback_start: str,
    exclude_channels: Optional[List[str]],
) -> Tuple[str, List[Any]]:
    """动态流失 order_intervals CTE 过滤器.

    等价于原 WHERE:
        WHERE (valid_order filter)
          AND o.spu_product_class IS NOT NULL
          AND o.pay_time >= ?
          AND (exclude-channel filter, optional)

    Returns:
        (where_sql, params) — [lookback_start, ...ex_params].
    """
    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    if exclude_channels:
        fb.with_exclude_channels(exclude_channels)
    where_sql, params = fb.build()
    extra_sql = "o.spu_product_class IS NOT NULL AND o.pay_time >= ?"
    extra_params: List[Any] = [lookback_start]
    return f"{extra_sql} AND {where_sql}", extra_params + params


def _build_user_orders_where(
    lookback_start: str,
    exclude_channels: Optional[List[str]],
    alias: str = "o",
) -> Tuple[str, List[Any]]:
    """user_last_order / ulo 过滤器 (4 个 builder 共用).

    等价于原 WHERE (alias 默认为 "o", 固定阈值的 ulo 子查询用 alias="" 表示无别名):
        WHERE (valid_order filter)
          AND {alias}pay_time >= ?
          AND (exclude-channel filter, optional)

    Args:
        alias: 表别名 ("o" 表示 `FROM orders o`, "" 表示 `FROM orders`).

    Returns:
        (where_sql, params) — [lookback_start, ...ex_params].
    """
    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    if exclude_channels:
        fb.with_exclude_channels(exclude_channels)
    where_sql, params = fb.build()
    prefix = f"{alias}." if alias else ""
    extra_sql = f"{prefix}pay_time >= ?"
    extra_params: List[Any] = [lookback_start]
    return f"{extra_sql} AND {where_sql}", extra_params + params


def _build_segment_filter(segment_id: Optional[int]) -> Tuple[str, List[Any]]:
    """segment_id 可选过滤器.

    Returns:
        ("AND r.segment_id = ?", [segment_id]) 或 ("", []).
    """
    if segment_id is None:
        return "", []
    return "AND r.segment_id = ?", [segment_id]


def get_churn_risk_distribution(
    date: str,
    segment_id: Optional[int] = None,
    churn_mode: str = "dynamic",
    fixed_threshold: int = 60,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    获取各象限流失风险分布

    Args:
        date: 分析日期 (YYYY-MM-DD)
        segment_id: 可选，筛选特定象限
        churn_mode: 'dynamic'（动态阈值）或 'fixed'（固定阈值）
        fixed_threshold: 固定阈值天数（仅 fixed 模式使用）

    Returns:
        {
            "date": str,
            "churn_mode": str,
            "total_users": int,
            "high_risk": int,
            "medium_risk": int,
            "low_risk": int,
            "by_segment": {
                "1": {"name": "钻石会员", "high": 0, "medium": 0, "low": 0},
                ...
            }
        }
    """
    conn = get_connection()

    try:
        if churn_mode == "dynamic":
            sql, params = _build_dynamic_churn_sql(date, segment_id, exclude_channels)
        else:
            sql, params = _build_fixed_churn_sql(date, segment_id, fixed_threshold, exclude_channels)

        df = conn.execute(sql, params).fetchdf()

        # 按象限和风险等级聚合
        if "segment_id" not in df.columns or "risk_level" not in df.columns:
            return _empty_distribution(date, churn_mode)

        by_segment = {}
        for seg_id in range(1, 10):
            seg_df = df[df["segment_id"] == seg_id] if "segment_id" in df.columns else pd.DataFrame()
            by_segment[str(seg_id)] = {
                "name": _segment_name(seg_id),
                "high": int(len(seg_df[seg_df["risk_level"] == "high"])) if "risk_level" in df.columns else 0,
                "medium": int(len(seg_df[seg_df["risk_level"] == "medium"])) if "risk_level" in df.columns else 0,
                "low": int(len(seg_df[seg_df["risk_level"] == "low"])) if "risk_level" in df.columns else 0,
            }

        total = len(df)
        high = int(len(df[df["risk_level"] == "high"])) if "risk_level" in df.columns else 0
        medium = int(len(df[df["risk_level"] == "medium"])) if "risk_level" in df.columns else 0
        low = int(len(df[df["risk_level"] == "low"])) if "risk_level" in df.columns else 0

        return {
            "date": date,
            "churn_mode": churn_mode,
            "total_users": total,
            "high_risk": high,
            "medium_risk": medium,
            "low_risk": low,
            "high_risk_rate": round(high / total, 4) if total > 0 else 0,
            "by_segment": by_segment
        }
    finally:
        pass


def get_churn_risk_users(
    date: str,
    risk_level: Optional[str] = None,
    segment_id: Optional[int] = None,
    churn_mode: str = "dynamic",
    fixed_threshold: int = 60,
    limit: int = 100,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    获取高流失风险用户列表
    """
    conn = get_connection()

    try:
        if churn_mode == "dynamic":
            sql, params = _build_dynamic_user_sql(date, segment_id, limit, exclude_channels)
        else:
            sql, params = _build_fixed_user_sql(date, segment_id, fixed_threshold, limit, exclude_channels)

        df = conn.execute(sql, params).fetchdf()

        if df.empty:
            return {
                "date": date,
                "mode": churn_mode,
                "total_matched": 0,
                "users": [],
            }

        if risk_level:
            df = df[df["risk_level"] == risk_level]

        total_matched = len(df)
        users = df.to_dict("records")
        for row in users:
            row["segment_name"] = _segment_name(int(row.get("segment_id", 9)))
            row["risk_score"] = float(row.get("risk_score", 0) or 0.0)

        # 简化返回结构
        user_list = []
        for row in users:
            user_list.append({
                "user_id": row.get("user_id", ""),
                "segment_id": int(row.get("segment_id", 9)),
                "segment_name": row.get("segment_name", "其他"),
                "risk_score": row.get("risk_score", 0.0),
                "risk_level": row.get("risk_level", "low"),
                "last_order_days": int(row.get("last_order_days", 0) or 0),
                "frequency": int(row.get("frequency", 0) or 0),
                "monetary": float(row.get("monetary", 0.0) or 0.0),
            })

        return {
            "date": date,
            "mode": churn_mode,
            "total_matched": total_matched,
            "users": user_list[:limit]
        }
    finally:
        pass


def _build_dynamic_churn_sql(
    date: str, segment_id: Optional[int], exclude_channels: Optional[List[str]] = None
) -> Tuple[str, list]:
    """
    构建动态阈值流失分布 SQL（参数化查询）
    Returns: (sql_string, params_list)

    SQL 中 ? 出现顺序:
        order_intervals(lookback, ex) → user_last_order(lookback, ex) →
        DATE(?) → analysis_date=? → seg_filter(?)
    """
    analysis_date = datetime.strptime(date, "%Y-%m-%d")
    lookback_start = (analysis_date - timedelta(days=730)).strftime("%Y-%m-%d")

    # order_intervals 过滤器 (含 spu_product_class IS NOT NULL)
    oi_where, oi_params = _build_order_intervals_where(lookback_start, exclude_channels)
    # user_last_order 过滤器
    ulo_where, ulo_params = _build_user_orders_where(lookback_start, exclude_channels)
    # segment_id 过滤
    seg_sql, seg_params = _build_segment_filter(segment_id)

    # params 顺序: oi + ulo + DATE(?) + analysis_date + seg
    params: List[Any] = []
    params.extend(oi_params)
    params.extend(ulo_params)
    params.append(date)  # DATE(?)
    params.append(date)  # analysis_date = ?
    params.extend(seg_params)

    sql = f"""
    WITH order_intervals AS (
        SELECT
            o.user_id,
            o.spu_product_class,
            o.pay_time,
            LAG(o.pay_time) OVER (
                PARTITION BY o.user_id, o.spu_product_class
                ORDER BY o.pay_time
            ) AS prev_pay_time
        FROM orders o
        WHERE {oi_where}
    ),
    user_cycle AS (
        SELECT
            user_id,
            spu_product_class,
            MEDIAN(DATEDIFF('day', prev_pay_time, pay_time)) AS typical_cycle_days,
            COUNT(*) AS order_count
        FROM order_intervals
        WHERE prev_pay_time IS NOT NULL
        GROUP BY user_id, spu_product_class
        HAVING COUNT(*) >= 2
    ),
    user_last_order AS (
        SELECT
            o.user_id,
            MAX(o.pay_time) AS last_pay_time,
            COUNT(DISTINCT o.order_id) AS frequency,
            SUM(o.actual_amount) AS monetary
        FROM orders o
        WHERE {ulo_where}
        GROUP BY o.user_id
    ),
    user_rfm_base AS (
        SELECT
            ulo.user_id,
            ulo.last_pay_time,
            ulo.frequency,
            ulo.monetary,
            r.segment_id,
            DATEDIFF('day', ulo.last_pay_time, DATE(?)) AS last_order_days
        FROM user_last_order ulo
        LEFT JOIN user_rfm r
            ON ulo.user_id = r.user_id
            AND r.analysis_date = ?
            AND r.metric_type = 'GMV'
            AND r.lookback_days = 90
        WHERE ulo.last_pay_time IS NOT NULL
        {seg_sql}
    ),
    user_churn AS (
        SELECT
            u.user_id,
            u.segment_id,
            u.last_order_days,
            u.frequency,
            u.monetary,
            CASE
                WHEN u.frequency < 3 THEN
                    CASE
                        WHEN u.last_order_days > {FIXED_R_THRESHOLD} THEN 'high'
                        WHEN u.last_order_days > 30 THEN 'medium'
                        ELSE 'low'
                    END
                WHEN uc.typical_cycle_days IS NULL THEN
                    CASE
                        WHEN u.last_order_days > {FIXED_R_THRESHOLD} THEN 'high'
                        WHEN u.last_order_days > 30 THEN 'medium'
                        ELSE 'low'
                    END
                ELSE
                    CASE
                        WHEN (u.last_order_days - uc.typical_cycle_days) * 100.0 / NULLIF(uc.typical_cycle_days, 0) > 150 THEN 'high'
                        WHEN (u.last_order_days - uc.typical_cycle_days) * 100.0 / NULLIF(uc.typical_cycle_days, 0) > 100 THEN 'medium'
                        ELSE 'low'
                    END
            END AS risk_level,
            CASE
                WHEN u.frequency < 3 OR uc.typical_cycle_days IS NULL THEN
                    CAST({FIXED_R_THRESHOLD} AS DOUBLE)
                ELSE
                    (u.last_order_days - COALESCE(uc.typical_cycle_days, {FIXED_R_THRESHOLD})) * 100.0 / NULLIF(COALESCE(uc.typical_cycle_days, {FIXED_R_THRESHOLD}), 0)
            END AS risk_score
        FROM user_rfm_base u
        LEFT JOIN user_cycle uc ON u.user_id = uc.user_id
    )
    SELECT
        user_id,
        COALESCE(segment_id, 9) AS segment_id,
        last_order_days,
        frequency,
        monetary,
        risk_level,
        risk_score
    FROM user_churn
    """
    return sql, params


def _build_fixed_churn_sql(
    date: str, segment_id: Optional[int], threshold: int, exclude_channels: Optional[List[str]] = None
) -> Tuple[str, list]:
    """
    构建固定阈值流失分布 SQL（参数化查询）
    Returns: (sql_string, params_list)

    SQL 中 ? 顺序:
        DATE(?)x4 → ulo 子查询(lookback, ex) → analysis_date=? → seg_filter(?)
    """
    analysis_date = datetime.strptime(date, "%Y-%m-%d")
    lookback_start = (analysis_date - timedelta(days=730)).strftime("%Y-%m-%d")

    ulo_where, ulo_params = _build_user_orders_where(lookback_start, exclude_channels, alias="")
    seg_sql, seg_params = _build_segment_filter(segment_id)

    # params 顺序: DATE(?)x4 + ulo + analysis_date + seg
    params: List[Any] = []
    params.extend([date, date, date, date])  # 4 个 DATE(?)
    params.extend(ulo_params)
    params.append(date)  # analysis_date = ?
    params.extend(seg_params)

    sql = f"""
    SELECT
        ulo.user_id,
        COALESCE(r.segment_id, 9) AS segment_id,
        DATEDIFF('day', ulo.last_pay_time, DATE(?)) AS last_order_days,
        ulo.frequency,
        ulo.monetary,
        CASE
            WHEN DATEDIFF('day', ulo.last_pay_time, DATE(?)) > {threshold} THEN 'high'
            WHEN DATEDIFF('day', ulo.last_pay_time, DATE(?)) > 30 THEN 'medium'
            ELSE 'low'
        END AS risk_level,
        DATEDIFF('day', ulo.last_pay_time, DATE(?)) AS risk_score
    FROM (
        SELECT user_id, MAX(pay_time) AS last_pay_time,
               COUNT(DISTINCT order_id) AS frequency,
               SUM(actual_amount) AS monetary
        FROM orders
        WHERE {ulo_where}
        GROUP BY user_id
    ) ulo
    LEFT JOIN user_rfm r
        ON ulo.user_id = r.user_id
        AND r.analysis_date = ?
        AND r.metric_type = 'GMV'
        AND r.lookback_days = 90
    WHERE 1=1
    {seg_sql}
    """
    return sql, params


def _build_dynamic_user_sql(
    date: str, segment_id: Optional[int], limit: int, exclude_channels: Optional[List[str]] = None
) -> Tuple[str, list]:
    """
    构建动态阈值用户列表 SQL（参数化查询）
    Returns: (sql_string, params_list)

    SQL 中 ? 顺序:
        order_intervals(lookback, ex) → user_last_order(lookback, ex) →
        DATE(?) → analysis_date=? → seg_filter(?) → LIMIT ?
    """
    analysis_date = datetime.strptime(date, "%Y-%m-%d")
    lookback_start = (analysis_date - timedelta(days=730)).strftime("%Y-%m-%d")

    oi_where, oi_params = _build_order_intervals_where(lookback_start, exclude_channels)
    ulo_where, ulo_params = _build_user_orders_where(lookback_start, exclude_channels)
    seg_sql, seg_params = _build_segment_filter(segment_id)

    params: List[Any] = []
    params.extend(oi_params)
    params.extend(ulo_params)
    params.append(date)  # DATE(?)
    params.append(date)  # analysis_date = ?
    params.extend(seg_params)
    params.append(limit)

    sql = f"""
    WITH order_intervals AS (
        SELECT
            o.user_id,
            o.spu_product_class,
            o.pay_time,
            LAG(o.pay_time) OVER (
                PARTITION BY o.user_id, o.spu_product_class
                ORDER BY o.pay_time
            ) AS prev_pay_time
        FROM orders o
        WHERE {oi_where}
    ),
    user_cycle AS (
        SELECT
            user_id,
            spu_product_class,
            MEDIAN(DATEDIFF('day', prev_pay_time, pay_time)) AS typical_cycle_days
        FROM order_intervals
        WHERE prev_pay_time IS NOT NULL
        GROUP BY user_id, spu_product_class
        HAVING COUNT(*) >= 2
    ),
    user_last_order AS (
        SELECT
            o.user_id,
            MAX(o.pay_time) AS last_pay_time,
            COUNT(DISTINCT o.order_id) AS frequency,
            SUM(o.actual_amount) AS monetary
        FROM orders o
        WHERE {ulo_where}
        GROUP BY o.user_id
    ),
    user_rfm_base AS (
        SELECT
            ulo.user_id,
            ulo.last_pay_time,
            ulo.frequency,
            ulo.monetary,
            r.segment_id,
            DATEDIFF('day', ulo.last_pay_time, DATE(?)) AS last_order_days
        FROM user_last_order ulo
        LEFT JOIN user_rfm r
            ON ulo.user_id = r.user_id
            AND r.analysis_date = ?
            AND r.metric_type = 'GMV'
            AND r.lookback_days = 90
        WHERE ulo.last_pay_time IS NOT NULL
        {seg_sql}
    ),
    user_churn AS (
        SELECT
            u.user_id,
            COALESCE(u.segment_id, 9) AS segment_id,
            u.last_order_days,
            u.frequency,
            u.monetary,
            CASE
                WHEN u.frequency < 3 THEN
                    CASE
                        WHEN u.last_order_days > {FIXED_R_THRESHOLD} THEN 'high'
                        WHEN u.last_order_days > 30 THEN 'medium'
                        ELSE 'low'
                    END
                WHEN uc.typical_cycle_days IS NULL THEN
                    CASE
                        WHEN u.last_order_days > {FIXED_R_THRESHOLD} THEN 'high'
                        WHEN u.last_order_days > 30 THEN 'medium'
                        ELSE 'low'
                    END
                ELSE
                    CASE
                        WHEN (u.last_order_days - uc.typical_cycle_days) * 100.0 / NULLIF(uc.typical_cycle_days, 0) > 150 THEN 'high'
                        WHEN (u.last_order_days - uc.typical_cycle_days) * 100.0 / NULLIF(uc.typical_cycle_days, 0) > 100 THEN 'medium'
                        ELSE 'low'
                    END
            END AS risk_level,
            CASE
                WHEN u.frequency < 3 THEN CAST(u.last_order_days AS DOUBLE)
                ELSE (u.last_order_days - COALESCE(uc.typical_cycle_days, {FIXED_R_THRESHOLD})) * 100.0 / NULLIF(COALESCE(uc.typical_cycle_days, {FIXED_R_THRESHOLD}), 0)
            END AS risk_score
        FROM user_rfm_base u
        LEFT JOIN user_cycle uc ON u.user_id = uc.user_id
    )
    SELECT *
    FROM user_churn
    ORDER BY risk_score DESC, last_order_days DESC
    LIMIT ?
    """
    return sql, params


def _build_fixed_user_sql(
    date: str, segment_id: Optional[int], threshold: int, limit: int, exclude_channels: Optional[List[str]] = None
) -> Tuple[str, list]:
    """
    构建固定阈值用户列表 SQL（参数化查询）
    Returns: (sql_string, params_list)

    SQL 中 ? 顺序:
        DATE(?)x4 → ulo 子查询(lookback, ex) → analysis_date=? → seg_filter(?) → LIMIT ?
    """
    analysis_date = datetime.strptime(date, "%Y-%m-%d")
    lookback_start = (analysis_date - timedelta(days=730)).strftime("%Y-%m-%d")

    ulo_where, ulo_params = _build_user_orders_where(lookback_start, exclude_channels, alias="")
    seg_sql, seg_params = _build_segment_filter(segment_id)

    params: List[Any] = []
    params.extend([date, date, date, date])  # 4 个 DATE(?)
    params.extend(ulo_params)
    params.append(date)  # analysis_date = ?
    params.extend(seg_params)
    params.append(limit)

    sql = f"""
    SELECT
        ulo.user_id,
        COALESCE(r.segment_id, 9) AS segment_id,
        DATEDIFF('day', ulo.last_pay_time, DATE(?)) AS last_order_days,
        ulo.frequency,
        ulo.monetary,
        CASE
            WHEN DATEDIFF('day', ulo.last_pay_time, DATE(?)) > {threshold} THEN 'high'
            WHEN DATEDIFF('day', ulo.last_pay_time, DATE(?)) > 30 THEN 'medium'
            ELSE 'low'
        END AS risk_level,
        DATEDIFF('day', ulo.last_pay_time, DATE(?)) AS risk_score
    FROM (
        SELECT user_id, MAX(pay_time) AS last_pay_time,
               COUNT(DISTINCT order_id) AS frequency,
               SUM(actual_amount) AS monetary
        FROM orders
        WHERE {ulo_where}
        GROUP BY user_id
    ) ulo
    LEFT JOIN user_rfm r
        ON ulo.user_id = r.user_id
        AND r.analysis_date = ?
        AND r.metric_type = 'GMV'
        AND r.lookback_days = 90
    WHERE 1=1
    {seg_sql}
    ORDER BY risk_score DESC
    LIMIT ?
    """
    return sql, params


def _empty_distribution(date: str, churn_mode: str) -> Dict[str, Any]:
    """返回空分布"""
    by_segment = {
        str(seg_id): {"name": _segment_name(seg_id), "high": 0, "medium": 0, "low": 0}
        for seg_id in range(1, 10)
    }
    return {
        "date": date,
        "churn_mode": churn_mode,
        "total_users": 0,
        "high_risk": 0,
        "medium_risk": 0,
        "low_risk": 0,
        "high_risk_rate": 0,
        "by_segment": by_segment
    }
