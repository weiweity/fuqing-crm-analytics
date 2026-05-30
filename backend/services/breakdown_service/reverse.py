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

# ── 工具函数 ─────────────────────────────────────────────────


def _reverse_breakdown(
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
    """倒拆：从目标反推各R区间所需人数/UV/派样量"""

    # 1. 获取数据
    current_rf = _get_r_interval_current_distribution(conn, activity_start)
    ly_repurchase = _get_ly_repurchase_by_r_interval(conn, ly_start, ly_end)
    new_channel_data = _get_new_customer_by_channel(conn, ly_start, ly_end)
    uv_data = _get_uv_reference(conn, activity_start, activity_end)

    # 2. 构建字典
    ly_dict = {}
    for row in ly_repurchase:
        key = (row["r_interval"], row["f_segment"])
        ly_dict[key] = {
            "repurchase_rate": row["repurchase_rate"],
            "aus": row["aus"],
            "total_users": row["total_users"],
        }

    # 3. 老客倒拆：先计算去年老客GMV各区间占比，按占比拆分目标
    # 先跑一遍顺推算去年GMV结构
    ly_old_gmv_by_interval = {}
    ly_old_gmv_total = 0.0

    for row in current_rf:
        key = (row["r_interval"], row["f_segment"])
        ly = ly_dict.get(key, {"repurchase_rate": 0.03, "aus": 0, "total_users": 0})
        interval_gmv = row["user_count"] * ly["repurchase_rate"] * (ly["aus"] if ly["aus"] > 0 else 50.0)
        ly_old_gmv_by_interval[key] = interval_gmv
        ly_old_gmv_total += interval_gmv

    old_target = target_gmv * old_customer_ratio_target

    r_interval_breakdown = []
    total_old_users = 0

    for row in current_rf:
        r_interval = row["r_interval"]
        f_segment = row["f_segment"]
        user_count = row["user_count"]
        total_old_users += user_count

        key = (r_interval, f_segment)
        ly = ly_dict.get(key, {"repurchase_rate": 0.03, "aus": 0, "total_users": 0})
        est_rate = min(ly["repurchase_rate"] * adjustment, 0.95)
        est_aus = ly["aus"] if ly["aus"] > 0 else 50.0

        # 按去年GMV占比拆分老客目标
        if ly_old_gmv_total > 0:
            interval_share = ly_old_gmv_by_interval.get(key, 0) / ly_old_gmv_total
        else:
            interval_share = 1.0 / len(current_rf) if current_rf else 0

        interval_target = old_target * interval_share
        # 反推所需人数 = 目标GMV / (回购率 × 客单价)
        needed_users = int(interval_target / (est_rate * est_aus)) if (est_rate * est_aus) > 0 else 0
        user_gap = needed_users - user_count

        r_interval_breakdown.append({
            "r_interval": r_interval,
            "f_segment": f_segment,
            "current_users": user_count,
            "est_repurchase_rate": round(est_rate, 4),
            "est_aus": round(est_aus, 2),
            "interval_target_gmv": round(interval_target, 2),
            "needed_users": needed_users,
            "user_gap": user_gap,
            "ly_repurchase_rate": round(ly["repurchase_rate"], 4),
            "ly_total_users": ly["total_users"],
        })

    # 4. 新客倒拆：按渠道漏斗占比拆分新客目标
    new_target = target_gmv * (1 - old_customer_ratio_target)
    ly_new_gmv_total = sum(ch["new_gmv"] or 0 for ch in new_channel_data)

    new_channel_breakdown = []
    total_new_users = 0

    for ch in new_channel_data:
        channel = ch["channel"]
        ly_new_gmv = ch["new_gmv"] or 0
        ly_new_aus = ch["new_aus"] or 50.0
        ly_new_users = ch["new_users"] or 0

        if ly_new_gmv_total > 0:
            channel_share = ly_new_gmv / ly_new_gmv_total
        else:
            channel_share = 1.0 / len(new_channel_data) if new_channel_data else 0

        channel_target = new_target * channel_share
        needed_users = int(channel_target / ly_new_aus) if ly_new_aus > 0 else 0
        user_gap = needed_users - int(ly_new_users * NEW_CUSTOMER_GROWTH_FACTOR)

        total_new_users += needed_users
        new_channel_breakdown.append({
            "channel": channel,
            "ly_new_users": ly_new_users,
            "ly_new_aus": round(ly_new_aus, 2),
            "channel_target_gmv": round(channel_target, 2),
            "needed_users": needed_users,
            "user_gap": user_gap,
        })

    # 5. 新客倒推到UV：所需UV = 新客目标 / (客单价 × 入会率 × 首单转化率)
    # 简化：所需新客人数 / 入会率 ≈ 所需UV
    estimated_conversion = 0.4  # 新客首单转化率参考
    needed_uv = int(total_new_users / (uv_data["member_join_rate"] * estimated_conversion)) if uv_data["member_join_rate"] > 0 else 0
    uv_gap = needed_uv - uv_data["uv"]

    # 6. 补gap建议
    suggestions = []
    # 老客缺口建议
    old_total_gap = sum(item["user_gap"] for item in r_interval_breakdown if item["user_gap"] > 0)
    if old_total_gap > 0:
        old_suggestions = ["建议加大老客触达力度，提升回购率"]
        for item in r_interval_breakdown:
            if item["user_gap"] > 0 and item["user_gap"] > item["current_users"] * 0.3:
                old_suggestions.append(f"{item['r_interval']}({item['f_segment']})缺口较大，建议针对性加深offer或增加触达轮次")
            elif item["r_interval"] in ("近7-12个月已购客", "近13-24个月已购客", "2年外已购客") and item["user_gap"] > 0:
                old_suggestions.append(f"{item['r_interval']}沉睡人群缺口，建议发送唤醒券")
        suggestions.append({
            "dimension": "老客",
            "gap_users": old_total_gap,
            "suggestions": old_suggestions,
            "priority": "P0" if old_total_gap > total_old_users * 0.2 else "P1"
        })

    # 新客缺口建议
    new_total_gap_users = sum(item["user_gap"] for item in new_channel_breakdown if item["user_gap"] > 0)
    if new_total_gap_users > 0 or uv_gap > 0:
        new_suggestions = []
        if uv_gap > 0:
            new_suggestions.append(f"UV缺口{uv_gap:,}，建议加大派样力度（U先/小美盒）或增加付费推广")
        new_suggestions.append("提升入会率：优化入会引导、增加0.01特权钩子")
        suggestions.append({
            "dimension": "新客",
            "gap_users": new_total_gap_users,
            "uv_gap": uv_gap,
            "suggestions": new_suggestions,
            "priority": "P0" if uv_gap > uv_data["uv"] * 0.3 else "P1"
        })

    return {
        "mode": "reverse",
        "mode_label": "倒拆（从目标反推）",
        "target_gmv": round(target_gmv, 2),
        "total_estimate": None,  # 倒拆不输出预估，直接给所需
        "total_gap": None,
        "gap_ratio": None,
        "old_customer": {
            "old_users_total": total_old_users,
            "old_gmv_target": round(old_target, 2),
            "r_interval_breakdown": r_interval_breakdown,
        },
        "new_customer": {
            "new_gmv_target": round(new_target, 2),
            "channel_breakdown": new_channel_breakdown,
            "uv_reference": uv_data["uv"],
            "member_join_rate": uv_data["member_join_rate"],
            "needed_uv": needed_uv,
            "uv_gap": uv_gap,
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
            "old_customer_formula": "老客目标 → 按去年各R区间GMV占比拆分 → 反推各区所需人数 = 目标GMV/(回购率×客单价) → gap = 所需-现状",
            "old_customer_source": "参见 [PROCEDURE] 芙清老客拆解四步法、[PROCEDURE] 老客RFM分析四步法",
            "new_customer_formula": "新客目标 → 按去年各渠道GMV占比拆分 → 反推所需UV = 新客目标/(客单价×入会率×转化率)",
            "new_customer_source": "参见 [PROCEDURE] 芙清新客拆解、[PROCEDURE] 新客预估三步走、[PROCEDURE] 会员招募量预估三方法",
        },
    }


# ── 补gap建议生成 ─────────────────────────────────────────────
