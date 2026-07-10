"""
Sample CRM - 统一计算规则 (L4.81 治本: no *100 契约)

本文件是所有 YOY、占比、MOM 等计算规则的唯一真实来源。
任何计算逻辑的修改必须在此修改，所有 Service 调用此处函数。

计算规则 (L4.81 治本, user 7/10 拍板):
1. 绝对值 YOY：(当年 - 去年) / 去年 → 原始 ratio (no *100, e.g. 0.25 = +25% / 100)
2. 占比/比率 YOY：(当年 - 去年) → 原始 ratio 差 (no *100, e.g. 0.05 = +5pp / 100)
3. 回购率 YOY：当年回购率 - 去年回购率 → 原始 ratio 差 (no *100)
4. MOM 跟 YOY 1:1 stable 沿用

调用契约 (跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用):
- yoy_absolute() 返回 raw ratio (no *100, 0.25 = +25% / 100, frontend caller *100 显示)
- yoy_ratio() / yoy_repurchase_rate() / mom_ratio() 返回 raw ratio 差 (no *100, 0.05 = +5pp / 100, frontend caller *100 显示)
- 前端 caller (YOYBadge / MetricCard / Excel 导出) 必 *100 显示
- 命名约定: *_ratio (raw 0-1 decimal, no *100) / *_pct (frontend *100 后) / *_ppt (frontend *100 后)
- 治本真因 (跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用):
  - 旧契约: backend *100, frontend 直接显示 → backend 责任过重, frontend 看不到 *100
  - 新契约: backend no *100, frontend *100 显示 → frontend 责任, display 灵活 (YOYBadge unit: 'pp' / '%' / 'raw' 灵活)
  - 跟 user "我需要的是 pp, 然后不要 *100" 1:1 stable 永久规则化沿用
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
    单位：raw ratio (no *100, e.g. 0.25 = +25% / 100, frontend caller *100 显示)

    L4.81 治本契约变更:
    - 旧 (已废): round((cur - comp) / comp * 100, 2) 返回 25.0 (+25%)
    - 新 (L4.81): round((cur - comp) / comp, 4) 返回 0.25 (+25% / 100)
    - frontend YOYBadge / MetricCard / Excel 导出 必 *100 显示

    Example:
        GSV YOY = (100 - 80) / 80 = 0.25 (frontend *100 = +25%)
    """
    try:
        cur_f = float(cur) if cur is not None else 0.0
        comp_f = float(comp) if comp is not None else 0.0
        if abs(comp_f) > 1e-6:
            return round((cur_f - comp_f) / comp_f, 4)
    except (TypeError, ValueError):
        pass
    return None


def yoy_ratio(cur: Optional[float], comp: Optional[float]) -> Optional[float]:
    """
    占比/比率 YOY（老客占比、会员占比、回购率等）

    公式：cur - comp
    单位：raw ratio 差 (no *100, e.g. 0.05 = +5pp / 100, frontend caller *100 显示)

    L4.81 治本契约变更:
    - 旧 (已废): round((cur - comp) * 100, 2) 返回 5.0 (+5pp)
    - 新 (L4.81): round((cur - comp), 4) 返回 0.05 (+5pp / 100)
    - frontend YOYBadge / MetricCard / Excel 导出 必 *100 显示 (unit: 'pp' / 'raw' 灵活)

    Example:
        老客占比 YOY = 0.60 - 0.55 = 0.05 (frontend *100 = +5pp)
    """
    try:
        cur_f = float(cur) if cur is not None else 0.0
        comp_f = float(comp) if comp is not None else 0.0
        return round((cur_f - comp_f), 4)
    except (TypeError, ValueError):
        pass
    return None


def yoy_repurchase_rate(cur: Optional[float], comp: Optional[float]) -> Optional[float]:
    """
    回购率 YOY（与 yoy_ratio 相同，语义区分）

    公式：cur - comp
    单位：raw ratio 差 (no *100, e.g. 0.05 = +5pp / 100, frontend caller *100 显示)

    L4.81 治本契约变更: 跟 yoy_ratio 1:1 stable 沿用, no *100
    """
    return yoy_ratio(cur, comp)


def mom_absolute(cur: Optional[float], prev: Optional[float]) -> Optional[float]:
    """
    绝对值 MOM（环比）

    公式：(cur - prev) / prev
    单位：raw ratio (no *100, e.g. 0.25 = +25% / 100, frontend caller *100 显示)

    L4.81 治本契约变更: 跟 yoy_absolute 1:1 stable 沿用, no *100
    """
    try:
        cur_f = float(cur) if cur is not None else 0.0
        prev_f = float(prev) if prev is not None else 0.0
        if prev_f != 0:
            return round((cur_f - prev_f) / prev_f, 4)
    except (TypeError, ValueError):
        pass
    return None


def mom_ratio(cur: Optional[float], prev: Optional[float]) -> Optional[float]:
    """
    占比/比率 MOM（环比）

    公式：cur - prev
    单位：raw ratio 差 (no *100, e.g. 0.05 = +5pp / 100, frontend caller *100 显示)

    L4.81 治本契约变更: 跟 yoy_ratio 1:1 stable 沿用, no *100
    """
    try:
        cur_f = float(cur) if cur is not None else 0.0
        prev_f = float(prev) if prev is not None else 0.0
        return round((cur_f - prev_f), 4)
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
    # 防御 NoneType (Sprint 201 R1 v2.1 followup: pre-existing NoneType 阻塞 CI -x, 跟 dual_conn 0 关联)
    if numerator is None or denominator is None:
        return default
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
