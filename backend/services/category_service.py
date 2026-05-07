"""
芙清 CRM 客户分析系统 - 品类分析服务
Week 4 品类分布、品类象限矩阵、品类用户画像
"""

import duckdb
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from backend.db.connection import get_connection
from backend.semantic.filters import OrderFilters, expand_channels
from backend.semantic.calculations import yoy_absolute, yoy_ratio


def _normalize_date(date_val) -> str:
    """统一日期格式处理(兼容 date 对象和字符串)"""
    if hasattr(date_val, 'strftime'):
        return date_val.strftime("%Y-%m-%d")
    if isinstance(date_val, str):
        return date_val[:10] if len(date_val) > 10 else date_val
    return str(date_val)


from backend.semantic.segments import get_registry


def _segment_meta(seg_id: int) -> dict:
    """从 registry 获取象限元数据,避免硬编码"""
    registry = get_registry()
    seg = registry.get(seg_id)
    if seg:
        return {"name": seg.name_cn, "en": seg.name_en, "color": seg.color}
    return {"name": "其他", "en": "Others", "color": "#BDC3C7"}


# SPU 字段映射
SPU_LEVELS = {
    "category": "spu_category",      # 一级品类
    "type": "spu_type",               # 二级品类
    "tier": "spu_tier",              # 层级
    "class": "spu_product_class",    # 产品类
    "subclass": "spu_product_subclass",  # 产品子类
    "cosmetic": "spu_cosmetic",      # 功效
    "spec": "spu_spec",              # 规格
}


def get_category_distribution(
    date: str,
    lookback_days: int = 90,
    level: str = "category",
    segment_id: Optional[int] = None,
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    获取品类分布 (GSV口径)

    Args:
        date: 分析日期 (YYYY-MM-DD)
        lookback_days: 回溯天数
        level: category/type/tier/class/subclass/cosmetic/spec
        segment_id: 象限筛选(可选)
        channel: 渠道筛选(可选)
        exclude_channels: 排除的渠道列表

    Returns:
        {
            "date": str,
            "level": str,
            "total_users": int,
            "total_gmv": float,
            "distribution": [{"name": str, "user_count": int, "gmv": float, "占比": float}, ...]
        }
    """
    if level not in SPU_LEVELS:
        raise ValueError(f"Invalid level: {level}")
    category_field = SPU_LEVELS[level]
    category_field_expr = f"COALESCE(o.{category_field}, '未知')"

    # 使用语义层构建过滤条件
    valid_sql, _ = OrderFilters.valid_order()

    # 渠道参数展开
    def _expand_filters(ch: Optional[str], ex: Optional[List[str]]) -> tuple:

        ch_filter, ch_params = "", []
        if ch and ch != "全店":
            db = expand_channels([ch])
            if len(db) == 1:
                ch_filter = "AND o.channel = ?"
                ch_params = [db[0]]
            else:
                ch_filter = f"AND o.channel IN ({','.join(['?'] * len(db))})"
                ch_params = list(db)
        ex_filter, ex_params = "", []
        if ex:
            ex_db = expand_channels(ex)
            ex_filter = f"AND o.channel NOT IN ({','.join(['?'] * len(ex_db))})"
            ex_params = list(ex_db)
        return ch_filter, ch_params, ex_filter, ex_params

    channel_filter, channel_params, exclude_filter, exclude_params = _expand_filters(channel, exclude_channels)

    # 象限筛选
    segment_filter = ""
    if segment_id is not None:
        segment_filter = "AND r.segment_id = ?"

    # 日期计算（params 依赖此变量）
    date_str = _normalize_date(date)
    start_date = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    sql = f"""
    WITH base_params AS (
        SELECT DATE(?) AS analysis_date, DATE(?) AS start_date
    ),
    period_orders AS (
        SELECT o.user_id, o.actual_amount, o.order_id, o.is_member,
               {category_field_expr} AS category_name
        FROM orders o
        CROSS JOIN base_params p
        LEFT JOIN user_rfm r ON o.user_id = r.user_id
            AND r.analysis_date = ? AND r.metric_type = 'GMV' AND r.lookback_days = ?
        WHERE o.pay_time >= p.start_date
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          {segment_filter}
          {channel_filter}
          {exclude_filter}
    ),
    category_summary AS (
        SELECT category_name,
               COUNT(DISTINCT user_id) AS user_count,
               COUNT(DISTINCT CASE WHEN is_member THEN user_id END) AS member_count,
               SUM(actual_amount) AS gmv,
               SUM(CASE WHEN is_member THEN actual_amount ELSE 0 END) AS member_gsv
        FROM period_orders
        GROUP BY category_name
    )
    SELECT category_name, user_count, member_count, gmv, member_gsv
    FROM category_summary ORDER BY gmv DESC
    """

    total_query = f"""
    WITH base_params AS (
        SELECT DATE(?) AS analysis_date, DATE(?) AS start_date
    )
    SELECT COUNT(DISTINCT o.user_id) AS total_users,
           COUNT(DISTINCT CASE WHEN o.is_member THEN o.user_id END) AS total_members,
           SUM(o.actual_amount) AS total_gmv
    FROM orders o
    CROSS JOIN base_params p
    LEFT JOIN user_rfm r ON o.user_id = r.user_id
        AND r.analysis_date = ? AND r.metric_type = 'GMV' AND r.lookback_days = ?
    WHERE o.pay_time >= p.start_date
      AND o.pay_time < DATE(?) + INTERVAL '1' DAY
      AND {valid_sql}
      {segment_filter}
      {channel_filter}
      {exclude_filter}
    """

    conn = get_connection()
    try:
        # 参数顺序: date_str, start_date, date_str, lookback_days, date_str, [segment_id], [channel_params], [exclude_params]
        params = [date_str, start_date, date_str, lookback_days, date_str]
        if segment_id is not None:
            params.append(segment_id)
        params.extend(channel_params)
        params.extend(exclude_params)

        result = conn.execute(sql, params).fetchall()
        total_result = conn.execute(total_query, params).fetchone()
        total_users = int(total_result[0]) if total_result[0] else 0
        total_members = int(total_result[1]) if total_result[1] else 0
        total_gmv = float(total_result[2]) if total_result[2] else 0.0
    finally:
        conn.close()

    distribution = []
    for row in result:
        category_name = row[0]
        user_count = int(row[1]) if row[1] else 0
        member_count = int(row[2]) if row[2] else 0
        gmv = float(row[3]) if row[3] else 0.0
        member_gsv = float(row[4]) if row[4] else 0.0
        pct = round(user_count / total_users * 100, 2) if total_users > 0 else 0
        penetration_rate = round(user_count / total_users, 4) if total_users > 0 else 0.0
        member_ratio = round(member_gsv / gmv, 4) if gmv > 0 else 0.0
        distribution.append({
            "name": category_name,
            "user_count": user_count,
            "member_count": member_count,
            "gmv": round(gmv, 2),
            "member_gsv": round(member_gsv, 2),
            "pct": pct,
            "penetration_rate": penetration_rate,
            "member_ratio": member_ratio,
        })

    return {
        "date": date_str,
        "level": level,
        "total_users": total_users,
        "total_members": total_members,
        "total_gmv": round(total_gmv, 2),
        "distribution": distribution
    }


def get_category_segment_matrix(
    date: str,
    lookback_days: int = 90,
    level: str = "type",
    top_n: int = 10,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    获取品类-象限交叉矩阵
    Plan B: 实时 SQL RFM 计算(全历史 F),与老客健康模块口径一致

    Args:
        date: 分析日期 (YYYY-MM-DD)
        lookback_days: 回溯天数
        level: category/type/tier/class/subclass/cosmetic/spec
        top_n: 每个象限返回前 N 个品类
        exclude_channels: 排除的渠道列表

    Returns:
        {
            "date": str,
            "level": str,
            "matrix": {
                "1": [{"category": str, "user_count": int, "gmv": float}, ...],
                ...
            },
            "segments": [{"id": int, "name": str, "color": str}, ...]
        }
    """
    conn = get_connection()
    try:
        date_str = _normalize_date(date)
        start_date = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        # 使用语义层构建过滤条件
        valid_sql, _ = OrderFilters.valid_order()

        category_field = SPU_LEVELS.get(level, "spu_type")
        category_field_expr = f"COALESCE(o.{category_field}, '未知')"

        # 排除渠道

        exclude_filter = ""
        exclude_params: List[str] = []
        if exclude_channels:
            db_ex = expand_channels(exclude_channels)
            placeholders = ",".join(["?"] * len(db_ex))
            exclude_filter = f"AND o.channel NOT IN ({placeholders})"
            exclude_params = list(db_ex)

        # 统一引用 semantic/segments.py 中的 RFM_THRESHOLDS,禁止硬编码
        from backend.semantic.segments import RFM_THRESHOLDS

        _rt = RFM_THRESHOLDS["r"]
        _ft = RFM_THRESHOLDS["f"]
        _mt = RFM_THRESHOLDS["m"]

        sql = f"""
        WITH base_params AS (
            SELECT DATE(?) AS analysis_date, DATE(?) AS start_date
        ),
        -- 全历史用户统计(用于 RFM 计算,截止 analysis_date)
        user_stats_all AS (
            SELECT
                o.user_id,
                MAX(o.pay_time) AS last_pay_time,
                COUNT(DISTINCT o.order_id) AS order_count,
                SUM(o.actual_amount) AS gsv
            FROM orders o
            WHERE o.pay_time <= (SELECT analysis_date FROM base_params) + INTERVAL '1' DAY
              AND o.pay_time >= '2000-01-01'
              AND {valid_sql}
              {exclude_filter}
            GROUP BY o.user_id
        ),
        rfm_scored AS (
            SELECT
                user_id,
                CASE
                    WHEN DATEDIFF('day', last_pay_time::DATE, (SELECT analysis_date FROM base_params)) < {_rt[0]} THEN 5
                    WHEN DATEDIFF('day', last_pay_time::DATE, (SELECT analysis_date FROM base_params)) < {_rt[1]} THEN 4
                    WHEN DATEDIFF('day', last_pay_time::DATE, (SELECT analysis_date FROM base_params)) < {_rt[2]} THEN 3
                    WHEN DATEDIFF('day', last_pay_time::DATE, (SELECT analysis_date FROM base_params)) < {_rt[3]} THEN 2
                    ELSE 1
                END AS r_score,
                CASE
                    WHEN order_count >= {_ft[3] + 1} THEN 5
                    WHEN order_count >= {_ft[2] + 1} THEN 4
                    WHEN order_count = {_ft[2]} THEN 3
                    WHEN order_count = {_ft[1]} THEN 2
                    ELSE 1
                END AS f_score,
                CASE
                    WHEN gsv >= {_mt[3]} THEN 5
                    WHEN gsv >= {_mt[2]} THEN 4
                    WHEN gsv >= {_mt[1]} THEN 3
                    WHEN gsv >= {_mt[0]} THEN 2
                    ELSE 1
                END AS m_score
            FROM user_stats_all
        ),
        segmented AS (
            SELECT
                user_id,
                CASE
                    WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 1
                    WHEN r_score < 4 AND f_score >= 4 AND m_score >= 4 THEN 2
                    WHEN r_score >= 4 AND f_score < 4 AND m_score >= 4 THEN 3
                    WHEN r_score < 4 AND f_score < 4 AND m_score >= 4 THEN 4
                    WHEN r_score >= 4 AND f_score >= 4 AND m_score < 4 THEN 5
                    WHEN r_score < 4 AND f_score >= 4 AND m_score < 4 THEN 6
                    WHEN r_score >= 4 AND f_score < 4 AND m_score < 4 THEN 7
                    ELSE 8
                END AS segment_id
            FROM rfm_scored
        ),
        -- 品类订单(lookback 窗口)
        category_orders AS (
            SELECT
                o.user_id,
                o.actual_amount,
                {category_field_expr} AS category_name
            FROM orders o
            CROSS JOIN base_params p
            WHERE o.pay_time >= p.start_date
              AND o.pay_time < p.analysis_date + INTERVAL '1' DAY
              AND {valid_sql}
              {exclude_filter}
        ),
        category_segment AS (
            SELECT
                co.category_name,
                COALESCE(s.segment_id, 9) AS segment_id,
                COUNT(DISTINCT co.user_id) AS user_count,
                SUM(co.actual_amount) AS gmv
            FROM category_orders co
            LEFT JOIN segmented s ON co.user_id = s.user_id
            GROUP BY co.category_name, s.segment_id
        )
        SELECT
            category_name,
            segment_id,
            user_count,
            gmv
        FROM category_segment
        ORDER BY segment_id, user_count DESC
        """

        # 参数: base_params(2) + user_stats_all exclude + category_orders exclude
        params: List[Any] = [date_str, start_date]
        params.extend(exclude_params)
        params.extend(exclude_params)

        result = conn.execute(sql, params).fetchall()

        # 按象限分组,每组取 top_n
        segment_data: Dict[int, List[Dict[str, Any]]] = {i: [] for i in range(1, 10)}
        for row in result:
            category_name = row[0]
            segment_id = int(row[1])
            user_count = int(row[2]) if row[2] else 0
            gmv = float(row[3]) if row[3] else 0.0

            if len(segment_data[segment_id]) < top_n:
                segment_data[segment_id].append({
                    "category": category_name,
                    "user_count": user_count,
                    "gmv": round(gmv, 2)
                })

        return {
            "date": date_str,
            "level": level,
            "matrix": {str(k): v for k, v in segment_data.items()},
            "segments": [
                {"id": seg_id, **_segment_meta(seg_id)}
                for seg_id in range(1, 10)
            ]
        }
    finally:
        conn.close()


def get_category_user_profile(
    date: str,
    lookback_days: int = 90,
    category: str = "护肤",
    type: Optional[str] = None
) -> Dict[str, Any]:
    """
    获取品类用户画像(某品类的用户特征)

    Args:
        date: 分析日期 (YYYY-MM-DD)
        lookback_days: 回溯天数
        category: 一级品类筛选
        type: 二级品类筛选(可选)

    Returns:
        {
            "date": str,
            "category": str,
            "type": str or None,
            "total_users": int,
            "total_gmv": float,
            "avg_order_value": float,
            "avg_frequency": float,
            "segment_distribution": [{"segment_id": int, "name": str, "user_count": int, "占比": float}, ...],
            "province_distribution": [{"province": str, "user_count": int}, ...],
            "channel_distribution": [{"channel": str, "user_count": int}, ...]
        }
    """
    conn = get_connection()
    date_str = _normalize_date(date)
    start_date = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    # 使用语义层构建过滤条件
    valid_sql, _ = OrderFilters.valid_order()

    # 品类筛选
    category_filter = "AND COALESCE(o.spu_category, '未知') = ?"
    params = [date_str, start_date, date_str, lookback_days, date_str, category]
    if type is not None:
        category_filter += " AND COALESCE(o.spu_type, '未知') = ?"
        params.append(type)

    # 使用单次查询获取所有数据
    sql = f"""
    WITH base_params AS (
        SELECT
            DATE(?) AS analysis_date,
            DATE(?) AS start_date
    ),
    period_orders AS (
        SELECT
            o.user_id,
            o.actual_amount,
            o.order_id,
            o.province,
            o.channel,
            COALESCE(r.segment_id, 9) AS segment_id
        FROM orders o
        CROSS JOIN base_params p
        LEFT JOIN user_rfm r ON o.user_id = r.user_id
            AND r.analysis_date = ?
            AND r.metric_type = 'GMV'
            AND r.lookback_days = ?
        WHERE o.pay_time >= p.start_date
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          {category_filter}
    ),
    overall AS (
        SELECT
            COUNT(DISTINCT user_id) AS total_users,
            SUM(actual_amount) AS total_gmv
        FROM period_orders
    ),
    segment_dist AS (
        SELECT
            segment_id,
            COUNT(DISTINCT user_id) AS user_count
        FROM period_orders
        GROUP BY segment_id
    ),
    province_dist AS (
        SELECT
            COALESCE(province, '未知') AS province,
            COUNT(DISTINCT user_id) AS user_count
        FROM period_orders
        GROUP BY province
    ),
    """

    # 由于无法在一个查询中同时获取多个分组的数据,使用多次查询
    # 先获取总数
    total_sql = f"""
    WITH base_params AS (
        SELECT
            DATE(?) AS analysis_date,
            DATE(?) AS start_date
    ),
    period_orders AS (
        SELECT
            o.user_id,
            o.actual_amount,
            o.order_id,
            COALESCE(r.segment_id, 9) AS segment_id
        FROM orders o
        CROSS JOIN base_params p
        LEFT JOIN user_rfm r ON o.user_id = r.user_id
            AND r.analysis_date = ?
            AND r.metric_type = 'GMV'
            AND r.lookback_days = ?
        WHERE o.pay_time >= p.start_date
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          AND COALESCE(o.spu_category, '未知') = ?
    )
    SELECT
        COUNT(DISTINCT user_id) AS total_users,
        SUM(actual_amount) AS total_gmv
    FROM period_orders
    """

    total_params = [date_str, start_date, date_str, lookback_days, date_str, category]
    total_result = conn.execute(total_sql, total_params).fetchone()
    total_users = int(total_result[0]) if total_result[0] else 0
    total_gmv = float(total_result[1]) if total_result[1] else 0.0
    avg_order_value = total_gmv / total_users if total_users > 0 else 0.0

    # 象限分布
    seg_sql = f"""
    WITH base_params AS (
        SELECT
            DATE(?) AS analysis_date,
            DATE(?) AS start_date
    ),
    period_orders AS (
        SELECT
            o.user_id,
            COALESCE(r.segment_id, 9) AS segment_id
        FROM orders o
        CROSS JOIN base_params p
        LEFT JOIN user_rfm r ON o.user_id = r.user_id
            AND r.analysis_date = ?
            AND r.metric_type = 'GMV'
            AND r.lookback_days = ?
        WHERE o.pay_time >= p.start_date
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          AND COALESCE(o.spu_category, '未知') = ?
    )
    SELECT
        segment_id,
        COUNT(DISTINCT user_id) AS user_count
    FROM period_orders
    GROUP BY segment_id
    ORDER BY user_count DESC
    """
    seg_result = conn.execute(seg_sql, total_params).fetchall()

    segment_distribution = []
    for row in seg_result:
        seg_id = int(row[0])
        user_count = int(row[1]) if row[1] else 0
        pct = round(user_count / total_users * 100, 2) if total_users > 0 else 0
        segment_distribution.append({
            "segment_id": seg_id,
            "name": _segment_meta(seg_id)["name"],
            "user_count": user_count,
            "pct": pct
        })

    # 省份分布
    prov_sql = f"""
    WITH base_params AS (
        SELECT
            DATE(?) AS analysis_date,
            DATE(?) AS start_date
    ),
    period_orders AS (
        SELECT
            o.user_id,
            o.province
        FROM orders o
        CROSS JOIN base_params p
        WHERE o.pay_time >= p.start_date
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          AND COALESCE(o.spu_category, '未知') = ?
    )
    SELECT
        COALESCE(province, '未知') AS province,
        COUNT(DISTINCT user_id) AS user_count
    FROM period_orders
    GROUP BY province
    ORDER BY user_count DESC
    LIMIT 10
    """
    prov_result = conn.execute(prov_sql, [date_str, start_date, date_str, category]).fetchall()

    province_distribution = [
        {"province": row[0], "user_count": int(row[1]) if row[1] else 0}
        for row in prov_result
    ]

    # 渠道分布
    chan_sql = f"""
    WITH base_params AS (
        SELECT
            DATE(?) AS analysis_date,
            DATE(?) AS start_date
    ),
    period_orders AS (
        SELECT
            o.user_id,
            o.channel
        FROM orders o
        CROSS JOIN base_params p
        WHERE o.pay_time >= p.start_date
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          AND COALESCE(o.spu_category, '未知') = ?
    )
    SELECT
        COALESCE(channel, '未知') AS channel,
        COUNT(DISTINCT user_id) AS user_count
    FROM period_orders
    GROUP BY channel
    ORDER BY user_count DESC
    """
    chan_result = conn.execute(chan_sql, [date_str, start_date, date_str, category]).fetchall()

    channel_distribution = [
        {"channel": row[0], "user_count": int(row[1]) if row[1] else 0}
        for row in chan_result
    ]

    conn.close()

    return {
        "date": date_str,
        "category": category,
        "type": type,
        "total_users": total_users,
        "total_gmv": round(total_gmv, 2),
        "avg_order_value": round(avg_order_value, 2),
        "avg_frequency": 0.0,  # 简化计算
        "segment_distribution": segment_distribution,
        "province_distribution": province_distribution,
        "channel_distribution": channel_distribution
    }


def _compute_category_period(
    conn: duckdb.DuckDBPyConnection,
    start_date: str,
    end_date: str,
    cutoff: str,
    level: str,
    metric_type: str,
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
    member_only: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """
    计算单个周期的品类聚合数据

    Args:
        member_only: 如果为 True,只统计 is_member=TRUE 的订单(会员专属口径)
    """
    level_col = SPU_LEVELS.get(level, "spu_type")
    valid_sql, _ = OrderFilters.gmv_base() if metric_type == "GMV" else OrderFilters.valid_order()
    amount_cond = "o.actual_amount > 0" if metric_type == "GMV" else "o.actual_amount >= 0"
    channel_sql = ""
    exclude_sql = ""
    member_sql = "AND o.is_member = TRUE" if member_only else ""
    params = [cutoff, start_date, end_date]
    if channel and channel != "全店":

        db_channels = expand_channels([channel])
        if len(db_channels) == 1:
            channel_sql = "AND o.channel = ?"
            params.append(db_channels[0])
        else:
            placeholders = ",".join(["?"] * len(db_channels))
            channel_sql = f"AND o.channel IN ({placeholders})"
            params.extend(db_channels)
    if exclude_channels:
        db_ex = expand_channels(exclude_channels)
        placeholders = ",".join(["?"] * len(db_ex))
        exclude_sql = f"AND o.channel NOT IN ({placeholders})"
        params.extend(db_ex)

    sql = f"""
    WITH period_orders AS (
        SELECT
            COALESCE(o.{level_col}, '未知') AS category_name,
            o.user_id,
            o.actual_amount,
            o.is_member,
            CASE WHEN ufp.first_pay_date >= DATE(?) THEN 1 ELSE 0 END AS is_new
        FROM orders o
        LEFT JOIN user_first_purchase ufp ON o.user_id = ufp.user_id
        WHERE o.pay_time >= ?
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          AND ({amount_cond})
          {channel_sql}
          {exclude_sql}
          {member_sql}
    )
    SELECT
        category_name,
        SUM(actual_amount) AS total_gsv,
        COUNT(DISTINCT user_id) AS total_users,
        SUM(CASE WHEN is_member THEN actual_amount ELSE 0 END) AS member_gsv,
        SUM(CASE WHEN is_new = 0 THEN actual_amount ELSE 0 END) AS old_gsv,
        COUNT(DISTINCT CASE WHEN is_new = 0 THEN user_id END) AS old_users,
        SUM(CASE WHEN is_new = 1 THEN actual_amount ELSE 0 END) AS new_gsv,
        COUNT(DISTINCT CASE WHEN is_new = 1 THEN user_id END) AS new_users
    FROM period_orders
    GROUP BY category_name
    ORDER BY total_gsv DESC
    """

    result = conn.execute(sql, params).fetchall()
    data = {}
    for row in result:
        name = row[0]
        total_gsv = float(row[1] or 0)
        total_users = int(row[2] or 0)
        member_gsv = float(row[3] or 0)
        old_gsv = float(row[4] or 0)
        old_users = int(row[5] or 0)
        new_gsv = float(row[6] or 0)
        new_users = int(row[7] or 0)
        data[name] = {
            "gsv": total_gsv,
            "users": total_users,
            "aus": total_gsv / total_users if total_users > 0 else 0.0,
            "member_gsv": member_gsv,
            "member_ratio": member_gsv / total_gsv if total_gsv > 0 else 0.0,
            "old_gsv": old_gsv,
            "old_users": old_users,
            "old_aus": old_gsv / old_users if old_users > 0 else 0.0,
            "old_ratio": old_gsv / total_gsv if total_gsv > 0 else 0.0,
            "new_gsv": new_gsv,
            "new_users": new_users,
            "new_aus": new_gsv / new_users if new_users > 0 else 0.0,
            "new_ratio": new_gsv / total_gsv if total_gsv > 0 else 0.0,
        }
    return data


def get_category_overview(
    start_date: str,
    end_date: str,
    level: str = "class",
    metric_type: str = "GSV",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    品类概览(按Excel格式)
    返回全店和会员两张表,含新老客拆分及同比
    """
    from datetime import date, timedelta

    conn = get_connection()

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    cutoff = (date(start_dt.year, start_dt.month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")

    ly_start = (start_dt - timedelta(days=365)).strftime("%Y-%m-%d")
    ly_end = (end_dt - timedelta(days=365)).strftime("%Y-%m-%d")
    ly_start_dt = datetime.strptime(ly_start, "%Y-%m-%d")
    ly_cutoff = (date(ly_start_dt.year, ly_start_dt.month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")

    cur = _compute_category_period(conn, start_date, end_date, cutoff, level, metric_type, channel, exclude_channels)
    comp = _compute_category_period(conn, ly_start, ly_end, ly_cutoff, level, metric_type, channel, exclude_channels)

    # P0-001: 会员专属口径(is_member=TRUE 过滤)
    cur_m = _compute_category_period(conn, start_date, end_date, cutoff, level, metric_type, channel, exclude_channels, member_only=True)
    comp_m = _compute_category_period(conn, ly_start, ly_end, ly_cutoff, level, metric_type, channel, exclude_channels, member_only=True)

    conn.close()

    def _build_row(name: str, c: Dict[str, Any], p: Dict[str, Any]) -> Dict[str, Any]:
        # 老客/新客人数占比
        users = c.get("users", 0)
        old_users = c.get("old_users", 0)
        new_users = c.get("new_users", 0)
        old_users_ratio = round(old_users / users, 4) if users > 0 else 0.0
        new_users_ratio = round(new_users / users, 4) if users > 0 else 0.0

        comp_users = p.get("users", 0)
        comp_old_users = p.get("old_users", 0)
        comp_new_users = p.get("new_users", 0)
        comp_old_users_ratio = round(comp_old_users / comp_users, 4) if comp_users > 0 else 0.0
        comp_new_users_ratio = round(comp_new_users / comp_users, 4) if comp_users > 0 else 0.0

        return {
            "name": name,
            "gsv": round(c.get("gsv", 0), 2),
            "gsv_yoy": yoy_absolute(c.get("gsv", 0), p.get("gsv", 0)),
            "users": c.get("users", 0),
            "users_yoy": yoy_absolute(c.get("users", 0), p.get("users", 0)),
            "aus": round(c.get("aus", 0), 2),
            "aus_yoy": yoy_absolute(c.get("aus", 0), p.get("aus", 0)),
            "old_gsv": round(c.get("old_gsv", 0), 2),
            "old_gsv_yoy": yoy_absolute(c.get("old_gsv", 0), p.get("old_gsv", 0)),
            "old_ratio": round(c.get("old_ratio", 0), 4),
            "old_ratio_yoy": yoy_ratio(c.get("old_ratio", 0), p.get("old_ratio", 0)),
            "old_users": c.get("old_users", 0),
            "old_users_yoy": yoy_absolute(c.get("old_users", 0), p.get("old_users", 0)),
            "old_aus": round(c.get("old_aus", 0), 2),
            "old_aus_yoy": yoy_absolute(c.get("old_aus", 0), p.get("old_aus", 0)),
            "new_gsv": round(c.get("new_gsv", 0), 2),
            "new_gsv_yoy": yoy_absolute(c.get("new_gsv", 0), p.get("new_gsv", 0)),
            "new_ratio": round(c.get("new_ratio", 0), 4),
            "new_ratio_yoy": yoy_ratio(c.get("new_ratio", 0), p.get("new_ratio", 0)),
            "new_users": c.get("new_users", 0),
            "new_users_yoy": yoy_absolute(c.get("new_users", 0), p.get("new_users", 0)),
            "new_aus": round(c.get("new_aus", 0), 2),
            "new_aus_yoy": yoy_absolute(c.get("new_aus", 0), p.get("new_aus", 0)),
            "old_users_ratio": old_users_ratio,
            "old_users_ratio_yoy": yoy_ratio(old_users_ratio, comp_old_users_ratio),
            "new_users_ratio": new_users_ratio,
            "new_users_ratio_yoy": yoy_ratio(new_users_ratio, comp_new_users_ratio),
            "member_ratio": round(c.get("member_ratio", 0), 4),
            "member_ratio_yoy": yoy_ratio(c.get("member_ratio", 0), p.get("member_ratio", 0)),
        }

    all_names = sorted(set(cur.keys()) | set(comp.keys()), key=lambda x: (cur.get(x, {}).get("gsv", 0) + comp.get(x, {}).get("gsv", 0)), reverse=True)

    all_rows = []
    member_rows = []
    for name in all_names:
        c = cur.get(name, {})
        p = comp.get(name, {})
        all_rows.append(_build_row(name, c, p))
        # P0-001: member_rows 使用会员专属口径(is_member=TRUE 过滤)
        c_m = cur_m.get(name, {})
        p_m = comp_m.get(name, {})
        m_row = _build_row(name, c_m, p_m)
        # FIX: member_ratio 分母应为全店总GSV，而非会员专属口径的GSV
        total_gsv_all = c.get("gsv", 0)
        member_gsv_all = c.get("member_gsv", 0)
        comp_total_gsv_all = p.get("gsv", 0)
        comp_member_gsv_all = p.get("member_gsv", 0)
        if total_gsv_all > 0:
            m_row["member_ratio"] = round(member_gsv_all / total_gsv_all, 4)
        if comp_total_gsv_all > 0:
            m_row["member_ratio_yoy"] = yoy_ratio(
                member_gsv_all / total_gsv_all if total_gsv_all > 0 else 0,
                comp_member_gsv_all / comp_total_gsv_all
            )
        member_rows.append(m_row)

    # ─── TTL 行计算 ────────────────────────────────────────────
    # 全店 TTL
    total_gsv = sum(c.get("gsv", 0) for c in cur.values())
    total_old_gsv = sum(c.get("old_gsv", 0) for c in cur.values())
    total_new_gsv = sum(c.get("new_gsv", 0) for c in cur.values())
    total_users = sum(c.get("users", 0) for c in cur.values())
    total_old_users = sum(c.get("old_users", 0) for c in cur.values())
    total_new_users = sum(c.get("new_users", 0) for c in cur.values())
    total_member_gsv = sum(c.get("member_gsv", 0) for c in cur.values())

    # 去年全店 TTL
    comp_total_gsv = sum(p.get("gsv", 0) for p in comp.values())
    comp_total_old_gsv = sum(p.get("old_gsv", 0) for p in comp.values())
    comp_total_new_gsv = sum(p.get("new_gsv", 0) for p in comp.values())
    comp_total_users = sum(p.get("users", 0) for p in comp.values())
    comp_total_old_users = sum(p.get("old_users", 0) for p in comp.values())
    comp_total_new_users = sum(p.get("new_users", 0) for p in comp.values())
    comp_total_member_gsv = sum(p.get("member_gsv", 0) for p in comp.values())

    all_ttl = _build_row("TTL", {
        "gsv": total_gsv,
        "users": total_users,
        "old_gsv": total_old_gsv,
        "old_users": total_old_users,
        "new_gsv": total_new_gsv,
        "new_users": total_new_users,
        "member_gsv": total_member_gsv,
    }, {
        "gsv": comp_total_gsv,
        "users": comp_total_users,
        "old_gsv": comp_total_old_gsv,
        "old_users": comp_total_old_users,
        "new_gsv": comp_total_new_gsv,
        "new_users": comp_total_new_users,
        "member_gsv": comp_total_member_gsv,
    })

    # P0-002: 会员 TTL(使用会员专属口径 cur_m/comp_m,users/old_users/new_users 必须来自会员数据)
    mem_total_gsv = sum(c.get("gsv", 0) for c in cur_m.values())
    mem_total_users = sum(c.get("users", 0) for c in cur_m.values())
    mem_total_old_gsv = sum(c.get("old_gsv", 0) for c in cur_m.values())
    mem_total_old_users = sum(c.get("old_users", 0) for c in cur_m.values())
    mem_total_new_gsv = sum(c.get("new_gsv", 0) for c in cur_m.values())
    mem_total_new_users = sum(c.get("new_users", 0) for c in cur_m.values())

    mem_comp_total_gsv = sum(p.get("gsv", 0) for p in comp_m.values())
    mem_comp_total_users = sum(p.get("users", 0) for p in comp_m.values())
    mem_comp_total_old_gsv = sum(p.get("old_gsv", 0) for p in comp_m.values())
    mem_comp_total_old_users = sum(p.get("old_users", 0) for p in comp_m.values())
    mem_comp_total_new_gsv = sum(p.get("new_gsv", 0) for p in comp_m.values())
    mem_comp_total_new_users = sum(p.get("new_users", 0) for p in comp_m.values())

    # FIX: member_ttl 的 member_ratio 分母应为全店总GSV
    member_ttl = _build_row("TTL", {
        "gsv": mem_total_gsv,
        "users": mem_total_users,
        "old_gsv": mem_total_old_gsv,
        "old_users": mem_total_old_users,
        "new_gsv": mem_total_new_gsv,
        "new_users": mem_total_new_users,
        "member_gsv": total_member_gsv,
    }, {
        "gsv": mem_comp_total_gsv,
        "users": mem_comp_total_users,
        "old_gsv": mem_comp_total_old_gsv,
        "old_users": mem_comp_total_old_users,
        "new_gsv": mem_comp_total_new_gsv,
        "new_users": mem_comp_total_new_users,
        "member_gsv": comp_total_member_gsv,
    })
    # 覆盖 member_ratio: 全店会员GSV / 全店总GSV
    if total_gsv > 0:
        member_ttl["member_ratio"] = round(total_member_gsv / total_gsv, 4)
    if comp_total_gsv > 0:
        member_ttl["member_ratio_yoy"] = yoy_ratio(
            total_member_gsv / total_gsv if total_gsv > 0 else 0,
            comp_total_member_gsv / comp_total_gsv
        )

    return {
        "date_start": start_date,
        "date_end": end_date,
        "level": level,
        "channel": channel,
        "metric_type": metric_type,
        "all_rows": all_rows,
        "member_rows": member_rows,
        "all_ttl": all_ttl,
        "member_ttl": member_ttl,
    }


# =============================================================================
# 品类看板 v2 - 新增 Service 函数
# =============================================================================

def _build_value_score(
    high_val_ratio: float, wool_ratio: float, member_ratio: float, aus: float,
    rank_high_val: int, rank_wool: int, rank_member: int, rank_aus: int,
    total_count: int
) -> tuple[float, str]:
    """
    计算价值评分和等级(辅助函数)
    评分 = 高价值占比排名*0.4 + (100-羊毛党占比排名)*0.3 + 会员占比排名*0.2 + AUS排名*0.1
    """
    # 百分位排名转0-100分数(排名1=n/2*100/n,排名越靠前分数越高)
    score_high_val = (total_count - rank_high_val + 1) / total_count * 100
    score_wool = (total_count - rank_wool + 1) / total_count * 100  # 羊毛党占比低=高分
    score_member = (total_count - rank_member + 1) / total_count * 100
    score_aus = (total_count - rank_aus + 1) / total_count * 100

    total_score = (
        score_high_val * 0.4 +
        score_wool * 0.3 +
        score_member * 0.2 +
        score_aus * 0.1
    )

    if total_score >= 80:
        grade = "A"
    elif total_score >= 65:
        grade = "B"
    elif total_score >= 50:
        grade = "C"
    elif total_score >= 35:
        grade = "D"
    else:
        grade = "E"

    return round(total_score, 1), grade


# ---- 价值分层 ---------------------------------------------------------------

LOW_PRICE_CHANNELS = ["U先派样", "百补派样", "赠品&0.01渠道", "其他"]


def _compute_wool_party_breakdown(
    conn: "duckdb.DuckDBPyConnection",
    start_date: str, end_date: str,
    level: str, channel: Optional[str], exclude_channels: Optional[List[str]]
) -> Dict[str, Dict[str, Any]]:
    """
    计算羊毛党细分统计（Type1 + Type2），按品类聚合。

    Type1: 历史有正装订单，在窗口内 100% 订单为小样
    Type2: 历史无正装订单，在窗口内 100% 订单为小样

    NOTE: 羊毛党定义依赖低价渠道订单，因此**不应用** exclude_channels 过滤。
          exclude_channels 通常就是低价渠道列表，若应用则 sample_orders 永远为 0。
    """
    level_col = SPU_LEVELS.get(level, "spu_product_class")
    valid_sql, _ = OrderFilters.valid_order()

    channel_params = []

    channel_sql = ""
    if channel and channel != "全店":

        db_channels = expand_channels([channel])
        if len(db_channels) == 1:
            channel_sql = "AND o.channel = ?"
            channel_params = [db_channels[0]]
        else:
            placeholders = ",".join(["?"] * len(db_channels))
            channel_sql = f"AND o.channel IN ({placeholders})"
            channel_params = list(db_channels)

    # 正装 = 非低价渠道；小样 = 低价渠道
    SAMPLE_CHANNELS = ('U先派样', '百补派样', '赠品&0.01渠道', '其他')

    params = [start_date, end_date] + channel_params

    sql = f"""
    WITH window_orders AS (
        SELECT
            COALESCE(o.{level_col}, '未知') AS category_name,
            o.user_id,
            o.channel
        FROM orders o
        WHERE o.pay_time >= ?
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          {channel_sql}
    ),
    user_window_summary AS (
        SELECT
            category_name,
            user_id,
            COUNT(*) AS total_orders,
            COUNT(CASE WHEN channel IN {SAMPLE_CHANNELS} THEN 1 END) AS sample_orders
        FROM window_orders
        GROUP BY category_name, user_id
    ),
    ever_formal_users AS (
        -- 历史上买过正装的用户(只检查窗口内出现的用户，减少扫描范围)
        SELECT DISTINCT o.user_id
        FROM orders o
        WHERE o.user_id IN (SELECT DISTINCT user_id FROM window_orders)
          AND {valid_sql}
          AND o.channel NOT IN {SAMPLE_CHANNELS}
    ),
    wool_classified AS (
        SELECT
            ws.category_name,
            ws.user_id,
            CASE
                WHEN ef.user_id IS NOT NULL THEN 'type1'
                ELSE 'type2'
            END AS wool_type
        FROM user_window_summary ws
        LEFT JOIN ever_formal_users ef ON ws.user_id = ef.user_id
        WHERE ws.total_orders > 0
          AND ws.sample_orders = ws.total_orders  -- 100% 小样
    )
    SELECT
        category_name,
        COUNT(DISTINCT CASE WHEN wool_type = 'type1' THEN user_id END) AS type1_count,
        COUNT(DISTINCT CASE WHEN wool_type = 'type2' THEN user_id END) AS type2_count,
        COUNT(DISTINCT user_id) AS total_wool_count
    FROM wool_classified
    GROUP BY category_name
    """
    result = conn.execute(sql, params).fetchall()
    return {
        row[0]: {
            "type1_count": int(row[1] or 0),
            "type2_count": int(row[2] or 0),
            "total_count": int(row[3] or 0),
        }
        for row in result
    }


def _compute_value_tier_base(
    conn: "duckdb.DuckDBPyConnection",
    start_date: str, end_date: str, cutoff: str,
    level: str, channel: Optional[str], exclude_channels: Optional[List[str]]
) -> tuple:
    """计算价值分层基础数据（高价值人数 + 总用户 + 总GMV + 会员GMV）"""
    level_col = SPU_LEVELS.get(level, "spu_product_class")
    valid_sql, _ = OrderFilters.valid_order()

    channel_params = []
    exclude_params = []

    channel_sql = ""
    if channel and channel != "全店":

        db_channels = expand_channels([channel])
        if len(db_channels) == 1:
            channel_sql = "AND o.channel = ?"
            channel_params = [db_channels[0]]
        else:
            placeholders = ",".join(["?"] * len(db_channels))
            channel_sql = f"AND o.channel IN ({placeholders})"
            channel_params = list(db_channels)

    exclude_sql = ""
    if exclude_channels:
        db_ex = expand_channels(exclude_channels)
        placeholders = ",".join(["?"] * len(db_ex))
        exclude_sql = f"AND o.channel NOT IN ({placeholders})"
        exclude_params = list(db_ex)

    # 查询 user_rfm 最新分析日期
    latest_rfm_row = conn.execute(
        "SELECT MAX(analysis_date) FROM user_rfm WHERE metric_type = 'GMV' AND lookback_days = 90"
    ).fetchone()
    latest_rfm_date = latest_rfm_row[0] if latest_rfm_row and latest_rfm_row[0] else cutoff

    params = [latest_rfm_date, start_date, end_date] + channel_params + exclude_params

    sql = f"""
    WITH period_orders AS (
        SELECT COALESCE(o.{level_col}, '未知') AS category_name,
               o.user_id, o.actual_amount, o.is_member,
               COALESCE(r.segment_id, 9) AS segment_id
        FROM orders o
        LEFT JOIN user_rfm r ON o.user_id = r.user_id
            AND r.analysis_date = DATE(?) AND r.metric_type = 'GMV' AND r.lookback_days = 90
        WHERE o.pay_time >= ? AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql} {channel_sql} {exclude_sql}
    )
    SELECT category_name,
           COUNT(DISTINCT user_id) AS total_users,
           SUM(actual_amount) AS total_gsv,
           COUNT(DISTINCT CASE WHEN segment_id IN (1, 2) THEN user_id END) AS high_value_users,
           SUM(CASE WHEN is_member THEN actual_amount ELSE 0 END) AS member_gsv
    FROM period_orders GROUP BY category_name
    """
    result = conn.execute(sql, params).fetchall()

    # 计算羊毛党细分
    wool_breakdown = _compute_wool_party_breakdown(
        conn, start_date, end_date, level, channel, exclude_channels)

    return result, wool_breakdown


def get_category_value_tier(
    start_date: str,
    end_date: str,
    level: str = "class",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """价值分层 - 各品类羊毛党指数 + 高价值占比 + 价值评分

    多时间窗口羊毛党统计:
    - default: 使用传入的 start_date~end_date 作为默认窗口
    - 30d: end_date 往前推 30 天
    - 90d: end_date 往前推 90 天
    - all: 全部历史(2020-01-01 ~ end_date)
    """
    from datetime import date, timedelta

    conn = get_connection()
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        cutoff = (date(start_dt.year, start_dt.month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")

        # ---- 默认窗口(用户选择的时间范围) ----
        result, wool_breakdown = _compute_value_tier_base(
            conn, start_date, end_date, cutoff, level, channel, exclude_channels)

        # ---- 多窗口羊毛党计算 ----
        # 30天窗口
        start_30d = (end_dt - timedelta(days=30)).strftime("%Y-%m-%d")
        wool_30d = _compute_wool_party_breakdown(
            conn, start_30d, end_date, level, channel, exclude_channels)
        # 90天窗口
        start_90d = (end_dt - timedelta(days=90)).strftime("%Y-%m-%d")
        wool_90d = _compute_wool_party_breakdown(
            conn, start_90d, end_date, level, channel, exclude_channels)
        # 全部历史
        wool_all = _compute_wool_party_breakdown(
            conn, "2000-01-01", end_date, level, channel, exclude_channels)
    finally:
        conn.close()

    # 构建品类数据
    MIN_USERS_FOR_SCORING = 100  # 用户基数门槛: 低于此数不参与评分排名
    cat_data = []
    for row in result:
        total_users = int(row[1] or 0)
        if total_users == 0:
            continue
        total_gsv = float(row[2] or 0)
        high_value_users = int(row[3] or 0)
        member_gsv = float(row[4] or 0)
        wool = wool_breakdown.get(row[0], {"type1_count": 0, "type2_count": 0, "total_count": 0})
        wool_total = wool["total_count"]
        cat_data.append({
            "category_name": row[0],
            "total_users": total_users,
            "total_gsv": total_gsv,
            "high_value_users": high_value_users,
            "high_value_ratio": high_value_users / total_users,
            "wool_party": {
                "type1_count": wool["type1_count"],
                "type2_count": wool["type2_count"],
                "total_count": wool_total,
                "type1_ratio": wool["type1_count"] / total_users if total_users > 0 else 0,
                "type2_ratio": wool["type2_count"] / total_users if total_users > 0 else 0,
            },
            "member_ratio": member_gsv / total_gsv if total_gsv > 0 else 0,
            "avg_aus": total_gsv / total_users,
            "is_sample_insufficient": total_users < MIN_USERS_FOR_SCORING,
        })

    # 分离符合门槛的品类和样本不足的品类
    qualifying = [c for c in cat_data if not c["is_sample_insufficient"]]
    insufficient = [c for c in cat_data if c["is_sample_insufficient"]]

    # 计算排名(仅对符合门槛的品类)
    total_count = len(qualifying)
    if total_count > 0:
        rank_map = {c["category_name"]: {"high_val": i+1, "wool": i+1, "member": i+1, "aus": i+1}
                    for i, c in enumerate(sorted(qualifying, key=lambda x: x["high_value_ratio"], reverse=True))}
        for i, c in enumerate(sorted(qualifying, key=lambda x: x["wool_party"]["total_count"] / max(x["total_users"], 1), reverse=True)):
            rank_map[c["category_name"]]["wool"] = i + 1
        for i, c in enumerate(sorted(qualifying, key=lambda x: x["member_ratio"], reverse=True)):
            rank_map[c["category_name"]]["member"] = i + 1
        for i, c in enumerate(sorted(qualifying, key=lambda x: x["avg_aus"], reverse=True)):
            rank_map[c["category_name"]]["aus"] = i + 1

        for c in qualifying:
            ranks = rank_map[c["category_name"]]
            score, grade = _build_value_score(
                c["high_value_ratio"],
                c["wool_party"]["total_count"] / c["total_users"] if c["total_users"] > 0 else 0,
                c["member_ratio"], c["avg_aus"],
                ranks["high_val"], ranks["wool"], ranks["member"], ranks["aus"], total_count)
            c["value_score"] = score
            c["value_grade"] = grade

    # 样本不足的品类: 不参与排名, 标记为"样本不足"
    for c in insufficient:
        c["value_score"] = 0
        c["value_grade"] = "样本不足"

    # 合并后按用户数降序排列(符合门槛的在前, 样本不足的在后)
    qualifying.sort(key=lambda x: x["total_users"], reverse=True)
    insufficient.sort(key=lambda x: x["total_users"], reverse=True)
    cat_data = qualifying + insufficient

    dual_axis = {
        "categories": [c["category_name"] for c in cat_data],
        "wool_party_ratios": [round(c["wool_party"]["total_count"] / c["total_users"], 4) for c in cat_data],
        "high_value_ratios": [round(c["high_value_ratio"], 4) for c in cat_data],
    }
    table = [{"category_name": c["category_name"],
              "total_users": c["total_users"],
              "high_value_users": c["high_value_users"],
              "high_value_ratio": round(c["high_value_ratio"], 4),
              "wool_party": c["wool_party"],
              "member_ratio": round(c["member_ratio"], 4),
              "avg_aus": round(c["avg_aus"], 2),
              "value_score": c["value_score"], "value_grade": c["value_grade"]}
             for c in cat_data]

    # ---- 多窗口羊毛党数据组装 ----
    def _build_window_table(wool_map: Dict[str, Dict[str, Any]], window_label: str) -> List[Dict[str, Any]]:
        rows = []
        for c in cat_data:
            cat = c["category_name"]
            w = wool_map.get(cat, {"type1_count": 0, "type2_count": 0, "total_count": 0})
            tu = c["total_users"]
            rows.append({
                "category_name": cat,
                "total_users": tu,
                "high_value_users": c["high_value_users"],
                "high_value_ratio": round(c["high_value_ratio"], 4),
                "wool_party": {
                    "type1_count": w["type1_count"],
                    "type2_count": w["type2_count"],
                    "total_count": w["total_count"],
                    "type1_ratio": w["type1_count"] / tu if tu > 0 else 0,
                    "type2_ratio": w["type2_count"] / tu if tu > 0 else 0,
                },
                "member_ratio": round(c["member_ratio"], 4),
                "avg_aus": round(c["avg_aus"], 2),
                "value_score": c["value_score"],
                "value_grade": c["value_grade"],
            })
        return rows

    wool_party_by_window = {
        "default": table,
        "30d": _build_window_table(wool_30d, "30d"),
        "90d": _build_window_table(wool_90d, "90d"),
        "all": _build_window_table(wool_all, "all"),
    }

    suggestions = []
    high_wool = [c for c in cat_data if c["wool_party"]["total_count"] / c["total_users"] > 0.4]
    if high_wool:
        suggestions.append(f"羊毛党占比 > 40%: {high_wool[0]['category_name']} 建议重新评估该品类渠道ROI")

    return {
        "dual_axis_line": dual_axis,
        "table": table,
        "operation_suggestions": suggestions,
        "data_quality_note": (
            f"基于 {sum(c['total_users'] for c in cat_data)} 名用户 / {start_date}~{end_date} 计算。"
            f"排名仅统计用户数 ≥ {MIN_USERS_FOR_SCORING} 的品类，共 {len(qualifying)} 个。"
            f"样本不足(<{MIN_USERS_FOR_SCORING}人)的 {len(insufficient)} 个品类不参与评分排名。"
            f"羊毛党统计基于渠道分类(U先派样/百补派样/赠品&0.01/其他=小样)，不受'剔除低价'筛选影响。"
        ),
        "wool_party_by_window": wool_party_by_window,
    }


# ---- 品类流转 ---------------------------------------------------------------

def _compute_temporal_association(
    conn: "duckdb.DuckDBPyConnection",
    target_category: str,
    start_date: str,
    end_date: str,
    level: str,
    window_days: int,
    channel: Optional[str],
    exclude_channels: Optional[List[str]],
) -> Dict[str, Any]:
    """
    时序关联分析: 买 target_category 的用户前后买了什么

    Returns:
        {"post_purchase": [...], "pre_purchase": [...]}
    """
    from datetime import timedelta

    level_col = SPU_LEVELS.get(level, "spu_product_class")
    valid_sql, _ = OrderFilters.valid_order()

    # 渠道参数
    channel_params: List[Any] = []
    exclude_params: List[Any] = []
    channel_sql = ""
    if channel and channel != "全店":

        db_channels = expand_channels([channel])
        if len(db_channels) == 1:
            channel_sql = "AND o.channel = ?"
            channel_params = [db_channels[0]]
        else:
            placeholders = ",".join(["?"] * len(db_channels))
            channel_sql = f"AND o.channel IN ({placeholders})"
            channel_params = list(db_channels)

    exclude_sql = ""
    if exclude_channels:
        db_ex = expand_channels(exclude_channels)
        placeholders = ",".join(["?"] * len(db_ex))
        exclude_sql = f"AND o.channel NOT IN ({placeholders})"
        exclude_params = list(db_ex)

    # 后置购买: 买 target 之后买的其他品类(限制 window_days 内)
    post_sql = f"""
    WITH target_orders AS (
        SELECT DISTINCT o.user_id, o.pay_time, o.order_id
        FROM orders o
        WHERE COALESCE(o.{level_col}, '未知') = ?
          AND o.pay_time >= ?
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          {channel_sql}
          {exclude_sql}
    ),
    post_orders AS (
        SELECT
            COALESCE(o.{level_col}, '未知') AS category_name,
            o.user_id,
            o.actual_amount,
            o.pay_time,
            t.pay_time AS target_pay_time
        FROM orders o
        INNER JOIN target_orders t ON o.user_id = t.user_id
        WHERE o.pay_time > t.pay_time
          AND o.pay_time <= t.pay_time + INTERVAL '1' DAY * ?
          AND COALESCE(o.{level_col}, '未知') != ?
          AND {valid_sql}
          {channel_sql}
          {exclude_sql}
    )
    SELECT
        category_name,
        COUNT(DISTINCT user_id) AS user_count,
        COUNT(*) AS order_count,
        SUM(actual_amount) AS gsv,
        AVG(DATEDIFF('day', target_pay_time::DATE, pay_time::DATE)) AS avg_days_gap
    FROM post_orders
    GROUP BY category_name
    ORDER BY user_count DESC
    LIMIT 20
    """
    # target_category, start_date, end_date, + channel + exclude + window_days + target_category + channel + exclude
    post_params = [target_category, start_date, end_date] + channel_params + exclude_params + [window_days, target_category] + channel_params + exclude_params
    post_result = conn.execute(post_sql, post_params).fetchall()

    # 前置购买: 买 target 之前买的其他品类(限制 window_days 内)
    pre_sql = f"""
    WITH target_orders AS (
        SELECT DISTINCT o.user_id, o.pay_time, o.order_id
        FROM orders o
        WHERE COALESCE(o.{level_col}, '未知') = ?
          AND o.pay_time >= ?
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          {channel_sql}
          {exclude_sql}
    ),
    pre_orders AS (
        SELECT
            COALESCE(o.{level_col}, '未知') AS category_name,
            o.user_id,
            o.actual_amount,
            o.pay_time,
            t.pay_time AS target_pay_time
        FROM orders o
        INNER JOIN target_orders t ON o.user_id = t.user_id
        WHERE o.pay_time < t.pay_time
          AND o.pay_time >= t.pay_time - INTERVAL '1' DAY * ?
          AND COALESCE(o.{level_col}, '未知') != ?
          AND {valid_sql}
          {channel_sql}
          {exclude_sql}
    )
    SELECT
        category_name,
        COUNT(DISTINCT user_id) AS user_count,
        COUNT(*) AS order_count,
        SUM(actual_amount) AS gsv,
        AVG(DATEDIFF('day', pay_time::DATE, target_pay_time::DATE)) AS avg_days_gap
    FROM pre_orders
    GROUP BY category_name
    ORDER BY user_count DESC
    LIMIT 20
    """
    # target_category, start_date, end_date, + channel + exclude + window_days + target_category + channel + exclude
    pre_params = [target_category, start_date, end_date] + channel_params + exclude_params + [window_days, target_category] + channel_params + exclude_params
    pre_result = conn.execute(pre_sql, pre_params).fetchall()

    # 目标品类总购买用户数(用于计算 ratio)
    total_sql = f"""
    SELECT COUNT(DISTINCT user_id)
    FROM orders o
    WHERE COALESCE(o.{level_col}, '未知') = ?
      AND o.pay_time >= ?
      AND o.pay_time < DATE(?) + INTERVAL '1' DAY
      AND {valid_sql}
      {channel_sql}
      {exclude_sql}
    """
    total_result = conn.execute(total_sql, [target_category, start_date, end_date] + channel_params + exclude_params).fetchone()
    total_users = int(total_result[0] or 0) if total_result else 0

    def _build_assoc(rows) -> List[Dict[str, Any]]:
        result = []
        for row in rows:
            uc = int(row[1] or 0)
            if total_users > 0:
                result.append({
                    "category_name": row[0],
                    "user_count": uc,
                    "order_count": int(row[2] or 0),
                    "gsv": round(float(row[3] or 0), 2),
                    "ratio": round(uc / total_users, 4),
                    "avg_days_gap": round(float(row[4] or 0), 1),
                })
        return result

    return {
        "post_purchase": _build_assoc(post_result),
        "pre_purchase": _build_assoc(pre_result),
    }


def get_category_flow(
    start_date: str,
    end_date: str,
    level: str = "class",
    top_n: int = 10,
    window_days: int = 90,
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
    target_category: Optional[str] = None,
) -> Dict[str, Any]:
    """
    品类流转 - 桑基图数据 + 流转矩阵 + 时序关联分析

    Args:
        start_date: 周期开始日期
        end_date: 周期结束日期
        level: 品类级别
        top_n: TOP N 品类
        window_days: 流转时间窗口(天)
        channel: 渠道筛选
        exclude_channels: 排除渠道列表
        target_category: 目标品类(传入时返回前后置购买关联)

    Returns:
        CategoryFlowResponse 结构
    """
    import json
    from pathlib import Path

    # 有 target_category 时不走缓存(动态分析)
    cache_dir = Path("backend/cache/category_flow")
    import hashlib
    channel_key = (channel or "") + "|" + "|".join(sorted(exclude_channels or []))
    channel_hash = hashlib.md5(channel_key.encode()).hexdigest()[:8]
    cache_file = cache_dir / f"flow_{start_date}_{end_date}_w{window_days}_top{top_n}_{level}_{channel_hash}.json"

    # 尝试读取缓存(仅在无 target_category 时)
    data_stale = False
    if target_category is None and cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
            # 时序关联为空(缓存数据不带此字段)
            cached.setdefault("target_category", None)
            cached.setdefault("post_purchase", None)
            cached.setdefault("pre_purchase", None)
            return {
                **cached,
                "data_stale": False,
                "data_quality_note": f"本Tab基于 {start_date}~{end_date} 窗口 {window_days} 天的流转数据计算",
            }
        except Exception:
            data_stale = True

    conn = get_connection()
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        window_start = (start_dt - timedelta(days=window_days)).strftime("%Y-%m-%d")

        level_col = SPU_LEVELS.get(level, "spu_product_class")
        valid_sql, _ = OrderFilters.valid_order()

        # 构建基础 params(只包含日期过滤,channel/exclude 动态追加)
        base_params: List[Any] = [window_start, end_date]

        channel_sql = ""
        if channel and channel != "全店":
    
            db_channels = expand_channels([channel])
            if len(db_channels) == 1:
                channel_sql = "AND o.channel = ?"
                base_params.append(db_channels[0])
            else:
                placeholders = ",".join(["?"] * len(db_channels))
                channel_sql = f"AND o.channel IN ({placeholders})"
                base_params.extend(db_channels)

        exclude_sql = ""
        if exclude_channels:
            from backend.semantic.filters import expand_channels as _ec
            db_ex = _ec(exclude_channels)
            placeholders = ",".join(["?"] * len(db_ex))
            exclude_sql = f"AND o.channel NOT IN ({placeholders})"
            base_params.extend(db_ex)

        # 查找TOP N品类
        top_cat_sql = f"""
        WITH all_orders AS (
            SELECT
                COALESCE(o.{level_col}, '未知') AS category_name,
                o.user_id,
                o.pay_time,
                o.order_id
            FROM orders o
            WHERE o.pay_time >= ?
              AND o.pay_time < DATE(?) + INTERVAL '1' DAY
              AND {valid_sql}
              {channel_sql}
              {exclude_sql}
        ),
        user_first_order AS (
            SELECT user_id, category_name AS first_category, pay_time
            FROM all_orders o1
            WHERE order_id = (
                SELECT order_id FROM all_orders o2
                WHERE o2.user_id = o1.user_id
                ORDER BY pay_time ASC LIMIT 1
            )
        ),
        user_second_order AS (
            SELECT user_id, category_name AS second_category, pay_time
            FROM all_orders o1
            WHERE order_id = (
                SELECT order_id FROM all_orders o2
                WHERE o2.user_id = o1.user_id
                ORDER BY pay_time ASC LIMIT 1 OFFSET 1
            )
        )
        SELECT first_category, COUNT(DISTINCT user_id) AS first_users
        FROM user_first_order
        GROUP BY first_category
        ORDER BY first_users DESC
        LIMIT ?
        """
        top_cats_result = conn.execute(top_cat_sql + " OFFSET 0", base_params + [top_n]).fetchall()
        top_cats = [row[0] for row in top_cats_result]

        if len(top_cats) < top_n:
            top_cats_result = conn.execute(top_cat_sql, base_params + [top_n]).fetchall()
            top_cats = [row[0] for row in top_cats_result[:top_n]]

        # flow_sql 参数: 2个日期 + channel + exclude + top_cats(from IN) + top_cats(to IN)
        channel_params_flow = []
        exclude_params_flow = []
        if channel and channel != "全店":
            channel_params_flow = list(db_channels)
        if exclude_channels:
            exclude_params_flow = list(exclude_channels)
        params_flow = [window_start, end_date] + channel_params_flow + exclude_params_flow + top_cats + top_cats

        flow_sql = f"""
        WITH all_orders AS (
            SELECT
                COALESCE(o.{level_col}, '未知') AS category_name,
                o.user_id,
                o.pay_time,
                o.order_id
            FROM orders o
            WHERE o.pay_time >= ?
              AND o.pay_time < DATE(?) + INTERVAL '1' DAY
              AND {valid_sql}
              {channel_sql}
              {exclude_sql}
        ),
        user_first_order AS (
            SELECT user_id, category_name AS first_category, pay_time
            FROM all_orders o1
            WHERE order_id = (
                SELECT order_id FROM all_orders o2
                WHERE o2.user_id = o1.user_id
                ORDER BY pay_time ASC LIMIT 1
            )
        ),
        user_second_order AS (
            SELECT user_id, category_name AS second_category, pay_time
            FROM all_orders o1
            WHERE order_id = (
                SELECT order_id FROM all_orders o2
                WHERE o2.user_id = o1.user_id
                ORDER BY pay_time ASC LIMIT 1 OFFSET 1
            )
        ),
        flow_pairs AS (
            SELECT
                COALESCE(fo.first_category, '未知') AS from_cat,
                COALESCE(so.second_category, '未知') AS to_cat,
                COUNT(DISTINCT fo.user_id) AS flow_users
            FROM user_first_order fo
            INNER JOIN user_second_order so ON fo.user_id = so.user_id
            WHERE fo.first_category IN ({",".join(["?"] * len(top_cats))})
              OR so.second_category IN ({",".join(["?"] * len(top_cats))})
            GROUP BY fo.first_category, so.second_category
        )
        SELECT from_cat, to_cat, flow_users
        FROM flow_pairs
        WHERE from_cat != to_cat
        ORDER BY flow_users DESC
        """
        flow_result = conn.execute(flow_sql, params_flow).fetchall()

        # 构建桑基图数据
        other_node = "其他"
        raw_links = []
        for row in flow_result:
            from_cat, to_cat, users = row[0], row[1], int(row[2] or 0)
            if users > 0 and from_cat != to_cat:
                # 非TOP品类归类到"其他"
                src = from_cat if from_cat in top_cats else other_node
                tgt = to_cat if to_cat in top_cats else other_node
                raw_links.append({"source": src, "target": tgt, "value": users})

        # 合并同名link（归类后可能产生重复source→target）
        merged = {}
        for l in raw_links:
            key = (l["source"], l["target"])
            if key in merged:
                merged[key]["value"] += l["value"]
            else:
                merged[key] = {"source": l["source"], "target": l["target"], "value": l["value"]}
        links = list(merged.values())

        # 重新构建节点列表
        node_names = list(set(top_cats))
        for l in links:
            node_names.append(l["source"])
            node_names.append(l["target"])
        node_names = list(dict.fromkeys(node_names))  # 去重保序
        if other_node not in node_names:
            # 若没有其他节点但有link指向其他，补充
            has_other = any(l["source"] == other_node or l["target"] == other_node for l in links)
            if has_other:
                node_names.append(other_node)

        sankey_data = {
            "nodes": [{"name": n, "category_name": n} for n in node_names],
            "links": links,
        }

        # 流转矩阵
        all_cats = top_cats + [other_node]
        sources = top_cats
        targets = top_cats + [other_node]

        matrix = [[0] * len(targets) for _ in range(len(sources))]
        concentration_warnings = []
        for row in flow_result:
            from_idx = sources.index(row[0]) if row[0] in sources else -1
            to_idx = targets.index(row[1]) if row[1] in targets else -1
            if from_idx >= 0 and to_idx >= 0:
                matrix[from_idx][to_idx] = int(row[2] or 0)

        # 来源集中度警告
        for i, src in enumerate(sources):
            total_inflow = sum(matrix[j][i] for j in range(len(sources)))
            if total_inflow > 0:
                max_source_ratio = max(matrix[j][i] for j in range(len(sources))) / total_inflow
                if max_source_ratio > 0.6:
                    concentration_warnings.append(f"{src} 过度依赖单一来源(占比>{int(max_source_ratio*100)}%)")

        flow_matrix_data = {
            "sources": sources,
            "targets": targets,
            "matrix": matrix,
            "concentration_warnings": concentration_warnings,
        }

        # 保存缓存
        cache_dir.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"sankey_data": sankey_data, "matrix": flow_matrix_data}, f, ensure_ascii=False)

        result = {
            "sankey_data": sankey_data,
            "matrix": flow_matrix_data,
            "data_stale": data_stale,
            "data_quality_note": f"本Tab基于 {start_date}~{end_date} 窗口 {window_days} 天的流转数据计算",
        }

        # 时序关联分析
        if target_category:
            temporal = _compute_temporal_association(
                conn, target_category, start_date, end_date,
                level, window_days, channel, exclude_channels)
            result["target_category"] = target_category
            result["post_purchase"] = temporal["post_purchase"]
            result["pre_purchase"] = temporal["pre_purchase"]
    finally:
        conn.close()

    return result


# ---- 购物篮分析 -------------------------------------------------------------

def _compute_market_basket(
    conn: "duckdb.DuckDBPyConnection",
    target_category: str,
    start_date: str,
    end_date: str,
    level: str,
    channel: Optional[str],
    exclude_channels: Optional[List[str]],
) -> Dict[str, Any]:
    """
    计算单个周期的购物篮关联数据

    Returns:
        {
            "target_category": str,
            "total_orders": int,
            "target_order_count": int,
            "items": [
                {
                    "category_name": str,
                    "co_order_count": int,
                    "support": float,
                    "confidence": float,
                    "lift": float,
                    "target_order_count": int,
                }
            ]
        }
    """
    level_col = SPU_LEVELS.get(level, "spu_product_class")
    valid_sql, _ = OrderFilters.valid_order()

    # 渠道参数
    channel_params: List[Any] = []
    exclude_params: List[Any] = []
    channel_sql = ""
    if channel and channel != "全店":

        db_channels = expand_channels([channel])
        if len(db_channels) == 1:
            channel_sql = "AND o.channel = ?"
            channel_params = [db_channels[0]]
        else:
            placeholders = ",".join(["?"] * len(db_channels))
            channel_sql = f"AND o.channel IN ({placeholders})"
            channel_params = list(db_channels)

    exclude_sql = ""
    if exclude_channels:
        db_ex = expand_channels(exclude_channels)
        placeholders = ",".join(["?"] * len(db_ex))
        exclude_sql = f"AND o.channel NOT IN ({placeholders})"
        exclude_params = list(db_ex)

    # 日期参数
    date_params = [start_date, end_date]
    base_params = date_params + channel_params + exclude_params

    sql = f"""
    WITH
    -- 周期内所有有效订单
    period_orders AS (
        SELECT DISTINCT order_id, COALESCE(o.{level_col}, '未知') AS category_name
        FROM orders o
        WHERE o.pay_time >= ?
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          {channel_sql}
          {exclude_sql}
    ),
    -- 包含目标品类的订单
    target_orders AS (
        SELECT DISTINCT order_id
        FROM period_orders
        WHERE category_name = ?
    ),
    -- 目标品类的订单数
    target_count AS (
        SELECT COUNT(*) AS target_order_count FROM target_orders
    ),
    -- 总订单数(去重)
    total_count AS (
        SELECT COUNT(DISTINCT order_id) AS total_orders FROM period_orders
    ),
    -- 与目标品类同单出现的其他品类
    basket_items AS (
        SELECT
            po.category_name,
            COUNT(DISTINCT po.order_id) AS co_order_count
        FROM period_orders po
        INNER JOIN target_orders t ON po.order_id = t.order_id
        WHERE po.category_name != ?
        GROUP BY po.category_name
    ),
    -- 各品类的独立订单数(用于lift分母)
    item_orders AS (
        SELECT
            category_name,
            COUNT(DISTINCT order_id) AS item_order_count
        FROM period_orders
        GROUP BY category_name
    )
    SELECT
        b.category_name,
        b.co_order_count,
        tc.target_order_count,
        tc2.total_orders,
        i.item_order_count
    FROM basket_items b
    LEFT JOIN item_orders i ON b.category_name = i.category_name
    CROSS JOIN target_count tc
    CROSS JOIN total_count tc2
    ORDER BY b.co_order_count DESC
    LIMIT 50
    """

    # 参数: date(2) + channel + exclude + target(2)
    # item_orders 复用 period_orders，不需要额外参数
    params = base_params + [target_category, target_category]
    rows = conn.execute(sql, params).fetchall()

    items = []
    total_orders = 0
    target_count = 0
    for row in rows:
        cat_name = row[0]
        co_count = int(row[1] or 0)
        target_count = int(row[2] or 0)
        total_orders = int(row[3] or 0)
        item_count = int(row[4] or 0)

        if target_count == 0 or total_orders == 0:
            continue

        support = co_count / total_orders
        confidence = co_count / target_count
        item_prob = item_count / total_orders if total_orders > 0 else 0
        lift = confidence / item_prob if item_prob > 0 else 0

        items.append({
            "category_name": cat_name,
            "co_order_count": co_count,
            "support": round(support, 4),
            "confidence": round(confidence, 4),
            "lift": round(lift, 4),
            "target_order_count": target_count,
        })

    return {
        "target_category": target_category,
        "total_orders": total_orders,
        "target_order_count": target_count,
        "items": items,
    }


def get_market_basket(
    start_date: str,
    end_date: str,
    target_category: str,
    level: str = "class",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    购物篮分析 - 目标品类的关联品类 + YoY对比

    Args:
        start_date: 周期开始日期
        end_date: 周期结束日期
        target_category: 目标品类名称
        level: 品类级别
        channel: 渠道筛选
        exclude_channels: 排除渠道列表

    Returns:
        MarketBasketResponse 结构
    """
    from dateutil.relativedelta import relativedelta

    conn = get_connection()

    try:
        # 当期
        current = _compute_market_basket(
            conn, target_category, start_date, end_date,
            level, channel, exclude_channels)

        # 去年同期
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        prev_start = (start_dt - relativedelta(years=1)).strftime("%Y-%m-%d")
        prev_end = (end_dt - relativedelta(years=1)).strftime("%Y-%m-%d")

        previous = _compute_market_basket(
            conn, target_category, prev_start, prev_end,
            level, channel, exclude_channels)

    finally:
        conn.close()

    # 构建排名映射
    prev_rank = {item["category_name"]: i + 1 for i, item in enumerate(previous["items"])}
    prev_conf = {item["category_name"]: item["confidence"] for item in previous["items"]}
    prev_lift = {item["category_name"]: item["lift"] for item in previous["items"]}

    yoy_items = []
    for i, cur_item in enumerate(current["items"]):
        cat = cur_item["category_name"]
        prev_item = next((p for p in previous["items"] if p["category_name"] == cat), None)

        rank_chg = None
        conf_chg = None
        lift_chg = None

        if prev_item:
            rank_chg = i + 1 - prev_rank.get(cat, i + 1)
            conf_chg = round(cur_item["confidence"] - prev_conf.get(cat, 0), 4)
            lift_chg = round(cur_item["lift"] - prev_lift.get(cat, 0), 4)

        yoy_items.append({
            "category_name": cat,
            "current": cur_item,
            "previous": prev_item,
            "confidence_change": conf_chg,
            "lift_change": lift_chg,
            "rank_change": rank_chg,
        })

    return {
        "target_category": target_category,
        "total_orders": current["total_orders"],
        "target_order_count": current["target_order_count"],
        "period_label": f"{start_date}~{end_date}",
        "yoy_period_label": f"{prev_start}~{prev_end}",
        "items": yoy_items,
        "data_quality_note": (
            f"本Tab基于 {current['total_orders']} 笔订单 / "
            f"{current['target_order_count']} 笔目标品类订单计算"
        ),
    }


# ---- 品类流失 ---------------------------------------------------------------

def get_category_churn(
    start_date: str,
    end_date: str,
    level: str = "class",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    品类流失 - MoM变化 + 流失去向 + 流失用户数

    Args:
        start_date: 周期开始日期
        end_date: 周期结束日期
        level: 品类级别
        channel: 渠道筛选
        exclude_channels: 排除渠道列表

    Returns:
        CategoryChurnResponse 结构
    """
    from datetime import date, timedelta

    conn = get_connection()
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    period_days = (end_dt - start_dt).days + 1

    prev_start = (start_dt - timedelta(days=period_days)).strftime("%Y-%m-%d")
    prev_end = (end_dt - timedelta(days=period_days)).strftime("%Y-%m-%d")

    level_col = SPU_LEVELS.get(level, "spu_product_class")
    valid_sql, _ = OrderFilters.valid_order()

    # channel/exclude 在两个CTE(current+previous)都出现,参数需传两次
    channel_params = []
    exclude_params = []
    channel_sql = ""
    if channel and channel != "全店":

        db_channels = expand_channels([channel])
        if len(db_channels) == 1:
            channel_sql = "AND o.channel = ?"
            channel_params = [db_channels[0]]
        else:
            placeholders = ",".join(["?"] * len(db_channels))
            channel_sql = f"AND o.channel IN ({placeholders})"
            channel_params = list(db_channels)

    exclude_sql = ""
    if exclude_channels:
        db_ex = expand_channels(exclude_channels)
        placeholders = ",".join(["?"] * len(db_ex))
        exclude_sql = f"AND o.channel NOT IN ({placeholders})"
        exclude_params = list(db_ex)

    # 参数顺序: current(start_date,end_date) + channel + exclude
    #           + previous(prev_start,prev_end) + channel + exclude
    params = (
        [start_date, end_date] + channel_params + exclude_params +
        [prev_start, prev_end] + channel_params + exclude_params
    )

    sql = f"""
    WITH current_period_users AS (
        SELECT DISTINCT
            COALESCE(o.{level_col}, '未知') AS category_name,
            o.user_id
        FROM orders o
        WHERE o.pay_time >= ?
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          {channel_sql}
          {exclude_sql}
    ),
    previous_period_users AS (
        SELECT DISTINCT
            COALESCE(o.{level_col}, '未知') AS category_name,
            o.user_id
        FROM orders o
        WHERE o.pay_time >= ?
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          {channel_sql}
          {exclude_sql}
    ),
    current_period_totals AS (
        -- 本期各品类总用户数(用于展示"本期规模")
        SELECT
            category_name,
            COUNT(DISTINCT user_id) AS curr_total_users
        FROM current_period_users
        GROUP BY category_name
    ),
    category_churn AS (
        SELECT
            p.category_name,
            COUNT(DISTINCT p.user_id) AS prev_users,
            COUNT(DISTINCT c.user_id) AS curr_users,
            COUNT(DISTINCT CASE WHEN c.user_id IS NOT NULL THEN p.user_id END) AS retained_users,
            COUNT(DISTINCT CASE WHEN c.user_id IS NULL THEN p.user_id END) AS churned_users
        FROM previous_period_users p
        LEFT JOIN current_period_users c ON p.user_id = c.user_id AND p.category_name = c.category_name
        GROUP BY p.category_name
    ),
    inter_category_churn AS (
        -- 上期买A,本期买B(B!=A)的用户
        SELECT
            p.category_name AS from_category,
            COALESCE(c.category_name, '沉默流失') AS to_category,
            COUNT(DISTINCT p.user_id) AS inter_churn_users
        FROM previous_period_users p
        INNER JOIN current_period_users c ON p.user_id = c.user_id
        WHERE p.category_name != c.category_name
        GROUP BY p.category_name, c.category_name
    ),
    silent_churn AS (
        -- 上期买A,本期无订单
        SELECT
            p.category_name,
            COUNT(DISTINCT p.user_id) AS silent_users
        FROM previous_period_users p
        WHERE NOT EXISTS (SELECT 1 FROM current_period_users c WHERE c.user_id = p.user_id)
        GROUP BY p.category_name
    ),
    top_churn_dest AS (
        SELECT
            from_category,
            to_category,
            inter_churn_users,
            ROW_NUMBER() OVER (PARTITION BY from_category ORDER BY inter_churn_users DESC) AS rn
        FROM inter_category_churn
    )
    SELECT
        cc.category_name,
        cc.prev_users,
        COALESCE(ct.curr_total_users, 0) AS curr_total_users,
        cc.retained_users,
        cc.churned_users,
        COALESCE(sc.silent_users, 0) AS silent_users,
        tcd1.to_category AS top_dest1,
        tcd1.inter_churn_users AS top_dest1_users,
        tcd2.to_category AS top_dest2,
        tcd2.inter_churn_users AS top_dest2_users
    FROM category_churn cc
    LEFT JOIN current_period_totals ct ON cc.category_name = ct.category_name
    LEFT JOIN silent_churn sc ON cc.category_name = sc.category_name
    LEFT JOIN top_churn_dest tcd1 ON cc.category_name = tcd1.from_category AND tcd1.rn = 1
    LEFT JOIN top_churn_dest tcd2 ON cc.category_name = tcd2.from_category AND tcd2.rn = 2
    """
    result = conn.execute(sql, params).fetchall()
    conn.close()

    scatter_data = []
    bar_data = []
    table = []

    for row in result:
        cat_name = row[0]
        prev_users = int(row[1] or 0)
        curr_total_users = int(row[2] or 0)  # 本期该品类总用户数
        retained = int(row[3] or 0)
        churned = int(row[4] or 0)
        silent = int(row[5] or 0)
        inter_churned = churned - silent  # 品类间流失 = 总流失 - 沉默流失

        mom_change = (curr_total_users - prev_users) / prev_users if prev_users > 0 else 0

        top_dest1 = row[6] if row[6] else "无"
        top_dest1_users = int(row[7] or 0)
        top_dest2 = row[8] if row[8] else "无"
        top_dest2_users = int(row[9] or 0)

        dest1_ratio = top_dest1_users / inter_churned if inter_churned > 0 else 0
        dest2_ratio = top_dest2_users / inter_churned if inter_churned > 0 else 0

        scatter_data.append({
            "category_name": cat_name,
            "current_users": curr_total_users,
            "mom_change_rate": round(mom_change, 4),
            "churn_users": churned,
            "inter_churn": inter_churned,
            "silent_churn": silent,
        })

        bar_data.append({
            "category_name": cat_name,
            "current_users": curr_total_users,
            "previous_users": prev_users,
            "mom_change_rate": round(mom_change, 4),
        })

        # 挽回建议
        suggestion = ""
        if inter_churned > 0 and top_dest1 != "无":
            suggestion = f"触达推送 {top_dest1}"
        elif silent > churned * 0.5:
            suggestion = "发送召回触达,配合首单礼包促进回流"

        table.append({
            "category_name": cat_name,
            "current_users": curr_total_users,
            "previous_users": prev_users,
            "mom_change_rate": round(mom_change, 4),
            "inter_churn": inter_churned,
            "silent_churn": silent,
            "top_churn_dest1": top_dest1,
            "top_churn_dest1_ratio": round(dest1_ratio, 4),
            "top_churn_dest2": top_dest2,
            "top_churn_dest2_ratio": round(dest2_ratio, 4),
            "挽回建议": suggestion,
        })

    # 按流失严重度排序
    scatter_data.sort(key=lambda x: x["mom_change_rate"])
    table.sort(key=lambda x: x["mom_change_rate"])

    suggestions = []
    large_decline = [t for t in table if t["mom_change_rate"] < -0.2 and t["previous_users"] > 1000]
    if large_decline:
        suggestions.append(f"⚠️ 紧急:{large_decline[0]['category_name']} 流失加速(<-20%),建议重新评估资源分配")

    return {
        "scatter_data": scatter_data,
        "bar_data": bar_data,
        "table": table,
        "operation_suggestions": suggestions,
        "data_quality_note": f"本期: {start_date}~{end_date},上期: {prev_start}~{prev_end}",
    }


# ---- 品类详情页 ------------------------------------------------------------

def get_category_daily_trend(
    category_id: str,
    start_date: str,
    end_date: str,
    granularity: str = "daily",
) -> Dict[str, Any]:
    """
    品类日趋势

    Args:
        category_id: 品类ID/名称
        start_date: 开始日期
        end_date: 结束日期
        granularity: daily/weekly/monthly

    Returns:
        CategoryDailyTrendResponse
    """
    conn = get_connection()
    valid_sql, _ = OrderFilters.valid_order()

    # 根据粒度确定日期分组
    if granularity == "monthly":
        date_col = "STRFTIME('%Y-%m', pay_time)"
        date_key_name = "date_key"
    elif granularity == "weekly":
        date_col = "STRFTIME('%Y-W%W', pay_time)"
        date_key_name = "date_key"
    else:
        date_col = "CAST(pay_time AS DATE)"
        date_key_name = "date_key"

    sql = f"""
    WITH daily_data AS (
        SELECT
            {date_col} AS {date_key_name},
            SUM(actual_amount) AS gmv,
            COUNT(DISTINCT user_id) AS user_count
        FROM orders
        WHERE pay_time >= ?
          AND pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          AND spu_product_class = ?
        GROUP BY {date_col}
        ORDER BY {date_col}
    )
    SELECT {date_key_name}, gmv, user_count
    FROM daily_data
    """
    result = conn.execute(sql, [start_date, end_date, category_id]).fetchall()
    conn.close()

    dates = [row[0] for row in result]
    gmv = [float(row[1] or 0) for row in result]
    user_count = [int(row[2] or 0) for row in result]
    aus = [round(g / u if u > 0 else 0, 2) for g, u in zip(gmv, user_count)]
    new_customer_ratio = [0.0] * len(dates)  # 简化

    return {
        "category_id": category_id,
        "category_name": category_id,
        "granularity": granularity,
        "dates": dates,
        "gmv": gmv,
        "user_count": user_count,
        "aus": aus,
        "new_customer_ratio": new_customer_ratio,
    }


def get_category_user_list(
    category_id: str,
    start_date: str,
    end_date: str,
    limit: int = 100,
) -> Dict[str, Any]:
    """
    品类用户明细

    Args:
        category_id: 品类ID/名称
        start_date: 开始日期
        end_date: 结束日期
        limit: 返回用户数上限

    Returns:
        CategoryUserListResponse
    """
    conn = get_connection()
    valid_sql, _ = OrderFilters.valid_order()

    sql = f"""
    WITH category_users AS (
        SELECT DISTINCT
            o.user_id,
            COUNT(DISTINCT o.order_id) AS order_count,
            SUM(o.actual_amount) AS total_gmv,
            MIN(o.pay_time) AS first_order_date,
            MAX(o.pay_time) AS last_order_date
        FROM orders o
        WHERE o.pay_time >= ?
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          AND spu_product_class = ?
        GROUP BY o.user_id
    ),
    user_segments AS (
        SELECT r.user_id, r.segment_id
        FROM user_rfm r
        WHERE r.analysis_date = (
            SELECT MAX(analysis_date) FROM user_rfm
        )
    )
    SELECT
        cu.user_id,
        cu.order_count,
        cu.total_gmv,
        cu.first_order_date,
        cu.last_order_date,
        COALESCE(us.segment_id, 9) AS segment_id,
        EXISTS(SELECT 1 FROM orders o WHERE o.user_id = cu.user_id AND o.is_member = TRUE LIMIT 1) AS is_member
    FROM category_users cu
    LEFT JOIN user_segments us ON cu.user_id = us.user_id
    ORDER BY cu.total_gmv DESC
    LIMIT ?
    """
    result = conn.execute(sql, [start_date, end_date, category_id, limit]).fetchall()

    # 获取总用户数
    count_sql = """
    SELECT COUNT(DISTINCT user_id)
    FROM orders
    WHERE pay_time >= ? AND pay_time < DATE(?) + INTERVAL '1' DAY
      AND {valid_sql}
      AND spu_product_class = ?
    """
    total_result = conn.execute(count_sql, [start_date, end_date, category_id]).fetchone()
    total_users = int(total_result[0] if total_result else 0)
    conn.close()

    # 获取象限名称
    from backend.semantic.segments import get_registry
    registry = get_registry()

    users = []
    for row in result:
        seg_id = int(row[5])
        seg = registry.get(seg_id)
        seg_name = seg.name_cn if seg else "其他"

        users.append({
            "user_id": str(row[0]),
            "nickname": f"用户{str(row[0])[:8]}",
            "order_count": int(row[1] or 0),
            "total_gmv": round(float(row[2] or 0), 2),
            "first_order_date": str(row[3])[:10] if row[3] else "",
            "last_order_date": str(row[4])[:10] if row[4] else "",
            "segment_id": seg_id,
            "segment_name": seg_name,
            "is_member": bool(row[6]),
            "is_wool_party": False,  # 简化
        })

    return {
        "category_id": category_id,
        "category_name": category_id,
        "total_users": total_users,
        "users": users,
    }


def _resolve_repurchase_date_ranges(
    start_date: str,
    end_date: str,
) -> Dict[str, Any]:
    """
    解析品类回购分析的日期范围（当前期/同比期/前年期）。
    复用 _resolve_date_ranges 的逻辑但简化接口。
    """
    from datetime import date as dt_date, timedelta as dt_timedelta
    import calendar

    sy, sm, sd = map(int, start_date.split("-"))
    ey, em, ed = map(int, end_date.split("-"))
    cutoff_date = dt_date(sy, sm, 1) - dt_timedelta(days=1)
    cutoff = cutoff_date.strftime("%Y-%m-%d")

    def _safe_date(y: int, m: int, d: int) -> dt_date:
        """闰年安全: 2-29 → 2-28"""
        max_day = calendar.monthrange(y, m)[1]
        return dt_date(y, m, min(d, max_day))

    # 同比期: 去年同期
    comp_start = _safe_date(sy - 1, sm, sd).strftime("%Y-%m-%d")
    comp_end = _safe_date(ey - 1, em, ed).strftime("%Y-%m-%d")
    comp_cutoff = (dt_date(sy - 1, sm, 1) - dt_timedelta(days=1)).strftime("%Y-%m-%d")

    # 前年期
    prev2_start = _safe_date(sy - 2, sm, sd).strftime("%Y-%m-%d")
    prev2_end = _safe_date(ey - 2, em, ed).strftime("%Y-%m-%d")
    prev2_cutoff = (dt_date(sy - 2, sm, 1) - dt_timedelta(days=1)).strftime("%Y-%m-%d")

    return {
        "current": (f"{start_date} 00:00:00", f"{end_date} 23:59:59", cutoff),
        "comp": (f"{comp_start} 00:00:00", f"{comp_end} 23:59:59", comp_cutoff),
        "prev2": (f"{prev2_start} 00:00:00", f"{prev2_end} 23:59:59", prev2_cutoff),
        "labels": (str(sy), str(sy - 1), str(sy - 2)),
    }


# R区间分段顺序（与 rfm_service.py 保持一致）
_R_SEGMENT_ORDER = [
    "近1个月已购客",
    "近2-3个月已购客",
    "近4-6月已购客",
    "近7-12个月已购客",
    "近13个月-近24个月已购客",
    "2年外已购客",
    "已购客TTL",
]


def _run_category_repurchase_period(
    conn: duckdb.DuckDBPyConnection,
    start_dt: str,
    end_dt: str,
    cutoff_dt: str,
    category: str,
    category_field: str = "spu_product_class",
    metric_type: str = "GSV",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> tuple[
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
]:
    """
    执行单个周期的品类回购分析查询，返回4组数据：
    - all_same: 全店-同品回购
    - all_cross: 全店-跨品类回购
    - member_same: 会员-同品回购
    - member_cross: 会员-跨品类回购
    """
    from backend.semantic.filters import expand_channels

    valid_sql, _ = OrderFilters.valid_order()

    # 渠道过滤
    channel_where_base = ""
    base_params_extra: List[str] = []
    if channel and channel != "全店":
        db_channels = expand_channels([channel])
        if len(db_channels) == 1:
            channel_where_base = " AND o.channel = ?"
            base_params_extra = [db_channels[0]]
        else:
            ph = ",".join(["?"] * len(db_channels))
            channel_where_base = f" AND o.channel IN ({ph})"
            base_params_extra = list(db_channels)

    exclude_where = ""
    exclude_params: List[str] = []
    if exclude_channels:
        db_ex = expand_channels(exclude_channels)
        ex_ph = ",".join(["?"] * len(db_ex))
        exclude_where = f" AND o.channel NOT IN ({ex_ph})"
        exclude_params = list(db_ex)

    refund_where = "AND is_refund = FALSE" if metric_type == "GSV" else ""

    # 参数组装
    # hist_customers: cutoff, cutoff (cutoff参数)
    # base_orders: start_dt, end_dt
    # hist_customers 的排除/渠道参数
    hist_params: List[str] = [cutoff_dt, cutoff_dt]
    base_params: List[str] = [start_dt, end_dt]

    # 品类字段安全值（白名单校验已由 level 参数约束）
    safe_category = category.replace("'", "''")

    sql = f"""
    WITH
    base_orders AS (
        SELECT user_id, actual_amount
        FROM orders o
        WHERE pay_time >= ?::TIMESTAMP
          AND pay_time <= ?::TIMESTAMP
          AND {valid_sql}
          {channel_where_base}
          {exclude_where}
          {refund_where}
    ),
    hist_customers AS (
        SELECT
            user_id,
            DATEDIFF('day', MAX(pay_time)::DATE, ?::DATE) AS recency_days,
            BOOL_OR(is_member) AS is_member
        FROM orders o
        WHERE o.{category_field} = '{safe_category}'
          AND pay_time <= ?::TIMESTAMP
          AND {valid_sql}
          {exclude_where}
        GROUP BY user_id
    ),
    r_segmented AS (
        SELECT
            user_id, recency_days, is_member,
            CASE
                WHEN recency_days BETWEEN 0 AND 30 THEN '近1个月已购客'
                WHEN recency_days BETWEEN 31 AND 90 THEN '近2-3个月已购客'
                WHEN recency_days BETWEEN 91 AND 180 THEN '近4-6月已购客'
                WHEN recency_days BETWEEN 181 AND 365 THEN '近7-12个月已购客'
                WHEN recency_days BETWEEN 366 AND 730 THEN '近13个月-近24个月已购客'
                WHEN recency_days > 730 THEN '2年外已购客'
            END AS r_segment
        FROM hist_customers
    ),
    member_segmented AS (
        SELECT user_id, r_segment FROM r_segmented WHERE is_member = TRUE
    ),
    -- 同品回购：分析期内购买同一品类的用户
    same_repurchase AS (
        SELECT DISTINCT user_id
        FROM orders o
        WHERE o.{category_field} = '{safe_category}'
          AND pay_time >= ?::TIMESTAMP
          AND pay_time <= ?::TIMESTAMP
          AND {valid_sql}
          {channel_where_base}
          {exclude_where}
          {refund_where}
    ),
    -- 跨品类回购：分析期内购买任何其他品类的用户
    cross_repurchase AS (
        SELECT DISTINCT user_id
        FROM orders o
        WHERE o.{category_field} IS NOT NULL
          AND o.{category_field} != '{safe_category}'
          AND pay_time >= ?::TIMESTAMP
          AND pay_time <= ?::TIMESTAMP
          AND {valid_sql}
          {channel_where_base}
          {exclude_where}
          {refund_where}
    ),
    -- 同品回购金额
    same_repurchase_amounts AS (
        SELECT o.user_id, SUM(o.actual_amount) AS repurchase_gsv
        FROM orders o
        WHERE o.{category_field} = '{safe_category}'
          AND o.pay_time >= ?::TIMESTAMP
          AND o.pay_time <= ?::TIMESTAMP
          AND {valid_sql}
          {channel_where_base}
          {exclude_where}
          {refund_where}
        GROUP BY o.user_id
    ),
    -- 跨品类回购金额
    cross_repurchase_amounts AS (
        SELECT o.user_id, SUM(o.actual_amount) AS repurchase_gsv
        FROM orders o
        WHERE o.{category_field} IS NOT NULL
          AND o.{category_field} != '{safe_category}'
          AND o.pay_time >= ?::TIMESTAMP
          AND o.pay_time <= ?::TIMESTAMP
          AND {valid_sql}
          {channel_where_base}
          {exclude_where}
          {refund_where}
        GROUP BY o.user_id
    ),
    -- 全店 同品
    stats_all_same AS (
        SELECT r.r_segment,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT sr.user_id) AS repurchase_users,
               COALESCE(SUM(sra.repurchase_gsv), 0) AS repurchase_gsv
        FROM r_segmented r
        LEFT JOIN same_repurchase sr ON r.user_id = sr.user_id
        LEFT JOIN same_repurchase_amounts sra ON r.user_id = sra.user_id
        GROUP BY r.r_segment
    ),
    ttl_all_same AS (
        SELECT '已购客TTL' AS r_segment, SUM(hist_users) AS hist_users,
               SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv
        FROM stats_all_same
    ),
    -- 全店 跨品类
    stats_all_cross AS (
        SELECT r.r_segment,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT cr.user_id) AS repurchase_users,
               COALESCE(SUM(cra.repurchase_gsv), 0) AS repurchase_gsv
        FROM r_segmented r
        LEFT JOIN cross_repurchase cr ON r.user_id = cr.user_id
        LEFT JOIN cross_repurchase_amounts cra ON r.user_id = cra.user_id
        GROUP BY r.r_segment
    ),
    ttl_all_cross AS (
        SELECT '已购客TTL' AS r_segment, SUM(hist_users) AS hist_users,
               SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv
        FROM stats_all_cross
    ),
    -- 会员 同品
    stats_member_same AS (
        SELECT r.r_segment,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT sr.user_id) AS repurchase_users,
               COALESCE(SUM(sra.repurchase_gsv), 0) AS repurchase_gsv
        FROM member_segmented r
        LEFT JOIN same_repurchase sr ON r.user_id = sr.user_id
        LEFT JOIN same_repurchase_amounts sra ON r.user_id = sra.user_id
        GROUP BY r.r_segment
    ),
    ttl_member_same AS (
        SELECT '已购客TTL' AS r_segment, SUM(hist_users) AS hist_users,
               SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv
        FROM stats_member_same
    ),
    -- 会员 跨品类
    stats_member_cross AS (
        SELECT r.r_segment,
               COUNT(DISTINCT r.user_id) AS hist_users,
               COUNT(DISTINCT cr.user_id) AS repurchase_users,
               COALESCE(SUM(cra.repurchase_gsv), 0) AS repurchase_gsv
        FROM member_segmented r
        LEFT JOIN cross_repurchase cr ON r.user_id = cr.user_id
        LEFT JOIN cross_repurchase_amounts cra ON r.user_id = cra.user_id
        GROUP BY r.r_segment
    ),
    ttl_member_cross AS (
        SELECT '已购客TTL' AS r_segment, SUM(hist_users) AS hist_users,
               SUM(repurchase_users) AS repurchase_users, SUM(repurchase_gsv) AS repurchase_gsv
        FROM stats_member_cross
    )
    SELECT 'all_same' AS mode, r_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM stats_all_same UNION ALL SELECT * FROM ttl_all_same
    )
    UNION ALL
    SELECT 'all_cross' AS mode, r_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM stats_all_cross UNION ALL SELECT * FROM ttl_all_cross
    )
    UNION ALL
    SELECT 'member_same' AS mode, r_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM stats_member_same UNION ALL SELECT * FROM ttl_member_same
    )
    UNION ALL
    SELECT 'member_cross' AS mode, r_segment, hist_users, repurchase_users, repurchase_gsv FROM (
        SELECT * FROM stats_member_cross UNION ALL SELECT * FROM ttl_member_cross
    )
    """

    # SQL中?出现顺序（严格对应）:
    # base_orders: 2(start,end) + ch + ex
    # hist_customers: 2(cutoff,cutoff) + ex
    # same_repurchase: 2(start,end) + ch + ex
    # cross_repurchase: 2(start,end) + ch + ex
    # same_repurchase_amounts: 2(start,end) + ch + ex
    # cross_repurchase_amounts: 2(start,end) + ch + ex

    full_params = base_params + base_params_extra + exclude_params  # base_orders
    full_params += hist_params + exclude_params                      # hist_customers
    full_params += base_params + base_params_extra + exclude_params  # same_repurchase
    full_params += base_params + base_params_extra + exclude_params  # cross_repurchase
    full_params += base_params + base_params_extra + exclude_params  # same_repurchase_amounts
    full_params += base_params + base_params_extra + exclude_params  # cross_repurchase_amounts

    rows = conn.execute(sql, full_params).fetchall()

    results: Dict[str, Dict[str, Dict[str, float]]] = {
        "all_same": {}, "all_cross": {},
        "member_same": {}, "member_cross": {},
    }
    totals: Dict[str, float] = {
        "all_same": 0.0, "all_cross": 0.0,
        "member_same": 0.0, "member_cross": 0.0,
    }

    for r in rows:
        mode, segment, hist_users, repurchase_users, repurchase_gsv = r
        entry = {
            "hist_users": int(hist_users or 0),
            "repurchase_users": int(repurchase_users or 0),
            "repurchase_rate": float(repurchase_users or 0) / float(hist_users or 1) if hist_users else 0.0,
            "repurchase_gsv": float(repurchase_gsv or 0),
            "repurchase_gsv_ratio": 0.0,
        }
        if segment != "已购客TTL":
            totals[mode] += float(repurchase_gsv or 0)
        results[mode][segment] = entry

    # 计算 gsv_ratio
    for mode in results:
        for seg in results[mode]:
            gsv = results[mode][seg]["repurchase_gsv"]
            results[mode][seg]["repurchase_gsv_ratio"] = gsv / totals[mode] if totals[mode] > 0 else 0.0

    # 补全缺失的 segment
    for mode in results:
        for seg in _R_SEGMENT_ORDER:
            if seg not in results[mode]:
                results[mode][seg] = {
                    "hist_users": 0, "repurchase_users": 0,
                    "repurchase_rate": 0.0, "repurchase_gsv": 0.0, "repurchase_gsv_ratio": 0.0,
                }

    return results["all_same"], results["all_cross"], results["member_same"], results["member_cross"]


def get_category_repurchase_flow(
    start_date: str,
    end_date: str,
    category: str,
    level: str = "class",
    metric_type: str = "GSV",
    channel: Optional[str] = None,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    品类回购分析主接口
    同品回购 + 跨品类回购，R区间分段，3年同比
    """
    if level not in SPU_LEVELS:
        raise ValueError(f"Invalid level: {level}")
    category_field = SPU_LEVELS[level]

    ranges = _resolve_repurchase_date_ranges(start_date, end_date)
    cur_start, cur_end, cutoff = ranges["current"]
    comp_start, comp_end, comp_cutoff = ranges["comp"]
    prev2_start, prev2_end, prev2_cutoff = ranges["prev2"]
    year_label, comp_label, prev2_label = ranges["labels"]

    conn = get_connection()
    try:
        # 当前年
        cur_same, cur_cross, cur_m_same, cur_m_cross = _run_category_repurchase_period(
            conn, cur_start, cur_end, cutoff, category, category_field, metric_type, channel, exclude_channels
        )
        # 去年
        comp_same, comp_cross, comp_m_same, comp_m_cross = _run_category_repurchase_period(
            conn, comp_start, comp_end, comp_cutoff, category, category_field, metric_type, channel, exclude_channels
        )
        # 前年
        prev2_same, prev2_cross, prev2_m_same, prev2_m_cross = _run_category_repurchase_period(
            conn, prev2_start, prev2_end, prev2_cutoff, category, category_field, metric_type, channel, exclude_channels
        )
    finally:
        conn.close()

    def _build_rows(cur_data, comp_data, prev2_data):
        rows = []
        for seg in _R_SEGMENT_ORDER:
            c = cur_data.get(seg, {})
            p = comp_data.get(seg, {})
            p2 = prev2_data.get(seg, {})
            rows.append({
                "r_segment": seg,
                "hist_users_current": c.get("hist_users", 0),
                "repurchase_users_current": c.get("repurchase_users", 0),
                "repurchase_rate_current": round(c.get("repurchase_rate", 0.0), 4),
                "repurchase_gsv_current": round(c.get("repurchase_gsv", 0.0), 2),
                "repurchase_gsv_ratio_current": round(c.get("repurchase_gsv_ratio", 0.0), 4),
                "hist_users_comp": p.get("hist_users", 0),
                "repurchase_rate_comp": round(p.get("repurchase_rate", 0.0), 4),
                "hist_users_prev2": p2.get("hist_users", 0),
                "repurchase_rate_prev2": round(p2.get("repurchase_rate", 0.0), 4),
                "yoy_hist_users": yoy_absolute(c.get("hist_users", 0), p.get("hist_users", 0)),
                "yoy_repurchase_users": yoy_absolute(c.get("repurchase_users", 0), p.get("repurchase_users", 0)),
                "yoy_repurchase_rate": yoy_ratio(c.get("repurchase_rate", 0.0), p.get("repurchase_rate", 0.0)),
                "yoy_repurchase_gsv": yoy_absolute(c.get("repurchase_gsv", 0.0), p.get("repurchase_gsv", 0.0)),
                "yoy_repurchase_gsv_ratio": yoy_ratio(c.get("repurchase_gsv_ratio", 0.0), p.get("repurchase_gsv_ratio", 0.0)),
            })
        return rows

    return {
        "year_label": year_label,
        "comp_year_label": comp_label,
        "prev2_year_label": prev2_label,
        "target_category": category,
        "same_category_rows": _build_rows(cur_same, comp_same, prev2_same),
        "cross_category_rows": _build_rows(cur_cross, comp_cross, prev2_cross),
        "member_same_category_rows": _build_rows(cur_m_same, comp_m_same, prev2_m_same),
        "member_cross_category_rows": _build_rows(cur_m_cross, comp_m_cross, prev2_m_cross),
    }


if __name__ == "__main__":
    # 测试
    print("=== 品类分布测试 ===")
    result = get_category_distribution("2026-03-19", lookback_days=90, level="category")
    print(f"日期: {result['date']}, 总用户: {result['total_users']}, 总GMV: {result['total_gmv']}")
    print(f"前5品类: {[d['name'] for d in result['distribution'][:5]]}")

    print("\n=== 品类象限矩阵测试 ===")
    result = get_category_segment_matrix("2026-03-19", lookback_days=90, level="type", top_n=5)
    print(f"日期: {result['date']}, Level: {result['level']}")
    for seg_id in range(1, 4):
        print(f"  象限{seg_id}: {[c['category'] for c in result['matrix'][str(seg_id)]]}")

    print("\n=== 品类用户画像测试 ===")
    result = get_category_user_profile("2026-03-19", lookback_days=90, category="护肤")
    print(f"品类: {result['category']}, 用户: {result['total_users']}, GMV: {result['total_gmv']}")
    print(f"象限分布前3: {[s['name'] for s in result['segment_distribution'][:3]]}")

    print("\n=== 品类概览测试 ===")
    result = get_category_overview("2026-04-01", "2026-04-17", level="type", metric_type="GSV")
    print(f"周期: {result['date_start']} ~ {result['date_end']}")
    print(f"前3品类: {[r['name'] for r in result['all_rows'][:3]]}")
    print(f"TOP1 老客GSV: {result['all_rows'][0]['old_gsv']:.0f}, 新客GSV: {result['all_rows'][0]['new_gsv']:.0f}")
