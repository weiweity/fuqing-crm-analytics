"""
芙清 CRM - 统一计算规则

本文件是所有 YOY、占比、MOM 等计算规则的唯一真实来源。
任何计算逻辑的修改必须在此修改，所有 Service 调用此处函数。

计算规则 (Sprint 13 更新):
1. 绝对值 YOY：(当年 - 去年) / 去年 * 100 → 百分比数值 (已 *100, e.g. 25.0 = +25%)
2. 占比/比率 YOY：(当年 - 去年) * 100 → pp 数值 (已 *100, e.g. 5.0 = +5pp)
3. 回购率 YOY：当年回购率 - 去年回购率 → pp 数值 (已 *100)

调用契约:
- yoy_absolute() 返回 percentage (已 *100, 25.0 = 25%)
- yoy_ratio() / yoy_repurchase_rate() / mom_ratio() 返回 pp 数值 (已 *100, 5.0 = 5pp)
- 前端 caller 不要再 *100, 直接 pass-through 给 YOYBadge / MetricCard
- 命名约定: *_ratio (0-1 decimal) / *_pct (percentage 已 *100) / *_ppt (pp 差已 *100)
"""

from typing import Optional


# ============================================================
# GSV 口径 SQL 表达式（单一数据源）
# ============================================================
GSV_AMOUNT_COL: str = """
    CASE WHEN is_refund = FALSE AND order_status != '交易关闭'
         THEN actual_amount ELSE 0 END
""".strip()


def yoy_absolute(cur: Optional[float], comp: Optional[float]) -> Optional[float]:
    """
    绝对值 YOY（金额、人数、客单价等）

    公式：(cur - comp) / comp
    单位：比例（乘100变为百分比）

    Example:
        GSV YOY = (100 - 80) / 80 = 0.25 (即 25%)
    """
    try:
        cur_f = float(cur) if cur is not None else 0.0
        comp_f = float(comp) if comp is not None else 0.0
        if abs(comp_f) > 1e-6:
            return round((cur_f - comp_f) / comp_f * 100, 2)
    except (TypeError, ValueError):
        pass
    return None


def yoy_ratio(cur: Optional[float], comp: Optional[float]) -> Optional[float]:
    """
    占比/比率 YOY（老客占比、会员占比、回购率等）

    公式：cur - comp
    单位：百分点差（pp）

    Example:
        老客占比 YOY = 0.60 - 0.55 = 0.05 (即 +5pp)
    """
    try:
        cur_f = float(cur) if cur is not None else 0.0
        comp_f = float(comp) if comp is not None else 0.0
        return round((cur_f - comp_f) * 100, 2)
    except (TypeError, ValueError):
        pass
    return None


def yoy_repurchase_rate(cur: Optional[float], comp: Optional[float]) -> Optional[float]:
    """
    回购率 YOY（与 yoy_ratio 相同，语义区分）

    公式：cur - comp
    单位：百分点差（pp）

    Example:
        回购率 YOY = 0.35 - 0.30 = 0.05 (即 +5pp)
    """
    return yoy_ratio(cur, comp)


def mom_absolute(cur: Optional[float], prev: Optional[float]) -> Optional[float]:
    """
    绝对值 MOM（环比）

    公式：(cur - prev) / prev
    单位：比例（乘100变为百分比）
    """
    try:
        cur_f = float(cur) if cur is not None else 0.0
        prev_f = float(prev) if prev is not None else 0.0
        if prev_f != 0:
            return round((cur_f - prev_f) / prev_f * 100, 2)
    except (TypeError, ValueError):
        pass
    return None


def mom_ratio(cur: Optional[float], prev: Optional[float]) -> Optional[float]:
    """
    占比/比率 MOM（环比）

    公式：cur - prev
    单位：百分点差（pp）
    """
    try:
        cur_f = float(cur) if cur is not None else 0.0
        prev_f = float(prev) if prev is not None else 0.0
        return round((cur_f - prev_f) * 100, 2)
    except (TypeError, ValueError):
        pass
    return None


def safe_ratio(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    安全除法（避免除零）

    Args:
        numerator: 分子
        denominator: 分母
        default: 分母为0时的默认值

    Returns:
        numerator / denominator 或 default
    """
    return numerator / denominator if denominator != 0 else default


def percentage_to_ratio(percent: float) -> float:
    """
    百分比转小数（存储用）

    Example:
        60% → 0.60
    """
    return percent / 100


def ratio_to_percentage(ratio: float) -> float:
    """
    小数转百分比（展示用）

    Example:
        0.60 → 60
    """
    return ratio * 100
