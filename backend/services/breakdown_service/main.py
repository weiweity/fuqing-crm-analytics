"""
一键拆解服务 v2

基于历史数据自动完成大促拆解：
- 老客：按R区间（6档）× F段（F>1/F=1）逐层预估
- 新客：按渠道漏斗逐渠道预估
- 支持顺拆（现状→预估）和倒拆（目标→反推）两种模式
- 仅GSV口径

参考：[PROCEDURE] 芙清老客拆解四步法、[PROCEDURE] 芙清新客拆解、[PROCEDURE] 老客RFM分析四步法
"""

from typing import Optional, Dict, Any

from backend.db.connection import get_connection
from backend.config import REPURCHASE_ADJUSTMENT
from ._shared import (
    _detect_activity_type,
    _get_default_ly_dates,
)
from .forward import _forward_breakdown
from .reverse import _reverse_breakdown


# ── 工具函数 ─────────────────────────────────────────────────


def calculate_one_click_breakdown(
    target_gmv: float,
    activity_start: str,
    activity_end: str,
    last_year_start: Optional[str] = None,
    last_year_end: Optional[str] = None,
    old_customer_ratio_target: Optional[float] = 0.6,
    breakdown_mode: str = "forward",
) -> Dict[str, Any]:
    """
    一键拆解主函数

    Args:
        target_gmv: 全店GSV目标（元）
        activity_start: 活动开始日期 YYYY-MM-DD
        activity_end: 活动结束日期 YYYY-MM-DD
        last_year_start: 去年同期开始（可选，不传则自动推算）
        last_year_end: 去年同期结束（可选）
        old_customer_ratio_target: 老客占比目标（默认60%）
        breakdown_mode: 拆解模式 "forward"（顺拆）或 "reverse"（倒拆）

    Returns:
        拆解结果字典

    Note:
        仅支持GSV口径（is_refund=FALSE AND order_status!='交易关闭', 剔除购物金）
    """
    # 参数校验
    if breakdown_mode not in ("forward", "reverse"):
        raise ValueError(f"breakdown_mode must be 'forward' or 'reverse', got '{breakdown_mode}'")

    conn = get_connection()
    try:
        # 1. 自动推算去年同期
        if not last_year_start or not last_year_end:
            ly_start, ly_end = _get_default_ly_dates(activity_start, activity_end)
        else:
            ly_start, ly_end = last_year_start, last_year_end

        activity_type = _detect_activity_type(activity_start, activity_end)
        adjustment = REPURCHASE_ADJUSTMENT.get(activity_type, 1.1)

        if breakdown_mode == "forward":
            result = _forward_breakdown(
                conn, target_gmv, activity_start, activity_end,
                ly_start, ly_end, old_customer_ratio_target,
                activity_type, adjustment
            )
        else:
            result = _reverse_breakdown(
                conn, target_gmv, activity_start, activity_end,
                ly_start, ly_end, old_customer_ratio_target,
                activity_type, adjustment
            )

        return result

    finally:
        pass
