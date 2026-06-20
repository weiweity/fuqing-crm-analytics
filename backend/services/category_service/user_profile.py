"""
品类分析服务
Sample CRM 客户分析系统 - 品类分析服务
Week 4 品类分布、品类象限矩阵、品类用户画像

Sprint 54 Lane B L3 FilterBuilder 改造:
- 5 个查询 (total / seg / prov / chan + 共享 CTE) 中 5 处 (valid_order filter) f-string 内嵌
  + 多个 (category filter) 字符串拼接 — 全部收到 `?` DB-API 参数化.
- 设计原则:
  1. 去掉原 base_params CTE (中间转 DATE 用的 workaround), 直接用 `?` 占位.
  2. valid_order / category / time range 用 FilterBuilder.build() + add_extra.
  3. user_rfm JOIN 条件走专用 helper (date_str + lookback_days 2 个 ?).
  4. 5 个查询共享同一份 period_orders WHERE, helper 返回 (where_sql, params).
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple


from backend.db.connection import get_connection
from backend.semantic.segments import _segment_meta
from backend.semantic.time import normalize_date as _normalize_date
from backend.semantic.filters import FilterBuilder, MetricType


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


# ─────────────────────────────────────────────────────────────
# Sprint 54 Lane B L3 FilterBuilder helpers
#
# _build_user_profile_period_where — 5 个查询共享的 period_orders CTE WHERE
# _build_user_rfm_join            — total_sql / seg_sql 的 user_rfm LEFT JOIN
# ─────────────────────────────────────────────────────────────


def _build_user_profile_period_where(
    start_date: str,
    end_date: str,
    category: str,
) -> Tuple[str, List[Any]]:
    """user_profile 5 个查询的 period_orders WHERE 共享.

    等价于原 WHERE (去掉 base_params CTE, 直接用 ?):
        WHERE o.pay_time >= DATE(?)
          AND o.pay_time < DATE(?) + INTERVAL '1' DAY
          AND (valid_order filter)
          AND COALESCE(TRIM(o.spu_category), '未知') = ?

    Returns:
        (where_sql, params) — [start_date, end_date, category].
    """
    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    where_sql, params = fb.build()
    extra_sql = (
        "o.pay_time >= DATE(?) "
        "AND o.pay_time < DATE(?) + INTERVAL '1' DAY"
    )
    extra_params: List[Any] = [start_date, end_date]
    extra_sql += f" AND {_cat_expr('spu_category')} = ?"
    extra_params.append(category)
    return f"{extra_sql} AND {where_sql}", extra_params + params


def _build_user_rfm_join(
    date_str: str,
    lookback_days: int,
) -> Tuple[str, List[Any]]:
    """user_rfm LEFT JOIN 条件 (total_sql / seg_sql 用, 共享 segment_id).

    等价于原 ON:
        LEFT JOIN user_rfm r ON o.user_id = r.user_id
            AND r.analysis_date = ?
            AND r.metric_type = 'GMV'
            AND r.lookback_days = ?

    Returns:
        (join_sql, params) — [date_str, lookback_days].
    """
    join_sql = (
        "LEFT JOIN user_rfm r ON o.user_id = r.user_id\n"
        "        AND r.analysis_date = ?\n"
        "        AND r.metric_type = 'GMV'\n"
        "        AND r.lookback_days = ?"
    )
    return join_sql, [date_str, lookback_days]


def get_category_user_profile(
    date: str,
    lookback_days: int = 90,
    category: str = "护肤",
    type: Optional[str] = None
) -> Dict[str, Any]:
    """
    获取品类用户画像(某品类的用户特征)
    """
    conn = get_connection()
    try:
        date_str = _normalize_date(date)
        start_date = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        # 5 个查询共享的 period_orders WHERE
        period_where, period_params = _build_user_profile_period_where(
            start_date=start_date,
            end_date=date_str,
            category=category,
        )
        # total_sql / seg_sql 的 user_rfm JOIN
        rfm_join, rfm_params = _build_user_rfm_join(
            date_str=date_str,
            lookback_days=lookback_days,
        )

        # 总数 + GMV
        total_sql = f"""
        WITH period_orders AS (
            SELECT
                o.user_id,
                o.actual_amount,
                o.order_id,
                COALESCE(r.segment_id, 9) AS segment_id
            FROM orders o
            {rfm_join}
            WHERE {period_where}
        )
        SELECT
            COUNT(DISTINCT user_id) AS total_users,
            SUM(actual_amount) AS total_gmv
        FROM period_orders
        """
        total_params = rfm_params + period_params
        total_result = conn.execute(total_sql, total_params).fetchone()
        total_users = int(total_result[0]) if total_result[0] else 0
        total_gmv = float(total_result[1]) if total_result[1] else 0.0
        avg_order_value = total_gmv / total_users if total_users > 0 else 0.0

        # 象限分布
        seg_sql = f"""
        WITH period_orders AS (
            SELECT
                o.user_id,
                COALESCE(r.segment_id, 9) AS segment_id
            FROM orders o
            {rfm_join}
            WHERE {period_where}
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

        # 省份分布 (无 user_rfm JOIN, 直接用 period_where)
        prov_sql = f"""
        WITH period_orders AS (
            SELECT
                o.user_id,
                o.province
            FROM orders o
            WHERE {period_where}
        )
        SELECT
            COALESCE(province, '未知') AS province,
            COUNT(DISTINCT user_id) AS user_count
        FROM period_orders
        GROUP BY province
        ORDER BY user_count DESC
        LIMIT 10
        """
        prov_result = conn.execute(prov_sql, period_params).fetchall()

        province_distribution = [
            {"province": row[0], "user_count": int(row[1]) if row[1] else 0}
            for row in prov_result
        ]

        # 渠道分布 (无 user_rfm JOIN, 直接用 period_where)
        chan_sql = f"""
        WITH period_orders AS (
            SELECT
                o.user_id,
                o.channel
            FROM orders o
            WHERE {period_where}
        )
        SELECT
            COALESCE(channel, '未知') AS channel,
            COUNT(DISTINCT user_id) AS user_count
        FROM period_orders
        GROUP BY channel
        ORDER BY user_count DESC
        """
        chan_result = conn.execute(chan_sql, period_params).fetchall()

        channel_distribution = [
            {"channel": row[0], "user_count": int(row[1]) if row[1] else 0}
            for row in chan_result
        ]

    finally:
        pass

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
