"""
一键拆解服务 v2

基于历史数据自动完成大促拆解：
- 老客：按R区间（6档）× F段（F>1/F=1）逐层预估
- 新客：按渠道漏斗逐渠道预估
- 支持顺拆（现状→预估）和倒拆（目标→反推）两种模式
- 仅GSV口径

参考：[PROCEDURE] 芙清老客拆解四步法、[PROCEDURE] 芙清新客拆解、[PROCEDURE] 老客RFM分析四步法
"""

from typing import Dict, Any

from ._shared import (
    _get_r_interval_current_distribution,
    _get_ly_repurchase_by_r_interval,
    _get_new_customer_by_channel,
    _get_uv_reference,
    NEW_CUSTOMER_GROWTH_FACTOR,
)
from .suggestions import _generate_suggestions

from backend.semantic.calculations import safe_ratio


# ── 工具函数 ─────────────────────────────────────────────────


def _forward_breakdown(
    conn,
    target_gmv: float,
    activity_start: str,
    activity_end: str,
    ly_start: str,
    ly_end: str,
    old_customer_ratio_target: float,
    activity_type: str,
    adjustment: float
) -> Dict[str, Any]:
    """顺拆：从现状数据预估，计算目标gap"""

    # 1. 获取数据
    current_rf = _get_r_interval_current_distribution(conn, activity_start)
    ly_repurchase = _get_ly_repurchase_by_r_interval(conn, ly_start, ly_end)
    new_channel_data = _get_new_customer_by_channel(conn, ly_start, ly_end)
    uv_data = _get_uv_reference(conn, activity_start, activity_end)
    # 顺拆时：若当前活动期无UV数据，回退到去年同期UV作为参考
    if uv_data["uv"] == 0 and ly_start and ly_end:
        uv_data = _get_uv_reference(conn, ly_start, ly_end)

    # 2. 构建去年回购率/客单价查询字典
    ly_dict = {}
    for row in ly_repurchase:
        key = (row["r_interval"], row["f_segment"])
        ly_dict[key] = {
            "repurchase_rate": row["repurchase_rate"],
            "aus": row["aus"],
            "total_users": row["total_users"],
            "repurchased_users": row["repurchased_users"],
        }

    # 3. 老客预估：按R区间×F段逐层计算
    r_interval_breakdown = []
    old_total_estimate = 0.0
    total_old_users = 0

    for row in current_rf:
        r_interval = row["r_interval"]
        f_segment = row["f_segment"]
        user_count = row["user_count"]

        total_old_users += user_count

        ly = ly_dict.get((r_interval, f_segment), {
            "repurchase_rate": 0.03,
            "aus": 0,
            "total_users": 0,
            "repurchased_users": 0
        })

        # 预估回购率 = 去年回购率 × 活动调整系数（上限95%）
        est_rate = min(ly["repurchase_rate"] * adjustment, 0.95)
        # 预估客单价 = 去年客单价（有回购才有客单价参考）
        est_aus = ly["aus"] if ly["aus"] > 0 else 50.0

        est_gmv = user_count * est_rate * est_aus
        old_total_estimate += est_gmv

        r_interval_breakdown.append({
            "r_interval": r_interval,
            "f_segment": f_segment,
            "user_count": user_count,
            "ly_repurchase_rate": round(ly["repurchase_rate"], 4),
            "est_repurchase_rate": round(est_rate, 4),
            "est_aus": round(est_aus, 2),
            "est_gmv": round(est_gmv, 2),
            "ly_total_users": ly["total_users"],
            "ly_repurchased_users": ly["repurchased_users"],
        })

    old_target = target_gmv * old_customer_ratio_target
    old_gap = old_target - old_total_estimate

    # 4. 新客预估：按渠道漏斗
    new_channel_breakdown = []
    new_total_estimate = 0.0
    total_new_users = 0

    for ch in new_channel_data:
        channel = ch["channel"]
        ly_new_users = ch["new_users"] or 0
        ly_new_aus = ch["new_aus"] or 0

        est_new_users = int(ly_new_users * NEW_CUSTOMER_GROWTH_FACTOR)
        est_new_aus = ly_new_aus  # 新客客单价通常相对稳定
        est_new_gmv = est_new_users * est_new_aus

        new_total_estimate += est_new_gmv
        total_new_users += est_new_users

        new_channel_breakdown.append({
            "channel": channel,
            "ly_new_users": ly_new_users,
            "est_new_users": est_new_users,
            "ly_new_aus": round(ly_new_aus, 2),
            "est_new_aus": round(est_new_aus, 2),
            "est_new_gmv": round(est_new_gmv, 2),
        })

    new_target = target_gmv * (1 - old_customer_ratio_target)
    new_gap = new_target - new_total_estimate

    # 5. 总计
    total_estimate = old_total_estimate + new_total_estimate
    total_gap = target_gmv - total_estimate
    gap_ratio = safe_ratio(total_gap, target_gmv, 0)

    # 6. 补gap建议
    suggestions = _generate_suggestions(
        old_gap, old_target, new_gap, new_target, total_gap, target_gmv
    )

    return {
        "mode": "forward",
        "mode_label": "顺拆（从现状预估）",
        "target_gmv": round(target_gmv, 2),
        "total_estimate": round(total_estimate, 2),
        "total_gap": round(total_gap, 2),
        "gap_ratio": round(gap_ratio, 4),
        "old_customer": {
            "old_users_total": total_old_users,
            "old_gmv_estimate": round(old_total_estimate, 2),
            "old_gmv_target": round(old_target, 2),
            "old_gmv_gap": round(old_gap, 2),
            "r_interval_breakdown": r_interval_breakdown,
        },
        "new_customer": {
            "new_users_total": total_new_users,
            "new_gmv_estimate": round(new_total_estimate, 2),
            "new_gmv_target": round(new_target, 2),
            "new_gmv_gap": round(new_gap, 2),
            "channel_breakdown": new_channel_breakdown,
            "uv_reference": uv_data["uv"],
            "member_join_rate": uv_data["member_join_rate"],
        },
        "suggestions": suggestions,
        "activity_period": {"start": activity_start, "end": activity_end},
        "reference_period": {"start": ly_start, "end": ly_end},
        "meta": {
            "activity_type": activity_type,
            "repurchase_adjustment": adjustment,
            "metric_type": "GSV",
        },
        "breakdown_logic": {
            "old_customer_formula": "老客GMV = Σ(各R区间各F段人数 × 该区间去年回购率×活动系数 × 该区间去年客单价)",
            "old_customer_source": "参见 [PROCEDURE] 芙清老客拆解四步法、[PROCEDURE] 老客RFM分析四步法",
            "new_customer_formula": "新客GMV = Σ(各渠道去年新客人数×1.1 × 去年新客客单价)",
            "new_customer_source": "参见 [PROCEDURE] 芙清新客拆解、[PROCEDURE] 新客预估三步走",
        },
    }


# ── 主服务：倒拆 ──────────────────────────────────────────────
