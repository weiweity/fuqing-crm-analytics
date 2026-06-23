"""
品类分析服务
Sample CRM 客户分析系统 - 品类分析服务
Week 4 品类分布、品类象限矩阵、品类用户画像
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List


from backend.db.connection import get_connection
from backend.semantic.segments import _segment_meta
from backend.semantic.time import normalize_date as _normalize_date
from backend.semantic.filters import FilterBuilder, MetricType, expand_channels


SPU_LEVELS = {
    "category": "spu_category",      # 一级品类
    "type": "spu_type",               # 二级品类
    "tier": "spu_tier",              # 层级
    "class": "spu_product_class",    # 产品类
    "subclass": "spu_product_subclass",  # 产品子类
    "cosmetic": "spu_cosmetic",      # 功效
    "spec": "spu_spec",              # 规格
}

# 非产品品类（营销赠品、虚拟商品、物料等），从品类看板中排除
EXCLUDED_PRODUCT_CATEGORIES = (
    '购物金', '0.01', '邮费补差链接', '明星小卡', '刮刮卡',
    '有价优惠劵', '盲盒', '手持镜', '帆布袋', '帆布包',
    '加湿器', '起泡网', '吸油纸', '硅胶刷', '湿敷棉',
    '洗脸巾', 'PR礼盒', '多品类集合链',
)


def _cat_expr(field: str) -> str:
    """品类字段表达式：TRIM + COALESCE，修复尾部空格问题"""
    return f"COALESCE(TRIM(o.{field}), '未知')"


def _excluded_cat_filter(field: str) -> str:
    """生成排除非产品品类的 SQL 片段"""
    placeholders = ",".join(["?"] * len(EXCLUDED_PRODUCT_CATEGORIES))
    return f"AND TRIM(COALESCE(o.{field}, '未知')) NOT IN ({placeholders})"


def _build_distribution_filter(
    channel: Optional[str],
    exclude_channels: Optional[List[str]],
) -> tuple:
    """Sprint 54 Lane C L3: 收编 valid_order() + channel + exclude 到 FilterBuilder
    避免 f-string 内嵌 (本函数本身无 f-string 输出,所有用户输入走 add_extra 参数化).

    Sprint 98 真治本: FilterBuilder 默认输出 `o.channel`, 跟
    `LEFT JOIN user_rfm r` 共存时不触发 DuckDB Binder 错.

    Returns:
        (where_clause, params) — where_clause 拼到 SQL 模板 `AND {where_clause}` 中;
        params 拼到 conn.execute 参数列表开头.
    """
    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    if channel and channel != "全店":
        fb.with_channels([channel])
    elif exclude_channels:
        fb.with_exclude_channels(exclude_channels)
    where_sql, params = fb.build()
    return where_sql, params


def _build_distribution_channel_filter(
    channel: Optional[str],
    exclude_channels: Optional[List[str]],
) -> tuple:
    """Sprint 54 Lane C L3 fix: 返回 (channel_str, exclude_str, params).

    旧版 distribution.py 用了 `{channel_filter_str}` `{exclude_filter_str}` 占位符但漏定义
    → NameError. 本函数生成 channel IN / channel NOT IN 两个独立 SQL 片段 + 合并 params.

    注意: 这跟 _build_distribution_filter 不重复 — 后者只生成 valid_order + channel
    合并的 where, 本函数生成**纯 channel/exclude 逻辑**(给 _excluded_cat_filter
    一样的"AND ..." 形式前缀).
    """
    channel_parts: List[str] = []
    exclude_parts: List[str] = []
    params: List[Any] = []
    if channel and channel != "全店":
        ch_list = expand_channels([channel])
        placeholders = ",".join(["?"] * len(ch_list))
        channel_parts.append(f"AND o.channel IN ({placeholders})")
        params.extend(ch_list)
    if exclude_channels:
        ex_list = expand_channels(exclude_channels)
        placeholders = ",".join(["?"] * len(ex_list))
        exclude_parts.append(f"AND o.channel NOT IN ({placeholders})")
        params.extend(ex_list)
    return " ".join(channel_parts), " ".join(exclude_parts), params


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
    category_field_expr = _cat_expr(category_field)
    excluded_cat_sql = _excluded_cat_filter(category_field)

    # Sprint 54 Lane C L3: valid_order + channel + exclude 收编到 FilterBuilder
    valid_where_clause, valid_where_params = _build_distribution_filter(channel, exclude_channels)
    # Sprint 54 Lane C L3 fix: 补充 channel_filter / exclude_filter (跟 _excluded_cat_filter
    # 一样返回 "AND ..." 或 "" 形式, 拼到 SQL 模板). 否则 {channel_filter_str}/{exclude_filter_str} NameError.
    channel_filter_str, exclude_filter_str, channel_filter_params = _build_distribution_channel_filter(channel, exclude_channels)
    # 象限筛选 (segment_id 是用户输入,走 `?` 占位)
    # 不用 segment 时用 1=1 (无占位) 避免 NULL 比较问题
    if segment_id is not None:
        segment_filter = "AND r.segment_id = ?"
        segment_params = [segment_id]
    else:
        segment_filter = "AND 1 = 1"
        segment_params = []

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
          AND {valid_where_clause}
          {excluded_cat_sql}
          {segment_filter}
          {channel_filter_str}
          {exclude_filter_str}
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
      AND {valid_where_clause}
      {excluded_cat_sql}
      {segment_filter}
      {channel_filter_str}
      {exclude_filter_str}
    """

    conn = get_connection()
    try:
        # Sprint 60.1.1 fix: params 顺序对齐 SQL `?` 占位符位置 (跟 Sprint 60 治本同根因类型).
        # SQL `?` 顺序 (按 SQL 文本出现位置):
        #   1-2) base_params DATE(?) × 2 (analysis_date, start_date)
        #   3) period_orders r.analysis_date = ?
        #   4) period_orders r.lookback_days = ?
        #   5) period_orders DATE(?) + INTERVAL '1' DAY (end_date)
        #   6-7) valid_where_clause (FilterBuilder): pay_time >= ? AND pay_time <= ?  (2)
        #   8-11) valid_where_clause: o.channel NOT IN (?,?,?,?) (exclude × 4, 已 Sprint 60.1 加 o. 前缀)
        #   12-29) excluded_cat_sql NOT IN (?,?,...×18) EXCLUDED_PRODUCT_CATEGORIES
        # 修前: valid_where_params 在前 → SQL 第 1 个 DATE(?) 拿到 pay_time start, 错位 2 params.
        # 修后: base+rfm 在前, valid_where_params 在中, EXCLUDED 在后, 跟 SQL `?` 一一对应.
        excluded_params = list(EXCLUDED_PRODUCT_CATEGORIES)
        params = (
            [date_str, start_date]
            + segment_params
            + [date_str, lookback_days, date_str]
            + list(valid_where_params)
            + excluded_params
            + channel_filter_params
        )

        result = conn.execute(sql, params).fetchall()
        total_result = conn.execute(total_query, params).fetchone()
        total_users = int(total_result[0]) if total_result[0] else 0
        total_members = int(total_result[1]) if total_result[1] else 0
        total_gmv = float(total_result[2]) if total_result[2] else 0.0
    finally:
        pass

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

        # Sprint 54 Lane C L3: valid_order + exclude 收编到 FilterBuilder
        valid_where_clause, valid_where_params = _build_distribution_filter(None, exclude_channels)
        # Sprint 54 Lane C L3 fix: get_category_segment_matrix 也要 {exclude_filter_str}
        _, exclude_filter_str, _ = _build_distribution_channel_filter(None, exclude_channels)

        category_field = SPU_LEVELS.get(level, "spu_type")
        category_field_expr = _cat_expr(category_field)
        excluded_cat_sql = _excluded_cat_filter(category_field)

        # 统一引用 semantic/segments.py 中的 RFM_THRESHOLDS,禁止硬编码
        from backend.semantic.segments import RFM_THRESHOLDS

        _rt = RFM_THRESHOLDS["r"]
        _ft = RFM_THRESHOLDS["f"]
        _mt = RFM_THRESHOLDS["m"]

        excluded_params = list(EXCLUDED_PRODUCT_CATEGORIES)

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
              AND {valid_where_clause}
              {exclude_filter_str}
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
              AND {valid_where_clause}
              {excluded_cat_sql}
              {exclude_filter_str}
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

        # Sprint 54 Lane C L3: 顺序为 valid_where_params + base + excluded
        # valid_where_clause 已经包含 valid_order + exclude (FilterBuilder 输出)
        params: List[Any] = (
            list(valid_where_params)
            + [date_str, start_date]
            + excluded_params
        )

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
        pass
