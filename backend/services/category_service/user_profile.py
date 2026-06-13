"""
品类分析服务
Sample CRM 客户分析系统 - 品类分析服务
Week 4 品类分布、品类象限矩阵、品类用户画像
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional


from backend.db.connection import get_connection
from backend.semantic.segments import _segment_meta
from backend.semantic.time import normalize_date as _normalize_date
from backend.semantic.filters import OrderFilters


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
    try:
        date_str = _normalize_date(date)
        start_date = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    
        # 使用语义层构建过滤条件
        valid_sql, _ = OrderFilters.valid_order()
    
        # 品类筛选
        category_filter = f"AND {_cat_expr('spu_category')} = ?"
        params = [date_str, start_date, date_str, lookback_days, date_str, category]
        if type is not None:
            category_filter += f" AND {_cat_expr('spu_type')} = ?"
            params.append(type)
    
        # 使用单次查询获取所有数据
    
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
              AND {_cat_expr('spu_category')} = ?
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
              AND {_cat_expr('spu_category')} = ?
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
              AND {_cat_expr('spu_category')} = ?
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
              AND {_cat_expr('spu_category')} = ?
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
