"""
Sample CRM 客户分析系统 - 地域分析服务
Week 4 地域分布、地域象限矩阵、地域趋势
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from backend.db.connection import get_connection
from backend.semantic.filters import OrderFilters
from backend.semantic.segments import _segment_meta
from backend.semantic.time import normalize_date as _normalize_date


def _coalesce_field(field: str, replacement: str = "未知") -> str:
    """处理 NULL 值"""
    return f"COALESCE({field}, '{replacement}')"


def get_geo_distribution(
    date: str,
    lookback_days: int = 90,
    level: str = "省份",
    top_n: int = 50,
    segment_id: Optional[int] = None,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    获取地域分布

    Args:
        date: 分析日期 (YYYY-MM-DD)
        lookback_days: 回溯天数
        level: 省份/城市
        top_n: 返回前 N 条
        segment_id: 象限筛选（可选）
        exclude_channels: 排除的渠道列表（可选）

    Returns:
        {
            "date": str,
            "level": str,
            "total_users": int,
            "total_gmv": float,
            "distribution": [{"name": str, "user_count": int, "gmv": float, "占比": float}, ...]
        }
    """
    conn = get_connection()
    try:
        date_str = _normalize_date(date)
        start_date = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        # 使用语义层构建过滤条件
        valid_sql, _ = OrderFilters.valid_order()

        # 地域字段
        geo_field = "province" if level == "省份" else "city"
        geo_field_expr = f"COALESCE(o.{geo_field}, '未知')"

        # 象限筛选
        segment_filter = ""
        if segment_id is not None:
            segment_filter = "AND r.segment_id = ?"

        # 排除渠道
        exclude_filter = ""
        exclude_params = []
        if exclude_channels:
            placeholders = ",".join(["?"] * len(exclude_channels))
            exclude_filter = f"AND o.channel NOT IN ({placeholders})"
            exclude_params = list(exclude_channels)

        # 参数顺序: date_str(analysis_date), start_date, date_str(analysis_date for r join), lookback_days, date_str(end_date for +INTERVAL), [segment_id], [exclude_channels]
        base_params = [date_str, start_date, date_str, lookback_days, date_str]
        if segment_id is not None:
            base_params.append(segment_id)
        base_params.extend(exclude_params)

        # 主查询 - 地域分布
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
                {geo_field_expr} AS geo_name
            FROM orders o
            CROSS JOIN base_params p
            LEFT JOIN user_rfm r ON o.user_id = r.user_id
                AND r.analysis_date = ?
                AND r.metric_type = 'GMV'
                AND r.lookback_days = ?
            WHERE o.pay_time >= p.start_date
              AND o.pay_time < DATE(?) + INTERVAL '1' DAY
              AND {valid_sql}
              {segment_filter}
              {exclude_filter}
        ),
        geo_summary AS (
            SELECT
                geo_name,
                COUNT(DISTINCT user_id) AS user_count,
                SUM(actual_amount) AS gmv
            FROM period_orders
            GROUP BY geo_name
        )
        SELECT
            geo_name,
            user_count,
            gmv
        FROM geo_summary
        ORDER BY user_count DESC
        LIMIT ?
        """

        result = conn.execute(sql, base_params + [top_n]).fetchall()

        # 总计查询
        total_query = f"""
        WITH base_params AS (
            SELECT
                DATE(?) AS analysis_date,
                DATE(?) AS start_date
        )
        SELECT
            COUNT(DISTINCT o.user_id) AS total_users,
            SUM(o.actual_amount) AS total_gmv
        FROM orders o
        CROSS JOIN base_params p
        LEFT JOIN user_rfm r ON o.user_id = r.user_id
            AND r.analysis_date = ?
            AND r.metric_type = 'GMV'
            AND r.lookback_days = ?
        WHERE o.pay_time >= p.start_date
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND {valid_sql}
          {segment_filter}
          {exclude_filter}
        """

        total_result = conn.execute(total_query, base_params).fetchone()
        total_users = int(total_result[0]) if total_result[0] else 0
        total_gmv = float(total_result[1]) if total_result[1] else 0.0
    finally:
        pass

    distribution = []
    for row in result:
        geo_name = row[0]
        user_count = int(row[1]) if row[1] else 0
        gmv = float(row[2]) if row[2] else 0.0
        user_pct = round(user_count / total_users * 100, 2) if total_users > 0 else 0
        gmv_pct = round(gmv / total_gmv * 100, 2) if total_gmv > 0 else 0
        distribution.append({
            "name": geo_name,
            "user_count": user_count,
            "gmv": round(gmv, 2),
            "user_ratio": round(user_pct / 100, 4),   # 前端期望小数
            "gmv_ratio": round(gmv_pct / 100, 4),     # 前端期望小数
        })

    return {
        "date": date_str,
        "level": level,
        "total_users": total_users,
        "total_gmv": round(total_gmv, 2),
        "distribution": distribution
    }


def get_geo_segment_matrix(
    date: str,
    lookback_days: int = 90,
    top_n: int = 10,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    获取地域-象限交叉矩阵

    Args:
        date: 分析日期 (YYYY-MM-DD)
        lookback_days: 回溯天数
        top_n: 每个象限返回前 N 个省份
        exclude_channels: 排除的渠道列表（可选）

    Returns:
        {
            "date": str,
            "matrix": {
                "1": [{"province": str, "user_count": int, "gmv": float}, ...],
                "2": [...],
                ...
            },
            "segments": [{"id": int, "name": str, "color": str}, ...]
        }
    """
    conn = get_connection()
    try:
        date_str = _normalize_date(date)
        (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        # 使用语义层构建过滤条件
        valid_sql, _ = OrderFilters.valid_order()

        # 排除渠道
        exclude_filter = ""
        exclude_params = []
        if exclude_channels:
            placeholders = ",".join(["?"] * len(exclude_channels))
            exclude_filter = f"AND o.channel NOT IN ({placeholders})"
            exclude_params = list(exclude_channels)

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
                o.province,
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
              {exclude_filter}
        ),
        geo_segment AS (
            SELECT
                COALESCE(province, '未知') AS province,
                segment_id,
                COUNT(DISTINCT user_id) AS user_count,
                SUM(actual_amount) AS gmv
            FROM period_orders
            GROUP BY province, segment_id
        )
        SELECT
            province,
            segment_id,
            user_count,
            gmv
        FROM geo_segment
        ORDER BY segment_id, user_count DESC
        """

        params = [date_str, date_str, date_str, lookback_days, date_str]
        params.extend(exclude_params)
        result = conn.execute(sql, params).fetchall()
    finally:
        pass

    # 按象限分组，每组取 top_n
    segment_data = {i: [] for i in range(1, 10)}
    for row in result:
        province = row[0]
        segment_id = int(row[1])
        user_count = int(row[2]) if row[2] else 0
        gmv = float(row[3]) if row[3] else 0.0

        if len(segment_data[segment_id]) < top_n:
            segment_data[segment_id].append({
                "province": province,
                "user_count": user_count,
                "gmv": round(gmv, 2)
            })

    return {
        "date": date_str,
        "matrix": {str(k): v for k, v in segment_data.items()},
        "segments": [
            {"id": seg_id, **_segment_meta(seg_id)}
            for seg_id in range(1, 10)
        ]
    }


def get_geo_trend(
    start_date: str,
    end_date: str,
    lookback_days: int = 90,
    top_n: int = 5,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    获取地域趋势（多时间点）

    Args:
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        lookback_days: 回溯天数
        top_n: 追踪前 N 个省份
        exclude_channels: 排除的渠道列表（可选）

    Returns:
        {
            "time_points": [str, ...],
            "top_provinces": [str, ...],
            "trends": {
                "省份1": {"dates": [...], "users": [...], "gmv": [...]},
                ...
            }
        }
    """
    conn = get_connection()
    try:
        start_str = _normalize_date(start_date)
        end_str = _normalize_date(end_date)

        # 使用语义层构建过滤条件
        valid_sql, _ = OrderFilters.valid_order()

        # 排除渠道
        exclude_filter = ""
        exclude_params = []
        if exclude_channels:
            placeholders = ",".join(["?"] * len(exclude_channels))
            exclude_filter = f"AND o.channel NOT IN ({placeholders})"
            exclude_params = list(exclude_channels)

        # 生成时间点（每月一个）
        from datetime import datetime
        start_dt = datetime.strptime(start_str, "%Y-%m-%d")
        end_dt = datetime.strptime(end_str, "%Y-%m-%d")

        time_points = []
        current = start_dt
        while current <= end_dt:
            time_points.append(current.strftime("%Y-%m-%d"))
            # 每月推进
            if current.month == 12:
                current = datetime(current.year + 1, 1, 1)
            else:
                current = datetime(current.year, current.month + 1, 1)

        if not time_points:
            return {"time_points": [], "top_provinces": [], "trends": {}}

        # 获取 top_n 省份
        top_provinces_query = f"""
        WITH base_params AS (
            SELECT
                DATE(?) AS start_date,
                DATE(?) AS end_date
        ),
        period_orders AS (
            SELECT DISTINCT
                o.user_id,
                o.province,
                o.actual_amount,
                o.pay_time
            FROM orders o
            CROSS JOIN base_params p
            WHERE o.pay_time >= p.start_date
              AND o.pay_time <= p.end_date + INTERVAL '1' DAY
              AND {valid_sql}
              {exclude_filter}
        ),
        province_summary AS (
            SELECT
                COALESCE(province, '未知') AS province,
                COUNT(DISTINCT user_id) AS user_count
            FROM period_orders
            GROUP BY province
        )
        SELECT province
        FROM province_summary
        ORDER BY user_count DESC
        LIMIT ?
        """

        top_provinces_result = conn.execute(top_provinces_query, [start_str, end_str] + exclude_params + [top_n]).fetchall()
        top_provinces = [row[0] for row in top_provinces_result]

        # 用单条 SQL 按月查出所有省份分组数据
        month_sql = f"""
        WITH base_params AS (
            SELECT
                DATE(?) AS start_date,
                DATE(?) AS end_date
        ),
        period_orders AS (
            SELECT
                o.user_id,
                o.actual_amount,
                COALESCE(o.province, '未知') AS province,
                DATE_TRUNC('month', o.pay_time)::DATE AS month_start
            FROM orders o
            CROSS JOIN base_params p
            WHERE o.pay_time >= p.start_date
              AND o.pay_time <= p.end_date + INTERVAL '1' DAY
              AND {valid_sql}
              {exclude_filter}
        )
        SELECT
            province,
            month_start,
            COUNT(DISTINCT user_id) AS user_count,
            SUM(actual_amount) AS gmv
        FROM period_orders
        WHERE province IN ({','.join(['?'] * len(top_provinces))})
        GROUP BY province, month_start
        ORDER BY province, month_start
        """

        month_result = conn.execute(
            month_sql, [start_str, end_str] + exclude_params + top_provinces
        ).fetchall()

        # 用字典 {province: {month_str: (users, gmv)}} 映射
        month_data: Dict[str, Dict[str, tuple]] = {}
        for row in month_result:
            prov = row[0]
            month_str = str(row[1])  # DATE_TRUNC 返回 DATE，str() 得到 YYYY-MM-DD
            users = int(row[2]) if row[2] else 0
            gmv = round(float(row[3]) if row[3] else 0.0, 2)
            if prov not in month_data:
                month_data[prov] = {}
            month_data[prov][month_str] = (users, gmv)

        # 构建 trends
        trends = {province: {"dates": [], "users": [], "gmv": []} for province in top_provinces}
        for tp in time_points:
            for province in top_provinces:
                trends[province]["dates"].append(tp)
                matched = month_data.get(province, {}).get(tp)
                if matched:
                    trends[province]["users"].append(matched[0])
                    trends[province]["gmv"].append(matched[1])
                else:
                    trends[province]["users"].append(0)
                    trends[province]["gmv"].append(0.0)
    finally:
        pass

    return {
        "time_points": time_points,
        "top_provinces": top_provinces,
        "trends": trends
    }


if __name__ == "__main__":
    # 测试
    print("=== 地域分布测试 ===")
    result = get_geo_distribution("2026-03-19", lookback_days=90, level="省份", top_n=10)
    print(f"日期: {result['date']}, 总用户: {result['total_users']}, 总GMV: {result['total_gmv']}")
    print(f"前5省份: {[d['name'] for d in result['distribution'][:5]]}")

    print("\n=== 地域象限矩阵测试 ===")
    result = get_geo_segment_matrix("2026-03-19", lookback_days=90, top_n=5)
    print(f"日期: {result['date']}")
    for seg_id in range(1, 4):
        print(f"  象限{seg_id}: {[p['province'] for p in result['matrix'][str(seg_id)]]}")

    print("\n=== 地域趋势测试 ===")
    result = get_geo_trend("2026-01-01", "2026-03-19", lookback_days=90, top_n=3)
    print(f"时间点: {result['time_points']}")
    print(f"省份: {result['top_provinces']}")
