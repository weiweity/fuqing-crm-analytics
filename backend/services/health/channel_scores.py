"""
老客健康分析仪表盘 - 所有渠道健康评分对比

遍历 ACTIVE_UI_CHANNELS，分别计算各渠道的健康评分及同比。
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from backend.db.connection import get_connection
from backend.semantic.channels import ACTIVE_UI_CHANNELS, UI_TO_DB
from backend.services.health.overview import (
    _build_filter,
    _compute_repurchase_rate,
    _compute_product_repurchase_rate,
    _compute_old_customer_metrics,
    _compute_health_score,
    _compute_yoy_metrics,
    _compute_dynamic_targets,
)


ALL_UI_CHANNELS = ACTIVE_UI_CHANNELS


def get_channel_health_scores(
    analysis_date: str,
    period_days: int = 30,
    exclude_channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    计算所有渠道的健康评分（当期 + 去年同期 + YOY）

    Args:
        analysis_date: 分析日期 YYYY-MM-DD
        period_days: 分析周期天数
        exclude_channels: 排除渠道列表（如低价剔除）

    Returns:
        {
            "analysis_date": str,
            "period_days": int,
            "exclude_channels": Optional[List[str]],
            "scores": [
                {
                    "channel": str,        # UI 渠道名
                    "health_score": float,
                    "health_level": str,
                    "ly_health_score": float | None,
                    "health_score_yoy": float | None,
                },
                ...
            ]
        }
    """
    end_dt = datetime.strptime(analysis_date, "%Y-%m-%d").date()
    start_dt = end_dt - timedelta(days=period_days - 1)
    start_date = start_dt.strftime("%Y-%m-%d")
    end_date = analysis_date

    conn = get_connection()
    try:
        scores = []
        for ui_channel in ALL_UI_CHANNELS:
            # 如果该渠道在排除列表中，跳过
            if exclude_channels and ui_channel in exclude_channels:
                continue

            db_channel = UI_TO_DB.get(ui_channel, ui_channel)

            # 当期指标
            where_sql, params = _build_filter(exclude_channels, start_date, end_date, db_channel)
            repurchase_rate, period_repurchase_users, _ = _compute_repurchase_rate(conn, where_sql, params)
            product_rate = _compute_product_repurchase_rate(conn, where_sql, params)
            old_metrics = _compute_old_customer_metrics(conn, where_sql, params, start_date)

            # 动态目标（去年同周期实际值）
            ch_targets = _compute_dynamic_targets(conn, analysis_date, period_days, exclude_channels, db_channel)
            health_score, health_level = _compute_health_score(
                repurchase_rate,
                product_rate,
                old_metrics["old_customer_gsv_ratio"],
                old_metrics["old_customer_aus"],
                period_repurchase_users,
                period_days,
                targets=ch_targets,
            )

            # 去年同期
            yoy_prev = _compute_yoy_metrics(conn, analysis_date, period_days, exclude_channels, db_channel, targets=ch_targets)
            ly_health_score = yoy_prev.get("yoy_health_score")
            health_score_yoy = round(health_score - ly_health_score, 1) if ly_health_score is not None else None

            scores.append({
                "channel": ui_channel,
                "health_score": health_score,
                "health_level": health_level,
                "ly_health_score": ly_health_score,
                "health_score_yoy": health_score_yoy,
            })

        # 全店（不指定渠道）
        where_sql, params = _build_filter(exclude_channels, start_date, end_date, None)
        repurchase_rate, period_repurchase_users, _ = _compute_repurchase_rate(conn, where_sql, params)
        product_rate = _compute_product_repurchase_rate(conn, where_sql, params)
        old_metrics = _compute_old_customer_metrics(conn, where_sql, params, start_date)
        all_targets = _compute_dynamic_targets(conn, analysis_date, period_days, exclude_channels, None)
        health_score, health_level = _compute_health_score(
            repurchase_rate,
            product_rate,
            old_metrics["old_customer_gsv_ratio"],
            old_metrics["old_customer_aus"],
            period_repurchase_users,
            period_days,
            targets=all_targets,
        )
        yoy_prev = _compute_yoy_metrics(conn, analysis_date, period_days, exclude_channels, None, targets=all_targets)
        ly_health_score = yoy_prev.get("yoy_health_score")
        health_score_yoy = round(health_score - ly_health_score, 1) if ly_health_score is not None else None

        scores.insert(0, {
            "channel": "全店",
            "health_score": health_score,
            "health_level": health_level,
            "ly_health_score": ly_health_score,
            "health_score_yoy": health_score_yoy,
        })

        return {
            "analysis_date": analysis_date,
            "period_days": period_days,
            "exclude_channels": exclude_channels,
            "scores": scores,
        }
    finally:
        pass
