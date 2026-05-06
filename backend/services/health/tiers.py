"""
老客健康分析仪表盘 - 模块3: 客户价值分层

基于GSV和订单数的NTILE百分位分层。
"""

from typing import Dict, Any, Optional, List

from backend.db.connection import get_connection
from backend.semantic.filters import FilterBuilder, MetricType
from backend.semantic.calculations import safe_ratio
from . import config as health_config


# 运营分层映射表
SEGMENT_MAP = {
    ("S", "high"): ("超级用户", "1v1专属客服，新品优先体验", 1),
    ("A", "high"): ("忠实买家", "会员日优先，积分翻倍", 2),
    ("S", "medium"): ("潜力金主", "复购券，跨品推荐", 3),
    ("A", "medium"): ("潜力金主", "复购券，跨品推荐", 3),
    ("S", "low"): ("沉睡价值", "大促召回，短信触达", 4),
    ("A", "low"): ("沉睡价值", "大促召回，短信触达", 4),
    ("B", "high"): ("价格敏感", "满减活动，拼团", 5),
    ("C", "high"): ("价格敏感", "满减活动，拼团", 5),
    ("B", "medium"): ("常规用户", "常规积分，满赠", 6),
    ("C", "medium"): ("常规用户", "常规积分，满赠", 6),
    ("B", "low"): ("边缘用户", "低成本维护", 6),
    ("C", "low"): ("边缘用户", "低成本维护", 6),
}


def get_value_tiers(analysis_date: str, lookback_days: int = 365,
                    exclude_channels: Optional[List[str]] = None,
                    channel: Optional[str] = None) -> Dict[str, Any]:
    """
    客户价值分层
    - 价值分层: S(Top 5%) / A(Top 20%) / B(Top 50%) / C(Bottom 50%)
    - 频次分层: 阈值从配置读取，默认 high(>=5单) / medium(>=2单) / low(1单)
    """
    conn = get_connection()
    try:
        fb = FilterBuilder()
        fb.with_metric_type(MetricType.GSV)
        fb.with_lookback(analysis_date, lookback_days)
        if exclude_channels:
            fb.with_exclude_channels(exclude_channels)
        if channel:
            fb.with_channels([channel])
        where_sql, params = fb.build()

        # 频次阈值从配置读取
        freq_cfg = health_config.FREQUENCY_TIER_THRESHOLDS
        high_threshold = freq_cfg.get("high", 5)
        medium_threshold = freq_cfg.get("medium", 2)

        # 用户统计 + PERCENT_RANK分层
        rows = conn.execute(f"""
            WITH user_stats AS (
                SELECT
                    user_id,
                    SUM(actual_amount) as gsv,
                    COUNT(DISTINCT order_id) as order_count
                FROM orders
                WHERE {where_sql}
                GROUP BY user_id
            ),
            ranked AS (
                SELECT
                    user_id,
                    gsv,
                    order_count,
                    PERCENT_RANK() OVER (ORDER BY gsv) as gsv_pct,
                    PERCENT_RANK() OVER (ORDER BY order_count) as freq_pct
                FROM user_stats
            )
            SELECT
                CASE
                    WHEN gsv_pct >= 0.95 THEN 'S'
                    WHEN gsv_pct >= 0.80 THEN 'A'
                    WHEN gsv_pct >= 0.50 THEN 'B'
                    ELSE 'C'
                END as value_tier,
                CASE
                    WHEN order_count >= ? THEN 'high'
                    WHEN order_count >= ? THEN 'medium'
                    ELSE 'low'
                END as freq_tier,
                COUNT(*) as user_count,
                SUM(gsv) as gsv,
                AVG(gsv) as avg_gsv,
                AVG(order_count) as avg_orders
            FROM ranked
            GROUP BY value_tier, freq_tier
            ORDER BY value_tier, freq_tier
        """, params + [high_threshold, medium_threshold]).fetchall()

        # 计算总价值
        total_gsv = sum(float(r[3]) for r in rows)
        total_users = sum(int(r[2]) for r in rows)

        # 价值层级汇总
        value_tier_map: Dict[str, Dict[str, Any]] = {}
        freq_tier_map: Dict[str, Dict[str, Any]] = {}
        segments = []

        for r in rows:
            vt = r[0]
            ft = r[1]
            count = int(r[2])
            gsv = float(r[3])
            avg_gsv = float(r[4])
            avg_orders = float(r[5])

            # 价值层级聚合
            if vt not in value_tier_map:
                value_tier_map[vt] = {"count": 0, "gsv": 0.0}
            value_tier_map[vt]["count"] += count
            value_tier_map[vt]["gsv"] += gsv

            # 频次层级聚合
            if ft not in freq_tier_map:
                freq_tier_map[ft] = {"count": 0}
            freq_tier_map[ft]["count"] += count

            # 运营分层
            seg_name, action, priority = SEGMENT_MAP.get((vt, ft), ("其他", "观察", 6))
            segments.append({
                "segment_code": f"{vt}-{ft}",
                "segment_name": seg_name,
                "value_tier": vt,
                "frequency_tier": ft,
                "user_count": count,
                "gsv": round(gsv, 2),
                "gsv_ratio": round(safe_ratio(gsv, total_gsv, 0.0), 4),
                "avg_order_value": round(avg_gsv, 2),
                "avg_orders_per_user": round(avg_orders, 2),
                "suggested_action": action,
                "priority": priority,
            })

        # 构建价值层级定义
        tier_names = {"S": "超级价值", "A": "高价值", "B": "中等价值", "C": "长尾价值"}
        value_tiers = []
        for code in ["S", "A", "B", "C"]:
            if code in value_tier_map:
                d = value_tier_map[code]
                value_tiers.append({
                    "tier_code": code,
                    "tier_name": tier_names[code],
                    "user_count": d["count"],
                    "gsv": round(d["gsv"], 2),
                    "gsv_ratio": round(safe_ratio(d["gsv"], total_gsv, 0.0), 4),
                })

        # 构建频次层级定义
        freq_names = {"high": "高频", "medium": "中频", "low": "低频"}
        freq_thresholds = {"high": (4, None), "medium": (2, 3), "low": (1, 1)}
        frequency_tiers = []
        for code in ["high", "medium", "low"]:
            if code in freq_tier_map:
                min_o, max_o = freq_thresholds[code]
                frequency_tiers.append({
                    "tier_code": code,
                    "tier_name": freq_names[code],
                    "order_threshold_min": min_o,
                    "order_threshold_max": max_o,
                    "user_count": freq_tier_map[code]["count"],
                })

        # 洞察
        insights = []
        top_segment = max(segments, key=lambda x: x["gsv_ratio"], default=None)
        if top_segment:
            insights.append(f"{top_segment['segment_name']}贡献{top_segment['gsv_ratio']*100:.1f}% GSV，是核心人群")
        s_count = value_tier_map.get("S", {}).get("count", 0)
        s_ratio = s_count / max(total_users, 1)
        insights.append(f"超级用户占比{s_ratio*100:.1f}%（{s_count}人），{'低于预期，建议加强高价值用户运营' if s_ratio < 0.03 else '符合预期'}")

        return {
            "analysis_date": analysis_date,
            "lookback_days": lookback_days,
            "value_tiers": value_tiers,
            "frequency_tiers": frequency_tiers,
            "segments": segments,
            "insights": insights,
        }

    finally:
        conn.close()
